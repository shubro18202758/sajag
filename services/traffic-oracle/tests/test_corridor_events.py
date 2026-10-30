"""Corridor-event generalization tests (core stream).

Covers the event-agnostic extensions that must not disturb the VVIP base
case: SituationInputs public-event profile fields, the merged
situation-engine subject query (events + legacy movements), the events API
request model (incl. the 013 ``officer`` creation actor), the
/events/active row shape with its lifecycle fields (spines and phases read
in two batched queries), EMERGENCY_VEHICLE scheduling, and the
ambulance-rate multiplier.
"""

from __future__ import annotations

import asyncio
from datetime import datetime

import pytest

from traffic_oracle.adaptive.engine_loop import _load_active_movements
from traffic_oracle.adaptive.enums import (
    CrowdDensity,
    ProtectionClass,
    SecurityTier,
    SituationClass,
)
from traffic_oracle.adaptive.inputs import SituationInputs, round_trip
from traffic_oracle.adaptive.situation import SECURITY_POINTS, SituationEngine
from traffic_oracle.events import CorridorEventRequest, EVENT_KINDS, event_inputs_key
from traffic_oracle.simulation.engine import ClosurePolicy, SimulationEngine
from traffic_oracle.simulation.events import (
    EventConfig,
    EventSource,
    EventType,
    ScheduledEvent,
)
from traffic_oracle.simulation.network import default_network
from traffic_oracle.simulation.scenarios import (
    SCENARIO_LIBRARY,
    ScenarioSpec,
    get_scenario,
    list_scenarios,
)

USE_CASE_IDS = (
    "vvip_convoy_base",
    "ganesh_visarjan_girgaon",
    "cloudburst_high_tide",
    "cyclone_landfall_recovery",
    "wankhede_egress",
    "sea_link_breakdown_surge",
    "shivaji_park_parade",
    "gateway_ferry_transit",
    "mumbai_marathon",
    "marine_drive_new_year",
    "weh_crash_ambulance",
    "metro_work_zone",
    "crawford_market_fire",
    "mithi_overflow_kurla",
    "diwali_air_quality",
    "october_heat_breakdowns",
    "weh_treefall_squall",
    "ganeshotsav_night",
    "dadar_surge",
)

USE_CASE_KINDS = {
    "vvip_convoy_base": "protected_movement",
    "ganesh_visarjan_girgaon": "mass_gathering",
    "cloudburst_high_tide": "emergency_evacuation",
    "cyclone_landfall_recovery": "work_zone",
    "wankhede_egress": "egress_surge",
    "sea_link_breakdown_surge": "egress_surge",
    "shivaji_park_parade": "ceremonial",
    "gateway_ferry_transit": "mass_gathering",
    "mumbai_marathon": "race",
    "marine_drive_new_year": "mass_gathering",
    "weh_crash_ambulance": "emergency_evacuation",
    "metro_work_zone": "work_zone",
    "crawford_market_fire": "emergency_evacuation",
    "mithi_overflow_kurla": "emergency_evacuation",
    "diwali_air_quality": "mass_gathering",
    "october_heat_breakdowns": "work_zone",
    "weh_treefall_squall": "work_zone",
    "ganeshotsav_night": "procession",
    "dadar_surge": "egress_surge",
}


# ── SituationInputs extension ───────────────────────────────────────────────


