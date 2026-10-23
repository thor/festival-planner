from festival_planner.domain.users import LOCAL_ISSUER, User, user_for

from .fakes import InMemoryUnitOfWork, concurrently, sequential_ids


def test_user_for_creates_a_user_once():
    uow = InMemoryUnitOfWork()
    ids = sequential_ids()
    first = user_for(uow, LOCAL_ISSUER, "thor", new_id=ids)
    again = user_for(uow, LOCAL_ISSUER, "thor", new_id=ids)
    assert first == again
    assert (first.issuer, first.subject) == ("local", "thor")


def test_users_are_keyed_on_issuer_and_subject():
    uow = InMemoryUnitOfWork()
    ids = sequential_ids()
    assert user_for(uow, "local", "thor", new_id=ids) != user_for(
        uow, "https://accounts.example", "thor", new_id=ids
    )


def test_user_for_returns_the_user_a_concurrent_first_sight_created():
    uow = InMemoryUnitOfWork()
    winner = User(id="winner", issuer=LOCAL_ISSUER, subject="thor")
    uow.hooks["users.save"] = concurrently(
        uow, lambda state: state.users.__setitem__(winner.id, winner)
    )
    assert user_for(uow, LOCAL_ISSUER, "thor", new_id=sequential_ids()) == winner
