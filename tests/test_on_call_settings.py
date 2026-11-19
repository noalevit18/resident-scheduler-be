from dataclasses import dataclass, field
from typing import Optional
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from app.models.models import OnCallDistributionMode
from app.schemas.schemas import (
    OnCallStationCreate,
    OnCallStationGroupWrite,
    OnCallStationUpdateEntry,
    OnCallUnitSettingsWrite,
    OnCallGeneralSettingsWrite,
)
from app.services.on_call_settings_service import (
    OnCallSettingsError,
    OnCallSettingsService,
    check_turns_have_priority,
    drop_priority_from_rotation,
    validate_division_certifications,
    validate_division_rotations,
)


# --- Schemas ---

def test_station_defaults_to_daily_rotation_without_priority() -> None:
    station = OnCallStationCreate(name="ER", initials="ER")
    assert station.distribution_mode.value == "rotation_daily"
    assert station.priority_unit_id is None


def test_turns_station_needs_a_priority_unit() -> None:
    with pytest.raises(ValidationError):
        OnCallStationCreate.model_validate({"name": "NICU", "initials": "NI", "distributionMode": "turns"})
    station = OnCallStationCreate.model_validate({"name": "NICU", "initials": "NI", "distributionMode": "turns", "priorityUnitId": str(uuid4())})
    assert station.distribution_mode.value == "turns"


def test_update_rejects_null_distribution_but_allows_clearing_priority() -> None:
    with pytest.raises(ValidationError):
        OnCallStationUpdateEntry.model_validate({"id": 1, "distributionMode": None})
    entry = OnCallStationUpdateEntry.model_validate({"id": 1, "priorityUnitId": None})
    assert entry.model_dump(exclude_unset=True, exclude={"id"}) == {"priority_unit_id": None}


def test_group_requires_a_name_and_dedupes_stations() -> None:
    with pytest.raises(ValidationError):
        OnCallStationGroupWrite.model_validate({"stationIds": [1]})
    assert OnCallStationGroupWrite(name="Receiving day", station_ids=[3, 1, 3]).station_ids == [3, 1]


def test_unit_settings_default_to_every_station_without_priority() -> None:
    settings = OnCallUnitSettingsWrite()
    assert (settings.station_ids, settings.priority_station_ids) == ([], [])


# --- Unit settings service (fake repository) ---

@dataclass
class FakeStation:
    id: int
    name: str
    distribution_mode: OnCallDistributionMode = OnCallDistributionMode.ROTATION_DAILY
    priority_unit_id: Optional[UUID] = None
    rotation_unit_ids: list[UUID] = field(default_factory=list)


class FakeDb:
    def __init__(self) -> None:
        self.committed = False
        self.rolled_back = False

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True


@dataclass
class FakeRepository:
    stations: list[FakeStation]
    units: dict[UUID, str]
    coverage: dict[UUID, list[int]] = field(default_factory=dict)
    db: FakeDb = field(default_factory=FakeDb)

    def division_unit_names(self, division_id: UUID) -> dict[UUID, str]:
        return self.units

    def active_stations(self, division_id: UUID) -> list[FakeStation]:
        return self.stations

    def coverage_by_unit(self, division_id: UUID) -> dict[UUID, list[int]]:
        return self.coverage

    def replace_coverage(self, unit_id: UUID, station_ids: list[int]) -> None:
        if station_ids:
            self.coverage[unit_id] = list(station_ids)
        else:
            self.coverage.pop(unit_id, None)


NICU, WARD = uuid4(), uuid4()
DIVISION = uuid4()


def _service(stations: list[FakeStation]) -> tuple[OnCallSettingsService, FakeRepository]:
    repository = FakeRepository(stations=stations, units={NICU: "NICU", WARD: "Ward"})
    return OnCallSettingsService(repository), repository  # type: ignore[arg-type]


def test_priority_takes_over_the_station_and_releases_others() -> None:
    nicu_station = FakeStation(1, "NICU", priority_unit_id=WARD)
    er = FakeStation(2, "ER", priority_unit_id=NICU)
    service, repository = _service([nicu_station, er])

    result = service.update_unit_settings(NICU, DIVISION, OnCallUnitSettingsWrite(station_ids=[1], priority_station_ids=[1]))

    assert nicu_station.priority_unit_id == NICU
    assert er.priority_unit_id is None
    assert repository.coverage[NICU] == [1]
    assert result.priority_station_ids == [1]
    assert repository.db.committed


