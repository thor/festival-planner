"""The schema masks an unexpected resolver exception but not a GraphQL error.

A `LookupError` raised by a resolver (e.g. because a referenced Venue is
missing) must not reach the client with its own message: that could leak
internals. A GraphQL-level error, such as asking for an unknown field, is
already a client-facing message and must stay as written.
"""

import datetime
import logging
import zoneinfo
from collections.abc import Iterable

import pytest
from starlette.testclient import TestClient

from festival_planner.api.ids import encode
from festival_planner.api.tests.support import api_client
from festival_planner.domain.festival import Festival, FestivalId
from festival_planner.domain.programme import (
    Film,
    FilmId,
    ProgrammeEntry,
    ProgrammeEntryId,
    Screening,
    ScreeningId,
    VenueId,
)
from festival_planner.domain.tests.fakes import InMemoryUnitOfWork

OSLO = zoneinfo.ZoneInfo("Europe/Oslo")

FESTIVAL = Festival(
    id=FestivalId("festival-2030"),
    slug="fest-2030",
    name="Fest 2030",
    start_date=datetime.date(2030, 11, 8),
    end_date=datetime.date(2030, 11, 17),
    time_zone="Europe/Oslo",
    series_id=None,
)
FILM = Film(id=FilmId("film-a"), title="A", year=2030)
ENTRY = ProgrammeEntry(
    id=ProgrammeEntryId("entry-a"),
    film_id=FILM.id,
    title="A",
    year=2030,
    country=None,
    url=None,
)
# This Screening's venue_id names a Venue that was never saved: a data
# inconsistency the API never produces itself, but the fault we want to
# provoke to test masking.
BROKEN_SCREENING = Screening(
    id=ScreeningId("screening-broken"),
    programme_entry_id=ENTRY.id,
    venue_id=VenueId("missing-venue"),
    start_time=datetime.datetime(2030, 11, 9, 18, tzinfo=OSLO),
    end_time=datetime.datetime(2030, 11, 9, 20, tzinfo=OSLO),
)


def _seeded() -> InMemoryUnitOfWork:
    uow = InMemoryUnitOfWork()
    with uow:
        uow.festivals.save(FESTIVAL)
        uow.films.save(FILM)
        uow.programme.save_entry(FESTIVAL.id, ENTRY.id, ENTRY)
        uow.programme.save_screening(BROKEN_SCREENING)
        uow.commit()
    return uow


@pytest.fixture
def client() -> Iterable[TestClient]:
    with api_client(_seeded()) as c:
        yield c


def test_an_unexpected_exception_is_masked(
    client: TestClient, caplog: pytest.LogCaptureFixture
):
    screening_id = encode("Screening", BROKEN_SCREENING.id)
    with caplog.at_level(logging.ERROR):
        response = client.post(
            "/graphql",
            json={
                "query": """
                query ($id: ID!) {
                    node(id: $id) { ... on Screening { venue { name } } }
                }
                """,
                "variables": {"id": screening_id},
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["data"] == {"node": None}
    [error] = body["errors"]
    assert error["message"] == "Unexpected error."
    assert "missing-venue" not in error["message"]
    # Masked from the client, but still logged for operators to find.
    assert "missing-venue" in caplog.text


def test_a_validation_error_keeps_its_message(client: TestClient):
    response = client.post(
        "/graphql",
        json={"query": '{ festival(slug: "fest-2030") { noSuchField } }'},
    )

    assert response.status_code == 200
    body = response.json()
    assert "data" not in body or body["data"] is None
    [error] = body["errors"]
    assert "noSuchField" in error["message"]