class TestSituationInputsExtension:
    def test_crowd_class_overrides_score_derived_level(self):
        explicit = SituationInputs.from_scores(
            vvip_class="none",
            predicted_congestion_idx=0.2,
            crowd_score=0.1,           # would derive LOW
            crowd_class="EXTREME",     # public-event profile override
        )
        assert explicit.crowd is CrowdDensity.EXTREME
        assert explicit.crowd_class is CrowdDensity.EXTREME
        score_only = SituationInputs.from_scores(
            vvip_class="none",
            predicted_congestion_idx=0.2,
            crowd_score=0.1,
        )
        assert score_only.crowd is CrowdDensity.LOW
        assert score_only.crowd_class is None

    def test_duration_class_round_trip(self):
        inputs = SituationInputs.from_scores(
            vvip_class="none",
            predicted_congestion_idx=0.2,
            duration_class="multi_week",
        )
        assert round_trip(inputs) == inputs
        assert inputs.to_dict()["duration_class"] == "multi_week"
        assert inputs.to_dict()["crowd_class"] is None

    def test_base_case_defaults_unchanged(self):
        """No crowd_class/duration_class given → legacy fields verbatim."""
        inputs = SituationInputs.from_scores(
            vvip_class="Z+", predicted_congestion_idx=0.5
        )
        d = inputs.to_dict()
        assert d["crowd_class"] is None
        assert d["duration_class"] == "minutes"
        assert d == {
            "vvip_class": "Z+", "traffic_regime": "HEAVY", "weather": "CLEAR",
            "crowd": "LOW", "anomaly_active": False, "event_active": False,
            "crowd_class": None, "duration_class": "minutes",
        }

    def test_public_event_classifies_through_crowd_not_security(self):
        engine = SituationEngine()
        calm = engine.classify(SituationInputs.from_scores(
            vvip_class="none", predicted_congestion_idx=0.2))
        assert calm.situation_class is SituationClass.GREEN
        assert SECURITY_POINTS[SecurityTier.NONE] == 0
        packed = engine.classify(SituationInputs.from_scores(
            vvip_class="none", predicted_congestion_idx=0.95,
            crowd_class="EXTREME", event_active=True, anomaly_active=True))
        # 0 sec + 6 traffic + 0 weather + 3 crowd + 2 anomaly + 1 event = 12 → RED
        assert packed.severity_score == 12
        assert packed.situation_class is SituationClass.RED
        assert packed.code.startswith("none:")

    def test_protection_class_alias(self):
        assert ProtectionClass is SecurityTier
        assert SecurityTier.from_code("PUBLIC") is SecurityTier.NONE


# ── Engine-loop subject merge (events + legacy movements) ───────────────────


class _FakeConn:
    def __init__(self, event_rows, movement_rows):
        self._event_rows = event_rows
        self._movement_rows = movement_rows
        self.queries = []

    async def fetch(self, sql):
        self.queries.append(sql)
        if "events.corridor_events" in sql:
            return self._event_rows
        return self._movement_rows


class _FakeAcquire:
    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, *exc):
        return False


class _FakePool:
    def __init__(self, conn):
        self._conn = conn

    def acquire(self):
        return _FakeAcquire(self._conn)


class TestEngineLoopSubjectMerge:
    def test_events_and_movements_merged_events_first(self):
        conn = _FakeConn(
            event_rows=[
                {"event_id": "e-1", "protection_class": "none"},
                {"event_id": "e-2", "protection_class": "Z"},
            ],
            movement_rows=[
                {"movement_id": "m-1", "vvip_class": "Z+"},
                # an event soft-links this movement id: must not duplicate
                {"movement_id": "e-2", "vvip_class": "Z"},
            ],
        )
        subjects = asyncio.run(_load_active_movements(_FakePool(conn)))
        assert subjects == [
            ("e-1", "none"),
            ("e-2", "Z"),
            ("m-1", "Z+"),
        ]
        assert any("events.corridor_events" in q for q in conn.queries)
        assert any("convoy.movements" in q for q in conn.queries)

    def test_events_table_missing_degrades_to_movements(self):
        class _BrokenEventsConn(_FakeConn):
            async def fetch(self, sql):
                if "events.corridor_events" in sql:
                    raise RuntimeError("relation does not exist (007 pending)")
                return await _FakeConn.fetch(self, sql)

        conn = _BrokenEventsConn([], [{"movement_id": "m-1", "vvip_class": "Y"}])
        subjects = asyncio.run(_load_active_movements(_FakePool(conn)))
        assert subjects == [("m-1", "Y")]

    def test_inputs_key_shape(self):
        assert event_inputs_key("abc") == "adaptive:inputs:abc"


