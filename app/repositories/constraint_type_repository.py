from sqlalchemy.orm import Session
from models.models import ConstraintType
from schemas.schemas import ConstraintTypeCreate
from uuid import UUID

class ConstraintTypeRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_all(self, account_id: UUID):
        return self.db.query(ConstraintType).filter(ConstraintType.account_id == account_id).all()

    def create(self, data: ConstraintTypeCreate):
        db_obj = ConstraintType(**data.model_dump())
        self.db.add(db_obj)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj

    def delete(self, c_id: int, account_id: UUID):
        obj = self.db.query(ConstraintType).filter(ConstraintType.id == c_id, ConstraintType.account_id == account_id).first()
        if obj:
            self.db.delete(obj)
            self.db.commit()
            return True
        return False
