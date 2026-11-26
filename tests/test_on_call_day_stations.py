from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from types import SimpleNamespace
from typing import Optional
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from app.models.models import OnCallDayStation
from app.repositories.on_call_shift_repository import month_bounds
from app.schemas.schemas import OnCallDayStationsWrite
from app.services.on_call_day_station_service import OnCallDayStationError, OnCallDayStationService
from tests.fake_on_call_versions import FakeVersionRepository


@dataclass
class FakeRepository:
    """In-memory stand-in for OnCallDayStationRepository's insert-only snapshots."""
    station_ids: set[int]
    rows: list[OnCallDayStation] = field(default_factory=list)
    versions: list[SimpleNamespace] = field(default_factory=list)

    def _versions_of(self, unit_id: UUID, month: str) -> list[SimpleNamespace]:
        return sorted(
            (v for v in self.versions if v.unit_id == unit_id and v.month == month),
            key=lambda v: v.version, reverse=True,
        )

    def get_latest_version_row(self, unit_id: UUID, month: str, for_update: bool = False) -> Optional[SimpleNamespace]:
        return next(iter(self._versions_of(unit_id, month)), None)

    def get_version_history(self, unit_id: UUID, month: str) -> list[SimpleNamespace]:
        return self._versions_of(unit_id, month)

    def get_by_version(self, unit_id: UUID, month: str, version: int) -> list[OnCallDayStation]:
        start, end = month_bounds(month)
        return sorted(
            (r for r in self.rows if r.unit_id == unit_id and start <= r.date < end and r.version == version),
            key=lambda r: (r.date, r.on_call_station_id),
        )

    def save_snapshot(
        self, unit_id: UUID, month: str, rows: list[OnCallDayStation], created_by: Optional[UUID], version: int,
    ) -> None:
        for row in rows:
            row.version = version
        self.rows.extend(rows)
        self.versions.append(SimpleNamespace(
            unit_id=unit_id, month=month, version=version, created_at=datetime.now(timezone.utc), created_by=created_by,
        ))

    def division_station_ids(self, division_id: UUID) -> set[int]:
        return self.station_ids


UNIT, OTHER_UNIT, DIVISION, USER = uuid4(), uuid4(), uuid4(), uuid4()


def _service() -> tuple[OnCallDayStationService, FakeRepository]:
    repository = FakeRepository(station_ids={1, 2})
    return OnCallDayStationService(repository, FakeVersionRepository(division_id=DIVISION)), repository  # type: ignore[arg-type]


def _write(*entries: dict) -> OnCallDayStationsWrite:
    return OnCallDayStationsWrite.model_validate({"entries": list(entries)})


def test_write_accepts_camel_case_and_rejects_a_station_changed_twice_a_day() -> None:
    data = _write({"date": "2099-01-05", "stationId": 1, "isAdded": True})
    assert data.entries[0].station_id == 1 and data.entries[0].is_added
    with pytest.raises(ValidationError):
        _write(
            {"date": "2099-01-05", "stationId": 1, "isAdded": True},
            {"date": "2099-01-05", "stationId": 1, "isAdded": False},
        )


def test_an_unsaved_month_is_version_0_with_no_changes() -> None:
    service, _ = _service()
    result = service.get_month(UNIT, "2099-01")
    assert (result.version, result.entries) == (0, [])


def test_each_save_is_a_new_version_and_earlier_versions_stay_readable() -> None:
    service, repository = _service()
    first = service.replace_month(UNIT, DIVISION, "2099-01", _write({"date": "2099-01-03", "stationId": 2, "isAdded": True}), USER)
    second = service.replace_month(UNIT, DIVISION, "2099-01", _write({"date": "2099-01-31", "stationId": 1, "isAdded": False}), USER)

    assert (first.version, second.version) == (1, 2)
    assert [(e.date, e.station_id, e.is_added) for e in second.entries] == [(date(2099, 1, 31), 1, False)]
    assert [(e.date, e.station_id) for e in service.get_month(UNIT, "2099-01", 1).entries] == [(date(2099, 1, 3), 2)]
    assert service.get_month(UNIT, "2099-01").version == 2
    assert [v.version for v in service.get_version_history(UNIT, "2099-01")] == [2, 1]
    assert len(repository.rows) == 2  # nothing deleted
    assert repository.rows[-1].created_by == USER


def test_clearing_every_change_still_makes_a_version() -> None:
    service, _ = _service()
    service.replace_month(UNIT, DIVISION, "2099-01", _write({"date": "2099-01-03", "stationId": 2, "isAdded": True}), USER)
    cleared = service.replace_month(UNIT, DIVISION, "2099-01", _write(), USER)
    assert (cleared.version, cleared.entries) == (2, [])
    assert len(service.get_month(UNIT, "2099-01", 1).entries) == 1


def test_versions_are_shared_by_the_division_and_month() -> None:
    service, _ = _service()
    service.replace_month(UNIT, DIVISION, "2099-01", _write({"date": "2099-01-03", "stationId": 2, "isAdded": True}), USER)
    other_unit = service.replace_month(OTHER_UNIT, DIVISION, "2099-01", _write(), USER)
    other_month = service.replace_month(UNIT, DIVISION, "2099-02", _write(), USER)
    assert (other_unit.version, other_month.version) == (2, 1)
    assert len(service.get_month(UNIT, "2099-01").entries) == 1


def test_a_version_reads_each_units_latest_changes_at_or_below_it() -> None:
    service, _ = _service()
    service.replace_month(UNIT, DIVISION, "2099-01", _write({"date": "2099-01-03", "stationId": 2, "isAdded": True}), USER)
    service.replace_month(OTHER_UNIT, DIVISION, "2099-01", _write(), USER)
    at_two = service.get_month(UNIT, "2099-01", 2)
    assert (at_two.version, [e.station_id for e in at_two.entries]) == (1, [2])
    assert (service.get_month(OTHER_UNIT, "2099-01", 1).version, service.get_month(OTHER_UNIT, "2099-01", 1).entries) == (0, [])


def test_replace_rejects_dates_outside_the_month_and_unknown_stations() -> None:
    service, repository = _service()
    with pytest.raises(OnCallDayStationError) as outside:
        service.replace_month(UNIT, DIVISION, "2099-01", _write({"date": "2099-02-01", "stationId": 1, "isAdded": True}), USER)
    assert outside.value.code == "on_call_day_outside_month"
    with pytest.raises(OnCallDayStationError) as unknown:
        service.replace_month(UNIT, DIVISION, "2099-01", _write({"date": "2099-01-02", "stationId": 9, "isAdded": True}), USER)
    assert unknown.value.code == "on_call_station_not_in_division"
    assert repository.versions == []


def test_replace_keeps_whether_a_change_shifts_the_turns() -> None:
    service, repository = _service()
    result = service.replace_month(
        UNIT, DIVISION, "2099-01",
        _write(
            {"date": "2099-01-04", "stationId": 1, "isAdded": False, "shiftsTurns": True},
            {"date": "2099-01-05", "stationId": 2, "isAdded": True},
        ),
        USER,
    )
    assert [(e.station_id, e.shifts_turns) for e in result.entries] == [(1, True), (2, False)]
    assert [row.shifts_turns for row in repository.rows] == [True, False]
