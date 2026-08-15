import enum
from sqlalchemy import (
    Column,
    Index,
    Integer,
    Text,
    Boolean,
    DateTime,
    ForeignKey,
    Date,
    ARRAY,
    UniqueConstraint,
    Enum as SQLEnum
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from database import Base


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


class Account(Base):
    __tablename__ = "accounts"
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    account_name = Column(Text, unique=True, nullable=False)
    country = Column(Text, nullable=False)
    state = Column(Text)
    city = Column(Text)
    hospital_name = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    divisions = relationship("Division", back_populates="account", cascade="all, delete-orphan")


class Division(Base):
    __tablename__ = "divisions"
    __table_args__ = (
        UniqueConstraint("account_id", "name", name="divisions_account_id_name_key"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False)
    name = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    account = relationship("Account", back_populates="divisions")
    units = relationship("Unit", back_populates="division", cascade="all, delete-orphan")
    users = relationship("User", back_populates="division")


class Unit(Base):
    __tablename__ = "units"
    __table_args__ = (
        UniqueConstraint("division_id", "name", name="units_division_id_name_key"),
        Index("idx_units_division_id", "division_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    division_id = Column(UUID(as_uuid=True), ForeignKey("divisions.id", ondelete="CASCADE"), nullable=False)

    name = Column(Text, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    division = relationship("Division", back_populates="units")
    users = relationship("User", back_populates="unit")


class StaffRotation(Base):
    __tablename__ = "staff_rotations"
    id = Column(Integer, primary_key=True, autoincrement=True)
    division_id = Column(UUID(as_uuid=True), ForeignKey("divisions.id", ondelete="CASCADE"), nullable=False)
    name = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Certification(Base):
    __tablename__ = "certifications"
    id = Column(Integer, primary_key=True, autoincrement=True)
    unit_id = Column(UUID(as_uuid=True), ForeignKey("units.id", ondelete="CASCADE"), nullable=False)
    name = Column(Text, nullable=False)
    color = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class StaffMember(Base):
    __tablename__ = "staff_members"
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    unit_id = Column(UUID(as_uuid=True), ForeignKey("units.id", ondelete="CASCADE"), nullable=False)
    month = Column(Date)
    name = Column(Text, nullable=False)
    rotation = Column(Integer)
    certifications_ids = Column(ARRAY(Integer))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class Senior(Base):
    __tablename__ = "seniors"
    id = Column(Integer, primary_key=True, autoincrement=True)
    unit_id = Column(UUID(as_uuid=True), ForeignKey("units.id", ondelete="CASCADE"), nullable=False)
    name = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class ShiftStation(Base):
    __tablename__ = "shift_stations"
    id = Column(Integer, primary_key=True, autoincrement=True)
    unit_id = Column(UUID(as_uuid=True), ForeignKey("units.id", ondelete="CASCADE"), nullable=False)
    name = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Station(Base):
    __tablename__ = "stations"
    id = Column(Integer, primary_key=True, autoincrement=True)
    unit_id = Column(UUID(as_uuid=True), ForeignKey("units.id", ondelete="CASCADE"), nullable=False)
    name = Column(Text, nullable=False)
    is_default = Column(Boolean, default=False, nullable=False)
    certification_id = Column(Integer)
    bg_color = Column(Text)
    border_color = Column(Text)
    optional = Column(Boolean, default=False, nullable=False)
    min_staff_members = Column(Integer)
    active_days = Column(ARRAY(Integer))
    recurrence_type = Column(SQLEnum(RecurrenceType, name="recurrence_type_enum"))
    recurrence_interval = Column(Integer)
    recurrence_base_date = Column(Date)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class Shift(Base):
    __tablename__ = "shifts"
    id = Column(Integer, primary_key=True, autoincrement=True)
    unit_id = Column(UUID(as_uuid=True), ForeignKey("units.id", ondelete="CASCADE"), nullable=False)
    shift_date = Column(Date, nullable=False)
    shift_station_id = Column(Integer, nullable=False)
    staff_member_id = Column(UUID(as_uuid=True), ForeignKey("staff_members.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class ConstraintType(Base):
    __tablename__ = "constraints_types"
    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False)
    name = Column(Text, nullable=False)
    color = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Constraint(Base):
    __tablename__ = "constraints"
    id = Column(Integer, primary_key=True, autoincrement=True)
    unit_id = Column(UUID(as_uuid=True), ForeignKey("units.id", ondelete="CASCADE"), nullable=False)
    constraint_date = Column(Date, nullable=False)
    constraint_type_id = Column(Integer, nullable=False)
    staff_member_id = Column(UUID(as_uuid=True), ForeignKey("staff_members.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class ScheduleStaffMember(Base):
    __tablename__ = "schedule_staff_members"
    id = Column(Integer, primary_key=True, autoincrement=True)
    unit_id = Column(UUID(as_uuid=True), ForeignKey("units.id", ondelete="CASCADE"), nullable=False)
    schedule_date = Column(Date, nullable=False)
    staff_member_id = Column(UUID(as_uuid=True), ForeignKey("staff_members.id", ondelete="CASCADE"), nullable=False)
    station_id = Column(Integer, nullable=False)
    is_stand_by = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ScheduleSenior(Base):
    __tablename__ = "schedule_seniors"
    id = Column(Integer, primary_key=True, autoincrement=True)
    unit_id = Column(UUID(as_uuid=True), ForeignKey("units.id", ondelete="CASCADE"), nullable=False)
    schedule_date = Column(Date, nullable=False)
    senior_id = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ScheduleVersion(Base):
    __tablename__ = "schedule_versions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    unit_id = Column(UUID(as_uuid=True), ForeignKey("units.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    is_published = Column(Boolean, default=False, nullable=False)
    schedule = Column(JSONB, server_default="{}", nullable=False)

    # store the id of the user who updated this schedule version
    update_admin_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL", onupdate="CASCADE"), nullable=True)


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("unit_id", "email", name="users_unit_id_email_key"),
        UniqueConstraint("division_id", "email", name="users_division_id_email_key"),
        Index("idx_users_email", "email"),
        Index("idx_users_division_id", "division_id"),
        Index("idx_users_unit_id", "unit_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    division_id = Column(UUID(as_uuid=True), ForeignKey("divisions.id", ondelete="SET NULL"), nullable=True)
    unit_id = Column(UUID(as_uuid=True), ForeignKey("units.id", ondelete="SET NULL"), nullable=True)
    name = Column(Text, nullable=False)
    email = Column(Text, nullable=False)
    staff_role = Column(SQLEnum(StaffRole, name="staffrole"), nullable=False)
    role = Column(SQLEnum(UserRole, name="userrole"), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    division = relationship("Division", back_populates="users")
    unit = relationship("Unit", back_populates="users")