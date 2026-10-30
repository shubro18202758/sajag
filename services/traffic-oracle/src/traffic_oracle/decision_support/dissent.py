"""Recommendation dissent (C-U): not just the winner — why not the runner-up, and what single change would flip it.

Every clause is computed, never boilerplate:

* **why not the runner-up** — the closeness gap, the rank stability, and the heavily weighted criteria on which
  the recommended COA beats it — a lead on a fixed prior (the per-action safety table, the nominal time to effect:
  ``mcda.FIXED_PRIORS``) is said to be one and never claimed as a simulated advantage (HON-7, HON-8); when the
  runner-up is the do-nothing baseline held down by the public-safety
  floor, the clause says that instead of claiming a scoring win, and no closeness gap to the held baseline is
  claimed (the margin is never negative because of the hold);
* **the best blocked response** (FIX-C) — when the highest-scoring course of action that units could unblock
  outscores the pick, it is named with its closeness, what is actually short (from its own required and free
  units — "a patrol is free, but no 108 ambulance is free", never a blanket "none is on duty") and the
  plain-language action ("request units"), never buried behind a do-nothing recommendation;
* **the public-safety floor** (FIX-C) — when it holds, the sentence says the do-nothing baseline is held below
  every feasible response COA with the credibility the floor acted on; below the act-on-it threshold the
  rationale says verify first and points at the information COA (and names what is missing when the information
  COA cannot be resourced);
* **what would flip it**, each checked against the actual model:
  - *more units*: an infeasible COA whose TOPSIS closeness beats the pick would win once resourced (its shortfall
    is the change); one that would still lose is said to.  A COA blocked because an area-level report has no road
    ("no road anchor") is NOT a resourcing question: the change it needs is a road-level location for the report
    (a segment or a junction) and a regeneration, and its closeness on the notional arterial decides nothing;
  - *a reweighting*: the smallest single-criterion weight increase (×1.25 … ×8) under which the runner-up
    overtakes the pick, or that none does — never offered for a baseline the floor holds down (no weight can put
    it first: the floor is non-compensatory) or for a runner-up that cannot be resourced;
  - *an official source*: the value of information re-evaluated at official-grade credibility (0.95) and the
    credibility below which the engine would advise verifying first — for a reported situation, and for a
    corridor event a named officer promoted from one;
* **the honest corroboration sentence of the PoC** — how many independent publishers and source tiers stand
  behind the report, and that its credibility is not inflated past its verification state.  A corridor event
  promoted from OSINT carries its report's corroboration; an emulator event says EMULATED; only a live event
  opened on the city's own channel says that no OSINT corroboration is involved;
* **context, never corroboration** — a district-level source attached to a point report (source role
  ``context``) is named as "District warning in effect (<publisher>)" for an official one, else "District-level
  report in effect", and is not counted as corroboration, as a publisher or in the credibility;
* the infeasible aggressive option's note (ranked last and labelled — ``INFEASIBLE`` when no road anchor blocks
  it, ``RESOURCE-INFEASIBLE`` for units — with its 108 and cascade effects when the wargame shows them, said to be
  on a notional arterial for an area-level report);
* the second-order flags, each with what the wargame actually did with it: a live 108 route is fed to the
  cascade's 108 delay and a live closure with a segment is kept out of the reassignment (``twin+cascade`` only),
  its clearance named as a change only when it lies on an alternative the reassignment would otherwise use;
  everything else is "listed, not modelled";
* the brain's strategy prior when it disagrees — recorded, never scored.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any

from traffic_oracle.decision_support.coa import AGENCY_NOUN, ANCHOR_SHORTFALL
from traffic_oracle.decision_support.feasibility import FEED_UNAVAILABLE
from traffic_oracle.decision_support.mcda import CRITERION_IDS, FIXED_PRIORS, VERIFY_BELOW, topsis

__all__ = ["OFFICIAL_CREDIBILITY", "build_dissent", "context_sentence", "corroboration_sentence"]

OFFICIAL_CREDIBILITY = 0.95
_WEIGHT_STEPS = (1.25, 1.5, 2.0, 3.0, 5.0, 8.0)


def corroboration_sentence(
    situation: Mapping[str, Any], *, subject_kind: str, subject: Mapping[str, Any] | None = None
) -> str:
    """The PoC's honest corroboration sentence, by verification state — and, for a corridor ``event`` subject,
    by where the event came from (``subject``: :meth:`engine.Frame.subject_info`)."""
    if subject_kind != "event":
        return _osint_corroboration(situation)
    info = subject or {}
    state = situation.get("verification_state")
    cred = float(situation.get("credibility") or 0.0)
    origin = info.get("origin")
    if origin == "osint":
        # promoted from a reported situation: its corroboration is that report's, never the city's own channel
        lead = "The subject is a corridor event a named officer promoted from OSINT report %s" % (
            info.get("origin_urn") or "(its id is not recorded)")
        if not info.get("origin_detail", True):
            return lead + (
                "; that report's sources are not readable here, so the event keeps its stored %s at credibility "
                "%.2f and no independent publisher or source tier is claimed." % (state, cred)
            )
        return lead + ". " + _osint_corroboration(situation)
    if origin == "emulated" or state == "EMULATED":
        return (
            "The subject is an EMULATED corridor event (the event emulator's, credibility %.2f): not a real-world "
            "report, so no corroboration of any kind is involved." % cred
        )
    if state == "CONFIRMED":
        return (
            "The subject is a corridor event CONFIRMED by a named duty officer (credibility %.2f): no OSINT "
            "corroboration is involved." % cred
        )
    opened = info.get("opened_by") or "an operator"
    planning = "; still in planning" if info.get("status") == "planning" else ""
    text = (
        "The subject is a corridor event on the city's own channel, opened by %s%s (%s, credibility %.2f): the "
        "city's own record, not a third-party report, so no OSINT corroboration is involved." % (
            opened, planning, state, cred)
    )
    if info.get("derived_state"):
        text += (
            " It stores no verification state, so the DSS labels the city's own record %s (a duty officer's "
            "confirmation would make it CONFIRMED)." % state
        )
    return text


def _osint_corroboration(situation: Mapping[str, Any]) -> str:
    """The corroboration of a reported situation (or of the report a corridor event was promoted from)."""
    state = situation.get("verification_state")
    cred = float(situation.get("credibility") or 0.0)
    pubs = int(situation.get("independent_publishers") or 0)
    tiers = len(situation.get("source_tiers") or [])
    if state == "CONFIRMED":
        return (
            "The report is CONFIRMED by a named duty officer (%d source tier(s), %d independent publisher(s), "
            "credibility %.2f)." % (tiers, pubs, cred)
        )
    if state == "OFFICIAL-VERIFIED":
        return (
            "Corroboration includes an official source (%d source tier(s), %d independent publisher(s)), so the "
            "report is OFFICIAL-VERIFIED at credibility %.2f." % (tiers, pubs, cred)
        )
    if state == "UNVERIFIED-OSINT":
        return (
            "The report is UNVERIFIED-OSINT (%d independent publisher(s), %d source tier(s), credibility %.2f): "
            "it is not corroborated by a news or official source yet, and its credibility is not inflated."
            % (pubs, tiers, cred)
        )
    if situation.get("cross_type_corroborated"):
        return (
            "Corroboration is REAL and crosses source types: %d independent publisher(s), %d source tier(s), but "
            "no official confirmation yet, so verification_state stays %s and credibility (%.2f) is not inflated "
            "to official grade." % (pubs, tiers, state, cred)
        )
    return (
        "Corroboration is REAL but within one tier: %d independent news publisher(s), %d source tier(s) (no "
        "official confirmation yet), so verification_state stays %s and credibility is not inflated to official "
        "grade." % (pubs, tiers, state)
    )


def context_sentence(context: Sequence[Mapping[str, Any]]) -> str | None:
    """The context clause: each context source's note, said as context and never as corroboration."""
    notes = [str(c.get("note")) for c in context if c.get("note")]
    if not notes:
        return None
    return (
        "Context, not corroboration: %s — area-level source(s) attached to this report for context only, not "
        "counted as corroboration, as a publisher or in the credibility." % "; ".join(notes[:4])
    )


