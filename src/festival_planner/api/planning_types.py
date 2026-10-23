"""GraphQL types for a signed-in User's planning: Drafts, Schedules, inputs.

Each resolver reads through one Planner call on a worker thread, or through
the request's DataLoaders. Drafts and Schedules are Nodes only to their owner.
"""

import asyncio
import datetime
import enum
from collections.abc import Iterable, Mapping
from typing import Annotated, Self, assert_never

import strawberry
from strawberry import relay

from ..domain import change_sets as cs
from ..domain import drafts as d
from ..domain import festival as f
from ..domain import insights as ins
from ..domain import planning as pl
from ..domain import programme as p
from ..domain import solving as so
from ..domain.planner import DraftView, NotFoundError
from ..domain.users import UserId
from .context import Info
from .ids import decode
from .programme_types import Festival, Film, NodeResolver, ProgrammeEntry, Screening
from .programme_types import Venue as VenueType

RESET = "Null resets the setting to its default."


@strawberry.enum(description="Where a Draft's solve is.")
class DraftStatus(enum.Enum):
    """The domain's `DraftStatus`, mapped by value."""

    SOLVING = "SOLVING"
    READY = "READY"
    INFEASIBLE = "INFEASIBLE"
    FAILED = "FAILED"


@strawberry.enum(description="What a Flag is about.")
class FlagKind(enum.Enum):
    """The domain's `FlagKind`, mapped by value."""

    WITHDRAWN_COMMITMENT = "WITHDRAWN_COMMITMENT"
    WITHDRAWN_TICKET = "WITHDRAWN_TICKET"
    UNSCHEDULED_TICKET = "UNSCHEDULED_TICKET"
    WITHDRAWN_IN_SCHEDULE = "WITHDRAWN_IN_SCHEDULE"


# --- Loading related objects -----------------------------------------------


async def _screening(info: Info, screening_id: p.ScreeningId) -> Screening:
    value = await info.context.loaders.screening.load(screening_id)
    if value is None:
        raise LookupError(f"Screening {screening_id!r} is missing")
    return Screening.from_domain(value)


async def _screenings(info: Info, ids: Iterable[p.ScreeningId]) -> list[Screening]:
    """The Screenings, by start time; each must exist."""
    wanted = list(ids)
    found = await info.context.loaders.screening.load_many(wanted)
    values: list[p.Screening] = []
    for screening_id, value in zip(wanted, found, strict=True):
        if value is None:
            raise LookupError(f"Screening {screening_id!r} is missing")
        values.append(value)
    values.sort(key=lambda s: (s.start_time, s.id))
    return [Screening.from_domain(s) for s in values]


async def _entry(info: Info, entry_id: p.ProgrammeEntryId) -> ProgrammeEntry:
    value = await info.context.loaders.programme_entry.load(entry_id)
    if value is None:
        raise LookupError(f"Programme Entry {entry_id!r} is missing")
    return ProgrammeEntry.from_domain(value)


async def _entries(
    info: Info, ids: Iterable[p.ProgrammeEntryId]
) -> list[ProgrammeEntry]:
    """The Programme Entries, by title; each must exist."""
    wanted = list(ids)
    found = await info.context.loaders.programme_entry.load_many(wanted)
    values: list[p.ProgrammeEntry] = []
    for entry_id, value in zip(wanted, found, strict=True):
        if value is None:
            raise LookupError(f"Programme Entry {entry_id!r} is missing")
        values.append(value)
    values.sort(key=lambda e: (p.title_key(e.title), e.id))
    return [ProgrammeEntry.from_domain(e) for e in values]


async def _venue(info: Info, venue_id: p.VenueId) -> VenueType:
    value = await info.context.loaders.venue.load(venue_id)
    if value is None:
        raise LookupError(f"Venue {venue_id!r} is missing")
    return VenueType.from_domain(value)


async def _festival(info: Info, festival_id: f.FestivalId) -> Festival:
    value = await info.context.loaders.festival.load(festival_id)
    if value is None:
        raise LookupError(f"Festival {festival_id!r} is missing")
    return Festival.from_domain(value)


