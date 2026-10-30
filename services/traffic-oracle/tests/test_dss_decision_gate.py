"""POST /api/v1/decision-support/{dss_id}/decision — the named-officer gate (C-U; LG 25 relies on its order).

Dual-mode (the fake store always; the int3c sandbox with ``OSINT_TEST_DSN``, every row run-scoped and deleted):

* the FROZEN order: 422 body → 409 ``officer-required`` (before ANY lookup: an existing, a random and a malformed
  ``dss_id`` all answer it) → 404 unknown ``dss_id`` → 409 ``not-proposed`` (an expired DSS, the expiry applied
  first) → ``unknown-coa`` | ``coa-vetoed`` | ``coa-infeasible`` → ``no-anchor``;
* approve on an unpromoted ``osint_event`` with dispatch actions: the report is promoted with the same officer
  (``dss_id`` in its provenance), N dispatch REQUESTS land in ``requested`` (one per dispatch action, each with its
  audit row), the DSS is ``approved`` and one log row is written; a retry after a forced failure in step 2 reuses
  the promoted event and creates no duplicate;
* reject and defer need a note and write the state and a log row only;
* ``next_steps`` name every other verb with its home;
* the recording connection: an approval writes the 022 tables, the promotion and the dispatch requests — nothing
  else;
* a DSS generated on the corridor event an approval promoted carries its OSINT report's provenance and
  corroboration (never 'the city's own channel'); an expiry the decision finds under its lock is committed.
"""

from __future__ import annotations

import json
from datetime import timedelta

import pytest

from fixtures.dss.fakedss import (
    BACKENDS,
    OFFICER,
    create_event,
    dss_backend,
    seed_situations,
    road_units,
    write_statements,
)
from fixtures.osint.harness import reset_osint_state
from fixtures.osint.signals import new_tag
from osint_common.types import DecisionSupport, DssDecisionResult
from traffic_oracle.decision_support import store as dss_store
from traffic_oracle.osint import store as osint_store

#: the synthetic OSINT fixtures here predate the scope rule (tests/conftest.py)
SCOPE_GATE_OFF = True

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")

UNKNOWN = "0b7e3c2a-2222-4d1e-9a8b-5c6d7e8f9a0b"


@pytest.fixture(autouse=True)
def _clean():
    reset_osint_state()
    yield
    reset_osint_state()


def _client(app, base_url: str = "http://127.0.0.1"):
    from httpx import ASGITransport, AsyncClient

    return AsyncClient(transport=ASGITransport(app=app), base_url=base_url)


async def _decide(app, dss_id: str, body: dict, *, header: str | None = OFFICER, base_url: str = "http://127.0.0.1"):
    headers = {"x-sajag-officer": header} if header else {}
    async with _client(app, base_url) as c:
        return await c.post(f"/api/v1/decision-support/{dss_id}/decision", json=body, headers=headers)


async def _generate(bk, app, urn: str, body: dict | None = None) -> dict:
    async with _client(app) as c:
        r = await c.post(f"/api/v1/decision-support/{urn}/generate", json=body or {})
    assert r.status_code == 201, r.text
    bk.track_dss(r.json()["dss_id"])
    return r.json()


async def _get(app, dss_id: str) -> dict:
    async with _client(app) as c:
        r = await c.get(f"/api/v1/decision-support/{dss_id}")
    assert r.status_code == 200, r.text
    return r.json()


async def _dispatches(bk, event_id: str) -> list[dict]:
    if bk.db is not None:
        return [dict(d, dispatch_id=str(d["dispatch_id"])) for d in bk.db.dispatches
                if str(d["event_id"]) == str(event_id)]
    rows = await bk.fetch(
        "SELECT dispatch_id, agency, unit_id, status, requested_by, request_payload, waypoint_junction "
        "FROM corridor.dispatches WHERE event_id = $1::uuid ORDER BY created_at", event_id)
    out = []
    for r in rows:
        d = dict(r)
        d["dispatch_id"] = str(d["dispatch_id"])
        d["request_payload"] = json.loads(d["request_payload"])
        out.append(d)
    return out


async def _audits(bk, dispatch_ids: list[str]) -> list[dict]:
    if bk.db is not None:
        return [e for e in bk.db.dispatch_events if e["dispatch_id"] in set(dispatch_ids)]
    rows = await bk.fetch(
        "SELECT dispatch_id::text AS dispatch_id, from_status, to_status, actor, note FROM corridor.dispatch_events "
        "WHERE dispatch_id = ANY($1::uuid[])", dispatch_ids)
    return [dict(r) for r in rows]


