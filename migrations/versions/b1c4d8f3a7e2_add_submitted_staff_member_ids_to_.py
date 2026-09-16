"""add_submitted_staff_member_ids_to_constraints

Revision ID: b1c4d8f3a7e2
Revises: 9f2a7c1e6b3d
Create Date: 2026-09-14 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'b1c4d8f3a7e2'
down_revision: Union[str, Sequence[str], None] = '9f2a7c1e6b3d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'constraints',
        sa.Column('submitted_staff_member_ids', postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=False, server_default='{}'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('constraints', 'submitted_staff_member_ids')