def _beats(
    a: Mapping[str, float], b: Mapping[str, float], keep: Sequence[str], weights: Mapping[str, float]
) -> list[str]:
    """Discriminating criteria on which ``a`` beats ``b``, heaviest weighted advantage first."""
    adv = [(weights[c] * (a[c] - b[c]), c) for c in keep if a[c] - b[c] > 1e-9]
    adv.sort(key=lambda t: (-t[0], t[1]))
    return [c for _, c in adv]


def _beats_clause(wins: Sequence[str]) -> str:
    """What the pick beats the runner-up on, never claiming a lead on a fixed prior (HON-7, HON-8) as a simulated
    advantage: ``safety_risk_reduction`` is a per-action table and ``time_to_effect`` a nominal time per COA kind
    (:data:`mcda.FIXED_PRIORS`), so a lead there is said to be one, apart from the modelled advantages."""
    modelled = [c for c in wins if c not in FIXED_PRIORS]
    priors = [c for c in wins if c in FIXED_PRIORS]
    prior_words = " and ".join("%s (%s)" % (c, FIXED_PRIORS[c]) for c in priors)
    if len(modelled) > 1:
        text = "the pick beats it on %s (its largest weighted advantages)" % ", ".join(modelled[:2])
    elif modelled:
        text = "the pick beats it on %s (its only discriminating advantage%s)" % (
            modelled[0], " outside the fixed priors" if priors else "")
    elif priors:
        return "the pick leads it only on %s — so no simulated advantage is claimed" % prior_words
    else:
        return "the pick beats it on no single discriminating criterion, only on the overall distance to the ideal"
    if priors:
        text += "; it also leads on %s, not a simulated advantage" % prior_words
    return text


