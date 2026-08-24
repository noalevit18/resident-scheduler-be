from sqlalchemy.orm import Session
from app.models.models import StaffCertification, StaffRotation
from app.schemas.schemas import StaffCertificationCreate, StaffRotationCreate
from uuid import UUID


class StaffCertificationRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_all(self, unit_id: UUID):
        return self.db.query(StaffCertification).filter(StaffCertification.unit_id == unit_id).all()

    def create(self, data: StaffCertificationCreate):
        db_obj = StaffCertification(**data.model_dump())
        self.db.add(db_obj)
        self.db.commit()
        return db_obj

    def update(self, certification_id: int, unit_id: UUID, data: dict):
        obj = self.db.query(StaffCertification).filter(StaffCertification.id == certification_id, StaffCertification.unit_id == unit_id).first()
        if obj:
            for key, value in data.items():
                if hasattr(obj, key):
                    setattr(obj, key, value)
            self.db.commit()
            return obj
        return None

    def delete(self, certification_id: int, unit_id: UUID):
        obj = self.db.query(StaffCertification).filter(StaffCertification.id == certification_id, StaffCertification.unit_id == unit_id).first()
        if not obj:
            return None
        name = obj.name
        self.db.delete(obj)
        self.db.commit()
        return name


class StaffRotationRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_all(self, division_id: UUID):
        return self.db.query(StaffRotation).filter(StaffRotation.division_id == division_id).all()

    def create(self, data: StaffRotationCreate):
        db_obj = StaffRotation(**data.model_dump())
        self.db.add(db_obj)
        self.db.commit()
        return db_obj

    def update(self, rotation_id: int, division_id: UUID, data: dict):
        obj = self.db.query(StaffRotation).filter(StaffRotation.id == rotation_id, StaffRotation.division_id == division_id).first()
        if obj:
            for key, value in data.items():
                if hasattr(obj, key):
                    setattr(obj, key, value)
            self.db.commit()
            return obj
        return None

    def delete(self, rotation_id: int, division_id: UUID):
        obj = self.db.query(StaffRotation).filter(StaffRotation.id == rotation_id, StaffRotation.division_id == division_id).first()
        if not obj:
            return None
        name = obj.name
        self.db.delete(obj)
        self.db.commit()
        return name
