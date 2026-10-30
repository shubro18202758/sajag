"""GET /api/v1/city/feed — the ``osint`` feed kind (C-C extension of contract C-T; OS-5).

* "Situation surfaced: <label> · <verification label> · <n> sources" — actor ``osint-ingress
  (system)``, machine, ``source: "osint"``, with the verification state, credibility and C-Q
  provenance; a held situation is never narrated;
* "Promoted to a corridor event by <officer>" — human;
* "Decision support: <decision> <COA label> by <officer>" from ``decision.dss_decision_log``;
* every text goes through the plate masking of the C-C feed;
* without migrations 021 / 022 the feed is today's: no OSINT source, no OSINT row.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import test_city_router as tcr
from httpx import ASGITransport, AsyncClient
from test_city_snapshot import OsintCity, _ingest, _place_name

from fixtures.osint.harness import BACKENDS, backend, client, make_app, reset_osint_state
from fixtures.osint.signals import new_tag
from osint_common import ethics
from traffic_oracle.city import common
from traffic_oracle.city import feed as feed_mod

#: the synthetic OSINT fixtures here predate the scope rule (tests/conftest.py)
SCOPE_GATE_OFF = True

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")


@pytest.fixture(autouse=True)
def _clean_state():
    reset_osint_state()
    yield
    reset_osint_state()


async def _feed(app: Any, query: str = "?kinds=osint&limit=500") -> dict:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://127.0.0.1") as c:
        r = await c.get("/api/v1/city/feed" + query)
    assert r.status_code == 200, r.text
    return r.json()


def _log(dss_id: str, decision: str, officer: str, *, coa_id: str | None, note: str | None,
         at: datetime, promoted: Any = None) -> dict:
    return {"log_id": abs(hash((dss_id, decision, at))) % 10**9, "dss_id": dss_id, "decision": decision,
            "coa_id": coa_id, "officer": officer, "note": note, "at": at, "promoted_event_id": promoted,
            "dispatch_ids": []}


async def test_surfaced_situations_are_narrated_as_osint_machine_rows():
    city = OsintCity()
    tag = new_tag()
    ids = await _ingest(city.osint_pool, tag)
    body = await _feed(city.app())
    items = {i["id"]: i for i in body["items"]}
    crash = items[f"resolved_events:{ids['weh']}"]
    assert crash["text"] == (f"Situation surfaced: Road accident · {_place_name('weh')} · "
                          "News-reported · 5 reports")
    assert (crash["kind"], crash["actor"], crash["actor_kind"], crash["source"]) == (
        "osint", feed_mod.OSINT_INGRESS_ACTOR, "machine", "osint")
    assert crash["verification_state"] == "NEWS-REPORTED" and crash["credibility"] == 0.65
    assert crash["urns"][:2] == [f"osint_event:{ids['weh']}", "segment:1015"] and crash["severity"] == "warn"
    prov = crash["props"]["provenance"]
    assert prov["source_feeds"] == ["google_news_rss"] and prov["links_withheld"] == 5
    sachet = items[f"resolved_events:{ids['sachet']}"]
    assert sachet["text"].endswith("· Official, verified · 1 report")
    # held situations are counts, never narrated
    assert f"resolved_events:{ids['nowcast']}" not in items and f"resolved_events:{ids['social']}" not in items
    assert {i["source"] for i in body["items"]} == {"osint"}
    assert set(body["sources"]) == {"resolved_events", "osint_promotions", "dss_decision_log"}
    assert all(s["status"] == "ok" for s in body["sources"].values()), body["sources"]
    for i in body["items"]:
        assert set(i) == tcr.FEED_KEYS
        ethics.assert_no_person_keys(i)


async def test_osint_texts_are_plate_masked():
    city = OsintCity()
    ids = await _ingest(city.osint_pool, new_tag())
    city.db.events[ids["weh"]]["label"] = f"Road accident · MH01AB1234 near {_place_name('weh')}"
    body = await _feed(city.app())
    crash = next(i for i in body["items"] if i["id"] == f"resolved_events:{ids['weh']}")
    assert "MH01AB1234" not in crash["text"] and "MH01AB•••4" in crash["text"]


async def test_decision_support_decisions_are_narrated_human_and_masked():
    city = OsintCity()
    ids = await _ingest(city.osint_pool, new_tag())
    now = datetime.now(UTC)
    dss_osint, dss_event = str(uuid.uuid4()), str(uuid.uuid4())
    city.db.dss[dss_osint] = {"dss_id": dss_osint, "event_urn": f"osint_event:{ids['weh']}", "state": "approved",
                              "generated_at": now - timedelta(minutes=9), "horizon_min": 45,
                              "recommendation": '{"top_coa_id": "coa_std"}'}
    city.db.dss[dss_event] = {"dss_id": dss_event, "event_urn": f"event:{tcr.E_PURSUIT}", "state": "rejected",
                              "generated_at": now - timedelta(minutes=8), "horizon_min": 45,
                              "recommendation": '{"top_coa_id": "coa_std"}'}
    city.db.coa[(dss_osint, "coa_std")] = {"label": "Advisory + 108 ambulance + 1 patrol"}
    promoted = uuid.uuid4()
    city.db.dss_log += [
        _log(dss_osint, "approve", "Duty Officer A", coa_id="coa_std", note=None,
             at=now - timedelta(minutes=2), promoted=promoted),
        _log(dss_event, "reject", "Duty Officer B", coa_id=None, note="tow truck MH01AB1234 already there",
             at=now - timedelta(minutes=1)),
    ]
    body = await _feed(city.app())
    rows = [i for i in body["items"] if i["id"].startswith("dss_decision_log:")]
    assert len(rows) == 2
    approve, reject = sorted(rows, key=lambda i: i["t"])
    assert approve["text"] == "Decision support: approved Advisory + 108 ambulance + 1 patrol by Duty Officer A"
    assert (approve["actor"], approve["actor_kind"], approve["source"]) == ("Duty Officer A", "human", "osint")
    assert approve["verification_state"] == "NEWS-REPORTED" and approve["severity"] == "warn"
    assert approve["urns"] == [f"osint_event:{ids['weh']}", f"event:{promoted}"]
    assert approve["props"]["decision"] == "approve" and approve["props"]["dss_id"] == dss_osint
    assert reject["text"].startswith("Decision support: rejected by Duty Officer B — tow truck MH01AB•••4")
    assert "MH01AB1234" not in reject["text"]
    assert reject["verification_state"] is None and reject["source"] in ("live", "emulated", "osint")


async def test_scoped_audits_carry_their_osint_rows():
    city = OsintCity()
    ids = await _ingest(city.osint_pool, new_tag())
    conn = city.city_pool.conn
    items, sources = await feed_mod.collect_feed(
        conn, since=common.EPOCH, limit=50, scope=feed_mod.FeedScope(osint_event_ids=[ids["dadar"]])
    )
    assert [i["id"] for i in items] == [f"resolved_events:{ids['dadar']}"]
    assert sources["resolved_events"]["status"] == "ok"


async def test_without_the_migrations_the_feed_is_todays():
    pool = tcr.CityFakePool(tcr.city_tables())
    app = tcr.make_app(pool, tcr.city_valkey())
    body = await _feed(app, "?limit=500")
    assert {i["kind"] for i in body["items"]} == {"event", "enforcement", "anpr", "dispatch", "signals",
                                                  "ama", "brain"}
    assert not set(body["sources"]) & {"resolved_events", "osint_promotions", "dss_decision_log"}
    only = await _feed(app)
    assert only["items"] == [] and only["sources"] == {}
    assert not [sql for sql in pool.conn.calls if "osint." in sql or "decision." in sql]


@pytest.mark.parametrize("kind", [p for p in BACKENDS if p != "fake"])
async def test_feed_on_the_sandbox(kind):
    tag = new_tag()
    async with backend(kind, tag) as bk:
        ids = await _ingest(bk.pool, tag, bk)
        app = make_app(bk.pool)
        async with client(app) as c:
            r = await c.get("/api/v1/city/feed", params={"kinds": "osint", "limit": 500})
        assert r.status_code == 200, r.text
        items = {i["id"]: i for i in r.json()["items"]}
        crash = items[f"resolved_events:{ids['weh']}"]
        assert crash["source"] == "osint" and crash["actor_kind"] == "machine"
        assert crash["text"].startswith(f"Situation surfaced: Road accident · {_place_name('weh')}")
        assert f"resolved_events:{ids['social']}" not in items
        assert all(s["status"] == "ok" for s in r.json()["sources"].values()), r.json()["sources"]
        # a decision on the situation: the subject joins on the uuid parsed from its URN
        dss_id, log_at = str(uuid.uuid4()), datetime.now(UTC) - timedelta(seconds=5)
        bk.cleanup.dss_ids.add(dss_id)
        async with bk.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    "INSERT INTO decision.decision_support (dss_id, event_urn, state, generated_at, horizon_min, "
                    "seed, input_fingerprint, situation, criteria, ahp, recommendation, provenance, labels) VALUES "
                    "($1::uuid, $2, 'rejected', $3, 45, 1, $4, '{}'::jsonb, '[]'::jsonb, '{}'::jsonb, "
                    "'{\"top_coa_id\": \"coa_std\"}'::jsonb, '{}'::jsonb, ARRAY['SIMULATED'])",
                    dss_id, f"osint_event:{ids['weh']}", log_at, f"{tag}-fp")
                await conn.execute(
                    "INSERT INTO decision.dss_decision_log (dss_id, decision, officer, note, at) VALUES "
                    "($1::uuid, 'reject', 'Sandbox Officer', 'test', $2)", dss_id, log_at)
        async with client(app) as c:
            r = await c.get("/api/v1/city/feed", params={"kinds": "osint", "limit": 500})
        (row,) = [i for i in r.json()["items"] if i["id"].startswith("dss_decision_log:")
                  and i["props"]["dss_id"] == dss_id]
        assert row["text"] == "Decision support: rejected by Sandbox Officer — test"
        assert row["verification_state"] == "NEWS-REPORTED" and row["credibility"] == 0.65  # joined
