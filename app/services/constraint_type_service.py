import logging

from app.repositories.constraint_type_repository import ConstraintTypeRepository
from app.schemas.schemas import ConstraintTypeCreate
from app.context import get_current_user_label
from uuid import UUID

logger = logging.getLogger(__name__)

class ConstraintTypeService:
    def __init__(self, repository: ConstraintTypeRepository):
        self.repository = repository

    def get_all(self, division_id: UUID):
        return self.repository.get_all(division_id)

    def create(self, data: ConstraintTypeCreate):
        return self.repository.create(data)

    def delete(self, c_id: int, division_id: UUID):
        name = self.repository.delete(c_id, division_id)
        logger.info("Deleted constraint type %s (division_id=%s) by %s", name or c_id, division_id, get_current_user_label())
        return True
