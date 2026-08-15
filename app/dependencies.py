from sqlalchemy.orm import Session
from fastapi import Depends
from database import get_db

# Repositories
from repositories.constraint_repository import ConstraintRepository
from repositories.constraint_type_repository import ConstraintTypeRepository
from repositories.metadata_repository import MetadataRepository
from repositories.staff_repository import StaffRepository
from repositories.senior_repository import SeniorRepository
from repositories.shift_repository import ShiftRepository
from repositories.shift_station_repository import ShiftStationRepository
from repositories.station_repository import StationRepository
from repositories.unit_repository import UnitRepository
from repositories.user_repository import UserRepository

# Services
from services.constraint_service import ConstraintService
from services.constraint_type_service import ConstraintTypeService
from services.staff_service import StaffService
from services.senior_service import SeniorService
from services.shift_service import ShiftService
from services.shift_station_service import ShiftStationService
from services.station_service import StationService
from services.unit_service import UnitService
from services.schedule_service import ScheduleService
from services.user_service import UserService
from services.metadata_service import MetadataService

# --- Repository Factories ---
def get_constraint_repository(db: Session = Depends(get_db)): return ConstraintRepository(db)
def get_constraint_type_repository(db: Session = Depends(get_db)): return ConstraintTypeRepository(db)
def get_staff_repository(db: Session = Depends(get_db)): return StaffRepository(db)
def get_senior_repository(db: Session = Depends(get_db)): return SeniorRepository(db)
def get_shift_repository(db: Session = Depends(get_db)): return ShiftRepository(db)
def get_shift_station_repository(db: Session = Depends(get_db)): return ShiftStationRepository(db)
def get_station_repository(db: Session = Depends(get_db)): return StationRepository(db)
def get_unit_repository(db: Session = Depends(get_db)): return UnitRepository(db)
def get_user_repository(db: Session = Depends(get_db)): return UserRepository(db)
def get_metadata_repository(db: Session = Depends(get_db)): return MetadataRepository(db)

# --- Service Factories     ---
def get_constraint_service(repo: ConstraintRepository = Depends(get_constraint_repository)): return ConstraintService(repo)
def get_constraint_type_service(repo: ConstraintTypeRepository = Depends(get_constraint_type_repository)): return ConstraintTypeService(repo)
def get_staff_service(repo: StaffRepository = Depends(get_staff_repository)): return StaffService(repo)
def get_senior_service(repo: SeniorRepository = Depends(get_senior_repository)): return SeniorService(repo)
def get_shift_service(repo: ShiftRepository = Depends(get_shift_repository)): return ShiftService(repo)
def get_shift_station_service(repo: ShiftStationRepository = Depends(get_shift_station_repository)): return ShiftStationService(repo)
def get_station_service(repo: StationRepository = Depends(get_station_repository)): return StationService(repo)
def get_unit_service(repo: UnitRepository = Depends(get_unit_repository)): return UnitService(repo)
def get_schedule_service(): return ScheduleService()
def get_user_service(
    repo: UserRepository = Depends(get_user_repository),
    unit_service: UnitService = Depends(get_unit_service)
):
    return UserService(repo, unit_service)
def get_metadata_service(repo: MetadataRepository = Depends(get_metadata_repository)): return MetadataService(repo)

