"""
One-time migration: Firestore on-call ("attendings") data -> Postgres, in
two parts run together against a single unit:

1. `attendings/main_attending` doc's `shiftStations` field (a flat array of
   station-name strings, e.g. ["פגייה", "מיון1", ...]) -> `on_call_stations`
   table. Matched by (division_id, name) among active (non-soft-deleted)
   rows: an existing row is left as-is, a missing one is created. Idempotent.

2. `attendings/main_attending` doc's `attending` field (a map keyed by
   non-zero-padded, 0-indexed-month date strings, e.g. "2026-9-1" for
   October 1st — see `parse_attending_date_key` — each value an array of
   `{attendingStation, id}` objects) -> `on_call_shifts` table (the
   insert-only, versioned monthly on-call calendar). `id` is expected to
   already hold a Postgres `staff_members.id` UUID — same assumption
   `migrate_constraints_to_postgres.py` makes for `residents`
   (`scripts/migrate_residents_to_staff.py` is expected to have already
   rewritten these ids). The station name is read from `attendingStation`,
   falling back to the older `comment` field when `attendingStation` is
   absent (older monthly entries used `comment` for the same purpose), then
   resolved to an `on_call_stations.id` via the cache built in part 1 —
   creating a new station on the fly (added to the same cache) if the name
   isn't already known, since older data routinely used station names never
   listed in `shiftStations`.

`on_call_shifts` tracks its current version per (unit_id, month) in the
dedicated `monthly_on_call_versions` table: part 2 groups entries by month
and inserts one full snapshot per month via the same
`OnCallShiftRepository.save_entries_snapshot` the API's save endpoint uses,
with no `created_by` (nullable — no acting user in a script) and
`is_published=False` (migrated data starts as an unpublished draft; publish
explicitly via the API once reviewed). Note this means re-running the
script for real a second time creates a *new* version rather than being a
true no-op for part 2 — harmless (the latest version is what reads
return) but worth knowing before re-running against a unit already
migrated. Part 1 stays idempotent (matched by name, never renamed).

Does NOT touch `staff_member_submissions` or `staff_member_submission_metadata`
— both are self-serve-form tables with no Firestore equivalent.

Usage:
    python -m scripts.migrate_on_call_to_postgres --unit-id <UUID> [--dry-run]

`--dry-run` runs every Firestore read and DB lookup/create but skips real
writes and rolls back at the end — it only prints what would be
created/updated. Always dry-run first.
"""

import argparse
import os
import re
import sys
from collections import defaultdict
from datetime import date
from typing import Optional
from uuid import UUID

import firebase_admin
from firebase_admin import credentials, firestore
from sqlalchemy.orm import Session

sys.path.insert(0, ".")

from app.database import SessionLocal  # noqa: E402
from app.models.models import OnCallStation, StaffMember, Unit  # noqa: E402
from app.repositories.on_call_shift_repository import OnCallShiftRepository  # noqa: E402
from app.schemas.schemas import OnCallShiftEntry  # noqa: E402


def init_firebase() -> firestore.Client:
    firebase_project_id = os.getenv("FIREBASE_PROJECT_ID")
    init_options = {"projectId": firebase_project_id} if firebase_project_id else None
    try:
        firebase_admin.get_app()
    except ValueError:
        firebase_admin.initialize_app(credentials.ApplicationDefault(), options=init_options)
    return firestore.client(database_id=os.getenv("FIRESTORE_DATABASE_ID"))


# Hebrew text mixed with ASCII digits (e.g. "מיון 1") is prone to invisible
# bidi/formatting control characters (U+200E/U+200F left-to-right/
# right-to-left marks, U+202A-U+202E embeddings, U+2066-U+2069 isolates)
# sneaking in depending on which UI/input path wrote the string — two
# values that display identically can then compare unequal. Also collapse
# whitespace (a stray double space, or a non-breaking space U+00A0) for the
# same reason. Without this, `shiftStations` entries and `attendingStation`
# values that look identical fail to match and get silently dropped.
_BIDI_CONTROL_CHARS = "".join(chr(c) for c in (
    0x200E, 0x200F,  # LRM, RLM
    0x202A, 0x202B, 0x202C, 0x202D, 0x202E,  # LRE, RLE, PDF, LRO, RLO
    0x2066, 0x2067, 0x2068, 0x2069,  # LRI, RLI, FSI, PDI
))


def normalize_station_name(name: Optional[str]) -> Optional[str]:
    if name is None:
        return None
    cleaned = "".join(ch for ch in name if ch not in _BIDI_CONTROL_CHARS)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned or None


def resolve_station_name(item: dict) -> Optional[str]:
    """Newer `attending` entries hold the station name under
    `attendingStation`. Older entries instead used `comment` for the same
    field — fall back to it only when `attendingStation` is absent, since
    that's the field the current schema/UI actually writes."""
    raw = item.get("attendingStation")
    if raw is None:
        raw = item.get("comment")
    return normalize_station_name(raw)


def parse_attending_date_key(key: str) -> date:
    """Firestore keys are non-zero-padded 'YYYY-M-D' (e.g. '2026-9-1') with
    the month 0-indexed — unlike every other date-keyed record in this app
    (see normalizeOnCallDateKey in the FE's scheduleMergeUtils.ts), a
    leftover from the old FE writing `date.getMonth()` directly. Split and
    int-cast each part rather than strptime, which requires zero-padding,
    and add 1 to the month to convert to calendar-month."""
    year_s, month_s, day_s = key.split("-")
    return date(int(year_s), int(month_s) + 1, int(day_s))


