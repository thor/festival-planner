import datetime
from dataclasses import replace

import pytest

from festival_planner.domain.planning import Preferences
from festival_planner.domain.programme import Event
from festival_planner.domain.solving import formulate
from festival_planner.domain.tests.builders import DAY, at, entry, request, screening
from festival_planner.domain.travel import Route


def candidate_ids(req) -> set[str]:
    return {s.id for s in formulate(req).candidates}


class TestCandidates:
    def test_all_screenings_are_candidates_by_default(self):
        req = request(
            screening("a", "14:00", "16:00"), screening("b", "18:00", "20:00")
        )
        assert candidate_ids(req) == {"a", "b"}

    def test_excluded_screening_is_dropped(self):
        req = request(
            screening("a", "14:00", "16:00"),
            screening("b", "18:00", "20:00"),
            excluded_screenings=frozenset({"a"}),
        )
        assert candidate_ids(req) == {"b"}

    def test_excluded_programme_entry_drops_all_its_screenings(self):
        req = request(
            screening("a1", "14:00", "16:00", entry_id="a"),
            screening("a2", "18:00", "20:00", entry_id="a"),
            excluded_programme_entries=frozenset({"a"}),
        )
        assert candidate_ids(req) == set()

    def test_seen_film_is_dropped(self):
        req = request(
            screening("a", "14:00", "16:00"), seen_films=frozenset({"film-a"})
        )
        assert candidate_ids(req) == set()

    def test_seen_film_with_film_commitment_is_kept(self):
        req = request(
            screening("a", "14:00", "16:00"),
            seen_films=frozenset({"film-a"}),
            film_commitments=frozenset({"a"}),
        )
        assert candidate_ids(req) == {"a"}

    def test_screenings_outside_date_range_are_dropped(self):
        next_day = DAY + datetime.timedelta(days=1)
        req = request(
            screening("a", "14:00", "16:00"),
            screening("b", "14:00", "16:00", day=next_day),
            preferences=Preferences(start_date=next_day),
        )
        assert candidate_ids(req) == {"b"}

    def test_screening_commitment_overrides_exclusion_seen_and_dates(self):
        req = request(
            screening("a", "14:00", "16:00"),
            screening_commitments=frozenset({"a"}),
            excluded_screenings=frozenset({"a"}),
            seen_films=frozenset({"film-a"}),
            preferences=Preferences(end_date=DAY - datetime.timedelta(days=1)),
        )
        formulation = formulate(req)
        assert {s.id for s in formulation.candidates} == {"a"}
        assert formulation.required == {"a"}


class TestStartedScreenings:
    def test_started_screening_in_active_schedule_is_required(self):
        req = request(
            screening("a", "14:00", "16:00"),
            active_schedule=frozenset({"a"}),
            now=at("15:00"),
        )
        formulation = formulate(req)
        assert formulation.required == {"a"}
        assert {s.id for s in formulation.candidates} == {"a"}

    def test_started_screening_outside_active_schedule_is_dropped(self):
        req = request(screening("a", "14:00", "16:00"), now=at("15:00"))
        assert candidate_ids(req) == set()

    def test_started_committed_screening_is_unsatisfiable(self):
        req = request(
            screening("a", "14:00", "16:00"),
            screening_commitments=frozenset({"a"}),
            now=at("15:00"),
        )
        formulation = formulate(req)
        assert formulation.unsatisfiable
        assert formulation.candidates == ()

    def test_started_active_screening_is_kept_despite_later_rules(self):
        next_day = DAY + datetime.timedelta(days=1)
        req = request(
            screening("a", "14:00", "16:00"),
            active_schedule=frozenset({"a"}),
            now=at("15:00"),
            excluded_screenings=frozenset({"a"}),
            excluded_programme_entries=frozenset({"a"}),
            seen_films=frozenset({"film-a"}),
            preferences=Preferences(start_date=next_day),
        )
        formulation = formulate(req)
        assert {s.id for s in formulation.candidates} == {"a"}
        assert formulation.required == {"a"}

    def test_started_screenings_do_not_conflict_with_each_other(self):
        req = request(
            screening("a", "14:00", "16:00"),
            screening("b", "16:10", "18:00"),
            active_schedule=frozenset({"a", "b"}),
            now=at("19:00"),
            preferences=Preferences(buffer_minutes=30),
        )
        formulation = formulate(req)
        assert formulation.conflicts == frozenset()
        assert formulation.required == {"a", "b"}

    def test_started_screening_still_conflicts_with_unreachable_future_one(self):
        req = request(
            screening("a", "14:00", "16:00"),
            screening("b", "16:10", "18:00"),
            active_schedule=frozenset({"a"}),
            now=at("15:00"),
            preferences=Preferences(buffer_minutes=30),
        )
        assert conflicts(req) == {frozenset({"a", "b"})}


