import asyncio
import json
from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient

from conftest import NOW, make_hydro
from hydro.api import create_app
from hydro.config import Settings
from hydro.replay import (DEFAULT_EVENT, EVENTS, IMD_STATIONS, IMD_WINDOWS, MAY_12H, MAY_HOUR_0910, REPORTED,
                          REPORTED_MAY, station_series, replay)

DATA = Path(__file__).resolve().parents[1] / "src" / "hydro" / "data"


def test_dry_nowcast_is_all_class_0_with_labelled_drivers(hydro_dry):
    nc = asyncio.run(hydro_dry.nowcast(now=NOW))
    assert nc["counts_by_class"]["0"] == len(hydro_dry.net.segments) and nc["flagged"] == []
    assert nc["labels"] == {"rain": "LIVE", "tide": "MODELLED (approximate)", "susceptibility": "MODELLED",
                            "pumps": "EMULATED", "risk": "MODELLED"}
    d = nc["segments"][0]["drivers"]
    assert d["rain"]["label"] == "LIVE" and d["tide"]["label"].startswith("MODELLED")
    assert d["susceptibility"]["label"] == "MODELLED" and d["pumps"]["label"] == "EMULATED"
    assert [p for p in nc["proposals"]] == []


def test_storm_flags_segments_with_lead_times_and_proposals(hydro_storm):
    nc = asyncio.run(hydro_storm.nowcast(now=NOW))
    segs = {s["segment_id"]: s for s in nc["segments"]}
    assert len(nc["flagged"]) > 10
    for sid in nc["flagged"]:
        s = segs[sid]
        assert s["risk_class"] >= 2 and not s["elevated"]
        assert s["expected_depth_band"] in ("10–30 cm", "> 30 cm")
        assert 0 <= s["lead_time_min"] <= 120
    for sid, s in segs.items():
        if s["elevated"]:
            assert s["risk_class"] == 0
    kinds = [p["kind"] for p in nc["proposals"]]
    n = len(nc["flagged"])
    assert kinds.count("waterlogging_reroute") == n and kinds.count("live_wire_hazard") == n
    assert kinds.count("ambulance_window") == n and kinds.count("public_advisory_draft") == 1
    assert kinds.count("pump_request") == 1
    for p in nc["proposals"]:
        assert p["state"] == "proposed" and p["recommendation"]["decision"] == "await_officer"
        assert p["human_gate"]["officer"] is None and p["human_gate"]["required_role"] == "duty_officer"
        assert all(a["requires_officer"] for a in p["actions"])
    wire = next(p for p in nc["proposals"] if p["kind"] == "live_wire_hazard")
    assert wire["for_officer_approval"] and wire["actions"][0]["params"]["to_agency"] == "power"
    adv = next(p for p in nc["proposals"] if p["kind"] == "public_advisory_draft")
    assert "पाणी साचण्याची शक्यता" in adv["text"]["mr"] and "waterlogging" in adv["text"]["en"]
    assert "जलभराव" in adv["text"]["hi"] and adv["subject_urn"] == "place:mumbai"
    for lang in ("en", "mr", "hi"):
        assert "112" in adv["text"][lang] and "1916" in adv["text"][lang] and "(108)" in adv["text"][lang]
    assert any("\u0900" <= ch <= "\u097f" for ch in adv["text"]["mr"])
    assert not any("\u0980" <= ch <= "\u09ff" for lang in ("mr", "hi") for ch in adv["text"][lang])  # no Bengali
    rr = next(p for p in nc["proposals"] if p["kind"] == "waterlogging_reroute")
    assert "best" in rr["actions"][0]["params"]["notify_agencies"]
    amb = next(p for p in nc["proposals"] if p["kind"] == "ambulance_window")
    assert amb["actions"][0]["params"]["nearest_hospital"]["id"] in ("kem", "sion_hospital", "nair_hospital",
                                                                     "jj_hospital", "cooper_hospital")
    pr = next(p for p in nc["proposals"] if p["kind"] == "pump_request")
    assert pr["actions"][0]["params"]["helpline"] == "1916" and "EMULATED" in pr["summary"]
    assert 1 <= len(pr["actions"][0]["params"]["sites"]) <= 8
    tide = segs[nc["flagged"][0]]["drivers"]["tide"]
    assert tide["station"].startswith("Apollo Bunder") and tide["gate_close_level_m"] == 4.5
    assert 0.0 <= tide["outfall_restriction_now"] <= 1.0


