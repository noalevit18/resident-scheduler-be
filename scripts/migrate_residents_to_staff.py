"""
One-time migration: Firestore `residentsConfig/main_residents` -> Postgres `staff_members`.

Moves the frontend's legacy Firestore-stored "residents" list onto the
backend `staff_members` table, resolving each resident to a matching `User`
row (by case-insensitive/trimmed name match, same rule as the frontend's
"Linked User" dropdown default-select), and rewrites resident-id references
in the other Firestore docs that are *not* migrated by this script
(`schedules/main_schedule`, `schedules/published_schedule`,
`attendings/main_attending`, `constraints/main_constraints`) so they keep
resolving against the new backend-generated ids.

Usage:
    python -m scripts.migrate_residents_to_staff --unit-id <UUID> [--dry-run]

`--dry-run` runs every step (including Firestore reads and DB lookups) but
skips all writes (no INSERTs, no Firestore doc updates) — it only prints the
old-id -> new-id mapping and any unresolved-user report. Always dry-run
first and review the report before running for real.

Idempotent: the new staff_members.id is a deterministic uuid5 derived from
the resident's old Firestore id, so re-running the script (even for real)
will upsert rather than duplicate rows, and the Firestore-doc rewrite step
is a no-op on a second run once the old ids no longer appear anywhere.

month_rotation/month_certifications: start from "rotationByMonth"/
"certificationsByMonth" as-is, then any of FALLBACK_MONTHS missing from
there is filled in from the flat "rotation"/"certifications" field —
months already present are never overwritten. month_certifications id
arrays are always sorted ascending.
"""

import argparse
import os
import sys
import uuid
from datetime import datetime, date
from typing import Any, Optional
from uuid import UUID

import firebase_admin
from firebase_admin import credentials, firestore
from sqlalchemy.orm import Session

sys.path.insert(0, ".")

from app.database import SessionLocal  # noqa: E402
from app.models.models import StaffMember, StaffRotation, StaffCertification, User, Unit  # noqa: E402

# Deterministic UUID namespace for this migration — do not change once run
# against real data, or old-id -> new-id derivation stops matching.
MIGRATION_NAMESPACE = uuid.UUID("6f9c2b3a-6e6e-4b0e-9a1a-6f2a2f0d9a11")

# Rotation name to skip entirely — never resolved to a real staff_rotations
# row, never added to a resident's rotation list. Unlike the old "מחלקה"
# special-case, "מחלקה" is now treated as a regular rotation.
IGNORED_ROTATION = "חיצוני"

# When a resident has no per-month rotation/certification data (no
# "rotationByMonth"/"certificationsByMonth"), the flat "rotation"/
# "certifications" fields are applied to these months instead.
FALLBACK_MONTHS = ["2026-07", "2026-08", "2026-09"]


def init_firebase() -> firestore.Client:
    firebase_project_id = os.getenv("FIREBASE_PROJECT_ID")
    init_options = {"projectId": firebase_project_id} if firebase_project_id else None
    try:
        firebase_admin.get_app()
    except ValueError:
        firebase_admin.initialize_app(credentials.ApplicationDefault(), options=init_options)
    return firestore.client(database_id=os.getenv("FIRESTORE_DATABASE_ID"))


def old_id_to_uuid(old_id: str) -> UUID:
    return uuid.uuid5(MIGRATION_NAMESPACE, str(old_id))


def normalize_name(name: str) -> str:
    return (name or "").strip().lower()


def resolve_user_id(db: Session, unit_id: UUID, division_id: UUID, resident_name: str, report: list) -> Optional[UUID]:
    candidates = db.query(User).filter(
        (User.unit_id == unit_id) | (User.division_id == division_id)
    ).all()
    target = normalize_name(resident_name)
    matches = [u for u in candidates if normalize_name(u.name) == target]

    if len(matches) == 1:
        return matches[0].id
    if len(matches) == 0:
        report.append(f"UNRESOLVED (no matching user): resident name={resident_name!r}")
        return None
    report.append(
        f"AMBIGUOUS ({len(matches)} matching users): resident name={resident_name!r} "
        f"-> candidates={[str(m.id) for m in matches]}"
    )
    return matches[0].id  # best-effort: take the first, flagged for manual review


