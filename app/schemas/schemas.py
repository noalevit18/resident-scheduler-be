import enum
import re
import datetime as dt
from datetime import datetime, date
from typing import Optional, List, Any, Dict
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


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
    CLERK = "clerk"


class SpecialDateType(str, enum.Enum):
    partial_day = "partial_day"
    sabbatical = "sabbatical"
    regular = "regular"


class SubmissionFeature(str, enum.Enum):
    constraints = "constraints"
    on_call = "on_call"


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
    active: bool = False
    created_at: Optional[datetime] = None


class UnitCreate(Unit):
    division_id: UUID
    name: str = Field(..., min_length=1, max_length=100)


class UnitUpdate(SnakeCaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    active: Optional[bool] = None


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

class StaffCertification(SnakeCaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    color: Optional[str] = None


class StaffCertificationCreate(StaffCertification):
    unit_id: UUID


class StaffCertificationUpdate(SnakeCaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    color: Optional[str] = None


class StaffCertificationResponse(StaffCertification):
    model_config = ConfigDict(from_attributes=True)

    id: int
    unit_id: UUID
    created_at: datetime


class StaffSettingsResponse(SnakeCaseModel):
    certifications: list[StaffCertificationResponse]
    rotations: list[StaffRotationResponse]

# ==========================================
# STAFF SCHEMAS
# ==========================================


class Staff(SnakeCaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    user_id: Optional[UUID] = None
    active_since: Optional[str] = None
    archived_since: Optional[str] = None
    month_rotation: Optional[Dict[str, List[int]]] = {}
    month_certifications: Optional[Dict[str, List[int]]] = {}


class StaffCreate(Staff):
    unit_id: UUID


class StaffUpdate(SnakeCaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    user_id: Optional[UUID] = None
    active_since: Optional[str] = None
    archived_since: Optional[str] = None
    month_rotation: Optional[Dict[str, List[int]]] = None
    month_certifications: Optional[Dict[str, List[int]]] = None


class StaffResponse(Staff):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    unit_id: UUID
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


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
# ON-CALL STATION SCHEMAS
# ==========================================

class OnCallStationCreate(SnakeCaseModel):
    name: str = Field(..., min_length=1, max_length=64)


class OnCallStationsCreate(SnakeCaseModel):
    entries: List[OnCallStationCreate]


class OnCallStationUpdateEntry(SnakeCaseModel):
    id: int
    name: Optional[str] = Field(None, min_length=1, max_length=64)


class OnCallStationsUpdate(SnakeCaseModel):
    entries: List[OnCallStationUpdateEntry] = Field(default_factory=list)
    deleted: List[int] = Field(default_factory=list)


class OnCallStationResponse(SnakeCaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    division_id: UUID
    name: str
    created_at: datetime
    created_by: Optional[UUID] = None
    is_deleted: bool = False


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
# ON-CALL SHIFT SCHEMAS
# ==========================================

class OnCallShiftEntry(SnakeCaseModel):
    date: date
    station_assignments: Dict[UUID, int] = Field(default_factory=dict)


class MonthlyOnCallShiftsUpdate(SnakeCaseModel):
    """`entries` is the complete set of dates the month should have — any
    previously-saved date missing from it is treated as deleted (no
    carry-forward); there's no separate tombstone/deleted list."""
    entries: List[OnCallShiftEntry] = Field(default_factory=list)
    is_published: bool = False


class OnCallShiftResponse(SnakeCaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    division_id: UUID
    unit_id: UUID
    date: date
    station_assignments: Dict[UUID, int]
    submitted_assignments: Dict[UUID, int] = Field(default_factory=dict)
    version: int
    created_at: datetime
    created_by: Optional[UUID] = None


class MonthlyOnCallShiftsResponse(SnakeCaseModel):
    shifts: List[OnCallShiftResponse]
    version: int
    is_published: bool = False
    published_at: Optional[date] = None
    published_by: Optional[UUID] = None


class OnCallShiftHistoryResponse(SnakeCaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    version: int
    is_published: bool = False
    published_at: Optional[date] = None
    published_by: Optional[UUID] = None
    created_at: datetime
    created_by: Optional[UUID] = None


# ==========================================
# CONSTRAINT TYPE SCHEMAS
# ==========================================

class ConstraintTypeColor(SnakeCaseModel):
    bg: str
    text: str
    border: str
    is_custom: Optional[bool] = False


class ConstraintType(SnakeCaseModel):
    account_id: UUID
    name: str = Field(..., min_length=1, max_length=100)
    color: ConstraintTypeColor
    is_hard: bool = False
    created_at: Optional[datetime] = None


class ConstraintTypeCreate(ConstraintType):
    account_id: UUID


class ConstraintTypeUpdate(SnakeCaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    color: Optional[ConstraintTypeColor] = None
    is_hard: Optional[bool] = None


class ConstraintTypeResponse(ConstraintType):
    model_config = ConfigDict(from_attributes=True)

    id: int
    account_id: UUID
    color: Optional[ConstraintTypeColor] = None
    created_at: datetime
    updated_at: datetime
    is_deleted: bool = False


# ==========================================
# SPECIAL DATE (HOLIDAY) SCHEMAS
# ==========================================

class SpecialDateBase(SnakeCaseModel):
    date: date
    label: str = Field(..., min_length=1, max_length=200)
    type: SpecialDateType


class SpecialDateResponse(SpecialDateBase):
    model_config = ConfigDict(from_attributes=True)

    account_id: UUID
    created_at: datetime
    created_by: Optional[UUID] = None
    updated_at: datetime
    updated_by: Optional[UUID] = None


class SpecialDateBulkEntry(SpecialDateBase):
    pass


class SpecialDatesBulkUpdate(SnakeCaseModel):
    upserts: List[SpecialDateBulkEntry] = []
    delete_dates: List[date] = []


# ==========================================
# CONSTRAINT SCHEMAS
# ==========================================

class ConstraintEntry(SnakeCaseModel):
    type_id: int
    date: date
    staff_member_ids: List[UUID] = Field(default_factory=list)


class MonthlyConstraintsUpdate(SnakeCaseModel):
    entries: List[ConstraintEntry]


class ConstraintResponse(SnakeCaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    unit_id: UUID
    type_id: int
    date: date
    staff_member_ids: List[UUID]
    submitted_staff_member_ids: List[UUID] = Field(default_factory=list)
    version: int
    created_at: datetime
    created_by: Optional[UUID] = None


class ConstraintUserComment(SnakeCaseModel):
    date: Optional[dt.date] = None  # None => the month's general comment
    comment: str


class ConstraintUserComments(SnakeCaseModel):
    staff_member_id: UUID
    comments: List[ConstraintUserComment]


class MonthlyConstraintsResponse(SnakeCaseModel):
    constraints: List[ConstraintResponse]
    user_comments: List[ConstraintUserComments]


class PullSubmissionsResponse(SnakeCaseModel):
    constraints: List[ConstraintResponse]
    user_comments: List[ConstraintUserComments]


class ConstraintHistoryResponse(SnakeCaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    version: int
    created_at: datetime
    created_by: Optional[UUID] = None


# ==========================================
# SUBMISSION WINDOW SCHEMAS (shared: constraints + on-call)
# ==========================================

class SubmissionWindowUpdate(SnakeCaseModel):
    unit_id: UUID
    month: str
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None


class PullInformationEntry(SnakeCaseModel):
    pulled_at: Optional[datetime] = None
    pulled_by: Optional[UUID] = None

    @field_validator("pulled_at", mode="before")
    @classmethod
    def _parse_pulled_at(cls, value):
        # Postgres renders a timestamptz's UTC offset as "+00" (no minutes)
        # when a value written straight from SQL (e.g. jsonb_build_object)
        # lands in this jsonb column — stricter than pydantic-core's
        # RFC3339 parser accepts, though datetime.fromisoformat handles it.
        if isinstance(value, str):
            return datetime.fromisoformat(value)
        return value


class SubmissionWindowResponse(SnakeCaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    unit_id: UUID
    month: str
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    updated_by: Optional[UUID] = None
    pull_information: Dict[SubmissionFeature, PullInformationEntry] = {}
    created_at: datetime
    updated_at: datetime


# ==========================================
# STAFF MEMBER SUBMISSION SCHEMAS (member-facing, shared: constraints + on-call)
# ==========================================

class StaffMemberSubmissionEntry(SnakeCaseModel):
    date: Optional[dt.date] = None  # None => the month's general-comment row
    constraint_type_id: Optional[int] = None
    on_call_station_id: Optional[int] = None
    comment: Optional[str] = Field(None, max_length=1024)


class MemberMonthlySubmissionUpdate(SnakeCaseModel):
    entries: List[StaffMemberSubmissionEntry]


class StaffSubmissionStatusResponse(SnakeCaseModel):
    staff_member_id: UUID
    name: str
    submitted: bool


class StaffMemberSubmissionResponse(SnakeCaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    unit_id: UUID
    staff_member_id: UUID
    month: str
    date: Optional[dt.date] = None
    constraint_type_id: Optional[int] = None
    on_call_station_id: Optional[int] = None
    comment: Optional[str] = None
    submitted_empty: bool = False
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
    firebase_uid: Optional[str] = None
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
    account_id: Optional[UUID] = None
    # None when not applicable (no unit, or no staff_members row for this
    # user in it — e.g. a pure admin account); True/False otherwise.
    constraints_submitted_this_month: Optional[bool] = None

