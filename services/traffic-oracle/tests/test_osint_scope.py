"""The OSINT scope gate at the oracle's trust boundary (osint_common.scope, traffic_oracle.osint.ingest).

Events are about places and road situations: a person-crime report, a clash between groups and a political item
are rejected (``out_of_scope_*``) and never stored; a procession or gathering on a road is kept with its political
terms withheld; a stored signal from before the rule is left out of re-fusion. English, Marathi and Hindi
headlines, all synthetic. This module runs with the gate ON (it never sets ``SCOPE_GATE_OFF``).
"""

from __future__ import annotations

from typing import Any

import pytest

from fixtures.osint.harness import BACKENDS, backend, client, make_app
from fixtures.osint.signals import FakePipeline, canonical_set, new_tag, payload
from osint_common.types import RawOsintSignal
from traffic_oracle.osint import ingest


def _with_text(base: RawOsintSignal, title: str, text: str = "") -> RawOsintSignal:
    return RawOsintSignal.model_validate(dict(base.model_dump(), title=title, text=text))


async def _post(app: Any, signals: list[Any]) -> Any:
    async with client(app) as c:
        return await c.post("/api/v1/osint/signals", json={"signals": [payload(s) for s in signals]})


async def _stored(bk: Any, signal_id: str) -> dict | None:
    if bk.db is not None:
        return bk.db.signals.get(signal_id)
    async with bk.pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM osint.raw_signals WHERE signal_id = $1", signal_id)
    return dict(row) if row else None


# ── the verdicts, signal by signal ───────────────────────────────────────────


DROPPED = [
    # crime
    ("Daylight robbery at a jewellery shop near Gariahat crossing", "crime"),
    ("Chain snatching reported on Rash Behari Avenue", "crime"),
    ("গড়িয়াহাটে ছিনতাই, গ্রেপ্তার এক", "crime"),
    ("बेहाला में चोरी, एक गिरफ्तार", "crime"),
    # a clash between groups
    ("Clash between two groups near Behala Chowrasta, stones pelted", "conflict"),
    ("বেহালায় দুই গোষ্ঠীর সংঘর্ষ", "conflict"),
    ("बेहाला में दो गुटों में झड़प", "conflict"),
    # political (no road impact)
    ("Pre-poll meeting of party workers at a community hall in Tollygunge", "political"),
    ("নির্বাচনের প্রার্থী তালিকা প্রকাশ", "political"),
    ("उपचुनाव के लिए मतदान कल", "political"),
    # the live item that started this: pre-poll clash, post-poll case, Lalbazar (already redacted); a case is
    # tested first, so it reads as crime (it would be refused as conflict and as political too)
    ("[WITHHELD] ভোটের আগে সংঘর্ষ, ভোট-পরবর্তী [WITHHELD] মামলা নিয়ে [WITHHELD] লালবাজার", "crime"),
]

KEPT = [
    "Bus and truck collide on EM Bypass near Ruby, traffic slow towards Science City",
    "Heavy rain waterlogs Thanthania; Bidhan Sarani slow",
    "Fire at a godown in Burrabazar, fire tenders on MG Road",
    "Durga Puja procession on Strand Road: roads closed till 22:00",
    "থানতানিয়ায় জল জমে যানজট",
    "हावड़ा ब्रिज पर भारी जाम",
    "Thunderstorm warning for Kolkata and Howrah",
]


@pytest.fixture
def base() -> RawOsintSignal:
    return canonical_set(new_tag())["em_bypass"][0]


@pytest.mark.parametrize(("title", "reason"), DROPPED)
def test_out_of_scope_items_are_refused_by_reason(base, title, reason):
    kept, out, masked = ingest.scope_screen(_with_text(base, title))
    assert kept is None and out == reason and masked == 0


