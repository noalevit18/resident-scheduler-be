from dataclasses import dataclass, field
from datetime import date
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from app.models.models import OnCallDayNote
from app.schemas.schemas import OnCallDayNotesWrite
from app.services.on_call_day_note_service import OnCallDayNoteError, OnCallDayNoteService


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
    rows: list[OnCallDayNote] = field(default_factory=list)
    db: FakeDb = field(default_factory=FakeDb)

    def get_monthly_notes(self, division_id: UUID, start: date, end: date) -> list[OnCallDayNote]:
        return sorted(
            (row for row in self.rows if row.division_id == division_id and start <= row.date < end),
            key=lambda row: row.date,
        )

    def delete_month(self, division_id: UUID, start: date, end: date) -> None:
        self.rows = [row for row in self.rows if not (row.division_id == division_id and start <= row.date < end)]

    def add_all(self, rows: list[OnCallDayNote]) -> None:
        self.rows.extend(rows)


DIVISION, OTHER_DIVISION, USER = uuid4(), uuid4(), uuid4()


def _service(rows: list[OnCallDayNote] | None = None) -> tuple[OnCallDayNoteService, FakeRepository]:
    repository = FakeRepository(rows=list(rows or []))
    return OnCallDayNoteService(repository), repository  # type: ignore[arg-type]


def _write(*entries: tuple[str, str]) -> OnCallDayNotesWrite:
    return OnCallDayNotesWrite.model_validate({"entries": [{"date": day, "text": text} for day, text in entries]})


def test_write_trims_the_text_and_rejects_blank_long_or_duplicate_notes() -> None:
    assert _write(("2099-01-05", "  2 ER releasers  ")).entries[0].text == "2 ER releasers"
    with pytest.raises(ValidationError):
        _write(("2099-01-05", "   "))
    with pytest.raises(ValidationError):
        _write(("2099-01-05", "x" * 501))
    with pytest.raises(ValidationError):
        _write(("2099-01-05", "a"), ("2099-01-05", "b"))


def test_save_replaces_only_the_divisions_month() -> None:
    kept_other_month = OnCallDayNote(division_id=DIVISION, date=date(2099, 2, 1), text="February")
    kept_other_division = OnCallDayNote(division_id=OTHER_DIVISION, date=date(2099, 1, 5), text="Other")
    replaced = OnCallDayNote(division_id=DIVISION, date=date(2099, 1, 3), text="Old")
    service, repository = _service([kept_other_month, kept_other_division, replaced])

    response = service.update_monthly_notes(DIVISION, "2099-01", _write(("2099-01-31", "New")), USER)

    assert [(entry.date, entry.text) for entry in response.entries] == [(date(2099, 1, 31), "New")]
    assert kept_other_month in repository.rows and kept_other_division in repository.rows
    assert replaced not in repository.rows
    assert repository.rows[-1].created_by == USER
    assert repository.db.committed


def test_save_rejects_a_date_outside_the_month() -> None:
    service, repository = _service()
    with pytest.raises(OnCallDayNoteError) as error:
        service.update_monthly_notes(DIVISION, "2099-01", _write(("2099-02-01", "Too late")), USER)
    assert error.value.code == "on_call_day_outside_month"
    assert not repository.db.committed
