import logging
from uuid import UUID

from app.context import get_current_user_label
from app.models.models import OnCallDayNote
from app.repositories.on_call_day_note_repository import OnCallDayNoteRepository
from app.repositories.on_call_shift_repository import month_bounds
from app.schemas.schemas import OnCallDayNoteEntry, OnCallDayNotesResponse, OnCallDayNotesWrite

logger = logging.getLogger(__name__)


class OnCallDayNoteError(Exception):
    """A rejected day-notes save, in the API's `{ error, message }` shape."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


class OnCallDayNoteService:
    """The notes on days of a division's on-call roster, saved per month. Not
    versioned: every view shows the latest notes, old roster versions included."""

    def __init__(self, repository: OnCallDayNoteRepository):
        self.repository = repository

    def get_monthly_notes(self, division_id: UUID, month: str) -> OnCallDayNotesResponse:
        start, end = month_bounds(month)
        rows = self.repository.get_monthly_notes(division_id, start, end)
        return OnCallDayNotesResponse(
            division_id=division_id,
            month=month,
            entries=[OnCallDayNoteEntry(date=row.date, text=row.text) for row in rows],
        )

    def update_monthly_notes(
        self, division_id: UUID, month: str, data: OnCallDayNotesWrite, user_id: UUID | None,
    ) -> OnCallDayNotesResponse:
        """Replaces the division+month's notes. Every date must be in the month."""
        start, end = month_bounds(month)
        outside = sorted({entry.date.isoformat() for entry in data.entries if not start <= entry.date < end})
        if outside:
            raise OnCallDayNoteError("on_call_day_outside_month", f"Dates outside {month}: {', '.join(outside)}")

        db = self.repository.db
        try:
            self.repository.delete_month(division_id, start, end)
            self.repository.add_all([
                OnCallDayNote(division_id=division_id, date=entry.date, text=entry.text, created_by=user_id)
                for entry in data.entries
            ])
            db.commit()
        except Exception:
            db.rollback()
            raise
        logger.info(
            "Saved %d on-call day notes for division_id=%s month=%s by %s",
            len(data.entries), division_id, month, get_current_user_label(),
        )
        return self.get_monthly_notes(division_id, month)