# ── Events API request model ────────────────────────────────────────────────


class TestCorridorEventRequest:
    def test_defaults_are_public_event(self):
        req = CorridorEventRequest(
            event_kind="procession", title="Bijoya Dashami immersion procession",
            route_spines=[{"segment_ids": [1012]}],
        )
        assert req.protection_class == "none"
        assert req.crowd_class == "LOW"

    def test_invalid_kind_rejected(self):
        with pytest.raises(ValueError):
            CorridorEventRequest(
                event_kind="parade",  # not one of the 8 archetypes
                title="x", route_spines=[{"segment_ids": [1]}],
            )

    def test_invalid_protection_class_rejected(self):
        with pytest.raises(ValueError):
            CorridorEventRequest(
                event_kind="race", protection_class="Q",
                title="x", route_spines=[{"segment_ids": [1]}],
            )

    def test_invalid_crowd_class_rejected(self):
        with pytest.raises(ValueError):
            CorridorEventRequest(
                event_kind="race", crowd_class="PACKED",
                title="x", route_spines=[{"segment_ids": [1]}],
            )

    def test_officer_is_optional_trimmed_and_bounded(self):
        req = CorridorEventRequest(
            event_kind="race", title="x", route_spines=[{"segment_ids": [1]}],
        )
        assert req.officer is None
        req = CorridorEventRequest(
            event_kind="race", title="x", route_spines=[{"segment_ids": [1]}],
            officer="  Duty   Officer A ",
        )
        assert req.officer == "Duty Officer A"
        for bad in ("x", "  ", "z" * 65):
            with pytest.raises(ValueError):
                CorridorEventRequest(
                    event_kind="race", title="x", route_spines=[{"segment_ids": [1]}],
                    officer=bad,
                )

    def test_event_kinds(self):
        # 010 (C3 lockstep): + crime_incident + vehicle_pursuit;
        # 021 (C3 lockstep): + the six OSINT reported-situation kinds
        assert len(EVENT_KINDS) == 16
        assert "crime_incident" in EVENT_KINDS and "vehicle_pursuit" in EVENT_KINDS
        assert set(OSINT_NEW_KINDS) <= set(EVENT_KINDS)
        assert EVENT_KINDS[-6:] == OSINT_NEW_KINDS
        assert set(USE_CASE_KINDS.values()) <= set(EVENT_KINDS)


# ── OSINT provenance fields on the request (021, contract C-T) ──────────────

OSINT_NEW_KINDS = (
    "reported_crime", "public_disorder", "road_accident", "hazard", "flooding", "infra_failure",
)


def _osint_req(**over):
    body = {
        "event_kind": "road_accident",
        "title": "Road accident · Science City (EM Bypass)",
        "route_spines": [{"label": "primary", "segment_ids": [1045]}],
        "metadata": {"source": "osint", "osint_event_id": "4f7a9c1e-0b5d-4c33-9e21-7d8a6b5c4e3f"},
        "officer": "Sandbox Officer",
        "source_kind": "osint",
        "credibility": 0.65,
        "verification_state": "NEWS-REPORTED",
        "provenance": {
            "source_feeds": ["google_news_rss"],
            "publishers": ["news-a.example", "news-b.example"],
            "geocoder": "gazetteer_exact",
            "geocode_confidence": 0.719,
            "osint_event_id": "4f7a9c1e-0b5d-4c33-9e21-7d8a6b5c4e3f",
            "dss_id": None,
        },
        "geotag": {"lon": 72.8623, "lat": 19.0652},
    }
    body.update(over)
    return body


