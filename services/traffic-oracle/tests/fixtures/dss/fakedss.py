"""The offline backend of the decision-support tests (OS-6) and the int3c switch.

* :class:`FakeDssDB` / :class:`FakeDssConn` extend OS-5's fake store (``fixtures/osint/fakedb.py``, read-only
  reuse) with the 022 tables (``decision.*``), the dispatch channel (``corridor.dispatches`` + its audit), the
  reads of the subject framing and a small DIRECTED road graph around segment 1045 (the int3c values), on which
  the pgRouting statements of ``decision_support.cascade`` are answered in Python (``networkx``).  Every
  statement is matched exactly (an unexpected one is an ``AssertionError``), ``transaction()`` rolls every table
  back when its block raises, and ``calls`` records every statement (the recording connection).
* :class:`FakeValkey` is a C-A unit feed (``units:emulated:*``).
* :func:`dss_backend` yields the fake, or the int3c / int3cl sandbox when ``OSINT_TEST_DSN`` is set (the DSN
  guard of ``fixtures/osint/db.py``), cleaning up every row the test wrote.
* Synthetic only: fictional publishers, emulated unit ids, no person anywhere.
"""

from __future__ import annotations

import itertools
import json
import os
import uuid
from collections.abc import AsyncIterator, Iterable, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import networkx as nx
import pytest

from fixtures.osint.db import DSN_ENV, osint_db
from fixtures.osint.fakedb import FakeOsintConn, FakeOsintDB, FakePool
from fixtures.osint.harness import client, make_app
from fixtures.osint.signals import FakePipeline, canonical_set, payload
from osint_common.types import RawOsintSignal
from traffic_oracle.city import common
from traffic_oracle.decision_support import cascade, feasibility
from traffic_oracle.decision_support import store as dss_store
from traffic_oracle.osint import store as osint_store
from traffic_oracle.units import router as units_router

__all__ = [
    "BACKENDS",
    "FIXTURES",
    "OFFICER",
    "ROAD_GRAPH",
    "DssBackend",
    "FakeDssConn",
    "FakeDssDB",
    "FakeValkey",
    "dss_app",
    "dss_backend",
    "load_fixture",
    "create_event",
    "seed_situations",
    "road_units",
    "write_statements",
]

FIXTURES = Path(__file__).resolve().parent
OFFICER = "Sandbox Officer"

BACKENDS = [
    "fake",
    pytest.param("db", marks=pytest.mark.skipif(not os.environ.get(DSN_ENV), reason=f"{DSN_ENV} not set")),
]


def load_fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# A SYNTHETIC neighbourhood of segment 1045 (Sector V - New Town link) in the directed line graph.  The
# topology and costs are the int3c corridor.road_graph values, rounded; the other ids, the junction ids
# (9, 10, 28, 29) and the Salt Lake / New Town road names are local to this fake (not the network's).
# ---------------------------------------------------------------------------

#: segment → (road_name, road_class, lanes, speed_kmh, length_m, lon, lat)
ROAD_SEGMENTS: dict[int, tuple[str, str, int, float, float, float, float]] = {
    1016: ("Salt Lake Bypass", "primary", 6, 60, 1444.0, 88.4554, 22.60368),
    1019: ("Rajarhat Main Road", "secondary", 4, 40, 2492.0, 88.46534, 22.59787),
    1020: ("Narkelbagan Road", "tertiary", 4, 40, 3227.0, 88.45689, 22.57557),
    1023: ("Kestopur Road", "tertiary", 4, 40, 3205.0, 88.43863, 22.59813),
    1033: ("EM Bypass (North)", "trunk", 4, 80, 6852.0, 88.4269, 22.62581),
    1040: ("Biswa Bangla Sarani (South)", "trunk", 8, 80, 5635.0, 88.43604, 22.54694),
    1045: ("Sector V - New Town link", "trunk", 8, 80, 3416.0, 88.44735, 22.5782),
    1047: ("Major Arterial Road (New Town)", "trunk", 4, 70, 7856.0, 88.41821, 22.56317),
}

