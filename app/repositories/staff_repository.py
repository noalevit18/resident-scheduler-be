from sqlalchemy.orm import Session
from app.models.models import StaffMember
from app.schemas.schemas import StaffCreate
from uuid import UUID

class StaffRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_all(self, unit_id: UUID):
        return self.db.query(StaffMember).filter(StaffMember.unit_id == unit_id).all()

    def get_by_id(self, member_id: UUID, unit_id: UUID):
        return self.db.query(StaffMember).filter(StaffMember.id == member_id, StaffMember.unit_id == unit_id).first()

    def create(self, staff_data: StaffCreate):
        db_staff = StaffMember(**staff_data.model_dump())
        self.db.add(db_staff)
        self.db.commit()
        self.db.refresh(db_staff)
        return db_staff

    def delete(self, member_id: UUID, unit_id: UUID):
        obj = self.db.query(StaffMember).filter(StaffMember.id == member_id, StaffMember.unit_id == unit_id).first()
        if obj:
            self.db.delete(obj)
            self.db.commit()
            return True
        return False


