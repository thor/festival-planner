"""days

Stored Preferences and Change Sets keep the days a User can go, not a date
range: start_date and end_date become days, and set_date_range items become
set_days. An open end runs to the Festival's own first or last day.

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-24 00:00:00.000000

"""

import datetime
import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _days(
    start: str | None, end: str | None, festival: tuple[str, str]
) -> list[str] | None:
    """Every day from `start` to `end`; None for no bounds at all."""
    if start is None and end is None:
        return None
    first = datetime.date.fromisoformat(start or festival[0])
    last = datetime.date.fromisoformat(end or festival[1])
    return [
        (first + datetime.timedelta(days=n)).isoformat()
        for n in range((last - first).days + 1)
    ] or None


def _preferences(value: dict, festival: tuple[str, str]) -> dict:
    start, end = value.pop("start_date", None), value.pop("end_date", None)
    return {**value, "days": value.get("days") or _days(start, end, festival)}


def _change_set(value: dict, festival: tuple[str, str]) -> dict:
    items = [
        {
            "kind": "set_days",
            "days": _days(item.get("start_date"), item.get("end_date"), festival),
        }
        if item.get("kind") == "set_date_range"
        else item
        for item in value.get("items", [])
    ]
    return {**value, "items": items}


def _rewrite(table: str, column: str, change, festivals) -> None:
    connection = op.get_bind()
    keys = "user_id, festival_id" if table == "planning_inputs" else "id"
    rows = connection.execute(
        sa.text(f"SELECT {keys}, festival_id, {column} FROM {table}")
    ).all()
    for *key, festival_id, raw in rows:
        updated = json.dumps(
            change(json.loads(raw), festivals[festival_id]), separators=(",", ":")
        )
        if updated == raw:
            continue
        where = (
            "user_id = :k0 AND festival_id = :k1"
            if table == "planning_inputs"
            else "id = :k0"
        )
        connection.execute(
            sa.text(f"UPDATE {table} SET {column} = :v WHERE {where}"),
            {"v": updated, **{f"k{i}": k for i, k in enumerate(key)}},
        )


def upgrade() -> None:
    festivals = {
        id: (str(start), str(end))
        for id, start, end in op.get_bind()
        .execute(sa.text("SELECT id, start_date, end_date FROM festival"))
        .all()
    }
    _rewrite("planning_inputs", "preferences", _preferences, festivals)
    _rewrite("schedule", "change_set", _change_set, festivals)
    _rewrite("draft", "change_set", _change_set, festivals)


def downgrade() -> None:
    raise NotImplementedError("Days cannot become a single date range again")
