from uuid import UUID

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from app.schemas.schemas import (
    ExternalOnCallPhysicianCreate,
    ExternalOnCallPhysicianUpdate,
    ExternalOnCallPhysicianResponse,
)
from app.services.authorization_service import AuthorizationService
from app.services.external_on_call_physician_service import (
    ExternalOnCallPhysicianConflictError,
    ExternalOnCallPhysicianError,
    ExternalOnCallPhysicianNotFoundError,
    ExternalOnCallPhysicianService,
)
from app.dependencies import get_authorization_service, get_external_on_call_physician_service
from app.context import bind_current_user

router = APIRouter(prefix="/onCall/externalPhysicians", tags=["onCall"])


def _error_response(error: ExternalOnCallPhysicianError) -> JSONResponse:
    if isinstance(error, ExternalOnCallPhysicianNotFoundError):
        status_code = status.HTTP_404_NOT_FOUND
    elif isinstance(error, ExternalOnCallPhysicianConflictError):
        status_code = status.HTTP_409_CONFLICT
    else:
        status_code = status.HTTP_400_BAD_REQUEST
    return JSONResponse(status_code=status_code, content={"error": error.code, "message": error.message})


@router.get("", response_model=list[ExternalOnCallPhysicianResponse])
def get_external_physicians(
    unit_id: UUID,
    include_archived: bool = False,
    service: ExternalOnCallPhysicianService = Depends(get_external_on_call_physician_service),
    authz: AuthorizationService = Depends(get_authorization_service),
    current_user: dict = Depends(bind_current_user),
):
    user = authz.get_logged_in_user_or_raise(current_user)
    authz.authorize_division_view(user, unit_id)
    return service.get_all(unit_id, include_archived)


@router.post("", response_model=ExternalOnCallPhysicianResponse)
def create_external_physician(
    data: ExternalOnCallPhysicianCreate,
    service: ExternalOnCallPhysicianService = Depends(get_external_on_call_physician_service),
    authz: AuthorizationService = Depends(get_authorization_service),
    current_user: dict = Depends(bind_current_user),
):
    user = authz.get_logged_in_user_or_raise(current_user)
    authz.authorize_unit(user, data.unit_id)
    authz.require_admin_role(user)
    try:
        return service.create(data.unit_id, data, user.id)
    except ExternalOnCallPhysicianError as e:
        return _error_response(e)


@router.patch("/{physician_id}", response_model=ExternalOnCallPhysicianResponse)
def update_external_physician(
    physician_id: UUID,
    unit_id: UUID,
    data: ExternalOnCallPhysicianUpdate,
    service: ExternalOnCallPhysicianService = Depends(get_external_on_call_physician_service),
    authz: AuthorizationService = Depends(get_authorization_service),
    current_user: dict = Depends(bind_current_user),
):
    user = authz.get_logged_in_user_or_raise(current_user)
    authz.authorize_unit(user, unit_id)
    authz.require_admin_role(user)
    fields = data.model_dump(exclude_unset=True)
    if not fields:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "no_fields_to_update", "message": "No fields to update"},
        )
    try:
        return service.update(physician_id, unit_id, fields, user.id)
    except ExternalOnCallPhysicianError as e:
        return _error_response(e)


@router.post("/{physician_id}/archive", response_model=ExternalOnCallPhysicianResponse)
def archive_external_physician(
    physician_id: UUID,
    unit_id: UUID,
    service: ExternalOnCallPhysicianService = Depends(get_external_on_call_physician_service),
    authz: AuthorizationService = Depends(get_authorization_service),
    current_user: dict = Depends(bind_current_user),
):
    user = authz.get_logged_in_user_or_raise(current_user)
    authz.authorize_unit(user, unit_id)
    authz.require_admin_role(user)
    try:
        return service.archive(physician_id, unit_id, user.id)
    except ExternalOnCallPhysicianError as e:
        return _error_response(e)


@router.post("/{physician_id}/unarchive", response_model=ExternalOnCallPhysicianResponse)
def unarchive_external_physician(
    physician_id: UUID,
    unit_id: UUID,
    service: ExternalOnCallPhysicianService = Depends(get_external_on_call_physician_service),
    authz: AuthorizationService = Depends(get_authorization_service),
    current_user: dict = Depends(bind_current_user),
):
    user = authz.get_logged_in_user_or_raise(current_user)
    authz.authorize_unit(user, unit_id)
    authz.require_admin_role(user)
    try:
        return service.unarchive(physician_id, unit_id)
    except ExternalOnCallPhysicianError as e:
        return _error_response(e)