def test_priority_must_be_on_a_covered_station() -> None:
    service, repository = _service([FakeStation(1, "NICU"), FakeStation(2, "ER")])
    with pytest.raises(OnCallSettingsError) as error:
        service.update_unit_settings(NICU, DIVISION, OnCallUnitSettingsWrite(station_ids=[1], priority_station_ids=[2]))
    assert error.value.code == "on_call_priority_not_covered"
    assert not repository.db.committed


def test_unrestricted_unit_may_have_priority_anywhere() -> None:
    er = FakeStation(2, "ER")
    service, _ = _service([FakeStation(1, "NICU"), er])
    service.update_unit_settings(WARD, DIVISION, OnCallUnitSettingsWrite(priority_station_ids=[2]))
    assert er.priority_unit_id == WARD


def test_removing_the_priority_of_a_turns_station_is_refused() -> None:
    nicu_station = FakeStation(1, "NICU", distribution_mode=OnCallDistributionMode.TURNS, priority_unit_id=NICU)
    service, repository = _service([nicu_station])
    with pytest.raises(OnCallSettingsError) as error:
        service.update_unit_settings(NICU, DIVISION, OnCallUnitSettingsWrite(station_ids=[1]))
    assert error.value.code == "on_call_turns_needs_priority"
    assert repository.db.rolled_back


def test_unknown_unit_is_rejected() -> None:
    service, _ = _service([FakeStation(1, "NICU")])
    with pytest.raises(OnCallSettingsError):
        service.update_unit_settings(uuid4(), DIVISION, OnCallUnitSettingsWrite())


def test_turns_check_passes_with_a_priority_unit() -> None:
    check_turns_have_priority([FakeStation(1, "NICU", OnCallDistributionMode.TURNS, NICU)])  # type: ignore[list-item]


# --- Rotation order and start date ---

def test_station_rotation_defaults_to_no_explicit_order_and_no_date() -> None:
    station = OnCallStationCreate(name="ICU", initials="IC")
    assert station.rotation_unit_ids == []
    assert station.rotation_start_date is None


def test_station_rotation_order_is_deduped_and_date_parsed() -> None:
    first, second = uuid4(), uuid4()
    station = OnCallStationCreate.model_validate({
        "name": "ICU", "initials": "IC", "distributionMode": "rotation_weekly", "rotationStartDate": "2026-11-01",
        "rotationUnitIds": [str(second), str(first), str(second)],
    })
    assert station.rotation_unit_ids == [second, first]
    assert station.rotation_start_date.isoformat() == "2026-11-01"


def test_update_rejects_null_rotation_fields() -> None:
    with pytest.raises(ValidationError):
        OnCallStationUpdateEntry.model_validate({"id": 1, "rotationStartDate": None})
    with pytest.raises(ValidationError):
        OnCallStationUpdateEntry.model_validate({"id": 1, "rotationUnitIds": None})


def test_priority_unit_leaves_the_rotation() -> None:
    station = FakeStation(1, "ICU", priority_unit_id=NICU, rotation_unit_ids=[WARD, NICU])
    drop_priority_from_rotation(station)  # type: ignore[arg-type]
    assert station.rotation_unit_ids == [WARD]


def test_taking_priority_removes_the_unit_from_the_rotation() -> None:
    icu = FakeStation(1, "ICU", rotation_unit_ids=[NICU, WARD])
    service, _ = _service([icu])
    service.update_unit_settings(NICU, DIVISION, OnCallUnitSettingsWrite(priority_station_ids=[1]))
    assert icu.rotation_unit_ids == [WARD]


# --- Staff rotation mapping ---

class FakeRotationRepository:
    def division_rotation_ids(self, division_id: UUID) -> set[int]:
        return {3, 4}


