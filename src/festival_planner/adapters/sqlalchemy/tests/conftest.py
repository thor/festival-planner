from collections.abc import Iterator

import pytest
from sqlalchemy import Engine

from festival_planner.adapters.sqlalchemy.database import create_engine_for, migrate


@pytest.fixture
def engine(tmp_path) -> Iterator[Engine]:
    engine = create_engine_for(f"sqlite:///{tmp_path / 'test.db'}")
    migrate(engine)
    yield engine
    engine.dispose()
