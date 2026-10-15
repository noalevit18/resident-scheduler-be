"""constraint_kind_and_friday_ranking

Revision ID: a7c4e1d8b3f2
Revises: f3a8b6c2d9e1
Create Date: 2026-10-15 00:00:00.000000

Constraint types get an explicit `kind` (BLOCKING / PREFERENCE) in place of
`is_hard`, and preference types an explicit `preference` scale (1 = want,
0 = informational, -1 = prefer not) instead of being recognised by their
name. Existing types named like "want" / "prefer not" are backfilled as
PREFERENCE types with their scale — even when they were stored as hard
(is_hard), which would otherwise block the very members who asked for a day.

Fridays can also be ranked: a month's submission window carries its
`friday_mode`, a member's rank is a submission row with no constraint type,
and the constraints calendar keeps a date's ranks on a row with no type
(`staff_member_ranks`).

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'a7c4e1d8b3f2'
down_revision: Union[str, Sequence[str], None] = 'f3a8b6c2d9e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

WANT_NAMES = ('רוצה', 'want', 'request')
PREFER_NOT_NAMES = ('מעדיף שלא', 'prefernot', 'prefer not', 'prefer_not')

constraint_type_kind = postgresql.ENUM('BLOCKING', 'PREFERENCE', name='constraint_type_kind', create_type=False)
friday_mode = postgresql.ENUM('PREFERENCE', 'RANKING', name='friday_mode', create_type=False)


def _backfill_preference(value: int, names: tuple[str, ...]) -> None:
    quoted = ", ".join("'" + name.replace("'", "''") + "'" for name in names)
    op.execute(
        f"UPDATE constraint_types SET kind = 'PREFERENCE', preference = {int(value)} "
        f"WHERE lower(trim(name)) IN ({quoted})"
    )


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    constraint_type_kind.create(bind, checkfirst=True)
    friday_mode.create(bind, checkfirst=True)

    # constraint_types: is_hard -> kind, plus the preference scale
    op.add_column('constraint_types', sa.Column('kind', constraint_type_kind, nullable=True))
    op.execute("UPDATE constraint_types SET kind = CASE WHEN is_hard THEN 'BLOCKING' ELSE 'PREFERENCE' END::constraint_type_kind")
    op.alter_column('constraint_types', 'kind', nullable=False)
    op.add_column(
        'constraint_types',
        sa.Column('preference', sa.SmallInteger(), nullable=False, server_default=sa.text('0')),
    )
    _backfill_preference(1, WANT_NAMES)
    _backfill_preference(-1, PREFER_NOT_NAMES)
    op.drop_column('constraint_types', 'is_hard')

    # constraints: a type-less row per date holds that date's Friday ranks
    op.alter_column('constraints', 'type_id', existing_type=sa.Integer(), nullable=True)
    op.add_column(
        'constraints',
        sa.Column('staff_member_ranks', postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.create_index(
        'ix_constraints_rank_row_unique', 'constraints', ['unit_id', 'date', 'version'],
        unique=True, postgresql_where=sa.text('type_id IS NULL'),
    )

    # submissions: a member's Friday rank, and the month's Friday mode
    op.add_column('staff_member_submissions', sa.Column('rank', sa.SmallInteger(), nullable=True))
    op.add_column(
        'staff_member_submission_metadata',
        sa.Column('friday_mode', friday_mode, nullable=False, server_default='PREFERENCE'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('staff_member_submission_metadata', 'friday_mode')
    op.drop_column('staff_member_submissions', 'rank')

    op.drop_index('ix_constraints_rank_row_unique', table_name='constraints')
    op.drop_column('constraints', 'staff_member_ranks')
    op.execute('DELETE FROM constraints WHERE type_id IS NULL')
    op.alter_column('constraints', 'type_id', existing_type=sa.Integer(), nullable=False)

    op.add_column(
        'constraint_types',
        sa.Column('is_hard', sa.Boolean(), nullable=False, server_default=sa.text('false')),
    )
    op.execute("UPDATE constraint_types SET is_hard = (kind = 'BLOCKING')")
    op.drop_column('constraint_types', 'preference')
    op.drop_column('constraint_types', 'kind')

    bind = op.get_bind()
    friday_mode.drop(bind, checkfirst=True)
    constraint_type_kind.drop(bind, checkfirst=True)