# --- Bases for things that point at a Screening, Entry or pair -------------


@strawberry.type
class _OnScreening:
    screening_id: strawberry.Private[p.ScreeningId]

    @strawberry.field
    async def screening(self, info: Info) -> Screening:
        return await _screening(info, self.screening_id)


@strawberry.type
class _OnProgrammeEntry:
    programme_entry_id: strawberry.Private[p.ProgrammeEntryId]

    @strawberry.field
    async def programme_entry(self, info: Info) -> ProgrammeEntry:
        return await _entry(info, self.programme_entry_id)


@strawberry.type
class _Pair:
    preferred_id: strawberry.Private[p.ProgrammeEntryId]
    other_id: strawberry.Private[p.ProgrammeEntryId]

    @strawberry.field
    async def preferred(self, info: Info) -> ProgrammeEntry:
        return await _entry(info, self.preferred_id)

    @strawberry.field
    async def other(self, info: Info) -> ProgrammeEntry:
        return await _entry(info, self.other_id)


# --- Change Set items: one type per domain item ----------------------------


@strawberry.type
class AddScreeningCommitment(_OnScreening):
    pass


@strawberry.type
class ReleaseScreeningCommitment(_OnScreening):
    pass


@strawberry.type
class AddFilmCommitment(_OnProgrammeEntry):
    pass


@strawberry.type
class ReleaseFilmCommitment(_OnProgrammeEntry):
    pass


@strawberry.type
class AddExcludedScreening(_OnScreening):
    pass


@strawberry.type
class RemoveExcludedScreening(_OnScreening):
    pass


@strawberry.type
class AddExcludedProgrammeEntry(_OnProgrammeEntry):
    pass


@strawberry.type
class RemoveExcludedProgrammeEntry(_OnProgrammeEntry):
    pass


@strawberry.type
class SetProgrammeEntryWeight(_OnProgrammeEntry):
    weight: float | None = strawberry.field(description=RESET)


@strawberry.type
class SetScreeningWeight(_OnScreening):
    weight: float | None = strawberry.field(description=RESET)


@strawberry.type
class SetYearWeight:
    year: int
    weight: float | None = strawberry.field(description=RESET)


@strawberry.type(description="The general buffer, or with a Venue that Venue's.")
class SetBuffer:
    venue_id: strawberry.Private[p.VenueId | None]
    minutes: int | None = strawberry.field(description=RESET)

    @strawberry.field
    async def venue(self, info: Info) -> VenueType | None:
        return None if self.venue_id is None else await _venue(info, self.venue_id)


@strawberry.type
class SetDateRange:
    start_date: datetime.date | None
    end_date: datetime.date | None


@strawberry.type
class SetEventWeight:
    weight: float | None = strawberry.field(description=RESET)


@strawberry.type
class SetAttendEvents:
    attend: bool | None = strawberry.field(description=RESET)


@strawberry.type
class SetTransportMode:
    mode: str | None = strawberry.field(description=RESET)


@strawberry.type
class SetComparisonWeight:
    weight: float | None = strawberry.field(description=RESET)


@strawberry.type(description="Replaces any earlier Comparison of the same pair.")
class RecordComparison(_Pair):
    pass


ChangeSetItem = Annotated[
    AddScreeningCommitment
    | ReleaseScreeningCommitment
    | AddFilmCommitment
    | ReleaseFilmCommitment
    | AddExcludedScreening
    | RemoveExcludedScreening
    | AddExcludedProgrammeEntry
    | RemoveExcludedProgrammeEntry
    | SetProgrammeEntryWeight
    | SetScreeningWeight
    | SetYearWeight
    | SetBuffer
    | SetDateRange
    | SetEventWeight
    | SetAttendEvents
    | SetTransportMode
    | SetComparisonWeight
    | RecordComparison,
    strawberry.union("ChangeSetItem", description="One change a Change Set proposes."),
]


