from sqlalchemy.orm import Session
from app.models.models import ConstraintType
from app.schemas.schemas import ConstraintTypeCreate, ConstraintTypeUpdate
from uuid import UUID

class ConstraintTypeRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_all(self, account_id: UUID, include_deleted: bool = False):
        query = self.db.query(ConstraintType).filter(ConstraintType.account_id == account_id)
        if not include_deleted:
            query = query.filter(ConstraintType.is_deleted.is_(False))
        return query.all()

    def get_by_id(self, c_id: int, account_id: UUID):
        return self.db.query(ConstraintType).filter(
            ConstraintType.id == c_id, ConstraintType.account_id == account_id, ConstraintType.is_deleted.is_(False),
        ).first()

    def get_existing_ids(self, ids: list[int], account_id: UUID) -> set[int]:
        if not ids:
            return set()
        rows = (
            self.db.query(ConstraintType.id)
            .filter(ConstraintType.id.in_(ids), ConstraintType.account_id == account_id)
            .all()
        )
        return {r.id for r in rows}

    def create(self, data: ConstraintTypeCreate):
        db_obj = ConstraintType(**data.model_dump())
        self.db.add(db_obj)
        self.db.commit()
        return db_obj

    def update(self, c_id: int, account_id: UUID, data: ConstraintTypeUpdate):
        obj = self.get_by_id(c_id, account_id)
        if not obj:
            return None
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(obj, field, value)
        self.db.commit()
        return obj

    def delete(self, c_id: int, account_id: UUID):
        obj = self.get_by_id(c_id, account_id)
        if not obj:
            return None
        name = obj.name
        obj.is_deleted = True
        self.db.commit()
        return name
