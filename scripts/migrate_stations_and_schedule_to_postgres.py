"""
One-time migration: Firestore stations + schedule -> Postgres, run against a
single unit. Firestore is only read, never written.

Part 1 — stations:
Every doc in the Firestore `stations` collection becomes one `stations` row
(docs whose id starts with "il_emek_ped_a_" — stale copies — are ignored),
upserted by (unit_id, firestore_id) so re-running never duplicates stations.
`certificationName` is resolved to a `staff_certifications.id` of the same
unit by (normalized) name; `color.isCustom` is ignored; a missing
`recurrenceType` means a manual station (NULL); an `alternating` station
becomes every-x-days, interval 2, base date 2026-06-01 (migrated history
is unaffected: each day's stations come from stationsByDate / the
assignments, not from recurrence). A non-`custom_` station key
that schedule data references but that no longer exists in the collection
gets a soft-deleted placeholder row (name = the Firestore key) so history
isn't lost. Keys starting with `custom_` are stations added manually to a
single schedule — they never become `stations` rows. Every upserted station
gets a `station_versions` row effective from 1970-01-01 when it has none yet
or its versioned config changed (so re-runs don't add versions); placeholders
get a retired version. Saturday works only through active_days: "dept" and
any station whose activeDays included 6 get 6 in active_days and
active_on_sabbatical=true.

Part 1b — on-call station -> station mapping:
`ON_CALL_STATION_MAPPING` (on-call station name -> station name) is resolved
by normalized name against the unit's division's `on_call_stations` and the
unit's `stations`, and upserted into `on_call_station_mappings` by
(unit_id, on_call_station_id). Unmatched names, and division on-call
stations the mapping doesn't cover, go to the report. "dept" gets
prefer_day_before_on_call=true when it has at least one mapping (replaces
the old generator's ward/מחלקה name matching).

Part 2 — schedule:
Snapshots are collected in this order: every `schedule_versions` doc (sorted
by `savedAt`), then `schedules/published_schedule` (published), then
`schedules/main_schedule` (draft). Each snapshot is split by month, and each
(month, snapshot) becomes a new `schedule_versions` version for that month via
`ScheduleRepository.save_snapshot` — unless it's identical to the month's
previous version (an unchanged draft is skipped; an identical but newly
published snapshot is kept so the publish is recorded).

Date keys are "YYYY-MM-DD" or, in older docs, the UTC instant of local
midnight ("2026-06-02T21:00:00.000Z" = 2026-06-03, Asia/Jerusalem).

Per date, `stationsByDate[date]` decides the day's stations and their order:
- A station list (older shape): exactly those stations, in that order
  (entries flagged `removedFromDay` excluded).
- The override map (`removedStationIds`, `addedOptionalStationIds`,
  `manualStations`, `stationOrder`): it doesn't list the regular stations, so
  the day gets `stationOrder` + `addedOptionalStationIds` + `manualStations`
  + the assigned stations, minus `removedStationIds`; ordered by
  `stationOrder`, then the stations collection's order.
- No entry for the date: the assigned stations, in the stations collection's
  order.
Custom stations (`custom_` ids) take their name from the list / manualStations
and never become `stations` rows.
- `selectionsByDate[date][stationKey]` (staff id list) -> assignments. A
  selection on a station that isn't one of the day's stations is ignored and
  reported.
- `standbyByDate` / `standByDate` (`{date: [staffIds]}`) -> is_stand_by=true
  on that staff member's assignment on a station with enable_stand_by (at
  most once per day; custom stations never). Firestore has no such flag, so
  "dept" — the only station the old FE showed stand-by on — gets
  enable_stand_by=true unless the doc says otherwise.
- `seniorIdsByDate` / `seniorsIdsByDate` (Postgres UUIDs), falling back to
  `seniorsByDate` mapped through migrate_seniors_to_postgres.old_id_to_uuid.
- Ignored: `shiftStations`, `versionId`, `dayModesByDate`, and the
  `residents` array inside `stationsByDate` list entries.
Version metadata: `savedAt` -> created_at, `savedBy` (email) -> created_by
(user looked up by email), `is_published`, `constraintsVersion`,
`onCallVersion`. Each version is pinned to the station versions in effect
during its month for every station shown or active (Firestore never
versioned stations, so all migrated history pins the same versions).

Anything that can't be resolved is skipped and listed in the "needs manual
review" report at the end — never guessed at.

Part 1 is idempotent. Part 2 is not: re-running it for real appends new
versions on top of the already-migrated ones (reads return the latest, so the
result looks the same, but history gets duplicated) — same caveat as
migrate_on_call_to_postgres.py.

Usage:
    python -m scripts.migrate_stations_and_schedule_to_postgres --unit-id <UUID> [--dry-run]

`--dry-run` runs every Firestore read and DB lookup, stages the station
upserts (to get ids) and rolls everything back at the end; no schedule
versions are written. Always dry-run first and review the report.
"""

