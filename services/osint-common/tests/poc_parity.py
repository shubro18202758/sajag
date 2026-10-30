#!/usr/bin/env python3
"""PoC parity for osint_common (OS-1) — a script, not a test (``test_poc_parity.py`` asserts the same).

The real PoC outputs are READ IN PLACE and never copied (plan R13); only counts, ids and field names are printed,
never a title or a text. Usage::

    python tests/poc_parity.py [POC_OUT_DIR]       # default: $OSINT_POC_DIR, else the orchestration PoC out/

Checks:
1. every record of ``signals.raw.json`` validates as ``RawOsintSignal`` (forbidden keys, surviving PII, the
   sha1 signal id, the raw whitelist);
2. ``dss_output.json`` validates as ``DecisionSupport`` once the C-U-only fields are defaulted (``poc_dss_to_cu``
   lists every step it takes);
3. every ``sajag_event_kind`` of ``events.fused.json`` is one of the sixteen kinds and none is ``crime_incident``.
"""

from __future__ import annotations

import copy
import json
import os
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from osint_common.kinds import ALL_EVENT_KINDS
from osint_common.types import DecisionSupport, RawOsintSignal, signal_rejection_reason

def _poc_root() -> Path:
    """The OSINT prototype, read in place: OSINT_POC_ROOT, else ``.orchestration/osint/prototype`` in this checkout
    or in the checkout whose ``.worktrees/<name>`` this is (absent in a clone, where the PoC tests skip)."""
    if os.environ.get("OSINT_POC_ROOT"):
        return Path(os.environ["OSINT_POC_ROOT"])
    for parent in Path(__file__).resolve().parents:
        candidate = parent / ".orchestration" / "osint" / "prototype"
        if candidate.is_dir():
            return candidate
    return Path(".orchestration/osint/prototype")


POC_OUT_DEFAULT = _poc_root() / "out"


def poc_out_dir(arg: str | None = None) -> Path:
    return Path(arg or os.environ.get("OSINT_POC_DIR") or POC_OUT_DEFAULT)


def check_signals(out: Path) -> dict[str, Any]:
    records = json.loads((out / "signals.raw.json").read_text(encoding="utf-8"))
    valid, failures = 0, []
    for rec in records:
        try:
            RawOsintSignal.model_validate(rec)
            valid += 1
        except ValidationError as exc:
            failures.append({"signal_id": rec.get("signal_id"), "reason": signal_rejection_reason(exc)})
    return {
        "total": len(records),
        "valid": valid,
        "failures": failures,
        "by_source": dict(sorted(Counter(r.get("source") for r in records).items())),
        "pii_redactions": sum(int(r.get("pii_redactions") or 0) for r in records),
    }


#: Every field the C-U shape has and the PoC's dss_output.json lacks or names differently, with what the adapter
#: does about it. The WP named the first five; the rest are listed so nothing is defaulted silently.
ADAPTER_STEPS: tuple[str, ...] = (
    "state <- human_gate.state ('proposed') [C-U-only]",
    "seed <- provenance.seed (20261024; the PoC kept it under provenance) [C-U-only]",
    "horizon_min <- 45 (C-U's default horizon) [C-U-only]",
    "recommendation.strategy_prior <- null (no brain prior in the PoC) [C-U-only]",
    "provenance.wargame_method <- 'surrogate' (the PoC's provenance.wargame says 'Monte-Carlo surrogate') [C-U-only]",
    "generated_at <- dss_output.json mtime (UTC) [C-U-only: the PoC wrote no timestamp]",
    "human_gate.note dropped [PoC-only prose; C-U human_gate has no note]",
    "coa_set[].actions[].target -> target_urn; the non-URN 'ICCC' (the step's home, not a target) -> null",
    "provenance.sources[] + signal_id (matched by url in signals.raw.json) + role (first primary, rest corroborating)",
    "model defaults (C-U nullable or list fields): situation.junction_id null, human_gate.decided_at null, "
    "situation.attach.corroborates_live_urn null and .distance_m null (X18 AttachResult), "
    "provenance.sim_run_ids [], provenance.model_tiers [], provenance.brain_degraded false, "
    "coa_set[].actions[].params {}, coa_set[].predicted_outcome.cascade.affected_segment_ids []",
)


