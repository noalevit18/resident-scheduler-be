from fastapi import APIRouter, Depends, HTTPException, status
from uuid import UUID
from app.schemas.schemas import Constraint, ConstraintCreate, ConstraintType, ConstraintTypeCreate
from app.services.constraint_service import ConstraintService
from app.services.constraint_type_service import ConstraintTypeService
from app.dependencies import get_constraint_service, get_constraint_type_service

router = APIRouter(prefix="/constraints", tags=["constraints"])



# Constraint CRUD
@router.get("", response_model=list[Constraint])
def get_constraints(account_id: UUID, service: ConstraintService = Depends(get_constraint_service)):
    return service.get_all_constraints(account_id)

@router.post("", response_model=Constraint)
def create_constraint(data: ConstraintCreate, service: ConstraintService = Depends(get_constraint_service)):
    return service.create_constraint(data)

# Constraint Type CRUD
@router.get("/types", response_model=list[ConstraintType])
def get_types(account_id: UUID, service: ConstraintTypeService = Depends(get_constraint_type_service)):
    return service.get_all(account_id)

@router.post("/types", response_model=ConstraintType)
def create_type(data: ConstraintTypeCreate, service: ConstraintTypeService = Depends(get_constraint_type_service)):
    return service.create(data)

@router.delete("/types/{c_id}")
def delete_type(c_id: int, account_id: UUID, service: ConstraintTypeService = Depends(get_constraint_type_service)):
    try:
        service.delete(c_id, account_id)
        return {"message": "Constraint type deleted successfully"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