import argparse
import logging
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

sys.path.insert(0, ".")

from app.database import SessionLocal  # noqa: E402
from app.models.models import (  # noqa: E402
    OnCallStation, OnCallStationMapping, RecurrenceType, Senior, StaffCertification, StaffMember,
    Station, Unit, User,
)
from app.repositories.schedule_repository import ScheduleRepository  # noqa: E402
from app.repositories.station_repository import EPOCH, StationRepository, version_sort_key  # noqa: E402
from app.services.schedule_service import versions_in_month  # noqa: E402
from app.services.station_service import versioned_config  # noqa: E402
from app.repositories.on_call_shift_repository import month_bounds  # noqa: E402
from app.schemas.schemas import ScheduleAssignmentEntry, ScheduleDayEntry, ScheduleStationEntry  # noqa: E402
from scripts.migrate_on_call_to_postgres import normalize_station_name  # noqa: E402
from scripts.migrate_residents_to_staff import init_firebase  # noqa: E402
from scripts.migrate_seniors_to_postgres import old_id_to_uuid as old_senior_id_to_uuid  # noqa: E402

CUSTOM_STATION_PREFIX = "custom_"
# on-call station name (`on_call_stations.name`) -> station name (`stations.name`)
ON_CALL_STATION_MAPPING = {
    "מחלקה שקטה": "מחלקה",
    "מחלקה מקבלת": "מחלקה",
    "מיון 1": "משחרר מיון",
    "מיון 2": "משחרר מיון",
}
# Older schedule docs keyed dates as the UTC instant of local midnight
# (e.g. "2026-06-02T21:00:00.000Z" for June 3rd); converted in this zone.
LOCAL_TZ = ZoneInfo("Asia/Jerusalem")
# Stale per-account copies of stations in the Firestore `stations`
# collection; ignored completely.
IGNORED_STATION_DOC_PREFIX = "il_emek_ped_a_"
DEPT_STATION_ID = "dept"
SATURDAY = 6
# FE "alternating" (odd/even days by month parity) has no Postgres equivalent;
# such stations are migrated as every 2 days counted from this date.
ALTERNATING_AS_EVERY_X_DAYS = (2, date(2026, 6, 1))
DAY_OVERRIDE_KEYS = ("removedStationIds", "addedOptionalStationIds", "manualStations", "stationOrder")
SCHEDULE_DOCS = [("schedules", "published_schedule", True), ("schedules", "main_schedule", False)]


# ==========================================
# Generic parsing helpers
# ==========================================

def parse_date(value: Any) -> Optional[date]:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def parse_datetime(value: Any) -> Optional[datetime]:
    """`savedAt` is a Firestore Timestamp (datetime subclass) in newer docs
    and an ISO string in older ones."""
    if value is None:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def parse_int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def as_ordered_list(value: Any) -> list:
    """Firestore arrays sometimes come back as index-keyed maps."""
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return [v for _, v in sorted(value.items(), key=lambda kv: parse_int(kv[0]) or 0)]
    return []


def is_custom_station(key: str) -> bool:
    return key.startswith(CUSTOM_STATION_PREFIX)


# ==========================================
# Part 1: stations
# ==========================================

def load_certification_ids(db: Session, unit_id: UUID) -> dict:
    rows = db.query(StaffCertification.name, StaffCertification.id).filter(StaffCertification.unit_id == unit_id).all()
    return {normalize_station_name(row.name): row.id for row in rows}


def recurrence_fields(data: dict, label: str, report: list) -> dict:
    """The Postgres recurrence columns for a Firestore station config."""
    if data.get("recurrenceType") == "alternating":
        interval, base_date = ALTERNATING_AS_EVERY_X_DAYS
        report.append(
            f"CONVERTED recurrence: {label} alternating ({data.get('alternatingType') or 'odd-on-odd'}) "
            f"-> every-x-days interval={interval} base={base_date.isoformat()}"
        )
        return {
            "recurrence_type": RecurrenceType.EVERY_X_DAYS,
            "recurrence_interval": interval,
            "recurrence_base_date": base_date,
        }
    base_date_raw = data.get("recurrenceBaseDate")
    base_date = parse_date(base_date_raw) if base_date_raw else None
    if base_date_raw and base_date is None:
        report.append(f"INVALID recurrenceBaseDate: {label} value={base_date_raw!r}")
    return {
        "recurrence_type": resolve_recurrence_type(data.get("recurrenceType"), label, report),
        "recurrence_interval": parse_int(data.get("recurrenceInterval")),
        "recurrence_base_date": base_date,
    }


