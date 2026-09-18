"""add special_dates table

Revision ID: 7d97b6ec9a2e
Revises: b1c4d8f3a7e2
Create Date: 2026-09-17 19:04:37.088538

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '7d97b6ec9a2e'
down_revision: Union[str, Sequence[str], None] = 'b1c4d8f3a7e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'special_dates',
        sa.Column('account_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('label', sa.Text(), nullable=False),
        sa.Column('type', sa.Enum('PARTIAL_DAY', 'SABBATICAL', 'REGULAR', name='special_date_type'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(['account_id'], ['accounts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('account_id', 'date'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('special_dates')
    op.execute('DROP TYPE IF EXISTS special_date_type')