async def _logs(bk, dss_id: str) -> list[dict]:
    if bk.db is not None:
        return [x for x in bk.db.dss_log if x["dss_id"] == dss_id]
    rows = await bk.fetch(
        "SELECT decision, coa_id, officer, note, promoted_event_id, dispatch_ids, next_steps "
        "FROM decision.dss_decision_log WHERE dss_id = $1::uuid ORDER BY log_id", dss_id)
    out = []
    for r in rows:
        d = dict(r)
        d["promoted_event_id"] = str(d["promoted_event_id"]) if d["promoted_event_id"] else None
        d["dispatch_ids"] = [str(x) for x in d["dispatch_ids"]]
        d["next_steps"] = json.loads(d["next_steps"])
        out.append(d)
    return out


async def _promoted_of(bk, oid: str) -> str | None:
    async with bk.pool.acquire() as conn:
        row = await osint_store.get_row(conn, oid)
    return str(row["promoted_event_id"]) if row and row["promoted_event_id"] else None


async def _corridor(bk, event_id: str) -> dict:
    if bk.db is not None:
        e = dict(bk.db.corridor[event_id])
        e["provenance"] = json.loads(e["provenance"]) if isinstance(e["provenance"], str) else e["provenance"]
        return e
    rows = await bk.fetch(
        "SELECT status, source_kind, provenance FROM events.corridor_events WHERE event_id = $1::uuid", event_id)
    e = dict(rows[0])
    e["provenance"] = json.loads(e["provenance"])
    return e


async def _age(bk, dss_id: str, minutes: int) -> None:
    if bk.db is not None:
        bk.db.dss[dss_id]["generated_at"] -= timedelta(minutes=minutes)
        return
    async with bk.pool.acquire() as conn:
        await conn.execute(
            "UPDATE decision.decision_support SET generated_at = generated_at - make_interval(mins => $2) "
            "WHERE dss_id = $1::uuid", dss_id, minutes)


def _units(tag: str) -> dict:
    """One free patrol and one 108: the aggressive COA (2 police) is infeasible."""
    return road_units(police=1, committed_police=0, ambulance=1, prefix=tag[-6:] + "-")


# ── the frozen order of checks ────────────────────────────────────────────────


@pytest.mark.parametrize("kind", BACKENDS)
async def test_officer_required_before_any_lookup(kind):
    tag = new_tag()
    async with dss_backend(kind, tag) as bk:
        app, ids = await seed_situations(bk, tag, units=_units(tag))
        doc = await _generate(bk, app, f"osint_event:{ids['em_bypass']}")
        for did in (doc["dss_id"], UNKNOWN, "not-a-uuid"):
            if bk.conn is not None:
                bk.conn.calls.clear()
            r = await _decide(app, did, {"decision": "approve", "coa_id": "coa_std"}, header=None)
            assert r.status_code == 409, (did, r.text)
            assert r.json()["detail"] == "officer-required"
            if bk.conn is not None:
                assert dss_store._SQL_DSS_ROW not in bk.conn.calls  # no lookup happened
                assert bk.conn.calls == []
        # a header that did not come over loopback names no officer
        r = await _decide(app, doc["dss_id"], {"decision": "approve", "coa_id": "coa_std"},
                          base_url="http://10.0.0.5")
        assert r.status_code == 409 and r.json()["detail"] == "officer-required"
        # 422 (the body's shape) comes first of all — even without an officer
        for body in ({"decision": "maybe"}, {"decision": "approve"}, {"decision": "reject"},
                     {"decision": "defer", "note": "  "}, {"decision": "approve", "coa_id": "coa_std", "x": 1}):
            r = await _decide(app, UNKNOWN, body, header=None)
            assert r.status_code == 422, (body, r.text)
        assert (await _get(app, doc["dss_id"]))["state"] == "proposed"


