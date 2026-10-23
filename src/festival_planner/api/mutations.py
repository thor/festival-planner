"""Mutations: each takes one `input` and returns a success type or a typed error.

Every mutation needs a signed-in viewer, else it returns `NotSignedIn`. An id
that does not decode to the expected type is `NotFound`.
"""

from typing import Annotated

import strawberry

from ..domain import drafts as d
from ..domain import festival as f
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
from .inputs import CreateDraftInput, DraftInput, to_change_set
from .planning_types import Draft, Schedule


@strawberry.type
class DraftResult:
    draft: Draft


@strawberry.type
class ScheduleResult:
    schedule: Schedule


@strawberry.type(description="The Draft is gone.")
class Discarded:
    draft_id: strawberry.ID


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


def _draft_id(global_id: strawberry.ID) -> d.DraftId | None:
    domain_id = decode(global_id, "Draft")
    return None if domain_id is None else d.DraftId(domain_id)


def _no_draft(global_id: strawberry.ID) -> NotFound:
    return NotFound(message=f"No Draft {global_id!r}")


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
