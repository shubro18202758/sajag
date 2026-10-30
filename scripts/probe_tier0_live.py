#!/usr/bin/env python3
"""Live tier-0 probe — the repeat-identical-plan experiment on real traffic.

Live-audit context (finding tier0-cache-never-hits-live): verify_all.sh only
runs the MOCKED pytest suite for the tier-0 gate; nothing measured the gate
against the live stack, where nothing fed traffic.memory_docs and every
checkpoint read ``miss_novel`` forever. This script is that live
measurement. It runs the plan flow's pre-movement checkpoint (the same
``DeciderBrain.build_state_doc`` / ``pre_movement_questions`` builders, the
same trigger, forced) through a real ``DeciderBrain`` against the LIVE
model-host (:8083, the 27B) and LIVE embedding service (:8085, the corpus),
N times with the identical body. Its state doc is a fixed stand-in for the
gate body: production's lists the oracle's candidate routes under their
content-derived labels (``workflows/pre_movement.py`` ``_route_state_doc``),
so this measures the cache on an identical repeat, not production's exact
bytes — check_tier0_live.sh (a) measures the real /plan flow.

Two run modes:

    python3 scripts/probe_tier0_live.py            # repeat-plan experiment
    python3 scripts/probe_tier0_live.py --verify-corpus

``--verify-corpus`` only asserts the corpus/read side against the current
DB state (a :8085/search scoped to the movement id recalls the feeder's
kind=decision doc, judged against the tier-0 floor) — no 27B calls.

Output: one JSON line per checkpoint (tier, tier0 status, novelty status,
best score/doc, per-answer confidences) + a summary with Prometheus
DELTAS (miss_novel / miss_no_entry / miss_below_routine_floor / stored /
hit / memory feeder). Exit code is always 0 unless the harness itself
fails — the numbers are the measurement; interpretation belongs to the
check script or the reader (a live ``hit`` additionally requires the
27B's confidences to clear CONFIDENCE_FLOOR, which is a user calibration
decision, not a wiring property).

Pure client: no DB writes of its own — corpus writes happen only through
the DeciderBrain feeder under test (kind=decision upserts), exactly as
production would.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "services" / "convoy-brain" / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from prometheus_client import REGISTRY  # noqa: E402

from convoy_brain.config import (  # noqa: E402
    CONFIDENCE_FLOOR,
    TIER0_ROUTINE_SIMILARITY_FLOOR,
    load_service_urls,
)
from convoy_brain.decider import DeciderBrain  # noqa: E402
from convoy_brain.llm.decider_client import DeciderClient  # noqa: E402
from convoy_brain.memory.memory_client import (  # noqa: E402
    NOVELTY_SEARCH_KINDS,
    MemoryClient,
)

#: The gate's movement body: Mantralaya → Mumbai Airport T2, class Z,
#: far-future departure — both POIs on the Mumbai road network
#: (Mantralaya is junction 1 on Marine Drive 1001, T2 its departure forecourt,
#: junction 49 at the end of the Sahar Elevated Road 1020). MUST equal check_tier0_live.sh BODY: --verify-corpus searches with
#: this body's state doc, scoped to the gate's movement, to recall the
#: decision doc its plans fed.
GATE_BODY = {
    "origin": (72.8255127, 18.9275189),
    "destination": (72.8724794, 19.0999035),
    "vvip_class": "Z",
    "planned_departure": "2030-01-01T00:00:00Z",
}

#: The composite gate's (b) leg: a genuinely different corridor ON the
#: network (Haji Ali junction → Dadar TT Circle, the island city's spine; =
#: check_tier0_live.sh BODY_DIFFERENT) — its plan must be a MISS, never a
#: hit. (The former Surat pair no longer snaps to any segment, so its plan
#: never reached the decider checkpoint at all.)
DIFFERENT_POI_BODY = {
    "origin": (72.81137, 18.97811),
    "destination": (72.84811, 19.01753),
    "vvip_class": "Z",
    "planned_departure": "2030-01-01T00:00:00Z",
}

BODIES = {"gate": GATE_BODY, "different_poi": DIFFERENT_POI_BODY}


def build_state_doc(body: dict | None = None) -> str:
    """A pre-movement state doc for a body (the plan flow's builder and
    trigger; a fixed stand-in for production's candidate-route list)."""
    body = body or GATE_BODY
    return DeciderBrain.build_state_doc(
        trigger="pre_movement",
        summary=(
            f"Pre-event planning. Protection class {body['vvip_class']}, "
            f"departure {body['planned_departure']}, origin "
            f"{body['origin']}, destination {body['destination']}."
        ),
        context={"phase": "pre_movement"},
        pre_movement=True,
    )


def build_questions() -> dict[str, dict]:
    """The exact question set the pre-movement workflow asks."""
    return DeciderBrain.pre_movement_questions(
        ["primary", "alternate", "delay_departure"]
    )


def metric(name: str, labels: dict[str, str] | None = None) -> float:
    return REGISTRY.get_sample_value(name, labels) or 0.0


def tier0_deltas(before: dict[str, float]) -> dict[str, float]:
    names = [
        "miss_novel", "miss_no_entry", "miss_below_routine_floor",
        "miss_ttl_expired", "stored", "hit",
    ]
    out: dict[str, float] = {}
    for outcome in names:
        after = metric(
            "vvip_decider_tier0_cache_events_total", {"outcome": outcome}
        )
        out[outcome] = after - before.get(outcome, 0.0)
    return out


async def verify_corpus_only(args: argparse.Namespace) -> int:
    memory = MemoryClient(
        base_url=args.embedding_url or load_service_urls().embedding
    )
    state_doc = build_state_doc()
    result = await memory.search(state_doc, movement_id=args.movement_id)
    print(json.dumps({
        "mode": "verify-corpus",
        "movement_id": args.movement_id,
        "search_status": result.status,
        "hits": result.hits,
        "best_score": result.best_score,
        "best_doc_id": result.best_doc_id,
        "best_kind": result.best_kind,
        "tier0_floor": TIER0_ROUTINE_SIMILARITY_FLOOR,
    }))
    await memory.aclose()
    return 0


async def run_experiment(args: argparse.Namespace) -> int:
    urls = load_service_urls()
    decider = DeciderClient(base_url=args.model_host_url or urls.model_host)
    memory = MemoryClient(base_url=args.embedding_url or urls.embedding)
    brain = DeciderBrain(decider, memory_client=memory)

    before_tier0 = {
        outcome: metric("vvip_decider_tier0_cache_events_total", {"outcome": outcome})
        for outcome in (
            "miss_novel", "miss_no_entry", "miss_below_routine_floor",
            "miss_ttl_expired", "stored", "hit",
        )
    }
    before_recorded = metric(
        "vvip_decider_memory_record_events_total", {"outcome": "recorded"}
    )

    movement_id = args.movement_id or str(uuid.uuid4())
    body = BODIES[args.variant]
    state_doc = build_state_doc(body)
    questions = build_questions()

    rows = []
    for i in range(args.plans):
        if i and args.gap_sec:
            # The live plan flow spaces pre-movement checkpoints ~2 min
            # apart (corridor/routes/security/diversions/scenario steps in
            # between), so NOVELTY_MEMO_TTL_SEC (30 s) never bridges two
            # plans. Back-to-back checkpoints in one process WOULD read the
            # memoized zero-hit search of plan 1 and never see the corpus
            # doc the feeder just wrote — space them like production does.
            await asyncio.sleep(args.gap_sec)
        result = await brain.checkpoint(
            movement_id=movement_id,
            trigger="pre_movement",
            state_doc=state_doc,
            questions=questions,
            force=True,  # the plan flow always forces pre-movement checkpoints
        )
        row = {
            "plan": i + 1,
            "tier": result.tier,
            "tier0_status": result.audit.get("tier0_cache", {}).get("status"),
            "novelty_status": result.audit.get("novelty_latch", {}).get("status"),
            "best_score": result.audit.get("tier0_cache", {}).get("best_score"),
            "best_doc_id": result.audit.get("tier0_cache", {}).get("best_doc_id"),
            "confidences": {
                name: (
                    round(ans.confidence, 4) if ans.confidence is not None
                    else None
                )
                for name, ans in result.answers.items()
            },
        }
        rows.append(row)
        print(json.dumps(row))

    # Corpus verification: recall with the same state doc, scoped to the
    # movement, like the gate does.
    recall = await memory.search(state_doc, movement_id=movement_id)

    summary = {
        "mode": "repeat-plan-experiment",
        "movement_id": movement_id,
        "plans": args.plans,
        "confidence_floor": CONFIDENCE_FLOOR,
        "tier0_floor": TIER0_ROUTINE_SIMILARITY_FLOOR,
        "tier0_deltas": tier0_deltas(before_tier0),
        "memory_feeder_recorded_delta": (
            metric("vvip_decider_memory_record_events_total", {"outcome": "recorded"})
            - before_recorded
        ),
        "post_run_search": {
            "status": recall.status,
            "hits": recall.hits,
            "best_score": recall.best_score,
            "best_doc_id": recall.best_doc_id,
            "best_kind": recall.best_kind,
            "kinds_searched": NOVELTY_SEARCH_KINDS,
        },
    }
    print(json.dumps(summary))
    await decider.aclose()
    await memory.aclose()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plans", type=int, default=4)
    parser.add_argument(
        "--variant", choices=sorted(BODIES), default="gate",
        help="gate = the gate's Mantralaya → Mumbai Airport T2 body; different_poi = "
             "the composite gate's (b) leg body (Haji Ali junction → Dadar TT Circle)",
    )
    parser.add_argument(
        "--gap-sec", type=float, default=0.0,
        help="sleep between plans (use > NOVELTY_MEMO_TTL_SEC=30 to observe "
             "corpus visibility like the real plan flow does)",
    )
    parser.add_argument("--movement-id", default=None)
    parser.add_argument("--model-host-url", default=None)
    parser.add_argument("--embedding-url", default=None)
    parser.add_argument("--verify-corpus", action="store_true")
    args = parser.parse_args()
    if args.verify_corpus:
        if not args.movement_id:
            parser.error("--verify-corpus requires --movement-id")
        return asyncio.run(verify_corpus_only(args))
    return asyncio.run(run_experiment(args))


if __name__ == "__main__":
    raise SystemExit(main())
