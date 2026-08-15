from repositories.shift_repository import ShiftRepository
from schemas.schemas import ShiftCreate
from uuid import UUID

class ShiftService:
    def __init__(self, repository: ShiftRepository):
        self.repository = repository

    def get_all_shifts(self, unit_id: UUID):
        return self.repository.get_all(unit_id)

    def create_shift(self, data: ShiftCreate):
        return self.repository.create(data)
