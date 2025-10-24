"""Scraper for filmfrasor.no film festival."""

import re
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Optional
import httpx
from bs4 import BeautifulSoup
from hishel import Controller, SQLiteStorage, CacheClient
from pydantic import ValidationError

from ..models import Cinema, Film, FilmList, build_normalization_map
from ..config import ConfigLoader
from .base import BaseScraper
from .._logging import get_logger

logger = get_logger(__name__)


class FilmfrasorScraper(BaseScraper):
    """Scraper for the Filmfrasor.no festival website."""

    BASE_URL = "https://www.filmfrasor.no"

    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        year: Optional[int] = None,
        force_refresh: bool = False,
        config_dir: Optional[Path] = None,
        language: Optional[str] = "no",
    ):
        """Initialize the Filmfrasor scraper.

        Args:
            cache_dir: Directory to cache scraped data and HTTP responses
            year: Festival year (defaults to current year)
            force_refresh: If True, bypass HTTP cache and fetch fresh data
            config_dir: Directory containing config files (for cinema validation)
        """
        super().__init__(cache_dir)
        self.year = year or datetime.now().year
        self.force_refresh = force_refresh
        self.config_dir = config_dir
        self.language = language
        self.known_cinemas: set[Cinema] = set()  # Store known cinema names for parsing

        # Set up HTTP cache directory
        if cache_dir:
            self.http_cache_dir = cache_dir / ".http_cache"
        else:
            self.http_cache_dir = Path(".cache") / "filmfrasor_http"

        self.http_cache_dir.mkdir(parents=True, exist_ok=True)

        # Load valid cinemas if config_dir provided
        if config_dir:
            self._setup_cinema_validation(config_dir)
        else:
            logger.warning("No config_dir provided - cinema validation disabled")

        # Create HTTP client (with or without caching)
        if self.force_refresh:
            # No caching - use standard client
            self.client = httpx.Client(timeout=30.0, follow_redirects=True)
        else:
            # Set up Hishel storage with SQLite backend
            db_path = str(self.http_cache_dir / "hishel_cache.db")
            connection = sqlite3.connect(db_path)
            storage = SQLiteStorage(
                connection=connection,
                ttl=None,  # No expiration for festival data
            )

            # Use cached client
            self.client = CacheClient(
                controller=Controller(
                    allow_stale=True, force_cache=not self.force_refresh
                ),
                storage=storage,
                timeout=30.0,
                follow_redirects=True,
            )

    def _setup_cinema_validation(self, config_dir: Path) -> None:
        """Set up cinema validation from config.

        Args:
            config_dir: Directory containing cinemas.yaml
        """
        try:
            # Load cinema config
            data_dir = config_dir.parent / "data"  # Dummy data_dir, not used here
            loader = ConfigLoader(config_dir, data_dir)
            cinema_config = loader.load_cinema_config()

            # Build and set normalization map from cinema aliases
            if cinema_config.cinema_aliases:
                normalization_map = build_normalization_map(
                    cinema_config.cinema_aliases
                )
                Film.set_normalization_map(normalization_map)

                # Store known cinema names (canonical + aliases) for parsing
                for canonical, aliases in cinema_config.cinema_aliases.items():
                    self.known_cinemas.add(canonical.lower())
                    for alias in aliases:
                        self.known_cinemas.add(alias.lower())

                logger.info(
                    "Cinema normalization enabled",
                    canonical_names=sorted(cinema_config.cinema_aliases.keys()),
                    total_aliases=len(normalization_map),
                )
            else:
                logger.warning("No cinema aliases found in config")

            # Extract valid cinemas
            valid_cinemas = loader.get_valid_cinemas(cinema_config)

            if valid_cinemas:
                # Set valid cinemas on Film model for validation
                Film.set_valid_cinemas(valid_cinemas)
                logger.info(
                    "Cinema validation enabled", valid_cinemas=sorted(valid_cinemas)
                )
            else:
                logger.warning("No cinemas found in config - validation disabled")

        except Exception as e:
            logger.error("Failed to load cinema config", error=str(e))
            logger.warning("Cinema validation disabled due to config load error")

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
            # Fetch the programme page
            programme_url = f"{self.BASE_URL}/{self.language}/program"

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
                    from_cache = film_response.extensions.get("from_cache", False)

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

                except Exception as e:
                    logger.error("Error scraping film page", url=film_url, error=str(e))
                    continue

        except httpx.HTTPError as e:
            logger.error("HTTP error while scraping", error=str(e), exc_info=True)
        except Exception as e:
            logger.error("Error while scraping", error=str(e), exc_info=True)

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

        # Look for links that point to film pages
        # Filmfrasor.no film pages typically have URLs like /no/film/film-title
        for link in soup.find_all("a", href=True):
            href = link["href"]

            # Check if this looks like a film page link
            if f"/{self.language}/film/" in href:
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

            # Extract country
            country = self._extract_country(soup)

            # Extract screening times
            # Look for elements that contain screening information
            screening_elements = self._find_screening_elements(soup)

            for screening_elem in screening_elements:
                try:
                    screening_info = self._parse_screening_element(screening_elem)

                    if screening_info:
                        start_time, end_time, cinema, auditorium, special_notes = (
                            screening_info
                        )

                        try:
                            screening = Film(
                                title=title,
                                country=country,
                                start_time=start_time,
                                end_time=end_time,
                                cinema=cinema,
                                auditorium=auditorium,
                                special_notes=special_notes,
                            )
                            screenings.append(screening)
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

                except Exception as e:
                    logger.warning(
                        "Error parsing screening element",
                        title=title,
                        error=str(e),
                    )
                    continue

        except Exception as e:
            print(f"  Error parsing film page {url}: {e}")

        return screenings

    def _extract_title(self, soup: BeautifulSoup) -> Optional[str]:
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

    def _extract_country(self, soup: BeautifulSoup) -> str:
        """Extract country information from the page."""
        # Look for common patterns for country information
        country_keywords = [
            "land:",
            "country:",
            "produksjonsland:",
            "production country:",
        ]

        for text in soup.find_all(string=True):
            text_lower = text.lower().strip()
            for keyword in country_keywords:
                if keyword in text_lower:
                    # Extract the country after the keyword
                    country = text.split(":", 1)[-1].strip()
                    if country:
                        return country

        return "Unknown"

    def _find_screening_elements(self, soup: BeautifulSoup) -> list:
        """Find elements that contain screening information.

        Filmfrasor.no uses a structure where each screening is in a div
        that contains three child divs:
        1. Date (e.g., "lør. 08.11")
        2. Time range (e.g., "13:15 - 14:53")
        3. Cinema (e.g., "Vika 3")
        """
        screening_elements = []

        # Look for div elements that have exactly 3 direct div children
        # and match the screening pattern
        for container in soup.find_all("div", attrs={"class": "event-shows-container"}):
            # Get direct div children only (not nested)
            direct_divs = [child for child in container.children if child.name == "div"]

            # We want exactly 3 direct children (date, time, cinema)
            if len(direct_divs) == 3:
                # Check if they match the screening pattern
                div_texts = [d.get_text(strip=True) for d in direct_divs]

                # Pattern check:
                # 1st div: date like "lør. 08.11"
                # 2nd div: time range like "13:15 - 14:53"
                # 3rd div: cinema name like "Vika 3"

                has_date = re.search(r"\d{1,2}\.\d{1,2}", div_texts[0])
                has_time_range = re.search(
                    r"\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2}", div_texts[1]
                )

                if has_date and has_time_range:
                    # This looks like a valid screening element
                    screening_elements.append(container)

        return screening_elements

    def _parse_screening_element(self, element) -> Optional[tuple]:
        """Parse a screening element to extract time, cinema, etc.

        The element contains three child divs:
        1. Date (e.g., "lør. 08.11")
        2. Time range (e.g., "13:15 - 14:53")
        3. Cinema with auditorium (e.g., "Vika 3")

        Returns:
            Tuple of (start_time, end_time, cinema, auditorium, special_notes) or None
        """
        # Get the three direct child divs
        direct_divs = [child for child in element.children if child.name == "div"]

        if len(direct_divs) != 3:
            return None
        print([x.get_text(strip=True) for x in direct_divs])

        date_text = direct_divs[0].get_text(strip=True)
        time_text = direct_divs[1].get_text(strip=True)
        cinema_text = direct_divs[2].get_text(strip=True)

        # Parse date: "lør. 08.11" -> day 08, month 11
        date_match = re.search(r"(\d{1,2})\.(\d{1,2})", date_text)
        if not date_match:
            return None

        day = int(date_match.group(1))
        month = int(date_match.group(2))

        # Parse time range: "13:15 - 14:53"
        time_match = re.search(r"(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})", time_text)
        if not time_match:
            return None

        start_hour = int(time_match.group(1))
        start_minute = int(time_match.group(2))
        end_hour = int(time_match.group(3))
        end_minute = int(time_match.group(4))

        # Use specified year or current year
        year = self.year

        try:
            start_time = datetime(year, month, day, start_hour, start_minute)
            end_time = datetime(year, month, day, end_hour, end_minute)
        except ValueError:
            return None

        # Extract cinema name and auditorium
        # Pattern: "Vika 3" -> cinema="Vika", auditorium="3"
        cinema, auditorium = self._split_cinema_and_auditorium(cinema_text.strip())

        # Extract special notes from the parent container
        full_text = element.get_text(" ", strip=True)
        special_notes = self._extract_special_notes(full_text)

        return (start_time, end_time, cinema, auditorium, special_notes)

    def _split_cinema_and_auditorium(
        self, cinema_text: str
    ) -> tuple[str, Optional[str]]:
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

    def _extract_special_notes(self, text: str) -> Optional[str]:
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
