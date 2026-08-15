import enum
import re
from datetime import datetime, date
from typing import Optional, List, Any, Dict
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


# ==========================================
# BASE MODEL
# ==========================================

class SnakeCaseModel(BaseModel):
    @model_validator(mode="before")
    @classmethod
    def normalize_keys(cls, data):
        if not isinstance(data, dict):
            return data

        normalized = {}
        for key, value in data.items():
            if isinstance(key, str):
                normalized_key = re.sub(r"(?<!^)(?=[A-Z])", "_", key).lower()
                normalized[normalized_key] = value
            else:
                normalized[key] = value

        return normalized


# ==========================================
# ENUMS
# ==========================================

class RecurrenceType(str, enum.Enum):
    weekly = "weekly"
    every_x_days = "every-x-days"
    every_x_weeks = "every-x-weeks"


class UserRole(str, enum.Enum):
    owner = "owner"
    division_admin = "division_admin"
    unit_admin = "unit_admin"
    user = "user"


class StaffRole(str, enum.Enum):
    ATTENDING = "attending"
    RESIDENT = "resident"
    INTERN = "intern"
    NURSE = "nurse"


# ==========================================
# ACCOUNT SCHEMAS
# ==========================================

class Account(SnakeCaseModel):
    account_name: str = Field(..., min_length=1, max_length=100)
    country: str = Field(..., min_length=1, max_length=100)
    state: Optional[str] = None
    city: Optional[str] = None
    hospital_name: str = Field(..., min_length=1, max_length=200)


class AccountUpdate(SnakeCaseModel):
    account_name: Optional[str] = Field(None, min_length=1, max_length=100)
    country: Optional[str] = Field(None, min_length=1, max_length=100)
    state: Optional[str] = None
    city: Optional[str] = None
    hospital_name: Optional[str] = Field(None, min_length=1, max_length=200)


class AccountResponse(Account):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    updated_at: datetime


# ==========================================
# DIVISION SCHEMAS
# ==========================================

class Division(SnakeCaseModel):
    id: Optional[UUID] = None
    account_id: UUID
    name: str = Field(..., min_length=1, max_length=100)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class DivisionCreate(Division):
    account_id: UUID
    name: str = Field(..., min_length=1, max_length=100)


class DivisionUpdate(SnakeCaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)


class DivisionResponse(Division):
    model_config = ConfigDict(from_attributes=True)


# ==========================================
# UNIT SCHEMAS
# ==========================================

class Unit(SnakeCaseModel):
    id: Optional[UUID] = None
    division_id: UUID
    name: str = Field(..., min_length=1, max_length=100)
    created_at: Optional[datetime] = None


class UnitCreate(Unit):
    division_id: UUID
    name: str = Field(..., min_length=1, max_length=100)


class UnitUpdate(SnakeCaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)


class UnitResponse(Unit):
    model_config = ConfigDict(from_attributes=True)
    division_id: UUID
    created_at: datetime


# ==========================================
# STAFF ROTATION SCHEMAS (Division level)
# ==========================================


class StaffRotation(SnakeCaseModel):
    name: str = Field(..., min_length=1, max_length=100)


class StaffRotationCreate(StaffRotation):
    division_id: UUID


class StaffRotationUpdate(SnakeCaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)


class StaffRotationResponse(StaffRotation):
    model_config = ConfigDict(from_attributes=True)

    id: int
    division_id: UUID
    created_at: datetime


# ==========================================
# CERTIFICATION SCHEMAS
# ==========================================

