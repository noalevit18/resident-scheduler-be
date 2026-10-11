import logging
from datetime import datetime, timezone
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models.models import (
    ScheduleAssignment, ScheduleSenior, ScheduleStation, ScheduleVersion, ScheduleVersionStation, StationVersion,
)
from app.schemas.schemas import ScheduleDayEntry, ScheduleStationEntry

logger = logging.getLogger(__name__)

VERSION_UNIQUE_CONSTRAINT = "schedule_versions_unit_id_month_version_key"


class ScheduleVersionConflictError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


class ScheduleRepository:
    """The schedule tables are insert-only: every save inserts a new
    `schedule_versions` row plus a complete snapshot of the month under it.
    "Current state" of a month = the version row with the highest
    `version`. The only in-place update is (un)publishing a version row."""

    def __init__(self, db: Session):
        self.db = db

    # --- reads ---

    def _get_latest_version_row(self, unit_id: UUID, month: str, for_update: bool = False) -> Optional[ScheduleVersion]:
        query = self.db.query(ScheduleVersion).filter(
            ScheduleVersion.unit_id == unit_id, ScheduleVersion.month == month,
        ).order_by(ScheduleVersion.version.desc())
        if for_update:
            query = query.with_for_update()
        return query.first()

    def get_version_status(self, unit_id: UUID, month: str) -> Optional[ScheduleVersion]:
        return self._get_latest_version_row(unit_id, month)

    def get_version_row(self, unit_id: UUID, month: str, version: int, for_update: bool = False) -> Optional[ScheduleVersion]:
        query = self.db.query(ScheduleVersion).filter(
            ScheduleVersion.unit_id == unit_id, ScheduleVersion.month == month, ScheduleVersion.version == version,
        )
        if for_update:
            query = query.with_for_update()
        return query.first()

    def get_saved_months(self, unit_id: UUID, from_month: str) -> List[str]:
        """The months ("YYYY-MM") from `from_month` on that have a saved schedule."""
        rows = (
            self.db.query(ScheduleVersion.month)
            .filter(ScheduleVersion.unit_id == unit_id, ScheduleVersion.month >= from_month)
            .distinct()
            .order_by(ScheduleVersion.month)
            .all()
        )
        return [row.month for row in rows]

    def get_version_history(self, unit_id: UUID, month: str) -> List[ScheduleVersion]:
        return (
            self.db.query(ScheduleVersion)
            .filter(ScheduleVersion.unit_id == unit_id, ScheduleVersion.month == month)
            .order_by(ScheduleVersion.version.desc())
            .all()
        )

    def get_stations(self, version_id: int) -> List[ScheduleStation]:
        return (
            self.db.query(ScheduleStation)
            .options(selectinload(ScheduleStation.assignments))
            .filter(ScheduleStation.schedule_version_id == version_id)
            .order_by(ScheduleStation.date, ScheduleStation.display_order, ScheduleStation.id)
            .all()
        )

    def get_latest_published(self, unit_id: UUID, month: str) -> Optional[ScheduleVersion]:
        return (
            self.db.query(ScheduleVersion)
            .filter(ScheduleVersion.unit_id == unit_id, ScheduleVersion.month == month, ScheduleVersion.is_published.is_(True))
            .order_by(ScheduleVersion.version.desc())
            .first()
        )

    def get_pinned_versions(self, version_id: int) -> List[StationVersion]:
        """The station versions this schedule version is pinned to (possibly
        several per station)."""
        rows = (
            self.db.query(ScheduleVersionStation)
            .options(selectinload(ScheduleVersionStation.station_version))
            .filter(ScheduleVersionStation.schedule_version_id == version_id)
            .all()
        )
        return [row.station_version for row in rows]

    def get_seniors(self, version_id: int) -> List[ScheduleSenior]:
        return (
            self.db.query(ScheduleSenior)
            .filter(ScheduleSenior.schedule_version_id == version_id)
            .order_by(ScheduleSenior.date)
            .all()
        )

    # --- writes ---

    def _insert_version_row(
        self, unit_id: UUID, month: str, version: int, created_by: Optional[UUID], is_published: bool,
        constraints_version: Optional[int], on_call_version: Optional[int], created_at: Optional[datetime],
    ) -> ScheduleVersion:
        published_at = (created_at or datetime.now(timezone.utc)) if is_published else None
        row = ScheduleVersion(
            unit_id=unit_id, month=month, version=version,
            is_published=is_published, published_at=published_at,
            published_by=created_by if is_published else None,
            constraints_version=constraints_version, on_call_version=on_call_version,
            created_by=created_by,
        )
        if created_at:
            row.created_at = created_at
        self.db.add(row)
        self.db.flush()
        return row

    def _insert_pins(self, version_id: int, pins: List[StationVersion]) -> None:
        unique_pins = {pin.id: pin for pin in pins}.values()
        self.db.add_all([
            ScheduleVersionStation(schedule_version_id=version_id, station_id=pin.station_id, station_version_id=pin.id)
            for pin in unique_pins
        ])

    def _insert_stations(
        self, version_id: int, days: List[ScheduleDayEntry],
    ) -> List[Tuple[ScheduleStation, ScheduleStationEntry]]:
        """Expects every entry's `display_order` to be already resolved."""
        pairs = [
            (
                ScheduleStation(
                    schedule_version_id=version_id, date=day.date, station_id=entry.station_id,
                    custom_name=entry.custom_name, display_order=entry.display_order,
                ),
                entry,
            )
            for day in days
            for entry in day.stations
        ]
        self.db.add_all([row for row, _ in pairs])
        self.db.flush()
        return pairs

    def _insert_assignments(self, station_pairs: List[Tuple[ScheduleStation, ScheduleStationEntry]]) -> int:
        rows = [
            ScheduleAssignment(
                schedule_station_id=station_row.id,
                staff_member_id=assignment.staff_member_id,
                is_stand_by=assignment.is_stand_by,
            )
            for station_row, entry in station_pairs
            for assignment in entry.assignments
        ]
        self.db.add_all(rows)
        return len(rows)

    def _insert_seniors(self, version_id: int, days: List[ScheduleDayEntry]) -> int:
        rows = [
            ScheduleSenior(schedule_version_id=version_id, date=day.date, senior_id=day.senior_id)
            for day in days
            if day.senior_id
        ]
        self.db.add_all(rows)
        return len(rows)

    def _check_base_version(self, latest: Optional[ScheduleVersion], base_version: Optional[int]) -> None:
        """Optimistic concurrency: the client edited `base_version`; reject the
        save when someone else saved a newer version meanwhile."""
        latest_version = latest.version if latest else 0
        if base_version is not None and base_version != latest_version:
            self.db.rollback()  # release the FOR UPDATE lock
            raise ScheduleVersionConflictError(
                "schedule_version_conflict",
                f"The schedule was changed by someone else (version {latest_version}, you edited {base_version})",
            )

    def _write_snapshot(
        self, unit_id: UUID, month: str, days: List[ScheduleDayEntry], pins: List[StationVersion],
        created_by: Optional[UUID], is_published: bool,
        constraints_version: Optional[int], on_call_version: Optional[int], created_at: Optional[datetime],
        base_version: Optional[int],
    ) -> ScheduleVersion:
        latest = self._get_latest_version_row(unit_id, month, for_update=True)
        self._check_base_version(latest, base_version)
        next_version = (latest.version if latest else 0) + 1
        version_row = self._insert_version_row(
            unit_id, month, next_version, created_by, is_published, constraints_version, on_call_version, created_at,
        )
        self._insert_pins(version_row.id, pins)
        station_pairs = self._insert_stations(version_row.id, days)
        assignment_count = self._insert_assignments(station_pairs)
        senior_count = self._insert_seniors(version_row.id, days)
        self.db.commit()
        logger.info(
            "save_snapshot (schedule): %d stations, %d assignments, %d seniors (unit_id=%s, month=%s, version=%d)",
            len(station_pairs), assignment_count, senior_count, unit_id, month, next_version,
        )
        return version_row

    def save_snapshot(
        self, unit_id: UUID, month: str, days: List[ScheduleDayEntry], pins: List[StationVersion],
        created_by: Optional[UUID], is_published: bool,
        constraints_version: Optional[int], on_call_version: Optional[int],
        created_at: Optional[datetime] = None, base_version: Optional[int] = None,
    ) -> ScheduleVersion:
        """`days` is the complete desired state of the month. `pins` are the
        station versions this version is pinned to. `base_version`, when set,
        must still be the latest version (else ScheduleVersionConflictError).
        `created_at` overrides the server default (used by the Firestore
        migration to keep the original save time)."""
        for _ in range(3):  # retry covers a race between two concurrent first-time-or-latest saves
            try:
                return self._write_snapshot(
                    unit_id, month, days, pins, created_by, is_published,
                    constraints_version, on_call_version, created_at, base_version,
                )
            except IntegrityError as e:
                self.db.rollback()
                if VERSION_UNIQUE_CONSTRAINT not in str(e.orig):
                    raise
        raise ScheduleVersionConflictError("schedule_version_conflict", "Concurrent update detected — please retry")

    def set_published(
        self, unit_id: UUID, month: str, version: int, is_published: bool, user_id: Optional[UUID],
    ) -> ScheduleVersion:
        row = self.get_version_row(unit_id, month, version, for_update=True)
        if not row:
            raise ValueError(f"Schedule version {version} not found for {month}")
        row.is_published = is_published
        row.published_at = datetime.now(timezone.utc) if is_published else None
        row.published_by = user_id if is_published else None
        self.db.commit()
        return row
