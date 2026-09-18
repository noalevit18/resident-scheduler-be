import logging
from datetime import date

from sqlalchemy.exc import IntegrityError

from app.repositories.special_date_repository import SpecialDateRepository
from app.schemas.schemas import SpecialDatesBulkUpdate
from app.context import get_current_user_label
from uuid import UUID

logger = logging.getLogger(__name__)


class DuplicateSpecialDateError(ValueError):
    """Raised when two entries in the same batch land on the same date."""


class SpecialDateService:
    def __init__(self, repository: SpecialDateRepository):
        self.repository = repository

    def get_all(self, account_id: UUID):
        return self.repository.get_all(account_id)

    def get_by_date(self, account_id: UUID, date: date):
        day = self.repository.get_by_date(account_id, date)
        if not day:
            raise ValueError("Special date not found")
        return day

    def save_all(self, data: SpecialDatesBulkUpdate, account_id: UUID, update_user_id: UUID | None):
        try:
            special_dates = self.repository.save_all(data.upserts, data.delete_dates, account_id, update_user_id)
        except IntegrityError:
            self.repository.db.rollback()
            raise DuplicateSpecialDateError("Duplicate date within the special dates batch")
        logger.info(
            "Saved special dates for account_id=%s (%d upserted, %d deleted) by %s",
            account_id, len(data.upserts), len(data.delete_dates), get_current_user_label(),
        )
        return special_dates
