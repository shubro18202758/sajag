"""An in-memory fake of the OSINT store (migration 021), the decision log (022) and the slice of
the corridor-event tables a promotion writes — the offline backend of the OS-5 tests.

Every SQL constant of ``traffic_oracle.osint.store`` / ``live_state`` and the OSINT reads of
``traffic_oracle.city`` is answered by a handler that applies the statement's own filters to the
in-memory tables (the ``test_city_router.py`` pattern); the events module's inline statements
(create, lifecycle transition) are matched by prefix.  An unexpected statement is an
``AssertionError`` (never a silent empty answer).  ``transaction()`` rolls the tables back when its
block raises, so "nothing is stored" is observable.  The same tests run against the int3c sandbox
when ``OSINT_TEST_DSN`` is set (``fixtures/osint/db.py``).
"""

from __future__ import annotations

import copy
import itertools
import json
import re
import uuid
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

from traffic_oracle import events as events_mod
from traffic_oracle.adaptive import engine_loop
from traffic_oracle.city import common
from traffic_oracle.city import dossier as dos
from traffic_oracle.city import entities as ent
from traffic_oracle.city import feed as feed_mod
from traffic_oracle.osint import live_state, store
from traffic_oracle.units import router as units_router

__all__ = ["FakeOsintConn", "FakeOsintDB", "FakePool", "FakeValkey", "city_osint_handlers"]

_FAR = datetime(1970, 1, 1, tzinfo=UTC)


def _now() -> datetime:
    return datetime.now(UTC)


def _js(value: Any) -> Any:
    return json.loads(value) if isinstance(value, str) else value


def _ids(values: Iterable[Any]) -> set[str]:
    return {str(v) for v in (values or [])}


class FakeOsintDB:
    """The tables (``relations`` says which exist, like ``to_regclass``)."""

    def __init__(self, *, migrated: bool = True) -> None:
        self.relations: set[str] = {"events.event_status_log"}
        self.columns: set[tuple[str, str]] = set()
        if migrated:
            self.relations |= set(common.OSINT_RELATIONS) | set(common.DECISION_RELATIONS)
            self.relations.add(common.DECISION_LOG_RELATION)
            self.columns.add((common.EVENTS_TABLE, common.EVENT_PROVENANCE_COLUMN))
        self.signals: dict[str, dict] = {}
        self.events: dict[str, dict] = {}
        self.sources: dict[tuple[str, str], str] = {}
        self.geocodes: list[dict] = []
        self.gazetteer: dict[int, dict] = {}
        self.corridor: dict[str, dict] = {}
        self.routes: list[dict] = []
        self.status_log: list[dict] = []
        self.phases: list[dict] = []
        self.dispatches: list[dict] = []
        #: convoy.movements / convoy.planned_routes (legacy movements) and corridor.agency_stations
        self.movements: dict[str, dict] = {}
        self.planned_routes: list[dict] = []
        self.stations: list[dict] = []
        #: osint.event_sources.role accepts 'context' (migration 023)
        self.context_role = True
        #: a slice of the Mumbai network (the city this deployment serves), ids and junction ends as in
        #: scripts/data/osm_network.json: the Western Express Highway from the Bandra merge (34) by
        #: Kalanagar (37), Vakola (39) and the Sahar Elevated Road (48) to Andheri (50) — segments 1013,
        #: 1014, 1015 and 1016 — LBS Marg over Ghatkopar (1038), Hindmata (19) and Dadar TT Circle (20);
        #: and a slice of the Kolkata network (the second pack, its ids as that pack's network numbered
        #: them, replayed by the mechanics suites): EM Bypass from Ruby crossing to Science City (1035)
        #: and on to Chingrighata (1036), the Rash Behari Avenue connector (1034) and Rash Behari Avenue
        #: (1032, 1033) to Gariahat, Maa Flyover (1029), Syed Amir Ali Avenue (1030), Hazra Road (1031)
        #: and Diamond Harbour Road over Taratala (1049). The two packs number their networks
        #: independently: their segment slices here are disjoint (a junction id both packs use is simply known).
        self.segments: set[int] = {1013, 1014, 1015, 1016, 1038,
                                   1029, 1030, 1031, 1032, 1033, 1034, 1035, 1036, 1049}
        self.junctions: set[int] = {19, 34, 37, 39, 48, 50,
                                    17, 18, 20, 22, 23, 24, 26, 27, 29, 30, 31}
        #: (from_segment, to_segment, via_junction): corridor.segment_adjacency — and, edge by edge,
        #: corridor.road_graph (a segment-to-segment graph over that slice)
        self.adjacency: list[tuple[int, int, int]] = [
            (1013, 1014, 37), (1014, 1013, 37),  # Kalanagar junction (Western Express Highway)
            (1014, 1015, 39), (1015, 1014, 39),  # Vakola (Western Express Highway)
            (1015, 1016, 48), (1016, 1015, 48),  # Western Express Highway (Sahar Elevated Road)
            (1029, 1030, 17), (1030, 1029, 17),  # Park Circus seven-point crossing
            (1034, 1035, 29), (1035, 1034, 29),  # Ruby crossing
            (1035, 1036, 30), (1036, 1035, 30),  # Science City
            (1033, 1034, 23), (1034, 1033, 23),  # Gariahat crossing
        ]
        self.dss: dict[str, dict] = {}
        self.coa: dict[tuple[str, str], dict] = {}
        self.dss_log: list[dict] = []
        self._seq = itertools.count(1)

    # -- snapshots for transaction rollback -------------------------------
    _TABLES = ("signals", "events", "sources", "geocodes", "gazetteer", "corridor", "routes",
               "status_log", "phases", "dispatches", "movements", "planned_routes", "stations",
               "dss", "coa", "dss_log")

    def snapshot(self) -> dict:
        return {name: copy.deepcopy(getattr(self, name)) for name in self._TABLES}

    def restore(self, snap: dict) -> None:
        for name, value in snap.items():
            setattr(self, name, value)

    # -- views ------------------------------------------------------------
    def members(self, oid: str) -> list[tuple[str, str]]:
        return sorted(((sid, role) for (o, sid), role in self.sources.items() if o == oid),
                      key=lambda x: (x[1] != "primary", x[0]))

    def view(self, oid: str) -> dict:
        """One resolved_events row + the C-Q provenance columns (context members apart)."""
        row = dict(self.events[oid])
        members = self.members(oid)
        reporting = [(sid, role) for sid, role in members if role != "context"]
        sigs = [self.signals[sid] for sid, _ in reporting if sid in self.signals]
        ctx = [self.signals[sid] for sid, role in members if role == "context" and sid in self.signals]
        row["source_feeds"] = sorted({s["source"] for s in sigs}) or None
        row["publishers"] = sorted({s["publisher"] for s in sigs if s["publisher"]}) or None
        row["links_withheld"] = sum(1 for s in sigs if s["url"] is None and s["source_tier"] != "official")
        geos = [g for g in self.geocodes if g["signal_id"] in {sid for sid, _ in reporting}]
        primary = {sid for sid, role in members if role == "primary"}
        geos.sort(key=lambda g: (g["signal_id"] not in primary, -(g["confidence"] or 0), g["signal_id"]))
        row["geocoder"] = geos[0]["method"] if geos else None
        row["context_publishers"] = sorted({s["publisher"] for s in ctx if s["publisher"]}) or None
        row["context_official"] = any(s["source_tier"] == "official" for s in ctx)
        # FIX-E item 10: the context-member count like the real reads select it
        # (common.OSINT_CONTEXT_MEMBERS_SQL) — the dossier's own column
        row["context_members"] = len(ctx)
        return row

    @staticmethod
    def surfaced(r: Mapping[str, Any]) -> bool:
        tiers = set(r["source_tiers"] or [])
        return bool(
            r["is_event"] and r["superseded_by"] is None and r["rep_lon"] is not None
            and r["rep_lat"] is not None and r["sajag_event_kind"] is not None
            and r["event_class"] != "general_news"
            and not (tiers <= {"social_unverified"} and r["source_count"] < 2)
        )

    def toponyms_of(self, oid: str) -> set[str]:
        sids = {sid for sid, _ in self.members(oid)}
        return {g["toponym"].lower() for g in self.geocodes if g["signal_id"] in sids and g["toponym"]}


