"""Shared pytest fixtures."""

import pytest

from festival_planner.models import Film


@pytest.fixture(autouse=True)
def _reset_film_cinema_validation():
    """`Film` keeps cinema validation in class variables; isolate each test."""
    Film._valid_cinemas = None
    Film._normalization_map = {}
    yield
    Film._valid_cinemas = None
    Film._normalization_map = {}
