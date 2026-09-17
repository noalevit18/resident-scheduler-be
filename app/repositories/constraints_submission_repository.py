from datetime import datetime, timezone
from typing import List
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.models import ConstraintsSubmission
from app.schemas.schemas import ConstraintSubmissionEntry


class ConstraintsSubmissionRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_member_month(self, unit_id: UUID, staff_member_id: UUID, month: str):
        return self.db.query(ConstraintsSubmission).filter(
            ConstraintsSubmission.unit_id == unit_id,
            ConstraintsSubmission.staff_member_id == staff_member_id,
            ConstraintsSubmission.month == month,
        ).order_by(ConstraintsSubmission.date).all()

    def get_by_unit_month(self, unit_id: UUID, month: str):
        """Every staff member's submission rows for the whole unit+month —
        used to pull submissions in bulk into the `constraints` calendar."""
        return self.db.query(ConstraintsSubmission).filter(
            ConstraintsSubmission.unit_id == unit_id,
            ConstraintsSubmission.month == month,
        ).all()

    def get_submitted_staff_ids(self, unit_id: UUID, month: str):
        rows = self.db.query(ConstraintsSubmission.staff_member_id).filter(
            ConstraintsSubmission.unit_id == unit_id,
            ConstraintsSubmission.month == month,
        ).distinct().all()
        return {r[0] for r in rows}

    def has_member_submitted(self, unit_id: UUID, staff_member_id: UUID, month: str) -> bool:
        return self.db.query(ConstraintsSubmission.id).filter(
            ConstraintsSubmission.unit_id == unit_id,
            ConstraintsSubmission.staff_member_id == staff_member_id,
            ConstraintsSubmission.month == month,
        ).first() is not None

    def upsert_many(
        self, unit_id: UUID, staff_member_id: UUID, month: str, entries: List[ConstraintSubmissionEntry],
        submitted_empty: bool = False,
    ):
        existing_rows = self.get_by_member_month(unit_id, staff_member_id, month)
        rows_by_date = {row.date: row for row in existing_rows if row.date is not None}
        comment_row = next((row for row in existing_rows if row.date is None), None)

        seen_dates = set()
        results = []
        for entry in entries:
            if entry.date is None:
                comment_text = entry.comment or None
                if comment_row:
                    comment_row.comment = comment_text
                    results.append(comment_row)
                elif comment_text:
                    comment_row = ConstraintsSubmission(
                        unit_id=unit_id, staff_member_id=staff_member_id, month=month,
                        date=None, type_id=None, comment=comment_text,
                    )
                    self.db.add(comment_row)
                    results.append(comment_row)
                continue

            seen_dates.add(entry.date)
            row = rows_by_date.get(entry.date)
            if row:
                row.type_id = entry.type_id
                row.comment = entry.comment or None
            else:
                row = ConstraintsSubmission(
                    unit_id=unit_id, staff_member_id=staff_member_id, month=month,
                    date=entry.date, type_id=entry.type_id, comment=entry.comment or None,
                )
                self.db.add(row)
                rows_by_date[entry.date] = row
            results.append(row)

        for date_key, row in rows_by_date.items():
            if date_key not in seen_dates:
                self.db.delete(row)
                if row in results:
                    results.remove(row)

        # Every call leaves at least the general-comment row (date IS NULL) behind.
        # That marks that this member submitted the constraints form for this month, even if all the dates are empty.
        if comment_row is None:
            comment_row = ConstraintsSubmission(
                unit_id=unit_id, staff_member_id=staff_member_id, month=month,
                date=None, type_id=None, comment=None,
            )
            self.db.add(comment_row)
        comment_row.submitted_empty = submitted_empty
        if comment_row not in results:
            results.append(comment_row)

        now = datetime.now(timezone.utc)
        for row in results:
            row.updated_at = now

        self.db.commit()
        return results
