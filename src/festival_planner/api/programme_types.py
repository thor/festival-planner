"""GraphQL types for festival data: Festivals, Venues, Films and the programme.

Relations resolve through the request's DataLoaders. Lists of a Festival's
Programme Entries and Screenings are relay connections over in-memory lists.
"""

import datetime
from collections.abc import Awaitable, Callable, Iterable, Mapping
from typing import Self

import strawberry
from strawberry import relay

from ..domain import festival as f
from ..domain import programme as p
from .context import Info


@strawberry.type(description="Something belonging to a Screening beyond the film.")
class Event:
    description: str
    start_time: datetime.datetime | None = strawberry.field(
        description="Null when the Event happens within the Screening."
    )
    end_time: datetime.datetime | None

    @classmethod
    def from_domain(cls, value: p.Event) -> Self:
        return cls(
            description=value.description,
            start_time=value.start_time,
            end_time=value.end_time,
        )


@strawberry.type(description="The recurring identity that groups Festivals.")
class FestivalSeries:
    slug: str
    name: str

    @classmethod
    def from_domain(cls, value: f.FestivalSeries) -> Self:
        return cls(slug=value.slug, name=value.name)


@strawberry.type(description="A fixed physical place where Screenings take place.")
class Venue(relay.Node):
    id: relay.NodeID[str]
    name: str

    @classmethod
    def from_domain(cls, value: p.Venue) -> Self:
        return cls(id=value.id, name=value.name)


@strawberry.type(description="A cinematic work, independent of any Festival.")
class Film(relay.Node):
    id: relay.NodeID[str]
    title: str
    year: int | None

    @classmethod
    def from_domain(cls, value: p.Film) -> Self:
        return cls(id=value.id, title=value.title, year=value.year)


@strawberry.type(
    description="A single showing of a Programme Entry at a given time and Venue."
)
class Screening(relay.Node):
    id: relay.NodeID[str]
    start_time: datetime.datetime
    end_time: datetime.datetime
    auditorium: str | None
    ticket_url: str | None
    events: list[Event]
    withdrawn: bool = strawberry.field(
        description="Whether the Screening is no longer in the programme."
    )
    programme_entry_id: strawberry.Private[p.ProgrammeEntryId]
    venue_id: strawberry.Private[p.VenueId]

    @classmethod
    def from_domain(cls, value: p.Screening) -> Self:
        return cls(
            id=value.id,
            start_time=value.start_time,
            end_time=value.end_time,
            auditorium=value.auditorium,
            ticket_url=value.ticket_url,
            events=[Event.from_domain(e) for e in value.events],
            withdrawn=value.withdrawn,
            programme_entry_id=value.programme_entry_id,
            venue_id=value.venue_id,
        )

    @strawberry.field
    async def programme_entry(self, info: Info) -> "ProgrammeEntry":
        entry = await info.context.loaders.programme_entry.load(self.programme_entry_id)
        if entry is None:
            raise LookupError(f"Programme Entry {self.programme_entry_id!r} is missing")
        return ProgrammeEntry.from_domain(entry)

    @strawberry.field
    async def venue(self, info: Info) -> Venue:
        venue = await info.context.loaders.venue.load(self.venue_id)
        if venue is None:
            raise LookupError(f"Venue {self.venue_id!r} is missing")
        return Venue.from_domain(venue)


@strawberry.type(description="A Film as presented in one Festival's programme.")
class ProgrammeEntry(relay.Node):
    id: relay.NodeID[str]
    title: str
    year: int | None
    country: str | None
    url: str | None
    film_id: strawberry.Private[p.FilmId]

    @classmethod
    def from_domain(cls, value: p.ProgrammeEntry) -> Self:
        return cls(
            id=value.id,
            title=value.title,
            year=value.year,
            country=value.country,
            url=value.url,
            film_id=value.film_id,
        )

    @strawberry.field
    async def film(self, info: Info) -> Film:
        film = await info.context.loaders.film.load(self.film_id)
        if film is None:
            raise LookupError(f"Film {self.film_id!r} is missing")
        return Film.from_domain(film)

    @strawberry.field(description="By start time.")
    async def screenings(
        self, info: Info, include_withdrawn: bool = False
    ) -> list[Screening]:
        key = (p.ProgrammeEntryId(self.id), include_withdrawn)
        screenings = await info.context.loaders.screenings_of_entry.load(key)
        return [Screening.from_domain(s) for s in screenings]


