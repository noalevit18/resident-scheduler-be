"""
One-time setup: creates a dedicated Account -> Division -> Unit -> User
hierarchy for the frontend's Playwright E2E suite, isolated from any real
data in this database.

The frontend E2E tests sign in as Firebase Auth users provisioned by
`resident-scheduler-fe/e2e/scripts/setup-firebase-test-user.ts` (run that
first). This script provisions the matching side: `users` rows with the
same emails, so POST /users/login (which looks a user up by the Firebase ID
token's email claim) recognizes them instead of force-signing them out.

Creates three units under one division:
  - "E2E Test Unit" (active) — the main unit; home of the default admin
    (unit_admin) and a plain non-admin user.
  - "E2E Test Unit (Inactive)" (inactive) — only for verifying that unit
    dropdowns which intentionally show every unit (e.g. the user
    create/edit modals, via useUnits) list inactive units too, unlike the
    unit-switcher dropdown (useActiveUnits) which deliberately filters them
    out.
  - "E2E Test Unit 2" (active) — home of a second unit_admin, used to verify
    a unit admin can edit their own unit but not another one. Must be
    *active*: the unit-switcher only lists active units, so an inactive
    home unit would never appear there to switch away from.

Everything this script creates hangs off one Account, so tearing it all back
down later is one delete: `DELETE FROM accounts WHERE account_name = ...`
(divisions/units/users cascade via ON DELETE CASCADE).

Idempotent: safe to re-run — looks up each row by its unique name/email
first and reuses it instead of creating duplicates.

Usage:
    python -m scripts.seed_e2e_test_data
"""

import os
import sys

sys.path.insert(0, ".")

from app.database import SessionLocal  # noqa: E402
from app.models.models import Account, Division, Unit, User, UserRole, StaffRole  # noqa: E402

ACCOUNT_NAME = "E2E Test Account"
DIVISION_NAME = "E2E Test Division"
UNIT_NAME = "E2E Test Unit"
INACTIVE_UNIT_NAME = "E2E Test Unit (Inactive)"
UNIT2_NAME = "E2E Test Unit 2"

# Must match resident-scheduler-fe/.env.e2e.
ADMIN_EMAIL = os.environ.get("E2E_TEST_USER_EMAIL", "e2e-test-admin@example.com")
ADMIN_NAME = os.environ.get("E2E_TEST_USER_NAME", "E2E Test Admin")

PLAIN_USER_EMAIL = os.environ.get("E2E_TEST_USER2_EMAIL", "e2e-test-user@example.com")
PLAIN_USER_NAME = os.environ.get("E2E_TEST_USER2_NAME", "E2E Test User")

UNIT2_ADMIN_EMAIL = os.environ.get("E2E_TEST_USER3_EMAIL", "e2e-test-unit2-admin@example.com")
UNIT2_ADMIN_NAME = os.environ.get("E2E_TEST_USER3_NAME", "E2E Test Unit2 Admin")


def get_or_create_unit(db, division_id, name: str, active: bool) -> Unit:
    unit = db.query(Unit).filter_by(division_id=division_id, name=name).one_or_none()
    if unit is None:
        unit = Unit(division_id=division_id, name=name, active=active)
        db.add(unit)
        db.flush()
        print(f"Created unit: id={unit.id} name={unit.name} active={active}")
    else:
        print(f"Reusing existing unit: id={unit.id} name={unit.name}")
    return unit


def get_or_create_user(db, *, division_id, unit_id, name: str, email: str, staff_role: StaffRole, role: UserRole) -> User:
    user = db.query(User).filter_by(email=email.lower()).one_or_none()
    if user is None:
        user = User(
            division_id=division_id,
            unit_id=unit_id,
            name=name,
            email=email.lower(),
            staff_role=staff_role,
            role=role,
            is_active=True,
        )
        db.add(user)
        db.flush()
        print(f"Created user: id={user.id} email={user.email} role={user.role} unit_id={unit_id}")
    else:
        print(f"Reusing existing user: id={user.id} email={user.email} role={user.role}")
        if not user.is_active:
            print("  Warning: this user is is_active=False — /users/login will reject it. Fix manually.")
    return user


def main() -> None:
    db = SessionLocal()
    try:
        account = db.query(Account).filter_by(account_name=ACCOUNT_NAME).one_or_none()
        if account is None:
            account = Account(account_name=ACCOUNT_NAME, country="IL", hospital_name="E2E Test Hospital")
            db.add(account)
            db.flush()
            print(f"Created account: id={account.id} name={account.account_name}")
        else:
            print(f"Reusing existing account: id={account.id} name={account.account_name}")

        division = db.query(Division).filter_by(account_id=account.id, name=DIVISION_NAME).one_or_none()
        if division is None:
            division = Division(account_id=account.id, name=DIVISION_NAME)
            db.add(division)
            db.flush()
            print(f"Created division: id={division.id} name={division.name}")
        else:
            print(f"Reusing existing division: id={division.id} name={division.name}")

        unit = get_or_create_unit(db, division.id, UNIT_NAME, active=True)
        inactive_unit = get_or_create_unit(db, division.id, INACTIVE_UNIT_NAME, active=False)
        unit2 = get_or_create_unit(db, division.id, UNIT2_NAME, active=True)

        get_or_create_user(
            db, division_id=division.id, unit_id=unit.id,
            name=ADMIN_NAME, email=ADMIN_EMAIL,
            staff_role=StaffRole.ATTENDING, role=UserRole.UNIT_ADMIN,
        )
        get_or_create_user(
            db, division_id=division.id, unit_id=unit.id,
            name=PLAIN_USER_NAME, email=PLAIN_USER_EMAIL,
            staff_role=StaffRole.RESIDENT, role=UserRole.USER,
        )
        get_or_create_user(
            db, division_id=division.id, unit_id=unit2.id,
            name=UNIT2_ADMIN_NAME, email=UNIT2_ADMIN_EMAIL,
            staff_role=StaffRole.ATTENDING, role=UserRole.UNIT_ADMIN,
        )

        db.commit()
        print("\nDone. Safe for E2E tests to freely create/delete residents, stations, and schedule")
        print(f"data under unit_id={unit.id} (main) / {unit2.id} (unit 2) without touching any other data.")
        print(f"Inactive unit for dropdown checks: unit_id={inactive_unit.id}")
        print(f"\nTo remove everything this script created later:\n  DELETE FROM accounts WHERE account_name = '{ACCOUNT_NAME}';")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
