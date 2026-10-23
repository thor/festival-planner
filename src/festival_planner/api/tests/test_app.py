import pytest
from starlette.testclient import TestClient

from festival_planner.api.app import create_app
from festival_planner.api.server import build_server
from festival_planner.api.tests.support import (
    ALICE,
    FakeVerifier,
    api_client,
    dependencies,
    gql,
)
from festival_planner.domain.tests.fakes import InMemoryUnitOfWork

VIEWER = "{ viewer { issuer subject } }"


def test_signed_out_viewer_is_null():
    with api_client(InMemoryUnitOfWork()) as c:
        assert gql(c, "{ viewer { subject } }") == {"viewer": None}


def test_a_valid_token_signs_in_and_creates_the_user():
    uow = InMemoryUnitOfWork()
    with api_client(uow) as c:
        assert gql(c, VIEWER, token=ALICE) == {
            "viewer": {"issuer": "local", "subject": "alice"}
        }
    with uow:
        assert uow.users.by_identity("local", "alice") is not None


def _post(client: TestClient, authorization: str):
    return client.post(
        "/graphql",
        json={"query": VIEWER},
        headers={"Authorization": authorization},
    )


def _assert_invalid_token(response) -> None:
    assert response.status_code == 401
    assert response.json() == {"error": "invalid_token"}
    assert response.headers["WWW-Authenticate"] == 'Bearer error="invalid_token"'


def test_an_invalid_token_is_401():
    uow = InMemoryUnitOfWork()
    with api_client(uow) as c:
        _assert_invalid_token(_post(c, "Bearer nope"))
    assert uow.stored.users == {}


def test_a_non_bearer_authorization_is_401():
    uow = InMemoryUnitOfWork()
    deps = dependencies(uow)
    with TestClient(create_app(deps)) as c:
        _assert_invalid_token(_post(c, "Basic abc"))
    assert isinstance(deps.verifier, FakeVerifier)
    assert deps.verifier.verified == []
    assert uow.stored.users == {}


def test_an_empty_bearer_token_is_401():
    with api_client(InMemoryUnitOfWork()) as c:
        _assert_invalid_token(_post(c, "Bearer "))


def test_graphiql_is_served_on_get():
    with api_client(InMemoryUnitOfWork()) as c:
        response = c.get("/graphql", headers={"Accept": "text/html"})
    assert response.status_code == 200
    assert "graphiql" in response.text.lower()


def test_startup_and_shutdown_hooks_run():
    events: list[str] = []
    app = create_app(
        dependencies(InMemoryUnitOfWork()),
        on_startup=lambda: events.append("startup"),
        on_shutdown=lambda: events.append("shutdown"),
    )
    with TestClient(app):
        assert events == ["startup"]
    assert events == ["startup", "shutdown"]


def test_a_failing_startup_still_runs_shutdown():
    events: list[str] = []

    def failing_startup() -> None:
        raise RuntimeError("startup failed")

    app = create_app(
        dependencies(InMemoryUnitOfWork()),
        on_startup=failing_startup,
        on_shutdown=lambda: events.append("shutdown"),
    )
    with pytest.raises(RuntimeError, match="startup failed"), TestClient(app):
        pass
    assert events == ["shutdown"]


def test_build_server_on_a_fresh_database(tmp_path):
    app = build_server(str(tmp_path / "db.sqlite"), {})
    with TestClient(app) as c:
        assert gql(c, "{ viewer { subject } }") == {"viewer": None}