def sync_on_call_stations(doc_data: dict, db: Session, division_id: UUID, dry_run: bool) -> dict:
    """Part 1: `shiftStations` array -> `on_call_stations` table. Returns a
    {name: id} cache for part 2."""
    raw_names = doc_data.get("shiftStations") or []
    names = [n for n in (normalize_station_name(n) for n in raw_names) if n]
    print(f"Found {len(raw_names)} station names in Firestore shiftStations: {raw_names!r}")
    print(f"  normalized: {names!r}")

    existing = {
        row.name: row.id
        for row in db.query(OnCallStation.name, OnCallStation.id)
        .filter(OnCallStation.division_id == division_id, OnCallStation.is_deleted.is_(False))
        .all()
    }
    cache = dict(existing)
    created = 0
    for name in names:
        if name in cache:
            continue
        print(f"  create on_call_station name={name!r}")
        if not dry_run:
            row = OnCallStation(division_id=division_id, name=name, created_by=None)
            db.add(row)
            db.flush()
            cache[name] = row.id
        created += 1
    print(f"Stations: existing={len(existing)} created={created}")
    return cache


def sync_on_call_shifts(
    doc_data: dict, db: Session, unit_id: UUID, division_id: UUID, station_cache: dict, dry_run: bool,
) -> None:
    """Part 2: `attending` map -> `on_call_shifts` table."""
    attending = doc_data.get("attending") or {}
    print(f"Found {len(attending)} dates in Firestore attending map")

    known_staff_ids = {str(row[0]) for row in db.query(StaffMember.id).filter(StaffMember.unit_id == unit_id).all()}

    entries_by_month: dict = defaultdict(dict)
    skipped = 0
    stations_created = 0

    for date_key, items in attending.items():
        try:
            entry_date = parse_attending_date_key(date_key)
        except ValueError as e:
            print(f"  [{date_key!r}] WARNING: could not parse date key ({e}), skipping this date entirely")
            skipped += len(items)
            continue
        month = entry_date.strftime("%Y-%m")
        assignments: dict = {}

        for item in items:
            staff_id = item.get("id")
            station_name = resolve_station_name(item)
            if staff_id not in known_staff_ids:
                print(f"  [{date_key}] WARNING: staff_member {staff_id} not found in unit's staff_members, skipping")
                skipped += 1
                continue
            if station_name is None:
                print(f"  [{date_key}] WARNING: no attendingStation/comment on entry for staff_member {staff_id}, skipping")
                skipped += 1
                continue
            station_id = station_cache.get(station_name)
            if station_id is None:
                print(f"  [{date_key}] station name {station_name!r} not in on_call_stations, creating it")
                if dry_run:
                    # No real id to assign without writing — report the
                    # entry as skipped-for-now rather than fabricate one.
                    skipped += 1
                    continue
                row = OnCallStation(division_id=division_id, name=station_name, created_by=None)
                db.add(row)
                db.flush()
                station_cache[station_name] = row.id
                station_id = row.id
                stations_created += 1
            assignments[staff_id] = station_id

        if assignments:
            print(f"  [{date_key}] station_assignments={assignments}")
            entries_by_month[month][entry_date] = OnCallShiftEntry(date=entry_date, station_assignments=assignments)

    print(f"Shifts: skipped_entries={skipped} stations_created={stations_created}")

    repository = OnCallShiftRepository(db)
    for month, entries_by_date in sorted(entries_by_month.items()):
        entries = list(entries_by_date.values())
        print(f"\nSaving on-call snapshot for month={month}: {len(entries)} dates")
        if not dry_run:
            repository.save_entries_snapshot(unit_id, division_id, month, entries, created_by=None, is_published=False)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--unit-id", required=True, help="Target unit UUID to migrate on-call stations and shifts into")
    parser.add_argument("--dry-run", action="store_true", help="Report only, no writes")
    args = parser.parse_args()

    unit_id = UUID(args.unit_id)
    dry_run = args.dry_run

    fs = init_firebase()
    db: Session = SessionLocal()

    unit = db.query(Unit).filter(Unit.id == unit_id).first()
    if not unit:
        print(f"ERROR: unit {unit_id} not found")
        sys.exit(1)
    division_id = unit.division_id

    print(f"Migrating on-call stations + shifts into unit={unit_id} (division={division_id}) — dry_run={dry_run}")

    doc = fs.collection("attendings").document("main_attending").get()
    if not doc.exists:
        print("No attendings/main_attending doc found — nothing to migrate.")
        db.close()
        return
    doc_data = doc.to_dict() or {}

    print("\n--- Part 1: on-call stations ---")
    station_cache = sync_on_call_stations(doc_data, db, division_id, dry_run)

    print("\n--- Part 2: on-call shifts calendar ---")
    sync_on_call_shifts(doc_data, db, unit_id, division_id, station_cache, dry_run)

    if dry_run:
        db.rollback()
    else:
        db.commit()  # covers any staged on_call_station changes not already committed by part 2's snapshot save
    db.close()
    print("\nDone." + (" (dry run — no writes were made)" if dry_run else ""))


if __name__ == "__main__":
    main()
