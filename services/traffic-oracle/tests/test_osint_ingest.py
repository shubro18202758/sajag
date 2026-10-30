"""POST /api/v1/osint/signals — the trust boundary, the ethics rails and re-fusion (C-T; OS-5).

Every test runs against the in-memory fake store and, when ``OSINT_TEST_DSN`` names a sandbox
(int3c / int3cl), against that database too — writing only its own rows (run-unique signal ids,
fused ids prefixed ``test-<uuid>``) and deleting them afterwards.  The pipeline is the deterministic
fake of ``fixtures/osint/signals.py`` (OS-3 / OS-4 build the real one in this wave; the integration
test covers it).

* a forbidden key at any depth → ``rejected: forbidden_key``, nothing stored; a surviving PII
  pattern → ``pii_unredacted``;
* a ``reddit_rss`` signal labelled ``OFFICIAL-VERIFIED`` with prior 0.95 is stored and fused as
  ``UNVERIFIED-OSINT`` with its SOURCE_PRIORS values (plan R26) — a caller cannot mint an official
  situation; a self-declared ``EMULATED`` label is kept (it only lowers trust);
* a news/social signal's raw URL is never stored (a URL-shaped source id is stored hashed); an
  official one keeps its URL;
* duplicates are counted; the window is re-fused; ``osint_event_id`` is stable when a corroborating
  signal arrives; ``superseded_by`` is set on a merge;
* the window cap takes WHOLE units: a situation that does not fit is left out with its row, links
  and ``osint_event_id`` untouched (never re-fused half-seen), and joins again once it fits; a
  promotion that commits while the pipeline runs is still inherited by the absorber;
* 503 "osint pipeline not deployed" when ``get_pipeline`` raises — nothing stored; a failing pipeline
  rolls the whole batch back.
"""

from __future__ import annotations

import hashlib
import sys
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from fixtures.osint.harness import BACKENDS, backend, client, make_app, reset_osint_state
from fixtures.osint.signals import FakePipeline, canonical_set, new_tag, payload, rekey
from osint_common import ethics, kinds
from osint_common.testing import social_single_signal
from osint_common.types import RawOsintSignal
from traffic_oracle.osint import ingest, live_state, store

#: the synthetic OSINT fixtures here predate the scope rule (tests/conftest.py)
SCOPE_GATE_OFF = True

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")



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


async def _stored(bk: Any, signal_id: str) -> dict | None:
    if bk.db is not None:
        return bk.db.signals.get(signal_id)
    async with bk.pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM osint.raw_signals WHERE signal_id = $1", signal_id)
    return dict(row) if row else None


async def _event_by_fused(bk: Any, fused: str) -> dict | None:
    if bk.db is not None:
        return next((dict(r) for r in bk.db.events.values() if r["fused_event_id"] == fused), None)
    async with bk.pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM osint.resolved_events WHERE fused_event_id = $1", fused)
    return dict(row) if row else None


async def _post(app: Any, signals: list[Any], **kw: Any) -> Any:
    body = {"signals": [s if isinstance(s, dict) else payload(s) for s in signals], **kw}
    async with client(app) as c:
        return await c.post("/api/v1/osint/signals", json=body)


# ── ethics rails at the trust boundary ───────────────────────────────────────


@pytest.mark.parametrize("kind", BACKENDS)
async def test_forbidden_key_at_any_depth_is_rejected_and_never_stored(kind):
    tag = new_tag()
    good = canonical_set(tag)["gariahat"]
    planted = payload(rekey(good, tag + "-planted"))
    planted["raw_geo_hint"]["deep"] = {"items": [{"victim_name": "x"}]}  # any depth
    async with backend(kind, tag) as bk:
        bk.track(good)
        pipe = FakePipeline(tag)
        r = await _post(make_app(bk.pool, pipe), [planted, good])
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["accepted"] == 1
        assert body["rejected"] == [{"signal_id": planted["signal_id"], "reason": "forbidden_key"}]
        assert await _stored(bk, planted["signal_id"]) is None
        assert planted["signal_id"] not in {s.signal_id for s in pipe.calls[-1]}


@pytest.mark.parametrize("kind", BACKENDS)
async def test_surviving_pii_is_rejected_and_never_stored(kind):
    tag = new_tag()
    base = canonical_set(tag)["gariahat"]
    leaky = payload(rekey(base, tag + "-pii"))
    leaky["text"] = leaky["text"] + " A 45-year-old shopkeeper was hurt."
    async with backend(kind, tag) as bk:
        r = await _post(make_app(bk.pool, FakePipeline(tag)), [leaky])
        assert r.status_code == 200, r.text
        assert r.json()["rejected"] == [{"signal_id": leaky["signal_id"], "reason": "pii_unredacted"}]
        assert r.json()["accepted"] == 0
        assert await _stored(bk, leaky["signal_id"]) is None


def test_screen_signal_reasons_and_safe_echo():
    tag = new_tag()
    good = payload(canonical_set(tag)["gariahat"])
    assert ingest.screen_signal(good)[1] is None
    assert ingest.screen_signal({**good, "author": "x"})[1] == "forbidden_key"
    assert ingest.screen_signal({**good, "title": "Accident; a 45-year-old hurt"})[1] == "pii_unredacted"
    assert ingest.screen_signal({**good, "signal_id": "0" * 40})[1] == "invalid"
    assert ingest.screen_signal({**good, "unknown_field": 1})[1] == "invalid"
    # a rejected signal's id is echoed only when it IS a signal id — never free text
    assert ingest._echo_id({"signal_id": "Mr Somebody"}) is None
    assert ingest._echo_id({"signal_id": "a" * 40}) == "a" * 40


# ── the trust boundary (plan R26) ────────────────────────────────────────────


