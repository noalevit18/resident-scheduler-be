from app.repositories.constraint_repository import ConstraintRepository
from app.schemas.schemas import ConstraintCreate
from uuid import UUID

class ConstraintService:
    def __init__(self, repository: ConstraintRepository):
        self.repository = repository

    def get_all_constraints(self, unit_id: UUID):
        return self.repository.get_all(unit_id)

    def create_constraint(self, data: ConstraintCreate):
        return self.repository.create(data)
