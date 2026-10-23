"""Mutations: each takes one `input` and returns a success type or a typed error.

Every mutation needs a signed-in viewer, else it returns `NotSignedIn`. An id
that does not decode to the expected type is `NotFound`.
"""

from typing import Annotated

import strawberry

from ..domain import drafts as d
from ..domain import festival as f
from ..domain import planning as pl
from ..domain import programme as p
from ..domain.change_sets import InvalidChangeSetError
from ..domain.planner import (
    DraftNotAcceptableError,
    DraftStillSolvingError,
    NotFoundError,
)
from .context import Info
from .errors import (
    DraftNotAcceptable,
    DraftStillSolving,
    InvalidChangeSet,
    NotFound,
    NotSignedIn,
)
from .ids import decode, encode
from .inputs import (
    CreateDraftInput,
    DraftInput,
    FilmInput,
    ScreeningInput,
    to_change_set,
)
from .planning_types import Draft, Schedule, Ticket
from .programme_types import Film, Screening


@strawberry.type
class DraftResult:
    draft: Draft


@strawberry.type
class ScheduleResult:
    schedule: Schedule


@strawberry.type(description="The Draft is gone.")
class Discarded:
    draft_id: strawberry.ID


@strawberry.type
class TicketResult:
    ticket: Ticket


@strawberry.type
class ScreeningResult:
    screening: Screening


@strawberry.type
class FilmResult:
    film: Film


CreateDraftResult = Annotated[
    DraftResult | InvalidChangeSet | NotFound | NotSignedIn,
    strawberry.union("CreateDraftResult"),
]
ResolveDraftResult = Annotated[
    DraftResult | InvalidChangeSet | DraftStillSolving | NotFound | NotSignedIn,
    strawberry.union("ResolveDraftResult"),
]
AcceptDraftResult = Annotated[
    ScheduleResult | DraftNotAcceptable | NotFound | NotSignedIn,
    strawberry.union("AcceptDraftResult"),
]
DiscardDraftResult = Annotated[
    Discarded | NotFound | NotSignedIn,
    strawberry.union("DiscardDraftResult"),
]
RecordTicketResult = Annotated[
    TicketResult | NotFound | NotSignedIn,
    strawberry.union("RecordTicketResult"),
]
ScreeningMutationResult = Annotated[
    ScreeningResult | NotFound | NotSignedIn,
    strawberry.union("ScreeningMutationResult"),
]
FilmMutationResult = Annotated[
    FilmResult | NotFound | NotSignedIn,
    strawberry.union("FilmMutationResult"),
]


@strawberry.input(description="A Screening to get a Ticket for.")
class RecordTicketInput:
    screening_id: strawberry.ID
    exchangeable: bool = False
    refundable: bool = False


def _draft_id(global_id: strawberry.ID) -> d.DraftId | None:
    domain_id = decode(global_id, "Draft")
    return None if domain_id is None else d.DraftId(domain_id)


def _no_draft(global_id: strawberry.ID) -> NotFound:
    return NotFound(message=f"No Draft {global_id!r}")


def _screening_id(global_id: strawberry.ID) -> p.ScreeningId | None:
    domain_id = decode(global_id, "Screening")
    return None if domain_id is None else p.ScreeningId(domain_id)


def _no_screening(global_id: strawberry.ID) -> NotFound:
    return NotFound(message=f"No Screening {global_id!r}")


def _film_id(global_id: strawberry.ID) -> p.FilmId | None:
    domain_id = decode(global_id, "Film")
    return None if domain_id is None else p.FilmId(domain_id)


def _no_film(global_id: strawberry.ID) -> NotFound:
    return NotFound(message=f"No Film {global_id!r}")


