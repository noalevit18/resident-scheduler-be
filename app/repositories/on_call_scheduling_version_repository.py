import logging
from typing import Callable, Optional, TypeVar
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models.models import OnCallSchedulingVersion, OnCallSchedulingVersionEntity, OnCallVersionKind, Unit
from app.repositories.on_call_shift_repository import OnCallVersionConflictError

logger = logging.getLogger(__name__)

T = TypeVar("T")


class OnCallSchedulingVersionRepository:
    """The division+month counter every on-call constraints, roster and day-stations write takes its version
    number from, and the record of what each version wrote."""

    def __init__(self, db: Session):
        self.db = db

    def division_of(self, unit_id: UUID) -> Optional[UUID]:
        return self.db.query(Unit.division_id).filter(Unit.id == unit_id).scalar()

    def _allocate(self, division_id: UUID, month: str, created_by: Optional[UUID]) -> OnCallSchedulingVersion:
        """Inserts the division+month's next version. Locking the latest row serializes concurrent saves; two
        racing first-ever saves collide on the unique key instead."""
        latest = (
            self.db.query(OnCallSchedulingVersion)
            .filter(OnCallSchedulingVersion.division_id == division_id, OnCallSchedulingVersion.month == month)
            .order_by(OnCallSchedulingVersion.version.desc())
            .with_for_update()
            .first()
        )
        row = OnCallSchedulingVersion(
            division_id=division_id, month=month, version=(latest.version if latest else 0) + 1, created_by=created_by,
        )
        self.db.add(row)
        self.db.flush()
        return row

    def record(self, version_row: OnCallSchedulingVersion, unit_id: UUID, kind: OnCallVersionKind) -> None:
        """Marks the unit's entity as written by this version."""
        self.db.add(OnCallSchedulingVersionEntity(scheduling_version_id=version_row.id, unit_id=unit_id, kind=kind))

    def transaction(
        self, division_id: UUID, month: str, created_by: Optional[UUID], body: Callable[[OnCallSchedulingVersion], T],
    ) -> T:
        """Allocates a new version, runs `body` (which writes entities under it, without committing) and commits
        it all at once — or none of it."""
        try:
            version_row = self._allocate(division_id, month, created_by)
            result = body(version_row)
            self.db.flush()
            version = version_row.version
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise OnCallVersionConflictError("on_call_version_conflict", "Concurrent update detected — please retry")
        except Exception:
            self.db.rollback()
            raise
        logger.info("Saved on-call scheduling version %d (division_id=%s, month=%s)", version, division_id, month)
        return result

    def resolve(self, unit_id: UUID, month: str, kind: OnCallVersionKind, at_most: int) -> Optional[int]:
        """The unit's latest version of `kind` at or below `at_most`, or None if none was saved by then."""
        return (
            self.db.query(func.max(OnCallSchedulingVersion.version))
            .join(OnCallSchedulingVersionEntity, OnCallSchedulingVersionEntity.scheduling_version_id == OnCallSchedulingVersion.id)
            .filter(
                OnCallSchedulingVersionEntity.unit_id == unit_id,
                OnCallSchedulingVersionEntity.kind == kind,
                OnCallSchedulingVersion.month == month,
                OnCallSchedulingVersion.version <= at_most,
            )
            .scalar()
        )

    def get_history(self, division_id: UUID, month: str) -> list[OnCallSchedulingVersion]:
        """Every version of the division+month with what it wrote, newest first."""
        return (
            self.db.query(OnCallSchedulingVersion)
            .options(selectinload(OnCallSchedulingVersion.entities))
            .filter(OnCallSchedulingVersion.division_id == division_id, OnCallSchedulingVersion.month == month)
            .order_by(OnCallSchedulingVersion.version.desc())
            .all()
        )

    def get_version(self, division_id: UUID, month: str, version: int) -> Optional[OnCallSchedulingVersion]:
        return (
            self.db.query(OnCallSchedulingVersion)
            .options(selectinload(OnCallSchedulingVersion.entities))
            .filter(
                OnCallSchedulingVersion.division_id == division_id,
                OnCallSchedulingVersion.month == month,
                OnCallSchedulingVersion.version == version,
            )
            .first()
        )
