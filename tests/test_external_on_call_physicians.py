from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from app.models.models import ExternalOnCallPhysician
from app.schemas.schemas import (
    ExternalOnCallPhysicianCreate,
    ExternalOnCallPhysicianResponse,
    ExternalOnCallPhysicianUpdate,
)
from app.services.external_on_call_physician_service import (
    USER_INDEX,
    ExternalOnCallPhysicianConflictError,
    ExternalOnCallPhysicianError,
    ExternalOnCallPhysicianNotFoundError,
    ExternalOnCallPhysicianService,
)


# --- Schemas ---

def test_create_requires_a_name_and_trims_it() -> None:
    with pytest.raises(ValidationError):
        ExternalOnCallPhysicianCreate.model_validate({"unitId": str(UNIT), "userId": str(uuid4()), "activationDate": "2026-12-01"})
    with pytest.raises(ValidationError):
        ExternalOnCallPhysicianCreate(unit_id=UNIT, activation_date=ACTIVATION, name="   ")
    assert ExternalOnCallPhysicianCreate(unit_id=UNIT, activation_date=ACTIVATION, name="  Dr. Cohen ").name == "Dr. Cohen"


def test_create_accepts_camel_case_user_id() -> None:
    user_id = uuid4()
    data = ExternalOnCallPhysicianCreate.model_validate({"unitId": str(UNIT), "name": "Dr. Levi", "userId": str(user_id), "activationDate": "2026-12-01"})
    assert data.user_id == user_id


def test_update_rejects_null_name_but_allows_clearing_user() -> None:
    with pytest.raises(ValidationError):
        ExternalOnCallPhysicianUpdate.model_validate({"name": None})
    update = ExternalOnCallPhysicianUpdate.model_validate({"userId": None})
    assert update.model_dump(exclude_unset=True) == {"user_id": None}


# --- Service (fake repository) ---

class _FakeOrig(Exception):
    pass


def _integrity_error(index_name: str) -> IntegrityError:
    return IntegrityError("INSERT ...", {}, _FakeOrig(f'duplicate key value violates unique constraint "{index_name}"'))


class FakeRepository:
    def __init__(self) -> None:
        self.rows: dict[UUID, ExternalOnCallPhysician] = {}

    def _check_unique(self, obj: ExternalOnCallPhysician) -> None:
        for other in self.rows.values():
            if other.id == obj.id or other.archived_at is not None or other.unit_id != obj.unit_id:
                continue
            if obj.user_id is not None and other.user_id == obj.user_id:
                raise _integrity_error(USER_INDEX)

    def get_all(self, unit_id: UUID, include_archived: bool = False) -> list[ExternalOnCallPhysician]:
        rows = [r for r in self.rows.values() if r.unit_id == unit_id]
        if not include_archived:
            rows = [r for r in rows if r.archived_at is None]
        return sorted(rows, key=lambda r: r.name)

    def get_by_id(self, physician_id: UUID, unit_id: UUID) -> Optional[ExternalOnCallPhysician]:
        row = self.rows.get(physician_id)
        return row if row and row.unit_id == unit_id else None

    def get_by_user_id(self, user_id: UUID, unit_id: UUID) -> Optional[ExternalOnCallPhysician]:
        return next(
            (r for r in self.rows.values() if r.user_id == user_id and r.unit_id == unit_id and r.archived_at is None),
            None,
        )

    def get_by_ids(self, ids: list[UUID], unit_id: UUID) -> dict[UUID, ExternalOnCallPhysician]:
        return {i: self.rows[i] for i in ids if i in self.rows and self.rows[i].unit_id == unit_id}

    def create(self, unit_id: UUID, data: ExternalOnCallPhysicianCreate, created_by: Optional[UUID]) -> ExternalOnCallPhysician:
        obj = ExternalOnCallPhysician(
            id=uuid4(), unit_id=unit_id, name=data.name, user_id=data.user_id,
            created_by=created_by, created_at=datetime.now(timezone.utc), archived_at=None, archived_by=None,
            activation_date=data.activation_date,
        )
        self._check_unique(obj)
        self.rows[obj.id] = obj
        return obj

    def update(self, obj: ExternalOnCallPhysician, fields: dict[str, Any]) -> ExternalOnCallPhysician:
        candidate = ExternalOnCallPhysician(
            id=obj.id, unit_id=obj.unit_id, archived_at=obj.archived_at,
            name=fields.get("name", obj.name), user_id=fields.get("user_id", obj.user_id),
        )
        self._check_unique(candidate)
        for key, value in fields.items():
            setattr(obj, key, value)
        return obj

    def set_archived(
        self, obj: ExternalOnCallPhysician, archived_at: Optional[datetime], archived_by: Optional[UUID],
    ) -> ExternalOnCallPhysician:
        if archived_at is None:
            candidate = ExternalOnCallPhysician(id=obj.id, unit_id=obj.unit_id, name=obj.name, user_id=obj.user_id, archived_at=None)
            self._check_unique(candidate)
        obj.archived_at = archived_at
        obj.archived_by = archived_by
        return obj


