"""Festivals and the series that group them."""

import datetime
import zoneinfo
from typing import Self

from pydantic import model_validator

from .values import Slug, TimeZone, Value

FestivalId = str
FestivalSeriesId = str


class FestivalSeries(Value):
    """The recurring identity that groups Festivals across years."""

    id: FestivalSeriesId
    slug: Slug
    name: str


class Festival(Value):
    """A single edition of a film festival."""

    id: FestivalId
    slug: Slug
    name: str
    start_date: datetime.date
    end_date: datetime.date
    time_zone: TimeZone
    series_id: FestivalSeriesId | None = None

    @model_validator(mode="after")
    def _ends_after_it_starts(self) -> Self:
        if self.end_date < self.start_date:
            raise ValueError(f"Festival {self.slug!r} cannot end before it starts")
        return self

    def local_date(self, instant: datetime.datetime) -> datetime.date:
        """The festival-local calendar day of `instant`."""
        return instant.astimezone(zoneinfo.ZoneInfo(self.time_zone)).date()
