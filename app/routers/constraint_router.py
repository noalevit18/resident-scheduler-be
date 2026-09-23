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
)
from app.services.constraint_service import ConstraintService
from app.services.constraint_type_service import ConstraintTypeService
from app.services.authorization_service import AuthorizationService
from app.repositories.constraint_repository import MONTH_PATTERN, VersionConflictError
from app.dependencies import (
    get_constraint_service,
    get_constraint_type_service,
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
