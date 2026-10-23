from festival_planner.domain.users import LOCAL_ISSUER, user_for

from .fakes import InMemoryUnitOfWork, sequential_ids


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
