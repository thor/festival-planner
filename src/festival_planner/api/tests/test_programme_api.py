import datetime
import zoneinfo
from collections.abc import Iterable, Mapping
from typing import Any

import pytest
from starlette.testclient import TestClient

from festival_planner.api.app import create_app
from festival_planner.api.ids import encode
from festival_planner.api.tests.support import api_client, dependencies, gql
from festival_planner.domain.festival import (
    Festival,
    FestivalId,
    FestivalSeries,
    FestivalSeriesId,
)
from festival_planner.domain.programme import (
    Event,
    Film,
    FilmId,
    ProgrammeEntry,
    ProgrammeEntryId,
    Screening,
    ScreeningId,
    Venue,
    VenueId,
)
from festival_planner.domain.tests.fakes import InMemoryUnitOfWork

OSLO = zoneinfo.ZoneInfo("Europe/Oslo")


def _at(hour: int) -> datetime.datetime:
    return datetime.datetime(2030, 11, 9, hour, tzinfo=OSLO)


SERIES = FestivalSeries(id=FestivalSeriesId("series-fest"), slug="fest", name="Fest")
FESTIVAL = Festival(
    id=FestivalId("festival-2030"),
    slug="fest-2030",
    name="Fest 2030",
    start_date=datetime.date(2030, 11, 8),
    end_date=datetime.date(2030, 11, 17),
    time_zone="Europe/Oslo",
    series_id=SERIES.id,
)
VENUE_A = Venue(id=VenueId("venue-a"), name="A")
VENUE_B = Venue(id=VenueId("venue-b"), name="B")


def _entry(title: str, year: int) -> tuple[Film, ProgrammeEntry]:
    key = title.lower()
    film = Film(id=FilmId(f"film-{key}"), title=title, year=year)
    entry = ProgrammeEntry(
        id=ProgrammeEntryId(f"entry-{key}"),
        film_id=film.id,
        title=title,
        year=year,
        country="NO",
        url=f"https://fest.example/{key}",
    )
    return film, entry


FILM_BANANA, BANANA = _entry("Banana", 2029)
FILM_APPLE, APPLE = _entry("apple", 2030)
FILM_CHERRY, CHERRY = _entry("Cherry", 2028)

TALK = Event(description="Q&A", start_time=_at(20), end_time=_at(21))
APPLE_EVENING = Screening(
    id=ScreeningId("screening-apple-evening"),
    programme_entry_id=APPLE.id,
    venue_id=VENUE_A.id,
    start_time=_at(18),
    end_time=_at(20),
    auditorium="Hall 1",
    ticket_url="https://fest.example/tickets/1",
    events=(TALK,),
)
APPLE_LATE = Screening(
    id=ScreeningId("screening-apple-late"),
    programme_entry_id=APPLE.id,
    venue_id=VENUE_B.id,
    start_time=_at(21),
    end_time=_at(23),
)
BANANA_AFTERNOON = Screening(
    id=ScreeningId("screening-banana"),
    programme_entry_id=BANANA.id,
    venue_id=VENUE_B.id,
    start_time=_at(16),
    end_time=_at(18),
)
CHERRY_WITHDRAWN = Screening(
    id=ScreeningId("screening-cherry"),
    programme_entry_id=CHERRY.id,
    venue_id=VENUE_A.id,
    start_time=_at(20),
    end_time=_at(22),
    withdrawn=True,
)


def _seeded() -> InMemoryUnitOfWork:
    uow = InMemoryUnitOfWork()
    with uow:
        uow.festivals.save_series(SERIES)
        uow.festivals.save(FESTIVAL)
        uow.venues.save(VENUE_B)
        uow.venues.save(VENUE_A)
        for film in (FILM_BANANA, FILM_APPLE, FILM_CHERRY):
            uow.films.save(film)
        for entry in (BANANA, APPLE, CHERRY):
            uow.programme.save_entry(FESTIVAL.id, entry.id, entry)
        for s in (APPLE_LATE, CHERRY_WITHDRAWN, APPLE_EVENING, BANANA_AFTERNOON):
            uow.programme.save_screening(s)
        uow.commit()
    return uow


@pytest.fixture
def client() -> Iterable[TestClient]:
    with api_client(_seeded()) as c:
        yield c


def test_festivals_are_listed(client: TestClient):
    data = gql(
        client,
        "{ festivals { slug name startDate endDate timeZone series { slug name } } }",
    )
    assert data == {
        "festivals": [
            {
                "slug": "fest-2030",
                "name": "Fest 2030",
                "startDate": "2030-11-08",
                "endDate": "2030-11-17",
                "timeZone": "Europe/Oslo",
                "series": {"slug": "fest", "name": "Fest"},
            }
        ]
    }


def test_an_unknown_festival_is_null(client: TestClient):
    assert gql(client, '{ festival(slug: "nope") { slug } }') == {"festival": None}


def test_venues_are_listed_by_name(client: TestClient):
    data = gql(client, "{ venues { id name } }")
    assert data == {
        "venues": [
            {"id": encode("Venue", "venue-a"), "name": "A"},
            {"id": encode("Venue", "venue-b"), "name": "B"},
        ]
    }


ENTRIES_PAGE = """
query ($after: String) {
  festival(slug: "fest-2030") {
    programmeEntries(first: 2, after: $after) {
      edges { node { title } }
      pageInfo { hasNextPage endCursor }
    }
  }
}
"""


def _entries_page(client: TestClient, after: str | None) -> dict[str, Any]:
    data = gql(client, ENTRIES_PAGE, {"after": after})
    return data["festival"]["programmeEntries"]