def resolve_recurrence_type(raw: Any, label: str, report: list) -> Optional[RecurrenceType]:
    if not raw:
        return None
    try:
        return RecurrenceType(raw)
    except ValueError:
        report.append(f"UNKNOWN recurrenceType: {label} value={raw!r} (stored as NULL / manual)")
        return None


def resolve_certification_id(data: dict, certification_ids: dict, label: str, report: list) -> Optional[int]:
    name = normalize_station_name(data.get("certificationName"))
    certification_id = certification_ids.get(name) if name else None
    if data.get("requiresCertification") and certification_id is None:
        report.append(f"UNMATCHED certification: {label} certificationName={data.get('certificationName')!r}")
    return certification_id


def saturday_fields(data: dict, firestore_id: str) -> dict:
    """Saturday now works only through active_days containing 6 (nothing is
    special-cased for "dept" any more): "dept" and any station already active
    on Saturday get 6 in active_days and active_on_sabbatical=true."""
    active_days = [int(d) for d in as_ordered_list(data.get("activeDays"))]
    if firestore_id != DEPT_STATION_ID and SATURDAY not in active_days:
        return {"active_days": active_days, "active_on_sabbatical": False}
    return {"active_days": sorted(set(active_days) | {SATURDAY}), "active_on_sabbatical": True}


def station_fields(data: dict, certification_ids: dict, label: str, report: list) -> dict:
    """`prefer_day_before_on_call` is deliberately absent: it's set in part 1b
    once the on-call mappings exist, and left untouched on re-runs."""
    color = data.get("color") or {}
    return {
        "name": data.get("name") or label,
        "is_default": bool(data.get("isFallback", False)),
        "certification_id": resolve_certification_id(data, certification_ids, label, report),
        "bg_color": color.get("bg"),
        "border_color": color.get("border"),
        "text_color": color.get("text"),
        "optional": bool(data.get("optional", False)),
        "min_staff_members": parse_int(data.get("minResidents")),
        **saturday_fields(data, label),
        **recurrence_fields(data, label, report),
        "display_order": parse_int(data.get("order")),
        # Firestore predates the flag; the old FE only ever showed stand-by on
        # "dept", so that's the default when the doc doesn't say.
        "enable_stand_by": bool(data.get("enableStandBy", label == DEPT_STATION_ID)),
        "is_deleted": False,
        "deleted_at": None,
        "deleted_by": None,
    }


def upsert_station(db: Session, unit_id: UUID, firestore_id: str, fields: dict) -> Station:
    row = db.query(Station).filter(Station.unit_id == unit_id, Station.firestore_id == firestore_id).first()
    if row is None:
        row = Station(unit_id=unit_id, firestore_id=firestore_id)
        db.add(row)
    for key, value in fields.items():
        setattr(row, key, value)
    db.flush()
    StationRepository(db).snapshot_if_changed(row, versioned_config(row), created_by=None)
    return row


def canonical_station_docs(docs: list, report: list) -> list:
    """[(station_id, data)] with one doc per station id. Docs whose id starts
    with IGNORED_STATION_DOC_PREFIX are skipped entirely. Should another doc
    still share a station id, the doc whose id equals the station id wins
    (the FE saves stations that way), else the first in doc-id order."""
    by_station: dict = {}
    for snap in docs:
        if snap.id.startswith(IGNORED_STATION_DOC_PREFIX):
            continue
        data = snap.to_dict() or {}
        by_station.setdefault(data.get("id") or snap.id, []).append((snap.id, data))
    result = []
    for station_id, candidates in by_station.items():
        chosen = next((c for c in candidates if c[0] == station_id), candidates[0])
        for doc_id, _ in candidates:
            if doc_id != chosen[0]:
                report.append(f"DUPLICATE station doc ignored: {doc_id!r} (same id {station_id!r} as doc {chosen[0]!r})")
        result.append((station_id, chosen[1]))
    return result


