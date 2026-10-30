"""POST /api/v1/decision-support/{event_urn}/generate and GET /api/v1/decision-support/{dss_id} (C-U).

Dual-mode: the fake store always; the int3c / int3cl sandbox with ``OSINT_TEST_DSN`` — there every assertion is
scoped to the test's own run-scoped subjects (a seeded sandbox holds other situations and DSS rows), and every
row the test wrote is deleted on teardown.

* 201 a new DecisionSupport (validated against osint_common's model), compute-only, no officer;
* the 10-minute idempotency (200, same dss_id) for the same subject and input fingerprint;
* a new DSS supersedes the subject's previous proposal (``superseded``, ``superseded_by``); one proposed DSS per
  subject;
* lazy expiry on read (``generated_at + horizon_min``), written by the GET;
* 404 unknown / held / malformed subject and unknown dss_id; 409 ``event-closed``;
* corridor-event subjects; twin+cascade (< 5 s) and surrogate (< 1 s) timings;
* a CONTEXT member (a district alert attached to a street report, FIX-B-ORACLE) is listed in provenance.sources
  and named in the dissent as context, never counted in the feeds, publishers, injury cue or confidence;
* honest copy (ethics rule 7): an area-level report's anchor-blocked COAs are never a 'resourcing' flip; a live
  event says who opened it and that its label was derived, an emulator event says EMULATED; each second-order
  flag says what the twin+cascade did with it (a live closure really is kept out of the reassignment).
"""

from __future__ import annotations

import hashlib
import time
from datetime import UTC, datetime, timedelta

import pytest

from fixtures.dss.fakedss import BACKENDS, OFFICER, create_event, dss_backend, load_fixture, seed_situations
from fixtures.osint.harness import client, reset_osint_state
from fixtures.osint.signals import new_tag
from osint_common.types import DecisionSupport, SourceRef
from traffic_oracle.decision_support import coa, engine, router
from traffic_oracle.decision_support import store as dss_store
from traffic_oracle.osint import store as osint_store
from traffic_oracle.decision_support.feasibility import UnitPlane
from traffic_oracle.decision_support.wargame import SegmentModel

#: the synthetic OSINT fixtures here predate the scope rule (tests/conftest.py)
SCOPE_GATE_OFF = True

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")

UNKNOWN = "0b7e3c2a-2222-4d1e-9a8b-5c6d7e8f9a0b"


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    reset_osint_state()
    monkeypatch.setattr(engine, "WARGAME_MODE", "auto")
    yield
    reset_osint_state()


async def _gen(app, urn: str, body: dict | None = None):
    async with client(app) as c:
        return await c.post(f"/api/v1/decision-support/{urn}/generate", json=body or {})


async def _get(app, dss_id: str):
    async with client(app) as c:
        return await c.get(f"/api/v1/decision-support/{dss_id}")


async def _row(bk, dss_id: str) -> dict:
    if bk.db is not None:
        return dict(bk.db.dss[dss_id])
    rows = await bk.fetch(
        "SELECT state, superseded_by, generated_at, horizon_min, requested_by, input_fingerprint "
        "FROM decision.decision_support WHERE dss_id = $1::uuid", dss_id)
    return dict(rows[0])


async def _proposed(bk, urn: str) -> list[str]:
    if bk.db is not None:
        return [d["dss_id"] for d in bk.db.dss.values() if d["event_urn"] == urn and d["state"] == "proposed"]
    rows = await bk.fetch(
        "SELECT dss_id FROM decision.decision_support WHERE event_urn = $1 AND state = 'proposed'", urn)
    return [str(r["dss_id"]) for r in rows]


async def _age(bk, dss_id: str, minutes: int) -> None:
    if bk.db is not None:
        bk.db.dss[dss_id]["generated_at"] -= timedelta(minutes=minutes)
        return
    async with bk.pool.acquire() as conn:
        await conn.execute(
            "UPDATE decision.decision_support SET generated_at = generated_at - make_interval(mins => $2) "
            "WHERE dss_id = $1::uuid", dss_id, minutes)


async def _sim_methods(bk, dss_id: str) -> set[str]:
    if bk.db is not None:
        return {r["method"] for r in bk.db.sim_runs if r["dss_id"] == dss_id}
    rows = await bk.fetch("SELECT DISTINCT method FROM decision.coa_sim_runs WHERE dss_id = $1::uuid", dss_id)
    return {r["method"] for r in rows}


