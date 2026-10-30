"""GET /api/v1/city/entities with OSINT — the C-C extension of contract C-T (OS-5; plan X13).

* ``osint_event`` entities are ALWAYS ``source: "osint"`` with a verification state (never "live");
  their props are the OsintEventRow fields (``dss`` included) plus the C-Q provenance and
  ``context_members`` — the store's count of CONTEXT members, the feed's own subquery (FIX-AUDIT-A),
  so a surface counts reports as ``source_count - context_members``, never from the capped,
  distinct ``context_publishers``;
* no held situation is an entity; ``place`` entities come only from the places linked to the
  surfaced situations (a held report's place never appears);
* ``props.dss`` is the latest decision support (``horizon_min``, ``expires_at``) and reads
  ``state: "expired"`` — not ``proposed`` — once ``expires_at`` has passed, the row itself unchanged
  (the snapshot never writes);
* ``set(feeds) == set(ENTITY_KINDS)`` still holds with the new kinds; ``feeds.osint_event.held_social``
  is an integer and there is no ``feeds.osint`` key;
* with the ``osint`` and ``decision`` schemas absent, the snapshot is today's (the guard): the same
  entities, the same feeds, no ``dss``, and not one statement touches ``osint.*`` / ``decision.*``.

Offline the canned city of test_city_router.py is extended with the OSINT handlers of
``fixtures/osint/fakedb.py`` (situations ingested through POST /osint/signals with the fake
pipeline); with ``OSINT_TEST_DSN`` the same checks run on the sandbox, scoped to this run's rows.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
import test_city_router as tcr
from httpx import ASGITransport, AsyncClient

from fixtures.osint.db import TEST_GAZ_BASE
from fixtures.osint.fakedb import FakeOsintConn, FakeOsintDB, FakePool, city_osint_handlers
from fixtures.osint.harness import BACKENDS, backend, client, make_app, reset_osint_state
from fixtures.osint.signals import PLACES, FakePipeline, mumbai_set, new_tag, payload
from osint_common import ethics
from osint_common.types import DssSummary, OsintEventRow
from traffic_oracle import events as events_mod
from traffic_oracle.city import common
from traffic_oracle.city import entities as ent
from traffic_oracle.osint import store

#: the synthetic OSINT fixtures here predate the scope rule (tests/conftest.py)
SCOPE_GATE_OFF = True

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")

GAZETTEER = Path(__file__).resolve().parents[3] / "scripts" / "data" / "osint_gazetteer.json"
OLD_KINDS = ("event", "vehicle", "sighting", "camera", "junction", "unit", "convoy", "dispatch",
             "recommendation", "anomaly")


@pytest.fixture(autouse=True)
def _clean_state():
    reset_osint_state()
    yield
    reset_osint_state()


def _gazetteer_entries() -> list[dict]:
    return json.loads(GAZETTEER.read_text(encoding="utf-8"))["entries"]


def _place_name(key: str) -> str:
    """The canonical name the fixture resolver gives place ``key`` (``fixtures/osint/signals.PLACES``):
    the tests read it there, so they follow the fixture's city."""
    return PLACES[key]["toponym"]


def _place_id(key: str) -> str:
    """The ``place`` entity id of fixture place ``key``: its gazetteer entry's slug + ``gaz_id`` (C-T). A road
    name spans several gazetteer entries on the Mumbai network (one per segment): the entry is the one on the
    fixture place's own segment or junction (a junction the city pack also lists as a landmark has two entries on
    it; the first, the network junction's, is taken)."""
    name, place = _place_name(key), PLACES[key]
    gaz_id = next(e["gaz_id"] for e in _gazetteer_entries() if e["canonical_name"] == name
                  and (e.get("segment_id"), e.get("junction_id")) == (place["segment_id"], place["junction_id"]))
    return common.place_slug(name, gaz_id)


def _place_ids_named(key: str) -> set[str]:
    """Every gazetteer entry carrying fixture place ``key``'s name, as ``place`` entity ids."""
    name = _place_name(key)
    return {common.place_slug(name, e["gaz_id"]) for e in _gazetteer_entries() if e["canonical_name"] == name}


