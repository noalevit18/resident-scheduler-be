import logging
from collections import defaultdict
from datetime import date
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from app.models.models import ScheduleVersion, StationVersion
from app.repositories.constraint_repository import ConstraintRepository
from app.repositories.on_call_shift_repository import OnCallShiftRepository, month_bounds
from app.repositories.schedule_repository import ScheduleRepository, ScheduleVersionConflictError
from app.repositories.special_date_repository import SpecialDateRepository
from app.repositories.station_repository import version_in_effect, version_sort_key
from app.schemas.schemas import (
    MonthlyScheduleResponse, MonthlyScheduleUpdate, ScheduleAssignmentEntry, ScheduleDayEntry,
    ScheduleDayResponse, ScheduleHistoryResponse, ScheduleStationEntry, ScheduleStationResponse,
    StationVersionResponse,
)
from app.services.schedule_station_sync import merge_day
from app.services.senior_service import SeniorService
from app.services.staff_service import StaffService
from app.services.station_service import StationService
from app.context import get_current_user_label

logger = logging.getLogger(__name__)


class ScheduleValidationError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


def versions_in_month(versions: List[StationVersion], start: date, end: date) -> List[StationVersion]:
    """Every version of one station in effect on some day in [start, end):
    the one in effect on `start` plus those taking effect inside the range."""
    in_effect = {}
    for day in [start] + [v.effective_from for v in versions if start < v.effective_from < end]:
        version = version_in_effect(versions, day)
        if version:
            in_effect[version.id] = version
    return sorted(in_effect.values(), key=version_sort_key)