class TestOsintRequestFields:
    def test_defaults_are_null_no_inference(self):
        req = CorridorEventRequest(
            event_kind="race", title="x", route_spines=[{"segment_ids": [1]}]
        )
        assert (
            req.source_kind, req.credibility, req.verification_state, req.provenance, req.geotag
        ) == (None, None, None, None, None)

    def test_a_full_osint_request_validates(self):
        req = CorridorEventRequest(**_osint_req())
        assert req.source_kind == "osint" and req.verification_state == "NEWS-REPORTED"
        assert req.geotag is not None and (req.geotag.lon, req.geotag.lat) == (72.8623, 19.0652)

    @pytest.mark.parametrize("kind", ["operator", "brain", "emulator"])
    def test_other_source_kinds_need_no_label(self, kind):
        CorridorEventRequest(
            **_osint_req(source_kind=kind, credibility=None, verification_state=None)
        )

    @pytest.mark.parametrize(
        "over",
        [
            {"source_kind": "twitter"},
            {"verification_state": "LIVE"},
            {"credibility": 1.2},
            {"credibility": -0.1},
            {"credibility": float("nan")},
            {"credibility": None},  # osint needs its credibility
            {"verification_state": None},  # osint needs its honest label
            {"geotag": {"lon": 72.0, "lat": 23.0}},  # outside the city bbox
            {"geotag": {"lon": 72.5, "lat": 23.5}},
            {"geotag": {"lon": 72.5}},
            {"geotag": {"lon": 72.5, "lat": 23.0, "alt": 3}},
            {"provenance": {"publishers": ["news-a.example"], "author": "x"}},
            {"provenance": {"sources": [{"title": "t", "post_author": "x"}]}},
            {"provenance": {"meta": {"deep": {"faces": []}}}},
            # compound keys the denylist matches as a substring (fail closed)
            {"provenance": {"personid": "x"}},
            {"provenance": {"sources": [{"reportername": "x"}]}},
            {"provenance": {"meta": {"userName": "x"}}},
            # an exempt key carries only its contract type
            {"provenance": {"touches_persons": "x"}},
            {"provenance": {"note": "x" * 5000}},  # over 4 KB
            {"provenance": {"note": "nul\x00"}},
            # CONFIRMED records an officer's confirmation (plan R29): never on create
            {"verification_state": "CONFIRMED"},
        ],
    )
    def test_invalid_osint_fields_are_refused(self, over):
        with pytest.raises(ValueError):
            CorridorEventRequest(**_osint_req(**over))

    @pytest.mark.parametrize("kind", ["operator", "brain", "emulator", "osint"])
    def test_confirmed_is_refused_on_create_for_every_source_kind(self, kind):
        with pytest.raises(ValueError, match="officer's confirmation"):
            CorridorEventRequest(**_osint_req(source_kind=kind, verification_state="CONFIRMED"))
        with pytest.raises(ValueError, match="officer's confirmation"):
            CorridorEventRequest(
                event_kind="race",
                title="x",
                route_spines=[{"segment_ids": [1]}],
                verification_state="CONFIRMED",
            )

    def test_person_key_rule_matches_the_ethics_denylist(self):
        from traffic_oracle.events import is_person_key

        for key in (
            "author", "authorName", "post_author", "faces", "individual_id", "individualId",
            "driver_name", "driverName", "victims", "authorname", "personid", "personname",
            "postauthor", "reportername", "victimname", "suspectname", "ownername", "userName",
            "faceprint", "authority", "interface", "handler", "ownership", "suspected_cause",
        ):
            assert is_person_key(key), key
        for key in (
            "surface_forms", "surfaced", "touches_persons", "publishers", "source_feeds",
            "geocoder", "geocode_confidence", "osint_event_id", "dss_id",
        ):
            assert not is_person_key(key), key

    def test_a_provenance_keyed_by_opaque_ids_is_accepted(self):
        """A map keyed by signal id or uuid never fails at random: about 1 sha1 in 2,000
        spells "face"."""
        import hashlib

        from traffic_oracle.events import is_person_key

        sid = hashlib.sha1(b"google_news_rss:synthetic:559").hexdigest()
        oid = "0b7e3c2a-face-4d1e-9a8b-5c6d7e8f9a0b"
        assert "face" in sid and not is_person_key(sid) and not is_person_key(oid)
        prov = {
            **_osint_req()["provenance"],
            "signals": {sid: {"role": "primary"}},
            "events": {oid: "x"},
        }
        assert CorridorEventRequest(**_osint_req(provenance=prov)).provenance == prov
        # the terms, and ids that are not whole and canonical, are still refused
        for key in ("faceprint", "face_id", sid.upper(), f"event:{oid}"):
            assert is_person_key(key), key
            bad = {"signals": {key: {"role": "primary"}}}
            with pytest.raises(ValueError):
                CorridorEventRequest(**_osint_req(provenance=bad))


