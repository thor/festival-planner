"""The GraphQL schema."""

import asyncio
from collections.abc import Mapping

import strawberry
from strawberry import relay

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


schema = strawberry.Schema(query=Query, mutation=Mutation)