def change_set_item(item: cs.ChangeSetItem) -> ChangeSetItem:
    match item:
        case cs.AddScreeningCommitment():
            return AddScreeningCommitment(screening_id=item.screening_id)
        case cs.ReleaseScreeningCommitment():
            return ReleaseScreeningCommitment(screening_id=item.screening_id)
        case cs.AddFilmCommitment():
            return AddFilmCommitment(programme_entry_id=item.programme_entry_id)
        case cs.ReleaseFilmCommitment():
            return ReleaseFilmCommitment(programme_entry_id=item.programme_entry_id)
        case cs.AddExcludedScreening():
            return AddExcludedScreening(screening_id=item.screening_id)
        case cs.RemoveExcludedScreening():
            return RemoveExcludedScreening(screening_id=item.screening_id)
        case cs.AddExcludedProgrammeEntry():
            return AddExcludedProgrammeEntry(programme_entry_id=item.programme_entry_id)
        case cs.RemoveExcludedProgrammeEntry():
            return RemoveExcludedProgrammeEntry(
                programme_entry_id=item.programme_entry_id
            )
        case cs.SetProgrammeEntryWeight():
            return SetProgrammeEntryWeight(
                programme_entry_id=item.programme_entry_id, weight=item.weight
            )
        case cs.SetScreeningWeight():
            return SetScreeningWeight(
                screening_id=item.screening_id, weight=item.weight
            )
        case cs.SetYearWeight():
            return SetYearWeight(year=item.year, weight=item.weight)
        case cs.SetBuffer():
            return SetBuffer(venue_id=item.venue_id, minutes=item.minutes)
        case cs.SetDateRange():
            return SetDateRange(start_date=item.start_date, end_date=item.end_date)
        case cs.SetEventWeight():
            return SetEventWeight(weight=item.weight)
        case cs.SetAttendEvents():
            return SetAttendEvents(attend=item.attend)
        case cs.SetTransportMode():
            return SetTransportMode(mode=item.mode)
        case cs.SetComparisonWeight():
            return SetComparisonWeight(weight=item.weight)
        case cs.RecordComparison():
            return RecordComparison(preferred_id=item.preferred, other_id=item.other)
        case _:
            assert_never(item)


def _change_set(change_set: cs.ChangeSet) -> list[ChangeSetItem]:
    return [change_set_item(item) for item in change_set.items]


# --- Drafts and Schedules --------------------------------------------------


@strawberry.type(description="A Screening in a Draft's Schedule.")
class ScheduledScreening(_OnScreening):
    arrival_time: datetime.datetime
    weight: float

    @classmethod
    def from_domain(cls, value: so.ScheduledScreening) -> Self:
        return cls(
            screening_id=value.screening_id,
            arrival_time=value.arrival_time,
            weight=value.weight,
        )


@strawberry.type(description="A Draft's Schedule against the Active Schedule.")
class DraftDiff:
    score_delta: float = strawberry.field(
        description=(
            "The Draft's score minus the Active Schedule's, "
            "both under the Draft's Preferences."
        )
    )
    added_ids: strawberry.Private[frozenset[p.ScreeningId]]
    removed_ids: strawberry.Private[frozenset[p.ScreeningId]]
    dropped_ticket_ids: strawberry.Private[frozenset[p.ScreeningId]]

    @classmethod
    def from_domain(cls, value: ins.DraftDiff) -> Self:
        return cls(
            score_delta=value.score_delta,
            added_ids=value.added,
            removed_ids=value.removed,
            dropped_ticket_ids=value.dropped_tickets,
        )

    @strawberry.field(description="By start time.")
    async def added(self, info: Info) -> list[Screening]:
        return await _screenings(info, self.added_ids)

    @strawberry.field(description="By start time.")
    async def removed(self, info: Info) -> list[Screening]:
        return await _screenings(info, self.removed_ids)

    @strawberry.field(
        description="Removed Screenings the User holds a Ticket for; by start time."
    )
    async def dropped_tickets(self, info: Info) -> list[Screening]:
        return await _screenings(info, self.dropped_ticket_ids)


