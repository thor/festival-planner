"""Test parsing of filmfrasor.no pages, using markup from the 2026 website."""

from datetime import datetime

import httpx
import pytest
from bs4 import BeautifulSoup

from festival_planner.scrapers.filmfrasor import (
    FilmfrasorScraper,
    _AsciiHeadersTransport,
    _minutes,
)

FILM_LIST = """
<div class="grid">
  <a href="https://www.filmfrasor.no/no/film/">Alle filmer</a>
  <div class="card  film ">
    <a href="https://www.filmfrasor.no/no/film/2026/no-other-choice">No Other Choice</a>
  </div>
  <div class="card  film ">
    <a href="https://www.filmfrasor.no/no/film/1994/cronos">Cronos</a>
  </div>
  <a href="https://www.filmfrasor.no/no/arrangement/2026/oppvarming">Oppvarming</a>
  <a href="https://www.filmfrasor.no/en/film/2026/no-other-choice">English</a>
</div>
"""

ENTRY_INFO = """
<section class="entry-info">
  <h1 class="title">
    No Other Choice
  </h1>
  <div class="extra">
    Land
    <span>
      Sør-Korea
    </span>
    |
    År
    <span>
      2025
    </span>
    |
    Regissør
    <span>
      <a href="/no/search/results?q=director:Park Chan-wook">Park Chan-wook</a>
    </span>
  </div>
</section>
"""

ENTRY_INFO_WITHOUT_COUNTRY = """
<section class="entry-info">
  <div class="extra">
    |
    År
    <span>
      1994
    </span>
    |
  </div>
</section>
"""


def show_item(data_start: str | None, date: str, time: str) -> str:
    start_attr = f' data-start="{data_start}"' if data_start else ""
    return f"""
<div class="show-item "{start_attr}>
  <div class="date-time-location">
    <div class="date">{date}</div>
    <div class="time">{time}</div>
    <div class="location" style="background-color: ; ">Vika Kino 3</div>
  </div>
  <div class="events">
    <a href="https://www.filmfrasor.no/no/arrangement/2026/x" class="event-item special">Q&amp;A med regissør</a>
    <a href="https://checkout.ebillett.no/287/events/61447" target="_blank" class="event-item billett">Kjøp billett</a>
  </div>
</div>
"""


@pytest.fixture
def scraper(tmp_path):
    return FilmfrasorScraper(cache_dir=tmp_path, year=2026)


def soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def test_film_links_only_include_film_pages(scraper):
    links = scraper._extract_film_links(soup(FILM_LIST))

    assert sorted(links) == [
        "https://www.filmfrasor.no/no/film/1994/cronos",
        "https://www.filmfrasor.no/no/film/2026/no-other-choice",
    ]


def test_title(scraper):
    assert scraper._extract_title(soup(ENTRY_INFO)) == "No Other Choice"


def test_country_and_year_from_labelled_facts(scraper):
    assert scraper._extract_country_and_year(soup(ENTRY_INFO)) == ("Sør-Korea", 2025)


def test_missing_country_is_unknown(scraper):
    assert scraper._extract_country_and_year(soup(ENTRY_INFO_WITHOUT_COUNTRY)) == (
        "Unknown",
        1994,
    )


def test_screening_elements_match_padded_class(scraper):
    page = soup(show_item("2026-11-04 18:00", "ons. 04.11", "18:00 - 20:19"))

    assert len(scraper._find_screening_elements(page)) == 1


def test_screening_takes_date_and_year_from_data_start(scraper):
    element = soup(show_item("2026-11-04 18:00", "ons. 04.11", "18:00 - 20:19")).find(
        class_="show-item"
    )

    assert scraper._parse_screening_element(element) == (
        datetime(2026, 11, 4, 18, 0),
        datetime(2026, 11, 4, 20, 19),
        "Vika Kino",
        "3",
        "Q&A med regissør",
        "https://checkout.ebillett.no/287/events/61447",
    )


def test_screening_without_data_start_uses_date_text_and_configured_year(scraper):
    element = soup(show_item(None, "lør. 08.11", "13:15 - 14:53")).find(
        class_="show-item"
    )

    start_time, end_time, *_ = scraper._parse_screening_element(element)

    assert start_time == datetime(2026, 11, 8, 13, 15)
    assert end_time == datetime(2026, 11, 8, 14, 53)