def resolve_rotation_id(db: Session, division_id: UUID, name: str, cache: dict, dry_run: bool) -> list:
    """Resolves a rotation name to its staff_rotations id, get-or-create.
    IGNORED_ROTATION (and any unset name) maps to an empty id list and is
    never added to the rotation list or created as a row."""
    if not name or name == IGNORED_ROTATION:
        return []
    if name in cache:
        return [cache[name]]

    row = db.query(StaffRotation).filter(
        StaffRotation.division_id == division_id, StaffRotation.name == name
    ).first()
    if row:
        cache[name] = row.id
        return [row.id]

    if dry_run:
        # Can't allocate a real id without writing; report and skip.
        return []

    row = StaffRotation(division_id=division_id, name=name)
    db.add(row)
    db.flush()
    cache[name] = row.id
    return [row.id]


def resolve_certification_ids(db: Session, unit_id: UUID, names: list, cache: dict, dry_run: bool) -> list:
    """Mirrors the frontend useStaff hook's resolveCertificationIds:
    lazily creates a real staff_certifications row for any name (including
    the hardcoded BASE_CERTIFICATIONS) not already present for this unit."""
    ids = []
    for name in names:
        if not name:
            continue
        if name in cache:
            ids.append(cache[name])
            continue

        row = db.query(StaffCertification).filter(
            StaffCertification.unit_id == unit_id, StaffCertification.name == name
        ).first()
        if row:
            cache[name] = row.id
            ids.append(row.id)
            continue

        if dry_run:
            continue

        row = StaffCertification(unit_id=unit_id, name=name)
        db.add(row)
        db.flush()
        cache[name] = row.id
        ids.append(row.id)
    return ids


def build_month_rotation(db: Session, division_id: UUID, r: dict, cache: dict, dry_run: bool) -> dict:
    """Resolves "rotationByMonth" as-is, then makes sure every FALLBACK_MONTHS
    entry is present — any of those months missing from "rotationByMonth" is
    filled in from the flat "rotation" field. Months already present (in or
    out of FALLBACK_MONTHS) are left untouched."""
    by_month = r.get("rotationByMonth") or {}
    month_rotation = {
        month: resolve_rotation_id(db, division_id, name, cache, dry_run) for month, name in by_month.items()
    }

    rotation_name = r.get("rotation")
    if rotation_name:
        fallback_ids = resolve_rotation_id(db, division_id, rotation_name, cache, dry_run)
        for month in FALLBACK_MONTHS:
            month_rotation.setdefault(month, fallback_ids)

    return month_rotation


def build_month_certifications(db: Session, unit_id: UUID, r: dict, cache: dict, dry_run: bool) -> dict:
    """Resolves "certificationsByMonth" as-is, then makes sure every
    FALLBACK_MONTHS entry is present — any of those months missing from
    "certificationsByMonth" is filled in from the flat "certifications"
    field. Months already present are left untouched. Id arrays are always
    sorted ascending."""
    by_month = r.get("certificationsByMonth") or {}
    month_certifications = {
        month: sorted(resolve_certification_ids(db, unit_id, names or [], cache, dry_run))
        for month, names in by_month.items()
    }

    cert_names = r.get("certifications") or []
    if cert_names:
        fallback_ids = sorted(resolve_certification_ids(db, unit_id, cert_names, cache, dry_run))
        for month in FALLBACK_MONTHS:
            month_certifications.setdefault(month, fallback_ids)

    return month_certifications


def serialize_date(v: Any) -> Optional[str]:
    if v is None:
        return None
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    return str(v)


def rewrite_ids_in_place(value: Any, id_map: dict) -> Any:
    """Recursively replaces any string matching an old resident id with its
    new UUID, anywhere it appears in a Firestore document (station selection
    lists, standby lists, senior lists, attending entries, constraint
    container `residents` arrays — all of which store bare resident-id
    strings or {id, ...} objects)."""
    if isinstance(value, str):
        return id_map.get(value, value)
    if isinstance(value, list):
        return [rewrite_ids_in_place(v, id_map) for v in value]
    if isinstance(value, dict):
        return {k: rewrite_ids_in_place(v, id_map) for k, v in value.items()}
    return value


