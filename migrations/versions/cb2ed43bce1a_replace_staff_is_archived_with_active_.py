"""replace_staff_is_archived_with_active_archived_month

Revision ID: cb2ed43bce1a
Revises: 8ef3cc063cb1
Create Date: 2026-08-18 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cb2ed43bce1a'
down_revision: Union[str, Sequence[str], None] = '8ef3cc063cb1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('staff_members', sa.Column('active_since', sa.Text()))
    op.add_column('staff_members', sa.Column('archived_since', sa.Text()))
    op.drop_column('staff_members', 'is_archived')


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column(
        'staff_members', sa.Column('is_archived', sa.Boolean(), nullable=False, server_default=sa.false())
    )
    op.drop_column('staff_members', 'archived_since')
    op.drop_column('staff_members', 'active_since')
