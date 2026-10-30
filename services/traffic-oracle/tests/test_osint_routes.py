"""GET /api/v1/osint/events, GET /api/v1/osint/events/{id}, GET /api/v1/osint/gazetteer/resolve (C-T).

Dual-mode like test_osint_ingest.py: the in-memory fake always, the sandbox database when
``OSINT_TEST_DSN`` is set (assertions scoped to this run's own rows — fused ids prefixed with the
run tag — never a global count).  The situations come in through POST /osint/signals with the fake
pipeline over the canonical synthetic fixtures:

    EM Bypass    road_accident + public_conflict (affray+collision), segment 1035, 0.65, NEWS-REPORTED
    Gariahat     reported_crime at junction 23 (Gariahat crossing), 0.60, NEWS-REPORTED
    SACHET       weather_hazard, Kolkata district (area level), 0.95, OFFICIAL-VERIFIED
    nowcast      West Bengal state-level → HELD (outside_city)
    one post     single social source at Taratala → HELD (social_single_source)

* the list filters (bbox, class incl. a correlated class, min_credibility, state, since, limit) and
  their 422s; every row is a valid OsintEventRow with no person key;
* held situations appear only as counts — never a row, and their dossier is a 404;
* the dossier: sources by publisher with a news/social link withheld (and said so), geocodes,
  the audit trail, the C-Q provenance;
* the resolve endpoint through a fake resolver (whitelisted candidate fields, person keys dropped),
  503 when the resolver is not deployed; read-only.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from fixtures.osint.harness import BACKENDS, backend, client, make_app, reset_osint_state
from fixtures.osint.signals import FakePipeline, canonical_set, new_tag, payload
from osint_common import ethics
from osint_common.types import Geocode, OsintEventRow, SourceRef
from traffic_oracle.city.common import SOURCE_LINK_WITHHELD
from traffic_oracle.osint import router as osint_router

#: the synthetic OSINT fixtures here predate the scope rule (tests/conftest.py)
SCOPE_GATE_OFF = True

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")


@pytest.fixture(autouse=True)
def _clean_state():
    reset_osint_state()
    osint_router.RESOLVE_HOOK = None
    yield
    osint_router.RESOLVE_HOOK = None
    reset_osint_state()


async def _seed(bk: Any, tag: str) -> tuple[Any, dict[str, dict]]:
    """Ingest the canonical set; ``(app, {name: resolved item})``."""
    sets = canonical_set(tag)
    signals = [*sets["em_bypass"], sets["gariahat"], sets["sachet_district"], sets["sachet_state"], sets["social"]]
    bk.track(*signals)
    app = make_app(bk.pool, FakePipeline(tag))
    async with client(app) as c:
        r = await c.post("/api/v1/osint/signals", json={"signals": [payload(s) for s in signals]})
    assert r.status_code == 200, r.text
    names = {
        "em_bypass": sets["em_bypass"][0].signal_id,
        "gariahat": sets["gariahat"].signal_id,
        "sachet": sets["sachet_district"].signal_id,
        "nowcast": sets["sachet_state"].signal_id,
        "social": sets["social"].signal_id,
    }
    by_name: dict[str, dict] = {}
    pipe_ids = {}
    for item in r.json()["resolved"]:
        pipe_ids[item["fused_event_id"]] = item
    fake = FakePipeline(tag)
    for name, anchor in names.items():
        by_name[name] = pipe_ids[fake.fused_id(anchor)]
    return app, by_name


async def _list(app: Any, tag: str, query: str = "") -> tuple[int, dict, list[dict]]:
    if "limit=" not in query:  # a seeded sandbox holds other rows: read the whole page
        query += ("&" if query else "?") + "limit=200"
    async with client(app) as c:
        r = await c.get("/api/v1/osint/events" + query)
    body = r.json()
    mine = [e for e in body.get("events", []) if e["fused_event_id"].startswith(tag)] if r.status_code == 200 else []
    return r.status_code, body, mine


@pytest.mark.parametrize("kind", BACKENDS)
async def test_list_serves_surfaced_situations_and_counts_the_held(kind):
    tag = new_tag()
    async with backend(kind, tag) as bk:
        app, sit = await _seed(bk, tag)
        status, body, mine = await _list(app, tag)
        assert status == 200
        assert set(body) == {"as_of", "events", "held"}
        assert [e["osint_event_id"] for e in mine] == [
            sit["sachet"]["osint_event_id"], sit["em_bypass"]["osint_event_id"], sit["gariahat"]["osint_event_id"]
        ]  # by credibility, then recency
        for e in mine:
            OsintEventRow.model_validate(e)
            ethics.assert_no_person_keys(e)
            assert e["urn"] == f"osint_event:{e['osint_event_id']}"
        crash = next(e for e in mine if e["osint_event_id"] == sit["em_bypass"]["osint_event_id"])
        assert crash["correlated_classes"] == ["road_accident", "public_conflict"]
        assert crash["subtype"] == "affray+collision" and crash["segment_id"] == 1035
        assert crash["toponym"] == "Eastern Metropolitan Bypass"
        assert crash["credibility"] == 0.65 and crash["verification_state"] == "NEWS-REPORTED"
        assert crash["source_count"] == 5 and crash["independent_publishers"] == 2
        assert crash["attach"] == {"novel": True, "corroborates_live_urn": None} and crash["dss"] is None
        robbery = next(e for e in mine if e["osint_event_id"] == sit["gariahat"]["osint_event_id"])
        assert robbery["junction_id"] == 23 and robbery["toponym"] == "Gariahat crossing"
        # held situations are COUNTS only — never a row
        held_ids = {sit["nowcast"]["osint_event_id"], sit["social"]["osint_event_id"]}
        assert not held_ids & {e["osint_event_id"] for e in body["events"]}
        assert set(body["held"]) == {"social_single_source", "not_event_class", "outside_city"}
        assert body["held"]["social_single_source"] >= 1 and body["held"]["outside_city"] >= 1
        if bk.db is not None:  # the fake holds this run only: exact
            assert body["held"] == {"social_single_source": 1, "not_event_class": 0, "outside_city": 1}


@pytest.mark.parametrize("kind", BACKENDS)
async def test_list_filters(kind):
    tag = new_tag()
    async with backend(kind, tag) as bk:
        app, sit = await _seed(bk, tag)
        ids = {name: s["osint_event_id"] for name, s in sit.items()}

        async def got(query: str) -> list[str]:
            status, _, mine = await _list(app, tag, query)
            assert status == 200, query
            return [e["osint_event_id"] for e in mine]

        assert await got("?class=road_accident") == [ids["em_bypass"]]
        assert await got("?class=public_conflict") == [ids["em_bypass"]]  # a correlated class matches
        assert await got("?class=reported_crime") == [ids["gariahat"]]
        assert await got("?min_credibility=0.9") == [ids["sachet"]]
        assert await got("?min_credibility=0.65") == [ids["sachet"], ids["em_bypass"]]  # REAL 0.65 included
        assert await got("?state=NEWS-REPORTED") == [ids["em_bypass"], ids["gariahat"]]
        assert await got("?state=OFFICIAL-VERIFIED") == [ids["sachet"]]
        assert await got("?bbox=88.39,22.52,88.40,22.53") == [ids["em_bypass"]]  # EM Bypass at Kasba
        future = (datetime.now(UTC) + timedelta(hours=1)).isoformat().replace("+00:00", "Z")
        assert await got(f"?since={future}") == []
        past = (datetime.now(UTC) - timedelta(minutes=10)).isoformat().replace("+00:00", "Z")
        assert set(await got(f"?since={past}")) == {ids["em_bypass"], ids["gariahat"], ids["sachet"]}
        status, body, _ = await _list(app, tag, "?limit=1")
        assert status == 200 and len(body["events"]) == 1
        for bad in ("?class=ufo", "?state=TRUSTED", "?bbox=1,2,3", "?min_credibility=2", "?limit=201",
                    "?limit=0", "?since=yesterday"):
            status, _, _ = await _list(app, tag, bad)
            assert status == 422, bad


@pytest.mark.parametrize("kind", BACKENDS)
async def test_dossier_of_a_surfaced_situation(kind):
    tag = new_tag()
    async with backend(kind, tag) as bk:
        app, sit = await _seed(bk, tag)
        oid = sit["em_bypass"]["osint_event_id"]
        async with client(app) as c:
            r = await c.get(f"/api/v1/osint/events/{oid}")
        assert r.status_code == 200, r.text
        body = r.json()
        assert set(body) >= {"event", "sources", "geocodes", "audit", "provenance", "source_notes"}
        OsintEventRow.model_validate(body["event"])
        assert body["event"]["osint_event_id"] == oid
        assert len(body["sources"]) == 5
        for s in body["sources"]:
            SourceRef.model_validate(s)  # exactly a SourceRef (C-T): a typed consumer takes it as it is
            assert s["url"] is None  # a news link is withheld
            assert s["publisher"] in ("news-a.example", "news-b.example")
        assert [s["role"] for s in body["sources"]].count("primary") == 1
        # the honest note sits beside the sources, one per source in the same order
        notes = body["source_notes"]
        assert [n["signal_id"] for n in notes] == [s["signal_id"] for s in body["sources"]]
        assert all(n == {"signal_id": n["signal_id"], "source_tier": "aggregator",
                         "link_note": SOURCE_LINK_WITHHELD} for n in notes)
        assert len(body["geocodes"]) == 5
        for g in body["geocodes"]:
            Geocode.model_validate(g)
            assert g["segment_id"] == 1035 and g["toponym"] == "Eastern Metropolitan Bypass"
        prov = body["provenance"]
        assert prov["source_feeds"] == ["google_news_rss"]
        assert prov["publishers"] == ["news-a.example", "news-b.example"]
        assert prov["links_withheld"] == 5 and prov["link_note"] == SOURCE_LINK_WITHHELD
        assert prov["geocoder"] == "gazetteer_exact" and prov["geocode_confidence"] == 0.68
        surfaced = next(i for i in body["audit"] if i["id"] == f"resolved_events:{oid}")
        assert surfaced["kind"] == "osint" and surfaced["source"] == "osint"
        assert surfaced["text"].startswith("Situation surfaced: Road accident · Eastern Metropolitan Bypass")
        assert "News-reported" in surfaced["text"] and surfaced["text"].endswith("5 reports")
        assert surfaced["verification_state"] == "NEWS-REPORTED" and surfaced["credibility"] == 0.65
        ethics.assert_no_person_keys(body)


@pytest.mark.parametrize("kind", BACKENDS)
async def test_dossier_is_a_404_for_held_unknown_and_superseded_and_422_malformed(kind):
    tag = new_tag()
    async with backend(kind, tag) as bk:
        app, sit = await _seed(bk, tag)
        async with client(app) as c:
            for name in ("nowcast", "social"):
                r = await c.get(f"/api/v1/osint/events/{sit[name]['osint_event_id']}")
                assert r.status_code == 404, name
            assert (await c.get("/api/v1/osint/events/0b7e3c2a-1111-4d1e-9a8b-5c6d7e8f9a0b")).status_code == 404
            assert (await c.get("/api/v1/osint/events/not-a-uuid")).status_code == 422


@pytest.mark.parametrize("kind", BACKENDS)
async def test_official_sources_keep_their_link(kind):
    tag = new_tag()
    async with backend(kind, tag) as bk:
        app, sit = await _seed(bk, tag)
        async with client(app) as c:
            body = (await c.get(f"/api/v1/osint/events/{sit['sachet']['osint_event_id']}")).json()
        (src,) = body["sources"]
        SourceRef.model_validate(src)
        (note,) = body["source_notes"]
        assert note == {"signal_id": src["signal_id"], "source_tier": "official", "link_note": None}
        assert body["event"]["area_level"] is True and body["event"]["verification_state"] == "OFFICIAL-VERIFIED"


async def _insert_dss(bk: Any, urn: str, top_coa_id: str) -> str:
    """One proposed decision support for ``urn`` naming ``top_coa_id`` (cleaned up on the sandbox)."""
    import json
    import uuid

    dss_id, now = str(uuid.uuid4()), datetime.now(UTC)
    recommendation = json.dumps({"top_coa_id": top_coa_id})
    if bk.db is not None:
        bk.db.dss[dss_id] = {"dss_id": dss_id, "event_urn": urn, "state": "proposed", "generated_at": now,
                             "horizon_min": 45, "recommendation": recommendation}
        bk.db.coa[(dss_id, top_coa_id)] = {"label": "Advisory"}
        return dss_id
    bk.cleanup.dss_ids.add(dss_id)
    async with bk.pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                "INSERT INTO decision.decision_support (dss_id, event_urn, state, generated_at, horizon_min, seed, "
                "input_fingerprint, situation, criteria, ahp, recommendation, provenance, labels) VALUES ($1::uuid, "
                "$2, 'proposed', $3, 45, 1, $4, '{}'::jsonb, '[]'::jsonb, '{}'::jsonb, $5::jsonb, '{}'::jsonb, "
                "ARRAY['SIMULATED'])", dss_id, urn, now, f"{dss_id}-fp", recommendation)
            await conn.execute("INSERT INTO decision.coa (dss_id, coa_id, kind, label) VALUES ($1::uuid, $2, "
                               "'standard', 'Advisory')", dss_id, top_coa_id)
    return dss_id


@pytest.mark.parametrize("kind", BACKENDS)
async def test_a_malformed_decision_support_costs_the_situation_only_its_dss(kind):
    tag = new_tag()
    async with backend(kind, tag) as bk:
        app, sit = await _seed(bk, tag)
        oid = sit["em_bypass"]["osint_event_id"]
        await _insert_dss(bk, f"osint_event:{oid}", "COA-1")  # not a CoaId: DssSummary refuses it
        status, _, mine = await _list(app, tag)
        assert status == 200
        crash = next(e for e in mine if e["osint_event_id"] == oid)  # still listed ...
        assert crash["dss"] is None  # ... without the malformed summary
        OsintEventRow.model_validate(crash)
        async with client(app) as c:
            r = await c.get(f"/api/v1/osint/events/{oid}")
        assert r.status_code == 200 and r.json()["event"]["dss"] is None  # the dossier opens


# ── the routes before migration 021, and the mount ──────────────────────────


async def test_reads_answer_503_before_migration_021():
    async with backend("fake", new_tag(), migrated=False) as bk:
        app = make_app(bk.pool)
        async with client(app) as c:
            for path in ("/api/v1/osint/events", "/api/v1/osint/events/0b7e3c2a-1111-4d1e-9a8b-5c6d7e8f9a0b"):
                r = await c.get(path)
                assert r.status_code == 503 and "not migrated" in r.json()["detail"], path


async def test_the_real_router_replaced_the_stubs():
    from traffic_oracle.__main__ import create_app

    reset_osint_state()
    app = create_app()  # no pool: the real routes answer 503 "database pool unavailable"
    async with client(app) as c:
        r = await c.get("/api/v1/osint/events")
    assert r.status_code == 503 and r.json() == {"detail": "database pool unavailable"}


# ── GET /api/v1/osint/gazetteer/resolve ──────────────────────────────────────


async def test_resolve_through_a_fake_resolver_is_whitelisted_and_read_only():
    calls: list[tuple[str, int]] = []

    def fake_resolve_text(q: str, limit: int = 5) -> list[dict]:
        calls.append((q, limit))
        return [
            {"gaz_id": 27, "canonical_name": "Taratala (Diamond Harbour Road)",
             "feature_type": "junction", "lon": 88.3212219, "lat": 22.5101057, "segment_id": None,
             "junction_id": 27, "confidence": 0.82, "method": "gazetteer_exact",
             "surface_forms": ["taratala", "তারাতলা"], "internal_score": 3.1},
            {"gaz_id": 9, "canonical_name": "x", "uploader": "someone"},  # never a person field
        ]

    osint_router.RESOLVE_HOOK = fake_resolve_text
    async with backend("fake", new_tag()) as bk:
        app = make_app(bk.pool)
        async with client(app) as c:
            r = await c.get("/api/v1/osint/gazetteer/resolve", params={"q": "তারাতলা মোড়", "limit": 3})
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["q"] == "তারাতলা মোড়" and calls == [("তারাতলা মোড়", 3)]  # Marathi, as written
            (cand,) = body["candidates"]
            assert set(cand) == {"gaz_id", "canonical_name", "feature_type", "lon", "lat", "segment_id",
                                 "junction_id", "confidence", "method"}
            assert cand["junction_id"] == 27
            for bad in ({}, {"q": ""}, {"q": "x" * 201}, {"q": "tara\x00tala"}):
                assert (await c.get("/api/v1/osint/gazetteer/resolve", params=bad)).status_code == 422
        assert bk.conn.calls == []  # read-only: not one statement


async def test_resolve_is_503_when_the_resolver_is_not_deployed(monkeypatch):
    monkeypatch.setitem(sys.modules, "osint_geo", None)
    monkeypatch.setitem(sys.modules, "osint_geo.resolver", None)
    async with backend("fake", new_tag()) as bk:
        app = make_app(bk.pool)
        async with client(app) as c:
            r = await c.get("/api/v1/osint/gazetteer/resolve", params={"q": "taratala"})
    assert r.status_code == 503 and r.json() == {"detail": osint_router.RESOLVER_NOT_DEPLOYED}


# ── FIX-B: context sources apart; the held counts by reason ──────────────────


def _context_pair(tag: str) -> tuple[Any, Any]:
    """A street report (fictional news publisher) and the district SACHET alert in effect there."""
    from fixtures.osint.signals import rekey

    sets = canonical_set(tag)
    alert = sets["sachet_district"]
    report = rekey(sets["em_bypass"][0], f"{tag}-storm", title="Thunderstorm uproots trees on EM Bypass near Kasba",
                   text="Thunderstorm uproots trees on EM Bypass near Kasba; traffic slowed.",
                   published_at=alert.published_at + timedelta(minutes=30), pii_redactions=0)
    return report, alert


@pytest.mark.parametrize("kind", BACKENDS)
async def test_the_dossier_lists_context_sources_apart_never_as_corroboration(kind):
    tag = new_tag()
    report, alert = _context_pair(tag)
    async with backend(kind, tag) as bk:
        bk.track(report, alert)
        pipe = FakePipeline(tag)
        pipe.groups = {report.signal_id: "storm", alert.signal_id: "storm"}
        app = make_app(bk.pool, pipe)
        async with client(app) as c:
            r = await c.post("/api/v1/osint/signals", json={"signals": [payload(report), payload(alert)]})
            assert r.status_code == 200, r.text
            (sit,) = r.json()["resolved"]
            body = (await c.get(f"/api/v1/osint/events/{sit['osint_event_id']}")).json()
            city = (await c.get("/api/v1/city/entities", params={"kinds": "osint_event"})).json()
        # the situation stands on the street report alone ...
        assert [s["signal_id"] for s in body["sources"]] == [report.signal_id]
        assert [n["signal_id"] for n in body["source_notes"]] == [report.signal_id]
        # ... the district warning in effect there is listed apart, as context
        (ctx,) = body["context_sources"]
        SourceRef.model_validate(ctx)
        assert ctx["signal_id"] == alert.signal_id and ctx["role"] == "context"
        assert body["context_notes"] == [{"signal_id": alert.signal_id, "source_tier": "official",
                                          "publisher": "sachet.ndma.gov.in", "note": "District warning in effect",
                                          "link_note": None}]
        event = body["event"]
        assert event["verification_state"] == "NEWS-REPORTED"  # never verified by the context alert
        assert event["independent_publishers"] == 1 and event["source_tiers"] == ["aggregator"]
        assert event["credibility"] == pytest.approx(0.6)
        prov = body["provenance"]
        assert prov["publishers"] == ["news-a.example"] and prov["source_feeds"] == ["google_news_rss"]
        assert prov["context_publishers"] == ["sachet.ndma.gov.in"]
        assert prov["context_note"] == "District warning in effect"
        # the city picture carries the same provenance: the alert is never one of the situation's sources
        (ent,) = [e for e in city["entities"] if e["id"] == sit["osint_event_id"]]
        assert ent["props"]["provenance"]["publishers"] == ["news-a.example"]
        assert ent["props"]["provenance"]["context_publishers"] == ["sachet.ndma.gov.in"]
        ethics.assert_no_person_keys(body)


@pytest.mark.parametrize("kind", BACKENDS)
async def test_held_social_single_source_counts_the_aggregate_only_reason(kind):
    from fixtures.osint.signals import rekey
    from osint_common.testing import social_single_signal

    tag = new_tag()
    since = (datetime.now(UTC) - timedelta(seconds=5)).isoformat().replace("+00:00", "Z")
    post = rekey(social_single_signal(), tag)  # one post: the aggregate-only rule
    chatter = rekey(social_single_signal(), f"{tag}-chat", title="Evening at Taratala, nice weather",
                    text="Evening at Taratala, nice weather today.")  # social, but not an event class
    async with backend(kind, tag) as bk:
        bk.track(post, chatter)
        pipe = FakePipeline(tag)
        pipe.groups = {post.signal_id: "post", chatter.signal_id: "chatter"}  # two situations
        app = make_app(bk.pool, pipe)
        async with client(app) as c:
            r = await c.post("/api/v1/osint/signals", json={"signals": [payload(post), payload(chatter)]})
            assert r.status_code == 200, r.text
            held = (await c.get("/api/v1/osint/events", params={"since": since, "limit": 200})).json()["held"]
        # the pipeline's social_held is the broader count by design: every held, social-only situation
        assert r.json()["counts"]["social_held"] == 2
        if bk.db is not None:  # the fake holds this run only: exact
            assert held == {"social_single_source": 1, "not_event_class": 1, "outside_city": 0}
        else:
            assert held["social_single_source"] >= 1 and held["not_event_class"] >= 1


def test_held_buckets_match_the_pipelines_reasons_from_their_start():
    from traffic_oracle.osint import store

    assert store.held_bucket("single social source (aggregate-only rule)") == "social_single_source"
    assert store.held_bucket("Single social source (aggregate-only rule)") == "social_single_source"
    assert store.held_bucket("not an event class") == "not_event_class"
    assert store.held_bucket("state-level area: not located in the city") == "outside_city"
    assert store.held_bucket(store.WITHDRAWN_REASON) is None
    assert store.held_bucket(None) is None
    # a reason is never bucketed by a phrase inside another reason
    assert store.held_bucket("not an event class (chatter of a single social community)") == "not_event_class"


@pytest.mark.parametrize("kind", BACKENDS)
async def test_the_ingest_route_hands_the_live_state_the_apps_valkey(kind):
    """POST /api/v1/osint/signals passes ``app.state.adaptive_valkey`` to the live state: a C-B convoy frame
    there reaches the pipeline as an ACTIVE convoy ref at the frame's position (no other test goes through the
    route with a Valkey: the harness sets it to None)."""
    import uuid

    from fixtures.osint.fakedb import FakeValkey

    tag = new_tag()
    report = canonical_set(tag)["em_bypass"][0]
    mid = str(uuid.uuid4())  # a synthetic movement no store row names: a convoy in motion (C-B frames)
    frame = {"movement_id": mid, "event_id": None, "lon": 88.3961, "lat": 22.5262, "speed_kmh": 42.0,
             "heading": 180.0, "t": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
             "source": "emulated_gps", "progress": 0.4, "segment_id": 1035}
    async with backend(kind, tag) as bk:
        bk.track(report)
        pipe = FakePipeline(tag)
        app = make_app(bk.pool, pipe)
        app.state.adaptive_valkey = FakeValkey({f"convoy:position:{mid}": frame})
        async with client(app) as c:
            r = await c.post("/api/v1/osint/signals", json={"signals": [payload(report)]})
        assert r.status_code == 200, r.text
        live = pipe.lives[-1]
        assert live is not None
        (ref,) = [e for e in live.live_events if e.urn == f"convoy:{mid}"]
        assert (ref.event_kind, ref.status) == ("protected_movement", "active")
        assert (ref.lon, ref.lat) == pytest.approx((88.3961, 22.5262))
        assert ref.segment_ids == [1035]  # no route in the store: the frame's own segment
