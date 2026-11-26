import logging
from typing import Optional
from uuid import UUID

from app.models.models import ConstraintTypeScope, SubmissionScope
from app.repositories.on_call_submission_repository import OnCallSubmissionRepository, OnCallSubmitter
from app.services.authorization_service import AuthorizationError
from app.services.constraint_type_service import ConstraintTypeService
from app.services.external_on_call_physician_service import ExternalOnCallPhysicianService
from app.services.staff_member_submission_metadata_service import StaffMemberSubmissionMetadataService
from app.services.staff_service import StaffService
from app.services.user_service import UserService
from app.schemas.schemas import MemberMonthlyOnCallSubmissionUpdate
from app.context import get_current_user_label

logger = logging.getLogger(__name__)


class OnCallSubmissionService:
    """The self-serve on-call constraints form — separate from the daily
    schedule's submissions: its own rows, general comment, "submitted empty"
    flag, submission status and (ON_CALL) submission window. Open to the
    unit's staff members and to its external on-call physicians active in the
    month."""

    def __init__(
        self,
        repository: OnCallSubmissionRepository,
        submission_metadata_service: StaffMemberSubmissionMetadataService,
        staff_service: StaffService,
        constraint_type_service: ConstraintTypeService,
        external_physician_service: ExternalOnCallPhysicianService,
        user_service: UserService,
    ):
        self.repository = repository
        self.submission_metadata_service = submission_metadata_service
        self.staff_service = staff_service
        self.constraint_type_service = constraint_type_service
        self.external_physician_service = external_physician_service
        self.user_service = user_service

    def _find_self(self, unit_id: UUID, month: str, current_user: dict) -> Optional[OnCallSubmitter]:
        """The caller as a staff member of the unit, else as one of its
        external physicians active in the month."""
        user_id = self.user_service.get_logged_in_user_id(current_user)
        if not user_id:
            return None
        try:
            staff_member = self.staff_service.is_logged_in_user_a_staff_member(unit_id, current_user)
            return OnCallSubmitter(staff_member_id=staff_member.id)
        except ValueError:
            pass
        physician = self.external_physician_service.get_active_in_month_by_user_id(user_id, unit_id, month)
        return OnCallSubmitter(external_physician_id=physician.id) if physician else None

    def _resolve_self(self, unit_id: UUID, month: str, current_user: dict) -> OnCallSubmitter:
        submitter = self._find_self(unit_id, month, current_user)
        if submitter is None:
            raise ValueError("Logged-in user is neither a staff member nor an active external physician of this unit")
        return submitter

    def is_active_external_physician(self, unit_id: UUID, month: str, current_user: dict) -> bool:
        """Whether the caller submits to this unit as an external physician —
        such a caller may come from another unit of the division."""
        submitter = self._find_self(unit_id, month, current_user)
        return submitter is not None and submitter.external_physician_id is not None

    def get_member_month(
        self, unit_id: UUID, month: str, current_user: dict, staff_member_id: Optional[UUID] = None,
        external_physician_id: Optional[UUID] = None, is_admin: bool = False,
    ):
        """Defaults to the logged-in caller's own submission; an admin may
        fetch any staff member or external physician of the unit, anyone else
        only their own."""
        if staff_member_id is not None and external_physician_id is not None:
            raise ValueError("Pass either staff_member_id or external_physician_id, not both")
        if staff_member_id is None and external_physician_id is None:
            return self.repository.get_by_submitter_month(unit_id, self._resolve_self(unit_id, month, current_user), month)

        target = OnCallSubmitter(staff_member_id=staff_member_id, external_physician_id=external_physician_id)
        if is_admin:
            if staff_member_id is not None:
                self.staff_service.get_staff_member(staff_member_id, unit_id)  # raises ValueError if not in this unit
            elif not self.external_physician_service.get_by_ids([external_physician_id], unit_id):
                raise ValueError("External physician not found")
        elif self._resolve_self(unit_id, month, current_user) != target:
            raise AuthorizationError("You can only view your own submission")
        return self.repository.get_by_submitter_month(unit_id, target, month)

    def get_submission_status(self, unit_id: UUID, month: str):
        """One row per staff member and per external physician active in the
        month, flagging whether they have submitted the on-call form (anything,
        including "empty") this month."""
        submitted_staff_ids, submitted_external_ids = self.repository.get_submitted_ids(unit_id, month)
        staff_rows = [
            {"staff_member_id": m.id, "name": m.name, "submitted": m.id in submitted_staff_ids}
            for m in self.staff_service.get_all_members(unit_id)
        ]
        external_rows = [
            {"external_physician_id": p.id, "name": p.name, "submitted": p.id in submitted_external_ids}
            for p in self.external_physician_service.get_active_in_month(unit_id, month)
        ]
        return staff_rows + external_rows

    def update_member_month(
        self, unit_id: UUID, month: str, data: MemberMonthlyOnCallSubmissionUpdate, current_user: dict,
        empty: bool = False,
    ):
        submitter = self._resolve_self(unit_id, month, current_user)

        if len([e for e in data.entries if e.date is None]) > 1:
            raise ValueError("Only one general-comment entry (date=null) is allowed per request")

        dated_entries = [e for e in data.entries if e.date is not None]
        if len({e.date for e in dated_entries}) != len(dated_entries):
            raise ValueError("Only one on-call entry is allowed per date")
        for entry in dated_entries:
            if entry.date.strftime("%Y-%m") != month:
                raise ValueError(f"Entry date {entry.date} is not in month {month}")

        if any(e.preference is not None or e.constraint_type_id is not None for e in dated_entries):
            self.submission_metadata_service.assert_window_open(unit_id, month, SubmissionScope.ON_CALL)

        type_ids = {e.constraint_type_id for e in dated_entries if e.constraint_type_id is not None}
        existing = self.constraint_type_service.get_existing_ids_for_unit(
            list(type_ids), unit_id, ConstraintTypeScope.ON_CALL,
        )
        if type_ids - existing:
            raise ValueError("On-call constraint type not found")

        rows = self.repository.replace_month(unit_id, submitter, month, data.entries, submitted_empty=empty)
        logger.info(
            "Updated %d on-call submission entries (unit_id=%s, %s, month=%s, empty=%s) by %s",
            len(rows), unit_id, submitter, month, empty, get_current_user_label(),
        )
        return rows