def rewrite_firestore_doc(fs: firestore.Client, collection: str, doc_name: str, id_map: dict, dry_run: bool) -> None:
    ref = fs.collection(collection).document(doc_name)
    snap = ref.get()
    if not snap.exists:
        print(f"  [{collection}/{doc_name}] does not exist, skipping")
        return
    data = snap.to_dict()
    rewritten = rewrite_ids_in_place(data, id_map)
    if rewritten == data:
        print(f"  [{collection}/{doc_name}] no matching ids found, no change")
        return
    print(f"  [{collection}/{doc_name}] rewriting resident-id references")
    if not dry_run:
        ref.set(rewritten)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--unit-id", required=True, help="Target unit UUID to migrate residents into")
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

    print(f"Migrating residents into unit={unit_id} (division={division_id}) — dry_run={dry_run}")

    doc = fs.collection("residentsConfig").document("main_residents").get()
    if not doc.exists:
        print("No residentsConfig/main_residents doc found — nothing to migrate.")
        return

    residents = doc.to_dict().get("residents", [])
    print(f"Found {len(residents)} residents in Firestore")

    report: list = []
    id_map: dict = {}
    rotation_cache: dict = {}
    cert_cache: dict = {}

    for r in residents:
        old_id = r.get("id")
        if not old_id:
            continue
        new_id = old_id_to_uuid(old_id)
        id_map[str(old_id)] = str(new_id)

        user_id = resolve_user_id(db, unit_id, division_id, r.get("name", ""), report)

        month_rotation = build_month_rotation(db, division_id, r, rotation_cache, dry_run)
        month_certifications = build_month_certifications(db, unit_id, r, cert_cache, dry_run)

        print(
            f"  {old_id} -> {new_id}  name={r.get('name')!r}  user_id={user_id}  "
            f"months_rotation={list(month_rotation.keys())}  months_certs={list(month_certifications.keys())}"
        )

        if dry_run:
            continue

        # user_id is nullable — a resident with no resolvable user is still
        # migrated (unmapped), not skipped, so its rotation/certification
        # data isn't lost. It stays flagged in the report above for manual
        # linking later.
        existing = db.query(StaffMember).filter(StaffMember.id == new_id).first()
        if existing:
            existing.name = r.get("name", "")
            existing.user_id = user_id
            existing.active_since = r.get("activeMonth")
            existing.archived_since = r.get("archivedMonth")
            existing.month_rotation = month_rotation
            existing.month_certifications = month_certifications
        else:
            db.add(StaffMember(
                id=new_id,
                unit_id=unit_id,
                user_id=user_id,
                name=r.get("name", ""),
                active_since=r.get("activeMonth"),
                archived_since=r.get("archivedMonth"),
                month_rotation=month_rotation,
                month_certifications=month_certifications,
            ))

    if not dry_run:
        db.commit()
    else:
        db.rollback()

    print("\n--- ID mapping (old Firestore id -> new backend UUID) ---")
    for old_id, new_id in id_map.items():
        print(f"  {old_id} -> {new_id}")

    if report:
        print("\n--- Needs manual review ---")
        for line in report:
            print(f"  {line}")
    else:
        print("\nAll residents resolved to exactly one user — nothing to review.")

    print("\n--- Rewriting resident-id references in other Firestore docs ---")
    rewrite_firestore_doc(fs, "schedules", "main_schedule", id_map, dry_run)
    rewrite_firestore_doc(fs, "schedules", "published_schedule", id_map, dry_run)
    rewrite_firestore_doc(fs, "attendings", "main_attending", id_map, dry_run)
    rewrite_firestore_doc(fs, "constraints", "main_constraints", id_map, dry_run)

    db.close()
    print("\nDone." + (" (dry run — no writes were made)" if dry_run else ""))


if __name__ == "__main__":
    main()