def test_station_series_keeps_every_observed_window_total():
    from datetime import UTC, datetime, timedelta

    start = datetime(2025, 8, 18, 14, 30, tzinfo=UTC) + timedelta(minutes=15)  # 20:00 IST + one step
    n = 100
    want = (IMD_WINDOWS["night"]["santacruz"] + (IMD_WINDOWS["day1_24h"]["santacruz"] - IMD_WINDOWS["night"]["santacruz"])
            + IMD_WINDOWS["day2_24h"]["santacruz"])
    flat = station_series("santacruz", start, n)
    timing = np.zeros(n)
    timing[50:54] = 20.0  # a burst inside the 08:30–15:00 window
    timed = station_series("santacruz", start, n, timing=timing)
    for s in (flat, timed):
        assert abs(np.sum(s) * 0.25 - want) < 1e-6
    assert timed.max() > 2 * flat.max()  # the archive's timing concentrates the window's total
    # Mahalaxmi has no 20-Aug figure: it is filled from the other stations, never left at zero
    assert np.sum(station_series("mahalaxmi", start, n)[60:]) > 0
    assert {k for k, *_ in IMD_STATIONS} == set(IMD_WINDOWS["night"])


def test_replay_runs_and_honest_check():
    hy = make_hydro(0.0, burst=12.0)
    rp = asyncio.run(replay(hy, DEFAULT_EVENT))
    assert DEFAULT_EVENT == "2025-08-19" and rp["title"].startswith("Mumbai")
    arc, gauge, flat = (rp["runs"][k] for k in ("open_meteo_archive", "imd_gauge_anchored",
                                                 "imd_gauge_flat_sensitivity"))
    # the mocked archive carries 1 mm/h (+ a 12 mm/h burst): nothing floods on its own rain, and it says why
    assert arc["flagged_segments"] == 0 and "finding" in arc
    assert gauge["flagged_segments"] > 5 and gauge["reported_check"]["hit_rate"] >= 0.5
    assert flat["flagged_segments"] < gauge["flagged_segments"] and flat["label"].startswith("SENSITIVITY")
    assert gauge["earliest_flag_ist"].startswith("2025-08-19")
    assert rp["official"]["imd_24h_to_0830_19aug_mm"]["santacruz"] == 238.2
    assert rp["tide"]["label"].startswith("MODELLED") and rp["tide"]["station"].startswith("Apollo Bunder")
    assert [h["at"][11:16] for h in rp["tide"]["high_waters_ist"]][0] == "09:04"
    assert len(gauge["reported_check"]["items"]) == len(REPORTED)
    for it in gauge["reported_check"]["items"]:
        assert it["sources"] and it["reported_by_ist"]
        if it["lead_before_first_report_min"] is not None:
            assert it["warning_lead_perfect_nowcast_min"] == it["lead_before_first_report_min"] + 120
            assert not it["roundup_after_window"]
    assert gauge["reported_check"]["off_network"]  # listed, not scored
    assert "not called a false alarm" in rp["honesty"] and "upper bound" in rp["honesty"]
    snap = gauge["snapshot"]
    assert snap["label"].startswith("HINDSIGHT") and snap["flagged_within_horizon"] >= snap["flagged_now"]


