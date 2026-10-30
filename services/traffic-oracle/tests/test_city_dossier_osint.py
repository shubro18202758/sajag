"""The city dossier of a situation carries its per-signal sources (FIX-E, ruling R2).

    * ``sources[]`` — one row per REPORT the situation stands on: publisher,
      tier, the (already-redacted) title, the fetch mode, and a url on the
      OFFICIAL tiers only (a news/social URL may name a person; it is never
      stored, never sent);
    * ``source_notes`` — beside them, in the same order, keyed by signal_id:
      the tier and, for a news or social source, the honest withheld-link
      note;
    * ``context_sources`` — the district alerts in effect there, listed
      APART (context, never corroboration);
    * ``context_members`` — the count of those context members, read in the
      dossier's own SQL through ``common.OSINT_CONTEXT_MEMBERS_SQL`` (the
      same subquery the snapshot's entities and the city feed select), and
      the fake store's ``view()`` supplies it like the real row does.

Hermetic fake-backend tests (the test_city_router pattern).
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path

from fixtures.osint.fakedb import FakeOsintConn, FakeOsintDB, FakePool
from traffic_oracle.city import common
from traffic_oracle.city import dossier as dos
from traffic_oracle.city import feed as feed_mod

NOW = datetime.now(timezone.utc)


def _seed() -> tuple[FakeOsintConn, FakeOsintDB, dict[str, str]]:
    """A situation standing on two street reports (fictional news publishers), an OFFICIAL
    corroborating member (a SACHET CAP alert resolved at the same street point, carrying its
    url — the official url is the only kind the dossier ever keeps), and the district SACHET
    alert in effect there as the CONTEXT member, fused as one situation on a bare fake."""
    from fixtures.osint.harness import client, make_app
    from fixtures.osint.signals import FakePipeline, canonical_set, new_tag, payload, rekey
    from traffic_oracle.osint import store as osint_store

    tag = new_tag()
    db = FakeOsintDB()
    pool = FakePool(FakeOsintConn(db))
    osint_store.GAZETTEER_LOADER = lambda: []  # tests never sync the real gazetteer
    sets = canonical_set(tag)
    alert = sets["sachet_district"]
    cap = rekey(
        sets["sachet_district"],
        f"{tag}-cap",
        title="Thunderstorm warning issued for the Park Street area",
        url="https://sachet.ndma.gov.in/cap/sample-2026",
        category_hint=["CAP", "cluster:em_bypass"],  # resolved at the street point: a REPORTING member
    )
    ctx = rekey(
        sets["sachet_district"],
        f"{tag}-ctx",
        title="Heavy rainfall warning for Kolkata district",
        url="https://sachet.ndma.gov.in/cap/sample-ctx",
        category_hint=[*alert.category_hint, "cluster:sachet-district"],  # the district: CONTEXT
    )
    report = rekey(
        sets["em_bypass"][0],
        f"{tag}-storm",
        title="Thunderstorm uproots trees near the Park Street crossing",
        text="Thunderstorm uproots trees near the Park Street crossing; traffic slowed.",
        category_hint=[*sets["em_bypass"][0].category_hint, "cluster:em_bypass"],  # the fixture's street point
        published_at=alert.published_at,
        pii_redactions=0,
    )
    second = rekey(
        sets["em_bypass"][1],
        f"{tag}-crash",
        title="Car crashes into three vehicles near the Park Street crossing",
        text="Car crashes into three vehicles near the Park Street crossing.",
        category_hint=[*sets["em_bypass"][1].category_hint, "cluster:em_bypass"],
        published_at=alert.published_at,
        pii_redactions=0,
    )
    pipe = FakePipeline(tag)
    pipe.groups = {
        report.signal_id: "storm",
        second.signal_id: "storm",
        cap.signal_id: "storm",
        ctx.signal_id: "storm",
    }
    app = make_app(pool, pipe)

    async def run() -> dict[str, str]:
        async with client(app) as c:
            r = await c.post(
                "/api/v1/osint/signals", json={"signals": [payload(report), payload(second), payload(cap), payload(ctx)]}
            )
            assert r.status_code == 200, r.text
            (sit,) = r.json()["resolved"]
        return {
            "em_bypass": sit["osint_event_id"],
            "report": report.signal_id,
            "second": second.signal_id,
            "official": cap.signal_id,
            "ctx": ctx.signal_id,
            "social": "",
        }

    return FakeOsintConn(db), db, asyncio.run(run())


def _roles(conn: FakeOsintConn, oid: str) -> tuple[set[str], set[str]]:
    """(reporting signal ids, context signal ids) of one situation."""
    reporting: set[str] = set()
    context: set[str] = set()
    for (o, sid), role in conn.db.sources.items():
        if o != oid:
            continue
        (context if role == "context" else reporting).add(sid)
    return reporting, context


def test_the_dossier_carries_its_per_signal_sources():
    conn, _db, ids = _seed()
    reporting, context = _roles(conn, ids["em_bypass"])
    assert reporting == {ids["report"], ids["second"], ids["official"]} and context == {ids["ctx"]}, (
        reporting,
        context,
    )

    dossier = asyncio.run(dos.build_dossier(conn, "osint_event", ids["em_bypass"], now=NOW))
    assert dossier is not None
    props = dossier["entity"]["props"]

    # context_members: the store's own count, selected by the dossier SQL
    assert props["context_members"] == len(context), props["context_members"]

    # sources[]: the REPORTS only, never a context member
    sources = props["sources"]
    assert {s["signal_id"] for s in sources} == reporting, sources
    by_id = {s["signal_id"]: s for s in sources}
    # the OFFICIAL reporting member keeps its url (R2a): the official url is the only kind
    # the dossier ever sends, and the test seeds one so the keeping is actually exercised
    assert by_id[ids["official"]]["tier"] == "official", by_id[ids["official"]]
    assert by_id[ids["official"]]["url"] == "https://sachet.ndma.gov.in/cap/sample-2026", by_id[ids["official"]]
    for s in sources:
        assert set(s) >= {"publisher", "tier", "title", "fetch_mode", "url", "signal_id"}, s
        assert s["title"] and len(s["title"]) <= 1000
        if s["tier"] == "official":
            assert s["url"], s
        else:
            assert s["url"] is None, s  # a news/social url is never stored, never sent
        assert s["fetch_mode"], s

    # source_notes: the same order, keyed by signal_id, the honest withheld note
    notes = props["source_notes"]
    assert [n["signal_id"] for n in notes] == [s["signal_id"] for s in sources], notes
    for n, s in zip(notes, sources, strict=True):
        assert n["source_tier"] == s["tier"]
        assert (n["link_note"] is None) == (s["tier"] == "official"), n

    # context_sources: listed apart, never inside sources; the district alert's own official
    # url is kept there too
    ctx = props["context_sources"]
    assert {c["signal_id"] for c in ctx} == context, ctx
    assert not {c["signal_id"] for c in ctx} & reporting
    assert all(c["url"] == "https://sachet.ndma.gov.in/cap/sample-ctx" for c in ctx), ctx


def test_an_unknown_situation_is_never_a_dossier():
    conn, _db, _ids = _seed()
    assert asyncio.run(dos.build_dossier(conn, "osint_event", "00000000-0000-4000-8000-000000000000", now=NOW)) is None


def test_the_city_feed_reads_context_members_through_the_shared_constant():
    """Item 10: feed.py imports common.OSINT_CONTEXT_MEMBERS_SQL — no inline copy."""
    src = Path(feed_mod.__file__).read_text()
    header = "\n".join(src.splitlines()[:220])
    assert "OSINT_CONTEXT_MEMBERS_SQL" in header, "feed.py does not import the shared constant"
    assert "es.role = 'context') AS context_members" not in src, "the inline copy is still there"
    assert common.OSINT_CONTEXT_MEMBERS_SQL in feed_mod._SQL_FEED_OSINT_SURFACED


def test_the_dossier_sql_selects_the_context_members_column():
    assert common.OSINT_CONTEXT_MEMBERS_SQL in dos._SQL_DOSSIER_OSINT_EVENT
