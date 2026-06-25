from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime, date
from typing import List, Optional
from enum import Enum

class RecurrenceType(str, Enum):
    weekly = "weekly"
    every_x_days = "every-x-days"
    every_x_weeks = "every-x-weeks"

class AdminRole(str, Enum):
    owner = "owner"
    admin = "admin"

class AccountBase(BaseModel):
    slug: str
    country: str
    state: Optional[str] = None
    city: Optional[str] = None
    hospital_name: str

class AccountCreate(AccountBase):
    pass

class Account(AccountBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

class ResidentRotationBase(BaseModel):
    account_id: UUID
    name: str

class ResidentRotationCreate(ResidentRotationBase):
    pass

class ResidentRotation(ResidentRotationBase):
    id: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

class CertificationBase(BaseModel):
    account_id: UUID
    name: str

class CertificationCreate(CertificationBase):
    pass

class Certification(CertificationBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

class ResidentBase(BaseModel):
    account_id: UUID
    name: str
    rotation: Optional[int] = None
    certifications_ids: Optional[List[int]] = None

class ResidentCreate(ResidentBase):
    pass

class Resident(ResidentBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

class SeniorBase(BaseModel):
    account_id: UUID
    name: str

class SeniorCreate(SeniorBase):
    pass

class Senior(SeniorBase):
    id: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

class ShiftStationBase(BaseModel):
    account_id: UUID
    name: str

class ShiftStationCreate(ShiftStationBase):
    pass

class ShiftStation(ShiftStationBase):
    id: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

class StationBase(BaseModel):
    account_id: UUID
    name: str
    is_default: bool = False
    certification_id: Optional[int] = None
    bg_color: Optional[str] = None
    border_color: Optional[str] = None
    optional: bool = False
    min_residents: Optional[int] = None
    active_days: Optional[List[int]] = None
    recurrence_type: Optional[RecurrenceType] = None
    recurrence_interval: Optional[int] = None
    recurrence_base_date: Optional[date] = None

class StationCreate(StationBase):
    pass

class Station(StationBase):
    id: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

class ShiftBase(BaseModel):
    account_id: UUID
    row_date: date
    shift_station_id: int
    resident_id: UUID

class ShiftCreate(ShiftBase):
    pass

class Shift(ShiftBase):
    id: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

class ConstraintTypeBase(BaseModel):
    account_id: UUID
    name: str
    color: Optional[str] = None

class ConstraintTypeCreate(ConstraintTypeBase):
    pass

class ConstraintType(ConstraintTypeBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

class ConstraintBase(BaseModel):
    account_id: UUID
    row_date: date
    constraint_type_id: int
    resident_id: UUID

class ConstraintCreate(ConstraintBase):
    pass

class Constraint(ConstraintBase):
    id: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

class ScheduleResidentBase(BaseModel):
    account_id: UUID
    row_date: date
    resident_id: UUID
    station_id: int
    is_stand_by: bool = False
    is_draft: bool = True

class ScheduleResidentCreate(ScheduleResidentBase):
    pass

class ScheduleResident(ScheduleResidentBase):
    id: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

class ScheduleSeniorBase(BaseModel):
    account_id: UUID
    row_date: date
    senior_id: int
    is_draft: bool = True

class ScheduleSeniorCreate(ScheduleSeniorBase):
    pass

class ScheduleSenior(ScheduleSeniorBase):
    id: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

class ScheduleVersionBase(BaseModel):
    account_id: UUID
    is_published: bool = False
    schedule: dict = {}

class ScheduleVersionCreate(ScheduleVersionBase):
    pass

class ScheduleVersion(ScheduleVersionBase):
    id: int
    created_at: datetime
    update_admin: str
    model_config = ConfigDict(from_attributes=True)

class AccountAdmin(BaseModel):
    account_id: UUID
    email: str
    role: AdminRole = AdminRole.admin

class AccountAdminCreate(AccountAdmin):
    pass

class AccountAdminResponse(AccountAdmin):
    id: UUID
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)