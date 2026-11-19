from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from uuid import UUID

from app.schemas.schemas import (
    OnCallStationsCreate,
    OnCallStationsUpdate,
    OnCallStationResponse,
    OnCallStationGroupWrite,
    OnCallStationGroupResponse,
    OnCallUnitSettingsWrite,
    OnCallUnitSettingsResponse,
    OnCallGeneralSettingsWrite,
    OnCallGeneralSettingsResponse,
    MonthlyOnCallShiftsUpdate,
    MonthlyOnCallShiftsResponse,
    OnCallShiftHistoryResponse,
    SubmissionWindowUpdate,
    SubmissionWindowResponse,
)
from app.services.on_call_shift_service import OnCallShiftService, OnCallStationDivisionMismatchError
from app.services.on_call_station_service import OnCallStationService, OnCallStationNameConflictError
from app.services.on_call_settings_service import (
    OnCallGroupNameConflictError,
    OnCallSettingsError,
    OnCallSettingsService,
)
from app.services.staff_member_submission_metadata_service import StaffMemberSubmissionMetadataService
from app.services.unit_service import UnitService
from app.services.authorization_service import AuthorizationService, AuthorizationError
from app.repositories.on_call_shift_repository import MONTH_PATTERN, OnCallVersionConflictError
from app.dependencies import (
    get_on_call_shift_service,
    get_on_call_station_service,
    get_on_call_settings_service,
    get_unit_service,
    get_authorization_service,
)
from app.context import bind_current_user

router = APIRouter(prefix="/onCall", tags=["onCall"])


def _validate_month(month: str) -> None:
    if not MONTH_PATTERN.match(month):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="month must be in YYYY-MM format")


def _division_id_for_unit(unit_id: UUID, unit_service: UnitService) -> UUID:
    unit = unit_service.get_unit_details(unit_id)
    if not unit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unit not found")
    return unit["division_id"]


def _current_user_division_id(user, authz: AuthorizationService) -> UUID:
    division_id = authz.user_division_id(user)
    if not division_id:
        raise AuthorizationError("Your account is not associated with a division")
    return division_id



@router.get("", response_model=MonthlyOnCallShiftsResponse)
def get_on_call_shifts(
    unit_id: UUID, month: str, version: int | None = None,
    service: OnCallShiftService = Depends(get_on_call_shift_service),
    authz: AuthorizationService = Depends(get_authorization_service),
    current_user: dict = Depends(bind_current_user),
):
    _validate_month(month)
    user = authz.get_logged_in_user_or_raise(current_user)
    authz.authorize_division_view(user, unit_id)
    return service.get_monthly(unit_id, month, version)


@router.post("", response_model=MonthlyOnCallShiftsResponse)
def update_on_call_shifts(
    unit_id: UUID,
    month: str,
    data: MonthlyOnCallShiftsUpdate,
    service: OnCallShiftService = Depends(get_on_call_shift_service),
    unit_service: UnitService = Depends(get_unit_service),
    authz: AuthorizationService = Depends(get_authorization_service),
    current_user: dict = Depends(bind_current_user),
):
    _validate_month(month)
    user = authz.get_logged_in_user_or_raise(current_user)
    authz.authorize_unit(user, unit_id)
    authz.require_admin_role(user)
    division_id = _division_id_for_unit(unit_id, unit_service)
    try:
        return service.update_monthly_shifts(unit_id, division_id, month, data, user.id)
    except OnCallVersionConflictError as e:
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"error": e.code, "message": e.message})
    except OnCallStationDivisionMismatchError as e:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"error": e.code, "message": e.message})
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/history", response_model=list[OnCallShiftHistoryResponse])
def get_on_call_shift_history(
    unit_id: UUID, month: str,
    service: OnCallShiftService = Depends(get_on_call_shift_service),
    authz: AuthorizationService = Depends(get_authorization_service),
    current_user: dict = Depends(bind_current_user),
):
    _validate_month(month)
    user = authz.get_logged_in_user_or_raise(current_user)
    authz.authorize_unit_view(user, unit_id)
    return service.get_version_history(unit_id, month)


