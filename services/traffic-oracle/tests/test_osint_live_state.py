"""The live corridor state the OSINT pipeline reads — ``traffic_oracle.osint.live_state.snapshot`` (C-T, X18;
OSINT SPEC §1.6 (c): correlation with the live corridor / movement / enforcement and 108 state).

Over the in-memory fake store (``fixtures/osint/fakedb.py``) and a fake Valkey (C-B frames, never a server):

* an ACTIVE protected movement is a live ref with the route it RUNS — its current rank-1 spine — never its
  alternates; active events come first, so a tail of stale plans never pushes a running event out of the bound;
* convoys in motion: an active legacy movement and a C-B position frame become ``convoy:<movement_id>`` refs
  (``protected_movement``, the live position, the route); a planning one carries its status, a finished one is
  dropped, an unreadable Valkey never fails the snapshot;
* 108 routes: an approved / en-route ambulance dispatch's route is the path its unit drives (the units module's
  C-N rule over the road graph), or the route stored with it; requested, on-scene and waypoint-less dispatches
  have none;
* closures: an ACTIVE event's phase in force now with a closure policy, in the simulator's AND the brain's
  vocabulary; an approved event's phase or a signal hold closes nothing;
* through the REAL pipeline (``osint_analysis``): an OSINT situation on those segments raises the
  ``protected_corridor``, ``convoy``, ``ambulance_route`` and ``closure`` flags — and none for a planning or
  approved event or movement; the attach check never corroborates a protected movement or a convoy;
* the snapshot is read-only.

The same flags fire on the int3c sandbox in ``test_osint_ingest.py`` (rolled-back seed, real pipeline).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from fixtures.osint.fakedb import FakeOsintConn, FakeOsintDB, FakeValkey
from fixtures.osint.harness import reset_osint_state
from traffic_oracle.osint import live_state

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")

NOW = datetime.now(UTC)


@pytest.fixture(autouse=True)
def _clean_state():
    reset_osint_state()
    yield
    reset_osint_state()


def _db() -> tuple[FakeOsintDB, FakeOsintConn]:
    db = FakeOsintDB()
    return db, FakeOsintConn(db)


def _event(
    db: FakeOsintDB,
    kind: str,
    status: str,
    spines: list[list[int]],
    *,
    minutes_ago: int = 30,
    movement_id: str | None = None,
) -> str:
    eid = str(uuid.uuid4())
    db.corridor[eid] = {
        "event_id": uuid.UUID(eid), "event_kind": kind, "status": status, "title": f"test {kind}",
        "metadata": "{}", "source_kind": None, "created_at": NOW - timedelta(minutes=minutes_ago),
        "updated_at": NOW, "geotag_lon": None, "geotag_lat": None,
        "movement_id": uuid.UUID(movement_id) if movement_id else None,
    }
    for rank, segments in enumerate(spines, start=1):
        db.routes.append({"event_id": eid, "route_rank": rank,
                          "label": "primary" if rank == 1 else f"alt-{rank - 1}",
                          "segment_ids": list(segments), "superseded_at": None})
    return eid


def _phase(db: FakeOsintDB, eid: str, closure_type: str, *, start: int = -10, end: int = 30) -> None:
    db.phases.append({"event_id": eid, "window_start": NOW + timedelta(minutes=start),
                      "window_end": NOW + timedelta(minutes=end),
                      "closure_policy": {"advance_closure_sec": 120, "closure_type": closure_type}})


def _movement(db: FakeOsintDB, status: str, route: list[int] | None) -> str:
    mid = str(uuid.uuid4())
    db.movements[mid] = {"movement_id": uuid.UUID(mid), "status": status}
    if route is not None:
        db.planned_routes.append({"movement_id": uuid.UUID(mid), "route_rank": 1, "segment_ids": list(route)})
    return mid


def _frame(mid: str, *, event_id: str | None = None, lon: float = 88.3961, lat: float = 22.5262,
           segment_id: int | None = None) -> tuple[str, dict]:
    return f"convoy:position:{mid}", {
        "movement_id": mid, "event_id": event_id, "lon": lon, "lat": lat, "speed_kmh": 42.0, "heading": 180.0,
        "t": NOW.isoformat().replace("+00:00", "Z"), "source": "emulated_gps", "progress": 0.4,
        "segment_id": segment_id,
    }


def _dispatch(db: FakeOsintDB, eid: str, status: str, *, waypoint: int | None = 30,
              payload: dict | None = None) -> str:
    did = str(uuid.uuid4())
    db.dispatches.append({"dispatch_id": uuid.UUID(did), "event_id": uuid.UUID(eid), "agency": "ambulance",
                          "unit_id": "AMB-108-07", "status": status, "waypoint_junction": waypoint,
                          "request_payload": payload or {}})
    return did


def _refs(snap: Any) -> dict[str, Any]:
    return {r.urn: r for r in snap.live_events}


# ── protected movements: the route the event runs ─────────────────────────────


async def test_an_active_protected_movement_carries_its_primary_route_never_its_alternates():
    db, conn = _db()
    eid = _event(db, "protected_movement", "active", [[1034, 1035], [1033, 1029], [1030]])
    snap = await live_state.snapshot(conn, now=NOW)
    ref = _refs(snap)[f"event:{eid}"]
    assert (ref.event_kind, ref.status) == ("protected_movement", "active")
    assert ref.segment_ids == [1034, 1035]  # the brain's alt-1 / alt-2 are contingencies, not the corridor
    assert ref.lon is not None and ref.lat is not None


async def test_a_movement_linked_event_without_a_spine_takes_its_planned_route():
    db, conn = _db()
    mid = _movement(db, "approved", [1035, 1036])
    eid = _event(db, "protected_movement", "active", [], movement_id=mid)
    _phase(db, eid, "partial")  # the brain's Z protocol phase closes that route
    snap = await live_state.snapshot(conn, now=NOW)
    assert _refs(snap)[f"event:{eid}"].segment_ids == [1035, 1036]
    assert {(c.segment_id, c.event_urn) for c in snap.closures} == {(1035, f"event:{eid}"), (1036, f"event:{eid}")}


async def test_active_events_come_first_within_the_bound(monkeypatch):
    db, conn = _db()
    stale = [_event(db, "work_zone", "planning", [[1033]], minutes_ago=600 + i) for i in range(3)]
    running = _event(db, "protected_movement", "active", [[1035]], minutes_ago=1)
    monkeypatch.setattr(live_state, "MAX_LIVE", 2)
    monkeypatch.setattr(live_state, "MAX_EVENTS", 2, raising=False)
    snap = await live_state.snapshot(conn, now=NOW)
    urns = [r.urn for r in snap.live_events if r.urn.startswith("event:")]
    assert f"event:{running}" in urns and len(urns) == 2
    assert {u.split(":", 1)[1] for u in urns} - {running} <= set(stale)


# ── convoys in motion ─────────────────────────────────────────────────────────


async def test_an_active_movement_and_its_live_frame_are_one_convoy_ref():
    db, conn = _db()
    mid = _movement(db, "active", [1034, 1035])
    key, doc = _frame(mid, lon=88.3967, lat=22.5271)
    snap = await live_state.snapshot(conn, now=NOW, valkey=FakeValkey({key: doc}))
    convoys = [r for r in snap.live_events if r.urn.startswith("convoy:")]
    assert len(convoys) == 1
    (ref,) = convoys
    assert ref.urn == f"convoy:{mid}" and ref.event_kind == "protected_movement" and ref.status == "active"
    assert (ref.lon, ref.lat) == (88.3967, 22.5271)  # the live convoy position
    assert ref.segment_ids == [1034, 1035]  # its route


async def test_a_frame_linked_to_an_active_protected_movement_runs_that_events_route():
    db, conn = _db()
    eid = _event(db, "protected_movement", "active", [[1035, 1036], [1033]])
    key, doc = _frame("escort-em-bypass-01", event_id=eid)
    snap = await live_state.snapshot(conn, now=NOW, valkey=FakeValkey({key: doc}))
    ref = _refs(snap)["convoy:escort-em-bypass-01"]
    assert ref.status == "active" and ref.segment_ids == [1035, 1036]
    assert _refs(snap)[f"event:{eid}"].status == "active"  # the event itself stays a ref of its own


async def test_a_convoy_without_a_frame_flags_by_route_only():
    db, conn = _db()
    mid = _movement(db, "active", [1035])
    ref = _refs(await live_state.snapshot(conn, now=NOW))[f"convoy:{mid}"]
    assert (ref.lon, ref.lat) == (None, None) and ref.segment_ids == [1035]


async def test_planning_and_finished_convoys_are_never_active_and_an_unlinked_frame_is():
    db, conn = _db()
    planning = _movement(db, "planning", [1035])
    done = _movement(db, "completed", [1035])
    approved_event = _event(db, "protected_movement", "approved", [[1035]])
    frames = dict([
        _frame(planning), _frame(done), _frame("escort-approved", event_id=approved_event),
        _frame("escort-unlinked", segment_id=1035),
    ])
    refs = _refs(await live_state.snapshot(conn, now=NOW, valkey=FakeValkey(frames)))
    assert refs[f"convoy:{planning}"].status == "planning"
    assert f"convoy:{done}" not in refs  # a finished movement is not a convoy in motion
    assert refs["convoy:escort-approved"].status == "approved"
    unlinked = refs["convoy:escort-unlinked"]
    assert unlinked.status == "active" and unlinked.segment_ids == [1035]  # a C-B frame: a convoy moving now


async def test_an_unreadable_valkey_never_fails_the_snapshot():
    class Broken:
        async def scan_iter(self, **_: Any):
            raise ConnectionError("valkey down (test)")
            yield  # pragma: no cover

    db, conn = _db()
    mid = _movement(db, "active", [1035])
    snap = await live_state.snapshot(conn, now=NOW, valkey=Broken())
    assert _refs(snap)[f"convoy:{mid}"].segment_ids == [1035]


# ── 108 routes ────────────────────────────────────────────────────────────────


async def test_an_en_route_108_dispatch_routes_along_its_units_path():
    db, conn = _db()
    eid = _event(db, "emergency_evacuation", "active", [[1034, 1033]])
    did = _dispatch(db, eid, "en_route", waypoint=30)
    snap = await live_state.snapshot(conn, now=NOW)
    # staged at the event's first spine segment (1034), to the nearest approach of junction 30 (1035)
    assert [(r.dispatch_urn, r.segment_ids) for r in snap.ambulance_routes] == [(f"dispatch:{did}", [1034, 1035])]


async def test_a_stored_route_wins_and_requested_on_scene_or_waypointless_dispatches_have_none():
    db, conn = _db()
    eid = _event(db, "emergency_evacuation", "active", [[1034]])
    stored = _dispatch(db, eid, "approved", payload={"route_segment_ids": [1032, 1035]})
    for status in ("requested", "on_scene", "completed"):
        _dispatch(db, eid, status, waypoint=30)
    _dispatch(db, eid, "en_route", waypoint=None)
    snap = await live_state.snapshot(conn, now=NOW)
    assert [(r.dispatch_urn, r.segment_ids) for r in snap.ambulance_routes] == [
        (f"dispatch:{stored}", [1032, 1035])
    ]


def _station(db: FakeOsintDB, segment_id: int | None) -> None:
    db.stations.append({"station_id": "AMB-POST-01", "agency": "ambulance", "name": "108 post (synthetic)",
                        "lon": 88.4030, "lat": 22.5150, "segment_id": segment_id})


async def test_a_unit_stages_only_from_its_events_own_spine_never_a_planned_route_fallback():
    """units.router._resolve_path stages from the event's OWN current spine; an event without one (its route
    here is the linked movement's planned route) leaves the unit waiting: no 108 route is invented."""
    db, conn = _db()
    mid = _movement(db, "active", [1035, 1036])
    eid = _event(db, "protected_movement", "active", [], movement_id=mid)
    _dispatch(db, eid, "en_route", waypoint=30)
    snap = await live_state.snapshot(conn, now=NOW)
    assert _refs(snap)[f"event:{eid}"].segment_ids == [1035, 1036]  # the event still flags on that route
    assert snap.ambulance_routes == []


