import pytest
from pydantic import ValidationError

from festival_planner.domain.ingestion import (
    AmbiguousVenueNameError,
    SourceEntry,
    SourceFestival,
    SourceProgramme,
    SourceScreening,
    VenueDirectory,
)
from festival_planner.domain.programme import Venue

from .builders import at

FESTIVAL = SourceFestival(slug="fests-2025", name="Fests 2025", time_zone="Europe/Oslo")


def test_source_programme_rejects_duplicate_source_keys():
    entry = SourceEntry(source_key="film/a", title="A")
    with pytest.raises(ValidationError, match="Duplicate source key 'film/a'"):
        SourceProgramme(festival=FESTIVAL, entries=(entry, entry))


def test_source_screening_cannot_end_before_it_starts():
    with pytest.raises(ValidationError):
        SourceScreening(venue_name="Vika", start_time=at("20:00"), end_time=at("18:00"))


def test_venue_directory_resolves_names_and_aliases():
    vika = Venue(id="v", name="Vika", aliases=frozenset({"Vika Kino"}))
    directory = VenueDirectory((vika,))
    assert directory.resolve("vika kino") == vika
    assert directory.resolve("Vega") is None


def test_venue_directory_rejects_a_name_shared_by_two_venues():
    a = Venue(id="a", name="Vika", aliases=frozenset({"Kino"}))
    b = Venue(id="b", name="Vega", aliases=frozenset({"kino"}))
    with pytest.raises(AmbiguousVenueNameError, match="'kino'"):
        VenueDirectory((a, b))
