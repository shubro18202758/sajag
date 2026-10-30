"""GET /api/v1/vehicles/lookup + /lookups — the audited full-mark search
(FIX-C-PLATESEARCH; hardened by FIX-AUDIT-A).

Officer-only: the deck-verified ``x-sajag-officer`` header (loopback
only), checked BEFORE the plate, the pool and any read or write — an
anonymous caller gets the 409 and nothing else, for a malformed mark too
(never a 422), and a query or body officer claim is never accepted.
Every COMPLETED lookup, found or not, writes exactly ONE
``corridor.vehicle_lookup_audit`` row whose mark crosses the wire only
MASKED — never hashed (migration 025 dropped the reversible
``mark_sha256``) and never in clear.  No log record (structlog or
stdlib) carries the canonical mark.  The throttled retention reap runs
before the vehicle row and the disclosure basis, and reaps old audit
rows too.  Reads leave only under the existing C6 rule
(``store.disclosure_basis``): earmarked → the whole trail, evidence-only
→ the evidence reads, neither → ``reads: []`` plus the honest note (a
200, not /sightings' 404).

Fake pool through the REAL vehicles router (test_vehicles_watchlist's
canned-table block): the 409 ordering, the 422s, the C6 mapping, the
audit-write contract.  A DB-backed variant against the int3c sandbox
lives at the bottom, behind SAJAG_TEST_PG_DSN.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from structlog.testing import capture_logs

from traffic_oracle.city.common import mask_plate
from traffic_oracle.vehicles import store as vstore

pytest.importorskip("httpx")

from httpx import ASGITransport, AsyncClient  # noqa: E402

T0 = datetime(2026, 11, 5, 5, 0, 0, tzinfo=timezone.utc)
LOCAL = "http://127.0.0.1"
HEADER = {"x-sajag-officer": "Duty%20Officer%20A"}
OFFICER = "Duty Officer A"
MARK = "WB06EM9001"

#: Pinned by the FIX-C-PLATESEARCH contract — the module must export
#: byte-identical constants and the wire bodies must carry them verbatim
#: (ASCII hyphen in the 409 reason, em-dash in the note).
OFFICER_REQUIRED_DETAIL = {
    "error": "officer-required",
    "reason": "x-sajag-officer header absent - a full-mark vehicle lookup is "
              "officer-only and audited; nothing was looked up and nothing "
              "was written",
}
NO_BASIS_NOTE = (
    "No lawful basis to show this vehicle's camera reads — earmark it "
    "with a lawful basis to proceed"
)
LOOKUP_INVALID_PLATE_DETAIL = (
    "not a registration plate: expected a state code, a district number, an optional series and a "
    "4-digit number (for example 'MH 01 AB' then 4 digits), or a BH-series plate (the input is not "
    "echoed back)"
)


@pytest.fixture(autouse=True)
def _quiet_reaper():
    """The process-wide reaper is throttled; start each test 'just ran'
    (the reap-ordering test below makes it due on purpose)."""
    vstore.REAPER.reset()
    vstore.REAPER._last_attempt = vstore.REAPER._clock()
    yield
    vstore.REAPER.reset()


# ── fake pool + router (test_vehicles_watchlist's block) ────────────────────


@dataclass
class FakeRow(dict):
    """A dict row (asyncpg Record-like: r['col'])."""

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)

    def __getitem__(self, k):
        return dict.__getitem__(self, k)


@dataclass
class FakeTransaction:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


@dataclass
class FakeConn:
    store: "FakeStore"

    async def fetchrow(self, sql, *args):
        return self.store.fetchrow(sql, args)

    async def fetch(self, sql, *args):
        return self.store.fetch(sql, args)

    def transaction(self):
        return FakeTransaction()


@dataclass
class FakeAcquire:
    conn: FakeConn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, *exc):
        return False


@dataclass
class FakeStore:
    """Fake asyncpg pool: routes by SQL substring to canned rows.

    ``matches``: list of (substring, rows_or_row) tried in order per call.
    """

    matches: list = field(default_factory=list)
    calls: list = field(default_factory=list)

    def _rows_for(self, sql):
        for needle, rows in self.matches:
            if needle in sql:
                return rows if isinstance(rows, list) else [rows]
        return []

    def fetchrow(self, sql, args):
        self.calls.append(("fetchrow", sql, args))
        rows = self._rows_for(sql)
        return rows[0] if rows else None

    def fetch(self, sql, args):
        self.calls.append(("fetch", sql, args))
        return self._rows_for(sql)

    def acquire(self):
        return FakeAcquire(FakeConn(self))


def _client(store: FakeStore, base_url: str = "http://testserver") -> TestClient:
    """``base_url`` sets the server address the request 'arrived' on: the
    x-sajag-officer header is honoured only on a loopback one."""
    app = FastAPI()
    app.state.pool = store
    from traffic_oracle.vehicles import router as vehicles_router

    app.include_router(vehicles_router)
    return TestClient(app, base_url=base_url)


def _read_rows(n: int = 2) -> list:
    return [
        FakeRow(sighting_id=uuid.uuid4(), plate=MARK, camera_id=f"EM-CAM-0{i}",
                t=T0 + timedelta(minutes=i), lon=88.37 + i / 100, lat=22.53,
                speed_kmh=52.0 + i, heading=10.0, vehicle_class="car",
                source="emulated_anpr", run_id=uuid.uuid4(),
                matched_plate_hit=True)
        for i in range(n)
    ]


def _found_store(vid, *, earmarked, lawful_reads, earmark_row="default",
                 reads="default", plate=MARK):
    if earmark_row == "default":
        earmark_row = FakeRow(state="watch", reason="FIR-linked stolen plate",
                              lawful_basis="stolen_vehicle_fir",
                              retention_until=T0 + timedelta(days=30))
    if reads == "default":
        reads = _read_rows()
    return FakeStore(matches=[
        ("FROM corridor.vehicles WHERE plate = $1",
         FakeRow(vehicle_id=vid, plate=plate, vehicle_class="car")),
        ("AS lawful_reads", FakeRow(earmarked=earmarked, lawful_reads=lawful_reads)),
        ("ORDER BY earmarked_at DESC LIMIT 1", earmark_row),
        ("AND status = 'pending'",
         [FakeRow(recommendation_id=uuid.uuid4(), rule_id="R_SPD_SEGMENT",
                  status="pending")]),
        ("event_kind = 'vehicle_pursuit'",
         [FakeRow(event_id=uuid.uuid4(), status="approved",
                  recommendation_id=str(uuid.uuid4()))]),
        ("ST_X(s.position)", reads),
        ("INSERT INTO corridor.vehicle_lookup_audit",
         FakeRow(id=uuid.uuid4(), looked_up_at=T0)),
    ])


def _audit_args(store: FakeStore) -> list:
    return [a for _kind, sql, a in store.calls
            if "INSERT INTO corridor.vehicle_lookup_audit" in sql]


_HEX_DIGEST_RE = re.compile(r"^[0-9a-f]{32,128}$", re.I)


def _digests(canonical: str) -> set[str]:
    """Every common hash of the canonical mark (hex), any case."""
    out = set()
    for name in ("md5", "sha1", "sha224", "sha256", "sha384", "sha512"):
        for text in (canonical, canonical.lower()):
            out.add(hashlib.new(name, text.encode()).hexdigest())
    return out


def _assert_no_hash_of_the_mark(args: tuple, canonical: str) -> None:
    """No argument is a hash of the mark, nor any hex digest at all
    (an unsalted hash of a mask-hiding-3-digits mark falls to 1000 tries)."""
    for a in args:
        assert not (isinstance(a, str) and _HEX_DIGEST_RE.match(a)), a
        assert a not in _digests(canonical)


def _assert_one_masked_audit_row(store: FakeStore, canonical: str,
                                 found: bool, disclosure: str) -> None:
    """Every completed officer lookup writes EXACTLY ONE audit row whose
    arguments carry the MASKED mark and nothing else about it — never the
    canonical mark and never a hash of it (migration 025) — while the
    vehicle SELECT necessarily binds the mark: that IS the lookup."""
    inserts = _audit_args(store)
    assert len(inserts) == 1
    officer, masked, found_arg, disclosure_arg = inserts[0]
    assert officer == OFFICER
    assert masked == mask_plate(canonical)
    assert found_arg is found and disclosure_arg == disclosure
    assert canonical not in inserts[0]  # never the raw mark, in the audit
    _assert_no_hash_of_the_mark(inserts[0], canonical)
    (sql,) = [q for _k, q, _a in store.calls
              if "INSERT INTO corridor.vehicle_lookup_audit" in q]
    assert "sha" not in sql.lower()  # no hash column is written


class TestOfficerGate:
    def test_no_officer_is_409_and_nothing_is_read_or_written(self):
        store = FakeStore()
        r = _client(store, base_url=LOCAL).get(
            "/api/v1/vehicles/lookup", params={"plate": MARK}
        )
        assert r.status_code == 409
        assert r.json() == {"detail": OFFICER_REQUIRED_DETAIL}
        assert store.calls == []  # the officer check precedes every read

    def test_header_off_loopback_is_still_409(self):
        """A non-loopback connection gets None from authenticated_officer
        (units/router.py) — the same 409, nothing else."""
        store = FakeStore()
        r = _client(store).get(  # http://testserver: not loopback
            "/api/v1/vehicles/lookup", params={"plate": MARK}, headers=HEADER
        )
        assert r.status_code == 409
        assert r.json() == {"detail": OFFICER_REQUIRED_DETAIL}
        assert store.calls == []

    def test_malformed_officer_header_is_422_before_anything(self):
        store = FakeStore()
        r = _client(store, base_url=LOCAL).get(
            "/api/v1/vehicles/lookup", params={"plate": MARK},
            headers={"x-sajag-officer": "Duty%00Officer"},
        )
        assert r.status_code == 422
        assert store.calls == []

    def test_officer_gate_precedes_the_pool_409_not_503(self):
        """Without a pool an anonymous caller still gets the 409 (gate
        first); a named officer only then reaches the 503."""
        app = FastAPI()
        from traffic_oracle.vehicles import router as vehicles_router

        app.include_router(vehicles_router)
        c = TestClient(app, base_url=LOCAL)
        assert c.get("/api/v1/vehicles/lookup",
                     params={"plate": MARK}).status_code == 409
        assert c.get("/api/v1/vehicles/lookup", params={"plate": MARK},
                     headers=HEADER).status_code == 503

    @pytest.mark.parametrize("params", [
        {"plate": "NOT-A-PLATE!!"},
        {"plate": "WB06EM9001!!"},   # a mark with junk: malformed, still 409
        {"plate": "A" * 33},         # over the length bound
        {"plate": ""},
        {},                          # no plate at all
    ])
    def test_anonymous_malformed_plate_is_409_never_422(self, params):
        """The gate precedes EVERY plate check — presence, length and shape
        (audit A, PS-M2): an anonymous caller cannot tell a well-formed
        mark from a malformed one, and FastAPI never validates first."""
        store = FakeStore()
        for c, headers in ((_client(store, base_url=LOCAL), None),  # no header
                           (_client(store), HEADER)):  # a header off loopback
            r = c.get("/api/v1/vehicles/lookup", params=params, headers=headers)
            assert r.status_code == 409, (params, r.text)
            assert r.json() == {"detail": OFFICER_REQUIRED_DETAIL}
        assert store.calls == []

    @pytest.mark.parametrize("params", [
        {"officer": OFFICER},
        {"x-sajag-officer": "Duty%20Officer%20A"},
        {"x_sajag_officer": OFFICER},
        {"earmarked_by": OFFICER},
    ])
    def test_a_query_officer_claim_is_never_accepted(self, params):
        """Header-only attribution (audit A, PS-M10): a query parameter
        naming an officer is a 409, nothing read, nothing written."""
        store = FakeStore()
        r = _client(store, base_url=LOCAL).get(
            "/api/v1/vehicles/lookup", params={"plate": MARK, **params}
        )
        assert r.status_code == 409, r.text
        assert r.json() == {"detail": OFFICER_REQUIRED_DETAIL}
        assert store.calls == []

    @pytest.mark.parametrize("body", [
        {"officer": OFFICER},
        {"earmarked_by": OFFICER},
        {"x-sajag-officer": OFFICER},
    ])
    def test_a_body_officer_claim_is_never_accepted(self, body):
        store = FakeStore()
        c = _client(store, base_url=LOCAL)
        r = c.request("GET", "/api/v1/vehicles/lookup",
                      params={"plate": MARK}, json=body)
        assert r.status_code == 409, r.text
        r = c.request("GET", "/api/v1/vehicles/lookups", json=body)
        assert r.status_code == 409, r.text
        assert store.calls == []


class TestLookupValidation:
    def test_malformed_mark_with_officer_is_422_and_unaudited(self):
        store = FakeStore()
        r = _client(store, base_url=LOCAL).get(
            "/api/v1/vehicles/lookup", params={"plate": "NOT-A-PLATE!!"},
            headers=HEADER,
        )
        assert r.status_code == 422
        assert r.json()["detail"].startswith("not a registration plate:")
        assert store.calls == []  # normalization precedes the pool
        assert _audit_args(store) == []

    @pytest.mark.parametrize("plate", ["MH12AB3456!!", "MH12AB34567", "mh12ab3456x"])
    def test_a_malformed_plate_is_never_echoed(self, plate):
        """A near-mark is a mark in all but one character: the 422 never
        repeats the input (normalize_plate's own message would)."""
        store = FakeStore()
        r = _client(store, base_url=LOCAL).get(
            "/api/v1/vehicles/lookup", params={"plate": plate}, headers=HEADER,
        )
        assert r.status_code == 422
        assert r.json() == {"detail": LOOKUP_INVALID_PLATE_DETAIL}
        assert plate not in r.text and "3456" not in r.text
        assert store.calls == []

    def test_overlong_plate_param_is_fastapi_422(self):
        store = FakeStore()
        r = _client(store, base_url=LOCAL).get(
            "/api/v1/vehicles/lookup", params={"plate": "A" * 33},
            headers=HEADER,
        )
        assert r.status_code == 422
        assert store.calls == []

    def test_module_exports_the_pinned_constants(self):
        from traffic_oracle import vehicles

        assert vehicles.OFFICER_REQUIRED_DETAIL == OFFICER_REQUIRED_DETAIL
        assert vehicles.NO_BASIS_NOTE == NO_BASIS_NOTE
        assert vehicles.LOOKUP_INVALID_PLATE_DETAIL == LOOKUP_INVALID_PLATE_DETAIL


class TestLookupDisclosure:
    def test_earmarked_vehicle_gets_the_whole_lawful_trail(self):
        vid = uuid.uuid4()
        store = _found_store(vid, earmarked=True, lawful_reads=True)
        # a spaced/dashed spelling normalizes to the one canonical mark
        r = _client(store, base_url=LOCAL).get(
            "/api/v1/vehicles/lookup", params={"plate": "wb 06 em-9001"},
            headers=HEADER,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["found"] is True
        assert body["mark"] == MARK  # full mark: the officer is named
        assert body["mark_masked"] == mask_plate(MARK) == "WB06EM•••1"
        assert body["vehicle_id"] == str(vid)
        assert body["vehicle_class"] == "car"
        assert body["earmark"] == {
            "state": "watch",
            "reason": "FIR-linked stolen plate",
            "lawful_basis": "stolen_vehicle_fir",
            "retention_until": (T0 + timedelta(days=30)).isoformat(),
        }
        assert body["open_recommendations"] == [
            {"recommendation_id": body["open_recommendations"][0]
                ["recommendation_id"],
             "rule_id": "R_SPD_SEGMENT", "status": "pending"}
        ]
        (pursuit,) = body["open_pursuits"]
        assert set(pursuit) == {"event_id", "status", "recommendation_id"}
        assert pursuit["status"] == "approved"
        assert body["disclosure"] == "active_earmark"
        assert body["note"] is None
        assert body["source"] == "emulated_anpr"
        assert len(body["reads"]) == 2
        assert set(body["reads"][0]) == {
            "sighting_id", "plate", "camera_id", "t", "position",
            "speed_kmh", "heading", "vehicle_class", "source", "run_id",
            "matched_plate_hit",
        }
        assert body["reads"][0]["plate"] == MARK
        assert body["audit"] == {
            "officer": OFFICER, "looked_up_at": T0.isoformat(),
            "mark_masked": "WB06EM•••1", "found": True,
            "disclosure": "active_earmark",
        }
        # the vehicle row is looked up by the CANONICAL mark ...
        (veh_args,) = [a for _k, sql, a in store.calls
                       if "FROM corridor.vehicles WHERE plate = $1" in sql]
        assert veh_args == (MARK,)
        # ... reads are the /sightings default cap, never a client limit
        (reads_args,) = [a for _k, sql, a in store.calls
                         if "ST_X(s.position)" in sql]
        assert reads_args == (vid, 100)
        _assert_one_masked_audit_row(store, MARK, True, "active_earmark")

    def test_a_client_limit_parameter_is_not_honoured(self):
        vid = uuid.uuid4()
        store = _found_store(vid, earmarked=True, lawful_reads=True)
        r = _client(store, base_url=LOCAL).get(
            "/api/v1/vehicles/lookup",
            params={"plate": MARK, "limit": "1"},  # not a route parameter
            headers=HEADER,
        )
        assert r.status_code == 200
        (reads_args,) = [a for _k, sql, a in store.calls
                         if "ST_X(s.position)" in sql]
        assert reads_args == (vid, 100)

    def test_evidence_only_gets_the_evidence_reads(self):
        vid = uuid.uuid4()
        store = _found_store(vid, earmarked=False, lawful_reads=True,
                             earmark_row=None)
        r = _client(store, base_url=LOCAL).get(
            "/api/v1/vehicles/lookup", params={"plate": MARK}, headers=HEADER
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["disclosure"] == "evidence_only"
        assert body["earmark"] is None
        assert body["note"] is None
        assert len(body["reads"]) == 2
        # the SAME fetch_sightings call — there is no second, widened query
        (reads_args,) = [a for _k, sql, a in store.calls
                         if "ST_X(s.position)" in sql]
        assert reads_args == (vid, 100)
        _assert_one_masked_audit_row(store, MARK, True, "evidence_only")

    def test_no_basis_withholds_reads_and_says_so(self):
        vid = uuid.uuid4()
        store = _found_store(vid, earmarked=False, lawful_reads=False,
                             earmark_row=None, reads=[])
        r = _client(store, base_url=LOCAL).get(
            "/api/v1/vehicles/lookup", params={"plate": MARK}, headers=HEADER
        )
        assert r.status_code == 200, r.text  # not /sightings' 404
        body = r.json()
        assert body["found"] is True
        assert body["disclosure"] == "none"
        assert body["reads"] == []
        assert body["note"] == NO_BASIS_NOTE  # the verbatim honest sentence
        # C6 withholds the reads only: identity, state, recommendations and
        # pursuits are still the officer's to see
        assert body["earmark"] is None
        assert len(body["open_recommendations"]) == 1
        assert len(body["open_pursuits"]) == 1
        assert not any("ST_X(s.position)" in sql for _k, sql, _a in store.calls)
        _assert_one_masked_audit_row(store, MARK, True, "none")

    def test_unknown_mark_answers_found_false_exactly_like_a_known_one(self):
        store = FakeStore(matches=[
            ("INSERT INTO corridor.vehicle_lookup_audit",
             FakeRow(id=uuid.uuid4(), looked_up_at=T0)),
        ])
        r = _client(store, base_url=LOCAL).get(
            "/api/v1/vehicles/lookup", params={"plate": "22BH1234AA"},
            headers=HEADER,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["found"] is False
        assert body["mark"] == "22BH1234AA"  # a BH-series mark normalizes too
        assert body["mark_masked"] == mask_plate("22BH1234AA")
        assert body["vehicle_id"] is None and body["vehicle_class"] is None
        assert body["earmark"] is None
        assert body["open_recommendations"] == []
        assert body["open_pursuits"] == []
        assert body["disclosure"] == "none"
        assert body["reads"] == [] and body["note"] is None
        assert body["audit"]["found"] is False
        # an unknown mark is ONE vehicle read + ONE audit write, nothing else
        assert len(store.calls) == 2
        _assert_one_masked_audit_row(store, "22BH1234AA", False, "none")

    def test_every_officer_call_writes_exactly_one_audit_row(self):
        """Two completed lookups in one store: two INSERTs — one per
        lookup, whatever the disclosure turned out to be."""
        vid = uuid.uuid4()
        store = _found_store(vid, earmarked=False, lawful_reads=False,
                             earmark_row=None, reads=[])
        c = _client(store, base_url=LOCAL)
        c.get("/api/v1/vehicles/lookup", params={"plate": MARK}, headers=HEADER)
        c.get("/api/v1/vehicles/lookup", params={"plate": "wb-06-em-9001"},
              headers=HEADER)
        assert len(_audit_args(store)) == 2
        # both rows describe the same canonical mark, masked — never hashed
        for args in _audit_args(store):
            assert args == (OFFICER, mask_plate(MARK), True, "none")
            _assert_no_hash_of_the_mark(args, MARK)


class TestNothingLogsTheMark:
    """No log record anywhere — structlog events or stdlib records, at any
    level — carries a canonical mark (audit A, PS-M15).  The route logs
    the MASK; the access line is masked by logfilters (test_access_log_mask)."""

    def _lookups(self, caplog) -> tuple[list[dict], list[logging.LogRecord]]:
        vid = uuid.uuid4()
        caplog.set_level(logging.DEBUG)
        with capture_logs() as events:
            for store, plate, headers in (
                (_found_store(vid, earmarked=True, lawful_reads=True), "wb 06 em-9001", HEADER),
                (_found_store(vid, earmarked=False, lawful_reads=False,
                              earmark_row=None, reads=[]), MARK, HEADER),
                (FakeStore(matches=[("INSERT INTO corridor.vehicle_lookup_audit",
                                     FakeRow(id=uuid.uuid4(), looked_up_at=T0))]),
                 "22BH1234AA", HEADER),
                (FakeStore(), MARK, None),               # anonymous 409
                (FakeStore(), MARK + "!!", HEADER),      # malformed 422
            ):
                _client(store, base_url=LOCAL).get(
                    "/api/v1/vehicles/lookup", params={"plate": plate}, headers=headers
                )
        return events, list(caplog.records)

    def test_no_structlog_event_or_stdlib_record_carries_the_mark(self, caplog):
        events, records = self._lookups(caplog)
        looked_up = [e for e in events if e.get("event") == "vehicles.vehicle_looked_up"]
        assert len(looked_up) == 3  # one per completed lookup: the logging is live
        assert {e["mark_masked"] for e in looked_up} == {
            mask_plate(MARK), mask_plate("22BH1234AA")}
        # the oracle's records only: httpx/httpcore are the TEST CLIENT's own
        # loggers (they print the URL it sent; the oracle never uses them here)
        records = [r for r in records if not r.name.startswith(("httpx", "httpcore"))]
        for text in [repr(e) for e in events] + [r.getMessage() for r in records]:
            for mark in (MARK, "22BH1234AA"):
                assert mark not in text and mark.lower() not in text, text
                for digest in _digests(mark):
                    assert digest not in text


class TestReapBeforeDisclosure:
    """Like /sightings (test_vehicle_privacy's ordering test): the throttled
    retention reap is attempted FIRST — before the vehicle row and the
    disclosure basis — so a read the reap removes is never disclosed, and
    the lookup audit's own retention runs with it (audit A, S3)."""

    def _due_store(self, vid, **kw) -> FakeStore:
        store = _found_store(vid, **kw)
        store.matches.insert(0, ("pg_try_advisory_xact_lock", FakeRow(got=True)))
        return store

    def test_reap_runs_before_the_vehicle_row_and_the_basis(self):
        vstore.REAPER.reset()  # due
        vid = uuid.uuid4()
        store = self._due_store(vid, earmarked=True, lawful_reads=True)
        r = _client(store, base_url=LOCAL).get(
            "/api/v1/vehicles/lookup", params={"plate": MARK}, headers=HEADER
        )
        assert r.status_code == 200, r.text
        sqls = [sql for _k, sql, _a in store.calls]
        first = {needle: next(i for i, q in enumerate(sqls) if needle in q)
                 for needle in ("pg_try_advisory_xact_lock",
                                "DELETE FROM corridor.vehicle_lookup_audit",
                                "FROM corridor.vehicles WHERE plate = $1",
                                "AS lawful_reads", "ST_X(s.position)")}
        assert (first["pg_try_advisory_xact_lock"]
                < first["DELETE FROM corridor.vehicle_lookup_audit"]
                < first["FROM corridor.vehicles WHERE plate = $1"]
                < first["AS lawful_reads"] < first["ST_X(s.position)"])
        deletes = [q for q in sqls if q.lstrip().upper().startswith("DELETE")]
        assert deletes == [vstore.REAP_DEFAULT_SQL, vstore.REAP_EARMARKED_SQL,
                           vstore.REAP_ORPHAN_VEHICLES_SQL, vstore.REAP_LOOKUP_AUDIT_SQL]
        (audit_reap_args,) = [a for _k, q, a in store.calls
                              if q == vstore.REAP_LOOKUP_AUDIT_SQL]
        assert audit_reap_args == (vstore.LOOKUP_AUDIT_RETENTION_DAYS,)
        assert vstore.REAPER.due() is False  # throttled: not per lookup

    def test_an_unknown_mark_reaps_too_and_an_anonymous_call_never(self):
        vstore.REAPER.reset()  # due
        store = FakeStore()
        r = _client(store, base_url=LOCAL).get(
            "/api/v1/vehicles/lookup", params={"plate": MARK})
        assert r.status_code == 409 and store.calls == []
        assert vstore.REAPER.due() is True  # the gate precedes the reap
        store = FakeStore(matches=[
            ("pg_try_advisory_xact_lock", FakeRow(got=True)),
            ("INSERT INTO corridor.vehicle_lookup_audit",
             FakeRow(id=uuid.uuid4(), looked_up_at=T0)),
        ])
        r = _client(store, base_url=LOCAL).get(
            "/api/v1/vehicles/lookup", params={"plate": "22BH1234AA"}, headers=HEADER)
        assert r.status_code == 200, r.text
        assert vstore.REAP_LOOKUP_AUDIT_SQL in [q for _k, q, _a in store.calls]

    def test_audit_reap_sql_is_bound_and_bounded(self):
        sql = vstore.REAP_LOOKUP_AUDIT_SQL
        assert sql.startswith("DELETE FROM corridor.vehicle_lookup_audit ")
        assert "a.looked_up_at < NOW() - make_interval(days => $1::int)" in sql
        assert sql.endswith("RETURNING a.id")
        assert vstore.LOOKUP_AUDIT_RETENTION_DAYS == 90  # the earmark cap


class TestLookupsList:
    def test_no_officer_is_409_and_nothing_is_read(self):
        store = FakeStore()
        r = _client(store, base_url=LOCAL).get("/api/v1/vehicles/lookups")
        assert r.status_code == 409
        assert r.json() == {"detail": OFFICER_REQUIRED_DETAIL}
        assert store.calls == []

    @pytest.mark.parametrize("query", ["?limit=0", "?limit=201", "?limit=abc",
                                       "?officer=Duty%20Officer%20A",
                                       "?limit=5&officer=Duty%20Officer%20A"])
    def test_anonymous_is_409_whatever_the_limit_or_a_query_claim(self, query):
        store = FakeStore()
        r = _client(store, base_url=LOCAL).get("/api/v1/vehicles/lookups" + query)
        assert r.status_code == 409, r.text
        assert r.json() == {"detail": OFFICER_REQUIRED_DETAIL}
        assert store.calls == []

    def test_lists_masked_rows_only_and_writes_nothing(self):
        store = FakeStore(matches=[
            ("FROM corridor.vehicle_lookup_audit",
             [FakeRow(id=uuid.uuid4(), looked_up_at=T0, officer=OFFICER,
                      mark_masked="WB06EM•••1", found=True,
                      disclosure="active_earmark")]),
        ])
        r = _client(store, base_url=LOCAL).get(
            "/api/v1/vehicles/lookups?limit=25", headers=HEADER
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["count"] == 1
        (row,) = body["lookups"]
        assert set(row) == {"id", "looked_up_at", "officer", "mark_masked",
                            "found", "disclosure"}
        assert row["mark_masked"] == "WB06EM•••1" and row["officer"] == OFFICER
        # the hash is never selected back (hash + mask would undo the mask)
        (sql,) = [q for _k, q, _a in store.calls
                  if "FROM corridor.vehicle_lookup_audit" in q]
        assert "mark_sha256" not in sql
        assert _audit_args(store) == []  # reading the audit writes no row

    def test_limit_is_bounded(self):
        store = FakeStore()
        c = _client(store, base_url=LOCAL)
        assert c.get("/api/v1/vehicles/lookups?limit=0",
                     headers=HEADER).status_code == 422
        assert c.get("/api/v1/vehicles/lookups?limit=201",
                     headers=HEADER).status_code == 422
        assert c.get("/api/v1/vehicles/lookups?limit=abc",
                     headers=HEADER).status_code == 422
        assert store.calls == []
        # the default and the bounds themselves are served
        for query, want in (("", 50), ("?limit=1", 1), ("?limit=200", 200)):
            store = FakeStore()
            r = _client(store, base_url=LOCAL).get(
                "/api/v1/vehicles/lookups" + query, headers=HEADER)
            assert r.status_code == 200, r.text
            assert [a for _k, _q, a in store.calls] == [(want,)]


# ── DB-backed (int3c sandbox only, ALWAYS rolled back) ──────────────────────

_DSN = os.environ.get("SAJAG_TEST_PG_DSN", "")
_LIVE_PORT = ":56434/"  # the shared live store — never written by tests
_SANDBOX = "127.0.0.1:56561"  # int3c — the only sandbox this may touch

#: Frozen literals, ``$n`` placeholders — the store module's own
#: discipline: every value binds as a parameter, nothing is ever shaped
#: into SQL text.
_DB_HAS_024 = "SELECT to_regclass('corridor.vehicle_lookup_audit')"
_DB_HAS_HASH = (
    "SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE "
    "table_schema = 'corridor' AND table_name = 'vehicle_lookup_audit' "
    "AND column_name = 'mark_sha256')"
)
_DB_AUDIT_COLUMNS = (
    "SELECT column_name FROM information_schema.columns WHERE "
    "table_schema = 'corridor' AND table_name = 'vehicle_lookup_audit' "
    "ORDER BY ordinal_position"
)
_DB_SEED_AUDIT = (
    "INSERT INTO corridor.vehicle_lookup_audit (looked_up_at, officer, "
    "mark_masked, found, disclosure) VALUES (NOW() - make_interval(days => $1), "
    "'pytest', $2, FALSE, 'none') RETURNING id"
)
_DB_AUDIT_IDS = "SELECT id FROM corridor.vehicle_lookup_audit WHERE id = ANY($1::uuid[])"
_DB_SEED_VEHICLE = (
    "INSERT INTO corridor.vehicles (plate, vehicle_class, first_seen, last_seen) "
    "VALUES ($1, 'car', NOW(), NOW()) RETURNING vehicle_id"
)
_DB_SEED_EARMARK = (
    "INSERT INTO corridor.vehicle_earmarks (vehicle_id, state, reason, "
    "lawful_basis, retention_days, earmarked_by, earmarked_at, retention_until) "
    "VALUES ($1, 'watch', 'pytest full-mark lookup', 'stolen_vehicle_fir', 30, "
    "'pytest', NOW(), NOW() + make_interval(days => 30)) RETURNING earmark_id"
)
_DB_AUDIT_ROWS = (
    "SELECT officer, mark_masked, found, disclosure "
    "FROM corridor.vehicle_lookup_audit ORDER BY looked_up_at"
)

db = pytest.mark.skipif(
    not _DSN or _LIVE_PORT in _DSN or _SANDBOX not in _DSN,
    reason="set SAJAG_TEST_PG_DSN to the int3c sandbox (127.0.0.1:56561) — "
           "never the live :56434 store",
)


class _Ctx:
    """``async with`` yielding a fixed value (an acquired conn, a tx)."""

    def __init__(self, value=None) -> None:
        self.value = value

    async def __aenter__(self):
        return self.value

    async def __aexit__(self, *exc):
        return False


class _OneConnPool:
    """The router's pool, bound to one connection inside an OUTER
    transaction (every inner transaction becomes a savepoint)."""

    def __init__(self, conn) -> None:
        self._conn = conn

    def acquire(self):
        return _Ctx(self._conn)


async def _lookups_on_store() -> dict:
    """earmarked + no-basis + unknown lookups and the audit list, on the
    real schema, inside a transaction that is ALWAYS rolled back."""
    import asyncpg

    from traffic_oracle.vehicles import router as vehicles_router

    conn = await asyncpg.connect(_DSN)
    tx = conn.transaction()
    await tx.start()
    try:
        if await conn.fetchval(_DB_HAS_024) is None:
            return {"skipped_no_024": True}
        if await conn.fetchval(_DB_HAS_HASH):
            return {"skipped_no_024": False, "skipped_no_025": True}
        earmarked_mark, plain_mark = "WB06DB0001", "WB06DC0002"
        for mark in (earmarked_mark, plain_mark):
            vid = await conn.fetchval(_DB_SEED_VEHICLE, mark)
            if mark == earmarked_mark:
                await conn.fetchval(_DB_SEED_EARMARK, vid)
        app = FastAPI()
        app.state.pool = _OneConnPool(conn)
        app.include_router(vehicles_router)
        async with AsyncClient(transport=ASGITransport(app=app),
                               base_url=LOCAL) as c:
            anon = await c.get("/api/v1/vehicles/lookup",
                               params={"plate": earmarked_mark})
            earmarked = await c.get("/api/v1/vehicles/lookup",
                                    params={"plate": "wb 06 db-0001"},
                                    headers=HEADER)
            no_basis = await c.get("/api/v1/vehicles/lookup",
                                   params={"plate": plain_mark},
                                   headers=HEADER)
            unknown = await c.get("/api/v1/vehicles/lookup",
                                  params={"plate": "22BH1234AA"},
                                  headers=HEADER)
            listed = await c.get("/api/v1/vehicles/lookups?limit=10",
                                 headers=HEADER)
        rows = await conn.fetch(_DB_AUDIT_ROWS)
        return {
            "skipped_no_024": False, "skipped_no_025": False,
            "columns": [r["column_name"] for r in await conn.fetch(_DB_AUDIT_COLUMNS)],
            "anon": anon, "earmarked": earmarked, "no_basis": no_basis,
            "unknown": unknown, "listed": listed,
            "rows": [dict(r) for r in rows],
        }
    finally:
        await tx.rollback()  # ALWAYS: nothing persists
        await conn.close()


@db
def test_db_lookup_writes_audited_rows_on_the_real_schema():
    out = asyncio.run(_lookups_on_store())
    if out["skipped_no_024"]:
        pytest.skip("migration 024 not applied to this sandbox store yet")
    if out["skipped_no_025"]:
        pytest.skip("migration 025 (drop mark_sha256) not applied to this sandbox store yet")
    # 025: the audit holds nothing about the mark but its mask
    assert out["columns"] == ["id", "looked_up_at", "officer", "mark_masked",
                              "found", "disclosure"]
    assert out["anon"].status_code == 409  # and it wrote nothing
    assert out["earmarked"].status_code == 200, out["earmarked"].text
    e = out["earmarked"].json()
    assert e["found"] is True and e["mark"] == "WB06DB0001"
    assert e["disclosure"] == "active_earmark"
    assert e["earmark"]["lawful_basis"] == "stolen_vehicle_fir"
    assert e["reads"] == []  # earmarked, never sighted: no trail to show
    assert out["no_basis"].status_code == 200
    n = out["no_basis"].json()
    assert n["found"] is True and n["disclosure"] == "none"
    assert n["note"] == NO_BASIS_NOTE and n["reads"] == []
    assert out["unknown"].status_code == 200
    u = out["unknown"].json()
    assert u["found"] is False and u["reads"] == [] and u["note"] is None
    rows = out["rows"]
    assert len(rows) == 3  # the anonymous 409 audited nothing
    assert all(r["officer"] == OFFICER for r in rows)
    # the stored mark is only ever the mask + the hash of the canonical mark
    assert all(r["mark_masked"] == mask_plate(m)
               for r, m in zip(sorted(rows, key=lambda r: r["mark_masked"]),
                               sorted([mask_plate("WB06DB0001"),
                                       mask_plate("WB06DC0002"),
                                       mask_plate("22BH1234AA")])))
    assert any(r["mark_masked"] == mask_plate("22BH1234AA")
               and r["found"] is False for r in rows)
    assert any(r["disclosure"] == "active_earmark" for r in rows)
    assert out["listed"].status_code == 200
    body = out["listed"].json()
    assert body["count"] == 3
    assert all("mark_sha256" not in row for row in body["lookups"])
    assert all("WB06DB0001" not in row.values() for row in body["lookups"])


async def _audit_reap_on_store() -> dict:
    """Two audit rows either side of the 90-day cap, the real reap, the
    survivors — inside a transaction that is ALWAYS rolled back."""
    import asyncpg

    conn = await asyncpg.connect(_DSN)
    tx = conn.transaction()
    await tx.start()
    try:
        if await conn.fetchval(_DB_HAS_024) is None:
            return {"skipped": "migration 024 not applied to this sandbox store yet"}
        if await conn.fetchval(_DB_HAS_HASH):
            return {"skipped": "migration 025 not applied to this sandbox store yet"}
        cap = vstore.LOOKUP_AUDIT_RETENTION_DAYS
        old = await conn.fetchval(_DB_SEED_AUDIT, cap + 1, mask_plate("WB06DD0003"))
        kept = await conn.fetchval(_DB_SEED_AUDIT, cap - 1, mask_plate("WB06DD0004"))
        now = datetime.now(timezone.utc)
        removed = await vstore.reap_expired_sightings(conn, now - timedelta(days=30))
        left = {r["id"] for r in await conn.fetch(_DB_AUDIT_IDS, [old, kept])}
        return {"skipped": None, "old": old, "kept": kept, "left": left,
                "removed": removed}
    finally:
        await tx.rollback()  # ALWAYS: nothing persists
        await conn.close()


@db
def test_db_lookup_audit_rows_past_the_cap_are_reaped():
    out = asyncio.run(_audit_reap_on_store())
    if out["skipped"]:
        pytest.skip(out["skipped"])
    assert out["left"] == {out["kept"]}
    assert out["removed"] >= 1