class Certification(SnakeCaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    color: Optional[str] = None


class CertificationCreate(Certification):
    unit_id: UUID


class CertificationUpdate(SnakeCaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    color: Optional[str] = None


class CertificationResponse(Certification):
    model_config = ConfigDict(from_attributes=True)

    id: int
    unit_id: UUID
    created_at: datetime



# ==========================================
# STAFF SCHEMAS
# ==========================================


class Staff(SnakeCaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    month: Optional[date] = None
    rotation: Optional[int] = None
    certifications_ids: Optional[List[int]] = []


class StaffCreate(Staff):
    unit_id: UUID


class StaffUpdate(SnakeCaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    month: Optional[date] = None
    rotation: Optional[int] = None
    certifications_ids: Optional[List[int]] = None


class StaffResponse(Staff):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    unit_id: UUID
    created_at: datetime
    updated_at: datetime


# ==========================================
# SENIOR SCHEMAS
# ==========================================

class Senior(SnakeCaseModel):
    name: str = Field(..., min_length=1, max_length=100)


class SeniorCreate(Senior):
    unit_id: UUID


class SeniorUpdate(SnakeCaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)


class SeniorResponse(Senior):
    model_config = ConfigDict(from_attributes=True)

    id: int
    unit_id: UUID
    created_at: datetime
    updated_at: datetime


# ==========================================
# SHIFT STATION SCHEMAS
# ==========================================

class ShiftStation(SnakeCaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    created_at: Optional[datetime] = None


class ShiftStationCreate(ShiftStation):
    unit_id: UUID


class ShiftStationUpdate(SnakeCaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)


class ShiftStationResponse(ShiftStation):
    model_config = ConfigDict(from_attributes=True)

    id: int
    unit_id: UUID
    created_at: datetime


# ==========================================
# STATION SCHEMAS
# ==========================================

class Station(SnakeCaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    is_default: bool = False
    certification_id: Optional[int] = None
    bg_color: Optional[str] = None
    border_color: Optional[str] = None
    optional: bool = False
    min_staff_members: Optional[int] = None
    active_days: Optional[List[int]] = []
    recurrence_type: Optional[RecurrenceType] = None
    recurrence_interval: Optional[int] = None
    recurrence_base_date: Optional[date] = None


class StationCreate(Station):
    unit_id: UUID


class StationUpdate(SnakeCaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    is_default: Optional[bool] = None
    certification_id: Optional[int] = None
    bg_color: Optional[str] = None
    border_color: Optional[str] = None
    optional: Optional[bool] = None
    min_staff_members: Optional[int] = None
    active_days: Optional[List[int]] = None
    recurrence_type: Optional[RecurrenceType] = None
    recurrence_interval: Optional[int] = None
    recurrence_base_date: Optional[date] = None


class StationResponse(Station):
    model_config = ConfigDict(from_attributes=True)

    id: int
    unit_id: UUID
    created_at: datetime
    updated_at: datetime


# ==========================================
# SHIFT SCHEMAS
# ==========================================

class Shift(SnakeCaseModel):
    shift_date: date
    shift_station_id: int
    staff_member_id: UUID


class ShiftCreate(Shift):
    unit_id: UUID


class ShiftUpdate(SnakeCaseModel):
    shift_date: Optional[date] = None
    shift_station_id: Optional[int] = None
    staff_member_id: Optional[UUID] = None


class ShiftResponse(Shift):
    model_config = ConfigDict(from_attributes=True)

    id: int
    unit_id: UUID
    created_at: datetime
    updated_at: datetime


# ==========================================
# CONSTRAINT TYPE SCHEMAS
# ==========================================

class ConstraintType(SnakeCaseModel):
    account_id: UUID
    name: str = Field(..., min_length=1, max_length=100)
    color: Optional[str] = None
    created_at: Optional[datetime] = None


class ConstraintTypeCreate(ConstraintType):
    account_id: UUID


class ConstraintTypeUpdate(SnakeCaseModel):
    account_id: Optional[UUID] = None
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    color: Optional[str] = None


class ConstraintTypeResponse(ConstraintType):
    model_config = ConfigDict(from_attributes=True)

    id: int
    account_id: UUID
    created_at: datetime


# ==========================================
# CONSTRAINT SCHEMAS
# ==========================================

class Constraint(SnakeCaseModel):
    constraint_date: date
    constraint_type_id: int
    staff_member_id: UUID


class ConstraintCreate(Constraint):
    unit_id: UUID


class ConstraintUpdate(SnakeCaseModel):
    constraint_date: Optional[date] = None
    constraint_type_id: Optional[int] = None
    staff_member_id: Optional[UUID] = None


class ConstraintResponse(Constraint):
    model_config = ConfigDict(from_attributes=True)

    id: int
    unit_id: UUID
    created_at: datetime
    updated_at: datetime


# ==========================================
# SCHEDULE STAFF MEMBER SCHEMAS
# ==========================================

class ScheduleStaffMember(SnakeCaseModel):
    schedule_date: date
    staff_member_id: UUID
    station_id: int
    is_stand_by: bool = False
    created_at: Optional[datetime] = None


class ScheduleStaffMemberCreate(ScheduleStaffMember):
    unit_id: UUID


class ScheduleStaffMemberUpdate(SnakeCaseModel):
    schedule_date: Optional[date] = None
    staff_member_id: Optional[UUID] = None
    station_id: Optional[int] = None
    is_stand_by: Optional[bool] = None


class ScheduleStaffMemberResponse(ScheduleStaffMember):
    model_config = ConfigDict(from_attributes=True)

    id: int
    unit_id: UUID
    created_at: datetime


# ==========================================
# SCHEDULE SENIOR SCHEMAS
# ==========================================

class ScheduleSenior(SnakeCaseModel):
    schedule_date: date
    senior_id: int
    created_at: Optional[datetime] = None


class ScheduleSeniorCreate(ScheduleSenior):
    unit_id: UUID


class ScheduleSeniorUpdate(SnakeCaseModel):
    schedule_date: Optional[date] = None
    senior_id: Optional[int] = None

class ScheduleSeniorResponse(ScheduleSenior):
    model_config = ConfigDict(from_attributes=True)

    id: int
    unit_id: UUID
    created_at: datetime


# ==========================================
# SCHEDULE VERSION SCHEMAS
# ==========================================

class ScheduleVersion(SnakeCaseModel):
    is_published: bool = False
    schedule: Dict[str, Any] = {}
    update_admin_id: Optional[UUID] = None
    created_at: Optional[datetime] = None


class ScheduleVersionCreate(ScheduleVersion):
    unit_id: UUID


class ScheduleVersionUpdate(SnakeCaseModel):
    is_published: Optional[bool] = None
    schedule: Optional[Dict[str, Any]] = None
    update_admin_id: Optional[UUID] = None


class ScheduleVersionResponse(ScheduleVersion):
    model_config = ConfigDict(from_attributes=True)

    id: int
    unit_id: UUID
    update_admin_id: Optional[UUID] = None
    created_at: datetime


# ==========================================
# USER SCHEMAS
# ==========================================

class User(SnakeCaseModel):
    id: Optional[UUID] = None
    division_id: Optional[UUID] = None
    unit_id: Optional[UUID] = None
    name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    staff_role: Optional[StaffRole] = None
    role: UserRole = UserRole.user
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class UserCreate(User):
    division_id: Optional[UUID] = None
    unit_id: Optional[UUID] = None


class UserUpdate(SnakeCaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    email: Optional[EmailStr] = None
    division_id: Optional[UUID] = None
    unit_id: Optional[UUID] = None
    staff_role: Optional[StaffRole] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None


class UserResponse(User):
    model_config = ConfigDict(from_attributes=True)
    hospital_name: Optional[str] = None
    division_name: Optional[str] = None
    unit_name: Optional[str] = None

