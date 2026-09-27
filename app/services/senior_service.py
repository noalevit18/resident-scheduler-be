import logging
from typing import Optional
from uuid import UUID

from app.repositories.senior_repository import SeniorRepository
from app.schemas.schemas import SeniorCreate
from app.context import get_current_user_label

logger = logging.getLogger(__name__)


class SeniorService:
    def __init__(self, repository: SeniorRepository):
        self.repository = repository

    def get_all_seniors(self, unit_id: UUID, include_deleted: bool = False):
        return self.repository.get_all(unit_id, include_deleted)

    def create_senior(self, data: SeniorCreate, created_by: Optional[UUID]):
        senior = self.repository.create(data, created_by)
        logger.info("Created senior %s (unit_id=%s) by %s", senior.name, data.unit_id, get_current_user_label())
        return senior

    def update_senior(self, senior_id: UUID, unit_id: UUID, update_data: dict):
        senior = self.repository.update(senior_id, unit_id, update_data)
        if not senior:
            raise ValueError("Senior not found")
        logger.info("Updated senior %s (unit_id=%s) by %s", senior.name, unit_id, get_current_user_label())
        return senior

    def delete_senior(self, senior_id: UUID, unit_id: UUID, deleted_by: Optional[UUID]):
        senior = self.repository.delete(senior_id, unit_id, deleted_by)
        if not senior:
            raise ValueError("Senior not found")
        logger.info("Deleted senior %s (unit_id=%s) by %s", senior.name, unit_id, get_current_user_label())
        return True
