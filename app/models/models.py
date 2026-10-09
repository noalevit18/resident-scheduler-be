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
    CheckConstraint,
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


class SubmissionFeature(str, enum.Enum):
    CONSTRAINTS = "constraints"
    ON_CALL = "on_call"


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
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    unit_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("units.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    deleted_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))


class OnCallStation(Base):
    __tablename__ = "on_call_stations"
    __table_args__ = (
        Index(
            "ux_on_call_stations_division_id_name_active",
            "division_id", "name",
            unique=True,
            postgresql_where=text("is_deleted = false"),
        ),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    division_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("divisions.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"), nullable=False)


class Station(Base):
    """Station definition. GLOBAL fields (name, colors, display_order) live
    only here and apply to every month, past ones included. VERSIONED fields
    are mirrored here from the latest-effective `station_versions` row; what
    applies on a given date is the version in effect on that date (greatest
    `effective_from` <= date, ties to the higher version). Soft-deleted
    rather than removed, since older schedule versions keep referencing it.
    `recurrence_type` NULL means a manual (non-recurring) station."""
    __tablename__ = "stations"
    __table_args__ = (
        UniqueConstraint("unit_id", "firestore_id", name="stations_unit_id_firestore_id_key"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    unit_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("units.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_secondary: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"), nullable=False)
    secondary_to: Mapped[List[int]] = mapped_column(ARRAY(Integer), default=list, server_default=text("'{}'"), nullable=False)
    certification_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("staff_certifications.id", ondelete="SET NULL"))
    bg_color: Mapped[Optional[str]] = mapped_column(Text)
    border_color: Mapped[Optional[str]] = mapped_column(Text)
    text_color: Mapped[Optional[str]] = mapped_column(Text)
    optional: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    min_staff_members: Mapped[Optional[int]] = mapped_column(Integer)
    min_staff_on_sabbatical: Mapped[Optional[int]] = mapped_column(Integer)
    min_staff_on_half_day: Mapped[Optional[int]] = mapped_column(Integer)
    active_days: Mapped[Optional[List[int]]] = mapped_column(ARRAY(Integer))
    recurrence_type: Mapped[Optional[RecurrenceType]] = mapped_column(SQLEnum(RecurrenceType, name="recurrence_type_enum"))
    recurrence_interval: Mapped[Optional[int]] = mapped_column(Integer)
    recurrence_base_date: Mapped[Optional[date]] = mapped_column(Date)
    display_order: Mapped[Optional[int]] = mapped_column(Integer)
    enable_stand_by: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"), nullable=False)
    active_on_sabbatical: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"), nullable=False)
    prefer_day_before_on_call: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"), nullable=False)
    # The Firestore `stations` doc id this row was migrated from (NULL for
    # stations created through the API) — lets the migration script upsert.
    firestore_id: Mapped[Optional[str]] = mapped_column(Text)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"), nullable=False)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    deleted_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class StationVersion(Base):
    """A station's versioned configuration effective from `effective_from`.
    Insert-only, except that a version no schedule version pins may be
    replaced in place by a change with the same `effective_from`.
    `is_retired` marks the final version written when a station is deleted."""
    __tablename__ = "station_versions"
    __table_args__ = (
        UniqueConstraint("station_id", "version", name="station_versions_station_id_version_key"),
        Index("idx_station_versions_station_id_effective_from", "station_id", "effective_from"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    station_id: Mapped[int] = mapped_column(Integer, ForeignKey("stations.id", ondelete="RESTRICT"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    is_retired: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"), nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_secondary: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"), nullable=False)
    secondary_to: Mapped[List[int]] = mapped_column(ARRAY(Integer), default=list, server_default=text("'{}'"), nullable=False)
    certification_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("staff_certifications.id", ondelete="SET NULL"))
    optional: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    min_staff_members: Mapped[Optional[int]] = mapped_column(Integer)
    min_staff_on_sabbatical: Mapped[Optional[int]] = mapped_column(Integer)
    min_staff_on_half_day: Mapped[Optional[int]] = mapped_column(Integer)
    active_days: Mapped[Optional[List[int]]] = mapped_column(ARRAY(Integer))
    recurrence_type: Mapped[Optional[RecurrenceType]] = mapped_column(SQLEnum(RecurrenceType, name="recurrence_type_enum", create_type=False))
    recurrence_interval: Mapped[Optional[int]] = mapped_column(Integer)
    recurrence_base_date: Mapped[Optional[date]] = mapped_column(Date)
    enable_stand_by: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"), nullable=False)
    active_on_sabbatical: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"), nullable=False)
    prefer_day_before_on_call: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))


