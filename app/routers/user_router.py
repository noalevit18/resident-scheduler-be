from fastapi import APIRouter, Depends, HTTPException, status
from uuid import UUID
from app.schemas.schemas import User, UserResponse, UserUpdate
from app.services.user_service import UserService
from app.services.staff_member_submission_service import StaffMemberSubmissionService
from app.dependencies import get_user_service, get_staff_member_submission_service
from app.auth import get_current_user
from app.context import bind_current_user

router = APIRouter(prefix="/users", tags=["users"])

# Login endpoint that validates user existence in DB
@router.post("/login", response_model=UserResponse)
def login_user(
    service: UserService = Depends(get_user_service),
    submission_service: StaffMemberSubmissionService = Depends(get_staff_member_submission_service),
    current_user: dict = Depends(get_current_user)
):
    try:
        user_response = service.login(current_user.get("sub"), current_user["email"])
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))

    if user_response.unit_id:
        user_response.constraints_submitted_this_month = submission_service.has_submitted_this_month(
            user_response.unit_id, current_user
        )

    return user_response

@router.patch("/{user_id}")
def update_user(user_id: UUID, division_id: UUID, update_data: UserUpdate, service: UserService = Depends(get_user_service)):
    user_data = update_data.model_dump(exclude_unset=True)
    if not user_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update")
    if not service.update_user(user_id, division_id, user_data):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return {"message": "User updated"}

@router.get("", response_model=list[User])
def get_users(division_id: UUID, service: UserService = Depends(get_user_service)):
    return service.get_all_users(division_id)

@router.post("", response_model=User)
def create_user(data: User, service: UserService = Depends(get_user_service)):
    return service.create_user(data)

@router.delete("/{user_id}")
def delete_user(user_id: UUID, division_id: UUID, service: UserService = Depends(get_user_service), _: dict = Depends(bind_current_user)):
    try:
        service.delete_user(user_id, division_id)
        return {"message": "User deleted successfully"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