#: (from, to, via junction, cost s) — the 012 directed line graph
ROAD_GRAPH: tuple[tuple[int, int, int, float], ...] = (
    (1016, 1019, 9, 98.6), (1016, 1023, 9, 89.6), (1016, 1045, 9, 98.6),
    (1019, 1016, 9, 236.3), (1019, 1023, 9, 227.3), (1019, 1045, 9, 236.3),
    (1020, 1040, 28, 293.4), (1020, 1045, 28, 300.4),
    (1023, 1016, 9, 291.5), (1023, 1019, 9, 291.5), (1023, 1033, 29, 298.5), (1023, 1045, 9, 291.5),
    (1023, 1047, 29, 298.5),
    (1033, 1023, 29, 318.3), (1033, 1047, 29, 311.3),
    (1040, 1020, 28, 256.6), (1040, 1045, 28, 263.6), (1040, 1047, 10, 265.6),
    (1045, 1016, 9, 165.7), (1045, 1019, 9, 165.7), (1045, 1020, 28, 163.7), (1045, 1023, 9, 156.7),
    (1045, 1040, 28, 163.7),
    (1047, 1023, 29, 414.0), (1047, 1033, 29, 407.0), (1047, 1040, 10, 416.0),
)

SIGNALISED_JUNCTIONS = frozenset({9})


def _graph(exclude: Iterable[int] = ()) -> nx.DiGraph:
    g = nx.DiGraph()
    ex = set(exclude)
    for a, b, _via, cost in ROAD_GRAPH:
        if a in ex or b in ex:
            continue
        g.add_edge(a, b, weight=cost)
    return g


def road_units(*, police: int = 1, ambulance: int = 1, committed_police: int = 1, traffic: int = 0,
             prefix: str = "") -> dict[str, str]:
    """A C-A unit feed near Sector V: ``police`` free patrols plus ``committed_police`` committed ones (their
    dispatches are seeded by the test), ``ambulance`` 108s, ``traffic`` traffic units — emulated ids only
    (``prefix`` makes them run-unique on a shared sandbox)."""
    frames: dict[str, str] = {}
    t = datetime.now(UTC).isoformat()

    def add(unit_id: str, agency: str, lon: float, lat: float) -> None:
        unit_id = prefix + unit_id
        frames[f"units:emulated:{unit_id}"] = json.dumps(
            {"unit_id": unit_id, "agency": agency, "lon": lon, "lat": lat, "status": "patrol", "t": t}
        )

    for i in range(police + committed_police):
        add(f"PCR-EM-{i + 1:02d}", "police", 88.4554 + 0.001 * i, 22.6037)
    for i in range(ambulance):
        add(f"108-EM-{i + 1:02d}", "ambulance", 88.4360, 22.5470 + 0.001 * i)
    for i in range(traffic):
        add(f"TP-EM-{i + 1:02d}", "traffic", 88.4653, 22.5979)
    return frames


class FakeValkey:
    """``scan_iter`` + ``mget`` over a dict of C-A frames (``units:emulated:*``)."""

    def __init__(self, frames: Mapping[str, str] | None = None) -> None:
        self.frames = dict(frames or {})

    async def scan_iter(self, match: str = "*", count: int = 100) -> AsyncIterator[str]:
        prefix = match.rstrip("*")
        for k in sorted(self.frames):
            if k.startswith(prefix):
                yield k

    async def mget(self, keys: list[str]) -> list[Any]:
        return [self.frames.get(k) for k in keys]


# ---------------------------------------------------------------------------
# The fake store
# ---------------------------------------------------------------------------


class FakeDssDB(FakeOsintDB):
    _TABLES = (*FakeOsintDB._TABLES, "sim_runs", "dispatch_events")

    def __init__(self, *, migrated: bool = True) -> None:
        super().__init__(migrated=migrated)
        self.sim_runs: list[dict] = []
        self.dispatch_events: list[dict] = []
        self.segments |= set(ROAD_SEGMENTS)
        self.junctions |= {9, 10, 28, 29}
        self._log_seq = itertools.count(1)


def _js(value: Any) -> Any:
    return json.loads(value) if isinstance(value, str) else value


def _ts(value: Any) -> datetime:
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _proposed_ids(dispatch: Mapping[str, Any]) -> list[str] | None:
    """``_SQL_COMMITTED_UNITS``'s ``proposed_unit_ids`` column: a decision-support request's proposed units."""
    payload = _js(dispatch.get("request_payload"))
    if not isinstance(payload, dict) or payload.get("source") != "decision_support":
        return None
    ids = payload.get("proposed_unit_ids")
    if not isinstance(ids, list):
        return None
    return [str(u) for u in ids]