@strawberry.type(
    description="A proposed Schedule: a Change Set and the Schedule solved from it."
)
class Draft(relay.Node):
    id: relay.NodeID[str]
    status: DraftStatus
    stale: bool = strawberry.field(
        description="Whether the Active Schedule changed since this Draft was based on it."
    )
    change_set: list[ChangeSetItem]
    screenings: list[ScheduledScreening] = strawberry.field(
        description="By arrival time."
    )
    score: float
    reasons: list[str] = strawberry.field(
        description="Why the Draft is INFEASIBLE or FAILED."
    )
    notes: list[str] = strawberry.field(
        description="What re-solving changed in the Change Set."
    )
    created_at: datetime.datetime
    solved_at: datetime.datetime | None
    user_id: strawberry.Private[UserId]
    festival_id: strawberry.Private[f.FestivalId]

    @classmethod
    def from_view(cls, view: DraftView) -> Self:
        draft = view.draft
        scheduled = sorted(
            draft.scheduled, key=lambda s: (s.arrival_time, s.screening_id)
        )
        return cls(
            id=draft.id,
            status=DraftStatus(draft.status.value),
            stale=view.stale,
            change_set=_change_set(draft.change_set),
            screenings=[ScheduledScreening.from_domain(s) for s in scheduled],
            score=draft.score,
            reasons=list(draft.reasons),
            notes=list(draft.notes),
            created_at=draft.created_at,
            solved_at=draft.solved_at,
            user_id=draft.user_id,
            festival_id=draft.festival_id,
        )

    @strawberry.field
    async def festival(self, info: Info) -> Festival:
        return await _festival(info, self.festival_id)

    @strawberry.field(
        description=(
            "Against the current Active Schedule; null unless READY. "
            "Computed only when asked for."
        )
    )
    async def diff(self, info: Info) -> DraftDiff | None:
        ctx = info.context
        try:
            value = await ctx.run(
                ctx.deps.planner.draft_diff, self.user_id, d.DraftId(self.id)
            )
        except NotFoundError:
            return None
        return None if value is None else DraftDiff.from_domain(value)


@strawberry.type(
    description=(
        "An accepted Schedule. The one with the highest number is the Active "
        "Schedule; the others form the history."
    )
)
class Schedule(relay.Node):
    id: relay.NodeID[str]
    number: int
    score: float
    change_set: list[ChangeSetItem] = strawberry.field(
        description="The Change Set whose acceptance produced this Schedule."
    )
    accepted_at: datetime.datetime
    screening_ids: strawberry.Private[frozenset[p.ScreeningId]]
    festival_id: strawberry.Private[f.FestivalId]

    @classmethod
    def from_domain(cls, value: d.Schedule) -> Self:
        return cls(
            id=value.id,
            number=value.number,
            score=value.score,
            change_set=_change_set(value.change_set),
            accepted_at=value.accepted_at,
            screening_ids=value.screening_ids,
            festival_id=value.festival_id,
        )

    @strawberry.field
    async def festival(self, info: Info) -> Festival:
        return await _festival(info, self.festival_id)

    @strawberry.field(description="By start time.")
    async def screenings(self, info: Info) -> list[Screening]:
        return await _screenings(info, self.screening_ids)


# --- Inputs and Preferences ------------------------------------------------


@strawberry.type(description="Minutes to arrive before a Screening at a Venue.")
class VenueBuffer:
    venue_id: strawberry.Private[p.VenueId]
    minutes: int

    @strawberry.field
    async def venue(self, info: Info) -> VenueType:
        return await _venue(info, self.venue_id)


@strawberry.type
class ProgrammeEntryWeight(_OnProgrammeEntry):
    weight: float


@strawberry.type
class ScreeningWeight(_OnScreening):
    weight: float


@strawberry.type
class YearWeight:
    year: int
    weight: float


@strawberry.type(description="The User would rather watch `preferred` than `other`.")
class Comparison(_Pair):
    pass


