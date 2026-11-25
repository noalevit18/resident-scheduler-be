import enum
import uuid
from datetime import date, datetime
from typing import List, Optional

from sqlalchemy import (
    Index,
    Integer,
    SmallInteger,
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


class ConstraintTypeKind(str, enum.Enum):
    BLOCKING = "blocking"
    PREFERENCE = "preference"


class ConstraintTypeScope(str, enum.Enum):
    """Which calendar a constraint type belongs to: the daily schedule's
    constraints, or the on-call constraints (hard "can't" reasons only)."""
    SCHEDULE = "schedule"
    ON_CALL = "on_call"


class SubmissionScope(str, enum.Enum):
    """Which submission window a metadata row is: the daily schedule's
    (constraints, Friday mode, on-call shift requests) or the on-call
    constraints'."""
    SCHEDULE = "schedule"
    ON_CALL = "on_call"


class FridayMode(str, enum.Enum):
    PREFERENCE = "preference"
    RANKING = "ranking"


class UnitMode(str, enum.Enum):
    RESIDENTS = "residents"
    NURSING = "nursing"
    ATTENDINGS = "attendings"
    INTERNS = "interns"


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
    mode: Mapped[UnitMode] = mapped_column(
        SQLEnum(UnitMode, name="unit_mode"), default=UnitMode.RESIDENTS, server_default="RESIDENTS", nullable=False,
    )

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
    # {"YYYY-MM": {"<on_call_station_id>": rank}} — on-call stations the member is
    # certified for that month, each with the member's rank there (1..5, 5 = strongest).
    month_on_call_certifications: Mapped[Optional[dict]] = mapped_column(JSONB, server_default="{}")
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


class OnCallDistributionMode(str, enum.Enum):
    ROTATION_DAILY = "rotation_daily"
    ROTATION_WEEKLY = "rotation_weekly"
    TURNS = "turns"
    MANUAL = "manual"


class OnCallStationGroup(Base):
    """A named bucket of on-call stations that usually come together (staffed
    by the same unit on a given day, by default). Not versioned."""
    __tablename__ = "on_call_station_groups"
    __table_args__ = (
        UniqueConstraint("division_id", "name", name="on_call_station_groups_division_id_name_key"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    division_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("divisions.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    stations: Mapped[List["OnCallStation"]] = relationship(
        "OnCallStation", order_by="OnCallStation.group_order", lazy="selectin", viewonly=True,
    )

    @property
    def station_ids(self) -> List[int]:
        """The group's active stations, in display order."""
        return [station.id for station in self.stations if not station.is_deleted]


class OnCallDivisionSettings(Base):
    """General on-call settings of a division. A division without a row uses
    the defaults."""
    __tablename__ = "on_call_division_settings"
    division_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("divisions.id", ondelete="CASCADE"), primary_key=True)
    shift_length_hours: Mapped[int] = mapped_column(Integer, default=24, server_default=text("24"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class ExternalOnCallPhysician(Base):
    """A physician who takes on-call shifts for a unit without being one of
    its residents. Not a staff member; optionally connected to a regular user.
    Archived rather than deleted (archived_at set), so past shifts can keep
    referencing them."""
    __tablename__ = "external_on_call_physicians"
    __table_args__ = (
        Index(
            "ux_external_on_call_physicians_unit_id_user_id_active",
            "unit_id", "user_id",
            unique=True,
            postgresql_where=text("archived_at IS NULL AND user_id IS NOT NULL"),
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    unit_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("units.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    activation_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    archived_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    archived_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))


class OnCallUnitStation(Base):
    """A station a unit's residents can cover. A unit with no rows can cover
    every station."""
    __tablename__ = "on_call_unit_stations"
    unit_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("units.id", ondelete="CASCADE"), primary_key=True)
    on_call_station_id: Mapped[int] = mapped_column(Integer, ForeignKey("on_call_stations.id", ondelete="CASCADE"), primary_key=True, index=True)


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
    initials: Mapped[Optional[str]] = mapped_column(Text)
    # {"bg", "text", "border", "is_custom"} — same shape as ConstraintType.color.
    color: Mapped[Optional[dict]] = mapped_column(JSONB)
    number_of_residents: Mapped[int] = mapped_column(Integer, default=1, server_default=text("1"), nullable=False)
    requires_independent: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"), nullable=False)
    open_to_external: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"), nullable=False)
    distribution_mode: Mapped[OnCallDistributionMode] = mapped_column(
        SQLEnum(OnCallDistributionMode, name="on_call_distribution_mode"),
        default=OnCallDistributionMode.ROTATION_DAILY, server_default="ROTATION_DAILY", nullable=False,
    )
    priority_unit_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("units.id", ondelete="SET NULL"))
    staff_rotation_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("staff_rotations.id", ondelete="SET NULL"))
    required_certification_ids: Mapped[list[int]] = mapped_column(
        ARRAY(Integer), default=list, server_default=text("'{}'"), nullable=False,
    )
    rotation_length: Mapped[int] = mapped_column(Integer, default=1, server_default=text("1"), nullable=False)
    rotation_start_date: Mapped[date] = mapped_column(Date, server_default=func.current_date(), default=date.today, nullable=False)
    rotation_unit_ids: Mapped[List[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), default=list, server_default=text("'{}'"), nullable=False,
    )
    group_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("on_call_station_groups.id", ondelete="SET NULL"), index=True)
    group_order: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"), nullable=False)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    unit_coverage: Mapped[List["OnCallUnitStation"]] = relationship("OnCallUnitStation", cascade="all, delete-orphan")


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
    active_on_half_day: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"), nullable=False)
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
    active_on_half_day: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"), nullable=False)
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
    kind: Mapped[ConstraintTypeKind] = mapped_column(
        SQLEnum(ConstraintTypeKind, name="constraint_type_kind"), default=ConstraintTypeKind.BLOCKING, nullable=False,
    )
    # Preference scale of a PREFERENCE type: 1 = want, 0 = informational, -1 = prefer not.
    preference: Mapped[int] = mapped_column(SmallInteger, default=0, server_default=text("0"), nullable=False)
    scope: Mapped[ConstraintTypeScope] = mapped_column(
        SQLEnum(ConstraintTypeScope, name="constraint_type_scope"),
        default=ConstraintTypeScope.SCHEDULE, server_default="SCHEDULE", nullable=False,
    )
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
        # The Friday-rank row of a date (type_id IS NULL) — at most one per version.
        Index(
            "ix_constraints_rank_row_unique",
            "unit_id", "date", "version",
            unique=True,
            postgresql_where=text("type_id IS NULL"),
        ),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    unit_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("units.id", ondelete="CASCADE"), nullable=False)
    # NULL marks the date's Friday-rank row, whose ranks live in staff_member_ranks.
    type_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("constraint_types.id", ondelete="RESTRICT"))
    date: Mapped[date] = mapped_column(Date, nullable=False)
    staff_member_ids: Mapped[List[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), default=list, server_default="{}", nullable=False)
    submitted_staff_member_ids: Mapped[List[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), default=list, server_default="{}", nullable=False)
    # {"<staff_member_id str>": <rank int>} — only on the Friday-rank row (type_id IS NULL).
    staff_member_ranks: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}", nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"))