class FakeOsintConn:
    """An asyncpg-like connection over :class:`FakeOsintDB`."""

    def __init__(self, db: FakeOsintDB) -> None:
        self.db = db
        self.calls: list[str] = []
        self.handlers = self._handlers()
        self.prefix_handlers = self._prefix_handlers()
        self._depth = 0

    # -- driver -----------------------------------------------------------
    def _handler(self, sql: str) -> Any:
        h = self.handlers.get(sql)
        if h is not None:
            return h
        for prefix, fn in self.prefix_handlers:
            if sql.startswith(prefix):
                return fn
        raise AssertionError("unexpected SQL: " + sql[:120])

    async def fetch(self, sql: str, *args: Any) -> list:
        self.calls.append(sql)
        return list(self._handler(sql)(*args) or [])

    async def fetchrow(self, sql: str, *args: Any) -> Any:
        rows = await self.fetch(sql, *args)
        return rows[0] if rows else None

    async def fetchval(self, sql: str, *args: Any) -> Any:
        self.calls.append(sql)
        if sql == common._SQL_REGCLASS:
            return args[0] in self.db.relations
        if sql == common._SQL_COLUMN:
            return (args[0], args[1]) in self.db.columns
        if sql == getattr(store, "_SQL_CONTEXT_ROLE", None):
            return self.db.context_role
        raise AssertionError("unexpected fetchval: " + sql[:120])

    async def execute(self, sql: str, *args: Any) -> str:
        self.calls.append(sql)
        self._handler(sql)(*args)
        return "OK"

    async def executemany(self, sql: str, rows: Iterable[tuple]) -> None:
        for r in rows:
            await self.execute(sql, *r)

    def transaction(self) -> FakeOsintConn._Tx:
        return FakeOsintConn._Tx(self)

    class _Tx:
        def __init__(self, conn: FakeOsintConn) -> None:
            self.conn = conn
            self.snap: dict | None = None

        async def __aenter__(self) -> FakeOsintConn._Tx:
            if self.conn._depth == 0:
                self.snap = self.conn.db.snapshot()
            self.conn._depth += 1
            return self

        async def __aexit__(self, exc_type: Any, *exc: Any) -> bool:
            self.conn._depth -= 1
            if exc_type is not None and self.snap is not None:
                self.conn.db.restore(self.snap)
            return False

    # -- handlers ---------------------------------------------------------
    def _handlers(self) -> dict[str, Any]:
        db = self.db
        h: dict[str, Any] = {}
        h[store._SQL_INGEST_LOCK] = lambda: None
        h[store._SQL_INSERT_SIGNAL] = self._insert_signal
        h[store._SQL_WINDOW_SEEDS] = self._window_seeds
        h[store._SQL_WINDOW_SITUATIONS] = self._window_situations
        h[store._SQL_WINDOW_ROWS] = self._window_rows
        h[store._SQL_MEMBERSHIP] = self._membership
        h[store._SQL_CLEAR_SELF_ATTACH] = self._clear_self_attach
        h[store._SQL_KNOWN_SEGMENTS] = lambda ids: [(i,) for i in ids if i in db.segments]
        h[store._SQL_KNOWN_JUNCTIONS] = lambda ids: [(i,) for i in ids if i in db.junctions]
        h[store._SQL_UPSERT_EVENT] = self._upsert_event
        h[store._SQL_DELETE_SOURCES] = lambda ids: [
            db.sources.pop(k) for k in list(db.sources) if k[1] in _ids(ids)
        ]
        h[store._SQL_INSERT_SOURCES] = lambda oids, sids, roles: [
            db.sources.setdefault((str(o), str(s)), r) for o, s, r in zip(oids, sids, roles, strict=True)
        ]
        h[store._SQL_DELETE_GEOCODES] = lambda ids: setattr(
            db, "geocodes", [g for g in db.geocodes if g["signal_id"] not in _ids(ids)]
        )
        h[store._SQL_INSERT_GEOCODE] = self._insert_geocode
        h[store._SQL_SUPERSEDE] = self._supersede
        h[store._SQL_INHERIT_PROMOTION] = self._inherit
        h[store._SQL_WITHDRAW] = self._withdraw
        h[store._SQL_LIST_EVENTS] = self._list_events
        h[store._SQL_HELD_COUNTS] = self._held_counts
        h[store._SQL_EVENT_ROW] = lambda oid: [db.view(str(oid))] if str(oid) in db.events else []
        h[store._SQL_EVENT_ROW_FOR_UPDATE] = lambda oid: (
            [dict(db.events[str(oid)])] if str(oid) in db.events else []
        )
        h[store._SQL_EVENT_SOURCES] = self._event_sources
        h[store._SQL_EVENT_GEOCODES] = self._event_geocodes
        h[store._SQL_PRIMARY_SOURCE] = lambda oid: self._event_sources(oid)[:1]
        h[store._SQL_JUNCTION_SEGMENT] = lambda jid: [
            {"segment_id": f} for f in sorted({a for a, _, v in db.adjacency if v == jid})
        ][:1]
        h[store._SQL_ORPHAN_PROMOTION] = lambda oid: [
            {"event_id": e["event_id"], "status": e["status"]}
            for e in sorted(db.corridor.values(), key=lambda e: e["created_at"])
            if e["source_kind"] == "osint"
            and (_js(e["metadata"]) or {}).get("osint_event_id") == str(oid)
            and e["status"] in ("planning", "approved", "active")
        ][:1]
        h[store._SQL_SET_PROMOTED] = self._set_promoted
        h[store._SQL_GAZETTEER_UPSERT] = self._gazetteer_upsert
        # live state (read-only)
        for sql in (live_state._SQL_LIVE_EVENTS, live_state._SQL_LIVE_EVENTS_GEOTAG):
            h[sql] = self._live_events_for(sql)
        h[ent._SQL_EVENT_SPINES] = self._spines
        h[ent._SQL_EVENT_SPINES_CURRENT] = self._spines
        h[ent._SQL_EVENT_SPINE_HISTORY] = lambda ids: []
        h[live_state._SQL_AMBULANCE_DISPATCHES] = self._ambulance_dispatches_for(live_state._SQL_AMBULANCE_DISPATCHES)
        h[live_state._SQL_CLOSING_EVENTS] = self._closing_events_for(live_state._SQL_CLOSING_EVENTS)
        # (getattr: the fixture also loads against an older live_state, for before/after runs)
        h[getattr(live_state, "_SQL_EVENT_STATUS", "-")] = lambda ids: [
            {"event_id": e["event_id"], "status": e["status"], "event_kind": e["event_kind"],
             "movement_id": e.get("movement_id")}
            for e in db.corridor.values() if str(e["event_id"]) in _ids(ids)
        ]
        h[getattr(live_state, "_SQL_ACTIVE_MOVEMENTS", "-")] = lambda limit: [
            {"movement_id": m["movement_id"], "status": m["status"]}
            for m in sorted(db.movements.values(), key=lambda m: str(m["movement_id"]))
            if m["status"] == "active"
        ][:limit]
        h[getattr(live_state, "_SQL_MOVEMENT_STATUS", "-")] = lambda ids: [
            {"movement_id": m["movement_id"], "status": m["status"]}
            for m in db.movements.values() if str(m["movement_id"]) in _ids(ids)
        ]
        h[engine_loop._MOVEMENT_ROUTES_SQL] = lambda ids: [
            {"movement_id": r["movement_id"], "route_rank": r["route_rank"], "segment_ids": list(r["segment_ids"])}
            for r in sorted(db.planned_routes, key=lambda r: (str(r["movement_id"]), r["route_rank"]))
            if str(r["movement_id"]) in _ids(ids)
        ]
        h[units_router._SQL_JUNCTION_ADJACENT_SEGMENT] = lambda jid: [
            {"segment_id": f} for f in sorted({a for a, _, v in db.adjacency if v == jid})
        ]
        h[units_router._SQL_SHORTEST_PATH] = self._shortest_path
        h[units_router._SQL_NEAREST_STATION] = lambda agency, jid: [
            dict(st) for st in db.stations if st["agency"] == agency
        ][:1]
        h.update(city_osint_handlers(db))
        # the feed sources a scoped OSINT audit can reach
        h[feed_mod._SQL_FEED_EVENT_LOG] = self._feed_event_log
        for sql in (feed_mod._SQL_FEED_EVENT_CREATED, feed_mod._SQL_FEED_DISPATCH,
                    feed_mod._SQL_FEED_ENFORCEMENT, feed_mod._SQL_FEED_ANPR,
                    feed_mod._SQL_FEED_SITUATIONS, feed_mod._SQL_FEED_OVERRIDES,
                    common._SQL_SUBJECT_EVENTS):
            h[sql] = lambda *a: []
        # a cancelled / completed event walks its open dispatches shut (none here)
        h[units_router._SQL_OPEN_EVENT_DISPATCHES] = lambda eid, statuses: [
            d for d in db.dispatches if str(d.get("event_id")) == str(eid) and d["status"] in statuses
        ]
        h[events_mod._SQL_EVENT_FOR_UPDATE] = lambda eid: [
            {k: db.corridor[str(eid)][k] for k in ("event_id", "status", "event_kind", "title")}
        ] if str(eid) in db.corridor else []
        # the city dossier of a situation: the corridor events it relates to, its road
        h[dos._SQL_DOSSIER_EVENTS] = self._dossier_events
        h[dos._SQL_DOSSIER_EVENTS_PROVENANCE] = self._dossier_events
        h[ent._SQL_SUBJECT_BANDS] = lambda keys: []
        h[dos._SQL_DOSSIER_SEGMENTS] = lambda sids: [
            {"segment_id": s, "road_name": f"Test road {s}", "road_class": "primary", "lanes": 2,
             "speed_limit_kmh": 50, "oneway": False, "lon": 88.3957601, "lat": 22.5255148, "length_m": 500.0}
            for s in sorted({int(x) for x in sids}) if s in db.segments
        ]
        return h

    _DOSSIER_EVENT_KEYS = ("event_id", "event_kind", "title", "status", "metadata", "created_at",
                           "updated_at", "actual_start", "actual_end", "source_kind", "credibility",
                           "verification_state")

    def _dossier_events(self, ids: list[Any]) -> list:
        rows = [self.db.corridor[str(i)] for i in _ids(ids) if str(i) in self.db.corridor]
        rows.sort(key=lambda e: e["created_at"], reverse=True)
        return [
            {**{k: e.get(k) for k in self._DOSSIER_EVENT_KEYS}, "protection_class": None, "crowd_class": None,
             "movement_id": None, "planned_start": None, "planned_end": None, "zone_lon": None, "zone_lat": None}
            for e in rows
        ]

    def _prefix_handlers(self) -> list[tuple[str, Any]]:
        return [
            ("INSERT INTO events.corridor_events (", self._create_event),
            ("INSERT INTO events.event_routes (event_id, route_rank, label, segment_ids) VALUES", self._add_route),
            ("INSERT INTO events.event_phases (", lambda *a: None),
            ("INSERT INTO events.event_status_log (event_id, from_status, to_status, actor, note) VALUES ($1, NULL, 'planning'",
             self._creation_log),
            ("UPDATE events.corridor_events SET status = $2", self._status_update),
            ("INSERT INTO events.event_status_log (event_id, from_status, to_status, actor, note) VALUES ($1, $2, $3, $4, $5)",
             self._log_insert),
        ]

    # -- signals ----------------------------------------------------------
    _SIGNAL_KEYS = ("signal_id", "source", "source_id", "source_tier", "publisher", "url", "title",
                    "body", "language", "published_at", "fetched_at", "valid_until", "fetch_mode",
                    "pii_redactions", "raw_geo_hint", "category_hint", "tone", "provenance_label",
                    "credibility_prior", "license", "redistributable", "raw", "run_id")

    def _insert_signal(self, *params: Any) -> list:
        row = dict(zip(self._SIGNAL_KEYS, params, strict=True))
        if row["signal_id"] in self.db.signals:
            return []
        row["_stored_at"] = _now()
        self.db.signals[row["signal_id"]] = row
        return [{"signal_id": row["signal_id"]}]

    def _window_seeds(self, batch: list[str], hours: int, published_hours: int, limit: int) -> list:
        db, now = self.db, _now()
        pubs = [db.signals[s]["published_at"] for s in batch if s in db.signals and db.signals[s]["published_at"]]
        lo = min(pubs) - timedelta(hours=published_hours) if pubs else None
        hi = max(pubs) + timedelta(hours=published_hours) if pubs else None
        rows = [
            s for sid, s in db.signals.items()
            if sid in batch or s["fetched_at"] > now - timedelta(hours=hours)
            or (lo is not None and s["published_at"] is not None and lo <= s["published_at"] <= hi)
        ]
        rows.sort(key=lambda s: (s["signal_id"] not in batch, -s["fetched_at"].timestamp(), s["signal_id"]))
        return [{"signal_id": s["signal_id"], "in_batch": s["signal_id"] in batch} for s in rows[:limit]]

    def _window_situations(self, ids: list[str]) -> list:
        """Every current situation reachable from ``ids`` (transitively, through shared members)."""
        db = self.db
        live = {o for o, r in db.events.items() if r["superseded_by"] is None}
        sits = {o for (o, s) in db.sources if s in _ids(ids) and o in live}
        while True:
            members = {s for (o, s) in db.sources if o in sits}
            more = {o for (o, s) in db.sources if s in members and o in live} - sits
            if not more:
                break
            sits |= more
        pairs = sorted((o, s) for (o, s) in db.sources if o in sits)
        return [{"osint_event_id": uuid.UUID(o), "signal_id": s} for o, s in pairs]

    def _window_rows(self, ids: list[str], batch: list[str]) -> list:
        rows = [self.db.signals[s] for s in _ids(ids) if s in self.db.signals]
        rows.sort(key=lambda s: (s["signal_id"] not in batch, -s["fetched_at"].timestamp(), s["signal_id"]))
        return [dict(r) for r in rows]

    def _membership(self, ids: list[str]) -> list:
        """store._SQL_MEMBERSHIP: current situations of these signals, roles and area flags."""
        db, out = self.db, []
        for (o, s), role in db.sources.items():
            if s not in _ids(ids) or db.events[o]["superseded_by"] is not None:
                continue
            geo_area = any(g["area_level"] for g in db.geocodes if g["signal_id"] == s)
            out.append({"osint_event_id": uuid.UUID(o), "signal_id": s, "role": role,
                        "situation_area": bool(db.events[o]["area_level"]),
                        "member_area": role == "context" or geo_area})
        return out

    @staticmethod
    def _statuses_in(sql: str, column: str) -> set[str]:
        """The literal statuses of ``<column> IN (...)`` in ``sql`` (the fake applies the statement's
        own filter, whatever version of it the module under test carries)."""
        m = re.search(re.escape(column) + r" IN \(([^)]*)\)", sql)
        return set(re.findall(r"'([a-z_]+)'", m.group(1))) if m else set()

    def _ambulance_dispatches_for(self, sql: str) -> Any:
        statuses = self._statuses_in(sql, "d.status")

        def run(limit: int) -> list:
            out = []
            for d in self.db.dispatches:
                e = self.db.corridor.get(str(d.get("event_id")))
                if (d["agency"] == "ambulance" and d["status"] in statuses
                        and e is not None and e["status"] in ("planning", "approved", "active")):
                    out.append({"dispatch_id": d["dispatch_id"], "event_id": d["event_id"],
                                "waypoint_junction": d.get("waypoint_junction"),
                                "request_payload": d.get("request_payload"), "event_kind": e["event_kind"]})
            return out[:limit]

        return run

    def _shortest_path(self, source: int, target: int) -> list:
        """pgr_dijkstra over the adjacency (unit cost per hop): rows ``{seq, node, edge, cost, agg_cost}``."""
        frontier, prev = [int(source)], {int(source): None}
        while frontier and int(target) not in prev:
            nxt = []
            for node in frontier:
                for a, b, _ in sorted(self.db.adjacency):
                    if a == node and b not in prev:
                        prev[b] = node
                        nxt.append(b)
            frontier = nxt
        if int(target) not in prev or int(source) == int(target):
            return []
        path, node = [], int(target)
        while node is not None:
            path.append(node)
            node = prev[node]
        path.reverse()
        return [{"seq": i + 1, "node": n, "edge": -1 if i == len(path) - 1 else i, "cost": 1.0,
                 "agg_cost": float(i)} for i, n in enumerate(path)]

    def _clear_self_attach(self, ids: list[Any]) -> list:
        """The lineage rule of store._SQL_CLEAR_SELF_ATTACH over the in-memory tables."""
        db, out = self.db, []
        for oid in sorted(_ids(ids)):
            r = db.events.get(oid)
            live = (r or {}).get("corroborates_live_urn") or ""
            if not live.startswith("event:"):
                continue
            lineage, frontier = {oid}, {oid}
            while frontier:
                frontier = {o for o, x in db.events.items()
                            if x["superseded_by"] is not None and str(x["superseded_by"]) in frontier} - lineage
                lineage |= frontier
            own = {str(db.events[o]["promoted_event_id"]) for o in lineage
                   if db.events[o]["promoted_event_id"] is not None}
            own |= {str(e["event_id"]) for e in db.corridor.values() if e["source_kind"] == "osint"
                    and (_js(e["metadata"]) or {}).get("osint_event_id") in lineage}
            if live in {f"event:{e}" for e in own}:
                r.update(attach_novel=True, corroborates_live_urn=None, updated_at=_now())
                out.append({"osint_event_id": uuid.UUID(oid)})
        return out

    # -- situations -------------------------------------------------------
    _EVENT_KEYS = ("fused_event_id", "event_class", "subtype", "sajag_event_kind", "sajag_incident_kind",
                   "label", "summary", "toponym", "rep_lon", "rep_lat", "segment_id", "junction_id",
                   "window_start", "window_end", "credibility", "verification_state",
                   "geocode_confidence", "area_level", "source_count", "source_tiers",
                   "independent_publishers", "cross_type_corroborated", "correlated_classes",
                   "is_event", "held_reason", "attach_novel", "corroborates_live_urn",
                   "second_order", "labels")

    def _upsert_event(self, *params: Any) -> list:
        values = dict(zip(self._EVENT_KEYS, params, strict=True))
        values["second_order"] = _js(values["second_order"])
        existing = next((r for r in self.db.events.values() if r["fused_event_id"] == values["fused_event_id"]), None)
        now = _now()
        if existing is not None:
            existing.update(values, superseded_by=None, updated_at=now)
            return [{"osint_event_id": uuid.UUID(existing["osint_event_id"]), "inserted": False}]
        oid = str(uuid.uuid4())
        self.db.events[oid] = dict(values, osint_event_id=oid, promoted_event_id=None,
                                   superseded_by=None, created_at=now, updated_at=now)
        return [{"osint_event_id": uuid.UUID(oid), "inserted": True}]

    _GEO_KEYS = ("signal_id", "toponym", "feature_type", "lon", "lat", "segment_id", "junction_id",
                 "snapped_to", "confidence", "bucket", "method", "residual_m", "area_level",
                 "area_scope", "alternatives")

    def _insert_geocode(self, *params: Any) -> None:
        row = dict(zip(self._GEO_KEYS, params, strict=True))
        row["alternatives"] = _js(row["alternatives"])
        self.db.geocodes.append(row)

    def _supersede(self, old: str, new: str) -> None:
        r = self.db.events[str(old)]
        if r["superseded_by"] is None:
            r["superseded_by"] = uuid.UUID(str(new))

    def _inherit(self, absorber: Any, absorbed: Any) -> list:
        """The absorber takes the absorbed row's promotion AS IT STANDS (never twice)."""
        a, o = self.db.events[str(absorber)], self.db.events[str(absorbed)]
        if (o["promoted_event_id"] is None or str(o["superseded_by"]) != str(absorber)
                or a["promoted_event_id"] is not None):
            return []
        a.update(promoted_event_id=o["promoted_event_id"], updated_at=_now())
        return [{"osint_event_id": uuid.UUID(str(absorber))}]

    def _withdraw(self, ids: list[str], reason: str) -> None:
        for oid in ids:
            r = self.db.events[str(oid)]
            if r["superseded_by"] is None:
                r.update(is_event=False, held_reason=reason)

    def _list_events(self, lon0, lat0, lon1, lat1, cls, min_cred, state, since, limit) -> list:
        out = []
        for oid, r in self.db.events.items():
            if not self.db.surfaced(r):
                continue
            if lon0 is not None and not (lon0 <= r["rep_lon"] <= lon1 and lat0 <= r["rep_lat"] <= lat1):
                continue
            if cls is not None and cls != r["event_class"] and cls not in (r["correlated_classes"] or []):
                continue
            if min_cred is not None and round(r["credibility"], 4) < round(min_cred, 4):
                continue
            if state is not None and r["verification_state"] != state:
                continue
            touched = max(r["window_end"] or r["created_at"], r["updated_at"])
            if since is not None and touched < since:
                continue
            out.append(self.db.view(oid))
        out.sort(key=lambda r: (-r["credibility"], -(r["window_end"] or r["created_at"]).timestamp(), r["osint_event_id"]))
        return out[:limit]

    def _held_counts(self, since) -> list:
        counts: dict[Any, int] = {}
        for r in self.db.events.values():
            if r["is_event"] or r["superseded_by"] is not None:
                continue
            touched = max(r["window_end"] or r["created_at"], r["updated_at"])
            if since is not None and touched < since:
                continue
            counts[r["held_reason"]] = counts.get(r["held_reason"], 0) + 1
        return [{"held_reason": k, "n": v} for k, v in counts.items()]

    def _event_sources(self, oid: Any) -> list:
        out = []
        for sid, role in self.db.members(str(oid)):
            s = self.db.signals.get(sid)
            if s is not None:
                out.append(dict(s, role=role))
        return out

    def _event_geocodes(self, oid: Any) -> list:
        members = self.db.members(str(oid))
        primary = {sid for sid, role in members if role == "primary"}
        geos = [dict(g) for g in self.db.geocodes if g["signal_id"] in {sid for sid, _ in members}]
        geos.sort(key=lambda g: (g["signal_id"] not in primary, -(g["confidence"] or 0), g["signal_id"]))
        return geos

    def _set_promoted(self, oid: str, event_id: str) -> list:
        r = self.db.events.get(str(oid))
        if r is None or r["promoted_event_id"] is not None:
            return []
        r["promoted_event_id"] = uuid.UUID(str(event_id))
        return [{"osint_event_id": uuid.UUID(str(oid))}]

    def _gazetteer_upsert(self, gaz_id, name, ftype, forms, norm, lang, lon, lat, seg, junc, imp, source, prior) -> None:
        self.db.gazetteer[int(gaz_id)] = {
            "gaz_id": int(gaz_id), "canonical_name": name, "feature_type": ftype, "surface_forms": list(forms),
            "name_norm": norm, "lang_primary": lang, "lon": lon, "lat": lat, "segment_id": seg,
            "junction_id": junc, "importance": imp, "source": source, "confidence_prior": prior,
        }

    # -- corridor events (the slice a promotion writes) --------------------
    def _live_events_for(self, sql: str) -> Any:
        active_first = "CASE e.status WHEN 'active'" in sql

        def run(limit: int) -> list:
            rank = {"active": 0, "approved": 1, "planning": 2}
            rows = [e for e in self.db.corridor.values() if e["status"] in rank]
            if active_first:  # active, approved, planning; newest first within a status
                rows.sort(key=lambda e: (rank[e["status"]], -e["created_at"].timestamp(), str(e["event_id"])))
            else:  # the statement's own order: oldest first
                rows.sort(key=lambda e: (e["created_at"], str(e["event_id"])))
            return [
                {"event_id": e["event_id"], "event_kind": e["event_kind"], "status": e["status"],
                 "movement_id": e.get("movement_id"), "zone_lon": None, "zone_lat": None,
                 "geotag_lon": e.get("geotag_lon"), "geotag_lat": e.get("geotag_lat")}
                for e in rows[:limit]
            ]

        return run

    def _spines(self, ids: list) -> list:
        wanted = _ids(ids)
        out = []
        for r in sorted(self.db.routes, key=lambda r: (str(r["event_id"]), r["route_rank"])):
            if str(r["event_id"]) in wanted and r.get("superseded_at") is None:
                out.append({**r, "lon": 88.3957601, "lat": 22.5255148, "variant": r.get("variant")})
        return out

    def _closing_events_for(self, sql: str) -> Any:
        statuses = self._statuses_in(sql, "e.status") or {"active"}
        literal_types = self._statuses_in(sql, "'closure_type'")

        def run(closure_types: Iterable[str] | None = None) -> list:
            types = set(closure_types) if closure_types is not None else literal_types
            now = _now()
            out = []
            for p in self.db.phases:
                e = self.db.corridor.get(str(p["event_id"]))
                if (e and e["status"] in statuses and p["window_start"] <= now <= p["window_end"]
                        and (_js(p.get("closure_policy")) or {}).get("closure_type") in types
                        and {"event_id": p["event_id"]} not in out):
                    out.append({"event_id": p["event_id"]})
            return out

        return run

    def _create_event(self, kind, protection, crowd, title, description, movement_id, planned_start,
                      planned_end, zone, metadata, source_kind, credibility, verification_state,
                      provenance, lon, lat) -> list:
        eid = uuid.uuid4()
        now = _now()
        self.db.corridor[str(eid)] = {
            "event_id": eid, "event_kind": kind, "protection_class": protection, "crowd_class": crowd,
            "title": title, "description": description, "status": "planning", "metadata": metadata,
            "source_kind": source_kind, "credibility": credibility,
            "verification_state": verification_state, "provenance": provenance,
            "geotag_lon": lon, "geotag_lat": lat, "created_at": now, "updated_at": now,
            "actual_start": None, "actual_end": None,
        }
        return [{"event_id": eid, "created_at": now}]

    def _add_route(self, eid, rank, label, segment_ids) -> None:
        self.db.routes.append({"event_id": eid, "route_rank": rank, "label": label,
                               "segment_ids": list(segment_ids), "superseded_at": None})

    def _creation_log(self, eid, actor, note) -> None:
        self.db.status_log.append({"seq": next(self.db._seq), "event_id": eid, "from_status": None,
                                   "to_status": "planning", "actor": actor, "note": note, "at": _now()})

    def _status_update(self, eid, to_status, from_status) -> list:
        e = self.db.corridor.get(str(eid))
        if e is None or e["status"] != from_status:
            return []
        e["status"] = to_status
        if to_status == "active" and e["actual_start"] is None:
            e["actual_start"] = _now()
        if to_status in ("completed", "cancelled"):
            e["actual_end"] = _now()
        e["updated_at"] = _now()
        return [{"actual_start": e["actual_start"], "actual_end": e["actual_end"]}]

    def _log_insert(self, eid, from_status, to_status, actor, note) -> list:
        row = {"seq": next(self.db._seq), "event_id": eid, "from_status": from_status,
               "to_status": to_status, "actor": actor, "note": note, "at": _now()}
        self.db.status_log.append(row)
        return [{"seq": row["seq"], "at": row["at"]}]

    def _feed_event_log(self, since, limit, unscoped, event_ids) -> list:
        wanted = _ids(event_ids)
        out = []
        for row in self.db.status_log:
            e = self.db.corridor.get(str(row["event_id"]))
            if e is None or row["at"] <= since or not (unscoped or str(row["event_id"]) in wanted):
                continue
            out.append({**row, "event_kind": e["event_kind"], "title": e["title"], "metadata": e["metadata"]})
        out.sort(key=lambda r: (r["at"], r["seq"]), reverse=True)
        return out[:limit]


