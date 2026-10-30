"""Runner + replay tests with fake seams — no network, no database.

These pin the cause-tape delivery contract: which seams receive which
frames; that the corridor event goes 'active' at t0 and 'completed' at the
horizon THROUGH the oracle's lifecycle seam (C-F) with the system officer;
that an activation the oracle could not take at t0 is retried every few
wall seconds until it lands, and a run whose event never went live is
'failed', never 'completed'; that windows and stamps are wall time; that
live injections carry NO emulator header while replays re-post the stored
tape VERBATIM with the X-Emulation-Replay header — the single tell; that a
stop closes the event and the row; and that a run delivering nothing is
never 'completed'.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from event_emulator.library import load_library
from event_emulator.runner import (
    ACTIVATE_RETRY_SEC,
    RunControl,
    RunnerDeps,
    cap_frame_log,
    execute_replay,
    execute_run,
)
from event_emulator.spec import EmulationSpec
from event_emulator.tape import CauseTape, chain_polyline, movement_uuid
from fakes import FakeNats, FakeOracle, FakeStore, FakeTwin, FakeValkey, NoSleep


def _deps(**kw) -> RunnerDeps:
    store = kw.get("store", FakeStore())
    return RunnerDeps(
        store=store,
        valkey=kw.get("valkey", FakeValkey()),
        twin=kw.get("twin", FakeTwin()),
        nats=kw.get("nats", FakeNats()),
        oracle=kw.get("oracle", FakeOracle(store=store)),
        sleep=kw.get("sleep", NoSleep()),
    )


#: The Wankhede egress route on the Mumbai network.
EDEN = load_library()["wankhede_egress"].config["route_segment_ids"]


def _spec(uid: str, **kw) -> EmulationSpec:
    params = dict(use_case_id=uid, clock_scale=1000.0, tick_sec=30.0)
    params.update(kw)
    return EmulationSpec(**params)


class TestExecuteRun:
    async def test_full_delivery(self):
        deps = _deps()
        outcome = await execute_run(deps, _spec("wankhede_egress"),
                                    library=load_library())
        assert outcome.status == "completed"
        assert outcome.delivery["failed"] == 0
        store: FakeStore = deps.store
        mv = store.movements[outcome.movement_id]
        assert mv["vvip_class"] == "X"
        assert mv["status"] == "completed"
        segs, pts = store.routes[outcome.movement_id]
        assert segs == EDEN
        # ONE line: every segment's road line chained in route order (the
        # fake lines do not touch: 2 points each), from the movement's
        # origin to its destination
        assert len(pts) == 2 * len(segs)
        assert (mv["origin"], mv["destination"]) == (pts[0], pts[-1])
        vk: FakeValkey = deps.valkey
        assert len(vk.docs) == 1  # keyed per movement; last doc wins in fake
        assert vk.sources[outcome.movement_id][0] == outcome.run_id

    async def test_movement_starts_and_ends_where_its_route_does(self):
        # the Eden Gardens route on a chained network whose segments are
        # stored in both directions: the middle one runs against the drive
        a, b, c = EDEN
        j = [(88.3402, 22.5679), (88.3418, 22.5622), (88.3478, 22.5612), (88.3514, 22.5531)]
        bend = (88.3409, 22.5650)
        store = FakeStore(
            paths={a: [j[0], bend, j[1]], b: [j[2], j[1]], c: [j[2], j[3]]},
            vias={(a, b): [j[1]], (b, c): [j[2]]})
        deps = _deps(store=store)
        outcome = await execute_run(deps, _spec("wankhede_egress"),
                                    library=load_library())
        mv = store.movements[outcome.movement_id]
        segs, line = store.routes[outcome.movement_id]
        assert segs == EDEN
        # origin: where the first segment is entered; destination: where the
        # last is left — the route's ends, not a segment's middle
        assert (mv["origin"], mv["destination"]) == (j[0], j[3])
        # one LineString, oriented, each shared junction once
        assert line == [j[0], bend, j[1], j[2], j[3]]

    async def test_movement_keeps_the_on_road_anchors_without_route_lines(self):
        class NoLines(FakeStore):
            async def route_geometry(self, segment_ids):
                return {"lines": {}, "oneway": {}, "vias": []}

        store = NoLines()
        deps = _deps(store=store)
        outcome = await execute_run(deps, _spec("gateway_ferry_transit"),
                                    library=load_library())
        segs, line = store.routes[outcome.movement_id]
        assert line == [store.anchors[s] for s in segs]
        mv = store.movements[outcome.movement_id]
        assert (mv["origin"], mv["destination"]) == (line[0], line[-1])

    async def test_event_lifecycle_goes_through_c_f(self):
        deps = _deps()
        outcome = await execute_run(deps, _spec("wankhede_egress"),
                                    library=load_library())
        oracle: FakeOracle = deps.oracle
        moves = [(t[1], t[2]) for t in oracle.transitions if t[0] == outcome.movement_id]
        assert moves == [("planning", "active"), ("active", "completed")]
        assert all(t[3] == "event-emulator (system)" for t in oracle.transitions)
        store: FakeStore = deps.store
        ev = store.events[outcome.movement_id]
        assert ev["status"] == "completed"
        # creation row of the status ledger written with the event
        assert store.status_log[0][1:4] == (None, "planning", "event-emulator (system)")

    async def test_corridor_event_row_written(self):
        deps = _deps()
        outcome = await execute_run(deps, _spec("wankhede_egress"),
                                    library=load_library())
        store: FakeStore = deps.store
        ev = store.events[outcome.movement_id]
        assert ev["event_kind"] == "egress_surge"
        assert ev["protection_class"] == "none"   # public event (007 rule)
        assert ev["crowd_class"] == "EXTREME"
        assert ev["movement_id"] == outcome.movement_id  # soft link
        meta = ev["metadata"]
        assert meta["source"] == "event-emulator"
        assert meta["mode"] == "use_case"
        assert meta["run_id"] == outcome.run_id
        assert store.event_routes[outcome.movement_id] == EDEN
        # the honest label and the Mumbai places the scenario is about
        assert meta["label"] == "SIMULATED"
        assert "wankhede" in meta["places"]
        assert meta["title_mr"].startswith("वानखेडे स्टेडियम")
        assert ev["title"] == "Wankhede Stadium — Match-Night Egress"
        assert ev["description"].startswith("SIMULATED scenario 'wankhede_egress'")
        label, _ws, _we, policy = store.event_phases[outcome.movement_id]
        assert label == "egress_surge"
        assert policy == {"advance_closure_sec": 60, "closure_type": "signal_hold"}

    async def test_event_window_is_wall_time(self):
        deps = _deps()
        t0 = datetime(2026, 10, 22, 6, 0, tzinfo=timezone.utc)
        outcome = await execute_run(deps, _spec("ganesh_visarjan_girgaon",
                                                clock_scale=10.0, t0_anchor=t0),
                                    library=load_library())
        ev = deps.store.events[outcome.movement_id]
        assert ev["planned_start"] == t0
        # a 60-minute scenario at x10 holds the road for 6 wall minutes
        assert ev["planned_end"] == t0 + timedelta(minutes=6)
        _label, ws, we, _p = deps.store.event_phases[outcome.movement_id]
        assert (ws, we) == (t0, t0 + timedelta(minutes=6))

    async def test_live_runs_get_run_scoped_identity(self):
        lib = load_library()
        deps = _deps()
        a = await execute_run(deps, _spec("mumbai_marathon"), library=lib)
        b = await execute_run(deps, _spec("mumbai_marathon"), library=lib)
        assert a.run_id != b.run_id
        assert a.movement_id != b.movement_id
        seed = lib["mumbai_marathon"].config["seed"]
        assert a.movement_id == movement_uuid("mumbai_marathon", seed, a.run_id)

    async def test_protected_movement_keeps_vvip_class(self):
        deps = _deps()
        outcome = await execute_run(deps, _spec("vvip_convoy_base"),
                                    library=load_library())
        ev = deps.store.events[outcome.movement_id]
        assert ev["protection_class"] == "Z+"
        assert ev["event_kind"] == "protected_movement"

    async def test_twin_body_carries_causes_verbatim(self):
        twin = FakeTwin()
        deps = _deps(twin=twin)
        lib = load_library()
        cfg = lib["cloudburst_high_tide"].config
        outcome = await execute_run(deps, _spec("cloudburst_high_tide"), library=lib)
        assert len(twin.posts) == 1
        body = twin.posts[0]["body"]
        assert body["route_segment_ids"] == cfg["route_segment_ids"]
        assert body["departure_time"] == cfg["departure_time"]
        assert body["closure_policy"] == cfg["closure_policy"]
        assert body["horizon_min"] == cfg["horizon_min"]
        assert body["n_replications"] == cfg["n_replications"]
        assert body["weather"] == cfg["weather"]
        assert body["event_overrides"]["waterlogging"] == 3
        assert body["event_overrides"]["breakdown"] == 1.8
        assert "ambulance_rate_multiplier" in body["event_overrides"]
        kinds = {e["type"] for e in body["forced_events"]}
        assert "waterlogging" in kinds
        assert "emergency_vehicle" in kinds
        assert "emergency_request" not in kinds
        assert body["scenario_id"] == "cloudburst_high_tide"
        assert outcome.twin["delivery_level"] == "twin_scenario_library"
        assert outcome.twin["summary"]["replications"] == 1

    async def test_twin_library_miss_resends_without_scenario(self):
        twin = FakeTwin(library={"cloudburst_high_tide"})
        deps = _deps(twin=twin)
        outcome = await execute_run(deps, _spec("watchlist_anpr_sweep"),
                                    library=load_library())
        assert [("scenario_id" in p["body"]) for p in twin.posts] == [True, False]
        assert outcome.twin["delivery_level"] == "twin_route_only"
        assert outcome.twin["library_miss"] is True
        assert outcome.twin["scenario_id_sent"] is None
        # remembered: the next run of the use case skips the 404 round trip
        await execute_run(deps, _spec("watchlist_anpr_sweep"), library=load_library())
        assert "scenario_id" not in twin.posts[-1]["body"]
        assert len(twin.posts) == 3

    async def test_twin_summary_lands_in_the_ledger(self):
        deps = _deps()
        outcome = await execute_run(deps, _spec("gateway_ferry_transit"),
                                    library=load_library())
        spec = deps.store.runs[outcome.run_id]["spec"]
        assert spec["twin"]["delivery_level"] == "twin_scenario_library"
        assert spec["twin"]["http_status"] == 200
        assert spec["final_status"] == "completed"
        assert spec["frame_log"] and len(spec["frame_log"]) <= 300

    async def test_live_injection_carries_no_replay_header(self):
        twin = FakeTwin()
        nats = FakeNats()
        deps = _deps(twin=twin, nats=nats)
        await execute_run(deps, _spec("mumbai_marathon"), library=load_library())
        assert twin.posts[0]["replay_run_id"] is None
        assert all(b["replay_run_id"] is None for b in nats.batches)

    async def test_nats_batches_only_on_emulated_subject(self):
        nats = FakeNats()
        deps = _deps(nats=nats)
        await execute_run(deps, _spec("gateway_ferry_transit"), library=load_library())
        assert nats.batches
        assert all(b["subject"] == "corridor.traffic.emulated" for b in nats.batches)
        route = load_library()["gateway_ferry_transit"].config["route_segment_ids"]
        assert all(len(b["rows"]) == len(route) for b in nats.batches)  # route size

    async def test_probe_rows_sit_on_their_segments_anchor(self):
        # each per-segment row is placed at the store's on-road anchor of
        # the segment it claims (the midpoint along the line), never
        # anywhere else
        nats = FakeNats()
        deps = _deps(nats=nats)
        await execute_run(deps, _spec("gateway_ferry_transit"), library=load_library())
        anchors = deps.store.anchors
        for batch in nats.batches:
            for sid, lon, lat, _speed, _cong in batch["rows"]:
                assert (lon, lat) == anchors[sid]

    async def test_twin_failure_is_recorded_not_fatal(self):
        twin = FakeTwin(status_codes=[503])
        deps = _deps(twin=twin)
        outcome = await execute_run(deps, _spec("vvip_convoy_base"),
                                    library=load_library())
        assert outcome.status == "completed"  # DB/valkey seams still drove
        twin_entry = [e for e in outcome.frame_log if e["kind"] == "twin_post"]
        assert twin_entry[0]["result"] == "failed"
        assert twin_entry[0]["http_status"] == 503
        assert twin_entry[0]["delivery_level"] == "twin_rejected"

    async def test_missing_seams_skip_honestly_and_fail(self):
        deps = RunnerDeps(store=None, valkey=None, twin=None, nats=None,
                          oracle=None, sleep=NoSleep())
        outcome = await execute_run(deps, _spec("cyclone_landfall_recovery"),
                                    library=load_library())
        assert outcome.run_id is None
        assert outcome.delivery["skipped"] > 0
        assert outcome.delivery["delivered"] == 0
        # nothing reached anything: never reported 'completed'
        assert outcome.status == "failed"

    async def test_oracle_down_leaves_event_open_and_says_so(self):
        store = FakeStore()
        oracle = FakeOracle(store=store, down=True)
        deps = _deps(store=store, oracle=oracle)
        outcome = await execute_run(deps, _spec("cyclone_landfall_recovery"), library=load_library())
        lifecycle = [e for e in outcome.frame_log if e["kind"] == "event_lifecycle"]
        assert lifecycle and all(e["result"] == "failed" for e in lifecycle)
        assert store.events[outcome.movement_id]["status"] == "planning"
        # frames around an event that never went live are not a completed run
        assert outcome.status == "failed"
        assert outcome.reason.startswith("the corridor event never became active (C-F)")

    async def test_unknown_use_case_raises(self):
        deps = _deps()
        with pytest.raises(KeyError):
            await execute_run(deps, _spec("nope"), library=load_library())


class _OutageClock:
    """A virtual wall clock the injected sleep advances (frames fire at
    t0 + t_sec / clock_scale on it), with the oracle's outage window: down
    from the start, back ``down_for`` virtual seconds later (None: never).
    Every lifecycle call is timed on it."""

    def __init__(self, oracle: FakeOracle, down_for: float | None) -> None:
        self.now = datetime.now(timezone.utc).timestamp()
        self.t0 = self.now
        self.oracle = oracle
        self.down_for = down_for
        self.calls: list[tuple[float, str]] = []
        oracle.down = True
        real = oracle.event_status

        async def timed(event_id, to_status, note=None, replay_run_id=None):
            self.calls.append((self.now - self.t0, to_status))
            return await real(event_id, to_status, note, replay_run_id)

        oracle.event_status = timed   # type: ignore[method-assign]

    def __call__(self) -> float:
        return self.now

    async def sleep(self, delay: float) -> None:
        self.now += delay
        if self.down_for is not None and self.now - self.t0 >= self.down_for:
            self.oracle.down = False


def _outage_deps(down_for: float | None) -> tuple[RunnerDeps, _OutageClock]:
    store = FakeStore()
    oracle = FakeOracle(store=store)
    clock = _OutageClock(oracle, down_for)
    deps = _deps(store=store, oracle=oracle, sleep=clock.sleep)
    deps.clock = clock
    return deps, clock


class TestLateActivation:
    """The oracle cannot take the t0 'active' (an outage): the create frame
    counts failed, the activation is retried every ACTIVATE_RETRY_SEC of
    wall time, and the run is completed only if the event went live."""

    async def test_activation_lands_once_the_oracle_is_back(self):
        deps, clock = _outage_deps(down_for=14.0)
        control = RunControl()
        outcome = await execute_run(deps, _spec("cyclone_landfall_recovery", clock_scale=10.0),
                                    library=load_library(), control=control)
        assert outcome.status == "completed", outcome.reason
        mid = outcome.movement_id
        moves = [(t[1], t[2]) for t in deps.oracle.transitions if t[0] == mid]
        assert moves == [("planning", "active"), ("active", "completed")]
        # attempts: t0, then one per 5-10 wall seconds until it landed
        attempts = [t for t, to in clock.calls if to == "active"]
        assert attempts[0] < 1.0 and len(attempts) >= 3
        gaps = [b - a for a, b in zip(attempts, attempts[1:])]
        assert all(ACTIVATE_RETRY_SEC <= g <= 2 * ACTIVATE_RETRY_SEC for g in gaps), gaps
        assert attempts[-1] >= 14.0
        # the create frame was re-counted delivered when the event went live
        create = next(e for e in outcome.frame_log if e["kind"] == "event_row")
        assert create["result"] == "delivered" and create["activated_late"] is True
        assert create["activation_attempts"] == len(attempts) and "reason" not in create
        late = [e for e in outcome.frame_log
                if e["kind"] == "event_lifecycle" and e.get("late")]
        assert len(late) == 1 and late[0]["result"] == "delivered"
        assert control.progress.failed == 0
        assert control.progress.delivered == control.progress.frame == control.progress.total
        assert deps.store.movements[mid]["status"] == "completed"
        spec = deps.store.runs[outcome.run_id]["spec"]
        assert spec["final_status"] == "completed" and spec["event_status"] == "completed"
        assert spec["event_activation"] == {"active": True, "attempts": len(attempts),
                                            "late": True, "error": None}

    async def test_no_lifecycle_seam_is_not_retried(self):
        deps, clock = _outage_deps(down_for=None)
        deps.oracle = None
        outcome = await execute_run(deps, _spec("cyclone_landfall_recovery", clock_scale=10.0),
                                    library=load_library())
        assert outcome.status == "failed"
        assert "oracle seam not configured" in outcome.reason
        create = next(e for e in outcome.frame_log if e["kind"] == "event_row")
        assert create["result"] == "failed" and create["activation_attempts"] == 1

    async def test_progress_counts_the_pending_event_as_failed(self):
        deps, clock = _outage_deps(down_for=None)
        control = RunControl()
        seen: list[tuple[str | None, int]] = []

        async def sleep(delay: float) -> None:
            await clock.sleep(delay)
            seen.append((control.event_status, control.progress.failed))

        deps.sleep = sleep
        await execute_run(deps, _spec("cyclone_landfall_recovery", clock_scale=10.0),
                          library=load_library(), control=control)
        # mid-run the poll says: event still 'planning', its create frame failed
        assert seen and all(s == ("planning", 1) for s in seen[1:-1])

    async def test_an_event_that_never_went_live_fails_the_run(self):
        deps, clock = _outage_deps(down_for=None)
        control = RunControl()
        outcome = await execute_run(deps, _spec("cyclone_landfall_recovery", clock_scale=10.0),
                                    library=load_library(), control=control)
        assert outcome.status == "failed"
        assert outcome.reason.startswith("the corridor event never became active (C-F)")
        assert "ConnectError" in outcome.reason
        attempts = [t for t, to in clock.calls if to == "active"]
        assert len(attempts) > 30                       # retried for the whole run
        create = next(e for e in outcome.frame_log if e["kind"] == "event_row")
        assert create["result"] == "failed" and "not active" in create["reason"]
        assert create["activation_attempts"] == len(attempts)
        # the failed frames: the create (never live) and the horizon close
        # (the oracle is still down) — every other frame was delivered
        failed = [e for e in outcome.frame_log
                  if e["kind"] == "event_row" and e["result"] == "failed"]
        assert len(failed) == 2 and control.progress.failed == 2
        assert control.progress.delivered == control.progress.frame - 2
        assert control.event_status == "planning"
        row = deps.store.runs[outcome.run_id]
        assert row["status"] == "failed" and row["spec"]["reason"] == outcome.reason
        # every inputs doc still reached Valkey: the frames were not the fault
        assert deps.valkey.docs

    async def test_an_event_closed_by_an_officer_is_not_retried(self):
        deps, clock = _outage_deps(down_for=8.0)
        oracle: FakeOracle = deps.oracle
        cancelled: list[str] = []
        real_sleep = clock.sleep

        async def sleep(delay: float) -> None:
            await real_sleep(delay)
            # back up — and a duty officer cancels the still-planning event
            for eid, ev in deps.store.events.items():
                if not oracle.down and ev["status"] == "planning" and not cancelled:
                    cancelled.append(eid)
                    await oracle.event_status(eid, "cancelled", "duty officer")

        deps.sleep = sleep
        outcome = await execute_run(deps, _spec("cyclone_landfall_recovery", clock_scale=10.0),
                                    library=load_library())
        assert cancelled == [outcome.movement_id]
        assert outcome.status == "failed"
        assert "cancelled before it became active" in outcome.reason
        actives = [t for t, to in clock.calls if to == "active"]
        assert all(t <= 8.0 + 2 * ACTIVATE_RETRY_SEC for t in actives)   # then it stopped
        # nothing left for the run to close: no completion attempt either
        assert deps.store.events[outcome.movement_id]["status"] == "cancelled"
        complete = [e for e in outcome.frame_log
                    if e["kind"] == "event_row" and e.get("t_sec", 0) > 0]
        assert complete and complete[-1]["result"] == "skipped"


class TestStop:
    async def test_stop_mid_run_closes_event_and_row(self):
        control = RunControl()
        sleep = NoSleep(on_call=lambda n: control.request_stop("stopped") if n == 40 else None)
        deps = _deps(sleep=sleep)
        outcome = await execute_run(deps, _spec("ganesh_visarjan_girgaon"),
                                    library=load_library(), control=control)
        assert outcome.status == "stopped"
        store: FakeStore = deps.store
        assert store.events[outcome.movement_id]["status"] == "completed"
        assert store.movements[outcome.movement_id]["status"] == "completed"
        assert store.runs[outcome.run_id]["status"] == "stopped"
        progress = store.runs[outcome.run_id]["spec"]["progress"]
        assert 0 < progress["frame"] < progress["total"]
        last = deps.oracle.transitions[-1]
        assert last[2] == "completed" and "stopped by operator" in last[4]

    async def test_interrupted_falls_back_to_stopped_column(self):
        control = RunControl()
        control.request_stop("interrupted")
        deps = _deps()
        outcome = await execute_run(deps, _spec("cyclone_landfall_recovery"),
                                    library=load_library(), control=control)
        assert outcome.status == "interrupted"
        row = deps.store.runs[outcome.run_id]
        assert row["status"] == "stopped"           # 009 CHECK predates 'interrupted'
        assert row["spec"]["final_status"] == "interrupted"



# ── scripted unit tracks ride the store's DRAWN paths (contract C-K) ────────

#: The flagship's track segments as the store draws them once traced: the
#: library line's ends with a bend (~650 m off) the embedded route_geometry
#: lacks.
_TRACKS = load_library()["ganesh_visarjan_girgaon"].config["unit_tracks"]


def _drawn() -> dict[int, list[tuple[float, float]]]:
    out = {}
    for sid, pts in _TRACKS["route_geometry"].items():
        (x0, y0), (x1, y1) = pts[0], pts[-1]
        bend = ((x0 + x1) / 2.0 + 0.004, (y0 + y1) / 2.0 + 0.004)
        out[int(sid)] = [(x0, y0), bend, (x1, y1)]
    return out


DRAWN = _drawn()
_UNITS = {u["unit_id"]: [int(s) for s in u["segment_ids"]] for u in _TRACKS["units"]}


def _off_line_m(point, line) -> float:
    """Metres from a point to a polyline (local equirectangular frame)."""
    import math

    lon0, lat0 = point
    kx = 111_320.0 * math.cos(math.radians(lat0))
    xy = [((lon - lon0) * kx, (lat - lat0) * 110_574.0) for lon, lat in line]
    best = math.inf
    for (x1, y1), (x2, y2) in zip(xy, xy[1:]):
        dx, dy = x2 - x1, y2 - y1
        t = max(0.0, min(1.0, -(x1 * dx + y1 * dy) / ((dx * dx + dy * dy) or 1.0)))
        best = min(best, math.hypot(x1 + t * dx, y1 + t * dy))
    return best


class _TrackStore(FakeStore):
    """FakeStore that records segment_paths reads (or fails them)."""

    def __init__(self, *, fail: bool = False, **kw) -> None:
        super().__init__(**kw)
        self.fail = fail
        self.path_calls: list[list[int]] = []

    async def segment_paths(self, segment_ids):
        self.path_calls.append(list(segment_ids))
        if self.fail:
            raise RuntimeError("store down")
        return await super().segment_paths(segment_ids)


def _track(tape: CauseTape, unit_id: str) -> list[tuple[float, float]]:
    return [tuple(f.payload["position"]) for f in tape.frames
            if f.kind == "agency_unit" and f.payload["unit_id"] == unit_id]


class TestUnitTrackGeometry:
    async def test_recorded_units_follow_the_stores_drawn_paths(self):
        store = _TrackStore(paths={s: list(line) for s, line in DRAWN.items()})
        deps = _deps(store=store)
        outcome = await execute_run(deps, _spec("ganesh_visarjan_girgaon"),
                                    library=load_library())
        # the flagship has no watchlist knobs: ONE read, for its track
        # segments in first-seen order
        seen: list[int] = []
        for segs in _UNITS.values():
            seen += [s for s in segs if s not in seen]
        assert store.path_calls == [seen]
        library_lines = {int(s): [tuple(p) for p in pts]
                         for s, pts in _TRACKS["route_geometry"].items()}
        for unit, segs in _UNITS.items():
            line = chain_polyline(segs, DRAWN)
            points = _track(outcome.tape, unit)
            assert points, unit
            assert max(_off_line_m(p, line) for p in points) < 1.0, unit
        # …and off the library's straighter line where the drawn road bends
        run = chain_polyline(_UNITS["AMB-EM-108"], library_lines)
        assert max(_off_line_m(p, run) for p in _track(outcome.tape, "AMB-EM-108")) > 300.0

    async def test_a_store_that_cannot_answer_keeps_the_library_geometry(self):
        store = _TrackStore(fail=True)
        deps = _deps(store=store)
        outcome = await execute_run(deps, _spec("ganesh_visarjan_girgaon"),
                                    library=load_library())
        assert outcome.status == "completed"
        lines = {int(s): [tuple(p) for p in pts] for s, pts in _TRACKS["route_geometry"].items()}
        beat = chain_polyline(_UNITS["MTP-EM-21"], lines)
        points = _track(outcome.tape, "MTP-EM-21")
        assert points and max(_off_line_m(p, beat) for p in points) < 1.0

    async def test_units_are_mumbai_traffic_police_and_an_ambulance(self):
        deps = _deps()
        outcome = await execute_run(deps, _spec("ganesh_visarjan_girgaon"), library=load_library())
        units = {f.payload["unit_id"]: f.payload for f in outcome.tape.frames
                 if f.kind == "agency_unit"}
        assert set(units) == set(_UNITS)
        assert units["MTP-EM-21"]["agency"] == "traffic"
        assert units["AMB-EM-108"]["agency"] == "ambulance"
        assert all("EM" in uid and "EMULATED" in u["label"] for uid, u in units.items())
        # the run ends at JJ Hospital: stationary, 'arrived'
        last = [f.payload for f in outcome.tape.frames
                if f.kind == "agency_unit" and f.payload["unit_id"] == "AMB-EM-108"][-1]
        assert last["status"] == "arrived" and last["speed_kmh"] == 0.0


class TestFrameLog:
    def test_cap_keeps_failures_first(self):
        log = [{"frame": i, "kind": "inputs_doc", "result": "delivered"} for i in range(1000)]
        log[10]["result"] = "failed"
        kept, dropped = cap_frame_log(log, cap=100)
        assert len(kept) == 100 and dropped == 900
        assert log[10] in kept
        assert kept[-1] is log[-1]


class TestReplay:
    async def test_replay_reposts_tape_verbatim_with_header(self):
        lib = load_library()
        deps = _deps()
        first = await execute_run(deps, _spec("sea_link_breakdown_surge"), library=lib)

        twin = FakeTwin()
        nats = FakeNats()
        deps2 = _deps(twin=twin, nats=nats)
        second = await execute_replay(
            deps2, tape=first.tape, clock_scale=1000.0, replay_of=first.run_id,
            library=lib,
        )
        assert [f.to_dict() for f in second.tape.frames] == \
            [f.to_dict() for f in first.tape.frames]
        assert second.tape.seed == first.tape.seed
        assert second.tape.movement_id == first.tape.movement_id
        assert second.tape.t0_anchor_iso >= first.tape.t0_anchor_iso
        assert twin.posts[0]["replay_run_id"] == second.run_id
        assert all(b["replay_run_id"] == second.run_id for b in nats.batches)
        store2: FakeStore = deps2.store
        assert store2.runs[second.run_id]["is_replay"] is True
        assert store2.runs[second.run_id]["replay_of"] == first.run_id

    async def test_replay_reanimates_same_event_through_c_f(self):
        lib = load_library()
        deps = _deps()
        first = await execute_run(deps, _spec("shivaji_park_parade"), library=lib)
        assert deps.store.events[first.movement_id]["status"] == "completed"
        second = await execute_replay(
            deps, tape=first.tape, clock_scale=1000.0, replay_of=first.run_id,
            library=lib,
        )
        assert second.movement_id == first.movement_id
        store: FakeStore = deps.store
        assert store.events[first.movement_id]["status"] == "completed"
        # the re-animation is its own ledger row (completed → planning)
        assert any(r[1] == "completed" and r[2] == "planning" for r in store.status_log)
        meta = store.events[first.movement_id]["metadata"]
        assert meta["is_replay"] is True and meta["run_id"] == second.run_id

    async def test_replay_from_ledger_json(self):
        lib = load_library()
        deps = _deps()
        first = await execute_run(deps, _spec("cyclone_landfall_recovery"), library=lib)
        raw = json.loads(first.tape.to_json())
        tape = CauseTape.from_dict(raw)
        assert tape.to_json() == first.tape.to_json()
        stored = deps.store.runs[first.run_id]["tape"]
        assert CauseTape.from_dict(stored).to_json() == first.tape.to_json()
