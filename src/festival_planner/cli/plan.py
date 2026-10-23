"""Plan a Festival as the local User: Drafts, Schedules, Tickets and Seen."""

import contextlib
import datetime
import getpass
import zoneinfo
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import typer
import yaml
from rich.console import Console
from rich.markup import escape
from sqlalchemy import Engine

from ..adapters.in_process.jobs import ImmediateJobRunner
from ..adapters.in_process.notifications import NullDraftSolvedNotifier
from ..adapters.json_files.solve_request import dump_solve_request
from ..adapters.solver.cpsat import CpSatScheduleSolver
from ..adapters.sqlalchemy.unit_of_work import SqlAlchemyUnitOfWork
from ..domain.change_sets import ChangeSet, InvalidChangeSetError
from ..domain.drafts import DraftStatus
from ..domain.planner import DraftView, Planner, PlanningError
from ..domain.planning import Ticket
from ..domain.programme import ScreeningId
from ..domain.users import LOCAL_ISSUER, user_for
from .db import DATABASE_OPTION, open_database

app = typer.Typer(
    name="plan", help="Plan a Festival: Drafts, Schedules, Tickets and Seen."
)
ticket_app = typer.Typer(name="ticket", help="Record Tickets you hold.")
seen_app = typer.Typer(name="seen", help="Mark Films Seen, or correct inferred Seen.")
app.add_typer(ticket_app, name="ticket")
app.add_typer(seen_app, name="seen")
console = Console()


@dataclass
class _Session:
    planner: Planner
    user_id: str
    engine: Engine

    def unit_of_work(self) -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(self.engine)


@contextlib.contextmanager
def _session(database: str | None) -> Iterator[_Session]:
    """The Planner acting as the local User; planning errors become exit code 1."""
    engine = open_database(database)
    try:
        planner = Planner(
            lambda: SqlAlchemyUnitOfWork(engine),
            CpSatScheduleSolver(),
            ImmediateJobRunner(),
            NullDraftSolvedNotifier(),
            clock=lambda: datetime.datetime.now(datetime.UTC),
        )
        planner.resume_solving()
        user = user_for(SqlAlchemyUnitOfWork(engine), LOCAL_ISSUER, getpass.getuser())
        yield _Session(planner, user.id, engine)
    except InvalidChangeSetError as e:
        for problem in e.problems:
            console.print(
                f"[bold red]{escape(problem.message)}[/bold red]", soft_wrap=True
            )
        raise typer.Exit(code=1) from e
    except PlanningError as e:
        console.print(f"[bold red]{escape(str(e))}[/bold red]", soft_wrap=True)
        raise typer.Exit(code=1) from e
    finally:
        engine.dispose()


def _load_change_set(path: Path | None) -> ChangeSet:
    if path is None:
        return ChangeSet()
    data = yaml.safe_load(path.read_text())  # JSON is YAML too
    return ChangeSet.model_validate(
        data if isinstance(data, dict) else {"items": data or []}
    )


def _describe(
    s: _Session, festival_id: str, screening_ids: Iterable[ScreeningId]
) -> dict[ScreeningId, str]:
    """One line per Screening: festival-local day and time, title and Venue."""
    with s.unit_of_work() as uow:
        festival = uow.festivals.by_id(festival_id)
        zone = zoneinfo.ZoneInfo(festival.time_zone) if festival else datetime.UTC
        screenings = uow.programme.screenings_by_id(list(screening_ids))
        titles = {
            e.id: e.title
            for e in uow.programme.entries_by_id(
                {x.programme_entry_id for x in screenings}
            )
        }
        venues = {v.id: v.name for v in uow.venues.all()}
    return {
        x.id: (
            f"{x.start_time.astimezone(zone):%Y-%m-%d %a %H:%M}-"
            f"{x.end_time.astimezone(zone):%H:%M}  "
            f"{titles.get(x.programme_entry_id, x.programme_entry_id)}  "
            f"({venues.get(x.venue_id, x.venue_id)})  [{x.id}]"
        )
        for x in screenings
    }


def _by_time(
    lines: dict[ScreeningId, str], ids: Iterable[ScreeningId]
) -> list[ScreeningId]:
    """The ids in chronological order (lines start with the local date and time);
    an unknown id stands for itself."""
    return sorted(ids, key=lambda i: (lines.get(i, i), i))


