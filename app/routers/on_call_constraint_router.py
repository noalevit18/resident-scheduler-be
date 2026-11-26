import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse

from app.models.models import ConstraintTypeScope, SubmissionScope
from app.schemas.schemas import (
    ConstraintTypeResponse,
    MemberMonthlyOnCallSubmissionUpdate,
    OnCallSubmissionResponse,
    OnCallSubmissionStatusResponse,
    OnCallSubmissionWindowResponse,
    OnCallSubmissionWindowUpdate,
    OnCallConstraintTypeCreate,
    OnCallConstraintTypeUpdate,
    MonthlyOnCallConstraintsResponse,
    MonthlyOnCallConstraintsUpdate,
    OnCallConstraintHistoryResponse,
    OnCallConstraintResponse,
)
from app.services.on_call_constraint_service import OnCallConstraintService
from app.services.on_call_submission_service import OnCallSubmissionService
from app.services.constraint_type_service import ConstraintTypeService
from app.services.staff_member_submission_metadata_service import (
    StaffMemberSubmissionMetadataService, SubmissionWindowError,
)
from app.services.authorization_service import AuthorizationError, AuthorizationService
from app.repositories.constraint_repository import MONTH_PATTERN, VersionConflictError
from app.dependencies import (
    get_on_call_constraint_service,
    get_on_call_submission_service,
    get_constraint_type_service,
    get_staff_member_submission_metadata_service,
    get_authorization_service,
)
from app.context import bind_current_user

router = APIRouter(prefix="/on-call-constraints", tags=["on-call-constraints"])
logger = logging.getLogger(__name__)


def _validate_month(month: str) -> None:
    if not MONTH_PATTERN.match(month):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="month must be in YYYY-MM format")


@router.get("", response_model=MonthlyOnCallConstraintsResponse)
def get_on_call_constraints(
    unit_id: UUID, month: str, version_id: int | None = None,
    service: OnCallConstraintService = Depends(get_on_call_constraint_service),
    authz: AuthorizationService = Depends(get_authorization_service),
    current_user: dict = Depends(bind_current_user),
):
    _validate_month(month)
    user = authz.get_logged_in_user_or_raise(current_user)
    authz.authorize_division_view(user, unit_id)
    return service.get_monthly_constraints(unit_id, month, version_id)


@router.post("", response_model=list[OnCallConstraintResponse])
def update_on_call_constraints(
    unit_id: UUID,
    month: str,
    account_id: UUID,
    data: MonthlyOnCallConstraintsUpdate,
    service: OnCallConstraintService = Depends(get_on_call_constraint_service),
    authz: AuthorizationService = Depends(get_authorization_service),
    current_user: dict = Depends(bind_current_user),
):
    """Saves a new version of the month. Dates present in `entries` are
    replaced by exactly those entries; other dates are carried forward."""
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


@router.get("/history", response_model=list[OnCallConstraintHistoryResponse])
def get_on_call_constraint_history(
    unit_id: UUID, month: str,
    service: OnCallConstraintService = Depends(get_on_call_constraint_service),
    authz: AuthorizationService = Depends(get_authorization_service),
    current_user: dict = Depends(bind_current_user),
):
    """Saved versions of this unit+month's on-call constraints calendar, newest first."""
    _validate_month(month)
    user = authz.get_logged_in_user_or_raise(current_user)
    authz.authorize_unit_view(user, unit_id)
    return service.get_version_history(unit_id, month)