@pytest.mark.parametrize("kind", BACKENDS)
async def test_generate_twin_cascade_then_idempotent_then_supersede(kind):
    tag = new_tag()
    async with dss_backend(kind, tag) as bk:
        app, ids = await seed_situations(bk, tag)
        urn = f"osint_event:{ids['em_bypass']}"
        t0 = time.perf_counter()
        r = await _gen(app, urn, {"requested_by": "deck"})
        elapsed = time.perf_counter() - t0
        assert r.status_code == 201, r.text
        doc = r.json()
        DecisionSupport.model_validate(doc)
        assert elapsed < 5.0, elapsed  # twin + cascade on the segment-1045 subject
        assert doc["event_urn"] == urn and doc["state"] == "proposed"
        assert doc["provenance"]["wargame_method"] == "twin+cascade"
        assert doc["human_gate"] == {"state": "proposed", "required_role": "duty_officer", "officer": None,
                                     "decided_at": None, "audit_ref": None}
        assert doc["recommendation"]["decision"] == "await_officer"
        assert doc["situation"]["segment_id"] == 1045
        assert doc["situation"]["verification_state"] == "NEWS-REPORTED"
        assert doc["situation"]["credibility"] == pytest.approx(0.65)
        assert doc["labels"] == ["NEWS-REPORTED", "SIMULATED"]
        assert doc["seed"] == engine.DEFAULT_SEED and doc["horizon_min"] == 45
        by = {c["coa_id"]: c for c in doc["coa_set"]}
        assert set(by) == {"coa_base", "coa_min", "coa_std", "coa_agg", "coa_info"}
        assert "twin" in by["coa_agg"]["predicted_outcome"]["method"]
        assert "surrogate" in by["coa_std"]["predicted_outcome"]["method"]
        assert all("cascade" in c["predicted_outcome"]["method"] for c in doc["coa_set"])
        assert by["coa_agg"]["predicted_outcome"]["cascade"]["parallel_routes_loaded"]
        assert await _sim_methods(bk, doc["dss_id"]) == {"twin", "surrogate", "cascade"}
        assert len(doc["provenance"]["sim_run_ids"]) >= len(doc["coa_set"])
        bk.track_dss(doc["dss_id"])
        assert await _proposed(bk, urn) == [doc["dss_id"]]
        assert (await _row(bk, doc["dss_id"]))["requested_by"] == "deck"

        # the same question within 10 minutes: 200, the same proposal
        again = await _gen(app, urn, {"requested_by": "brain"})
        assert again.status_code == 200, again.text
        assert again.json()["dss_id"] == doc["dss_id"]
        DecisionSupport.model_validate(again.json())

        # another question (horizon): a new proposal supersedes the previous one
        other = await _gen(app, urn, {"horizon_min": 90})
        assert other.status_code == 201, other.text
        new_id = other.json()["dss_id"]
        bk.track_dss(new_id)
        assert new_id != doc["dss_id"] and other.json()["horizon_min"] == 90
        old = await _row(bk, doc["dss_id"])
        assert old["state"] == "superseded" and str(old["superseded_by"]) == new_id
        assert await _proposed(bk, urn) == [new_id]  # one proposed DSS per subject
        g = await _get(app, doc["dss_id"])
        assert g.status_code == 200
        assert g.json()["state"] == "superseded" and g.json()["human_gate"]["state"] == "superseded"
        DecisionSupport.model_validate(g.json())

        # older than 10 minutes (still inside its horizon): the same question is asked again → a new one
        await _age(bk, new_id, 11)
        fresh = await _gen(app, urn, {"horizon_min": 90})
        assert fresh.status_code == 201
        bk.track_dss(fresh.json()["dss_id"])
        assert (await _row(bk, new_id))["state"] == "superseded"


