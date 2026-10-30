"""Config tests: deck-origin parsing fails closed; flags and seeds parse."""

from __future__ import annotations

from datetime import date

import pytest

from event_emulator.config import (
    get_settings,
    parse_deck_origins,
    parse_density,
    parse_flag,
    parse_puja_nights,
)


class TestDeckOrigins:
    @pytest.mark.parametrize("raw, expected", [
        ("http://127.0.0.1:5273", ("http://127.0.0.1:5273",)),
        ("https://deck.example.org", ("https://deck.example.org",)),
        ("http://127.0.0.1:5273, https://deck.example.org/",
         ("http://127.0.0.1:5273", "https://deck.example.org")),
    ])
    def test_accepted(self, raw, expected):
        assert parse_deck_origins(raw) == expected

    @pytest.mark.parametrize("raw", [
        "*",
        "http://x:1/path",
        "ftp://x",
        "http://u:p@x:1",
        " , ",
        "http://h:notaport",
        "http://h:99999",
        "http://h:-1",
        "http://h:",
        "http://h:0",
        "http://127.0.0.1:5273,*",
    ])
    def test_refused(self, raw):
        with pytest.raises(ValueError):
            parse_deck_origins(raw)


class TestEnv:
    @pytest.mark.parametrize("raw, value", [
        ("1", True), ("true", True), ("on", True), ("0", False), ("", False),
        (None, False), ("no", False),
    ])
    def test_flag(self, raw, value):
        assert parse_flag(raw) is value

    def test_living_city_and_seed(self, monkeypatch):
        monkeypatch.setenv("EMULATOR_LIVING_CITY", "1")
        monkeypatch.setenv("EMULATOR_CITY_SEED", "2026")
        s = get_settings()
        assert s.living_city is True and s.city_seed == 2026
        monkeypatch.setenv("EMULATOR_LIVING_CITY", "0")
        monkeypatch.delenv("EMULATOR_CITY_SEED")
        s = get_settings()
        assert s.living_city is False and s.city_seed == 400001

    def test_living_violators_default_on(self, monkeypatch):
        monkeypatch.delenv("EMULATOR_LIVING_VIOLATORS", raising=False)
        assert get_settings().living_violators is True
        monkeypatch.setenv("EMULATOR_LIVING_VIOLATORS", "0")
        assert get_settings().living_violators is False
        monkeypatch.setenv("EMULATOR_LIVING_VIOLATORS", " ")     # blank: the default
        assert get_settings().living_violators is True

    def test_bad_deck_origins_fail_closed(self, monkeypatch):
        monkeypatch.setenv("EMULATOR_DECK_ORIGINS", "http://h:notaport")
        with pytest.raises(ValueError):
            get_settings()


class TestPujaNights:
    def test_parsed_sorted_and_deduplicated(self):
        assert parse_puja_nights("2026-10-19, 2026-10-17,2026-10-18,2026-10-17") == (
            date(2026, 10, 17), date(2026, 10, 18), date(2026, 10, 19))

    @pytest.mark.parametrize("raw", ["", " , ", "17-10-2026", "2026-13-01", "tomorrow"])
    def test_refused(self, raw):
        with pytest.raises(ValueError):
            parse_puja_nights(raw)

    def test_env_override(self, monkeypatch):
        monkeypatch.delenv("EMULATOR_PUJA_NIGHTS", raising=False)
        assert get_settings().puja_nights is None          # city.PUJA_NIGHTS
        monkeypatch.setenv("EMULATOR_PUJA_NIGHTS", "2027-10-06,2027-10-07,2027-10-08")
        assert get_settings().puja_nights == (
            date(2027, 10, 6), date(2027, 10, 7), date(2027, 10, 8))
        monkeypatch.setenv("EMULATOR_PUJA_NIGHTS", "not-a-date")
        with pytest.raises(ValueError):
            get_settings()


class TestLivingDensity:
    @pytest.mark.parametrize("raw, level", [("1", 1), (" 2 ", 2), ("3", 3)])
    def test_accepted(self, raw, level):
        assert parse_density(raw) == level

    @pytest.mark.parametrize("raw", ["0", "4", "-1", "two", "2.5", "high"])
    def test_refused(self, raw):
        with pytest.raises(ValueError):
            parse_density(raw)

    def test_env(self, monkeypatch):
        monkeypatch.delenv("EMULATOR_LIVING_DENSITY", raising=False)
        assert get_settings().living_density == 1           # the baseline city
        monkeypatch.setenv("EMULATOR_LIVING_DENSITY", " ")   # blank: the default
        assert get_settings().living_density == 1
        monkeypatch.setenv("EMULATOR_LIVING_DENSITY", "2")
        assert get_settings().living_density == 2
        monkeypatch.setenv("EMULATOR_LIVING_DENSITY", "9")   # a typo fails closed
        with pytest.raises(ValueError):
            get_settings()