async def test_a_pursuit_unit_stages_at_its_agencys_post_and_a_post_without_a_segment_draws_no_path():
    db, conn = _db()
    pursuit = _event(db, "vehicle_pursuit", "active", [[1034]])  # the suspect's spine: never the unit's start
    did = _dispatch(db, pursuit, "en_route", waypoint=30)
    _station(db, 1033)
    snap = await live_state.snapshot(conn, now=NOW)
    assert [(r.dispatch_urn, r.segment_ids) for r in snap.ambulance_routes] == [(f"dispatch:{did}", [1033, 1034, 1035])]
    # a post the road graph cannot place (no nearest segment): the unit waits at the post, as the units module draws it
    db.stations[0]["segment_id"] = None
    live_state.reset_route_cache()
    assert (await live_state.snapshot(conn, now=NOW)).ambulance_routes == []


async def test_a_pursuit_without_a_spine_is_not_staged_at_a_post():
    """The units module reads a pursuit only from an event WITH a spine (``pursuit = bool(spine) and ...``)."""
    db, conn = _db()
    mid = _movement(db, "active", [1035])
    eid = _event(db, "vehicle_pursuit", "active", [], movement_id=mid)
    _dispatch(db, eid, "en_route", waypoint=30)
    _station(db, 1033)
    snap = await live_state.snapshot(conn, now=NOW)
    assert snap.ambulance_routes == []
    assert not any("agency_stations" in c for c in conn.calls)