@pytest.mark.parametrize("kind", BACKENDS)
async def test_404_unknown_then_not_proposed_then_coa_refusals(kind, monkeypatch):
    tag = new_tag()
    async with dss_backend(kind, tag) as bk:
        app, ids = await seed_situations(bk, tag, units=_units(tag))
        for did in (UNKNOWN, "not-a-uuid"):
            r = await _decide(app, did, {"decision": "approve", "coa_id": "coa_std"})
            assert r.status_code == 404, r.text
            r = await _decide(app, did, {"decision": "reject", "note": "x"}, header=None)
            assert r.status_code == 409  # still officer-required first

        doc = await _generate(bk, app, f"osint_event:{ids['em_bypass']}")
        did = doc["dss_id"]
        by = {c["coa_id"]: c for c in doc["coa_set"]}
        assert by["coa_agg"]["resource_feasibility"]["feasible"] is False
        r = await _decide(app, did, {"decision": "approve", "coa_id": "coa_nope"})
        assert r.status_code == 409 and r.json()["detail"] == "unknown-coa"
        r = await _decide(app, did, {"decision": "approve", "coa_id": "coa_agg"})
        assert r.status_code == 409 and r.json()["detail"] == "coa-infeasible"
        assert (await _get(app, did))["state"] == "proposed"

        # no-anchor: a junction-anchored report whose junction has no segment left to be promoted onto
        robbery = await _generate(bk, app, f"osint_event:{ids['gariahat']}")
        assert robbery["situation"]["junction_id"] == 23  # Gariahat crossing
        monkeypatch.setattr(osint_store, "junction_adjacent_segment", _no_segment)
        r = await _decide(app, robbery["dss_id"], {"decision": "approve", "coa_id": "coa_std"})
        assert r.status_code == 409 and r.json()["detail"] == "no-anchor"
        assert (await _get(app, robbery["dss_id"]))["state"] == "proposed"
        assert await _promoted_of(bk, ids["gariahat"]) is None

        # an expired DSS is not proposed (the expiry is applied first, so even an unknown COA reads not-proposed)
        await _age(bk, did, 46)
        r = await _decide(app, did, {"decision": "approve", "coa_id": "coa_nope"})
        assert r.status_code == 409 and r.json()["detail"] == "not-proposed"
        assert (await _get(app, did))["state"] == "expired"
        r = await _decide(app, did, {"decision": "reject", "note": "too late"})
        assert r.status_code == 409 and r.json()["detail"] == "not-proposed"


async def _no_segment(conn, junction_id):
    return None


# ── approve: promote + dispatch requests + log, idempotent ───────────────────


@pytest.mark.parametrize("kind", BACKENDS)
async def test_approve_promotes_and_creates_dispatch_requests_then_retry_duplicates_nothing(kind, monkeypatch):
    tag = new_tag()
    async with dss_backend(kind, tag) as bk:
        app, ids = await seed_situations(bk, tag, units=_units(tag))
        oid = ids["em_bypass"]
        doc = await _generate(bk, app, f"osint_event:{oid}")
        did = doc["dss_id"]
        std = next(c for c in doc["coa_set"] if c["coa_id"] == "coa_std")
        n = sum(1 for a in std["actions"] if a["verb"] == "dispatch")
        assert n == 2  # the 108 and one patrol
        assert await _promoted_of(bk, oid) is None

        # step 2 fails after the first dispatch request: everything of step 2 rolls back
        real_audit = dss_store._audit
        calls = {"n": 0}

        async def flaky_audit(*a, **k):
            calls["n"] += 1
            if calls["n"] == 2:
                raise RuntimeError("forced step-2 failure (test)")
            return await real_audit(*a, **k)

        monkeypatch.setattr(dss_store, "_audit", flaky_audit)
        with pytest.raises(RuntimeError):
            await _decide(app, did, {"decision": "approve", "coa_id": "coa_std", "note": "go"})
        monkeypatch.setattr(dss_store, "_audit", real_audit)
        promoted = await _promoted_of(bk, oid)
        assert promoted is not None  # step 1 (its own transactions) stands
        bk.track_event(promoted)
        assert await _dispatches(bk, promoted) == []
        assert (await _get(app, did))["state"] == "proposed"
        assert await _logs(bk, did) == []

        # the retry: the promoted event is reused, the requests are created once
        r = await _decide(app, did, {"decision": "approve", "coa_id": "coa_std", "note": "go"})
        assert r.status_code == 200, r.text
        res = DssDecisionResult.model_validate(r.json()).model_dump(mode="json")
        assert res["state"] == "approved" and res["coa_id"] == "coa_std" and res["officer"] == OFFICER
        assert res["promoted_event_id"] == promoted
        assert len(res["dispatch_ids"]) == n
        rows = await _dispatches(bk, promoted)
        assert len(rows) == n
        assert {d["status"] for d in rows} == {"requested"}
        assert sorted(d["agency"] for d in rows) == ["ambulance", "police"]
        assert {d["dispatch_id"] for d in rows} == set(res["dispatch_ids"])
        for d in rows:
            assert d["requested_by"] == OFFICER
            assert d["request_payload"]["dss_id"] == did and did in d["request_payload"]["note"]
            assert d["request_payload"]["source"] == "decision_support"
            assert d["unit_id"].endswith(("PCR-EM-01", "108-EM-01"))
        assert d["waypoint_junction"] == 9  # the signalised junction the hold targets
        audits = await _audits(bk, res["dispatch_ids"])
        assert len(audits) == n
        assert all(a["to_status"] == "requested" and a["from_status"] is None and a["actor"] == OFFICER
                   for a in audits)
        corridor = await _corridor(bk, promoted)
        assert corridor["status"] == "active" and corridor["source_kind"] == "osint"
        assert corridor["provenance"]["dss_id"] == did
        logs = await _logs(bk, did)
        assert len(logs) == 1
        log = logs[0]
        assert (log["decision"], log["coa_id"], log["officer"], log["note"]) == ("approve", "coa_std", OFFICER, "go")
        assert log["promoted_event_id"] == promoted and sorted(log["dispatch_ids"]) == sorted(res["dispatch_ids"])
        assert log["next_steps"] == res["next_steps"]
        got = await _get(app, did)
        DecisionSupport.model_validate(got)
        assert got["state"] == "approved"
        assert got["human_gate"]["officer"] == OFFICER and got["human_gate"]["decided_at"]
        assert got["human_gate"]["audit_ref"].startswith("dss_decision_log:")
        # decided: a second decision is refused, nothing more is written
        again = await _decide(app, did, {"decision": "approve", "coa_id": "coa_std"})
        assert again.status_code == 409 and again.json()["detail"] == "not-proposed"
        assert len(await _dispatches(bk, promoted)) == n