class ScheduleService:
    def __init__(
        self,
        repository: ScheduleRepository,
        station_service: StationService,
        staff_service: StaffService,
        senior_service: SeniorService,
        constraint_repository: ConstraintRepository,
        on_call_shift_repository: OnCallShiftRepository,
        special_date_repository: SpecialDateRepository,
    ):
        self.repository = repository
        self.station_service = station_service
        self.staff_service = staff_service
        self.senior_service = senior_service
        self.constraint_repository = constraint_repository
        self.on_call_shift_repository = on_call_shift_repository
        self.special_date_repository = special_date_repository

    # --- response mapping ---

    def _to_history_response(self, version_row: ScheduleVersion) -> ScheduleHistoryResponse:
        return ScheduleHistoryResponse.model_validate(version_row)

    def _to_days(self, version_row: ScheduleVersion) -> List[ScheduleDayResponse]:
        stations_by_date: dict = defaultdict(list)
        for row in self.repository.get_stations(version_row.id):
            stations_by_date[row.date].append(ScheduleStationResponse(
                id=row.id, station_id=row.station_id, custom_name=row.custom_name, display_order=row.display_order,
                assignments=[
                    ScheduleAssignmentEntry(staff_member_id=a.staff_member_id, is_stand_by=a.is_stand_by)
                    for a in row.assignments
                ],
            ))
        senior_by_date = {row.date: row.senior_id for row in self.repository.get_seniors(version_row.id)}
        all_dates = sorted(set(stations_by_date) | set(senior_by_date))
        return [
            ScheduleDayResponse(date=d, senior_id=senior_by_date.get(d), stations=stations_by_date.get(d, []))
            for d in all_dates
        ]

    def _month_station_responses(
        self, unit_id: UUID, month: str, version_row: Optional[ScheduleVersion],
    ) -> List[StationVersionResponse]:
        """Per station: every version in effect on some day of the month plus
        every version the returned schedule version pins. Stations with only
        retired versions in the month (and nothing pinned) are left out."""
        start, end = month_bounds(month)
        pinned = self.repository.get_pinned_versions(version_row.id) if version_row else []
        pinned_ids = {v.id for v in pinned}
        by_station: Dict[int, Dict[int, StationVersion]] = defaultdict(dict)
        for station_id, versions in self.station_service.get_unit_versions(unit_id).items():
            for v in versions_in_month(versions, start, end):
                by_station[station_id][v.id] = v
        for v in pinned:
            by_station[v.station_id][v.id] = v
        by_station = {
            sid: vs for sid, vs in by_station.items()
            if any(not v.is_retired or v.id in pinned_ids for v in vs.values())
        }
        stations = self.station_service.get_by_ids(list(by_station), unit_id, include_deleted=True)
        on_call_ids = self.station_service.get_on_call_station_ids(list(by_station))
        responses = [
            self.station_service.to_version_response(stations[sid], v, on_call_ids.get(sid, []), v.id in pinned_ids)
            for sid, vs in by_station.items() if sid in stations
            for v in vs.values()
        ]
        return sorted(responses, key=lambda r: (
            r.display_order is None, r.display_order or 0, r.station_id, r.effective_from, r.version,
        ))

    def _to_monthly_response(
        self, unit_id: UUID, month: str, version_row: Optional[ScheduleVersion],
    ) -> MonthlyScheduleResponse:
        stations = self._month_station_responses(unit_id, month, version_row)
        if not version_row:
            return MonthlyScheduleResponse(days=[], stations=stations, version=0)
        return MonthlyScheduleResponse(
            days=self._to_days(version_row),
            stations=stations,
            version=version_row.version,
            is_published=version_row.is_published,
            published_at=version_row.published_at,
            published_by=version_row.published_by,
            constraints_version=version_row.constraints_version,
            on_call_version=version_row.on_call_version,
            created_at=version_row.created_at,
        )

    # --- validation ---

    def _validate_days_in_month(self, days: List[ScheduleDayEntry], month: str) -> None:
        seen = set()
        for day in days:
            if day.date.strftime("%Y-%m") != month:
                raise ScheduleValidationError("schedule_date_outside_month", f"Date {day.date} is not in month {month}")
            if day.date in seen:
                raise ScheduleValidationError("schedule_duplicate_date", f"Date {day.date} appears more than once")
            seen.add(day.date)

    def _validate_staff(self, days: List[ScheduleDayEntry], unit_id: UUID) -> None:
        """A staff member may sit on several stations of one day (e.g. a
        mandatory station plus optional/custom ones — the FE warns about more
        than one mandatory station); only a repeat within the same station is
        rejected."""
        staff_ids = set()
        for day in days:
            for station in day.stations:
                station_staff_ids = [a.staff_member_id for a in station.assignments]
                if len(station_staff_ids) != len(set(station_staff_ids)):
                    raise ScheduleValidationError(
                        "schedule_duplicate_assignment",
                        f"A staff member is assigned more than once to the same station on {day.date}",
                    )
                staff_ids.update(station_staff_ids)
        if staff_ids - self.staff_service.get_unit_member_ids(list(staff_ids), unit_id):
            raise ScheduleValidationError("schedule_staff_member_not_found", "One or more staff members are not in this unit")

    def _validate_stations(self, days: List[ScheduleDayEntry], unit_id: UUID) -> dict:
        """Returns {station_id: Station} for the referenced configured stations."""
        for day in days:
            day_station_ids = [s.station_id for s in day.stations if s.station_id is not None]
            if len(day_station_ids) != len(set(day_station_ids)):
                raise ScheduleValidationError("schedule_duplicate_station", f"A station appears more than once on {day.date}")
        station_ids = {s.station_id for day in days for s in day.stations if s.station_id is not None}
        stations = self.station_service.get_by_ids(list(station_ids), unit_id, include_deleted=True)
        if station_ids - set(stations.keys()):
            raise ScheduleValidationError("schedule_station_not_found", "One or more stations are not in this unit")
        return stations

    def _validate_seniors(self, days: List[ScheduleDayEntry], unit_id: UUID) -> None:
        senior_ids = {day.senior_id for day in days if day.senior_id}
        if senior_ids - self.senior_service.get_unit_senior_ids(list(senior_ids), unit_id):
            raise ScheduleValidationError("schedule_senior_not_found", "One or more seniors are not in this unit")

    # --- station version pinning ---

    def _resolve_pins(self, unit_id: UUID, month: str, referenced_station_ids: set) -> List[StationVersion]:
        """The station versions a new schedule version is pinned to: every
        version in effect on any day of the month, for every station shown or
        active (has a non-retired version in effect during the month). A past
        month keeps the previous schedule version's pins and adds only
        versions newer than what it pinned for that station."""
        start, end = month_bounds(month)
        in_month = {
            sid: versions_in_month(versions, start, end)
            for sid, versions in self.station_service.get_unit_versions(unit_id).items()
        }
        considered = set(referenced_station_ids) | {
            sid for sid, versions in in_month.items() if any(not v.is_retired for v in versions)
        }
        fresh = [v for sid in considered for v in in_month.get(sid, [])]
        if month >= date.today().strftime("%Y-%m"):
            return fresh
        previous = self.repository.get_version_status(unit_id, month)
        if not previous:
            return fresh
        carried = self.repository.get_pinned_versions(previous.id)
        max_pinned: Dict[int, int] = {}
        for v in carried:
            max_pinned[v.station_id] = max(max_pinned.get(v.station_id, 0), v.version)
        return carried + [v for v in fresh if v.version > max_pinned.get(v.station_id, 0)]

    # --- defaults ---

    def _apply_default_order(self, days: List[ScheduleDayEntry], stations: dict) -> List[ScheduleDayEntry]:
        """`stations` is {station_id: Station}. A configured station with no
        `display_order` gets the station's (global) order; a custom one goes after the last station of the
        day (stations with no order at all fall in the same way, in input
        order)."""
        resolved_days = []
        for day in days:
            resolved = []
            for entry in day.stations:
                order = entry.display_order
                if order is None and entry.station_id is not None:
                    order = stations[entry.station_id].display_order
                resolved.append((entry, order))
            next_order = max((o for _, o in resolved if o is not None), default=-1) + 1
            day_stations = []
            for entry, order in resolved:
                if order is None:
                    order, next_order = next_order, next_order + 1
                day_stations.append(entry.model_copy(update={"display_order": order}))
            resolved_days.append(day.model_copy(update={"stations": day_stations}))
        return resolved_days

    def _current_source_versions(self, unit_id: UUID, month: str) -> Tuple[Optional[int], Optional[int]]:
        """(constraints_version, on_call_version) currently in effect for the month."""
        on_call_row = self.on_call_shift_repository.get_version_status(unit_id, month)
        return (
            self.constraint_repository.get_current_version(unit_id, month),
            on_call_row.version if on_call_row else None,
        )

    # --- public API ---

    def get_monthly(
        self, unit_id: UUID, month: str, version: Optional[int] = None, published_only: bool = False,
    ) -> MonthlyScheduleResponse:
        """`published_only`: the latest published version (version 0 / empty
        when nothing is published) — for non-admins and "view as user"."""
        if version:
            version_row = self.repository.get_version_row(unit_id, month, version)
            if not version_row:
                raise ValueError(f"Schedule version {version} not found for {month}")
        elif published_only:
            version_row = self.repository.get_latest_published(unit_id, month)
        else:
            version_row = self.repository.get_version_status(unit_id, month)
        return self._to_monthly_response(unit_id, month, version_row)

    def get_version_history(self, unit_id: UUID, month: str) -> List[ScheduleHistoryResponse]:
        return [self._to_history_response(row) for row in self.repository.get_version_history(unit_id, month)]

    def update_monthly(
        self, unit_id: UUID, month: str, data: MonthlyScheduleUpdate, created_by: Optional[UUID],
    ) -> MonthlyScheduleResponse:
        self._validate_days_in_month(data.days, month)
        self._validate_staff(data.days, unit_id)
        stations = self._validate_stations(data.days, unit_id)
        self._validate_seniors(data.days, unit_id)
        pins = self._resolve_pins(unit_id, month, set(stations))
        days = self._apply_default_order(data.days, stations)
        constraints_version, on_call_version = self._current_source_versions(unit_id, month)

        version_row = self.repository.save_snapshot(
            unit_id, month, days, pins, created_by, data.is_published, constraints_version, on_call_version,
            base_version=data.base_version,
        )
        logger.info(
            "Saved monthly schedule version %d: %d days (unit_id=%s, month=%s) by %s",
            version_row.version, len(days), unit_id, month, get_current_user_label(),
        )
        return self._to_monthly_response(unit_id, month, version_row)

    def publish_version(self, unit_id: UUID, month: str, version: int, user_id: Optional[UUID]) -> ScheduleHistoryResponse:
        version_row = self.repository.set_published(unit_id, month, version, True, user_id)
        logger.info("Published schedule version %d (unit_id=%s, month=%s) by %s", version, unit_id, month, get_current_user_label())
        return self._to_history_response(version_row)

    def unpublish_version(self, unit_id: UUID, month: str, version: int, user_id: Optional[UUID]) -> ScheduleHistoryResponse:
        version_row = self.repository.set_published(unit_id, month, version, False, user_id)
        logger.info("Unpublished schedule version %d (unit_id=%s, month=%s) by %s", version, unit_id, month, get_current_user_label())
        return self._to_history_response(version_row)

    # --- station changes ---

    def _sync_month_stations(self, unit_id: UUID, month: str, from_date: date, created_by: Optional[UUID]) -> bool:
        """Saves a new version of the month with the station versions its
        latest version isn't pinned to applied (see schedule_station_sync) on
        each saved day from `from_date` on. Keeps the latest version's
        published state. Returns whether it saved."""
        latest = self.repository.get_version_status(unit_id, month)
        if not latest:
            return False
        start, end = month_bounds(month)
        pinned_ids = {v.id for v in self.repository.get_pinned_versions(latest.id)}
        versions_by_station = self.station_service.get_unit_versions(unit_id)
        stations = self.station_service.get_by_ids(list(versions_by_station), unit_id, include_deleted=True)
        order_by_station = {sid: station.display_order for sid, station in stations.items()}
        special_dates = self.special_date_repository.get_types_for_unit(unit_id, start, end)

        days, changed = [], False
        for stored in self._to_days(latest):
            day = ScheduleDayEntry(
                date=stored.date, senior_id=stored.senior_id,
                stations=[ScheduleStationEntry(**s.model_dump(exclude={"id"})) for s in stored.stations],
            )
            applies = day.stations and day.date >= from_date
            merged = merge_day(day, versions_by_station, pinned_ids, order_by_station, special_dates) if applies else None
            changed = changed or merged is not None
            days.append(merged or day)
        if not changed:
            return False

        referenced = {s.station_id for d in days for s in d.stations if s.station_id is not None}
        try:
            self.repository.save_snapshot(
                unit_id, month, days, self._resolve_pins(unit_id, month, referenced), created_by, latest.is_published,
                latest.constraints_version, latest.on_call_version, base_version=latest.version,
            )
        except ScheduleVersionConflictError:
            logger.warning("Station sync skipped: month %s changed meanwhile (unit_id=%s)", month, unit_id)
            return False
        return True

    def apply_station_changes(self, unit_id: UUID, effective_from: date, created_by: Optional[UUID]) -> List[str]:
        """Applies station changes to the saved schedules they affect: every
        saved day from `effective_from` on, in whatever month it falls. Past
        months are protected by the station rules themselves (recurrence
        changes and deletions can't take effect in a past month), so a past
        month only changes when a station was explicitly dated into it.
        Returns the months that got a new version."""
        synced = [
            month for month in self.repository.get_saved_months(unit_id, effective_from.strftime("%Y-%m"))
            if self._sync_month_stations(unit_id, month, effective_from, created_by)
        ]
        logger.info(
            "Applied station changes from %s to schedule months %s (unit_id=%s) by %s",
            effective_from, synced, unit_id, get_current_user_label(),
        )
        return synced
