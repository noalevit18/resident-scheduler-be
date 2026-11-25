from datetime import date, datetime, timezone
from types import SimpleNamespace
from typing import Any, Optional
from uuid import UUID, uuid4

import pytest

from app.models.models import ExternalOnCallPhysician, StaffMemberOnCallSubmission
from app.repositories.on_call_submission_repository import OnCallSubmitter
from app.schemas.schemas import MonthlyOnCallShiftsUpdate, OnCallShiftEntry
from app.services.authorization_service import AuthorizationError
from app.services.external_on_call_physician_service import ExternalOnCallPhysicianService, is_active_in_month
from app.services.on_call_constraint_service import OnCallConstraintService
from app.services.on_call_shift_service import OnCallShiftService, OnCallStationNotOpenToExternalError
from app.services.on_call_submission_service import OnCallSubmissionService
from tests.fake_on_call_versions import FakeVersionRepository

UNIT = uuid4()
MONTH = "2026-12"


def _physician(
    activation: date, archived_at: Optional[datetime] = None, user_id: Optional[UUID] = None, name: str = "Dr. Levi",
) -> ExternalOnCallPhysician:
    return ExternalOnCallPhysician(
        id=uuid4(), unit_id=UNIT, name=name, user_id=user_id, activation_date=activation, archived_at=archived_at,
    )


# --- Active in month ---

@pytest.mark.parametrize(
    "activation, archived_at, expected",
    [
        (date(2026, 12, 31), None, True),  # activated during the month
        (date(2026, 1, 1), None, True),
        (date(2027, 1, 1), None, False),  # not yet activated
        (date(2026, 1, 1), datetime(2027, 1, 3, tzinfo=timezone.utc), True),  # archived after the month
        (date(2026, 1, 1), datetime(2026, 12, 15, tzinfo=timezone.utc), False),  # archived during the month
        (date(2026, 1, 1), datetime(2026, 11, 2, tzinfo=timezone.utc), False),  # archived before the month
    ],
)
def test_is_active_in_month(activation: date, archived_at: Optional[datetime], expected: bool) -> None:
    assert is_active_in_month(_physician(activation, archived_at), MONTH) is expected


def test_submitter_needs_exactly_one_id() -> None:
    with pytest.raises(ValueError):
        OnCallSubmitter()
    with pytest.raises(ValueError):
        OnCallSubmitter(staff_member_id=uuid4(), external_physician_id=uuid4())


# --- Service ---

class FakeSubmissionRepository:
    def __init__(self) -> None:
        self.saved: list[OnCallSubmitter] = []
        self.submitted_externals: set[UUID] = set()

    def get_by_submitter_month(self, unit_id: UUID, submitter: OnCallSubmitter, month: str) -> list[Any]:
        return [submitter]

    def get_submitted_ids(self, unit_id: UUID, month: str) -> tuple[set[UUID], set[UUID]]:
        return set(), self.submitted_externals

    def replace_month(self, unit_id: UUID, submitter: OnCallSubmitter, month: str, entries: list, submitted_empty: bool = False) -> list:
        self.saved.append(submitter)
        return []


class FakeExternalRepository:
    def __init__(self, physicians: list[ExternalOnCallPhysician]) -> None:
        self.physicians = physicians

    def get_all(self, unit_id: UUID, include_archived: bool = False) -> list[ExternalOnCallPhysician]:
        return [p for p in self.physicians if include_archived or p.archived_at is None]

    def get_all_by_user_id(self, user_id: UUID, unit_id: UUID) -> list[ExternalOnCallPhysician]:
        return [p for p in self.physicians if p.user_id == user_id]

    def get_by_ids(self, ids: list[UUID], unit_id: UUID) -> dict[UUID, ExternalOnCallPhysician]:
        return {p.id: p for p in self.physicians if p.id in ids}


class FakeStaffService:
    def __init__(self, staff_by_user: dict[UUID, UUID]) -> None:
        self.staff_by_user = staff_by_user

    def is_logged_in_user_a_staff_member(self, unit_id: UUID, current_user: dict) -> Any:
        staff_id = self.staff_by_user.get(current_user["id"])
        if staff_id is None:
            raise ValueError("Logged-in user has no staff member record in this unit")
        return SimpleNamespace(id=staff_id)

    def get_all_members(self, unit_id: UUID) -> list[Any]:
        return []