def migrate_stations(fs, db: Session, unit_id: UUID, report: list) -> tuple:
    """Returns ({firestore_id: Station}, [raw Firestore config dicts]). Part 2
    orders a day's stations by the configs' `order` when stationsByDate
    doesn't."""
    certification_ids = load_certification_ids(db, unit_id)
    docs = list(fs.collection("stations").stream())
    print(f"Found {len(docs)} stations in Firestore")
    stations, configs = {}, []
    for firestore_id, data in canonical_station_docs(docs, report):
        if is_custom_station(firestore_id):
            report.append(f"SKIPPED custom station in stations collection: {firestore_id!r}")
            continue
        configs.append({**data, "id": firestore_id})
        row = upsert_station(db, unit_id, firestore_id, station_fields(data, certification_ids, firestore_id, report))
        stations[firestore_id] = row
        print(f"  {firestore_id} -> id={row.id} name={row.name!r} certification_id={row.certification_id} "
              f"recurrence={row.recurrence_type} order={row.display_order}")
    return stations, configs


def ensure_placeholder_station(db: Session, unit_id: UUID, key: str, stations: dict, report: list) -> Station:
    """A station referenced by schedule data that no longer exists in the
    Firestore collection: keep it as a soft-deleted row so history resolves."""
    if key not in stations:
        row = upsert_station(db, unit_id, key, {
            "name": key, "is_deleted": True, "deleted_at": datetime.now(timezone.utc),
        })
        repo = StationRepository(db)
        versions = repo.get_versions([row.id]).get(row.id, [])
        if not max(versions, key=version_sort_key).is_retired:
            # Retired from the start: pinned where history shows it, never "active".
            repo.write_version(row, EPOCH, versioned_config(row), created_by=None, is_retired=True)
        stations[key] = row
        report.append(f"PLACEHOLDER station created (soft-deleted): {key!r} -> id={row.id}")
    return stations[key]


# ==========================================
# Part 1b: on-call station -> station mapping
# ==========================================

def names_to_ids(rows) -> dict:
    return {normalize_station_name(row.name): row.id for row in rows}


def upsert_on_call_mapping(db: Session, unit_id: UUID, on_call_station_id: int, station_id: int) -> None:
    row = db.query(OnCallStationMapping).filter(
        OnCallStationMapping.unit_id == unit_id, OnCallStationMapping.on_call_station_id == on_call_station_id,
    ).first()
    if row is None:
        db.add(OnCallStationMapping(unit_id=unit_id, on_call_station_id=on_call_station_id, station_id=station_id))
    else:
        row.station_id = station_id
    db.flush()


def migrate_on_call_mappings(db: Session, unit_id: UUID, division_id: UUID, report: list) -> None:
    on_call_ids = names_to_ids(db.query(OnCallStation).filter(
        OnCallStation.division_id == division_id, OnCallStation.is_deleted.is_(False),
    ).all())
    station_ids = names_to_ids(db.query(Station).filter(Station.unit_id == unit_id, Station.is_deleted.is_(False)).all())
    for on_call_name, station_name in ON_CALL_STATION_MAPPING.items():
        on_call_station_id = on_call_ids.get(normalize_station_name(on_call_name))
        station_id = station_ids.get(normalize_station_name(station_name))
        if on_call_station_id is None:
            report.append(f"UNMATCHED on-call station for mapping: {on_call_name!r}")
        if station_id is None:
            report.append(f"UNMATCHED station for on-call mapping: {station_name!r} (from {on_call_name!r})")
        if on_call_station_id is None or station_id is None:
            continue
        upsert_on_call_mapping(db, unit_id, on_call_station_id, station_id)
        print(f"  on-call {on_call_name!r} (id={on_call_station_id}) -> station {station_name!r} (id={station_id})")

    mapped_names = {normalize_station_name(name) for name in ON_CALL_STATION_MAPPING}
    for name in sorted(n for n in on_call_ids if n not in mapped_names):
        report.append(f"UNMAPPED on-call station (no station mapping): {name!r}")
    enable_dept_prefer_day_before_on_call(db, unit_id, report)


def enable_dept_prefer_day_before_on_call(db: Session, unit_id: UUID, report: list) -> None:
    """The old generator preferred, for the ward station, staff on call the
    next day in the ward on-call station (name matching on ward/מחלקה). That's
    now prefer_day_before_on_call on "dept", via its on-call mappings."""
    dept = db.query(Station).filter(Station.unit_id == unit_id, Station.firestore_id == DEPT_STATION_ID).first()
    if dept is None:
        report.append(f"NO {DEPT_STATION_ID!r} station: prefer_day_before_on_call not set")
        return
    if not StationRepository(db).get_on_call_station_ids([dept.id]).get(dept.id):
        report.append(f"{DEPT_STATION_ID!r} has no on-call mapping: prefer_day_before_on_call not set")
        return
    dept.prefer_day_before_on_call = True
    StationRepository(db).snapshot_if_changed(dept, versioned_config(dept), created_by=None)
    print(f"  prefer_day_before_on_call=true on {DEPT_STATION_ID!r} (id={dept.id})")


