import logging
from datetime import date, timedelta
from typing import Optional
from uuid import UUID

from app.models.models import FridayMode, SpecialDateType
from app.repositories.constraint_repository import month_bounds
from app.repositories.staff_member_submission_repository import StaffMemberSubmissionRepository
from app.services.constraint_type_service import ConstraintTypeService
from app.services.special_date_service import SpecialDateService
from app.services.staff_member_submission_metadata_service import StaffMemberSubmissionMetadataService
from app.services.staff_service import StaffService
from app.services.authorization_service import AuthorizationError
from app.schemas.schemas import MemberMonthlySubmissionUpdate, StaffMemberSubmissionEntry
from app.context import get_current_user_label

logger = logging.getLogger(__name__)

FRIDAY = 4  # date.weekday()


class StaffMemberSubmissionService:
    """Shared self-serve submission subsystem: a single date's entry can
    carry a constraint_type_id, an on_call_station_id, or both at once —
    used by both the constraints and on-call features' pull flows."""

    def __init__(
        self,
        repository: StaffMemberSubmissionRepository,
        submission_metadata_service: StaffMemberSubmissionMetadataService,
        staff_service: StaffService,
        special_date_service: SpecialDateService,
        constraint_type_service: ConstraintTypeService,
    ):
        self.repository = repository
        self.submission_metadata_service = submission_metadata_service
        self.staff_service = staff_service
        self.special_date_service = special_date_service
        self.constraint_type_service = constraint_type_service

    def get_member_month(
        self, unit_id: UUID, month: str, current_user: dict, staff_member_id: Optional[UUID] = None,
        is_admin: bool = False,
    ):
        """Defaults to the logged-in caller's own submission. `staff_member_id`
        fetches a specific member's instead — allowed for an admin, or for a
        regular member passing their own id (equivalent to omitting it);
        any other id is denied, per the "only their own submission" scope
        AuthorizationService documents as this service's responsibility to
        enforce."""
        if staff_member_id is None:
            staff_member = self.staff_service.is_logged_in_user_a_staff_member(unit_id, current_user)
            target_id = staff_member.id
        elif is_admin:
            self.staff_service.get_staff_member(staff_member_id, unit_id)  # raises ValueError if not in this unit
            target_id = staff_member_id
        else:
            staff_member = self.staff_service.is_logged_in_user_a_staff_member(unit_id, current_user)
            if staff_member.id != staff_member_id:
                raise AuthorizationError("You can only view your own submission")
            target_id = staff_member_id
        return self.repository.get_by_member_month(unit_id, target_id, month)

    def has_submitted_this_month(self, unit_id: UUID, current_user: dict) -> Optional[bool]:
        try:
            staff_member = self.staff_service.is_logged_in_user_a_staff_member(unit_id, current_user)
        except ValueError:
            return None
        month = date.today().strftime("%Y-%m")
        return self.repository.has_member_submitted(unit_id, staff_member.id, month)

    def get_submission_status(self, unit_id: UUID, month: str):
        """One row per staff member in the unit, flagging whether they have
        submitted anything (any entry, including the general comment) for
        this month yet."""
        members = self.staff_service.get_all_members(unit_id)
        submitted_ids = self.repository.get_submitted_staff_ids(unit_id, month)
        return [
            {"staff_member_id": m.id, "name": m.name, "submitted": m.id in submitted_ids}
            for m in members
        ]

    def _ranked_fridays(self, unit_id: UUID, month: str) -> list[date]:
        """The Fridays of `month` a member can rank: every calendar Friday except
        those the unit's account marked as a sabbatical. Their count is the
        month's highest allowed rank."""
        start, end = month_bounds(month)
        special_types = self.special_date_service.get_types_for_unit(unit_id, start, end)
        day = start + timedelta(days=(FRIDAY - start.weekday()) % 7)
        fridays = []
        while day < end:
            if special_types.get(day) != SpecialDateType.SABBATICAL:
                fridays.append(day)
            day += timedelta(days=7)
        return fridays

    def _validate_friday_ranks(self, unit_id: UUID, month: str, dated_entries: list[StaffMemberSubmissionEntry]):
        """In ranking mode a member ranks the month's Fridays (unique ranks,
        1..number of Fridays) in place of "want" types; otherwise no ranks."""
        ranked_entries = [e for e in dated_entries if e.rank is not None]
        if self.submission_metadata_service.get_friday_mode(unit_id, month) != FridayMode.RANKING:
            if ranked_entries:
                raise ValueError("Fridays can only be ranked when the month is in ranking mode")
            return

        fridays = set(self._ranked_fridays(unit_id, month))
        for entry in ranked_entries:
            if entry.date not in fridays:
                raise ValueError(f"{entry.date} is not a Friday that can be ranked")
            if entry.rank > len(fridays):
                raise ValueError(f"Ranks must be between 1 and {len(fridays)}")
        ranks = [e.rank for e in ranked_entries]
        if len(set(ranks)) != len(ranks):
            raise ValueError("Each rank can be used only once per month")

        friday_type_ids = [e.constraint_type_id for e in dated_entries if e.date in fridays and e.constraint_type_id is not None]
        preferences = self.constraint_type_service.get_preferences_by_ids(friday_type_ids)
        if any(preference > 0 for preference in preferences.values()):
            raise ValueError("Rank Fridays instead of marking them as wanted")

    def update_member_month(
        self, unit_id: UUID, month: str, data: MemberMonthlySubmissionUpdate, current_user: dict, empty: bool = False,
    ):
        staff_member = self.staff_service.is_logged_in_user_a_staff_member(unit_id, current_user)

        general_comment_entries = [e for e in data.entries if e.date is None]
        if len(general_comment_entries) > 1:
            raise ValueError("Only one general-comment entry (date=null) is allowed per request")

        dated_entries = [e for e in data.entries if e.date is not None]
        seen_dates = {e.date for e in dated_entries}
        if len(seen_dates) != len(dated_entries):
            raise ValueError("Only one submission entry is allowed per date")

        # The submission window is shared by every feature — gate on it
        # once if any entry carries a constraint_type_id or an
        # on_call_station_id.
        if any(
            e.constraint_type_id is not None or e.on_call_station_id is not None or e.rank is not None
            for e in data.entries
        ):
            self.submission_metadata_service.assert_window_open(unit_id, month)

        self._validate_friday_ranks(unit_id, month, dated_entries)

        rows = self.repository.upsert_many(unit_id, staff_member.id, month, data.entries, submitted_empty=empty)
        logger.info(
            "Updated %d submission entries (unit_id=%s, staff_member_id=%s, month=%s, empty=%s) by %s",
            len(rows), unit_id, staff_member.id, month, empty, get_current_user_label(),
        )
        return rows
