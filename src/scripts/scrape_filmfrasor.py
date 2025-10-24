#!/usr/bin/env python3
"""Standalone script to scrape Filmfrasor.no programme."""

import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path to import festival_planner
sys.path.insert(0, str(Path(__file__).parent.parent))

from festival_planner.scrapers import FilmfrasorScraper
from festival_planner.config import ConfigLoader


def main():
    """Main function to scrape and cache Filmfrasor programme."""
    # Setup paths
    project_root = Path(__file__).parent.parent.parent
    config_dir = project_root / "config"
    data_dir = project_root / "data"

    # Ensure data directory exists
    data_dir.mkdir(parents=True, exist_ok=True)

    print(f"Scraping Filmfrasor.no for year {datetime.now().year}...")
    print(f"Output directory: {data_dir}")

    # Initialize scraper
    scraper = FilmfrasorScraper(cache_dir=data_dir)

    # Scrape programme
    try:
        film_list = scraper.scrape()
        print(f"✓ Successfully scraped {len(film_list.films)} films")

        # Save to YAML
        loader = ConfigLoader(config_dir, data_dir)
        output_file = data_dir / "films.yaml"
        loader.save_films(film_list, output_file)

        print(f"✓ Saved to {output_file}")

        # Display summary
        if film_list.films:
            print("\nSummary:")
            cinemas = set(film.cinema for film in film_list.films)
            print(f"  Cinemas: {len(cinemas)}")
            print(f"  Cinema names: {', '.join(sorted(cinemas))}")

            dates = set(film.date for film in film_list.films)
            print(f"  Dates: {len(dates)}")
            if dates:
                print(f"  Date range: {min(dates)} to {max(dates)}")

        return 0

    except Exception as e:
        print(f"✗ Error: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