@pytest.mark.parametrize("kind", BACKENDS)
async def test_next_steps_match_the_verbs(kind):
    tag = new_tag()
    async with dss_backend(kind, tag) as bk:
        app, ids = await seed_situations(bk, tag, units=_units(tag))
        doc = await _generate(bk, app, f"osint_event:{ids['em_bypass']}")
        r = await _decide(app, doc["dss_id"], {"decision": "approve", "coa_id": "coa_info"},
                          header=OFFICER)
        assert r.status_code == 200, r.text
        res = r.json()
        if res["promoted_event_id"]:
            bk.track_event(res["promoted_event_id"])
        info = next(c for c in doc["coa_set"] if c["coa_id"] == "coa_info")
        others = [a["verb"] for a in info["actions"] if a["verb"] != "dispatch"]
        assert [s["verb"] for s in res["next_steps"]] == others
        homes = {s["verb"]: s["home"] for s in res["next_steps"]}
        assert homes == {"request_cctv": "ICCC, outside Sajag", "monitor": "none"}
        cctv = next(s for s in res["next_steps"] if s["verb"] == "request_cctv")
        assert cctv["label"] == "Situation check at the junction (ICCC) — no identification"
        assert len(res["dispatch_ids"]) == 1  # the verifying patrol
        std_homes = {"advisory": "Advisories (draft only)", "signal_hold": "City signal plans (writer off by default)",
                     "closure": "Corridor operations", "diversion": "Corridor operations"}
        from traffic_oracle.decision_support import coa

        for verb, home in std_homes.items():
            assert coa.NEXT_STEP_HOMES[verb] == home
        assert coa.NEXT_STEP_HOMES["escort_switch"] == "Movement tab"


@pytest.mark.parametrize("kind", BACKENDS)
async def test_reject_and_defer_need_a_note_and_write_only_state_and_log(kind):
    tag = new_tag()
    async with dss_backend(kind, tag) as bk:
        app, ids = await seed_situations(bk, tag, units=_units(tag))
        for decision, subject in (("reject", "em_bypass"), ("defer", "gariahat")):
            doc = await _generate(bk, app, f"osint_event:{ids[subject]}")
            did = doc["dss_id"]
            r = await _decide(app, did, {"decision": decision})
            assert r.status_code == 422
            r = await _decide(app, did, {"decision": decision, "note": "   "})
            assert r.status_code == 422
            r = await _decide(app, did, {"decision": decision, "note": "officer judgement: wait for ICCC"},
                              header=None if decision == "defer" else OFFICER)
            if decision == "defer":
                assert r.status_code == 409  # no header and no body officer
                r = await _decide(app, did, {"decision": decision, "note": "officer judgement: wait for ICCC",
                                             "officer": "Duty Officer B"}, header=None)
            assert r.status_code == 200, r.text
            res = DssDecisionResult.model_validate(r.json())
            assert res.state == ("rejected" if decision == "reject" else "deferred")
            assert res.dispatch_ids == [] and res.promoted_event_id is None and res.next_steps == []
            assert await _promoted_of(bk, ids[subject]) is None
            logs = await _logs(bk, did)
            assert len(logs) == 1 and logs[0]["decision"] == decision
            assert logs[0]["note"] == "officer judgement: wait for ICCC"
            got = await _get(app, did)
            DecisionSupport.model_validate(got)
            assert got["state"] == res.state and got["human_gate"]["officer"] == res.officer