def test_station_staff_rotation_is_optional_and_clearable() -> None:
    assert OnCallStationCreate(name="ER", initials="ER").staff_rotation_id is None
    assert OnCallStationCreate.model_validate({"name": "ER", "initials": "ER", "staffRotationId": 3}).staff_rotation_id == 3
    entry = OnCallStationUpdateEntry.model_validate({"id": 1, "staffRotationId": None})
    assert entry.model_dump(exclude_unset=True, exclude={"id"}) == {"staff_rotation_id": None}


def test_staff_rotation_must_belong_to_the_division() -> None:
    repository = FakeRotationRepository()
    validate_division_rotations(repository, DIVISION, [3, 4])  # type: ignore[arg-type]
    with pytest.raises(OnCallSettingsError) as error:
        validate_division_rotations(repository, DIVISION, [3, 9])  # type: ignore[arg-type]
    assert error.value.code == "on_call_rotation_not_in_division"


# --- Required certifications ---

class FakeCertificationRepository:
    def division_certification_ids(self, division_id: UUID) -> set[int]:
        return {10, 11}


def test_required_certifications_default_empty_deduped_and_not_null() -> None:
    assert OnCallStationCreate(name="ER", initials="ER").required_certification_ids == []
    station = OnCallStationCreate.model_validate({"name": "ER", "initials": "ER", "requiredCertificationIds": [11, 10, 11]})
    assert station.required_certification_ids == [11, 10]
    with pytest.raises(ValidationError):
        OnCallStationUpdateEntry.model_validate({"id": 1, "requiredCertificationIds": None})


def test_required_certifications_must_belong_to_the_division() -> None:
    repository = FakeCertificationRepository()
    validate_division_certifications(repository, DIVISION, [10, 11])  # type: ignore[arg-type]
    with pytest.raises(OnCallSettingsError) as error:
        validate_division_certifications(repository, DIVISION, [10, 99])  # type: ignore[arg-type]
    assert error.value.code == "on_call_certification_not_in_division"


# --- Rotation length ---

def test_rotation_length_defaults_to_one_and_is_bounded() -> None:
    assert OnCallStationCreate(name="ICU", initials="I").rotation_length == 1
    station = OnCallStationCreate.model_validate(
        {"name": "ICU", "initials": "I", "distributionMode": "rotation_weekly", "rotationLength": 2},
    )
    assert station.rotation_length == 2
    with pytest.raises(ValidationError):
        OnCallStationCreate(name="ICU", initials="I", rotation_length=0)
    with pytest.raises(ValidationError):
        OnCallStationUpdateEntry.model_validate({"id": 1, "rotationLength": None})


# --- General settings ---

class FakeGeneralRepository:
    def __init__(self) -> None:
        self.settings: Optional[object] = None
        self.db = FakeDb()

    def get_division_settings(self, division_id: UUID) -> Optional[object]:
        return self.settings

    def add_division_settings(self, settings: object) -> None:
        self.settings = settings


def test_shift_length_is_bounded() -> None:
    assert OnCallGeneralSettingsWrite.model_validate({"shiftLengthHours": 26}).shift_length_hours == 26
    for value in (0, 49):
        with pytest.raises(ValidationError):
            OnCallGeneralSettingsWrite(shift_length_hours=value)


def test_general_settings_default_then_saved() -> None:
    repository = FakeGeneralRepository()
    service = OnCallSettingsService(repository)  # type: ignore[arg-type]
    assert service.get_general_settings(DIVISION).shift_length_hours == 24

    saved = service.update_general_settings(DIVISION, OnCallGeneralSettingsWrite(shift_length_hours=21))

    assert saved.shift_length_hours == 21
    assert service.get_general_settings(DIVISION).shift_length_hours == 21
    assert repository.db.committed


def test_soft_delete_keeps_the_row_and_records_when() -> None:
    from types import SimpleNamespace
    from app.repositories.on_call_station_repository import OnCallStationRepository

    station = SimpleNamespace(is_deleted=False, deleted_at=None, group_id=3, unit_coverage=["covers"])
    OnCallStationRepository(db=None).soft_delete(station)  # type: ignore[arg-type]
    assert station.is_deleted is True
    assert station.deleted_at is not None and station.deleted_at.tzinfo is not None
    assert station.group_id is None and station.unit_coverage == []
