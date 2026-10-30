"""PoC parity, asserted (the real PoC outputs read in place; skipped where the PoC directory is absent, e.g. CI)."""

from __future__ import annotations

import pytest

import poc_parity

OUT = poc_parity.poc_out_dir()
pytestmark = pytest.mark.skipif(
    not (OUT / "signals.raw.json").is_file(), reason=f"PoC outputs not present at {OUT} (read in place only)"
)


def test_all_107_poc_signals_validate():
    sig = poc_parity.check_signals(OUT)
    assert sig["total"] == 107
    assert sig["valid"] == 107, sig["failures"]
    assert sig["by_source"] == {"gdelt_doc": 8, "google_news_rss": 49, "reddit_rss": 40, "sachet_cap": 10}
    assert sig["pii_redactions"] == 60


def test_poc_dss_validates_once_the_cu_only_fields_are_defaulted():
    dss = poc_parity.check_dss(OUT)
    assert dss["valid"], dss.get("errors")
    assert dss["top_coa_id"] == "coa_std"
    assert dss["ranked"][-1] == "coa_agg" and dss["infeasible"] == ["coa_agg"]
    assert dss["consistency_ratio"] == pytest.approx(0.0346)
    assert dss["closeness"]["coa_std"] == pytest.approx(0.8555)
    assert dss["evoi"] == pytest.approx(-0.0105) and dss["advise_gather"] is False
    assert "SIMULATED" in dss["labels"] and dss["wargame_method"] == "surrogate"


def test_fused_kinds_are_known_and_never_crime_incident():
    fused = poc_parity.check_fused(OUT)
    assert fused["fused"] == 13 and fused["surfaced"] == 3
    assert fused["unknown_kinds"] == [] and fused["crime_incident"] == 0