@router.post("/pull-submissions", response_model=MonthlyOnCallConstraintsResponse)
def pull_on_call_constraint_submissions(
    unit_id: UUID, month: str,
    service: OnCallConstraintService = Depends(get_on_call_constraint_service),
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


def _authorize_submitter(
    user, unit_id: UUID, month: str, current_user: dict,
    authz: AuthorizationService, service: OnCallSubmissionService,
) -> bool:
    """Lets in whoever may act on the unit, and the unit's external physicians
    active in the month (who may belong to another unit). Returns False when
    the caller is let in only as an external physician — their own
    submission is then all they may access."""
    try:
        authz.authorize_unit(user, unit_id)
        return True
    except AuthorizationError:
        if service.is_active_external_physician(unit_id, month, current_user):
            return False
        raise


# --- On-call constraint type CRUD (hard "can't" reasons: vacation, army, ...) ---

@router.get("/types", response_model=list[ConstraintTypeResponse])
def get_on_call_constraint_types(
    account_id: UUID,
    include_deleted: bool = False,
    service: ConstraintTypeService = Depends(get_constraint_type_service),
    authz: AuthorizationService = Depends(get_authorization_service),
    current_user: dict = Depends(bind_current_user),
):
    user = authz.get_logged_in_user_or_raise(current_user)
    authz.authorize_account(user, account_id)
    return service.get_all(account_id, ConstraintTypeScope.ON_CALL, include_deleted)


@router.get("/types/{c_id}", response_model=ConstraintTypeResponse)
def get_on_call_constraint_type(
    c_id: int, account_id: UUID,
    service: ConstraintTypeService = Depends(get_constraint_type_service),
    authz: AuthorizationService = Depends(get_authorization_service),
    current_user: dict = Depends(bind_current_user),
):
    user = authz.get_logged_in_user_or_raise(current_user)
    authz.authorize_account(user, account_id)
    try:
        return service.get_by_id(c_id, account_id, ConstraintTypeScope.ON_CALL)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/types", response_model=ConstraintTypeResponse)
def create_on_call_constraint_type(
    data: OnCallConstraintTypeCreate,
    service: ConstraintTypeService = Depends(get_constraint_type_service),
    authz: AuthorizationService = Depends(get_authorization_service),
    current_user: dict = Depends(bind_current_user),
):
    user = authz.get_logged_in_user_or_raise(current_user)
    authz.authorize_account(user, data.account_id)
    authz.require_admin_role(user)
    return service.create_on_call(data)


@router.patch("/types/{c_id}", response_model=ConstraintTypeResponse)
def update_on_call_constraint_type(
    c_id: int, account_id: UUID, data: OnCallConstraintTypeUpdate,
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
        return service.update_on_call(c_id, account_id, data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete("/types/{c_id}")
def delete_on_call_constraint_type(
    c_id: int, account_id: UUID,
    service: ConstraintTypeService = Depends(get_constraint_type_service),
    authz: AuthorizationService = Depends(get_authorization_service),
    current_user: dict = Depends(bind_current_user),
):
    user = authz.get_logged_in_user_or_raise(current_user)
    authz.authorize_account(user, account_id)
    authz.require_admin_role(user)
    try:
        service.delete(c_id, account_id, ConstraintTypeScope.ON_CALL)
        return {"message": "On-call constraint type deleted successfully"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


# --- On-call submissions (self-serve, by staff members and external physicians; separate from the daily /submissions) ---

@router.get("/submissions", response_model=list[OnCallSubmissionResponse])
def get_member_on_call_submission(
    unit_id: UUID, month: str, staff_member_id: UUID | None = None, external_physician_id: UUID | None = None,
    service: OnCallSubmissionService = Depends(get_on_call_submission_service),
    authz: AuthorizationService = Depends(get_authorization_service),
    current_user: dict = Depends(bind_current_user),
):
    """Defaults to the logged-in caller's own on-call submission. Pass
    `staff_member_id` or `external_physician_id` to fetch a specific
    submitter's — allowed for an admin, or for a caller passing their own id."""
    _validate_month(month)
    user = authz.get_logged_in_user_or_raise(current_user)
    in_unit_scope = _authorize_submitter(user, unit_id, month, current_user, authz, service)
    try:
        return service.get_member_month(
            unit_id, month, current_user, staff_member_id, external_physician_id,
            in_unit_scope and authz.is_admin(user),
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/submissions", response_model=list[OnCallSubmissionResponse])
def update_member_on_call_submission(
    unit_id: UUID, month: str, data: MemberMonthlyOnCallSubmissionUpdate, empty: bool = False,
    service: OnCallSubmissionService = Depends(get_on_call_submission_service),
    authz: AuthorizationService = Depends(get_authorization_service),
    current_user: dict = Depends(bind_current_user),
):
    """Replaces the caller's whole on-call month. `empty=true` records
    "no on-call constraints this month" as a real submission."""
    _validate_month(month)
    user = authz.get_logged_in_user_or_raise(current_user)
    _authorize_submitter(user, unit_id, month, current_user, authz, service)
    try:
        return service.update_member_month(unit_id, month, data, current_user, empty)
    except SubmissionWindowError as e:
        return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content={"error": e.code, "message": e.message})
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/submissions/status", response_model=list[OnCallSubmissionStatusResponse])
def get_on_call_submission_status(
    unit_id: UUID, month: str,
    service: OnCallSubmissionService = Depends(get_on_call_submission_service),
    authz: AuthorizationService = Depends(get_authorization_service),
    current_user: dict = Depends(bind_current_user),
):
    _validate_month(month)
    user = authz.get_logged_in_user_or_raise(current_user)
    authz.authorize_unit(user, unit_id)
    authz.require_admin_role(user)
    return service.get_submission_status(unit_id, month)


# --- On-call constraints submission window (separate from the schedule's /submissions/metadata) ---

@router.get("/submissions/metadata", response_model=OnCallSubmissionWindowResponse | None)
def get_on_call_submission_metadata(
    unit_id: UUID, month: str,
    service: StaffMemberSubmissionMetadataService = Depends(get_staff_member_submission_metadata_service),
    authz: AuthorizationService = Depends(get_authorization_service),
    current_user: dict = Depends(bind_current_user),
):
    _validate_month(month)
    user = authz.get_logged_in_user_or_raise(current_user)
    authz.authorize_unit_view(user, unit_id)
    return service.get(unit_id, month, SubmissionScope.ON_CALL)


@router.post("/submissions/metadata", status_code=status.HTTP_204_NO_CONTENT)
def update_on_call_submission_metadata(
    data: OnCallSubmissionWindowUpdate,
    service: StaffMemberSubmissionMetadataService = Depends(get_staff_member_submission_metadata_service),
    authz: AuthorizationService = Depends(get_authorization_service),
    current_user: dict = Depends(bind_current_user),
):
    _validate_month(data.month)
    user = authz.get_logged_in_user_or_raise(current_user)
    authz.authorize_unit(user, data.unit_id)
    authz.require_admin_role(user)
    try:
        service.upsert_on_call(data, current_user)
    except SubmissionWindowError as e:
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"error": e.code, "message": e.message})


@router.delete("/submissions/metadata", status_code=status.HTTP_204_NO_CONTENT)
def delete_on_call_submission_metadata(
    unit_id: UUID, month: str,
    service: StaffMemberSubmissionMetadataService = Depends(get_staff_member_submission_metadata_service),
    authz: AuthorizationService = Depends(get_authorization_service),
    current_user: dict = Depends(bind_current_user),
):
    _validate_month(month)
    user = authz.get_logged_in_user_or_raise(current_user)
    authz.authorize_unit(user, unit_id)
    authz.require_admin_role(user)
    service.clear_window(unit_id, month, SubmissionScope.ON_CALL)
