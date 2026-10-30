"""POST /api/v1/ai-proposals/decision and GET /api/v1/ai-proposals/decisions — the named-officer record of the AI
services' proposals (forecast, hydro, twin).

Offline (a fake pool answering exactly the module's statements; nothing leaves the process):

* the FROZEN order: 422 body (a reject without a note, an unknown source, a proposal not in ``proposed``, an
  unknown key, a person key in the evidence, an over-long evidence) → 409 ``officer-required`` BEFORE any lookup
  (the pool is never acquired) → 503 store missing → the row; a second decision on the same proposal → 409
  ``already-decided`` with the earlier decision, officer and time;
* approve records exactly one row and answers ``actuated: false``, ``outcome: recorded`` — the route writes
  nothing else (the recording connection sees one INSERT);
* the deck-verified header officer wins over a body officer (the body's is kept as ``claimed_officer``), and a
  header on a non-loopback connection is ignored;
* the record lists newest first, filtered by source; the coordination seam mounts both routes.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from traffic_oracle.ai_proposals import router as ai_router
from traffic_oracle.city import common

OFFICER = "Sandbox Officer"


class FakeConn:
    def __init__(self, db: FakeDB) -> None:
        self.db = db

    async def fetchval(self, sql: str, *args: Any) -> Any:
        self.db.calls.append(sql)
        assert sql == common._SQL_REGCLASS, sql
        return self.db.migrated and args[0] == ai_router.AI_PROPOSAL_LOG

    async def fetchrow(self, sql: str, *args: Any) -> Any:
        self.db.calls.append(sql)
        if sql == ai_router._SQL_INSERT:
            pid = args[0]
            if any(r["proposal_id"] == pid for r in self.db.rows):
                return None
            self.db.clock += timedelta(seconds=1)
            row = {
                "log_id": len(self.db.rows) + 1,
                "proposal_id": pid,
                "source": args[1],
                "kind": args[2],
                "subject_urn": args[3],
                "summary": args[4],
                "labels": list(args[5]),
                "evidence": args[6],
                "decision": args[7],
                "officer": args[8],
                "actor_source": args[9],
                "note": args[10],
                "decided_at": self.db.clock,
            }
            self.db.rows.append(row)
            return {"log_id": row["log_id"], "decided_at": row["decided_at"]}
        if sql == ai_router._SQL_EXISTING:
            return next((r for r in self.db.rows if r["proposal_id"] == args[0]), None)
        raise AssertionError(f"unexpected statement: {sql}")

    async def fetch(self, sql: str, *args: Any) -> list[dict[str, Any]]:
        self.db.calls.append(sql)
        assert sql == ai_router._SQL_LIST, sql
        limit, source = args
        rows = [r for r in self.db.rows if source is None or r["source"] == source]
        rows.sort(key=lambda r: (r["decided_at"], r["log_id"]), reverse=True)
        return rows[:limit]


class FakeDB:
    def __init__(self, migrated: bool = True) -> None:
        self.migrated = migrated
        self.rows: list[dict[str, Any]] = []
        self.calls: list[str] = []
        self.acquired = 0
        self.clock = datetime(2026, 10, 28, 12, 0, tzinfo=UTC)

    @asynccontextmanager
    async def acquire(self):
        self.acquired += 1
        yield FakeConn(self)


@pytest.fixture(autouse=True)
def _fresh_probe(monkeypatch):
    monkeypatch.setattr(common, "_REL_CACHE", {})


def _app(db: FakeDB | None) -> FastAPI:
    app = FastAPI()
    app.include_router(ai_router.router)
    app.state.pool = db
    return app


def _proposal(pid: str = "hy-reroute-1033-20250923T0200Z", **over: Any) -> dict[str, Any]:
    p = {
        "proposal_id": pid,
        "source": "hydro",
        "kind": "waterlogging_reroute",
        "subject_urn": "segment:1033",
        "summary": "Gariahat crossing (Rash Behari Avenue): waterlogging risk 3 (> 30 cm), deep water in about 45 min.",
        "labels": ["MODELLED", "LIVE", "EMULATED"],
        "state": "proposed",
        "evidence": {"risk_class": 3, "lead_time_deep_min": 45, "drivers": {"tide": {"gate_closed_now": True}}},
    }
    p.update(over)
    return p


async def _post(app: FastAPI, body: dict, *, header: str | None = OFFICER, base_url: str = "http://127.0.0.1"):
    headers = {"x-sajag-officer": header} if header else {}
    async with AsyncClient(transport=ASGITransport(app=app), base_url=base_url) as c:
        return await c.post("/api/v1/ai-proposals/decision", json=body, headers=headers)


async def _get(app: FastAPI, query: str = ""):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://127.0.0.1") as c:
        return await c.get(f"/api/v1/ai-proposals/decisions{query}")


# ── step 1: shape → 422 ─────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "body",
    [
        {"proposal": _proposal(), "decision": "reject"},
        {"proposal": _proposal(), "decision": "reject", "note": "   "},
        {"proposal": _proposal(source="oracle"), "decision": "approve"},
        {"proposal": _proposal(state="approved"), "decision": "approve"},
        {"proposal": _proposal(), "decision": "defer", "note": "later"},
        {"proposal": _proposal(pid="bad id/with slash"), "decision": "approve"},
        {"proposal": _proposal(kind="Bad-Kind"), "decision": "approve"},
        {"proposal": _proposal(labels=["x" * 41]), "decision": "approve"},
        {"proposal": _proposal(labels=[f"L{i}" for i in range(9)]), "decision": "approve"},
        {"proposal": {**_proposal(), "extra": 1}, "decision": "approve"},
        {"proposal": _proposal(), "decision": "approve", "unknown": True},
        {"proposal": _proposal(evidence={"author": "x"}), "decision": "approve"},
        {"proposal": _proposal(evidence={"blob": "x" * (33 * 1024)}), "decision": "approve"},
        {"proposal": _proposal(summary="ok\x00no"), "decision": "approve"},
        {"proposal": _proposal(), "decision": "approve", "officer": "X"},
    ],
)
async def test_shape_is_422_before_anything(body):
    db = FakeDB()
    r = await _post(_app(db), body)
    assert r.status_code == 422, r.text
    assert db.acquired == 0 and not db.rows


# ── step 2: a named officer, before any lookup ──────────────────────────────


async def test_officer_required_before_any_lookup():
    db = FakeDB(migrated=False)  # even a store without 026 answers officer-required first
    r = await _post(_app(db), {"proposal": _proposal(), "decision": "approve"}, header=None)
    assert r.status_code == 409
    assert r.json()["detail"] == "officer-required" and r.json()["reason"]
    assert db.acquired == 0 and db.calls == []
    # no pool at all: still officer-required, never a 503
    r = await _post(_app(None), {"proposal": _proposal(), "decision": "reject", "note": "dry now"}, header=None)
    assert r.status_code == 409 and r.json()["detail"] == "officer-required"


async def test_a_header_off_loopback_is_ignored():
    db = FakeDB()
    r = await _post(_app(db), {"proposal": _proposal(), "decision": "approve"}, base_url="http://10.0.0.5")
    assert r.status_code == 409 and r.json()["detail"] == "officer-required"
    assert db.acquired == 0


# ── step 3: the store ───────────────────────────────────────────────────────


async def test_store_missing_is_503():
    r = await _post(_app(None), {"proposal": _proposal(), "decision": "approve"})
    assert r.status_code == 503 and r.json()["detail"] == "database pool unavailable"
    db = FakeDB(migrated=False)
    r = await _post(_app(db), {"proposal": _proposal(), "decision": "approve"})
    assert r.status_code == 503 and "026" in r.json()["detail"]
    assert not db.rows


# ── step 4: the record ──────────────────────────────────────────────────────


async def test_approve_records_one_row_and_actuates_nothing():
    db = FakeDB()
    r = await _post(_app(db), {"proposal": _proposal(), "decision": "approve", "note": "  divert early  "})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["actuated"] is False and out["outcome"] == "recorded"
    assert out["decision"] == "approve" and out["officer"] == OFFICER
    assert out["actor_source"] == "x-sajag-officer" and out["claimed_officer"] is None
    assert out["note"] == "divert early"
    assert out["proposal_id"] == "hy-reroute-1033-20250923T0200Z" and out["source"] == "hydro"
    assert out["kind"] == "waterlogging_reroute" and out["subject_urn"] == "segment:1033"
    assert out["log_id"] == 1 and out["decided_at"].startswith("2026-10-28T12:00:01")
    assert len(db.rows) == 1 and db.rows[0]["labels"] == ["MODELLED", "LIVE", "EMULATED"]
    assert '"risk_class": 3' in db.rows[0]["evidence"]
    # the recording connection: the probe and ONE insert — no signal, dispatch or event statement
    writes = [c for c in db.calls if c != common._SQL_REGCLASS]
    assert writes == [ai_router._SQL_INSERT]


async def test_body_officer_records_when_no_header():
    db = FakeDB()
    r = await _post(_app(db), {"proposal": _proposal(source="twin", kind="webster_retime", subject_urn="junction:31"),
                               "decision": "reject", "note": "coordination matters here", "officer": "  R.  Sen "},
                    header=None)
    assert r.status_code == 200, r.text
    assert r.json()["officer"] == "R. Sen" and r.json()["actor_source"] == "body"
    assert db.rows[0]["decision"] == "reject" and db.rows[0]["note"] == "coordination matters here"


async def test_header_officer_wins_over_body_officer():
    db = FakeDB()
    r = await _post(_app(db), {"proposal": _proposal(), "decision": "approve", "officer": "Someone Else"})
    assert r.status_code == 200, r.text
    assert r.json()["officer"] == OFFICER and r.json()["claimed_officer"] == "Someone Else"
    assert db.rows[0]["officer"] == OFFICER and db.rows[0]["actor_source"] == "x-sajag-officer"


async def test_second_decision_is_409_already_decided():
    db = FakeDB()
    app = _app(db)
    first = await _post(app, {"proposal": _proposal(), "decision": "approve"})
    assert first.status_code == 200
    again = await _post(app, {"proposal": _proposal(), "decision": "reject", "note": "changed my mind"},
                        header="Another Officer")
    assert again.status_code == 409
    body = again.json()
    assert body["detail"] == "already-decided" and body["reason"]
    assert body["decision"] == "approve" and body["officer"] == OFFICER
    assert body["decided_at"] == first.json()["decided_at"] and body["proposal_id"] == _proposal()["proposal_id"]
    assert len(db.rows) == 1


# ── the record ──────────────────────────────────────────────────────────────


async def test_list_is_newest_first_and_filters_by_source():
    db = FakeDB()
    app = _app(db)
    for pid, src, kind in (("fc-1043-20261028T1200Z", "forecast", "pre_emptive_diversion"),
                           ("hy-wire-1033-20261028T1215Z", "hydro", "live_wire_hazard"),
                           ("twin-53e70c3c19ac", "twin", "webster_retime")):
        r = await _post(app, {"proposal": _proposal(pid=pid, source=src, kind=kind), "decision": "approve"})
        assert r.status_code == 200, r.text
    r = await _get(app)
    assert r.status_code == 200
    ids = [d["proposal_id"] for d in r.json()["decisions"]]
    assert ids == ["twin-53e70c3c19ac", "hy-wire-1033-20261028T1215Z", "fc-1043-20261028T1200Z"]
    first = r.json()["decisions"][0]
    assert set(first) == {"log_id", "proposal_id", "source", "kind", "subject_urn", "decision", "officer", "note",
                          "decided_at", "labels"}
    r = await _get(app, "?source=hydro&limit=5")
    assert [d["source"] for d in r.json()["decisions"]] == ["hydro"]
    r = await _get(app, "?limit=1")
    assert len(r.json()["decisions"]) == 1
    assert (await _get(app, "?source=oracle")).status_code == 422
    assert (await _get(app, "?limit=0")).status_code == 422


async def test_list_without_the_store_is_503():
    assert (await _get(_app(None))).status_code == 503
    assert (await _get(_app(FakeDB(migrated=False)))).status_code == 503


# ── the coordination seam ───────────────────────────────────────────────────


async def test_coordination_mounts_both_routes():
    from traffic_oracle import coordination

    assert coordination.AI_PROPOSAL_PATHS == ("/api/v1/ai-proposals/decisions",)
    app = FastAPI()
    coordination.register_coordination_routers(app)
    assert coordination._route_exists(app, "/api/v1/ai-proposals/decision")
    assert coordination._route_exists(app, "/api/v1/ai-proposals/decisions")
    # the real routes answer (no pool → the route's own 503, never the stub's "not deployed")
    r = await _post(app, {"proposal": _proposal(), "decision": "approve"})
    assert r.status_code == 503 and r.json() == {"detail": "database pool unavailable"}
    r = await _get(app)
    assert r.status_code == 503 and r.json() == {"detail": "database pool unavailable"}