class OnCallStationMapping(Base):
    """Not versioned. Within a unit, each on-call station maps to at most one
    station; a station can have many on-call stations."""
    __tablename__ = "on_call_station_mappings"
    __table_args__ = (
        UniqueConstraint("unit_id", "on_call_station_id", name="on_call_station_mappings_unit_id_on_call_station_id_key"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    unit_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("units.id", ondelete="CASCADE"), nullable=False)
    on_call_station_id: Mapped[int] = mapped_column(Integer, ForeignKey("on_call_stations.id", ondelete="CASCADE"), nullable=False)
    station_id: Mapped[int] = mapped_column(Integer, ForeignKey("stations.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


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


class MonthOnCallVersion(Base):
    """Insert-only, one row per (unit_id, month, version) — every
    new on-call version gets its OWN row rather than updating the previous
    one, so the publish history (which version was published, when, by
    whom) is preserved rather than overwritten on the next save."""
    __tablename__ = "monthly_on_call_versions"
    __table_args__ = (
        UniqueConstraint("unit_id", "month", "version", name="monthly_on_call_versions_unit_id_month_version_key"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    unit_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("units.id", ondelete="CASCADE"), nullable=False)
    month: Mapped[str] = mapped_column(Text, nullable=False)  # "YYYY-MM"
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"), nullable=False)
    published_at: Mapped[Optional[date]] = mapped_column(Date)
    published_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))


class OnCallShift(Base):
    """One row per (unit_id, date, version); """
    __tablename__ = "on_call_shifts"
    __table_args__ = (
        UniqueConstraint("unit_id", "date", "version", name="on_call_shifts_unit_id_date_version_key"),
        Index("idx_on_call_shifts_unit_id_date_version", "unit_id", "date", "version"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    division_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("divisions.id", ondelete="CASCADE"), nullable=False)
    unit_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("units.id", ondelete="CASCADE"), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    station_assignments: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}", nullable=False)
    # {"<staff_member_id str>": <on_call_station_id int>, ...} — the full assignment for this date
    submitted_assignments: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}", nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"))


class StaffMemberSubmissionMetadata(Base):
    """One row per (unit_id, month): the submission window (start_time/
    end_time) of constraints and on-call.
    pull_information tracks each feature's own pulled_at/pulled_by
    independently, keyed by feature name, e.g.
    {"constraints": {"pulled_at": "...", "pulled_by": "<user-id>"}}."""
    __tablename__ = "staff_member_submission_metadata"
    __table_args__ = (
        UniqueConstraint("unit_id", "month", name="staff_member_submission_metadata_unit_id_month_key"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    unit_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("units.id", ondelete="CASCADE"), nullable=False)
    month: Mapped[str] = mapped_column(Text, nullable=False)  # "YYYY-MM"
    start_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    updated_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"))
    pull_information: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class StaffMemberSubmission(Base):
    """Shared self-serve submission row: a single date's submission can
    carry a constraint type, an on-call station, or both at once. Every
    submission call replaces the full row (both fields together)."""
    __tablename__ = "staff_member_submissions"
    __table_args__ = (
        Index(
            "ix_staff_member_submissions_per_date_unique",
            "unit_id", "staff_member_id", "month", "date",
            unique=True,
            postgresql_where=text("date IS NOT NULL"),
        ),
        Index(
            "ix_staff_member_submissions_general_comment_unique",
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
    constraint_type_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("constraint_types.id", ondelete="CASCADE"))
    on_call_station_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("on_call_stations.id", ondelete="CASCADE"))
    comment: Mapped[Optional[str]] = mapped_column(Text)
    submitted_empty: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class ScheduleVersion(Base):
    """Insert-only, one row per (unit_id, month, version). Every schedule
    save inserts a new version row plus a full snapshot of the month in
    `schedule_stations` / `schedule_assignments` / `schedule_seniors`.
    The only in-place update is (un)publishing. `constraints_version` and
    `on_call_version` record which constraints/on-call versions were current
    when this version was saved."""
    __tablename__ = "schedule_versions"
    __table_args__ = (
        UniqueConstraint("unit_id", "month", "version", name="schedule_versions_unit_id_month_version_key"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    unit_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("units.id", ondelete="CASCADE"), nullable=False)
    month: Mapped[str] = mapped_column(Text, nullable=False)  # "YYYY-MM"
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"), nullable=False)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    published_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    constraints_version: Mapped[Optional[int]] = mapped_column(Integer)
    on_call_version: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))

    stations: Mapped[List["ScheduleStation"]] = relationship("ScheduleStation", back_populates="schedule_version")
    seniors: Mapped[List["ScheduleSenior"]] = relationship("ScheduleSenior", back_populates="schedule_version")


