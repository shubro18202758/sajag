#!/usr/bin/env python3
"""osint_scope_cleanup.py — retire stored OSINT situations that are out of scope.

The oracle's ingest refuses person-crime, group-conflict and political items since the scope gate
(``osint_common.scope``; ``traffic_oracle.osint.ingest``) and leaves stored ones out of every re-fusion,
so a situation of the last 72 h is withdrawn on the next ingest cycle by itself. Older situations, and
any surfaced before the rule, stay surfaced until this script retires them.

    python3 scripts/osint_scope_cleanup.py            dry-run (default): SELECT only; prints counts and ids
    python3 scripts/osint_scope_cleanup.py --apply    retires them (one UPDATE, one transaction)

A situation is out of scope when its class or a correlated class is ``reported_crime``, ``public_conflict``
or ``unrest``, or when its label or summary reads as crime, conflict or politics (the same cue lists as the
gate). A procession or gathering whose stored summary carries political terms is retired too
(``political_terms``): if its signals are still inside the 72 h window, the next re-fusion writes it again
with those terms withheld.

Retiring is the store's own withdrawal: ``is_event = FALSE`` and ``held_reason = 'withdrawn: out of scope
(<reason>)'`` (a withdrawn situation counts in no held bucket). No row is deleted; the raw signals, the
sources and the audit stay. A corridor event an officer promoted from such a situation is never touched:
it is listed for the officer to review (closing it is a human decision).

Never prints a label, a summary or any other text: ids, classes and reasons only.

Env: POSTGIS_CONTAINER (sajag-postgis), POSTGIS_USER (corridor_admin), POSTGIS_DB (corridor_db).
Exit: 0 done · 1 a query failed · 2 usage.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from collections import Counter
from collections.abc import Callable, Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "osint-common" / "src"))

from osint_common import scope  # noqa: E402 — the path above is this checkout's package

FS, RS = "\x1f", "\x1e"
_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")

SQL_SURFACED = (
    "SELECT r.osint_event_id::text, r.event_class, array_to_string(r.correlated_classes, ','), "
    "coalesce(r.label, ''), coalesce(r.summary, '') FROM osint.resolved_events r "
    "WHERE r.is_event AND r.superseded_by IS NULL ORDER BY r.created_at"
)
SQL_PROMOTED = (
    "SELECT e.metadata->>'osint_event_id', e.event_id::text, e.status FROM events.corridor_events e "
    "WHERE e.source_kind = 'osint' AND e.status IN ('planning', 'approved', 'active')"
)


def psql_cmd() -> list[str]:
    return [
        "docker", "exec", os.environ.get("POSTGIS_CONTAINER") or "sajag-postgis", "psql", "-X", "-At",
        "-v", "ON_ERROR_STOP=1", "-F", FS, "-R", RS,
        "-U", os.environ.get("POSTGIS_USER") or "corridor_admin", "-d", os.environ.get("POSTGIS_DB") or "corridor_db",
    ]


def run_sql(query: str) -> list[list[str]] | None:
    try:
        out = subprocess.run([*psql_cmd(), "-c", query], capture_output=True, text=True, timeout=60, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if out.returncode != 0:
        return None
    return [rec.split(FS) for rec in out.stdout.split(RS) if rec.strip()]


def verdict(event_class: str, correlated: Sequence[str], label: str, summary: str) -> str | None:
    """The retirement reason of one stored situation, else None (pure)."""
    for cls in (event_class, *correlated):
        reason = scope.screen_class(cls)
        if reason is not None:
            return reason
    v = scope.screen(label, summary)
    if v.reason is not None:
        return v.reason
    if v.masked:
        return "political_terms"
    return None


def plan(rows: Sequence[Sequence[str]]) -> list[tuple[str, str, str]]:
    """[(osint_event_id, event_class, reason)] for the rows to retire."""
    out = []
    for row in rows:
        if len(row) < 5 or not _UUID.match(row[0]):
            continue
        oid, cls, corr, label, summary = row[:5]
        reason = verdict(cls, [c for c in corr.split(",") if c], label, summary)
        if reason is not None:
            out.append((oid, cls, reason))
    return out


def retire_sql(items: Sequence[tuple[str, str, str]]) -> str:
    """One UPDATE per reason, in one transaction; ids are validated UUIDs."""
    by_reason: dict[str, list[str]] = {}
    for oid, _, reason in items:
        if not _UUID.match(oid) or reason not in (*scope.REASONS, "political_terms"):
            raise ValueError("refusing an unexpected id or reason")
        by_reason.setdefault(reason, []).append(oid)
    stmts = [
        "UPDATE osint.resolved_events SET is_event = FALSE, "
        f"held_reason = 'withdrawn: out of scope ({reason})', updated_at = NOW() "
        f"WHERE osint_event_id = ANY('{{{','.join(ids)}}}'::uuid[]) AND superseded_by IS NULL AND is_event;"
        for reason, ids in sorted(by_reason.items())
    ]
    return "BEGIN; " + " ".join(stmts) + " COMMIT;"


def main(argv: Sequence[str], sql: Callable[[str], list[list[str]] | None] = run_sql) -> int:
    args = list(argv)
    apply = "--apply" in args
    if any(a not in ("--apply",) for a in args):
        print(__doc__.split("\n\n")[1])
        return 0 if args in (["-h"], ["--help"]) else 2
    rows = sql(SQL_SURFACED)
    if rows is None:
        print("[osint-scope] the store did not answer (docker exec psql)", file=sys.stderr)
        return 1
    items = plan(rows)
    counts = Counter(reason for _, _, reason in items)
    promoted = {r[0]: (r[1], r[2]) for r in (sql(SQL_PROMOTED) or []) if len(r) >= 3}
    print(f"[osint-scope] {len(rows)} surfaced situation(s); {len(items)} out of scope: "
          + (", ".join(f"{k} {v}" for k, v in sorted(counts.items())) or "none"))
    for oid, cls, reason in items:
        note = ""
        if oid in promoted:
            event_id, status = promoted[oid]
            note = f" · promoted to corridor event {event_id} ({status}): left for the officer to review"
        print(f"  {oid}  {cls:16s} {reason}{note}")
    if not items:
        return 0
    if not apply:
        print("[osint-scope] dry-run: nothing written; --apply retires them (is_event false, held 'withdrawn: out of scope')")
        return 0
    if sql(retire_sql(items)) is None:
        print("[osint-scope] the retirement failed; nothing was changed (one transaction)", file=sys.stderr)
        return 1
    print(f"[osint-scope] retired {len(items)} situation(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
