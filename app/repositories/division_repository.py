from sqlalchemy.orm import Session, joinedload
from app.models.models import Division
from uuid import UUID

class DivisionRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, division_id: UUID):
        return (
            self.db.query(Division)
            .options(joinedload(Division.account))
            .filter(Division.id == division_id)
            .first()
        )