def _print_view(s: _Session, view: DraftView) -> None:
    draft = view.draft
    stale = " (stale)" if view.stale else ""
    style = {
        DraftStatus.READY: "green",
        DraftStatus.SOLVING: "yellow",
    }.get(draft.status, "red")
    console.print(
        f"[{style}]Draft {draft.id}: {draft.status}{stale}[/{style}]", soft_wrap=True
    )
    for reason in draft.reasons:
        console.print(f"  {escape(reason)}", soft_wrap=True)
    for note in draft.notes:
        console.print(f"  Note: {escape(note)}", soft_wrap=True)
    if view.diff is None:
        return
    d = view.diff
    console.print(
        f"  +{len(d.added)} −{len(d.removed)}  score {d.score_delta:+.2f}",
        soft_wrap=True,
    )
    lines = _describe(s, draft.festival_id, d.added | d.removed | d.dropped_tickets)
    for sign, ids in (("+", d.added), ("−", d.removed)):
        for i in _by_time(lines, ids):
            console.print(f"  {sign} {escape(lines.get(i, i))}", soft_wrap=True)
    for i in _by_time(lines, d.dropped_tickets):
        console.print(
            f"  [yellow]Ticket dropped: {escape(lines.get(i, i))}[/yellow]",
            soft_wrap=True,
        )


@app.command()
def draft(
    festival: str = typer.Argument(..., help="Festival slug"),
    change_set: Annotated[
        Path | None,
        typer.Option("--change-set", help="YAML or JSON list of change-set items"),
    ] = None,
    database: str | None = DATABASE_OPTION,
) -> None:
    """Create and solve a Draft."""
    with _session(database) as s:
        _print_view(
            s, s.planner.create_draft(s.user_id, festival, _load_change_set(change_set))
        )


@app.command()
def drafts(
    festival: str = typer.Argument(..., help="Festival slug"),
    database: str | None = DATABASE_OPTION,
) -> None:
    """List the Drafts of a Festival."""
    with _session(database) as s:
        views = s.planner.drafts(s.user_id, festival)
        if not views:
            console.print("No drafts")
        for view in views:
            d = view.draft
            line = f"{d.id}  {d.status}"
            if view.stale:
                line += "  stale"
            if view.diff:
                line += (
                    f"  +{len(view.diff.added)} −{len(view.diff.removed)}"
                    f"  score {view.diff.score_delta:+.2f}"
                )
            console.print(line, soft_wrap=True)


@app.command()
def show(
    draft_id: str = typer.Argument(..., metavar="DRAFT", help="Draft id"),
    export_request: Annotated[
        Path | None,
        typer.Option(
            "--export-request",
            help="Write the solve request as JSON, replayable with `solve --request`",
        ),
    ] = None,
    database: str | None = DATABASE_OPTION,
) -> None:
    """Show a Draft's Schedule and how it differs from the Active Schedule."""
    with _session(database) as s:
        view = s.planner.draft(s.user_id, draft_id)
        _print_view(s, view)
        lines = _describe(s, view.draft.festival_id, view.draft.screening_ids)
        console.print("Schedule:")
        for i in _by_time(lines, view.draft.screening_ids):
            console.print(f"  {escape(lines.get(i, i))}", soft_wrap=True)
        if export_request is not None:
            dump_solve_request(
                s.planner.solve_request(s.user_id, draft_id), export_request
            )
            console.print(f"Solve request written to {export_request}")


@app.command()
def accept(
    draft_id: str = typer.Argument(..., metavar="DRAFT", help="Draft id"),
    database: str | None = DATABASE_OPTION,
) -> None:
    """Accept a Draft: its Schedule becomes the Active Schedule."""
    with _session(database) as s:
        schedule = s.planner.accept(s.user_id, draft_id)
        console.print(
            f"[green]Schedule {schedule.number} is now active "
            f"({len(schedule.screening_ids)} screenings, score {schedule.score:.2f})"
            "[/green]",
            soft_wrap=True,
        )


@app.command()
def resolve(
    draft_id: str = typer.Argument(..., metavar="DRAFT", help="Draft id"),
    database: str | None = DATABASE_OPTION,
) -> None:
    """Solve a Draft again against the current Active Schedule."""
    with _session(database) as s:
        _print_view(s, s.planner.resolve(s.user_id, draft_id))


