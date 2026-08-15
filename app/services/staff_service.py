from app.repositories.staff_repository import StaffRepository
from app.schemas.schemas import Staff, StaffCreate
from uuid import UUID

class StaffService:
    def __init__(self, repository: StaffRepository):
        self.repository = repository

    def get_all_staff(self, unit_id: UUID):
        return self.repository.get_all(unit_id)

    def get_staff_member(self, member_id: UUID, unit_id: UUID):
        staff_member = self.repository.get_by_id(member_id, unit_id)
        if not staff_member:
            raise ValueError("Staff member not found")
        return staff_member

    def create_staff(self, staff_data: StaffCreate):
        return self.repository.create(staff_data)

    def delete_staff(self, member_id: UUID, unit_id: UUID):
        if not self.repository.delete(member_id, unit_id):
            raise ValueError("Staff member not found")
        return True