def test_screening_past_midnight_ends_next_day(scraper):
    element = soup(show_item("2026-11-07 23:00", "lør. 07.11", "23:00 - 00:45")).find(
        class_="show-item"
    )

    start_time, end_time, *_ = scraper._parse_screening_element(element)

    assert start_time == datetime(2026, 11, 7, 23, 0)
    assert end_time == datetime(2026, 11, 8, 0, 45)


def test_screening_from_another_festival_year_is_skipped(scraper):
    element = soup(show_item("2024-11-09 15:15", "lør. 09.11", "15:15 - 17:00")).find(
        class_="show-item"
    )

    assert scraper._parse_screening_element(element) is None


def test_non_ascii_response_headers_are_percent_encoded():
    link = "<https://www.filmfrasor.no/no/film/2026/adrián>; rel=canonical"
    transport = _AsciiHeadersTransport(
        httpx.MockTransport(
            lambda request: httpx.Response(
                200, headers=[(b"link", link.encode())], content=b"ok"
            )
        )
    )

    with httpx.Client(transport=transport) as client:
        response = client.get("https://www.filmfrasor.no/no/film/2026/adrián")

    assert response.headers["link"] == (
        "<https://www.filmfrasor.no/no/film/2026/adri%C3%A1n>; rel=canonical"
    )
    assert response.text == "ok"


FILM_DETAILS = """
<div class="header-content">
  <img src="https://festivalkontoret.s3.amazonaws.com/filmbilder/2025-Festival/_articleFullWidth/Noviembre.jpg" alt="">
</div>
<div class="outer_wrapper">
  <img src="https://festivalkontoret.s3.amazonaws.com/posters/2025/_posterTransform/Noviembre.jpg" alt="">
  <section class="entry-main-text">
    <p class="tagline">Denne intense thrilleren gjenforteller stormingen av Justispalasset.</p>
    <p>Palasset rommer landets høyesterett.</p>
    <p>Resultatet er et klaustrofobisk kammerspill. </p>
  </section>
  <section class="entry-technical main">
    <p class="age_line"><span>Aldersgrense</span><span class="age_limit_technical">15 <img class="age_tooltip" src="/graphics/question_icon.svg"/> <span class="age_reason">Grafisk vold.</span></span></p>
    <p><span>Språk</span>
      Spansk
    </p>
    <p><span>Undertekst</span>
      Engelsk
    </p>
    <p><span>Spilletid</span> 1t 18m</p>
    <p><span>Originaltittel</span> Noviembre</p>
    <p><span>Sjanger</span>Thriller</p>
    <p><span>Regissør</span> Tomás Corredor</p>
    <p><span>Lenker</span><span class="technical-links">
      <a href="https://www.imdb.com/title/tt18274520/" target="_blank">IMDb</a>
    </span></p>
  </section>
  <section class="entry-technical">
    <p><span>Språk</span> Annet</p>
  </section>
  <section class="entry-related">
    <a class="card film"><img src="https://festivalkontoret.s3.amazonaws.com/posters/2025/_posterTransform/Other.jpg"></a>
  </section>
</div>
"""


def test_details_from_the_film_page(scraper):
    details = scraper._extract_details(soup(FILM_DETAILS))
    assert details.tagline == (
        "Denne intense thrilleren gjenforteller stormingen av Justispalasset."
    )
    assert details.synopsis == (
        "Palasset rommer landets høyesterett.\n\n"
        "Resultatet er et klaustrofobisk kammerspill."
    )
    assert details.poster_url is not None and details.poster_url.endswith(
        "/Noviembre.jpg"
    )
    assert details.still_url is not None and "/filmbilder/" in details.still_url
    assert (details.runtime_minutes, details.age_limit) == (78, "15")
    assert (details.language, details.subtitles) == ("Spansk", "Engelsk")
    assert (details.original_title, details.genre, details.director) == (
        "Noviembre",
        "Thriller",
        "Tomás Corredor",
    )
    assert details.imdb_url == "https://www.imdb.com/title/tt18274520/"


def test_a_page_without_details_has_none(scraper):
    details = scraper._extract_details(soup(ENTRY_INFO))
    assert details.model_dump(exclude_none=True) == {}


@pytest.mark.parametrize(
    ("text", "minutes"),
    [("1t 18m", 78), ("2h", 120), ("95 min", 95), ("1 h 5 min", 65), ("", None)],
)
def test_running_time(text, minutes):
    assert _minutes(text) == minutes
