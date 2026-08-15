from repositories.constraint_type_repository import ConstraintTypeRepository
from schemas.schemas import ConstraintTypeCreate
from uuid import UUID

class ConstraintTypeService:
    def __init__(self, repository: ConstraintTypeRepository):
        self.repository = repository

    def get_all(self, division_id: UUID):
        return self.repository.get_all(division_id)

    def create(self, data: ConstraintTypeCreate):
        return self.repository.create(data)

    def delete(self, c_id: int, division_id: UUID):
        if not self.repository.delete(c_id, division_id):
            raise ValueError("Constraint type not found")
        return True
