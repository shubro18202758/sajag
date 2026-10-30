"""Value of information (C-U): a REAL expected-value-of-information number drives "gather first or act now".

Belief ``c`` = the credibility that the situation is as reported.  Each scored COA has a loss if the report is
real (unresolved public-safety harm dominates; disruption and cascade are secondary) and a loss if it is false
(the footprint imposed on the city is pure waste) — the PoC's ``coa_losses``.  Then (Howard 1966):

* ``L_act_now`` = min over the FEASIBLE COAs of ``c·L_real + (1 − c)·L_false``;
* ``L_gather_then_act`` = the information COA's cost (operational cost + a delay penalty from its time to effect)
  + ``c·min L_real + (1 − c)·L_false(baseline)`` — act optimally once the truth is known;
* ``EVOI = L_act_now − L_gather_then_act``.  Because the information cost is inside ``L_gather_then_act``, EVOI is
  the value of verifying first NET of its cost: ``advise_gather`` holds only when the value of verifying exceeds
  the information COA's cost — by the PoC's decision margin, ``EVOI > 0.02`` — and only when the information COA
  can actually be carried out (feasible, unvetoed).

The ``why`` sentence is derived from the dominant term of the value of verifying, which splits into two regrets
of acting now: the footprint wasted if the report is false (``(1 − c)·(L_false(act) − L_false(baseline))``, the
credibility term) and the better response missed if it is real (``c·(L_real(act) − min L_real)``, the margin
term).  When gathering is advised the larger one names the reason; otherwise "acting now dominates".  A
resource-blocked best response and the public-safety floor's verify-first mode are named in the ``why`` too
(FIX-C) — a blocked COA is reported with what is missing, never silently dropped.  The ``why`` also says that the
credibility it weighs is uncalibrated (a source-prior score, not a measured probability), so the EVOI is indicative
(HON-18).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from traffic_oracle.decision_support.coa import CoaDraft
from traffic_oracle.decision_support.mcda import VERIFY_BELOW
from traffic_oracle.decision_support.wargame import SegmentModel, resolve_lanes

__all__ = ["ADVISE_MARGIN", "UNCALIBRATED_NOTE", "Losses", "coa_losses", "dominant_term", "value_of_information"]

#: the PoC's decision margin on EVOI
ADVISE_MARGIN = 0.02
#: what the ``why`` says about the belief it weighs (HON-18): credibility is a source-prior score with capped
#: corroboration bumps (``osint_analysis.credibility``), not a probability calibrated against outcomes
UNCALIBRATED_NOTE = (
    "credibility %.2f is an uncalibrated source-prior score, not a measured probability, so this EVOI is "
    "indicative"
)
#: the information COA's operational cost (a unit's time) and its delay penalty per 10 min to effect
INFO_BASE_COST = 0.10
INFO_DELAY_COST = 0.25


@dataclass(frozen=True)
class Losses:
    if_real: float
    if_false: float


def coa_losses(draft: CoaDraft, outcome: Mapping[str, Any], *, injuries: bool, seg: SegmentModel) -> Losses:
    """``(loss if real, loss if false)`` in the PoC's normalised loss unit (0 .. ~1.5)."""
    harm = 1.0 - float(outcome["event_resolution_prob"])
    if injuries and not draft.dispatch_108:
        harm += 0.35  # the injured left unserved
    disruption = min(1.0, float(outcome["total_disruption_vehicle_hours"]["mean"]) / seg.disruption_scale)
    cascade = min(1.0, float(outcome["cascade"]["spillover_vehicle_hours"]["mean"]) / seg.spillover_scale)
    lb = resolve_lanes(draft.effects.lanes_blocked, seg.lanes)
    resource = min(
        1.0,
        draft.responder_units * 0.18 + (0.2 if draft.dispatch_108 else 0.0) + seg.lane_equivalents(lb) * 0.12,
    )
    return Losses(
        if_real=1.00 * harm + 0.25 * disruption + 0.25 * cascade,
        if_false=0.60 * disruption + 0.60 * cascade + 0.40 * resource,
    )


