"""The brain's MCP vocabulary mirrors the oracle's (C-T / C-C / C3 lockstep).

The two services never import each other, so the shared enums are compared
as data — parsed by regex from the oracle's own source files:
    city/common.py    ENTITY_KINDS (12: the 10 + osint_event, place),
                      FEED_KINDS (8: + osint), the plate STATE_CODES (39)
    events/__init__.py EVENT_KINDS (16: the 10 + the six OSINT reported
                      situations — crime_incident stays ANPR/watchlist-only)
Also pins: the canvas layers keep every previous id and gain the two OSINT
layers, parse_urn accepts the OSINT id grammars (osint_event uuid, place
slug) and refuses bad ids, and the brain's plate mask locksteps the oracle's
separator set.
"""

from __future__ import annotations

import ast
import re
import uuid
from pathlib import Path

import pytest

from convoy_brain.mcp import server as mcp_server
from convoy_brain.mcp.server import (
    _CANVAS_LAYERS_DEF,
    _CITY_ENTITY_KINDS_DEF,
    _CITY_FEED_KINDS_DEF,
    _MARK_SEP,
    _PLATE_STATE_CODES,
    parse_urn,
)

ORACLE = Path(__file__).resolve().parents[2] / "traffic-oracle/src/traffic_oracle"
COMMON_SRC = (ORACLE / "city/common.py").read_text(encoding="utf-8")
EVENTS_SRC = (ORACLE / "events/__init__.py").read_text(encoding="utf-8")


def _tuple_of_names(source: str, name: str) -> tuple[str, ...]:
    """One ``NAME: tuple[str, ...] = (…)`` literal from oracle source, as data.

    The block ends at a lone ``)`` line — comments inside the block carry
    their own parentheses, so a first-``)`` scan would truncate it.
    """
    found = re.search(rf"^{name}: tuple\[str, \.\.\.\] = \(\n(.*?)^\)",
                      source, re.DOTALL | re.MULTILINE)
    assert found, f"{name} not found in oracle source"
    return tuple(re.findall(r'"([A-Za-z0-9_]+)"', found.group(1)))


def _oracle_mark_sep() -> str:
    """The oracle's _MARK_SEP literal, parsed as data (adjacent string
    literals concatenated — exactly what the oracle module sees)."""
    found = re.search(r"_MARK_SEP = \(\n(.*?)\n\)", COMMON_SRC, re.DOTALL)
    assert found, "_MARK_SEP not found in oracle source"
    return ast.literal_eval("(" + found.group(1) + ")")


class TestVocabMirror:
    def test_entity_kinds_equal_the_oracles(self):
        assert _CITY_ENTITY_KINDS_DEF == _tuple_of_names(COMMON_SRC, "ENTITY_KINDS")
        assert "osint_event" in _CITY_ENTITY_KINDS_DEF and "place" in _CITY_ENTITY_KINDS_DEF

    def test_feed_kinds_equal_the_oracles(self):
        assert _CITY_FEED_KINDS_DEF == _tuple_of_names(COMMON_SRC, "FEED_KINDS")
        assert "osint" in _CITY_FEED_KINDS_DEF

    def test_event_kinds_equal_the_oracles(self):
        """The six reported-situation kinds are known to the events board
        filter; city_link.EVENT_KINDS intentionally stays at the 8 archetypes
        (brain-planned movements only)."""
        assert tuple(sorted(mcp_server._EVENT_KINDS)) == tuple(
            sorted(_tuple_of_names(EVENTS_SRC, "EVENT_KINDS")))
        assert {"reported_crime", "public_disorder", "road_accident", "hazard",
                "flooding", "infra_failure"} <= mcp_server._EVENT_KINDS

    def test_canvas_layers_keep_every_previous_id_and_gain_osint(self):
        previous = ("events", "flow", "traces", "enforcement", "signals",
                    "units", "dispatch", "convoy", "cameras", "anomalies",
                    "photoreal-3d")
        assert set(previous) <= set(_CANVAS_LAYERS_DEF)
        assert {"osint", "places"} <= set(_CANVAS_LAYERS_DEF)


OSINT_ID = "1b94e9d2-7e11-4174-a735-7dd3be3189cf"


class TestParseUrnOsint:
    def test_osint_event_takes_a_uuid(self):
        assert parse_urn(f"osint_event:{OSINT_ID}") == ("osint_event", OSINT_ID)
        assert parse_urn("OSINT_EVENT:" + OSINT_ID) is None  # kinds are lower-case
        assert parse_urn(f"osint_event:{OSINT_ID.upper()}") == ("osint_event", OSINT_ID)

    def test_place_takes_the_ct_slug(self):
        assert parse_urn("place:sg_highway") == ("place", "sg_highway")
        assert parse_urn("place:sector_v_salt_lake_bypass_106") == (
            "place", "sector_v_salt_lake_bypass_106")

    @pytest.mark.parametrize("urn", [
        "osint_event:not-a-uuid",
        f"osint_event:{OSINT_ID}x",
        "osint_event:",
        "place:Sector V",
        "place:-sg_highway",
        "place:SG_Highway",
        "place:sg-highway",
        "place:" + "a" * 65,
        "person:42",  # stays refused: events are about places, never persons
    ])
    def test_bad_ids_are_refused(self, urn):
        assert parse_urn(urn) is None


class TestPlateMaskLockstep:
    def test_state_codes_equal_the_oracles(self):
        assert _PLATE_STATE_CODES == _tuple_of_names(COMMON_SRC, "STATE_CODES")
        assert len(_PLATE_STATE_CODES) == 39

    def test_separator_set_is_the_oracles(self):
        """The same separator SET (matching behaviour; member order inside a
        character class does not matter)."""
        assert sorted(_MARK_SEP) == sorted(_oracle_mark_sep())

    def _oracle_plate_regex(self) -> re.Pattern:
        """The oracle's combined any-case rule, rebuilt from its parsed
        pieces (the oracle's own construction, its data)."""
        return re.compile(
            r"\b((" + "|".join(_PLATE_STATE_CODES) + r")" + _oracle_mark_sep()
            + r"\d{1,2}" + _oracle_mark_sep()
            + r"(?:([a-z]{1,3})(" + _oracle_mark_sep() + r"))?)(\d{4})\b",
            re.IGNORECASE | re.ASCII,
        )

    def test_any_case_plate_regex_matches_as_the_oracles(self):
        from convoy_brain.mcp.server import _PLATE_IN_TEXT_RE

        oracle_rx = self._oracle_plate_regex()
        corpus = [
            "mh06em9001", "MH06EM9001", "MH.06.EM.9001", "MH-01-AB-1234",
            "WB/06/EM/9001", "WB_06_EM_9001", "MH 01 AB 1234", "mh12qp9988",
            "As of 24 Oct 2026", "OD 24 Oct 2026", "MH 01 MAY 1234",
            "osint_event:1b94e9d2-7e11-4174-a735-7dd3be3189cf",
            "12:45", "2026", "report 4401/2026", "no marks here",
        ]
        for text in corpus:
            assert [m.group(0) for m in _PLATE_IN_TEXT_RE.finditer(text)] == [
                m.group(0) for m in oracle_rx.finditer(text)
            ], text
