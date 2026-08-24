from fastapi import APIRouter, Depends, HTTPException, status
from uuid import UUID
from app.schemas.schemas import Station, StationCreate
from app.services.station_service import StationService
from app.dependencies import get_station_service
from app.context import bind_current_user

router = APIRouter(prefix="/stations", tags=["stations"])

@router.get("", response_model=list[Station])
def get_stations(account_id: UUID, service: StationService = Depends(get_station_service)):
    return service.get_all_stations(account_id)

@router.post("", response_model=Station)
def create_station(data: StationCreate, service: StationService = Depends(get_station_service)):
    return service.create_station(data)

@router.delete("/{station_id}")
def delete_station(station_id: int, account_id: UUID, service: StationService = Depends(get_station_service), _: dict = Depends(bind_current_user)):
    try:
        service.delete_station(station_id, account_id)
        return {"message": "Station deleted successfully"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
