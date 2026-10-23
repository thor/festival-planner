"""Mint bearer tokens from the local issuer (ADR-0003)."""

import datetime
import getpass
import shlex
from pathlib import Path

import typer
from rich.console import Console
from rich.markup import escape

from ..adapters.jwt.verifier import ISSUERS_ENV
from ..adapters.local_issuer.issuer import LocalIssuer

app = typer.Typer(name="token", help="Mint bearer tokens from the local issuer.")
console = Console()

DIRECTORY_OPTION = typer.Option(
    None,
    "--directory",
    help="Where the local issuer's keys live (default: the XDG data directory)",
)


def _issuer(directory: Path | None) -> LocalIssuer:
    chosen = directory or LocalIssuer.default_directory()
    return LocalIssuer(chosen.absolute())


@app.command()
def init(
    force: bool = typer.Option(False, "--force", help="Replace any existing keys"),
    directory: Path | None = DIRECTORY_OPTION,
) -> None:
    """Create the local issuer's keypair."""
    issuer = _issuer(directory)
    try:
        issuer.init(force=force)
    except FileExistsError as e:
        console.print(f"[bold red]{escape(str(e))}[/bold red]", soft_wrap=True)
        raise typer.Exit(code=1) from e
    trusted = issuer.trusted_issuer().model_dump_json(exclude_defaults=True)
    typer.echo(f"export {ISSUERS_ENV}={shlex.quote(f'[{trusted}]')}")


@app.command()
def issue(
    subject: str | None = typer.Option(
        None, "--subject", help="Token subject (default: the OS user)"
    ),
    days: int = typer.Option(30, "--days", help="Token lifetime in days"),
    directory: Path | None = DIRECTORY_OPTION,
) -> None:
    """Print a bearer token for the given subject."""
    issuer = _issuer(directory)
    try:
        token = issuer.issue(
            subject or getpass.getuser(),
            lifetime=datetime.timedelta(days=days),
        )
    except FileNotFoundError as e:
        console.print(f"[bold red]{escape(str(e))}[/bold red]", soft_wrap=True)
        raise typer.Exit(code=1) from e
    typer.echo(token)