async def _ingest(pool: Any, tag: str, bk: Any = None) -> dict[str, str]:
    """The canonical set through POST /osint/signals; ``{name: osint_event_id}``."""
    sets = mumbai_set(tag)
    signals = [*sets["weh"], sets["dadar"], sets["sachet_mumbai"], sets["sachet_maharashtra"], sets["social"]]
    if bk is not None:
        bk.track(*signals)
    app = make_app(pool, FakePipeline(tag))
    async with client(app) as c:
        r = await c.post("/api/v1/osint/signals", json={"signals": [payload(s) for s in signals]})
    assert r.status_code == 200, r.text
    fake = FakePipeline(tag)
    by_fused = {i["fused_event_id"]: i["osint_event_id"] for i in r.json()["resolved"]}
    anchors = {"weh": sets["weh"][0], "dadar": sets["dadar"], "sachet": sets["sachet_mumbai"],
               "nowcast": sets["sachet_maharashtra"], "social": sets["social"]}
    return {name: by_fused[fake.fused_id(s.signal_id)] for name, s in anchors.items()}


def _dss_row(urn: str, *, generated_at: datetime, horizon_min: int, state: str = "proposed") -> dict:
    return {
        "dss_id": str(uuid.uuid4()), "event_urn": urn, "state": state, "generated_at": generated_at,
        "horizon_min": horizon_min, "recommendation": json.dumps({"top_coa_id": "coa_std"}),
    }


class OsintCity:
    """The canned city of test_city_router.py + the OSINT store (one shared FakeOsintDB)."""

    def __init__(self, *, migrated: bool = True) -> None:
        self.db = FakeOsintDB(migrated=migrated)
        self.osint_pool = FakePool(FakeOsintConn(self.db))
        tables = tcr.city_tables()
        if migrated:
            tables["relations"] |= set(common.OSINT_RELATIONS) | set(common.DECISION_RELATIONS)
            tables["relations"].add(common.DECISION_LOG_RELATION)
        self.city_pool = tcr.CityFakePool(tables)
        self.city_pool.conn.handlers.update(city_osint_handlers(self.db))

    def app(self) -> Any:
        app = tcr.make_app(self.city_pool, tcr.city_valkey())
        store.GAZETTEER_LOADER = lambda: []
        return app


async def _snapshot(app: Any, query: str = "") -> dict:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://127.0.0.1") as c:
        r = await c.get("/api/v1/city/entities" + query)
    assert r.status_code == 200, r.text
    return r.json()


# ── offline: the canned city + OSINT ─────────────────────────────────────────


async def _osint_city() -> tuple[OsintCity, dict[str, str], str]:
    city = OsintCity()
    tag = new_tag()
    async with city.osint_pool.acquire() as conn:
        async with conn.transaction():
            await store.sync_gazetteer(conn, _gazetteer_entries())
    ids = await _ingest(city.osint_pool, tag)
    return city, ids, tag


async def test_osint_entities_are_always_osint_with_a_verification_state():
    city, ids, _ = await _osint_city()
    body = await _snapshot(city.app())
    osint = {e["id"]: e for e in body["entities"] if e["kind"] == "osint_event"}
    assert set(osint) == {ids["weh"], ids["dadar"], ids["sachet"]}
    for e in osint.values():
        assert e["source"] == "osint" and e["source"] != "live"
        assert e["verification_state"] in ("NEWS-REPORTED", "OFFICIAL-VERIFIED")
        assert e["credibility"] == e["props"]["credibility"]
        assert set(e) == tcr.ENTITY_KEYS
        props = dict(e["props"])
        assert set(props) == set(ent.OSINT_EVENT_ROW_FIELDS) | {"provenance", "context_members"}
        OsintEventRow.model_validate({k: v for k, v in props.items()
                                      if k not in ("provenance", "context_members")})
        assert isinstance(props["context_members"], int) and props["context_members"] >= 0
        assert set(props["provenance"]) >= {"source_feeds", "publishers", "geocoder", "geocode_confidence"}
        ethics.assert_no_person_keys(e)
    crash = osint[ids["weh"]]
    # (the snapshot carries a point to 1e-5 degrees, about a metre)
    assert (crash["lon"], crash["lat"]) == pytest.approx((PLACES["weh"]["lon"], PLACES["weh"]["lat"]),
                                                         abs=1e-5)
    assert crash["state"] == "surfaced"
    assert "segment:1015" in crash["links"] and crash["label"] == f"Road accident · {_place_name('weh')}"
    assert osint[ids["sachet"]]["verification_state"] == "OFFICIAL-VERIFIED"
    assert osint[ids["sachet"]]["props"]["area_level"] is True
    # every pre-existing record carries the new fields, null for non-OSINT rows
    others = [e for e in body["entities"] if e["kind"] not in ("osint_event", "place")]
    assert others and all(e["verification_state"] is None and e["credibility"] is None for e in others)
    assert all(e["source"] in ("live", "emulated") for e in others)


