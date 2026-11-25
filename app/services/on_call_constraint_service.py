import logging
from collections import defaultdict
from typing import Optional
from uuid import UUID

from app.models.models import ConstraintTypeScope, OnCallSchedulingVersion, OnCallVersionKind
from app.repositories.on_call_constraint_repository import OnCallConstraintRepository, row_key
from app.repositories.on_call_scheduling_version_repository import OnCallSchedulingVersionRepository
from app.repositories.on_call_submission_repository import OnCallSubmissionRepository
from app.services.constraint_service import get_users_comments
from app.services.constraint_type_service import ConstraintTypeService
from app.services.external_on_call_physician_service import ExternalOnCallPhysicianService
from app.services.staff_member_submission_metadata_service import StaffMemberSubmissionMetadataService
from app.services.staff_service import StaffService
from app.schemas.schemas import MonthlyOnCallConstraintsUpdate, OnCallConstraintEntry, SubmissionFeature
from app.context import get_current_user_label

logger = logging.getLogger(__name__)


class OnCallConstraintService:
    """The monthly on-call constraints calendar: per date, which of the unit's
    on-call residents — its staff members and its external on-call
    physicians, both listed in `staff_member_ids` — want (2) / prefer (1) /
    prefer not (-1) / can't (-2) be on call, or can't for a hard reason (an
    on-call constraint type, e.g. vacation). Anyone not listed on a date
    "can" (0)."""

    def __init__(
        self,
        repository: OnCallConstraintRepository,
        submission_repository: OnCallSubmissionRepository,
        submission_metadata_service: StaffMemberSubmissionMetadataService,
        constraint_type_service: ConstraintTypeService,
        staff_service: StaffService,
        external_physician_service: ExternalOnCallPhysicianService,
        version_repository: OnCallSchedulingVersionRepository,
    ):
        self.repository = repository
        self.version_repository = version_repository
        self.submission_repository = submission_repository
        self.submission_metadata_service = submission_metadata_service
        self.constraint_type_service = constraint_type_service
        self.staff_service = staff_service
        self.external_physician_service = external_physician_service

    def get_monthly_constraints(self, unit_id: UUID, month: str, version: Optional[int] = None):
        """The month's constraints — as of the shared on-call scheduling `version` when given (its latest version at
        or below it; none if nothing was saved by then), else the latest."""
        if version is not None:
            resolved = self.version_repository.resolve(unit_id, month, OnCallVersionKind.CONSTRAINTS, version)
            rows = self.repository.get_by_version(unit_id, month, resolved) if resolved else []
        else:
            rows = self.repository.get_by_month(unit_id, month)
        submissions = self.submission_repository.get_by_unit_month(unit_id, month)
        return {"constraints": rows, "user_comments": get_users_comments(submissions, lambda s: s.submitter_id)}

    def get_version_history(self, unit_id: UUID, month: str):
        return self.repository.get_version_history(unit_id, month)

    def _division_of(self, unit_id: UUID) -> UUID:
        division_id = self.version_repository.division_of(unit_id)
        if not division_id:
            raise ValueError("Unit not found")
        return division_id

    def validate_entries(self, unit_id: UUID, month: str, account_id: UUID, entries: list[OnCallConstraintEntry]) -> None:
        """Rejects (ValueError) entries outside the month, duplicates, unknown types or residents."""
        type_ids: set = set()
        staff_ids: set = set()
        seen_keys: set = set()
        members_by_date: dict = defaultdict(set)
        for entry in entries:
            if entry.date.strftime("%Y-%m") != month:
                raise ValueError(f"Entry date {entry.date} is not in month {month}")
            key = row_key(entry.type_id, entry.preference, entry.date)
            if key in seen_keys:
                raise ValueError(f"Duplicate on-call constraint entry on {entry.date}")
            seen_keys.add(key)
            if entry.type_id is not None:
                type_ids.add(entry.type_id)
            for staff_id in entry.staff_member_ids:
                # A member has a single on-call value per date.
                if staff_id in members_by_date[entry.date]:
                    raise ValueError(f"Staff member {staff_id} has more than one on-call constraint on {entry.date}")
                members_by_date[entry.date].add(staff_id)
            staff_ids.update(entry.staff_member_ids)

        existing_type_ids = self.constraint_type_service.get_existing_ids(
            list(type_ids), account_id, ConstraintTypeScope.ON_CALL,
        )
        if type_ids - existing_type_ids:
            raise ValueError("On-call constraint type not found")

        unknown_ids = staff_ids - self.staff_service.get_unit_member_ids(list(staff_ids), unit_id)
        if unknown_ids - self.external_physician_service.get_unit_physician_ids(list(unknown_ids), unit_id):
            raise ValueError("Staff member not found")

    def write_entries(
        self, unit_id: UUID, month: str, entries: list[OnCallConstraintEntry], created_by: Optional[UUID],
        version_row: OnCallSchedulingVersion,
    ):
        """Writes validated entries under a shared version being saved (committed by the caller)."""
        rows = self.repository.save_entries_snapshot(unit_id, month, entries, created_by, version_row.version)
        self.version_repository.record(version_row, unit_id, OnCallVersionKind.CONSTRAINTS)
        return rows

    def update_monthly_constraints(
        self, unit_id: UUID, month: str, account_id: UUID, data: MonthlyOnCallConstraintsUpdate,
        created_by: Optional[UUID],
    ):
        self.validate_entries(unit_id, month, account_id, data.entries)
        rows = self.version_repository.transaction(
            self._division_of(unit_id), month, created_by,
            lambda version_row: self.write_entries(unit_id, month, data.entries, created_by, version_row),
        )
        logger.info(
            "Saved monthly on-call constraints snapshot: %d entries (unit_id=%s, month=%s) by %s",
            len(rows), unit_id, month, get_current_user_label(),
        )
        return rows

    def pull_member_submissions(self, unit_id: UUID, month: str, created_by: Optional[UUID]):
        """Merges every submitter's — staff member's or external physician's — on-call wishes (`preference` /
        `constraint_type_id` on their on-call submission rows) into the
        on-call constraints calendar. Manually-added members are kept;
        members who came from a previous pull are replaced by today's
        submissions — the same provenance rules as ConstraintService's pull."""
        submissions = self.submission_repository.get_by_unit_month(unit_id, month)
        existing = self.repository.get_by_month(unit_id, month)

        submitted: dict = defaultdict(list)
        submitted_members_by_date: dict = defaultdict(set)
        for s in submissions:
            if s.date is None or (s.preference is None and s.constraint_type_id is None):
                continue
            submitted[row_key(s.constraint_type_id, s.preference, s.date)].append(s.submitter_id)
            submitted_members_by_date[s.date].add(s.submitter_id)

        merged: dict = {}
        submitted_ids_by_key: dict = {}
        for row in existing:
            key = row_key(row.type_id, row.preference, row.date)
            # A member's own submission for the date overrides an admin's manual value,
            # so each member keeps a single value per date.
            kept = [
                sid for sid in row.staff_member_ids
                if sid not in row.submitted_staff_member_ids and sid not in submitted_members_by_date[row.date]
            ]
            if kept:
                merged[key] = kept
                submitted_ids_by_key[key] = []  # whatever's left is manual, by construction
        for key, staff_ids in submitted.items():
            target = merged.setdefault(key, [])
            for staff_id in staff_ids:
                if staff_id not in target:
                    target.append(staff_id)
            submitted_ids_by_key[key] = list(staff_ids)

        entries = [
            OnCallConstraintEntry(date=entry_date, type_id=type_id, preference=preference, staff_member_ids=staff_ids)
            for (type_id, preference, entry_date), staff_ids in merged.items()
        ]

        def write(version_row: OnCallSchedulingVersion):
            written = self.repository.save_entries_snapshot(
                unit_id, month, entries, created_by, version_row.version, carry_forward_untouched=False,
                submitted_staff_member_ids_by_key=submitted_ids_by_key,
            )
            self.version_repository.record(version_row, unit_id, OnCallVersionKind.CONSTRAINTS)
            return written

        rows = self.version_repository.transaction(self._division_of(unit_id), month, created_by, write)
        self.submission_metadata_service.mark_pulled(unit_id, month, SubmissionFeature.on_call_constraints, created_by)
        logger.info(
            "Pulled %d submission-derived entries into on-call constraints (unit_id=%s, month=%s) by %s",
            len(rows), unit_id, month, get_current_user_label(),
        )
        return {"constraints": rows, "user_comments": get_users_comments(submissions, lambda s: s.submitter_id)}