@pytest.mark.parametrize("kind", BACKENDS)
async def test_reddit_labelled_official_is_stored_and_fused_as_unverified(kind):
    tag = new_tag()
    posts = [
        rekey(social_single_signal(), f"{tag}-{n}", category_hint=["subreddit:example_city", "cluster:taratala"])
        for n in range(2)
    ]
    forged = [
        payload(p, source_tier="official", provenance_label="OFFICIAL-VERIFIED",
                credibility_prior=0.95, license="public_domain", redistributable=True)
        for p in posts
    ]
    prior = kinds.SOURCE_PRIORS["reddit_rss"]
    async with backend(kind, tag) as bk:
        bk.track(*posts)
        pipe = FakePipeline(tag)
        app = make_app(bk.pool, pipe)
        r = await _post(app, forged)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["accepted"] == 2 and body["trust_boundary"]["payload_disagreed"] == 2
        for p in posts:
            row = await _stored(bk, p.signal_id)
            assert row["provenance_label"] == "UNVERIFIED-OSINT"
            assert row["source_tier"] == "social_unverified"
            assert abs(row["credibility_prior"] - prior.credibility_prior) < 1e-6
            assert row["license"] == prior.license and row["redistributable"] is False
            assert row["url"] is None  # a social link is never stored
        fused_in = {s.signal_id: s for s in pipe.calls[-1]}
        for p in posts:
            s = fused_in[p.signal_id]
            assert (s.provenance_label, s.credibility_prior, s.source_tier) == (
                "UNVERIFIED-OSINT", prior.credibility_prior, "social_unverified")
        (sit,) = body["resolved"]
        assert sit["verification_state"] == "UNVERIFIED-OSINT" and sit["credibility"] <= 0.30
        async with client(app) as c:
            listed = (await c.get("/api/v1/osint/events", params=_recent())).json()["events"]
        mine = [e for e in listed if e["fused_event_id"].startswith(tag)]
        assert mine and all(e["verification_state"] != "OFFICIAL-VERIFIED" for e in mine)


def test_prepare_signal_keeps_a_self_declared_synthetic_label_only():
    tag = new_tag()
    news = canonical_set(tag)["em_bypass"][0]
    emulated = RawOsintSignal.model_validate({**news.model_dump(), "provenance_label": "EMULATED"})
    p = ingest.prepare_signal(emulated)
    assert p.signal.provenance_label == "EMULATED" and p.disagreed  # lowers trust: kept
    official = RawOsintSignal.model_validate({**news.model_dump(), "provenance_label": "OFFICIAL-VERIFIED"})
    p = ingest.prepare_signal(official)
    assert p.signal.provenance_label == "NEWS-REPORTED" and p.disagreed  # raises trust: refused
    assert p.signal.url is None and p.url_withheld  # a news link is withheld
    untouched = ingest.prepare_signal(news)
    assert not untouched.disagreed


@pytest.mark.parametrize("kind", BACKENDS)
async def test_news_and_social_links_are_never_stored_official_ones_are(kind):
    tag = new_tag()
    sets = canonical_set(tag)
    news = sets["em_bypass"][0]
    url_id = rekey(news, tag, source="gdelt_doc", source_tier="news_regional")
    url_id = RawOsintSignal.model_validate({
        **url_id.model_dump(),
        "source_id": "https://news-a.example/city/a-named-person-slug-123",
        "signal_id": hashlib.sha1(b"gdelt_doc:https://news-a.example/city/a-named-person-slug-123").hexdigest(),
        "raw": {},
    })
    sachet = rekey(sets["sachet_district"], tag, url="https://sachet.ndma.gov.in/cap_public_website/FetchXMLFile?identifier=x1")
    async with backend(kind, tag) as bk:
        bk.track(news, url_id, sachet)
        r = await _post(make_app(bk.pool, FakePipeline(tag)), [news, url_id, sachet])
        assert r.status_code == 200, r.text
        assert r.json()["trust_boundary"]["urls_withheld"] == 2
        assert (await _stored(bk, news.signal_id))["url"] is None
        stored = await _stored(bk, url_id.signal_id)
        assert stored["url"] is None
        assert stored["source_id"].startswith(store.HASHED_SOURCE_ID_PREFIX)
        assert "named-person" not in stored["source_id"]
        assert stored["source_id"] == store.HASHED_SOURCE_ID_PREFIX + hashlib.sha256(
            b"https://news-a.example/city/a-named-person-slug-123").hexdigest()
        assert (await _stored(bk, sachet.signal_id))["url"].startswith("https://sachet.ndma.gov.in/")
        # the hashed row is still re-fusable
        rebuilt = store.signal_from_row(stored)
        assert rebuilt is not None and rebuilt.signal_id == url_id.signal_id


# ── storage, duplicates, re-fusion, identity, merges ─────────────────────────


@pytest.mark.parametrize("kind", BACKENDS)
async def test_duplicates_are_counted_and_never_overwritten(kind):
    tag = new_tag()
    sig = canonical_set(tag)["gariahat"]
    async with backend(kind, tag) as bk:
        bk.track(sig)
        app = make_app(bk.pool, FakePipeline(tag))
        first = (await _post(app, [sig], run_id="run-1")).json()
        second = await _post(app, [sig, sig], run_id="run-2")
        assert second.status_code == 200, second.text
        assert (first["accepted"], first["duplicates"]) == (1, 0)
        assert (second.json()["accepted"], second.json()["duplicates"]) == (0, 2)
        assert (await _stored(bk, sig.signal_id))["run_id"] == "run-1"


@pytest.mark.parametrize("kind", BACKENDS)
async def test_window_is_refused_and_the_situation_id_is_stable(kind):
    tag = new_tag()
    crash = canonical_set(tag)["em_bypass"]
    anchor, corroborating = crash[0], crash[1]
    async with backend(kind, tag) as bk:
        bk.track(*crash)
        pipe = FakePipeline(tag)
        app = make_app(bk.pool, pipe)
        one = (await _post(app, [anchor])).json()
        two = (await _post(app, [corroborating])).json()
        # the second batch re-fused the window: the earlier report is in it
        assert {anchor.signal_id, corroborating.signal_id} <= {s.signal_id for s in pipe.calls[-1]}
        (a,) = one["resolved"]
        (b,) = two["resolved"]
        assert a["osint_event_id"] == b["osint_event_id"] and a["fused_event_id"] == b["fused_event_id"]
        assert (a["source_count"], b["source_count"]) == (1, 2)
        assert b["credibility"] == pytest.approx(0.65)  # two independent publishers
        row = await _event_by_fused(bk, b["fused_event_id"])
        assert row["superseded_by"] is None and row["source_count"] == 2


