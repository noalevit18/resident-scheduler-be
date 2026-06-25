from sqlalchemy.orm import Session
from fastapi import Depends
from database import get_db

# Repositories
from repositories.constraint_repository import ConstraintRepository
from repositories.constraint_type_repository import ConstraintTypeRepository
from repositories.resident_repository import ResidentRepository
from repositories.senior_repository import SeniorRepository
from repositories.shift_repository import ShiftRepository
from repositories.shift_station_repository import ShiftStationRepository
from repositories.station_repository import StationRepository
from repositories.account_admin_repository import AccountAdminRepository

# Services
from services.constraint_service import ConstraintService
from services.constraint_type_service import ConstraintTypeService
from services.resident_service import ResidentService
from services.senior_service import SeniorService
from services.shift_service import ShiftService
from services.shift_station_service import ShiftStationService
from services.station_service import StationService
from services.schedule_service import ScheduleService
from services.account_admin_service import AccountAdminService

# --- Repository Factories ---
def get_constraint_repository(db: Session = Depends(get_db)): return ConstraintRepository(db)
def get_constraint_type_repository(db: Session = Depends(get_db)): return ConstraintTypeRepository(db)
def get_resident_repository(db: Session = Depends(get_db)): return ResidentRepository(db)
def get_senior_repository(db: Session = Depends(get_db)): return SeniorRepository(db)
def get_shift_repository(db: Session = Depends(get_db)): return ShiftRepository(db)
def get_shift_station_repository(db: Session = Depends(get_db)): return ShiftStationRepository(db)
def get_station_repository(db: Session = Depends(get_db)): return StationRepository(db)
def get_account_admin_repository(db: Session = Depends(get_db)): return AccountAdminRepository(db)

# --- Service Factories ---
def get_constraint_service(repo: ConstraintRepository = Depends(get_constraint_repository)): return ConstraintService(repo)
def get_constraint_type_service(repo: ConstraintTypeRepository = Depends(get_constraint_type_repository)): return ConstraintTypeService(repo)
def get_resident_service(repo: ResidentRepository = Depends(get_resident_repository)): return ResidentService(repo)
def get_senior_service(repo: SeniorRepository = Depends(get_senior_repository)): return SeniorService(repo)
def get_shift_service(repo: ShiftRepository = Depends(get_shift_repository)): return ShiftService(repo)
def get_shift_station_service(repo: ShiftStationRepository = Depends(get_shift_station_repository)): return ShiftStationService(repo)
def get_station_service(repo: StationRepository = Depends(get_station_repository)): return StationService(repo)
def get_schedule_service(): return ScheduleService()
def get_account_admin_service(repo: AccountAdminRepository = Depends(get_account_admin_repository)): return AccountAdminService(repo)
