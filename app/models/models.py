import enum
from sqlalchemy import Column, ForeignKeyConstraint, Index, Integer, String, Boolean, DateTime, ForeignKey, Date, ARRAY, Enum, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from database import Base

class RecurrenceType(enum.Enum):
    weekly = "weekly"
    every_x_days = "every-x-days"
    every_x_weeks = "every-x-weeks"

class AdminRole(enum.Enum):
    owner = "owner"
    admin = "admin"


class Account(Base):
    __tablename__ = "accounts"
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    slug = Column(String, unique=True, nullable=False)
    country = Column(String, nullable=False)
    state = Column(String)
    city = Column(String)
    hospital_name = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

class ResidentRotation(Base):
    __tablename__ = "resident_rotations"
    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

class Certification(Base):
    __tablename__ = "certifications"
    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False)

class Resident(Base):
    __tablename__ = "residents"
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False)
    rotation = Column(Integer)
    certifications_ids = Column(ARRAY(Integer))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

class Senior(Base):
    __tablename__ = "seniors"
    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

class ShiftStation(Base):
    __tablename__ = "shift_stations"
    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

class Station(Base):
    __tablename__ = "stations"
    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False)
    is_default = Column(Boolean, default=False, nullable=False)
    certification_id = Column(Integer)
    bg_color = Column(String)
    border_color = Column(String)
    optional = Column(Boolean, default=False, nullable=False)
    min_residents = Column(Integer)
    active_days = Column(ARRAY(Integer))
    recurrence_type = Column(Enum(RecurrenceType, name="recurrence_type_enum"))
    recurrence_interval = Column(Integer)
    recurrence_base_date = Column(Date)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

class Shift(Base):
    __tablename__ = "shifts"
    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False)
    row_date = Column(Date, nullable=False)
    shift_station_id = Column(Integer, nullable=False)
    resident_id = Column(UUID(as_uuid=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

class ConstraintType(Base):
    __tablename__ = "constraints_types"
    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False)
    color = Column(String)

class Constraint(Base):
    __tablename__ = "constraints"
    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False)
    row_date = Column(Date, nullable=False)
    constraint_type_id = Column(Integer, nullable=False)
    resident_id = Column(UUID(as_uuid=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

class ScheduleResident(Base):
    __tablename__ = "schedule_residents"
    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False)
    row_date = Column(Date, nullable=False)
    resident_id = Column(UUID(as_uuid=True), nullable=False)
    station_id = Column(Integer, nullable=False)
    is_stand_by = Column(Boolean, default=False, nullable=False)
    is_draft = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

class ScheduleSenior(Base):
    __tablename__ = "schedule_seniors"
    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False)
    row_date = Column(Date, nullable=False)
    senior_id = Column(Integer, nullable=False)
    is_draft = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

class ScheduleVersion(Base):
    __tablename__ = "schedule_versions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    is_published = Column(Boolean, default=False, nullable=False)
    schedule = Column(JSONB, server_default='{}', nullable=False)

    update_admin = Column(String, server_default="deleted_admin", nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ["account_id", "update_admin"],
            ["account_admins.account_id", "account_admins.email"],
            ondelete="SET DEFAULT",  # Retains the default string if the admin row is deleted
            onupdate="CASCADE",
            name="fk_schedule_versions_update_admin"
        ),
    )

class AccountAdmin(Base):
    __tablename__ = "account_admins"
    __table_args__ = (
        UniqueConstraint("account_id", "email", name="account_admins_account_id_email_key"),
        Index("idx_account_admins_email", "email")
    )

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False)
    email = Column(String, nullable=False)  # Maps to your 'text' data type
    role = Column(Enum(AdminRole, name="admin_role", create_type=False), server_default="admin", nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now()) 