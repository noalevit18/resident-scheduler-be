from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.models import StaffMemberOnCallSubmission
from app.schemas.schemas import OnCallSubmissionEntry


@dataclass(frozen=True)
class OnCallSubmitter:
    """Whose on-call submission a row is: a staff member of the unit or one of
    its external on-call physicians — exactly one of the two ids is set."""
    staff_member_id: Optional[UUID] = None
    external_physician_id: Optional[UUID] = None

    def __post_init__(self) -> None:
        if (self.staff_member_id is None) == (self.external_physician_id is None):
            raise ValueError("An on-call submitter is either a staff member or an external physician")

    def __str__(self) -> str:
        if self.staff_member_id is not None:
            return f"staff_member_id={self.staff_member_id}"
        return f"external_physician_id={self.external_physician_id}"


class OnCallSubmissionRepository:
    """Self-serve on-call constraints (`staff_member_on_call_submissions`) of
    staff members and external on-call physicians."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_submitter_month(self, unit_id: UUID, submitter: OnCallSubmitter, month: str):
        if submitter.staff_member_id is not None:
            submitter_filter = StaffMemberOnCallSubmission.staff_member_id == submitter.staff_member_id
        else:
            submitter_filter = StaffMemberOnCallSubmission.external_physician_id == submitter.external_physician_id
        return self.db.query(StaffMemberOnCallSubmission).filter(
            StaffMemberOnCallSubmission.unit_id == unit_id,
            submitter_filter,
            StaffMemberOnCallSubmission.month == month,
        ).order_by(StaffMemberOnCallSubmission.date).all()

    def get_by_unit_month(self, unit_id: UUID, month: str):
        """Every submitter's rows — staff members' and external physicians'."""
        return self.db.query(StaffMemberOnCallSubmission).filter(
            StaffMemberOnCallSubmission.unit_id == unit_id,
            StaffMemberOnCallSubmission.month == month,
        ).all()

    def get_submitted_ids(self, unit_id: UUID, month: str) -> tuple[set[UUID], set[UUID]]:
        """(staff member ids, external physician ids) that submitted this month."""
        rows = self.db.query(
            StaffMemberOnCallSubmission.staff_member_id, StaffMemberOnCallSubmission.external_physician_id,
        ).filter(
            StaffMemberOnCallSubmission.unit_id == unit_id,
            StaffMemberOnCallSubmission.month == month,
        ).distinct().all()
        staff_ids = {staff_id for staff_id, _ in rows if staff_id is not None}
        external_ids = {external_id for _, external_id in rows if external_id is not None}
        return staff_ids, external_ids

    def replace_month(
        self, unit_id: UUID, submitter: OnCallSubmitter, month: str, entries: List[OnCallSubmissionEntry],
        submitted_empty: bool = False,
    ):
        """Replaces the submitter's whole month: dates in `entries` are upserted,
        other dates are deleted. The general-comment row (date IS NULL) is
        always left behind — it marks the form as submitted, even if empty."""
        existing_rows = self.get_by_submitter_month(unit_id, submitter, month)
        rows_by_date = {row.date: row for row in existing_rows if row.date is not None}
        comment_row = next((row for row in existing_rows if row.date is None), None)

        def new_row(row_date) -> StaffMemberOnCallSubmission:
            row = StaffMemberOnCallSubmission(
                unit_id=unit_id,
                staff_member_id=submitter.staff_member_id,
                external_physician_id=submitter.external_physician_id,
                month=month,
                date=row_date,
            )
            self.db.add(row)
            return row

        seen_dates = set()
        results = []
        for entry in entries:
            if entry.date is None:
                if comment_row is None:
                    comment_row = new_row(None)
                comment_row.comment = entry.comment or None
                continue

            seen_dates.add(entry.date)
            row = rows_by_date.get(entry.date)
            if row is None:
                row = new_row(entry.date)
                rows_by_date[entry.date] = row
            row.preference = entry.preference
            row.constraint_type_id = entry.constraint_type_id
            row.comment = entry.comment or None
            results.append(row)

        for date_key, row in rows_by_date.items():
            if date_key not in seen_dates:
                self.db.delete(row)

        if comment_row is None:
            comment_row = new_row(None)
        comment_row.submitted_empty = submitted_empty
        results.append(comment_row)

        now = datetime.now(timezone.utc)
        for row in results:
            row.updated_at = now

        self.db.commit()
        return results
