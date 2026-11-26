import logging
from datetime import datetime, timezone
from typing import Any, Callable, Optional
from uuid import UUID

from sqlalchemy.exc import IntegrityError

from app.models.models import ExternalOnCallPhysician
from app.repositories.external_on_call_physician_repository import ExternalOnCallPhysicianRepository
from app.schemas.schemas import ExternalOnCallPhysicianCreate
from app.context import get_current_user_label

logger = logging.getLogger(__name__)

USER_INDEX = "ux_external_on_call_physicians_unit_id_user_id_active"


class ExternalOnCallPhysicianError(Exception):
    """A well-formed request that can't be applied (400)."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


class ExternalOnCallPhysicianNotFoundError(ExternalOnCallPhysicianError):
    """No such physician in the unit (404)."""


class ExternalOnCallPhysicianConflictError(ExternalOnCallPhysicianError):
    """Another active physician in the unit is connected to this user (409)."""


def _conflict_from_integrity_error(error: IntegrityError) -> ExternalOnCallPhysicianConflictError:
    if USER_INDEX in str(error.orig):
        return ExternalOnCallPhysicianConflictError(
            "external_physician_duplicate_user", "This user is already connected to an active external physician",
        )
    return ExternalOnCallPhysicianConflictError(
        "external_physician_conflict", "The external physician conflicts with an existing one",
    )


def is_active_in_month(physician: ExternalOnCallPhysician, month: str) -> bool:
    """Active in a "YYYY-MM" month: activated by the month's end and not
    archived before or during it."""
    if physician.activation_date.strftime("%Y-%m") > month:
        return False
    return physician.archived_at is None or physician.archived_at.strftime("%Y-%m") > month


class ExternalOnCallPhysicianService:
    def __init__(self, repository: ExternalOnCallPhysicianRepository):
        self.repository = repository

    def get_all(self, unit_id: UUID, include_archived: bool = False) -> list[ExternalOnCallPhysician]:
        return self.repository.get_all(unit_id, include_archived)

    def get_active_in_month(self, unit_id: UUID, month: str) -> list[ExternalOnCallPhysician]:
        return [p for p in self.repository.get_all(unit_id, include_archived=True) if is_active_in_month(p, month)]

    def get_active_in_month_by_id(
        self, physician_id: UUID, unit_id: UUID, month: str,
    ) -> Optional[ExternalOnCallPhysician]:
        physician = self.repository.get_by_id(physician_id, unit_id)
        return physician if physician and is_active_in_month(physician, month) else None

    def get_active_in_month_by_user_id(
        self, user_id: UUID, unit_id: UUID, month: str,
    ) -> Optional[ExternalOnCallPhysician]:
        """The physician connected to this user who is active in the month."""
        return next(
            (p for p in self.repository.get_all_by_user_id(user_id, unit_id) if is_active_in_month(p, month)),
            None,
        )

    def get_by_user_id(self, user_id: UUID, unit_id: UUID) -> Optional[ExternalOnCallPhysician]:
        """The active external physician connected to this user in the unit."""
        return self.repository.get_by_user_id(user_id, unit_id)

    def get_by_ids(self, ids: list[UUID], unit_id: UUID) -> dict[UUID, ExternalOnCallPhysician]:
        return self.repository.get_by_ids(ids, unit_id)

    def get_unit_physician_ids(self, ids: list[UUID], unit_id: UUID) -> set[UUID]:
        """Which of `ids` are this unit's external physicians (archived ones included)."""
        return set(self.repository.get_by_ids(ids, unit_id))

    def create(
        self, unit_id: UUID, data: ExternalOnCallPhysicianCreate, created_by: Optional[UUID],
    ) -> ExternalOnCallPhysician:
        physician = self._write(lambda: self.repository.create(unit_id, data, created_by))
        logger.info(
            "Created external on-call physician id=%s (unit_id=%s) by %s",
            physician.id, unit_id, get_current_user_label(),
        )
        return physician

    def update(
        self, physician_id: UUID, unit_id: UUID, fields: dict[str, Any], updated_by: Optional[UUID] = None,
    ) -> ExternalOnCallPhysician:
        """Applies an update payload. An `archived` flag archives/unarchives:
        unarchiving happens before the other fields are applied, archiving
        after (an archived physician's fields can't be edited)."""
        fields = dict(fields)
        archived = fields.pop("archived", None)
        if archived is False:
            self.unarchive(physician_id, unit_id)
        physician = self._get_or_raise(physician_id, unit_id) if not fields else self._update_fields(
            physician_id, unit_id, fields,
        )
        if archived is True:
            physician = self.archive(physician_id, unit_id, updated_by)
        return physician

    def _update_fields(self, physician_id: UUID, unit_id: UUID, fields: dict[str, Any]) -> ExternalOnCallPhysician:
        physician = self._get_or_raise(physician_id, unit_id)
        if physician.archived_at is not None:
            raise ExternalOnCallPhysicianError(
                "external_physician_archived", "An archived external physician cannot be edited",
            )
        physician = self._write(lambda: self.repository.update(physician, fields))
        logger.info(
            "Updated external on-call physician id=%s (unit_id=%s, fields=%s) by %s",
            physician_id, unit_id, sorted(fields), get_current_user_label(),
        )
        return physician

    def archive(self, physician_id: UUID, unit_id: UUID, archived_by: Optional[UUID]) -> ExternalOnCallPhysician:
        physician = self._get_or_raise(physician_id, unit_id)
        if physician.archived_at is not None:
            return physician
        physician = self.repository.set_archived(physician, datetime.now(timezone.utc), archived_by)
        logger.info(
            "Archived external on-call physician id=%s (unit_id=%s) by %s",
            physician_id, unit_id, get_current_user_label(),
        )
        return physician

    def unarchive(self, physician_id: UUID, unit_id: UUID) -> ExternalOnCallPhysician:
        physician = self._get_or_raise(physician_id, unit_id)
        if physician.archived_at is None:
            return physician
        physician = self._write(lambda: self.repository.set_archived(physician, None, None))
        logger.info(
            "Unarchived external on-call physician id=%s (unit_id=%s) by %s",
            physician_id, unit_id, get_current_user_label(),
        )
        return physician

    def _get_or_raise(self, physician_id: UUID, unit_id: UUID) -> ExternalOnCallPhysician:
        physician = self.repository.get_by_id(physician_id, unit_id)
        if not physician:
            raise ExternalOnCallPhysicianNotFoundError(
                "external_physician_not_found", "External physician not found",
            )
        return physician

    @staticmethod
    def _write(operation: Callable[[], ExternalOnCallPhysician]) -> ExternalOnCallPhysician:
        try:
            return operation()
        except IntegrityError as e:
            raise _conflict_from_integrity_error(e) from e
