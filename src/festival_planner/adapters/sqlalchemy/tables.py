"""Database tables. Rows are adapter types; repositories map them to the domain."""

import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator

ID = String(36)

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class UTCDateTime(TypeDecorator[datetime.datetime]):
    """Aware datetimes stored as naive UTC, read back with tzinfo=UTC."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError(f"Refusing to store naive datetime {value!r}")
        return value.astimezone(datetime.UTC).replace(tzinfo=None)

    def process_result_value(self, value, dialect):
        return None if value is None else value.replace(tzinfo=datetime.UTC)


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class FestivalSeriesRow(Base):
    __tablename__ = "festival_series"
    id: Mapped[str] = mapped_column(ID, primary_key=True)
    slug: Mapped[str] = mapped_column(String, unique=True)
    name: Mapped[str] = mapped_column(String)


class FestivalRow(Base):
    __tablename__ = "festival"
    id: Mapped[str] = mapped_column(ID, primary_key=True)
    slug: Mapped[str] = mapped_column(String, unique=True)
    name: Mapped[str] = mapped_column(String)
    start_date: Mapped[datetime.date] = mapped_column(Date)
    end_date: Mapped[datetime.date] = mapped_column(Date)
    time_zone: Mapped[str] = mapped_column(String)
    series_id: Mapped[str | None] = mapped_column(ForeignKey("festival_series.id"))


class FilmRow(Base):
    __tablename__ = "film"
    id: Mapped[str] = mapped_column(ID, primary_key=True)
    title: Mapped[str] = mapped_column(String)
    year: Mapped[int | None] = mapped_column(Integer)
    match_key: Mapped[str] = mapped_column(String)
    """`domain.programme.title_key(title)`, for resolving Films at ingestion."""
    __table_args__ = (Index("ix_film_match_key_year", "match_key", "year"),)


class VenueRow(Base):
    __tablename__ = "venue"
    id: Mapped[str] = mapped_column(ID, primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True)
    aliases: Mapped[list["VenueAliasRow"]] = relationship(
        cascade="all, delete-orphan", order_by="VenueAliasRow.alias"
    )


class VenueAliasRow(Base):
    __tablename__ = "venue_alias"
    venue_id: Mapped[str] = mapped_column(
        ForeignKey("venue.id", ondelete="CASCADE"), primary_key=True
    )
    alias: Mapped[str] = mapped_column(String, primary_key=True)


class RouteRow(Base):
    __tablename__ = "route"
    from_venue_id: Mapped[str] = mapped_column(ForeignKey("venue.id"), primary_key=True)
    to_venue_id: Mapped[str] = mapped_column(ForeignKey("venue.id"), primary_key=True)
    mode: Mapped[str] = mapped_column(String, primary_key=True)
    minutes: Mapped[int] = mapped_column(Integer)
    __table_args__ = (CheckConstraint("minutes >= 0", name="minutes_non_negative"),)


class ProgrammeEntryRow(Base):
    __tablename__ = "programme_entry"
    id: Mapped[str] = mapped_column(ID, primary_key=True)
    festival_id: Mapped[str] = mapped_column(ForeignKey("festival.id"))
    source_key: Mapped[str] = mapped_column(String)
    film_id: Mapped[str] = mapped_column(ForeignKey("film.id"))
    title: Mapped[str] = mapped_column(String)
    year: Mapped[int | None] = mapped_column(Integer)
    country: Mapped[str | None] = mapped_column(String)
    url: Mapped[str | None] = mapped_column(String)
    # Details: what the Festival says about the film.
    tagline: Mapped[str | None] = mapped_column(Text)
    synopsis: Mapped[str | None] = mapped_column(Text)
    poster_url: Mapped[str | None] = mapped_column(String)
    still_url: Mapped[str | None] = mapped_column(String)
    runtime_minutes: Mapped[int | None] = mapped_column(Integer)
    original_title: Mapped[str | None] = mapped_column(String)
    director: Mapped[str | None] = mapped_column(String)
    genre: Mapped[str | None] = mapped_column(String)
    language: Mapped[str | None] = mapped_column(String)
    subtitles: Mapped[str | None] = mapped_column(String)
    age_limit: Mapped[str | None] = mapped_column(String)
    imdb_url: Mapped[str | None] = mapped_column(String)
    __table_args__ = (UniqueConstraint("festival_id", "source_key"),)


class ScreeningRow(Base):
    __tablename__ = "screening"
    id: Mapped[str] = mapped_column(ID, primary_key=True)
    programme_entry_id: Mapped[str] = mapped_column(ForeignKey("programme_entry.id"))
    venue_id: Mapped[str] = mapped_column(ForeignKey("venue.id"))
    start_time: Mapped[datetime.datetime] = mapped_column(UTCDateTime)
    end_time: Mapped[datetime.datetime] = mapped_column(UTCDateTime)
    auditorium: Mapped[str | None] = mapped_column(String)
    ticket_url: Mapped[str | None] = mapped_column(String)
    withdrawn: Mapped[bool] = mapped_column(default=False)
    events: Mapped[list["ScreeningEventRow"]] = relationship(
        cascade="all, delete-orphan", order_by="ScreeningEventRow.position"
    )
    __table_args__ = (UniqueConstraint("programme_entry_id", "venue_id", "start_time"),)


class ScreeningEventRow(Base):
    __tablename__ = "screening_event"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    screening_id: Mapped[str] = mapped_column(
        ForeignKey("screening.id", ondelete="CASCADE")
    )
    position: Mapped[int] = mapped_column(Integer)
    description: Mapped[str] = mapped_column(String)
    start_time: Mapped[datetime.datetime | None] = mapped_column(UTCDateTime)
    end_time: Mapped[datetime.datetime | None] = mapped_column(UTCDateTime)


PLANNING_TARGET_KINDS = (
    "screening_commitments",
    "film_commitments",
    "excluded_screenings",
    "excluded_programme_entries",
)
"""`PlanningTargetRow.kind` values: the set fields of `PlanningInputs`."""


class UserRow(Base):
    __tablename__ = "app_user"
    id: Mapped[str] = mapped_column(ID, primary_key=True)
    issuer: Mapped[str] = mapped_column(String)
    subject: Mapped[str] = mapped_column(String)
    __table_args__ = (UniqueConstraint("issuer", "subject"),)


class PlanningInputsRow(Base):
    __tablename__ = "planning_inputs"
    user_id: Mapped[str] = mapped_column(ForeignKey("app_user.id"), primary_key=True)
    festival_id: Mapped[str] = mapped_column(
        ForeignKey("festival.id"), primary_key=True
    )
    preferences: Mapped[str] = mapped_column(Text)
    """`Preferences` as JSON."""


class PlanningTargetRow(Base):
    """One commitment or Excluded id of a User's accepted inputs."""

    __tablename__ = "planning_target"
    user_id: Mapped[str] = mapped_column(ForeignKey("app_user.id"), primary_key=True)
    festival_id: Mapped[str] = mapped_column(
        ForeignKey("festival.id"), primary_key=True
    )
    kind: Mapped[str] = mapped_column(String, primary_key=True)
    target_id: Mapped[str] = mapped_column(ID, primary_key=True)


