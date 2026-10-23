"""CLI commands for solving the festival scheduling optimization problem."""

import datetime
import zoneinfo
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import typer
from rich import box
from rich.console import Console
from rich.table import Table
from rich.text import Text

from ..adapters.json_files.solve_request import (
    UnsupportedFormatError,
    dump_solve_request,
    load_solve_request,
)
from ..adapters.solver.cpsat import CpSatScheduleSolver
from ..adapters.yaml_files.solve_request import build_solve_request
from ..config import ConfigLoader
from ..domain.programme import ProgrammeEntry, Screening, Venue
from ..domain.solving import SolveRequest, SolveResult

console = Console()
app = typer.Typer()


@dataclass(frozen=True)
class ScheduledRow:
    """A scheduled Screening with everything needed to display it.

    `arrival_time`, `start` and `end` are festival-local.
    """

    screening: Screening
    entry: ProgrammeEntry
    venue: Venue
    arrival_time: datetime.datetime
    start: datetime.datetime
    end: datetime.datetime
    weight: float


def _scheduled_rows(request: SolveRequest, result: SolveResult) -> list[ScheduledRow]:
    local = zoneinfo.ZoneInfo(request.time_zone)
    screenings = {s.id: s for s in request.screenings}
    entries = {e.id: e for e in request.programme_entries}
    venues = {v.id: v for v in request.venues}
    rows = []
    for scheduled in result.scheduled:
        screening = screenings[scheduled.screening_id]
        rows.append(
            ScheduledRow(
                screening=screening,
                entry=entries[screening.programme_entry_id],
                venue=venues[screening.venue_id],
                arrival_time=scheduled.arrival_time.astimezone(local),
                start=screening.start_time.astimezone(local),
                end=screening.end_time.astimezone(local),
                weight=scheduled.weight,
            )
        )
    return rows


def _link(text: str, url: str | None) -> Text:
    """Format text as a clickable link if a URL is available."""
    if url:
        return Text(text, style=f"link {url}")
    return Text(text)


def _parse_dates(dates: str) -> tuple[datetime.date, datetime.date]:
    """Parse `YYYY-MM-DD:YYYY-MM-DD` or a single `YYYY-MM-DD`."""
    start, _, end = dates.partition(":")
    return datetime.date.fromisoformat(start), datetime.date.fromisoformat(end or start)


def _apply_overrides(
    request: SolveRequest,
    *,
    dates: str | None,
    buffer_time: int | None,
    time_limit: int | None,
) -> SolveRequest:
    preferences = request.preferences
    if buffer_time is not None:
        preferences = preferences.model_copy(update={"buffer_minutes": buffer_time})
    if dates:
        start, end = _parse_dates(dates)
        preferences = preferences.model_copy(
            update={"start_date": start, "end_date": end}
        )
    request = request.model_copy(update={"preferences": preferences})
    if time_limit is not None:
        request = request.model_copy(update={"time_limit_seconds": time_limit})
    return request


def _load_request_from_yaml() -> SolveRequest:
    loader = ConfigLoader()
    console.print("[bold blue]Loading configuration...[/bold blue]")
    config = loader.load_config()
    films = loader.load_films().films
    console.print(f"[green]Loaded {len(films)} film screenings[/green]")
    return build_solve_request(films, config)


