"""add firebase_uid to users

Revision ID: 4272c79be86a
Revises: 5c1dfefc6882
Create Date: 2026-09-01 10:17:19.956825

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4272c79be86a'
down_revision: Union[str, Sequence[str], None] = '5c1dfefc6882'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('users', sa.Column('firebase_uid', sa.Text(), nullable=True))
    op.create_index('idx_users_firebase_uid', 'users', ['firebase_uid'], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('idx_users_firebase_uid', table_name='users')
    op.drop_column('users', 'firebase_uid')