def poc_dss_to_cu(poc: dict[str, Any], signals: list[dict[str, Any]], generated_at: str) -> dict[str, Any]:
    """The PoC DSS in the C-U shape (``ADAPTER_STEPS``); everything else passes through untouched."""
    d = copy.deepcopy(poc)
    prov = d["provenance"]
    d["state"] = d["human_gate"]["state"]
    d["seed"] = prov.pop("seed")
    d["horizon_min"] = 45
    d["recommendation"]["strategy_prior"] = None
    method = str(prov.pop("wargame"))
    prov["wargame_method"] = "surrogate" if "surrogate" in method.lower() else "twin+cascade"
    d["generated_at"] = generated_at
    d["human_gate"].pop("note", None)
    for coa in d["coa_set"]:
        for action in coa["actions"]:
            if "target" in action:
                target = action.pop("target")
                action["target_urn"] = target if isinstance(target, str) and ":" in target else None
    by_url = {s["url"]: s["signal_id"] for s in signals if s.get("url")}
    for i, src in enumerate(prov["sources"]):
        src["signal_id"] = by_url[src["url"]]
        src["role"] = "primary" if i == 0 else "corroborating"
    return d


def check_dss(out: Path) -> dict[str, Any]:
    path = out / "dss_output.json"
    poc = json.loads(path.read_text(encoding="utf-8"))
    signals = json.loads((out / "signals.raw.json").read_text(encoding="utf-8"))
    mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    adapted = poc_dss_to_cu(poc, signals, mtime)
    try:
        dss = DecisionSupport.model_validate(adapted)
    except ValidationError as exc:
        return {"valid": False, "errors": [(e["loc"], e["msg"][:160]) for e in exc.errors(include_url=False)]}
    rec = dss.recommendation
    return {
        "valid": True,
        "dss_id": dss.dss_id,
        "event_urn": dss.event_urn,
        "top_coa_id": rec.top_coa_id,
        "ranked": rec.ranked_coa_ids,
        "consistency_ratio": dss.ahp.consistency_ratio,
        "closeness": {c.coa_id: c.score.closeness for c in dss.coa_set},
        "infeasible": [c.coa_id for c in dss.coa_set if not c.resource_feasibility.feasible],
        "evoi": rec.value_of_information.evoi,
        "advise_gather": rec.value_of_information.advise_gather,
        "labels": dss.labels,
        "wargame_method": dss.provenance.wargame_method,
    }


def check_fused(out: Path) -> dict[str, Any]:
    fused = json.loads((out / "events.fused.json").read_text(encoding="utf-8"))["fused_events"]
    kinds_seen = [f.get("sajag_event_kind") for f in fused]
    present = [k for k in kinds_seen if k is not None]
    return {
        "fused": len(fused),
        "surfaced": sum(1 for f in fused if f.get("is_event")),
        "sajag_event_kinds": dict(sorted(Counter(present).items())),
        "unknown_kinds": sorted({k for k in present if k not in ALL_EVENT_KINDS}),
        "crime_incident": sum(1 for k in present if k == "crime_incident"),
    }


def main(argv: list[str]) -> int:
    out = poc_out_dir(argv[1] if len(argv) > 1 else None)
    print(f"# osint_common PoC parity — PoC outputs read in place from {out} (nothing copied)")
    sig = check_signals(out)
    print(f"[1] signals.raw.json: {sig['valid']}/{sig['total']} validate as RawOsintSignal")
    print(f"    by source: {sig['by_source']}  pii_redactions (sum): {sig['pii_redactions']}")
    for f in sig["failures"]:
        print(f"    FAIL {f['signal_id']}: {f['reason']}")
    dss = check_dss(out)
    print("[2] dss_output.json as DecisionSupport after defaulting the C-U-only fields:")
    for step in ADAPTER_STEPS:
        print(f"    - {step}")
    if dss["valid"]:
        print(f"    VALID: dss_id={dss['dss_id']} event_urn={dss['event_urn']} top={dss['top_coa_id']}")
        print(f"    ranked={dss['ranked']} CR={dss['consistency_ratio']} infeasible={dss['infeasible']}")
        print(f"    closeness={dss['closeness']} EVOI={dss['evoi']} advise_gather={dss['advise_gather']}")
        print(f"    labels={dss['labels']} wargame_method={dss['wargame_method']}")
    else:
        print(f"    INVALID: {dss['errors']}")
    fused = check_fused(out)
    print(f"[3] events.fused.json: {fused['fused']} situations, {fused['surfaced']} surfaced")
    print(f"    sajag_event_kinds: {fused['sajag_event_kinds']}")
    print(f"    outside the 16 kinds: {fused['unknown_kinds']}  crime_incident: {fused['crime_incident']}")
    ok = (
        sig["valid"] == sig["total"] == 107
        and dss["valid"]
        and not fused["unknown_kinds"]
        and fused["crime_incident"] == 0
    )
    print("PARITY " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