@strawberry.type(description="A User's settings that shape their Schedules.")
class Preferences:
    buffer_minutes: int = strawberry.field(
        description="Minutes to arrive before a Screening, unless its Venue has its own."
    )
    venue_buffers: list[VenueBuffer] = strawberry.field(description="By Venue id.")
    start_date: datetime.date | None
    end_date: datetime.date | None
    programme_entry_weights: list[ProgrammeEntryWeight] = strawberry.field(
        description="By Programme Entry id."
    )
    screening_weights: list[ScreeningWeight] = strawberry.field(
        description="By Screening id."
    )
    year_weights: list[YearWeight] = strawberry.field(description="By year.")
    event_weight: float
    attend_events: bool
    transport_mode: str | None
    comparison_weight: float = strawberry.field(
        description="How strongly Comparisons shift Programme Entry weights."
    )
    comparisons: list[Comparison]

    @classmethod
    def from_domain(cls, value: pl.Preferences) -> Self:
        return cls(
            buffer_minutes=value.buffer_minutes,
            venue_buffers=[
                VenueBuffer(venue_id=k, minutes=v)
                for k, v in sorted(value.venue_buffer_minutes.items())
            ],
            start_date=value.start_date,
            end_date=value.end_date,
            programme_entry_weights=[
                ProgrammeEntryWeight(programme_entry_id=k, weight=v)
                for k, v in sorted(value.programme_entry_weights.items())
            ],
            screening_weights=[
                ScreeningWeight(screening_id=k, weight=v)
                for k, v in sorted(value.screening_weights.items())
            ],
            year_weights=[
                YearWeight(year=k, weight=v)
                for k, v in sorted(value.year_weights.items())
            ],
            event_weight=value.event_weight,
            attend_events=value.attend_events,
            transport_mode=value.transport_mode,
            comparison_weight=value.comparison_weight,
            comparisons=[
                Comparison(preferred_id=c.preferred, other_id=c.other)
                for c in value.comparisons
            ],
        )


@strawberry.type(
    description="A User's accepted commitments, Excluded and Preferences for a Festival."
)
class PlanningInputs:
    preferences: Preferences
    screening_commitment_ids: strawberry.Private[frozenset[p.ScreeningId]]
    film_commitment_ids: strawberry.Private[frozenset[p.ProgrammeEntryId]]
    excluded_screening_ids: strawberry.Private[frozenset[p.ScreeningId]]
    excluded_programme_entry_ids: strawberry.Private[frozenset[p.ProgrammeEntryId]]

    @classmethod
    def from_domain(cls, value: pl.PlanningInputs) -> Self:
        return cls(
            preferences=Preferences.from_domain(value.preferences),
            screening_commitment_ids=value.screening_commitments,
            film_commitment_ids=value.film_commitments,
            excluded_screening_ids=value.excluded_screenings,
            excluded_programme_entry_ids=value.excluded_programme_entries,
        )

    @strawberry.field(description="By start time.")
    async def screening_commitments(self, info: Info) -> list[Screening]:
        return await _screenings(info, self.screening_commitment_ids)

    @strawberry.field(description="By title.")
    async def film_commitments(self, info: Info) -> list[ProgrammeEntry]:
        return await _entries(info, self.film_commitment_ids)

    @strawberry.field(description="By start time.")
    async def excluded_screenings(self, info: Info) -> list[Screening]:
        return await _screenings(info, self.excluded_screening_ids)

    @strawberry.field(description="By title.")
    async def excluded_programme_entries(self, info: Info) -> list[ProgrammeEntry]:
        return await _entries(info, self.excluded_programme_entry_ids)


# --- Flags, suggestions, Tickets --------------------------------------------


@strawberry.type(description="Something in a User's planning that needs attention.")
class Flag:
    kind: FlagKind
    message: str
    screening: Screening | None = strawberry.field(
        description="The Screening concerned, if the Flag is about one."
    )
    programme_entry: ProgrammeEntry | None = strawberry.field(
        description="The Programme Entry concerned, if not a Screening."
    )