async def test_no_held_situation_is_an_entity_and_places_come_only_from_links():
    city, ids, _ = await _osint_city()
    body = await _snapshot(city.app())
    urns = {e["urn"] for e in body["entities"]}
    assert f"osint_event:{ids['nowcast']}" not in urns and f"osint_event:{ids['social']}" not in urns
    places = {e["id"]: e for e in body["entities"] if e["kind"] == "place"}
    # the road-accident reports are on the Western Express Highway, the robbery at Dadar TT Circle; the
    # SACHET district names no gazetteer place; the HELD social post (the Ghatkopar place) links nothing.
    # Places are linked BY NAME (C-T): "Western Express Highway" names one gazetteer entry per segment
    # of the road (1013-1019), so the situation links each of them, its own segment's among them; and
    # "Dadar TT Circle" names two entries on junction 20 (the network junction and the city-pack landmark)
    assert {e["props"]["canonical_name"] for e in places.values()} == {_place_name("weh"),
                                                                       _place_name("dadar")}
    road, circle = _place_ids_named("weh"), _place_ids_named("dadar")
    assert len(road) == 7 and len(circle) == 2 and set(places) == road | circle
    kc = places[_place_id("weh")]
    assert common.PLACE_SLUG_RE.fullmatch(kc["id"]) and kc["props"]["segment_id"] == 1015
    assert kc["source"] == "osint" and kc["verification_state"] is None
    assert set(kc["props"]) == set(ent.PLACE_PROP_FIELDS)
    def osint_links(place: dict) -> list[str]:
        return [u for u in place["links"] if u.startswith("osint_event:")]

    for pid in road:
        assert places[pid]["props"]["osint_event_count"] == 1
        assert osint_links(places[pid]) == [f"osint_event:{ids['weh']}"]
    assert "segment:1015" in kc["links"]  # its own road segment
    for pid in circle:
        junction = places[pid]
        assert junction["props"]["junction_id"] == 20 and osint_links(junction) == [f"osint_event:{ids['dadar']}"]
    crash = next(e for e in body["entities"] if e["id"] == ids["weh"])
    assert kc["urn"] in crash["links"]
    held_place = common.name_slug(_place_name("ghatkopar"))
    assert not any(held_place in e["id"] for e in body["entities"] if e["kind"] == "place")


async def test_feeds_stay_keyed_by_entity_kind_with_held_social():
    city, _, _ = await _osint_city()
    body = await _snapshot(city.app())
    assert set(body["feeds"]) == set(common.ENTITY_KINDS)
    assert "osint" not in body["feeds"]
    held = body["feeds"]["osint_event"]["held_social"]
    assert isinstance(held, int) and held == 1  # the one social post (the state nowcast is official)
    # the 7 gazetteer entries of the Western Express Highway (one per segment, linked by name) and the 2 of
    # Dadar TT Circle (the network junction and the city-pack landmark)
    assert body["feeds"]["osint_event"]["count"] == 3 and body["feeds"]["place"]["count"] == 9
    assert all(f["status"] == "ok" for f in body["feeds"].values()), body["feeds"]