# ==========================================
# Part 2: schedule
# ==========================================

@dataclass
class Snapshot:
    label: str
    data: dict
    is_published: bool
    created_at: Optional[datetime]
    created_by: Optional[UUID]
    constraints_version: Optional[int]
    on_call_version: Optional[int]


@dataclass
class ScheduleContext:
    db: Session
    unit_id: UUID
    stations: dict  # {firestore_id: Station}
    config_index: dict  # {station_id: position in the stations collection's order}
    staff_ids: set
    senior_ids: set
    report: list
    user_cache: dict = field(default_factory=dict)


def resolve_user_id(ctx: ScheduleContext, division_id: UUID, saved_by: Any, label: str) -> Optional[UUID]:
    if not saved_by:
        return None
    key = str(saved_by).strip().lower()
    if key not in ctx.user_cache:
        row = ctx.db.query(User.id).filter(
            func.lower(User.email) == key, User.is_deleted.is_(False),
            (User.division_id == division_id) | (User.unit_id == ctx.unit_id),
        ).first()
        ctx.user_cache[key] = row[0] if row else None
        if not row:
            ctx.report.append(f"UNMATCHED savedBy: {label} savedBy={saved_by!r} (created_by left NULL)")
    return ctx.user_cache[key]


def build_snapshot(ctx: ScheduleContext, division_id: UUID, label: str, data: dict, is_published: bool) -> Snapshot:
    created_by = resolve_user_id(ctx, division_id, data.get("savedBy"), label)
    return Snapshot(
        label=label, data=data, is_published=is_published,
        created_at=parse_datetime(data.get("savedAt")), created_by=created_by,
        constraints_version=parse_int(data.get("constraintsVersion")),
        on_call_version=parse_int(data.get("onCallVersion")),
    )


def collect_snapshots(fs, ctx: ScheduleContext, division_id: UUID) -> list:
    history = []
    for snap in fs.collection("schedule_versions").stream():
        data = snap.to_dict() or {}
        is_published = bool(data.get("is_published", data.get("isPublished", False)))
        snapshot = build_snapshot(ctx, division_id, f"schedule_versions/{snap.id}", data, is_published)
        if snapshot.created_at is None:
            ctx.report.append(f"NO savedAt: {snapshot.label} (ordered before dated versions)")
        history.append((snapshot.created_at is not None, snapshot.created_at or datetime.min, snap.id, snapshot))
    history.sort(key=lambda t: t[:3])
    snapshots = [t[3] for t in history]

    for collection, doc_name, is_published in SCHEDULE_DOCS:
        snap = fs.collection(collection).document(doc_name).get()
        if not snap.exists:
            print(f"  [{collection}/{doc_name}] does not exist, skipping")
            continue
        snapshots.append(build_snapshot(ctx, division_id, f"{collection}/{doc_name}", snap.to_dict() or {}, is_published))
    print(f"Collected {len(snapshots)} schedule snapshots ({len(history)} from schedule_versions)")
    return snapshots


def senior_ids_by_date(data: dict) -> dict:
    """Per date: the new Postgres-id maps win, else the legacy map mapped
    through the seniors migration's deterministic id."""
    merged = {k: str(old_senior_id_to_uuid(v)) for k, v in (data.get("seniorsByDate") or {}).items() if isinstance(v, str)}
    for key in ("seniorsIdsByDate", "seniorIdsByDate"):
        merged.update({k: v for k, v in (data.get(key) or {}).items() if isinstance(v, str)})
    return merged


def all_date_keys(data: dict) -> set:
    keys = set()
    for name in ("selectionsByDate", "stationsByDate", "standbyByDate", "standByDate",
                 "seniorsByDate", "seniorIdsByDate", "seniorsIdsByDate"):
        keys.update((data.get(name) or {}).keys())
    return keys


# --- Stations per date ---
# stationsByDate[date] is the source of truth for which stations a day shows
# and in what order. A station that only appears in selectionsByDate is
# ignored when stationsByDate lists the day's stations.

def assigned_station_keys(data: dict, date_key: str) -> list:
    """selectionsByDate keys of this date that have at least one staff id."""
    selections = (data.get("selectionsByDate") or {}).get(date_key) or {}
    return [key for key, staff_ids in selections.items() if as_ordered_list(staff_ids)]