class FakeDssConn(FakeOsintConn):
    """OS-5's fake connection plus the decision-support statements."""

    def __init__(self, db: FakeDssDB) -> None:
        super().__init__(db)
        self.handlers.update(self._dss_handlers())
        self.prefix_handlers.append(("INSERT INTO corridor.dispatch_events (", self._audit_insert))
        #: test hook: raise inside the next DSS_DISPATCH_INSERT number N (1-based)
        self.fail_on_dispatch: int | None = None
        self._dispatch_count = 0

    async def fetchval(self, sql: str, *args: Any) -> Any:
        if sql == units_router._SQL_AUDIT_DETAIL_COLUMN:
            self.calls.append(sql)
            return True
        return await super().fetchval(sql, *args)

    # -- handlers -----------------------------------------------------------
    def _dss_handlers(self) -> dict[str, Any]:
        db = self.db
        s = dss_store
        h: dict[str, Any] = {
            s._SQL_LOCK_SUBJECT: lambda urn: [],
            s._SQL_PROPOSED_FOR_UPDATE: lambda urn: sorted(
                [d for d in db.dss.values() if d["event_urn"] == urn and d["state"] == "proposed"],
                key=lambda d: d["generated_at"], reverse=True),
            s._SQL_REUSABLE: lambda urn, fp, since: sorted(
                [d for d in db.dss.values() if d["event_urn"] == urn and d["state"] == "proposed"
                 and d["input_fingerprint"] == fp and _ts(d["generated_at"]) > since],
                key=lambda d: d["generated_at"], reverse=True)[:1],
            s._SQL_EXPIRE: lambda did: self._set_state(did, "expired"),
            s._SQL_SUPERSEDE: lambda did, by: self._set_state(did, "superseded", superseded_by=str(by)),
            s._SQL_INSERT_DSS: self._insert_dss,
            s._SQL_INSERT_COA: self._insert_coa,
            s._SQL_INSERT_SIM_RUN: self._insert_sim_run,
            s._SQL_DSS_ROW: lambda did: [dict(db.dss[str(did)])] if str(did) in db.dss else [],
            s._SQL_DSS_ROW_FOR_UPDATE: lambda did: [dict(db.dss[str(did)])] if str(did) in db.dss else [],
            s._SQL_COAS: lambda did: sorted(
                [dict(c) for (d, _), c in db.coa.items() if d == str(did)], key=lambda c: c["coa_id"]),
            s._SQL_LATEST_LOG: lambda did: sorted(
                [x for x in db.dss_log if x["dss_id"] == str(did)], key=lambda x: (x["at"], x["log_id"]),
                reverse=True)[:1],
            s._SQL_DECIDE: self._decide,
            s._SQL_INSERT_LOG: self._insert_log,
            s._SQL_EVENT_SUBJECT: self._event_subject,
            s._SQL_EVENT_STATUS: lambda eid: (
                [{"status": db.corridor[str(eid)]["status"]}] if str(eid) in db.corridor else []),
            s._SQL_SEGMENT_POINT: lambda sid: (
                [{"road_name": ROAD_SEGMENTS[sid][0], "lon": ROAD_SEGMENTS[sid][5], "lat": ROAD_SEGMENTS[sid][6]}]
                if sid in ROAD_SEGMENTS else []),
            s.DSS_DISPATCH_INSERT: self._dispatch_insert,
            units_router._SQL_EVENT_CHECK: lambda eid: (
                [{"event_id": db.corridor[str(eid)]["event_id"], "status": db.corridor[str(eid)]["status"]}]
                if str(eid) in db.corridor else []),
            units_router._SQL_EVENT_SPINE_START: self._spine_start,
            feasibility._SQL_COMMITTED_UNITS: lambda statuses, live: [
                {"agency": d["agency"], "unit_id": d["unit_id"], "proposed_unit_ids": _proposed_ids(d)}
                for d in db.dispatches
                if d["status"] in statuses and db.corridor.get(str(d["event_id"]), {}).get("status") in live
            ],
            cascade._SQL_ADJACENCY: self._adjacency,
            cascade._SQL_SEGMENT_INFO: self._segment_info,
            cascade._SQL_KSP: self._ksp,
            cascade._SQL_PATH_COSTS: self._path_costs,
            cascade._SQL_NEAREST_SEGMENTS: self._nearest,
        }
        return h

    def _set_state(self, did: Any, state: str, **extra: Any) -> list:
        d = self.db.dss.get(str(did))
        if d is None or d["state"] != "proposed":
            return []
        d.update(state=state, updated_at=datetime.now(UTC), **extra)
        return [{"dss_id": d["dss_id"]}]

    _DSS_KEYS = ("dss_id", "event_urn", "generated_at", "horizon_min", "seed", "input_fingerprint", "situation",
                 "criteria", "ahp", "recommendation", "provenance", "scoring_note", "labels", "strategy_prior",
                 "requested_by")

    def _insert_dss(self, *params: Any) -> None:
        row = dict(zip(self._DSS_KEYS, params, strict=True))
        if any(d["event_urn"] == row["event_urn"] and d["state"] == "proposed" for d in self.db.dss.values()):
            raise AssertionError("uq_decision_support_one_proposed violated")  # the 022 partial unique index
        row.update(dss_id=str(row["dss_id"]), state="proposed", decided_by=None, decided_at=None,
                   decision_note=None, chosen_coa_id=None, superseded_by=None, updated_at=datetime.now(UTC))
        row["generated_at"] = _ts(row["generated_at"])
        self.db.dss[row["dss_id"]] = row

    _COA_KEYS = ("dss_id", "coa_id", "kind", "label", "actions", "predicted_outcome", "resource_feasibility",
                 "attributes", "score", "ethics")

    def _insert_coa(self, *params: Any) -> None:
        row = dict(zip(self._COA_KEYS, params, strict=True))
        row["dss_id"] = str(row["dss_id"])
        self.db.coa[(row["dss_id"], row["coa_id"])] = row

    def _insert_sim_run(self, dss_id, coa_id, sim_run_id, method, seed, metrics) -> None:
        if (str(dss_id), coa_id) not in self.db.coa:
            raise AssertionError("coa_sim_runs FK: the COA row must exist")
        self.db.sim_runs.append({"dss_id": str(dss_id), "coa_id": coa_id, "sim_run_id": sim_run_id,
                                 "method": method, "seed": seed, "metrics": _js(metrics)})

    def _decide(self, did, state, actor, at, coa_id, note) -> list:
        d = self.db.dss.get(str(did))
        if d is None or d["state"] != "proposed":
            return []
        d.update(state=state, decided_by=actor, decided_at=_ts(at), chosen_coa_id=coa_id, decision_note=note,
                 updated_at=datetime.now(UTC))
        return [{"dss_id": d["dss_id"]}]

    def _insert_log(self, did, decision, coa_id, officer, note, at, promoted, dispatch_ids, next_steps) -> list:
        row = {"log_id": next(self.db._log_seq), "dss_id": str(did), "decision": decision, "coa_id": coa_id,
               "officer": officer, "note": note, "at": _ts(at),
               "promoted_event_id": str(promoted) if promoted else None,
               "dispatch_ids": [str(x) for x in dispatch_ids], "next_steps": _js(next_steps)}
        self.db.dss_log.append(row)
        return [{"log_id": row["log_id"]}]

    def _event_subject(self, eid: Any) -> list:
        e = self.db.corridor.get(str(eid))
        if e is None:
            return []
        return [{"event_id": e["event_id"], "event_kind": e["event_kind"], "title": e["title"],
                 "description": e["description"], "status": e["status"], "metadata": e["metadata"],
                 "source_kind": e["source_kind"], "credibility": e["credibility"],
                 "verification_state": e["verification_state"], "provenance": e.get("provenance"),
                 "geotag_lon": e.get("geotag_lon"), "geotag_lat": e.get("geotag_lat")}]

    def _spine_start(self, eid: Any) -> list:
        rows = sorted((r for r in self.db.routes if str(r["event_id"]) == str(eid)), key=lambda r: r["route_rank"])
        e = self.db.corridor.get(str(eid))
        return [{"segment_ids": rows[0]["segment_ids"], "event_kind": e["event_kind"] if e else None}] if rows else []

    def _dispatch_insert(self, event_id, agency, unit_id, waypoint, requested_by, payload) -> list:
        self._dispatch_count += 1
        if self.fail_on_dispatch is not None and self._dispatch_count >= self.fail_on_dispatch:
            self.fail_on_dispatch = None
            raise RuntimeError("forced step-2 failure (test)")
        did = uuid.uuid4()
        now = datetime.now(UTC)
        self.db.dispatches.append({
            "dispatch_id": did, "event_id": event_id, "agency": agency, "unit_id": unit_id,
            "waypoint_junction": waypoint, "status": "requested", "requested_by": requested_by,
            "request_payload": _js(payload), "created_at": now,
        })
        return [{"dispatch_id": did, "created_at": now}]

    def _audit_insert(self, dispatch_id, from_status, to_status, actor, note, detail=None) -> None:
        self.db.dispatch_events.append({"dispatch_id": str(dispatch_id), "from_status": from_status,
                                        "to_status": to_status, "actor": actor, "note": note,
                                        "detail": _js(detail) if detail else None})

    # -- the road graph ----------------------------------------------------------
    def _adjacency(self, ids: list[int]) -> list:
        want = set(ids)
        return [
            {"from_segment_id": a, "to_segment_id": b, "via_junction_id": via,
             "signal_control": via in SIGNALISED_JUNCTIONS}
            for a, b, via, _ in ROAD_GRAPH if a in want or b in want
        ]

    def _segment_info(self, ids: list[int]) -> list:
        out = []
        for sid in sorted(set(ids)):
            if sid not in ROAD_SEGMENTS:
                continue
            name, rclass, lanes, speed, length, lon, lat = ROAD_SEGMENTS[sid]
            out.append({"segment_id": sid, "road_name": name, "road_class": rclass, "lanes": lanes,
                        "speed_limit_kmh": speed, "oneway": False, "length_m": length, "lon": lon, "lat": lat})
        return out

    def _ksp(self, source: int, target: int, k: int, exclude: list[int]) -> list:
        g = _graph(exclude)
        if source not in g or target not in g:
            return []
        out = []
        try:
            paths = itertools.islice(nx.shortest_simple_paths(g, source, target, weight="weight"), k)
            for pid, path in enumerate(paths, start=1):
                agg = 0.0
                for seq, node in enumerate(path, start=1):
                    out.append({"path_id": pid, "path_seq": seq, "node": node, "cost": 0.0, "agg_cost": agg})
                    if seq < len(path):
                        agg += g[node][path[seq]]["weight"]
        except nx.NetworkXNoPath:
            return []
        return out

    def _path_costs(self, sources: list[int], target: int) -> list:
        g = _graph()
        out = []
        for s in sorted(sources):
            try:
                out.append({"start_vid": s, "agg_cost": nx.shortest_path_length(g, s, target, weight="weight")})
            except (nx.NetworkXNoPath, nx.NodeNotFound):
                continue
        return out

    def _nearest(self, lons: list[float], lats: list[float]) -> list:
        out = []
        for i, (lon, lat) in enumerate(zip(lons, lats, strict=True), start=1):
            best = min(ROAD_SEGMENTS, key=lambda s: (ROAD_SEGMENTS[s][5] - lon) ** 2 + (ROAD_SEGMENTS[s][6] - lat) ** 2)
            out.append({"i": i, "segment_id": best})
        return out


