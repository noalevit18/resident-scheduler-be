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

    def get_existing_ids(self, ids: list[UUID], unit_id: UUID) -> set[UUID]:
        """Batch existence check: which of `ids` belong to this unit.
        One round trip regardless of how many ids are passed."""
        if not ids:
            return set()
        rows = (
            self.db.query(StaffMember.id)
            .filter(StaffMember.id.in_(ids), StaffMember.unit_id == unit_id)
            .all()
        )
        return {r.id for r in rows}

    def get_by_user_id(self, user_id: UUID, unit_id: UUID):
        return self.db.query(StaffMember).filter(StaffMember.user_id == user_id, StaffMember.unit_id == unit_id).first()

    def create(self, staff_data: StaffCreate):
        db_staff = StaffMember(**staff_data.model_dump())
        self.db.add(db_staff)
        self.db.commit()
        return db_staff

    def update(self, member_id: UUID, unit_id: UUID, data: dict):
        obj = self.db.query(StaffMember).filter(StaffMember.id == member_id, StaffMember.unit_id == unit_id).first()
        if obj:
            for key, value in data.items():
                if hasattr(obj, key):
                    setattr(obj, key, value)
            self.db.commit()
            return obj
        return None

    def delete(self, member_id: UUID, unit_id: UUID):
        obj = self.db.query(StaffMember).filter(StaffMember.id == member_id, StaffMember.unit_id == unit_id).first()
        if not obj:
            return None
        name = obj.name
        self.db.delete(obj)
        self.db.commit()
        return name
