from sqlalchemy.orm import Session
from app.models.models import Senior
from app.schemas.schemas import SeniorCreate
from uuid import UUID
from typing import Optional


class SeniorRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_all(self, unit_id: UUID, include_deleted: bool = False):
        query = self.db.query(Senior).filter(Senior.unit_id == unit_id)
        if not include_deleted:
            query = query.filter(Senior.is_deleted.is_(False))
        return query.all()

    def get_by_id(self, senior_id: UUID, unit_id: UUID):
        return self.db.query(Senior).filter(
            Senior.id == senior_id, Senior.unit_id == unit_id, Senior.is_deleted.is_(False),
        ).first()

    def create(self, data: SeniorCreate, created_by: Optional[UUID]):
        db_obj = Senior(**data.model_dump(), created_by=created_by)
        self.db.add(db_obj)
        self.db.commit()
        return db_obj

    def update(self, senior_id: UUID, unit_id: UUID, data: dict):
        obj = self.get_by_id(senior_id, unit_id)
        if not obj:
            return None
        for key, value in data.items():
            setattr(obj, key, value)
        self.db.commit()
        return obj

    def delete(self, senior_id: UUID, unit_id: UUID, deleted_by: Optional[UUID]):
        obj = self.get_by_id(senior_id, unit_id)
        if not obj:
            return None
        obj.is_deleted = True
        obj.deleted_by = deleted_by
        self.db.commit()
        return obj