class FakeUserService:
    def get_logged_in_user_id(self, current_user: dict) -> Optional[UUID]:
        return current_user["id"]


def _service(
    physicians: list[ExternalOnCallPhysician], staff_by_user: Optional[dict[UUID, UUID]] = None,
) -> tuple[OnCallSubmissionService, FakeSubmissionRepository]:
    repo = FakeSubmissionRepository()
    service = OnCallSubmissionService(
        repo,  # type: ignore[arg-type]
        SimpleNamespace(assert_window_open=lambda *args: None),  # type: ignore[arg-type]
        FakeStaffService(staff_by_user or {}),  # type: ignore[arg-type]
        SimpleNamespace(get_existing_ids_for_unit=lambda *args: set()),  # type: ignore[arg-type]
        ExternalOnCallPhysicianService(FakeExternalRepository(physicians)),  # type: ignore[arg-type]
        FakeUserService(),  # type: ignore[arg-type]
    )
    return service, repo


def test_active_external_physician_submits_as_external() -> None:
    user_id = uuid4()
    physician = _physician(date(2026, 1, 1), user_id=user_id)
    service, repo = _service([physician])
    service.update_member_month(UNIT, MONTH, SimpleNamespace(entries=[]), {"id": user_id})  # type: ignore[arg-type]
    assert repo.saved == [OnCallSubmitter(external_physician_id=physician.id)]
    assert service.is_active_external_physician(UNIT, MONTH, {"id": user_id})


def test_staff_record_wins_over_external_record() -> None:
    user_id, staff_id = uuid4(), uuid4()
    service, repo = _service([_physician(date(2026, 1, 1), user_id=user_id)], {user_id: staff_id})
    service.update_member_month(UNIT, MONTH, SimpleNamespace(entries=[]), {"id": user_id})  # type: ignore[arg-type]
    assert repo.saved == [OnCallSubmitter(staff_member_id=staff_id)]
    assert not service.is_active_external_physician(UNIT, MONTH, {"id": user_id})


def test_external_physician_not_yet_active_cannot_submit() -> None:
    user_id = uuid4()
    service, _ = _service([_physician(date(2027, 1, 1), user_id=user_id)])
    with pytest.raises(ValueError):
        service.update_member_month(UNIT, MONTH, SimpleNamespace(entries=[]), {"id": user_id})  # type: ignore[arg-type]
    assert not service.is_active_external_physician(UNIT, MONTH, {"id": user_id})


def test_external_physician_views_only_their_own_submission() -> None:
    user_id = uuid4()
    mine = _physician(date(2026, 1, 1), user_id=user_id)
    other = _physician(date(2026, 1, 1), user_id=uuid4())
    service, _ = _service([mine, other])
    own = service.get_member_month(UNIT, MONTH, {"id": user_id}, external_physician_id=mine.id)
    assert own == [OnCallSubmitter(external_physician_id=mine.id)]
    with pytest.raises(AuthorizationError):
        service.get_member_month(UNIT, MONTH, {"id": user_id}, external_physician_id=other.id)


def test_status_lists_only_external_physicians_active_in_month() -> None:
    active = _physician(date(2026, 1, 1), name="Dr. Active")
    archived = _physician(date(2026, 1, 1), archived_at=datetime(2026, 11, 1, tzinfo=timezone.utc), name="Dr. Gone")
    future = _physician(date(2027, 2, 1), name="Dr. Later")
    service, repo = _service([active, archived, future])
    repo.submitted_externals = {active.id}
    assert service.get_submission_status(UNIT, MONTH) == [
        {"external_physician_id": active.id, "name": "Dr. Active", "submitted": True},
    ]


# --- External physicians in the on-call calendars ---

def test_submitter_id_is_the_staff_or_external_id() -> None:
    staff_id, external_id = uuid4(), uuid4()
    assert StaffMemberOnCallSubmission(staff_member_id=staff_id).submitter_id == staff_id
    assert StaffMemberOnCallSubmission(external_physician_id=external_id).submitter_id == external_id


