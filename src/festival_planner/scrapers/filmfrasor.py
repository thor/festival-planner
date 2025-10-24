"""Scraper for filmfrasor.no film festival."""

import re
from datetime import datetime
from pathlib import Path
from typing import Optional
import httpx
from bs4 import BeautifulSoup

from ..models import Film, FilmList
from .base import BaseScraper


class FilmfrasorScraper(BaseScraper):
    """Scraper for the Filmfrasor.no festival website."""

    BASE_URL = "https://filmfrasor.no"

    def __init__(self, cache_dir: Optional[Path] = None, year: Optional[int] = None):
        """Initialize the Filmfrasor scraper.

        Args:
            cache_dir: Directory to cache scraped data
            year: Festival year (defaults to current year)
        """
        super().__init__(cache_dir)
        self.year = year or datetime.now().year

    def get_festival_name(self) -> str:
        """Get the name of the festival."""
        return f"Films fra Sør {self.year}"

    def scrape(self) -> FilmList:
        """Scrape the Filmfrasor programme.

        Returns:
            FilmList containing all scraped films
        """
        films = []

        try:
            # Fetch the programme page
            programme_url = f"{self.BASE_URL}/no/program"

            with httpx.Client(timeout=30.0, follow_redirects=True) as client:
                response = client.get(programme_url)
                response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            # Parse the HTML structure to extract film information
            # Note: This is a placeholder implementation that needs to be adapted
            # to the actual HTML structure of filmfrasor.no
            films = self._parse_programme_page(soup)

        except httpx.HTTPError as e:
            print(f"HTTP error while scraping: {e}")
        except Exception as e:
            print(f"Error while scraping: {e}")

        return FilmList(films=films)

    def _parse_programme_page(self, soup: BeautifulSoup) -> list[Film]:
        """Parse the programme page HTML to extract film information.

        This method needs to be adapted to the actual HTML structure of the website.

        Args:
            soup: BeautifulSoup object of the programme page

        Returns:
            List of Film objects
        """
        films = []

        # Look for common HTML patterns for programme listings
        # This is a flexible implementation that tries multiple patterns

        # Pattern 1: Look for article or section elements with film classes
        film_elements = soup.find_all(
            ["article", "div", "section"],
            class_=re.compile(r"film|screening|event|programme", re.I),
        )

        if not film_elements:
            # Pattern 2: Look for list items
            film_elements = soup.find_all(
                "li", class_=re.compile(r"film|screening|event", re.I)
            )

        for element in film_elements:
            try:
                film = self._parse_film_element(element)
                if film:
                    films.append(film)
            except Exception as e:
                # Skip problematic elements
                print(f"Error parsing film element: {e}")
                continue

        return films

    def _parse_film_element(self, element) -> Optional[Film]:
        """Parse a single film element.

        Args:
            element: BeautifulSoup element containing film information

        Returns:
            Film object or None if parsing fails
        """
        # Extract title
        title_elem = element.find(
            ["h1", "h2", "h3", "h4"], class_=re.compile(r"title|name", re.I)
        )
        if not title_elem:
            title_elem = element.find(["h1", "h2", "h3", "h4"])

        if not title_elem:
            return None

        title = title_elem.get_text(strip=True)

        # Extract country
        country_elem = element.find(class_=re.compile(r"country|origin|nation", re.I))
        country = country_elem.get_text(strip=True) if country_elem else "Unknown"

        # Extract time information
        time_elem = element.find(class_=re.compile(r"time|date|when|schedule", re.I))
        if not time_elem:
            time_elem = element.find("time")

        if not time_elem:
            return None

        # Try to parse datetime from various formats
        time_text = time_elem.get_text(strip=True)
        datetime_attr = time_elem.get("datetime")

        start_time, end_time = self._parse_time_info(time_text, datetime_attr)

        if not start_time or not end_time:
            return None

        # Extract cinema/venue
        venue_elem = element.find(
            class_=re.compile(r"venue|cinema|location|place", re.I)
        )
        cinema = venue_elem.get_text(strip=True) if venue_elem else "Unknown"

        # Extract special notes
        notes_elem = element.find(
            class_=re.compile(r"note|special|tag|event-type", re.I)
        )
        special_notes = notes_elem.get_text(strip=True) if notes_elem else None

        return Film(
            title=title,
            country=country,
            start_time=start_time,
            end_time=end_time,
            cinema=cinema,
            special_notes=special_notes,
        )

    def _parse_time_info(
        self, time_text: str, datetime_attr: Optional[str]
    ) -> tuple[Optional[datetime], Optional[datetime]]:
        """Parse time information from text or datetime attribute.

        Args:
            time_text: Text content of time element
            datetime_attr: datetime attribute value (if present)

        Returns:
            Tuple of (start_time, end_time) or (None, None) if parsing fails
        """
        # Try to parse from datetime attribute first
        if datetime_attr:
            try:
                start_time = datetime.fromisoformat(
                    datetime_attr.replace("Z", "+00:00")
                )
                # Assume 2 hour duration if end time not specified
                end_time = start_time.replace(hour=start_time.hour + 2)
                return start_time, end_time
            except ValueError:
                pass

        # Try to parse from text
        # Common patterns: "15:00 - 17:00", "2024-09-15 18:00", etc.

        # Pattern: "HH:MM - HH:MM"
        time_range = re.search(r"(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})", time_text)
        if time_range:
            start_hour, start_min, end_hour, end_min = time_range.groups()

            # Need a date - try to find it in the text or use current year
            date_match = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", time_text)
            if date_match:
                year, month, day = date_match.groups()
                start_time = datetime(
                    int(year), int(month), int(day), int(start_hour), int(start_min)
                )
                end_time = datetime(
                    int(year), int(month), int(day), int(end_hour), int(end_min)
                )
                return start_time, end_time

        # If we can't parse, return None
        return None, None