@pytest.mark.parametrize("kind", BACKENDS)
async def test_event_subject_dispatches_on_its_own_event(kind):
    tag = new_tag()
    async with dss_backend(kind, tag) as bk:
        app, _ids = await seed_situations(bk, tag, units=_units(tag))
        eid = await create_event(bk, app)
        doc = await _generate(bk, app, f"event:{eid}")
        r = await _decide(app, doc["dss_id"], {"decision": "approve", "coa_id": "coa_std"},
                          header=OFFICER)
        assert r.status_code == 200, r.text
        res = r.json()
        assert res["promoted_event_id"] is None
        rows = await _dispatches(bk, eid)
        assert len(rows) == len(res["dispatch_ids"]) >= 1
        assert {d["status"] for d in rows} == {"requested"}


async def test_header_wins_and_the_claim_is_kept():
    tag = new_tag()
    async with dss_backend("fake", tag) as bk:
        app, ids = await seed_situations(bk, tag, units=_units(tag))
        doc = await _generate(bk, app, f"osint_event:{ids['em_bypass']}")
        r = await _decide(app, doc["dss_id"], {"decision": "approve", "coa_id": "coa_std", "officer": "Someone Else"},
                          header="Duty Officer A")
        assert r.status_code == 200, r.text
        assert r.json()["officer"] == "Duty Officer A"
        ev = [e for e in bk.db.dispatch_events if e["dispatch_id"] in set(r.json()["dispatch_ids"])]
        assert ev and all(e["actor"] == "Duty Officer A" for e in ev)
        assert all(e["detail"]["claimed_officer"] == "Someone Else" for e in ev)


async def test_an_approval_writes_only_the_022_tables_the_promotion_and_dispatch_requests():
    """The recording connection: every write statement of an approval, by table."""
    tag = new_tag()
    async with dss_backend("fake", tag) as bk:
        app, ids = await seed_situations(bk, tag, units=_units(tag))
        doc = await _generate(bk, app, f"osint_event:{ids['em_bypass']}")
        bk.conn.calls.clear()
        r = await _decide(app, doc["dss_id"], {"decision": "approve", "coa_id": "coa_std"})
        assert r.status_code == 200, r.text
        allowed = (
            "INSERT INTO decision.dss_decision_log", "UPDATE decision.decision_support",
            "INSERT INTO corridor.dispatches", "INSERT INTO corridor.dispatch_events",
            # the promotion (OS-5, through the events module)
            "INSERT INTO events.corridor_events", "INSERT INTO events.event_routes", "INSERT INTO events.event_phases",
            "INSERT INTO events.event_status_log", "UPDATE events.corridor_events SET status",
            "UPDATE osint.resolved_events SET promoted_event_id",
        )
        writes = write_statements(bk.conn.calls)
        assert writes
        for sql in writes:
            assert sql.startswith(allowed), sql[:100]
        assert sum(1 for s in writes if s.startswith("INSERT INTO corridor.dispatches")) == 2
        assert not any(s.startswith(("UPDATE corridor.dispatches", "DELETE")) for s in writes)


# ── the corridor event an approval promoted, as a subject of its own ─────────


