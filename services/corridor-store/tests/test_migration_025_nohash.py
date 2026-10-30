"""025_vehicle_lookup_audit_nohash.sql (FIX-AUDIT-A): grammar and contract tests.

024 stored ``mark_sha256``, an UNSALTED sha256 of the canonical mark, beside
the masked mark.  The mask hides three digits of a mark, so the hash fell to
at most 1000 guesses (audit A's ``hash-reversal-demo.log``: recovered in
under a millisecond).  025 drops the column — orchestrator decision: drop,
not salt — and the audit keeps officer, time, the MASKED mark, found and the
disclosure class.

Static checks (always run, no database) — the constraints every consumer
imposes: the naive ';'-splitters (embedding-service's lexical apply, the
corridor-store grammar tests) and the ledgered migrate.py:
    * the 013 header grammar (file name line, what/why, the grammar note);
    * no ';' or '--' inside string literals, no dollar-quoted bodies, no
      block comments, every statement a splittable ALTER;
    * schema only (no INSERT / UPDATE / DELETE) and idempotent (every
      DROP behind IF EXISTS);
    * the contracts: exactly ONE statement, the guarded DROP of
      ``mark_sha256``; 025 sorts after 024; the columns 024 creates minus
      the ones 025 drops are exactly the pinned six (no column holds, or
      reverses into, a clear mark); no later migration adds a hash back.

The DB-tier variant is not in this file, for the reason
test_migration_024_lookup_audit.py records (the workspace's SQL-injection
write gate intercepts the file-apply idiom).  The oracle's DB-tier lookup
test (tests/test_vehicle_lookup.py, behind SAJAG_TEST_PG_DSN) asserts the
column is absent on a store migrated through 025.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]  # services/corridor-store
MIGRATIONS = ROOT / "migrations"
M024 = MIGRATIONS / "024_vehicle_lookup_audit.sql"
WAVE = {"025": MIGRATIONS / "025_vehicle_lookup_audit_nohash.sql"}

#: What an audit row may carry after 025 — who, when, the MASKED mark,
#: found, the disclosure class (and its own id).
AUDIT_COLUMNS = ["id", "looked_up_at", "officer", "mark_masked", "found", "disclosure"]


def _no_comments(sql_text: str) -> str:
    return "\n".join(line.split("--", 1)[0] for line in sql_text.splitlines())


def _statements(sql_text: str) -> list[str]:
    """Split like the naive consumers: strip -- comments, split on ';'."""
    return [s.strip() for s in _no_comments(sql_text).split(";") if s.strip()]


def _flat(stmt: str) -> str:
    return " ".join(stmt.split())


def _created_columns() -> list[str]:
    body = re.search(
        r"CREATE TABLE IF NOT EXISTS corridor\.vehicle_lookup_audit \((.*?)\n\);",
        _no_comments(M024.read_text()), re.S,
    ).group(1)
    return [line.split()[0] for line in body.splitlines() if line.strip()]


def _dropped_columns(sql_text: str) -> set[str]:
    return set(re.findall(
        r"ALTER TABLE corridor\.vehicle_lookup_audit DROP COLUMN IF EXISTS (\w+)",
        _flat(_no_comments(sql_text)),
    ))


# ── static: grammar ────────────────────────────────────────────────────────


@pytest.mark.parametrize("num", sorted(WAVE))
class TestGrammar:
    def test_013_header_grammar(self, num):
        path = WAVE[num]
        lines = path.read_text().splitlines()
        assert lines[0] == f"-- {path.name}", "first line names the file"
        header = "\n".join(line for line in lines if line.startswith("--"))
        assert "SCHEMA ONLY, idempotent" in header
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
        for stmt in stmts:
            flat = _flat(stmt)
            assert flat.split()[0] == "ALTER", flat[:60]
            assert not re.search(r"\bINSERT\s+INTO\b|\bDELETE\s+FROM\b|\bUPDATE\s+\S+\s+SET\b",
                                 flat, re.I), flat[:60]
            for verb in re.findall(r"\bDROP (COLUMN|CONSTRAINT)\b(?! IF EXISTS)", flat):
                pytest.fail(f"unguarded DROP {verb}: {flat[:80]}")


# ── static: contracts ──────────────────────────────────────────────────────


def test_exactly_one_statement_the_guarded_hash_drop() -> None:
    stmts = _statements(WAVE["025"].read_text())
    assert [_flat(s) for s in stmts] == [
        "ALTER TABLE corridor.vehicle_lookup_audit DROP COLUMN IF EXISTS mark_sha256"
    ]


def test_runs_after_024_in_the_ledgered_order() -> None:
    names = sorted(p.name for p in MIGRATIONS.glob("0*.sql"))
    assert names.index(WAVE["025"].name) == names.index(M024.name) + 1


def test_the_audit_keeps_exactly_the_pinned_six_columns() -> None:
    """024's columns minus every later drop: no hash, no clear mark."""
    later = [p for p in sorted(MIGRATIONS.glob("0*.sql")) if p.name > M024.name]
    dropped: set[str] = set()
    for path in later:
        dropped |= _dropped_columns(path.read_text())
    assert [c for c in _created_columns() if c not in dropped] == AUDIT_COLUMNS
    assert "mark_sha256" in dropped


def test_no_later_migration_adds_a_hash_or_mark_column_back() -> None:
    for path in sorted(MIGRATIONS.glob("0*.sql")):
        if path.name <= M024.name:
            continue
        flat = _flat(_no_comments(path.read_text()))
        for m in re.finditer(r"ALTER TABLE corridor\.vehicle_lookup_audit ADD COLUMN"
                             r"(?: IF NOT EXISTS)? (\w+)", flat):
            assert m.group(1) in AUDIT_COLUMNS, f"{path.name} adds {m.group(1)}"
        # a later file names a hash only to DROP it (025)
        kept = re.sub(r"DROP COLUMN IF EXISTS \w+", "", flat)
        assert not re.search(r"sha256|digest\(|\bhash", kept, re.I), path.name


def test_the_hash_check_goes_with_the_column() -> None:
    """024's only hash constraint is the column's inline length CHECK, which
    PostgreSQL drops with the column: 025 needs no DROP CONSTRAINT."""
    checks = re.findall(r"CHECK \(([^()]*(?:\([^()]*\))?[^()]*)\)", M024.read_text())
    hash_checks = [c for c in checks if "mark_sha256" in c]
    assert hash_checks == ["char_length(mark_sha256) = 64"]
    created = _no_comments(M024.read_text())
    (line,) = [ln for ln in created.splitlines() if "mark_sha256" in ln]
    assert line.split()[0] == "mark_sha256", "the CHECK is inline on the column"
