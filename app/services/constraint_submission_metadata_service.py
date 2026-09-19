import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from app.repositories.constraint_submission_metadata_repository import ConstraintSubmissionMetadataRepository
from app.services.user_service import UserService
from app.schemas.schemas import ConstraintSubmissionMetadataUpdate
from app.context import get_current_user_label

logger = logging.getLogger(__name__)


class SubmissionWindowError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


class ConstraintSubmissionMetadataService:
    def __init__(self, repository: ConstraintSubmissionMetadataRepository, user_service: UserService):
        self.repository = repository
        self.user_service = user_service

    def get(self, unit_id: UUID, month: str):
        return self.repository.get_by_unit_month(unit_id, month)

    def upsert(self, data: ConstraintSubmissionMetadataUpdate, current_user: dict):
        updated_by = self.user_service.get_logged_in_user_id(current_user)
        row = self.repository.upsert(data.unit_id, data.month, data.start_time, data.end_time, updated_by)
        logger.info(
            "Updated constraint submission window (unit_id=%s, month=%s, start=%s, end=%s) by %s",
            data.unit_id, data.month, data.start_time, data.end_time, get_current_user_label(),
        )
        return row

    def mark_pulled(self, unit_id: UUID, month: str, pulled_by: Optional[UUID]):
        row = self.repository.mark_pulled(unit_id, month, pulled_by)
        logger.info(
            "Marked constraint submission window as pulled (unit_id=%s, month=%s) by %s",
            unit_id, month, get_current_user_label(),
        )
        return row

    def assert_window_open(self, unit_id: UUID, month: str):
        row = self.repository.get_by_unit_month(unit_id, month)
        now = datetime.now(timezone.utc)
        if not row:
            raise SubmissionWindowError("window_not_configured", "Submission window not configured for this month")
        if now < row.start_time:
            raise SubmissionWindowError("window_not_open", "Submission window is not open yet")
        if row.end_time is not None and now > row.end_time:
            raise SubmissionWindowError("window_closed", "Submission window has closed")
