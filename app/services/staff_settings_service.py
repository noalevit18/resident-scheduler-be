import logging

from app.repositories.staff_settings_repository import StaffCertificationRepository, StaffRotationRepository
from app.schemas.schemas import StaffCertificationCreate, StaffRotationCreate, StaffSettingsResponse
from app.context import get_current_user_label
from uuid import UUID

logger = logging.getLogger(__name__)


class StaffCertificationService:
    def __init__(self, repository: StaffCertificationRepository):
        self.repository = repository

    def get_all_certifications(self, unit_id: UUID):
        return self.repository.get_all(unit_id)

    def create_certification(self, data: StaffCertificationCreate):
        return self.repository.create(data)

    def update_certification(self, certification_id: int, unit_id: UUID, data: dict):
        updated = self.repository.update(certification_id, unit_id, data)
        if not updated:
            raise ValueError("Certification not found")
        return updated

    def delete_certification(self, certification_id: int, unit_id: UUID):
        name = self.repository.delete(certification_id, unit_id)
        logger.info("Deleted certification %s (unit_id=%s) by %s", name or certification_id, unit_id, get_current_user_label())
        return True


class StaffRotationService:
    def __init__(self, repository: StaffRotationRepository):
        self.repository = repository

    def get_all_rotations(self, division_id: UUID):
        return self.repository.get_all(division_id)

    def create_rotation(self, data: StaffRotationCreate):
        return self.repository.create(data)

    def update_rotation(self, rotation_id: int, division_id: UUID, data: dict):
        updated = self.repository.update(rotation_id, division_id, data)
        if not updated:
            raise ValueError("Staff rotation not found")
        return updated

    def delete_rotation(self, rotation_id: int, division_id: UUID):
        name = self.repository.delete(rotation_id, division_id)
        logger.info("Deleted staff rotation %s (division_id=%s) by %s", name or rotation_id, division_id, get_current_user_label())
        return True


class StaffSettingsService:
    def __init__(self, certification_service: StaffCertificationService, rotation_service: StaffRotationService):
        self.certification_service = certification_service
        self.rotation_service= rotation_service


    def get_all_settings(self, division_id: UUID, unit_id: UUID):
        certifications_response = self.certification_service.get_all_certifications(unit_id)
        rotations_response = self.rotation_service.get_all_rotations(division_id)
        return StaffSettingsResponse(certifications=certifications_response, rotations=rotations_response)



