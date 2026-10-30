"""The evaluation set: the report rules on the reference text.

This is the upper bound for the audio round trip (no ASR errors). It must
stay perfect: a rule change that breaks a phrase here is a regression.
"""

from __future__ import annotations

from collections import Counter

from speech_service.kinds import KINDS
from speech_service.places import Gazetteer
from speech_service.report import build_report


def test_mumbai_phrases_in_three_languages(phrases: list[dict], gaz: Gazetteer) -> None:
    langs = Counter(p["lang"] for p in phrases)
    assert set(langs) == {"mr", "hi", "en"} and min(langs.values()) >= 10, langs
    assert len({p["id"] for p in phrases}) == len(phrases)
    assert {p["kind"] for p in phrases} == set(KINDS)  # every kind, and "other"
    ids = {p.id for p in gaz.places}
    misses = []
    for p in phrases:
        assert p["place"] in ids
        rep = build_report(p["text"], gaz, source="field-text", language=p["lang"])
        got = (rep["place"] or {}).get("id")
        if got != p["place"] or rep["kind"] != p["kind"]:
            misses.append((p["id"], got, rep["kind"]))
        assert rep["verification_state"] == "UNVERIFIED-FIELD"
    assert misses == []