async def test_a_dispatch_already_on_an_approach_drives_straight_and_paths_are_cached():
    db, conn = _db()
    eid = _event(db, "emergency_evacuation", "active", [[1035, 1034]])
    _dispatch(db, eid, "en_route", waypoint=30)
    first = await live_state.snapshot(conn, now=NOW)
    assert [r.segment_ids for r in first.ambulance_routes] == [[1035]]
    eid2 = _event(db, "emergency_evacuation", "active", [[1033]])
    _dispatch(db, eid2, "approved", waypoint=30)
    await live_state.snapshot(conn, now=NOW)
    searches = sum(1 for c in conn.calls if "pgr_dijkstra" in c)
    await live_state.snapshot(conn, now=NOW)
    assert sum(1 for c in conn.calls if "pgr_dijkstra" in c) == searches  # the second read is cached


# ── closures ──────────────────────────────────────────────────────────────────


async def test_closures_come_from_active_events_in_both_vocabularies_only():
    db, conn = _db()
    brain = _event(db, "protected_movement", "active", [[1035, 1036], [1033]])
    _phase(db, brain, "full")  # the brain's Z+ protocol phase
    emulator = _event(db, "procession", "active", [[1030]])
    _phase(db, emulator, "partial_closure")
    approved = _event(db, "protected_movement", "approved", [[1034]])
    _phase(db, approved, "full_closure")  # not in force: the movement has not started
    hold = _event(db, "race", "active", [[1029]])
    _phase(db, hold, "signal_hold")
    later = _event(db, "ceremonial", "active", [[1031]])
    _phase(db, later, "full_closure", start=60, end=120)
    snap = await live_state.snapshot(conn, now=NOW)
    assert {(c.segment_id, c.event_urn) for c in snap.closures} == {
        (1035, f"event:{brain}"), (1036, f"event:{brain}"), (1030, f"event:{emulator}"),
    }


