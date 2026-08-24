import logging

from app.repositories.senior_repository import SeniorRepository
from app.schemas.schemas import SeniorCreate
from app.context import get_current_user_label
from uuid import UUID

logger = logging.getLogger(__name__)

class SeniorService:
    def __init__(self, repository: SeniorRepository):
        self.repository = repository

    def get_all_seniors(self, unit_id: UUID):
        return self.repository.get_all(unit_id)

    def create_senior(self, data: SeniorCreate):
        return self.repository.create(data)

    def delete_senior(self, senior_id: int, unit_id: UUID):
        name = self.repository.delete(senior_id, unit_id)
        logger.info("Deleted senior %s (unit_id=%s) by %s", name or senior_id, unit_id, get_current_user_label())
        return True
