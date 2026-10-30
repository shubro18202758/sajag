"""Signal-timing proposals, each tested in the twin against "do nothing".

Candidates for a junction (or corridor) under stress:

* **extend green** for a movement by N s for M minutes (taken from the
  other phase, cycle and offset unchanged, no phase below the minimum);
* **green wave**: re-offset the signals along a corridor for a platoon at a
  progression speed, for M minutes;
* **max-pressure**: switch the junction(s) to max-pressure control for M
  minutes;
* **Webster re-time**: run the junction on Webster's cycle and split
  (computed from the twin's flows) for M minutes; this one changes the
  cycle, so coordination with neighbours is not kept and the summary says so.

All candidates run in one batched twin run from the same warmed-up state
with the same demand, over the whole network, so a change that only moves
the queue to a neighbouring junction shows up in the network delay.

Ranking (``rank``):

1. *Guards* — a candidate is eligible only if it cuts delay at the focus
   by at least ``MIN_GAIN_PCT`` (3 %), does not raise network delay, does
   not raise cross-street delay by more than the tolerance (default 25 %),
   and does not add spill-back anywhere in the network.
2. *Score* — among eligible candidates: weighted reductions in focus
   delay (0.45), network delay (0.35) and max queue (0.20).

The best eligible candidate becomes a proposal object. It is never an
action: ``verification_state`` is MODELLED and it ``requires`` a named
officer's approval; if no officer decides, the current plan holds.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

import numpy as np

from sajag_twin import params as P
from sajag_twin.metrics import Focus, compare, series_for
from sajag_twin.network import Network, NetworkError, Program
from sajag_twin.signals import Plan, Window, extend_green, green_wave_offsets
from sajag_twin.twin import Scenario, Twin

__all__ = ["Candidate", "build_candidates", "corridor_path", "make_proposal", "rank", "run_proposals"]

MOVEMENT_EN = {"through": "main-road (through)", "cross": "cross-street"}
MOVEMENT_MR = {"through": "मुख्य रस्त्याच्या", "cross": "आडव्या रस्त्याच्या"}

W_FOCUS, W_NET, W_QUEUE = 0.45, 0.35, 0.20


@dataclass
class Candidate:
    plan: Plan
    kind: str
    junction_ids: list[int]
    duration_min: float
    movement: str | None = None
    green_delta_s: int = 0
    speed_kmh: float | None = None
    programs: dict[int, Program] = field(default_factory=dict)
    summary_en: str = ""
    summary_mr: str = ""


# ---------------------------------------------------------------------------
# Corridors
# ---------------------------------------------------------------------------


def corridor_path(net: Network, segment_ids: list[int] | None = None, junction_ids: list[int] | None = None) -> tuple[list[int], list[int]]:
    """(junctions in travel order, directed links) of a corridor.

    From a list of segment ids (a legal directed path, as the platform's
    route spines are) or from a list of junction ids (consecutive ones
    must be joined by a link).
    """
    if segment_ids:
        segs = [int(s) for s in segment_ids]
        # orient: try each direction of the first segment and follow
        for first in net.links_of_segment(segs[0]):
            path_links = [first]
            ok = True
            for sid in segs[1:]:
                at = net.links[path_links[-1]].to_j
                nxt = [li for li in net.links_of_segment(sid) if net.links[li].from_j == at]
                if not nxt:
                    ok = False
                    break
                path_links.append(nxt[0])
            if ok:
                js = [net.links[path_links[0]].from_j] + [net.links[li].to_j for li in path_links]
                return js, path_links
        raise NetworkError("segment_ids are not a connected directed path on the network")
    if junction_ids and len(junction_ids) >= 2:
        links = []
        for a, b in zip(junction_ids, junction_ids[1:]):
            li = net.link_between(a, b)
            if li is None:
                raise NetworkError(f"no link from junction {a} to {b}")
            links.append(li)
        return list(junction_ids), links
    raise NetworkError("a corridor needs segment_ids or at least two junction_ids")


# ---------------------------------------------------------------------------
# Candidates
# ---------------------------------------------------------------------------


def corridor_names(net: Network, js: list[int], links: list[int]) -> tuple[str, str]:
    """(English, Marathi) names of a corridor: its roads, and its end junctions."""
    roads: list[str] = []
    for li in links:
        n = net.links[li].road_name
        if n not in roads:
            roads.append(n)
    a, b = net.junctions[js[0]], net.junctions[js[-1]]
    en = f"{' / '.join(roads[:3])} ({a.name} to {b.name})"
    mr = f"{a.name_mr or a.name} ते {b.name_mr or b.name}"
    return en, mr


def _durations(horizon_min: float) -> list[float]:
    out = sorted({min(horizon_min, 20.0), min(horizon_min, 30.0)})
    return [d for d in out if d >= 5.0] or [horizon_min]


def _jname(net: Network, jid: int) -> tuple[str, str]:
    j = net.junctions[jid]
    return j.name, (j.name_mr or j.name)


def _extend_candidate(net: Network, jid: int, label: str, n: int, m: float) -> Candidate | None:
    j = net.junctions[jid]
    if j.program is None:
        return None
    new = extend_green(j.program, label, n)
    if new is None:
        return None
    gained = new.green_of(label) - j.program.green_of(label)
    if gained <= 0:
        return None
    other = "cross" if label == "through" else "through"
    name, name_mr = _jname(net, jid)
    plan = Plan(f"extend {label} +{gained}s {int(m)}min @J{jid}", [Window(jid, 0.0, m * 60.0, "fixed", new)], "extend_green")
    c = Candidate(plan, "extend_green", [jid], m, movement=label, green_delta_s=gained, programs={jid: new})
    c.summary_en = (
        f"Give the {MOVEMENT_EN.get(label, label)} movement at {name} {gained} s more green for {int(m)} min "
        f"(taken from the {MOVEMENT_EN.get(other, other)} movement; cycle {new.cycle_sec} s unchanged)."
    )
    c.summary_mr = (
        f"{name_mr} येथे {MOVEMENT_MR.get(label, label)} सिग्नलला {int(m)} मिनिटांसाठी {gained} सेकंद अधिक हिरवा "
        f"({MOVEMENT_MR.get(other, other)} वेळेतून घेतलेला; चक्र {new.cycle_sec} सेकंद, न बदलता)।"
    )
    plan.description = c.summary_en
    return c


def _mp_candidate(net: Network, jids: list[int], m: float) -> Candidate:
    names = ", ".join(_jname(net, j)[0] for j in jids)
    names_mr = ", ".join(_jname(net, j)[1] for j in jids)
    plan = Plan(f"max-pressure {int(m)}min @{','.join(f'J{j}' for j in jids)}", [Window(j, 0.0, m * 60.0, "max_pressure") for j in jids], "max_pressure")
    c = Candidate(plan, "max_pressure", list(jids), m)
    c.summary_en = (
        f"Switch {names} to max-pressure control for {int(m)} min: each cycle the green split follows the queues "
        f"(cycle, phase order and offset unchanged; minimum green {P.MIN_GREEN_S} s)."
    )
    c.summary_mr = (
        f"{names_mr} येथे {int(m)} मिनिटांसाठी मॅक्स-प्रेशर नियंत्रण: प्रत्येक चक्रात रांगेच्या लांबीनुसार हिरव्याची विभागणी "
        f"(चक्र, फेजचा क्रम आणि ऑफसेट तेच; किमान हिरवा {P.MIN_GREEN_S} सेकंद)।"
    )
    plan.description = c.summary_en
    return c


def _webster_candidate(net: Network, jid: int, prog: Program, m: float) -> Candidate:
    j = net.junctions[jid]
    cur = j.program
    name, name_mr = _jname(net, jid)
    greens = "/".join(str(g) for g, _ in prog.phases)
    cur_greens = "/".join(str(g) for g, _ in cur.phases)  # type: ignore[union-attr]
    plan = Plan(f"Webster {prog.cycle_sec}s {int(m)}min @J{jid}", [Window(jid, 0.0, m * 60.0, "fixed", prog)], "webster_retime")
    c = Candidate(plan, "webster_retime", [jid], m, programs={jid: prog})
    c.summary_en = (
        f"Re-time {name} to Webster's cycle and split for {int(m)} min: cycle {cur.cycle_sec} s to {prog.cycle_sec} s, "  # type: ignore[union-attr]
        f"greens {cur_greens} s to {greens} s (the offset is kept but coordination with neighbouring signals is not)."
    )
    c.summary_mr = (
        f"{name_mr} येथे {int(m)} मिनिटांसाठी वेबस्टर पद्धतीने वेळ बदल: चक्र {cur.cycle_sec} वरून {prog.cycle_sec} सेकंद, "  # type: ignore[union-attr]
        f"हिरवा {cur_greens} वरून {greens} सेकंद (ऑफसेट तोच, पण शेजारच्या सिग्नलशी समन्वय राहणार नाही)।"
    )
    plan.description = c.summary_en
    return c


def stressed_movements(twin: Twin, sc: Scenario, junction_ids: list[int]) -> dict[int, list[str]]:
    """Per junction: its movement labels, most delayed first (a do-nothing run)."""
    res = twin.run(sc, [Plan("do nothing")])
    out: dict[int, list[str]] = {}
    for jid in junction_ids:
        j = twin.net.junctions[jid]
        if j.program is None:
            continue
        delay = {lab: 0.0 for lab in j.program.labels}
        for li, lab in j.approach_label.items():
            delay[lab] = delay.get(lab, 0.0) + float(res.link_delay_vs[0, li])
        for x in range(twin.cp.X):
            if int(twin.cp.vx_junction[x]) == jid:
                delay["cross"] = delay.get("cross", 0.0) + float(res.vx_delay_vs[0, x])
        out[jid] = sorted(delay, key=lambda k: (-delay[k], k))
    return out


def build_candidates(
    twin: Twin,
    sc: Scenario,
    *,
    junction_ids: list[int],
    corridor: tuple[list[int], list[int]] | None,
    horizon_min: float,
    max_candidates: int = 24,
) -> list[Candidate]:
    net = twin.net
    out: list[Candidate] = []
    durs = _durations(horizon_min)
    stress = stressed_movements(twin, sc, junction_ids) if junction_ids else {}
    for jid in junction_ids:
        j = net.junctions[jid]
        if not j.signalised:
            continue
        labels = stress.get(jid, [])
        if not labels:
            continue
        stressed = labels[0]
        for n in (6, 10, 15, 20):
            for m in durs:
                c = _extend_candidate(net, jid, stressed, n, m)
                if c:
                    out.append(c)
        for other in labels[1:]:
            for n in (6, 10):
                c = _extend_candidate(net, jid, other, n, durs[0])
                if c:
                    out.append(c)
        for m in durs:
            out.append(_mp_candidate(net, [jid], m))
        wb = twin.webster_for(sc.demand, jid)
        if [g for g, _ in wb.program.phases] != [g for g, _ in j.program.phases] or wb.program.cycle_sec != j.program.cycle_sec:
            for m in durs:
                out.append(_webster_candidate(net, jid, wb.program, m))
    if corridor is not None:
        js, links = corridor
        sig = [j for j in js if net.junctions[j].signalised]
        if len(sig) >= 2:
            programs = {j: net.junctions[j].program for j in sig}
            vf = float(np.mean([net.links[li].vf_kmh for li in links]))
            road, road_mr = corridor_names(net, js, links)
            for frac in (0.7, 0.85):
                speed = round(vf * frac)
                offs = green_wave_offsets(net, js, programs, speed)  # type: ignore[arg-type]
                if not offs:
                    continue
                for m in durs[-1:]:
                    plan = Plan(
                        f"green wave {speed} km/h {int(m)}min",
                        [Window(j, 0.0, m * 60.0, "fixed", p) for j, p in offs.items()],
                        "green_wave",
                    )
                    c = Candidate(plan, "green_wave", sig, m, speed_kmh=speed, programs=offs)
                    c.summary_en = (
                        f"Re-offset {len(sig)} signals along {road} for a green wave at {speed} km/h for {int(m)} min "
                        "(greens unchanged; offsets only)."
                    )
                    c.summary_mr = (
                        f"{road_mr} मार्गावर {len(sig)} सिग्नलचे ऑफसेट बदलून {speed} किमी/तास वेगाची ग्रीन वेव्ह, "
                        f"{int(m)} मिनिटांसाठी (हिरव्याची वेळ तीच; फक्त ऑफसेट)।"
                    )
                    plan.description = c.summary_en
                    out.append(c)
            if not junction_ids:
                # the corridor's own movement, at every signal on it
                for n in (6, 10):
                    windows, progs = [], {}
                    for a, j in zip(links, js[1:]):
                        if j not in sig:
                            continue
                        lab = net.junctions[j].approach_label.get(a, "through")
                        newp = extend_green(net.junctions[j].program, lab, n)  # type: ignore[arg-type]
                        if newp:
                            windows.append(Window(j, 0.0, durs[-1] * 60.0, "fixed", newp))
                            progs[j] = newp
                    if windows:
                        plan = Plan(f"corridor +{n}s", windows, "extend_green")
                        c = Candidate(plan, "extend_green", sorted(progs), durs[-1], movement="corridor", green_delta_s=n, programs=progs)
                        c.summary_en = (
                            f"Give the corridor movement {n} s more green at {len(progs)} signals along {road} for {int(durs[-1])} min "
                            "(taken from the cross movement; cycles unchanged)."
                        )
                        c.summary_mr = (
                            f"{road_mr} मार्गावर {len(progs)} सिग्नलवर कॉरिडॉरच्या दिशेला {int(durs[-1])} मिनिटांसाठी {n} सेकंद अधिक हिरवा "
                            "(आडव्या रस्त्याच्या वेळेतून घेतलेला; चक्र तेच)।"
                        )
                        plan.description = c.summary_en
                        out.append(c)
                out.append(_mp_candidate(net, sig, durs[-1]))
    # keep the list bounded: drop the largest green changes first
    if len(out) > max_candidates:
        out.sort(key=lambda c: (c.green_delta_s, -c.duration_min))
        out = out[:max_candidates]
    return out


# ---------------------------------------------------------------------------
# Ranking
# ---------------------------------------------------------------------------


def eligibility(delta: dict, cross_tol_pct: float) -> list[str]:
    """Reasons a candidate is NOT eligible (empty = eligible)."""
    why = []
    if delta["network_delay_change_pct"] > 0.0:
        why.append("raises network delay (would move the jam)")
    if delta["cross_street_delay_change_pct"] > cross_tol_pct:
        why.append(f"raises cross-street delay by more than {cross_tol_pct:.0f}%")
    if delta["network_spillback_change_min"] > 0.5:
        why.append("adds spill-back in the network")
    if delta["delay_change_pct"] > -P.MIN_GAIN_PCT:
        why.append(f"reduces delay at the focus by less than {P.MIN_GAIN_PCT:.0f}% (not worth a change)")
    return why


def score(delta: dict) -> float:
    return -(W_FOCUS * delta["delay_change_pct"] + W_NET * delta["network_delay_change_pct"] + W_QUEUE * delta["max_queue_change_pct"])


def rank(deltas: list[dict], cross_tol_pct: float) -> list[tuple[int, float, list[str]]]:
    """[(candidate index, score, ineligibility reasons)], best first."""
    rows = [(i, score(d), eligibility(d, cross_tol_pct)) for i, d in enumerate(deltas)]
    rows.sort(key=lambda r: (bool(r[2]), -r[1], r[0]))
    return rows


# ---------------------------------------------------------------------------
# Confidence (a modelled heuristic, not a probability)
# ---------------------------------------------------------------------------

_SOURCE_FACTOR = {"LIVE": 1.0, "EMULATED": 0.85, "SIMULATED": 0.7}


def confidence(twin: Twin, sc: Scenario, cand: Candidate, base_plan: Plan, focus: Focus) -> dict:
    """Does the gain hold if demand is 10% lower or higher?"""
    scales = [0.9, 1.1]
    plans = [base_plan, cand.plan] * len(scales)
    dscale = np.repeat(np.array(scales), 2)
    res = twin.run(sc, plans, demand_scale=dscale)
    mets = twin.metrics(res, focus)
    holds = 1  # the nominal run already passed the guards
    detail = [{"demand_scale": 1.0, "holds": True}]
    for i, s in enumerate(scales):
        d = compare(mets[2 * i + 1], mets[2 * i])
        ok = d["delay_change_pct"] < 0 and d["network_delay_change_pct"] <= 0.0
        holds += int(ok)
        detail.append({"demand_scale": s, "holds": ok, "delay_change_pct": d["delay_change_pct"],
                       "network_delay_change_pct": d["network_delay_change_pct"]})
    robust = holds / (len(scales) + 1)
    src = _SOURCE_FACTOR.get(sc.demand.label, 0.7)
    ctrl = min(1.0 if twin.net.junctions[j].control == "programmed" else 0.8 for j in cand.junction_ids)
    value = round(robust * src * ctrl, 2)
    level = "high" if value >= 0.75 else ("medium" if value >= 0.45 else "low")
    return {
        "score": value,
        "level": level,
        "basis": [
            f"gain holds in {holds} of {len(scales) + 1} demand levels (90%, 100%, 110%)",
            f"demand source {sc.demand.label} (factor {src})",
            "baseline timings from the network's MODELLED program" if ctrl == 1.0
            else "baseline timings are a twin-assumed template (factor 0.8)",
        ],
        "sensitivity": detail,
        "note": "A modelled heuristic for how robust the twin result is, not a probability.",
    }


# ---------------------------------------------------------------------------
# Proposal object
# ---------------------------------------------------------------------------


def make_proposal(
    twin: Twin,
    sc: Scenario,
    cand: Candidate,
    delta: dict,
    cand_metrics: dict,
    base_metrics: dict,
    conf: dict,
    horizon_min: float,
) -> dict:
    net = twin.net
    pid_src = json.dumps(
        {"p": {str(k): v.to_dict() for k, v in cand.programs.items()}, "k": cand.kind, "j": cand.junction_ids,
         "m": cand.duration_min, "t": sc.demand.start.isoformat()},
        sort_keys=True,
    )
    pid = "twin-" + hashlib.sha1(pid_src.encode()).hexdigest()[:12]
    juncs = [
        {"junction_id": j, "key": net.junctions[j].key, "name": net.junctions[j].name, "name_mr": net.junctions[j].name_mr,
         "control": net.junctions[j].control}
        for j in cand.junction_ids
    ]
    change: dict = {
        "kind": cand.kind,
        "summary": cand.summary_en,
        "summary_mr": cand.summary_mr,
        "movement": cand.movement,
        "green_delta_s": cand.green_delta_s or None,
        "speed_kmh": cand.speed_kmh,
        "programs": {str(j): p.to_dict() for j, p in cand.programs.items()},
        "revert_to": {str(j): net.junctions[j].program.to_dict() for j in cand.junction_ids if net.junctions[j].program},  # type: ignore[union-attr]
    }
    if cand.kind == "max_pressure":
        change["controller"] = {
            "form": "cyclic max-pressure (Varaiya 2013; Le et al. 2015)",
            "split_rule": "each cycle, usable green in proportion to phase pressure",
            "min_green_s": P.MIN_GREEN_S,
            "cycle_offset_lost_time": "unchanged from the current program",
        }
    return {
        "proposal_id": pid,
        "kind": cand.kind,
        "junction_ids": cand.junction_ids,
        "junctions": juncs,
        "targets": [f"junction:{j}" for j in cand.junction_ids],
        "change": change,
        "duration_min": cand.duration_min,
        "twin_metrics": {
            "horizon_min": horizon_min,
            **delta,
            "do_nothing": {k: v for k, v in base_metrics.items() if k != "approaches"},
            "with_change": {k: v for k, v in cand_metrics.items() if k != "approaches"},
            "approaches": {"do_nothing": base_metrics["approaches"], "with_change": cand_metrics["approaches"]},
        },
        "confidence": conf,
        "assumptions": P.assumptions_doc() + sc.demand.notes,
        "demand": sc.demand.to_dict(),
        "verification_state": "MODELLED",
        "requires": "named officer approval",
        "requires_officer": True,
        "status": "PROPOSED",
        "actuation": "none: the twin never changes a signal; an approved plan goes through the platform's signal writer",
        "if_no_decision": "the current plan holds",
    }


def run_proposals(
    twin: Twin,
    sc: Scenario,
    *,
    junction_ids: list[int],
    corridor: tuple[list[int], list[int]] | None,
    horizon_min: float,
    cross_tol_pct: float = 25.0,
    max_candidates: int = 24,
    with_series: bool = True,
) -> dict:
    net = twin.net
    focus = Focus(junction_ids=list(junction_ids), corridor_links=list(corridor[1]) if corridor else [])
    base_plan = Plan("do nothing", [], "do_nothing", "Keep the current programs (do nothing).")
    cands = build_candidates(twin, sc, junction_ids=junction_ids, corridor=corridor, horizon_min=horizon_min, max_candidates=max_candidates)
    res = twin.run(sc, [base_plan] + [c.plan for c in cands])
    mets = twin.metrics(res, focus)
    base = mets[0]
    deltas = [compare(m, base) for m in mets[1:]]
    order = rank(deltas, cross_tol_pct)
    ranked = []
    for pos, (i, sc_val, why) in enumerate(order):
        c = cands[i]
        ranked.append({
            "rank": pos + 1,
            "name": c.plan.name,
            "kind": c.kind,
            "junction_ids": c.junction_ids,
            "summary": c.summary_en,
            "summary_mr": c.summary_mr,
            "duration_min": c.duration_min,
            "score": round(sc_val, 2),
            "eligible": not why,
            "not_eligible_because": why,
            **deltas[i],
        })
    top = None
    if order and not order[0][2]:
        i = order[0][0]
        conf = confidence(twin, sc, cands[i], base_plan, focus)
        top = make_proposal(twin, sc, cands[i], deltas[i], mets[i + 1], base, conf, horizon_min)
        if with_series:
            top["twin_metrics"]["series"] = {
                "do_nothing": series_for(twin.cp, res, 0, focus),
                "with_change": series_for(twin.cp, res, i + 1, focus),
            }
    return {
        "focus": {
            "junction_ids": junction_ids,
            "corridor_links": [net.links[li].link_id for li in focus.corridor_links],
        },
        "horizon_min": horizon_min,
        "do_nothing": base,
        "candidates_evaluated": len(cands),
        "ranked": ranked,
        "proposal": top,
        "recommendation": "propose" if top else "hold: no candidate beats do-nothing without moving the jam",
        "sim_elapsed_s": round(res.elapsed_s, 3),
    }