UNIT = uuid4()
OTHER_UNIT = uuid4()
ADMIN = uuid4()
USER = uuid4()
DIVISION_USER = uuid4()  # a division-based user (no unit), like most users
ACTIVATION = date(2026, 12, 1)


def _service() -> ExternalOnCallPhysicianService:
    return ExternalOnCallPhysicianService(FakeRepository())  # type: ignore[arg-type]


def test_create_sets_creator_and_is_active() -> None:
    service = _service()
    physician = service.create(UNIT, ExternalOnCallPhysicianCreate(unit_id=UNIT, activation_date=ACTIVATION, name="Dr. Cohen", user_id=USER), ADMIN)
    assert (physician.unit_id, physician.created_by, physician.user_id, physician.archived_at) == (UNIT, ADMIN, USER, None)
    response = ExternalOnCallPhysicianResponse.model_validate(physician)
    assert response.name == "Dr. Cohen"


def test_any_existing_user_can_be_connected_like_staff() -> None:
    """No unit/division membership check (same as staff members): a
    division-based user without a unit can be connected."""
    service = _service()
    physician = service.create(UNIT, ExternalOnCallPhysicianCreate(unit_id=UNIT, activation_date=ACTIVATION, name="Dr. Cohen", user_id=DIVISION_USER), ADMIN)
    assert physician.user_id == DIVISION_USER
    assert service.get_by_user_id(DIVISION_USER, UNIT) is physician
    assert service.get_by_user_id(DIVISION_USER, OTHER_UNIT) is None


def test_same_name_is_allowed_but_duplicate_active_user_conflicts() -> None:
    service = _service()
    service.create(UNIT, ExternalOnCallPhysicianCreate(unit_id=UNIT, activation_date=ACTIVATION, name="Dr. Cohen", user_id=USER), ADMIN)
    namesake = service.create(UNIT, ExternalOnCallPhysicianCreate(unit_id=UNIT, activation_date=ACTIVATION, name="Dr. Cohen"), ADMIN)
    assert namesake.name == "Dr. Cohen"
    assert len(service.get_all(UNIT)) == 2
    with pytest.raises(ExternalOnCallPhysicianConflictError) as exc:
        service.create(UNIT, ExternalOnCallPhysicianCreate(unit_id=UNIT, activation_date=ACTIVATION, name="Dr. Levi", user_id=USER), ADMIN)
    assert exc.value.code == "external_physician_duplicate_user"


def test_archive_hides_from_list_and_unarchive_restores() -> None:
    service = _service()
    physician = service.create(UNIT, ExternalOnCallPhysicianCreate(unit_id=UNIT, activation_date=ACTIVATION, name="Dr. Cohen"), ADMIN)
    archived = service.archive(physician.id, UNIT, ADMIN)
    assert archived.archived_at is not None
    assert archived.archived_by == ADMIN
    assert ExternalOnCallPhysicianResponse.model_validate(archived).archived_by == ADMIN
    assert service.get_all(UNIT) == []
    assert [p.id for p in service.get_all(UNIT, include_archived=True)] == [physician.id]
    assert service.get_by_ids([physician.id], UNIT).keys() == {physician.id}

    restored = service.unarchive(physician.id, UNIT)
    assert (restored.archived_at, restored.archived_by) == (None, None)
    assert [p.id for p in service.get_all(UNIT)] == [physician.id]


def test_archived_user_can_be_reconnected_but_blocks_unarchive() -> None:
    service = _service()
    first = service.create(UNIT, ExternalOnCallPhysicianCreate(unit_id=UNIT, activation_date=ACTIVATION, name="Dr. Cohen", user_id=USER), ADMIN)
    service.archive(first.id, UNIT, ADMIN)
    service.create(UNIT, ExternalOnCallPhysicianCreate(unit_id=UNIT, activation_date=ACTIVATION, name="Dr. Levi", user_id=USER), ADMIN)
    with pytest.raises(ExternalOnCallPhysicianConflictError) as exc:
        service.unarchive(first.id, UNIT)
    assert exc.value.code == "external_physician_duplicate_user"