@pytest.mark.parametrize("kind", BACKENDS)
async def test_a_merge_supersedes_the_absorbed_situation(kind):
    tag = new_tag()
    base = canonical_set(tag)["gariahat"]
    t0 = datetime(2026, 10, 20, 10, 0, tzinfo=UTC)

    def sig(n: int, clusters: list[str], minutes: int) -> RawOsintSignal:
        return rekey(base, f"{tag}-m{n}", published_at=t0 + timedelta(minutes=minutes),
                     category_hint=[f"cluster:{c}" for c in clusters])

    a, c, bridge = sig(1, ["m1@taratala"], 0), sig(2, ["m2@taratala"], 5), sig(3, ["m1@taratala", "m2@taratala"], 9)
    async with backend(kind, tag) as bk:
        bk.track(a, c, bridge)
        app = make_app(bk.pool, FakePipeline(tag))
        first = (await _post(app, [a, c])).json()
        ids = {r["fused_event_id"]: r["osint_event_id"] for r in first["resolved"]}
        assert len(ids) == 2
        merged = (await _post(app, [bridge])).json()
        (survivor,) = merged["resolved"]
        assert survivor["source_count"] == 3
        absorbed = next(oid for oid in ids.values() if oid != survivor["osint_event_id"])
        assert merged["superseded"] == [{"osint_event_id": absorbed, "superseded_by": survivor["osint_event_id"]}]
        gone = next(f for f, oid in ids.items() if oid == absorbed)
        row = await _event_by_fused(bk, gone)
        assert str(row["superseded_by"]) == survivor["osint_event_id"]
        async with client(app) as cl:
            assert (await cl.get(f"/api/v1/osint/events/{absorbed}")).status_code == 404


# ── the window cap: whole units only ─────────────────────────────────────────


def test_plan_window_takes_whole_units_only():
    seeds = [("b_dup", True), ("b_new", True), ("x1", False), ("f1", False), ("x3", False), ("f2", False)]
    memberships = [("X", f"x{i}") for i in range(1, 6)] + [("Y", "b_dup"), ("Y", "y2")]
    plan = store.plan_window(seeds, memberships, 4)
    # the batch's new report first, then the batch's own situation Y (whole), then by seed order:
    # X (5 reports) does not fit the 1 left — skipped WHOLE; f1 fits; f2 no longer does
    assert set(plan.signal_ids) == {"b_new", "b_dup", "y2", "f1"}
    assert (plan.units, plan.truncated_units, plan.truncated_signals) == (3, 2, 6)
    assert plan.situated == {plan.unit_of["b_dup"]} and plan.unit_of["b_dup"] == plan.unit_of["y2"]
    assert not {"x1", "x2", "x3", "x4", "x5"} & set(plan.signal_ids)
    # two situations sharing a member are ONE unit: both whole, or neither
    shared = [("P", "p1"), ("P", "both"), ("Q", "both"), ("Q", "q1")]
    assert set(store.plan_window([("p1", False)], shared, 3).signal_ids) == {"p1", "both", "q1"}
    tight = store.plan_window([("p1", False), ("lone", False)], shared, 2)
    assert tight.signal_ids == ["lone"] and (tight.truncated_units, tight.truncated_signals) == (1, 3)


async def _situation_state(bk: Any, oid: str) -> dict:
    """A situation's row, its links and its members' geocodes, exactly as stored."""
    if bk.db is not None:
        members = bk.db.members(oid)
        sids = {s for s, _ in members}
        return {"row": dict(bk.db.events[oid]), "links": members,
                "geocodes": sorted(g["signal_id"] for g in bk.db.geocodes if g["signal_id"] in sids)}
    async with bk.pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM osint.resolved_events WHERE osint_event_id = $1::uuid", oid)
        links = await conn.fetch("SELECT signal_id, role FROM osint.event_sources WHERE osint_event_id = $1::uuid "
                                 "ORDER BY signal_id", oid)
        geos = await conn.fetch("SELECT g.signal_id FROM osint.geocodes g JOIN osint.event_sources es ON "
                                "es.signal_id = g.signal_id WHERE es.osint_event_id = $1::uuid ORDER BY 1", oid)
    return {"row": dict(row), "links": sorted((r["signal_id"], r["role"]) for r in links),
            "geocodes": [g["signal_id"] for g in geos]}


@pytest.mark.parametrize("kind", BACKENDS)
async def test_a_situation_that_does_not_fit_the_window_is_left_whole_and_untouched(kind, monkeypatch):
    tag = new_tag()
    sets = canonical_set(tag)
    crash, robbery = sets["em_bypass"], sets["gariahat"]
    late = rekey(crash[1], tag + "-late")  # one more report of the EM Bypass crash
    async with backend(kind, tag) as bk:
        bk.track(*crash, robbery, late)
        pipe = FakePipeline(tag)
        app = make_app(bk.pool, pipe)
        (sit,) = (await _post(app, crash)).json()["resolved"]
        assert sit["source_count"] == 5
        before = await _situation_state(bk, sit["osint_event_id"])
        assert len(before["links"]) == 5
        monkeypatch.setattr(store, "WINDOW_LIMIT", 3)  # read at call time
        r = await _post(app, [robbery])  # published within 72 h of the crash: its reports are seeds
        assert r.status_code == 200, r.text
        # the 5-report situation does not fit the 2 places left: left out WHOLE, not cut to 2
        assert r.json()["window"] == {"signals": 1, "truncated": 5, "unreadable": 0}
        assert [s.signal_id for s in pipe.calls[-1]] == [robbery.signal_id]
        assert await _situation_state(bk, sit["osint_event_id"]) == before  # row, links, id untouched
        # once it fits again it is re-fused whole, and the new report corroborates it
        monkeypatch.setattr(store, "WINDOW_LIMIT", 2000)
        r = await _post(app, [late])
        assert r.status_code == 200, r.text
        assert r.json()["window"]["truncated"] == 0
        (grown,) = [x for x in r.json()["resolved"] if x["fused_event_id"] == sit["fused_event_id"]]
        assert grown["osint_event_id"] == sit["osint_event_id"] and grown["source_count"] == 6
        assert {s.signal_id for s in crash} <= {s.signal_id for s in pipe.calls[-1]}