def config_order_key(ctx: ScheduleContext, key: str) -> tuple:
    """Order in the Firestore stations collection; unknown/custom keys last."""
    index = ctx.config_index.get(key)
    return (index is None, index if index is not None else 0, key)


def listed_station_entries(raw: list) -> list:
    """Old shape: an ordered Station[] — exactly these stations, in this
    order (entries flagged removedFromDay excluded)."""
    entries = []
    for ext in raw:
        if isinstance(ext, dict) and ext.get("id") and not ext.get("removedFromDay"):
            custom_name = ext.get("name") if is_custom_station(ext["id"]) else None
            entries.append((ext["id"], custom_name))
    return entries


def override_station_entries(ctx: ScheduleContext, data: dict, date_key: str, overrides: dict) -> list:
    """New shape: {removedStationIds, addedOptionalStationIds, manualStations,
    stationOrder}. It doesn't list the day's regular stations, so those are
    the assigned ones; everything in removedStationIds is dropped. Order:
    stationOrder first, then the stations collection's order."""
    removed = set(as_ordered_list(overrides.get("removedStationIds")))
    manual = {m["id"]: m.get("name") for m in as_ordered_list(overrides.get("manualStations")) if isinstance(m, dict) and m.get("id")}
    station_order = as_ordered_list(overrides.get("stationOrder"))
    keys = list(dict.fromkeys(
        station_order + as_ordered_list(overrides.get("addedOptionalStationIds")) + list(manual)
        + assigned_station_keys(data, date_key)
    ))
    order_index = {key: i for i, key in enumerate(station_order)}
    keys = sorted(
        (key for key in keys if key not in removed),
        key=lambda key: (order_index.get(key, len(order_index)), config_order_key(ctx, key)),
    )
    return [(key, manual.get(key) if is_custom_station(key) or key in manual else None) for key in keys]


def station_entries_for_date(ctx: ScheduleContext, d: date, date_key: str, data: dict, label: str) -> list:
    """The day's stations in display order: [(station_key, custom_name)] —
    custom_name is set only for custom stations.
    - stationsByDate[date] is a list: exactly those stations, in that order.
    - stationsByDate[date] is the override map: see override_station_entries.
    - no stationsByDate[date]: the assigned stations, in the stations
      collection's order."""
    raw = (data.get("stationsByDate") or {}).get(date_key)
    if isinstance(raw, dict) and not any(k in raw for k in DAY_OVERRIDE_KEYS):
        raw = as_ordered_list(raw)
    if isinstance(raw, list):
        entries = listed_station_entries(raw)
    elif isinstance(raw, dict):
        entries = override_station_entries(ctx, data, date_key, raw)
    else:
        entries = [(key, None) for key in sorted(assigned_station_keys(data, date_key), key=lambda k: config_order_key(ctx, k))]

    result, seen_keys = [], set()
    for key, custom_name in entries:
        if key in seen_keys:
            # Old lists can repeat a station; one schedule station per key.
            ctx.report.append(f"DUPLICATE station in stationsByDate: {label} date={date_key} key={key!r} (kept first)")
            continue
        seen_keys.add(key)
        if is_custom_station(key) or custom_name is not None:
            if not custom_name:
                ctx.report.append(f"CUSTOM station without name: {label} date={date_key} key={key!r} (key used as name)")
                custom_name = key
        result.append((key, custom_name))
    return result


def build_assignments(ctx: ScheduleContext, staff_ids: list, stand_by_ids: set, label: str, date_key: str) -> list:
    assignments = []
    for staff_id in as_ordered_list(staff_ids):
        if str(staff_id) not in ctx.staff_ids:
            ctx.report.append(f"UNKNOWN staff member: {label} date={date_key} id={staff_id!r} (skipped)")
            continue
        assignments.append(ScheduleAssignmentEntry(staff_member_id=UUID(str(staff_id)), is_stand_by=str(staff_id) in stand_by_ids))
    return assignments