# ── read-only ─────────────────────────────────────────────────────────────────


async def test_the_snapshot_is_read_only():
    db, conn = _db()
    eid = _event(db, "protected_movement", "active", [[1034, 1035]])
    _phase(db, eid, "full")
    _dispatch(db, eid, "en_route", waypoint=30)
    mid = _movement(db, "active", [1035])
    await live_state.snapshot(conn, now=NOW, valkey=FakeValkey(dict([_frame(mid)])))
    writes = [s for s in conn.calls if s.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))]
    assert writes == []


# ── lockstep: the private helpers borrowed from the units module and the adaptive loop ──


def test_the_borrowed_private_helpers_keep_their_names_shapes_and_staging_rule():
    """live_state reuses, by name, the units module's C-N staging helpers and the adaptive loop's movement-route
    query (private names with no public twin; the WP reuses the oracle's own queries, no new ones). A rename, a
    signature change or a new staging rule there must fail HERE, by name, never inside an ingest."""
    import inspect

    from traffic_oracle.adaptive import engine_loop
    from traffic_oracle.units import router as units_router

    assert live_state._MOVEMENT_ROUTES_SQL is engine_loop._MOVEMENT_ROUTES_SQL
    assert "convoy.planned_routes" in engine_loop._MOVEMENT_ROUTES_SQL and "$1::uuid[]" in engine_loop._MOVEMENT_ROUTES_SQL
    adjacent = units_router._SQL_JUNCTION_ADJACENT_SEGMENT
    assert "segment_adjacency" in adjacent and "AS segment_id" in adjacent and "via_junction_id = $1" in adjacent
    for name, params in {"_nearest_station": ["conn", "agency", "waypoint"],
                         "_shortest_path_on": ["conn", "source", "target"]}.items():
        fn = getattr(units_router, name)
        assert inspect.iscoroutinefunction(fn), name
        assert list(inspect.signature(fn).parameters) == params, name
    assert list(inspect.signature(units_router.cheapest_path).parameters) == ["paths"]
    assert units_router.PURSUIT_EVENT_KIND == "vehicle_pursuit"
    # the staging rule live_state mirrors (_ambulance_route): the event's own spine; a pursuit WITH a spine
    # stages at its agency's post, on that post's segment (None: no path)
    rule = inspect.getsource(units_router._resolve_path)
    assert "pursuit = bool(spine) and" in rule, "units: the pursuit rule changed; update live_state._ambulance_route"
    assert 'start_seg = station["point"], station["segment_id"]' in rule, "units: the post staging rule changed"


