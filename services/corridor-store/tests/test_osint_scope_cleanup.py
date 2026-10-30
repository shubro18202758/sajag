"""scripts/osint_scope_cleanup.py: dry-run by default (SELECT only), retires out-of-scope situations in one
transaction with --apply, never prints a stored text, and never touches a promoted corridor event."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "scripts" / "osint_scope_cleanup.py"

IDS = [f"{i:08x}-0000-4000-8000-000000000000" for i in range(1, 7)]
ROWS = [
    [IDS[0], "reported_crime", "", "Reported crime · Behala", "A theft at a shop"],
    [IDS[1], "public_conflict", "", "Public conflict · Behala", "Two groups clash"],
    [IDS[2], "fire", "", "Fire · New Market", "অগ্নিকাণ্ডে গ্রেপ্তার এক"],  # an arrest in a fire case
    [IDS[3], "road_accident", "road_accident,public_conflict", "Road accident · EM Bypass", "Collision"],
    [IDS[4], "procession", "", "Procession · Behala", "রাজনৈতিক মিছিলে রাস্তায় যানজট"],
    [IDS[5], "weather_hazard", "", "Weather hazard · Mumbai", "Thunderstorm warning"],
]


@pytest.fixture
def mod():
    spec = importlib.util.spec_from_file_location("osint_scope_cleanup_under_test", SCRIPT)
    m = importlib.util.module_from_spec(spec)
    sys.modules["osint_scope_cleanup_under_test"] = m
    spec.loader.exec_module(m)
    return m


def _fake(sent: list[str], promoted: list[list[str]] | None = None):
    def sql(query: str):
        sent.append(query)
        if query.startswith("SELECT r.osint_event_id"):
            return [list(r) for r in ROWS]
        if query.startswith("SELECT e.metadata"):
            return promoted or []
        return []

    return sql


def test_plan_reasons(mod):
    plan = mod.plan(ROWS)
    assert [(oid, reason) for oid, _, reason in plan] == [
        (IDS[0], "crime"), (IDS[1], "conflict"), (IDS[2], "crime"), (IDS[3], "conflict"),
        (IDS[4], "political_terms"),
    ]


def test_dry_run_selects_only_and_prints_no_text(mod, capsys):
    sent: list[str] = []
    assert mod.main([], sql=_fake(sent)) == 0
    assert all(q.startswith("SELECT") for q in sent)
    out = capsys.readouterr().out
    assert "5 out of scope" in out and "dry-run" in out
    for _, _, label, summary in (r[1:] for r in ROWS):
        assert summary not in out and label not in out


def test_apply_is_one_transaction_and_leaves_promoted_events_alone(mod, capsys):
    sent: list[str] = []
    promoted = [[IDS[1], "11111111-2222-4333-8444-555555555555", "active"]]
    assert mod.main(["--apply"], sql=_fake(sent, promoted)) == 0
    writes = [q for q in sent if not q.startswith("SELECT")]
    assert len(writes) == 1 and writes[0].startswith("BEGIN;") and writes[0].endswith("COMMIT;")
    assert "events.corridor_events" not in writes[0] and "DELETE" not in writes[0]
    assert "held_reason = 'withdrawn: out of scope (crime)'" in writes[0]
    assert IDS[5] not in writes[0]
    assert "left for the officer to review" in capsys.readouterr().out


def test_unexpected_ids_are_refused(mod):
    with pytest.raises(ValueError):
        mod.retire_sql([("x'); DROP TABLE t; --", "fire", "crime")])
    # a malformed id from the store is never planned
    assert mod.plan([["not-a-uuid", "reported_crime", "", "", ""]]) == []


def test_usage(mod):
    assert mod.main(["--force"], sql=_fake([])) == 2
