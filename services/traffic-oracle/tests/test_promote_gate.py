"""POST /api/v1/osint/events/{id}/promote — the named-officer gate (C-T; OS-5).

Dual-mode (the fake store always; the sandbox database with ``OSINT_TEST_DSN``, where every corridor
event a test promotes is cancelled through the lifecycle and then deleted with the test's rows).

* 409 ``officer-required`` without an officer — for an existing AND for an unknown id, checked
  before any lookup; a header that did not come over loopback names no officer; 404 for an unknown
  id with an officer;
* 409 ``not-an-event`` (held), ``no-anchor`` (an area-level report), ``already-promoted`` (+event_id);
* success goes through ``events.create_event`` with ``source_kind`` 'osint', the verification state
  KEPT, a geotag inside the city box, the spine [1035] for the road-accident fixture (a junction-anchored one rides the
  segment entering its junction), and status ``active`` through the lifecycle, whose audit names the
  officer; the promotion is narrated in the city feed;
* the kind override never yields ``crime_incident`` or ``vehicle_pursuit`` (422);
* a direct ``POST /api/v1/events`` with ``source_kind`` 'osint' and no promotion flag is still refused
  (OS-1's rule);
* the callable OS-6 reuses: ``promote_osint_event`` (``dss_id`` lands in the provenance) and
  ``PromoteRefused``; an orphaned corridor event is adopted, never duplicated;
* a promoted situation NEVER corroborates its own corridor event — not when a later report re-fuses
  it against a live state that now holds that event, and not when it absorbed the promoted
  situation (it inherits the promotion instead): ``attach`` stays as it was and no ``corroborates``
  relation points at the event (``promoted_to`` does);
* promotions in flight are bounded (``MAX_CONCURRENT_PROMOTIONS``): they can never drain the pool.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi import Request

from fixtures.osint.harness import BACKENDS, backend, client, make_app, reset_osint_state
from fixtures.osint.signals import PLACES, FakePipeline, canonical_set, new_tag, payload, rekey
from traffic_oracle import events as events_mod
from traffic_oracle.osint import promote

#: the synthetic OSINT fixtures here predate the scope rule (tests/conftest.py)
SCOPE_GATE_OFF = True

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")

OFFICER = "Sandbox Officer"
UNKNOWN = "0b7e3c2a-2222-4d1e-9a8b-5c6d7e8f9a0b"



def _recent() -> dict:
    """Scope a list read to rows touched in the last hour (a seeded sandbox holds others)."""
    from datetime import UTC, datetime, timedelta

    since = (datetime.now(UTC) - timedelta(hours=1)).isoformat().replace("+00:00", "Z")
    return {"since": since, "limit": 200}

@pytest.fixture(autouse=True)
def _clean_state():
    reset_osint_state()
    yield
    reset_osint_state()


async def _seed(bk: Any, tag: str) -> tuple[Any, dict[str, str]]:
    sets = canonical_set(tag)
    signals = [*sets["em_bypass"], sets["gariahat"], sets["sachet_district"], sets["social"]]
    bk.track(*signals)
    app = make_app(bk.pool, FakePipeline(tag))
    async with client(app) as c:
        r = await c.post("/api/v1/osint/signals", json={"signals": [payload(s) for s in signals]})
    assert r.status_code == 200, r.text
    fake = FakePipeline(tag)
    by_fused = {i["fused_event_id"]: i["osint_event_id"] for i in r.json()["resolved"]}
    ids = {
        "em_bypass": by_fused[fake.fused_id(sets["em_bypass"][0].signal_id)],
        "gariahat": by_fused[fake.fused_id(sets["gariahat"].signal_id)],
        "sachet": by_fused[fake.fused_id(sets["sachet_district"].signal_id)],
        "social": by_fused[fake.fused_id(sets["social"].signal_id)],
    }
    return app, ids


async def _promote(app: Any, oid: str, *, header: str | None = OFFICER, body: dict | None = None,
                   base_url: str = "http://127.0.0.1") -> Any:
    from httpx import ASGITransport, AsyncClient

    headers = {"x-sajag-officer": header} if header else {}
    async with AsyncClient(transport=ASGITransport(app=app), base_url=base_url) as c:
        return await c.post(f"/api/v1/osint/events/{oid}/promote", json=body or {}, headers=headers)


async def _cancel(bk: Any, app: Any, event_id: str) -> None:
    bk.track_event(event_id)
    async with client(app) as c:
        r = await c.post(f"/api/v1/events/{event_id}/status",
                         json={"to_status": "cancelled", "officer": OFFICER, "note": "test cleanup"})
    # the lifecycle cancels it (the sandbox then deletes the test rows)
    assert r.status_code == 200, r.text
    assert r.json()["to_status"] == "cancelled"


async def _corridor(bk: Any, event_id: str) -> dict:
    if bk.db is not None:
        e = dict(bk.db.corridor[event_id])
        e["metadata"] = json.loads(e["metadata"])
        e["provenance"] = json.loads(e["provenance"]) if e["provenance"] else None
        e["spines"] = [r["segment_ids"] for r in bk.db.routes if str(r["event_id"]) == event_id]
        e["log"] = [(x["from_status"], x["to_status"], x["actor"], x["note"])
                    for x in bk.db.status_log if str(x["event_id"]) == event_id]
        return e
    async with bk.pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT event_kind, status, title, metadata, source_kind, credibility, verification_state, "
            "provenance, ST_X(geotag) AS geotag_lon, ST_Y(geotag) AS geotag_lat "
            "FROM events.corridor_events WHERE event_id = $1::uuid", event_id)
        spines = await conn.fetch(
            "SELECT segment_ids FROM events.event_routes WHERE event_id = $1::uuid ORDER BY route_rank", event_id)
        log = await conn.fetch(
            "SELECT from_status, to_status, actor, note FROM events.event_status_log "
            "WHERE event_id = $1::uuid ORDER BY seq", event_id)
    e = dict(row)
    e["metadata"] = json.loads(e["metadata"])
    e["provenance"] = json.loads(e["provenance"]) if e["provenance"] else None
    e["spines"] = [list(r["segment_ids"]) for r in spines]
    e["log"] = [(r["from_status"], r["to_status"], r["actor"], r["note"]) for r in log]
    return e


# ── the officer first, before any lookup ─────────────────────────────────────


@pytest.mark.parametrize("kind", BACKENDS)
async def test_officer_required_for_an_existing_and_an_unknown_id(kind):
    tag = new_tag()
    async with backend(kind, tag) as bk:
        app, ids = await _seed(bk, tag)
        before = len(bk.conn.calls) if bk.conn is not None else 0
        for oid in (ids["em_bypass"], UNKNOWN, "not-a-uuid"):
            r = await _promote(app, oid, header=None)
            assert r.status_code == 409, (oid, r.text)
            assert r.json()["detail"] == "officer-required"
            r = await _promote(app, oid, header=None, body={"officer": "   "})  # blank names nobody
            assert r.status_code == 409 and r.json()["detail"] == "officer-required"
        if bk.conn is not None:
            assert bk.conn.calls[before:] == []  # no lookup happened first


@pytest.mark.parametrize("kind", BACKENDS)
async def test_a_header_from_off_loopback_names_no_officer(kind):
    tag = new_tag()
    async with backend(kind, tag) as bk:
        app, ids = await _seed(bk, tag)
        r = await _promote(app, ids["em_bypass"], header=OFFICER, base_url="http://deck.example")
        assert r.status_code == 409 and r.json()["detail"] == "officer-required"


@pytest.mark.parametrize("kind", BACKENDS)
async def test_404_for_an_unknown_id_with_an_officer(kind):
    tag = new_tag()
    async with backend(kind, tag) as bk:
        app, _ = await _seed(bk, tag)
        assert (await _promote(app, UNKNOWN)).status_code == 404
        assert (await _promote(app, "not-a-uuid", header=None, body={"officer": OFFICER})).status_code == 404


async def test_malformed_officers_and_kinds_are_422():
    tag = new_tag()
    async with backend("fake", tag) as bk:
        app, ids = await _seed(bk, tag)
        assert (await _promote(app, ids["em_bypass"], header=None, body={"officer": "x"})).status_code == 422
        for kind_ in ("crime_incident", "vehicle_pursuit", "ufo"):
            r = await _promote(app, ids["em_bypass"], body={"event_kind": kind_})
            assert r.status_code == 422, kind_
        assert (await _promote(app, ids["em_bypass"], body={"note": "n" * 501})).status_code == 422
        assert (await _promote(app, ids["em_bypass"], body={"author": "x"})).status_code == 422


# ── the refusals ─────────────────────────────────────────────────────────────


@pytest.mark.parametrize("kind", BACKENDS)
async def test_not_an_event_no_anchor_and_already_promoted(kind):
    tag = new_tag()
    async with backend(kind, tag) as bk:
        app, ids = await _seed(bk, tag)
        r = await _promote(app, ids["social"])  # held: a single social source
        assert r.status_code == 409 and r.json()["detail"] == "not-an-event"
        r = await _promote(app, ids["sachet"])  # an area-level report: no road anchor
        assert r.status_code == 409 and r.json()["detail"] == "no-anchor"
        first = await _promote(app, ids["em_bypass"])
        assert first.status_code == 201, first.text
        event_id = first.json()["event_id"]
        try:
            again = await _promote(app, ids["em_bypass"], header="Another Officer")
            assert again.status_code == 409
            assert again.json()["detail"] == "already-promoted" and again.json()["event_id"] == event_id
        finally:
            await _cancel(bk, app, event_id)


# ── success ──────────────────────────────────────────────────────────────────


def test_geotag_is_the_point_inside_the_city_box():
    """A promoted event's geotag is the situation's representative point, only inside the city box
    (``events.GEOTAG_BBOX``: the Mumbai bbox of cities/mumbai/city.json)."""
    assert events_mod.GEOTAG_BBOX == (72.77, 18.89, 72.99, 19.28)
    assert promote._geotag({"rep_lon": 72.8481, "rep_lat": 19.0175}) == {"lon": 72.8481, "lat": 19.0175}  # Dadar TT
    for lon, lat in ((72.70, 19.00), (72.85, 19.35), (77.21, 28.61), (None, 19.02), (72.85, None)):
        assert promote._geotag({"rep_lon": lon, "rep_lat": lat}) is None, (lon, lat)




@pytest.mark.parametrize("kind", BACKENDS)
async def test_success_creates_an_osint_event_and_activates_it(kind, monkeypatch):
    tag = new_tag()
    created: list[Any] = []
    real_create = events_mod.create_event

    async def spy(req, request):
        created.append((req, getattr(request.state, "osint_promotion", None)))
        return await real_create(req, request)

    monkeypatch.setattr(events_mod, "create_event", spy)
    async with backend(kind, tag) as bk:
        app, ids = await _seed(bk, tag)
        r = await _promote(app, ids["em_bypass"], body={"note": "patrol confirms one lane blocked"})
        assert r.status_code == 201, r.text
        body = r.json()
        event_id = body["event_id"]
        try:
            assert {k: body[k] for k in ("osint_event_id", "event_kind", "status", "verification_state",
                                         "source_kind")} == {
                "osint_event_id": ids["em_bypass"], "event_kind": "road_accident", "status": "active",
                "verification_state": "NEWS-REPORTED", "source_kind": "osint",
            }
            (req, flag), = created
            assert flag is True and req.source_kind == "osint"  # through create_event, flag set
            e = await _corridor(bk, event_id)
            assert e["status"] == "active" and e["event_kind"] == "road_accident"
            assert e["source_kind"] == "osint" and e["verification_state"] == "NEWS-REPORTED"
            assert e["credibility"] == pytest.approx(0.65, abs=1e-6)
            # the geotag is the situation's point when it lies inside the city box (events.GEOTAG_BBOX,
            # the Mumbai bbox), never a point outside it (test_geotag_is_the_point_inside_the_city_box)
            lon, lat = PLACES["em_bypass"]["lon"], PLACES["em_bypass"]["lat"]
            if promote._geotag({"rep_lon": lon, "rep_lat": lat}) is not None:
                # (the store keeps the geotag to 1e-5 degrees, about a metre)
                assert (e["geotag_lon"], e["geotag_lat"]) == pytest.approx((lon, lat), abs=1e-5)
            else:
                assert e["geotag_lon"] is None and e["geotag_lat"] is None
            assert e["spines"] == [[1035]]
            assert e["metadata"] == {"source": "osint", "osint_event_id": ids["em_bypass"]}
            prov = e["provenance"]
            assert prov["osint_event_id"] == ids["em_bypass"] and prov["source_url"] is None
            assert prov["source_feeds"] == ["google_news_rss"] and prov["dss_id"] is None
            assert prov["publishers"] == ["news-a.example", "news-b.example"]
            assert prov["source_url_note"] and prov["geocoder"] == "gazetteer_exact"
            # the lifecycle audit names the officer: created, then activated, by them
            assert e["log"][0][:3] == (None, "planning", OFFICER)
            assert e["log"][1][:3] == ("planning", "active", OFFICER)
            assert "patrol confirms one lane blocked" in e["log"][1][3]
            async with client(app) as c:
                listed = (await c.get("/api/v1/osint/events", params=_recent())).json()["events"]
                feed = (await c.get("/api/v1/city/feed?kinds=osint,event&limit=500")).json()["items"]
            crash = next(x for x in listed if x["osint_event_id"] == ids["em_bypass"])
            assert crash["promoted_event_id"] == event_id
            promo = next(i for i in feed if i["id"] == f"osint_promotion:{event_id}")
            assert promo["text"].startswith(f"Promoted to a corridor event by {OFFICER}")
            assert promo["actor_kind"] == "human" and promo["source"] == "osint"
            assert promo["verification_state"] == "NEWS-REPORTED"
            own = [i for i in feed if f"event:{event_id}" in i["urns"] and i["kind"] == "event"]
            assert own and all(i["source"] == "osint" for i in own)  # never passes for live
        finally:
            await _cancel(bk, app, event_id)


@pytest.mark.parametrize("kind", BACKENDS)
async def test_a_junction_anchored_situation_rides_the_segment_entering_it(kind):
    tag = new_tag()
    async with backend(kind, tag) as bk:
        app, ids = await _seed(bk, tag)
        r = await _promote(app, ids["gariahat"], header=None, body={"officer": OFFICER})
        assert r.status_code == 201, r.text
        event_id = r.json()["event_id"]
        try:
            e = await _corridor(bk, event_id)
            assert e["spines"] == [[1033]]  # the lowest segment entering junction 23 (Gariahat crossing)
            assert e["event_kind"] == "reported_crime" and e["status"] == "active"
            assert e["log"][1][2] == OFFICER  # the body officer, no header
        finally:
            await _cancel(bk, app, event_id)


@pytest.mark.parametrize("kind", BACKENDS)
async def test_the_kind_override(kind):
    tag = new_tag()
    async with backend(kind, tag) as bk:
        app, ids = await _seed(bk, tag)
        r = await _promote(app, ids["em_bypass"], body={"event_kind": "public_disorder"})
        assert r.status_code == 201, r.text
        try:
            assert r.json()["event_kind"] == "public_disorder"
            assert (await _corridor(bk, r.json()["event_id"]))["event_kind"] == "public_disorder"
        finally:
            await _cancel(bk, app, r.json()["event_id"])


# ── OS-1's rule still holds; the callable for OS-6 ───────────────────────────


async def test_a_direct_osint_event_post_is_still_refused():
    async with backend("fake", new_tag()) as bk:
        app = make_app(bk.pool)
        async with client(app) as c:
            r = await c.post("/api/v1/events", json={
                "event_kind": "road_accident", "title": "forged", "route_spines": [{"segment_ids": [1035]}],
                "source_kind": "osint", "credibility": 0.9, "verification_state": "NEWS-REPORTED",
            })
        assert r.status_code == 422 and r.json()["detail"] == events_mod.OSINT_PROMOTION_ONLY
        assert bk.db.corridor == {}


def test_promote_refused_codes_and_body():
    assert promote.REFUSAL_CODES == ("officer-required", "already-promoted", "no-anchor", "not-an-event")
    exc = promote.PromoteRefused("already-promoted", event_id="e1")
    assert exc.code == "already-promoted" and exc.body()["detail"] == "already-promoted"
    assert exc.body()["event_id"] == "e1" and exc.response().status_code == 409
    with pytest.raises(ValueError):
        promote.PromoteRefused("officer-missing")
    assert "crime_incident" not in promote.PROMOTABLE_KINDS and "vehicle_pursuit" not in promote.PROMOTABLE_KINDS
    assert len(promote.PROMOTABLE_KINDS) == 14


@pytest.mark.parametrize("kind", BACKENDS)
async def test_the_callable_os6_reuses_records_the_dss_id(kind):
    tag = new_tag()
    dss_id = str(uuid.uuid4())
    async with backend(kind, tag) as bk:
        app, ids = await _seed(bk, tag)

        @app.post("/test-only/approve/{oid}")
        async def approve(oid: str, request: Request) -> Any:  # what OS-6's decision route does
            try:
                return await promote.promote_osint_event(request, oid, officer=OFFICER, dss_id=dss_id)
            except promote.PromoteRefused as exc:
                return exc.response()

        async with client(app) as c:
            r = await c.post(f"/test-only/approve/{ids['em_bypass']}")
            assert r.status_code == 200, r.text
            event_id = r.json()["event_id"]
            try:
                assert r.json()["status"] == "active"
                assert (await _corridor(bk, event_id))["provenance"]["dss_id"] == dss_id
                again = await c.post(f"/test-only/approve/{ids['em_bypass']}")
                assert again.status_code == 409 and again.json()["event_id"] == event_id
            finally:
                await _cancel(bk, app, event_id)


async def test_an_orphaned_corridor_event_is_adopted_never_duplicated():
    tag = new_tag()
    async with backend("fake", tag) as bk:
        app, ids = await _seed(bk, tag)
        orphan = str(uuid.uuid4())
        from datetime import UTC, datetime

        bk.db.corridor[orphan] = {
            "event_id": uuid.UUID(orphan), "event_kind": "road_accident", "status": "planning",
            "title": "x", "description": "", "metadata": json.dumps({"source": "osint", "osint_event_id": ids["em_bypass"]}),
            "source_kind": "osint", "credibility": 0.65, "verification_state": "NEWS-REPORTED",
            "provenance": None, "created_at": datetime.now(UTC), "updated_at": datetime.now(UTC),
            "actual_start": None, "actual_end": None,
        }
        r = await _promote(app, ids["em_bypass"])
        assert r.status_code == 201 and r.json()["event_id"] == orphan
        assert len(bk.db.corridor) == 1 and bk.db.corridor[orphan]["status"] == "active"


# ── a promoted situation never corroborates its own corridor event ───────────


async def _post_signals(app: Any, signals: list[Any]) -> Any:
    async with client(app) as c:
        return await c.post("/api/v1/osint/signals", json={"signals": [payload(s) for s in signals]})


async def _views(app: Any, oid: str) -> tuple[dict, dict, dict]:
    """``(GET /osint/events/{oid} body, city dossier body, the city snapshot entity)``."""
    async with client(app) as c:
        own = await c.get(f"/api/v1/osint/events/{oid}")
        city = await c.get(f"/api/v1/city/entity/osint_event/{oid}")
        snap = await c.get("/api/v1/city/entities", params={"kinds": "osint_event"})
    assert own.status_code == 200 and city.status_code == 200 and snap.status_code == 200
    entity = next(e for e in snap.json()["entities"] if e["kind"] == "osint_event" and e["id"] == oid)
    return own.json(), city.json(), entity


def _assert_never_self_corroborated(event_id: str, own: dict, city: dict, entity: dict, before: dict) -> None:
    mine = f"event:{event_id}"
    for attach in (own["event"]["attach"], city["entity"]["props"]["attach"], entity["props"]["attach"]):
        assert attach == before and attach["corroborates_live_urn"] != mine
    rels = [(x["relation"], x["entity"]["urn"]) for x in city["related"]]
    assert ("promoted_to", mine) in rels
    assert ("corroborates", mine) not in rels
    assert own["event"]["promoted_event_id"] == event_id and entity["links"].count(mine) == 1


@pytest.mark.parametrize("kind", BACKENDS)
async def test_a_promoted_situation_never_corroborates_its_own_event(kind):
    tag = new_tag()
    sets = canonical_set(tag)
    late = rekey(sets["em_bypass"][1], tag + "-late")  # one more report of the same crash, after promotion
    async with backend(kind, tag) as bk:
        app, ids = await _seed(bk, tag)
        oid = ids["em_bypass"]
        before = (await _views(app, oid))[0]["event"]["attach"]
        r = await _promote(app, oid)
        assert r.status_code == 201, r.text
        event_id = r.json()["event_id"]
        try:
            bk.track(late)
            pipe = FakePipeline(tag)
            app = make_app(bk.pool, pipe)
            ingest = await _post_signals(app, [late])
            assert ingest.status_code == 200, ingest.text
            (grown,) = [x for x in ingest.json()["resolved"] if x["osint_event_id"] == oid]
            assert grown["source_count"] == 6
            # the re-fusion DID see the promoted event live on segment 1035 (the fake attach then
            # names it) — the store records that attach as novel
            live = {e.urn: e for e in pipe.lives[-1].live_events}
            assert f"event:{event_id}" in live and 1035 in live[f"event:{event_id}"].segment_ids
            _assert_never_self_corroborated(event_id, *(await _views(app, oid)), before)
            if bk.db is not None:  # the fake holds this run only: exact
                assert before == {"novel": True, "corroborates_live_urn": None}
                assert ingest.json()["counts"]["attached_to_live"] == 0  # the counts say what was stored
        finally:
            await _cancel(bk, app, event_id)


@pytest.mark.parametrize("kind", BACKENDS)
async def test_an_absorber_inherits_the_promotion_and_never_corroborates_it(kind):
    tag = new_tag()
    base = canonical_set(tag)["em_bypass"][0]
    t0 = datetime(2026, 10, 20, 13, 0, tzinfo=UTC)

    def sig(n: int, clusters: list[str], minutes: int) -> Any:
        return rekey(base, f"{tag}-k{n}", published_at=t0 + timedelta(minutes=minutes),
                     category_hint=[f"cluster:{c}" for c in clusters])

    a, c, bridge = sig(1, ["k1@em_bypass"], 0), sig(2, ["k2@em_bypass"], 5), sig(3, ["k1@em_bypass", "k2@em_bypass"], 9)
    async with backend(kind, tag) as bk:
        bk.track(a, c, bridge)
        pipe = FakePipeline(tag)
        app = make_app(bk.pool, pipe)
        first = await _post_signals(app, [a, c])  # two situations at segment 1035
        assert first.status_code == 200, first.text
        ids = {r["fused_event_id"]: r["osint_event_id"] for r in first.json()["resolved"]}
        a_id, c_id = ids[pipe.fused_id(a.signal_id)], ids[pipe.fused_id(c.signal_id)]
        before = (await _views(app, a_id))[0]["event"]["attach"]
        r = await _promote(app, c_id)
        assert r.status_code == 201, r.text
        event_id = r.json()["event_id"]
        try:
            merged = await _post_signals(app, [bridge])  # one report links the two: A absorbs C
            assert merged.status_code == 200, merged.text
            assert merged.json()["superseded"] == [{"osint_event_id": c_id, "superseded_by": a_id}]
            _assert_never_self_corroborated(event_id, *(await _views(app, a_id)), before)
            again = await _promote(app, a_id)  # inherited: never promoted twice
            assert again.status_code == 409 and again.json()["detail"] == "already-promoted"
            assert again.json()["event_id"] == event_id
        finally:
            await _cancel(bk, app, event_id)


async def test_concurrent_promotions_are_bounded(monkeypatch):
    tag = new_tag()
    base = canonical_set(tag)["em_bypass"][0]
    signals = [rekey(base, f"{tag}-p{n}", category_hint=[f"cluster:p{n}@em_bypass"]) for n in range(6)]
    async with backend("fake", tag) as bk:
        app = make_app(bk.pool, FakePipeline(tag))
        r = await _post_signals(app, signals)
        oids = [x["osint_event_id"] for x in r.json()["resolved"]]
        assert len(oids) == 6
        in_flight = peak = 0
        real_create = events_mod.create_event

        async def slow_create(req, request):
            nonlocal in_flight, peak
            in_flight += 1
            peak = max(peak, in_flight)
            try:
                await asyncio.sleep(0.02)
                return await real_create(req, request)
            finally:
                in_flight -= 1

        monkeypatch.setattr(events_mod, "create_event", slow_create)
        results = await asyncio.gather(*(_promote(app, oid) for oid in oids))
        assert [x.status_code for x in results] == [201] * 6
        assert 2 <= peak <= promote.MAX_CONCURRENT_PROMOTIONS  # concurrent, never more than the gate
        assert len({x.json()["event_id"] for x in results}) == 6
