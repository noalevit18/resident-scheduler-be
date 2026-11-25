import logging
from typing import Optional
from uuid import UUID

from app.context import get_current_user_label
from app.models.models import OnCallDayStation, OnCallSchedulingVersion, OnCallVersionKind
from app.repositories.on_call_day_station_repository import OnCallDayStationRepository
from app.repositories.on_call_scheduling_version_repository import OnCallSchedulingVersionRepository
from app.repositories.on_call_shift_repository import month_bounds
from app.schemas.schemas import (
    OnCallDayStationEntry, OnCallDayStationsResponse, OnCallDayStationsWrite, OnCallDayVersionHistoryResponse,
)

logger = logging.getLogger(__name__)


class OnCallDayStationError(Exception):
    """A rejected day-stations save, in the API's `{ error, message }` shape."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


class OnCallDayStationService:
    """A unit's per-day changes to the stations it populates, saved per month as snapshots under shared on-call
    scheduling versions."""

    def __init__(self, repository: OnCallDayStationRepository, version_repository: OnCallSchedulingVersionRepository):
        self.repository = repository
        self.version_repository = version_repository

    def get_month(self, unit_id: UUID, month: str, version: Optional[int] = None) -> OnCallDayStationsResponse:
        """The unit+month's day-station changes — as of the shared on-call scheduling `version` when given (its
        latest changes at or below it; none if nothing was saved by then), else the latest."""
        if version is None:
            latest = self.repository.get_latest_version_row(unit_id, month)
            resolved = latest.version if latest else None
        else:
            resolved = self.version_repository.resolve(unit_id, month, OnCallVersionKind.DAY_STATIONS, version)
        rows = self.repository.get_by_version(unit_id, month, resolved) if resolved else []
        return OnCallDayStationsResponse(
            unit_id=unit_id,
            month=month,
            version=resolved or 0,
            entries=[
                OnCallDayStationEntry(
                    date=row.date, station_id=row.on_call_station_id, is_added=row.is_added, shifts_turns=row.shifts_turns,
                )
                for row in rows
            ],
        )

    def get_version_history(self, unit_id: UUID, month: str) -> list[OnCallDayVersionHistoryResponse]:
        return [
            OnCallDayVersionHistoryResponse.model_validate(row)
            for row in self.repository.get_version_history(unit_id, month)
        ]

    def validate_entries(self, division_id: UUID, month: str, entries: list[OnCallDayStationEntry]) -> None:
        """Every date must be in the month and every station the division's."""
        start, end = month_bounds(month)
        outside = sorted({entry.date.isoformat() for entry in entries if not start <= entry.date < end})
        if outside:
            raise OnCallDayStationError("on_call_day_outside_month", f"Dates outside {month}: {', '.join(outside)}")
        division_stations = self.repository.division_station_ids(division_id)
        unknown = sorted({entry.station_id for entry in entries if entry.station_id not in division_stations})
        if unknown:
            raise OnCallDayStationError("on_call_station_not_in_division", f"Unknown on-call stations: {', '.join(map(str, unknown))}")

    def write_entries(
        self, unit_id: UUID, division_id: UUID, month: str, entries: list[OnCallDayStationEntry],
        user_id: Optional[UUID], version_row: OnCallSchedulingVersion,
    ) -> None:
        """Writes validated changes under a shared version being saved (committed by the caller)."""
        self.repository.save_snapshot(
            unit_id, month,
            [
                OnCallDayStation(
                    division_id=division_id,
                    unit_id=unit_id,
                    date=entry.date,
                    on_call_station_id=entry.station_id,
                    is_added=entry.is_added,
                    shifts_turns=entry.shifts_turns,
                    created_by=user_id,
                )
                for entry in entries
            ],
            user_id,
            version_row.version,
        )
        self.version_repository.record(version_row, unit_id, OnCallVersionKind.DAY_STATIONS)

    def replace_month(
        self, unit_id: UUID, division_id: UUID, month: str, data: OnCallDayStationsWrite, user_id: UUID | None,
    ) -> OnCallDayStationsResponse:
        """Saves the unit+month's complete set of changes as a new shared version; earlier versions are kept."""
        self.validate_entries(division_id, month, data.entries)

        def write(version_row: OnCallSchedulingVersion) -> int:
            self.write_entries(unit_id, division_id, month, data.entries, user_id, version_row)
            return version_row.version

        version = self.version_repository.transaction(division_id, month, user_id, write)
        logger.info(
            "Saved %d on-call day-station changes as version %d for unit_id=%s month=%s by %s",
            len(data.entries), version, unit_id, month, get_current_user_label(),
        )
        return self.get_month(unit_id, month, version)
