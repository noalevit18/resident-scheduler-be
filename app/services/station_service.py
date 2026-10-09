import logging
from datetime import date
from typing import Optional
from uuid import UUID

from app.models.models import Station, StationVersion
from app.repositories.station_repository import StationRepository, version_in_effect
from app.schemas.schemas import StationCreate, StationResponse, StationUpdate, StationVersionResponse
from app.services.on_call_station_service import OnCallStationService
from app.services.unit_service import UnitService
from app.context import get_current_user_label

logger = logging.getLogger(__name__)

# Changing only these updates `stations` in place, creates no version, and
# applies to past months too.
GLOBAL_STATION_FIELDS = ("name", "bg_color", "border_color", "text_color", "display_order")
# Copied into each `station_versions` row; a change creates (or replaces) a
# version effective from an admin-picked date.
VERSIONED_STATION_FIELDS = (
    "is_default", "is_secondary", "secondary_to", "certification_id", "optional", "min_staff_members", "min_staff_on_sabbatical",
    "min_staff_on_half_day", "active_days", "recurrence_type",
    "recurrence_interval", "recurrence_base_date", "enable_stand_by", "active_on_sabbatical", "prefer_day_before_on_call",
)
# The versioned fields deciding which days a station is active; a change to
# any of them can't take effect in a past month.
RECURRENCE_STATION_FIELDS = ("active_days", "recurrence_type", "recurrence_interval", "recurrence_base_date")


class StationValidationError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


def global_config(station: Station) -> dict:
    return {field: getattr(station, field) for field in GLOBAL_STATION_FIELDS}


def versioned_config(source: Station | StationVersion) -> dict:
    return {field: getattr(source, field) for field in VERSIONED_STATION_FIELDS}