class TestGroups:
    def test_film_commitment_requires_exactly_one_of_its_screenings(self):
        req = request(
            screening("a1", "14:00", "16:00", entry_id="a"),
            screening("a2", "18:00", "20:00", entry_id="a"),
            film_commitments=frozenset({"a"}),
        )
        assert formulate(req).exactly_one == (frozenset({"a1", "a2"}),)

    def test_film_commitment_without_screenings_is_unsatisfiable(self):
        req = request(
            screening("a", "14:00", "16:00"),
            entries=(entry("a"), entry("b")),
            film_commitments=frozenset({"b"}),
        )
        assert formulate(req).unsatisfiable

    def test_at_most_one_screening_per_programme_entry(self):
        req = request(
            screening("a1", "14:00", "16:00", entry_id="a"),
            screening("a2", "18:00", "20:00", entry_id="a"),
            screening("b", "21:00", "23:00"),
        )
        assert formulate(req).at_most_one == (frozenset({"a1", "a2"}),)


def conflicts(req) -> set[frozenset[str]]:
    return {frozenset(pair) for pair in formulate(req).conflicts}


class TestConflicts:
    def test_overlapping_screenings_conflict(self):
        req = request(
            screening("a", "14:00", "16:00"), screening("b", "15:00", "17:00")
        )
        assert conflicts(req) == {frozenset({"a", "b"})}

    def test_back_to_back_at_same_venue_without_buffer_is_fine(self):
        req = request(
            screening("a", "14:00", "16:00"), screening("b", "16:00", "18:00")
        )
        assert conflicts(req) == set()

    def test_buffer_of_next_venue_is_needed(self):
        req = request(
            screening("a", "14:00", "16:00"),
            screening("b", "16:10", "18:00"),
            preferences=Preferences(buffer_minutes=15),
        )
        assert conflicts(req) == {frozenset({"a", "b"})}

    def test_per_venue_buffer_overrides_general_buffer(self):
        req = request(
            screening("a", "14:00", "16:00", venue="A"),
            screening("b", "16:10", "18:00", venue="A"),
            preferences=Preferences(buffer_minutes=15, venue_buffer_minutes={"A": 5}),
        )
        assert conflicts(req) == set()

    def test_travel_time_uses_the_direction_travelled(self):
        req = request(
            screening("a", "14:00", "16:00", venue="A"),
            screening("b", "16:10", "18:00", venue="B"),
            routes=(
                Route(
                    from_venue_id="A",
                    to_venue_id="B",
                    mode="walk+e-scooter",
                    minutes=20,
                ),
                Route(
                    from_venue_id="B", to_venue_id="A", mode="walk+e-scooter", minutes=5
                ),
            ),
        )
        assert conflicts(req) == {frozenset({"a", "b"})}

    def test_chosen_transport_mode_is_used(self):
        req = request(
            screening("a", "14:00", "16:00", venue="A"),
            screening("b", "16:10", "18:00", venue="B"),
            routes=(
                Route(
                    from_venue_id="A",
                    to_venue_id="B",
                    mode="walk+e-scooter",
                    minutes=20,
                ),
                Route(
                    from_venue_id="B",
                    to_venue_id="A",
                    mode="walk+e-scooter",
                    minutes=20,
                ),
                Route(from_venue_id="A", to_venue_id="B", mode="bike", minutes=8),
            ),
            preferences=Preferences(buffer_minutes=0, transport_mode="bike"),
        )
        assert conflicts(req) == set()

    def test_separately_timed_event_blocks_time_when_attending_events(self):
        panel = Event(description="Panel", start_time=at("16:00"), end_time=at("17:00"))
        a = screening("a", "14:00", "16:00", events=(panel,))
        b = screening("b", "16:30", "18:00")
        assert conflicts(request(a, b)) == set()
        attending = request(
            a, b, preferences=Preferences(buffer_minutes=0, attend_events=True)
        )
        assert conflicts(attending) == {frozenset({"a", "b"})}

    def test_separately_timed_event_before_screening_blocks_time_when_attending(self):
        ceremony = Event(
            description="Ceremony", start_time=at("17:30"), end_time=at("18:00")
        )
        a = screening("a", "16:00", "17:45")
        b = screening("b", "18:00", "20:00", events=(ceremony,))
        assert conflicts(request(a, b)) == set()
        attending = request(
            a, b, preferences=Preferences(buffer_minutes=0, attend_events=True)
        )
        assert conflicts(attending) == {frozenset({"a", "b"})}

    def test_screenings_across_midnight_still_conflict(self):
        next_day = DAY + datetime.timedelta(days=1)
        late = screening("late", "23:00", "23:59")
        after_midnight = screening("early", "00:10", "02:00", day=next_day)
        req = request(late, after_midnight, preferences=Preferences(buffer_minutes=15))
        assert conflicts(req) == {frozenset({"late", "early"})}