@router.post("/history/{version}/publish", response_model=OnCallShiftHistoryResponse)
def publish_on_call_version(
    unit_id: UUID, month: str, version: int,
    service: OnCallShiftService = Depends(get_on_call_shift_service),
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


@router.post("/pull-submissions", response_model=MonthlyOnCallShiftsResponse)
def pull_on_call_submissions(
    unit_id: UUID, month: str,
    service: OnCallShiftService = Depends(get_on_call_shift_service),
    unit_service: UnitService = Depends(get_unit_service),
    authz: AuthorizationService = Depends(get_authorization_service),
    current_user: dict = Depends(bind_current_user),
):
    _validate_month(month)
    user = authz.get_logged_in_user_or_raise(current_user)
    authz.authorize_unit(user, unit_id)
    authz.require_admin_role(user)
    division_id = _division_id_for_unit(unit_id, unit_service)
    try:
        return service.pull_user_submissions(unit_id, division_id, month, user.id)
    except OnCallVersionConflictError as e:
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"error": e.code, "message": e.message})


def _settings_error_response(error: OnCallSettingsError) -> JSONResponse:
    code = status.HTTP_409_CONFLICT if isinstance(error, OnCallGroupNameConflictError) else status.HTTP_400_BAD_REQUEST
    return JSONResponse(status_code=code, content={"error": error.code, "message": error.message})


# --- On-call station CRUD (division-scoped, admin-only) ---

@router.get("/stations", response_model=list[OnCallStationResponse])
def get_on_call_stations(
    include_deleted: bool = False,
    service: OnCallStationService = Depends(get_on_call_station_service),
    authz: AuthorizationService = Depends(get_authorization_service),
    current_user: dict = Depends(bind_current_user),
):
    user = authz.get_logged_in_user_or_raise(current_user)
    division_id = _current_user_division_id(user, authz)
    return service.get_all(division_id, include_deleted)


@router.post("/stations", response_model=list[OnCallStationResponse])
def create_on_call_stations(
    data: OnCallStationsCreate,
    service: OnCallStationService = Depends(get_on_call_station_service),
    authz: AuthorizationService = Depends(get_authorization_service),
    current_user: dict = Depends(bind_current_user),
):
    user = authz.get_logged_in_user_or_raise(current_user)
    authz.require_admin_role(user)
    division_id = _current_user_division_id(user, authz)
    try:
        return service.create_all(division_id, data, user.id)
    except OnCallStationNameConflictError as e:
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"error": e.code, "message": e.message})
    except OnCallSettingsError as e:
        return _settings_error_response(e)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.patch("/stations", response_model=list[OnCallStationResponse])
def update_on_call_stations(
    data: OnCallStationsUpdate,
    service: OnCallStationService = Depends(get_on_call_station_service),
    authz: AuthorizationService = Depends(get_authorization_service),
    current_user: dict = Depends(bind_current_user),
):
    user = authz.get_logged_in_user_or_raise(current_user)
    authz.require_admin_role(user)
    division_id = _current_user_division_id(user, authz)
    try:
        return service.update_all(division_id, data)
    except OnCallStationNameConflictError as e:
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"error": e.code, "message": e.message})
    except OnCallSettingsError as e:
        return _settings_error_response(e)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete("/stations/{station_id}")