def test_update_archived_physician_is_rejected() -> None:
    service = _service()
    physician = service.create(UNIT, ExternalOnCallPhysicianCreate(unit_id=UNIT, activation_date=ACTIVATION, name="Dr. Cohen"), ADMIN)
    service.archive(physician.id, UNIT, ADMIN)
    with pytest.raises(ExternalOnCallPhysicianError) as exc:
        service.update(physician.id, UNIT, {"name": "Dr. Levi"})
    assert exc.value.code == "external_physician_archived"


def test_update_changes_and_clears_user() -> None:
    service = _service()
    physician = service.create(UNIT, ExternalOnCallPhysicianCreate(unit_id=UNIT, activation_date=ACTIVATION, name="Dr. Cohen"), ADMIN)
    updated = service.update(physician.id, UNIT, {"name": "Dr. Levi", "user_id": USER})
    assert (updated.name, updated.user_id) == ("Dr. Levi", USER)
    cleared = service.update(physician.id, UNIT, {"user_id": None})
    assert cleared.user_id is None
    assert service.update(physician.id, UNIT, {"user_id": DIVISION_USER}).user_id == DIVISION_USER


def test_update_schema_accepts_archived_but_not_null() -> None:
    assert ExternalOnCallPhysicianUpdate.model_validate({"archived": True}).model_dump(exclude_unset=True) == {"archived": True}
    with pytest.raises(ValidationError):
        ExternalOnCallPhysicianUpdate.model_validate({"archived": None})


def test_update_with_archived_flag_archives_and_unarchives() -> None:
    service = _service()
    physician = service.create(UNIT, ExternalOnCallPhysicianCreate(unit_id=UNIT, activation_date=ACTIVATION, name="Dr. Cohen"), ADMIN)
    archived = service.update(physician.id, UNIT, {"archived": True}, ADMIN)
    assert (archived.archived_at is not None, archived.archived_by) == (True, ADMIN)
    assert service.get_all(UNIT) == []
    restored = service.update(physician.id, UNIT, {"archived": False, "name": "Dr. Levi"})
    assert (restored.archived_at, restored.name) == (None, "Dr. Levi")
    archived = service.update(physician.id, UNIT, {"name": "Dr. Katz", "archived": True})
    assert (archived.archived_at is not None, archived.name) == (True, "Dr. Katz")


def test_create_requires_activation_date() -> None:
    with pytest.raises(ValidationError):
        ExternalOnCallPhysicianCreate.model_validate({"unitId": str(UNIT), "name": "Dr. Cohen"})


def test_activation_date_is_kept_as_given_and_can_be_changed() -> None:
    service = _service()
    future = date.today() + timedelta(days=60)
    data = ExternalOnCallPhysicianCreate.model_validate({"unitId": str(UNIT), "name": "Dr. Levi", "activationDate": future.isoformat()})
    physician = service.create(UNIT, data, ADMIN)
    assert ExternalOnCallPhysicianResponse.model_validate(physician).activation_date == future
    updated = service.update(physician.id, UNIT, {"activation_date": date(2027, 1, 1)})
    assert updated.activation_date == date(2027, 1, 1)


def test_update_rejects_null_activation_date() -> None:
    with pytest.raises(ValidationError):
        ExternalOnCallPhysicianUpdate.model_validate({"activationDate": None})
    update = ExternalOnCallPhysicianUpdate.model_validate({"activationDate": "2026-12-01"})
    assert update.model_dump(exclude_unset=True) == {"activation_date": date(2026, 12, 1)}


def test_physician_of_another_unit_is_not_found() -> None:
    service = _service()
    physician = service.create(UNIT, ExternalOnCallPhysicianCreate(unit_id=UNIT, activation_date=ACTIVATION, name="Dr. Cohen"), ADMIN)
    with pytest.raises(ExternalOnCallPhysicianNotFoundError):
        service.archive(physician.id, OTHER_UNIT, ADMIN)
    with pytest.raises(ExternalOnCallPhysicianNotFoundError):
        service.update(physician.id, OTHER_UNIT, {"name": "X"})