class FakeValkey:
    """The slice of a Valkey client the OSINT live state reads: ``scan_iter`` and ``mget`` over an
    in-memory dict (C-B convoy frames), never a server."""

    def __init__(self, docs: Mapping[str, Any] | None = None) -> None:
        self.docs: dict[str, str] = {
            k: (v if isinstance(v, str) else json.dumps(v)) for k, v in (docs or {}).items()
        }

    async def scan_iter(self, match: str = "*", count: int = 100) -> Any:
        prefix = match.rstrip("*")
        for key in sorted(self.docs):
            if key.startswith(prefix):
                yield key

    async def mget(self, keys: list[str]) -> list[Any]:
        return [self.docs.get(k) for k in keys]


class FakePool:
    """``acquire()`` always yields the one fake connection."""

    def __init__(self, conn: Any) -> None:
        self.conn = conn

    class _Acq:
        def __init__(self, conn: Any) -> None:
            self.conn = conn

        async def __aenter__(self) -> Any:
            return self.conn

        async def __aexit__(self, *exc: Any) -> bool:
            return False

    def acquire(self) -> FakePool._Acq:
        return FakePool._Acq(self.conn)


def city_osint_handlers(db: FakeOsintDB) -> dict[str, Any]:
    """The OSINT / decision-support READ statements of ``traffic_oracle.city`` over ``db`` — also
    installable on test_city_router's CityFakeConn (``conn.handlers.update(...)``)."""

    def recent(r: Mapping[str, Any], cutoff: datetime) -> bool:
        return (r["window_end"] is not None and r["window_end"] > cutoff) or r["created_at"] > cutoff

    def surfaced(cutoff: datetime, limit: int) -> list:
        rows = [db.view(o) for o, r in db.events.items() if db.surfaced(r) and recent(r, cutoff)]
        rows.sort(key=lambda r: (-r["credibility"], -(r["window_end"] or r["created_at"]).timestamp(),
                                 r["osint_event_id"]))
        return rows[:limit]

    def held_social(cutoff: datetime) -> list:
        n = sum(
            1 for r in db.events.values()
            if not r["is_event"] and r["superseded_by"] is None and r["source_tiers"]
            and set(r["source_tiers"]) <= {"social_unverified"}
            and not str(r["held_reason"] or "").startswith("withdrawn") and recent(r, cutoff)
        )
        return [{"n": n}]

    def event_sources(oid: Any) -> list:
        # FIX-E R2: the city dossier now reads the per-signal sources through the
        # store's own statement (osint.store._SQL_EVENT_SOURCES) — answer it like
        # FakeOsintConn does, from the same tables
        out = []
        for sid, role in db.members(str(oid)):
            sig = db.signals.get(sid)
            if sig is not None:
                out.append(dict(sig, role=role))
        return out

    def member_toponyms(ids: list) -> list:
        return [{"osint_event_id": o, "toponym": t} for o in _ids(ids) if o in db.events
                for t in sorted({g["toponym"] for g in db.geocodes
                                 if g["toponym"] and g["signal_id"] in {s for s, _ in db.members(o)}})]

    def places_by_name(names: list) -> list:
        wanted = {n.lower() for n in names}
        return [dict(g) for _, g in sorted(db.gazetteer.items()) if g["canonical_name"].lower() in wanted]

    def dss_latest(urns: list) -> list:
        out = []
        for u in urns:
            rows = sorted((d for d in db.dss.values() if d["event_urn"] == u),
                          key=lambda d: (d["generated_at"], d["dss_id"]), reverse=True)
            if rows:
                d = rows[0]
                top = (_js(d["recommendation"]) or {}).get("top_coa_id")
                coa = db.coa.get((d["dss_id"], top))
                out.append({"event_urn": u, "dss_id": d["dss_id"], "state": d["state"],
                            "generated_at": d["generated_at"], "horizon_min": d["horizon_min"],
                            "top_coa_id": top, "top_coa_label": coa["label"] if coa else None})
        return out

    def dossier_event(oid: Any) -> list:
        r = db.events.get(str(oid))
        return [db.view(str(oid))] if r is not None and db.surfaced(r) else []

    def place_events(name: str, limit: int) -> list:
        rows = [db.view(o) for o, r in db.events.items()
                if db.surfaced(r) and ((r["toponym"] or "").lower() == name or name in db.toponyms_of(o))]
        rows.sort(key=lambda r: (-r["credibility"], r["osint_event_id"]))
        return rows[:limit]

    def feed_surfaced(since, limit, unscoped, oids, eids) -> list:
        o_ids, e_ids = _ids(oids), _ids(eids)
        rows = [db.view(o) for o, r in db.events.items() if db.surfaced(r) and r["created_at"] > since
                and (unscoped or o in o_ids or str(r["promoted_event_id"]) in e_ids)]
        rows.sort(key=lambda r: (r["created_at"], r["osint_event_id"]), reverse=True)
        return rows[:limit]

    def feed_promoted(since, limit, unscoped, oids, eids) -> list:
        o_ids, e_ids = _ids(oids), _ids(eids)
        out: dict[str, dict] = {}
        for o, r in sorted(db.events.items(), key=lambda kv: (kv[1]["superseded_by"] is not None, kv[0])):
            p = r["promoted_event_id"]
            if p is None or str(p) in out or not (unscoped or o in o_ids or str(p) in e_ids):
                continue
            log = next((x for x in db.status_log if str(x["event_id"]) == str(p) and x["from_status"] is None), None)
            e = db.corridor.get(str(p))
            if log is None or e is None or log["at"] <= since:
                continue
            out[str(p)] = {"osint_event_id": o, "label": r["label"], "verification_state": r["verification_state"],
                           "credibility": r["credibility"], "promoted_event_id": p, "seq": log["seq"],
                           "actor": log["actor"], "at": log["at"], "event_kind": e["event_kind"]}
        return sorted(out.values(), key=lambda x: (x["at"], x["seq"]), reverse=True)[:limit]

    def feed_dss(since, limit, unscoped, subjects, eids) -> list:
        subj, e_ids = set(subjects or []), _ids(eids)
        out = []
        for row in db.dss_log:
            d = db.dss[row["dss_id"]]
            if row["at"] <= since or not (unscoped or d["event_urn"] in subj or str(row.get("promoted_event_id")) in e_ids):
                continue
            coa = db.coa.get((row["dss_id"], row.get("coa_id")))
            sit = None
            if d["event_urn"].startswith("osint_event:"):
                sit = db.events.get(d["event_urn"].split(":", 1)[1])
            out.append({**row, "event_urn": d["event_urn"], "coa_label": coa["label"] if coa else None,
                        "subject_label": sit["label"] if sit else None,
                        "verification_state": sit["verification_state"] if sit else None,
                        "credibility": sit["credibility"] if sit else None,
                        "event_metadata": None, "event_source_kind": None})
        out.sort(key=lambda x: (x["at"], x["log_id"]), reverse=True)
        return out[:limit]

    return {
        ent._SQL_OSINT_SURFACED: surfaced,
        ent._SQL_OSINT_HELD_SOCIAL: held_social,
        ent._SQL_OSINT_MEMBER_TOPONYMS: member_toponyms,
        ent._SQL_OSINT_PLACES_BY_NAME: places_by_name,
        ent._SQL_DSS_LATEST: dss_latest,
        dos._SQL_DOSSIER_OSINT_EVENT: dossier_event,
        store._SQL_EVENT_SOURCES: event_sources,
        # FIX-E R2: store.get_sources reads the situation's row first (its classes)
        store._SQL_EVENT_ROW: lambda oid: [db.view(str(oid))] if str(oid) in db.events else [],
        dos._SQL_DOSSIER_PLACE_EVENTS: place_events,
        dos._SQL_DOSSIER_PLACE: lambda gaz_id: [dict(db.gazetteer[gaz_id])] if gaz_id in db.gazetteer else [],
        dos._SQL_DOSSIER_PLACE_NAMES: lambda: [
            {"gaz_id": g["gaz_id"], "canonical_name": g["canonical_name"]} for _, g in sorted(db.gazetteer.items())
        ],
        feed_mod._SQL_FEED_OSINT_SURFACED: feed_surfaced,
        feed_mod._SQL_FEED_OSINT_PROMOTED: feed_promoted,
        feed_mod._SQL_FEED_DSS_DECISIONS: feed_dss,
    }
