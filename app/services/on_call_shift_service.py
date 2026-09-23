import logging
from collections import defaultdict
from typing import Optional
from uuid import UUID

from app.models.models import OnCallShift, SubmissionFeature
from app.repositories.on_call_shift_repository import OnCallShiftRepository
from app.repositories.staff_member_submission_repository import StaffMemberSubmissionRepository
from app.services.on_call_station_service import OnCallStationService
from app.services.staff_member_submission_metadata_service import StaffMemberSubmissionMetadataService
from app.services.staff_service import StaffService
from app.schemas.schemas import (
    MonthlyOnCallShiftsUpdate, MonthlyOnCallShiftsResponse, OnCallShiftResponse,
    OnCallShiftHistoryResponse, OnCallShiftEntry,
)
from app.context import get_current_user_label

logger = logging.getLogger(__name__)


class OnCallStationDivisionMismatchError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


class OnCallShiftService:
    def __init__(
        self,
        repository: OnCallShiftRepository,
        on_call_station_service: OnCallStationService,
        staff_service: StaffService,
        submission_repository: StaffMemberSubmissionRepository,
        submission_metadata_service: StaffMemberSubmissionMetadataService,
    ):
        self.repository = repository
        self.on_call_station_service = on_call_station_service
        self.staff_service = staff_service
        self.submission_repository = submission_repository
        self.submission_metadata_service = submission_metadata_service

    def _to_response(self, row: OnCallShift) -> OnCallShiftResponse:
        return OnCallShiftResponse(
            id=row.id, division_id=row.division_id, unit_id=row.unit_id, date=row.date,
            station_assignments=row.station_assignments, submitted_assignments=row.submitted_assignments,
            version=row.version,
            created_at=row.created_at, created_by=row.created_by,
        )

    def _to_monthly_response(self, rows: list[OnCallShift], status_row) -> MonthlyOnCallShiftsResponse:
        return MonthlyOnCallShiftsResponse(
            shifts=[self._to_response(r) for r in rows],
            version=status_row.version if status_row else 0,
            is_published=status_row.is_published if status_row else False,
            published_at=status_row.published_at if status_row else None,
            published_by=status_row.published_by if status_row else None,
        )

    def get_monthly(self, unit_id: UUID, month: str, version: Optional[int] = None) -> MonthlyOnCallShiftsResponse:
        rows = self.repository.get_by_version(unit_id, month, version) if version else self.repository.get_by_month(unit_id, month)
        status_row = self.repository.get_version_status(unit_id, month)
        return self._to_monthly_response(rows, status_row)

    def get_version_history(self, unit_id: UUID, month: str) -> list[OnCallShiftHistoryResponse]:
        return [
            OnCallShiftHistoryResponse(
                id=version_row.id, version=version_row.version, is_published=version_row.is_published,
                published_at=version_row.published_at, published_by=version_row.published_by,
                created_at=version_row.created_at, created_by=version_row.created_by,
            )
            for version_row in self.repository.get_version_history(unit_id, month)
        ]

    def publish_version(
        self, unit_id: UUID, month: str, version: int, published_by: Optional[UUID],
    ) -> OnCallShiftHistoryResponse:
        version_row = self.repository.publish_version(unit_id, month, version, published_by)
        logger.info(
            "Published on-call version %d (unit_id=%s, month=%s) by %s",
            version, unit_id, month, get_current_user_label(),
        )
        return OnCallShiftHistoryResponse(
            id=version_row.id, version=version_row.version, is_published=version_row.is_published,
            published_at=version_row.published_at, published_by=version_row.published_by,
            created_at=version_row.created_at, created_by=version_row.created_by,
        )

    def update_monthly_shifts(
        self, unit_id: UUID, division_id: UUID, month: str, data: MonthlyOnCallShiftsUpdate, created_by: Optional[UUID],
    ) -> MonthlyOnCallShiftsResponse:
        for entry in data.entries:
            if entry.date.strftime("%Y-%m") != month:
                raise ValueError(f"Entry date {entry.date} is not in month {month}")

        staff_ids = {sid for e in data.entries for sid in e.station_assignments}
        existing_staff_ids = self.staff_service.get_unit_member_ids(list(staff_ids), unit_id)
        if staff_ids - existing_staff_ids:
            raise ValueError("Staff member not found")

        # include_deleted=True: a shift may reference a station that has
        # since been deleted (kept for history) — only a station missing
        # entirely or belonging to another division is rejected.
        station_ids = {sta for e in data.entries for sta in e.station_assignments.values()}
        existing_stations = self.on_call_station_service.get_by_ids(list(station_ids), division_id, include_deleted=True)
        if set(station_ids) - set(existing_stations.keys()):
            raise OnCallStationDivisionMismatchError(
                "on_call_station_wrong_division", "One or more stations are not in this division",
            )

        rows = self.repository.save_entries_snapshot(
            unit_id, division_id, month, data.entries, created_by, is_published=data.is_published,
        )
        logger.info(
            "Saved monthly on-call shifts snapshot: %d entries (unit_id=%s, month=%s) by %s",
            len(rows), unit_id, month, get_current_user_label(),
        )
        status_row = self.repository.get_version_status(unit_id, month)
        return self._to_monthly_response(rows, status_row)

    def pull_user_submissions(self, unit_id: UUID, division_id: UUID, month: str, created_by: Optional[UUID]) -> MonthlyOnCallShiftsResponse:
        """Reads every staff_member_submissions row for this unit+month and keeps
        only the ones carrying an on_call_station_id."""
        submissions = self.submission_repository.get_by_unit_month(unit_id, month)
        existing = self.repository.get_by_month(unit_id, month)

        merged_by_date: dict = {}
        for row in existing:
            kept = {
                sid: station for sid, station in row.station_assignments.items()
                if sid not in row.submitted_assignments
            }
            if kept:
                merged_by_date[row.date] = kept

        submitted_by_date: dict = defaultdict(dict)
        for s in submissions:
            if s.date is None or s.on_call_station_id is None:
                continue
            submitted_by_date[s.date][str(s.staff_member_id)] = s.on_call_station_id

        submitted_assignments_by_date: dict = {}
        for d, assignments in submitted_by_date.items():
            merged_by_date.setdefault(d, {}).update(assignments)
            submitted_assignments_by_date[d] = dict(assignments)

        entries = [
            OnCallShiftEntry(date=d, station_assignments=assignments)
            for d, assignments in merged_by_date.items()
        ]

        rows = self.repository.save_entries_snapshot(
            unit_id, division_id, month, entries, created_by, is_published=False,
            submitted_assignments_by_date=submitted_assignments_by_date,
        )
        self.submission_metadata_service.mark_pulled(unit_id, month, SubmissionFeature.ON_CALL, created_by)
        logger.info(
            "Pulled on-call submissions into official calendar: %d dates (unit_id=%s, month=%s) by %s",
            len(rows), unit_id, month, get_current_user_label(),
        )
        status_row = self.repository.get_version_status(unit_id, month)
        return self._to_monthly_response(rows, status_row)