@pytest.mark.parametrize("kind", BACKENDS)
async def test_a_dss_on_the_promoted_event_carries_its_osint_report(kind, monkeypatch):
    """Ethics rule 7: approve coa_std on the road-accident report (it is promoted), then generate on
    event:<promoted>.  The event is NEWS-REPORTED and its provenance is the report's — feeds, the fictional
    publishers news-a/news-b, every source, the independent-publisher count and tiers — and the dissent never
    calls it the city's own channel; the 'an OFFICIAL source would ...' check runs for it."""
    tag = new_tag()
    async with dss_backend(kind, tag) as bk:
        app, ids = await seed_situations(bk, tag, units=road_units(police=2, committed_police=0, ambulance=2,
                                                                prefix=tag[-6:] + "-"))
        oid = ids["em_bypass"]
        report = await _generate(bk, app, f"osint_event:{oid}")
        r = await _decide(app, report["dss_id"], {"decision": "approve", "coa_id": "coa_std", "note": "go"})
        assert r.status_code == 200, r.text
        promoted = r.json()["promoted_event_id"]
        assert promoted
        bk.track_event(promoted)
        bk.subjects.add(f"event:{promoted}")
        doc = await _generate(bk, app, f"event:{promoted}")
        DecisionSupport.model_validate(doc)
        s, prov = doc["situation"], doc["provenance"]
        assert s["verification_state"] == "NEWS-REPORTED" and doc["labels"][0] == "NEWS-REPORTED"
        assert s["credibility"] == pytest.approx(0.65)
        assert prov["publishers"] == ["news-a.example", "news-b.example"]
        assert prov["feeds"] == report["provenance"]["feeds"] == ["google_news_rss"]
        assert sorted(x["signal_id"] for x in prov["sources"]) == sorted(
            x["signal_id"] for x in report["provenance"]["sources"])
        for key in ("independent_publishers", "source_tiers", "cross_type_corroborated"):
            assert s[key] == report["situation"][key], key
        assert s["independent_publishers"] == 2
        dissent = doc["recommendation"]["dissent"]
        assert "no OSINT corroboration" not in dissent and "city's own channel" not in dissent
        assert f"a corridor event a named officer promoted from OSINT report osint_event:{oid}" in dissent
        assert "Corroboration is REAL but within one tier: 2 independent news publisher(s)" in dissent
        assert "an OFFICIAL source" in dissent  # the official-source check runs for an OSINT-sourced event

        # [FIX-B-ORACLE] on this path too: a context member of the report is shown as context, never counted
        import hashlib

        from osint_common.types import SourceRef

        ctx = SourceRef(signal_id=hashlib.sha1(f"{tag}:ctx".encode(), usedforsecurity=False).hexdigest(),
                        source="sachet_cap", publisher="sachet.ndma.gov.in", url=None,
                        title="Synthetic replica: heavy rain warning for Kolkata district",
                        event_class="weather_hazard", credibility=0.95, fetch_mode="cached-sample", role="context")
        real = osint_store.get_sources

        async def get_sources(conn, osint_event_id):
            return [*await real(conn, osint_event_id), ctx]

        monkeypatch.setattr(osint_store, "get_sources", get_sources)
        with_ctx = await _generate(bk, app, f"event:{promoted}")
        prov = with_ctx["provenance"]
        assert prov["publishers"] == ["news-a.example", "news-b.example"] and "sachet_cap" not in prov["feeds"]
        assert [x["role"] for x in prov["sources"] if x["signal_id"] == ctx.signal_id] == ["context"]
        assert with_ctx["situation"]["independent_publishers"] == 2
        assert ("Context, not corroboration: District warning in effect (sachet.ndma.gov.in)"
                in with_ctx["recommendation"]["dissent"])


@pytest.mark.parametrize("kind", BACKENDS)
async def test_an_expiry_found_by_the_decision_is_written(kind):
    """``store.decide`` applies the lazy expiry under the row lock and COMMITS it before refusing
    ``not-proposed`` (the refusal no longer rolls the expiry back)."""
    tag = new_tag()
    async with dss_backend(kind, tag) as bk:
        app, ids = await seed_situations(bk, tag, units=_units(tag))
        doc = await _generate(bk, app, f"osint_event:{ids['gariahat']}", {"horizon_min": 15})
        did = doc["dss_id"]
        await _age(bk, did, 16)
        from datetime import UTC, datetime

        async with bk.pool.acquire() as conn:
            with pytest.raises(dss_store.Refused) as refused:
                await dss_store.decide(
                    conn, did, decision="reject", actor=OFFICER, detail=None, note="too late", coa=None,
                    event_id=None, waypoint_junction=None, promoted_event_id=None, next_steps=[],
                    now=datetime.now(UTC),
                )
        assert refused.value.code == "not-proposed"
        if bk.db is not None:
            state = bk.db.dss[did]["state"]
        else:
            state = (await bk.fetch("SELECT state FROM decision.decision_support WHERE dss_id = $1::uuid", did))[0][
                "state"]
        assert state == "expired"
        assert await _logs(bk, did) == []