@strawberry.type
class Mutation:
    @strawberry.mutation(
        description=(
            "A Draft of a Festival's Schedule with this Change Set, solved "
            "if that is quick; else poll it with `node`."
        )
    )
    async def create_draft(
        self, info: Info, input: CreateDraftInput
    ) -> CreateDraftResult:
        ctx = info.context
        if ctx.viewer is None:
            return NotSignedIn()
        domain_id = decode(input.festival_id, "Festival")
        festival = (
            None
            if domain_id is None
            else await ctx.loaders.festival.load(f.FestivalId(domain_id))
        )
        if festival is None:
            return NotFound(message=f"No Festival {input.festival_id!r}")
        try:
            change_set = to_change_set(input.change_set)
            view = await ctx.run(
                ctx.deps.planner.create_draft, ctx.viewer.id, festival.slug, change_set
            )
        except InvalidChangeSetError as e:
            return InvalidChangeSet.from_error(e)
        except NotFoundError as e:
            return NotFound(message=str(e))
        return DraftResult(draft=Draft.from_view(view))

    @strawberry.mutation(
        description=(
            "Solve a Draft again against the current Active Schedule and inputs."
        )
    )
    async def resolve_draft(self, info: Info, input: DraftInput) -> ResolveDraftResult:
        ctx = info.context
        if ctx.viewer is None:
            return NotSignedIn()
        if (draft_id := _draft_id(input.draft_id)) is None:
            return _no_draft(input.draft_id)
        try:
            view = await ctx.run(ctx.deps.planner.resolve, ctx.viewer.id, draft_id)
        except InvalidChangeSetError as e:
            return InvalidChangeSet.from_error(e)
        except DraftStillSolvingError as e:
            return DraftStillSolving(message=str(e))
        except NotFoundError:
            return _no_draft(input.draft_id)
        return DraftResult(draft=Draft.from_view(view))

    @strawberry.mutation(
        description=(
            "Make a READY, non-Stale Draft's Schedule the Active Schedule and "
            "apply its Change Set. The Draft is gone after."
        )
    )
    async def accept_draft(self, info: Info, input: DraftInput) -> AcceptDraftResult:
        ctx = info.context
        if ctx.viewer is None:
            return NotSignedIn()
        if (draft_id := _draft_id(input.draft_id)) is None:
            return _no_draft(input.draft_id)
        try:
            schedule = await ctx.run(ctx.deps.planner.accept, ctx.viewer.id, draft_id)
        except DraftNotAcceptableError as e:
            return DraftNotAcceptable(message=str(e))
        except NotFoundError:
            return _no_draft(input.draft_id)
        return ScheduleResult(schedule=Schedule.from_domain(schedule))

    @strawberry.mutation(description="Throw a Draft away.")
    async def discard_draft(self, info: Info, input: DraftInput) -> DiscardDraftResult:
        ctx = info.context
        if ctx.viewer is None:
            return NotSignedIn()
        if (draft_id := _draft_id(input.draft_id)) is None:
            return _no_draft(input.draft_id)
        try:
            await ctx.run(ctx.deps.planner.discard, ctx.viewer.id, draft_id)
        except NotFoundError:
            return _no_draft(input.draft_id)
        return Discarded(draft_id=strawberry.ID(encode("Draft", draft_id)))

    @strawberry.mutation(
        description="Record that the User holds a Ticket for a Screening."
    )
    async def record_ticket(
        self, info: Info, input: RecordTicketInput
    ) -> RecordTicketResult:
        ctx = info.context
        if ctx.viewer is None:
            return NotSignedIn()
        if (screening_id := _screening_id(input.screening_id)) is None:
            return _no_screening(input.screening_id)
        ticket = pl.Ticket(
            screening_id=screening_id,
            exchangeable=input.exchangeable,
            refundable=input.refundable,
        )
        try:
            await ctx.run(ctx.deps.planner.record_ticket, ctx.viewer.id, ticket)
        except NotFoundError:
            return _no_screening(input.screening_id)
        return TicketResult(ticket=Ticket.from_domain(ticket))

    @strawberry.mutation(description="Give up a Ticket for a Screening.")
    async def remove_ticket(
        self, info: Info, input: ScreeningInput
    ) -> ScreeningMutationResult:
        ctx = info.context
        if ctx.viewer is None:
            return NotSignedIn()
        if (screening_id := _screening_id(input.screening_id)) is None:
            return _no_screening(input.screening_id)
        value = await ctx.loaders.screening.load(screening_id)
        if value is None:
            return _no_screening(input.screening_id)
        await ctx.run(ctx.deps.planner.remove_ticket, ctx.viewer.id, screening_id)
        return ScreeningResult(screening=Screening.from_domain(value))

    @strawberry.mutation(description="Mark a Film Seen by hand.")
    async def mark_seen(self, info: Info, input: FilmInput) -> FilmMutationResult:
        ctx = info.context
        if ctx.viewer is None:
            return NotSignedIn()
        if (film_id := _film_id(input.film_id)) is None:
            return _no_film(input.film_id)
        try:
            await ctx.run(ctx.deps.planner.mark_seen, ctx.viewer.id, film_id)
        except NotFoundError:
            return _no_film(input.film_id)
        value = await ctx.loaders.film.load(film_id)
        if value is None:
            raise LookupError(f"Film {film_id!r} is missing")
        return FilmResult(film=Film.from_domain(value))

    @strawberry.mutation(description="Undo marking a Film Seen by hand.")
    async def unmark_seen(self, info: Info, input: FilmInput) -> FilmMutationResult:
        ctx = info.context
        if ctx.viewer is None:
            return NotSignedIn()
        if (film_id := _film_id(input.film_id)) is None:
            return _no_film(input.film_id)
        value = await ctx.loaders.film.load(film_id)
        if value is None:
            return _no_film(input.film_id)
        await ctx.run(ctx.deps.planner.unmark_seen, ctx.viewer.id, film_id)
        return FilmResult(film=Film.from_domain(value))

    @strawberry.mutation(
        description=('"I did not go": the Screening no longer makes its Film Seen.')
    )
    async def dismiss_inferred_seen(
        self, info: Info, input: ScreeningInput
    ) -> ScreeningMutationResult:
        ctx = info.context
        if ctx.viewer is None:
            return NotSignedIn()
        if (screening_id := _screening_id(input.screening_id)) is None:
            return _no_screening(input.screening_id)
        try:
            await ctx.run(
                ctx.deps.planner.dismiss_inferred_seen, ctx.viewer.id, screening_id
            )
        except NotFoundError:
            return _no_screening(input.screening_id)
        value = await ctx.loaders.screening.load(screening_id)
        if value is None:
            raise LookupError(f"Screening {screening_id!r} is missing")
        return ScreeningResult(screening=Screening.from_domain(value))

    @strawberry.mutation(
        description="Undo dismissing a Screening's inferred Seen Film."
    )
    async def restore_inferred_seen(
        self, info: Info, input: ScreeningInput
    ) -> ScreeningMutationResult:
        ctx = info.context
        if ctx.viewer is None:
            return NotSignedIn()
        if (screening_id := _screening_id(input.screening_id)) is None:
            return _no_screening(input.screening_id)
        value = await ctx.loaders.screening.load(screening_id)
        if value is None:
            return _no_screening(input.screening_id)
        await ctx.run(
            ctx.deps.planner.restore_inferred_seen, ctx.viewer.id, screening_id
        )
        return ScreeningResult(screening=Screening.from_domain(value))
