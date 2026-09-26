from fastapi import APIRouter, Depends, HTTPException, status
from uuid import UUID
from app.schemas.schemas import SeniorCreate, SeniorUpdate, SeniorResponse
from app.services.senior_service import SeniorService
from app.services.authorization_service import AuthorizationService
from app.dependencies import get_senior_service, get_authorization_service
from app.context import bind_current_user


router = APIRouter(prefix="/seniors", tags=["seniors"])


@router.get("", response_model=list[SeniorResponse])
def get_seniors(
    unit_id: UUID,
    include_deleted: bool = False,
    service: SeniorService = Depends(get_senior_service),
    authz: AuthorizationService = Depends(get_authorization_service),
    current_user: dict = Depends(bind_current_user),
):
    user = authz.get_logged_in_user_or_raise(current_user)
    authz.authorize_unit_view(user, unit_id)
    return service.get_all_seniors(unit_id, include_deleted)


@router.post("", response_model=SeniorResponse)
def create_senior(
    data: SeniorCreate,
    service: SeniorService = Depends(get_senior_service),
    authz: AuthorizationService = Depends(get_authorization_service),
    current_user: dict = Depends(bind_current_user),
):
    user = authz.get_logged_in_user_or_raise(current_user)
    authz.authorize_unit(user, data.unit_id)
    authz.require_admin_role(user)
    return service.create_senior(data, user.id)


@router.patch("/{senior_id}", response_model=SeniorResponse)
def update_senior(
    senior_id: UUID,
    unit_id: UUID,
    data: SeniorUpdate,
    service: SeniorService = Depends(get_senior_service),
    authz: AuthorizationService = Depends(get_authorization_service),
    current_user: dict = Depends(bind_current_user),
):
    user = authz.get_logged_in_user_or_raise(current_user)
    authz.authorize_unit(user, unit_id)
    authz.require_admin_role(user)
    update_data = data.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update")
    try:
        return service.update_senior(senior_id, unit_id, update_data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete("/{senior_id}")
def delete_senior(
    senior_id: UUID,
    unit_id: UUID,
    service: SeniorService = Depends(get_senior_service),
    authz: AuthorizationService = Depends(get_authorization_service),
    current_user: dict = Depends(bind_current_user),
):
    user = authz.get_logged_in_user_or_raise(current_user)
    authz.authorize_unit(user, unit_id)
    authz.require_admin_role(user)
    try:
        service.delete_senior(senior_id, unit_id, user.id)
        return {"message": "Senior deleted successfully"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
