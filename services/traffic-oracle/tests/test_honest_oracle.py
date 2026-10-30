"""FIX-G-ORACLE: what the oracle serves is honest (pre-release audit F-HONEST, F-CONN).

One test (or a small group) per audit item; every one fails on the pre-change oracle:

* HON-4  — a pursuit opened on an emulated sighting is an EMULATED event (``metadata.evidence_source``), and an FIR
  on an emulated record is served as a demo reference;
* HON-7  — the top-weighted safety criterion is a fixed per-action prior: labelled so in the criteria table and
  the scoring note, and the dissent never claims a lead on it as a simulated win;
* HON-8  — the time-to-effect criterion is a nominal time per COA kind, labelled so (not an "ETA to scene");
* HON-9  — the surrogate's 108 delay belongs only to a COA that dispatches a 108;
* HON-10 — a junction's phase from the stored program is "planned (signal program)", never a bare live state;
* HON-11 — a synthetic / simulated feed's tag is never badged live;
* HON-18 — the EVOI ``why`` says the credibility it weighs is uncalibrated;
* OSINT-3 (DSS part) — an area-level report (a neighbourhood, a far snap, a stored ``area_level``) gets only
  monitoring, advisory and verify-first COAs: no closure or dispatch on a guessed road;
* F-CONN-12 — the dead ``traffic_oracle.synthetic`` package is gone;
* F-CONN-09 — a hand-run oracle binds loopback by default.

Synthetic only: emulated plates and fictional publishers, no person anywhere.
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from fixtures.dss.fakedss import BACKENDS, dss_app, dss_backend, load_fixture
from fixtures.osint.harness import client, reset_osint_state
from fixtures.osint.signals import PLACES, FakePipeline, new_tag, payload, rekey
from osint_common.testing import gariahat_robbery_signal
from osint_common.types import DecisionSupport, Geocode
from traffic_oracle.city import common
from traffic_oracle.city import entities as ent
from traffic_oracle.city import feed as feed_mod
from traffic_oracle.decision_support import coa, dissent, engine, mcda, voi, wargame
from traffic_oracle.decision_support.feasibility import UnitPlane
from traffic_oracle.decision_support.wargame import SegmentModel

#: the synthetic OSINT fixtures here predate the scope rule (tests/conftest.py)
SCOPE_GATE_OFF = True

NOW = datetime(2026, 10, 26, 7, 30, tzinfo=UTC)
FIR_TITLE = "PURSUIT — stolen WB06EM9001 (FIR 4401/2026, Hare Street PS)"


# ─── HON-4: the scripted pursuit of an emulated vehicle is EMULATED; its FIR a demo reference ───────────────


class TestHon4EmulatedPursuit:
    def _lifecycle(self):
        import test_event_lifecycle as lc

        return lc

    def _created_meta(self, pool, before: set) -> dict:
        (eid,) = set(pool.db.events) - before
        md = pool.db.events[eid]["metadata"]
        return json.loads(md) if isinstance(md, str) else md

    def test_a_pursuit_on_an_emulated_sighting_is_stamped_emulated(self):
        lc = self._lifecycle()
        pool = lc.LifecyclePool()
        pool.db.recs[lc.REC_APPROVED]["sighting_source"] = "emulated_anpr"
        before = set(pool.db.events)
        meta = {"vehicle_id": str(lc.VEHICLE), "recommendation_id": str(lc.REC_APPROVED),
                "fir": "FIR 4401/2026, Hare Street PS", "opened_by": "Duty Officer A"}
        r = lc._post(lc._app(pool), "/api/v1/events", lc._pursuit(meta))
        assert r.status_code in (200, 201), r.text
        stored = self._created_meta(pool, before)
        assert stored["evidence_source"] == "emulated"
        # the caller's own metadata is kept (no source was sent): the stamp alone makes it EMULATED
        assert "source" not in stored and stored["fir"] == "FIR 4401/2026, Hare Street PS"
        assert common.event_source(stored) == "emulated"

    @pytest.mark.parametrize(
        "rec_extra",
        [{"evidence_source": "emulated_anpr"}, {"vehicle_reads_emulated": True}],
    )
    def test_the_evidence_or_the_vehicle_reads_decide_too(self, rec_extra):
        from traffic_oracle.events import pursuit_evidence_emulated

        assert pursuit_evidence_emulated({"sighting_source": None, **rec_extra}) is True

    def test_a_pursuit_on_a_live_sighting_stays_live(self):
        lc = self._lifecycle()
        pool = lc.LifecyclePool()
        pool.db.recs[lc.REC_APPROVED].update(sighting_source="live_anpr", vehicle_reads_emulated=False)
        before = set(pool.db.events)
        r = lc._post(lc._app(pool), "/api/v1/events", lc._pursuit(
            {"vehicle_id": str(lc.VEHICLE), "recommendation_id": str(lc.REC_APPROVED)}))
        assert r.status_code in (200, 201), r.text
        stored = self._created_meta(pool, before)
        assert "evidence_source" not in stored and common.event_source(stored) == "live"

    def test_the_pursuit_query_reads_the_evidence_source_under_the_same_lock(self):
        from traffic_oracle import events as events_mod

        sql = events_mod._SQL_PURSUIT_RECOMMENDATION
        assert "AS sighting_source" in sql and "AS evidence_source" in sql and "AS vehicle_reads_emulated" in sql
        assert sql.rstrip().endswith("FOR SHARE") and " JOIN " not in sql  # the lock stays on the recommendation

    def _event_row(self, meta: dict) -> dict:
        return {"event_id": uuid.UUID(int=7), "event_kind": "vehicle_pursuit", "title": FIR_TITLE,
                "status": "planning", "protection_class": "none", "crowd_class": "LOW", "metadata": meta,
                "updated_at": NOW, "movement_id": None, "planned_start": None, "planned_end": None,
                "actual_start": None, "actual_end": None, "source_kind": None, "verification_state": None,
                "credibility": None}

    def test_the_city_entity_is_emulated_and_its_fir_a_demo_reference(self):
        meta = {"vehicle_id": str(uuid.UUID(int=1)), "recommendation_id": str(uuid.UUID(int=2)),
                "fir": "FIR 4401/2026, Hare Street PS", "evidence_source": "emulated"}
        e = ent.event_entity(self._event_row(meta), [], None, NOW)
        assert e["source"] == "emulated"
        assert e["label"] == "PURSUIT — stolen WB06EM•••1 (demo FIR 4401/2026, Hare Street PS)"
        assert e["props"]["title"] == "PURSUIT — stolen WB06EM9001 (demo FIR 4401/2026, Hare Street PS)"
        assert e["props"]["metadata"]["fir"] == "demo FIR 4401/2026, Hare Street PS"
        assert e["props"]["metadata"]["evidence_source"] == "emulated"

    def test_a_live_event_keeps_its_text(self):
        meta = {"fir": "FIR 4401/2026, Hare Street PS", "source": "operator"}
        e = ent.event_entity(self._event_row(meta), [], None, NOW)
        assert e["source"] == "live"
        assert "demo FIR" not in json.dumps(e)

    def test_the_vehicle_and_feed_rows_of_emulated_reads_say_demo_fir(self):
        row = {"vehicle_id": uuid.UUID(int=3), "plate": "WB06EM9001", "vehicle_class": "car", "state": "flagged",
               "lawful_basis": "stolen_vehicle_fir", "reason": "STOLEN VEHICLE reported — FIR 4401/2026, Hare Street PS",
               "retention_until": NOW + timedelta(days=20)}
        last = {"sighting_id": uuid.UUID(int=4), "camera_id": "EM-CAM-03", "speed_kmh": 95.0, "heading": 40.0,
                "matched_plate_hit": "stolen_vehicle", "lon": 88.38, "lat": 22.56, "t": NOW,
                "source": "emulated_anpr"}
        v = ent.vehicle_entity(row, last, NOW)
        assert v["source"] == "emulated"
        assert v["props"]["earmark_reason"] == "STOLEN VEHICLE reported — demo FIR 4401/2026, Hare Street PS"
        item = common.feed_item("x:1", NOW, "event", [], actor=None, actor_kind="system",
                                text="Event opened: " + FIR_TITLE, source="emulated")
        assert "(demo FIR 4401/2026, Hare Street PS)" in item["text"]
        live = common.feed_item("x:2", NOW, "event", [], actor=None, actor_kind="system",
                                text="Event opened: " + FIR_TITLE, source="live")
        assert "demo" not in live["text"]

    def test_mark_demo_fir_is_idempotent_and_leaves_other_text(self):
        assert common.mark_demo_fir("FIR 4401/2026") == "demo FIR 4401/2026"
        assert common.mark_demo_fir("demo FIR 4401/2026") == "demo FIR 4401/2026"
        assert common.mark_demo_fir("FIR No. 12/2026") == "demo FIR No. 12/2026"
        assert common.mark_demo_fir("AFFIRM the FIRE drill") == "AFFIRM the FIRE drill"
        assert common.mark_demo_fir({"a": ["FIR 7/2026"], "n": 3}) == {"a": ["demo FIR 7/2026"], "n": 3}

    def test_the_events_list_marks_an_emulated_events_fir(self):
        from traffic_oracle import events as events_mod

        class Conn:
            async def fetchval(self, sql: str, *args: Any) -> Any:
                return None  # no 018 relation: spines are the pre-018 read

            async def fetch(self, sql: str, *args: Any) -> list:
                return []

        common.reset_relation_cache()
        base = {"event_kind": "vehicle_pursuit", "protection_class": "none", "crowd_class": "LOW",
                "title": FIR_TITLE, "description": "pursuit of a FIR 4401/2026 vehicle", "status": "planning",
                "movement_id": None, "planned_start": None, "planned_end": None, "actual_start": None,
                "actual_end": None, "updated_at": NOW, "zone_geojson": None}
        emu = {**base, "event_id": uuid.UUID(int=8),
               "metadata": json.dumps({"fir": "FIR 4401/2026", "evidence_source": "emulated"})}
        live = {**base, "event_id": uuid.UUID(int=9), "metadata": json.dumps({"fir": "FIR 4401/2026"})}
        out = asyncio.run(events_mod._event_rows_out(Conn(), [emu, live]))
        by = {o["event_id"]: o for o in out}
        e, lv = by[str(uuid.UUID(int=8))], by[str(uuid.UUID(int=9))]
        assert e["title"].endswith("(demo FIR 4401/2026, Hare Street PS)")
        assert e["description"] == "pursuit of a demo FIR 4401/2026 vehicle"
        assert e["metadata"]["fir"] == "demo FIR 4401/2026"
        assert lv["title"] == FIR_TITLE and lv["metadata"]["fir"] == "FIR 4401/2026"


# ─── DSS fixtures ────────────────────────────────────────────────────────────


def _subject() -> tuple[dict, engine.Frame, SegmentModel, UnitPlane, coa.Anchors]:
    fx = load_fixture("sector_v_dss_input.json")
    frame = engine.frame_from_poc(fx)
    seg = SegmentModel.from_doc(fx["segment_model"])
    plane = UnitPlane.from_fixture(fx["units"])
    anchors = coa.Anchors(
        segment_id=1045, junction_id=None, route_segment_ids=(1045,),
        hold_junction_id=fx["anchors"]["hold_junction_id"], place_urn=fx["anchors"]["place_urn"],
        diversion_via=seg.parallel_routes,
    )
    return fx, frame, seg, plane, anchors


def _robbery(fx: dict) -> dict:
    """The Sector V fixture as a reported robbery: a class whose standard response dispatches NO 108, no injury."""
    doc = json.loads(json.dumps(fx))
    ev = doc["dss_input_event"]
    ev["event_class"] = "reported_crime"
    ev["correlated_classes"] = ["reported_crime"]
    ev["subtype"] = "daylight_robbery"
    ev["sajag_event_kind"] = "reported_crime"
    ev["note"] = "Robbery reported near the club"
    for s in ev["sources"]:
        s["title"] = "Robbery reported near the club"
    return doc


# ─── HON-7 / HON-8: the fixed priors are labelled and never claimed as a simulated win ─────────────────────


class TestHon7Hon8FixedPriors:
    def test_the_criteria_table_labels_the_safety_prior_and_the_nominal_time(self):
        fx, frame, seg, plane, anchors = _subject()
        doc, _ = engine.compute(frame, seg=seg, anchors=anchors, plane=plane, seed=fx["seed"])
        labels = {c["id"]: c["label"] for c in doc["criteria"]}
        assert labels["safety_risk_reduction"] == (
            "Public-safety risk reduction (fixed prior by COA actions, not simulated)")
        assert labels["time_to_effect"] == "Speed of effect (nominal time by COA kind, not a unit ETA)"
        assert "ETA to scene" not in json.dumps(doc["criteria"])
        note = doc["scoring_note"]
        assert "safety_risk_reduction is a fixed prior, not a simulated outcome" in note
        assert "time_to_effect is a nominal time per COA kind, not a unit ETA" in note

    def test_the_dissent_never_claims_a_safety_win_from_the_constant(self):
        fx, frame, seg, plane, anchors = _subject()
        doc, _ = engine.compute(frame, seg=seg, anchors=anchors, plane=plane, seed=fx["seed"])
        text = doc["recommendation"]["dissent"]
        assert "beats it on safety_risk_reduction" not in text
        assert "the pick leads it only on safety_risk_reduction (a fixed per-action prior" in text

    @pytest.mark.parametrize(
        "wins, expected",
        [
            (["cascade_risk", "safety_risk_reduction", "resource_cost"],
             "the pick beats it on cascade_risk, resource_cost (its largest weighted advantages); it also leads "
             "on safety_risk_reduction (a fixed per-action prior, not a simulated outcome), not a simulated "
             "advantage"),
            (["safety_risk_reduction", "cascade_risk"],
             "the pick beats it on cascade_risk (its only discriminating advantage outside the fixed priors); it "
             "also leads on safety_risk_reduction (a fixed per-action prior, not a simulated outcome), not a "
             "simulated advantage"),
            (["time_to_effect", "safety_risk_reduction"],
             "the pick leads it only on time_to_effect (a nominal time per COA kind, not a unit ETA) and "
             "safety_risk_reduction (a fixed per-action prior, not a simulated outcome) — so no simulated "
             "advantage is claimed"),
            (["cascade_risk"], "the pick beats it on cascade_risk (its only discriminating advantage)"),
        ],
    )
    def test_the_beats_clause(self, wins, expected):
        assert dissent._beats_clause(wins) == expected


# ─── HON-9: the 108 delay belongs to a COA that dispatches a 108 ─────────────────────────────────────────


class TestHon9AmbulanceDelay:
    def test_no_108_no_108_delay(self):
        fx, _, seg, plane, anchors = _subject()
        frame = engine.frame_from_poc(_robbery(fx))
        doc, _ = engine.compute(frame, seg=seg, anchors=anchors, plane=plane, seed=fx["seed"])
        by = {c["coa_id"]: c for c in doc["coa_set"]}
        for cid in ("coa_std", "coa_agg"):
            assert not any((a["params"] or {}).get("agency") == "ambulance" for a in by[cid]["actions"]), cid
            assert by[cid]["predicted_outcome"]["emergency_impact"] == {
                "ambulance_delay_sec": 0, "green_corridor_ok": True}, cid
        assert "delay the 108" not in doc["recommendation"]["dissent"]

    def test_a_coa_with_its_own_108_keeps_the_pocs_delay(self):
        fx, frame, seg, plane, anchors = _subject()  # road accident: the 108 is in coa_std and coa_agg
        doc, _ = engine.compute(frame, seg=seg, anchors=anchors, plane=plane, seed=fx["seed"])
        by = {c["coa_id"]: c["predicted_outcome"]["emergency_impact"]["ambulance_delay_sec"]
              for c in doc["coa_set"]}
        assert by["coa_std"] == -60 and by["coa_agg"] == 180

    def test_the_surrogate_alone(self):
        drafts = coa.build_coas(event_class="reported_crime",
                                anchors=coa.Anchors(segment_id=1045, junction_id=None, route_segment_ids=(1045,)))
        seg = SegmentModel(1045, "Sector V - New Town link", "primary", 3, 2800.0, 50.0, 1.0)
        out = wargame.surrogate_wargame(drafts, seg, seed=1, ambulance_eta_sec=480.0).outcomes
        assert {cid: o["emergency_impact"]["ambulance_delay_sec"] for cid, o in out.items()} == {
            "coa_base": 0, "coa_min": 0, "coa_std": 0, "coa_agg": 0, "coa_info": 0}


# ─── HON-10: a junction's phase is the program's plan ─────────────────────────────────────────────────────


def test_hon10_a_junction_phase_is_planned_never_live():
    row = {"junction_id": 15, "junction_type": "roundabout", "signal_control": True, "program_source": "osm_assumed",
           "cycle_sec": 110, "offset_sec": 17, "phases": json.dumps([
               {"index": 0, "movements": ["NS"], "green_sec": 50},
               {"index": 1, "movements": ["EW"], "green_sec": 50}]),
           "program_updated_at": NOW - timedelta(days=2), "lon": 88.3667, "lat": 22.5607,
           "doc": {"name": "Moulali"}}
    e = ent.junction_entity(row, NOW)
    assert e["state"] in ("planned_green", "planned_lost")
    assert e["props"]["phase_status"] == "planned (signal program)"
    assert e["props"]["live_phase"] is False and e["props"]["phase_basis"] == "program_clock"


# ─── HON-11: a synthetic feed is never live ──────────────────────────────────────────────────────────────


class TestHon11SyntheticNeverLive:
    @pytest.mark.parametrize("tag", ["synthetic", "Synthetic", "edge-synthetic", "simulated", "sim_feed", "sim"])
    def test_synthetic_tags(self, tag):
        assert common.label_source(tag) == "emulated"

    @pytest.mark.parametrize("tag", ["live_anpr", "gps", "FleetGps", "GovernmentTraffic", "simple", None])
    def test_real_tags_stay_live(self, tag):
        assert common.label_source(tag) == "live"

    def test_a_flag_on_the_simulated_feed_is_not_live(self):
        row = {"anomaly_id": 837, "segment_id": 1013, "road_name": "Indira Gandhi Sarani (Red Road)",
               "lon": 88.346, "lat": 22.56,
               "timestamp_utc": NOW, "anomaly_type": "speed_zscore", "severity": "medium", "flagged_at": NOW,
               "n_15m": 2, "details": json.dumps(
                   {"source": "FleetGps", "data_quality": "Anomalous", "feed_quality": "Synthetic"})}
        e = ent.anomaly_entity(row, NOW)
        assert e["source"] == "emulated" and e["props"]["data_quality"] == "synthetic"

    def test_a_synthetic_anpr_read_in_the_feed_is_not_live(self):
        item = feed_mod.anpr_item({"sighting_id": uuid.UUID(int=5), "vehicle_id": uuid.UUID(int=6),
                                   "camera_id": "EM-CAM-01", "t": NOW, "matched_plate_hit": "watchlist",
                                   "plate": "WB06EM4321", "speed_kmh": 40, "heading": 10,
                                   "source": "synthetic", "run_id": None})
        assert item["source"] == "emulated"


# ─── HON-18: the EVOI why says the credibility is uncalibrated ───────────────────────────────────────────


def test_hon18_the_evoi_why_says_uncalibrated():
    fx, frame, seg, plane, anchors = _subject()
    doc, _ = engine.compute(frame, seg=seg, anchors=anchors, plane=plane, seed=fx["seed"])
    why = doc["recommendation"]["value_of_information"]["why"]
    assert "credibility 0.65 is an uncalibrated source-prior score, not a measured probability" in why
    assert voi.dominant_term(doc["recommendation"]["value_of_information"]) == "act_now"  # the lead is unchanged


# ─── OSINT-3 (DSS part): an area-level report gets advisory / verify COAs only ─────────────────────────


def _geo(**kw: Any) -> Geocode:
    base = {"signal_id": "a" * 40, "toponym": "Tiljala", "feature_type": "neighbourhood", "lon": 88.382,
            "lat": 22.535, "segment_id": 1036, "junction_id": None, "snapped_to": "Eastern Metropolitan Bypass",
            "method": "gazetteer_exact", "residual_m": 1988.5, "confidence": 0.602, "bucket": "medium",
            "area_level": False, "area_scope": None, "alternatives": []}
    base.update(kw)
    return Geocode(**base)


class TestOsint3AreaLevel:
    def test_a_neighbourhood_is_an_area(self):
        why = engine.area_reason(area_level=False, segment_id=1036, junction_id=None, geocodes=[_geo()])
        assert why == "the report names a neighbourhood (Tiljala), an area, not a road position"

    def test_a_far_landmark_snap_is_not_a_road_anchor(self):
        g = _geo(toponym="Science City", feature_type="landmark", residual_m=2268.1)
        why = engine.area_reason(area_level=False, segment_id=1036, junction_id=None, geocodes=[g])
        assert why is not None and "2268 m from segment 1036" in why and "900 m" in why

    def test_one_precise_member_keeps_the_anchor(self):
        near = _geo(toponym="Eastern Metropolitan Bypass", feature_type="road", residual_m=0.0)
        assert engine.area_reason(area_level=False, segment_id=1036, junction_id=None,
                                  geocodes=[_geo(), near]) is None
        landmark = _geo(toponym="Salt Lake Stadium", feature_type="landmark", residual_m=190.5)
        assert engine.area_reason(area_level=False, segment_id=1036, junction_id=None, geocodes=[landmark]) is None
        junction = _geo(toponym="Babughat (Strand Road)", feature_type="junction", segment_id=None,
                        junction_id=11, residual_m=0.0)
        assert engine.area_reason(area_level=False, segment_id=None, junction_id=11, geocodes=[junction]) is None

    def test_a_stored_area_level_situation_with_a_segment_drops_it(self):
        assert engine.area_reason(area_level=True, segment_id=1045, junction_id=None) == "it is stored as area-level"

    def test_the_poc_frame_drops_an_area_reports_segment(self):
        fx = load_fixture("sector_v_dss_input.json")
        fx["dss_input_event"]["area_level"] = True
        frame = engine.frame_from_poc(fx)
        assert frame.route_segment_ids == () and frame.area_level is True
        assert frame.situation["segment_id"] is None and frame.situation["junction_id"] is None
        assert frame.area_note and "segment 1045" in frame.area_note
        seg = SegmentModel.from_doc(fx["segment_model"])
        plane = UnitPlane.from_fixture(fx["units"])
        anchors = coa.Anchors(segment_id=None, junction_id=None, place_urn=fx["anchors"]["place_urn"],
                              area_level=frame.area_level)
        doc, _ = engine.compute(frame, seg=seg, anchors=anchors, plane=plane, seed=fx["seed"])
        DecisionSupport.model_validate(doc)
        _only_advisory_and_verify(doc)
        assert "Area-level report: it is stored as area-level" in doc["recommendation"]["dissent"]

    @pytest.mark.parametrize("kind", BACKENDS)
    async def test_a_neighbourhood_report_through_generate(self, kind):
        """The snapped-neighbourhood case (a neighbourhood snapped to a road 1.30 km away; the fixture's
        ``kasba`` place, Kasba snapped to EM Bypass) on the fake graph: the report names only a neighbourhood,
        so the DSS never closes, diverts, holds or dispatches on the road it was snapped to."""
        hood = PLACES["kasba"]
        reset_osint_state()
        tag = new_tag()
        async with dss_backend(kind, tag) as bk:
            sig = rekey(gariahat_robbery_signal(), tag, title=f"Two-wheeler accident reported in {hood['toponym']}",
                        category_hint=["cluster:kasba", "class:road_accident"])
            bk.track(sig)
            app = dss_app(bk, FakePipeline(tag))
            async with client(app) as c:
                r = await c.post("/api/v1/osint/signals", json={"signals": [payload(sig)]})
                assert r.status_code == 200, r.text
                (oid,) = [i["osint_event_id"] for i in r.json()["resolved"]]
                bk.subjects.add(f"osint_event:{oid}")
                g = await c.post(f"/api/v1/decision-support/osint_event:{oid}/generate", json={})
            assert g.status_code == 201, g.text
            doc = g.json()
            bk.track_dss(doc["dss_id"])
            DecisionSupport.model_validate(doc)
            assert doc["situation"]["segment_id"] is None and doc["situation"]["junction_id"] is None
            assert doc["situation"]["toponym"] == hood["toponym"]
            assert doc["provenance"]["wargame_method"] == "surrogate"  # no twin run on a guessed road
            _only_advisory_and_verify(doc)
            text = doc["recommendation"]["dissent"]
            assert (f"Area-level report: the report names a neighbourhood ({hood['toponym']}), an area, not a road "
                    f"position, so the road it was snapped to (segment {hood['segment_id']}) is a guess") in text
        reset_osint_state()


def _only_advisory_and_verify(doc: dict) -> None:
    """Every COA that dispatches, closes, diverts or holds a signal is infeasible up front; only the
    monitoring, advisory and verify-first COAs can be approved (and one of them is the pick)."""
    approvable = set()
    for c in doc["coa_set"]:
        verbs = {a["verb"] for a in c["actions"]}
        if verbs & {"dispatch", "closure", "diversion", "signal_hold"}:
            assert not c["resource_feasibility"]["feasible"], c["coa_id"]
            assert "no road anchor: area-level report" in c["resource_feasibility"]["shortfalls"], c["coa_id"]
        elif c["resource_feasibility"]["feasible"]:
            approvable.add(c["kind"])
    assert approvable <= {"baseline", "minimal", "information"} and approvable
    top = next(c for c in doc["coa_set"] if c["coa_id"] == doc["recommendation"]["top_coa_id"])
    assert top["kind"] in ("baseline", "minimal", "information")


# ─── F-CONN-12 / F-CONN-09 ─────────────────────────────────────────────────────────────────────────────


def test_fconn12_the_dead_synthetic_package_is_gone():
    assert importlib.util.find_spec("traffic_oracle.synthetic") is None


def test_fconn09_a_hand_run_oracle_binds_loopback(monkeypatch):
    import traffic_oracle.__main__ as main_mod

    seen: dict[str, Any] = {}
    monkeypatch.delenv("HOST", raising=False)
    monkeypatch.setattr(main_mod, "create_app", lambda: object())
    monkeypatch.setattr(main_mod.uvicorn, "run", lambda app, **kw: seen.update(kw))
    main_mod.main()
    assert seen["host"] == "127.0.0.1"
    monkeypatch.setenv("HOST", "0.0.0.0")  # a bridge-network container opts in explicitly
    main_mod.main()
    assert seen["host"] == "0.0.0.0"
