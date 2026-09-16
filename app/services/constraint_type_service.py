import logging

from app.repositories.constraint_type_repository import ConstraintTypeRepository
from app.schemas.schemas import ConstraintTypeCreate, ConstraintTypeUpdate
from app.context import get_current_user_label
from uuid import UUID

logger = logging.getLogger(__name__)

class ConstraintTypeService:
    def __init__(self, repository: ConstraintTypeRepository):
        self.repository = repository

    def get_all(self, account_id: UUID, include_deleted: bool = False):
        return self.repository.get_all(account_id, include_deleted=include_deleted)

    def get_by_id(self, c_id: int, account_id: UUID):
        constraint_type = self.repository.get_by_id(c_id, account_id)
        if not constraint_type:
            raise ValueError("Constraint type not found")
        return constraint_type

    def get_existing_ids(self, ids: list[int], account_id: UUID) -> set[int]:
        return self.repository.get_existing_ids(ids, account_id)

    def create(self, data: ConstraintTypeCreate):
        constraint_type = self.repository.create(data)
        logger.info("Created constraint type %s (account_id=%s) by %s", constraint_type.name, constraint_type.account_id, get_current_user_label())
        return constraint_type

    def update(self, c_id: int, account_id: UUID, data: ConstraintTypeUpdate):
        constraint_type = self.repository.update(c_id, account_id, data)
        if not constraint_type:
            raise ValueError("Constraint type not found")
        logger.info("Updated constraint type %s (account_id=%s) by %s", constraint_type.name, account_id, get_current_user_label())
        return constraint_type

    def delete(self, c_id: int, account_id: UUID):
        name = self.repository.delete(c_id, account_id)
        if not name:
            raise ValueError("Constraint type not found")
        logger.info("Deleted constraint type %s (account_id=%s) by %s", name, account_id, get_current_user_label())
        return True
