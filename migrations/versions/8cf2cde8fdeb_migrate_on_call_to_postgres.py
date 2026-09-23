"""migrate_on_call_to_postgres

Revision ID: 8cf2cde8fdeb
Revises: 7d97b6ec9a2e
Create Date: 2026-09-20 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '8cf2cde8fdeb'
down_revision: Union[str, Sequence[str], None] = '7d97b6ec9a2e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # --- A. drop legacy shift feature (unused, no referential integrity,
    # no seed/test data) ---
    op.drop_table('shifts')
    op.drop_table('shift_stations')

    # --- B. rename the submission-metadata table to be shared by every
    # feature: the window (start_time/end_time) is shared, and pull
    # tracking moves from pulled_at/pulled_by columns into a
    # pull_information jsonb map keyed by feature name, e.g.
    # {"constraints": {"pulled_at": "...", "pulled_by": "<user-id>"}} ---
    op.rename_table('constraint_submission_metadata', 'staff_member_submission_metadata')
    op.add_column(
        'staff_member_submission_metadata',
        sa.Column('pull_information', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
    )
    op.execute("""
        UPDATE staff_member_submission_metadata
        SET pull_information = jsonb_build_object(
            'constraints', jsonb_build_object('pulled_at', pulled_at, 'pulled_by', pulled_by)
        )
        WHERE pulled_at IS NOT NULL
    """)
    op.drop_constraint('constraint_submission_metadata_pulled_by_fkey', 'staff_member_submission_metadata', type_='foreignkey')
    op.drop_column('staff_member_submission_metadata', 'pulled_at')
    op.drop_column('staff_member_submission_metadata', 'pulled_by')
    op.execute(
        "ALTER TABLE staff_member_submission_metadata "
        "RENAME CONSTRAINT constraint_submission_metadata_unit_id_month_key "
        "TO staff_member_submission_metadata_unit_id_month_key"
    )
    # "Deleting" a submission window clears start_time/end_time to null
    # rather than removing the row (which also carries pull_information).
    op.alter_column('staff_member_submission_metadata', 'start_time', nullable=True)

    # --- C. create the on-call feature's own tables ---
    op.create_table(
        'on_call_stations',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('division_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.ForeignKeyConstraint(['division_id'], ['divisions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_on_call_stations_division_id', 'on_call_stations', ['division_id'])
    op.create_index(
        'ux_on_call_stations_division_id_name_active', 'on_call_stations', ['division_id', 'name'],
        unique=True, postgresql_where=sa.text('is_deleted = false'),
    )

    op.create_table(
        'monthly_on_call_versions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('unit_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('month', sa.Text(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('is_published', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('published_at', sa.Date(), nullable=True),
        sa.Column('published_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(['unit_id'], ['units.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['published_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('unit_id', 'month', 'version', name='monthly_on_call_versions_unit_id_month_version_key'),
    )

    op.create_table(
        'on_call_shifts',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('division_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('unit_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('station_assignments', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('submitted_assignments', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(['division_id'], ['divisions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['unit_id'], ['units.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('unit_id', 'date', 'version', name='on_call_shifts_unit_id_date_version_key'),
    )
    op.create_index('idx_on_call_shifts_unit_id_date_version', 'on_call_shifts', ['unit_id', 'date', 'version'])

    # --- D. generalize the submissions table (rename + column rename + new column) ---
    op.rename_table('constraints_submissions', 'staff_member_submissions')
    op.alter_column('staff_member_submissions', 'type_id', new_column_name='constraint_type_id')
    op.add_column('staff_member_submissions', sa.Column('on_call_station_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'staff_member_submissions_on_call_station_id_fkey', 'staff_member_submissions', 'on_call_stations',
        ['on_call_station_id'], ['id'], ondelete='CASCADE',
    )


def downgrade() -> None:
    """Downgrade schema."""
    # --- reverse D ---
    op.drop_constraint('staff_member_submissions_on_call_station_id_fkey', 'staff_member_submissions', type_='foreignkey')
    op.drop_column('staff_member_submissions', 'on_call_station_id')
    op.alter_column('staff_member_submissions', 'constraint_type_id', new_column_name='type_id')
    op.rename_table('staff_member_submissions', 'constraints_submissions')

    # --- reverse C ---
    op.drop_index('idx_on_call_shifts_unit_id_date_version', table_name='on_call_shifts')
    op.drop_table('on_call_shifts')
    op.drop_table('monthly_on_call_versions')
    op.drop_index('ux_on_call_stations_division_id_name_active', table_name='on_call_stations')
    op.drop_index('idx_on_call_stations_division_id', table_name='on_call_stations')
    op.drop_table('on_call_stations')

    # --- reverse B ---
    op.alter_column('staff_member_submission_metadata', 'start_time', nullable=False)
    op.execute(
        "ALTER TABLE staff_member_submission_metadata "
        "RENAME CONSTRAINT staff_member_submission_metadata_unit_id_month_key "
        "TO constraint_submission_metadata_unit_id_month_key"
    )
    op.add_column('staff_member_submission_metadata', sa.Column('pulled_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('staff_member_submission_metadata', sa.Column('pulled_by', postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        'constraint_submission_metadata_pulled_by_fkey', 'staff_member_submission_metadata', 'users',
        ['pulled_by'], ['id'], ondelete='RESTRICT',
    )
    op.execute("""
        UPDATE staff_member_submission_metadata
        SET pulled_at = (pull_information -> 'constraints' ->> 'pulled_at')::timestamptz,
            pulled_by = (pull_information -> 'constraints' ->> 'pulled_by')::uuid
        WHERE pull_information ? 'constraints'
    """)
    op.drop_column('staff_member_submission_metadata', 'pull_information')
    op.rename_table('staff_member_submission_metadata', 'constraint_submission_metadata')

    # --- reverse A (structure only — data is not recoverable) ---
    op.create_table(
        'shift_stations',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('unit_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['unit_id'], ['units.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'shifts',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('unit_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('shift_date', sa.Date(), nullable=False),
        sa.Column('shift_station_id', sa.Integer(), nullable=False),
        sa.Column('staff_member_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['staff_member_id'], ['staff_members.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['unit_id'], ['units.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
