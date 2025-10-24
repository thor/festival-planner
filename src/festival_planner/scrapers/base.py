"""Base interface for festival scrapers."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from ..models import FilmList


class BaseScraper(ABC):
    """Abstract base class for festival scrapers."""

    def __init__(self, cache_dir: Optional[Path] = None):
        """Initialize the scraper.

        Args:
            cache_dir: Directory to cache scraped data
        """
        self.cache_dir = cache_dir

    @abstractmethod
    def scrape(self) -> FilmList:
        """Scrape the festival programme and return a list of films.

        Returns:
            FilmList containing all scraped films
        """
        pass

    @abstractmethod
    def get_festival_name(self) -> str:
        """Get the name of the festival.

        Returns:
            Festival name as a string
        """
        pass