@pytest.mark.parametrize("title", KEPT)
def test_road_crowd_weather_and_hazard_items_pass_unchanged(base, title):
    kept, out, masked = ingest.scope_screen(_with_text(base, title))
    assert out is None and masked == 0 and kept is not None and kept.title == title


@pytest.mark.parametrize(
    ("title", "kept_words"),
    [
        ("Political rally of party workers blocks AJC Bose Road, traffic diverted", "rally"),
        ("রাজনৈতিক মিছিলে ধর্মতলায় যানজট", "মিছিলে"),
        ("राजनीतिक रैली से सड़क जाम", "रैली"),
    ],
)
def test_a_gathering_on_a_road_stays_with_its_political_terms_withheld(base, title, kept_words):
    kept, out, masked = ingest.scope_screen(_with_text(base, title))
    assert out is None and masked >= 1 and kept is not None
    assert "[WITHHELD]" in kept.title and kept_words in kept.title
    for word in ("Political", "party workers", "রাজনৈতিক", "राजनीतिक"):
        assert word not in kept.title


def test_the_classifier_class_is_screened_too(base):
    # no crime, clash or political WORD, but the lexicon classes it unrest (a bandh): political
    kept, out, _ = ingest.scope_screen(_with_text(base, "Bandh called: shops shut at Gariahat"))
    assert kept is None and out == "political"


def test_the_window_leaves_stored_out_of_scope_signals_out(base):
    crash = canonical_set(new_tag())["em_bypass"]
    robbery = canonical_set(new_tag())["gariahat"]
    kept, left_out = ingest.scope_window([*crash[:2], robbery])
    assert [s.signal_id for s in kept] == [s.signal_id for s in crash[:2]]
    assert dict(left_out) == {"crime": 1}


# ── end to end through POST /api/v1/osint/signals ───────────────────────────


@pytest.mark.parametrize("kind", BACKENDS)
async def test_a_reported_robbery_is_rejected_counted_and_never_stored(kind):
    tag = new_tag()
    robbery = canonical_set(tag)["gariahat"]
    async with backend(kind, tag) as bk:
        bk.track(robbery)
        app = make_app(bk.pool, FakePipeline(tag))
        reply = (await _post(app, [robbery])).json()
        assert reply["accepted"] == 0
        assert reply["rejected"] == [{"signal_id": robbery.signal_id, "reason": "out_of_scope_crime"}]
        assert reply["scope"]["rejected"] == {"crime": 1}
        assert await _stored(bk, robbery.signal_id) is None


@pytest.mark.parametrize("kind", BACKENDS)
async def test_the_clash_beside_a_collision_is_refused_and_the_collision_kept(kind):
    tag = new_tag()
    crash = canonical_set(tag)["em_bypass"]
    async with backend(kind, tag) as bk:
        bk.track(*crash)
        app = make_app(bk.pool, FakePipeline(tag))
        reply = (await _post(app, crash)).json()
        reasons = [r["reason"] for r in reply["rejected"]]
        assert reasons == ["out_of_scope_conflict"]
        assert reply["accepted"] == len(crash) - 1
        assert reply["scope"]["rejected"] == {"conflict": 1}


@pytest.mark.parametrize("kind", BACKENDS)
async def test_a_kept_gathering_is_stored_with_its_political_terms_withheld(kind):
    tag = new_tag()
    base = canonical_set(tag)["em_bypass"][0]
    rally = _with_text(base, "Political rally of party workers blocks EM Bypass near Ruby, traffic diverted")
    async with backend(kind, tag) as bk:
        bk.track(rally)
        app = make_app(bk.pool, FakePipeline(tag))
        reply = (await _post(app, [rally])).json()
        assert reply["accepted"] == 1 and reply["scope"]["masked_terms"] >= 2
        stored = await _stored(bk, rally.signal_id)
        assert stored is not None
        assert "Political" not in stored["title"] and "party workers" not in stored["title"]
        assert "[WITHHELD]" in stored["title"] and "EM Bypass" in stored["title"]
