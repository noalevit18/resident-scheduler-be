"""
One-time migration: Firestore constraint data -> Postgres, in two parts run
together against a single unit:

1. `constraint_types` collection -> `constraint_types` table. Each Firestore
   document is one constraint type keyed by an arbitrary doc id (e.g. "army"),
   with fields:
       color: { bg, text, border }
       id: <same as the doc id, redundant>
       name: str
       isHard: bool
       isFriday: bool          # legacy FE-only flag, has no Postgres column
       isCustom: bool          # older docs store this alongside `color`
                               # rather than nested in it (current FE model
                               # nests it as color.isCustom) — accepts either
   Matched by (account_id, name): an existing row is updated in place, a new
   one is inserted. Some concepts have two Firestore docs — an older English
   `name` and a newer Hebrew one (e.g. "vacation" / "חופש") — `NAME_ALIASES`
   lists the English keys and the doc for each is skipped entirely (not
   synced under either name): only the Hebrew doc is written to
   constraint_types.

2. `constraints/main_constraints` doc (the `constraintsByDate` blob) ->
   `constraints` table (the insert-only, versioned monthly calendar). Each
   doc key under `constraintsByDate` is an ISO datetime string (e.g.
   "2026-09-01T00:00:00.000Z") mapping to an array of constraint objects:
       { id, name, color, isHard, isCustom, residents: [<staff_member uuid>, ...] }
   Each entry's `name` is canonicalized via `NAME_ALIASES` too, so an item
   still tagged with an old English key (e.g. "vacation") resolves to the
   same type row as the Hebrew-named doc from part 1. Unlike other unmatched
   names, a legacy alias with no matching row is never auto-created — the
   entry is dropped with a warning instead (part 1 is expected to have
   already synced the real Hebrew doc; if it hasn't, that's surfaced rather
   than papered over with a fabricated row).
   `residents` is expected to already hold Postgres `staff_members.id` UUIDs
   — `scripts/migrate_residents_to_staff.py` rewrites this exact doc's
   resident-id references as part of its own run, so this script must run
   after that one. A `name` with no matching row from part 1 is get-or-
   created here too (reuses `build_color` so it still gets a real
   color/is_hard rather than defaults) — part 1 running
   first just means types get their canonical metadata rather than whatever
   a stray constraints-blob entry happens to carry.

`constraints` tracks its current version per (unit_id, month) in the
dedicated `monthly_constraints_versions` table: part 2 groups entries by
month and inserts one full snapshot per month via the same
`ConstraintRepository.save_entries_snapshot` the API's bulk-write endpoint
uses, with no `created_by` (nullable — no acting user in a script). Note this
means re-running the script for real a second time creates a *new* version
rather than being a true no-op for part 2 — harmless (the latest version is
what reads return) but worth knowing before re-running against a unit
already migrated. Part 1 stays idempotent (matched by name, updated in
place).

Does NOT touch `constraint_submission_metadata` or `constraints_submissions`
— both are brand-new self-serve-form tables with no Firestore equivalent.

Firestore's `constraint_types` collection is account-scoped (single-tenant
per Firestore project) while `constraints` is migrated per unit — this
script takes only `--unit-id` and derives `account_id` from it (via the
unit's division), so both parts run against a consistent account in one go.

Usage:
    python -m scripts.migrate_constraints_to_postgres --unit-id <UUID> [--dry-run]

`--dry-run` runs every Firestore read and DB lookup/create but skips real
writes and rolls back at the end — it only prints what would be
created/updated. Always dry-run first.
"""

import argparse
import os
import sys
from collections import defaultdict
from datetime import datetime
from typing import Optional
from uuid import UUID

import firebase_admin
from firebase_admin import credentials, firestore
from sqlalchemy.orm import Session

sys.path.insert(0, ".")

from app.database import SessionLocal  # noqa: E402
from app.models.models import ConstraintType, Division, StaffMember, Unit  # noqa: E402
from app.repositories.constraint_repository import ConstraintRepository  # noqa: E402
from app.schemas.schemas import ConstraintEntry  # noqa: E402