class ScheduleVersionStation(Base):
    """Station versions a schedule version is pinned to — kept at the
    schedule-version level (not per date). A month can pin several versions
    of one station (a change effective mid-month)."""
    __tablename__ = "schedule_version_stations"
    __table_args__ = (
        UniqueConstraint("schedule_version_id", "station_version_id", name="schedule_version_stations_version_station_version_key"),
        Index("idx_schedule_version_stations_station_version_id", "station_version_id"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    schedule_version_id: Mapped[int] = mapped_column(Integer, ForeignKey("schedule_versions.id", ondelete="CASCADE"), nullable=False)
    station_id: Mapped[int] = mapped_column(Integer, ForeignKey("stations.id", ondelete="RESTRICT"), nullable=False)
    station_version_id: Mapped[int] = mapped_column(Integer, ForeignKey("station_versions.id", ondelete="RESTRICT"), nullable=False)

    station_version: Mapped["StationVersion"] = relationship("StationVersion")


class ScheduleStation(Base):
    """A station shown on a date in one schedule version — either a
    configured station (`station_id`) or a custom station added manually to
    this schedule only (`custom_name`), never both."""
    __tablename__ = "schedule_stations"
    __table_args__ = (
        CheckConstraint("num_nonnulls(station_id, custom_name) = 1", name="schedule_stations_station_or_custom_check"),
        Index(
            "ux_schedule_stations_version_date_station",
            "schedule_version_id", "date", "station_id",
            unique=True,
            postgresql_where=text("station_id IS NOT NULL"),
        ),
        Index("idx_schedule_stations_version_date", "schedule_version_id", "date"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    schedule_version_id: Mapped[int] = mapped_column(Integer, ForeignKey("schedule_versions.id", ondelete="CASCADE"), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    station_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("stations.id", ondelete="RESTRICT"))
    custom_name: Mapped[Optional[str]] = mapped_column(Text)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False)

    schedule_version: Mapped["ScheduleVersion"] = relationship("ScheduleVersion", back_populates="stations")
    assignments: Mapped[List["ScheduleAssignment"]] = relationship("ScheduleAssignment", back_populates="schedule_station")


class ScheduleAssignment(Base):
    __tablename__ = "schedule_assignments"
    __table_args__ = (
        UniqueConstraint("schedule_station_id", "staff_member_id", name="schedule_assignments_station_staff_member_key"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    schedule_station_id: Mapped[int] = mapped_column(Integer, ForeignKey("schedule_stations.id", ondelete="CASCADE"), nullable=False, index=True)
    staff_member_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("staff_members.id", ondelete="RESTRICT"), nullable=False)
    is_stand_by: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"), nullable=False)

    schedule_station: Mapped["ScheduleStation"] = relationship("ScheduleStation", back_populates="assignments")


class ScheduleSenior(Base):
    """One senior per date per schedule version."""
    __tablename__ = "schedule_seniors"
    __table_args__ = (
        UniqueConstraint("schedule_version_id", "date", name="schedule_seniors_version_date_key"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    schedule_version_id: Mapped[int] = mapped_column(Integer, ForeignKey("schedule_versions.id", ondelete="CASCADE"), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    senior_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("seniors.id", ondelete="RESTRICT"), nullable=False)

    schedule_version: Mapped["ScheduleVersion"] = relationship("ScheduleVersion", back_populates="seniors")


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
