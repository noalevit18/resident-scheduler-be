from sqlalchemy.orm import Session
from app.models.models import Senior
from app.schemas.schemas import SeniorCreate
from uuid import UUID

class SeniorRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_all(self, unit_id: UUID):
        return self.db.query(Senior).filter(Senior.unit_id == unit_id).all()

    def create(self, data: SeniorCreate):
        db_obj = Senior(**data.model_dump())
        self.db.add(db_obj)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj

    def delete(self, senior_id: int, unit_id: UUID):
        obj = self.db.query(Senior).filter(Senior.id == senior_id, Senior.unit_id == unit_id).first()
        if obj:
            self.db.delete(obj)
            self.db.commit()
            return True
        return False

