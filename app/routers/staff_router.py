from fastapi import APIRouter, Depends, HTTPException, status
from uuid import UUID
from app.schemas.schemas import StaffCreate, StaffUpdate, StaffResponse
from app.services.staff_service import StaffService
from app.dependencies import get_staff_service
from app.context import bind_current_user

router = APIRouter(prefix="/staff", tags=["staff"])


@router.get("", response_model=list[StaffResponse])
def get_staff_members(unit_id: UUID, service: StaffService = Depends(get_staff_service)):
    return service.get_all_members(unit_id)

@router.get("/{member_id}", response_model=StaffResponse)
def get_member(member_id: UUID, unit_id: UUID, service: StaffService = Depends(get_staff_service)):
    try:
        return service.get_staff_member(member_id, unit_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

@router.post("", response_model=StaffResponse)
def create_member(member_data: StaffCreate, service: StaffService = Depends(get_staff_service)):
    return service.create_member(member_data)

@router.patch("/{member_id}", response_model=StaffResponse)
def update_member(member_id: UUID, unit_id: UUID, update_data: StaffUpdate, service: StaffService = Depends(get_staff_service)):
    member_data = update_data.model_dump(exclude_unset=True)
    if not member_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update")
    try:
        return service.update_member(member_id, unit_id, member_data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

@router.delete("/{member_id}")
def delete_member(member_id: UUID, unit_id: UUID, service: StaffService = Depends(get_staff_service), _: dict = Depends(bind_current_user)):
    try:
        service.delete_staff(member_id, unit_id)
        return {"message": "Staff member deleted successfully"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
