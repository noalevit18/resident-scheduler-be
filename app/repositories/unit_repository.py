from sqlalchemy.orm import Session, joinedload
from app.models.models import Unit, Division
from uuid import UUID

class UnitRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, unit_id: UUID):
        return (
            self.db.query(Unit)
            .options(joinedload(Unit.division).joinedload(Division.account))
            .filter(Unit.id == unit_id)
            .first()
        )