def _weight_flip(
    matrix: Sequence[Sequence[float]],
    weights: Sequence[float],
    top: int,
    runner: int,
    candidates: Sequence[str],
) -> tuple[str, float] | None:
    """The smallest single-criterion weight increase under which ``runner`` overtakes ``top``."""
    best: tuple[str, float] | None = None
    for crit in candidates:
        j = CRITERION_IDS.index(crit)
        for step in _WEIGHT_STEPS:
            w = list(weights)
            w[j] *= step
            total = sum(w)
            w = [x / total for x in w]
            c = topsis(matrix, w).closeness
            if c and c[runner] > c[top]:
                if best is None or step < best[1]:
                    best = (crit, step)
                break
    return best


def _advise_band(voi_at: Callable[[float], Mapping[str, Any]]) -> tuple[float, float] | None:
    """The credibility range (0.01 steps) in which the engine would advise verifying first, if any (EVOI is not
    monotonic in credibility: verifying pays when the report is neither near-certain nor near-dismissable)."""
    hits = [k / 100.0 for k in range(1, 100) if voi_at(k / 100.0)["advise_gather"]]
    return (hits[0], hits[-1]) if hits else None


def _anchor_blocked(coa: Mapping[str, Any]) -> bool:
    """A COA blocked up front because the report has no road (area-level): no unit count can fix that."""
    return ANCHOR_SHORTFALL in coa["resource_feasibility"]["shortfalls"]


def _unit_shortfalls(coa: Mapping[str, Any]) -> list[str]:
    return [s for s in coa["resource_feasibility"]["shortfalls"] if s != ANCHOR_SHORTFALL]


def _need_words(required: Mapping[str, int]) -> str:
    """The units a COA needs, in words: ``"a 108 ambulance and a patrol"`` (deterministic agency order)."""
    parts: list[str] = []
    for agency, n in sorted(required.items()):
        one, many = AGENCY_NOUN.get(agency, (agency, agency))
        parts.append(("a " if n == 1 else f"{n} ") + (one if n == 1 else many))
    return " and ".join(parts)