def init_firebase() -> firestore.Client:
    firebase_project_id = os.getenv("FIREBASE_PROJECT_ID")
    init_options = {"projectId": firebase_project_id} if firebase_project_id else None
    try:
        firebase_admin.get_app()
    except ValueError:
        firebase_admin.initialize_app(credentials.ApplicationDefault(), options=init_options)
    return firestore.client(database_id=os.getenv("FIRESTORE_DATABASE_ID"))


def build_color(data: dict) -> Optional[dict]:
    color = data.get("color") or {}
    if not color:
        return None
    return {
        "bg": color.get("bg", ""),
        "text": color.get("text", ""),
        "border": color.get("border", ""),
        "is_custom": bool(color.get("isCustom", data.get("isCustom", False))),
    }


def parse_date_key(date_key: str):
    return datetime.fromisoformat(date_key.replace("Z", "+00:00")).date()


# Firestore has duplicate constraint types for the same concept: an older
# English key (used as both a `constraint_types` doc's `name` and the `name`
# on constraints-blob entries) alongside a newer Hebrew display name (the
# canonical one now stored in `constraint_types`), e.g. "vacation" and
# "חופש". Collapse the English key onto its Hebrew counterpart so both
# resolve to a single constraint_types row instead of migrating as two.
NAME_ALIASES = {
    "vacation": "חופש",
    "sick": "מחלה",
    "preferNot": "מעדיף שלא",
    "want": "רוצה",
    "conference": "כנס",
    "army": "מילואים",
    "inLieu": "יום החזר",
}


def canonical_name(name: str) -> str:
    return NAME_ALIASES.get(name, name)


def sync_constraint_types(fs: firestore.Client, db: Session, account_id: UUID, cache: dict, dry_run: bool) -> None:
    """Part 1: `constraint_types` collection -> `constraint_types` table.
    Populates `cache` (name -> id) as it goes so part 2 can reuse it."""
    docs = list(fs.collection("constraint_types").stream())
    print(f"Found {len(docs)} constraint type documents in Firestore")

    created = updated = skipped = 0
    for snap in docs:
        data = snap.to_dict() or {}
        raw_name = data.get("name") or snap.id
        if raw_name in NAME_ALIASES:
            # Legacy English-keyed doc duplicating a proper Hebrew-named doc
            # elsewhere in this same collection (e.g. "vacation" next to
            # "חופש") — use the Hebrew doc's data, don't sync this one at all.
            print(f"  [{snap.id}] -> skip legacy alias doc name={raw_name!r} (canonical version is {canonical_name(raw_name)!r})")
            skipped += 1
            continue
        name = canonical_name(raw_name)
        color = build_color(data)
        is_hard = bool(data.get("isHard", False))

        existing = db.query(ConstraintType).filter(ConstraintType.account_id == account_id, ConstraintType.name == name).first()

        if existing:
            print(f"  [{snap.id}] -> update existing constraint type id={existing.id} name={name!r}")
            if not dry_run:
                existing.color = color
                existing.is_hard = is_hard
            cache[name] = existing.id
            updated += 1
        else:
            print(f"  [{snap.id}] -> create constraint type name={name!r} is_hard={is_hard} color={color}")
            if not dry_run:
                row = ConstraintType(account_id=account_id, name=name, color=color, is_hard=is_hard)
                db.add(row)
                db.flush()
                cache[name] = row.id
            created += 1

    print(f"Constraint types: created={created} updated={updated} skipped_legacy_alias_docs={skipped}")


def get_or_create_type(db: Session, account_id: UUID, entry: dict, cache: dict, dry_run: bool) -> Optional[int]:
    raw_name = entry.get("name")
    if not raw_name:
        return None
    name = canonical_name(raw_name)
    if name in cache:
        return cache[name]

    row = db.query(ConstraintType).filter(ConstraintType.account_id == account_id, ConstraintType.name == name).first()
    if row:
        cache[name] = row.id
        return row.id

    if raw_name in NAME_ALIASES:
        # Legacy alias with no matching canonical (Hebrew) type synced from
        # constraint_types — never fabricate a new row for it, the caller
        # drops the entry instead.
        return None

    if dry_run:
        return None  # can't allocate a real id without writing

    row = ConstraintType(
        account_id=account_id,
        name=name,
        color=build_color(entry),
        is_hard=bool(entry.get("isHard", False)),
    )
    db.add(row)
    db.flush()
    cache[name] = row.id
    return row.id