class MonthlyConstraintsVersion(Base):
    __tablename__ = "monthly_constraints_versions"
    unit_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("units.id", ondelete="CASCADE"), primary_key=True)
    month: Mapped[str] = mapped_column(Text, primary_key=True)  # "YYYY-MM"
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1", nullable=False)


class OnCallConstraint(Base):
    """The master monthly on-call constraints calendar. Insert-only /
    versioned exactly like `Constraint`. Each row groups the staff members
    sharing one value on one date: either a scale `preference` (2 = want,
    1 = prefer, -1 = prefer not, -2 = can't; 0 = "can" is the default and
    never stored) or a hard on-call constraint type (`type_id`, e.g.
    vacation / army — equivalent to can't)."""
    __tablename__ = "on_call_constraints"
    __table_args__ = (
        CheckConstraint(
            "(type_id IS NULL) <> (preference IS NULL)",
            name="ck_on_call_constraints_type_xor_preference",
        ),
        CheckConstraint(
            "preference IS NULL OR preference IN (-2, -1, 1, 2)",
            name="ck_on_call_constraints_preference_range",
        ),
        Index("idx_on_call_constraints_unit_id_date_version", "unit_id", "date", "version"),
        Index(
            "ux_on_call_constraints_type_row",
            "unit_id", "date", "type_id", "version",
            unique=True,
            postgresql_where=text("type_id IS NOT NULL"),
        ),
        Index(
            "ux_on_call_constraints_preference_row",
            "unit_id", "date", "preference", "version",
            unique=True,
            postgresql_where=text("preference IS NOT NULL"),
        ),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    unit_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("units.id", ondelete="CASCADE"), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    type_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("constraint_types.id", ondelete="RESTRICT"))
    preference: Mapped[Optional[int]] = mapped_column(SmallInteger)
    staff_member_ids: Mapped[List[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), default=list, server_default="{}", nullable=False)
    submitted_staff_member_ids: Mapped[List[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), default=list, server_default="{}", nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"))


class MonthlyOnCallConstraintsVersion(Base):
    __tablename__ = "monthly_on_call_constraints_versions"
    unit_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("units.id", ondelete="CASCADE"), primary_key=True)
    month: Mapped[str] = mapped_column(Text, primary_key=True)  # "YYYY-MM"
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1", nullable=False)


