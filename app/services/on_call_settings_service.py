import logging
from typing import Iterable
from uuid import UUID

from sqlalchemy.exc import IntegrityError

from app.context import get_current_user_label
from app.models.models import OnCallDistributionMode, OnCallDivisionSettings, OnCallStation, OnCallStationGroup
from app.repositories.on_call_settings_repository import OnCallSettingsRepository
from app.schemas.schemas import (
    OnCallGeneralSettingsResponse,
    OnCallGeneralSettingsWrite,
    OnCallStationGroupWrite,
    OnCallUnitSettingsResponse,
    OnCallUnitSettingsWrite,
)

logger = logging.getLogger(__name__)


class OnCallSettingsError(Exception):
    """A settings request that's well-formed but can't be applied (400)."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


class OnCallGroupNameConflictError(OnCallSettingsError):
    """Another group in the division has this name (409)."""


def validate_division_units(repository: OnCallSettingsRepository, division_id: UUID, unit_ids: Iterable[UUID]) -> None:
    unknown = set(unit_ids) - set(repository.division_unit_names(division_id))
    if unknown:
        raise OnCallSettingsError(
            "on_call_unit_not_in_division", f"Unit(s) not in this division: {sorted(str(u) for u in unknown)}",
        )


def validate_division_rotations(repository: OnCallSettingsRepository, division_id: UUID, rotation_ids: Iterable[int]) -> None:
    unknown = set(rotation_ids) - repository.division_rotation_ids(division_id)
    if unknown:
        raise OnCallSettingsError(
            "on_call_rotation_not_in_division", f"Staff rotation(s) not in this division: {sorted(unknown)}",
        )


def validate_division_certifications(
    repository: OnCallSettingsRepository, division_id: UUID, certification_ids: Iterable[int],
) -> None:
    unknown = set(certification_ids) - repository.division_certification_ids(division_id)
    if unknown:
        raise OnCallSettingsError(
            "on_call_certification_not_in_division", f"Staff certification(s) not in this division: {sorted(unknown)}",
        )


def active_stations_by_id(repository: OnCallSettingsRepository, division_id: UUID, station_ids: Iterable[int]) -> dict[int, OnCallStation]:
    stations = {station.id: station for station in repository.active_stations(division_id)}
    missing = set(station_ids) - set(stations)
    if missing:
        raise ValueError(f"On-call station(s) not found: {sorted(missing)}")
    return stations


def check_turns_have_priority(stations: Iterable[OnCallStation]) -> None:
    for station in stations:
        if station.distribution_mode == OnCallDistributionMode.TURNS and station.priority_unit_id is None:
            raise OnCallSettingsError(
                "on_call_turns_needs_priority",
                f"'{station.name}' is distributed by turns, so it needs a priority unit",
            )


def ensure_priority_unit_covers(repository: OnCallSettingsRepository, division_id: UUID, station: OnCallStation) -> None:
    """A priority unit must be able to cover its station: a restricted unit
    gets the station added to what it covers."""
    if station.priority_unit_id is None:
        return
    if station.priority_unit_id in repository.coverage_by_unit(division_id):
        repository.add_coverage(station.priority_unit_id, station.id)


def drop_priority_from_rotation(station: OnCallStation) -> None:
    """The priority unit isn't part of the station's rotation: it only takes
    the days it asks for, and the other units share the rest."""
    if station.priority_unit_id is not None and station.priority_unit_id in station.rotation_unit_ids:
        station.rotation_unit_ids = [unit_id for unit_id in station.rotation_unit_ids if unit_id != station.priority_unit_id]


class OnCallSettingsService:
    def __init__(self, repository: OnCallSettingsRepository):
        self.repository = repository

    # --- General ---

    def get_general_settings(self, division_id: UUID) -> OnCallGeneralSettingsResponse:
        """The division's settings, or the defaults when it never saved any."""
        settings = self.repository.get_division_settings(division_id)
        if settings is None:
            return OnCallGeneralSettingsResponse()
        return OnCallGeneralSettingsResponse(shift_length_hours=settings.shift_length_hours)

    def update_general_settings(self, division_id: UUID, data: OnCallGeneralSettingsWrite) -> OnCallGeneralSettingsResponse:
        settings = self.repository.get_division_settings(division_id)
        if settings is None:
            settings = OnCallDivisionSettings(division_id=division_id)
            self.repository.add_division_settings(settings)
        settings.shift_length_hours = data.shift_length_hours
        self.repository.db.commit()
        logger.info(
            "Updated on-call general settings (division_id=%s, shift_length_hours=%s) by %s",
            division_id, data.shift_length_hours, get_current_user_label(),
        )
        return OnCallGeneralSettingsResponse(shift_length_hours=settings.shift_length_hours)

    # --- Groups ---

    def get_groups(self, division_id: UUID) -> list[OnCallStationGroup]:
        return self.repository.get_groups(division_id)

    def create_group(self, division_id: UUID, data: OnCallStationGroupWrite) -> OnCallStationGroup:
        self._check_group_name_free(division_id, data.name, group_id=None)
        stations = active_stations_by_id(self.repository, division_id, data.station_ids)
        group = OnCallStationGroup(division_id=division_id, name=data.name)
        self.repository.add_group(group)
        self.repository.db.flush()
        self._set_members(group, [stations[station_id] for station_id in data.station_ids])
        self._commit()
        self.repository.db.refresh(group)
        logger.info("Created on-call station group %s (division_id=%s) by %s", group.name, division_id, get_current_user_label())
        return group

    def update_group(self, group_id: int, division_id: UUID, data: OnCallStationGroupWrite) -> OnCallStationGroup:
        group = self._get_group_or_raise(group_id, division_id)
        self._check_group_name_free(division_id, data.name, group_id=group.id)
        stations = active_stations_by_id(self.repository, division_id, data.station_ids)
        group.name = data.name
        self._set_members(group, [stations[station_id] for station_id in data.station_ids])
        self._commit()
        self.repository.db.refresh(group)
        logger.info("Updated on-call station group %s (division_id=%s) by %s", group.name, division_id, get_current_user_label())
        return group

    def delete_group(self, group_id: int, division_id: UUID) -> None:
        group = self._get_group_or_raise(group_id, division_id)
        for station in self.repository.stations_in_group(group.id):
            station.group_id = None
        self.repository.delete_group(group)
        self._commit()
        logger.info("Deleted on-call station group %s (division_id=%s) by %s", group.name, division_id, get_current_user_label())

    def _set_members(self, group: OnCallStationGroup, members: list[OnCallStation]) -> None:
        """Listed stations join the group in list order (leaving any other
        group); the group's stations that aren't listed leave it."""
        member_ids = {station.id for station in members}
        for station in self.repository.stations_in_group(group.id):
            if station.id not in member_ids:
                station.group_id = None
        for order, station in enumerate(members):
            station.group_id = group.id
            station.group_order = order

    def _get_group_or_raise(self, group_id: int, division_id: UUID) -> OnCallStationGroup:
        group = self.repository.get_group(group_id, division_id)
        if group is None:
            raise ValueError("On-call station group not found")
        return group

    def _check_group_name_free(self, division_id: UUID, name: str, group_id: int | None) -> None:
        existing = self.repository.get_group_by_name(name, division_id)
        if existing is not None and existing.id != group_id:
            raise OnCallGroupNameConflictError("on_call_group_duplicate_name", f"A group named '{name}' already exists")

    # --- Units ---

    def get_unit_settings(self, division_id: UUID) -> list[OnCallUnitSettingsResponse]:
        """Every unit of the division, unrestricted ones (`station_ids` empty) included."""
        coverage = self.repository.coverage_by_unit(division_id)
        priority: dict[UUID, list[int]] = {}
        for station in sorted(self.repository.active_stations(division_id), key=lambda s: s.id):
            if station.priority_unit_id is not None:
                priority.setdefault(station.priority_unit_id, []).append(station.id)
        return [
            OnCallUnitSettingsResponse(
                unit_id=unit_id, station_ids=coverage.get(unit_id, []), priority_station_ids=priority.get(unit_id, []),
            )
            for unit_id in self.repository.division_unit_names(division_id)
        ]

    def update_unit_settings(self, unit_id: UUID, division_id: UUID, data: OnCallUnitSettingsWrite) -> OnCallUnitSettingsResponse:
        validate_division_units(self.repository, division_id, [unit_id])
        stations = active_stations_by_id(self.repository, division_id, [*data.station_ids, *data.priority_station_ids])
        if data.station_ids:
            uncovered = [stations[station_id].name for station_id in data.priority_station_ids if station_id not in data.station_ids]
            if uncovered:
                raise OnCallSettingsError(
                    "on_call_priority_not_covered",
                    f"The unit can't have priority on stations it doesn't cover: {', '.join(uncovered)}",
                )

        priority_ids = set(data.priority_station_ids)
        try:
            self.repository.replace_coverage(unit_id, data.station_ids)
            for station in stations.values():
                if station.id in priority_ids:
                    station.priority_unit_id = unit_id
                    drop_priority_from_rotation(station)
                elif station.priority_unit_id == unit_id:
                    station.priority_unit_id = None
            check_turns_have_priority(stations.values())
        except OnCallSettingsError:
            self.repository.db.rollback()
            raise
        self._commit()
        logger.info(
            "Updated on-call unit settings (unit_id=%s, station_ids=%s, priority_station_ids=%s) by %s",
            unit_id, data.station_ids, data.priority_station_ids, get_current_user_label(),
        )
        return OnCallUnitSettingsResponse(
            unit_id=unit_id, station_ids=sorted(data.station_ids), priority_station_ids=sorted(priority_ids),
        )

    def _commit(self) -> None:
        try:
            self.repository.db.commit()
        except IntegrityError as e:
            self.repository.db.rollback()
            raise OnCallGroupNameConflictError("on_call_group_duplicate_name", "A group with this name already exists") from e