async def test_props_dss_reads_expired_lazily_and_never_writes():
    city, ids, _ = await _osint_city()
    now = datetime.now(UTC)
    stale = _dss_row(f"osint_event:{ids['weh']}", generated_at=now - timedelta(hours=2), horizon_min=45)
    fresh = _dss_row(f"osint_event:{ids['dadar']}", generated_at=now - timedelta(minutes=5), horizon_min=60)
    on_event = _dss_row(f"event:{tcr.E_PURSUIT}", generated_at=now - timedelta(minutes=1), horizon_min=30)
    for row in (stale, fresh, on_event):
        city.db.dss[row["dss_id"]] = row
        city.db.coa[(row["dss_id"], "coa_std")] = {"label": "Advisory + 108 ambulance + 1 patrol"}
    body = await _snapshot(city.app())
    by_id = {e["id"]: e for e in body["entities"]}
    expired = by_id[ids["weh"]]["props"]["dss"]
    DssSummary.model_validate(expired)
    assert expired["state"] == "expired" and expired["horizon_min"] == 45
    assert expired["expires_at"] == common.iso_z(stale["generated_at"] + timedelta(minutes=45))
    assert expired["top_coa_id"] == "coa_std" and expired["top_coa_label"].startswith("Advisory")
    assert city.db.dss[stale["dss_id"]]["state"] == "proposed"  # the row itself is unchanged
    assert by_id[ids["dadar"]]["props"]["dss"]["state"] == "proposed"
    assert by_id[ids["sachet"]]["props"]["dss"] is None
    pursuit = by_id[str(tcr.E_PURSUIT)]
    assert pursuit["props"]["dss"]["state"] == "proposed" and pursuit["props"]["dss"]["horizon_min"] == 30
    assert "dss" not in by_id[str(tcr.E_ZONE)]["props"]  # only when a DSS exists


async def test_a_row_that_fails_the_model_is_never_an_entity_nor_its_places():
    city, ids, _ = await _osint_city()
    # foreign rows the SQL surfacing rules pass but OsintEventRow refuses: "Official, verified"
    # with no official source, and a label that carries an age
    city.db.events[ids["dadar"]]["verification_state"] = "OFFICIAL-VERIFIED"
    city.db.events[ids["weh"]]["label"] = "Road accident; a 45-year-old hurt"
    body = await _snapshot(city.app())
    osint = {e["id"] for e in body["entities"] if e["kind"] == "osint_event"}
    assert osint == {ids["sachet"]}
    # their places go with them (each is linked only from a refused row)
    assert not [e for e in body["entities"] if e["kind"] == "place"]
    assert body["feeds"]["osint_event"]["count"] == 1
    async with AsyncClient(transport=ASGITransport(app=city.app()), base_url="http://127.0.0.1") as c:
        for name in ("dadar", "weh"):
            r = await c.get(f"/api/v1/city/entity/osint_event/{ids[name]}")
            assert r.status_code == 404, name
        place = await c.get(f"/api/v1/city/entity/place/{_place_id('weh')}")
        assert place.status_code == 200
        assert not [x for x in place.json()["related"] if x["relation"] == "reported_at"]


async def test_a_malformed_dss_costs_only_the_dss():
    city, ids, _ = await _osint_city()
    now = datetime.now(UTC)
    bad = {**_dss_row(f"osint_event:{ids['weh']}", generated_at=now, horizon_min=45),
           "recommendation": json.dumps({"top_coa_id": "COA-1"})}  # not a CoaId
    city.db.dss[bad["dss_id"]] = bad
    city.db.coa[(bad["dss_id"], "COA-1")] = {"label": "Advisory"}
    body = await _snapshot(city.app())
    crash = next(e for e in body["entities"] if e["id"] == ids["weh"])
    assert crash["props"]["dss"] is None  # the situation stays on the picture without it


async def test_an_older_row_never_shows_its_own_event_as_corroborated():
    city, ids, _ = await _osint_city()
    event_id = str(uuid.uuid4())
    # a row written before the store cleared self-attaches: it names its own promoted event
    city.db.events[ids["weh"]].update(promoted_event_id=uuid.UUID(event_id), attach_novel=False,
                                     corroborates_live_urn=f"event:{event_id}")
    body = await _snapshot(city.app())
    crash = next(e for e in body["entities"] if e["id"] == ids["weh"])
    assert crash["props"]["attach"] == {"novel": True, "corroborates_live_urn": None}
    assert crash["links"].count(f"event:{event_id}") == 1 and crash["state"] == "promoted"