def test_may_series_keeps_the_observed_hour_and_the_12h_totals():
    from datetime import UTC, datetime, timedelta

    start = datetime(2025, 5, 25, 16, 30, tzinfo=UTC) + timedelta(minutes=15)  # 22:00 IST + one step
    n = 68
    timing = np.ones(n)
    timing[20:24] = 30.0
    for st in ("nariman_point", "dadar"):
        s = station_series(st, start, n, timing=timing, event="2025-05-26")
        assert abs(np.sum(s) * 0.25 - MAY_12H[st]) < 1e-6
    s = station_series("nariman_point", start, n, timing=timing, event="2025-05-26")
    i0 = int((datetime(2025, 5, 26, 3, 30, tzinfo=UTC) - start).total_seconds() // 900) + 1  # 09:00 IST
    assert abs(np.sum(s[i0:i0 + 4]) * 0.25 - MAY_HOUR_0910["nariman_point"]) < 1e-6  # the observed hour


def test_may_replay_uses_the_reported_pump_failures():
    hy = make_hydro(0.0, burst=12.0)
    rp = asyncio.run(replay(hy, "2025-05-26"))
    assert set(EVENTS) == {"2025-08-19", "2025-05-26"} and rp["title"].startswith("Mumbai")
    assert rp["pumps"]["availability"]["hindmata_mps"] == 0.0 and rp["pumps"]["label"].startswith("AS REPORTED")
    g = rp["runs"]["imd_gauge_anchored"]["reported_check"]
    assert len(g["items"]) == len(REPORTED_MAY)
    # evening round-ups say where, not when: no lead is computed from them
    for it in g["items"]:
        if it["roundup_after_window"]:
            assert it["lead_before_first_report_min"] is None
    assert any(h["at"].startswith("2025-05-26T11:2") for h in rp["tide"]["high_waters_ist"])


def test_recorded_replay_matches_the_live_run_summary():
    """eval/replay_2025-08-19.json is the committed live run (Open-Meteo archive called on 30 Oct 2026)."""
    for ev in EVENTS:
        rec = json.loads((Path(__file__).resolve().parents[1] / "eval" / f"replay_{ev}.json").read_text())
        g = rec["runs"]["imd_gauge_anchored"]["reported_check"]
        assert g["on_network"] == len([i for i in g["items"] if i["on_network"]]) and g["flagged"] <= g["on_network"]
        assert rec["runs"]["open_meteo_archive"]["window_total_mm_city_mean"] < 200  # the grid misses the storm


def test_data_files_cover_the_network(hydro_dry):
    sus = json.loads((DATA / "susceptibility.json").read_text())
    assert set(sus["segments"]) == {str(s) for s in hydro_dry.net.segments}
    assert sus["label"] == "MODELLED" and "Copernicus" in sus["inputs"]["dem"]["product"]
    elevated = {k for k, v in sus["segments"].items() if v["elevated"]}
    assert elevated >= {"1006", "1007", "1008", "1009", "1058", "1059"}  # Coastal Road, Sea Link, Eastern Freeway
    assert not elevated & {"1013", "1014", "1015", "1016"}  # the Western Express Highway runs at grade
    under = {k: v for k, v in sus["segments"].items() if v.get("underpass")}
    assert set(under) == {"1027", "1030"} and all(v["score"] >= 0.9 for v in under.values())  # Milan, Andheri
    hs = json.loads((DATA / "hotspots.json").read_text())
    for h in hs["hotspots"]:
        assert h["sources"] or h.get("unverified") is True
        for s in h["sources"]:
            assert hs["sources"][s]["url"].startswith("http")


def _client(mm=0.0):
    hy = make_hydro(mm)
    return TestClient(create_app(Settings(), hydro=hy))


def test_api_endpoints():
    with _client(5.0) as c:
        h = c.get("/health").json()
        assert h["status"] == "ok" and h["labels"]["pumps"].startswith("EMULATED")
        nc = c.get("/hydro/nowcast").json()
        assert len(nc["segments"]) == h["network"]["segments"]
        t = c.get("/hydro/tide", params={"hours": 6}).json()
        assert t["label"].startswith("MODELLED") and len(t["series"]) == 25 and t["sources"]
        assert c.get("/hydro/tide", params={"hours": 100}).status_code == 422
        r = c.get("/hydro/rain").json()
        assert r["label"] == "LIVE" and len(r["points"]) == 18 and r["city"]["series"]
        assert t["station"].startswith("Apollo Bunder") and t["gate_close_level_m"] == 4.5
        assert all(0.0 <= x["outfall_restriction"] <= 1.0 for x in t["series"])
        p = c.get("/hydro/pumps").json()
        assert p["label"] == "EMULATED" and all(s["label"] == "EMULATED" for s in p["stations"])
        assert p["published"]["major_pumps_total"] == 43
        assert c.post("/hydro/replay", params={"event": "1999-01-01"}).status_code == 404
        rp = c.post("/hydro/replay").json()
        assert set(rp["runs"]) == {"open_meteo_archive", "imd_gauge_anchored", "imd_gauge_flat_sensitivity"}
