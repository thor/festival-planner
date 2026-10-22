"""The UnitOfWork port over one SQLAlchemy session."""

from types import TracebackType
from typing import Self

from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from .repositories import (
    SqlAlchemyFestivalRepository,
    SqlAlchemyFilmRepository,
    SqlAlchemyProgrammeRepository,
    SqlAlchemyRouteRepository,
    SqlAlchemyVenueRepository,
)


class SqlAlchemyUnitOfWork:
    """One session per `with` block. Leaving the block without `commit()`
    rolls back."""

    festivals: SqlAlchemyFestivalRepository
    venues: SqlAlchemyVenueRepository
    routes: SqlAlchemyRouteRepository
    films: SqlAlchemyFilmRepository
    programme: SqlAlchemyProgrammeRepository

    def __init__(self, engine: Engine):
        self._sessions = sessionmaker(engine, expire_on_commit=False)

    def __enter__(self) -> Self:
        self._session: Session = self._sessions()
        self.festivals = SqlAlchemyFestivalRepository(self._session)
        self.venues = SqlAlchemyVenueRepository(self._session)
        self.routes = SqlAlchemyRouteRepository(self._session)
        self.films = SqlAlchemyFilmRepository(self._session)
        self.programme = SqlAlchemyProgrammeRepository(self._session)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self._session.rollback()
        self._session.close()

    def commit(self) -> None:
        self._session.commit()