class _Tx:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class _CreateConn:
    """Answers create_event's reads and writes (ledger probe, event INSERT, spine/ledger rows)."""

    def __init__(self) -> None:
        import uuid as _uuid
        from datetime import timezone as _tz

        self.event_id = _uuid.UUID("9d0c6a52-41a4-4c0e-8f6b-2f4b1d1e7a10")
        self.created_at = datetime(2026, 10, 20, 15, 30, tzinfo=_tz.utc)
        self.inserts: list[tuple[str, tuple]] = []
        self.executes: list[tuple[str, tuple]] = []

    async def fetchval(self, sql, *args):
        return True  # the 013 ledger exists

    def transaction(self):
        return _Tx()

    async def fetchrow(self, sql, *args):
        if sql.startswith("INSERT INTO events.corridor_events"):
            self.inserts.append((sql, args))
            return {"event_id": self.event_id, "created_at": self.created_at}
        raise AssertionError("unexpected fetchrow: " + sql[:60])

    async def execute(self, sql, *args):
        self.executes.append((sql, args))
        return "INSERT 0 1"


def _post_event(body, *, promotion: bool):
    from httpx import ASGITransport, AsyncClient

    from traffic_oracle.__main__ import create_app
    from traffic_oracle.city.common import reset_relation_cache

    conn = _CreateConn()
    app = create_app()
    app.state.pool = _FakePool(conn)
    if promotion:

        @app.middleware("http")
        async def _osint_promotion(request, call_next):  # what OS-5's promote sets
            request.state.osint_promotion = True
            return await call_next(request)

    async def run():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            return await c.post("/api/v1/events", json=body)

    reset_relation_cache()
    try:
        return asyncio.run(run()), conn
    finally:
        reset_relation_cache()


class TestOsintPromotionGate:
    def test_osint_without_promotion_is_refused(self):
        r, conn = _post_event(_osint_req(), promotion=False)
        assert r.status_code == 422, r.text
        assert r.json() == {"detail": "osint events are created by promotion only"}
        assert conn.inserts == []  # nothing written

    def test_osint_with_promotion_writes_the_five_columns(self):
        body = _osint_req()
        r, conn = _post_event(body, promotion=True)
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "planning" and r.json()["event_kind"] == "road_accident"
        (sql, args), = conn.inserts
        assert "source_kind, credibility, verification_state, provenance, geotag)" in sql
        assert "ST_SetSRID(ST_MakePoint($15::float8, $16::float8), 4326)" in sql
        import json as _json

        assert args[10:13] == ("osint", 0.65, "NEWS-REPORTED")
        assert _json.loads(args[13]) == body["provenance"]
        assert args[14:16] == (72.8623, 19.0652)

    @pytest.mark.parametrize("promotion", [False, True])
    def test_confirmed_is_a_422_even_through_promotion(self, promotion):
        """Plan R29: nothing sets CONFIRMED (an officer's confirmation); a direct POST or a
        promotion asking for it is refused before anything is written."""
        r, conn = _post_event(_osint_req(verification_state="CONFIRMED"), promotion=promotion)
        assert r.status_code == 422, r.text
        assert "officer's confirmation" in r.text
        assert conn.inserts == []

    def test_other_source_kinds_post_directly(self):
        r, conn = _post_event(
            _osint_req(
                source_kind="operator", credibility=None, verification_state=None,
                provenance=None, geotag=None,
            ),
            promotion=False,
        )
        assert r.status_code == 200, r.text
        (_, args), = conn.inserts
        assert args[10:16] == ("operator", None, None, None, None, None)

    def test_a_plain_event_writes_nulls(self):
        r, conn = _post_event(
            {
                "event_kind": "procession",
                "title": "Bijoya Dashami immersion procession",
                "route_spines": [{"segment_ids": [1012]}],
            },
            promotion=False,
        )
        assert r.status_code == 200, r.text
        (_, args), = conn.inserts
        assert args[10:16] == (None, None, None, None, None, None)