def test_dss_summary_lazy_expiry_rule():
    t = datetime(2026, 10, 20, 15, 5, 0, 123456, tzinfo=UTC)
    row = {"dss_id": "d1", "state": "proposed", "generated_at": t, "horizon_min": 45,
           "top_coa_id": "coa_std", "top_coa_label": None}
    assert ent.dss_summary(row, t + timedelta(minutes=44))["state"] == "proposed"
    s = ent.dss_summary(row, t + timedelta(minutes=45))
    assert s["state"] == "expired" and s["top_coa_label"] == "coa_std"
    DssSummary.model_validate(s)
    assert ent.dss_summary({**row, "state": "approved"}, t + timedelta(days=1))["state"] == "approved"
    assert ent.dss_summary({**row, "top_coa_id": None}, t) is None


# ── context members, counted at the source (FIX-AUDIT-A) ─────────────────────


def test_the_snapshot_counts_context_members_with_the_feeds_own_subquery():
    """One rule, one text: the entity SQL selects the very subquery the feed's surfaced row does."""
    from traffic_oracle.city import feed as feed_mod

    sub = common.OSINT_CONTEXT_MEMBERS_SQL
    assert sub == ("(SELECT count(*) FROM osint.event_sources es WHERE es.osint_event_id = "
                   "r.osint_event_id AND es.role = 'context') AS context_members")
    assert sub in feed_mod._SQL_FEED_OSINT_SURFACED
    assert sub in ent._SQL_OSINT_SURFACED
    assert ent._SQL_OSINT_SURFACED.count("AS context_members") == 1


def _osint_row(**kw: Any) -> dict:
    t = datetime(2026, 10, 25, 9, 0, tzinfo=UTC)
    row = {
        "osint_event_id": "0b7e3c2a-4444-4d1e-9a8b-5c6d7e8f9a0b", "fused_event_id": "f1",
        "event_class": "waterlogging", "correlated_classes": [], "subtype": None,
        "sajag_event_kind": "flood_evacuation", "sajag_incident_kind": None,
        "label": "Waterlogging · Thanthania", "summary": "", "rep_lon": 88.362, "rep_lat": 22.577,
        "toponym": "Thanthania", "segment_id": None, "junction_id": 45, "geocode_confidence": 0.8,
        "area_level": False, "window_start": t, "window_end": t, "credibility": 0.7, "verification_state": "NEWS-REPORTED", "source_count": 4,
        "source_tiers": ["news", "official"], "independent_publishers": 2,
        "cross_type_corroborated": True, "attach_novel": True, "corroborates_live_urn": None,
        "second_order": [], "labels": ["NEWS-REPORTED"], "promoted_event_id": None, "created_at": t,
        "source_feeds": ["google_news"], "publishers": ["a.example", "b.example"], "links_withheld": 0,
        "geocoder": "gazetteer", "context_publishers": ["sachet.ndma.gov.in"], "context_official": True,
    }
    row.update(kw)
    return row


def test_the_entity_carries_the_stores_count_not_the_publisher_list():
    """Two context members of ONE publisher are two members: the distinct, capped publisher list
    would say one (the deck's old inference); the store's count says two — 4 members, 2 reports."""
    now = datetime(2026, 10, 25, 9, 5, tzinfo=UTC)
    e = ent.osint_event_entity(_osint_row(context_members=2), now)
    assert e["props"]["context_members"] == 2
    assert len(e["props"]["provenance"]["context_publishers"]) == 1
    assert e["props"]["source_count"] - e["props"]["context_members"] == 2
    # no context member: 0, never None; a pre-023 / odd value never leaks or goes negative
    no_ctx = _osint_row(context_members=0, context_publishers=None, context_official=False)
    assert ent.osint_event_entity(no_ctx, now)["props"]["context_members"] == 0
    for odd in (None, "x", float("nan"), -3):
        assert ent.osint_event_entity(_osint_row(context_members=odd), now)["props"]["context_members"] == 0
    assert ent.osint_event_entity({k: v for k, v in _osint_row().items()}, now)["props"]["context_members"] == 0


