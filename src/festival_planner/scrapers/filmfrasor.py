"""Scraper for filmfrasor.no film festival."""

import re
import time
from collections.abc import Iterable
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote

import httpx
from bs4 import BeautifulSoup, Tag
from hishel import BaseFilter, FilterPolicy, Response, SyncSqliteStorage
from hishel.httpx import SyncCacheTransport
from pydantic import ValidationError

from .._logging import get_logger
from ..models import Film, FilmDetails, FilmList
from .base import BaseScraper

logger = get_logger(__name__)


# Labels in .entry-technical, Norwegian and English, by field.
TECHNICAL_LABELS: dict[str, tuple[str, ...]] = {
    "age_limit": ("aldersgrense", "age limit", "age rating"),
    "language": ("språk", "language"),
    "subtitles": ("undertekst", "subtitles"),
    "runtime": ("spilletid", "running time", "runtime", "duration"),
    "original_title": ("originaltittel", "original title"),
    "genre": ("sjanger", "genre"),
    "director": ("regissør", "director"),
}


class _SuccessfulResponseFilter(BaseFilter[Response]):
    """Only cache successful (2xx) responses."""

    def needs_body(self) -> bool:
        return False

    def apply(self, item: Response, body: bytes | None) -> bool:
        return 200 <= item.status_code < 300


class _AsciiHeadersTransport(httpx.BaseTransport):
    """Percent-encode non-ASCII response header values.

    hishel re-encodes header values as ASCII, so a raw UTF-8 header such as
    ``Link: <https://www.filmfrasor.no/no/film/2026/adrián-...>`` would
    otherwise fail the request.
    """

    _SAFE = "".join(map(chr, range(0x20, 0x7F)))

    def __init__(self, transport: httpx.BaseTransport):
        self._transport = transport

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        response = self._transport.handle_request(request)
        if all(value.isascii() for _, value in response.headers.raw):
            return response
        return httpx.Response(
            status_code=response.status_code,
            headers=[
                (
                    key,
                    value
                    if value.isascii()
                    else quote(value, safe=self._SAFE).encode("ascii"),
                )
                for key, value in response.headers.raw
            ],
            stream=response.stream,
            extensions=response.extensions,
        )

    def close(self) -> None:
        self._transport.close()


