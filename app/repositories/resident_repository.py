from sqlalchemy.orm import Session
from models.models import Resident
from schemas.schemas import ResidentCreate
from uuid import UUID

class ResidentRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_all(self, account_id: UUID):
        return self.db.query(Resident).filter(Resident.account_id == account_id).all()

    def get_by_id(self, resident_id: UUID, account_id: UUID):
        return self.db.query(Resident).filter(Resident.id == resident_id, Resident.account_id == account_id).first()

    def create(self, resident_data: ResidentCreate):
        db_resident = Resident(**resident_data.model_dump())
        self.db.add(db_resident)
        self.db.commit()
        self.db.refresh(db_resident)
        return db_resident


