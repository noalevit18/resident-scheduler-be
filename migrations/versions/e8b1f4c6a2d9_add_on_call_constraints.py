"""Add on-call constraints, versioned per-day stations (with shift/turn settings), and notes.

A division+month's on-call constraints, rosters and day stations share one version number
(`on_call_scheduling_versions`). Existing rosters keep all their versions and numbers; the shared counter is
backfilled from them, so a division+month whose rosters reached version 10 saves version 11 next.

Revision ID: e8b1f4c6a2d9
Revises: a3d9f2e7c5b1
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'e8b1f4c6a2d9'
down_revision: Union[str, Sequence[str], None] = 'a3d9f2e7c5b1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    constraint_type_scope = postgresql.ENUM('SCHEDULE', 'ON_CALL', name='constraint_type_scope', create_type=False)
    submission_scope = postgresql.ENUM('SCHEDULE', 'ON_CALL', name='submission_scope', create_type=False)
    bind = op.get_bind()
    constraint_type_scope.create(bind, checkfirst=True)
    submission_scope.create(bind, checkfirst=True)

    op.add_column(
        'constraint_types',
        sa.Column('scope', constraint_type_scope, nullable=False, server_default='SCHEDULE'),
    )
    op.create_table(
        'on_call_constraints',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('unit_id', sa.UUID(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('type_id', sa.Integer(), nullable=True),
        sa.Column('preference', sa.SmallInteger(), nullable=True),
        sa.Column('staff_member_ids', postgresql.ARRAY(sa.UUID()), server_default='{}', nullable=False),
        sa.Column('submitted_staff_member_ids', postgresql.ARRAY(sa.UUID()), server_default='{}', nullable=False),
        sa.Column('version', sa.Integer(), server_default='1', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', sa.UUID(), nullable=True),
        sa.CheckConstraint('(type_id IS NULL) <> (preference IS NULL)', name='ck_on_call_constraints_type_xor_preference'),
        sa.CheckConstraint('preference IS NULL OR preference IN (-2, -1, 1, 2)', name='ck_on_call_constraints_preference_range'),
        sa.ForeignKeyConstraint(['unit_id'], ['units.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['type_id'], ['constraint_types.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_on_call_constraints_unit_id_date_version', 'on_call_constraints', ['unit_id', 'date', 'version'])
    op.create_index(
        'ux_on_call_constraints_type_row', 'on_call_constraints', ['unit_id', 'date', 'type_id', 'version'],
        unique=True, postgresql_where=sa.text('type_id IS NOT NULL'),
    )
    op.create_index(
        'ux_on_call_constraints_preference_row', 'on_call_constraints', ['unit_id', 'date', 'preference', 'version'],
        unique=True, postgresql_where=sa.text('preference IS NOT NULL'),
    )
    op.create_table(
        'monthly_on_call_constraints_versions',
        sa.Column('unit_id', sa.UUID(), nullable=False),
        sa.Column('month', sa.Text(), nullable=False),
        sa.Column('version', sa.Integer(), server_default='1', nullable=False),
        sa.ForeignKeyConstraint(['unit_id'], ['units.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('unit_id', 'month'),
    )
    op.create_table(
        'staff_member_on_call_submissions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('unit_id', sa.UUID(), nullable=False),
        sa.Column('staff_member_id', sa.UUID(), nullable=True),
        sa.Column('external_physician_id', sa.UUID(), nullable=True),
        sa.Column('month', sa.Text(), nullable=False),
        sa.Column('date', sa.Date(), nullable=True),
        sa.Column('preference', sa.SmallInteger(), nullable=True),
        sa.Column('constraint_type_id', sa.Integer(), nullable=True),
        sa.Column('comment', sa.Text(), nullable=True),
        sa.Column('submitted_empty', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('(staff_member_id IS NULL) <> (external_physician_id IS NULL)', name='ck_staff_member_on_call_submissions_one_submitter'),
        sa.CheckConstraint('preference IS NULL OR constraint_type_id IS NULL', name='ck_staff_member_on_call_submissions_preference_xor_type'),
        sa.CheckConstraint('preference IS NULL OR preference IN (-2, -1, 1, 2)', name='ck_staff_member_on_call_submissions_preference_range'),
        sa.CheckConstraint('date IS NOT NULL OR (preference IS NULL AND constraint_type_id IS NULL)', name='ck_staff_member_on_call_submissions_value_needs_date'),
        sa.ForeignKeyConstraint(['unit_id'], ['units.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['staff_member_id'], ['staff_members.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(
            ['external_physician_id'], ['external_on_call_physicians.id'], ondelete='CASCADE',
            name='fk_staff_member_on_call_submissions_external_physician_id',
        ),
        sa.ForeignKeyConstraint(['constraint_type_id'], ['constraint_types.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_staff_member_on_call_submissions_external_physician_id', 'staff_member_on_call_submissions', ['external_physician_id'])
    op.create_index(
        'ix_staff_member_on_call_submissions_per_date_unique', 'staff_member_on_call_submissions',
        ['unit_id', 'staff_member_id', 'month', 'date'], unique=True,
        postgresql_where=sa.text('date IS NOT NULL'),
    )
    op.create_index(
        'ix_staff_member_on_call_submissions_general_comment_unique', 'staff_member_on_call_submissions',
        ['unit_id', 'staff_member_id', 'month'], unique=True, postgresql_where=sa.text('date IS NULL'),
    )
    op.create_index(
        'ix_staff_member_on_call_submissions_external_per_date_unique', 'staff_member_on_call_submissions',
        ['unit_id', 'external_physician_id', 'month', 'date'], unique=True,
        postgresql_where=sa.text('date IS NOT NULL AND external_physician_id IS NOT NULL'),
    )
    op.create_index(
        'ix_staff_member_on_call_submissions_external_comment_unique', 'staff_member_on_call_submissions',
        ['unit_id', 'external_physician_id', 'month'], unique=True,
        postgresql_where=sa.text('date IS NULL AND external_physician_id IS NOT NULL'),
    )
    op.add_column(
        'staff_member_submission_metadata',
        sa.Column('scope', submission_scope, nullable=False, server_default='SCHEDULE'),
    )
    for name in ('staff_member_submission_metadata_unit_id_month_key', 'constraint_submission_metadata_unit_id_month_key'):
        op.execute(f'ALTER TABLE staff_member_submission_metadata DROP CONSTRAINT IF EXISTS {name}')
    op.create_unique_constraint(
        'staff_member_submission_metadata_unit_id_month_scope_key', 'staff_member_submission_metadata',
        ['unit_id', 'month', 'scope'],
    )

    # Per-day on-call station overrides — insert-only, one complete snapshot of the unit+month per version.
    op.create_table(
        'on_call_day_stations',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('division_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('divisions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('unit_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('units.id', ondelete='CASCADE'), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('on_call_station_id', sa.Integer(), sa.ForeignKey('on_call_stations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('is_added', sa.Boolean(), nullable=False),
        sa.Column('shifts_turns', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.UniqueConstraint(
            'unit_id', 'date', 'on_call_station_id', 'version', name='on_call_day_stations_unit_id_date_station_version_key',
        ),
    )
    op.create_index(
        'idx_on_call_day_stations_unit_id_date_version', 'on_call_day_stations', ['unit_id', 'date', 'version'],
    )
    op.create_table(
        'monthly_on_call_day_stations_versions',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('unit_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('units.id', ondelete='CASCADE'), nullable=False),
        sa.Column('month', sa.Text(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.UniqueConstraint(
            'unit_id', 'month', 'version', name='monthly_on_call_day_stations_versions_key',
        ),
    )

    # Division-level notes for each on-call roster day — not versioned, always the latest.
    op.create_table(
        'on_call_day_notes',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('division_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('divisions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.UniqueConstraint('division_id', 'date', name='on_call_day_notes_division_id_date_key'),
    )

    # The shared version counter of a division+month, and what each version saved for which unit.
    version_kind = postgresql.ENUM('CONSTRAINTS', 'ROSTER', 'DAY_STATIONS', name='on_call_version_kind', create_type=False)
    version_kind.create(bind, checkfirst=True)
    op.create_table(
        'on_call_scheduling_versions',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('division_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('divisions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('month', sa.Text(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.UniqueConstraint('division_id', 'month', 'version', name='on_call_scheduling_versions_division_month_version_key'),
    )
    op.create_table(
        'on_call_scheduling_version_entities',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            'scheduling_version_id', sa.Integer(),
            sa.ForeignKey('on_call_scheduling_versions.id', ondelete='CASCADE'), nullable=False,
        ),
        sa.Column('unit_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('units.id', ondelete='CASCADE'), nullable=False),
        sa.Column('kind', version_kind, nullable=False),
        sa.UniqueConstraint('scheduling_version_id', 'unit_id', 'kind', name='on_call_scheduling_version_entities_key'),
    )
    op.create_index(
        'idx_on_call_scheduling_version_entities_unit_kind', 'on_call_scheduling_version_entities', ['unit_id', 'kind'],
    )

    # Existing rosters keep every version and its number. Each roster version number already used by any unit of
    # a division+month becomes a shared version of it, recording the units' rosters saved under that number — so
    # the next save continues from the division+month's highest existing version (months without any start at 1).
    op.execute("""
        INSERT INTO on_call_scheduling_versions (division_id, month, version, created_at, created_by)
        SELECT DISTINCT ON (u.division_id, v.month, v.version)
            u.division_id, v.month, v.version, v.created_at, v.created_by
        FROM monthly_on_call_versions v JOIN units u ON u.id = v.unit_id
        ORDER BY u.division_id, v.month, v.version, v.created_at
    """)
    op.execute("""
        INSERT INTO on_call_scheduling_version_entities (scheduling_version_id, unit_id, kind)
        SELECT sv.id, v.unit_id, 'ROSTER'::on_call_version_kind
        FROM monthly_on_call_versions v
        JOIN units u ON u.id = v.unit_id
        JOIN on_call_scheduling_versions sv
            ON sv.division_id = u.division_id AND sv.month = v.month AND sv.version = v.version
    """)


def downgrade() -> None:
    """Rosters saved under the shared counter stay in `monthly_on_call_versions`/`on_call_shifts`, numbered per
    division+month (a unit's numbers may skip the versions other units of its division took)."""
    op.drop_index('idx_on_call_scheduling_version_entities_unit_kind', table_name='on_call_scheduling_version_entities')
    op.drop_table('on_call_scheduling_version_entities')
    op.drop_table('on_call_scheduling_versions')
    postgresql.ENUM(name='on_call_version_kind').drop(op.get_bind(), checkfirst=True)
    op.drop_table('on_call_day_notes')
    op.drop_table('monthly_on_call_day_stations_versions')
    op.drop_index('idx_on_call_day_stations_unit_id_date_version', table_name='on_call_day_stations')
    op.drop_table('on_call_day_stations')
    op.execute("DELETE FROM staff_member_submission_metadata WHERE scope = 'ON_CALL'")
    op.drop_constraint('staff_member_submission_metadata_unit_id_month_scope_key', 'staff_member_submission_metadata', type_='unique')
    op.create_unique_constraint(
        'staff_member_submission_metadata_unit_id_month_key', 'staff_member_submission_metadata', ['unit_id', 'month'],
    )
    op.drop_column('staff_member_submission_metadata', 'scope')
    op.drop_index('ix_staff_member_on_call_submissions_external_comment_unique', table_name='staff_member_on_call_submissions')
    op.drop_index('ix_staff_member_on_call_submissions_external_per_date_unique', table_name='staff_member_on_call_submissions')
    op.drop_index('ix_staff_member_on_call_submissions_external_physician_id', table_name='staff_member_on_call_submissions')
    op.drop_index('ix_staff_member_on_call_submissions_general_comment_unique', table_name='staff_member_on_call_submissions')
    op.drop_index('ix_staff_member_on_call_submissions_per_date_unique', table_name='staff_member_on_call_submissions')
    op.drop_table('staff_member_on_call_submissions')
    op.drop_table('monthly_on_call_constraints_versions')
    op.drop_index('ux_on_call_constraints_preference_row', table_name='on_call_constraints')
    op.drop_index('ux_on_call_constraints_type_row', table_name='on_call_constraints')
    op.drop_index('idx_on_call_constraints_unit_id_date_version', table_name='on_call_constraints')
    op.drop_table('on_call_constraints')
    op.execute("DELETE FROM constraint_types WHERE scope = 'ON_CALL'")
    op.drop_column('constraint_types', 'scope')
    submission_scope = postgresql.ENUM('SCHEDULE', 'ON_CALL', name='submission_scope', create_type=False)
    constraint_type_scope = postgresql.ENUM('SCHEDULE', 'ON_CALL', name='constraint_type_scope', create_type=False)
    submission_scope.drop(op.get_bind(), checkfirst=True)
    constraint_type_scope.drop(op.get_bind(), checkfirst=True)