"""Watchlist tape + delivery tests (contracts C2 / C-E / C-A) — no network.

Pins:
* the watchlist scenario builds anpr_read + agency_unit frames; reads sit
  ON the registered camera sites (no drift), carry no asserted hit, and the
  background traffic passes at law-abiding speeds;
* every synthetic plate carries the 'EM' marker (self-labelling);
* read ids are uuid5 over (use_case, seed, camera, plate, run) — stable
  across rebuilds, fresh per live run, identical in a replay;
* the fleeing FIR-named vehicle reads above every limit and is timed into
  the RED of a stop-line approach when the site's program is known;
* every vehicle drives ONE feasible journey — its reads follow a path, in
  time order, never closer in time than the road distance at its speed
  (the numbered hops of a God's-eye trace an operator can retrace);
* delivery goes through the oracle's ingest seam with WALL-CLOCK stamps
  (never in the future), source 'emulated_anpr' and the run id; the hit
  comes back from the oracle; a replay is idempotent;
* agency units publish clearly-labelled C-A docs with a wall stamp, and a
  unit an officer dispatched is left to the dispatch projection.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from event_emulator.library import load_library
from event_emulator.nats_seam import UNITS_EMULATED_SUBJECT
from event_emulator.profiles import profile_for
from event_emulator.runner import RunnerDeps, attach_signal_context, execute_replay, execute_run
from event_emulator.spec import EmulationSpec, ResolvedRun
from event_emulator.tape import _dist_m, anpr_read_uuid, build_tape, movement_states_at
from event_emulator.city import STOLEN_FIR_PLATE
from fakes import FakeNats, FakeOracle, FakeStore, FakeTwin, FakeValkey, NoSleep
from mumbai import (
    KEYS,
    SEGMENTS,
    SLIM,
    bearing,
    between,
    junction_xy,
    legs_at,
    passes,
    segment_named,
)

T0 = datetime(2026, 11, 5, 5, 0, 0, tzinfo=timezone.utc)
UC = "watchlist_anpr_sweep"

PROGRAM = {"cycle_sec": 100, "offset_sec": 0,
           "phases": [{"green_sec": 47, "movements": ["through"]},
                      {"green_sec": 38, "movements": ["cross"]}]}

#: The sweep route on the Mumbai network and its registered sites
#: (corridor.cameras shape after the store's attribution: nearest segment +
#: limit, governing junction): the network's emulated sweep cameras on the
#: route (EM-CAM-nn, mid-block), and two stop-line approach sites at
#: crossings the route passes (modelled here as the store would carry them).
ROUTE = load_library()[UC].config["route_segment_ids"]
_MID = [c for c in SLIM["cameras"]
        if str(c["camera_id"]).startswith("EM-CAM-") and c["segment_id"] in ROUTE]
_PASSES = passes(ROUTE)
#: two distinct crossings inside the route, each approached along the route
#: segment that arrives there
_STOP_IDX = (2, len(_PASSES) - 3) if len(_PASSES) >= 7 else (1, len(_PASSES) - 2)
_STOP_AT = [(_PASSES[i], ROUTE[i - 1]) for i in _STOP_IDX]


def _mid_site(c: dict) -> dict:
    seg = SEGMENTS[c["segment_id"]]
    a, b = junction_xy(seg["from_junction"]), junction_xy(seg["to_junction"])
    return {"camera_id": c["camera_id"], "lon": float(c["lon"]), "lat": float(c["lat"]),
            "junction_id": None, "heading_deg": None, "segment_id": c["segment_id"],
            "speed_limit_kmh": float(seg["speed_limit_kmh"] or 40), "oneway": seg["oneway"],
            "bearing_deg": bearing(a, b), "signal_junction_id": None}


def _stop_site(jid: int, sid: int) -> dict:
    seg = SEGMENTS[sid]
    other = seg["from_junction"] if seg["to_junction"] == jid else seg["to_junction"]
    here, there = junction_xy(jid), junction_xy(other)
    # 30 m back from the stop line, heading INTO the crossing
    lon = here[0] + (there[0] - here[0]) * 0.03
    lat = here[1] + (there[1] - here[1]) * 0.03
    return {"camera_id": f"EM-J{jid:02d}", "lon": round(lon, 7), "lat": round(lat, 7),
            "junction_id": jid, "heading_deg": bearing(there, here), "segment_id": sid,
            "speed_limit_kmh": float(seg["speed_limit_kmh"] or 40), "oneway": seg["oneway"],
            "bearing_deg": bearing(there, here), "signal_junction_id": jid}


SITES = [_mid_site(c) for c in _MID] + [_stop_site(j, s) for j, s in _STOP_AT]
LEGS = {j: legs_at(j) for j, _s in _STOP_AT}
PROGRAMS = {j: PROGRAM for j, _s in _STOP_AT}
#: reads: every mid-block site sees the six background cars, the earmark-
#: exercise plate and the fleeing car; the fleeing car also hits each stop line
N_READS = 8 * len(_MID) + len(_STOP_AT)


def _sites():
    return attach_signal_context([dict(s) for s in SITES], PROGRAMS, LEGS)


def _tape(seed: int | None = None, run_id: int | None = 7, sites=None, clock_scale=1000.0):
    lib = load_library()
    uc = lib[UC]
    spec = EmulationSpec(use_case_id=UC, seed=seed, t0_anchor=T0, tick_sec=30.0,
                         clock_scale=clock_scale)
    run = ResolvedRun.resolve(spec, uc)
    return build_tape(run, uc, profile_for(UC), run_id=run_id,
                      camera_sites=_sites() if sites is None else sites), uc, spec


def _anpr(tape):
    return [f for f in tape.frames if f.kind == "anpr_read"]


def _units(tape):
    return [f for f in tape.frames if f.kind == "agency_unit"]


class TestWatchlistTape:
    def test_frames_present_for_watchlist_scenario(self):
        tape, _, _ = _tape()
        # 4 sweep cameras x 8 vehicles + the fleeing car at 2 stop lines
        assert len(_MID) == 4 and len(_STOP_AT) == 2
        assert len(_anpr(tape)) == N_READS == 34
        assert len(_units(tape)) == 2 * (int(3600 / 20) + 1)

    def test_no_watchlist_frames_for_legacy_scenarios(self):
        lib = load_library()
        uc = lib["vvip_convoy_base"]
        spec = EmulationSpec(use_case_id="vvip_convoy_base", t0_anchor=T0, tick_sec=30.0)
        tape = build_tape(ResolvedRun.resolve(spec, uc), uc, profile_for("vvip_convoy_base"))
        assert _anpr(tape) == [] and _units(tape) == []

    def test_reads_sit_on_registered_sites(self):
        tape, _, _ = _tape()
        sites = {s["camera_id"]: (round(s["lon"], 6), round(s["lat"], 6)) for s in SITES}
        for f in _anpr(tape):
            assert tuple(f.payload["position"]) == sites[f.payload["camera_id"]]

    def test_no_hit_is_asserted(self):
        tape, _, _ = _tape()
        for f in _anpr(tape):
            assert "matched_plate_hit" not in f.payload
        roles = {f.payload["role"] for f in _anpr(tape)}
        assert roles == {"background", "stolen_fir_plate", "earmark_exercise_plate"}

    def test_every_plate_carries_em_marker(self):
        tape, _, _ = _tape()
        for f in _anpr(tape):
            assert "EM" in f.payload["plate"]

    def test_background_traffic_is_law_abiding(self):
        tape, _, _ = _tape()
        limits = {s["camera_id"]: s["speed_limit_kmh"] for s in SITES}
        for f in _anpr(tape):
            if f.payload["role"] != "stolen_fir_plate":
                assert f.payload["speed_kmh"] <= limits[f.payload["camera_id"]] * 0.9 + 0.05

    def test_fleeing_vehicle_speeds_everywhere(self):
        tape, _, _ = _tape()
        stolen = [f for f in _anpr(tape) if f.payload["role"] == "stolen_fir_plate"]
        assert len(stolen) == len(_MID) + len(_STOP_AT)
        assert all(f.payload["speed_kmh"] > 90.0 for f in stolen)

    # up to x20 the window holds more than a signal cycle, so a red always
    # exists; at x60 the whole 45-min scenario is 45 wall seconds and the
    # approach may be green throughout — the read then keeps its time and
    # the oracle decides on its own
    @pytest.mark.parametrize("clock_scale", [1.0, 10.0, 20.0])
    def test_fleeing_vehicle_runs_the_red_at_stop_lines(self, clock_scale):
        tape, _, spec = _tape(clock_scale=clock_scale)
        sites = {s["camera_id"]: s for s in _sites()}
        stop_reads = [f for f in _anpr(tape) if f.payload["camera_id"].startswith("EM-J")]
        assert len(stop_reads) == 2
        for f in stop_reads:
            site = sites[f.payload["camera_id"]]
            assert site["signal"]["movement"] in ("through", "cross")
            assert f.payload["heading"] == round(site["heading_deg"], 1)
            wall = T0.timestamp() + f.t_sec / spec.clock_scale
            states = movement_states_at(100, 0, PROGRAM["phases"], wall)
            assert states[site["signal"]["movement"]] == "red"

    @pytest.mark.parametrize("clock_scale", [1.0, 10.0, 20.0, 1000.0])
    def test_every_vehicle_drives_one_feasible_journey(self, clock_scale):
        tape, uc, _ = _tape(clock_scale=clock_scale)
        reads = _anpr(tape)
        assert len(reads) == N_READS                  # nothing falls off the window
        by_plate: dict[str, list] = {}
        for f in reads:
            by_plate.setdefault(f.payload["plate"], []).append(f)
        horizon = uc.horizon_sec
        for plate, hops in by_plate.items():
            hops.sort(key=lambda f: f.t_sec)
            cams = [f.payload["camera_id"] for f in hops]
            assert len(set(cams)) == len(cams), plate          # each camera once
            for a, b in zip(hops, hops[1:]):
                assert b.t_sec > a.t_sec, plate                # never two places at once
                gap_m = _dist_m(a.payload["position"], b.payload["position"])
                v = b.payload["speed_kmh"] / 3.6
                assert b.t_sec - a.t_sec >= gap_m / v - 1e-6, (plate, a, b)
            assert all(15.0 <= f.t_sec <= horizon - 15.0 for f in hops)
        # traffic drives the belt in path order (one way or the other): the
        # same nearest-next walk over the sweep sites for every car
        belts = {tuple(f.payload["camera_id"] for f in hops) for hops in by_plate.values()
                 if hops[0].payload["role"] != "stolen_fir_plate"}
        assert len({min(b, b[::-1]) for b in belts}) == 1, belts
        assert all(len(b) == len(_MID) for b in belts)
        # the chase spreads over the window, not one burst
        chase = by_plate[STOLEN_FIR_PLATE]
        assert chase[-1].t_sec - chase[0].t_sec >= 0.25 * horizon

    def test_read_ids_are_run_scoped_uuid5(self):
        tape, _, _ = _tape(run_id=7)
        for f in _anpr(tape):
            assert f.payload["read_id"] == anpr_read_uuid(
                UC, tape.seed, f.payload["camera_id"], f.payload["plate"], 7)
        other, _, _ = _tape(run_id=8)
        assert {f.payload["read_id"] for f in _anpr(tape)}.isdisjoint(
            {f.payload["read_id"] for f in _anpr(other)})

    def test_byte_identical_rebuild(self):
        a, _, _ = _tape(seed=777)
        b, _, _ = _tape(seed=777)
        assert a.to_json() == b.to_json()

    def test_fallback_without_registry_is_deterministic(self):
        a, _, _ = _tape(seed=5, sites=[])
        b, _, _ = _tape(seed=5, sites=[])
        assert a.to_json() == b.to_json()
        assert {f.payload["camera_id"] for f in _anpr(a)} == {
            "EM-CAM-01", "EM-CAM-02", "EM-CAM-03", "EM-CAM-04"}

    def test_units_ride_the_route(self):
        tape, _, _ = _tape()
        for f in _units(tape):
            p = f.payload
            assert p["agency"] == "traffic" and p["unit_id"].startswith("MTP-EM-")
            assert p["label"].startswith("Mumbai Traffic Police") and "EMULATED" in p["label"]
            assert p["status"] == "patrol"
            lon, lat = p["position"]
            # inside the Kolkata city pack's bbox
            assert 72.77 < lon < 72.99 and 18.89 < lat < 19.28


class TestApproachMapping:
    def test_through_and_cross_legs(self):
        # Park Street crossing: Jawaharlal Nehru Road north / south is the
        # through pair, Park Street crosses
        jid = KEYS["hindmata"]
        north = between("dadar_tt", "hindmata")
        south = between("hindmata", "parel")
        east = between("hindmata", "kem")
        legs = {jid: [
            {"segment_id": north, "road_class": "trunk", "bearing_deg": 33.5},
            {"segment_id": south, "road_class": "trunk", "bearing_deg": 194.7},
            {"segment_id": east, "road_class": "secondary", "bearing_deg": 136.0},
        ]}
        cams = [
            {"camera_id": "EM-J19", "lon": 72.8396, "lat": 19.00545, "junction_id": jid,
             "heading_deg": 14.7, "segment_id": south, "speed_limit_kmh": 40.0,
             "oneway": False, "bearing_deg": 194.7, "signal_junction_id": jid},
            {"camera_id": "EM-J19B", "lon": 72.8399, "lat": 19.0058, "junction_id": jid,
             "heading_deg": 316.0, "segment_id": east, "speed_limit_kmh": 40.0,
             "oneway": False, "bearing_deg": 136.0, "signal_junction_id": jid},
            {"camera_id": "EM-CAM-01", "lon": 72.8197, "lat": 19.0412, "junction_id": None,
             "heading_deg": None, "segment_id": segment_named("Bandra-Worli Sea Link (northbound)"),
             "speed_limit_kmh": 40.0, "oneway": True, "bearing_deg": 345.0,
             "signal_junction_id": None},
        ]
        sites = {s["camera_id"]: s for s in attach_signal_context(cams, {jid: PROGRAM}, legs)}
        assert sites["EM-J19"]["signal"]["movement"] == "through"
        assert sites["EM-J19B"]["signal"]["movement"] == "cross"
        assert sites["EM-CAM-01"]["signal"] is None


# ── runner delivery ─────────────────────────────────────────────────────────


def _deps(store=None, nats=None, oracle=None):
    store = store or FakeStore(cameras=[dict(s) for s in SITES], programs=PROGRAMS,
                               legs=LEGS)
    nats = nats or FakeNats()
    oracle = oracle or FakeOracle(store=store, earmarked={STOLEN_FIR_PLATE: "stolen_vehicle"})
    return RunnerDeps(store=store, valkey=FakeValkey(), twin=FakeTwin(), nats=nats,
                      oracle=oracle, sleep=NoSleep()), store, nats, oracle


def _spec(**kw):
    params = dict(use_case_id=UC, seed=42, t0_anchor=None, tick_sec=30.0,
                  clock_scale=1000.0, deliver_twin=False)
    params.update(kw)
    return EmulationSpec(**params)


class TestRunnerDelivery:
    def test_reads_go_through_the_oracle_seam(self):
        deps, store, nats, oracle = _deps()
        outcome = asyncio.run(execute_run(deps, _spec(), library=load_library()))
        assert outcome.status == "completed"
        entries = [e for e in outcome.frame_log if e["kind"] == "anpr_read"]
        assert len(entries) == N_READS
        assert all(e["result"] == "delivered" for e in entries)
        assert len(oracle.sightings) == N_READS
        for body, replay in oracle.sighting_bodies:
            assert body["source"] == "emulated_anpr"
            assert body["run_id"] == outcome.run_id
            assert "matched_plate_hit" not in body
            assert replay is None
        # nothing in the tape rides NATS but units + the Arrow plane
        assert {d[0] for d in nats.json_docs} == {UNITS_EMULATED_SUBJECT}

    def test_reads_are_stamped_at_wall_fire_time(self):
        # a virtual wall clock the injected sleep advances: every stamp must
        # be exactly t0 + t_sec / clock_scale — never t0 + t_sec, never ahead
        class Clock:
            def __init__(self) -> None:
                self.now = datetime.now(timezone.utc).timestamp()

            def __call__(self) -> float:
                return self.now

            async def sleep(self, delay: float) -> None:
                self.now += delay

        clock = Clock()
        deps, store, nats, oracle = _deps()
        deps.clock = clock
        deps.sleep = clock.sleep
        outcome = asyncio.run(execute_run(deps, _spec(clock_scale=10.0), library=load_library()))
        tape = outcome.tape
        t0 = datetime.fromisoformat(tape.t0_anchor_iso).timestamp()
        by_read = {f.payload["read_id"]: f for f in _anpr(tape)}
        assert len(oracle.sighting_bodies) == N_READS
        for body, _ in oracle.sighting_bodies:
            f = by_read[body["read_id"]]
            t = datetime.fromisoformat(body["t"]).timestamp()
            assert abs(t - (t0 + f.t_sec / 10.0)) < 1e-3
            assert t < t0 + f.t_sec or f.t_sec == 0     # not the scenario clock
        entry = next(e for e in outcome.frame_log if e["kind"] == "anpr_read")
        assert "t_sec" in entry and "t" in entry      # offset kept in the log

    def test_reads_never_stamped_ahead_of_the_clock(self):
        deps, store, nats, oracle = _deps()          # NoSleep: frames fire early
        asyncio.run(execute_run(deps, _spec(), library=load_library()))
        done = datetime.now(timezone.utc)
        for body, _ in oracle.sighting_bodies:
            assert datetime.fromisoformat(body["t"]) <= done

    def test_hits_come_from_the_oracle(self):
        deps, store, nats, oracle = _deps()
        outcome = asyncio.run(execute_run(deps, _spec(), library=load_library()))
        hits = {(e.get("hit")) for e in outcome.frame_log
                if e["kind"] == "anpr_read" and e.get("hit")}
        assert hits == {"stolen_vehicle"}     # only the actively earmarked plate

    def test_replay_is_idempotent_on_sightings(self):
        deps, store, nats, oracle = _deps()
        first = asyncio.run(execute_run(deps, _spec(), library=load_library()))
        second = asyncio.run(execute_replay(
            deps, tape=first.tape, clock_scale=1000.0, deliver_twin=False,
            replay_of=first.run_id, library=load_library()))
        replays = [e for e in second.frame_log
                   if e["kind"] == "anpr_read" and e["result"] == "delivered"]
        assert replays and all(e["duplicate"] is True for e in replays)
        assert len(oracle.sightings) == N_READS
        assert all(r == second.run_id for _b, r in oracle.sighting_bodies[N_READS:])

    def test_unit_docs_are_labelled_and_stamped(self):
        deps, store, nats, oracle = _deps()
        outcome = asyncio.run(execute_run(deps, _spec(), library=load_library()))
        docs = [d for s, d, _r in nats.json_docs if s == UNITS_EMULATED_SUBJECT]
        assert docs
        for doc in docs:
            assert doc["source"] == "emulated"
            assert doc["run_id"] == outcome.run_id
            assert doc["t"].endswith("+00:00")

    def test_dispatched_unit_is_handed_to_the_projection(self):
        store = FakeStore(cameras=[dict(s) for s in SITES], programs=PROGRAMS,
                          legs=LEGS, dispatched={"MTP-EM-01"})
        deps, store, nats, oracle = _deps(store=store)
        outcome = asyncio.run(execute_run(deps, _spec(), library=load_library()))
        published = {d["unit_id"] for s, d, _r in nats.json_docs if s == UNITS_EMULATED_SUBJECT}
        assert published == {"MTP-EM-02"}
        skipped = [e for e in outcome.frame_log
                   if e["kind"] == "agency_unit" and e["result"] == "skipped"]
        assert skipped and "dispatch" in skipped[0]["reason"]

    def test_corridor_event_kind_is_crime_incident(self):
        deps, store, nats, oracle = _deps()
        outcome = asyncio.run(execute_run(deps, _spec(), library=load_library()))
        assert store.events[outcome.movement_id]["event_kind"] == "crime_incident"
