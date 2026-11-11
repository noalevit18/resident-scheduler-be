"""add_color_to_on_call_stations

Revision ID: d9e3a5b7c1f4
Revises: c8d2f4a6b9e3
Create Date: 2026-11-10 00:00:00.000000

On-call stations get a `color` ({"bg", "text", "border", "is_custom"}),
the same JSONB shape as constraint_types.color. Nullable: existing stations
have none until an admin picks one.

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'd9e3a5b7c1f4'
down_revision: Union[str, Sequence[str], None] = 'c8d2f4a6b9e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('on_call_stations', sa.Column('color', postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('on_call_stations', 'color')
