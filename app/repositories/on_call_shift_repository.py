import logging
import re
from datetime import date
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.models import OnCallShift, MonthOnCallVersion
from app.repositories.constraint_repository import VersionConflictError
from app.schemas.schemas import OnCallShiftEntry

logger = logging.getLogger(__name__)

MONTH_PATTERN = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def month_bounds(month: str) -> Tuple[date, date]:
    """Given "YYYY-MM", returns (first_of_month, first_of_next_month) as
    Date objects, for filtering a Date column with a half-open range."""
    year, mon = (int(p) for p in month.split("-"))
    start = date(year, mon, 1)
    end = date(year + 1, 1, 1) if mon == 12 else date(year, mon + 1, 1)
    return start, end


class OnCallVersionConflictError(VersionConflictError):
    """A concurrent save took the version being written (409)."""


def _keys_to_str(assignments: dict) -> dict:
    return {str(k): v for k, v in assignments.items()}


class OnCallShiftRepository:
    """The `on_call_shifts` table is insert-only. One OnCallShift row IS the whole
    date's map of staff_member_id -> on_call_station_id — so a touched
    date's map is replaced wholesale, there's no per-key tombstone case."""

    def __init__(self, db: Session):
        self.db = db

    def _get_latest_version_row(self, unit_id: UUID, month: str, for_update: bool = False) -> Optional[MonthOnCallVersion]:
        """`monthly_on_call_versions` is insert-only (one row per version,
        never updated in place) — "the current version" is whichever row
        has the highest `version` number. Locking this row (for_update)
        during a save still serializes concurrent writers the same way
        locking the old single mutable row did."""
        query = self.db.query(MonthOnCallVersion).filter(
            MonthOnCallVersion.unit_id == unit_id, MonthOnCallVersion.month == month,
        ).order_by(MonthOnCallVersion.version.desc())
        if for_update:
            query = query.with_for_update()
        return query.first()

    def get_version_status(self, unit_id: UUID, month: str) -> Optional[MonthOnCallVersion]:
        """Exposes the current (latest) version + is_published flag for a unit+month."""
        return self._get_latest_version_row(unit_id, month)

    def get_by_month(self, unit_id: UUID, month: str) -> List[OnCallShift]:
        version_row = self._get_latest_version_row(unit_id, month)
        if not version_row:
            return []
        return self.get_by_version(unit_id, month, version_row.version)

    def get_version_history(self, unit_id: UUID, month: str) -> List[MonthOnCallVersion]:
        """Every version ever saved for this unit+month, each with its own
        is_published/published_at/published_by — newest first."""
        return (
            self.db.query(MonthOnCallVersion)
            .filter(MonthOnCallVersion.unit_id == unit_id, MonthOnCallVersion.month == month)
            .order_by(MonthOnCallVersion.version.desc())
            .all()
        )

    def get_by_version(self, unit_id: UUID, month: str, version: int) -> List[OnCallShift]:
        start, end = month_bounds(month)
        return (
            self.db.query(OnCallShift)
            .filter(OnCallShift.unit_id == unit_id, OnCallShift.date >= start, OnCallShift.date < end, OnCallShift.version == version)
            .order_by(OnCallShift.date)
            .all()
        )

    def publish_version(
        self, unit_id: UUID, month: str, version: int, published_by: Optional[UUID],
    ) -> MonthOnCallVersion:
        """Marks an already-saved version as published in place — no new
        version row is created, unlike save_entries_snapshot."""
        row = (
            self.db.query(MonthOnCallVersion)
            .filter(
                MonthOnCallVersion.unit_id == unit_id,
                MonthOnCallVersion.month == month,
                MonthOnCallVersion.version == version,
            )
            .with_for_update()
            .first()
        )
        if not row:
            raise ValueError(f"On-call version {version} not found for {month}")
        row.is_published = True
        row.published_at = date.today()
        row.published_by = published_by
        self.db.commit()
        self.db.refresh(row)
        return row

    def unpublish_versions(self, unit_ids: List[UUID], month: str, version: int) -> List[MonthOnCallVersion]:
        """Clears the units' rosters' published state at `version` in place, together; returns the rows found."""
        rows = (
            self.db.query(MonthOnCallVersion)
            .filter(
                MonthOnCallVersion.unit_id.in_(unit_ids),
                MonthOnCallVersion.month == month,
                MonthOnCallVersion.version == version,
            )
            .with_for_update()
            .all()
        )
        for row in rows:
            row.is_published = False
            row.published_at = None
            row.published_by = None
        self.db.commit()
        for row in rows:
            self.db.refresh(row)
        return rows

    def get_published_unit_ids(self, unit_ids: List[UUID], month: str, version: int) -> List[UUID]:
        """Which of the units' rosters are published at exactly `version`."""
        rows = (
            self.db.query(MonthOnCallVersion.unit_id)
            .filter(
                MonthOnCallVersion.unit_id.in_(unit_ids),
                MonthOnCallVersion.month == month,
                MonthOnCallVersion.version == version,
                MonthOnCallVersion.is_published.is_(True),
            )
            .all()
        )
        return [row.unit_id for row in rows]

    def save_entries_snapshot(
        self, unit_id: UUID, division_id: UUID, month: str,
        entries: List[OnCallShiftEntry], created_by: Optional[UUID],
        is_published: bool, version: int,
    ) -> List[OnCallShift]:
        """Writes the month as the unit's roster at `version` (a shared on-call scheduling version), without
        committing — the caller commits with the rest of the version. `entries` is the complete desired state for
        the month: any previously-saved date missing from it gets no row in the new version — the prior version's
        row is untouched (insert-only), but the date is gone as of this version, which is all a "delete" can
        mean here."""
        rows = [
            OnCallShift(
                division_id=division_id, unit_id=unit_id, date=e.date,
                station_assignments=_keys_to_str(e.station_assignments),
                submitted_assignments={},
                version=version, created_by=created_by,
            )
            for e in entries
        ]
        self.db.add_all(rows)
        self.db.add(MonthOnCallVersion(
            unit_id=unit_id, month=month, version=version, is_published=is_published,
            published_at=date.today() if is_published else None,
            published_by=created_by if is_published else None,
            created_by=created_by,
        ))
        logger.info(
            "save_entries_snapshot (on_call): %d rows (unit_id=%s, month=%s, version=%d)",
            len(rows), unit_id, month, version,
        )
        return rows