@strawberry.type(description="Two Programme Entries whose Screenings competed.")
class ComparisonSuggestion:
    weight_gap: float
    scheduled_id: strawberry.Private[p.ProgrammeEntryId]
    other_id: strawberry.Private[p.ProgrammeEntryId]

    @classmethod
    def from_domain(cls, value: ins.ComparisonSuggestion) -> Self:
        return cls(
            weight_gap=value.weight_gap,
            scheduled_id=value.scheduled,
            other_id=value.other,
        )

    @strawberry.field(description="The one that won a place in the Schedule.")
    async def scheduled(self, info: Info) -> ProgrammeEntry:
        return await _entry(info, self.scheduled_id)

    @strawberry.field
    async def other(self, info: Info) -> ProgrammeEntry:
        return await _entry(info, self.other_id)


@strawberry.type(description="A User's record that they hold a ticket.")
class Ticket(_OnScreening):
    exchangeable: bool
    refundable: bool

    @classmethod
    def from_domain(cls, value: pl.Ticket) -> Self:
        return cls(
            screening_id=value.screening_id,
            exchangeable=value.exchangeable,
            refundable=value.refundable,
        )


# --- The Viewer and their planning for a Festival --------------------------


@strawberry.type(description="A signed-in User's planning for one Festival.")
class FestivalPlanning:
    festival: Festival
    user_id: strawberry.Private[UserId]

    @strawberry.field
    async def active_schedule(self, info: Info) -> Schedule | None:
        ctx = info.context
        value = await ctx.run(
            ctx.deps.planner.active_schedule, self.user_id, self.festival.slug
        )
        return None if value is None else Schedule.from_domain(value)

    @relay.connection(relay.ListConnection[Schedule], description="Oldest first.")
    async def schedules(self, info: Info) -> Iterable[Schedule]:
        ctx = info.context
        values = await ctx.run(
            ctx.deps.planner.schedules, self.user_id, self.festival.slug
        )
        return [Schedule.from_domain(s) for s in values]

    @strawberry.field(description="Oldest first.")
    async def drafts(self, info: Info) -> list[Draft]:
        ctx = info.context
        views = await ctx.run(ctx.deps.planner.drafts, self.user_id, self.festival.slug)
        return [Draft.from_view(v) for v in views]

    @strawberry.field
    async def inputs(self, info: Info) -> PlanningInputs:
        ctx = info.context
        value = await ctx.run(ctx.deps.planner.inputs, self.user_id, self.festival.slug)
        return PlanningInputs.from_domain(value)

    @strawberry.field
    async def flags(self, info: Info) -> list[Flag]:
        ctx = info.context
        planner = ctx.deps.planner
        flags = await ctx.run(planner.flags, self.user_id, self.festival.slug)
        if not flags:
            return []
        inputs = await ctx.run(planner.inputs, self.user_id, self.festival.slug)

        # Only a withdrawn Film Commitment is about a Programme Entry; every
        # other Flag is about a Screening.
        about_entry = [
            flag.kind is ins.FlagKind.WITHDRAWN_COMMITMENT
            and flag.target_id in inputs.film_commitments
            for flag in flags
        ]
        screening_ids = [
            p.ScreeningId(flag.target_id)
            for flag, entry in zip(flags, about_entry, strict=True)
            if not entry
        ]
        entry_ids = [
            p.ProgrammeEntryId(flag.target_id)
            for flag, entry in zip(flags, about_entry, strict=True)
            if entry
        ]
        # One DataLoader batch per kind, instead of one load per Flag.
        screenings, entries = await asyncio.gather(
            ctx.loaders.screening.load_many(screening_ids),
            ctx.loaders.programme_entry.load_many(entry_ids),
        )
        screening_by_id = dict(zip(screening_ids, screenings, strict=True))
        entry_by_id = dict(zip(entry_ids, entries, strict=True))

        found: list[Flag] = []
        for flag, entry in zip(flags, about_entry, strict=True):
            if entry:
                entry_id = p.ProgrammeEntryId(flag.target_id)
                entry_value = entry_by_id[entry_id]
                if entry_value is None:
                    raise LookupError(f"Programme Entry {entry_id!r} is missing")
                screening = None
                programme_entry = ProgrammeEntry.from_domain(entry_value)
            else:
                screening_id = p.ScreeningId(flag.target_id)
                screening_value = screening_by_id[screening_id]
                if screening_value is None:
                    raise LookupError(f"Screening {screening_id!r} is missing")
                screening = Screening.from_domain(screening_value)
                programme_entry = None
            found.append(
                Flag(
                    kind=FlagKind(flag.kind.value),
                    message=flag.message,
                    screening=screening,
                    programme_entry=programme_entry,
                )
            )
        return found

    @strawberry.field(
        description=(
            "Pairs that competed in the latest READY Draft, else the Active "
            "Schedule, and are not compared yet; closest weights first."
        )
    )
    async def comparison_suggestions(
        self, info: Info, limit: int = 10
    ) -> list[ComparisonSuggestion]:
        ctx = info.context
        values = await ctx.run(
            ctx.deps.planner.suggest_comparisons,
            self.user_id,
            self.festival.slug,
            limit,
        )
        return [ComparisonSuggestion.from_domain(s) for s in values]


