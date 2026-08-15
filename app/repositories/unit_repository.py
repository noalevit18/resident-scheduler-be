from sqlalchemy.orm import Session
from models.models import Unit
from uuid import UUID

class UnitRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, unit_id: UUID):
        return self.db.query(Unit).filter(Unit.id == unit_id).first()