async def test_snapshot_entities_carry_each_situations_context_member_count():
    city, ids, _ = await _osint_city()
    db = city.db
    # the offline fake answers the entity SQL by its text; the subquery is emulated over the
    # same member table the fake store keeps (osint.event_sources: (event, signal) -> role)
    def context_of(oid: str) -> int:
        return sum(1 for _sid, role in db.members(oid) if role == "context")

    plain = city.city_pool.conn.handlers[ent._SQL_OSINT_SURFACED]
    city.city_pool.conn.handlers[ent._SQL_OSINT_SURFACED] = lambda *a: [
        {**r, "context_members": context_of(str(r["osint_event_id"]))} for r in plain(*a)]
    # the road-accident situation gains the district alert as CONTEXT — twice, one publisher (the
    # alert re-issued): two context members behind ONE distinct context publisher
    target = ids["weh"]
    assert context_of(target) == 0
    [(alert, _role)] = db.members(ids["sachet"])
    twin = f"{alert}-reissued"
    db.signals[twin] = dict(db.signals[alert], signal_id=twin)
    db.sources[(target, alert)] = "context"
    db.sources[(target, twin)] = "context"
    body = await _snapshot(city.app())
    osint = {e["id"]: e for e in body["entities"] if e["kind"] == "osint_event"}
    for oid, e in osint.items():
        assert e["props"]["context_members"] == context_of(oid), oid
    t = osint[target]["props"]
    assert t["context_members"] == 2
    assert len(t["provenance"]["context_publishers"]) == 1  # the deck's old inference: 1
    assert osint[ids["dadar"]]["props"]["context_members"] == 0


# ── the guard: an unmigrated database serves today's snapshot ────────────────


async def test_without_the_osint_and_decision_schemas_the_snapshot_is_todays(monkeypatch):
    from traffic_oracle.city import router as city_router

    frozen = datetime.now(UTC)
    monkeypatch.setattr(city_router, "_now", lambda: frozen)  # both snapshots at one instant
    pool = tcr.CityFakePool(tcr.city_tables())  # no osint.* / decision.* relation
    app = tcr.make_app(pool, tcr.city_valkey())
    full = await _snapshot(app)
    calls = list(pool.conn.calls)
    common.reset_relation_cache()
    old = await _snapshot(app, "?kinds=" + ",".join(OLD_KINDS))
    assert [e for e in full["entities"]] == [e for e in old["entities"]]
    for kind in OLD_KINDS:
        assert full["feeds"][kind] == old["feeds"][kind], kind
    assert set(full["feeds"]) == set(common.ENTITY_KINDS)
    assert full["feeds"]["osint_event"] == {"count": 0, "newest_t": None, "age_sec": None,
                                            "unlocated": 0, "status": "ok", "held_social": 0}
    assert full["feeds"]["place"] == {"count": 0, "newest_t": None, "age_sec": None,
                                      "unlocated": 0, "status": "ok"}
    assert not any("dss" in e["props"] for e in full["entities"])
    touched = [sql for sql in calls if "osint." in sql or "decision." in sql]
    assert touched == []  # probes only ever ask to_regclass; no osint / decision statement runs
    assert all(e["source"] in ("live", "emulated") for e in full["entities"])


def test_the_local_verification_states_are_the_events_ones():
    assert common.VERIFICATION_STATES == events_mod.VERIFICATION_STATES


def test_a_promoted_osint_corridor_event_is_badged_osint():
    row = {**tcr.city_tables()["events"][2], "metadata": json.dumps({"source": "osint",
           "osint_event_id": "0b7e3c2a-3333-4d1e-9a8b-5c6d7e8f9a0b"}),
           "source_kind": "osint", "verification_state": "NEWS-REPORTED", "credibility": 0.65}
    e = ent.event_entity(row, [], None, datetime.now(UTC))
    assert e["source"] == "osint" and e["verification_state"] == "NEWS-REPORTED"
    assert e["credibility"] == 0.65 and "osint_event:0b7e3c2a-3333-4d1e-9a8b-5c6d7e8f9a0b" in e["links"]
    assert e["props"]["source_kind"] == "osint"
    assert common.event_source({"source": "osint"}) == "osint"
    assert common.event_source({}, "osint") == "osint"
    assert common.label_source("osint") == "osint" and common.label_source("live_anpr") == "live"
    assert common.city_entity("event", "x", "x", 1, 1, now=datetime.now(UTC), source="weird")["source"] == "live"


