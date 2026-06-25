from fastapi import APIRouter, Depends, HTTPException, status
from uuid import UUID
from schemas.schemas import Resident, ResidentCreate
from services.resident_service import ResidentService
from dependencies import get_resident_service

router = APIRouter(prefix="/residents", tags=["residents"])


@router.get("/", response_model=list[Resident])
def get_residents(account_id: UUID, service: ResidentService = Depends(get_resident_service)):
    return service.get_all_residents(account_id)

@router.get("/{resident_id}", response_model=Resident)
def get_resident(resident_id: UUID, account_id: UUID, service: ResidentService = Depends(get_resident_service)):
    try:
        return service.get_resident(resident_id, account_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

@router.post("/", response_model=Resident)
def create_resident(resident_data: ResidentCreate, service: ResidentService = Depends(get_resident_service)):
    return service.create_resident(resident_data)

@router.delete("/{resident_id}")
def delete_resident(resident_id: UUID, account_id: UUID, service: ResidentService = Depends(get_resident_service)):
    try:
        service.delete_resident(resident_id, account_id)
        return {"message": "Resident deleted successfully"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
