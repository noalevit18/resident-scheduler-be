"""add_on_call_station_settings

Revision ID: b7e4c2a9f1d6
Revises: e8f1a2b3c4d5
Create Date: 2026-11-17 00:00:00.000000

On-call station settings. On-call stations are active every day; the
settings decide how many residents each needs and which unit covers it on a
given day.

- `on_call_stations`:
  - `initials`: the station's optional short name (e.g. "פ1" for "פגיה 1").
  - `number_of_residents`: exact number of residents on call each day
    (NOT NULL, default 1).
  - `requires_independent`: only independent residents can be on call at the
    station, not those who need backup (NOT NULL, default false).
  - `open_to_external`: external on-call residents (from outside the
    division) can be on call at the station (NOT NULL, default false).
  - `distribution_mode` (ROTATION_DAILY / ROTATION_WEEKLY / TURNS / MANUAL,
    default ROTATION_DAILY): how the days are divided between the units that
    can cover the station. MANUAL: the scheduler assigns it by hand.
  - `priority_unit_id`: the unit whose wishes are always granted (required
    for TURNS, checked by the API).
  - `staff_rotation_id`: the staff rotation mapped to the station; its
    residents get priority when residents are assigned there.
  - `required_certification_ids`: staff certifications a resident needs to
    be on call at the station (any one of them); empty: none needed.
  - `rotation_length`: days (ROTATION_DAILY) or weeks (ROTATION_WEEKLY)
    each unit covers in a row before the next one (NOT NULL, default 1).
  - `rotation_start_date`: the day the first unit in the rotation order
    starts. Existing stations start on the first of the current month.
  - `rotation_unit_ids`: the units' order in the rotation / turns.
  - `group_id` (nullable: no group) and `group_order` (order in the group).
  - `deleted_at`: when a (soft-)deleted station was deleted. It stays
    available up to the end of that month, for history, and is gone from the
    months after it (NULL on an older deleted station: gone from every month).
- `on_call_station_groups`: named buckets of stations that usually come
  together, unique by name per division.
- `on_call_unit_stations`: the stations a unit can cover (no rows: every
  station).
- `on_call_division_settings`: a division's general on-call settings, e.g.
  `shift_length_hours` (default 24). No row: the defaults.

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'b7e4c2a9f1d6'
down_revision: Union[str, Sequence[str], None] = 'e8f1a2b3c4d5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


distribution_mode_enum = postgresql.ENUM(
    'ROTATION_DAILY', 'ROTATION_WEEKLY', 'TURNS', 'MANUAL', name='on_call_distribution_mode', create_type=False,
)


def upgrade() -> None:
    """Upgrade schema."""
    distribution_mode_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        'on_call_station_groups',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('division_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('divisions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('division_id', 'name', name='on_call_station_groups_division_id_name_key'),
    )
    op.create_index('ix_on_call_station_groups_division_id', 'on_call_station_groups', ['division_id'])

    op.add_column('on_call_stations', sa.Column('initials', sa.Text(), nullable=True))
    op.add_column(
        'on_call_stations',
        sa.Column('number_of_residents', sa.Integer(), server_default=sa.text('1'), nullable=False),
    )
    op.add_column(
        'on_call_stations',
        sa.Column('requires_independent', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    )
    op.add_column(
        'on_call_stations',
        sa.Column('open_to_external', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    )
    op.add_column(
        'on_call_stations',
        sa.Column('distribution_mode', distribution_mode_enum, server_default='ROTATION_DAILY', nullable=False),
    )
    op.add_column('on_call_stations', sa.Column('priority_unit_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        'fk_on_call_stations_priority_unit_id', 'on_call_stations', 'units',
        ['priority_unit_id'], ['id'], ondelete='SET NULL',
    )
    op.add_column(
        'on_call_stations',
        sa.Column(
            'required_certification_ids', postgresql.ARRAY(sa.Integer()),
            server_default=sa.text("'{}'"), nullable=False,
        ),
    )
    op.add_column('on_call_stations', sa.Column('staff_rotation_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_on_call_stations_staff_rotation_id', 'on_call_stations', 'staff_rotations',
        ['staff_rotation_id'], ['id'], ondelete='SET NULL',
    )
    op.add_column(
        'on_call_stations',
        sa.Column('rotation_start_date', sa.Date(), server_default=sa.text('CURRENT_DATE'), nullable=False),
    )
    op.execute("UPDATE on_call_stations SET rotation_start_date = date_trunc('month', CURRENT_DATE)::date")
    op.add_column(
        'on_call_stations',
        sa.Column('rotation_length', sa.Integer(), server_default=sa.text('1'), nullable=False),
    )
    op.add_column(
        'on_call_stations',
        sa.Column(
            'rotation_unit_ids', postgresql.ARRAY(postgresql.UUID(as_uuid=True)),
            server_default=sa.text("'{}'"), nullable=False,
        ),
    )
    op.add_column('on_call_stations', sa.Column('group_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_on_call_stations_group_id', 'on_call_stations', 'on_call_station_groups',
        ['group_id'], ['id'], ondelete='SET NULL',
    )
    op.create_index('ix_on_call_stations_group_id', 'on_call_stations', ['group_id'])
    op.add_column('on_call_stations', sa.Column('group_order', sa.Integer(), server_default=sa.text('0'), nullable=False))
    op.add_column('on_call_stations', sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        'on_call_unit_stations',
        sa.Column('unit_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('units.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('on_call_station_id', sa.Integer(), sa.ForeignKey('on_call_stations.id', ondelete='CASCADE'), primary_key=True),
    )
    op.create_index('ix_on_call_unit_stations_on_call_station_id', 'on_call_unit_stations', ['on_call_station_id'])

    op.create_table(
        'on_call_division_settings',
        sa.Column('division_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('divisions.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('shift_length_hours', sa.Integer(), server_default=sa.text('24'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('on_call_division_settings')
    op.drop_index('ix_on_call_unit_stations_on_call_station_id', table_name='on_call_unit_stations')
    op.drop_table('on_call_unit_stations')

    op.drop_index('ix_on_call_stations_group_id', table_name='on_call_stations')
    op.drop_constraint('fk_on_call_stations_group_id', 'on_call_stations', type_='foreignkey')
    op.drop_constraint('fk_on_call_stations_staff_rotation_id', 'on_call_stations', type_='foreignkey')
    op.drop_constraint('fk_on_call_stations_priority_unit_id', 'on_call_stations', type_='foreignkey')
    for column in (
        'deleted_at', 'group_order', 'group_id', 'rotation_unit_ids', 'rotation_length', 'rotation_start_date',
        'staff_rotation_id', 'required_certification_ids', 'priority_unit_id', 'distribution_mode', 'open_to_external', 'requires_independent', 'number_of_residents', 'initials',
    ):
        op.drop_column('on_call_stations', column)

    op.drop_index('ix_on_call_station_groups_division_id', table_name='on_call_station_groups')
    op.drop_table('on_call_station_groups')
    distribution_mode_enum.drop(op.get_bind(), checkfirst=True)
