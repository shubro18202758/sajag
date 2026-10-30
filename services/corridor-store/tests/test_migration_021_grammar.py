"""Migration grammar + content tests for 021_osint_events.sql and 022_decision_support.sql (OS-1).

Static checks (the same constraints the naive `;`-splitter consumers and the ledgered migrate.py impose,
modelled on test_migration_010_grammar.py):
    * no ';' or '--' inside a string literal, no dollar-quoted body, no block comment;
    * idempotent shape: IF NOT EXISTS on every CREATE and ADD COLUMN, a guarded DROP CONSTRAINT IF EXISTS
      before every ADD CONSTRAINT, nothing destructive;
    * the C3 lockstep: the sixteen kinds on BOTH event-kind CHECKs = traffic_oracle.events.EVENT_KINDS, the
      verification states and source kinds = the oracle's tuples and osint_common's;
    * ethics: no person column anywhere in the osint and decision DDL (the spec §4 denylist), sajag_event_kind
      can never be crime_incident, and a value scan of every osint_common.testing fixture.

``test_applies_on_sandbox`` (skipped unless OSINT_TEST_DSN is set) applies every 021 then 022 statement on the
int3c (or int3cl) sandbox inside ONE transaction, introspects the result and ROLLS BACK: the sandbox is left
untouched. Its DSN guard accepts only 127.0.0.1:56561 or 127.0.0.1:56562 and refuses the live store (:56434).
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

import pytest

REPO = Path(__file__).resolve().parents[3]  # services/corridor-store/tests -> VVIP
MIGRATIONS = REPO / "services" / "corridor-store" / "migrations"
M021 = MIGRATIONS / "021_osint_events.sql"
M022 = MIGRATIONS / "022_decision_support.sql"
FILES = (M021, M022)

for _src in (
    REPO / "services" / "traffic-oracle" / "src",
    REPO / "services" / "osint-common" / "src",
    REPO / "services" / "event-emulator" / "src",
):
    if str(_src) not in sys.path:
        sys.path.insert(0, str(_src))

NEW_KINDS = ("reported_crime", "public_disorder", "road_accident", "hazard", "flooding", "infra_failure")
SANDBOX_ENDPOINTS = {("127.0.0.1", 56561), ("127.0.0.1", 56562)}
LIVE_PORT = 56434


def _no_comments(sql_text: str) -> str:
    return re.sub(r"--[^\n]*", "", sql_text)


def _statements(sql_text: str) -> list[str]:
    """Split like the naive consumers: strip -- comments, split on ';'."""
    return [s.strip() for s in _no_comments(sql_text).split(";") if s.strip()]


def _flat(stmt: str) -> str:
    return " ".join(stmt.split())


def _literals(sql_text: str) -> list[str]:
    return re.findall(r"'([^']*)'", _no_comments(sql_text))


def _balanced(text: str, open_at: int) -> str:
    """The text inside the parenthesis that opens at ``open_at``."""
    depth, i = 0, open_at
    while True:
        depth += {"(": 1, ")": -1}.get(text[i], 0)
        if depth == 0:
            return text[open_at + 1 : i]
        i += 1


def _check_list(sql_text: str, constraint: str) -> list[str]:
    """The quoted values of ``ADD CONSTRAINT <constraint> CHECK (...)``."""
    text = _no_comments(sql_text)
    m = re.search(r"ADD CONSTRAINT " + constraint + r" CHECK \(", text)
    assert m, f"re-ADD of {constraint} missing"
    return re.findall(r"'([A-Za-z_\-]+)'", _balanced(text, m.end() - 1))


def _column_def(body: str, column: str) -> str:
    """The full definition of ``column`` in a CREATE TABLE body (its CHECK included)."""
    return next(i for i in _top_level_items(body) if i.split()[0] == column)


def _create_table_bodies(sql_text: str) -> dict[str, str]:
    """{qualified table: body between the outer parentheses} for every CREATE TABLE."""
    text = _no_comments(sql_text)
    out: dict[str, str] = {}
    for m in re.finditer(r"CREATE TABLE IF NOT EXISTS (\S+) \(", text):
        depth, i = 1, m.end()
        while depth:
            depth += {"(": 1, ")": -1}.get(text[i], 0)
            i += 1
        out[m.group(1)] = text[m.end() : i - 1]
    return out


def _top_level_items(body: str) -> list[str]:
    items, depth, cur = [], 0, []
    for ch in body:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            items.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
    if "".join(cur).strip():
        items.append("".join(cur).strip())
    return items


def _columns(sql_text: str) -> dict[str, list[str]]:
    """{table: [column names]} from CREATE TABLE bodies and ADD COLUMN statements."""
    out: dict[str, list[str]] = {}
    for table, body in _create_table_bodies(sql_text).items():
        cols = []
        for item in _top_level_items(body):
            first = item.split()[0]
            if first.upper() in {"PRIMARY", "FOREIGN", "UNIQUE", "CHECK", "CONSTRAINT"}:
                continue
            cols.append(first)
        out[table] = cols
    for m in re.finditer(r"ALTER TABLE (\S+) ADD COLUMN IF NOT EXISTS (\w+)", _flat(_no_comments(sql_text))):
        out.setdefault(m.group(1), []).append(m.group(2))
    return out


def _event_kinds():
    from traffic_oracle.events import EVENT_KINDS

    return EVENT_KINDS


# ── grammar ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
class TestGrammar:
    def test_no_semicolon_or_double_hyphen_inside_string_literals(self, path):
        text = path.read_text()
        for literal in _literals(text):
            assert ";" not in literal, f"';' inside literal: {literal!r}"
            assert "--" not in literal, f"'--' inside literal: {literal!r}"
        # the embedding-service splitter strips comments line by line: same answer
        per_line = "\n".join(line.split("--", 1)[0] for line in text.splitlines())
        assert all(";" not in lit for lit in re.findall(r"'([^']*)'", per_line))

    def test_no_dollar_quoted_bodies_or_block_comments(self, path):
        text = path.read_text()
        assert "$$" not in text
        assert not re.search(r"\$[A-Za-z_]*\$", text)
        assert "/*" not in text and "*/" not in text

    def test_every_statement_is_splittable_sql(self, path):
        stmts = _statements(path.read_text())
        assert len(stmts) == {"021_osint_events.sql": 37, "022_decision_support.sql": 11}[path.name]
        for s in stmts:
            assert s.split()[0].upper() in {"CREATE", "ALTER"}, f"unexpected statement start: {s[:60]!r}"

    def test_idempotent_and_additive_shape(self, path):
        stmts = [_flat(s) for s in _statements(path.read_text())]
        dropped: set[tuple[str, str]] = set()
        for s in stmts:
            upper = s.upper()
            if upper.startswith("CREATE"):
                assert re.match(r"CREATE (SCHEMA|TABLE|INDEX|UNIQUE INDEX) IF NOT EXISTS ", s), s[:80]
            # nothing destructive (ON DELETE CASCADE on a new FK is a constraint, not a statement)
            assert not re.search(r"\b(DROP (TABLE|COLUMN|INDEX|SCHEMA|TYPE)|TRUNCATE|DELETE FROM)\b", upper), s
            m = re.match(r"ALTER TABLE (\S+) DROP CONSTRAINT IF EXISTS (\w+)$", s)
            if m:
                dropped.add((m.group(1), m.group(2)))
                continue
            m = re.match(r"ALTER TABLE (\S+) ADD CONSTRAINT (\w+) CHECK ", s)
            if m:
                assert (m.group(1), m.group(2)) in dropped, f"unguarded ADD CONSTRAINT {m.group(2)}"
                continue
            if upper.startswith("ALTER"):
                assert re.match(r"ALTER TABLE \S+ ADD COLUMN IF NOT EXISTS \w+ ", s), s[:80]


def test_older_migrations_untouched():
    """001-020 are ledgered (checksum = hard error): no older file carries a 021/022 addition."""
    for path in sorted(MIGRATIONS.glob("0[01]*.sql")) + [MIGRATIONS / "020_road_network_osm.sql"]:
        text = path.read_text()
        for marker in ("reported_crime", "infra_failure", "SCHEMA IF NOT EXISTS osint", "SCHEMA IF NOT EXISTS decision"):
            assert marker not in text, f"{path.name} carries {marker!r}"


# ── the C3 lockstep ──────────────────────────────────────────────────────────


class TestLockstep:
    def test_both_event_kind_checks_carry_the_sixteen_kinds(self):
        text = M021.read_text()
        kinds = _event_kinds()
        assert len(kinds) == 16 and set(NEW_KINDS) <= set(kinds)
        for con in ("corridor_events_event_kind_check", "event_profiles_event_kind_check"):
            values = _check_list(text, con)
            assert sorted(values) == sorted(kinds), con
            assert len(values) == 16

    def test_verification_states_agree(self):
        from osint_common.kinds import VERIFICATION_STATES as COMMON
        from traffic_oracle.events import VERIFICATION_STATES

        text = M021.read_text()
        corridor = _check_list(text, "corridor_events_verification_state_check")
        body = _create_table_bodies(text)["osint.resolved_events"]
        m = re.search(r"verification_state TEXT NOT NULL CHECK \(verification_state IN \((.*?)\)\)", body, re.S)
        assert m
        resolved = re.findall(r"'([A-Z\-]+)'", m.group(1))
        assert set(corridor) == set(resolved) == set(VERIFICATION_STATES) == set(COMMON)
        assert "SIMULATED" in resolved and len(resolved) == 6

    def test_source_kinds_agree(self):
        from osint_common.kinds import SOURCE_KINDS as COMMON
        from traffic_oracle.events import SOURCE_KINDS

        assert set(_check_list(M021.read_text(), "corridor_events_source_kind_check")) == set(SOURCE_KINDS)
        assert tuple(SOURCE_KINDS) == tuple(COMMON) == ("operator", "brain", "emulator", "osint")

    def test_incident_relaxations(self):
        from osint_common.kinds import INCIDENT_KINDS

        text = M021.read_text()
        assert _check_list(text, "incidents_source_check") == ["live", "scenario_run", "import", "osint"]
        assert _check_list(text, "incidents_incident_kind_check") == list(INCIDENT_KINDS)

    def test_022_enumerations_mirror_osint_common(self):
        from typing import get_args

        from osint_common import types

        text = M022.read_text()
        bodies = _create_table_bodies(text)

        def values(table: str, column: str) -> set[str]:
            return set(re.findall(r"'(\w+)'", _column_def(bodies[table], column)))

        dss_states = set(get_args(types.DssState))
        # the state column also carries its DEFAULT 'proposed', a member of the set
        assert values("decision.decision_support", "state") == dss_states
        assert values("decision.coa", "kind") == set(get_args(types.CoaKind))
        assert values("decision.dss_decision_log", "decision") == set(get_args(types.DecisionVerb))
        assert values("decision.decision_support", "requested_by") == set(get_args(types.RequestedBy))
        assert values("decision.coa_sim_runs", "method") == {"twin", "cascade", "surrogate"}
        assert _check_list(text, "memory_docs_kind_check") == [
            "incident", "aar", "decision", "scenario_run", "pattern", "osint",
        ]

    def test_one_proposed_dss_per_event(self):
        flat = _flat(_no_comments(M022.read_text()))
        assert (
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_decision_support_one_proposed ON decision.decision_support "
            "(event_urn) WHERE state = 'proposed'"
        ) in flat
        assert "CREATE INDEX IF NOT EXISTS idx_decision_support_event ON decision.decision_support " \
               "(event_urn, generated_at DESC)" in flat


# ── ethics ───────────────────────────────────────────────────────────────────


class TestEthicsSchema:
    def test_no_person_column_anywhere_in_the_osint_and_decision_ddl(self):
        from osint_common.ethics import EXEMPT_KEYS, FORBIDDEN_KEY_RE, is_forbidden_key

        assert FORBIDDEN_KEY_RE.startswith("author|person|handle")
        seen = 0
        substring_hits: set[str] = set()
        for path in FILES:
            for table, cols in _columns(path.read_text()).items():
                for col in cols:
                    seen += 1
                    assert not is_forbidden_key(col), f"{table}.{col} names a person"
                    # and the spec §4 regex as a word, the 010 test's form
                    assert not re.search(r"\b(?:" + FORBIDDEN_KEY_RE + r")\b", col), f"{table}.{col}"
                    # fail closed: the regex anywhere in a column name only for an exempt contract key
                    if re.search(FORBIDDEN_KEY_RE, col, re.IGNORECASE):
                        substring_hits.add(f"{table}.{col}")
                        assert col in EXEMPT_KEYS, f"{table}.{col}"
        assert seen >= 100
        assert substring_hits == {"osint.gazetteer.surface_forms"}

    def test_every_new_table_is_in_the_osint_or_decision_schema(self):
        tables = set(_create_table_bodies(M021.read_text())) | set(_create_table_bodies(M022.read_text()))
        assert tables == {
            "osint.raw_signals", "osint.gazetteer", "osint.resolved_events", "osint.geocodes", "osint.event_sources",
            "decision.decision_support", "decision.coa", "decision.coa_sim_runs", "decision.dss_decision_log",
        }

    def test_sajag_event_kind_can_never_be_crime_incident(self):
        values = _check_list(M021.read_text(), "resolved_events_sajag_event_kind_check")
        assert "crime_incident" not in values and "vehicle_pursuit" not in values
        assert sorted(values) == sorted(k for k in _event_kinds() if k not in ("crime_incident", "vehicle_pursuit"))
        assert "sajag_event_kind IS NULL OR sajag_event_kind IN" in _flat(M021.read_text())

    def test_value_scan_of_every_osint_common_fixture(self):
        from osint_common import ethics, testing

        def strings(v):
            if isinstance(v, str):
                yield v
            elif isinstance(v, dict):
                for x in v.values():
                    yield from strings(x)
            elif isinstance(v, list):
                for x in v:
                    yield from strings(x)

        scanned = 0
        for name in testing.__all__:
            fn = getattr(testing, name)
            if not callable(fn):
                continue
            value = fn()
            for item in value if isinstance(value, list) else [value]:
                dumped = item.model_dump(mode="json")
                ethics.assert_no_person_keys(dumped)
                for s in strings(dumped):
                    assert ethics.find_pii(s) == [], (name, s[:60])
                    scanned += 1
        assert scanned > 100


# ── the sandbox apply (BEGIN ... ROLLBACK) ───────────────────────────────────


def _sandbox_dsn(dsn: str) -> str:
    """Only the int3c / int3cl sandboxes, by address; the live store refused by name."""
    parts = urlsplit(dsn)
    if parts.port == LIVE_PORT or f":{LIVE_PORT}" in dsn:
        raise ValueError(f"refusing the live store (:{LIVE_PORT})")
    if (parts.hostname, parts.port) not in SANDBOX_ENDPOINTS:
        raise ValueError("OSINT_TEST_DSN must be a sandbox: 127.0.0.1:56561 (int3c) or 127.0.0.1:56562 (int3cl)")
    return dsn


def test_dsn_guard():
    ok = "postgresql://corridor_admin:pw@127.0.0.1:56561/corridor_db"
    assert _sandbox_dsn(ok) == ok
    _sandbox_dsn("postgresql://corridor_admin:pw@127.0.0.1:56562/corridor_db")
    for bad in (
        "postgresql://corridor_admin:pw@127.0.0.1:56434/corridor_db",
        "postgresql://corridor_admin:pw@localhost:56561/corridor_db",
        "postgresql://corridor_admin:pw@127.0.0.1:5432/corridor_db",
        "postgresql://corridor_admin:pw@10.0.0.5:56561/corridor_db",
    ):
        with pytest.raises(ValueError):
            _sandbox_dsn(bad)


_DSN = os.environ.get("OSINT_TEST_DSN")


@pytest.mark.skipif(not _DSN, reason="OSINT_TEST_DSN (int3c 127.0.0.1:56561 or int3cl :56562) not set")
def test_applies_on_sandbox():
    psycopg = pytest.importorskip("psycopg")
    dsn = _sandbox_dsn(_DSN or "")
    statements = _statements(M021.read_text()) + _statements(M022.read_text())

    def one(cur, sql, *args):
        cur.execute(sql, args or None)
        return cur.fetchone()

    def schema_state(cur) -> tuple:
        """What this test must leave exactly as it found it (before the wave-A migrate, or after it)."""
        return one(
            cur,
            "SELECT to_regnamespace('osint') IS NOT NULL, to_regnamespace('decision') IS NOT NULL, "
            "EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'events' "
            "AND table_name = 'corridor_events' AND column_name = 'source_kind'), "
            "(SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid = 'events.corridor_events'::regclass "
            "AND conname = 'corridor_events_event_kind_check'), "
            "(SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid = 'traffic.memory_docs'::regclass "
            "AND conname = 'memory_docs_kind_check'), "
            "(SELECT count(*) FROM events.corridor_events)",
        )

    # autocommit: conn.transaction() below is a real BEGIN ... ROLLBACK (nested ones are SAVEPOINTs)
    with psycopg.connect(dsn, connect_timeout=10, autocommit=True) as conn:
        cur = conn.cursor()
        before = schema_state(cur)
        with conn.transaction(force_rollback=True):
            cur.execute("SET LOCAL lock_timeout = '5s'")
            cur.execute("SET LOCAL statement_timeout = '60s'")
            for stmt in statements:
                cur.execute(stmt)

            # tables
            for table in (
                "osint.raw_signals", "osint.gazetteer", "osint.resolved_events", "osint.geocodes",
                "osint.event_sources", "decision.decision_support", "decision.coa", "decision.coa_sim_runs",
                "decision.dss_decision_log",
            ):
                assert one(cur, "SELECT to_regclass(%s) IS NOT NULL", table)[0], table

            # columns
            def columns(schema, table):
                cur.execute(
                    "SELECT column_name FROM information_schema.columns WHERE table_schema = %s AND table_name = %s",
                    (schema, table),
                )
                return {r[0] for r in cur.fetchall()}

            assert {"geotag", "source_kind", "credibility", "verification_state", "provenance"} <= columns(
                "events", "corridor_events"
            )
            assert {"publisher", "pii_redactions", "valid_until", "raw_geo_hint", "run_id", "body"} <= columns(
                "osint", "raw_signals"
            )
            assert {"snapped_to", "bucket", "area_level", "area_scope"} <= columns("osint", "geocodes")
            assert {
                "fused_event_id", "label", "summary", "sajag_incident_kind", "toponym", "area_level",
                "cross_type_corroborated", "is_event", "held_reason", "attach_novel", "corroborates_live_urn",
                "second_order", "labels", "superseded_by", "updated_at",
            } <= columns("osint", "resolved_events")
            for schema in ("osint", "decision"):
                cur.execute("SELECT table_name, column_name FROM information_schema.columns WHERE table_schema = %s",
                            (schema,))
                from osint_common.ethics import is_forbidden_key

                for table, col in cur.fetchall():
                    assert not is_forbidden_key(col), f"{schema}.{table}.{col}"

            # constraints: replaced exactly once, with the new lists
            def condef(table, name):
                row = one(
                    cur,
                    "SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid = to_regclass(%s) "
                    "AND conname = %s",
                    table,
                    name,
                )
                assert row, f"{table}.{name} missing"
                return row[0]

            for table, name in (("events.corridor_events", "corridor_events_event_kind_check"),
                                ("events.event_profiles", "event_profiles_event_kind_check")):
                d = condef(table, name)
                assert all(k in d for k in NEW_KINDS) and "crime_incident" in d
                n = one(cur, "SELECT count(*) FROM pg_constraint WHERE conrelid = to_regclass(%s) AND contype = 'c' "
                        "AND pg_get_constraintdef(oid) LIKE %s", table, "%event_kind%")[0]
                assert n == 1, f"{table}: {n} event_kind CHECKs (the old one was not dropped)"
            assert "'osint'" in condef("traffic.incidents", "incidents_source_check")
            assert "'robbery'" in condef("traffic.incidents", "incidents_incident_kind_check")
            assert "'osint'" in condef("traffic.memory_docs", "memory_docs_kind_check")
            assert "crime_incident" not in condef("osint.resolved_events", "resolved_events_sajag_event_kind_check")
            assert "'osint'" in condef("events.corridor_events", "corridor_events_source_kind_check")
            assert "SIMULATED" in condef("events.corridor_events", "corridor_events_verification_state_check")

            # the partial unique index: one proposed DSS per event
            idx = one(cur, "SELECT indexdef FROM pg_indexes WHERE schemaname = 'decision' "
                      "AND indexname = 'uq_decision_support_one_proposed'")
            assert idx and "UNIQUE" in idx[0] and "WHERE (state = 'proposed'::text)" in idx[0], idx

            # behaviour, inside savepoints (everything is rolled back with the outer transaction)
            urn = "osint_event:00000000-0000-4000-8000-0000000000aa"
            dss_insert = (
                "INSERT INTO decision.decision_support (event_urn, seed, input_fingerprint, situation, criteria, "
                "ahp, recommendation, provenance) VALUES (%s, 1, 'fp', '{}', '[]', '{}', '{}', '{}')"
            )
            cur.execute(dss_insert, (urn,))
            with pytest.raises(psycopg.errors.UniqueViolation), conn.transaction():
                cur.execute(dss_insert, (urn,))
            with pytest.raises(psycopg.errors.CheckViolation), conn.transaction():
                cur.execute(
                    "INSERT INTO osint.resolved_events (fused_event_id, event_class, sajag_event_kind, credibility, "
                    "verification_state) VALUES ('test-os1-a', 'reported_crime', 'crime_incident', 0.6, "
                    "'NEWS-REPORTED')"
                )
            cur.execute(
                "INSERT INTO osint.resolved_events (fused_event_id, event_class, sajag_event_kind, credibility, "
                "verification_state) VALUES ('test-os1-b', 'reported_crime', 'reported_crime', 0.6, 'SIMULATED')"
            )
            eid = one(
                cur,
                "INSERT INTO events.corridor_events (event_kind, title, source_kind, credibility, verification_state, "
                "provenance, geotag) VALUES ('road_accident', 'OS-1 sandbox test (rolled back)', 'osint', 0.65, "
                "'NEWS-REPORTED', '{}'::jsonb, ST_SetSRID(ST_MakePoint(88.363, 22.539), 4326)) RETURNING event_id",
            )[0]
            assert one(cur, "SELECT ST_X(geotag), ST_Y(geotag) FROM events.corridor_events WHERE event_id = %s",
                       eid) == (88.363, 22.539)
            for bad in (("source_kind", "'bogus'"), ("credibility", "1.5"), ("verification_state", "'LIVE'")):
                with pytest.raises(psycopg.errors.CheckViolation), conn.transaction():
                    cur.execute(f"UPDATE events.corridor_events SET {bad[0]} = {bad[1]} WHERE event_id = %s", (eid,))
            with pytest.raises(psycopg.errors.CheckViolation), conn.transaction():
                cur.execute("INSERT INTO traffic.memory_docs (kind, ref_id, title, body) VALUES ('person', 'x', 't', "
                            "'b')")

    # ROLLBACK: the sandbox is exactly as it was (a fresh connection sees the state from before the test)
    with psycopg.connect(dsn, connect_timeout=10, autocommit=True) as conn:
        assert schema_state(conn.cursor()) == before
