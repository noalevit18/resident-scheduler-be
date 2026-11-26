import logging
import time
from datetime import date
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.models import MonthlyOnCallConstraintsVersion, OnCallConstraint
from app.repositories.constraint_repository import month_bounds
from app.schemas.schemas import OnCallConstraintEntry

logger = logging.getLogger(__name__)

# A row's identity within a version: (type_id, preference, date) — exactly
# one of type_id / preference is set.
OnCallConstraintKey = Tuple[Optional[int], Optional[int], date]


def row_key(type_id: Optional[int], preference: Optional[int], entry_date: date) -> OnCallConstraintKey:
    return (type_id, preference, entry_date)


class OnCallConstraintRepository:
    """The `on_call_constraints` table is insert-only, versioned exactly like
    `constraints` (see ConstraintRepository): the current version of a
    unit+month is tracked in `monthly_on_call_constraints_versions`, and
    every save copies forward the dates it didn't touch, so each version is
    a complete snapshot of the month. Versions are shared on-call scheduling
    versions, so a unit's numbers can skip."""

    def __init__(self, db: Session):
        self.db = db

    def _get_version_row(self, unit_id: UUID, month: str, for_update: bool = False):
        query = self.db.query(MonthlyOnCallConstraintsVersion).filter(
            MonthlyOnCallConstraintsVersion.unit_id == unit_id, MonthlyOnCallConstraintsVersion.month == month,
        )
        if for_update:
            query = query.with_for_update()
        return query.first()

    def get_by_month(self, unit_id: UUID, month: str) -> List[OnCallConstraint]:
        version_row = self._get_version_row(unit_id, month)
        if not version_row:
            return []
        return self.get_by_version(unit_id, month, version_row.version)

    def get_by_version(self, unit_id: UUID, month: str, version: int) -> List[OnCallConstraint]:
        start, end = month_bounds(month)
        return (
            self.db.query(OnCallConstraint)
            .filter(
                OnCallConstraint.unit_id == unit_id, OnCallConstraint.date >= start, OnCallConstraint.date < end,
                OnCallConstraint.version == version,
            )
            .order_by(OnCallConstraint.date, OnCallConstraint.type_id, OnCallConstraint.preference)
            .all()
        )

    def get_version_history(self, unit_id: UUID, month: str):
        start, end = month_bounds(month)
        return (
            self.db.query(
                func.min(OnCallConstraint.id).label("id"),
                OnCallConstraint.version,
                OnCallConstraint.created_at,
                OnCallConstraint.created_by,
            )
            .filter(OnCallConstraint.unit_id == unit_id, OnCallConstraint.date >= start, OnCallConstraint.date < end)
            .group_by(OnCallConstraint.version, OnCallConstraint.created_at, OnCallConstraint.created_by)
            .order_by(OnCallConstraint.created_at.desc())
            .all()
        )

    def save_entries_snapshot(
        self, unit_id: UUID, month: str, entries: List[OnCallConstraintEntry], created_by: Optional[UUID],
        version: int,
        carry_forward_untouched: bool = True,
        submitted_staff_member_ids_by_key: Optional[dict] = None,
    ) -> List[OnCallConstraint]:
        """Writes the month at `version` (a shared on-call scheduling version), without committing — the caller
        commits with the rest of the version. A date present in `entries` is
        replaced by exactly its entries; any other date is carried forward
        unchanged (unless carry_forward_untouched=False, used by pull, whose
        entries already are the whole month). A value dropped from a touched
        date is kept as an empty "tombstone" row if it has submission
        history, so that provenance isn't lost along with the deletion."""
        start, end = month_bounds(month)
        touched_dates = {e.date for e in entries}
        touched_keys = {row_key(e.type_id, e.preference, e.date) for e in entries}
        submitted_staff_member_ids_by_key = submitted_staff_member_ids_by_key or {}
        t_start = time.perf_counter()

        version_row = self._get_version_row(unit_id, month, for_update=True)
        existing_by_key = {}
        carry_forward = []
        tombstoned = []
        if version_row:
            existing = (
                self.db.query(OnCallConstraint)
                .filter(
                    OnCallConstraint.unit_id == unit_id, OnCallConstraint.date >= start,
                    OnCallConstraint.date < end, OnCallConstraint.version == version_row.version,
                )
                .all()
            )
            existing_by_key = {row_key(r.type_id, r.preference, r.date): r for r in existing}
            if carry_forward_untouched:
                carry_forward = [r for r in existing if r.date not in touched_dates]
                tombstoned = [
                    r for r in existing
                    if r.date in touched_dates
                    and row_key(r.type_id, r.preference, r.date) not in touched_keys
                    and r.submitted_staff_member_ids
                ]

        def prior_submitted_ids(key: OnCallConstraintKey):
            prior = existing_by_key.get(key)
            return prior.submitted_staff_member_ids if prior else []

        rows = [
            OnCallConstraint(
                unit_id=unit_id, date=r.date, type_id=r.type_id, preference=r.preference,
                staff_member_ids=r.staff_member_ids, submitted_staff_member_ids=r.submitted_staff_member_ids,
                version=version, created_by=created_by,
            )
            for r in carry_forward
        ] + [
            OnCallConstraint(
                unit_id=unit_id, date=r.date, type_id=r.type_id, preference=r.preference,
                staff_member_ids=[], submitted_staff_member_ids=r.submitted_staff_member_ids,
                version=version, created_by=created_by,
            )
            for r in tombstoned
        ] + [
            OnCallConstraint(
                unit_id=unit_id, date=e.date, type_id=e.type_id, preference=e.preference,
                staff_member_ids=e.staff_member_ids,
                submitted_staff_member_ids=submitted_staff_member_ids_by_key.get(
                    row_key(e.type_id, e.preference, e.date),
                    prior_submitted_ids(row_key(e.type_id, e.preference, e.date)),
                ),
                version=version, created_by=created_by,
            )
            for e in entries
        ]
        self.db.add_all(rows)

        if version_row:
            version_row.version = version
        else:
            self.db.add(MonthlyOnCallConstraintsVersion(unit_id=unit_id, month=month, version=version))
        logger.info(
            "Saved on-call constraints snapshot version %d (unit_id=%s, month=%s, rows=%d) in %.0fms",
            version, unit_id, month, len(rows), (time.perf_counter() - t_start) * 1000,
        )
        return rows