def build_day(ctx: ScheduleContext, day: date, date_key: str, data: dict, seniors: dict, label: str) -> ScheduleDayEntry:
    selections = (data.get("selectionsByDate") or {}).get(date_key) or {}
    stand_by_map = data.get("standbyByDate") or data.get("standByDate") or {}
    stand_by_ids = {str(s) for s in as_ordered_list(stand_by_map.get(date_key))}

    visible = station_entries_for_date(ctx, day, date_key, data, label)
    visible_keys = {key for key, _ in visible}
    for key, staff_ids in selections.items():
        if key not in visible_keys and as_ordered_list(staff_ids):
            ctx.report.append(
                f"SELECTION ignored (station not in stationsByDate): {label} date={date_key} station={key!r} "
                f"staff={[str(x) for x in as_ordered_list(staff_ids)]}"
            )

    # A staff member may sit on several stations of one day (mandatory +
    # optional/custom) — every one is kept; only a repeat inside the same
    # station's list is collapsed (unique per schedule station). Stand-by is
    # set only on stations with enable_stand_by (custom stations never), at
    # most once per staff member per day.
    stations, stand_by_given, station_by_id = [], set(), {}
    for order, (key, custom_name) in enumerate(visible):
        station = None if custom_name else ctx.stations.get(key)
        station_stand_by_ids = (stand_by_ids - stand_by_given) if station is not None and station.enable_stand_by else set()
        assignments, station_staff_ids = [], set()
        for assignment in build_assignments(ctx, selections.get(key) or [], station_stand_by_ids, label, date_key):
            staff_id = str(assignment.staff_member_id)
            if staff_id in station_staff_ids:
                continue
            station_staff_ids.add(staff_id)
            assignments.append(assignment)
        stand_by_given |= {str(a.staff_member_id) for a in assignments if a.is_stand_by}
        station_id = None if custom_name else ensure_placeholder_station(ctx.db, ctx.unit_id, key, ctx.stations, ctx.report).id
        if station_id is not None and station_id in station_by_id:
            # Two Firestore keys resolving to the same Postgres station: one
            # schedule station per (date, station_id) — merge the assignments.
            existing = station_by_id[station_id]
            known = {str(a.staff_member_id) for a in existing.assignments}
            existing.assignments.extend(a for a in assignments if str(a.staff_member_id) not in known)
            ctx.report.append(
                f"MERGED stations: {label} date={date_key} key={key!r} -> station_id={station_id} (same station as an earlier key)"
            )
            continue
        entry = ScheduleStationEntry(
            station_id=station_id, custom_name=custom_name, display_order=order, assignments=assignments,
        )
        if station_id is not None:
            station_by_id[station_id] = entry
        stations.append(entry)

    for staff_id in sorted(stand_by_ids - stand_by_given):
        ctx.report.append(
            f"STAND-BY not applied: {label} date={date_key} staff={staff_id!r} "
            f"(no assignment on a stand-by-enabled station that day; assignments kept)"
        )

    return ScheduleDayEntry(date=day, senior_id=resolve_senior(ctx, seniors.get(date_key), label, date_key), stations=stations)


def resolve_senior(ctx: ScheduleContext, senior_id: Optional[str], label: str, date_key: str) -> Optional[UUID]:
    if not senior_id:
        return None
    if senior_id not in ctx.senior_ids:
        ctx.report.append(f"UNKNOWN senior: {label} date={date_key} id={senior_id!r} (skipped)")
        return None
    return UUID(senior_id)


def parse_schedule_date_key(key: str) -> Optional[date]:
    """"YYYY-MM-DD", or (older docs) the UTC instant of local midnight such as
    "2026-06-02T21:00:00.000Z", which is the local date 2026-06-03."""
    if "T" not in key:
        return parse_date(key)
    instant = parse_datetime(key)
    return instant.astimezone(LOCAL_TZ).date() if instant else None


def schedule_dates(ctx: ScheduleContext, data: dict, label: str) -> list:
    """[(date, date_key)] sorted by date. When two keys land on the same date
    (a doc mixing both formats), the plain "YYYY-MM-DD" key wins."""
    by_day: dict = {}
    for date_key in sorted(all_date_keys(data)):
        day = parse_schedule_date_key(date_key)
        if day is None:
            ctx.report.append(f"INVALID date key: {label} key={date_key!r} (skipped)")
            continue
        current = by_day.get(day)
        if current is not None:
            kept, dropped = (current, date_key) if "T" not in current else (date_key, current)
            ctx.report.append(f"DUPLICATE date key: {label} date={day} kept={kept!r} ignored={dropped!r}")
            by_day[day] = kept
        else:
            by_day[day] = date_key
    return sorted(by_day.items())


def split_snapshot_by_month(ctx: ScheduleContext, snapshot: Snapshot) -> dict:
    """Returns {"YYYY-MM": [ScheduleDayEntry]}."""
    data = snapshot.data
    seniors = senior_ids_by_date(data)
    days_by_month = defaultdict(list)
    for day, date_key in schedule_dates(ctx, data, snapshot.label):
        entry = build_day(ctx, day, date_key, data, seniors, snapshot.label)
        if entry.stations or entry.senior_id:
            days_by_month[day.strftime("%Y-%m")].append(entry)
    return days_by_month