class ScheduleRow(Base):
    __tablename__ = "schedule"
    id: Mapped[str] = mapped_column(ID, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_user.id"))
    festival_id: Mapped[str] = mapped_column(ForeignKey("festival.id"))
    number: Mapped[int] = mapped_column(Integer)
    score: Mapped[float] = mapped_column(Float)
    change_set: Mapped[str] = mapped_column(Text)
    """`ChangeSet` as JSON."""
    accepted_at: Mapped[datetime.datetime] = mapped_column(UTCDateTime)
    screenings: Mapped[list["ScheduleScreeningRow"]] = relationship(
        cascade="all, delete-orphan", order_by="ScheduleScreeningRow.screening_id"
    )
    __table_args__ = (UniqueConstraint("user_id", "festival_id", "number"),)


class ScheduleScreeningRow(Base):
    __tablename__ = "schedule_screening"
    schedule_id: Mapped[str] = mapped_column(
        ForeignKey("schedule.id", ondelete="CASCADE"), primary_key=True
    )
    screening_id: Mapped[str] = mapped_column(
        ForeignKey("screening.id"), primary_key=True
    )


class DraftRow(Base):
    __tablename__ = "draft"
    id: Mapped[str] = mapped_column(ID, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_user.id"))
    festival_id: Mapped[str] = mapped_column(ForeignKey("festival.id"))
    base_schedule_id: Mapped[str | None] = mapped_column(ForeignKey("schedule.id"))
    status: Mapped[str] = mapped_column(String)
    attempt: Mapped[int] = mapped_column(Integer)
    change_set: Mapped[str] = mapped_column(Text)
    score: Mapped[float] = mapped_column(Float)
    reasons: Mapped[str] = mapped_column(Text)
    """JSON list of strings."""
    notes: Mapped[str] = mapped_column(Text)
    """JSON list of strings."""
    created_at: Mapped[datetime.datetime] = mapped_column(UTCDateTime)
    solved_at: Mapped[datetime.datetime | None] = mapped_column(UTCDateTime)
    scheduled: Mapped[list["DraftScreeningRow"]] = relationship(
        cascade="all, delete-orphan", order_by="DraftScreeningRow.position"
    )
    __table_args__ = (Index("ix_draft_user_id_festival_id", "user_id", "festival_id"),)


class DraftScreeningRow(Base):
    __tablename__ = "draft_screening"
    draft_id: Mapped[str] = mapped_column(
        ForeignKey("draft.id", ondelete="CASCADE"), primary_key=True
    )
    screening_id: Mapped[str] = mapped_column(
        ForeignKey("screening.id"), primary_key=True
    )
    position: Mapped[int] = mapped_column(Integer)
    arrival_time: Mapped[datetime.datetime] = mapped_column(UTCDateTime)
    weight: Mapped[float] = mapped_column(Float)


class TicketRow(Base):
    __tablename__ = "ticket"
    user_id: Mapped[str] = mapped_column(ForeignKey("app_user.id"), primary_key=True)
    screening_id: Mapped[str] = mapped_column(
        ForeignKey("screening.id"), primary_key=True
    )
    exchangeable: Mapped[bool] = mapped_column(Boolean)
    refundable: Mapped[bool] = mapped_column(Boolean)


class SeenRow(Base):
    """A Film a User marked Seen by hand (or, later, by provider sync)."""

    __tablename__ = "seen"
    user_id: Mapped[str] = mapped_column(ForeignKey("app_user.id"), primary_key=True)
    film_id: Mapped[str] = mapped_column(ForeignKey("film.id"), primary_key=True)
    source: Mapped[str] = mapped_column(String)


class SeenDismissalRow(Base):
    """A Screening the User did not attend, though it was in their Active Schedule."""

    __tablename__ = "seen_dismissal"
    user_id: Mapped[str] = mapped_column(ForeignKey("app_user.id"), primary_key=True)
    screening_id: Mapped[str] = mapped_column(
        ForeignKey("screening.id"), primary_key=True
    )
