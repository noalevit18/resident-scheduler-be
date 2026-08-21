"""add_monthly_tracking_to_staff_members

Revision ID: 8ef3cc063cb1
Revises: 3f16172890c5
Create Date: 2026-08-18 14:03:23.995453

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '8ef3cc063cb1'
down_revision: Union[str, Sequence[str], None] = '3f16172890c5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('staff_members', sa.Column('user_id', postgresql.UUID(as_uuid=True)))
    op.create_foreign_key(
        'staff_members_user_id_fkey', 'staff_members', 'users', ['user_id'], ['id'], ondelete='SET NULL'
    )
    op.add_column(
        'staff_members', sa.Column('is_archived', sa.Boolean(), server_default=sa.false())
    )
    op.drop_column('staff_members', 'month')
    op.drop_column('staff_members', 'rotation')
    op.add_column(
        'staff_members',
        sa.Column('month_rotation', postgresql.JSONB(astext_type=sa.Text()), server_default='{}'),
    )
    op.drop_column('staff_members', 'certifications_ids')
    op.add_column(
        'staff_members',
        sa.Column(
            'month_certifications', postgresql.JSONB(astext_type=sa.Text()), server_default='{}'
        ),
    )
    op.alter_column(
        'staff_members', 'created_at',
        existing_type=sa.DateTime(timezone=True),
        existing_server_default=sa.text('now()'),
        nullable=True,
    )
    op.alter_column(
        'staff_members', 'updated_at',
        existing_type=sa.DateTime(timezone=True),
        existing_server_default=sa.text('now()'),
        nullable=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        'staff_members', 'updated_at',
        existing_type=sa.DateTime(timezone=True),
        existing_server_default=sa.text('now()'),
        nullable=False,
    )
    op.alter_column(
        'staff_members', 'created_at',
        existing_type=sa.DateTime(timezone=True),
        existing_server_default=sa.text('now()'),
        nullable=False,
    )
    op.drop_column('staff_members', 'month_certifications')
    op.add_column('staff_members', sa.Column('certifications_ids', postgresql.ARRAY(sa.Integer()), nullable=True))
    op.drop_column('staff_members', 'month_rotation')
    op.add_column('staff_members', sa.Column('rotation', sa.Integer(), nullable=True))
    op.add_column('staff_members', sa.Column('month', sa.Date(), nullable=True))
    op.drop_column('staff_members', 'is_archived')
    op.drop_constraint('staff_members_user_id_fkey', 'staff_members', type_='foreignkey')
    op.drop_column('staff_members', 'user_id')
