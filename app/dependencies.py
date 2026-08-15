from sqlalchemy.orm import Session
from fastapi import Depends
from app.database import get_db

# Repositories
from app.repositories.constraint_repository import ConstraintRepository
from app.repositories.constraint_type_repository import ConstraintTypeRepository
from app.repositories.metadata_repository import MetadataRepository
from app.repositories.staff_repository import StaffRepository
from app.repositories.senior_repository import SeniorRepository
from app.repositories.shift_repository import ShiftRepository
from app.repositories.shift_station_repository import ShiftStationRepository
from app.repositories.station_repository import StationRepository
from app.repositories.unit_repository import UnitRepository
from app.repositories.user_repository import UserRepository

# Services
from app.services.constraint_service import ConstraintService
from app.services.constraint_type_service import ConstraintTypeService
from app.services.staff_service import StaffService
from app.services.senior_service import SeniorService
from app.services.shift_service import ShiftService
from app.services.shift_station_service import ShiftStationService
from app.services.station_service import StationService
from app.services.unit_service import UnitService
from app.services.schedule_service import ScheduleService
from app.services.user_service import UserService
from app.services.metadata_service import MetadataService

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

