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
    user_id: Optional[UUID] = None


class SeniorCreate(Senior):
    unit_id: UUID


class SeniorUpdate(SnakeCaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    user_id: Optional[UUID] = None


class SeniorResponse(Senior):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    unit_id: UUID
    created_at: datetime
    created_by: Optional[UUID] = None
    is_deleted: bool = False
    deleted_by: Optional[UUID] = None


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
    is_secondary: bool = False
    secondary_to: List[int] = Field(default_factory=list)
    certification_id: Optional[int] = None
    bg_color: Optional[str] = None
    border_color: Optional[str] = None
    text_color: Optional[str] = None
    optional: bool = False
    min_staff_members: Optional[int] = None
    min_staff_on_sabbatical: Optional[int] = None
    min_staff_on_half_day: Optional[int] = None
    active_days: Optional[List[int]] = []
    recurrence_type: Optional[RecurrenceType] = None
    recurrence_interval: Optional[int] = None
    recurrence_base_date: Optional[date] = None
    display_order: Optional[int] = None
    enable_stand_by: bool = False
    active_on_sabbatical: bool = False
    prefer_day_before_on_call: bool = False


class StationCreate(Station):
    unit_id: UUID
    on_call_station_ids: List[int] = Field(default_factory=list)
    effective_from: date = Field(default_factory=date.today)


class StationUpdate(SnakeCaseModel):
    """Only the fields sent are applied (an explicit null clears a field —
    e.g. recurrence_type: null makes the station manual). Global fields
    (name, colors, display_order) update the station in place. A change to
    any versioned field requires `effective_from` and creates a station
    version from that date (or replaces an unpinned version with the same
    date). A change to a recurrence field (active_days, recurrence_*) can't
    have an `effective_from` before the current month. Omitting
    `on_call_station_ids` keeps the current mappings."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    is_default: Optional[bool] = None
    is_secondary: Optional[bool] = None
    secondary_to: Optional[List[int]] = None
    certification_id: Optional[int] = None
    bg_color: Optional[str] = None
    border_color: Optional[str] = None
    text_color: Optional[str] = None
    optional: Optional[bool] = None
    min_staff_members: Optional[int] = None
    min_staff_on_sabbatical: Optional[int] = None
    min_staff_on_half_day: Optional[int] = None
    active_days: Optional[List[int]] = None
    recurrence_type: Optional[RecurrenceType] = None
    recurrence_interval: Optional[int] = None
    recurrence_base_date: Optional[date] = None
    display_order: Optional[int] = None
    enable_stand_by: Optional[bool] = None
    active_on_sabbatical: Optional[bool] = None
    prefer_day_before_on_call: Optional[bool] = None
    on_call_station_ids: Optional[List[int]] = None
    effective_from: Optional[date] = None


class StationVersionResponse(Station):
    """A station as of one station version: global fields from the station,
    versioned fields from the version."""
    model_config = ConfigDict(from_attributes=True)

    station_id: int
    version: int
    effective_from: date
    is_retired: bool = False
    # Pinned by the returned schedule version (always false for version 0).
    is_pinned: bool = False
    is_deleted: bool = False
    on_call_station_ids: List[int] = Field(default_factory=list)


class StationResponse(Station):
    """Versioned fields are those of the version in effect today (or the
    earliest version when every version starts later)."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    unit_id: UUID
    version: int
    effective_from: Optional[date] = None
    is_retired: bool = False
    on_call_station_ids: List[int] = Field(default_factory=list)
    # Versions with effective_from > today ("changes scheduled from DD/MM").
    upcoming_versions: List[StationVersionResponse] = Field(default_factory=list)
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None
    deleted_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime


# ==========================================
# SCHEDULE SCHEMAS
# ==========================================

class ScheduleAssignmentEntry(SnakeCaseModel):
    staff_member_id: UUID
    is_stand_by: bool = False


class ScheduleStationEntry(SnakeCaseModel):
    """Either a configured station (`station_id`) or a custom station added
    manually to this schedule only (`custom_name`) — exactly one of the two.
    `display_order` defaults to the configured station's order (custom
    stations: after the last station of the day)."""
    station_id: Optional[int] = None
    custom_name: Optional[str] = Field(None, min_length=1, max_length=100)
    display_order: Optional[int] = None
    assignments: List[ScheduleAssignmentEntry] = Field(default_factory=list)

    @model_validator(mode="after")
    def station_or_custom(self):
        if (self.station_id is None) == (self.custom_name is None):
            raise ValueError("Exactly one of station_id or custom_name must be set")
        return self


class ScheduleDayEntry(SnakeCaseModel):
    date: date
    senior_id: Optional[UUID] = None
    stations: List[ScheduleStationEntry] = Field(default_factory=list)


class MonthlyScheduleUpdate(SnakeCaseModel):
    """`days` is the complete desired state of the month — any date missing
    from it has no stations/assignments/senior in the new version."""
    days: List[ScheduleDayEntry] = Field(default_factory=list)
    is_published: bool = False
    # The version the client edited; a save is rejected with 409
    # schedule_version_conflict when it's no longer the latest. Omit to
    # overwrite regardless.
    base_version: Optional[int] = None


class ScheduleStationResponse(ScheduleStationEntry):
    id: int
    display_order: int


class ScheduleDayResponse(ScheduleDayEntry):
    stations: List[ScheduleStationResponse] = Field(default_factory=list)


class ScheduleHistoryResponse(SnakeCaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    version: int
    is_published: bool = False
    published_at: Optional[datetime] = None
    published_by: Optional[UUID] = None
    constraints_version: Optional[int] = None
    on_call_version: Optional[int] = None
    created_at: datetime
    created_by: Optional[UUID] = None


class MonthlyScheduleResponse(SnakeCaseModel):
    """`stations`: per station, every version in effect on some day of the
    month (the one in effect on the 1st plus those with effective_from inside
    the month), plus every version the returned schedule version pins
    (`is_pinned`)."""
    days: List[ScheduleDayResponse]
    stations: List[StationVersionResponse] = Field(default_factory=list)
    version: int
    is_published: bool = False
    published_at: Optional[datetime] = None
    published_by: Optional[UUID] = None
    constraints_version: Optional[int] = None
    on_call_version: Optional[int] = None
    created_at: Optional[datetime] = None


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


# ==========================================
# CONSTRAINTS SUBMISSION SCHEMAS (member-facing)
# ==========================================

class ConstraintSubmissionEntry(SnakeCaseModel):
    date: Optional[dt.date] = None  # None => the month's general-comment row
    type_id: Optional[int] = None
    comment: Optional[str] = Field(None, max_length=1024)

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

