"""The emulator's Mumbai constants: they agree with the city pack, every
plate is a Maharashtra mark with the EM series, the modelled tide and the
Ganeshotsav calendar behave, and no copy of the previous city (Kolkata)
survives in the emulator's code, library or Marathi text."""

from __future__ import annotations

import codecs
import json
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from event_emulator.city import (
    CITY_NAME,
    EARMARK_EXERCISE_PLATE,
    IST,
    M2_PERIOD_SEC,
    PATROL_AGENCY,
    PLACES,
    PLATE_RTO_CODES,
    PUJA_NIGHTS,
    STOLEN_FIR_PLATE,
    emulated_plate,
    is_monsoon,
    place_name,
    puja_night_of,
    tide_index,
)

SERVICE = Path(__file__).resolve().parents[1]
REPO = SERVICE.parents[1]
PACK = REPO / "cities" / "mumbai"


def _pack(name: str) -> dict:
    path = PACK / name
    if not path.is_file():
        pytest.skip(f"city pack file {path} not in this tree")
    return json.loads(path.read_text(encoding="utf-8"))


class TestPack:
    def test_places_are_the_packs_landmarks_verbatim(self):
        marks = {m["id"]: m for m in _pack("landmarks.json")["landmarks"]}
        for pid, names in PLACES.items():
            assert pid in marks, pid
            assert names["en"] == marks[pid]["en"], pid
            assert names["mr"] == marks[pid]["mr"], pid

    def test_city_names(self):
        city = _pack("city.json")
        assert CITY_NAME == {k: city["name"][k] for k in ("en", "mr", "hi")}

    def test_plates_match_the_packs_format(self):
        rx = re.compile(_pack("city.json")["plates"]["regex"])
        for rto in PLATE_RTO_CODES:
            plate = emulated_plate(rto, 1234)
            assert rx.match(plate), plate
            assert plate.startswith("MH") and plate[4:6] == "EM"
        for plate in (STOLEN_FIR_PLATE, EARMARK_EXERCISE_PLATE):
            assert rx.match(plate) and plate[4:6] == "EM"

    def test_unknown_office_code_refused(self):
        with pytest.raises(ValueError):
            emulated_plate("27", 1)

    def test_place_names_never_invented(self):
        assert place_name("girgaon_chowpatty") == "Girgaon Chowpatty"
        assert place_name("girgaon_chowpatty", "mr") == "गिरगाव चौपाटी"
        with pytest.raises(KeyError):
            place_name("nowhere")

    def test_patrols_are_a_c_a_agency(self):
        # the oracle's closed agency registry (units/agencies.py)
        assert PATROL_AGENCY in ("police", "traffic", "ambulance", "fire")


class TestCalendar:
    def test_monsoon_months(self):
        assert [m for m in range(1, 13) if is_monsoon(date(2026, m, 1))] == [6, 7, 8, 9]

    def test_tide_is_a_modelled_semidiurnal_cycle(self):
        t = datetime(2026, 8, 18, 12, 0, tzinfo=IST)
        values = [tide_index(t + timedelta(minutes=10 * k)) for k in range(80)]
        assert all(0.0 <= v <= 1.0 for v in values)
        assert max(values) > 0.95 and min(values) < 0.05      # high and low water
        period = timedelta(seconds=M2_PERIOD_SEC)
        assert tide_index(t + period) == pytest.approx(tide_index(t), abs=1e-3)
        assert tide_index(t.astimezone(timezone.utc)) == tide_index(t)

    def test_puja_nights_run_from_evening_to_small_hours(self):
        saptami = PUJA_NIGHTS[2025][0]
        assert puja_night_of(saptami, 17.9) is None
        assert puja_night_of(saptami, 18.0) == saptami
        # 03:30 on Ashtami morning is still Saptami night
        assert puja_night_of(saptami + timedelta(days=1), 3.5) == saptami
        navami = PUJA_NIGHTS[2025][-1]
        assert puja_night_of(navami + timedelta(days=1), 3.9) == navami
        assert puja_night_of(navami + timedelta(days=1), 4.0) is None
        assert puja_night_of(navami + timedelta(days=1), 20.0) is None   # Dashami: over

    def test_puja_calendar_override(self):
        nights = (date(2027, 10, 7),)
        assert puja_night_of(date(2027, 10, 7), 21.0, nights) == date(2027, 10, 7)
        assert puja_night_of(PUJA_NIGHTS[2025][0], 21.0, nights) is None


# ── no trace of the previous city, and no forbidden words ──────────────────

#: Copy the emulator must never carry (rot13, so this file does not either):
#: the previous city's product name, two company names, and any mention of a
#: contest.
_FORBIDDEN = [codecs.decode(w, "rot13") for w in
              ("irre", "hore", "argsyvk", "unpxngba", "pbzcrgvgvba", "punyyratr")]
_OLD_CITY = re.compile(
    r"Kolkata|Calcutta|Howrah|West Bengal|Hooghly|Nabanna|Durga Puja|Sealdah|"
    r"Eden Gardens|Esplanade|BBD Bag|Salt Lake|EM Bypass|Burrabazar|Gangasagar|"
    r"\bWB ?\d{2}|WBTC|WBFES|\bKMC\b|\bKTP-EM|\bKP-EM|Nor'wester")
_BENGALI = re.compile(r"[\u0980-\u09FF]")


def _texts():
    for path in sorted((SERVICE / "src").rglob("*")):
        if path.suffix in (".py", ".json") and "__pycache__" not in path.parts:
            yield path, path.read_text(encoding="utf-8")
    for extra in (SERVICE / "README.md", SERVICE / "pyproject.toml",
                  SERVICE / "tools" / "mumbai_library.py"):
        if extra.is_file():
            yield extra, extra.read_text(encoding="utf-8")


class TestCopy:
    def test_no_previous_city_left(self):
        hits = [(p.name, m.group(0)) for p, text in _texts() for m in _OLD_CITY.finditer(text)]
        assert hits == []

    def test_no_bengali_script(self):
        assert [p.name for p, text in _texts() if _BENGALI.search(text)] == []

    def test_no_forbidden_words(self):
        hits = []
        for p, text in _texts():
            # a real Mumbai road name (OpenStreetMap), not a product name
            low = text.lower().replace("veer nariman", "")
            hits += [(p.name, w) for w in _FORBIDDEN if re.search(rf"\b{w}\b", low)]
        assert hits == []