@app.command()
def discard(
    draft_id: str = typer.Argument(..., metavar="DRAFT", help="Draft id"),
    database: str | None = DATABASE_OPTION,
) -> None:
    """Discard a Draft."""
    with _session(database) as s:
        s.planner.discard(s.user_id, draft_id)
        console.print(f"Discarded draft {draft_id}")


@app.command()
def schedule(
    festival: str = typer.Argument(..., help="Festival slug"),
    database: str | None = DATABASE_OPTION,
) -> None:
    """Show the Active Schedule and what needs attention."""
    with _session(database) as s:
        active = s.planner.active_schedule(s.user_id, festival)
        if active is None:
            console.print("No Active Schedule")
        else:
            console.print(
                f"Schedule {active.number}  score {active.score:.2f}", soft_wrap=True
            )
            lines = _describe(s, active.festival_id, active.screening_ids)
            for i in _by_time(lines, active.screening_ids):
                console.print(f"  {escape(lines.get(i, i))}", soft_wrap=True)
        for flag in s.planner.flags(s.user_id, festival):
            console.print(f"[yellow]{escape(flag.message)}[/yellow]", soft_wrap=True)


@app.command()
def compare(
    festival: str = typer.Argument(..., help="Festival slug"),
    limit: int = typer.Option(10, "--limit", "-n", help="Most suggestions to show"),
    database: str | None = DATABASE_OPTION,
) -> None:
    """Suggest Comparisons: which of two competing Films do you prefer?"""
    with _session(database) as s:
        suggestions = s.planner.suggest_comparisons(s.user_id, festival, limit)
        if not suggestions:
            console.print("No comparisons to suggest")
        with s.unit_of_work() as uow:
            titles = {
                e.id: e.title
                for e in uow.programme.entries_by_id(
                    {i for c in suggestions for i in (c.scheduled, c.other)}
                )
            }
        for c in suggestions:
            console.print(
                f"{escape(titles.get(c.scheduled, c.scheduled))} (scheduled) vs "
                f"{escape(titles.get(c.other, c.other))}  gap {c.weight_gap:.2f}",
                soft_wrap=True,
            )


@ticket_app.command("add")
def ticket_add(
    screening: str = typer.Argument(..., help="Screening id"),
    exchangeable: bool = typer.Option(False, "--exchangeable"),
    refundable: bool = typer.Option(False, "--refundable"),
    database: str | None = DATABASE_OPTION,
) -> None:
    """Record a Ticket for a Screening."""
    with _session(database) as s:
        s.planner.record_ticket(
            s.user_id,
            Ticket(
                screening_id=screening,
                exchangeable=exchangeable,
                refundable=refundable,
            ),
        )
        console.print(f"Ticket recorded for {screening}")


@ticket_app.command("remove")
def ticket_remove(
    screening: str = typer.Argument(..., help="Screening id"),
    database: str | None = DATABASE_OPTION,
) -> None:
    """Remove a Ticket."""
    with _session(database) as s:
        s.planner.remove_ticket(s.user_id, screening)
        console.print(f"Ticket removed for {screening}")


@seen_app.command("add")
def seen_add(
    film: str = typer.Argument(..., help="Film id"),
    database: str | None = DATABASE_OPTION,
) -> None:
    """Mark a Film Seen."""
    with _session(database) as s:
        s.planner.mark_seen(s.user_id, film)
        console.print(f"Film {film} marked Seen")


@seen_app.command("remove")
def seen_remove(
    film: str = typer.Argument(..., help="Film id"),
    database: str | None = DATABASE_OPTION,
) -> None:
    """Unmark a Film as Seen."""
    with _session(database) as s:
        s.planner.unmark_seen(s.user_id, film)
        console.print(f"Film {film} no longer marked Seen")


@seen_app.command("dismiss")
def seen_dismiss(
    screening: str = typer.Argument(..., help="Screening id"),
    database: str | None = DATABASE_OPTION,
) -> None:
    """Say you did not go to a Screening, so it does not make its Film Seen."""
    with _session(database) as s:
        s.planner.dismiss_inferred_seen(s.user_id, screening)
        console.print(f"Screening {screening} dismissed")


@seen_app.command("restore")
def seen_restore(
    screening: str = typer.Argument(..., help="Screening id"),
    database: str | None = DATABASE_OPTION,
) -> None:
    """Undo a dismissal."""
    with _session(database) as s:
        s.planner.restore_inferred_seen(s.user_id, screening)
        console.print(f"Screening {screening} restored")
