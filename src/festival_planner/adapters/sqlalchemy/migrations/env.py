"""Alembic environment: uses a passed-in connection, or resolves the URL."""

from alembic import context

from festival_planner.adapters.sqlalchemy.database import (
    create_engine_for,
    resolve_database_url,
)
from festival_planner.adapters.sqlalchemy.tables import Base, UTCDateTime


def _render_item(type_, obj, _autogen_context):
    # Migrations must not import adapter code that may change later.
    if type_ == "type" and isinstance(obj, UTCDateTime):
        return "sa.DateTime()"
    return False


def _run(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=Base.metadata,
        render_as_batch=True,
        render_item=_render_item,
    )
    with context.begin_transaction():
        context.run_migrations()


connection = context.config.attributes.get("connection")
if connection is not None:
    _run(connection)
else:
    url = context.config.get_main_option("sqlalchemy.url") or resolve_database_url()
    with create_engine_for(url).connect() as connection:
        _run(connection)
        connection.commit()