def _shortfall_words(rf: Mapping[str, Any]) -> str:
    """What is actually short, from the COA's own ``required_resources`` and ``availability`` — never a blanket
    claim: ``"a patrol is free, but no 108 ambulance is free"``, ``"none of them is free this cycle"``, ``"only 1
    of the 2 police units it needs is free"``, or that the unit feed is down (then nothing is counted as free)."""
    if any(FEED_UNAVAILABLE in s for s in rf.get("shortfalls") or ()):
        return "the unit feed is unavailable, so no unit is counted as free"
    required = rf.get("required_resources") or {}
    free = rf.get("availability") or {}
    short: list[str] = []
    covered: list[str] = []
    for agency, n in sorted(required.items()):
        have = int(free.get(agency) or 0)
        one, many = AGENCY_NOUN.get(agency, (agency, agency))
        if n <= have:
            covered.append(("a %s is free" % one) if n == 1 else ("%d %s are free" % (n, many)))
        elif have == 0:
            short.append(("no %s is free" % one) if n == 1 else ("no %s are free" % many))
        else:
            short.append("only %d of the %d %s it needs %s free" % (have, n, many, "is" if have == 1 else "are"))
    if not short:  # the shortfall is not a unit count (never reached for a unit-blocked COA)
        return "its units are not all free this cycle"
    if covered:
        return "%s, but %s" % (" and ".join(covered), " and ".join(short))
    if len(short) > 1 and all(int(free.get(a) or 0) == 0 for a in required):
        return "none of them is free this cycle"
    return " and ".join(short) + " this cycle"


def floor_stake(credibility: float) -> str:
    """Why the floor applies, in one clause with the numbers it acted on (the engine's scoring note uses it too)."""
    return (
        "people are reported hurt or public safety is at stake, and credibility %.2f is at or above the %.2f "
        "act-on-it threshold" % (credibility, VERIFY_BELOW)
    )


def _flag_handling(
    flag: Mapping[str, Any],
    *,
    twin: bool,
    closures_excluded: Sequence[int],
    closures_on_alternatives: Sequence[int],
    affected: set[int] | frozenset[int] = frozenset(),
) -> str:
    """What the wargame actually did with one second-order flag (``affected``: every segment some COA's cascade
    affects — a live 108 route adds delay only there)."""
    kind = flag.get("kind")
    seg = flag.get("segment_id")
    if twin and kind == "ambulance_route" and seg:
        if int(seg) in affected:
            return "fed to the cascade's 108 delay"
        return "fed to the cascade's 108 delay (no COA's cascade reaches its road, so it adds none)"
    if twin and kind == "closure" and seg and int(seg) in {int(s) for s in closures_excluded}:
        if int(seg) in {int(s) for s in closures_on_alternatives}:
            return "kept out of the cascade's reassignment (it lies on an alternative the reassignment would use)"
        return "kept out of the cascade's reassignment (on none of its alternatives, so no effect)"
    return "listed, not modelled"