class OnCallVersionKind(str, enum.Enum):
    """What a shared on-call scheduling version saved for a unit."""
    CONSTRAINTS = "CONSTRAINTS"
    ROSTER = "ROSTER"
    DAY_STATIONS = "DAY_STATIONS"


class OnCallSchedulingVersion(Base):
    """One save of a division+month's on-call scheduling. Insert-only. The unit's on-call constraints, roster and
    day stations a save writes all carry its `version` (their own tables' `version` columns), so one number names
    the whole page's state. `entities` records what the save wrote: an entity "as of version N" is its latest
    version at or below N."""
    __tablename__ = "on_call_scheduling_versions"
    __table_args__ = (
        UniqueConstraint("division_id", "month", "version", name="on_call_scheduling_versions_division_month_version_key"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    division_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("divisions.id", ondelete="CASCADE"), nullable=False)
    month: Mapped[str] = mapped_column(Text, nullable=False)  # "YYYY-MM"
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    entities: Mapped[List["OnCallSchedulingVersionEntity"]] = relationship(
        "OnCallSchedulingVersionEntity", back_populates="scheduling_version", cascade="all, delete-orphan",
    )


class OnCallSchedulingVersionEntity(Base):
    """A unit's entity (constraints, roster or day stations) written by a shared on-call scheduling version."""
    __tablename__ = "on_call_scheduling_version_entities"
    __table_args__ = (
        UniqueConstraint("scheduling_version_id", "unit_id", "kind", name="on_call_scheduling_version_entities_key"),
        Index("idx_on_call_scheduling_version_entities_unit_kind", "unit_id", "kind"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scheduling_version_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("on_call_scheduling_versions.id", ondelete="CASCADE"), nullable=False,
    )
    unit_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("units.id", ondelete="CASCADE"), nullable=False)
    kind: Mapped[OnCallVersionKind] = mapped_column(SQLEnum(OnCallVersionKind, name="on_call_version_kind"), nullable=False)
    scheduling_version: Mapped["OnCallSchedulingVersion"] = relationship("OnCallSchedulingVersion", back_populates="entities")


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


class OnCallDayStation(Base):
    """A unit's change to the stations it populates on a day, on top of what the
    stations' rotations give it: `is_added` true adds the station that day,
    false removes it. The on-call shifts are saved separately: the scheduling
    page takes the station's residents off call in the same save.
    Insert-only / versioned: every save inserts the unit+month's complete set
    of changes under a new `version` (see MonthlyOnCallDayStationsVersion);
    the month's current state is the rows of its latest version."""
    __tablename__ = "on_call_day_stations"
    __table_args__ = (
        UniqueConstraint(
            "unit_id", "date", "on_call_station_id", "version", name="on_call_day_stations_unit_id_date_station_version_key",
        ),
        Index("idx_on_call_day_stations_unit_id_date_version", "unit_id", "date", "version"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    division_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("divisions.id", ondelete="CASCADE"), nullable=False)
    unit_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("units.id", ondelete="CASCADE"), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    on_call_station_id: Mapped[int] = mapped_column(Integer, ForeignKey("on_call_stations.id", ondelete="CASCADE"), nullable=False)
    is_added: Mapped[bool] = mapped_column(Boolean, nullable=False)
    # For a "turns" station: the change re-flows the turns after it — an added day makes the unit's turn
    # (the next day goes to the unit after it), a removed day keeps the turn with the unit for the next day.
    shifts_turns: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))


