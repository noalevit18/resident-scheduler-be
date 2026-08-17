from sqlalchemy.orm import Session
from app.models.models import Constraint
from app.schemas.schemas import ConstraintCreate
from uuid import UUID

class ConstraintRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_all(self, unit_id: UUID):
        return self.db.query(Constraint).filter(Constraint.unit_id == unit_id).all()

    def create(self, data: ConstraintCreate):
        db_obj = Constraint(**data.model_dump())
        self.db.add(db_obj)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj
