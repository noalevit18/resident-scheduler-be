from fastapi import APIRouter, Depends, HTTPException, status
from uuid import UUID
from app.schemas.schemas import Shift, ShiftCreate, ShiftStation, ShiftStationCreate
from app.services.shift_service import ShiftService
from app.services.shift_station_service import ShiftStationService
from app.dependencies import get_shift_service, get_shift_station_service

router = APIRouter(prefix="/shifts", tags=["shifts"])

# Shift CRUD
@router.get("/", response_model=list[Shift])
def get_shifts(account_id: UUID, service: ShiftService = Depends(get_shift_service)):
    return service.get_all_shifts(account_id)

@router.post("/", response_model=Shift)
def create_shift(data: ShiftCreate, service: ShiftService = Depends(get_shift_service)):
    return service.create_shift(data)

# Shift Station CRUD
@router.get("/stations", response_model=list[ShiftStation])
def get_stations(account_id: UUID, service: ShiftStationService = Depends(get_shift_station_service)):
    return service.get_all(account_id)

@router.post("/stations", response_model=ShiftStation)
def create_station(data: ShiftStationCreate, service: ShiftStationService = Depends(get_shift_station_service)):
    return service.create(data)

@router.delete("/stations/{ss_id}")
def delete_station(ss_id: int, account_id: UUID, service: ShiftStationService = Depends(get_shift_station_service)):
    try:
        service.delete(ss_id, account_id)
        return {"message": "Shift station deleted successfully"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
