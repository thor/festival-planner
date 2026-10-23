"""entry details

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-23 23:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

COLUMNS = (
    ("tagline", sa.Text()),
    ("synopsis", sa.Text()),
    ("poster_url", sa.String()),
    ("still_url", sa.String()),
    ("runtime_minutes", sa.Integer()),
    ("original_title", sa.String()),
    ("director", sa.String()),
    ("genre", sa.String()),
    ("language", sa.String()),
    ("subtitles", sa.String()),
    ("age_limit", sa.String()),
    ("imdb_url", sa.String()),
)


def upgrade() -> None:
    with op.batch_alter_table("programme_entry", schema=None) as batch_op:
        for name, type_ in COLUMNS:
            batch_op.add_column(sa.Column(name, type_, nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("programme_entry", schema=None) as batch_op:
        for name, _ in reversed(COLUMNS):
            batch_op.drop_column(name)
