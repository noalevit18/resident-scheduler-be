import logging
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.models import MonthlyOnCallDayStationsVersion, OnCallDayStation, OnCallStation
from app.repositories.on_call_shift_repository import month_bounds

logger = logging.getLogger(__name__)


class OnCallDayStationRepository:
    """A unit's per-day changes to the stations it populates. Insert-only:
    each save is a complete snapshot of the unit+month under a shared on-call
    scheduling version, tracked in `monthly_on_call_day_stations_versions`."""

    def __init__(self, db: Session):
        self.db = db

    def get_latest_version_row(
        self, unit_id: UUID, month: str, for_update: bool = False,
    ) -> Optional[MonthlyOnCallDayStationsVersion]:
        query = self.db.query(MonthlyOnCallDayStationsVersion).filter(
            MonthlyOnCallDayStationsVersion.unit_id == unit_id, MonthlyOnCallDayStationsVersion.month == month,
        ).order_by(MonthlyOnCallDayStationsVersion.version.desc())
        if for_update:
            query = query.with_for_update()
        return query.first()

    def get_version_history(self, unit_id: UUID, month: str) -> list[MonthlyOnCallDayStationsVersion]:
        """Every version saved for the unit+month, newest first."""
        return (
            self.db.query(MonthlyOnCallDayStationsVersion)
            .filter(MonthlyOnCallDayStationsVersion.unit_id == unit_id, MonthlyOnCallDayStationsVersion.month == month)
            .order_by(MonthlyOnCallDayStationsVersion.version.desc())
            .all()
        )

    def get_by_version(self, unit_id: UUID, month: str, version: int) -> list[OnCallDayStation]:
        start, end = month_bounds(month)
        return (
            self.db.query(OnCallDayStation)
            .filter(
                OnCallDayStation.unit_id == unit_id, OnCallDayStation.date >= start, OnCallDayStation.date < end,
                OnCallDayStation.version == version,
            )
            .order_by(OnCallDayStation.date, OnCallDayStation.on_call_station_id)
            .all()
        )

    def save_snapshot(
        self, unit_id: UUID, month: str, rows: list[OnCallDayStation], created_by: Optional[UUID], version: int,
    ) -> None:
        """Inserts `rows` — the month's complete set of changes — as the unit+month's changes at `version` (a
        shared on-call scheduling version), without committing. Earlier versions' rows are never touched."""
        for row in rows:
            row.version = version
        self.db.add_all(rows)
        self.db.add(MonthlyOnCallDayStationsVersion(unit_id=unit_id, month=month, version=version, created_by=created_by))
        logger.info(
            "Saved on-call day-stations version %d (unit_id=%s, month=%s, rows=%d)", version, unit_id, month, len(rows),
        )

    def division_station_ids(self, division_id: UUID) -> set[int]:
        """Every station of the division, deleted ones included (past months keep theirs)."""
        rows = self.db.query(OnCallStation.id).filter(OnCallStation.division_id == division_id).all()
        return {row.id for row in rows}

