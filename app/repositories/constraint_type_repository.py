from sqlalchemy.orm import Session
from app.models.models import ConstraintType
from app.schemas.schemas import ConstraintTypeCreate
from uuid import UUID

class ConstraintTypeRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_all(self, division_id: UUID):
        return self.db.query(ConstraintType).filter(ConstraintType.division_id == division_id).all()

    def create(self, data: ConstraintTypeCreate):
        db_obj = ConstraintType(**data.model_dump())
        self.db.add(db_obj)
        self.db.commit()
        return db_obj

    def delete(self, c_id: int, division_id: UUID):
        obj = self.db.query(ConstraintType).filter(ConstraintType.id == c_id, ConstraintType.division_id == division_id).first()
        if not obj:
            return None
        name = obj.name
        self.db.delete(obj)
        self.db.commit()
        return name
