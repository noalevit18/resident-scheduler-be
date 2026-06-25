from repositories.resident_repository import ResidentRepository
from schemas.schemas import Resident, ResidentCreate
from uuid import UUID

class ResidentService:
    def __init__(self, repository: ResidentRepository):
        self.repository = repository

    def get_all_residents(self, account_id: UUID):
        return self.repository.get_all(account_id)

    def get_resident(self, resident_id: UUID, account_id: UUID):
        resident = self.repository.get_by_id(resident_id, account_id)
        if not resident:
            raise ValueError("Resident not found")
        return resident

    def create_resident(self, resident_data: ResidentCreate):
        return self.repository.create(resident_data)

    def delete_resident(self, resident_id: UUID, account_id: UUID):
        if not self.repository.delete(resident_id, account_id):
            raise ValueError("Resident not found")
        return True
