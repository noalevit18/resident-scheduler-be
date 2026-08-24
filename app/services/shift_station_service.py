import logging

from app.repositories.shift_station_repository import ShiftStationRepository
from app.schemas.schemas import ShiftStationCreate
from app.context import get_current_user_label
from uuid import UUID

logger = logging.getLogger(__name__)

class ShiftStationService:
    def __init__(self, repository: ShiftStationRepository):
        self.repository = repository

    def get_all(self, division_id: UUID):
        return self.repository.get_all(division_id)

    def create(self, data: ShiftStationCreate):
        return self.repository.create(data)

    def delete(self, ss_id: int, division_id: UUID):
        name = self.repository.delete(ss_id, division_id)
        logger.info("Deleted shift station %s (division_id=%s) by %s", name or ss_id, division_id, get_current_user_label())
        return True
