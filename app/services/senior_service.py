from repositories.senior_repository import SeniorRepository
from schemas.schemas import SeniorCreate
from uuid import UUID

class SeniorService:
    def __init__(self, repository: SeniorRepository):
        self.repository = repository

    def get_all_seniors(self, unit_id: UUID):
        return self.repository.get_all(unit_id)

    def create_senior(self, data: SeniorCreate):
        return self.repository.create(data)

    def delete_senior(self, senior_id: int, unit_id: UUID):
        if not self.repository.delete(senior_id, unit_id):
            raise ValueError("Senior not found")
        return True
