from app.repositories.division_repository import DivisionRepository
from uuid import UUID

class DivisionService:
    def __init__(self, repository: DivisionRepository):
        self.repository = repository

    def get_division_details(self, division_id: UUID):
        division = self.repository.get_by_id(division_id)
        if not division:
            return None

        hospital_name = division.account.hospital_name if division.account else None

        return {
            "division_id": division.id,
            "division_name": division.name,
            "hospital_name": hospital_name,
        }
