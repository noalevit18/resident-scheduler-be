from repositories.shift_station_repository import ShiftStationRepository
from schemas.schemas import ShiftStationCreate
from uuid import UUID

class ShiftStationService:
    def __init__(self, repository: ShiftStationRepository):
        self.repository = repository

    def get_all(self, account_id: UUID):
        return self.repository.get_all(account_id)

    def create(self, data: ShiftStationCreate):
        return self.repository.create(data)

    def delete(self, ss_id: int, account_id: UUID):
        if not self.repository.delete(ss_id, account_id):
            raise ValueError("Shift station not found")
        return True
