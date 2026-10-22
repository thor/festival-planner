"""Venues and Routes from the legacy cinema configuration."""

from ...domain.ingestion import SourceRoute, SourceVenue
from ...domain.programme import Venue
from ...domain.travel import DEFAULT_TRANSPORT_MODE, TransportMode
from ...models import CinemaConfig, build_normalization_map


class CinemaConfigVenues:
    """VenueSource and RouteProvider over `cinemas:` in config.yaml.

    Travel-time endpoints given by alias are mapped to their canonical name.
    Travel times apply in both directions unless the reverse is configured.
    """

    def __init__(
        self, cinemas: CinemaConfig, mode: TransportMode = DEFAULT_TRANSPORT_MODE
    ):
        self._cinemas = cinemas
        self._mode = mode
        self._canonical = build_normalization_map(cinemas.cinema_aliases)

    def _canonical_name(self, name: str) -> str:
        return self._canonical.get(name.lower().strip(), name)

    def venues(self) -> tuple[SourceVenue, ...]:
        aliases = self._cinemas.cinema_aliases
        endpoints = {self._canonical_name(n) for n in self._cinemas.get_valid_cinemas()}
        names = dict.fromkeys([*aliases, *sorted(endpoints)])
        return tuple(
            SourceVenue(name=n, aliases=frozenset(aliases.get(n, ()))) for n in names
        )

    def routes(self, venues: tuple[Venue, ...]) -> tuple[SourceRoute, ...]:
        minutes: dict[tuple[str, str], int] = {}
        for t in self._cinemas.travel_times:
            a, b = (
                self._canonical_name(t.from_cinema),
                self._canonical_name(t.to_cinema),
            )
            if a != b:
                minutes[a, b] = t.minutes
        for (a, b), m in list(minutes.items()):
            minutes.setdefault((b, a), m)
        return tuple(
            SourceRoute(from_venue=a, to_venue=b, mode=self._mode, minutes=m)
            for (a, b), m in minutes.items()
        )
