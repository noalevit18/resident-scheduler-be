import pytest
from pydantic import ValidationError

from app.schemas.schemas import (
    OnCallStationCreate,
    OnCallStationsUpdate,
    OnCallStationUpdateEntry,
)


def test_create_defaults_to_one_resident() -> None:
    entry = OnCallStationCreate(name="ER", initials="ER")
    assert entry.number_of_residents == 1


def test_create_accepts_camel_case() -> None:
    entry = OnCallStationCreate.model_validate({"name": "ER", "initials": "ER", "numberOfResidents": 2})
    assert entry.number_of_residents == 2


def test_active_days_is_no_longer_a_station_field() -> None:
    """On-call stations are active every day; a stale client sending activeDays is ignored."""
    entry = OnCallStationCreate.model_validate({"name": "ER", "initials": "ER", "activeDays": [0, 1]})
    assert "active_days" not in entry.model_dump()
    update = OnCallStationUpdateEntry.model_validate({"id": 1, "activeDays": [0, 1]})
    assert update.model_dump(exclude_unset=True, exclude={"id"}) == {}


@pytest.mark.parametrize("value", [0, -1, 51])
def test_number_of_residents_bounds(value: int) -> None:
    with pytest.raises(ValidationError):
        OnCallStationCreate(name="ER", initials="ER", number_of_residents=value)
    with pytest.raises(ValidationError):
        OnCallStationUpdateEntry(id=1, number_of_residents=value)


def test_update_omitted_fields_are_not_set() -> None:
    entry = OnCallStationUpdateEntry(id=1, name="ER")
    assert entry.model_dump(exclude_unset=True, exclude={"id"}) == {"name": "ER"}


def test_update_rejects_null_number_of_residents() -> None:
    with pytest.raises(ValidationError):
        OnCallStationUpdateEntry.model_validate({"id": 1, "numberOfResidents": None})
    with pytest.raises(ValidationError):
        OnCallStationCreate.model_validate({"name": "ER", "initials": "ER", "numberOfResidents": None})


def test_update_sets_number_of_residents() -> None:
    entry = OnCallStationUpdateEntry.model_validate({"id": 1, "numberOfResidents": 3})
    assert entry.model_dump(exclude_unset=True, exclude={"id"}) == {"number_of_residents": 3}


def test_update_sets_number_of_residents_in_batch_payload() -> None:
    payload = OnCallStationsUpdate.model_validate({"entries": [{"id": 1, "numberOfResidents": 4}]})
    assert payload.entries[0].number_of_residents == 4


def test_initials_are_optional_and_short() -> None:
    assert OnCallStationCreate(name="ER").initials is None
    assert OnCallStationCreate(name="ER", initials="  ").initials is None
    with pytest.raises(ValidationError):
        OnCallStationCreate(name="ER", initials="TOOLONG")
    assert OnCallStationCreate(name="פגיה 1", initials="פ1").initials == "פ1"
    cleared = OnCallStationUpdateEntry.model_validate({"id": 1, "initials": None})
    assert cleared.initials is None and "initials" in cleared.model_fields_set


def test_requires_independent_defaults_to_false() -> None:
    assert OnCallStationCreate(name="ER2", initials="E2").requires_independent is False
    assert OnCallStationCreate.model_validate({"name": "ER1", "initials": "E1", "requiresIndependent": True}).requires_independent
    with pytest.raises(ValidationError):
        OnCallStationUpdateEntry.model_validate({"id": 1, "requiresIndependent": None})


def test_open_to_external_defaults_to_false() -> None:
    assert OnCallStationCreate(name="ER2", initials="E2").open_to_external is False
    assert OnCallStationCreate.model_validate({"name": "ER1", "initials": "E1", "openToExternal": True}).open_to_external
    assert OnCallStationUpdateEntry.model_validate({"id": 1, "openToExternal": True}).open_to_external
    with pytest.raises(ValidationError):
        OnCallStationUpdateEntry.model_validate({"id": 1, "openToExternal": None})


def test_manual_distribution_needs_no_priority_unit() -> None:
    station = OnCallStationCreate.model_validate({"name": "ER3", "initials": "E3", "distributionMode": "manual"})
    assert station.distribution_mode.value == "manual"
    assert station.priority_unit_id is None
