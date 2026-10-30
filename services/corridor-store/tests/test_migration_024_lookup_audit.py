"""024_vehicle_lookup_audit.sql (FIX-C-PLATESEARCH): grammar and contract tests.

The officer-only full-mark lookup audit trail: officer, time, the MASKED mark,
a sha256 of the canonical mark, found, and the disclosure class. Never the raw
mark in clear text; no FK to corridor.vehicles (the audit survives vehicle
reaping and records unknown-mark lookups, which have no vehicle row).

024 is ledgered (migrate.py checksums every applied file) and never changes:
these tests pin it AS SHIPPED, hash column included.  That hash was
reversible (an unsalted sha256 of a mark whose mask hides three digits —
audit A), so 025_vehicle_lookup_audit_nohash.sql drops it; the effective
schema after 025 is pinned by test_migration_025_nohash.py.

Static checks (always run, no database) — the constraints every consumer
imposes: the naive ';'-splitters (embedding-service's lexical apply, the
corridor-store grammar tests) and the ledgered migrate.py:
    * the 013 header grammar (file name line, what/why, the grammar note);
    * no ';' or '--' inside string literals, no dollar-quoted bodies, no
      block comments, every statement a splittable CREATE / ALTER / COMMENT;
    * schema only (no INSERT / UPDATE / DELETE) and idempotent (IF NOT
      EXISTS everywhere);
    * the contracts: exactly TWO statements, the columns exactly the pinned
      seven (so no column can hold a clear mark), no REFERENCES at all, the
      disclosure CHECK equals the DisclosureBasis vocabulary plus 'none'
      (inline-CHECK idiom of test_migration_023_context_role.py — 024 adds no
      constraint, so _check_values' ADD-CONSTRAINT regex cannot match), and
      the sha256 length CHECK is present.

The DB-tier variant of test_migrations_016_019.py (fresh throwaway database,
001..023 as they ship, then 024 through the naive splitter, then 024 again
with an identical catalog) is NOT in this file: the workspace's SQL-injection
write gate intercepts the file-apply idiom it is built on (executing the
migration files' own statements — PostgreSQL DDL takes no bind parameters and
the statements are repo-controlled, not external input). The static half is
the merge gate per the WP contract; see the implementer's report.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]  # services/corridor-store
MIGRATIONS = ROOT / "migrations"
WAVE = {"024": MIGRATIONS / "024_vehicle_lookup_audit.sql"}


def _no_comments(sql_text: str) -> str:
    return "\n".join(line.split("--", 1)[0] for line in sql_text.splitlines())


def _statements(sql_text: str) -> list[str]:
    """Split like the naive consumers: strip -- comments, split on ';'."""
    return [s.strip() for s in _no_comments(sql_text).split(";") if s.strip()]


def _flat(stmt: str) -> str:
    return " ".join(stmt.split())


# ── static: grammar ────────────────────────────────────────────────────────


@pytest.mark.parametrize("num", sorted(WAVE))
class TestGrammar:
    def test_013_header_grammar(self, num):
        path = WAVE[num]
        lines = path.read_text().splitlines()
        assert lines[0] == f"-- {path.name}", "first line names the file"
        header = "\n".join(line for line in lines if line.startswith("--"))
        assert "SCHEMA ONLY, additive, idempotent" in header
        assert "Grammar constraint (007 header): consumed by naive ';'-splitters" in header
        assert "Ethics rails (C6)" in header

    def test_splitter_safe_literals(self, num):
        text = WAVE[num].read_text()
        for literal in re.findall(r"'([^']*)'", _no_comments(text)):
            assert ";" not in literal and "--" not in literal, literal
        assert "$$" not in text and not re.search(r"\$[A-Za-z_]+\$", text)
        assert "/*" not in text

    def test_schema_only_idempotent_statements(self, num):
        stmts = _statements(WAVE[num].read_text())
        assert stmts
        dropped: set[str] = set()
        for stmt in stmts:
            flat = _flat(stmt)
            assert flat.split()[0] in {"CREATE", "ALTER", "COMMENT"}, flat[:60]
            assert not re.search(r"\bINSERT\s+INTO\b|\bDELETE\s+FROM\b|\bUPDATE\s+\S+\s+SET\b",
                                 flat, re.I), flat[:60]
            if flat.startswith("CREATE"):
                assert flat.startswith(("CREATE TABLE IF NOT EXISTS",
                                        "CREATE INDEX IF NOT EXISTS")), flat[:60]
            if "ADD COLUMN" in flat:
                assert "ADD COLUMN IF NOT EXISTS" in flat, flat[:60]
            m = re.search(r"DROP CONSTRAINT IF EXISTS (\w+)", flat)
            if m:
                dropped.add(m.group(1))
            m = re.search(r"ADD CONSTRAINT (\w+)", flat)
            if m:
                assert m.group(1) in dropped, f"ADD {m.group(1)} without a guarded DROP"


# ── static: contracts ──────────────────────────────────────────────────────


def test_exactly_two_statements_table_then_index() -> None:
    stmts = _statements(WAVE["024"].read_text())
    assert len(stmts) == 2
    assert _flat(stmts[0]).startswith(
        "CREATE TABLE IF NOT EXISTS corridor.vehicle_lookup_audit"
    ), stmts[0][:60]
    flat_index = _flat(stmts[1])
    assert flat_index.startswith(
        "CREATE INDEX IF NOT EXISTS idx_vehicle_lookup_audit "
        "ON corridor.vehicle_lookup_audit"
    ), stmts[1][:60]
    assert "(looked_up_at DESC)" in flat_index


def test_columns_are_exactly_the_pinned_seven() -> None:
    """No column that could ever carry a raw registration mark in clear
    (as 024 shipped them — 025 drops mark_sha256, leaving six)."""
    body = re.search(
        r"CREATE TABLE IF NOT EXISTS corridor\.vehicle_lookup_audit \((.*?)\n\);",
        _no_comments(WAVE["024"].read_text()), re.S,
    ).group(1)
    columns = [line.split()[0] for line in body.splitlines() if line.strip()]
    assert columns == ["id", "looked_up_at", "officer", "mark_masked",
                       "mark_sha256", "found", "disclosure"]


def test_no_foreign_key_survives_reaping() -> None:
    flat = _flat(_no_comments(WAVE["024"].read_text()))
    assert "REFERENCES" not in flat, "the audit must survive vehicle reaping"


def test_check_lists_exactly_the_disclosure_classes() -> None:
    check = re.search(r"CHECK \(disclosure IN \(([^)]*)\)\)", WAVE["024"].read_text())
    assert check, "no disclosure CHECK in 024"
    values = re.findall(r"'([a-z_]+)'", check.group(1))
    assert sorted(values) == ["active_earmark", "evidence_only", "none"]


def test_hash_is_length_checked() -> None:
    assert "char_length(mark_sha256) = 64" in WAVE["024"].read_text()
