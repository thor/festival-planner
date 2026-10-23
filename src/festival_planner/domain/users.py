"""Users, keyed on the (issuer, subject) of their identity tokens (ADR-0003)."""

from collections.abc import Callable
from typing import TYPE_CHECKING, Protocol

from .ingestion import new_id as _new_id
from .values import Value

if TYPE_CHECKING:
    from .planning_ports import PlanningUnitOfWork

UserId = str

LOCAL_ISSUER = "local"
"""The issuer the CLI acts as, with the operating-system user as subject."""


class User(Value):
    """A person who plans their attendance at Festivals."""

    id: UserId
    issuer: str
    subject: str


class UserRepository(Protocol):
    def by_identity(self, issuer: str, subject: str) -> User | None: ...
    def save(self, user: User) -> None: ...


def user_for(
    uow: "PlanningUnitOfWork",
    issuer: str,
    subject: str,
    *,
    new_id: Callable[[], str] = _new_id,
) -> User:
    """The User with this identity, created on first sight."""
    with uow:
        if (user := uow.users.by_identity(issuer, subject)) is None:
            user = User(id=new_id(), issuer=issuer, subject=subject)
            uow.users.save(user)
            uow.commit()
    return user