# ── /events/active row shape (lifecycle fields, batched spines/phases) ──────


class _ActiveConn:
    def __init__(self) -> None:
        import json as _json
        import uuid as _uuid
        from datetime import timezone as _tz

        self.eid = _uuid.UUID("4508d86d-566b-438f-8414-b3d67fd7e6e4")
        now = datetime(2026, 10, 22, 12, 0, tzinfo=_tz.utc)
        self.row = {
            "event_id": self.eid, "event_kind": "vehicle_pursuit", "protection_class": "none",
            "crowd_class": "LOW", "title": "PURSUIT", "description": "", "status": "active",
            "movement_id": None, "planned_start": None, "planned_end": None,
            "actual_start": now, "actual_end": None,
            "metadata": _json.dumps({"vehicle_id": "v"}), "created_at": now, "updated_at": now,
            "zone_geojson": None,
        }
        self.calls: list[tuple[str, tuple]] = []

    async def fetch(self, sql, *args):
        from traffic_oracle import events as ev

        self.calls.append((sql, args))
        if sql == ev._ACTIVE_EVENTS_SQL:
            return [self.row]
        if sql == ev._SQL_EVENT_ROUTES:
            assert list(args[0]) == [self.eid]
            return [{"event_id": self.eid, "label": "belt", "segment_ids": [1012, 1015]}]
        if sql == ev._SQL_EVENT_PHASES:
            start = self.row["actual_start"]
            return [{"event_id": self.eid, "label": "pursuit",
                     "window_start": start, "window_end": start,
                     "closure_policy": '{"closure_type": "signal_hold"}'}]
        raise AssertionError("unexpected SQL: " + sql[:60])


class TestActiveEventsShape:
    def test_rows_carry_lifecycle_fields_and_batched_children(self):
        from httpx import ASGITransport, AsyncClient

        from traffic_oracle.__main__ import create_app

        conn = _ActiveConn()
        app = create_app()
        app.state.pool = _FakePool(conn)

        async def run():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
                return await c.get("/api/v1/events/active")

        r = asyncio.run(run())
        assert r.status_code == 200, r.text
        ev = r.json()["events"][0]
        assert ev["routes"] == [{"label": "belt", "segment_ids": [1012, 1015]}]
        assert ev["phases"][0]["closure_policy"] == {"closure_type": "signal_hold"}
        assert ev["actual_start"].startswith("2026-10-22T12:00") and ev["actual_end"] is None
        assert ev["updated_at"] is not None and ev["metadata"] == {"vehicle_id": "v"}
        assert len(conn.calls) == 3   # events + ONE spines read + ONE phases read
        # 021 (C-T): the five provenance keys, read tolerantly — a row without
        # the columns reads null, never a KeyError
        for key in ("source_kind", "credibility", "verification_state", "provenance", "geotag"):
            assert key in ev and ev[key] is None, key

    def test_rows_carry_the_five_osint_provenance_keys(self):
        from httpx import ASGITransport, AsyncClient

        from traffic_oracle import events as ev_mod
        from traffic_oracle.__main__ import create_app

        conn = _ActiveConn()
        conn.row.update(
            {
                "event_kind": "road_accident",
                "source_kind": "osint",
                "credibility": 0.6499999761581421,  # REAL → float8 on the wire
                "verification_state": "NEWS-REPORTED",
                "provenance": (
                    '{"source_feeds": ["google_news_rss"], "geocoder": "gazetteer_exact"}'
                ),
                "geotag_lon": 72.8623,
                "geotag_lat": 19.0652,
            }
        )
        assert "ST_X(e.geotag) AS geotag_lon" in ev_mod._ACTIVE_EVENTS_SQL
        five = "e.source_kind, e.credibility, e.verification_state, e.provenance"
        assert five in ev_mod._SQL_EVENTS_HISTORY
        app = create_app()
        app.state.pool = _FakePool(conn)

        async def run():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
                return await c.get("/api/v1/events/active")

        r = asyncio.run(run())
        assert r.status_code == 200, r.text
        ev = r.json()["events"][0]
        assert ev["source_kind"] == "osint" and ev["verification_state"] == "NEWS-REPORTED"
        assert ev["credibility"] == 0.65
        assert ev["provenance"] == {
            "source_feeds": ["google_news_rss"], "geocoder": "gazetteer_exact",
        }
        assert ev["geotag"] == {"lon": 72.8623, "lat": 19.0652}