def build_dissent(
    *,
    situation: Mapping[str, Any],
    subject_kind: str,
    coas: Sequence[Mapping[str, Any]],
    scored_ids: Sequence[str],
    closeness: Mapping[str, float],
    ranked_ids: Sequence[str],
    matrix: Sequence[Sequence[float]],
    weights: Sequence[float],
    keep: Sequence[str],
    stability: float,
    margin: float,
    voi: Mapping[str, Any],
    voi_at: Callable[[float], Mapping[str, Any]],
    strategy_prior: Mapping[str, Any] | None,
    second_order: Sequence[Mapping[str, Any]] = (),
    context: Sequence[Mapping[str, Any]] = (),
    subject: Mapping[str, Any] | None = None,
    wargame_method: str = "surrogate",
    closures_excluded: Sequence[int] = (),
    closures_on_alternatives: Sequence[int] = (),
    notional: bool = False,
    best_blocked: str | None = None,
    held_baseline: str | None = None,
    floor_mode: str = "none",
    area_note: str | None = None,
) -> str:
    """The dissent paragraph (≤ 4000 characters).  ``subject`` says where a corridor event came from,
    ``wargame_method``, ``closures_excluded`` and ``closures_on_alternatives`` what the wargame did with the
    second-order flags, and ``notional`` that the wargame ran on a notional arterial (an area-level report has no
    road).  ``best_blocked`` names the resource-blocked best response, ``held_baseline`` the do-nothing baseline
    the public-safety floor holds down, and ``floor_mode`` the floor's mode (``mcda.public_safety_floor``).
    ``area_note`` says why the framing dropped the report's road anchor (OSINT-3: an area, or a far snap)."""
    by_id = {c["coa_id"]: c for c in coas}
    wmap = dict(zip(CRITERION_IDS, weights, strict=True))
    top_id = ranked_ids[0]
    top = by_id[top_id]
    cred = float(situation.get("credibility") or 0.0)
    parts: list[str] = []
    runner_id = next((i for i in ranked_ids[1:] if i in closeness), None)
    # the COA the pick competes with on score (mcda.rank_coas's ``rival``): the runner-up — unless it is a
    # baseline the floor holds down.  The floor ranks every feasible response above the held baseline, so the
    # baseline is the runner-up only when no other feasible response exists: then nothing competes on score and
    # the margin is 0.0, never the negative gap to the held baseline's closeness.
    held_runner = runner_id is not None and runner_id == held_baseline
    rival_id = None if held_runner else runner_id
    if held_runner:
        run = by_id[runner_id]
        parts.append(
            "Runner-up is %s (%s, closeness %.3f vs %.3f): it scores closer to the ideal than the pick, but the "
            "public-safety floor (stated in the scoring note) holds a do-nothing baseline below every feasible "
            "response course of action — an ordering rule, not a scoring gap: no other feasible response competes "
            "with the pick this cycle, so no closeness gap is claimed (margin %.3f); %.0f%% rank stability under "
            "weight perturbation."
            % (runner_id, run["label"], closeness[runner_id], closeness[top_id], margin, stability * 100)
        )
    elif runner_id is not None:
        run = by_id[runner_id]
        beats = _beats_clause(_beats(top["attributes"], run["attributes"], keep, wmap))
        parts.append(
            "Runner-up is %s (%s, closeness %.3f vs %.3f): %s; the gap is %.3f with %.0f%% rank stability under "
            "weight perturbation."
            % (runner_id, run["label"], closeness[runner_id], closeness[top_id], beats, margin, stability * 100)
        )
    else:
        parts.append("There is no runner-up: every other course of action is vetoed.")

    # FIX-C: the best response is blocked on resources — named with what is missing and the plain-language
    # action, never buried behind a do-nothing recommendation.  A COA blocked only because an area-level report
    # has no road is not a resourcing question; the no-road-anchor clause below speaks for it.
    if best_blocked is not None:
        b = by_id[best_blocked]
        rf = b["resource_feasibility"]
        higher = [i for i in closeness if i != best_blocked and closeness[i] > closeness[best_blocked]]
        lead = ("the highest-scoring course of action" if not higher
                else "the highest-scoring course of action that more units would unblock")
        parts.append(
            "Best blocked: %s %s (%s, closeness %.3f vs the pick's %.3f) cannot be resourced this cycle — the "
            "best response needs %s; %s — request units (%s)."
            % (lead, best_blocked, b["label"], closeness[best_blocked], closeness[top_id],
               _need_words(rf["required_resources"]), _shortfall_words(rf), "; ".join(_unit_shortfalls(b)))
        )
    if floor_mode == "hold" and held_baseline is not None and held_baseline != runner_id:
        parts.append(
            "The public-safety floor holds the do-nothing baseline (%s, closeness %.3f) below every feasible "
            "response course of action (%s); its closeness is unchanged and still shown — the order is the "
            "floor's, not TOPSIS's."
            % (held_baseline, closeness[held_baseline], floor_stake(cred))
        )
    if floor_mode == "verify":
        info = next((c for c in coas if c["kind"] == "information"), None)
        extra = ""
        if info is not None and not info["resource_feasibility"]["feasible"]:
            extra = (" The information COA cannot be resourced this cycle (%s) — request units."
                     % "; ".join(_unit_shortfalls(info)))
        parts.append(
            "Verify first: people are reported hurt or public safety is at stake, but credibility %.2f is below "
            "the %.2f act-on-it threshold, so the report may not be real and the baseline is not held down — %s "
            "confirms or dismisses the report before any response.%s"
            % (cred, VERIFY_BELOW, ("the information COA %s" % info["coa_id"]) if info
               else "no information COA exists", extra)
        )

    flips: list[str] = []
    holds: list[str] = []
    anchor_blocked: list[str] = []
    # more units: an infeasible (unvetoed) COA that would win once resourced.  A COA blocked because the report
    # has no road is not a resourcing question (more units cannot supply a road anchor): it is said apart.
    for cid in scored_ids:
        c = by_id[cid]
        rf = c["resource_feasibility"]
        if rf["feasible"]:
            continue
        if _anchor_blocked(c):
            anchor_blocked.append(cid)
            continue
        need = "; ".join(rf["shortfalls"])
        if closeness[cid] > closeness[top_id]:
            flips.append("resourcing %s (%s) would make it the pick (closeness %.3f > %.3f)"
                         % (cid, need, closeness[cid], closeness[top_id]))
        else:
            holds.append("resourcing %s (%s) would not (%.3f < %.3f)" % (cid, need, closeness[cid],
                                                                          closeness[top_id]))
    # a reweighting toward the runner-up's strengths — never toward a baseline the floor holds down (no weight can
    # put it first), nor toward an infeasible runner-up (it ranks after every feasible COA: "more units" speaks)
    if held_runner:
        holds.append("no reweighting puts %s first (the public-safety floor is non-compensatory)" % runner_id)
    if (rival_id is not None and rival_id in scored_ids
            and by_id[rival_id]["resource_feasibility"]["feasible"]):
        idx = {cid: i for i, cid in enumerate(scored_ids)}
        cand = _beats(by_id[rival_id]["attributes"], top["attributes"], keep, wmap)
        flip = _weight_flip(matrix, weights, idx[top_id], idx[rival_id], cand) if cand else None
        if flip is not None:
            flips.append("raising the weight on '%s' %.4gx would put %s first" % (flip[0], flip[1], rival_id))
        elif cand:
            holds.append("no single reweighting up to 8x of %s puts %s first" % (", ".join(cand[:3]), rival_id))
        else:
            holds.append("%s is dominated on every discriminating criterion, so no reweighting flips it"
                         % rival_id)
    # an official source: for a reported situation, or a corridor event promoted from one
    reported = subject_kind == "osint_event" or (subject or {}).get("origin") == "osint"
    if reported and situation.get("verification_state") not in ("OFFICIAL-VERIFIED", "CONFIRMED"):
        official = voi_at(OFFICIAL_CREDIBILITY)
        if bool(official["advise_gather"]) != bool(voi["advise_gather"]):
            flips.append("an OFFICIAL source (police or ICCC confirmation, credibility %.2f) would %s"
                         % (OFFICIAL_CREDIBILITY, "advise verifying first" if official["advise_gather"]
                            else "remove the advice to verify first"))
        else:
            holds.append("an OFFICIAL source (credibility %.2f) would not change the advice (EVOI %.3f)"
                         % (OFFICIAL_CREDIBILITY, float(official["evoi"])))
    band = _advise_band(voi_at) if voi.get("info_coa_id") is not None else None
    if flips:
        parts.append("It would FLIP if " + "; or if ".join(flips) + ".")
    else:
        parts.append("No single change examined flips it.")
    if holds:
        parts.append("Not enough on its own: " + "; ".join(holds) + ".")
    if area_note:
        parts.append(area_note)
    if anchor_blocked:
        scores = ", ".join("%s %.3f" % (cid, closeness[cid]) for cid in anchor_blocked)
        also = ["%s would then also need %s" % (cid, "; ".join(_unit_shortfalls(by_id[cid])))
                for cid in anchor_blocked if _unit_shortfalls(by_id[cid])]
        parts.append(
            "No road anchor: %s cannot be approved until the report has a road-level location (a segment or a "
            "junction) — more units cannot supply one; regenerate once it is located on a road (%s closeness "
            "here, %s against the pick's %.3f, is %s and decides nothing about that road)%s."
            % (" and ".join(anchor_blocked), "its" if len(anchor_blocked) == 1 else "their", scores,
               closeness[top_id], "on a notional arterial" if notional else "without a road",
               ("; " + "; ".join(also)) if also else "")
        )
    if band is not None:
        lo, hi = band
        inside = lo <= cred <= hi
        parts.append(
            "The advice to verify first holds for a credibility between %.2f and %.2f (now %.2f, so the engine %s)."
            % (lo, hi, cred, "advises verifying first" if inside else "advises acting now")
        )
    parts.append(corroboration_sentence(situation, subject_kind=subject_kind, subject=subject))
    ctx = context_sentence(context)
    if ctx is not None:
        parts.append(ctx)

    infeasible = [by_id[c] for c in ranked_ids if not by_id[c]["resource_feasibility"]["feasible"]]
    spill = {c["coa_id"]: c["predicted_outcome"]["cascade"]["spillover_vehicle_hours"]["mean"] for c in coas}
    largest = max(spill, key=lambda k: spill[k]) if spill else None
    for c in infeasible:
        if c["kind"] != "aggressive":
            continue
        shortfalls = "; ".join(c["resource_feasibility"]["shortfalls"])
        if _anchor_blocked(c):
            label = "INFEASIBLE (%s)" % shortfalls
        else:
            label = "RESOURCE-INFEASIBLE this cycle (%s)" % shortfalls
        note = (
            "The more aggressive full-closure COA (%s) is %s and is ranked last and labelled, not hidden"
            % (c["coa_id"], label)
        )
        effects = []
        delay = float(c["predicted_outcome"]["emergency_impact"]["ambulance_delay_sec"])
        if delay > 0:
            effects.append("it would delay the 108 to the scene (%+d s)" % round(delay))
        if largest == c["coa_id"] and spill[largest] > 0:
            effects.append("cast the largest cascade (%.0f veh·h spillover)" % spill[largest])
        if effects:
            where = ", run on a notional arterial (the report has no road)," if notional else ""
            note += "; the wargame%s separately shows %s" % (where, " and ".join(effects))
        parts.append(note + ".")
    if second_order:
        twin = wargame_method == "twin+cascade"
        affected = {int(s) for c in coas for s in c["predicted_outcome"]["cascade"]["affected_segment_ids"]}
        flags = "; ".join(
            "%s %s%s — %s" % (str(f.get("kind", "")).replace("_", " "), f.get("urn"),
                              " (segment %s)" % f["segment_id"] if f.get("segment_id") else "",
                              _flag_handling(f, twin=twin, closures_excluded=closures_excluded,
                                             closures_on_alternatives=closures_on_alternatives, affected=affected))
            for f in list(second_order)[:6]
        )
        tail = "" if twin else " (the surrogate wargame models none of these flags)"
        parts.append("Second-order flags on live corridor state: %s%s." % (flags, tail))
        excluded = {int(s) for s in closures_excluded} if twin else set()
        effective = {int(s) for s in closures_on_alternatives} & excluded
        closures = [f for f in second_order if f.get("kind") == "closure"]
        kept_off = [f for f in closures if f.get("segment_id") and int(f["segment_id"]) in excluded]
        matters = [f for f in kept_off if int(f["segment_id"]) in effective]
        unmodelled = [f for f in closures if f not in kept_off]
        if matters:
            one = len(matters[:3]) == 1
            parts.append(
                "A cleared closure would change the reassignment: %s %s on an alternative road the reassignment "
                "would otherwise use, and %s kept out of it; once it clears, regenerate — the pick may change (the "
                "engine does not assume it clears)." % (
                    ", ".join("%s (segment %s)" % (f.get("urn"), f["segment_id"]) for f in matters[:3]),
                    "lies" if one else "lie", "is" if one else "are")
            )
        if unmodelled:
            parts.append(
                "A live closure (%s) is flagged but not modelled by the %s; regenerate once it clears."
                % (", ".join(str(f.get("urn")) for f in unmodelled[:3]),
                   "cascade" if twin else "surrogate wargame")
            )
    if strategy_prior:
        kind = strategy_prior.get("kind")
        conf = strategy_prior.get("confidence")
        conf_s = "confidence %.2f" % conf if isinstance(conf, (int, float)) else "no confidence"
        if kind != top["kind"]:
            match = next((c for c in coas if c["kind"] == kind), None)
            where = ("ranked #%d" % match["score"]["rank"]) if match else "not in this COA set"
            parts.append(
                "Sajag AI's strategy prior (%s) favours the %s response (p %.2f, %s); the MCDA has it %s. The prior "
                "is recorded, it does not change the scoring." % (strategy_prior.get("tier"), kind,
                                                                    float(strategy_prior.get("probability", 0)),
                                                                    conf_s, where)
            )
        else:
            parts.append("Sajag AI's strategy prior (%s) agrees: %s (p %.2f, %s)."
                         % (strategy_prior.get("tier"), kind, float(strategy_prior.get("probability", 0)), conf_s))
    text = " ".join(parts)
    return text[:4000]
