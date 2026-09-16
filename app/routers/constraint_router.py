import logging

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from uuid import UUID

from app.schemas.schemas import (
    ConstraintTypeCreate,
    ConstraintTypeUpdate,
    ConstraintTypeResponse,
    ConstraintResponse,
    MonthlyConstraintsResponse,
    PullSubmissionsResponse,
    ConstraintHistoryResponse,
    MonthlyConstraintsUpdate,
    ConstraintSubmissionMetadataResponse,
    ConstraintSubmissionMetadataUpdate,
    ConstraintSubmissionResponse,
    MemberMonthlySubmissionUpdate,
    StaffSubmissionStatusResponse,
)
from app.services.constraint_service import ConstraintService
from app.services.constraint_type_service import ConstraintTypeService
from app.services.constraint_submission_metadata_service import ConstraintSubmissionMetadataService, SubmissionWindowError
from app.services.constraints_submission_service import ConstraintsSubmissionService
from app.services.authorization_service import AuthorizationService
from app.repositories.constraint_repository import MONTH_PATTERN, VersionConflictError
from app.dependencies import (
    get_constraint_service,
    get_constraint_type_service,
    get_constraint_submission_metadata_service,
    get_constraints_submission_service,
    get_authorization_service,
)
from app.context import bind_current_user

router = APIRouter(prefix="/constraints", tags=["constraints"])
logger = logging.getLogger(__name__)


def _validate_month(month: str) -> None:
    if not MONTH_PATTERN.match(month):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="month must be in YYYY-MM format")


# --- Monthly master calendar (the default view of "constraints") ---

@router.get("", response_model=MonthlyConstraintsResponse)
def get_constraints(
    unit_id: UUID, month: str, version_id: int | None = None,
    service: ConstraintService = Depends(get_constraint_service),
    authz: AuthorizationService = Depends(get_authorization_service),
    current_user: dict = Depends(bind_current_user),
):
    _validate_month(month)
    user = authz.get_logged_in_user_or_raise(current_user)
    # A regular `user` may view any unit within their own division here, not just their own unit.
    authz.authorize_unit_view(user, unit_id)
    return service.get_monthly_constraints(unit_id, month, version_id)


@router.post("", response_model=list[ConstraintResponse])
def update_constraints(
    unit_id: UUID,
    month: str,
    account_id: UUID,
    data: MonthlyConstraintsUpdate,
    service: ConstraintService = Depends(get_constraint_service),
    authz: AuthorizationService = Depends(get_authorization_service),
    current_user: dict = Depends(bind_current_user),
):
    _validate_month(month)
    user = authz.get_logged_in_user_or_raise(current_user)
    authz.authorize_unit(user, unit_id)
    authz.authorize_account(user, account_id)
    authz.require_admin_role(user)
    try:
        return service.update_monthly_constraints(unit_id, month, account_id, data, user.id)
    except VersionConflictError as e:
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"error": e.code, "message": e.message})
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/history", response_model=list[ConstraintHistoryResponse])
def get_constraint_history(
    unit_id: UUID, month: str,
    service: ConstraintService = Depends(get_constraint_service),
    authz: AuthorizationService = Depends(get_authorization_service),
    current_user: dict = Depends(bind_current_user),
):
    """History of saved versions for this unit+month's constraints calendar
    — when each was created and by whom — newest first."""
    _validate_month(month)
    user = authz.get_logged_in_user_or_raise(current_user)
    authz.authorize_unit_view(user, unit_id)
    return service.get_version_history(unit_id, month)


@router.post("/pull-submissions", response_model=PullSubmissionsResponse)
def pull_member_submissions(
    unit_id: UUID, month: str,
    service: ConstraintService = Depends(get_constraint_service),
    authz: AuthorizationService = Depends(get_authorization_service),
    current_user: dict = Depends(bind_current_user),
):
    _validate_month(month)
    user = authz.get_logged_in_user_or_raise(current_user)
    authz.authorize_unit(user, unit_id)
    authz.require_admin_role(user)
    try:
        return service.pull_member_submissions(unit_id, month, user.id)
    except VersionConflictError as e:
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"error": e.code, "message": e.message})


# --- Submission window metadata (GET: any authenticated unit member; POST: admin + owner only) ---

@router.get("/submission-metadata", response_model=ConstraintSubmissionMetadataResponse | None)
def get_constraints_submission_metadata(
    unit_id: UUID, month: str,
    service: ConstraintSubmissionMetadataService = Depends(get_constraint_submission_metadata_service),
    authz: AuthorizationService = Depends(get_authorization_service),
    current_user: dict = Depends(bind_current_user),
):
    _validate_month(month)
    user = authz.get_logged_in_user_or_raise(current_user)
    authz.authorize_unit_view(user, unit_id)
    return service.get(unit_id, month)


