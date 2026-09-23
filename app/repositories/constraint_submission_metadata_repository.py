from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.models import ConstraintSubmissionMetadata


class ConstraintSubmissionMetadataRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_unit_month(self, unit_id: UUID, month: str):
        return self.db.query(ConstraintSubmissionMetadata).filter(
            ConstraintSubmissionMetadata.unit_id == unit_id,
            ConstraintSubmissionMetadata.month == month,
        ).first()

    def upsert(self, unit_id: UUID, month: str, start_time, end_time, updated_by: Optional[UUID]):
        row = self.get_by_unit_month(unit_id, month)
        if row:
            row.start_time = start_time
            row.end_time = end_time
            row.updated_by = updated_by
        else:
            row = ConstraintSubmissionMetadata(
                unit_id=unit_id, month=month, start_time=start_time, end_time=end_time, updated_by=updated_by,
            )
            self.db.add(row)
        self.db.commit()
        return row

    def mark_pulled(self, unit_id: UUID, month: str, pulled_by: Optional[UUID]):
        row = self.get_by_unit_month(unit_id, month)
        if not row:
            return None
        row.pulled_at = datetime.now(timezone.utc)
        row.pulled_by = pulled_by
        self.db.commit()
        return row
