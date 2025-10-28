"""CLI commands for setting custom preference weights on films."""

from typing import Optional
import typer
from rich.console import Console
from rich.prompt import Prompt
from iterfzf import iterfzf

from ..config import ConfigLoader
from ..models import FilmWeight
from .._logging import get_logger


console = Console()
logger = get_logger(__name__)
app = typer.Typer()


@app.command()
def set_weight(
    search: Optional[str] = typer.Option(
        None,
        "--search",
        "-s",
        help="Initial search term to filter films",
    ),
) -> None:
    """Set a custom weight for a film or specific screening using interactive fuzzy finder."""
    loader = ConfigLoader()

    # Load all films
    film_list = loader.load_films()

    # Load existing custom weight overrides
    config = loader.load_config()
    weights = config.films.weights

    # Build lookup maps for existing overrides
    # Screening-level: (title, start_time) -> weight
    screening_override_map = {
        (w.title, w.start_time): w.weight for w in weights if w.start_time is not None
    }

    # Film-level: title -> weight
    film_override_map = {w.title: w.weight for w in weights if w.start_time is None}

    # Filter by search term if provided
    films = film_list.films
    if search:
        search_lower = search.lower()
        films = [f for f in films if search_lower in f.title.lower()]

    if not films:
        console.print("[yellow]No films found matching your search.[/yellow]")
        return

    # Sort by date and time
    films.sort(key=lambda f: (f.date, f.start_time))

    # Create formatted strings and mapping
    film_strings = []
    film_map = {}

    for film in films:
        date_str = film.start_time.strftime("%a %d/%m")
        time_str = film.start_time.strftime("%H:%M")
        cinema_str = film.cinema
        if film.auditorium:
            cinema_str += f" {film.auditorium}"

        # Check if this screening has a custom weight override
        screening_key = (film.title, film.start_time)
        if screening_key in screening_override_map:
            weight_display = (
                f"{screening_override_map[screening_key]:+.1f} [custom screening]"
            )
        elif film.title in film_override_map:
            weight_display = f"{film_override_map[film.title]:+.1f} [custom film]"
        else:
            weight_display = f"{film.preference_weight:+.1f}"

        # Create a formatted string for fzf display
        formatted = f"{film.title:<60} │ {date_str} {time_str} │ {cinema_str:<25} │ Weight: {weight_display}"
        film_strings.append(formatted)
        film_map[formatted] = film

    # Use iterfzf for interactive selection
    try:
        selected = iterfzf(
            film_strings,
            prompt="Select a film screening > ",
            query=search or "",
        )
    except KeyboardInterrupt:
        console.print("\n[yellow]Selection cancelled.[/yellow]")
        return

    if not selected:
        console.print("[yellow]No film selected.[/yellow]")
        return

    selected_film = film_map[selected]

    # Ask user if they want to set weight for screening or film
    console.print()
    level_choice = Prompt.ask(
        "Set weight for",
        choices=["screening", "film"],
        default="screening",
    )

    is_film_level = level_choice == "film"

    # Get current weight based on level
    if is_film_level:
        # Film-level weight
        current_weight = film_override_map.get(
            selected_film.title, selected_film.preference_weight
        )
        weight_type = (
            "custom film" if selected_film.title in film_override_map else "scraped"
        )
    else:
        # Screening-level weight
        screening_key = (selected_film.title, selected_film.start_time)
        if screening_key in screening_override_map:
            current_weight = screening_override_map[screening_key]
            weight_type = "custom screening"
        elif selected_film.title in film_override_map:
            current_weight = film_override_map[selected_film.title]
            weight_type = "custom film"
        else:
            current_weight = selected_film.preference_weight
            weight_type = "scraped"

    # Ask for weight
    weight = typer.prompt(
        f"Enter custom weight for '{selected_film.title}' (current: {current_weight:+.1f} [{weight_type}])",
        type=float,
    )

    # Find existing override to update
    existing_idx = None
    for i, w in enumerate(weights):
        if is_film_level:
            # For film-level, match by title only and no start_time
            if w.title == selected_film.title and w.start_time is None:
                existing_idx = i
                break
        else:
            # For screening-level, match by title and start_time
            if (
                w.title == selected_film.title
                and w.start_time == selected_film.start_time
            ):
                existing_idx = i
                break

    # Create weight override
    film_weight = FilmWeight(
        title=selected_film.title,
        start_time=None if is_film_level else selected_film.start_time,
        weight=weight,
    )

    # Update or add
    if existing_idx is not None:
        weights[existing_idx] = film_weight
        level_str = "all screenings" if is_film_level else "this screening"
        console.print(
            f"[green]Updated weight for '{selected_film.title}' ({level_str}) to {weight:+.1f}[/green]"
        )
    else:
        weights.append(film_weight)
        level_str = "all screenings" if is_film_level else "this screening"
        console.print(
            f"[green]Set weight for '{selected_film.title}' ({level_str}) to {weight:+.1f}[/green]"
        )

    # Save
    loader.save_preferences(config.films)

    if not is_film_level:
        date_str = selected_film.start_time.strftime("%a %d/%m at %H:%M")
        console.print(f"[dim]({date_str} at {selected_film.cinema})[/dim]")
