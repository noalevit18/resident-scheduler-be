"""redesign_seniors_table

Revision ID: 2cf0513df568
Revises: 8cf2cde8fdeb
Create Date: 2026-09-26 00:00:00.000000

Replaces the `seniors` table's integer autoincrement id with a
gen_random_uuid() UUID id (so newly-migrated seniors get a Postgres id
usable as a stable reference from the Firestore-managed schedule), and adds
`user_id` (nullable FK to `users`, for optionally linking a senior to a
login), `created_by` (nullable FK to `users`), `is_deleted` (soft
delete — a senior may still be referenced by historical Firestore schedule
days after removal, so rows are never hard-deleted) and `deleted_by`
(nullable FK to `users`, set to the acting user when a senior is soft-
deleted). Drops `updated_at` (nothing yet updates a senior after creation
besides delete).

The `seniors` feature has no production data yet (unused by the frontend),
so this drops and recreates the table rather than an in-place column
migration.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '2cf0513df568'
down_revision: Union[str, Sequence[str], None] = '8cf2cde8fdeb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_table('seniors')
    op.create_table(
        'seniors',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('unit_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('deleted_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(['unit_id'], ['units.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['deleted_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('seniors')
    op.create_table(
        'seniors',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('unit_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['unit_id'], ['units.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