def test_pull_includes_external_physicians_submissions_and_comments() -> None:
    staff_id, external_id = uuid4(), uuid4()
    day = date(2026, 12, 3)
    submissions = [
        StaffMemberOnCallSubmission(staff_member_id=staff_id, date=day, preference=2),
        StaffMemberOnCallSubmission(external_physician_id=external_id, date=day, preference=2),
        StaffMemberOnCallSubmission(external_physician_id=external_id, date=None, comment="Mornings only"),
    ]
    saved: dict[str, Any] = {}

    def save(unit_id: UUID, month: str, entries: list, created_by: Any, version: int, **kwargs: Any) -> list:
        saved["entries"] = entries
        return entries

    service = OnCallConstraintService(
        SimpleNamespace(get_by_month=lambda *args: [], save_entries_snapshot=save),  # type: ignore[arg-type]
        SimpleNamespace(get_by_unit_month=lambda *args: submissions),  # type: ignore[arg-type]
        SimpleNamespace(mark_pulled=lambda *args: None),  # type: ignore[arg-type]
        SimpleNamespace(),  # type: ignore[arg-type]
        SimpleNamespace(),  # type: ignore[arg-type]
        SimpleNamespace(),  # type: ignore[arg-type]
        FakeVersionRepository(),  # type: ignore[arg-type]
    )
    result = service.pull_member_submissions(UNIT, MONTH, None)
    [entry] = saved["entries"]
    assert (entry.date, entry.preference, entry.staff_member_ids) == (day, 2, [staff_id, external_id])
    [comments] = result["user_comments"]
    assert comments.staff_member_id == external_id


def _shift_service(
    staff_ids: set[UUID], external_ids: set[UUID], open_to_external: bool, saved: dict | None = None,
    versions: FakeVersionRepository | None = None,
) -> OnCallShiftService:
    station = SimpleNamespace(open_to_external=open_to_external)
    saved = saved if saved is not None else {}
    repo = SimpleNamespace(
        save_entries_snapshot=lambda *args, **kwargs: saved.update(kwargs) or [],
        get_version_status=lambda *args: None,
    )
    return OnCallShiftService(
        repo,  # type: ignore[arg-type]
        SimpleNamespace(get_by_ids=lambda ids, *args, **kwargs: {i: station for i in ids}),  # type: ignore[arg-type]
        SimpleNamespace(get_unit_member_ids=lambda ids, unit_id: set(ids) & staff_ids),  # type: ignore[arg-type]
        SimpleNamespace(get_unit_physician_ids=lambda ids, unit_id: set(ids) & external_ids),  # type: ignore[arg-type]
        versions or FakeVersionRepository(),  # type: ignore[arg-type]
    )


def test_shifts_are_saved_under_a_shared_version() -> None:
    staff_id, saved, versions = uuid4(), {}, FakeVersionRepository()
    _shift_service({staff_id}, set(), open_to_external=False, saved=saved, versions=versions).update_monthly_shifts(
        UNIT, versions.division_id, MONTH, _shifts(staff_id), None,
    )
    assert saved["version"] == 1
    assert [(row.version, unit_id, kind.value) for row, unit_id, kind in versions.entities] == [(1, UNIT, "ROSTER")]


def _shifts(member_id: UUID) -> MonthlyOnCallShiftsUpdate:
    return MonthlyOnCallShiftsUpdate(entries=[OnCallShiftEntry(date=date(2026, 12, 3), station_assignments={member_id: 7})])


def test_shifts_accept_external_physicians_on_stations_open_to_them() -> None:
    external_id = uuid4()
    response = _shift_service(set(), {external_id}, open_to_external=True).update_monthly_shifts(
        UNIT, uuid4(), MONTH, _shifts(external_id), None,
    )
    assert response.version == 0


def test_shifts_reject_external_physicians_on_closed_stations_and_unknown_ids() -> None:
    external_id = uuid4()
    with pytest.raises(OnCallStationNotOpenToExternalError):
        _shift_service(set(), {external_id}, open_to_external=False).update_monthly_shifts(
            UNIT, uuid4(), MONTH, _shifts(external_id), None,
        )
    with pytest.raises(ValueError):
        _shift_service(set(), set(), open_to_external=True).update_monthly_shifts(
            UNIT, uuid4(), MONTH, _shifts(uuid4()), None,
        )
    staff_id = uuid4()
    _shift_service({staff_id}, set(), open_to_external=False).update_monthly_shifts(
        UNIT, uuid4(), MONTH, _shifts(staff_id), None,
    )
