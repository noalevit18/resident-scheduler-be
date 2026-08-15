from sqlalchemy.orm import Session
from models.models import Station
from schemas.schemas import StationCreate
from uuid import UUID

class StationRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_all(self, unit_id: UUID):
        return self.db.query(Station).filter(Station.unit_id == unit_id).all()

    def create(self, data: StationCreate):
        db_obj = Station(**data.model_dump())
        self.db.add(db_obj)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj

    def delete(self, station_id: int, unit_id: UUID):
        obj = self.db.query(Station).filter(Station.id == station_id, Station.unit_id == unit_id).first()
        if obj:
            self.db.delete(obj)
            self.db.commit()
            return True
        return False