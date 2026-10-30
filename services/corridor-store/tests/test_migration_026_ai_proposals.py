"""026_ai_proposal_decision_log.sql: grammar and contract tests (static, no database).

* the 013 header grammar (file name line, SCHEMA ONLY / idempotent, the 007 grammar note, the ethics rails);
* splitter-safe: no ';' or '--' inside string literals, no dollar-quoted bodies, no block comments;
* schema only and idempotent: every statement is a CREATE … IF NOT EXISTS, no INSERT / UPDATE / DELETE, no DROP;
* the contract the oracle's ai_proposals router writes: the pinned columns, proposal_id UNIQUE (the race-safe
  already-decided check), the source and decision CHECKs, officer NOT NULL; no person column; sorts after 025.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # services/corridor-store
MIGRATIONS = ROOT / "migrations"
M026 = MIGRATIONS / "026_ai_proposal_decision_log.sql"

COLUMNS = [
    "log_id", "proposal_id", "source", "kind", "subject_urn", "summary", "labels", "evidence", "decision",
    "officer", "actor_source", "note", "decided_at",
]


def _no_comments(sql_text: str) -> str:
    return "\n".join(line.split("--", 1)[0] for line in sql_text.splitlines())


def _statements(sql_text: str) -> list[str]:
    return [s.strip() for s in _no_comments(sql_text).split(";") if s.strip()]


def _flat(stmt: str) -> str:
    return " ".join(stmt.split())


def test_header_grammar() -> None:
    lines = M026.read_text().splitlines()
    assert lines[0] == f"-- {M026.name}"
    header = "\n".join(line for line in lines if line.startswith("--"))
    assert "SCHEMA ONLY, idempotent" in header
    assert "Grammar constraint (007 header): consumed by naive ';'-splitters" in header
    assert "Ethics rails (C6)" in header


def test_splitter_safe_literals() -> None:
    text = M026.read_text()
    for literal in re.findall(r"'([^']*)'", _no_comments(text)):
        assert ";" not in literal and "--" not in literal, literal
    assert "$$" not in text and not re.search(r"\$[A-Za-z_]+\$", text)
    assert "/*" not in text


def test_schema_only_idempotent() -> None:
    stmts = [_flat(s) for s in _statements(M026.read_text())]
    assert stmts
    for flat in stmts:
        assert re.match(r"CREATE (SCHEMA|TABLE|INDEX) IF NOT EXISTS ", flat), flat[:80]
        assert not re.search(r"\bINSERT\s+INTO\b|\bDELETE\s+FROM\b|\bUPDATE\s+\S+\s+SET\b|\bDROP\b", flat, re.I)


def _table_body() -> str:
    m = re.search(r"CREATE TABLE IF NOT EXISTS decision\.ai_proposal_decision_log \((.*?)\n\);",
                  _no_comments(M026.read_text()), re.S)
    assert m
    return m.group(1)


def test_the_pinned_columns_and_constraints() -> None:
    body = _table_body()
    cols = [line.split()[0] for line in body.splitlines() if line.strip()]
    assert cols == COLUMNS
    flat = _flat(body)
    assert "proposal_id TEXT NOT NULL UNIQUE" in flat
    assert "CHECK (source IN ('forecast', 'hydro', 'twin'))" in flat
    assert "CHECK (decision IN ('approve', 'reject'))" in flat
    assert "officer TEXT NOT NULL" in flat
    assert "decided_at TIMESTAMPTZ NOT NULL DEFAULT now()" in flat


def test_no_person_column() -> None:
    for col in COLUMNS:
        assert not re.search(r"author|person|handle|face|biometric|phone|email|owner|plate", col), col


def test_runs_after_025() -> None:
    names = sorted(p.name for p in MIGRATIONS.glob("0*.sql"))
    assert [n for n in names if n.startswith("026_")] == [M026.name]
    assert names.index(M026.name) == names.index("025_vehicle_lookup_audit_nohash.sql") + 1
