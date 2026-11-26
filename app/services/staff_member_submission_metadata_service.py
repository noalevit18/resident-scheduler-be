import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from app.models.models import FridayMode, SubmissionScope
from app.repositories.staff_member_submission_metadata_repository import StaffMemberSubmissionMetadataRepository
from app.repositories.staff_member_submission_repository import StaffMemberSubmissionRepository
from app.services.user_service import UserService
from app.schemas.schemas import OnCallSubmissionWindowUpdate, SubmissionFeature, SubmissionWindowUpdate
from app.context import get_current_user_label

logger = logging.getLogger(__name__)

# Which scope's row tracks each feature's pulls. SubmissionFeature.on_call
# (the old on-call station requests pull) is no longer pulled; its key stays
# readable in past months' pull_information.
FEATURE_SCOPES = {
    SubmissionFeature.constraints: SubmissionScope.SCHEDULE,
    SubmissionFeature.on_call_constraints: SubmissionScope.ON_CALL,
}


class SubmissionWindowError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


class StaffMemberSubmissionMetadataService:
    """Submission windows, one row per (unit_id, month, scope):
    - SCHEDULE: the daily schedule's window — constraints, Friday mode and
      on-call shift requests. Managed via /submissions/metadata.
    - ON_CALL: the on-call constraints' own window. Managed via
      /on-call-constraints/submissions/metadata.
    Each opens and closes independently, and pull_information tracks each
    feature's pulls on its scope's row (see FEATURE_SCOPES)."""

    def __init__(
        self,
        repository: StaffMemberSubmissionMetadataRepository,
        user_service: UserService,
        submission_repository: StaffMemberSubmissionRepository,
    ):
        self.repository = repository
        self.user_service = user_service
        self.submission_repository = submission_repository

    # --- shared, scoped ---

    def get(self, unit_id: UUID, month: str, scope: SubmissionScope):
        return self.repository.get_by_unit_month(unit_id, month, scope)

    def clear_window(self, unit_id: UUID, month: str, scope: SubmissionScope) -> bool:
        cleared = self.repository.clear_window(unit_id, month, scope)
        if cleared:
            logger.info(
                "Cleared %s submission window (unit_id=%s, month=%s) by %s",
                scope.value, unit_id, month, get_current_user_label(),
            )
        return cleared

    def mark_pulled(self, unit_id: UUID, month: str, feature: SubmissionFeature, pulled_by: Optional[UUID]):
        scope = FEATURE_SCOPES[feature]
        row = self.repository.mark_pulled(unit_id, month, scope, feature, pulled_by)
        logger.info(
            "Marked %s submission window as pulled (unit_id=%s, month=%s, feature=%s) by %s",
            scope.value, unit_id, month, feature.value, get_current_user_label(),
        )
        return row

    def assert_window_open(self, unit_id: UUID, month: str, scope: SubmissionScope):
        row = self.repository.get_by_unit_month(unit_id, month, scope)
        label = "On-call submission window" if scope == SubmissionScope.ON_CALL else "Submission window"
        now = datetime.now(timezone.utc)
        if not row or row.start_time is None:
            raise SubmissionWindowError("window_not_configured", f"{label} not configured for this month")
        if now < row.start_time:
            raise SubmissionWindowError("window_not_open", f"{label} is not open yet")
        if row.end_time is not None and now > row.end_time:
            raise SubmissionWindowError("window_closed", f"{label} has closed")

    # --- daily schedule window ---

    def upsert(self, data: SubmissionWindowUpdate, current_user: dict):
        updated_by = self.user_service.get_logged_in_user_id(current_user)
        if data.friday_mode is not None and data.friday_mode.value != self.get_friday_mode(data.unit_id, data.month).value:
            # Switching modes mid-month would mix ranks with want/prefer-not submissions.
            if self.submission_repository.get_submitted_staff_ids(data.unit_id, data.month):
                raise SubmissionWindowError(
                    "friday_mode_locked", "The Friday mode can't change once members have submitted for this month",
                )
        row = self.repository.upsert(
            data.unit_id, data.month, SubmissionScope.SCHEDULE, data.start_time, data.end_time, updated_by,
            FridayMode(data.friday_mode.value) if data.friday_mode is not None else None,
        )
        logger.info(
            "Updated schedule submission window (unit_id=%s, month=%s, start=%s, end=%s, friday_mode=%s) by %s",
            data.unit_id, data.month, data.start_time, data.end_time, data.friday_mode, get_current_user_label(),
        )
        return row

    def get_friday_mode(self, unit_id: UUID, month: str) -> FridayMode:
        row = self.repository.get_by_unit_month(unit_id, month, SubmissionScope.SCHEDULE)
        return row.friday_mode if row else FridayMode.PREFERENCE

    # --- on-call constraints window ---

    def upsert_on_call(self, data: OnCallSubmissionWindowUpdate, current_user: dict):
        updated_by = self.user_service.get_logged_in_user_id(current_user)
        row = self.repository.upsert(
            data.unit_id, data.month, SubmissionScope.ON_CALL, data.start_time, data.end_time, updated_by,
        )
        logger.info(
            "Updated on-call submission window (unit_id=%s, month=%s, start=%s, end=%s) by %s",
            data.unit_id, data.month, data.start_time, data.end_time, get_current_user_label(),
        )
        return row
