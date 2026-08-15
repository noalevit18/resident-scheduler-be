from fastapi import APIRouter, Depends, HTTPException, status
from uuid import UUID
from app.schemas.schemas import Senior, SeniorCreate
from app.services.senior_service import SeniorService
from app.dependencies import get_senior_service


router = APIRouter(prefix="/seniors", tags=["seniors"])


@router.get("/", response_model=list[Senior])
def get_seniors(account_id: UUID, service: SeniorService = Depends(get_senior_service)):
    return service.get_all_seniors(account_id)

@router.post("/", response_model=Senior)
def create_senior(data: SeniorCreate, service: SeniorService = Depends(get_senior_service)):
    return service.create_senior(data)

@router.delete("/{senior_id}")
def delete_senior(senior_id: int, account_id: UUID, service: SeniorService = Depends(get_senior_service)):
    try:
        service.delete_senior(senior_id, account_id)
        return {"message": "Senior deleted successfully"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))