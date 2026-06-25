from sqlalchemy.orm import Session
from models.models import Shift
from schemas.schemas import ShiftCreate
from uuid import UUID

class ShiftRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_all(self, account_id: UUID):
        return self.db.query(Shift).filter(Shift.account_id == account_id).all()

    def create(self, data: ShiftCreate):
        db_obj = Shift(**data.model_dump())
        self.db.add(db_obj)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj

    def delete(self, shift_id: int, account_id: UUID):
        obj = self.db.query(Shift).filter(Shift.id == shift_id, Shift.account_id == account_id).first()
        if obj:
            self.db.delete(obj)
            self.db.commit()
            return True
        return False