@pytest.mark.parametrize("kind", BACKENDS)
async def test_lazy_expiry_on_read(kind):
    tag = new_tag()
    async with dss_backend(kind, tag) as bk:
        app, ids = await seed_situations(bk, tag)
        urn = f"osint_event:{ids['gariahat']}"
        r = await _gen(app, urn, {"horizon_min": 15})
        assert r.status_code == 201, r.text
        dss_id = r.json()["dss_id"]
        bk.track_dss(dss_id)
        assert r.json()["situation"]["junction_id"] == 23  # Gariahat crossing
        await _age(bk, dss_id, 16)
        assert (await _row(bk, dss_id))["state"] == "proposed"  # nothing wrote the expiry yet
        g = await _get(app, dss_id)
        assert g.status_code == 200
        body = g.json()
        DecisionSupport.model_validate(body)
        assert body["state"] == "expired" and body["human_gate"]["state"] == "expired"
        assert (await _row(bk, dss_id))["state"] == "expired"  # the GET wrote it
        # a new generation after the expiry: 201; the expired one stays expired (never superseded)
        again = await _gen(app, urn, {"horizon_min": 15})
        assert again.status_code == 201
        bk.track_dss(again.json()["dss_id"])
        assert (await _row(bk, dss_id))["state"] == "expired"
        assert await _proposed(bk, urn) == [again.json()["dss_id"]]


@pytest.mark.parametrize("kind", BACKENDS)
async def test_area_level_subject_generates_with_up_front_infeasibility(kind):
    tag = new_tag()
    async with dss_backend(kind, tag) as bk:
        app, ids = await seed_situations(bk, tag)
        r = await _gen(app, f"osint_event:{ids['sachet']}")
        assert r.status_code == 201, r.text
        doc = r.json()
        bk.track_dss(doc["dss_id"])
        DecisionSupport.model_validate(doc)
        assert doc["situation"]["segment_id"] is None and doc["situation"]["junction_id"] is None
        assert doc["provenance"]["wargame_method"] == "surrogate"  # no road: nothing for the twin to run on
        blocked = []
        for c in doc["coa_set"]:
            if {a["verb"] for a in c["actions"]} & {"dispatch", "closure", "diversion", "signal_hold"}:
                assert "no road anchor: area-level report" in c["resource_feasibility"]["shortfalls"]
                blocked.append(c["coa_id"])
        assert doc["recommendation"]["top_coa_id"] in ("coa_base", "coa_min", "coa_info")
        # ethics rule 7: more units cannot supply a road anchor — the dissent names the real change
        dissent = doc["recommendation"]["dissent"]
        assert blocked and all(f"resourcing {cid}" not in dissent for cid in blocked)
        assert "resourcing coa_" not in dissent and "RESOURCE-INFEASIBLE" not in dissent
        assert ("cannot be approved until the report has a road-level location (a segment or a junction) — more "
                "units cannot supply one") in dissent
        assert "The more aggressive full-closure COA (coa_agg) is INFEASIBLE (no road anchor: area-level report" in (
            dissent)
        assert "on a notional arterial" in dissent


@pytest.mark.parametrize("kind", BACKENDS)
async def test_404_unknown_held_malformed_and_409_event_closed(kind):
    tag = new_tag()
    async with dss_backend(kind, tag) as bk:
        app, ids = await seed_situations(bk, tag)
        for urn in (f"osint_event:{UNKNOWN}", f"osint_event:{ids['social']}", f"event:{UNKNOWN}",
                    "osint_event:not-a-uuid", "person:" + UNKNOWN, "segment:1035"):
            r = await _gen(app, urn)
            assert r.status_code == 404, (urn, r.text)
        for dss_id in (UNKNOWN, "not-a-uuid"):
            g = await _get(app, dss_id)
            assert g.status_code == 404, dss_id
        # a corridor event subject, then closed
        eid = await create_event(bk, app)
        r = await _gen(app, f"event:{eid}")
        assert r.status_code == 201, r.text
        doc = r.json()
        bk.track_dss(doc["dss_id"])
        DecisionSupport.model_validate(doc)
        assert doc["situation"]["event_class"] == "road_accident"
        assert doc["situation"]["verification_state"] == "OFFICIAL-VERIFIED"
        assert doc["situation"]["segment_id"] == 1045
        assert doc["situation"]["geocode_confidence"] is None
        dissent = doc["recommendation"]["dissent"]
        # the label is derived (the event stores none) and the dissent says so, with who opened it and its status
        assert ("The subject is a corridor event on the city's own channel, opened by an operator; still in "
                "planning (OFFICIAL-VERIFIED, credibility 0.95)") in dissent
        assert "It stores no verification state, so the DSS labels the city's own record OFFICIAL-VERIFIED" in dissent
        assert doc["provenance"]["feeds"] == [] and doc["provenance"]["sources"] == []
        async with client(app) as c:
            moved = await c.post(f"/api/v1/events/{eid}/status",
                                 json={"to_status": "cancelled", "officer": OFFICER, "note": "test cleanup"})
        assert moved.status_code == 200, moved.text
        closed = await _gen(app, f"event:{eid}")
        assert closed.status_code == 409 and closed.json()["detail"] == "event-closed"


