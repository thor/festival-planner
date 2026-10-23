"""The Starlette app serving the GraphQL API, and bearer sign-in."""

import contextlib
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass

import anyio.to_thread
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route
from starlette.types import Receive, Scope, Send
from starlette.websockets import WebSocket
from strawberry.asgi import GraphQL

from ..domain.identity import Identity, InvalidTokenError, TokenVerifier
from ..domain.planner import Planner
from ..domain.programme_queries import ProgrammeQueries
from ..domain.users import User
from .context import Context
from .schema import schema


@dataclass(frozen=True)
class ApiDependencies:
    planner: Planner
    programme: ProgrammeQueries
    verifier: TokenVerifier
    users: Callable[[Identity], User]
    """Signs in: the User for an Identity, created on first sight."""


def _nothing() -> None:
    pass


def create_app(
    deps: ApiDependencies,
    *,
    on_startup: Callable[[], None] = _nothing,
    on_shutdown: Callable[[], None] = _nothing,
) -> Starlette:
    """GraphQL at `/graphql`: GET serves GraphiQL, POST runs queries."""

    @contextlib.asynccontextmanager
    async def lifespan(_app: Starlette) -> AsyncIterator[None]:
        try:
            await anyio.to_thread.run_sync(on_startup)
            yield
        finally:
            await anyio.to_thread.run_sync(on_shutdown)

    return Starlette(
        routes=[Route("/graphql", _GraphQL(deps))],
        lifespan=lifespan,
    )


class _InvalidToken(Exception):
    pass


_UNAUTHORIZED_HEADERS = {"WWW-Authenticate": 'Bearer error="invalid_token"'}


class _GraphQL(GraphQL[Context, None]):
    """Strawberry's ASGI app, signing in from the bearer token first.

    No `Authorization` header means signed out. Anything other than a valid
    `Bearer <token>` is a 401, before any resolver runs.
    """

    def __init__(self, deps: ApiDependencies) -> None:
        super().__init__(schema)
        self._deps = deps

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await super().__call__(scope, receive, send)
            return
        try:
            await super().__call__(scope, receive, send)
        except _InvalidToken:
            response = JSONResponse(
                {"error": "invalid_token"},
                status_code=401,
                headers=_UNAUTHORIZED_HEADERS,
            )
            await response(scope, receive, send)

    async def get_context(
        self, request: Request | WebSocket, response: Response | WebSocket
    ) -> Context:
        return Context(deps=self._deps, viewer=await self._sign_in(request))

    async def _sign_in(self, request: Request | WebSocket) -> User | None:
        authorization = request.headers.get("Authorization")
        if authorization is None:
            return None
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token.strip():
            raise _InvalidToken
        try:
            identity = await anyio.to_thread.run_sync(
                self._deps.verifier.verify, token.strip()
            )
        except InvalidTokenError:
            raise _InvalidToken from None
        return await anyio.to_thread.run_sync(self._deps.users, identity)