def value_of_information(
    scored: Sequence[CoaDraft],
    outcomes: Mapping[str, Mapping[str, Any]],
    feasible: Mapping[str, bool],
    *,
    credibility: float,
    margin: float,
    injuries: bool,
    seg: SegmentModel,
    blocked: Mapping[str, Sequence[str]] | None = None,
    blocked_best: str | None = None,
    floor_mode: str = "none",
) -> dict[str, Any]:
    """The C-U ``value_of_information`` block over the scored (unvetoed) COAs.

    ``blocked`` maps a COA id to its unit shortfalls and ``blocked_best`` names the resource-blocked best
    response (FIX-C): both are named in the ``why`` when present.  ``floor_mode`` is the public-safety floor's
    mode (``mcda.public_safety_floor``): ``"verify"`` adds the verify-first rationale when the engine is not
    already advising gathering."""
    cred = float(credibility)
    blocked = dict(blocked or {})
    losses = [coa_losses(c, outcomes[c.coa_id], injuries=injuries, seg=seg) for c in scored]
    feas = [i for i, c in enumerate(scored) if feasible.get(c.coa_id)]
    if not feas:
        feas = list(range(len(scored)))
    exp_now = [cred * losses[i].if_real + (1 - cred) * losses[i].if_false for i in feas]
    l_act = min(exp_now)
    act = feas[exp_now.index(l_act)]
    info_idx = next((i for i, c in enumerate(scored) if c.kind == "information"), None)
    best_real = min(losses[i].if_real for i in feas)
    base_idx = next((i for i, c in enumerate(scored) if c.kind == "baseline"), None)
    best_false = losses[base_idx].if_false if base_idx is not None else min(x.if_false for x in losses)
    info_cost = 0.0
    if info_idx is not None:
        tte = float(outcomes[scored[info_idx].coa_id]["time_to_effect_sec"])
        info_cost = INFO_BASE_COST + INFO_DELAY_COST * min(1.0, tte / 600.0)
    l_gather = info_cost + cred * best_real + (1 - cred) * best_false
    evoi = round(float(l_act - l_gather), 4)
    gross = float(l_act - (l_gather - info_cost))
    info_ok = info_idx is not None and bool(feasible.get(scored[info_idx].coa_id))
    advise = info_ok and evoi > ADVISE_MARGIN
    # the value of verifying splits into two regrets of acting now: the footprint wasted if the report is false
    # (the credibility term) and the better response missed if it is real (the margin term)
    regret_false = (1 - cred) * (losses[act].if_false - best_false)
    regret_real = cred * (losses[act].if_real - best_real)
    if advise:
        if regret_false >= regret_real:
            why = (
                "credibility %.2f leaves a material chance (%.0f%%) the report is unconfirmed; verifying first "
                "avoids an over-reaction whose footprint would be wasted (EVOI %.3f: the value of verifying %.3f "
                "exceeds its cost %.3f)" % (cred, (1 - cred) * 100, evoi, gross, info_cost)
            )
        else:
            why = (
                "decision margin is thin (%.3f); a short verify step is expected to improve the choice by EVOI "
                "%.3f (the value of verifying %.3f exceeds its cost %.3f)" % (margin, evoi, gross, info_cost)
            )
    elif info_idx is not None and not info_ok:
        missing = _missing_text(blocked.get(scored[info_idx].coa_id))
        why = (
            "acting now: verifying first is not available this cycle (the information COA cannot be resourced or "
            "is vetoed%s), so the recommended feasible COA stands (EVOI %.3f, credibility %.2f)"
            % (missing, evoi, cred)
        )
    elif info_idx is None:
        why = "acting now: there is no information COA to gather with (EVOI %.3f, credibility %.2f)" % (evoi, cred)
    else:
        why = (
            "acting now dominates: the value of verifying first (%.3f) does not exceed its cost (%.3f), EVOI "
            "%.3f; credibility %.2f and margin %.3f already justify committing to the recommended feasible COA"
            % (gross, info_cost, evoi, cred, margin)
        )
    # HON-18: the belief the EVOI weighs is the credibility score — source priors plus capped corroboration
    # bumps, never calibrated against outcomes — so the why says the number is indicative, not a probability
    why += "; " + UNCALIBRATED_NOTE % cred
    if blocked_best is not None:
        why += (
            "; the best response %s is blocked on resources (%s) — request units"
            % (blocked_best, "; ".join(blocked.get(blocked_best, ())))
        )
    if floor_mode == "verify" and not advise and info_idx is not None:
        why += (
            "; verify first: people are reported hurt or public safety is at stake, but credibility %.2f is below "
            "the %.2f act-on-it threshold — %s is the course that confirms or dismisses the report before any "
            "response" % (cred, VERIFY_BELOW, scored[info_idx].coa_id)
        )
    return {
        "evoi": evoi,
        "L_act_now": round(float(l_act), 4),
        "L_gather_then_act": round(float(l_gather), 4),
        "info_cost": round(info_cost, 4),
        "advise_gather": bool(advise),
        "info_coa_id": scored[info_idx].coa_id if info_idx is not None else None,
        "why": why[:1000],
    }


def _missing_text(shortfalls: Sequence[str] | None) -> str:
    """``": police: need 1, 0 free — request units"`` for the information COA's unit shortfalls (``""`` when it
    is vetoed or blocked only by a missing road anchor — the dissent says what that needs)."""
    if not shortfalls:
        return ""
    return ": %s — request units" % "; ".join(shortfalls)


def dominant_term(value: Mapping[str, Any]) -> str:
    """``"credibility"`` | ``"margin"`` | ``"act_now"`` — which term the ``why`` sentence follows."""
    why = str(value.get("why", ""))
    if why.startswith("credibility"):
        return "credibility"
    if why.startswith("decision margin"):
        return "margin"
    return "act_now"