@strawberry.type(description="A single edition of a film festival.")
class Festival(relay.Node):
    id: relay.NodeID[str]
    slug: str
    name: str
    start_date: datetime.date
    end_date: datetime.date
    time_zone: str = strawberry.field(
        description='An IANA time zone, e.g. "Europe/Oslo".'
    )
    series_id: strawberry.Private[f.FestivalSeriesId | None]

    @classmethod
    def from_domain(cls, value: f.Festival) -> Self:
        return cls(
            id=value.id,
            slug=value.slug,
            name=value.name,
            start_date=value.start_date,
            end_date=value.end_date,
            time_zone=value.time_zone,
            series_id=value.series_id,
        )

    @strawberry.field
    async def series(self, info: Info) -> FestivalSeries | None:
        if self.series_id is None:
            return None
        series = await info.context.loaders.festival_series.load(self.series_id)
        return None if series is None else FestivalSeries.from_domain(series)

    @relay.connection(relay.ListConnection[ProgrammeEntry], description="By title.")
    async def programme_entries(self, info: Info) -> Iterable[ProgrammeEntry]:
        ctx = info.context
        entries = await ctx.run(
            ctx.deps.programme.programme_entries, f.FestivalId(self.id)
        )
        for entry in entries:
            ctx.loaders.programme_entry.prime(entry.id, entry)
        return [ProgrammeEntry.from_domain(e) for e in entries]

    @relay.connection(relay.ListConnection[Screening], description="By start time.")
    async def screenings(
        self, info: Info, include_withdrawn: bool = False
    ) -> Iterable[Screening]:
        ctx = info.context
        screenings = await ctx.run(
            ctx.deps.programme.screenings,
            f.FestivalId(self.id),
            include_withdrawn=include_withdrawn,
        )
        for s in screenings:
            ctx.loaders.screening.prime(s.id, s)
        return [Screening.from_domain(s) for s in screenings]


async def festival_node(info: Info, domain_id: str) -> Festival | None:
    value = await info.context.loaders.festival.load(f.FestivalId(domain_id))
    return None if value is None else Festival.from_domain(value)


async def venue_node(info: Info, domain_id: str) -> Venue | None:
    value = await info.context.loaders.venue.load(p.VenueId(domain_id))
    return None if value is None else Venue.from_domain(value)


async def film_node(info: Info, domain_id: str) -> Film | None:
    value = await info.context.loaders.film.load(p.FilmId(domain_id))
    return None if value is None else Film.from_domain(value)


async def programme_entry_node(info: Info, domain_id: str) -> ProgrammeEntry | None:
    entry_id = p.ProgrammeEntryId(domain_id)
    value = await info.context.loaders.programme_entry.load(entry_id)
    return None if value is None else ProgrammeEntry.from_domain(value)


async def screening_node(info: Info, domain_id: str) -> Screening | None:
    value = await info.context.loaders.screening.load(p.ScreeningId(domain_id))
    return None if value is None else Screening.from_domain(value)


NodeResolver = Callable[[Info, str], Awaitable[relay.Node | None]]
"""Finds a node by its domain id, or `None`."""

PROGRAMME_NODES: Mapping[str, NodeResolver] = {
    "Festival": festival_node,
    "Venue": venue_node,
    "Film": film_node,
    "ProgrammeEntry": programme_entry_node,
    "Screening": screening_node,
}
"""Node resolvers for festival data, by GraphQL type name."""


@strawberry.type
class ProgrammeQuery:
    """The Query fields for festival data."""

    @strawberry.field(description="By start date, then slug.")
    async def festivals(self, info: Info) -> list[Festival]:
        ctx = info.context
        festivals = await ctx.run(ctx.deps.programme.festivals)
        return [Festival.from_domain(x) for x in festivals]

    @strawberry.field
    async def festival(self, info: Info, slug: str) -> Festival | None:
        ctx = info.context
        value = await ctx.run(ctx.deps.programme.festival, slug)
        return None if value is None else Festival.from_domain(value)

    @strawberry.field(description="By name.")
    async def venues(self, info: Info) -> list[Venue]:
        ctx = info.context
        venues = await ctx.run(ctx.deps.programme.venues)
        return [Venue.from_domain(v) for v in venues]
