"""Shared test setup: the ethics detector reads a small SYNTHETIC Mumbai gazetteer (tests/fixtures), so the tests
see the same places whatever the repo's generated gazetteer holds. A test about the repo gazetteer itself clears
the variable (``monkeypatch.delenv``)."""

from __future__ import annotations

from pathlib import Path

import pytest

from osint_common import ethics

TEST_GAZETTEER = Path(__file__).parent / "fixtures" / "mumbai_gazetteer.synthetic.json"


@pytest.fixture(autouse=True)
def _mumbai_test_gazetteer(monkeypatch):
    monkeypatch.setenv(ethics.GAZETTEER_ENV, str(TEST_GAZETTEER))
    ethics.reset_place_phrases()
    yield
    ethics.reset_place_phrases()
