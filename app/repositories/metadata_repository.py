from uuid import UUID

from app.schemas.schemas import UnitResponse
from app.models.models import Unit as UnitModel



class MetadataRepository:
    def __init__(self, session):
        self.session = session

    def get_units(self, division_id: UUID):
        units = self.session.query(UnitModel).filter(UnitModel.division_id == division_id).all()
        return [UnitResponse.model_validate(unit) for unit in units] if units else None