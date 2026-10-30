"""A forecast crossing becomes a PROPOSAL (never an action), with an English and a Marathi draft advisory."""

from datetime import UTC, datetime

from forecast.proposals import crossing_proposal


def _fc(sid: int) -> dict:
    return {"segment_id": sid, "now": {"vc": 0.7}, "data_label": "SIMULATED", "history_source": "test",
            "crossing": {"at": "2026-10-30T13:00:00+00:00", "in_min": 45, "vc_p10": 0.75, "vc_p50": 0.86,
                         "vc_p90": 0.97}}


def test_proposal_awaits_an_officer_and_drafts_marathi(mini_net):
    p = crossing_proposal(mini_net, _fc(9002), set(), datetime(2026, 10, 30, 12, 15, tzinfo=UTC), 0.8, 120,
                          ["SIMULATED", "MODELLED"], "test")
    assert p["state"] == "proposed" and p["recommendation"]["decision"] == "await_officer"
    assert p["human_gate"]["officer"] is None
    adv = next(a for a in p["actions"] if a["verb"] == "advisory")
    assert all(a["requires_officer"] for a in p["actions"])
    assert "Dadar TT Circle" in adv["params"]["draft_en"]
    assert adv["params"]["draft_mr"].startswith("दादर टीटी सर्कल जवळ सुमारे ४५ मिनिटांत")
    assert "after officer approval" in adv["params"]["channel"]


def test_no_marathi_draft_without_a_marathi_name(mini_net):
    p = crossing_proposal(mini_net, _fc(9005), set(), datetime(2026, 10, 30, 12, 15, tzinfo=UTC), 0.8, 120,
                          ["SIMULATED"], "test")
    adv = next(a for a in p["actions"] if a["verb"] == "advisory")
    assert "draft_mr" not in adv["params"] and adv["params"]["draft_en"]