def delete_on_call_station(
    station_id: int,
    service: OnCallStationService = Depends(get_on_call_station_service),
    authz: AuthorizationService = Depends(get_authorization_service),
    current_user: dict = Depends(bind_current_user),
):
    user = authz.get_logged_in_user_or_raise(current_user)
    authz.require_admin_role(user)
    division_id = _current_user_division_id(user, authz)
    try:
        service.delete(station_id, division_id)
        return {"message": "On-call station deleted successfully"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


# --- On-call station groups: named buckets of stations (division-scoped, admin-only) ---

@router.get("/stationGroups", response_model=list[OnCallStationGroupResponse])
def get_on_call_station_groups(
    service: OnCallSettingsService = Depends(get_on_call_settings_service),
    authz: AuthorizationService = Depends(get_authorization_service),
    current_user: dict = Depends(bind_current_user),
):
    user = authz.get_logged_in_user_or_raise(current_user)
    division_id = _current_user_division_id(user, authz)
    return service.get_groups(division_id)


@router.post("/stationGroups", response_model=OnCallStationGroupResponse)
def create_on_call_station_group(
    data: OnCallStationGroupWrite,
    service: OnCallSettingsService = Depends(get_on_call_settings_service),
    authz: AuthorizationService = Depends(get_authorization_service),
    current_user: dict = Depends(bind_current_user),
):
    user = authz.get_logged_in_user_or_raise(current_user)
    authz.require_admin_role(user)
    division_id = _current_user_division_id(user, authz)
    try:
        return service.create_group(division_id, data)
    except OnCallSettingsError as e:
        return _settings_error_response(e)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.put("/stationGroups/{group_id}", response_model=OnCallStationGroupResponse)
def replace_on_call_station_group(
    group_id: int,
    data: OnCallStationGroupWrite,
    service: OnCallSettingsService = Depends(get_on_call_settings_service),
    authz: AuthorizationService = Depends(get_authorization_service),
    current_user: dict = Depends(bind_current_user),
):
    """Replaces the group's name and stations; listed stations leave any other group."""
    user = authz.get_logged_in_user_or_raise(current_user)
    authz.require_admin_role(user)
    division_id = _current_user_division_id(user, authz)
    try:
        return service.update_group(group_id, division_id, data)
    except OnCallSettingsError as e:
        return _settings_error_response(e)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete("/stationGroups/{group_id}")
def delete_on_call_station_group(
    group_id: int,
    service: OnCallSettingsService = Depends(get_on_call_settings_service),
    authz: AuthorizationService = Depends(get_authorization_service),
    current_user: dict = Depends(bind_current_user),
):
    """Deletes the group; its stations stay, in no group."""
    user = authz.get_logged_in_user_or_raise(current_user)
    authz.require_admin_role(user)
    division_id = _current_user_division_id(user, authz)
    try:
        service.delete_group(group_id, division_id)
        return {"message": "On-call station group deleted successfully"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


# --- General on-call settings of the division (e.g. the shift length) ---

@router.get("/generalSettings", response_model=OnCallGeneralSettingsResponse)
def get_on_call_general_settings(
    service: OnCallSettingsService = Depends(get_on_call_settings_service),
    authz: AuthorizationService = Depends(get_authorization_service),
    current_user: dict = Depends(bind_current_user),
):
    """The defaults when the division never saved its settings."""
    user = authz.get_logged_in_user_or_raise(current_user)
    division_id = _current_user_division_id(user, authz)
    return service.get_general_settings(division_id)


@router.put("/generalSettings", response_model=OnCallGeneralSettingsResponse)
def replace_on_call_general_settings(
    data: OnCallGeneralSettingsWrite,
    service: OnCallSettingsService = Depends(get_on_call_settings_service),
    authz: AuthorizationService = Depends(get_authorization_service),
    current_user: dict = Depends(bind_current_user),
):
    user = authz.get_logged_in_user_or_raise(current_user)
    authz.require_admin_role(user)
    division_id = _current_user_division_id(user, authz)
    return service.update_general_settings(division_id, data)


# --- Per-unit on-call settings: coverable stations and priority (division-scoped, admin-only) ---

@router.get("/unitSettings", response_model=list[OnCallUnitSettingsResponse])
def get_on_call_unit_settings(
    service: OnCallSettingsService = Depends(get_on_call_settings_service),
    authz: AuthorizationService = Depends(get_authorization_service),
    current_user: dict = Depends(bind_current_user),
):
    """Every unit of the division; `stationIds` empty means it can cover every station."""
    user = authz.get_logged_in_user_or_raise(current_user)
    division_id = _current_user_division_id(user, authz)
    return service.get_unit_settings(division_id)


@router.put("/unitSettings/{unit_id}", response_model=OnCallUnitSettingsResponse)
def replace_on_call_unit_settings(
    unit_id: UUID,
    data: OnCallUnitSettingsWrite,
    service: OnCallSettingsService = Depends(get_on_call_settings_service),
    authz: AuthorizationService = Depends(get_authorization_service),
    current_user: dict = Depends(bind_current_user),
):
    user = authz.get_logged_in_user_or_raise(current_user)
    authz.require_admin_role(user)
    division_id = _current_user_division_id(user, authz)
    try:
        return service.update_unit_settings(unit_id, division_id, data)
    except OnCallSettingsError as e:
        return _settings_error_response(e)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
