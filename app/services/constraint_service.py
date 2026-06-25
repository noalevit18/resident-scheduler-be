from repositories.constraint_repository import ConstraintRepository
from schemas.schemas import ConstraintCreate
from uuid import UUID

class ConstraintService:
    def __init__(self, repository: ConstraintRepository):
        self.repository = repository

    def get_all_constraints(self, account_id: UUID):
        return self.repository.get_all(account_id)

    def create_constraint(self, data: ConstraintCreate):
        return self.repository.create(data)
