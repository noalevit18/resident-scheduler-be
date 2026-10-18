from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.models import FridayMode, StaffMemberSubmissionMetadata, SubmissionFeature


class StaffMemberSubmissionMetadataRepository:

    def __init__(self, db: Session):
        self.db = db

    def get_by_unit_month(self, unit_id: UUID, month: str):
        return self.db.query(StaffMemberSubmissionMetadata).filter(
            StaffMemberSubmissionMetadata.unit_id == unit_id,
            StaffMemberSubmissionMetadata.month == month,
        ).first()

    def upsert(
        self, unit_id: UUID, month: str, start_time, end_time, updated_by: Optional[UUID],
        friday_mode: Optional[FridayMode] = None,
    ):
        row = self.get_by_unit_month(unit_id, month)
        if row:
            row.start_time = start_time
            row.end_time = end_time
            row.updated_by = updated_by
        else:
            row = StaffMemberSubmissionMetadata(
                unit_id=unit_id, month=month,
                start_time=start_time, end_time=end_time, updated_by=updated_by,
            )
            self.db.add(row)
        if friday_mode is not None:
            row.friday_mode = friday_mode
        self.db.commit()
        return row

    def clear_window(self, unit_id: UUID, month: str) -> bool:
        row = self.get_by_unit_month(unit_id, month)
        if not row:
            return False
        row.start_time = None
        row.end_time = None
        self.db.commit()
        return True

    def mark_pulled(self, unit_id: UUID, month: str, feature: SubmissionFeature, pulled_by: Optional[UUID]):
        row = self.get_by_unit_month(unit_id, month)
        if not row:
            return None
        row.pull_information = {
            **row.pull_information,
            feature.value: {
                "pulled_at": datetime.now(timezone.utc).isoformat(),
                "pulled_by": str(pulled_by) if pulled_by else None,
            },
        }
        self.db.commit()
        return row
