from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status

from app.schemas.schemas import (
    SpecialDateResponse,
    SpecialDatesBulkUpdate,
)
from app.services.special_date_service import SpecialDateService, DuplicateSpecialDateError
from app.services.authorization_service import AuthorizationService
from app.dependencies import get_special_date_service, get_authorization_service
from app.context import bind_current_user

router = APIRouter(prefix="/specialDates", tags=["specialDates"])


@router.get("", response_model=list[SpecialDateResponse])
def get_special_dates(
    service: SpecialDateService = Depends(get_special_date_service),
    authz: AuthorizationService = Depends(get_authorization_service),
    current_user: dict = Depends(bind_current_user),
):
    user = authz.get_logged_in_user_or_raise(current_user)
    account_id = authz.get_account_id_or_raise(user)
    return service.get_all(account_id)


@router.get("/{special_date}", response_model=SpecialDateResponse)
def get_special_day(
    special_date: date,
    service: SpecialDateService = Depends(get_special_date_service),
    authz: AuthorizationService = Depends(get_authorization_service),
    current_user: dict = Depends(bind_current_user),
):
    user = authz.get_logged_in_user_or_raise(current_user)
    account_id = authz.get_account_id_or_raise(user)
    try:
        return service.get_by_date(account_id, special_date)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.put("", response_model=list[SpecialDateResponse])
def save_special_dates(
    data: SpecialDatesBulkUpdate,
    service: SpecialDateService = Depends(get_special_date_service),
    authz: AuthorizationService = Depends(get_authorization_service),
    current_user: dict = Depends(bind_current_user),
):
    """Saves every create/update/delete from one Manage Holidays save in a
    single request instead of one call per changed day."""
    user = authz.get_logged_in_user_or_raise(current_user)
    account_id = authz.get_account_id_or_raise(user)
    authz.require_admin_role(user)
    try:
        return service.save_all(data, account_id, user.id)
    except DuplicateSpecialDateError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
