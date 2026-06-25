from fastapi import APIRouter, Depends, HTTPException, status
from uuid import UUID
from schemas.schemas import AccountAdmin, AccountAdminCreate
from services.account_admin_service import AccountAdminService
from dependencies import get_account_admin_service

router = APIRouter(prefix="/admins", tags=["admins"])

@router.get("/", response_model=list[AccountAdmin])
def get_admins(account_id: UUID, service: AccountAdminService = Depends(get_account_admin_service)):
    return service.get_all_admins(account_id)

@router.post("/", response_model=AccountAdmin)
def create_admin(data: AccountAdminCreate, service: AccountAdminService = Depends(get_account_admin_service)):
    return service.create_admin(data)

@router.delete("/{admin_id}")
def delete_admin(admin_id: UUID, account_id: UUID, service: AccountAdminService = Depends(get_account_admin_service)):
    try:
        service.delete_admin(admin_id, account_id)
        return {"message": "Admin deleted successfully"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

