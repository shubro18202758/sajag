"""The REAL OSINT pipeline behind the oracle's ingest (OS-3's ``osint_geo`` + OS-4's ``osint_analysis``).

Skipped until both libraries import (they are built in the same wave as OS-5); live at the wave-B
gate.  Nothing here touches a database: the route test runs over the in-memory fake store.

* the real pipeline over ``osint_common.testing.weh_signals()`` — after the oracle's own trust
  boundary — gives exactly ONE surfaced, correlated situation, at segment 1015 (Western Express
  Highway, Vakola to the Sahar Elevated Road, on the Mumbai gazetteer);
* the same through ``POST /api/v1/osint/signals`` with the real ``get_pipeline()``;
* the fake resolver of ``fixtures/osint/signals.py`` places every Mumbai fixture where the real one
  does, so the fake-pipeline tests stand on the real Mumbai resolutions;
* with ``OSINT_POC_SIGNALS`` pointing at the proof-of-concept's ``signals.raw.json`` (read in place,
  never copied): those are the PREVIOUS city's captures, so only their shapes are checked — every one
  passes the trust boundary's shape checks (the few carrying Indic-script words the redactor cannot read
  are refused as ``pii_unredacted``), and none surfaces as a Mumbai situation (the old "3 surfaced
  situations" parity is retired with the other city's gazetteer);
* a promoted situation never corroborates its own corridor event: the real attach check DOES name
  the event once it is live, and the store records the situation novel (the promotion is
  ``promoted_to``, never independent confirmation).
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

pytest.importorskip("osint_geo.resolver", reason="osint_geo (OS-3) not importable yet")
pytest.importorskip("osint_analysis.pipeline", reason="osint_analysis (OS-4) not importable yet")

from fixtures.osint.harness import backend, client, make_app, reset_osint_state  # noqa: E402
from osint_common.testing import (  # noqa: E402
    dadar_robbery_signal,
    live_state_dadar_pursuit,
    sachet_maharashtra_signal,
    sachet_mumbai_signal,
    social_ghatkopar_signal,
    weh_signals,
)
from osint_common.types import RawOsintSignal  # noqa: E402
from traffic_oracle.osint import ingest  # noqa: E402

#: the synthetic OSINT fixtures here predate the scope rule (tests/conftest.py)
SCOPE_GATE_OFF = True

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")


@pytest.fixture(autouse=True)
def _clean_state():
    reset_osint_state()
    yield
    reset_osint_state()


def _surfaced(result):
    return [e for e in result.resolved if e.is_event]


def test_the_real_pipeline_correlates_the_weh_case_at_segment_1015():
    pipeline = ingest.get_pipeline()  # the real libraries, lazily imported
    signals = [ingest.prepare_signal(s).signal for s in weh_signals()]
    live = live_state_dadar_pursuit()
    result = pipeline.run(signals, resolver=pipeline.resolver, live=live, now=live.as_of)
    (situation,) = _surfaced(result)
    assert situation.segment_id == 1015 and situation.toponym == "Western Express Highway"
    assert situation.correlated_classes == ["road_accident", "public_conflict"]  # a correlated situation
    assert situation.subtype == "affray+collision" and situation.credibility == 0.65
    assert situation.attach.novel  # not the Dadar pursuit, several km away
    assert situation.verification_state != "OFFICIAL-VERIFIED"  # news only: never inflated
    assert {s.url for s in situation.sources} == {None}  # the oracle withheld the news links


async def test_the_real_pipeline_through_the_ingest_route():
    signals = weh_signals()
    async with backend("fake", "test-integration") as bk:
        app = make_app(bk.pool)  # no override: ingest.get_pipeline() is the real one
        async with client(app) as c:
            r = await c.post("/api/v1/osint/signals",
                             json={"signals": [s.model_dump(mode="json") for s in signals]})
            assert r.status_code == 200, r.text
            surfaced = [x for x in r.json()["resolved"] if x["is_event"]]
            assert len(surfaced) == 1 and surfaced[0]["segment_id"] == 1015
            listed = (await c.get("/api/v1/osint/events")).json()
        assert [e["segment_id"] for e in listed["events"]] == [1015]
        assert listed["events"][0]["source_count"] == len(signals)


def test_the_fake_resolver_places_the_canonical_fixtures_where_the_real_one_does():
    from fixtures.osint.signals import PLACES, FakeResolver

    pipeline = ingest.get_pipeline()
    cases = {
        "weh": weh_signals(), "dadar": [dadar_robbery_signal()],
        "ghatkopar": [social_ghatkopar_signal()], "sachet-mumbai": [sachet_mumbai_signal()],
        "sachet-maharashtra": [sachet_maharashtra_signal()],
    }
    for key, signals in cases.items():
        for raw in signals:
            signal = ingest.prepare_signal(raw).signal
            real = pipeline.resolver.resolve(signal)
            assert real is not None, key
            assert FakeResolver().resolve(signal) == real, key
            assert real.model_dump(exclude={"signal_id"}) == PLACES[key], key
    # (the Kolkata pack's PLACES, and the decision-support fixture's Sector V - New Town link, are that pack's
    # own resolutions: the Mumbai gazetteer does not hold their places, so they are not re-checked here)


@pytest.mark.skipif(not os.environ.get("OSINT_POC_SIGNALS"), reason="OSINT_POC_SIGNALS not set")
async def test_the_previous_citys_poc_capture_passes_as_shapes_and_never_surfaces_in_mumbai():
    """The proof-of-concept capture is the previous city's real headlines: on the Mumbai gazetteer its
    places do not exist, so the old parity (3 surfaced situations, segment 1045) cannot hold and is retired.
    What stays is shape-only: every record is a valid signal that passes the oracle's trust boundary — but
    for the ones carrying Indic-script words no redactor can read for names, refused as ``pii_unredacted`` —
    news and social links are withheld, and none of it surfaces as a Mumbai situation."""
    from osint_common import ethics

    records = json.loads(Path(os.environ["OSINT_POC_SIGNALS"]).read_text(encoding="utf-8"))
    signals = {r["signal_id"]: RawOsintSignal.model_validate(r) for r in records}
    unreadable = {sid for sid, s in signals.items()
                  if ethics.find_unredactable(s.title) or ethics.find_unredactable(s.text)}
    async with backend("fake", "test-integration") as bk:
        app = make_app(bk.pool)  # the real get_pipeline()
        async with client(app) as c:
            r = await c.post("/api/v1/osint/signals", json={"signals": records})
            assert r.status_code == 200, r.text
            body = r.json()
            listed = (await c.get("/api/v1/osint/events")).json()
        assert len(signals) == len(records) and body["accepted"] == len(records) - len(unreadable)
        assert {(x["signal_id"], x["reason"]) for x in body["rejected"]} == {(sid, "pii_unredacted") for sid in unreadable}
        assert body["counts"]["surfaced"] == 0 and listed["events"] == []
        assert not [row for row in bk.db.signals.values() if row["source_tier"] != "official" and row["url"]]


async def test_the_real_gazetteer_syncs_into_the_store_once():
    from fixtures.osint.fakedb import FakeOsintConn, FakeOsintDB, FakePool
    from traffic_oracle.osint import store

    db = FakeOsintDB()
    pool = FakePool(FakeOsintConn(db))
    stats = await store.ensure_gazetteer(pool)  # osint_geo.gazetteer.load(), the X19 entries
    assert stats is not None and stats["upserted"] >= 100 and stats["skipped"] == 0
    weh = db.gazetteer[87]  # the X19 entry of segment 1015, the Western Express Highway from Vakola to Sahar
    assert weh["canonical_name"] == "Western Express Highway" and weh["segment_id"] == 1015
    assert await store.ensure_gazetteer(pool) is None  # once per process


async def test_the_resolve_route_through_the_real_resolver():
    async with backend("fake", "test-integration") as bk:
        app = make_app(bk.pool)
        async with client(app) as c:
            r = await c.get("/api/v1/osint/gazetteer/resolve", params={"q": "हिंदमाता"})  # Hindmata, Dadar East
        assert r.status_code == 200, r.text
        cands = r.json()["candidates"]
        assert cands and set(cands[0]) == {"gaz_id", "canonical_name", "feature_type", "lon", "lat",
                                           "segment_id", "junction_id", "confidence", "method"}
        assert (cands[0]["canonical_name"], cands[0]["junction_id"]) == ("Hindmata (Dadar East)", 19)
        assert bk.conn.calls == []  # read-only


async def test_a_promoted_situation_never_corroborates_its_own_event_with_the_real_pipeline():
    from traffic_oracle.osint import live_state

    now = datetime.now(UTC)
    base = weh_signals()
    first = min(s.published_at for s in base)

    def current(s: RawOsintSignal) -> RawOsintSignal:  # the same reports, an hour ago: still current
        data = s.model_dump()
        data.update(published_at=now - timedelta(hours=1) + (s.published_at - first),
                    fetched_at=now - timedelta(minutes=5))
        return RawOsintSignal.model_validate(data)

    signals = [current(s) for s in base]
    # one collision report arrives after the promotion: the second, since without the embedder the fourth
    # ("rammed") report is the lexical bridge that links the third ("collided") one into the situation
    late = signals.pop(1)
    async with backend("fake", "test-integration") as bk:
        app = make_app(bk.pool)  # the real get_pipeline()
        async with client(app) as c:
            r = await c.post("/api/v1/osint/signals", json={"signals": [s.model_dump(mode="json") for s in signals]})
            assert r.status_code == 200, r.text
            (sit,) = [x for x in r.json()["resolved"] if x["is_event"]]
            oid = sit["osint_event_id"]
            promo = await c.post(f"/api/v1/osint/events/{oid}/promote", json={},
                                 headers={"x-sajag-officer": "Sandbox Officer"})
            assert promo.status_code == 201, promo.text
            event_id = promo.json()["event_id"]
            # the real attach check names the promoted event, now live at the same point ...
            pipeline = ingest.get_pipeline()
            live = await live_state.snapshot(bk.conn, now=datetime.now(UTC))
            probe = pipeline.run([*signals, ingest.prepare_signal(late).signal], resolver=pipeline.resolver,
                                 live=live, now=live.as_of)
            (proposed,) = _surfaced(probe)
            assert proposed.attach.corroborates_live_urn == f"event:{event_id}"
            # ... and through the route the store records the situation NOVEL
            r = await c.post("/api/v1/osint/signals", json={"signals": [late.model_dump(mode="json")]})
            assert r.status_code == 200, r.text
            (grown,) = [x for x in r.json()["resolved"] if x["osint_event_id"] == oid]
            assert grown["source_count"] == len(base)
            assert r.json()["counts"]["attached_to_live"] == 0
            own = (await c.get(f"/api/v1/osint/events/{oid}")).json()["event"]
            city = (await c.get(f"/api/v1/city/entity/osint_event/{oid}")).json()
            cancel = await c.post(f"/api/v1/events/{event_id}/status",
                                  json={"to_status": "cancelled", "officer": "Sandbox Officer", "note": "test"})
            assert cancel.status_code == 200, cancel.text
        assert own["attach"] == {"novel": True, "corroborates_live_urn": None}
        assert own["promoted_event_id"] == event_id
        rels = [(x["relation"], x["entity"]["urn"]) for x in city["related"]]
        assert ("promoted_to", f"event:{event_id}") in rels and ("corroborates", f"event:{event_id}") not in rels
