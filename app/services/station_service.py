from repositories.station_repository import StationRepository
from schemas.schemas import StationCreate
from uuid import UUID

class StationService:
    def __init__(self, repository: StationRepository):
        self.repository = repository

    def get_all_stations(self, account_id: UUID):
        return self.repository.get_all(account_id)

    def create_station(self, data: StationCreate):
        return self.repository.create(data)

    def delete_station(self, station_id: int, account_id: UUID):
        if not self.repository.delete(station_id, account_id):
            raise ValueError("Station not found")
        return True