class TestValidation:
    def test_duplicate_screening_ids_are_rejected(self):
        req = request(
            screening("a", "14:00", "16:00"),
            screening("a", "18:00", "20:00"),
            entries=(entry("a"),),
        )
        with pytest.raises(ValueError, match="'a'"):
            formulate(req)

    def test_duplicate_programme_entry_ids_are_rejected(self):
        req = request(
            screening("a", "14:00", "16:00"), entries=(entry("a"), entry("a"))
        )
        with pytest.raises(ValueError, match="'a'"):
            formulate(req)

    def test_duplicate_venue_ids_are_rejected(self):
        req = request(screening("a", "14:00", "16:00"))
        req = replace(req, venues=req.venues * 2)
        with pytest.raises(ValueError, match="'A'"):
            formulate(req)

    def test_unknown_programme_entry_is_rejected_naming_both_ids(self):
        req = request(
            screening("a", "14:00", "16:00", entry_id="e"), entries=(entry("other"),)
        )
        with pytest.raises(ValueError, match="'a'.*'e'"):
            formulate(req)

    def test_unknown_venue_is_rejected_naming_both_ids(self):
        req = request(screening("a", "14:00", "16:00"))
        req = replace(req, venues=())
        with pytest.raises(ValueError, match="'a'.*'A'"):
            formulate(req)

    def test_unknown_screening_commitment_is_unsatisfiable(self):
        req = request(
            screening("a", "14:00", "16:00"),
            screening_commitments=frozenset({"x"}),
        )
        assert formulate(req).unsatisfiable == (
            "Committed screening 'x' does not exist",
        )

    def test_unknown_film_commitment_is_unsatisfiable(self):
        req = request(
            screening("a", "14:00", "16:00"), film_commitments=frozenset({"x"})
        )
        assert formulate(req).unsatisfiable == (
            "Committed programme entry 'x' does not exist",
        )

    def test_unknown_ids_elsewhere_are_ignored(self):
        req = request(
            screening("a", "14:00", "16:00"),
            active_schedule=frozenset({"x"}),
            excluded_screenings=frozenset({"x"}),
            excluded_programme_entries=frozenset({"x"}),
            seen_films=frozenset({"x"}),
        )
        formulation = formulate(req)
        assert {s.id for s in formulation.candidates} == {"a"}
        assert not formulation.unsatisfiable