async def test_a_unit_with_an_unreadable_member_is_left_whole():
    tag = new_tag()
    crash = canonical_set(tag)["em_bypass"]
    async with backend("fake", tag) as bk:
        pipe = FakePipeline(tag)
        app = make_app(bk.pool, pipe)
        (sit,) = (await _post(app, crash[:4])).json()["resolved"]
        before = await _situation_state(bk, sit["osint_event_id"])
        bk.db.signals[crash[0].signal_id]["source"] = "retired_feed"  # no longer in SOURCE_PRIORS
        r = await _post(app, [crash[4]])
        assert r.status_code == 200, r.text
        assert r.json()["window"] == {"signals": 1, "truncated": 0, "unreadable": 4}
        assert [s.signal_id for s in pipe.calls[-1]] == [crash[4].signal_id]
        assert await _situation_state(bk, sit["osint_event_id"]) == before


async def test_a_promotion_that_commits_mid_ingest_is_inherited():
    tag = new_tag()
    base = canonical_set(tag)["em_bypass"][0]
    t0 = datetime(2026, 10, 20, 13, 0, tzinfo=UTC)

    def sig(n: int, clusters: list[str], minutes: int) -> RawOsintSignal:
        return rekey(base, f"{tag}-r{n}", published_at=t0 + timedelta(minutes=minutes),
                     category_hint=[f"cluster:{c}" for c in clusters])

    a, c, bridge = sig(1, ["r1@em_bypass"], 0), sig(2, ["r2@em_bypass"], 5), sig(3, ["r1@em_bypass", "r2@em_bypass"], 9)
    async with backend("fake", tag) as bk:
        app = make_app(bk.pool, FakePipeline(tag))
        first = (await _post(app, [a, c])).json()
        fake = FakePipeline(tag)
        ids = {r["fused_event_id"]: r["osint_event_id"] for r in first["resolved"]}
        a_id, c_id = ids[fake.fused_id(a.signal_id)], ids[fake.fused_id(c.signal_id)]
        promoted = uuid.uuid4()

        class Racing(FakePipeline):
            def __call__(self, signals, **kw):  # an officer's promotion of C commits mid-pipeline
                bk.db.events[c_id]["promoted_event_id"] = promoted
                return super().__call__(signals, **kw)

        app = make_app(bk.pool, Racing(tag))
        merged = (await _post(app, [bridge])).json()
        assert merged["superseded"] == [{"osint_event_id": c_id, "superseded_by": a_id}]
        # the absorber took the promotion as it stood after the supersede — never promotable twice
        assert bk.db.events[a_id]["promoted_event_id"] == promoted


@pytest.mark.parametrize("kind", BACKENDS)
async def test_an_unknown_road_id_is_stored_null_never_a_failure(kind):
    tag = new_tag()
    sig = rekey(canonical_set(tag)["gariahat"], tag, category_hint=["cluster:x@nowhere-road"])
    async with backend(kind, tag) as bk:
        bk.track(sig)
        r = await _post(make_app(bk.pool, FakePipeline(tag)), [sig])
        assert r.status_code == 200, r.text
        (sit,) = r.json()["resolved"]
        row = await _event_by_fused(bk, sit["fused_event_id"])
        assert row["segment_id"] is None and row["rep_lon"] is not None
        assert sit["segment_id"] is None  # the reply says what was stored


# ── not deployed / failing pipeline: nothing stored ──────────────────────────


@pytest.mark.parametrize("kind", BACKENDS)
async def test_503_when_the_pipeline_is_not_deployed_and_nothing_is_stored(kind, monkeypatch):
    tag = new_tag()
    sig = canonical_set(tag)["gariahat"]
    monkeypatch.setitem(sys.modules, "osint_analysis", None)
    monkeypatch.setitem(sys.modules, "osint_analysis.pipeline", None)
    async with backend(kind, tag) as bk:
        bk.track(sig)
        app = make_app(bk.pool)  # the REAL get_pipeline
        r = await _post(app, [sig])
        assert r.status_code == 503 and r.json() == {"detail": "osint pipeline not deployed"}
        assert await _stored(bk, sig.signal_id) is None


def test_get_pipeline_raises_503_when_either_library_is_missing(monkeypatch):
    for blocked in ("osint_analysis.pipeline", "osint_geo.resolver"):
        reset_osint_state()
        monkeypatch.setitem(sys.modules, blocked, None)
        with pytest.raises(Exception) as exc:
            ingest.get_pipeline()
        assert getattr(exc.value, "status_code", None) == 503
        assert exc.value.detail == ingest.PIPELINE_NOT_DEPLOYED
        monkeypatch.delitem(sys.modules, blocked)


@pytest.mark.parametrize("kind", BACKENDS)
async def test_a_failing_pipeline_rolls_the_batch_back(kind):
    tag = new_tag()
    sig = canonical_set(tag)["gariahat"]
    async with backend(kind, tag) as bk:
        bk.track(sig)
        r = await _post(make_app(bk.pool, FakePipeline(tag, fail=True)), [sig])
        assert r.status_code == 500 and "RuntimeError" in r.json()["detail"]
        assert await _stored(bk, sig.signal_id) is None


async def test_body_shape_is_a_422():
    async with backend("fake", new_tag()) as bk:
        app = make_app(bk.pool, FakePipeline(new_tag()))
        async with client(app) as c:
            assert (await c.post("/api/v1/osint/signals", json={"signals": []})).status_code == 422
            many = {"signals": [{}] * 201}
            assert (await c.post("/api/v1/osint/signals", json=many)).status_code == 422
            bad_run = {"signals": [{}], "run_id": "has space"}
            assert (await c.post("/api/v1/osint/signals", json=bad_run)).status_code == 422
            extra = {"signals": [{}], "author": "x"}
            assert (await c.post("/api/v1/osint/signals", json=extra)).status_code == 422


async def test_503_before_migration_021():
    tag = new_tag()
    async with backend("fake", tag, migrated=False) as bk:
        r = await _post(make_app(bk.pool, FakePipeline(tag)), [canonical_set(tag)["gariahat"]])
        assert r.status_code == 503 and "not migrated" in r.json()["detail"]
        assert bk.db.signals == {}


# ── the live state the pipeline attaches to (read-only) ──────────────────────


