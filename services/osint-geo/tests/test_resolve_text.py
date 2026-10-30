"""``resolve_text`` for ``GET /osint/gazetteer/resolve?q=`` (C-T): ranked, read-only gazetteer lookups of Mumbai
places, in English, Marathi and Hindi."""

from __future__ import annotations

import pytest

from osint_geo.resolver import resolve_text

KEYS = {"gaz_id", "canonical_name", "feature_type", "lon", "lat", "segment_id", "junction_id", "confidence", "method"}
#: The Western Express Highway's own segments (Kalanagar → Borivali, scripts/data/osm_network.json).
WEH = set(range(1013, 1020))
#: Lal Bahadur Shastri Marg's segments (Kurla → Ghatkopar → Vikhroli).
LBS = set(range(1038, 1043))


def test_the_ct_candidate_shape():
    out = resolve_text("Hindmata")
    assert out and all(set(c) == KEYS for c in out)
    top = out[0]
    assert top["gaz_id"] == 240 and top["canonical_name"] == "Hindmata (Dadar East)"
    # a recurring flooding spot pre-linked to its junction (Hindmata, junction 19)
    assert top["feature_type"] == "landmark" and top["junction_id"] == 19 and top["segment_id"] is None
    assert top["method"] == "gazetteer_exact" and 0.0 <= top["confidence"] <= 1.0


@pytest.mark.parametrize("q", ["Hindmata", "हिंदमाता", "hind mata", "Hindmata junction"])
def test_the_flooding_spot_by_its_usual_spellings(q):
    assert [c["canonical_name"] for c in resolve_text(q)] == ["Hindmata (Dadar East)"]


def test_junctions_roads_and_grammar():
    assert resolve_text("sion circle")[0]["junction_id"] == 23
    assert resolve_text("सायन सर्कल")[0]["junction_id"] == 23
    weh = resolve_text("WEH", limit=20)
    assert {c["segment_id"] for c in weh if c["canonical_name"] == "Western Express Highway"} == WEH
    assert all(c["feature_type"] == "road" for c in weh)
    top = resolve_text("Kalanagar chowk")[0]
    assert top["junction_id"] == 37 and top["method"] == "grammar"


def test_ranked_best_first_and_only_the_top_has_a_margin():
    out = resolve_text("Sion circle, Dharavi", limit=5)
    assert [c["feature_type"] for c in out[:2]] == ["junction", "neighbourhood"]
    assert out[0]["junction_id"] == 23 and out[1]["canonical_name"] == "Dharavi"
    assert out[0]["confidence"] > out[1]["confidence"]
    # F-HONEST OSINT-1: the bare area word is the neighbourhood alone, never the Dadar West junction (27) or the
    # station
    bare = resolve_text("dadar", limit=5)
    assert [c["feature_type"] for c in bare] == ["neighbourhood"] and bare[0]["segment_id"] is None
    assert bare[0]["junction_id"] is None and bare[0]["canonical_name"] == "Dadar"


def test_fuzzy_multi_word_only():
    fz = resolve_text("Wankhede Stadum")
    assert fz and fz[0]["gaz_id"] == 316 and fz[0]["method"] == "gazetteer_fuzzy"
    exact = resolve_text("Wankhede Stadium")
    assert fz[0]["confidence"] < exact[0]["confidence"]


@pytest.mark.parametrize(
    "q", ["india", "India", "road", "the", "", "zz", "Mumbai", "मुंबई", "dada", "Indra", "naka", "चौक", "setu",
          "airport", "kalanagar"]
)
def test_no_guess(q):
    assert resolve_text(q) == []


def test_limit_and_query_bounds():
    assert len(resolve_text("weh", limit=3)) == 3
    assert resolve_text("weh", limit=0) == [] and resolve_text("weh", limit=-5) == []
    assert len(resolve_text("weh", limit=10_000)) <= 50
    assert resolve_text("x" * 5000) == []


def test_an_operator_query_is_about_the_city():
    # the context gate is open for an operator's lookup: these resolve here although a national outlet's text
    # naming no Mumbai word would not
    assert resolve_text("fort")[0]["canonical_name"] == "Fort (Mumbai)"
    assert resolve_text("santacruz")[0]["canonical_name"] == "Santacruz"
    assert resolve_text("gandhi market")[0]["canonical_name"] == "Gandhi Market (Sion)"
    assert resolve_text("kasturba hospital")[0]["canonical_name"] == "Kasturba Hospital (Chinchpokli)"
    assert {c["feature_type"] for c in resolve_text("coastal road", limit=10)} == {"road"}
    assert resolve_text("airport") == []  # never the airport junctions by the common word
    assert resolve_text("mumbai airport t2")[0]["canonical_name"] == "Mumbai Airport T2"


@pytest.mark.parametrize("q", ["LBS Marg", "LBS road", "L B S Marg", "Lal Bahadur Shastri Marg", "एलबीएस मार्ग"])
def test_lbs_marg_by_its_usual_spellings(q):
    out = resolve_text(q, limit=10)
    # its own five segments, and the two Eastern Express Highway segments at Sion that OpenStreetMap also names
    # Lal Bahadur Shastri Marg for about 900 m each (1043, 1044)
    assert LBS <= {c["segment_id"] for c in out} <= LBS | {1043, 1044}
    assert {c["feature_type"] for c in out} == {"road"}


@pytest.mark.parametrize("q", ["CSMT", "CST station", "csmt station", "victoria terminus", "सीएसएमटी"])
def test_csmt_by_its_usual_spellings_is_the_terminus_landmark(q):
    # F-HONEST OSINT-1: the bare name is the terminus (a landmark pre-linked to junction 4), the junction entry only
    # by "CSMT junction"
    out = resolve_text(q)
    assert [c["canonical_name"] for c in out] == ["CSMT (Chhatrapati Shivaji Maharaj Terminus)"]
    assert out[0]["feature_type"] == "landmark" and out[0]["junction_id"] == 4
    j = resolve_text("CSMT junction")[0]
    assert (j["feature_type"], j["junction_id"], j["canonical_name"]) == ("junction", 4, "CSMT junction (D N Road)")


def test_read_only_and_deterministic():
    a = resolve_text("BMC headquarters")
    b = resolve_text("BMC headquarters")
    assert a == b and a[0]["canonical_name"] == "BMC headquarters"
    a[0]["canonical_name"] = "changed"
    assert resolve_text("BMC headquarters")[0]["canonical_name"] == "BMC headquarters"