@app.command()
def solve(
    dates: Annotated[
        str | None,
        typer.Option(
            "--dates",
            "-d",
            help="Date range filter (format: YYYY-MM-DD:YYYY-MM-DD or single date)",
        ),
    ] = None,
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Output file for schedule",
        ),
    ] = None,
    time_limit: Annotated[
        int | None,
        typer.Option(
            "--time-limit",
            "-t",
            help="Solver time limit in seconds (default: 60, or the request's own)",
        ),
    ] = None,
    buffer_time: Annotated[
        int | None,
        typer.Option(
            "--buffer",
            "-b",
            help="Buffer time before each film in minutes",
        ),
    ] = None,
    request_file: Annotated[
        Path | None,
        typer.Option(
            "--request",
            help="Solve a JSON solve request instead of the YAML configuration",
        ),
    ] = None,
    export_request: Annotated[
        Path | None,
        typer.Option(
            "--export-request",
            help="Write the solve request as JSON before solving",
        ),
    ] = None,
) -> None:
    """Solve the scheduling optimization problem."""
    if request_file:
        try:
            request = load_solve_request(request_file)
        except UnsupportedFormatError as e:
            console.print(f"[bold red]{e}[/bold red]", soft_wrap=True)
            raise typer.Exit(code=2) from e
        console.print(f"[green]Loaded solve request from {request_file}[/green]")
    else:
        request = _load_request_from_yaml()
    request = _apply_overrides(
        request, dates=dates, buffer_time=buffer_time, time_limit=time_limit
    )

    if export_request:
        dump_solve_request(request, export_request)
        console.print(f"[green]Solve request saved to {export_request}[/green]")

    console.print("[bold blue]Solving optimization problem...[/bold blue]")
    result = CpSatScheduleSolver().solve(request)

    if not result.is_solved:
        console.print(f"[bold red]No schedule found ({result.status})[/bold red]")
        for reason in result.reasons:
            console.print(f"  - {reason}")
        raise typer.Exit(code=1)

    rows = _scheduled_rows(request, result)
    console.print("[bold green]Solution found![/bold green]")
    console.print(f"Status: {result.status}")
    console.print(f"Objective value: {result.objective:.2f}")
    console.print(f"Solve time: {result.wall_time_seconds:.2f}s")
    console.print(f"Films scheduled: {len(rows)}")

    display_film_overview(request, rows)
    display_schedule(rows)

    if output:
        save_schedule_to_file(rows, output)
        console.print(f"[green]Schedule saved to {output}[/green]")


def _is_not_relevant(
    request: SolveRequest, entry: ProgrammeEntry, screenings: list[Screening]
) -> bool:
    """Whether the film is Seen or excluded, so missing it is no loss."""
    return (
        entry.film_id in request.seen_films
        or entry.id in request.excluded_programme_entries
        or all(s.id in request.excluded_screenings for s in screenings)
    )


def display_film_overview(request: SolveRequest, rows: list[ScheduledRow]) -> None:
    """Display every Programme Entry with whether and when it is scheduled."""
    screenings_by_entry: defaultdict[str, list[Screening]] = defaultdict(list)
    for screening in request.screenings:
        screenings_by_entry[screening.programme_entry_id].append(screening)
    row_by_entry = {row.entry.id: row for row in rows}
    venues = {v.id: v for v in request.venues}
    not_relevant = {
        entry.id
        for entry in request.programme_entries
        if entry.id not in row_by_entry
        and _is_not_relevant(request, entry, screenings_by_entry[entry.id])
    }
    missed = len(request.programme_entries) - len(rows) - len(not_relevant)

    console.print("\n[bold]Festival Overview[/bold]")
    console.print(f"Unique films: {len(request.programme_entries)}")
    console.print(f"Total screenings: {len(request.screenings)}")
    console.print(f"Films scheduled: [green]{len(rows)}[/green]")
    console.print(f"Films missed: [red]{missed}[/red]")
    console.print(f"Films not relevant (seen or excluded): {len(not_relevant)}")
    console.print()

    table = Table(title="All Films in Festival", box=box.MINIMAL)
    table.add_column("Status", justify="center", style="bold", width=8, no_wrap=True)
    table.add_column("Title", style="bold")
    table.add_column("Year", justify="center")
    table.add_column("Country", max_width=15, overflow="ellipsis", no_wrap=True)
    table.add_column("Screenings", justify="center")
    table.add_column("Date", style="cyan")
    table.add_column("Time", style="green")
    table.add_column("Venue", style="yellow")
    table.add_column("Events", style="dim")

    entries = sorted(request.programme_entries, key=lambda e: e.title)
    for idx, entry in enumerate(entries):
        row = row_by_entry.get(entry.id)
        screenings = screenings_by_entry[entry.id]
        shown = row.screening if row else screenings[0] if screenings else None
        status = Text.assemble(
            "✅" if row else "🚫" if entry.id in not_relevant else "❌",
            " ",
            _link("🎬", entry.url),
            " ",
            _link("🎫", shown.ticket_url if shown else None),
        )
        if row:
            screening = row.screening
            date_str = row.start.strftime("%a %d/%m")
            time_str = row.start.strftime("%H:%M")
            venue_str = venues[screening.venue_id].name + (
                f" {screening.auditorium}" if screening.auditorium else ""
            )
            events_str = "; ".join(e.description for e in screening.events)
        else:
            date_str = time_str = venue_str = events_str = ""

        table.add_row(
            status,
            _link(entry.title, entry.url),
            str(entry.year) if entry.year else "",
            entry.country or "",
            str(len(screenings)),
            date_str,
            time_str,
            venue_str,
            events_str,
            style="dim" if idx % 2 == 1 else None,
        )

    console.print(table)
    console.print()