class FilmfrasorScraper(BaseScraper):
    """Scraper for the Filmfrasor.no festival website."""

    BASE_URL = "https://www.filmfrasor.no"

    def __init__(
        self,
        cache_dir: Path | None = None,
        year: int | None = None,
        force_refresh: bool = False,
        known_venue_names: Iterable[str] = (),
        language: str | None = "no",
    ):
        """Initialize the Filmfrasor scraper.

        Args:
            cache_dir: Directory to cache scraped data and HTTP responses
            year: Festival year (defaults to current year)
            force_refresh: If True, bypass HTTP cache and fetch fresh data
            known_venue_names: Known cinema names and aliases, used to split
                "Vika Kino 3" into cinema and auditorium. Normalising and
                filtering cinemas is up to the caller (see
                ``models.normalise_cinemas``).
            language: Programme language
        """
        super().__init__(cache_dir)
        self.year = year or datetime.now().year
        self.force_refresh = force_refresh
        self.language = language
        # Known cinema names (lowercase), for splitting cinema and auditorium
        self.known_cinemas: set[str] = {name.lower() for name in known_venue_names}

        # Set up HTTP cache directory
        if cache_dir:
            self.http_cache_dir = cache_dir / ".http_cache"
        else:
            self.http_cache_dir = Path(".cache") / "filmfrasor_http"

        self.http_cache_dir.mkdir(parents=True, exist_ok=True)

        # Create HTTP client (with or without caching)
        if self.force_refresh:
            # No caching - use standard client
            self.client = httpx.Client(timeout=30.0, follow_redirects=True)
        else:
            # Cache successful responses indefinitely, ignoring HTTP cache headers
            # (festival data does not change within a run).
            self.client = httpx.Client(
                transport=SyncCacheTransport(
                    next_transport=_AsciiHeadersTransport(httpx.HTTPTransport()),
                    storage=SyncSqliteStorage(
                        database_path=self.http_cache_dir / "http_cache.db"
                    ),
                    policy=FilterPolicy(response_filters=[_SuccessfulResponseFilter()]),
                ),
                timeout=30.0,
                follow_redirects=True,
            )

    def get_festival_name(self) -> str:
        """Get the name of the festival."""
        return f"Film fra Sør {self.year}"

    def scrape(self) -> FilmList:
        """Scrape the Filmfrasor programme.

        Returns:
            FilmList containing all scraped films
        """
        films: list[Film] = []

        try:
            # Fetch the programme's film list view; the plain programme page
            # only shows a single day's calendar.
            programme_url = f"{self.BASE_URL}/{self.language}/program?films"

            logger.info("Fetching programme", url=programme_url)
            if self.force_refresh:
                logger.info("Cache refresh forced - fetching fresh data")
            else:
                logger.debug("Using HTTP cache", cache_dir=str(self.http_cache_dir))

            response = self.client.get(programme_url)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            # Find all film links on the programme page
            film_links = self._extract_film_links(soup)
            logger.info("Found film pages to scrape", count=len(film_links))

            # Visit each film page and extract screening information
            for idx, film_url in enumerate(film_links, 1):
                try:
                    # Be gentle - add a small delay between requests (only for non-cached)
                    if idx > 1 and not self.force_refresh:
                        time.sleep(0.3)

                    film_response = self.client.get(film_url)
                    film_response.raise_for_status()

                    # Check if from cache (Hishel extension)
                    from_cache = film_response.extensions.get(
                        "hishel_from_cache", False
                    )

                    logger.info(
                        "Scraping film page",
                        index=idx,
                        total=len(film_links),
                        url=film_url,
                        cached=from_cache,
                    )

                    film_soup = BeautifulSoup(film_response.text, "html.parser")
                    film_screenings = self._parse_film_page(film_soup, film_url)

                    films.extend(film_screenings)
                    logger.debug(
                        "Found screenings for film",
                        count=len(film_screenings),
                        url=film_url,
                    )

                except Exception:
                    # One broken film page must not stop the whole scrape.
                    logger.exception("Error scraping film page", url=film_url)
                    continue

        except httpx.HTTPError:
            logger.exception("HTTP error while scraping")
        except Exception:
            logger.exception("Error while scraping")

        logger.info("Scraping complete", total_screenings=len(films))
        return FilmList(films=sorted(films, key=lambda x: x.title))

    def _extract_film_links(self, soup: BeautifulSoup) -> list[str]:
        """Extract all film page links from the programme page.

        Args:
            soup: BeautifulSoup object of the programme page

        Returns:
            List of absolute URLs to film pages
        """
        film_links = set()

        # Film pages have URLs like /no/film/2026/film-title
        film_path = re.compile(rf"/{self.language}/film/\d{{4}}/[^/?#]+")
        for link in soup.find_all("a", href=True):
            href = link["href"]
            if not isinstance(href, str):
                logger.warning("Invalid href type", href=href, href_type=type(href))
                continue

            # Check if this looks like a film page link
            if film_path.search(href):
                # Make it an absolute URL if it's relative
                if href.startswith("/"):
                    full_url = f"{self.BASE_URL}{href}"
                else:
                    full_url = href

                # Avoid duplicates
                film_links.add(full_url)

        return list(film_links)

    def _parse_film_page(self, soup: BeautifulSoup, url: str) -> list[Film]:
        """Parse a single film page to extract screening information.

        Args:
            soup: BeautifulSoup object of the film page
            url: URL of the film page

        Returns:
            List of Film objects (one per screening)
        """
        screenings = []

        try:
            # Extract film title
            title = self._extract_title(soup)
            if not title:
                logger.warning("Could not find title", url=url)
                return []

            # Extract country and year
            country, year = self._extract_country_and_year(soup)
            details = self._extract_details(soup)

            # Extract screening times
            # Look for elements that contain screening information
            screening_elements = self._find_screening_elements(soup)

            for screening_elem in screening_elements:
                try:
                    screening_info = self._parse_screening_element(screening_elem)
                    if not screening_info:
                        continue

                    (
                        start_time,
                        end_time,
                        cinema,
                        auditorium,
                        special_notes,
                        ticket_url,
                    ) = screening_info

                    try:
                        screening = Film(
                            title=title,
                            country=country,
                            year=year,
                            url=url,
                            ticket_url=ticket_url,
                            start_time=start_time,
                            end_time=end_time,
                            cinema=cinema,
                            auditorium=auditorium,
                            special_notes=special_notes,
                            details=details,
                        )
                        screenings.append(screening)
                        logger.debug("Added screening", **screening.model_dump())
                    except ValidationError as e:
                        # Log validation error as warning and continue
                        logger.warning(
                            "Invalid film screening - skipping",
                            title=title,
                            cinema=cinema,
                            start_time=start_time,
                            error=str(e),
                        )
                        continue

                except Exception:
                    # Skip a screening the page lays out in a way we do not expect.
                    logger.warning(
                        "Error parsing screening element", title=title, exc_info=True
                    )
                    continue

        except Exception:
            logger.exception("Error parsing film page", url=url)

        return screenings

    def _extract_title(self, soup: BeautifulSoup) -> str | None:
        """Extract film title from the page."""
        # Try h1 first
        h1 = soup.find("h1")
        if h1:
            return h1.get_text(strip=True)

        # Try title tag
        title_tag = soup.find("title")
        if title_tag:
            title_text = title_tag.get_text(strip=True)
            # Remove common suffixes like "- Film fra Sør"
            title_text = re.sub(
                r"\s*[-–]\s*Film fra S[øo]r.*$", "", title_text, flags=re.IGNORECASE
            )
            return title_text

        return None

    def _extract_details(self, soup: BeautifulSoup) -> FilmDetails:
        """What the film page says about the film beyond its screenings.

        The tagline and synopsis are paragraphs of .entry-main-text. Facts are
        label/value paragraphs in .entry-technical ("<span>Språk</span>
        Spansk"); the page repeats that block, so the first value wins. Images
        of related films sit in .entry-related and are skipped.
        """
        main = soup.find(class_="entry-main-text")
        tagline = main.find(class_="tagline") if main else None
        paragraphs = (
            [
                p.get_text(" ", strip=True)
                for p in main.find_all("p", recursive=False)
                if "tagline" not in (p.get("class") or [])
            ]
            if main
            else []
        )

        facts: dict[str, str] = {}
        imdb_url = None
        for p in soup.select(".entry-technical p"):
            label = p.find("span")
            if label is None:
                continue
            key = label.get_text(" ", strip=True).lower()
            if imdb_url is None:
                link = p.find("a", href=re.compile(r"imdb\.com"))
                imdb_url = link["href"] if link else None
            value_tag = p.find(class_="age_limit_technical")
            if value_tag is not None:
                value = value_tag.find(string=True, recursive=False) or ""
            else:
                value = "".join(t for t in p.find_all(string=True) if t.parent is p)
            value = " ".join(value.split())
            for field, labels in TECHNICAL_LABELS.items():
                if key in labels and value:
                    facts.setdefault(field, value)

        def own_image(folder: str) -> str | None:
            for img in soup.find_all("img", src=re.compile(folder)):
                if img.find_parent(class_="entry-related") is None:
                    return img["src"]
            return None

        return FilmDetails(
            tagline=tagline.get_text(" ", strip=True) if tagline else None,
            synopsis="\n\n".join(p for p in paragraphs if p) or None,
            poster_url=own_image("/posters/"),
            still_url=own_image("/filmbilder/"),
            runtime_minutes=_minutes(facts.get("runtime")),
            original_title=facts.get("original_title"),
            director=facts.get("director"),
            genre=facts.get("genre"),
            language=facts.get("language"),
            subtitles=facts.get("subtitles"),
            age_limit=facts.get("age_limit"),
            imdb_url=imdb_url,
        )

    def _extract_country_and_year(self, soup: BeautifulSoup) -> tuple[str, int | None]:
        """Extract country and year information from the page.

        The facts live in .entry-info > .extra as label/value pairs, where each
        value is a span preceded by its label text:
        "Land <span>Sør-Korea</span> | År <span>2025</span> | Regissør <span>…</span>".
        Any pair may be missing.

        Returns:
            Tuple of (country, year) where year may be None if not found
        """
        entry_info = soup.find(class_="entry-info")
        extra_div = entry_info.find(class_="extra") if entry_info else None
        if not extra_div:
            logger.debug("No .entry-info .extra element found")
            return "Unknown", None

        facts: dict[str, str] = {}
        for span in extra_div.find_all("span", recursive=False):
            label = span.find_previous_sibling(string=True)
            if label is None:
                continue
            key = label.strip(" |\n\t").lower()
            facts[key] = span.get_text(" ", strip=True)

        country = facts.get("land") or facts.get("country") or "Unknown"

        year = None
        year_text = facts.get("år") or facts.get("year") or ""
        year_match = re.search(r"\b(19\d{2}|20\d{2})\b", year_text)
        if year_match:
            year = int(year_match.group(1))
        else:
            logger.debug("No year found", facts=facts)

        return country, year

    def _find_screening_elements(self, soup: BeautifulSoup) -> list:
        """Find elements that contain screening information.

        Filmfrasor.no uses divs with class "show-item" for each screening,
        with a data-start attribute like "2026-11-04 18:00".
        Each show-item contains:
        - class "date": Date (e.g., "lør. 08.11")
        - class "time": Time range (e.g., "13:15 - 14:53")
        - class "location": Cinema (e.g., "Vika 3")
        - class "special": Special notes (optional)
        """
        # Look for all divs with class "show-item"
        screening_elements = soup.find_all("div", attrs={"class": "show-item"})

        if not screening_elements:
            # Log diagnostic information if no elements found
            logger.warning(
                "No elements found with class 'show-item'. "
                "Website structure may have changed."
            )

        return screening_elements

    def _parse_screening_element(self, element: Tag) -> tuple | None:
        """Parse a screening element to extract time, cinema, etc.

        The element is a div with class "show-item" and a data-start attribute
        (e.g. "2026-11-04 18:00") containing:
        - class "date": Date (e.g., "lør. 08.11")
        - class "time": Time range (e.g., "13:15 - 14:53")
        - class "location": Cinema (e.g., "Vika 3")
        - class "special": Special notes (optional)

        Returns:
            Tuple of (start_time, end_time, cinema, auditorium, special_notes, ticket_url) or None
        """
        # The date (with year) comes from data-start; fall back to the
        # "date" element (e.g. "lør. 08.11") with the configured year.
        year = self.year
        data_start = element.get("data-start")
        start_match = (
            re.match(r"(\d{4})-(\d{2})-(\d{2})", data_start)
            if isinstance(data_start, str)
            else None
        )
        if start_match:
            year, month, day = (int(g) for g in start_match.groups())
            # Film pages may also list screenings from earlier festivals
            if year != self.year:
                logger.debug("Skipping screening from another year", year=year)
                return None
        else:
            date_elem = element.find(class_="date")
            if not date_elem:
                logger.debug("No date element found in show-item")
                return None

            date_text = date_elem.get_text(strip=True)
            date_match = re.search(r"(\d{1,2})\.(\d{1,2})", date_text)
            if not date_match:
                logger.debug("Could not parse date from text", date_text=date_text)
                return None

            day = int(date_match.group(1))
            month = int(date_match.group(2))

        # Extract time from element with class "time"
        time_elem = element.find(class_="time")
        if not time_elem:
            logger.debug("No time element found in show-item")
            return None

        time_text = time_elem.get_text(strip=True)

        # Parse time range: "13:15 - 14:53"
        time_match = re.search(r"(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})", time_text)
        if not time_match:
            logger.debug("Could not parse time from text", time_text=time_text)
            return None

        start_hour = int(time_match.group(1))
        start_minute = int(time_match.group(2))
        end_hour = int(time_match.group(3))
        end_minute = int(time_match.group(4))

        try:
            start_time = datetime(year, month, day, start_hour, start_minute)
            end_time = datetime(year, month, day, end_hour, end_minute)
        except ValueError as e:
            logger.debug("Invalid date/time values", error=str(e), day=day, month=month)
            return None

        # Screenings that run past midnight end on the next day
        if end_time <= start_time:
            end_time += timedelta(days=1)

        # Extract cinema from element with class "location"
        location_elem = element.find(class_="location")
        if not location_elem:
            logger.debug("No location element found in show-item")
            return None

        cinema_text = location_elem.get_text(strip=True)

        # Extract cinema name and auditorium
        # Pattern: "Vika 3" -> cinema="Vika", auditorium="3"
        cinema, auditorium = self._split_cinema_and_auditorium(cinema_text)

        # Extract special notes from element with class "special" (if present)
        special_elem = element.find(class_="special")
        special_notes = special_elem.get_text(strip=True) if special_elem else None

        # Extract ticket URL
        ticket_url_elem = element.find(class_="event-item billett")
        if not ticket_url_elem or ticket_url_elem.get("href") is None:
            logger.debug("No ticket URL element found in show-item")
            ticket_url = None
        else:
            ticket_url = ticket_url_elem.get("href")

        return (start_time, end_time, cinema, auditorium, special_notes, ticket_url)

    def _split_cinema_and_auditorium(self, cinema_text: str) -> tuple[str, str | None]:
        """Split cinema text into cinema name and auditorium.

        Uses config-based cinema names to intelligently parse the text.
        Cinema normalization is handled by the Film model's validator.

        Examples:
        - "Vika Kino 3" -> ("Vika Kino", "3")  # Model normalizes to "Vika"
        - "Cinemateket Lillebil" -> ("Cinemateket", "Lillebil")
        - "Vega 2" -> ("Vega", "2")
        - "Vega" -> ("Vega", None)

        Args:
            cinema_text: Text like "Vika 3" or "Cinemateket Lillebil"

        Returns:
            Tuple of (cinema, auditorium) where auditorium may be None
        """
        cinema_text = cinema_text.strip()
        if not cinema_text:
            return cinema_text, None

        cinema_text_lower = cinema_text.lower()

        # Try to match known cinema names (longest first to avoid partial matches)
        if self.known_cinemas:
            # Sort by length descending to match longest names first
            sorted_cinemas = sorted(self.known_cinemas, key=len, reverse=True)

            for known_cinema in sorted_cinemas:
                if cinema_text_lower.startswith(known_cinema):
                    # Extract cinema name (preserve original case)
                    cinema_name = cinema_text[: len(known_cinema)]
                    # Extract rest as auditorium
                    rest = cinema_text[len(known_cinema) :].strip()

                    return cinema_name, rest if rest else None

        # Fallback: Generic pattern matching for "Cinema Number"
        match = re.search(r"^(.+?)\s+(\d+)$", cinema_text)
        if match:
            cinema = match.group(1).strip()
            auditorium = match.group(2)
            return cinema, auditorium

        # No auditorium found
        return cinema_text, None

    def _extract_cinema_from_text(self, text: str) -> str:
        """Extract cinema name from text."""
        # Known Oslo cinemas
        cinemas = ["Cinemateket", "Vika Kino", "Vika", "Vega", "Vega Scene"]

        for cinema in cinemas:
            if cinema.lower() in text.lower():
                return cinema

        # If no known cinema found, try to extract something after common keywords
        cinema_keywords = ["cinema:", "kino:", "sted:", "venue:"]
        for keyword in cinema_keywords:
            if keyword in text.lower():
                parts = text.lower().split(keyword, 1)
                if len(parts) > 1:
                    # Take the next word or two
                    cinema_text = parts[1].strip().split()[0:2]
                    return " ".join(cinema_text).strip()

        return "Unknown"

    def _extract_special_notes(self, text: str) -> str | None:
        """Extract special notes like Q&A, premiere, etc."""
        keywords = [
            "Q&A",
            "q&a",
            "premiere",
            "åpning",
            "opening",
            "closing",
            "avslutning",
            "director",
            "regissør",
        ]

        found_notes = []
        for keyword in keywords:
            if keyword.lower() in text.lower():
                found_notes.append(keyword)

        return ", ".join(found_notes) if found_notes else None


def _minutes(text: str | None) -> int | None:
    """Minutes in a running time such as "1t 18m", "2h" or "95 min"."""
    hours = re.search(r"(\d+)\s*[th]", text or "")
    minutes = re.search(r"(\d+)\s*m", text or "")
    if not hours and not minutes:
        return None
    return (int(hours.group(1)) * 60 if hours else 0) + (
        int(minutes.group(1)) if minutes else 0
    )
