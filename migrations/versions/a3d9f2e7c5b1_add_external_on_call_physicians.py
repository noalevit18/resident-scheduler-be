"""add_external_on_call_physicians

Revision ID: a3d9f2e7c5b1
Revises: b7e4c2a9f1d6
Create Date: 2026-11-19 00:00:00.000000

External on-call physicians: physicians who take on-call shifts for a unit
without being its residents. They are not staff members.

- `external_on_call_physicians`:
  - `unit_id`: the unit whose on-call schedule they are part of.
  - `name`: display name.
  - `user_id`: the connected regular user (nullable: none).
  - `activation_date`: the first day the physician can be on call, set
    explicitly (NOT NULL, no default; may be in the future).
  - `created_at`, `created_by`: who added them and when.
  - `archived_at`, `archived_by`: when and by whom they were archived (NULL:
    active). Archived rows stay for history and can be unarchived, which
    clears both.
  - Names are not unique. Among active rows, a connected user (when set)
    is unique per unit.

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'a3d9f2e7c5b1'
down_revision: Union[str, Sequence[str], None] = 'b7e4c2a9f1d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'external_on_call_physicians',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.func.gen_random_uuid()),
        sa.Column('unit_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('units.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('activation_date', sa.Date(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('archived_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('archived_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
    )
    op.create_index('ix_external_on_call_physicians_unit_id', 'external_on_call_physicians', ['unit_id'])
    op.create_index(
        'ux_external_on_call_physicians_unit_id_user_id_active', 'external_on_call_physicians',
        ['unit_id', 'user_id'], unique=True,
        postgresql_where=sa.text('archived_at IS NULL AND user_id IS NOT NULL'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ux_external_on_call_physicians_unit_id_user_id_active', table_name='external_on_call_physicians')
    op.drop_index('ix_external_on_call_physicians_unit_id', table_name='external_on_call_physicians')
    op.drop_table('external_on_call_physicians')