# ── EMERGENCY_VEHICLE scheduling ────────────────────────────────────────────


class TestEmergencyVehicle:
    def test_resolve_has_no_capacity_effect(self):
        network = default_network()
        seg = network.require(1001)
        sched = ScheduledEvent(
            event_type=EventType.EMERGENCY_VEHICLE,
            segment_id=1001, start_sec=300.0, duration_sec=600.0,
            severity=0.9, label="green-corridor ambulance",
        )
        resolved = sched.resolve(object(), seg)
        assert resolved.source is EventSource.SCHEDULED
        assert resolved.capacity_factor == 1.0
        assert resolved.lanes_blocked == 0
        assert resolved.extra_demand_veh_h == 0.0
        assert resolved.green_ratio_factor == 1.0

    def test_scheduled_emergency_vehicle_charged_delay(self):
        engine = SimulationEngine(network=default_network())
        # the Western Express Highway from Vakola to Vile Parle (1015), 4.3 km
        # — long enough for the ambulance to meet the closure (Marine Drive
        # 1002 is 1.1 km on the real network)
        kwargs = dict(
            route_segment_ids=[1015],
            departure_time=datetime.fromisoformat("2026-10-13T18:00:00+05:30"),
            closure_policy=ClosurePolicy(
                advance_closure_sec=120, closure_type="full_closure"
            ),
            horizon_min=30,
            n_replications=4,
            seed=7,
        )
        without = engine.run(**kwargs)
        with_ev = engine.run(
            **kwargs,
            scheduled_events=[
                ScheduledEvent(
                    event_type=EventType.EMERGENCY_VEHICLE,
                    segment_id=1015, start_sec=60.0, duration_sec=600.0,
                    severity=0.9, label="ambulance mid-closure",
                )
            ],
        )
        assert all(
            w.ambulance_delay_sec >= wo.ambulance_delay_sec
            for w, wo in zip(with_ev, without, strict=True)
        )
        assert any(w.ambulance_delay_sec > 0.0 for w in with_ev)

    def test_ambulance_rate_multiplier_zero_removes_random_draws(self):
        engine = SimulationEngine(network=default_network())
        runs = engine.run(
            route_segment_ids=[1001],
            departure_time=datetime.fromisoformat("2026-10-13T18:00:00+05:30"),
            closure_policy=ClosurePolicy(advance_closure_sec=120),
            horizon_min=30,
            n_replications=4,
            seed=11,
            event_config=EventConfig(
                ambulance_rate_multiplier=0.0, disable_all=True
            ),
        )
        assert all(r.ambulance_delay_sec == 0.0 for r in runs)

    def test_event_config_default_multiplier_is_one(self):
        assert EventConfig().ambulance_rate_multiplier == 1.0


# ── Use-case scenario wiring ────────────────────────────────────────────────