@strawberry.type(description="The signed-in User.")
class Viewer:
    issuer: str
    subject: str
    user_id: strawberry.Private[UserId]

    @strawberry.field(description="By start time of the Screening.")
    async def tickets(self, info: Info) -> list[Ticket]:
        ctx = info.context
        tickets = await ctx.run(ctx.deps.planner.tickets, self.user_id)
        wanted = [t.screening_id for t in tickets]
        found = await ctx.loaders.screening.load_many(wanted)
        start_of = {s.id: s.start_time for s in found if s is not None}
        # Screenings are never deleted; a Ticket on an unknown one is dropped,
        # as `seenFilms` drops unknown Films.
        known = [t for t in tickets if t.screening_id in start_of]
        known.sort(key=lambda t: (start_of[t.screening_id], t.screening_id))
        return [Ticket.from_domain(t) for t in known]

    @strawberry.field(
        description="Marked by hand, or from an ended Screening in an Active Schedule; by title."
    )
    async def seen_films(self, info: Info) -> list[Film]:
        ctx = info.context
        ids = sorted(await ctx.run(ctx.deps.planner.seen_films, self.user_id))
        found = await ctx.loaders.film.load_many(ids)
        films = sorted(
            (film for film in found if film is not None),
            key=lambda film: (p.title_key(film.title), film.id),
        )
        return [Film.from_domain(film) for film in films]

    @strawberry.field(description="Null if the id is not a known Festival's.")
    async def planning(
        self, info: Info, festival_id: strawberry.ID
    ) -> FestivalPlanning | None:
        domain_id = decode(festival_id, "Festival")
        if domain_id is None:
            return None
        value = await info.context.loaders.festival.load(f.FestivalId(domain_id))
        if value is None:
            return None
        return FestivalPlanning(
            festival=Festival.from_domain(value), user_id=self.user_id
        )


# --- Nodes -------------------------------------------------------------------


async def draft_node(info: Info, domain_id: str) -> Draft | None:
    ctx = info.context
    if ctx.viewer is None:
        return None
    try:
        view = await ctx.run(
            ctx.deps.planner.draft, ctx.viewer.id, d.DraftId(domain_id)
        )
    except NotFoundError:
        return None
    return Draft.from_view(view)


async def schedule_node(info: Info, domain_id: str) -> Schedule | None:
    ctx = info.context
    if ctx.viewer is None:
        return None
    try:
        value = await ctx.run(
            ctx.deps.planner.schedule, ctx.viewer.id, d.ScheduleId(domain_id)
        )
    except NotFoundError:
        return None
    return Schedule.from_domain(value)


PLANNING_NODES: Mapping[str, NodeResolver] = {
    "Draft": draft_node,
    "Schedule": schedule_node,
}
"""Node resolvers for planning, by GraphQL type name; owner only."""
