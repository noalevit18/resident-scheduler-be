"""add clerk StaffRole

Revision ID: 5c1dfefc6882
Revises: d4a7e5f91b2c
Create Date: 2026-08-31 21:28:25.094444

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '5c1dfefc6882'
down_revision: Union[str, Sequence[str], None] = 'd4a7e5f91b2c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ALTER TYPE ... ADD VALUE cannot run inside a transaction block on
    # Postgres, so this must execute in an autocommit block.
    # Note: the existing labels are the enum member *names* (uppercase),
    # since SQLAlchemy's Enum type binds Python enums by .name by default
    # (see the initial migration's 'ATTENDING', 'RESIDENT', ... labels).
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE staffrole ADD VALUE IF NOT EXISTS 'CLERK'")


def downgrade() -> None:
    """Downgrade schema."""
    # Postgres has no DROP VALUE for enums. Removing 'CLERK' requires
    # recreating the type and will fail if any row still uses it.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE staffrole RENAME TO staffrole_old")
        op.execute(
            "CREATE TYPE staffrole AS ENUM "
            "('ATTENDING', 'RESIDENT', 'INTERN', 'NURSE')"
        )
        op.execute(
            "ALTER TABLE users "
            "ALTER COLUMN staff_role TYPE staffrole "
            "USING staff_role::text::staffrole"
        )
        op.execute("DROP TYPE staffrole_old")
