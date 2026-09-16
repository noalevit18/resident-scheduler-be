import logging
import re
import time
from datetime import date
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.models import Constraint, MonthlyConstraintsVersion
from app.schemas.schemas import ConstraintEntry

logger = logging.getLogger(__name__)

MONTH_PATTERN = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def month_bounds(month: str) -> Tuple[date, date]:
    """Given "YYYY-MM", returns (first_of_month, first_of_next_month) as
    Date objects, for filtering a Date column with a half-open range."""
    year, mon = (int(p) for p in month.split("-"))
    start = date(year, mon, 1)
    end = date(year + 1, 1, 1) if mon == 12 else date(year, mon + 1, 1)
    return start, end


class VersionConflictError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


class ConstraintRepository:
    """The `constraints` table is insert-only. Its "current version" for a
    given unit+month is tracked explicitly in `monthly_constraints_versions`,
    not inferred from the rows themselves — every save copies forward any
    date's rows it didn't touch, so each version is always a complete
    snapshot of the month, and a date with zero rows at the current version
    unambiguously has no constraints."""

    def __init__(self, db: Session):
        self.db = db

    def _get_version_row(self, unit_id: UUID, month: str, for_update: bool = False):
        query = self.db.query(MonthlyConstraintsVersion).filter(
            MonthlyConstraintsVersion.unit_id == unit_id, MonthlyConstraintsVersion.month == month,
        )
        if for_update:
            query = query.with_for_update()
        return query.first()

    def get_by_month(self, unit_id: UUID, month: str) -> List[Constraint]:
        version_row = self._get_version_row(unit_id, month)
        if not version_row:
            return []
        return self.get_by_version(unit_id, month, version_row.version)

    def get_version_history(self, unit_id: UUID, month: str):
        start, end = month_bounds(month)
        return (
            self.db.query(
                func.min(Constraint.id).label("id"),
                Constraint.version,
                Constraint.created_at,
                Constraint.created_by,
            )
            .filter(Constraint.unit_id == unit_id, Constraint.date >= start, Constraint.date < end)
            .group_by(Constraint.version, Constraint.created_at, Constraint.created_by)
            .order_by(Constraint.created_at.desc())
            .all()
        )

    def get_by_version(self, unit_id: UUID, month: str, version: int) -> List[Constraint]:
        start, end = month_bounds(month)
        return (
            self.db.query(Constraint)
            .filter(Constraint.unit_id == unit_id, Constraint.date >= start, Constraint.date < end, Constraint.version == version)
            .order_by(Constraint.date, Constraint.type_id)
            .all()
        )

    def get_by_version_id(self, unit_id: UUID, month: str, version: int) -> List[Constraint]:
        start, end = month_bounds(month)
        anchor = (
            self.db.query(Constraint.version)
            .filter(Constraint.version == version, Constraint.unit_id == unit_id, Constraint.date >= start, Constraint.date < end)
            .first()
        )
        if not anchor:
            return []
        return self.get_by_version(unit_id, month, anchor.version)

    def save_entries_snapshot(
        self, unit_id: UUID, month: str, entries: List[ConstraintEntry], created_by: Optional[UUID],
        carry_forward_untouched: bool = True,
        submitted_staff_member_ids_by_key: Optional[dict] = None,
    ):
        start, end = month_bounds(month)
        touched_dates = {e.date for e in entries}
        touched_keys = {(e.type_id, e.date) for e in entries}
        submitted_staff_member_ids_by_key = submitted_staff_member_ids_by_key or {}
        t_start = time.perf_counter()

        for _ in range(3):  # retry only covers the race on this month's very first-ever save
            t0 = time.perf_counter()
            version_row = self._get_version_row(unit_id, month, for_update=True)
            lock_ms = (time.perf_counter() - t0) * 1000
            current_version = version_row.version if version_row else 0
            next_version = current_version + 1

            existing_by_key = {}
            carry_forward = []
            tombstoned = []
            carry_ms = 0.0
            if version_row:
                t0 = time.perf_counter()
                existing = (
                    self.db.query(Constraint)
                    .filter(Constraint.unit_id == unit_id, Constraint.date >= start, Constraint.date < end, Constraint.version == current_version)
                    .all()
                )
                carry_ms = (time.perf_counter() - t0) * 1000
                existing_by_key = {(r.type_id, r.date): r for r in existing}
                if carry_forward_untouched:
                    carry_forward = [r for r in existing if r.date not in touched_dates]
                    # A type omitted on an otherwise-touched date is being
                    # deleted (see docstring) — but if it has submission
                    # history, keep the row (staff cleared) instead of
                    # dropping it outright, so that history isn't lost
                    # along with the admin's deletion.
                    tombstoned = [
                        r for r in existing
                        if r.date in touched_dates and (r.type_id, r.date) not in touched_keys
                        and r.submitted_staff_member_ids
                    ]

            def prior_submitted_ids(type_id, entry_date):
                prior = existing_by_key.get((type_id, entry_date))
                return prior.submitted_staff_member_ids if prior else []

            rows = [
                Constraint(
                    unit_id=unit_id, type_id=r.type_id, date=r.date,
                    staff_member_ids=r.staff_member_ids,
                    submitted_staff_member_ids=r.submitted_staff_member_ids,
                    version=next_version, created_by=created_by,
                )
                for r in carry_forward
            ] + [
                Constraint(
                    unit_id=unit_id, type_id=r.type_id, date=r.date,
                    staff_member_ids=[],
                    submitted_staff_member_ids=r.submitted_staff_member_ids,
                    version=next_version, created_by=created_by,
                )
                for r in tombstoned
            ] + [
                Constraint(
                    unit_id=unit_id, type_id=e.type_id, date=e.date,
                    staff_member_ids=e.staff_member_ids,
                    submitted_staff_member_ids=submitted_staff_member_ids_by_key.get(
                        (e.type_id, e.date), prior_submitted_ids(e.type_id, e.date),
                    ),
                    version=next_version, created_by=created_by,
                )
                for e in entries
            ]
            self.db.add_all(rows)

            if version_row:
                version_row.version = next_version
            else:
                self.db.add(MonthlyConstraintsVersion(unit_id=unit_id, month=month, version=next_version))

            try:
                t0 = time.perf_counter()
                self.db.commit()
                commit_ms = (time.perf_counter() - t0) * 1000
                logger.info(
                    "save_entries_snapshot timing (unit_id=%s, month=%s, rows=%d): "
                    "lock_version=%.0fms carry_forward_read=%.0fms commit=%.0fms total=%.0fms",
                    unit_id, month, len(rows), lock_ms, carry_ms, commit_ms, (time.perf_counter() - t_start) * 1000,
                )
                return rows
            except IntegrityError:
                self.db.rollback()
        raise VersionConflictError("constraints_version_conflict", "Concurrent update detected — please retry")
