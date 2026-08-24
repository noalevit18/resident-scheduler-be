from fastapi import APIRouter, Depends, HTTPException, status
from uuid import UUID
from app.schemas.schemas import (
    StaffCertificationCreate, StaffCertificationUpdate, StaffCertificationResponse,
    StaffRotationCreate, StaffRotationUpdate, StaffRotationResponse, StaffSettingsResponse,
)
from app.services.staff_settings_service import StaffCertificationService, StaffRotationService, StaffSettingsService
from app.dependencies import get_certification_service, get_staff_rotation_service, get_staff_settings_service
from app.context import bind_current_user

router = APIRouter(prefix="/staff/settings", tags=["staff/settings"])


# ==========================================
# CERTIFICATIONS (unit-scoped)
# ==========================================

@router.get("/certifications", response_model=list[StaffCertificationResponse])
def get_certifications(unit_id: UUID, service: StaffCertificationService = Depends(get_certification_service)):
    return service.get_all_certifications(unit_id)


@router.post("/certifications", response_model=StaffCertificationResponse)
def create_certification(data: StaffCertificationCreate, service: StaffCertificationService = Depends(get_certification_service)):
    return service.create_certification(data)


@router.patch("/certifications/{certification_id}")
def update_certification(
    certification_id: int,
    unit_id: UUID,
    update_data: StaffCertificationUpdate,
    service: StaffCertificationService = Depends(get_certification_service),
):
    certification_data = update_data.model_dump(exclude_unset=True)
    if not certification_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update")
    try:
        service.update_certification(certification_id, unit_id, certification_data)
        return {"message": "Certification updated"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete("/certifications/{certification_id}")
def delete_certification(certification_id: int, unit_id: UUID, service: StaffCertificationService = Depends(get_certification_service), _: dict = Depends(bind_current_user)):
    try:
        service.delete_certification(certification_id, unit_id)
        return {"message": "Certification deleted successfully"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


# ==========================================
# STAFF ROTATIONS (division-scoped)
# ==========================================

@router.get("/rotations", response_model=list[StaffRotationResponse])
def get_staff_rotations(division_id: UUID, service: StaffRotationService = Depends(get_staff_rotation_service)):
    return service.get_all_rotations(division_id)


@router.post("/rotations", response_model=StaffRotationResponse)
def create_staff_rotation(data: StaffRotationCreate, service: StaffRotationService = Depends(get_staff_rotation_service)):
    return service.create_rotation(data)


@router.patch("/rotations/{rotation_id}")
def update_staff_rotation(
    rotation_id: int,
    division_id: UUID,
    update_data: StaffRotationUpdate,
    service: StaffRotationService = Depends(get_staff_rotation_service),
):
    rotation_data = update_data.model_dump(exclude_unset=True)
    if not rotation_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update")
    try:
        service.update_rotation(rotation_id, division_id, rotation_data)
        return {"message": "Staff rotation updated"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete("/rotations/{rotation_id}")
def delete_staff_rotation(rotation_id: int, division_id: UUID, service: StaffRotationService = Depends(get_staff_rotation_service), _: dict = Depends(bind_current_user)):
    try:
        service.delete_rotation(rotation_id, division_id)
        return {"message": "Staff rotation deleted successfully"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


# ==========================================
# ALL STAFF SETTINGS
# ==========================================

@router.get("", response_model=StaffSettingsResponse)
def get_all_settings(division_id: UUID, unit_id: UUID, service: StaffSettingsService = Depends(get_staff_settings_service)):
    try:
        return service.get_all_settings(division_id, unit_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))