async def test_live_state_snapshot_reads_events_routes_and_closures():
    from fixtures.osint.fakedb import FakeOsintConn, FakeOsintDB

    db = FakeOsintDB()
    conn = FakeOsintConn(db)
    now = datetime.now(UTC)
    eid = "11111111-2222-4333-8444-555555555555"
    db.corridor[eid] = {"event_id": eid, "event_kind": "protected_movement", "status": "active",
                        "metadata": "{}", "source_kind": None, "created_at": now, "geotag_lon": None,
                        "geotag_lat": None}
    db.routes.append({"event_id": eid, "route_rank": 1, "label": "primary", "segment_ids": [1035, 1031],
                      "superseded_at": None})
    db.phases.append({"event_id": eid, "window_start": now - timedelta(minutes=5),
                      "window_end": now + timedelta(minutes=30),
                      "closure_policy": {"closure_type": "full_closure"}})
    db.dispatches.append({"dispatch_id": "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee", "event_id": eid,
                          "agency": "ambulance", "status": "en_route",
                          "request_payload": {"route_segment_ids": [1032, 1035]}})
    snap = await live_state.snapshot(conn, now=now)
    (ev,) = snap.live_events
    assert ev.urn == f"event:{eid}" and ev.segment_ids == [1035, 1031] and ev.lon is not None
    assert [r.segment_ids for r in snap.ambulance_routes] == [[1032, 1035]]
    assert {(c.segment_id, c.event_urn) for c in snap.closures} == {(1035, f"event:{eid}"), (1031, f"event:{eid}")}
    # read-only: no write statement was issued
    assert not [s for s in conn.calls if s.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))]


@pytest.mark.parametrize("kind", BACKENDS)
async def test_the_pipeline_sees_the_live_state(kind):
    tag = new_tag()
    sig = canonical_set(tag)["gariahat"]
    async with backend(kind, tag) as bk:
        bk.track(sig)
        pipe = FakePipeline(tag)
        r = await _post(make_app(bk.pool, pipe), [sig])
        assert r.status_code == 200, r.text
        assert pipe.lives[-1] is not None and pipe.lives[-1].as_of is not None


# ── the gazetteer sync (once per process, ids checked) ───────────────────────


@pytest.mark.parametrize("kind", BACKENDS)
async def test_gazetteer_sync_nulls_unknown_road_ids_and_skips_non_places(kind):
    from fixtures.osint.db import TEST_GAZ_BASE

    tag = new_tag()
    base = TEST_GAZ_BASE + int(hashlib.sha1(tag.encode()).hexdigest()[:6], 16)
    entries = [
        {"gaz_id": base + 1, "canonical_name": f"{tag} Test Road", "feature_type": "road",
         "surface_forms": ["test road"], "lon": 88.39, "lat": 22.53, "segment_id": 1035,
         "junction_id": None, "importance": 0.5, "source": "test", "lang_primary": "en"},
        {"gaz_id": base + 2, "canonical_name": f"{tag} Ghost Road", "feature_type": "road",
         "surface_forms": [], "lon": 88.39, "lat": 22.53, "segment_id": 999_999_001,
         "junction_id": 999_999, "importance": 0.5, "source": "test", "lang_primary": "en"},
        {"gaz_id": base + 3, "canonical_name": "x", "feature_type": "road", "author": "someone",
         "lon": 88.39, "lat": 22.53},
    ]
    async with backend(kind, tag) as bk:
        if bk.cleanup is not None:
            bk.cleanup.gaz_ids.update({base + 1, base + 2, base + 3})
        async with bk.pool.acquire() as conn:
            async with conn.transaction():
                stats = await store.sync_gazetteer(conn, entries)
            if bk.db is not None:
                rows = {g: dict(bk.db.gazetteer[g]) for g in bk.db.gazetteer}
            else:
                rows = {r["gaz_id"]: dict(r) for r in await conn.fetch(
                    "SELECT gaz_id, segment_id, junction_id FROM osint.gazetteer WHERE gaz_id = ANY($1::bigint[])",
                    [base + 1, base + 2, base + 3])}
        assert stats == {"upserted": 2, "skipped": 1, "nulled_road_ids": 1}
        assert rows[base + 1]["segment_id"] == 1035
        assert rows[base + 2]["segment_id"] is None and rows[base + 2]["junction_id"] is None
        assert base + 3 not in rows


# ── every statement of the OSINT store prepares on the real schema ───────────


@pytest.mark.parametrize("kind", [p for p in BACKENDS if p != "fake"])
async def test_every_osint_statement_prepares_on_the_sandbox(kind):
    from traffic_oracle.osint import promote as promote_mod

    statements = {
        f"{mod.__name__}.{name}": value
        for mod in (store, live_state, promote_mod)
        for name, value in vars(mod).items()
        if name.startswith("_SQL") and isinstance(value, str)
    }
    assert len(statements) >= 25
    async with backend(kind, new_tag()) as bk:
        async with bk.pool.acquire() as conn:
            tx = conn.transaction()
            await tx.start()
            failures = []
            try:
                for name, sql in sorted(statements.items()):
                    try:
                        async with conn.transaction():  # a savepoint: one failure aborts nothing else
                            await conn.prepare(sql)
                    except Exception as exc:  # noqa: BLE001 — collect them all
                        failures.append(f"{name}: {exc!r}")
            finally:
                await tx.rollback()
    assert not failures, "\n".join(failures)


def _fake_libraries(monkeypatch, resolver_cls):
    import types

    analysis, pipeline_mod = types.ModuleType("osint_analysis"), types.ModuleType("osint_analysis.pipeline")
    pipeline_mod.run_pipeline = lambda *a, **k: None
    geo, resolver_mod = types.ModuleType("osint_geo"), types.ModuleType("osint_geo.resolver")
    resolver_mod.GazetteerResolver = resolver_cls
    for name, mod in (("osint_analysis", analysis), ("osint_analysis.pipeline", pipeline_mod),
                      ("osint_geo", geo), ("osint_geo.resolver", resolver_mod)):
        monkeypatch.setitem(sys.modules, name, mod)
    return pipeline_mod


def test_get_pipeline_is_503_when_the_resolver_cannot_load(monkeypatch):
    class Broken:
        def __init__(self):
            raise FileNotFoundError("gazetteer missing (test)")

    _fake_libraries(monkeypatch, Broken)
    with pytest.raises(Exception) as exc:
        ingest.get_pipeline()
    assert getattr(exc.value, "status_code", None) == 503
    assert exc.value.detail == ingest.PIPELINE_NOT_DEPLOYED


