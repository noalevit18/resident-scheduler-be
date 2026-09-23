from sqlalchemy.orm import Session
from fastapi import Depends
from app.database import get_db

# Repositories
from app.repositories.constraint_repository import ConstraintRepository
from app.repositories.constraint_type_repository import ConstraintTypeRepository
from app.repositories.staff_member_submission_metadata_repository import StaffMemberSubmissionMetadataRepository
from app.repositories.staff_member_submission_repository import StaffMemberSubmissionRepository
from app.repositories.metadata_repository import MetadataRepository
from app.repositories.staff_repository import StaffRepository
from app.repositories.senior_repository import SeniorRepository
from app.repositories.on_call_station_repository import OnCallStationRepository
from app.repositories.on_call_shift_repository import OnCallShiftRepository
from app.repositories.station_repository import StationRepository
from app.repositories.unit_repository import UnitRepository
from app.repositories.division_repository import DivisionRepository
from app.repositories.user_repository import UserRepository
from app.repositories.staff_settings_repository import StaffCertificationRepository, StaffRotationRepository
from app.repositories.special_date_repository import SpecialDateRepository

# Services
from app.services.constraint_service import ConstraintService
from app.services.constraint_type_service import ConstraintTypeService
from app.services.staff_member_submission_metadata_service import StaffMemberSubmissionMetadataService
from app.services.staff_member_submission_service import StaffMemberSubmissionService
from app.services.authorization_service import AuthorizationService
from app.services.staff_service import StaffService
from app.services.senior_service import SeniorService
from app.services.on_call_station_service import OnCallStationService
from app.services.on_call_shift_service import OnCallShiftService
from app.services.station_service import StationService
from app.services.unit_service import UnitService
from app.services.division_service import DivisionService
from app.services.schedule_service import ScheduleService
from app.services.user_service import UserService
from app.services.metadata_service import MetadataService
from app.services.staff_settings_service import StaffCertificationService, StaffRotationService, StaffSettingsService
from app.services.special_date_service import SpecialDateService

# --- Repository Factories ---
def get_constraint_repository(db: Session = Depends(get_db)): return ConstraintRepository(db)
def get_constraint_type_repository(db: Session = Depends(get_db)): return ConstraintTypeRepository(db)
def get_staff_member_submission_metadata_repository(db: Session = Depends(get_db)): return StaffMemberSubmissionMetadataRepository(db)
def get_staff_member_submission_repository(db: Session = Depends(get_db)): return StaffMemberSubmissionRepository(db)
def get_staff_repository(db: Session = Depends(get_db)): return StaffRepository(db)
def get_senior_repository(db: Session = Depends(get_db)): return SeniorRepository(db)
def get_on_call_station_repository(db: Session = Depends(get_db)): return OnCallStationRepository(db)
def get_on_call_shift_repository(db: Session = Depends(get_db)): return OnCallShiftRepository(db)
def get_station_repository(db: Session = Depends(get_db)): return StationRepository(db)
def get_unit_repository(db: Session = Depends(get_db)): return UnitRepository(db)
def get_division_repository(db: Session = Depends(get_db)): return DivisionRepository(db)
def get_user_repository(db: Session = Depends(get_db)): return UserRepository(db)
def get_metadata_repository(db: Session = Depends(get_db)): return MetadataRepository(db)
def get_certification_repository(db: Session = Depends(get_db)): return StaffCertificationRepository(db)
def get_staff_rotation_repository(db: Session = Depends(get_db)): return StaffRotationRepository(db)
def get_special_date_repository(db: Session = Depends(get_db)): return SpecialDateRepository(db)

# --- Service Factories     ---
def get_constraint_type_service(repo: ConstraintTypeRepository = Depends(get_constraint_type_repository)): return ConstraintTypeService(repo)
def get_unit_service(repo: UnitRepository = Depends(get_unit_repository)): return UnitService(repo)
def get_division_service(repo: DivisionRepository = Depends(get_division_repository)): return DivisionService(repo)
def get_user_service(
    repo: UserRepository = Depends(get_user_repository),
    unit_service: UnitService = Depends(get_unit_service),
    division_service: DivisionService = Depends(get_division_service)
):
    return UserService(repo, unit_service, division_service)
def get_staff_service(
    repo: StaffRepository = Depends(get_staff_repository),
    user_service: UserService = Depends(get_user_service),
): return StaffService(repo, user_service)
def get_authorization_service(
    user_service: UserService = Depends(get_user_service),
    unit_service: UnitService = Depends(get_unit_service),
    division_service: DivisionService = Depends(get_division_service),
): return AuthorizationService(user_service, unit_service, division_service)
def get_staff_member_submission_metadata_service(
    repo: StaffMemberSubmissionMetadataRepository = Depends(get_staff_member_submission_metadata_repository),
    user_service: UserService = Depends(get_user_service),
): return StaffMemberSubmissionMetadataService(repo, user_service)
def get_constraint_service(
    repo: ConstraintRepository = Depends(get_constraint_repository),
    submission_repo: StaffMemberSubmissionRepository = Depends(get_staff_member_submission_repository),
    submission_metadata_service: StaffMemberSubmissionMetadataService = Depends(get_staff_member_submission_metadata_service),
    constraint_type_service: ConstraintTypeService = Depends(get_constraint_type_service),
    staff_service: StaffService = Depends(get_staff_service),
): return ConstraintService(repo, submission_repo, submission_metadata_service, constraint_type_service, staff_service)
def get_staff_member_submission_service(
    repo: StaffMemberSubmissionRepository = Depends(get_staff_member_submission_repository),
    submission_metadata_service: StaffMemberSubmissionMetadataService = Depends(get_staff_member_submission_metadata_service),
    staff_service: StaffService = Depends(get_staff_service),
): return StaffMemberSubmissionService(repo, submission_metadata_service, staff_service)
def get_senior_service(repo: SeniorRepository = Depends(get_senior_repository)): return SeniorService(repo)
def get_on_call_station_service(repo: OnCallStationRepository = Depends(get_on_call_station_repository)): return OnCallStationService(repo)
def get_on_call_shift_service(
    repo: OnCallShiftRepository = Depends(get_on_call_shift_repository),
    on_call_station_service: OnCallStationService = Depends(get_on_call_station_service),
    staff_service: StaffService = Depends(get_staff_service),
    submission_repo: StaffMemberSubmissionRepository = Depends(get_staff_member_submission_repository),
    submission_metadata_service: StaffMemberSubmissionMetadataService = Depends(get_staff_member_submission_metadata_service),
): return OnCallShiftService(repo, on_call_station_service, staff_service, submission_repo, submission_metadata_service)
def get_station_service(repo: StationRepository = Depends(get_station_repository)): return StationService(repo)
def get_schedule_service(): return ScheduleService()
def get_metadata_service(repo: MetadataRepository = Depends(get_metadata_repository)): return MetadataService(repo)
def get_certification_service(repo: StaffCertificationRepository = Depends(get_certification_repository)): return StaffCertificationService(repo)
def get_staff_rotation_service(repo: StaffRotationRepository = Depends(get_staff_rotation_repository)): return StaffRotationService(repo)
def get_staff_settings_service(certification_service: StaffCertificationService = Depends(get_certification_service),
                               rotation_service: StaffRotationService = Depends(get_staff_rotation_service)): return StaffSettingsService(certification_service, rotation_service)
def get_special_date_service(repo: SpecialDateRepository = Depends(get_special_date_repository)): return SpecialDateService(repo)
