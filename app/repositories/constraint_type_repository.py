from sqlalchemy.orm import Session
from app.models.models import ConstraintType, ConstraintTypeKind, ConstraintTypeScope, Division, Unit
from app.schemas.schemas import ConstraintTypeCreate, ConstraintTypeUpdate
from uuid import UUID

class ConstraintTypeRepository:
    """Every lookup is filtered by scope, so the schedule's and the on-call
    constraints' type lists never see each other's types."""

    def __init__(self, db: Session):
        self.db = db

    def get_all(self, account_id: UUID, scope: ConstraintTypeScope, include_deleted: bool = False):
        query = self.db.query(ConstraintType).filter(ConstraintType.account_id == account_id, ConstraintType.scope == scope)
        if not include_deleted:
            query = query.filter(ConstraintType.is_deleted.is_(False))
        return query.all()

    def get_by_id(self, c_id: int, account_id: UUID, scope: ConstraintTypeScope):
        return self.db.query(ConstraintType).filter(
            ConstraintType.id == c_id, ConstraintType.account_id == account_id, ConstraintType.scope == scope,
            ConstraintType.is_deleted.is_(False),
        ).first()

    def get_preferences_by_ids(self, ids: list[int]) -> dict[int, int]:
        """{type_id: preference} of the given types (0 for non-preference kinds)."""
        if not ids:
            return {}
        rows = self.db.query(ConstraintType.id, ConstraintType.preference).filter(ConstraintType.id.in_(ids)).all()
        return {r.id: r.preference for r in rows}

    def get_existing_ids(self, ids: list[int], account_id: UUID, scope: ConstraintTypeScope) -> set[int]:
        if not ids:
            return set()
        rows = (
            self.db.query(ConstraintType.id)
            .filter(ConstraintType.id.in_(ids), ConstraintType.account_id == account_id, ConstraintType.scope == scope)
            .all()
        )
        return {r.id for r in rows}

    def get_existing_ids_for_unit(self, ids: list[int], unit_id: UUID, scope: ConstraintTypeScope) -> set[int]:
        """The given ids that are types of `scope` in the unit's account (soft-deleted included,
        like get_existing_ids, so re-saving data that references a since-deleted type still works)."""
        if not ids:
            return set()
        rows = (
            self.db.query(ConstraintType.id)
            .join(Division, Division.account_id == ConstraintType.account_id)
            .join(Unit, Unit.division_id == Division.id)
            .filter(Unit.id == unit_id, ConstraintType.id.in_(ids), ConstraintType.scope == scope)
            .all()
        )
        return {r.id for r in rows}

    def create(self, data: ConstraintTypeCreate, scope: ConstraintTypeScope):
        db_obj = ConstraintType(**data.model_dump(), scope=scope)
        self.db.add(db_obj)
        self.db.commit()
        return db_obj

    def update(self, c_id: int, account_id: UUID, data: ConstraintTypeUpdate, scope: ConstraintTypeScope):
        obj = self.get_by_id(c_id, account_id, scope)
        if not obj:
            return None
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(obj, field, value)
        if obj.kind != ConstraintTypeKind.PREFERENCE:
            obj.preference = 0
        self.db.commit()
        return obj

    def delete(self, c_id: int, account_id: UUID, scope: ConstraintTypeScope):
        obj = self.get_by_id(c_id, account_id, scope)
        if not obj:
            return None
        name = obj.name
        obj.is_deleted = True
        self.db.commit()
        return name
