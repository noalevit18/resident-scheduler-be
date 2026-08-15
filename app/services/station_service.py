from repositories.station_repository import StationRepository
from schemas.schemas import StationCreate
from uuid import UUID

class StationService:
    def __init__(self, repository: StationRepository):
        self.repository = repository

    def get_all_stations(self, unit_id: UUID):
        return self.repository.get_all(unit_id)

    def create_station(self, data: StationCreate):
        return self.repository.create(data)

    def delete_station(self, station_id: int, unit_id: UUID):
        if not self.repository.delete(station_id, unit_id):
            raise ValueError("Station not found")
        return True