class TestUseCaseScenarios:
    def test_all_use_cases_registered(self):
        for sid in USE_CASE_IDS:
            assert sid in SCENARIO_LIBRARY, sid
        assert len(list_scenarios()) == 14 + len(USE_CASE_IDS)  # 14 legacy + the city's use cases
        from traffic_oracle.simulation.scenarios import USE_CASE_IDS as loaded
        assert loaded == USE_CASE_IDS

    @pytest.mark.parametrize("sid", USE_CASE_IDS)
    def test_use_case_specs_match_library_configs(self, sid):
        s: ScenarioSpec = get_scenario(sid)
        assert s.event_kind == USE_CASE_KINDS[sid]
        # every use-case spec is runnable end-to-end
        cfg = s.event_config()
        # the ambulance knob is the library's own (1.0 unless the scenario
        # models more calls: Kali Puja's breathing-difficulty calls, heat)
        assert cfg.ambulance_rate_multiplier == float(s.event_overrides.get("ambulance", 1.0))
        assert cfg.ambulance_rate_multiplier >= 1.0
        events = s.scheduled_events()
        for e in events:
            assert e.event_type in set(EventType)
        assert s.weather_state() is not None

    def test_base_case_reference_values(self):
        s = get_scenario("vvip_convoy_base")
        assert s.vvip_class == "Z+"
        # Mantralaya -> Marine Drive -> the Coastal Road -> the Sea Link -> the
        # Western Express Highway -> the Sahar Elevated Road to T2: one legal
        # path on the real network (the corridor-store profile's spine)
        assert list(s.route_segment_ids) == [1001, 1002, 1006, 1008, 1011, 1013, 1014, 1015,
                                             1020]
        assert s.closure_policy == {
            "advance_closure_sec": 180, "closure_type": "full_closure"}
        assert s.seed == 20261102 and s.n_replications == 10
        assert s.horizon_min == 45
        assert s.event_kind == "protected_movement"

    def test_base_case_deterministic_across_runs(self):
        engine = SimulationEngine(network=default_network())
        s = get_scenario("vvip_convoy_base")
        a = engine.run(
            route_segment_ids=list(s.route_segment_ids),
            departure_time=s.departure_dt(),
            closure_policy=ClosurePolicy(**s.closure_policy),
            horizon_min=s.horizon_min, n_replications=3, seed=s.seed,
        )
        b = engine.run(
            route_segment_ids=list(s.route_segment_ids),
            departure_time=s.departure_dt(),
            closure_policy=ClosurePolicy(**s.closure_policy),
            horizon_min=s.horizon_min, n_replications=3, seed=s.seed,
        )
        assert [r.to_dict() for r in a] == [r.to_dict() for r in b]

    def test_cloudburst_scenario_carries_weather_and_overrides(self):
        s = get_scenario("cloudburst_high_tide")
        assert s.weather["monsoon"] is True
        assert s.weather["rain_intensity_mm_h"] > 0
        assert s.event_overrides["waterlogging"] > 1
        assert s.event_overrides["breakdown"] > 1
        assert any(
            e["type"] == "waterlogging" for e in s.forced_events
        )
        # every forced hazard sits on a real segment of the network
        network = default_network()
        assert all(network.get(e["segment_id"]) is not None for e in s.forced_events)

    def test_ambulance_cases_carry_scheduled_emergency_vehicles(self):
        for sid in ("weh_crash_ambulance", "ganesh_visarjan_girgaon",
                    "crawford_market_fire", "diwali_air_quality",
                    "weh_treefall_squall"):
            kinds = [e.event_type for e in get_scenario(sid).scheduled_events()]
            assert EventType.EMERGENCY_VEHICLE in kinds, sid

    def test_legacy_scenarios_default_to_protected_movement(self):
        s = get_scenario("monsoon_evening_peak")
        assert s.event_kind == "protected_movement"
        assert s.crowd_class == "LOW"
        assert s.duration_class == "minutes"
