"""
One-time migration: Firestore `seniors` collection -> Postgres `seniors`
table, plus rewriting the Firestore-managed schedule's per-day senior
references to point at the new Postgres ids.

Part 1 — seniors:
Every doc in the Firestore `seniors` collection (`{name}`, doc id looking
like "sr_<timestamp>_<rand>") becomes one `seniors` row: `name` copied
as-is. `user_id` is intentionally left NULL — linking a senior to a login
is not attempted here, only ever done later through the API. `created_by`
is also left NULL (no acting user in a script).

Idempotent: the new `seniors.id` is a deterministic uuid5 derived from the
Firestore doc id (own namespace from `migrate_residents_to_staff.py`'s, so
the two migrations' ids never collide even though both are derived from
Firestore doc ids), so re-running (even for real) upserts rather than
duplicates.

Part 2 — schedule rewrite:
The Firestore schedule keeps a `seniorsByDate` map (`{"YYYY-MM-DD": "<old
seniors-collection doc id>"}`) on `schedules/main_schedule`,
`schedules/published_schedule`, and every doc in `schedule_versions`. This
does NOT touch or remove `seniorsByDate` — instead it adds a sibling
`seniorIdsByDate` map on each doc, same date keys, values resolved through
the id map from part 1 to the new Postgres UUID (as a string). A date
whose old id has no mapping (senior doc missing/never migrated) is logged
and left out of `seniorIdsByDate` rather than guessed at; `seniorsByDate`
itself is never modified so nothing already reading it breaks.

Usage:
    python -m scripts.migrate_seniors_to_postgres --unit-id <UUID> [--dry-run]

`--dry-run` runs every step (Firestore reads, DB lookups) but skips all
writes (no INSERTs, no Firestore doc updates) — it only prints the old-id
-> new-id mapping and any unresolved schedule-date report. Always dry-run
first and review the report before running for real.
"""

import argparse
import sys
import uuid
from uuid import UUID

from sqlalchemy.orm import Session

sys.path.insert(0, ".")

from app.database import SessionLocal  # noqa: E402
from app.models.models import Senior, Unit  # noqa: E402
from scripts.migrate_residents_to_staff import init_firebase  # noqa: E402

# Deterministic UUID namespace for this migration — distinct from
# migrate_residents_to_staff.py's namespace so ids derived from a Firestore
# seniors-collection doc id never collide with ids derived from an old
# resident id. Do not change once run against real data.
MIGRATION_NAMESPACE = uuid.UUID("b3d7c6a1-4f2e-4a8a-9d1e-8a2f5c6e1b47")

SCHEDULE_DOCS = [("schedules", "main_schedule"), ("schedules", "published_schedule")]


def old_id_to_uuid(old_id: str) -> UUID:
    return uuid.uuid5(MIGRATION_NAMESPACE, str(old_id))


def build_senior_ids_by_date(seniors_by_date: dict, id_map: dict, doc_label: str, report: list) -> dict:
    senior_ids_by_date = {}
    for date_key, old_id in (seniors_by_date or {}).items():
        if not isinstance(old_id, str):
            continue
        new_id = id_map.get(old_id)
        if not new_id:
            report.append(f"UNMAPPED schedule senior id: doc={doc_label} date={date_key} old_id={old_id!r}")
            continue
        senior_ids_by_date[date_key] = new_id
    return senior_ids_by_date


def rewrite_schedule_doc(fs, collection: str, doc_name: str, id_map: dict, dry_run: bool, report: list) -> None:
    label = f"{collection}/{doc_name}"
    ref = fs.collection(collection).document(doc_name)
    snap = ref.get()
    if not snap.exists:
        print(f"  [{label}] does not exist, skipping")
        return
    data = snap.to_dict()
    seniors_by_date = data.get("seniorsByDate")
    if not seniors_by_date:
        print(f"  [{label}] no seniorsByDate field, skipping")
        return

    senior_ids_by_date = build_senior_ids_by_date(seniors_by_date, id_map, label, report)
    print(f"  [{label}] seniorIdsByDate -> {len(senior_ids_by_date)}/{len(seniors_by_date)} dates mapped")
    if dry_run:
        return
    # `update` (not `set`) so every other field on the doc — including the
    # untouched `seniorsByDate` — is left exactly as-is.
    ref.update({"seniorIdsByDate": senior_ids_by_date})


def rewrite_schedule_versions(fs, id_map: dict, dry_run: bool, report: list) -> None:
    docs = list(fs.collection("schedule_versions").stream())
    print(f"  [schedule_versions] {len(docs)} docs found")
    for snap in docs:
        label = f"schedule_versions/{snap.id}"
        data = snap.to_dict() or {}
        seniors_by_date = data.get("seniorsByDate")
        if not seniors_by_date:
            continue
        senior_ids_by_date = build_senior_ids_by_date(seniors_by_date, id_map, label, report)
        print(f"  [{label}] seniorIdsByDate -> {len(senior_ids_by_date)}/{len(seniors_by_date)} dates mapped")
        if dry_run:
            continue
        snap.reference.update({"seniorIdsByDate": senior_ids_by_date})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--unit-id", required=True, help="Target unit UUID to migrate seniors into")
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

    print(f"Migrating seniors into unit={unit_id} — dry_run={dry_run}")

    docs = list(fs.collection("seniors").stream())
    print(f"Found {len(docs)} seniors in Firestore")

    report: list = []
    id_map: dict = {}

    for snap in docs:
        old_id = snap.id
        data = snap.to_dict() or {}
        name = data.get("name", "")
        new_id = old_id_to_uuid(old_id)
        id_map[old_id] = str(new_id)

        print(f"  {old_id} -> {new_id}  name={name!r}")

        if dry_run:
            continue

        existing = db.query(Senior).filter(Senior.id == new_id).first()
        if existing:
            existing.name = name
            existing.is_deleted = False
        else:
            db.add(Senior(
                id=new_id,
                unit_id=unit_id,
                name=name,
            ))

    if not dry_run:
        db.commit()
    else:
        db.rollback()

    print("\n--- ID mapping (old Firestore doc id -> new backend UUID) ---")
    for old_id, new_id in id_map.items():
        print(f"  {old_id} -> {new_id}")

    print("\n--- Rewriting schedule docs: adding seniorIdsByDate (seniorsByDate left untouched) ---")
    for collection, doc_name in SCHEDULE_DOCS:
        rewrite_schedule_doc(fs, collection, doc_name, id_map, dry_run, report)
    rewrite_schedule_versions(fs, id_map, dry_run, report)

    if report:
        print("\n--- Needs manual review ---")
        for line in report:
            print(f"  {line}")
    else:
        print("\nEverything resolved — nothing to review.")

    db.close()
    print("\nDone." + (" (dry run — no writes were made)" if dry_run else ""))


if __name__ == "__main__":
    main()
