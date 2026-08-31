from app.repositories.metadata_repository import MetadataRepository

class MetadataService:
    def __init__(self, repository: MetadataRepository):
        self.repository = repository

    def get_division_metadata(self, division_id: str):
        units = self.repository.get_units(division_id=division_id)

        return {
            "units": {str(u.id): {"name": u.name, "active": u.active} for u in units},
        }
