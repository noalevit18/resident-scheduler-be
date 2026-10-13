"""add_active_on_half_day_to_stations

Revision ID: f3a8b6c2d9e1
Revises: e5b2c9d4a1f7
Create Date: 2026-10-12 00:00:00.000000

A partial (half) day on a weekday now follows `active_on_half_day` instead
of the day of week, like a sabbatical follows `active_on_sabbatical` (Friday
and Saturday keep following active_days). Existing stations active on any
weekday, and every-x-days stations (which can land on any day), are
backfilled as active on half days, so they keep appearing on them.

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f3a8b6c2d9e1'
down_revision: Union[str, Sequence[str], None] = 'e5b2c9d4a1f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

WEEKDAYS = '{0,1,2,3,4}'
TABLES = ('stations', 'station_versions')


def upgrade() -> None:
    """Upgrade schema."""
    for table in TABLES:
        op.add_column(
            table,
            sa.Column('active_on_half_day', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        )
        op.execute(
            f"UPDATE {table} SET active_on_half_day = true "
            f"WHERE active_days && '{WEEKDAYS}'::int[] OR recurrence_type = 'EVERY_X_DAYS'"
        )


def downgrade() -> None:
    """Downgrade schema."""
    for table in TABLES:
        op.drop_column(table, 'active_on_half_day')
