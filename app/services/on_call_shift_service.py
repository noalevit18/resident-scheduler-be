import logging
from typing import Optional
from uuid import UUID

from app.models.models import OnCallSchedulingVersion, OnCallShift, OnCallVersionKind
from app.repositories.on_call_scheduling_version_repository import OnCallSchedulingVersionRepository
from app.repositories.on_call_shift_repository import OnCallShiftRepository
from app.services.external_on_call_physician_service import ExternalOnCallPhysicianService
from app.services.on_call_station_service import OnCallStationService
from app.services.staff_service import StaffService
from app.schemas.schemas import (
    MonthlyOnCallShiftsUpdate, MonthlyOnCallShiftsResponse, OnCallShiftResponse,
    OnCallShiftEntry, OnCallShiftHistoryResponse,
)
from app.context import get_current_user_label

logger = logging.getLogger(__name__)


class OnCallStationDivisionMismatchError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


class OnCallStationNotOpenToExternalError(OnCallStationDivisionMismatchError):
    """An external physician was assigned to a station not open to external physicians (400)."""


class OnCallShiftService:
    """A unit's on-call roster. `station_assignments` is keyed by the on-call
    resident's id — a staff member's or one of the unit's external on-call
    physicians'."""

    def __init__(
        self,
        repository: OnCallShiftRepository,
        on_call_station_service: OnCallStationService,
        staff_service: StaffService,
        external_physician_service: ExternalOnCallPhysicianService,
        version_repository: OnCallSchedulingVersionRepository,
    ):
        self.repository = repository
        self.on_call_station_service = on_call_station_service
        self.staff_service = staff_service
        self.external_physician_service = external_physician_service
        self.version_repository = version_repository

    def _to_response(self, row: OnCallShift) -> OnCallShiftResponse:
        return OnCallShiftResponse(
            id=row.id, division_id=row.division_id, unit_id=row.unit_id, date=row.date,
            station_assignments=row.station_assignments, submitted_assignments=row.submitted_assignments,
            version=row.version,
            created_at=row.created_at, created_by=row.created_by,
        )

    def _to_monthly_response(self, rows: list[OnCallShift], status_row) -> MonthlyOnCallShiftsResponse:
        """`status_row` is the month's latest version."""
        return MonthlyOnCallShiftsResponse(
            shifts=[self._to_response(r) for r in rows],
            version=status_row.version if status_row else 0,
            is_published=status_row.is_published if status_row else False,
            published_at=status_row.published_at if status_row else None,
            published_by=status_row.published_by if status_row else None,
        )

    @staticmethod
    def _to_history_response(version_row) -> OnCallShiftHistoryResponse:
        return OnCallShiftHistoryResponse(
            id=version_row.id, version=version_row.version, is_published=version_row.is_published,
            published_at=version_row.published_at, published_by=version_row.published_by,
            created_at=version_row.created_at, created_by=version_row.created_by,
        )

    def get_monthly(self, unit_id: UUID, month: str, version: Optional[int] = None) -> MonthlyOnCallShiftsResponse:
        """The unit's roster — as of the shared on-call scheduling `version` when given (its latest roster at or
        below it; empty if none was saved by then), else the latest."""
        status_row = self.repository.get_version_status(unit_id, month)
        if version:
            resolved = self.version_repository.resolve(unit_id, month, OnCallVersionKind.ROSTER, version)
            rows = self.repository.get_by_version(unit_id, month, resolved) if resolved else []
        else:
            rows = self.repository.get_by_month(unit_id, month)
        return self._to_monthly_response(rows, status_row)

    def get_version_history(self, unit_id: UUID, month: str) -> list[OnCallShiftHistoryResponse]:
        return [self._to_history_response(version_row) for version_row in self.repository.get_version_history(unit_id, month)]

    def publish_version(
        self, unit_id: UUID, month: str, version: int, published_by: Optional[UUID],
    ) -> OnCallShiftHistoryResponse:
        version_row = self.repository.publish_version(unit_id, month, version, published_by)
        logger.info(
            "Published on-call version %d (unit_id=%s, month=%s) by %s",
            version, unit_id, month, get_current_user_label(),
        )
        return self._to_history_response(version_row)

    def unpublish_version(self, unit_id: UUID, month: str, version: int) -> OnCallShiftHistoryResponse:
        rows = self.repository.unpublish_versions([unit_id], month, version)
        if not rows:
            raise ValueError(f"On-call version {version} not found for {month}")
        logger.info(
            "Unpublished on-call version %d (unit_id=%s, month=%s) by %s",
            version, unit_id, month, get_current_user_label(),
        )
        return self._to_history_response(rows[0])

    def validate_shifts(self, unit_id: UUID, division_id: UUID, month: str, entries: list[OnCallShiftEntry]) -> None:
        """Rejects entries outside the month, unknown residents, or stations that aren't the division's (or open to
        the external physicians assigned to them)."""
        for entry in entries:
            if entry.date.strftime("%Y-%m") != month:
                raise ValueError(f"Entry date {entry.date} is not in month {month}")

        staff_ids = {sid for e in entries for sid in e.station_assignments}
        external_ids = staff_ids - self.staff_service.get_unit_member_ids(list(staff_ids), unit_id)
        if external_ids - self.external_physician_service.get_unit_physician_ids(list(external_ids), unit_id):
            raise ValueError("Staff member not found")

        # include_deleted=True: a shift may reference a station that has
        # since been deleted (kept for history) — only a station missing
        # entirely or belonging to another division is rejected.
        station_ids = {sta for e in entries for sta in e.station_assignments.values()}
        existing_stations = self.on_call_station_service.get_by_ids(list(station_ids), division_id, include_deleted=True)
        if set(station_ids) - set(existing_stations.keys()):
            raise OnCallStationDivisionMismatchError(
                "on_call_station_wrong_division", "One or more stations are not in this division",
            )
        if any(
            not existing_stations[station_id].open_to_external
            for e in entries
            for sid, station_id in e.station_assignments.items()
            if sid in external_ids
        ):
            raise OnCallStationNotOpenToExternalError(
                "on_call_station_not_open_to_external",
                "External physicians can only be assigned to stations open to external physicians",
            )

    def write_shifts(
        self, unit_id: UUID, division_id: UUID, month: str, entries: list[OnCallShiftEntry], is_published: bool,
        created_by: Optional[UUID], version_row: OnCallSchedulingVersion,
    ) -> list[OnCallShift]:
        """Writes validated entries under a shared version being saved (committed by the caller)."""
        rows = self.repository.save_entries_snapshot(
            unit_id, division_id, month, entries, created_by, is_published=is_published, version=version_row.version,
        )
        self.version_repository.record(version_row, unit_id, OnCallVersionKind.ROSTER)
        return rows

    def update_monthly_shifts(
        self, unit_id: UUID, division_id: UUID, month: str, data: MonthlyOnCallShiftsUpdate, created_by: Optional[UUID],
    ) -> MonthlyOnCallShiftsResponse:
        self.validate_shifts(unit_id, division_id, month, data.entries)
        rows = self.version_repository.transaction(
            division_id, month, created_by,
            lambda version_row: self.write_shifts(
                unit_id, division_id, month, data.entries, data.is_published, created_by, version_row,
            ),
        )
        logger.info(
            "Saved monthly on-call shifts snapshot: %d entries (unit_id=%s, month=%s) by %s",
            len(rows), unit_id, month, get_current_user_label(),
        )
        status_row = self.repository.get_version_status(unit_id, month)
        return self._to_monthly_response(rows, status_row)

