import re

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from uuid import UUID

from app.schemas.schemas import (
    StaffMemberSubmissionResponse,
    MemberMonthlySubmissionUpdate,
    StaffSubmissionStatusResponse,
    SubmissionWindowResponse,
    SubmissionWindowUpdate,
)
from app.services.staff_member_submission_service import StaffMemberSubmissionService
from app.services.staff_member_submission_metadata_service import StaffMemberSubmissionMetadataService, SubmissionWindowError
from app.services.authorization_service import AuthorizationService
from app.dependencies import (
    get_staff_member_submission_metadata_service,
    get_staff_member_submission_service,
    get_authorization_service,
)
from app.context import bind_current_user

router = APIRouter(prefix="/submissions", tags=["submissions"])

MONTH_PATTERN = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def _validate_month(month: str) -> None:
    if not MONTH_PATTERN.match(month):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="month must be in YYYY-MM format")


# --- Member monthly submissions (self-serve: always the logged-in member) ---

@router.get("", response_model=list[StaffMemberSubmissionResponse])
def get_member_monthly_submission(
    unit_id: UUID, month: str, staff_member_id: UUID | None = None,
    service: StaffMemberSubmissionService = Depends(get_staff_member_submission_service),
    authz: AuthorizationService = Depends(get_authorization_service),
    current_user: dict = Depends(bind_current_user),
):
    """Defaults to the logged-in caller's own submission. Pass
    `staff_member_id` to fetch a specific member's instead — allowed for an
    admin, or for a regular member passing their own id; any other id is
    denied (AuthorizationError, handled globally as a 403)."""
    _validate_month(month)
    user = authz.get_logged_in_user_or_raise(current_user)
    authz.authorize_unit(user, unit_id)
    try:
        return service.get_member_month(unit_id, month, current_user, staff_member_id, authz.is_admin(user))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("", response_model=list[StaffMemberSubmissionResponse])
def update_member_monthly_submission(
    unit_id: UUID, month: str, data: MemberMonthlySubmissionUpdate, empty: bool = False,
    service: StaffMemberSubmissionService = Depends(get_staff_member_submission_service),
    authz: AuthorizationService = Depends(get_authorization_service),
    current_user: dict = Depends(bind_current_user),
):
    """`empty=true` lets a member explicitly submit "nothing this month" as
    a real submission — it's recorded on the general-comment row
    (submitted_empty=true) so submission-status checks, which just look for
    any row at all, see them as having submitted rather than as not having
    submitted yet."""
    _validate_month(month)
    user = authz.get_logged_in_user_or_raise(current_user)
    authz.authorize_unit(user, unit_id)
    try:
        return service.update_member_month(unit_id, month, data, current_user, empty)
    except SubmissionWindowError as e:
        return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content={"error": e.code, "message": e.message})
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/status", response_model=list[StaffSubmissionStatusResponse])
def get_submission_status(
    unit_id: UUID, month: str,
    service: StaffMemberSubmissionService = Depends(get_staff_member_submission_service),
    authz: AuthorizationService = Depends(get_authorization_service),
    current_user: dict = Depends(bind_current_user),
):
    _validate_month(month)
    user = authz.get_logged_in_user_or_raise(current_user)
    authz.authorize_unit(user, unit_id)
    authz.require_admin_role(user)
    return service.get_submission_status(unit_id, month)


@router.get("/metadata", response_model=SubmissionWindowResponse | None)
def get_staff_member_submission_metadata(
    unit_id: UUID, month: str,
    service: StaffMemberSubmissionMetadataService = Depends(get_staff_member_submission_metadata_service),
    authz: AuthorizationService = Depends(get_authorization_service),
    current_user: dict = Depends(bind_current_user),
):
    _validate_month(month)
    user = authz.get_logged_in_user_or_raise(current_user)
    authz.authorize_unit_view(user, unit_id)
    return service.get(unit_id, month)


@router.post("/metadata", status_code=status.HTTP_204_NO_CONTENT)
def update_staff_member_submission_metadata(
    data: SubmissionWindowUpdate,
    service: StaffMemberSubmissionMetadataService = Depends(get_staff_member_submission_metadata_service),
    authz: AuthorizationService = Depends(get_authorization_service),
    current_user: dict = Depends(bind_current_user),
):
    _validate_month(data.month)
    user = authz.get_logged_in_user_or_raise(current_user)
    authz.authorize_unit(user, data.unit_id)
    authz.require_admin_role(user)
    service.upsert(data, current_user)


@router.delete("/metadata", status_code=status.HTTP_204_NO_CONTENT)
def delete_staff_member_submission_metadata(
    unit_id: UUID, month: str,
    service: StaffMemberSubmissionMetadataService = Depends(get_staff_member_submission_metadata_service),
    authz: AuthorizationService = Depends(get_authorization_service),
    current_user: dict = Depends(bind_current_user),
):
    _validate_month(month)
    user = authz.get_logged_in_user_or_raise(current_user)
    authz.authorize_unit(user, unit_id)
    authz.require_admin_role(user)
    service.clear_window(unit_id, month)