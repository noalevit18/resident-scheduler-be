from sqlalchemy.orm import Session
from models.models import ShiftStation
from schemas.schemas import ShiftStationCreate
from uuid import UUID

class ShiftStationRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_all(self, division_id: UUID):
        return self.db.query(ShiftStation).filter(ShiftStation.division_id == division_id).all()

    def create(self, data: ShiftStationCreate):
        db_obj = ShiftStation(**data.model_dump())
        self.db.add(db_obj)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj

    def delete(self, ss_id: int, division_id: UUID):
        obj = self.db.query(ShiftStation).filter(ShiftStation.id == ss_id, ShiftStation.division_id == division_id).first()
        if obj:
            self.db.delete(obj)
            self.db.commit()
            return True
        return False
