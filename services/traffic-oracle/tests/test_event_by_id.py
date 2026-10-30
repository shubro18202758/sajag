"""GET /api/v1/events/{event_id} — one event row by id (FIX-AUDIT-C1).

The deck's public dispatch status (/driver, public-api.server.ts) applies
the OSINT firewall to the dispatch's OWN event row.  It used to look the
event up in GET /events?limit=200 (newest first), so an older event, or a
failed read, let the dispatch body out.  This route is the authoritative,
read-only lookup it now uses:

* 200: exactly a row of GET /events (same keys, same values), provenance
  included — ``source_kind``, ``verification_state``, ``credibility`` and
  ``metadata.source`` — for an operator row and a promoted OSINT row;
* 404 ``event {id} not found`` for an unknown id (the deck answers its
  driver "no such request" on exactly these words), 422 for a malformed id
  before the store is asked anything, 503 without a pool;
* no write: only SELECTs, never ``execute`` or a transaction;
* ``/active`` and the history list are untouched (``/active`` never reads
  as an id).

Fake pool through the REAL app (create_app), no database.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

pytest.importorskip("httpx")

from httpx import ASGITransport, AsyncClient  # noqa: E402

from traffic_oracle import events as events_mod  # noqa: E402
from traffic_oracle.__main__ import create_app  # noqa: E402
from traffic_oracle.city import common  # noqa: E402

T0 = datetime(2026, 10, 25, 9, 30, tzinfo=timezone.utc)
OPERATOR_ID = uuid.UUID("11111111-1111-4222-8333-444455556666")
OSINT_ID = uuid.UUID("33333333-1111-4222-8333-444455556666")


def _row(eid: uuid.UUID, **over: Any) -> dict:
    """An events.corridor_events row as the store returns it (JSONB as text)."""
    row = {
        "event_id": eid,
        "event_kind": "procession",
        "protection_class": "none",
        "crowd_class": "HIGH",
        "title": "Test procession",
        "description": "",
        "status": "active",
        "movement_id": None,
        "planned_start": T0 - timedelta(minutes=10),
        "planned_end": T0 + timedelta(hours=2),
        "actual_start": None,
        "actual_end": None,
        "metadata": json.dumps({}),
        "created_at": T0 - timedelta(days=3),
        "updated_at": T0 - timedelta(days=3),
        "source_kind": "operator",
        "credibility": None,
        "verification_state": None,
        "provenance": None,
        "geotag_lon": None,
        "geotag_lat": None,
        "zone_geojson": None,
    }
    row.update(over)
    return row


class ReadOnlyConn:
    """Answers the event SELECTs; any write (or an unknown statement) fails
    the test, and every statement is recorded."""

    def __init__(self, rows: dict[uuid.UUID, dict]) -> None:
        self.rows = rows
        self.calls: list[str] = []

    async def fetchval(self, sql: str, *args: Any):
        self.calls.append(sql)
        if sql in (common._SQL_REGCLASS, common._SQL_COLUMN):
            return False  # pre-018 store: every spine current, no history
        raise AssertionError("unexpected fetchval: " + sql[:80])

    async def fetchrow(self, sql: str, *args: Any):
        self.calls.append(sql)
        if sql == events_mod._SQL_EVENT_BY_ID:
            row = self.rows.get(args[0])
            return dict(row) if row else None
        raise AssertionError("unexpected fetchrow: " + sql[:80])

    async def fetch(self, sql: str, *args: Any):
        self.calls.append(sql)
        if sql == events_mod._SQL_EVENTS_HISTORY:
            return [dict(r) for r in sorted(
                self.rows.values(), key=lambda r: r["updated_at"], reverse=True
            )][: args[2]]
        if sql == events_mod._ACTIVE_EVENTS_SQL:
            return [dict(r) for r in self.rows.values()]
        if sql == events_mod._SQL_EVENT_ROUTES:
            return [
                {"event_id": eid, "label": "primary", "segment_ids": [1003, 1004]}
                for eid in args[0]
            ]
        if sql == events_mod._SQL_EVENT_PHASES:
            return []
        raise AssertionError("unexpected fetch: " + sql[:80])

    async def execute(self, sql: str, *args: Any):
        raise AssertionError("GET /events/{id} wrote: " + sql[:80])

    def transaction(self):
        raise AssertionError("GET /events/{id} opened a transaction")


class Pool:
    def __init__(self, rows: dict[uuid.UUID, dict]) -> None:
        self.conn = ReadOnlyConn(rows)

    class _Acq:
        def __init__(self, conn: ReadOnlyConn) -> None:
            self.conn = conn

        async def __aenter__(self):
            return self.conn

        async def __aexit__(self, *exc):
            return False

    def acquire(self):
        return Pool._Acq(self.conn)


def _rows() -> dict[uuid.UUID, dict]:
    return {
        OPERATOR_ID: _row(OPERATOR_ID),
        # A report a named officer promoted to a PUBLIC kind: the row the
        # deck's firewall must see whatever its age.
        OSINT_ID: _row(
            OSINT_ID,
            event_kind="mass_gathering",
            source_kind="osint",
            credibility=0.65,
            verification_state="NEWS-REPORTED",
            metadata=json.dumps({"source": "osint", "osint_event_id": "o-1"}),
            provenance=json.dumps({"feeds": ["gdelt"]}),
            updated_at=T0 - timedelta(days=30),
        ),
    }


def _app(pool: Pool | None):
    common.reset_relation_cache()
    app = create_app()
    app.state.pool = pool
    return app


def _get(app, path: str):
    async def run():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            return await c.get(path)

    return asyncio.run(run())


def test_one_event_is_a_row_of_the_history_list():
    pool = Pool(_rows())
    app = _app(pool)
    one = _get(app, f"/api/v1/events/{OPERATOR_ID}")
    assert one.status_code == 200, one.text
    body = one.json()
    listed = next(
        e for e in _get(app, "/api/v1/events?limit=500").json()["events"]
        if e["event_id"] == str(OPERATOR_ID)
    )
    assert body == listed
    assert body["routes"] == [{"label": "primary", "segment_ids": [1003, 1004]}]
    assert body["source_kind"] == "operator"


def test_an_osint_row_carries_its_provenance():
    body = _get(_app(Pool(_rows())), f"/api/v1/events/{OSINT_ID}").json()
    assert body["event_id"] == str(OSINT_ID)
    assert body["event_kind"] == "mass_gathering"
    assert body["source_kind"] == "osint"
    assert body["metadata"]["source"] == "osint"
    assert body["verification_state"] == "NEWS-REPORTED"
    assert body["credibility"] == 0.65
    assert body["provenance"] == {"feeds": ["gdelt"]}


def test_an_old_event_is_found_by_id_beyond_any_recent_window():
    # The audit's leak: the OSINT row is older than the newest N rows, so a
    # list read misses it; the by-id read never does.
    rows = _rows()
    for i in range(3):
        eid = uuid.uuid4()
        rows[eid] = _row(eid, updated_at=T0 - timedelta(minutes=i))
    app = _app(Pool(rows))
    newest = _get(app, "/api/v1/events?limit=3").json()["events"]
    assert str(OSINT_ID) not in {e["event_id"] for e in newest}
    one = _get(app, f"/api/v1/events/{OSINT_ID}")
    assert one.status_code == 200 and one.json()["source_kind"] == "osint"


def test_unknown_event_is_404_in_the_words_the_deck_matches():
    missing = uuid.uuid4()
    r = _get(_app(Pool(_rows())), f"/api/v1/events/{missing}")
    assert r.status_code == 404
    assert r.json() == {"detail": f"event {missing} not found"}


@pytest.mark.parametrize("bad", ["abc", "123", "33333333-3333-3333-3333-33333333333"])
def test_malformed_id_is_422_before_the_store_is_asked(bad):
    pool = Pool(_rows())
    r = _get(_app(pool), f"/api/v1/events/{bad}")
    assert r.status_code == 422
    assert pool.conn.calls == []


def test_no_pool_is_503():
    r = _get(_app(None), f"/api/v1/events/{OPERATOR_ID}")
    assert r.status_code == 503


def test_the_lookup_never_writes():
    pool = Pool(_rows())
    app = _app(pool)
    for eid in (OPERATOR_ID, OSINT_ID, uuid.uuid4()):
        assert _get(app, f"/api/v1/events/{eid}").status_code in (200, 404)
    assert pool.conn.calls, "the route asked the store nothing"
    for sql in pool.conn.calls:
        assert sql.lstrip().upper().startswith("SELECT"), sql[:80]
    assert events_mod._SQL_EVENT_BY_ID.upper().startswith("SELECT ")
    assert "FOR UPDATE" not in events_mod._SQL_EVENT_BY_ID.upper()


def test_active_and_history_routes_are_untouched():
    app = _app(Pool(_rows()))
    active = _get(app, "/api/v1/events/active")
    assert active.status_code == 200 and len(active.json()["events"]) == 2
    history = _get(app, "/api/v1/events")
    assert history.status_code == 200 and history.json()["count"] == 2


def test_the_route_is_registered_read_only_after_active():
    paths = [(r.path, frozenset(r.methods)) for r in events_mod.router.routes]
    by_id = [m for p, m in paths if p == "/api/v1/events/{event_id}"]
    assert by_id == [frozenset({"GET"})]
    # Starlette matches in declaration order: /active must come first.
    order = [p for p, _ in paths]
    assert order.index("/api/v1/events/active") < order.index("/api/v1/events/{event_id}")