def _titles(connection: Mapping[str, Any]) -> list[str]:
    return [edge["node"]["title"] for edge in connection["edges"]]


def test_programme_entries_page_by_title(client: TestClient):
    first = _entries_page(client, None)
    assert _titles(first) == ["apple", "Banana"]
    assert first["pageInfo"]["hasNextPage"] is True
    rest = _entries_page(client, first["pageInfo"]["endCursor"])
    assert _titles(rest) == ["Cherry"]
    assert rest["pageInfo"]["hasNextPage"] is False


def _ids(*screenings: Screening) -> list[str]:
    return [encode("Screening", s.id) for s in screenings]


def test_withdrawn_screenings_are_hidden_unless_asked(client: TestClient):
    query = """
    query ($withdrawn: Boolean!, $entry: ID!) {
      festival(slug: "fest-2030") {
        screenings(includeWithdrawn: $withdrawn) { edges { node { id } } }
      }
      node(id: $entry) {
        ... on ProgrammeEntry { screenings(includeWithdrawn: $withdrawn) { id } }
      }
    }
    """
    entry = encode("ProgrammeEntry", CHERRY.id)

    hidden = gql(client, query, {"withdrawn": False, "entry": entry})
    festival_ids = [e["node"]["id"] for e in hidden["festival"]["screenings"]["edges"]]
    assert festival_ids == _ids(BANANA_AFTERNOON, APPLE_EVENING, APPLE_LATE)
    assert hidden["node"] == {"screenings": []}

    shown = gql(client, query, {"withdrawn": True, "entry": entry})
    festival_ids = [e["node"]["id"] for e in shown["festival"]["screenings"]["edges"]]
    assert festival_ids == _ids(
        BANANA_AFTERNOON, APPLE_EVENING, CHERRY_WITHDRAWN, APPLE_LATE
    )
    assert shown["node"] == {
        "screenings": [{"id": encode("Screening", CHERRY_WITHDRAWN.id)}]
    }


def test_a_screening_shows_its_entry_venue_and_events(client: TestClient):
    query = """
    query ($id: ID!) {
      node(id: $id) {
        ... on Screening {
          startTime endTime auditorium ticketUrl withdrawn
          programmeEntry { title year country url film { title year } }
          venue { name }
          events { description startTime endTime }
        }
      }
    }
    """
    data = gql(client, query, {"id": encode("Screening", APPLE_EVENING.id)})
    assert data["node"] == {
        "startTime": "2030-11-09T18:00:00+01:00",
        "endTime": "2030-11-09T20:00:00+01:00",
        "auditorium": "Hall 1",
        "ticketUrl": "https://fest.example/tickets/1",
        "withdrawn": False,
        "programmeEntry": {
            "title": "apple",
            "year": 2030,
            "country": "NO",
            "url": "https://fest.example/apple",
            "film": {"title": "apple", "year": 2030},
        },
        "venue": {"name": "A"},
        "events": [
            {
                "description": "Q&A",
                "startTime": "2030-11-09T20:00:00+01:00",
                "endTime": "2030-11-09T21:00:00+01:00",
            }
        ],
    }


@pytest.mark.parametrize(
    ("type_name", "domain_id"),
    [
        ("Festival", FESTIVAL.id),
        ("Venue", VENUE_B.id),
        ("Film", FILM_CHERRY.id),
        ("ProgrammeEntry", BANANA.id),
        ("Screening", APPLE_LATE.id),
    ],
)
def test_node_finds_each_type(client: TestClient, type_name: str, domain_id: str):
    global_id = encode(type_name, domain_id)
    data = gql(
        client,
        "query ($id: ID!) { node(id: $id) { id __typename } }",
        {"id": global_id},
    )
    assert data == {"node": {"id": global_id, "__typename": type_name}}


@pytest.mark.parametrize(
    "global_id",
    ["!!", encode("Venue", APPLE_LATE.id), encode("Nope", "x")],
)
def test_node_of_garbage_or_the_wrong_type_is_null(client: TestClient, global_id: str):
    data = gql(client, "query ($id: ID!) { node(id: $id) { id } }", {"id": global_id})
    assert data == {"node": None}


def test_nodes_keeps_the_order_and_nulls_what_it_cannot_find(client: TestClient):
    ids = [encode("Venue", VENUE_A.id), "!!", encode("Film", FILM_APPLE.id)]
    data = gql(client, "query ($ids: [ID!]!) { nodes(ids: $ids) { id } }", {"ids": ids})
    assert data == {"nodes": [{"id": ids[0]}, None, {"id": ids[2]}]}


def test_films_of_many_entries_load_in_one_batch(monkeypatch: pytest.MonkeyPatch):
    deps = dependencies(_seeded())
    films_by_id = deps.programme.films_by_id
    calls: list[frozenset[FilmId]] = []

    def spy(ids: Iterable[FilmId]) -> Mapping[FilmId, Film]:
        wanted = frozenset(ids)
        calls.append(wanted)
        return films_by_id(wanted)

    monkeypatch.setattr(deps.programme, "films_by_id", spy)
    query = """
    { festival(slug: "fest-2030") {
        programmeEntries { edges { node { film { title } } } } } }
    """
    with TestClient(create_app(deps)) as c:
        data = gql(c, query)
    titles = [
        e["node"]["film"]["title"]
        for e in data["festival"]["programmeEntries"]["edges"]
    ]
    assert titles == ["apple", "Banana", "Cherry"]
    assert calls == [frozenset({FILM_APPLE.id, FILM_BANANA.id, FILM_CHERRY.id})]