def test_get_pipeline_loads_the_libraries_once(monkeypatch):
    built = []

    class Resolver:
        def __init__(self):
            built.append(self)

        def resolve(self, signal):
            return None

    pipeline_mod = _fake_libraries(monkeypatch, Resolver)
    first, second = ingest.get_pipeline(), ingest.get_pipeline()
    assert first is second and len(built) == 1
    assert first.run is pipeline_mod.run_pipeline and first.embedder is None  # never a model host


# ── FIX-B: absorption by member overlap, context roles, handles, the live state ──


async def _roles(bk: Any, oid: str) -> dict[str, str]:
    """{signal_id: role} of a situation's stored sources."""
    if bk.db is not None:
        return dict(bk.db.members(oid))
    async with bk.pool.acquire() as conn:
        rows = await conn.fetch("SELECT signal_id, role FROM osint.event_sources WHERE osint_event_id = $1::uuid", oid)
    return {r["signal_id"]: r["role"] for r in rows}


async def _row(bk: Any, oid: str) -> dict:
    if bk.db is not None:
        return dict(bk.db.events[oid])
    async with bk.pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM osint.resolved_events WHERE osint_event_id = $1::uuid", oid)
    return dict(row)


def _storm(tag: str, name: str, *, place: str, minutes: int) -> RawOsintSignal:
    """A synthetic point-level weather report (fictional publisher) at ``place`` (a fake-resolver key)."""
    where = {"em_bypass": "on EM Bypass near Kasba", "gariahat": "near Gariahat crossing"}[place]
    base = canonical_set(tag)["em_bypass"][0]
    t0 = canonical_set(tag)["sachet_district"].published_at
    return rekey(base, f"{tag}-{name}", title=f"Thunderstorm uproots trees {where}",
                 text=f"Thunderstorm uproots trees {where}; traffic slowed, police said.",
                 published_at=t0 + timedelta(minutes=minutes), pii_redactions=0)


def _alert(tag: str, name: str) -> RawOsintSignal:
    return rekey(canonical_set(tag)["sachet_district"], f"{tag}-{name}")


@pytest.mark.parametrize("kind", BACKENDS)
async def test_a_district_situation_whose_alert_joins_a_point_report_is_superseded_by_it(kind):
    tag = new_tag()
    alert = _alert(tag, "a")
    point = _storm(tag, "p", place="em_bypass", minutes=30)
    async with backend(kind, tag) as bk:
        bk.track(alert, point)
        pipe = FakePipeline(tag)
        app = make_app(bk.pool, pipe)
        (district,) = (await _post(app, [alert])).json()["resolved"]
        assert (await _row(bk, district["osint_event_id"]))["area_level"] is True
        # a later cycle: the alert joins the point report (OS-4: the point report anchors it)
        pipe.groups = {alert.signal_id: "storm", point.signal_id: "storm"}
        second = (await _post(app, [point])).json()
        (sit,) = second["resolved"]
        assert sit["osint_event_id"] != district["osint_event_id"]
        assert sit["fused_event_id"] == pipe.fused_id(point.signal_id)
        assert second["superseded"] == [
            {"osint_event_id": district["osint_event_id"], "superseded_by": sit["osint_event_id"]}
        ]
        assert str((await _row(bk, district["osint_event_id"]))["superseded_by"]) == sit["osint_event_id"]
        # the alert is stored as CONTEXT of the street situation, never as its corroboration
        assert await _roles(bk, sit["osint_event_id"]) == {point.signal_id: "primary", alert.signal_id: "context"}
        assert sit["verification_state"] == "NEWS-REPORTED"  # an official alert in context never verifies
        async with client(app) as c:
            assert (await c.get(f"/api/v1/osint/events/{district['osint_event_id']}")).status_code == 404


@pytest.mark.parametrize("kind", BACKENDS)
async def test_absorption_follows_the_identity_members_never_the_context_alerts(kind):
    tag = new_tag()
    a1, a2 = _alert(tag, "a1"), _alert(tag, "a2")
    p = _storm(tag, "p", place="em_bypass", minutes=30)
    t0 = _storm(tag, "t0", place="em_bypass", minutes=20)  # an earlier report of the same street situation
    q = _storm(tag, "q", place="gariahat", minutes=40)  # another street, the alerts re-attach there
    async with backend(kind, tag) as bk:
        bk.track(a1, a2, p, t0, q)
        pipe = FakePipeline(tag)
        app = make_app(bk.pool, pipe)
        pipe.groups = {p.signal_id: "s", a1.signal_id: "s", a2.signal_id: "s"}
        (old,) = (await _post(app, [p, a1, a2])).json()["resolved"]
        assert (await _roles(bk, old["osint_event_id"]))[p.signal_id] == "primary"
        pipe.groups = {t0.signal_id: "t", p.signal_id: "t", q.signal_id: "u", a1.signal_id: "u", a2.signal_id: "u"}
        second = (await _post(app, [t0, q])).json()
        ids = {r["fused_event_id"]: r["osint_event_id"] for r in second["resolved"]}
        street = ids[pipe.fused_id(t0.signal_id)]
        elsewhere = ids[pipe.fused_id(q.signal_id)]
        # its point report went to `street`; the two context alerts to `elsewhere` — the report decides
        assert second["superseded"] == [{"osint_event_id": old["osint_event_id"], "superseded_by": street}]
        assert await _roles(bk, elsewhere) == {q.signal_id: "primary", a1.signal_id: "context",
                                               a2.signal_id: "context"}