# ---------------------------------------------------------------------------
# Backends
# ---------------------------------------------------------------------------


@dataclass
class DssBackend:
    kind: str
    pool: Any
    db: FakeDssDB | None = None
    conn: FakeDssConn | None = None
    cleanup: Any = None
    #: the subject URNs this test created (every DSS row of theirs is deleted on teardown)
    subjects: set[str] = field(default_factory=set)

    def track(self, *signals: Any) -> None:
        if self.cleanup is not None:
            self.cleanup.signal_ids.update(s.signal_id for s in signals)

    def track_event(self, event_id: str | None) -> None:
        if self.cleanup is not None and event_id:
            self.cleanup.event_ids.add(str(event_id))

    def track_dss(self, *dss_ids: str | None) -> None:
        if self.cleanup is not None:
            self.cleanup.dss_ids.update(str(d) for d in dss_ids if d)

    async def fetch(self, sql: str, *args: Any) -> list:
        """A read for assertions (the database backend only)."""
        async with self.pool.acquire() as conn:
            return list(await conn.fetch(sql, *args))


@asynccontextmanager
async def dss_backend(kind: str, tag: str) -> AsyncIterator[DssBackend]:
    if kind == "fake":
        db = FakeDssDB()
        conn = FakeDssConn(db)
        yield DssBackend(kind, FakePool(conn), db=db, conn=conn)
        return
    saved = osint_store.FETCHED_WINDOW_HOURS
    osint_store.FETCHED_WINDOW_HOURS = 0
    bk: DssBackend | None = None
    try:
        async with osint_db(tag) as (pool, cleanup):
            bk = DssBackend(kind, pool, cleanup=cleanup)
            try:
                yield bk
            finally:
                # every DSS row of the test's own subjects (also the ones a test did not track by id)
                urns = sorted(bk.subjects)
                if urns:
                    async with pool.acquire() as conn:
                        rows = await conn.fetch(
                            "SELECT dss_id FROM decision.decision_support WHERE event_urn = ANY($1::text[])", urns
                        )
                    cleanup.dss_ids.update(str(r["dss_id"]) for r in rows)
    finally:
        osint_store.FETCHED_WINDOW_HOURS = saved


