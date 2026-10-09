from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from datetime import date
from uuid import UUID

from app.schemas.schemas import StationResponse, StationCreate, StationUpdate
from app.services.station_service import StationService, StationValidationError
from app.services.schedule_service import ScheduleService
from app.services.authorization_service import AuthorizationService
from app.dependencies import get_station_service, get_schedule_service, get_authorization_service
from app.context import bind_current_user

router = APIRouter(prefix="/stations", tags=["stations"])


@router.get("", response_model=list[StationResponse])
def get_stations(
    unit_id: UUID,
    include_deleted: bool = False,
    service: StationService = Depends(get_station_service),
    authz: AuthorizationService = Depends(get_authorization_service),
    current_user: dict = Depends(bind_current_user),
):
    user = authz.get_logged_in_user_or_raise(current_user)
    authz.authorize_division_view(user, unit_id)
    return service.get_all_stations(unit_id, include_deleted)


@router.post("", response_model=StationResponse)
def create_station(
    data: StationCreate,
    service: StationService = Depends(get_station_service),
    schedule_service: ScheduleService = Depends(get_schedule_service),
    authz: AuthorizationService = Depends(get_authorization_service),
    current_user: dict = Depends(bind_current_user),
):
    user = authz.get_logged_in_user_or_raise(current_user)
    authz.authorize_unit(user, data.unit_id)
    authz.require_admin_role(user)
    try:
        created = service.create_station(data, user.id)
        schedule_service.apply_station_changes(data.unit_id, data.effective_from, user.id)
        return created
    except StationValidationError as e:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"error": e.code, "message": e.message})


@router.patch("/{station_id}", response_model=StationResponse)
def update_station(
    station_id: int,
    unit_id: UUID,
    data: StationUpdate,
    service: StationService = Depends(get_station_service),
    schedule_service: ScheduleService = Depends(get_schedule_service),
    authz: AuthorizationService = Depends(get_authorization_service),
    current_user: dict = Depends(bind_current_user),
):
    user = authz.get_logged_in_user_or_raise(current_user)
    authz.authorize_unit(user, unit_id)
    authz.require_admin_role(user)
    try:
        updated = service.update_station(station_id, unit_id, data, user.id)
        if data.effective_from is not None:
            schedule_service.apply_station_changes(unit_id, data.effective_from, user.id)
        return updated
    except StationValidationError as e:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"error": e.code, "message": e.message})
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete("/{station_id}")
def delete_station(
    station_id: int,
    unit_id: UUID,
    effective_from: date | None = None,
    service: StationService = Depends(get_station_service),
    schedule_service: ScheduleService = Depends(get_schedule_service),
    authz: AuthorizationService = Depends(get_authorization_service),
    current_user: dict = Depends(bind_current_user),
):
    user = authz.get_logged_in_user_or_raise(current_user)
    authz.authorize_unit(user, unit_id)
    authz.require_admin_role(user)
    try:
        retired_from = effective_from or date.today()
        service.delete_station(station_id, unit_id, retired_from, user.id)
        schedule_service.apply_station_changes(unit_id, retired_from, user.id)
        return {"message": "Station deleted successfully"}
    except StationValidationError as e:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"error": e.code, "message": e.message})
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
