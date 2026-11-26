from datetime import date
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.models import OnCallDayNote


class OnCallDayNoteRepository:
    """The notes on days of a division's on-call roster. Not versioned: a
    month's notes are replaced as a whole on every save."""

    def __init__(self, db: Session):
        self.db = db

    # `start`..`end` is half-open: `end` is the next month's first day.

    def get_monthly_notes(self, division_id: UUID, start: date, end: date) -> list[OnCallDayNote]:
        return (
            self.db.query(OnCallDayNote)
            .filter(OnCallDayNote.division_id == division_id, OnCallDayNote.date >= start, OnCallDayNote.date < end)
            .order_by(OnCallDayNote.date)
            .all()
        )

    def delete_month(self, division_id: UUID, start: date, end: date) -> None:
        self.db.query(OnCallDayNote).filter(
            OnCallDayNote.division_id == division_id, OnCallDayNote.date >= start, OnCallDayNote.date < end,
        ).delete(synchronize_session=False)

    def add_all(self, rows: list[OnCallDayNote]) -> None:
        self.db.add_all(rows)
