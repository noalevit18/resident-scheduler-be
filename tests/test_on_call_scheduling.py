from datetime import date
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import pytest

from app.schemas.schemas import OnCallSchedulingSave
from app.services.on_call_day_station_service import OnCallDayStationError
from app.services.on_call_scheduling_service import OnCallSchedulingService
from tests.fake_on_call_versions import FakeVersionRepository

MONTH = "2099-01"
UNIT, OTHER_UNIT, ACCOUNT, USER = uuid4(), uuid4(), uuid4(), uuid4()


class RecordingEntityService:
    """Stands in for the constraint / shift / day-station services: validates via `reject`, records writes."""

    def __init__(self, versions: FakeVersionRepository, kind: str, writes: list, reject: Exception | None = None):
        self.versions, self.kind, self.writes, self.reject = versions, kind, writes, reject

    def _validate(self, *args: Any) -> None:
        if self.reject:
            raise self.reject

    validate_entries = validate_shifts = _validate

    def _write(self, unit_id: UUID, *args: Any) -> None:
        version_row = args[-1]
        self.writes.append((self.kind, unit_id, version_row.version))

    write_entries = write_shifts = _write


def _service(reject_day_stations: Exception | None = None) -> tuple[OnCallSchedulingService, FakeVersionRepository, list]:
    versions, writes = FakeVersionRepository(), []
    service = OnCallSchedulingService(
        versions,  # type: ignore[arg-type]
        SimpleNamespace(get_published_unit_ids=lambda *args: []),  # type: ignore[arg-type]
        RecordingEntityService(versions, "constraints", writes),  # type: ignore[arg-type]
        RecordingEntityService(versions, "roster", writes),  # type: ignore[arg-type]
        RecordingEntityService(versions, "dayStations", writes, reject_day_stations),  # type: ignore[arg-type]
    )
    return service, versions, writes


def _save(**fields: Any) -> OnCallSchedulingSave:
    return OnCallSchedulingSave.model_validate({"accountId": str(ACCOUNT), **fields})


def _roster(unit_id: UUID) -> dict:
    return {"unitId": str(unit_id), "entries": [{"date": "2099-01-03", "stationAssignments": {}}]}


def test_one_save_writes_every_entity_under_one_version() -> None:
    service, versions, writes = _service()
    first = service.save(
        versions.division_id, MONTH,
        _save(
            constraints={"unitId": str(UNIT), "entries": []},
            rosters=[_roster(UNIT), _roster(OTHER_UNIT)],
            dayStations=[{"unitId": str(UNIT), "entries": []}],
        ),
        USER,
    )
    second = service.save(versions.division_id, MONTH, _save(rosters=[_roster(UNIT)]), USER)

    assert (first.version, second.version) == (1, 2)
    assert writes == [
        ("dayStations", UNIT, 1), ("constraints", UNIT, 1), ("roster", UNIT, 1), ("roster", OTHER_UNIT, 1),
        ("roster", UNIT, 2),
    ]


def test_nothing_is_written_when_any_part_is_rejected() -> None:
    service, versions, writes = _service(reject_day_stations=OnCallDayStationError("bad", "bad"))
    with pytest.raises(OnCallDayStationError):
        service.save(
            versions.division_id, MONTH,
            _save(rosters=[_roster(UNIT)], dayStations=[{"unitId": str(UNIT), "entries": []}]),
            USER,
        )
    assert (writes, versions.versions) == ([], [])


def test_rejects_an_empty_save_and_units_of_another_division() -> None:
    service, versions, _ = _service()
    with pytest.raises(ValueError):
        service.save(versions.division_id, MONTH, _save(), USER)
    with pytest.raises(ValueError):
        service.save(uuid4(), MONTH, _save(rosters=[_roster(UNIT)]), USER)


def test_day_station_entries_parse_with_their_unit() -> None:
    data = _save(dayStations=[{"unitId": str(UNIT), "entries": [{"date": "2099-01-05", "stationId": 1, "isAdded": True}]}])
    [changes] = data.day_stations
    assert (changes.unit_id, changes.entries[0].date) == (UNIT, date(2099, 1, 5))