@pytest.mark.parametrize("kind", BACKENDS)
async def test_generate_writes_no_action(kind):
    """Compute-only: a generation writes the 022 tables and nothing else (the recording connection)."""
    tag = new_tag()
    async with dss_backend(kind, tag) as bk:
        app, ids = await seed_situations(bk, tag)
        if bk.conn is not None:
            bk.conn.calls.clear()
        r = await _gen(app, f"osint_event:{ids['em_bypass']}")
        assert r.status_code == 201
        bk.track_dss(r.json()["dss_id"])
        if bk.conn is not None:
            from fixtures.dss.fakedss import write_statements

            writes = write_statements(bk.conn.calls)
            assert writes, "a generation persists its proposal"
            for sql in writes:
                assert sql.startswith(("INSERT INTO decision.", "UPDATE decision.")), sql[:80]
            assert bk.db.dispatches == [] and bk.db.dss_log == []
            assert all(e["promoted_event_id"] is None for e in bk.db.events.values())


def test_surrogate_generation_is_under_a_second():
    fx = load_fixture("sector_v_dss_input.json")
    frame = engine.frame_from_poc(fx)
    seg = SegmentModel.from_doc(fx["segment_model"])
    plane = UnitPlane.from_fixture(fx["units"])
    anchors = coa.Anchors(segment_id=1045, junction_id=None, route_segment_ids=(1045,), hold_junction_id=28)
    t0 = time.perf_counter()
    doc, war = engine.compute(frame, seg=seg, anchors=anchors, plane=plane, seed=fx["seed"])
    assert time.perf_counter() - t0 < 1.0
    assert war.method == "surrogate"
    DecisionSupport.model_validate(doc)


async def test_forced_surrogate_mode_and_an_unmigrated_store(monkeypatch):
    tag = new_tag()
    async with dss_backend("fake", tag) as bk:
        app, ids = await seed_situations(bk, tag)
        monkeypatch.setattr(engine, "WARGAME_MODE", "surrogate")
        t0 = time.perf_counter()
        r = await _gen(app, f"osint_event:{ids['em_bypass']}")
        assert time.perf_counter() - t0 < 1.0
        assert r.status_code == 201
        assert r.json()["provenance"]["wargame_method"] == "surrogate"
        bk.db.relations.discard("decision.decision_support")
        from traffic_oracle.city import common

        common.reset_relation_cache()
        r = await _gen(app, f"osint_event:{ids['em_bypass']}", {"horizon_min": 60})
        assert r.status_code == 503 and "022" in r.json()["detail"]


async def test_a_twin_failure_falls_back_to_the_surrogate(monkeypatch):
    tag = new_tag()
    async with dss_backend("fake", tag) as bk:
        app, ids = await seed_situations(bk, tag)

        async def broken(*a, **k):
            raise RuntimeError("twin down")

        monkeypatch.setattr(engine, "TWIN_HOOK", broken)
        r = await _gen(app, f"osint_event:{ids['em_bypass']}")
        assert r.status_code == 201
        doc = r.json()
        assert doc["provenance"]["wargame_method"] == "surrogate"
        assert all("surrogate" in c["predicted_outcome"]["method"] for c in doc["coa_set"])


def _context_ref(tag: str, *, source: str, publisher: str, title: str, credibility: float) -> SourceRef:
    """A synthetic CONTEXT member (role 'context'): what main's get_sources() lists last for a point situation
    with a district-level member attached (migration 023)."""
    return SourceRef(
        signal_id=hashlib.sha1(f"{tag}:{source}:context".encode(), usedforsecurity=False).hexdigest(),
        source=source, publisher=publisher, url=None, title=title, event_class="weather_hazard",
        credibility=credibility, fetch_mode="cached-sample", role="context",
    )


def _with_context(monkeypatch, *extra: SourceRef) -> None:
    real = osint_store.get_sources

    async def get_sources(conn, osint_event_id):
        return [*await real(conn, osint_event_id), *extra]

    monkeypatch.setattr(osint_store, "get_sources", get_sources)


