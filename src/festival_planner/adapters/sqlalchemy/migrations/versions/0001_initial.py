"""initial

Revision ID: 0001
Revises:
Create Date: 2026-10-23 23:44:02.993371

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "app_user",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("issuer", sa.String(), nullable=False),
        sa.Column("subject", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_app_user")),
        sa.UniqueConstraint(
            "issuer", "subject", name=op.f("uq_app_user_issuer_subject")
        ),
    )
    op.create_table(
        "festival_series",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("slug", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_festival_series")),
        sa.UniqueConstraint("slug", name=op.f("uq_festival_series_slug")),
    )
    op.create_table(
        "film",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("match_key", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_film")),
    )
    with op.batch_alter_table("film", schema=None) as batch_op:
        batch_op.create_index(
            "ix_film_match_key_year", ["match_key", "year"], unique=False
        )

    op.create_table(
        "venue",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_venue")),
        sa.UniqueConstraint("name", name=op.f("uq_venue_name")),
    )
    op.create_table(
        "festival",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("slug", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("time_zone", sa.String(), nullable=False),
        sa.Column("series_id", sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(
            ["series_id"],
            ["festival_series.id"],
            name=op.f("fk_festival_series_id_festival_series"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_festival")),
        sa.UniqueConstraint("slug", name=op.f("uq_festival_slug")),
    )
    op.create_table(
        "route",
        sa.Column("from_venue_id", sa.String(length=36), nullable=False),
        sa.Column("to_venue_id", sa.String(length=36), nullable=False),
        sa.Column("mode", sa.String(), nullable=False),
        sa.Column("minutes", sa.Integer(), nullable=False),
        sa.CheckConstraint("minutes >= 0", name=op.f("ck_route_minutes_non_negative")),
        sa.ForeignKeyConstraint(
            ["from_venue_id"], ["venue.id"], name=op.f("fk_route_from_venue_id_venue")
        ),
        sa.ForeignKeyConstraint(
            ["to_venue_id"], ["venue.id"], name=op.f("fk_route_to_venue_id_venue")
        ),
        sa.PrimaryKeyConstraint(
            "from_venue_id", "to_venue_id", "mode", name=op.f("pk_route")
        ),
    )
    op.create_table(
        "seen",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("film_id", sa.String(length=36), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(
            ["film_id"], ["film.id"], name=op.f("fk_seen_film_id_film")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["app_user.id"], name=op.f("fk_seen_user_id_app_user")
        ),
        sa.PrimaryKeyConstraint("user_id", "film_id", name=op.f("pk_seen")),
    )
    op.create_table(
        "venue_alias",
        sa.Column("venue_id", sa.String(length=36), nullable=False),
        sa.Column("alias", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(
            ["venue_id"],
            ["venue.id"],
            name=op.f("fk_venue_alias_venue_id_venue"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("venue_id", "alias", name=op.f("pk_venue_alias")),
    )
    op.create_table(
        "planning_inputs",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("festival_id", sa.String(length=36), nullable=False),
        sa.Column("preferences", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["festival_id"],
            ["festival.id"],
            name=op.f("fk_planning_inputs_festival_id_festival"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["app_user.id"],
            name=op.f("fk_planning_inputs_user_id_app_user"),
        ),
        sa.PrimaryKeyConstraint(
            "user_id", "festival_id", name=op.f("pk_planning_inputs")
        ),
    )
    op.create_table(
        "planning_target",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("festival_id", sa.String(length=36), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("target_id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(
            ["festival_id"],
            ["festival.id"],
            name=op.f("fk_planning_target_festival_id_festival"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["app_user.id"],
            name=op.f("fk_planning_target_user_id_app_user"),
        ),
        sa.PrimaryKeyConstraint(
            "user_id",
            "festival_id",
            "kind",
            "target_id",
            name=op.f("pk_planning_target"),
        ),
    )
    op.create_table(
        "programme_entry",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("festival_id", sa.String(length=36), nullable=False),
        sa.Column("source_key", sa.String(), nullable=False),
        sa.Column("film_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("country", sa.String(), nullable=True),
        sa.Column("url", sa.String(), nullable=True),
        sa.Column("tagline", sa.Text(), nullable=True),
        sa.Column("synopsis", sa.Text(), nullable=True),
        sa.Column("poster_url", sa.String(), nullable=True),
        sa.Column("still_url", sa.String(), nullable=True),
        sa.Column("runtime_minutes", sa.Integer(), nullable=True),
        sa.Column("original_title", sa.String(), nullable=True),
        sa.Column("director", sa.String(), nullable=True),
        sa.Column("genre", sa.String(), nullable=True),
        sa.Column("language", sa.String(), nullable=True),
        sa.Column("subtitles", sa.String(), nullable=True),
        sa.Column("age_limit", sa.String(), nullable=True),
        sa.Column("imdb_url", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(
            ["festival_id"],
            ["festival.id"],
            name=op.f("fk_programme_entry_festival_id_festival"),
        ),
        sa.ForeignKeyConstraint(
            ["film_id"], ["film.id"], name=op.f("fk_programme_entry_film_id_film")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_programme_entry")),
        sa.UniqueConstraint(
            "festival_id",
            "source_key",
            name=op.f("uq_programme_entry_festival_id_source_key"),
        ),
    )
    op.create_table(
        "schedule",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("festival_id", sa.String(length=36), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("change_set", sa.Text(), nullable=False),
        sa.Column("accepted_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["festival_id"],
            ["festival.id"],
            name=op.f("fk_schedule_festival_id_festival"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["app_user.id"], name=op.f("fk_schedule_user_id_app_user")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_schedule")),
        sa.UniqueConstraint(
            "user_id",
            "festival_id",
            "number",
            name=op.f("uq_schedule_user_id_festival_id_number"),
        ),
    )
    op.create_table(
        "draft",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("festival_id", sa.String(length=36), nullable=False),
        sa.Column("base_schedule_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("change_set", sa.Text(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("reasons", sa.Text(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("solved_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["base_schedule_id"],
            ["schedule.id"],
            name=op.f("fk_draft_base_schedule_id_schedule"),
        ),
        sa.ForeignKeyConstraint(
            ["festival_id"], ["festival.id"], name=op.f("fk_draft_festival_id_festival")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["app_user.id"], name=op.f("fk_draft_user_id_app_user")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_draft")),
    )
    with op.batch_alter_table("draft", schema=None) as batch_op:
        batch_op.create_index(
            "ix_draft_user_id_festival_id", ["user_id", "festival_id"], unique=False
        )

    op.create_table(
        "screening",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("programme_entry_id", sa.String(length=36), nullable=False),
        sa.Column("venue_id", sa.String(length=36), nullable=False),
        sa.Column("start_time", sa.DateTime(), nullable=False),
        sa.Column("end_time", sa.DateTime(), nullable=False),
        sa.Column("auditorium", sa.String(), nullable=True),
        sa.Column("ticket_url", sa.String(), nullable=True),
        sa.Column("withdrawn", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["programme_entry_id"],
            ["programme_entry.id"],
            name=op.f("fk_screening_programme_entry_id_programme_entry"),
        ),
        sa.ForeignKeyConstraint(
            ["venue_id"], ["venue.id"], name=op.f("fk_screening_venue_id_venue")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_screening")),
        sa.UniqueConstraint(
            "programme_entry_id",
            "venue_id",
            "start_time",
            name=op.f("uq_screening_programme_entry_id_venue_id_start_time"),
        ),
    )
    op.create_table(
        "draft_screening",
        sa.Column("draft_id", sa.String(length=36), nullable=False),
        sa.Column("screening_id", sa.String(length=36), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("arrival_time", sa.DateTime(), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(
            ["draft_id"],
            ["draft.id"],
            name=op.f("fk_draft_screening_draft_id_draft"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["screening_id"],
            ["screening.id"],
            name=op.f("fk_draft_screening_screening_id_screening"),
        ),
        sa.PrimaryKeyConstraint(
            "draft_id", "screening_id", name=op.f("pk_draft_screening")
        ),
    )
    op.create_table(
        "schedule_screening",
        sa.Column("schedule_id", sa.String(length=36), nullable=False),
        sa.Column("screening_id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(
            ["schedule_id"],
            ["schedule.id"],
            name=op.f("fk_schedule_screening_schedule_id_schedule"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["screening_id"],
            ["screening.id"],
            name=op.f("fk_schedule_screening_screening_id_screening"),
        ),
        sa.PrimaryKeyConstraint(
            "schedule_id", "screening_id", name=op.f("pk_schedule_screening")
        ),
    )
    op.create_table(
        "screening_event",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("screening_id", sa.String(length=36), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("description", sa.String(), nullable=False),
        sa.Column("start_time", sa.DateTime(), nullable=True),
        sa.Column("end_time", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["screening_id"],
            ["screening.id"],
            name=op.f("fk_screening_event_screening_id_screening"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_screening_event")),
    )
    op.create_table(
        "seen_dismissal",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("screening_id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(
            ["screening_id"],
            ["screening.id"],
            name=op.f("fk_seen_dismissal_screening_id_screening"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["app_user.id"],
            name=op.f("fk_seen_dismissal_user_id_app_user"),
        ),
        sa.PrimaryKeyConstraint(
            "user_id", "screening_id", name=op.f("pk_seen_dismissal")
        ),
    )
    op.create_table(
        "ticket",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("screening_id", sa.String(length=36), nullable=False),
        sa.Column("exchangeable", sa.Boolean(), nullable=False),
        sa.Column("refundable", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["screening_id"],
            ["screening.id"],
            name=op.f("fk_ticket_screening_id_screening"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["app_user.id"], name=op.f("fk_ticket_user_id_app_user")
        ),
        sa.PrimaryKeyConstraint("user_id", "screening_id", name=op.f("pk_ticket")),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("ticket")
    op.drop_table("seen_dismissal")
    op.drop_table("screening_event")
    op.drop_table("schedule_screening")
    op.drop_table("draft_screening")
    op.drop_table("screening")
    with op.batch_alter_table("draft", schema=None) as batch_op:
        batch_op.drop_index("ix_draft_user_id_festival_id")

    op.drop_table("draft")
    op.drop_table("schedule")
    op.drop_table("programme_entry")
    op.drop_table("planning_target")
    op.drop_table("planning_inputs")
    op.drop_table("venue_alias")
    op.drop_table("seen")
    op.drop_table("route")
    op.drop_table("festival")
    op.drop_table("venue")
    with op.batch_alter_table("film", schema=None) as batch_op:
        batch_op.drop_index("ix_film_match_key_year")

    op.drop_table("film")
    op.drop_table("festival_series")
    op.drop_table("app_user")
