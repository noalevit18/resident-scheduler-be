import logging

from app.repositories.user_repository import UserRepository
from app.services.unit_service import UnitService
from app.services.division_service import DivisionService
from app.schemas.schemas import User, UserResponse
from app.context import get_current_user_label
from uuid import UUID

logger = logging.getLogger(__name__)

class UserService:
    def __init__(self, repository: UserRepository, unit_service: UnitService = None, division_service: DivisionService = None):
        self.repository = repository
        self.unit_service = unit_service
        self.division_service = division_service

    def get_all_users(self, division_id: UUID):
        return self.repository.get_all(division_id)

    def create_user(self, data: User):
        return self.repository.create(data)

    def update_user(self, user_id: UUID, division_id: UUID, user_data: dict):
        return self.repository.update_user(user_id, division_id, user_data)

    def login(self, email: str):
        user = self.repository.get_by_email(email)
        if not user:
            raise ValueError("User not found")
        if not user.is_active:
            raise ValueError("User is inactive")
        
        user_response = UserResponse.model_validate(user)
        
        if user.unit_id and self.unit_service:
            unit_data = self.unit_service.get_unit_details(user.unit_id)
            if unit_data:
                user_response.unit_name = unit_data.get("unit_name")
                user_response.division_name = unit_data.get("division_name")
                user_response.hospital_name = unit_data.get("hospital_name")
        elif user.division_id and self.division_service:
            division_data = self.division_service.get_division_details(user.division_id)
            if division_data:
                user_response.division_name = division_data.get("division_name")
                user_response.hospital_name = division_data.get("hospital_name")

        return user_response

    def delete_user(self, user_id: UUID, division_id: UUID):
        name = self.repository.delete(user_id, division_id)
        logger.info("Deleted user %s (division_id=%s) by %s", name or user_id, division_id, get_current_user_label())
        return True


