"""Travel between Venues."""

from functools import cached_property

from pydantic import Field

from .programme import VenueId
from .values import Value

TransportMode = str

DEFAULT_TRANSPORT_MODE: TransportMode = "walk+e-scooter"


class Route(Value):
    """A precalculated way of travelling from one Venue to another."""

    from_venue_id: VenueId
    to_venue_id: VenueId
    mode: TransportMode
    minutes: int = Field(ge=0)


class MissingRouteError(LookupError):
    """No Route exists between two Venues in the chosen or default mode."""


class RouteTable(Value):
    """All known Routes, plus the globally decided default Transport Mode."""

    routes: tuple[Route, ...] = ()
    default_mode: TransportMode = DEFAULT_TRANSPORT_MODE

    @cached_property
    def _minutes_by_key(self) -> dict[tuple[VenueId, VenueId, TransportMode], int]:
        return {
            (r.from_venue_id, r.to_venue_id, r.mode): r.minutes for r in self.routes
        }

    def minutes(
        self, from_venue_id: VenueId, to_venue_id: VenueId, mode: TransportMode | None
    ) -> int:
        """Travel minutes by `mode`, falling back to the default mode."""
        if from_venue_id == to_venue_id:
            return 0
        for candidate in (mode, self.default_mode):
            if candidate is None:
                continue
            key = (from_venue_id, to_venue_id, candidate)
            if key in self._minutes_by_key:
                return self._minutes_by_key[key]
        raise MissingRouteError(
            f"No route from {from_venue_id!r} to {to_venue_id!r} "
            f"by {mode!r} or default {self.default_mode!r}"
        )
