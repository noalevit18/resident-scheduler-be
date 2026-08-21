import logging

from app.repositories.station_repository import StationRepository
from app.schemas.schemas import StationCreate
from app.context import get_current_user_label
from uuid import UUID

logger = logging.getLogger(__name__)

class StationService:
    def __init__(self, repository: StationRepository):
        self.repository = repository

    def get_all_stations(self, unit_id: UUID):
        return self.repository.get_all(unit_id)

    def create_station(self, data: StationCreate):
        return self.repository.create(data)

    def delete_station(self, station_id: int, unit_id: UUID):
        name = self.repository.delete(station_id, unit_id)
        logger.info("Deleted station %s (unit_id=%s) by %s", name or station_id, unit_id, get_current_user_label())
        return True