@pytest.mark.parametrize("kind", BACKENDS)
async def test_a_context_member_is_shown_never_counted(kind, monkeypatch):
    """[FIX-B-ORACLE] On main, osint.store.get_sources() also returns a situation's CONTEXT members (role
    'context', listed last), e.g. a district SACHET alert attached to the segment-1045 street report.  The DSS lists
    it in provenance.sources with its role, says "District warning in effect (<publisher>)" in the dissent, and
    never counts it: the feeds, publishers, credibility, independent publishers, composite confidence and the
    whole scoring are what they are without it."""
    tag = new_tag()
    async with dss_backend(kind, tag) as bk:
        app, ids = await seed_situations(bk, tag)
        fixed = datetime.now(UTC)
        monkeypatch.setattr(router, "_now", lambda: fixed)  # both generations at one instant: same TOD demand
        urn = f"osint_event:{ids['em_bypass']}"
        plain = await _gen(app, urn)
        assert plain.status_code == 201, plain.text
        base = plain.json()
        bk.track_dss(base["dss_id"])
        assert "District warning" not in base["recommendation"]["dissent"]
        assert "Context, not corroboration" not in base["recommendation"]["dissent"]

        sachet = _context_ref(tag, source="sachet_cap", publisher="sachet.ndma.gov.in", credibility=0.95,
                              title="Synthetic replica: heavy rain warning for Kolkata district, injuries feared")
        _with_context(monkeypatch, sachet)
        r = await _gen(app, urn)
        assert r.status_code == 201, r.text  # a new member is a new question: a new proposal
        doc = r.json()
        bk.track_dss(doc["dss_id"])
        DecisionSupport.model_validate(doc)
        prov, was = doc["provenance"], base["provenance"]
        # (1) feeds and publishers: the situation's own members only
        assert "sachet_cap" not in prov["feeds"] and "sachet.ndma.gov.in" not in prov["publishers"]
        assert prov["feeds"] == was["feeds"] and prov["publishers"] == was["publishers"]
        # (2) provenance.sources keeps it, listed with its role
        listed = [s for s in prov["sources"] if s["signal_id"] == sachet.signal_id]
        assert len(listed) == 1 and listed[0]["role"] == "context" and listed[0]["source"] == "sachet_cap"
        assert len(prov["sources"]) == len(was["sources"]) + 1
        assert all(s["role"] != "context" for s in was["sources"])
        # (3) the dissent names it as context, never as corroboration
        dissent = doc["recommendation"]["dissent"]
        assert "Context, not corroboration: District warning in effect (sachet.ndma.gov.in)" in dissent
        assert "not counted as corroboration" in dissent
        # nothing it says is counted: credibility, publishers, confidence and the scoring are unchanged
        for key in ("credibility", "independent_publishers", "source_tiers", "verification_state",
                    "cross_type_corroborated", "composite_confidence"):
            assert doc["situation"][key] == base["situation"][key], key
        assert doc["recommendation"]["ranked_coa_ids"] == base["recommendation"]["ranked_coa_ids"]
        assert doc["recommendation"]["value_of_information"] == base["recommendation"]["value_of_information"]
        by_was = {c["coa_id"]: c for c in base["coa_set"]}
        for c in doc["coa_set"]:
            assert c["score"] == by_was[c["coa_id"]]["score"], c["coa_id"]
            assert c["attributes"] == by_was[c["coa_id"]]["attributes"], c["coa_id"]
            assert c["actions"] == by_was[c["coa_id"]]["actions"], c["coa_id"]


@pytest.mark.parametrize("kind", BACKENDS)
async def test_a_non_official_context_member_never_sets_the_injury_cue(kind, monkeypatch):
    """A non-official context member reads "District-level report in effect"; its title's injury words never
    reach the injury cue (the junction robbery report has none, so no 108 and no unserved-injury harm)."""
    tag = new_tag()
    async with dss_backend(kind, tag) as bk:
        app, ids = await seed_situations(bk, tag)
        now = datetime.now(UTC)
        async with bk.pool.acquire() as conn:
            before = await dss_store.load_frame(conn, "osint_event", ids["gariahat"], now=now)
        assert before.injuries is False and before.context == ()
        report = _context_ref(tag, source="google_news_rss", publisher="news-c.example", credibility=0.6,
                              title="Synthetic: several injured as storms hit villages across the district")
        _with_context(monkeypatch, report)
        async with bk.pool.acquire() as conn:
            frame = await dss_store.load_frame(conn, "osint_event", ids["gariahat"], now=now)
        assert frame.injuries is False
        assert frame.context == ({"source": "google_news_rss", "publisher": "news-c.example", "official": False,
                                  "note": "District-level report in effect"},)
        assert frame.feeds == before.feeds and frame.publishers == before.publishers
        assert [s["role"] for s in frame.sources][-1] == "context"
        r = await _gen(app, f"osint_event:{ids['gariahat']}")
        assert r.status_code == 201, r.text
        doc = r.json()
        bk.track_dss(doc["dss_id"])
        DecisionSupport.model_validate(doc)
        assert "Context, not corroboration: District-level report in effect" in doc["recommendation"]["dissent"]
        assert "news-c.example" not in doc["provenance"]["publishers"]
        std = next(c for c in doc["coa_set"] if c["coa_id"] == "coa_std")
        assert all((a["params"] or {}).get("agency") != "ambulance" for a in std["actions"])


