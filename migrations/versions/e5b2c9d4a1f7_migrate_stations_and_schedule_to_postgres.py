"""migrate_stations_and_schedule_to_postgres

Revision ID: e5b2c9d4a1f7
Revises: 2cf0513df568
Create Date: 2026-10-02 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'e5b2c9d4a1f7'
down_revision: Union[str, Sequence[str], None] = '2cf0513df568'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('stations', sa.Column('text_color', sa.Text(), nullable=True))
    op.add_column('stations', sa.Column('display_order', sa.Integer(), nullable=True))
    op.add_column('stations', sa.Column('min_staff_on_sabbatical', sa.Integer(), nullable=True))
    op.add_column('stations', sa.Column('min_staff_on_half_day', sa.Integer(), nullable=True))
    op.add_column('stations', sa.Column('enable_stand_by', sa.Boolean(), nullable=False, server_default=sa.text('false')))
    op.add_column('stations', sa.Column('active_on_sabbatical', sa.Boolean(), nullable=False, server_default=sa.text('false')))
    op.add_column('stations', sa.Column('prefer_day_before_on_call', sa.Boolean(), nullable=False, server_default=sa.text('false')))
    op.add_column('stations', sa.Column('is_secondary', sa.Boolean(), nullable=False, server_default=sa.text('false')))
    op.add_column('stations', sa.Column(
        'secondary_to', postgresql.ARRAY(sa.Integer()), nullable=False, server_default=sa.text("'{}'"),
    ))
    op.add_column('stations', sa.Column('firestore_id', sa.Text(), nullable=True))
    op.add_column('stations', sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default=sa.text('false')))
    op.add_column('stations', sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('stations', sa.Column('deleted_by', postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        'stations_deleted_by_fkey', 'stations', 'users', ['deleted_by'], ['id'], ondelete='SET NULL',
    )
    op.create_foreign_key(
        'stations_certification_id_fkey', 'stations', 'staff_certifications',
        ['certification_id'], ['id'], ondelete='SET NULL',
    )
    op.create_unique_constraint('stations_unit_id_firestore_id_key', 'stations', ['unit_id', 'firestore_id'])

    # --- A2. versioned station config (effective from a date; global
    # fields — name, colors, display_order — stay on `stations` only) and the
    # non-versioned on-call station -> station mapping ---
    op.create_table(
        'station_versions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('station_id', sa.Integer(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('effective_from', sa.Date(), nullable=False),
        sa.Column('is_retired', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('is_default', sa.Boolean(), nullable=False),
        sa.Column('certification_id', sa.Integer(), nullable=True),
        sa.Column('optional', sa.Boolean(), nullable=False),
        sa.Column('min_staff_members', sa.Integer(), nullable=True),
        sa.Column('min_staff_on_sabbatical', sa.Integer(), nullable=True),
        sa.Column('min_staff_on_half_day', sa.Integer(), nullable=True),
        sa.Column('active_days', sa.ARRAY(sa.Integer()), nullable=True),
        sa.Column(
            'recurrence_type',
            postgresql.ENUM('WEEKLY', 'EVERY_X_DAYS', 'EVERY_X_WEEKS', name='recurrence_type_enum', create_type=False),
            nullable=True,
        ),
        sa.Column('recurrence_interval', sa.Integer(), nullable=True),
        sa.Column('recurrence_base_date', sa.Date(), nullable=True),
        sa.Column('enable_stand_by', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('active_on_sabbatical', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('prefer_day_before_on_call', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('is_secondary', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('secondary_to', postgresql.ARRAY(sa.Integer()), nullable=False, server_default=sa.text("'{}'")),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(['station_id'], ['stations.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['certification_id'], ['staff_certifications.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('station_id', 'version', name='station_versions_station_id_version_key'),
    )
    op.create_index('idx_station_versions_station_id_effective_from', 'station_versions', ['station_id', 'effective_from'])

    op.create_table(
        'on_call_station_mappings',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('unit_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('on_call_station_id', sa.Integer(), nullable=False),
        sa.Column('station_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['unit_id'], ['units.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['on_call_station_id'], ['on_call_stations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['station_id'], ['stations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('unit_id', 'on_call_station_id', name='on_call_station_mappings_unit_id_on_call_station_id_key'),
    )
    op.create_index('ix_on_call_station_mappings_station_id', 'on_call_station_mappings', ['station_id'])

    # --- B. drop the legacy, never-used schedule tables (no code reads or
    # writes them) and recreate the schedule as insert-only versioned tables ---
    op.drop_table('schedule_staff_members')
    op.drop_table('schedule_seniors')
    op.drop_table('schedule_versions')

    op.create_table(
        'schedule_versions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('unit_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('month', sa.Text(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('is_published', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('published_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('constraints_version', sa.Integer(), nullable=True),
        sa.Column('on_call_version', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(['unit_id'], ['units.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['published_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('unit_id', 'month', 'version', name='schedule_versions_unit_id_month_version_key'),
    )

    # station versions a schedule version is pinned to — kept at the
    # schedule-version level, not per date; a month can pin several versions
    # of one station (a change effective mid-month)
    op.create_table(
        'schedule_version_stations',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('schedule_version_id', sa.Integer(), nullable=False),
        sa.Column('station_id', sa.Integer(), nullable=False),
        sa.Column('station_version_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['schedule_version_id'], ['schedule_versions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['station_id'], ['stations.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['station_version_id'], ['station_versions.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('schedule_version_id', 'station_version_id', name='schedule_version_stations_version_station_version_key'),
    )
    op.create_index('idx_schedule_version_stations_station_version_id', 'schedule_version_stations', ['station_version_id'])

    op.create_table(
        'schedule_stations',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('schedule_version_id', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('station_id', sa.Integer(), nullable=True),
        sa.Column('custom_name', sa.Text(), nullable=True),
        sa.Column('display_order', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['schedule_version_id'], ['schedule_versions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['station_id'], ['stations.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint('num_nonnulls(station_id, custom_name) = 1', name='schedule_stations_station_or_custom_check'),
    )
    op.create_index(
        'ux_schedule_stations_version_date_station', 'schedule_stations',
        ['schedule_version_id', 'date', 'station_id'],
        unique=True, postgresql_where=sa.text('station_id IS NOT NULL'),
    )
    op.create_index('idx_schedule_stations_version_date', 'schedule_stations', ['schedule_version_id', 'date'])

    op.create_table(
        'schedule_assignments',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('schedule_station_id', sa.Integer(), nullable=False),
        sa.Column('staff_member_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('is_stand_by', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.ForeignKeyConstraint(['schedule_station_id'], ['schedule_stations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['staff_member_id'], ['staff_members.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('schedule_station_id', 'staff_member_id', name='schedule_assignments_station_staff_member_key'),
    )
    op.create_index('ix_schedule_assignments_schedule_station_id', 'schedule_assignments', ['schedule_station_id'])

    op.create_table(
        'schedule_seniors',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('schedule_version_id', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('senior_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(['schedule_version_id'], ['schedule_versions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['senior_id'], ['seniors.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('schedule_version_id', 'date', name='schedule_seniors_version_date_key'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    # --- reverse B (structure only — schedule data is not recoverable) ---
    op.drop_table('schedule_seniors')
    op.drop_index('ix_schedule_assignments_schedule_station_id', table_name='schedule_assignments')
    op.drop_table('schedule_assignments')
    op.drop_index('idx_schedule_stations_version_date', table_name='schedule_stations')
    op.drop_index('ux_schedule_stations_version_date_station', table_name='schedule_stations')
    op.drop_table('schedule_stations')
    op.drop_index('idx_schedule_version_stations_station_version_id', table_name='schedule_version_stations')
    op.drop_table('schedule_version_stations')
    op.drop_table('schedule_versions')

    op.create_table(
        'schedule_versions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('unit_id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('is_published', sa.Boolean(), nullable=False),
        sa.Column('schedule', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
        sa.Column('update_admin_id', sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(['update_admin_id'], ['users.id'], name='fk_schedule_versions_update_admin', onupdate='CASCADE', ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['unit_id'], ['units.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'schedule_seniors',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('unit_id', sa.UUID(), nullable=False),
        sa.Column('schedule_date', sa.Date(), nullable=False),
        sa.Column('senior_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['unit_id'], ['units.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'schedule_staff_members',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('unit_id', sa.UUID(), nullable=False),
        sa.Column('schedule_date', sa.Date(), nullable=False),
        sa.Column('staff_member_id', sa.UUID(), nullable=False),
        sa.Column('station_id', sa.Integer(), nullable=False),
        sa.Column('is_stand_by', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['staff_member_id'], ['staff_members.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['unit_id'], ['units.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    # --- reverse A2 ---
    op.drop_index('ix_on_call_station_mappings_station_id', table_name='on_call_station_mappings')
    op.drop_table('on_call_station_mappings')
    op.drop_index('idx_station_versions_station_id_effective_from', table_name='station_versions')
    op.drop_table('station_versions')

    # --- reverse A ---
    op.drop_constraint('stations_unit_id_firestore_id_key', 'stations', type_='unique')
    op.drop_constraint('stations_certification_id_fkey', 'stations', type_='foreignkey')
    op.drop_constraint('stations_deleted_by_fkey', 'stations', type_='foreignkey')
    op.drop_column('stations', 'deleted_by')
    op.drop_column('stations', 'deleted_at')
    op.drop_column('stations', 'is_deleted')
    op.drop_column('stations', 'firestore_id')
    op.drop_column('stations', 'secondary_to')
    op.drop_column('stations', 'is_secondary')
    op.drop_column('stations', 'prefer_day_before_on_call')
    op.drop_column('stations', 'active_on_sabbatical')
    op.drop_column('stations', 'enable_stand_by')
    op.drop_column('stations', 'min_staff_on_half_day')
    op.drop_column('stations', 'min_staff_on_sabbatical')
    op.drop_column('stations', 'display_order')
    op.drop_column('stations', 'text_color')
