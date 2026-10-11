"""Applies station versions a saved schedule wasn't built with to its days —
the backend counterpart of the FE's `mergeNewStationVersions`
(src/utils/stationVersions.ts). On each stored day, every station whose
version in effect that day isn't pinned by the schedule version follows the
config exactly: a mandatory station is present exactly when it recurs, a
retired one is removed (with its assignments), and optional stations are
left as the admin placed them."""

from datetime import date, timedelta
from typing import Dict, List, Optional

from app.models.models import RecurrenceType, SpecialDateType, StationVersion
from app.repositories.station_repository import version_in_effect
from app.schemas.schemas import ScheduleDayEntry, ScheduleStationEntry

SATURDAY = 6
MONDAY = 1
MIN_RECURRENCE_INTERVAL = 2


def js_day_of_week(d: date) -> int:
    """JS Date.getDay(): 0 = Sunday ... 6 = Saturday."""
    return (d.weekday() + 1) % 7


def start_of_week(d: date) -> date:
    return d - timedelta(days=js_day_of_week(d))


def is_version_active_on_date(
    version: StationVersion, day: date, special_dates: Dict[date, SpecialDateType],
) -> bool:
    """Whether a station version recurs on `day`. Manual and retired versions never do."""
    if version.is_retired or version.recurrence_type is None:
        return False

    special_type = special_dates.get(day)
    if special_type == SpecialDateType.SABBATICAL:
        return version.active_on_sabbatical

    natural_dow = js_day_of_week(day)
    dow = MONDAY if special_type == SpecialDateType.PARTIAL_DAY and natural_dow == SATURDAY else natural_dow
    active_days = version.active_days or []
    interval = max(MIN_RECURRENCE_INTERVAL, version.recurrence_interval or MIN_RECURRENCE_INTERVAL)

    if version.recurrence_type == RecurrenceType.WEEKLY:
        return dow in active_days
    if version.recurrence_type == RecurrenceType.EVERY_X_DAYS:
        if version.recurrence_base_date is None:
            return False
        if dow == SATURDAY and SATURDAY not in active_days:
            return False
        return (day - version.recurrence_base_date).days % interval == 0
    if version.recurrence_type == RecurrenceType.EVERY_X_WEEKS:
        if version.recurrence_base_date is None or dow not in active_days:
            return False
        weeks = (start_of_week(day) - start_of_week(version.recurrence_base_date)).days // 7
        return weeks % interval == 0
    return False


def _insertion_index(stations: List[ScheduleStationEntry], order: Optional[int], order_by_station: Dict[int, Optional[int]]) -> int:
    """Before the first configured station with a greater display order."""
    target = order if order is not None else float("inf")
    for index, entry in enumerate(stations):
        if entry.station_id is None:
            continue
        other = order_by_station.get(entry.station_id)
        if (other if other is not None else float("inf")) > target:
            return index
    return len(stations)


def merge_day(
    day: ScheduleDayEntry,
    versions_by_station: Dict[int, List[StationVersion]],
    pinned_ids: set,
    order_by_station: Dict[int, Optional[int]],
    special_dates: Dict[date, SpecialDateType],
) -> Optional[ScheduleDayEntry]:
    """The day with unpinned station versions applied, or None when nothing changes."""
    stations = list(day.stations)
    changed = False
    for station_id, versions in versions_by_station.items():
        version = version_in_effect(versions, day.date)
        if version is None or version.id in pinned_ids:
            continue
        if version.optional and not version.is_retired:
            continue
        should_be_present = is_version_active_on_date(version, day.date, special_dates)
        is_present = any(entry.station_id == station_id for entry in stations)
        if should_be_present and not is_present:
            index = _insertion_index(stations, order_by_station.get(station_id), order_by_station)
            stations.insert(index, ScheduleStationEntry(station_id=station_id, display_order=0))
            changed = True
        elif not should_be_present and is_present:
            stations = [entry for entry in stations if entry.station_id != station_id]
            changed = True

    if not changed:
        return None
    return day.model_copy(update={
        "stations": [entry.model_copy(update={"display_order": order}) for order, entry in enumerate(stations)],
    })
