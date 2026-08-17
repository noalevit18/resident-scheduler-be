from app.repositories.unit_repository import UnitRepository
from uuid import UUID

class UnitService:
    def __init__(self, repository: UnitRepository):
        self.repository = repository

    def get_unit_details(self, unit_id: UUID):
        unit = self.repository.get_by_id(unit_id)
        if not unit:
            return None
        
        unit_name = unit.name
        division_name = unit.division.name if unit.division else None
        hospital_name = unit.division.account.hospital_name if unit.division and unit.division.account else None
        
        return {
            "unit_id": unit.id,
            "unit_name": unit_name,
            "division_id": unit.division_id,
            "division_name": division_name,
            "hospital_name": hospital_name
        }
