"""The per-request GraphQL context."""

from __future__ import annotations

import functools
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import anyio.to_thread
import strawberry

from ..domain.users import User

if TYPE_CHECKING:
    from .app import ApiDependencies


@dataclass
class Loaders:
    """The DataLoaders of one request, one per relation."""


@dataclass
class Context:
    deps: ApiDependencies
    viewer: User | None
    loaders: Loaders = field(default_factory=Loaders)

    async def run[**P, T](
        self, fn: Callable[P, T], *args: P.args, **kwargs: P.kwargs
    ) -> T:
        """`fn(*args, **kwargs)` on a worker thread, off the event loop."""
        return await anyio.to_thread.run_sync(functools.partial(fn, *args, **kwargs))


Info = strawberry.Info[Context, None]
