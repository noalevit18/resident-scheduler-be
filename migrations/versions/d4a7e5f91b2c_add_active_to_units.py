"""add_active_to_units

Revision ID: d4a7e5f91b2c
Revises: cb2ed43bce1a
Create Date: 2026-08-31 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4a7e5f91b2c'
down_revision: Union[str, Sequence[str], None] = 'cb2ed43bce1a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'units',
        sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.text('false')),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('units', 'active')