class StationService:
    def __init__(self, repository: StationRepository, on_call_station_service: OnCallStationService, unit_service: UnitService):
        self.repository = repository
        self.on_call_station_service = on_call_station_service
        self.unit_service = unit_service

    # --- responses ---

    def to_version_response(
        self, station: Station, version: StationVersion, on_call_station_ids: list[int], is_pinned: bool = False,
    ) -> StationVersionResponse:
        """Global fields from the station, versioned fields from the version."""
        return StationVersionResponse.model_validate({
            **global_config(station), **versioned_config(version),
            "station_id": station.id, "version": version.version, "effective_from": version.effective_from,
            "is_retired": version.is_retired, "is_pinned": is_pinned, "is_deleted": station.is_deleted,
            "on_call_station_ids": on_call_station_ids,
        })

    def _to_responses(self, stations: list[Station]) -> list[StationResponse]:
        ids = [s.id for s in stations]
        versions_by_station = self.repository.get_versions(ids)
        on_call_ids = self.repository.get_on_call_station_ids(ids)
        today = date.today()
        responses = []
        for station in stations:
            versions = versions_by_station.get(station.id, [])
            current = version_in_effect(versions, today) or (versions[0] if versions else None)
            station_on_call_ids = on_call_ids.get(station.id, [])
            data = {column.name: getattr(station, column.name) for column in Station.__table__.columns}
            if current:
                data.update(versioned_config(current), version=current.version,
                            effective_from=current.effective_from, is_retired=current.is_retired)
            else:
                data.update(version=0)
            data["on_call_station_ids"] = station_on_call_ids
            data["upcoming_versions"] = [
                self.to_version_response(station, v, station_on_call_ids) for v in versions if v.effective_from > today
            ]
            responses.append(StationResponse.model_validate(data))
        return responses

    # --- validation ---

    def _validate_on_call_station_ids(self, unit_id: UUID, on_call_station_ids: Optional[list[int]]) -> None:
        """On-call stations are division-level: they must exist (not deleted)
        in the station's unit's division."""
        if not on_call_station_ids:
            return
        unit = self.unit_service.get_unit_details(unit_id)
        if not unit:
            raise ValueError("Unit not found")
        found = self.on_call_station_service.get_by_ids(on_call_station_ids, unit["division_id"], include_deleted=False)
        if set(on_call_station_ids) - set(found.keys()):
            raise StationValidationError("on_call_station_not_found", "One or more on-call stations are not in this division")

    def _validate_prefer_day_before_on_call(self, prefer: bool, on_call_station_ids: list[int]) -> None:
        if prefer and not on_call_station_ids:
            raise StationValidationError(
                "station_prefer_requires_on_call",
                "prefer_day_before_on_call requires at least one mapped on-call station",
            )

    def _validate_secondary_to(
        self, unit_id: UUID, station_id: Optional[int], is_secondary: bool, secondary_to: list[int],
    ) -> None:
        """is_secondary and secondary_to go together: a secondary station is
        co-assigned from at least one other existing station of its unit."""
        if not is_secondary:
            return
        if not secondary_to:
            raise StationValidationError(
                "station_secondary_to_required", "A secondary station needs at least one station in secondary_to",
            )
        if station_id is not None and station_id in secondary_to:
            raise StationValidationError("station_secondary_to_self", "A station can't be secondary to itself")
        found = self.repository.get_by_ids(list(set(secondary_to)), unit_id, include_deleted=False)
        if set(secondary_to) - set(found.keys()):
            raise StationValidationError("station_secondary_to_not_found", "One or more secondary_to stations are not in this unit")

    def _validate_recurrence_not_in_past(self, changed: dict, effective_from: Optional[date]) -> None:
        """Past months may only take changes outside the recurrence: a change
        to which days the station is active must start this month or later."""
        if effective_from is None or effective_from >= date.today().replace(day=1):
            return
        recurrence_changes = sorted(k for k in changed if k in RECURRENCE_STATION_FIELDS)
        if recurrence_changes:
            raise StationValidationError(
                "station_recurrence_change_in_past",
                f"Recurrence fields ({', '.join(recurrence_changes)}) can't change in a past month; "
                "effective_from must be in the current month or later",
            )

    def _apply_to_later_versions(
        self, station: Station, versions: list[StationVersion], effective_from: date, changed: dict, created_by: Optional[UUID],
    ) -> None:
        """A change made from `effective_from` holds from then on: it's also
        written onto the version in effect at each later effective date, so a
        version scheduled after `effective_from` can't revert it. Pinned
        versions are left intact (write_version adds a newer one beside them)."""
        later_dates = sorted({v.effective_from for v in versions if v.effective_from > effective_from})
        for later_date in later_dates:
            later = version_in_effect(versions, later_date)
            if later is None or all(getattr(later, k) == v for k, v in changed.items()):
                continue
            self.repository.write_version(
                station, later_date, {**versioned_config(later), **changed}, created_by, is_retired=later.is_retired,
            )

    def _clear_other_defaults(
        self, unit_id: UUID, default_station_id: int, effective_from: date, created_by: Optional[UUID],
    ) -> None:
        """A unit has one default station: from `effective_from`, every other
        station that is the default then (or becomes it later) stops being it.
        No commit."""
        others = [s for s in self.repository.get_all(unit_id) if s.id != default_station_id]
        versions_by_station = self.repository.get_versions([s.id for s in others])
        for other in others:
            versions = versions_by_station.get(other.id, [])
            current = version_in_effect(versions, effective_from)
            later_default = any(v.is_default for v in versions if v.effective_from > effective_from)
            if current and current.is_default:
                self.repository.write_version(
                    other, effective_from, {**versioned_config(current), "is_default": False}, created_by,
                    is_retired=current.is_retired,
                )
            if (current and current.is_default) or later_default:
                self._apply_to_later_versions(other, versions, effective_from, {"is_default": False}, created_by)

    # --- public API ---

    def get_all_stations(self, unit_id: UUID, include_deleted: bool = False) -> list[StationResponse]:
        return self._to_responses(self.repository.get_all(unit_id, include_deleted))

    def get_by_ids(self, ids: list[int], unit_id: UUID, include_deleted: bool = True):
        return self.repository.get_by_ids(ids, unit_id, include_deleted)

    def get_unit_versions(self, unit_id: UUID) -> dict[int, list[StationVersion]]:
        return self.repository.get_unit_versions(unit_id)

    def get_on_call_station_ids(self, station_ids: list[int]) -> dict[int, list[int]]:
        return self.repository.get_on_call_station_ids(station_ids)

    def create_station(self, data: StationCreate, created_by: Optional[UUID]) -> StationResponse:
        self._validate_on_call_station_ids(data.unit_id, data.on_call_station_ids)
        self._validate_prefer_day_before_on_call(data.prefer_day_before_on_call, data.on_call_station_ids)
        if not data.is_secondary:
            data = data.model_copy(update={"secondary_to": []})
        self._validate_secondary_to(data.unit_id, None, data.is_secondary, data.secondary_to)
        station = self.repository.add_station(
            data.unit_id, data.model_dump(exclude={"unit_id", "on_call_station_ids", "effective_from"}),
        )
        self.repository.write_version(station, data.effective_from, versioned_config(station), created_by)
        if data.is_default:
            self._clear_other_defaults(data.unit_id, station.id, data.effective_from, created_by)
        self.repository.replace_on_call_mappings(data.unit_id, station.id, data.on_call_station_ids)
        self.repository.commit()
        logger.info(
            "Created station %s (id=%s, unit_id=%s, effective_from=%s) by %s",
            station.name, station.id, data.unit_id, data.effective_from, get_current_user_label(),
        )
        return self._to_responses([station])[0]

    def update_station(self, station_id: int, unit_id: UUID, data: StationUpdate, created_by: Optional[UUID]) -> StationResponse:
        station = self.repository.get_by_id(station_id, unit_id)
        if not station:
            raise ValueError("Station not found")
        sent = data.model_dump(exclude_unset=True, exclude={"on_call_station_ids", "effective_from"})
        versions = self.repository.get_versions([station.id]).get(station.id, [])
        base = version_in_effect(versions, data.effective_from or date.today()) or (versions[0] if versions else None)
        base_config = versioned_config(base) if base else versioned_config(station)
        changed = {k: v for k, v in sent.items() if k in VERSIONED_STATION_FIELDS and base_config.get(k) != v}
        # secondary_to only means something on a secondary station.
        base_secondary_to = base_config.get("secondary_to") or []
        is_secondary = changed.get("is_secondary", base_config.get("is_secondary"))
        secondary_to = changed.get("secondary_to", base_secondary_to) if is_secondary else []
        if secondary_to != base_secondary_to:
            changed["secondary_to"] = secondary_to
        else:
            changed.pop("secondary_to", None)
        self._validate_secondary_to(unit_id, station.id, bool(is_secondary), secondary_to)
        if changed and data.effective_from is None:
            raise StationValidationError(
                "station_effective_from_required", "effective_from is required when changing a versioned station field",
            )
        self._validate_recurrence_not_in_past(changed, data.effective_from)

        on_call_ids = (
            data.on_call_station_ids if data.on_call_station_ids is not None
            else self.repository.get_on_call_station_ids([station.id]).get(station.id, [])
        )
        self._validate_on_call_station_ids(unit_id, data.on_call_station_ids)
        self._validate_prefer_day_before_on_call(changed.get("prefer_day_before_on_call", base_config["prefer_day_before_on_call"]), on_call_ids)

        self.repository.apply_fields(station, {k: v for k, v in sent.items() if k in GLOBAL_STATION_FIELDS})
        if changed:
            self.repository.write_version(station, data.effective_from, {**base_config, **changed}, created_by)
            self._apply_to_later_versions(station, versions, data.effective_from, changed, created_by)
            if changed.get("is_default"):
                self._clear_other_defaults(unit_id, station.id, data.effective_from, created_by)
        if data.on_call_station_ids is not None:
            self.repository.replace_on_call_mappings(unit_id, station.id, data.on_call_station_ids)
        self.repository.commit()
        logger.info(
            "Updated station %s (id=%s, unit_id=%s, versioned_change=%s, effective_from=%s) by %s",
            station.name, station_id, unit_id, bool(changed), data.effective_from, get_current_user_label(),
        )
        return self._to_responses([station])[0]

    def delete_station(self, station_id: int, unit_id: UUID, effective_from: date, deleted_by: Optional[UUID]) -> bool:
        """Writes a final is_retired version at `effective_from` (config of the
        version in effect then) and soft-deletes the station."""
        station = self.repository.get_by_id(station_id, unit_id)
        if not station:
            raise ValueError("Station not found")
        if effective_from < date.today().replace(day=1):
            raise StationValidationError(
                "station_delete_in_past",
                "A station can't be removed from a past month; effective_from must be in the current month or later",
            )
        versions = self.repository.get_versions([station.id]).get(station.id, [])
        base = version_in_effect(versions, effective_from) or (versions[0] if versions else None)
        config = versioned_config(base) if base else versioned_config(station)
        self.repository.write_version(station, effective_from, config, deleted_by, is_retired=True)
        self.repository.soft_delete(station, deleted_by)
        self.repository.commit()
        logger.info(
            "Deleted station %s (unit_id=%s, retired from %s) by %s",
            station.name, unit_id, effective_from, get_current_user_label(),
        )
        return True
