import logging
from uuid import UUID

from app.models.models import ConstraintTypeScope
from app.repositories.constraint_type_repository import ConstraintTypeRepository
from app.schemas.schemas import (
    ConstraintTypeCreate, ConstraintTypeUpdate, OnCallConstraintTypeCreate, OnCallConstraintTypeUpdate,
)
from app.context import get_current_user_label

logger = logging.getLogger(__name__)

SCOPE_LABELS = {
    ConstraintTypeScope.SCHEDULE: "Constraint type",
    ConstraintTypeScope.ON_CALL: "On-call constraint type",
}


class ConstraintTypeService:
    """Constraint types of two separate lists, kept apart by `scope`:
    - SCHEDULE: the daily schedule's constraints — blocking or preference
      types (want / prefer not), managed via /constraints/types.
    - ON_CALL: the on-call constraints' hard "can't" reasons (vacation, army,
      ...) — always blocking, managed via /on-call-constraints/types.
    Every operation takes the scope it works on; a type of one scope is
    "not found" from the other's."""

    def __init__(self, repository: ConstraintTypeRepository):
        self.repository = repository

    # --- shared, scoped ---

    def get_all(self, account_id: UUID, scope: ConstraintTypeScope, include_deleted: bool = False):
        return self.repository.get_all(account_id, scope, include_deleted=include_deleted)

    def get_by_id(self, c_id: int, account_id: UUID, scope: ConstraintTypeScope):
        constraint_type = self.repository.get_by_id(c_id, account_id, scope)
        if not constraint_type:
            raise ValueError(f"{SCOPE_LABELS[scope]} not found")
        return constraint_type

    def get_existing_ids(self, ids: list[int], account_id: UUID, scope: ConstraintTypeScope) -> set[int]:
        return self.repository.get_existing_ids(ids, account_id, scope)

    def get_existing_ids_for_unit(self, ids: list[int], unit_id: UUID, scope: ConstraintTypeScope) -> set[int]:
        return self.repository.get_existing_ids_for_unit(ids, unit_id, scope)

    def get_preferences_by_ids(self, ids: list[int]) -> dict[int, int]:
        return self.repository.get_preferences_by_ids(ids)

    def delete(self, c_id: int, account_id: UUID, scope: ConstraintTypeScope):
        name = self.repository.delete(c_id, account_id, scope)
        if not name:
            raise ValueError(f"{SCOPE_LABELS[scope]} not found")
        logger.info(
            "Deleted %s constraint type %s (account_id=%s) by %s",
            scope.value, name, account_id, get_current_user_label(),
        )
        return True

    # --- daily schedule constraint types ---

    def create(self, data: ConstraintTypeCreate):
        return self._create(data, ConstraintTypeScope.SCHEDULE)

    def update(self, c_id: int, account_id: UUID, data: ConstraintTypeUpdate):
        return self._update(c_id, account_id, data, ConstraintTypeScope.SCHEDULE)

    # --- on-call constraint types (always blocking) ---

    def create_on_call(self, data: OnCallConstraintTypeCreate):
        return self._create(ConstraintTypeCreate(**data.model_dump()), ConstraintTypeScope.ON_CALL)

    def update_on_call(self, c_id: int, account_id: UUID, data: OnCallConstraintTypeUpdate):
        return self._update(
            c_id, account_id, ConstraintTypeUpdate(**data.model_dump(exclude_unset=True)), ConstraintTypeScope.ON_CALL,
        )

    # --- internals ---

    def _create(self, data: ConstraintTypeCreate, scope: ConstraintTypeScope):
        constraint_type = self.repository.create(data, scope)
        logger.info(
            "Created %s constraint type %s (account_id=%s) by %s",
            scope.value, constraint_type.name, constraint_type.account_id, get_current_user_label(),
        )
        return constraint_type

    def _update(self, c_id: int, account_id: UUID, data: ConstraintTypeUpdate, scope: ConstraintTypeScope):
        constraint_type = self.repository.update(c_id, account_id, data, scope)
        if not constraint_type:
            raise ValueError(f"{SCOPE_LABELS[scope]} not found")
        logger.info(
            "Updated %s constraint type %s (account_id=%s) by %s",
            scope.value, constraint_type.name, account_id, get_current_user_label(),
        )
        return constraint_type