class MonthlyOnCallDayStationsVersion(Base):
    """Insert-only, one row per (unit_id, month, version) — every day-stations
    save gets its own row, so a save that clears every change still shows in
    the history. The current version is the highest `version`."""
    __tablename__ = "monthly_on_call_day_stations_versions"
    __table_args__ = (
        UniqueConstraint("unit_id", "month", "version", name="monthly_on_call_day_stations_versions_key"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    unit_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("units.id", ondelete="CASCADE"), nullable=False)
    month: Mapped[str] = mapped_column(Text, nullable=False)  # "YYYY-MM"
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))


class OnCallDayNote(Base):
    """A free-text note on a day of the division's on-call roster, shown on the
    scheduling page — e.g. a special staffing requirement for that day. One per
    division and day; a month's notes are replaced as a whole on every save.
    Not versioned: every view shows the latest notes."""
    __tablename__ = "on_call_day_notes"
    __table_args__ = (
        UniqueConstraint("division_id", "date", name="on_call_day_notes_division_id_date_key"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    division_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("divisions.id", ondelete="CASCADE"), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))


class StaffMemberSubmissionMetadata(Base):
    """One row per (unit_id, month, scope): each scope's own submission
    window (start_time/end_time) — the daily schedule's (SCHEDULE) and the
    on-call constraints' (ON_CALL) open and close independently.
    pull_information tracks each feature's own pulled_at/pulled_by on its
    scope's row, keyed by feature name, e.g.
    {"constraints": {"pulled_at": "...", "pulled_by": "<user-id>"}}.
    friday_mode only applies to the SCHEDULE row."""
    __tablename__ = "staff_member_submission_metadata"
    __table_args__ = (
        UniqueConstraint(
            "unit_id", "month", "scope", name="staff_member_submission_metadata_unit_id_month_scope_key",
        ),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    unit_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("units.id", ondelete="CASCADE"), nullable=False)
    month: Mapped[str] = mapped_column(Text, nullable=False)  # "YYYY-MM"
    scope: Mapped[SubmissionScope] = mapped_column(
        SQLEnum(SubmissionScope, name="submission_scope"),
        default=SubmissionScope.SCHEDULE, server_default="SCHEDULE", nullable=False,
    )
    start_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    updated_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"))
    pull_information: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}", nullable=False)
    # How members express Friday wishes this month: want / prefer-not types, or a 1..N ranking.
    friday_mode: Mapped[FridayMode] = mapped_column(
        SQLEnum(FridayMode, name="friday_mode"), default=FridayMode.PREFERENCE, server_default="PREFERENCE", nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class StaffMemberSubmission(Base):
    """A member's daily schedule submission row: a date's constraint type or
    Friday rank; the date-less row holds the month's general comment.
    `on_call_station_id` is legacy and read-only — on-call station requests
    from before the on-call constraints form (StaffMemberOnCallSubmission);
    nothing writes it any more, and it's kept for the past months' data."""
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
    # The member's Friday rank (1 = most wanted) — only with constraint_type_id NULL, in ranking mode.
    rank: Mapped[Optional[int]] = mapped_column(SmallInteger)
    submitted_empty: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class StaffMemberOnCallSubmission(Base):
    """A member's self-serve on-call constraints for a month, kept apart from
    the daily schedule's `staff_member_submissions` (own comment, own
    "submitted empty" flag, own submission status). A dated row holds the
    member's on-call wish for that date: a -2..2 scale `preference` (0 = "can"
    is the default, never stored) or a hard on-call constraint type. The
    date-less row holds the month's general comment and marks the form as
    submitted. The submitter is either a staff member of the unit or one of
    its external on-call physicians — exactly one of the two ids is set."""
    __tablename__ = "staff_member_on_call_submissions"
    __table_args__ = (
        Index(
            "ix_staff_member_on_call_submissions_per_date_unique",
            "unit_id", "staff_member_id", "month", "date",
            unique=True,
            postgresql_where=text("date IS NOT NULL"),
        ),
        Index(
            "ix_staff_member_on_call_submissions_general_comment_unique",
            "unit_id", "staff_member_id", "month",
            unique=True,
            postgresql_where=text("date IS NULL"),
        ),
        Index(
            "ix_staff_member_on_call_submissions_external_per_date_unique",
            "unit_id", "external_physician_id", "month", "date",
            unique=True,
            postgresql_where=text("date IS NOT NULL AND external_physician_id IS NOT NULL"),
        ),
        Index(
            "ix_staff_member_on_call_submissions_external_comment_unique",
            "unit_id", "external_physician_id", "month",
            unique=True,
            postgresql_where=text("date IS NULL AND external_physician_id IS NOT NULL"),
        ),
        CheckConstraint(
            "(staff_member_id IS NULL) <> (external_physician_id IS NULL)",
            name="ck_staff_member_on_call_submissions_one_submitter",
        ),
        CheckConstraint(
            "preference IS NULL OR constraint_type_id IS NULL",
            name="ck_staff_member_on_call_submissions_preference_xor_type",
        ),
        CheckConstraint(
            "preference IS NULL OR preference IN (-2, -1, 1, 2)",
            name="ck_staff_member_on_call_submissions_preference_range",
        ),
        CheckConstraint(
            "date IS NOT NULL OR (preference IS NULL AND constraint_type_id IS NULL)",
            name="ck_staff_member_on_call_submissions_value_needs_date",
        ),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    unit_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("units.id", ondelete="CASCADE"), nullable=False)
    staff_member_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("staff_members.id", ondelete="CASCADE"))
    external_physician_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("external_on_call_physicians.id", ondelete="CASCADE"), index=True,
    )
    month: Mapped[str] = mapped_column(Text, nullable=False)  # "YYYY-MM"
    date: Mapped[Optional[date]] = mapped_column(Date)
    preference: Mapped[Optional[int]] = mapped_column(SmallInteger)
    constraint_type_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("constraint_types.id", ondelete="CASCADE"))
    comment: Mapped[Optional[str]] = mapped_column(Text)
    submitted_empty: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    @property
    def submitter_id(self) -> uuid.UUID:
        """The staff member's or the external physician's id — how the on-call
        calendars refer to the submitter."""
        submitter_id = self.staff_member_id or self.external_physician_id
        assert submitter_id is not None  # ck_staff_member_on_call_submissions_one_submitter
        return submitter_id


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
