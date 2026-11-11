"""add_on_call_certifications_to_staff

Revision ID: c8d2f4a6b9e3
Revises: a7c4e1d8b3f2
Create Date: 2026-11-10 00:00:00.000000

Staff members get `month_on_call_certifications`
({"YYYY-MM": {"<on-call station id>": rank}}, mirroring
`month_certifications`): the on-call stations a member is certified for
each month, with the member's rank (1..5, 5 = strongest) in each one, used
to balance on-call pairings. Existing rows are backfilled with {}.

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'c8d2f4a6b9e3'
down_revision: Union[str, Sequence[str], None] = 'a7c4e1d8b3f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'staff_members',
        sa.Column('month_on_call_certifications', postgresql.JSONB(astext_type=sa.Text()), server_default='{}'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('staff_members', 'month_on_call_certifications')
