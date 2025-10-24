#!/usr/bin/env python3
"""Standalone script to scrape Filmfrasor.no programme."""

import sys
import argparse
from pathlib import Path
from datetime import datetime

# Add parent directory to path to import festival_planner
sys.path.insert(0, str(Path(__file__).parent.parent))

from festival_planner.scrapers import FilmfrasorScraper
from festival_planner.config import ConfigLoader


def main():
    """Main function to scrape and cache Filmfrasor programme."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Scrape Filmfrasor.no programme")
    parser.add_argument(
        "--refresh",
        "-r",
        action="store_true",
        help="Force refresh: bypass HTTP cache and fetch fresh data",
    )
    parser.add_argument(
        "--year",
        "-y",
        type=int,
        default=datetime.now().year,
        help="Festival year (default: current year)",
    )
    args = parser.parse_args()
    
    # Setup paths
    project_root = Path(__file__).parent.parent.parent
    config_dir = project_root / "config"
    data_dir = project_root / "data"
    
    # Ensure data directory exists
    data_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Scraping Filmfrasor.no for year {args.year}...")
    print(f"Output directory: {data_dir}")
    if args.refresh:
        print("Force refresh enabled - fetching fresh data")
    
    # Initialize scraper
    scraper = FilmfrasorScraper(
        cache_dir=data_dir,
        year=args.year,
        force_refresh=args.refresh
    )
    
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
            
            auditoriums = set(f"{film.cinema} {film.auditorium}" for film in film_list.films)
            print(f"  Total auditoriums: {len(auditoriums)}")
            
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
