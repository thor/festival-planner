"""Typed errors that mutations return in their result unions."""

import enum
from typing import Self

import strawberry

from ..domain import change_sets as cs


@strawberry.type(description="The mutation needs a signed-in User.")
class NotSignedIn:
    message: str = "Sign in to do this"


@strawberry.type(
    description="An id is garbage, of the wrong type, unknown or not yours."
)
class NotFound:
    message: str


@strawberry.enum(description="What is wrong with a Change Set.")
class ChangeSetProblemCode(enum.Enum):
    """The domain's `ProblemCode`, mapped by value."""

    UNKNOWN_ID = "UNKNOWN_ID"
    CONFLICTING_ITEMS = "CONFLICTING_ITEMS"
    NO_OP = "NO_OP"
    COMMITTED_AND_EXCLUDED = "COMMITTED_AND_EXCLUDED"
    TWO_SCREENING_COMMITMENTS = "TWO_SCREENING_COMMITMENTS"
    INVALID_ITEM = "INVALID_ITEM"


@strawberry.type(description="One thing wrong with a Change Set.")
class ChangeSetProblem:
    code: ChangeSetProblemCode
    items: list[int] = strawberry.field(
        description="Indexes of the Change Set items involved, if any."
    )
    message: str

    @classmethod
    def from_domain(cls, value: cs.ChangeSetProblem) -> Self:
        return cls(
            code=ChangeSetProblemCode(value.code.value),
            items=list(value.items),
            message=value.message,
        )


@strawberry.type(description="The Change Set cannot be applied.")
class InvalidChangeSet:
    problems: list[ChangeSetProblem]

    @classmethod
    def from_error(cls, error: cs.InvalidChangeSetError) -> Self:
        return cls(problems=[ChangeSetProblem.from_domain(p) for p in error.problems])


@strawberry.type(description="The Draft is not READY, or is Stale; re-solve it first.")
class DraftNotAcceptable:
    message: str


@strawberry.type(description="The Draft is still solving; wait for it first.")
class DraftStillSolving:
    message: str