def test_context_notes_wording():
    """The literals (main's city.common OSINT context notes), one note per distinct context source."""
    srcs = [
        {"role": "primary", "source": "google_news_rss", "publisher": "news-a.example"},
        {"role": "context", "source": "sachet_cap", "publisher": "sachet.ndma.gov.in"},
        {"role": "context", "source": "sachet_cap", "publisher": "sachet.ndma.gov.in"},
        {"role": "context", "source": "google_news_rss", "publisher": "news-c.example"},
    ]
    assert [n["note"] for n in engine.context_notes(srcs)] == [
        "District warning in effect (sachet.ndma.gov.in)", "District-level report in effect"]
    assert engine.member_sources(srcs) == srcs[:1]


async def test_a_confirmed_corridor_event_keeps_its_label():
    """A stored CONFIRMED verification state is kept (not relabelled OFFICIAL-VERIFIED)."""
    tag = new_tag()
    async with dss_backend("fake", tag) as bk:
        app, _ = await seed_situations(bk, tag)
        eid = await create_event(bk, app)
        bk.db.corridor[eid]["verification_state"] = "CONFIRMED"
        r = await _gen(app, f"event:{eid}")
        assert r.status_code == 201, r.text
        doc = r.json()
        DecisionSupport.model_validate(doc)
        assert doc["situation"]["verification_state"] == "CONFIRMED"
        assert doc["labels"][0] == "CONFIRMED"


async def test_an_emulated_and_a_brain_opened_corridor_event_say_what_they_are():
    """Ethics rule 7: an emulator event is EMULATED (never 'the city's own channel'); an event the brain opened
    for a movement plan says so."""
    tag = new_tag()
    async with dss_backend("fake", tag) as bk:
        app, _ = await seed_situations(bk, tag)
        emu = await create_event(bk, app)
        bk.db.corridor[emu]["metadata"] = {"source": "event-emulator"}
        r = await _gen(app, f"event:{emu}")
        assert r.status_code == 201, r.text
        doc = r.json()
        DecisionSupport.model_validate(doc)
        assert doc["situation"]["verification_state"] == "EMULATED" and doc["labels"] == ["EMULATED", "SIMULATED"]
        dissent = doc["recommendation"]["dissent"]
        assert "The subject is an EMULATED corridor event (the event emulator's, credibility 1.00)" in dissent
        assert "city's own channel" not in dissent and "OFFICIAL source" not in dissent

        brain = await create_event(bk, app, kind="protected_movement")
        bk.db.corridor[brain]["metadata"] = {"source": "convoy-brain", "brain_status": "planned"}
        r = await _gen(app, f"event:{brain}")
        assert r.status_code == 201, r.text
        dissent = r.json()["recommendation"]["dissent"]
        assert "opened by the brain (a movement plan it registered); still in planning" in dissent


