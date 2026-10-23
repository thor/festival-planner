"""The per-request GraphQL context."""

from __future__ import annotations

import functools
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import anyio.to_thread
import strawberry

from ..domain.users import User
from .loaders import Loaders

if TYPE_CHECKING:
    from .app import ApiDependencies


@dataclass
class Context:
    deps: ApiDependencies
    viewer: User | None
    loaders: Loaders = field(init=False)
    """The DataLoaders of this request, one per relation."""

    def __post_init__(self) -> None:
        self.loaders = Loaders(self.deps.programme, self.run)

    async def run[**P, T](
        self, fn: Callable[P, T], *args: P.args, **kwargs: P.kwargs
    ) -> T:
        """`fn(*args, **kwargs)` on a worker thread, off the event loop."""
        return await anyio.to_thread.run_sync(functools.partial(fn, *args, **kwargs))


Info = strawberry.Info[Context, None]