def dss_app(bk: DssBackend, pipeline: Any = None, *, units: Mapping[str, str] | None = None) -> Any:
    """The real ``create_app()`` over the backend, with a fake C-A unit feed."""
    app = make_app(bk.pool, pipeline)
    app.state.adaptive_valkey = FakeValkey(units if units is not None else road_units())
    common.reset_relation_cache()
    return app


def _on_sector_v(report: Any) -> Any:
    """The canonical EM Bypass crash report re-told on the Sector V - New Town link (segment 1045), the subject of
    this fixture's synthetic road graph: same reports, same publishers, same classes, a place in this graph."""
    def told(text: str) -> str:
        return text.replace("EM Bypass near Kasba", "the Sector V - New Town link").replace(
            "EM Bypass", "Sector V - New Town link")

    return RawOsintSignal.model_validate({**report.model_dump(), "title": told(report.title), "text": told(report.text)})


async def seed_situations(bk: DssBackend, tag: str, *, units: Mapping[str, str] | None = None) -> tuple[Any, dict]:
    """The canonical synthetic situations through OS-5's ingest route (run-scoped): the road-accident
    ``affray+collision`` re-told at segment 1045 (the Sector V - New Town link), the robbery at junction 23
    (Gariahat crossing), the SACHET Kolkata district alert (area-level) and a held single social post.
    Returns ``(app, {em_bypass, gariahat, sachet, social})``."""
    sets = canonical_set(tag)
    sets["em_bypass"] = [_on_sector_v(s) for s in sets["em_bypass"]]
    signals = [*sets["em_bypass"], sets["gariahat"], sets["sachet_district"], sets["social"]]
    bk.track(*signals)
    app = dss_app(bk, FakePipeline(tag), units=units)
    async with client(app) as c:
        r = await c.post("/api/v1/osint/signals", json={"signals": [payload(x) for x in signals]})
    assert r.status_code == 200, r.text
    fake = FakePipeline(tag)
    by_fused = {i["fused_event_id"]: i["osint_event_id"] for i in r.json()["resolved"]}
    ids = {
        "em_bypass": by_fused[fake.fused_id(sets["em_bypass"][0].signal_id)],
        "gariahat": by_fused[fake.fused_id(sets["gariahat"].signal_id)],
        "sachet": by_fused[fake.fused_id(sets["sachet_district"].signal_id)],
        "social": by_fused[fake.fused_id(sets["social"].signal_id)],
    }
    bk.subjects.update(f"osint_event:{v}" for v in ids.values())
    return app, ids


async def create_event(bk: DssBackend, app: Any, *, kind: str = "road_accident", segments: list[int] | None = None,
                       title: str = "Test corridor event: two-car collision") -> str:
    """An operator corridor event (run-scoped, tracked for cleanup)."""
    async with client(app) as c:
        r = await c.post("/api/v1/events", json={
            "event_kind": kind, "title": title, "description": "Synthetic test event, one lane blocked",
            "route_spines": [{"label": "primary", "segment_ids": segments or [1045]}],
            "officer": OFFICER, "metadata": {"source": "operator"},
        })
    assert r.status_code in (200, 201), r.text
    eid = str(r.json()["event_id"])
    bk.track_event(eid)
    bk.subjects.add(f"event:{eid}")
    return eid


_WRITE_PREFIXES = ("INSERT", "UPDATE", "DELETE")


def write_statements(calls: Iterable[str]) -> list[str]:
    """The write statements a recording connection saw."""
    return [c for c in calls if c.lstrip().upper().startswith(_WRITE_PREFIXES)]
