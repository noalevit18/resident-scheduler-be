"""redesign_constraints_and_add_submission_tables

Revision ID: 9f2a7c1e6b3d
Revises: 44eade88750c
Create Date: 2026-09-04 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '9f2a7c1e6b3d'
down_revision: Union[str, Sequence[str], None] = '4272c79be86a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.rename_table('constraints_types', 'constraint_types')
    op.drop_column('constraint_types', 'color')
    op.add_column('constraint_types', sa.Column('color', postgresql.JSONB(astext_type=sa.Text())))
    op.add_column(
        'constraint_types',
        sa.Column('is_hard', sa.Boolean(), nullable=False, server_default=sa.text('false')),
    )
    op.add_column(
        'constraint_types',
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default=sa.text('false')),
    )
    op.add_column(
        'constraint_types',
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )

    # --- users: soft-delete flag ---
    op.add_column(
        'users',
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default=sa.text('false')),
    )
    op.drop_constraint('users_unit_id_email_key', 'users', type_='unique')
    op.drop_constraint('users_division_id_email_key', 'users', type_='unique')
    op.drop_index('idx_users_firebase_uid', table_name='users')
    op.create_index(
        'ux_users_unit_id_email_active', 'users', ['unit_id', 'email'], unique=True,
        postgresql_where=sa.text('is_deleted = false'),
    )
    op.create_index(
        'ux_users_division_id_email_active', 'users', ['division_id', 'email'], unique=True,
        postgresql_where=sa.text('is_deleted = false'),
    )
    op.create_index(
        'ux_users_firebase_uid_active', 'users', ['firebase_uid'], unique=True,
        postgresql_where=sa.text('is_deleted = false'),
    )

    # --- constraints: redesign to an insert-only/versioned monthly calendar ---
    op.drop_constraint('constraints_staff_member_id_fkey', 'constraints', type_='foreignkey')
    op.drop_column('constraints', 'staff_member_id')
    op.drop_column('constraints', 'updated_at')
    op.alter_column('constraints', 'constraint_date', new_column_name='date')
    op.alter_column('constraints', 'constraint_type_id', new_column_name='type_id')
    op.create_foreign_key(
        'constraints_type_id_fkey', 'constraints', 'constraint_types', ['type_id'], ['id'], ondelete='RESTRICT',
    )
    op.add_column(
        'constraints',
        sa.Column('staff_member_ids', postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=False, server_default='{}'),
    )
    op.add_column(
        'constraints',
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
    )
    op.add_column(
        'constraints',
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        'constraints_created_by_fkey', 'constraints', 'users', ['created_by'], ['id'], ondelete='RESTRICT',
    )
    op.create_unique_constraint(
        'constraints_unit_id_type_id_date_version_key', 'constraints', ['unit_id', 'type_id', 'date', 'version'],
    )
    op.create_index(
        'idx_constraints_unit_id_date_version', 'constraints', ['unit_id', 'date', 'version'],
    )

    # --- monthly_constraints_versions: tracks the current version per
    # unit+month independently of the constraints rows themselves ---
    op.create_table(
        'monthly_constraints_versions',
        sa.Column('unit_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('month', sa.Text(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.ForeignKeyConstraint(['unit_id'], ['units.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('unit_id', 'month'),
    )

    # --- constraint_submission_metadata ---
    op.create_table(
        'constraint_submission_metadata',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('unit_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('month', sa.Text(), nullable=False),
        sa.Column('start_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('end_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('pulled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('pulled_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['unit_id'], ['units.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['pulled_by'], ['users.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('unit_id', 'month', name='constraint_submission_metadata_unit_id_month_key'),
    )

    # --- constraints_submissions ---
    op.create_table(
        'constraints_submissions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('unit_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('staff_member_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('month', sa.Text(), nullable=False),
        sa.Column('date', sa.Date(), nullable=True),
        sa.Column('type_id', sa.Integer(), nullable=True),
        sa.Column('comment', sa.Text(), nullable=True),
        sa.Column('submitted_empty', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['unit_id'], ['units.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['staff_member_id'], ['staff_members.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['type_id'], ['constraint_types.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_constraints_submissions_per_date_unique', 'constraints_submissions',
        ['unit_id', 'staff_member_id', 'month', 'date'], unique=True,
        postgresql_where=sa.text('date IS NOT NULL'),
    )
    op.create_index(
        'ix_constraints_submissions_general_comment_unique', 'constraints_submissions',
        ['unit_id', 'staff_member_id', 'month'], unique=True,
        postgresql_where=sa.text('date IS NULL'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_constraints_submissions_general_comment_unique', table_name='constraints_submissions')
    op.drop_index('ix_constraints_submissions_per_date_unique', table_name='constraints_submissions')
    op.drop_table('constraints_submissions')
    op.drop_table('constraint_submission_metadata')
    op.drop_table('monthly_constraints_versions')

    op.drop_index('idx_constraints_unit_id_date_version', table_name='constraints')
    op.drop_constraint('constraints_unit_id_type_id_date_version_key', 'constraints', type_='unique')
    op.drop_constraint('constraints_created_by_fkey', 'constraints', type_='foreignkey')
    op.drop_column('constraints', 'created_by')
    op.drop_column('constraints', 'version')
    op.drop_column('constraints', 'staff_member_ids')
    op.drop_constraint('constraints_type_id_fkey', 'constraints', type_='foreignkey')
    op.alter_column('constraints', 'type_id', new_column_name='constraint_type_id')
    op.alter_column('constraints', 'date', new_column_name='constraint_date')
    op.add_column(
        'constraints',
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.add_column('constraints', sa.Column('staff_member_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        'constraints_staff_member_id_fkey', 'constraints', 'staff_members', ['staff_member_id'], ['id'], ondelete='CASCADE',
    )

    op.rename_table('constraint_types', 'constraint_types')

    op.drop_index('ux_users_firebase_uid_active', table_name='users')
    op.drop_index('ux_users_division_id_email_active', table_name='users')
    op.drop_index('ux_users_unit_id_email_active', table_name='users')
    op.create_index('idx_users_firebase_uid', 'users', ['firebase_uid'], unique=True)
    op.create_unique_constraint('users_division_id_email_key', 'users', ['division_id', 'email'])
    op.create_unique_constraint('users_unit_id_email_key', 'users', ['unit_id', 'email'])

    op.drop_column('users', 'is_deleted')

    op.drop_column('constraints_types', 'updated_at')
    op.drop_column('constraints_types', 'is_deleted')
    op.drop_column('constraints_types', 'is_hard')
    op.drop_column('constraints_types', 'color')
    op.add_column('constraint_types', sa.Column('color', sa.Text(), nullable=True))
