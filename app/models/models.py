import enum
import uuid
from datetime import date, datetime
from typing import List, Optional

from sqlalchemy import (
    Index,
    Integer,
    Text,
    Boolean,
    DateTime,
    ForeignKey,
    Date,
    ARRAY,
    UniqueConstraint,
    Enum as SQLEnum,
    text,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class RecurrenceType(str, enum.Enum):
    WEEKLY = "weekly"
    EVERY_X_DAYS = "every-x-days"
    EVERY_X_WEEKS = "every-x-weeks"


class UserRole(str, enum.Enum):
    OWNER = "owner"
    DIVISION_ADMIN = "division_admin"
    UNIT_ADMIN = "unit_admin"
    USER = "user"


class StaffRole(str, enum.Enum):
    ATTENDING = "attending"
    RESIDENT = "resident"
    INTERN = "intern"
    NURSE = "nurse"
    CLERK = "clerk"


class SpecialDateType(str, enum.Enum):
    PARTIAL_DAY = "partial_day"
    SABBATICAL = "sabbatical"
    REGULAR = "regular"


class Account(Base):
    __tablename__ = "accounts"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    account_name: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    country: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[Optional[str]] = mapped_column(Text)
    city: Mapped[Optional[str]] = mapped_column(Text)
    hospital_name: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    divisions: Mapped[List["Division"]] = relationship("Division", back_populates="account", cascade="all, delete-orphan")


class Division(Base):
    __tablename__ = "divisions"
    __table_args__ = (
        UniqueConstraint("account_id", "name", name="divisions_account_id_name_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    account: Mapped["Account"] = relationship("Account", back_populates="divisions")
    units: Mapped[List["Unit"]] = relationship("Unit", back_populates="division", cascade="all, delete-orphan")
    users: Mapped[List["User"]] = relationship("User", back_populates="division")


class Unit(Base):
    __tablename__ = "units"
    __table_args__ = (
        UniqueConstraint("division_id", "name", name="units_division_id_name_key"),
        Index("idx_units_division_id", "division_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    division_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("divisions.id", ondelete="CASCADE"), nullable=False)

    name: Mapped[str] = mapped_column(Text, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    division: Mapped["Division"] = relationship("Division", back_populates="units")
    users: Mapped[List["User"]] = relationship("User", back_populates="unit")


class StaffRotation(Base):
    __tablename__ = "staff_rotations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    division_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("divisions.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class StaffCertification(Base):
    __tablename__ = "staff_certifications"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    unit_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("units.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    color: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class StaffMember(Base):
    __tablename__ = "staff_members"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    unit_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("units.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    month_rotation: Mapped[Optional[dict]] = mapped_column(JSONB, server_default="{}")
    month_certifications: Mapped[Optional[dict]] = mapped_column(JSONB, server_default="{}")
    active_since: Mapped[Optional[str]] = mapped_column(Text)
    archived_since: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Senior(Base):
    __tablename__ = "seniors"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    unit_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("units.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class ShiftStation(Base):
    __tablename__ = "shift_stations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    unit_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("units.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Station(Base):
    __tablename__ = "stations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    unit_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("units.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    certification_id: Mapped[Optional[int]] = mapped_column(Integer)
    bg_color: Mapped[Optional[str]] = mapped_column(Text)
    border_color: Mapped[Optional[str]] = mapped_column(Text)
    optional: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    min_staff_members: Mapped[Optional[int]] = mapped_column(Integer)
    active_days: Mapped[Optional[List[int]]] = mapped_column(ARRAY(Integer))
    recurrence_type: Mapped[Optional[RecurrenceType]] = mapped_column(SQLEnum(RecurrenceType, name="recurrence_type_enum"))
    recurrence_interval: Mapped[Optional[int]] = mapped_column(Integer)
    recurrence_base_date: Mapped[Optional[date]] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class Shift(Base):
    __tablename__ = "shifts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    unit_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("units.id", ondelete="CASCADE"), nullable=False)
    shift_date: Mapped[date] = mapped_column(Date, nullable=False)
    shift_station_id: Mapped[int] = mapped_column(Integer, nullable=False)
    staff_member_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("staff_members.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class ConstraintType(Base):
    __tablename__ = "constraint_types"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    color: Mapped[Optional[dict]] = mapped_column(JSONB)
    is_hard: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class SpecialDate(Base):
    __tablename__ = "special_dates"

    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), primary_key=True)
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[SpecialDateType] = mapped_column(SQLEnum(SpecialDateType, name="special_date_type"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    updated_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))


class Constraint(Base):
    """The master monthly constraints calendar. Insert-only / versioned: a
    save never updates an existing row, it inserts a fresh batch of rows for
    the whole unit+month, all sharing the same new `version`. "Current state"
    of a month = the rows carrying MAX(version) for that unit_id+date range."""
    __tablename__ = "constraints"
    __table_args__ = (
        UniqueConstraint("unit_id", "type_id", "date", "version", name="constraints_unit_id_type_id_date_version_key"),
        Index("idx_constraints_unit_id_date_version", "unit_id", "date", "version"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    unit_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("units.id", ondelete="CASCADE"), nullable=False)
    type_id: Mapped[int] = mapped_column(Integer, ForeignKey("constraint_types.id", ondelete="RESTRICT"), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    staff_member_ids: Mapped[List[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), default=list, server_default="{}", nullable=False)
    submitted_staff_member_ids: Mapped[List[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), default=list, server_default="{}", nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"))


class MonthlyConstraintsVersion(Base):
    __tablename__ = "monthly_constraints_versions"
    unit_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("units.id", ondelete="CASCADE"), primary_key=True)
    month: Mapped[str] = mapped_column(Text, primary_key=True)  # "YYYY-MM"
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1", nullable=False)


class ConstraintSubmissionMetadata(Base):
    __tablename__ = "constraint_submission_metadata"
    __table_args__ = (
        UniqueConstraint("unit_id", "month", name="constraint_submission_metadata_unit_id_month_key"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    unit_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("units.id", ondelete="CASCADE"), nullable=False)
    month: Mapped[str] = mapped_column(Text, nullable=False)  # "YYYY-MM"
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    updated_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"))
    pulled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    pulled_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class ConstraintsSubmission(Base):
    __tablename__ = "constraints_submissions"
    __table_args__ = (
        Index(
            "ix_constraints_submissions_per_date_unique",
            "unit_id", "staff_member_id", "month", "date",
            unique=True,
            postgresql_where=text("date IS NOT NULL"),
        ),
        Index(
            "ix_constraints_submissions_general_comment_unique",
            "unit_id", "staff_member_id", "month",
            unique=True,
            postgresql_where=text("date IS NULL"),
        ),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    unit_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("units.id", ondelete="CASCADE"), nullable=False)
    staff_member_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("staff_members.id", ondelete="CASCADE"), nullable=False)
    month: Mapped[str] = mapped_column(Text, nullable=False)  # "YYYY-MM"
    date: Mapped[Optional[date]] = mapped_column(Date)
    type_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("constraint_types.id", ondelete="CASCADE"))
    comment: Mapped[Optional[str]] = mapped_column(Text)
    submitted_empty: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class ScheduleStaffMember(Base):
    __tablename__ = "schedule_staff_members"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    unit_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("units.id", ondelete="CASCADE"), nullable=False)
    schedule_date: Mapped[date] = mapped_column(Date, nullable=False)
    staff_member_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("staff_members.id", ondelete="CASCADE"), nullable=False)
    station_id: Mapped[int] = mapped_column(Integer, nullable=False)
    is_stand_by: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ScheduleSenior(Base):
    __tablename__ = "schedule_seniors"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    unit_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("units.id", ondelete="CASCADE"), nullable=False)
    schedule_date: Mapped[date] = mapped_column(Date, nullable=False)
    senior_id: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ScheduleVersion(Base):
    __tablename__ = "schedule_versions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    unit_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("units.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    schedule: Mapped[dict] = mapped_column(JSONB, server_default="{}", nullable=False)

    # store the id of the user who updated this schedule version
    update_admin_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL", onupdate="CASCADE"), nullable=True)


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        Index("idx_users_email", "email"),
        Index("idx_users_division_id", "division_id"),
        Index("idx_users_unit_id", "unit_id"),
        Index(
            "ux_users_unit_id_email_active", "unit_id", "email",
            unique=True, postgresql_where=text("is_deleted = false"),
        ),
        Index(
            "ux_users_division_id_email_active", "division_id", "email",
            unique=True, postgresql_where=text("is_deleted = false"),
        ),
        Index(
            "ux_users_firebase_uid_active", "firebase_uid",
            unique=True, postgresql_where=text("is_deleted = false"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    division_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("divisions.id", ondelete="SET NULL"), nullable=True)
    unit_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("units.id", ondelete="SET NULL"), nullable=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[str] = mapped_column(Text, nullable=False)
    firebase_uid: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    staff_role: Mapped[StaffRole] = mapped_column(SQLEnum(StaffRole, name="staffrole"), nullable=False)
    role: Mapped[UserRole] = mapped_column(SQLEnum(UserRole, name="userrole"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    division: Mapped[Optional["Division"]] = relationship("Division", back_populates="users")
    unit: Mapped[Optional["Unit"]] = relationship("Unit", back_populates="users")