# ── through the REAL pipeline: the second-order flags fire on these segments ──
#
# on the fake store's Mumbai slice (fixtures/osint/fakedb.py): the Western Express Highway from Kalanagar (1014)
# through Vakola (junction 39) to the Sahar Elevated Road (1015, junction 48), with 1013 the Bandra approach — the
# WEH situation of osint_common.testing.weh_signals() resolves to segment 1015 on the Mumbai gazetteer


def _current_weh_signals() -> list[Any]:
    from osint_common.testing import weh_signals
    from osint_common.types import RawOsintSignal
    from traffic_oracle.osint import ingest

    base = weh_signals()
    first = min(s.published_at for s in base)
    out = []
    for s in base:  # the same reports, an hour ago: still current at the snapshot
        data = s.model_dump()
        data.update(published_at=NOW - timedelta(hours=1) + (s.published_at - first),
                    fetched_at=NOW - timedelta(minutes=5))
        out.append(ingest.prepare_signal(RawOsintSignal.model_validate(data)).signal)
    return out


async def test_the_real_pipeline_raises_every_second_order_flag_on_the_live_state():
    pytest.importorskip("osint_geo.resolver", reason="osint_geo not importable")
    pytest.importorskip("osint_analysis.pipeline", reason="osint_analysis not importable")
    from traffic_oracle.osint import ingest

    db, conn = _db()
    corridor = _event(db, "protected_movement", "active", [[1014, 1015], [1013]])
    _phase(db, corridor, "full")
    planned = _event(db, "protected_movement", "approved", [[1015]])
    _phase(db, planned, "full_closure")
    _event(db, "protected_movement", "planning", [[1015]])
    accident = _event(db, "road_accident", "approved", [[1015]])  # approved: never corroborated
    medical = _event(db, "emergency_evacuation", "active", [[1014, 1013]])
    # staged at the event's first spine segment (1014), to the nearest approach of junction 48 (1015)
    ambulance = _dispatch(db, medical, "en_route", waypoint=48)
    _dispatch(db, medical, "requested", payload={"route_segment_ids": [1015]})
    convoy = _movement(db, "active", [1015])
    idle = _movement(db, "planning", [1015])
    # both convoys' position frames ~100 m from the situation's point on the Western Express Highway: only the
    # moving one is a flag
    valkey = FakeValkey(dict([_frame(convoy, lon=72.8463, lat=19.0858), _frame(idle, lon=72.8463, lat=19.0858)]))

    live = await live_state.snapshot(conn, now=NOW, valkey=valkey)
    pipeline = ingest.get_pipeline()
    result = pipeline.run(_current_weh_signals(), resolver=pipeline.resolver, live=live, now=live.as_of)
    (sit,) = [e for e in result.resolved if e.is_event]
    assert sit.segment_id == 1015
    flags = {(f.kind, f.urn, f.segment_id) for f in sit.second_order}
    assert flags == {
        ("protected_corridor", f"event:{corridor}", 1015),
        ("convoy", f"convoy:{convoy}", 1015),
        ("ambulance_route", f"dispatch:{ambulance}", 1015),
        ("closure", f"event:{corridor}", 1015),
    }
    named = {f.urn for f in sit.second_order}
    assert not named & {f"event:{planned}", f"event:{accident}", f"convoy:{idle}"}
    # a report on a protected corridor is a second-order effect, never the movement itself
    assert sit.attach.novel and sit.attach.corroborates_live_urn is None
    assert all("segment 1015" in f.note.lower() for f in sit.second_order)  # short, neutral notes
