"""rename_certifications_to_staff_certifications

Revision ID: 3f16172890c5
Revises: cac91e343716
Create Date: 2026-08-18 13:40:26.535062

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3f16172890c5'
down_revision: Union[str, Sequence[str], None] = 'cac91e343716'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.rename_table('certifications', 'staff_certifications')


def downgrade() -> None:
    """Downgrade schema."""
    op.rename_table('staff_certifications', 'certifications')
