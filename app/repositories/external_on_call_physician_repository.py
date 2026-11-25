from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.models import ExternalOnCallPhysician
from app.schemas.schemas import ExternalOnCallPhysicianCreate


class ExternalOnCallPhysicianRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_all(self, unit_id: UUID, include_archived: bool = False) -> list[ExternalOnCallPhysician]:
        query = self.db.query(ExternalOnCallPhysician).filter(ExternalOnCallPhysician.unit_id == unit_id)
        if not include_archived:
            query = query.filter(ExternalOnCallPhysician.archived_at.is_(None))
        return query.order_by(ExternalOnCallPhysician.name).all()

    def get_by_id(self, physician_id: UUID, unit_id: UUID) -> Optional[ExternalOnCallPhysician]:
        """Includes archived physicians."""
        return self.db.query(ExternalOnCallPhysician).filter(
            ExternalOnCallPhysician.id == physician_id, ExternalOnCallPhysician.unit_id == unit_id,
        ).first()

    def get_by_user_id(self, user_id: UUID, unit_id: UUID) -> Optional[ExternalOnCallPhysician]:
        """Active physicians only (a user has at most one active per unit)."""
        return self.db.query(ExternalOnCallPhysician).filter(
            ExternalOnCallPhysician.user_id == user_id,
            ExternalOnCallPhysician.unit_id == unit_id,
            ExternalOnCallPhysician.archived_at.is_(None),
        ).first()

    def get_all_by_user_id(self, user_id: UUID, unit_id: UUID) -> list[ExternalOnCallPhysician]:
        """Includes archived physicians — one user may have been connected to several over time."""
        return self.db.query(ExternalOnCallPhysician).filter(
            ExternalOnCallPhysician.user_id == user_id,
            ExternalOnCallPhysician.unit_id == unit_id,
        ).all()

    def get_by_ids(self, ids: list[UUID], unit_id: UUID) -> dict[UUID, ExternalOnCallPhysician]:
        """Includes archived physicians — past shifts keep referencing them."""
        if not ids:
            return {}
        rows = self.db.query(ExternalOnCallPhysician).filter(
            ExternalOnCallPhysician.id.in_(ids), ExternalOnCallPhysician.unit_id == unit_id,
        ).all()
        return {row.id: row for row in rows}

    def create(
        self, unit_id: UUID, data: ExternalOnCallPhysicianCreate, created_by: Optional[UUID],
    ) -> ExternalOnCallPhysician:
        obj = ExternalOnCallPhysician(
            unit_id=unit_id, name=data.name, user_id=data.user_id, created_by=created_by,
            activation_date=data.activation_date,
        )
        self.db.add(obj)
        self._commit()
        self.db.refresh(obj)
        return obj

    def update(self, obj: ExternalOnCallPhysician, fields: dict[str, Any]) -> ExternalOnCallPhysician:
        for key, value in fields.items():
            setattr(obj, key, value)
        self._commit()
        self.db.refresh(obj)
        return obj

    def set_archived(
        self, obj: ExternalOnCallPhysician, archived_at: Optional[datetime], archived_by: Optional[UUID],
    ) -> ExternalOnCallPhysician:
        """archived_at=None (and archived_by=None) unarchives."""
        obj.archived_at = archived_at
        obj.archived_by = archived_by
        self._commit()
        self.db.refresh(obj)
        return obj

    def _commit(self) -> None:
        """Rolls back on failure so the session stays usable (e.g. after a
        unique-index violation the service turns into a 409)."""
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
