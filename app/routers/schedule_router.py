from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from uuid import UUID

from app.schemas.schemas import MonthlyScheduleUpdate, MonthlyScheduleResponse, ScheduleHistoryResponse
from app.services.schedule_service import ScheduleService, ScheduleValidationError
from app.services.authorization_service import AuthorizationService
from app.repositories.on_call_shift_repository import MONTH_PATTERN
from app.repositories.schedule_repository import ScheduleVersionConflictError
from app.dependencies import get_schedule_service, get_authorization_service
from app.context import bind_current_user

router = APIRouter(prefix="/schedule", tags=["schedule"])


def _validate_month(month: str) -> None:
    if not MONTH_PATTERN.match(month):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="month must be in YYYY-MM format")


@router.get("", response_model=MonthlyScheduleResponse)
def get_schedule(
    unit_id: UUID, month: str, version: int | None = None, published_only: bool = False,
    service: ScheduleService = Depends(get_schedule_service),
    authz: AuthorizationService = Depends(get_authorization_service),
    current_user: dict = Depends(bind_current_user),
):
    _validate_month(month)
    user = authz.get_logged_in_user_or_raise(current_user)
    authz.authorize_division_view(user, unit_id)
    try:
        return service.get_monthly(unit_id, month, version, published_only)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("", response_model=MonthlyScheduleResponse)
def update_schedule(
    unit_id: UUID, month: str, data: MonthlyScheduleUpdate,
    service: ScheduleService = Depends(get_schedule_service),
    authz: AuthorizationService = Depends(get_authorization_service),
    current_user: dict = Depends(bind_current_user),
):
    _validate_month(month)
    user = authz.get_logged_in_user_or_raise(current_user)
    authz.authorize_unit(user, unit_id)
    authz.require_admin_role(user)
    try:
        return service.update_monthly(unit_id, month, data, user.id)
    except ScheduleVersionConflictError as e:
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"error": e.code, "message": e.message})
    except ScheduleValidationError as e:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"error": e.code, "message": e.message})


@router.get("/history", response_model=list[ScheduleHistoryResponse])
def get_schedule_history(
    unit_id: UUID, month: str,
    service: ScheduleService = Depends(get_schedule_service),
    authz: AuthorizationService = Depends(get_authorization_service),
    current_user: dict = Depends(bind_current_user),
):
    _validate_month(month)
    user = authz.get_logged_in_user_or_raise(current_user)
    authz.authorize_unit_view(user, unit_id)
    return service.get_version_history(unit_id, month)


@router.post("/history/{version}/publish", response_model=ScheduleHistoryResponse)
def publish_schedule_version(
    unit_id: UUID, month: str, version: int,
    service: ScheduleService = Depends(get_schedule_service),
    authz: AuthorizationService = Depends(get_authorization_service),
    current_user: dict = Depends(bind_current_user),
):
    _validate_month(month)
    user = authz.get_logged_in_user_or_raise(current_user)
    authz.authorize_unit(user, unit_id)
    authz.require_admin_role(user)
    try:
        return service.publish_version(unit_id, month, version, user.id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/history/{version}/unpublish", response_model=ScheduleHistoryResponse)
def unpublish_schedule_version(
    unit_id: UUID, month: str, version: int,
    service: ScheduleService = Depends(get_schedule_service),
    authz: AuthorizationService = Depends(get_authorization_service),
    current_user: dict = Depends(bind_current_user),
):
    _validate_month(month)
    user = authz.get_logged_in_user_or_raise(current_user)
    authz.authorize_unit(user, unit_id)
    authz.require_admin_role(user)
    try:
        return service.unpublish_version(unit_id, month, version, user.id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