async def test_a_point_situation_is_never_absorbed_into_a_district_one():
    tag = new_tag()
    alert = _alert(tag, "a")
    point = _storm(tag, "p", place="em_bypass", minutes=30)
    async with backend("fake", tag) as bk:
        pipe = FakePipeline(tag)
        app = make_app(bk.pool, pipe)
        pipe.groups = {alert.signal_id: "s", point.signal_id: "s"}
        (sit,) = (await _post(app, [alert, point])).json()["resolved"]
        async with client(app) as c:
            promo = await c.post(f"/api/v1/osint/events/{sit['osint_event_id']}/promote", json={},
                                 headers={"x-sajag-officer": "Sandbox Officer"})
        assert promo.status_code == 201, promo.text
        event_id = promo.json()["event_id"]
        # the street report no longer resolves; the alert falls back to a district situation of its own
        pipe.unresolved = {point.signal_id}
        again = (await _post(app, [alert])).json()  # a re-sent alert: a duplicate, the window re-fused
        (district,) = again["resolved"]
        assert district["osint_event_id"] != sit["osint_event_id"]
        assert again["superseded"] == []  # never "absorbed" by a coarser, district-wide warning
        row = bk.db.events[sit["osint_event_id"]]
        assert row["superseded_by"] is None and not row["is_event"]
        assert row["held_reason"] == store.WITHDRAWN_REASON
        assert str(row["promoted_event_id"]) == event_id  # the promotion stays with the street situation
        assert bk.db.events[district["osint_event_id"]]["promoted_event_id"] is None


def test_absorber_of_is_pure_and_reads_identity_members():
    M = store._Member
    point = {"p": M("primary", False), "a1": M("context", True), "a2": M("context", True)}
    owner = {"p": "T", "a1": "U", "a2": "U"}
    assert store.absorber_of(point, False, owner, {"T": False, "U": False}) == "T"
    # a district-only situation: every member is its identity (its alert decides)
    assert store.absorber_of({"a": M("primary", True)}, True, {"a": "S"}, {"S": False}) == "S"
    # a point situation whose report vanished is withdrawn, never absorbed into a district one
    assert store.absorber_of(point, False, {"a1": "D", "a2": "D"}, {"D": True}) is None
    assert store.absorber_of({"p": M("primary", False)}, False, {"p": "D"}, {"D": True}) is None
    # ties go to the situation holding the primary member
    tie = {"p": M("primary", False), "c": M("corroborating", False)}
    assert store.absorber_of(tie, False, {"p": "Z", "c": "A"}, {"Z": False, "A": False}) == "Z"


async def test_a_store_without_migration_023_writes_context_as_corroborating():
    tag = new_tag()
    alert = _alert(tag, "a")
    point = _storm(tag, "p", place="em_bypass", minutes=30)
    async with backend("fake", tag) as bk:
        bk.db.context_role = False
        pipe = FakePipeline(tag)
        pipe.groups = {alert.signal_id: "s", point.signal_id: "s"}
        r = await _post(make_app(bk.pool, pipe), [alert, point])
        assert r.status_code == 200, r.text
        (sit,) = r.json()["resolved"]
        assert bk.db.members(sit["osint_event_id"]) == [(point.signal_id, "primary"),
                                                       (alert.signal_id, "corroborating")]


_HANDLE_TITLE = ("Road closed for metro work near Taratala on Diamond Harbour Road submitted by "
                 "/u/synthetic_handle_01 [link] [comments]")
_HANDLE_TEXT = ("Road closed near Taratala, per u/synthetic_poster_7 the traffic is diverted; "
                "a case was registered u/s 279 earlier. See reddit.com/user/synthetic_handle_01 for photos.")


@pytest.mark.parametrize("kind", BACKENDS)
async def test_a_poster_handle_is_stripped_from_the_stored_and_fused_text(kind):
    tag = new_tag()
    post = rekey(social_single_signal(), tag, title=_HANDLE_TITLE, text=_HANDLE_TEXT)
    async with backend(kind, tag) as bk:
        bk.track(post)
        pipe = FakePipeline(tag)
        r = await _post(make_app(bk.pool, pipe), [post])
        assert r.status_code == 200, r.text
        # the count's key names no person: the reply passes the frozen person-key rail (ethics rule 3)
        ethics.assert_no_person_keys(r.json())
        assert r.json()["trust_boundary"]["account_refs_stripped"] == 1
        assert not any(ethics.is_forbidden_key(k) for k in r.json()["trust_boundary"])
        row = await _stored(bk, post.signal_id)
        assert row["title"] == "Road closed for metro work near Taratala on Diamond Harbour Road"
        assert "synthetic_poster_7" not in row["body"] and "synthetic_handle_01" not in row["body"]
        assert "[PERSON]" in row["body"] and "u/s 279" in row["body"]  # legal shorthand is not a handle
        (fused,) = [s for s in pipe.calls[-1] if s.signal_id == post.signal_id]
        assert "synthetic_" not in fused.title + fused.text


def test_the_handle_fallback_matches_the_pipelines_own_helper(monkeypatch):
    from osint_analysis.classify import strip_handles

    cases = [_HANDLE_TITLE, _HANDLE_TEXT, "menu/item and u/s 302 stay", "submitted by March 15", "plain text",
             "via /u/a_b-c and https://www.reddit.com/u/xyz_1/ too", "Taratala — submitted by [PERSON] [link]",
             "তারাতলায় রাস্তা বন্ধ, submitted by /u/synthetic_handle_02"]
    for text in cases:
        assert ingest._fallback_strip_handles(text, "[PERSON]") == strip_handles(text, "[PERSON]"), text
    monkeypatch.setattr(ingest, "HANDLE_STRIPPER_HOOK", ingest._fallback_strip_handles)
    assert ingest.strip_poster_handles(_HANDLE_TITLE) == "Road closed for metro work near Taratala on Diamond Harbour Road"


# ── the int3c sandbox: second-order flags fire on the live state (rolled-back seed) ──


