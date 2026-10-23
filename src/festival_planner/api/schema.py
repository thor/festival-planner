"""The GraphQL schema."""

import asyncio
from collections.abc import Mapping

import strawberry
from graphql.error import GraphQLError
from strawberry import relay
from strawberry.extensions import MaskErrors

from .context import Info
from .ids import decode_any
from .mutations import Mutation
from .planning_types import PLANNING_NODES, Viewer
from .programme_types import PROGRAMME_NODES, NodeResolver, ProgrammeQuery

assert PROGRAMME_NODES.keys().isdisjoint(PLANNING_NODES), "a Node type is twice"
NODES: Mapping[str, NodeResolver] = {**PROGRAMME_NODES, **PLANNING_NODES}
"""How `node` and `nodes` find each Node type, by GraphQL type name."""


async def _node(info: Info, global_id: str) -> relay.Node | None:
    decoded = decode_any(global_id)
    if decoded is None:
        return None
    type_name, domain_id = decoded
    resolver = NODES.get(type_name)
    return None if resolver is None else await resolver(info, domain_id)


@strawberry.type
class Query(ProgrammeQuery):
    @strawberry.field(
        description="The node with this id; null if the id is garbage or unknown."
    )
    async def node(self, info: Info, id: strawberry.ID) -> relay.Node | None:
        return await _node(info, id)

    @strawberry.field(description="Each id's node, or null, in the order given.")
    async def nodes(
        self, info: Info, ids: list[strawberry.ID]
    ) -> list[relay.Node | None]:
        return list(await asyncio.gather(*(_node(info, i) for i in ids)))

    @strawberry.field(description="The signed-in User; null when signed out.")
    def viewer(self, info: Info) -> Viewer | None:
        user = info.context.viewer
        if user is None:
            return None
        return Viewer(issuer=user.issuer, subject=user.subject, user_id=user.id)


def _should_mask_error(error: GraphQLError) -> bool:
    """Mask only an unexpected exception from a resolver.

    `error.original_error` is the Python exception a resolver raised (e.g.
    `LookupError`, a SQLAlchemy error); its message can leak internals and
    is not meant for clients. A GraphQL-level error, such as the `@oneOf`
    coercion error or an unknown field, has no `original_error`: it is
    already a client-facing message and stays visible. The typed error
    unions (`NotFound`, `NotSignedIn`, ...) are plain return values, never
    exceptions, so they are untouched either way.
    """
    return error.original_error is not None


schema = strawberry.Schema(
    query=Query,
    mutation=Mutation,
    # A factory, not an instance: Strawberry builds one MaskErrors per
    # request from it, as it does for every extension.
    extensions=[lambda: MaskErrors(should_mask_error=_should_mask_error)],
)
