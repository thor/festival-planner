"""The GraphQL schema."""

import strawberry

from .context import Info


@strawberry.type(description="The signed-in User.")
class Viewer:
    issuer: str
    subject: str


@strawberry.type
class Query:
    @strawberry.field(description="The signed-in User; null when signed out.")
    def viewer(self, info: Info) -> Viewer | None:
        user = info.context.viewer
        if user is None:
            return None
        return Viewer(issuer=user.issuer, subject=user.subject)


schema = strawberry.Schema(query=Query)
