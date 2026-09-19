import logging
from collections import defaultdict
from typing import Optional
from uuid import UUID

from app.repositories.constraint_repository import ConstraintRepository
from app.repositories.constraints_submission_repository import ConstraintsSubmissionRepository
from app.services.constraint_submission_metadata_service import ConstraintSubmissionMetadataService
from app.services.constraint_type_service import ConstraintTypeService
from app.services.staff_service import StaffService
from app.schemas.schemas import (
    ConstraintEntry, MonthlyConstraintsUpdate, ConstraintUserComment, ConstraintUserComments,
)
from app.context import get_current_user_label

logger = logging.getLogger(__name__)


class ConstraintService:
    def __init__(
        self,
        repository: ConstraintRepository,
        submission_repository: ConstraintsSubmissionRepository,
        submission_metadata_service: ConstraintSubmissionMetadataService,
        constraint_type_service: ConstraintTypeService,
        staff_service: StaffService,
    ):
        self.repository = repository
        self.submission_repository = submission_repository
        self.submission_metadata_service = submission_metadata_service
        self.constraint_type_service = constraint_type_service
        self.staff_service = staff_service

    def get_users_comments(self, submissions) -> list[ConstraintUserComments]:
        comments_by_member: dict = defaultdict(list)
        for s in submissions:
            if s.comment:
                comments_by_member[s.staff_member_id].append(ConstraintUserComment(date=s.date, comment=s.comment))
        return [
            ConstraintUserComments(staff_member_id=staff_id, comments=entries)
            for staff_id, entries in comments_by_member.items()
        ]

    def get_monthly_constraints(self, unit_id: UUID, month: str, version: int | None = None):
        if version is not None:
            rows = self.repository.get_by_version_id(unit_id, month, version)
        else:
            rows = self.repository.get_by_month(unit_id, month)
        submissions = self.submission_repository.get_by_unit_month(unit_id, month)
        return {"constraints": rows, "user_comments": self.get_users_comments(submissions)}

    def get_version_history(self, unit_id: UUID, month: str):
        return self.repository.get_version_history(unit_id, month)

    def update_monthly_constraints(
        self, unit_id: UUID, month: str, account_id: UUID, data: MonthlyConstraintsUpdate, created_by: Optional[UUID],
    ):
        type_ids: set = set()
        staff_ids: set = set()
        for entry in data.entries:
            if entry.date.strftime("%Y-%m") != month:
                raise ValueError(f"Entry date {entry.date} is not in month {month}")
            type_ids.add(entry.type_id)
            staff_ids.update(entry.staff_member_ids)

        existing_type_ids = self.constraint_type_service.get_existing_ids(list(type_ids), account_id)
        if type_ids - existing_type_ids:
            raise ValueError("Constraint type not found")

        existing_staff_ids = self.staff_service.get_unit_member_ids(list(staff_ids), unit_id)
        if staff_ids - existing_staff_ids:
            raise ValueError("Staff member not found")

        rows = self.repository.save_entries_snapshot(unit_id, month, data.entries, created_by)
        logger.info(
            "Saved monthly constraints snapshot: %d entries (unit_id=%s, month=%s) by %s",
            len(rows), unit_id, month, get_current_user_label(),
        )
        return rows

    def pull_member_submissions(self, unit_id: UUID, month: str, created_by: Optional[UUID]):
        """Processes every staff member's `constraints_submissions` rows for
        this unit+month into the official `constraints` calendar."""
        submissions = self.submission_repository.get_by_unit_month(unit_id, month)
        existing = self.repository.get_by_month(unit_id, month)
        user_comments = self.get_users_comments(submissions)

        submitted: dict = defaultdict(list)
        for s in submissions:
            if s.date is None or s.type_id is None:
                continue
            submitted[(s.type_id, s.date)].append(s.staff_member_id)

        merged: dict = {}
        submitted_ids_by_key: dict = {}
        for row in existing:
            key = (row.type_id, row.date)
            kept = [sid for sid in row.staff_member_ids if sid not in row.submitted_staff_member_ids]
            if kept:
                merged[key] = kept
                submitted_ids_by_key[key] = []  # whatever's left is manual, by construction
        for key, staff_ids in submitted.items():
            target = merged.setdefault(key, [])
            for staff_id in staff_ids:
                if staff_id not in target:
                    target.append(staff_id)
            submitted_ids_by_key[key] = list(staff_ids)  # this pair's provenance is exactly today's submitters

        entries = [
            ConstraintEntry(type_id=type_id, date=entry_date, staff_member_ids=staff_ids)
            for (type_id, entry_date), staff_ids in merged.items()
        ]

        rows = self.repository.save_entries_snapshot(
            unit_id, month, entries, created_by, carry_forward_untouched=False,
            submitted_staff_member_ids_by_key=submitted_ids_by_key,
        )
        self.submission_metadata_service.mark_pulled(unit_id, month, created_by)
        logger.info(
            "Pulled %d submission-derived entries into constraints (unit_id=%s, month=%s) by %s",
            len(rows), unit_id, month, get_current_user_label(),
        )
        return {"constraints": rows, "user_comments": user_comments}
