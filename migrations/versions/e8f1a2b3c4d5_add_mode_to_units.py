"""add_mode_to_units

Revision ID: e8f1a2b3c4d5
Revises: d9e3a5b7c1f4
Create Date: 2026-11-11 00:00:00.000000

Each unit gets a `mode` describing which kind of staff it schedules
(residents / nursing / attendings / interns). Existing units default to
RESIDENTS.

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'e8f1a2b3c4d5'
down_revision: Union[str, Sequence[str], None] = 'd9e3a5b7c1f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

unit_mode = postgresql.ENUM('RESIDENTS', 'NURSING', 'ATTENDINGS', 'INTERNS', name='unit_mode', create_type=False)


def upgrade() -> None:
    """Upgrade schema."""
    unit_mode.create(op.get_bind(), checkfirst=True)
    op.add_column(
        'units',
        sa.Column('mode', unit_mode, nullable=False, server_default='RESIDENTS'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('units', 'mode')
    unit_mode.drop(op.get_bind(), checkfirst=True)