@pytest.mark.skipif(not __import__("os").environ.get("OSINT_TEST_DSN"), reason="OSINT_TEST_DSN not set")
async def test_second_order_flags_fire_on_the_sandbox_live_state_with_the_real_pipeline():
    """The REAL pipeline over the EM Bypass replica, ingested on the sandbox (int3c) while a protected
    movement, a convoy, a 108 dispatch and a closure are live — every row seeded inside this test's ONE
    transaction and rolled back: nothing is committed, nothing is left behind.

    The ids are the Kolkata network's (scripts/data/osm_network.json): EM Bypass from Ruby crossing to Science
    City (1035), the Rash Behari Avenue connector into Ruby crossing (1034), Rash Behari Avenue (1033) and
    Science City (junction 30); the sandbox must hold that network."""
    pytest.importorskip("osint_geo.resolver")
    pytest.importorskip("osint_analysis.pipeline")
    import json

    import asyncpg
    from fixtures.osint.db import sandbox_dsn
    from fixtures.osint.fakedb import FakeValkey
    from osint_common.testing import em_bypass_signals

    reset_osint_state()
    tag = new_tag()
    now = datetime.now(UTC)
    base = em_bypass_signals()
    first = min(s.published_at for s in base)
    signals = []
    for s in base:  # run-unique ids; the same reports an hour ago, so still current at the snapshot
        k = rekey(s, tag)
        data = k.model_dump()
        data.update(published_at=now - timedelta(hours=1) + (s.published_at - first),
                    fetched_at=now - timedelta(minutes=5))
        signals.append(RawOsintSignal.model_validate(data))

    conn = await asyncpg.connect(sandbox_dsn())
    saved = (store.FETCHED_WINDOW_HOURS, store.PUBLISHED_WINDOW_HOURS)
    store.FETCHED_WINDOW_HOURS = store.PUBLISHED_WINDOW_HOURS = 0  # this batch's own span only
    tx = conn.transaction()
    await tx.start()
    try:
        async def event(kind: str, status: str, spines: list[list[int]], closure: str | None) -> str:
            eid = await conn.fetchval(
                "INSERT INTO events.corridor_events (event_kind, protection_class, title, status, metadata) "
                "VALUES ($1, $2, $3, $4, $5::jsonb) RETURNING event_id",
                kind, "Z+" if kind == "protected_movement" else "none", f"{tag} {kind} {status}", status,
                json.dumps({"source": "test", "test_tag": tag}))
            for rank, segs in enumerate(spines, start=1):
                await conn.execute(
                    "INSERT INTO events.event_routes (event_id, route_rank, label, segment_ids) VALUES ($1, $2, $3, $4)",
                    eid, rank, "primary" if rank == 1 else f"alt-{rank - 1}", segs)
            if closure:
                await conn.execute(
                    "INSERT INTO events.event_phases (event_id, phase_rank, label, window_start, window_end, "
                    "closure_policy) VALUES ($1, 1, 'closure', $2, $3, $4::jsonb)",
                    eid, now - timedelta(minutes=10), now + timedelta(minutes=30),
                    json.dumps({"advance_closure_sec": 120, "closure_type": closure}))
            return str(eid)

        async def movement(status: str, route: list[int]) -> str:
            mid = await conn.fetchval(
                "INSERT INTO convoy.movements (vvip_class, status, origin_geom, destination_geom) VALUES "
                "('Z+', $1, ST_SetSRID(ST_MakePoint(88.401, 22.513), 4326), ST_SetSRID(ST_MakePoint(88.398, 22.540), 4326)) "
                "RETURNING movement_id", status)
            await conn.execute(
                "INSERT INTO convoy.planned_routes (movement_id, route_rank, segment_ids, route_geom) VALUES "
                "($1, 1, $2, (SELECT geom FROM corridor.road_segments WHERE segment_id = $3))",
                mid, route, route[0])
            return str(mid)

        async def dispatch(eid: str, status: str, waypoint: int | None, payload: dict) -> str:
            return str(await conn.fetchval(
                "INSERT INTO corridor.dispatches (event_id, agency, unit_id, waypoint_junction, status, "
                "requested_by, request_payload) VALUES ($1, 'ambulance', $2, $3, $4, 'test', $5::jsonb) "
                "RETURNING dispatch_id", uuid.UUID(eid), "AMB-TEST-01", waypoint, status, json.dumps(payload)))

        corridor = await event("protected_movement", "active", [[1034, 1035], [1033]], "full")  # brain vocab
        approved = await event("protected_movement", "approved", [[1035]], "full_closure")
        planning = await event("protected_movement", "planning", [[1035]], None)
        medical = await event("emergency_evacuation", "active", [[1034, 1033]], None)
        ambulance = await dispatch(medical, "en_route", 30, {"note": "test"})  # its unit drives 1034 → 1035
        requested = await dispatch(medical, "requested", 30, {"route_segment_ids": [1035]})
        convoy = await movement("active", [1035])
        idle = await movement("planning", [1035])
        frames = {f"convoy:position:{m}": {"movement_id": m, "event_id": None, "lon": 88.3961, "lat": 22.5262,
                                            "speed_kmh": 40.0, "heading": 0.0, "t": now.isoformat(),
                                            "source": "emulated_gps", "progress": 0.3, "segment_id": 1035}
                  for m in (convoy, idle)}

        reply = await ingest.ingest_signals(conn, ingest.get_pipeline(), [payload(s) for s in signals],
                                            valkey=FakeValkey(frames), now=now)
        mine = {s.signal_id for s in signals}
        (sit,) = [x for x in reply["resolved"] if x["is_event"]]
        assert sit["segment_id"] == 1035 and reply["accepted"] == len(signals)
        row = await conn.fetchrow("SELECT second_order, attach_novel, corroborates_live_urn FROM "
                                  "osint.resolved_events WHERE osint_event_id = $1::uuid", sit["osint_event_id"])
        members = {r["signal_id"] for r in await conn.fetch(
            "SELECT signal_id FROM osint.event_sources WHERE osint_event_id = $1::uuid", sit["osint_event_id"])}
        assert members == mine
        flags = {(f["kind"], f["urn"], f["segment_id"]) for f in json.loads(row["second_order"])}
        assert flags == {
            ("protected_corridor", f"event:{corridor}", 1035),
            ("convoy", f"convoy:{convoy}", 1035),
            ("ambulance_route", f"dispatch:{ambulance}", 1035),
            ("closure", f"event:{corridor}", 1035),
        }
        named = {u for _, u, _ in flags}
        for urn in (f"event:{approved}", f"event:{planning}", f"convoy:{idle}", f"dispatch:{requested}"):
            assert urn not in named
        assert row["attach_novel"] is True and row["corroborates_live_urn"] is None
    finally:
        await tx.rollback()  # every seeded and ingested row goes with it
        store.FETCHED_WINDOW_HOURS, store.PUBLISHED_WINDOW_HOURS = saved
        try:
            left = await conn.fetchval("SELECT count(*) FROM events.corridor_events WHERE metadata->>'test_tag' = $1", tag)
            assert left == 0
        finally:
            await conn.close()