def sync_constraints(fs: firestore.Client, db: Session, unit_id: UUID, account_id: UUID, type_cache: dict, dry_run: bool) -> None:
    """Part 2: `constraints/main_constraints` doc -> `constraints` table."""
    doc = fs.collection("constraints").document("main_constraints").get()
    if not doc.exists:
        print("No constraints/main_constraints doc found — nothing to migrate.")
        return

    constraints_by_date = doc.to_dict().get("constraintsByDate", {})
    print(f"Found {len(constraints_by_date)} dates in Firestore")

    known_staff_ids = {str(row[0]) for row in db.query(StaffMember.id).filter(StaffMember.unit_id == unit_id).all()}

    # Keyed by (date, type_id) rather than a plain list: `constraints` has a
    # unique (unit_id, type_id, date, version) constraint, and NAME_ALIASES
    # can make two distinct Firestore items (e.g. one named "vacation", one
    # named "חופש") on the same date resolve to the same type_id — without
    # merging here that produces two rows for the same slot and the snapshot
    # save fails with VersionConflictError. Merge residents when that happens
    # instead of dropping either entry.
    entries_by_month: dict = defaultdict(dict)

    for date_key, items in constraints_by_date.items():
        entry_date = parse_date_key(date_key)
        month = entry_date.strftime("%Y-%m")

        for item in items:
            name = item.get("name")
            type_id = get_or_create_type(db, account_id, item, type_cache, dry_run)
            if type_id is None:
                print(f"  [{date_key}] WARNING: could not resolve type {name!r} to an existing constraint type (dry-run has no id to allocate, or this is a legacy alias name with no matching constraint_types row), skipping")
                continue

            residents = item.get("residents") or []
            staff_member_ids = [r for r in residents if str(r) in known_staff_ids]
            dropped = [r for r in residents if str(r) not in known_staff_ids]
            if dropped:
                print(f"  [{date_key}] WARNING: dropping {len(dropped)} resident id(s) not found in unit's staff_members: {dropped}")

            print(f"  [{date_key}] type={name!r} (type_id={type_id}) staff_member_ids={staff_member_ids}")

            month_entries = entries_by_month[month]
            key = (entry_date, type_id)
            existing_entry = month_entries.get(key)
            if existing_entry:
                merged_ids = list(existing_entry.staff_member_ids)
                merged_ids += [s for s in staff_member_ids if s not in merged_ids]
                print(f"  [{date_key}] NOTE: merging with earlier entry for type_id={type_id} on this date (name alias collapse) -> staff_member_ids={merged_ids}")
                month_entries[key] = ConstraintEntry(type_id=type_id, date=entry_date, staff_member_ids=merged_ids)
            else:
                month_entries[key] = ConstraintEntry(type_id=type_id, date=entry_date, staff_member_ids=staff_member_ids)

    repository = ConstraintRepository(db)
    for month, entries_by_key in sorted(entries_by_month.items()):
        entries = list(entries_by_key.values())
        print(f"\nSaving snapshot for month={month}: {len(entries)} entries")
        if not dry_run:
            repository.save_entries_snapshot(unit_id, month, entries, created_by=None)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--unit-id", required=True, help="Target unit UUID to migrate constraint types and constraints into")
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
    division = db.query(Division).filter(Division.id == unit.division_id).first()
    account_id = division.account_id

    print(f"Migrating constraint types + constraints into unit={unit_id} (account={account_id}) — dry_run={dry_run}")

    type_cache: dict = {}

    print("\n--- Part 1: constraint types ---")
    sync_constraint_types(fs, db, account_id, type_cache, dry_run)

    print("\n--- Part 2: constraints calendar ---")
    sync_constraints(fs, db, unit_id, account_id, type_cache, dry_run)

    if dry_run:
        db.rollback()
    else:
        db.commit()  # covers any staged constraint_type changes not already committed by part 2's snapshot save
    db.close()
    print("\nDone." + (" (dry run — no writes were made)" if dry_run else ""))


if __name__ == "__main__":
    main()
