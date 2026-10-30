"""023_osint_source_context_role.sql: the 'context' source role (grammar + lockstep with osint_common).

The store CHECK on osint.event_sources.role must list exactly osint_common.types.SourceRole, and the file must stay
in the plain-statement subset the naive ';'-splitters apply (see 007's GRAMMAR CONSTRAINT).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import get_args

ROOT = Path(__file__).resolve().parents[3]
MIGRATION = ROOT / "services" / "corridor-store" / "migrations" / "023_osint_source_context_role.sql"
sys.path.insert(0, str(ROOT / "services" / "osint-common" / "src"))

from osint_common.types import SourceRole  # noqa: E402


def _statements(sql: str) -> list[str]:
    body = "\n".join(line for line in sql.splitlines() if not line.lstrip().startswith("--"))
    return [s.strip() for s in body.split(";") if s.strip()]


def test_plain_statement_grammar() -> None:
    sql = MIGRATION.read_text()
    assert "$$" not in sql and "/*" not in sql
    stmts = _statements(sql)
    assert len(stmts) == 2
    assert stmts[0].startswith("ALTER TABLE osint.event_sources DROP CONSTRAINT IF EXISTS event_sources_role_check")
    assert stmts[1].startswith("ALTER TABLE osint.event_sources ADD CONSTRAINT event_sources_role_check")


def test_check_lists_exactly_the_source_roles() -> None:
    check = re.search(r"CHECK \(role IN \(([^)]*)\)\)", MIGRATION.read_text())
    assert check, "no role CHECK in 023"
    values = re.findall(r"'([a-z_]+)'", check.group(1))
    assert sorted(values) == sorted(get_args(SourceRole))
    assert "context" in values