def month_fingerprint(days: list) -> tuple:
    return tuple(
        (
            d.date, d.senior_id,
            tuple(
                (s.station_id, s.custom_name, s.display_order,
                 tuple(sorted((str(a.staff_member_id), a.is_stand_by) for a in s.assignments)))
                for s in d.stations
            ),
        )
        for d in days
    )


def migration_pins(ctx: ScheduleContext, month: str, days: list) -> list:
    """Same rule as ScheduleService._resolve_pins for a first save: every
    version in effect during the month, for every station shown or active."""
    start, end = month_bounds(month)
    shown = {s.station_id for d in days for s in d.stations if s.station_id is not None}
    in_month = {
        sid: versions_in_month(versions, start, end)
        for sid, versions in StationRepository(ctx.db).get_unit_versions(ctx.unit_id).items()
    }
    considered = shown | {sid for sid, versions in in_month.items() if any(not v.is_retired for v in versions)}
    return [v for sid in considered for v in in_month.get(sid, [])]


def migrate_schedule(fs, ctx: ScheduleContext, division_id: UUID, dry_run: bool) -> None:
    repository = ScheduleRepository(ctx.db)
    last_by_month: dict = {}  # month -> (fingerprint, is_published)
    counts: dict = defaultdict(int)

    for snapshot in collect_snapshots(fs, ctx, division_id):
        for month, days in sorted(split_snapshot_by_month(ctx, snapshot).items()):
            fingerprint = month_fingerprint(days)
            previous = last_by_month.get(month)
            if previous and previous[0] == fingerprint and (not snapshot.is_published or previous[1]):
                continue
            last_by_month[month] = (fingerprint, snapshot.is_published)
            counts[month] += 1
            print(f"  [{snapshot.label}] month={month} -> version {counts[month]} "
                  f"({len(days)} days, published={snapshot.is_published})")
            if dry_run:
                continue
            repository.save_snapshot(
                ctx.unit_id, month, days, migration_pins(ctx, month, days),
                snapshot.created_by, snapshot.is_published,
                snapshot.constraints_version, snapshot.on_call_version, created_at=snapshot.created_at,
            )

    print("\nVersions per month: " + ", ".join(f"{m}={c}" for m, c in sorted(counts.items())))


# ==========================================
# Entry point
# ==========================================

def print_report(report: list) -> None:
    if not report:
        print("\nEverything resolved — nothing to review.")
        return
    print(f"\n--- Needs manual review ({len(report)}) ---")
    for line in report:
        print(f"  {line}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--unit-id", required=True, help="Target unit UUID to migrate stations and schedule into")
    parser.add_argument("--dry-run", action="store_true", help="Report only, no writes")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)

    unit_id = UUID(args.unit_id)
    dry_run = args.dry_run

    fs = init_firebase()
    db: Session = SessionLocal()

    unit = db.query(Unit).filter(Unit.id == unit_id).first()
    if not unit:
        print(f"ERROR: unit {unit_id} not found")
        sys.exit(1)

    print(f"Migrating stations + schedule into unit={unit_id} — dry_run={dry_run}")
    report: list = []

    print("\n--- Part 1: stations ---")
    stations, configs = migrate_stations(fs, db, unit_id, report)

    print("\n--- Part 1b: on-call station -> station mapping ---")
    migrate_on_call_mappings(db, unit_id, unit.division_id, report)
    if not dry_run:
        # Committed before part 2 so a schedule save's rollback-and-retry
        # can't discard the station upserts.
        db.commit()

    print("\n--- Part 2: schedule ---")
    configs.sort(key=lambda cfg: parse_int(cfg.get("order")) if parse_int(cfg.get("order")) is not None else 999)
    ctx = ScheduleContext(
        db=db, unit_id=unit_id, stations=stations, report=report,
        config_index={cfg["id"]: i for i, cfg in enumerate(configs)},
        staff_ids={str(r[0]) for r in db.query(StaffMember.id).filter(StaffMember.unit_id == unit_id).all()},
        senior_ids={str(r[0]) for r in db.query(Senior.id).filter(Senior.unit_id == unit_id).all()},
    )
    migrate_schedule(fs, ctx, unit.division_id, dry_run)

    if dry_run:
        db.rollback()
    else:
        db.commit()  # covers placeholder stations created after the last schedule save
    db.close()

    print_report(report)
    print("\nDone." + (" (dry run — no writes were made)" if dry_run else ""))
    if not dry_run:
        logging.getLogger(__name__).info("Successfully migrated stations and schedule for unit_id=%s", unit_id)


if __name__ == "__main__":
    main()