def _rows_by_date(
    rows: list[ScheduledRow],
) -> dict[datetime.date, list[ScheduledRow]]:
    by_date: defaultdict[datetime.date, list[ScheduledRow]] = defaultdict(list)
    for row in rows:
        by_date[row.start.date()].append(row)
    return dict(sorted(by_date.items()))


def display_schedule(rows: list[ScheduledRow]) -> None:
    """Display the schedule as one table per day."""
    if not rows:
        console.print("[yellow]No films in schedule[/yellow]")
        return

    max_title_length = max(len(row.entry.title) for row in rows)

    for day, day_rows in _rows_by_date(rows).items():
        table = Table(title=f"Schedule for {day}", box=box.MINIMAL)
        table.add_column("Arrive", style="cyan")
        table.add_column("Start", style="green")
        table.add_column("End", style="red")
        table.add_column("Film", style="bold", min_width=max_title_length)
        table.add_column("Year", max_width=4, overflow="crop", no_wrap=True)
        table.add_column("Venue", style="yellow")
        table.add_column("Auditorium", style="magenta", no_wrap=True)
        table.add_column("Country", max_width=10, overflow="ellipsis", no_wrap=True)
        table.add_column("Weight", justify="right")

        for row in day_rows:
            screening = row.screening
            year_str = f"{row.entry.year:4d}" if row.entry.year else "    "
            table.add_row(
                row.arrival_time.strftime("%H:%M"),
                _link(row.start.strftime("%H:%M"), screening.ticket_url),
                row.end.strftime("%H:%M"),
                row.entry.title,
                _link(year_str, row.entry.url),
                row.venue.name,
                screening.auditorium or "",
                row.entry.country or "",
                f"{row.weight:+.1f}",
            )

        console.print(table)
        console.print()


def save_schedule_to_file(rows: list[ScheduledRow], filepath: Path) -> None:
    """Save the schedule as Markdown."""
    with open(filepath, "w") as f:
        f.write("# Festival Schedule\n\n")

        for day, day_rows in _rows_by_date(rows).items():
            f.write(f"## {day}\n\n")

            for row in day_rows:
                screening = row.screening
                title_md = (
                    f"[{row.entry.title}]({row.entry.url})"
                    if row.entry.url
                    else row.entry.title
                )
                f.write(f"### {title_md}\n")
                f.write(f"- **Arrive**: {row.arrival_time.strftime('%H:%M')}\n")
                f.write(f"- **Start**: {row.start.strftime('%H:%M')}\n")
                f.write(f"- **End**: {row.end.strftime('%H:%M')}\n")
                f.write(f"- **Venue**: {row.venue.name}\n")
                if screening.auditorium:
                    f.write(f"- **Auditorium**: {screening.auditorium}\n")
                if row.entry.country:
                    f.write(f"- **Country**: {row.entry.country}\n")
                f.writelines(
                    f"- **Event**: {event.description}\n" for event in screening.events
                )
                f.write(f"- **Weight**: {row.weight:+.1f}\n")
                f.write("\n")

            f.write("\n")


if __name__ == "__main__":
    app()
