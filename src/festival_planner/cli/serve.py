"""Serving the GraphQL API, and exporting its schema."""

import os
from pathlib import Path
from typing import Annotated

import typer

from .db import DATABASE_OPTION

app = typer.Typer()


@app.command()
def serve(
    database: str | None = DATABASE_OPTION,
    host: Annotated[str, typer.Option(help="Interface to listen on")] = "127.0.0.1",
    port: Annotated[int, typer.Option(help="Port to listen on")] = 8000,
    draft_wait: Annotated[
        float,
        typer.Option(help="Seconds a Draft mutation waits for its solve to finish"),
    ] = 2.0,
) -> None:
    """Serve the GraphQL API at /graphql."""
    import uvicorn

    from ..api.server import build_server

    server = build_server(database, os.environ, draft_wait_seconds=draft_wait)
    uvicorn.run(server, host=host, port=port)


@app.command("export-schema")
def export_schema(
    path: Annotated[
        Path | None, typer.Argument(help="File to write (default: stdout)")
    ] = None,
) -> None:
    """Write the GraphQL schema (SDL)."""
    from ..api.schema import schema

    sdl = schema.as_str() + "\n"
    if path is None:
        typer.echo(sdl, nl=False)
    else:
        path.write_text(sdl)
