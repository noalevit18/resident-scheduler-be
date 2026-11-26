import logging
from typing import Optional
from uuid import UUID

from app.context import get_current_user_label
from app.models.models import OnCallSchedulingVersion, OnCallVersionKind
from app.repositories.on_call_scheduling_version_repository import OnCallSchedulingVersionRepository
from app.repositories.on_call_shift_repository import OnCallShiftRepository
from app.schemas.schemas import (
    OnCallSchedulingHistoryResponse,
    OnCallSchedulingSave,
    OnCallSchedulingSaveResponse,
    OnCallSchedulingVersionEntityResponse,
)
from app.services.on_call_constraint_service import OnCallConstraintService
from app.services.on_call_day_station_service import OnCallDayStationService
from app.services.on_call_shift_service import OnCallShiftService

logger = logging.getLogger(__name__)


class OnCallSchedulingService:
    """The on-call scheduling page's saves: a unit's on-call constraints and the division's rosters and day stations,
    written together under one shared version — the number its history, view and restore go by."""

    def __init__(
        self,
        version_repository: OnCallSchedulingVersionRepository,
        shift_repository: OnCallShiftRepository,
        constraint_service: OnCallConstraintService,
        shift_service: OnCallShiftService,
        day_station_service: OnCallDayStationService,
    ):
        self.version_repository = version_repository
        self.shift_repository = shift_repository
        self.constraint_service = constraint_service
        self.shift_service = shift_service
        self.day_station_service = day_station_service

    def save(
        self, division_id: UUID, month: str, data: OnCallSchedulingSave, created_by: Optional[UUID],
    ) -> OnCallSchedulingSaveResponse:
        """Validates everything, then writes it all under one new version, atomically."""
        unit_ids = {roster.unit_id for roster in data.rosters} | {changes.unit_id for changes in data.day_stations}
        if data.constraints:
            unit_ids.add(data.constraints.unit_id)
        if not unit_ids:
            raise ValueError("Nothing to save")
        if any(self.version_repository.division_of(unit_id) != division_id for unit_id in unit_ids):
            raise ValueError("Unit not found in this division")

        if data.constraints:
            self.constraint_service.validate_entries(
                data.constraints.unit_id, month, data.account_id, data.constraints.entries,
            )
        for roster in data.rosters:
            self.shift_service.validate_shifts(roster.unit_id, division_id, month, roster.entries)
        for changes in data.day_stations:
            self.day_station_service.validate_entries(division_id, month, changes.entries)

        def write(version_row: OnCallSchedulingVersion) -> int:
            for changes in data.day_stations:
                self.day_station_service.write_entries(
                    changes.unit_id, division_id, month, changes.entries, created_by, version_row,
                )
            if data.constraints:
                self.constraint_service.write_entries(
                    data.constraints.unit_id, month, data.constraints.entries, created_by, version_row,
                )
            for roster in data.rosters:
                self.shift_service.write_shifts(
                    roster.unit_id, division_id, month, roster.entries, data.is_published, created_by, version_row,
                )
            return version_row.version

        version = self.version_repository.transaction(division_id, month, created_by, write)
        logger.info(
            "Saved on-call scheduling version %d (division_id=%s, month=%s, units=%d, published=%s) by %s",
            version, division_id, month, len(unit_ids), data.is_published, get_current_user_label(),
        )
        return OnCallSchedulingSaveResponse(version=version)

    def get_history(self, division_id: UUID, month: str) -> list[OnCallSchedulingHistoryResponse]:
        history = []
        for version_row in self.version_repository.get_history(division_id, month):
            roster_unit_ids = [entity.unit_id for entity in version_row.entities if entity.kind == OnCallVersionKind.ROSTER]
            history.append(OnCallSchedulingHistoryResponse(
                version=version_row.version,
                created_at=version_row.created_at,
                created_by=version_row.created_by,
                entities=[
                    OnCallSchedulingVersionEntityResponse(unit_id=entity.unit_id, kind=entity.kind.value)
                    for entity in version_row.entities
                ],
                published_unit_ids=(
                    self.shift_repository.get_published_unit_ids(roster_unit_ids, month, version_row.version)
                    if roster_unit_ids else []
                ),
            ))
        return history

    def unpublish(self, division_id: UUID, month: str, version: int) -> None:
        """Unpublishes every roster the version published."""
        version_row = self.version_repository.get_version(division_id, month, version)
        if not version_row:
            raise ValueError(f"On-call scheduling version {version} not found for {month}")
        roster_unit_ids = [entity.unit_id for entity in version_row.entities if entity.kind == OnCallVersionKind.ROSTER]
        self.shift_repository.unpublish_versions(roster_unit_ids, month, version)
        logger.info(
            "Unpublished on-call scheduling version %d (division_id=%s, month=%s) by %s",
            version, division_id, month, get_current_user_label(),
        )