# ── the sandbox database ─────────────────────────────────────────────────────


@pytest.mark.parametrize("kind", [p for p in BACKENDS if p != "fake"])
async def test_snapshot_on_the_sandbox(kind):
    tag = new_tag()
    async with backend(kind, tag) as bk:
        ids = await _ingest(bk.pool, tag, bk)
        base = TEST_GAZ_BASE + int(uuid.UUID(tag[5:]).int % 1_000_000) * 10
        entries = [
            {"gaz_id": base + 1, "canonical_name": _place_name("weh"), "feature_type": "landmark",
             "surface_forms": [_place_name("weh").lower()], "lon": PLACES["weh"]["lon"],
             "lat": PLACES["weh"]["lat"], "segment_id": None, "junction_id": None, "importance": 0.7,
             "source": "test", "lang_primary": "en"},
            {"gaz_id": base + 2, "canonical_name": _place_name("ghatkopar"), "feature_type": "road",
             "surface_forms": [_place_name("ghatkopar").lower()], "lon": PLACES["ghatkopar"]["lon"],
             "lat": PLACES["ghatkopar"]["lat"], "segment_id": None, "junction_id": None,
             "importance": 0.8, "source": "test", "lang_primary": "en"},
        ]
        bk.cleanup.gaz_ids.update({base + 1, base + 2})
        now = datetime.now(UTC)
        stale = _dss_row(f"osint_event:{ids['weh']}", generated_at=now - timedelta(hours=2), horizon_min=45)
        bk.cleanup.dss_ids.add(stale["dss_id"])
        async with bk.pool.acquire() as conn:
            async with conn.transaction():
                await store.sync_gazetteer(conn, entries)
                await conn.execute(
                    "INSERT INTO decision.decision_support (dss_id, event_urn, state, generated_at, horizon_min, "
                    "seed, input_fingerprint, situation, criteria, ahp, recommendation, provenance, labels) "
                    "VALUES ($1::uuid, $2, 'proposed', $3, 45, 1, $4, '{}'::jsonb, '[]'::jsonb, '{}'::jsonb, "
                    "$5::jsonb, '{}'::jsonb, ARRAY['SIMULATED'])",
                    stale["dss_id"], stale["event_urn"], stale["generated_at"], f"{tag}-fp", stale["recommendation"],
                )
                await conn.execute(
                    "INSERT INTO decision.coa (dss_id, coa_id, kind, label) VALUES ($1::uuid, 'coa_std', "
                    "'standard', 'Advisory + 108 ambulance + 1 patrol')", stale["dss_id"])
        app = make_app(bk.pool)
        body = await _snapshot(app)
        assert set(body["feeds"]) == set(common.ENTITY_KINDS) and "osint" not in body["feeds"]
        assert isinstance(body["feeds"]["osint_event"]["held_social"], int)
        assert body["feeds"]["osint_event"]["held_social"] >= 1
        mine = {e["id"]: e for e in body["entities"] if e["kind"] == "osint_event" and e["id"] in ids.values()}
        assert set(mine) == {ids["weh"], ids["dadar"], ids["sachet"]}  # never the held two
        assert all(e["source"] == "osint" and e["verification_state"] for e in mine.values())
        async with bk.pool.acquire() as conn:
            for oid, e in mine.items():  # context_members is the store's own count
                assert e["props"]["context_members"] == await conn.fetchval(
                    "SELECT count(*) FROM osint.event_sources WHERE osint_event_id = $1::uuid "
                    "AND role = 'context'", oid)
        dss = mine[ids["weh"]]["props"]["dss"]
        assert dss["state"] == "expired" and dss["horizon_min"] == 45 and dss["expires_at"]
        my_places = {e["props"]["canonical_name"] for e in body["entities"]
                     if e["kind"] == "place" and e["id"].endswith((f"_{base + 1}", f"_{base + 2}"))}
        assert my_places == {_place_name("weh")}  # the Ghatkopar place's only report is held
        async with bk.pool.acquire() as conn:
            assert await conn.fetchval(
                "SELECT state FROM decision.decision_support WHERE dss_id = $1::uuid", stale["dss_id"]
            ) == "proposed"  # read lazily; never written by the snapshot