@router.post("/submission-metadata", status_code=status.HTTP_204_NO_CONTENT)
def update_constraints_submission_metadata(
    data: ConstraintSubmissionMetadataUpdate,
    service: ConstraintSubmissionMetadataService = Depends(get_constraint_submission_metadata_service),
    authz: AuthorizationService = Depends(get_authorization_service),
    current_user: dict = Depends(bind_current_user),
):
    _validate_month(data.month)
    user = authz.get_logged_in_user_or_raise(current_user)
    authz.authorize_unit(user, data.unit_id)
    authz.require_admin_role(user)
    service.upsert(data, current_user)


# --- Member monthly submissions (self-serve: always the logged-in member) ---

@router.get("/submissions", response_model=list[ConstraintSubmissionResponse])
def get_member_monthly_submission(
    unit_id: UUID, month: str, staff_member_id: UUID | None = None,
    service: ConstraintsSubmissionService = Depends(get_constraints_submission_service),
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


@router.post("/submissions", response_model=list[ConstraintSubmissionResponse])
def update_member_monthly_submission(
    unit_id: UUID, month: str, data: MemberMonthlySubmissionUpdate, empty: bool = False,
    service: ConstraintsSubmissionService = Depends(get_constraints_submission_service),
    authz: AuthorizationService = Depends(get_authorization_service),
    current_user: dict = Depends(bind_current_user),
):
    """`empty=true` lets a member explicitly submit "no constraints this
    month" as a real submission — it's recorded on the general-comment row
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


@router.get("/submission-status", response_model=list[StaffSubmissionStatusResponse])
def get_submission_status(
    unit_id: UUID, month: str,
    service: ConstraintsSubmissionService = Depends(get_constraints_submission_service),
    authz: AuthorizationService = Depends(get_authorization_service),
    current_user: dict = Depends(bind_current_user),
):
    _validate_month(month)
    user = authz.get_logged_in_user_or_raise(current_user)
    authz.authorize_unit(user, unit_id)
    authz.require_admin_role(user)
    return service.get_submission_status(unit_id, month)


# --- Constraint Type CRUD ---

@router.get("/types", response_model=list[ConstraintTypeResponse])
def get_types(
    account_id: UUID,
    include_deleted: bool = False,
    service: ConstraintTypeService = Depends(get_constraint_type_service),
    authz: AuthorizationService = Depends(get_authorization_service),
    current_user: dict = Depends(bind_current_user),
):
    user = authz.get_logged_in_user_or_raise(current_user)
    authz.authorize_account(user, account_id)
    return service.get_all(account_id, include_deleted)


@router.get("/types/{c_id}", response_model=ConstraintTypeResponse)
def get_type(
    c_id: int, account_id: UUID,
    service: ConstraintTypeService = Depends(get_constraint_type_service),
    authz: AuthorizationService = Depends(get_authorization_service),
    current_user: dict = Depends(bind_current_user),
):
    user = authz.get_logged_in_user_or_raise(current_user)
    authz.authorize_account(user, account_id)
    try:
        return service.get_by_id(c_id, account_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/types", response_model=ConstraintTypeResponse)
def create_type(
    data: ConstraintTypeCreate,
    service: ConstraintTypeService = Depends(get_constraint_type_service),
    authz: AuthorizationService = Depends(get_authorization_service),
    current_user: dict = Depends(bind_current_user),
):
    user = authz.get_logged_in_user_or_raise(current_user)
    authz.authorize_account(user, data.account_id)
    authz.require_admin_role(user)
    return service.create(data)


@router.patch("/types/{c_id}", response_model=ConstraintTypeResponse)
def update_type(
    c_id: int, account_id: UUID, data: ConstraintTypeUpdate,
    service: ConstraintTypeService = Depends(get_constraint_type_service),
    authz: AuthorizationService = Depends(get_authorization_service),
    current_user: dict = Depends(bind_current_user),
):
    user = authz.get_logged_in_user_or_raise(current_user)
    authz.authorize_account(user, account_id)
    authz.require_admin_role(user)
    if not data.model_dump(exclude_unset=True):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update")
    try:
        return service.update(c_id, account_id, data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete("/types/{c_id}")
def delete_type(
    c_id: int, account_id: UUID,
    service: ConstraintTypeService = Depends(get_constraint_type_service),
    authz: AuthorizationService = Depends(get_authorization_service),
    current_user: dict = Depends(bind_current_user),
):
    user = authz.get_logged_in_user_or_raise(current_user)
    authz.authorize_account(user, account_id)
    authz.require_admin_role(user)
    try:
        service.delete(c_id, account_id)
        return {"message": "Constraint type deleted successfully"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