@pytest.mark.parametrize("kind", BACKENDS)
async def test_second_order_flags_say_what_the_twin_cascade_did_with_each(kind, monkeypatch):
    """Ethics rule 7, twin+cascade: a live 108 route is fed to the cascade's 108 delay (and said to add none when
    no COA's cascade reaches its road); a live closure with a segment is kept out of the reassignment, and its
    clearance is named as a change only when it lies on an alternative the reassignment would otherwise use (one
    off every alternative is said to have no effect); a protected corridor or a closure with no segment is
    'listed, not modelled'."""
    from osint_common.types import SecondOrderFlag

    tag = new_tag()
    async with dss_backend(kind, tag) as bk:
        app, ids = await seed_situations(bk, tag)
        fixed = datetime.now(UTC)
        monkeypatch.setattr(router, "_now", lambda: fixed)
        urn = f"osint_event:{ids['em_bypass']}"
        plain = await _gen(app, urn)
        assert plain.status_code == 201, plain.text
        bk.track_dss(plain.json()["dss_id"])
        closure = "event:0b7e3c2a-2222-4d1e-9a8b-5c6d7e8f9a03"
        far = "event:0b7e3c2a-2222-4d1e-9a8b-5c6d7e8f9a07"
        flags = [
            SecondOrderFlag(kind="ambulance_route", urn="dispatch:0b7e3c2a-2222-4d1e-9a8b-5c6d7e8f9a04",
                            segment_id=1045, note="a live 108 route crosses the scene"),
            SecondOrderFlag(kind="protected_corridor", urn="event:0b7e3c2a-2222-4d1e-9a8b-5c6d7e8f9a05",
                            segment_id=1045, note="a protected corridor uses the road"),
            SecondOrderFlag(kind="closure", urn=closure, segment_id=1047, note="a live closure nearby"),
            SecondOrderFlag(kind="closure", urn="event:0b7e3c2a-2222-4d1e-9a8b-5c6d7e8f9a06", segment_id=None,
                            note="a live closure with no segment"),
            SecondOrderFlag(kind="closure", urn=far, segment_id=999999, note="a live closure far away"),
            SecondOrderFlag(kind="ambulance_route", urn="dispatch:0b7e3c2a-2222-4d1e-9a8b-5c6d7e8f9a08",
                            segment_id=999998, note="a live 108 route far away"),
        ]
        real = osint_store.get_event

        async def get_event(conn, oid, *, now=None):
            ev = await real(conn, oid, now=now)
            return ev.model_copy(update={"second_order": flags}) if ev is not None and oid == ids["em_bypass"] else ev

        monkeypatch.setattr(osint_store, "get_event", get_event)
        r = await _gen(app, urn)
        assert r.status_code == 201, r.text
        doc = r.json()
        bk.track_dss(doc["dss_id"])
        DecisionSupport.model_validate(doc)
        assert doc["provenance"]["wargame_method"] == "twin+cascade"
        dissent = doc["recommendation"]["dissent"]
        assert "dispatch:0b7e3c2a-2222-4d1e-9a8b-5c6d7e8f9a04 (segment 1045) — fed to the cascade's 108 delay; " in (
            dissent)
        assert ("dispatch:0b7e3c2a-2222-4d1e-9a8b-5c6d7e8f9a08 (segment 999998) — fed to the cascade's 108 delay (no "
                "COA's cascade reaches its road, so it adds none)") in dissent
        corridor = "protected corridor event:0b7e3c2a-2222-4d1e-9a8b-5c6d7e8f9a05"
        assert f"{corridor} (segment 1045) — listed, not modelled" in dissent
        assert (f"closure {closure} (segment 1047) — kept out of the cascade's reassignment (it lies on an "
                "alternative the reassignment would use)") in dissent
        assert (f"closure {far} (segment 999999) — kept out of the cascade's reassignment (on none of its "
                "alternatives, so no effect)") in dissent
        assert (f"A cleared closure would change the reassignment: {closure} (segment 1047) lies on an alternative "
                "road the reassignment would otherwise use, and is kept out of it; once it clears, regenerate") in (
            dissent)
        assert f"{far} (segment 999999) lies on" not in dissent
        assert ("A live closure (event:0b7e3c2a-2222-4d1e-9a8b-5c6d7e8f9a06) is flagged but not modelled by the "
                "cascade") in dissent
        assert "weighed" not in dissent and "surrogate wargame models none" not in dissent
        # the closure really reached the reassignment: Major Arterial Road (1047) is no longer an alternative
        by_was = {c["coa_id"]: c for c in plain.json()["coa_set"]}
        agg = next(c for c in doc["coa_set"] if c["coa_id"] == "coa_agg")
        was_routes = by_was["coa_agg"]["predicted_outcome"]["cascade"]["parallel_routes_loaded"]
        now_routes = agg["predicted_outcome"]["cascade"]["parallel_routes_loaded"]
        assert "Major Arterial Road (New Town)" in was_routes and "Major Arterial Road (New Town)" not in now_routes
