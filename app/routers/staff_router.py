from fastapi import APIRouter, Depends, HTTPException, status
from uuid import UUID
from app.schemas.schemas import Staff, StaffCreate
from app.services.staff_service import StaffService
from app.dependencies import get_staff_service

router = APIRouter(prefix="/staff", tags=["staff"])


@router.get("", response_model=list[Staff])
def get_staff(account_id: UUID, service: StaffService = Depends(get_staff_service)):
    return service.get_all_staff(account_id)

@router.get("/{staff_id}", response_model=Staff)
def get_staff_member(staff_id: UUID, account_id: UUID, service: StaffService = Depends(get_staff_service)):
    try:
        return service.get_staff_member(staff_id, account_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

@router.post("", response_model=Staff)
def create_staff(staff_data: StaffCreate, service: StaffService = Depends(get_staff_service)):
    return service.create_staff(staff_data)

@router.delete("/{staff_id}")
def delete_staff(staff_id: UUID, account_id: UUID, service: StaffService = Depends(get_staff_service)):
    try:
        service.delete_staff(staff_id, account_id)
        return {"message": "Staff member deleted successfully"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
