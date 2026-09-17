import logging

from app.repositories.staff_repository import StaffRepository
from app.services.user_service import UserService
from app.schemas.schemas import StaffCreate
from app.context import get_current_user_label
from uuid import UUID

logger = logging.getLogger(__name__)


class StaffService:
    def __init__(self, repository: StaffRepository, user_service: UserService):
        self.repository = repository
        self.user_service = user_service

    def get_all_members(self, unit_id: UUID):
        return self.repository.get_all(unit_id)

    def get_staff_member(self, member_id: UUID, unit_id: UUID):
        staff_member = self.repository.get_by_id(member_id, unit_id)
        if not staff_member:
            raise ValueError("Staff member not found")
        return staff_member

    def get_unit_member_ids(self, ids: list[UUID], unit_id: UUID) -> set[UUID]:
        return self.repository.get_existing_ids(ids, unit_id)

    def is_logged_in_user_a_staff_member(self, unit_id: UUID, current_user: dict):
        user_id = self.user_service.get_logged_in_user_id(current_user)
        staff_member = self.repository.get_by_user_id(user_id, unit_id) if user_id else None
        if not staff_member:
            raise ValueError("Logged-in user has no staff member record in this unit")
        return staff_member

    def create_member(self, staff_data: StaffCreate):
        return self.repository.create(staff_data)

    def update_member(self, member_id: UUID, unit_id: UUID, update_data: dict):
        staff_member = self.repository.update(member_id, unit_id, update_data)
        if not staff_member:
            raise ValueError("Staff member not found")
        return staff_member

    def delete_staff(self, member_id: UUID, unit_id: UUID):
        name = self.repository.delete(member_id, unit_id)
        logger.info("Deleted staff member %s (unit_id=%s) by %s", name or member_id, unit_id, get_current_user_label())
        return True
