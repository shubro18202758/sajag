"""Build the decider side-by-side request set from the brain's own builders.

SIMULATED: every scenario below is synthetic (Mumbai places from
cities/mumbai/landmarks.json, invented numbers). Nothing here is a real
event, a real movement or a real statistic.

The question sets and state documents come from convoy-brain itself:
  pre_movement        workflows.pre_movement._route_options/_route_questions/_route_state_doc
                      + DeciderBrain.build_state_doc(pre_movement=True)
  tool_selection      DeciderBrain.tool_selection_question(orchestrator._TOOL_MENU)
                      + the orchestrator's operator_chat state document
  dss_coa             dss.coa_generator.dss_questions + the strategy_prior state document
  escort_incident     the live-escort incident question set (INCIDENT_ACTIONS)
  escort_departure    the live-escort departure question set (DEPARTURE_ACTIONS)
  post_clearance      the restoration_posture question (RESTORATION_POSTURES)
  probe               the brain's health probe and the C1 smoke shape (described
                      options, a five-level scale)

Some requests carry an ``expected`` answer (a synthetic label, only where the
operator's request names the tool or the situation leaves one sensible
answer); they score accuracy, the rest score agreement only.

Run from the repo root with an interpreter that has convoy-brain's
dependencies (the gate interpreter, $GATE_PYTHON); convoy-brain/src is put
on sys.path here:
    "$GATE_PYTHON" services/embedding-service/eval/decider/build_requests.py
Writes requests.json next to this file.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BRAIN_SRC = HERE.parents[2] / "convoy-brain" / "src"
if str(BRAIN_SRC) not in sys.path:
    sys.path.insert(0, str(BRAIN_SRC))

from convoy_brain.decider import DeciderBrain  # noqa: E402
from convoy_brain.dss.coa_generator import _CONTEXT_KEYS, dss_questions  # noqa: E402
from convoy_brain.orchestrator import _TOOL_MENU  # noqa: E402
from convoy_brain.workflows.live_escort import DEPARTURE_ACTIONS, INCIDENT_ACTIONS  # noqa: E402
from convoy_brain.workflows.post_clearance import RESTORATION_POSTURES  # noqa: E402
from convoy_brain.workflows.pre_movement import (  # noqa: E402
    _route_options,
    _route_questions,
    _route_state_doc,
)

REQUESTS: list[dict] = []


def add(rid: str, kind: str, state: str, questions: dict, expected: dict | None = None) -> None:
    REQUESTS.append({
        "id": rid,
        "kind": kind,
        "label": "SIMULATED",
        "state": state,
        "questions": questions,
        "expected": expected or {},
    })


# ── 1. pre-movement route checkpoints ───────────────────────────────────────


def route(seg0: int, n: int, km: float, eta_min: float, score: float, tier: str,
          violations: int = 0) -> dict:
    return {
        "segment_ids": list(range(seg0, seg0 + n)),
        "distance_m": km * 1000,
        "estimated_time_sec": eta_min * 60,
        "weighted_score": score,
        "route_tier": tier,
        "lane_violations": [seg0 + i for i in range(violations)],
    }


PRE_MOVEMENT = [
    # (id, class, departure, corridor, routes)
    ("pm-mantralaya-airport-zplus", "Z+", "2026-11-02T08:30:00+05:30",
     {"overall_status": "amber", "observations": 212, "segments": 64},
     [route(5100, 41, 24.6, 38, 0.82, "compliant"), route(5300, 47, 27.9, 44, 0.74, "compliant"),
      route(5500, 39, 23.8, 41, 0.61, "conditional", 3)]),
    ("pm-mantralaya-airport-peak-red", "Z+", "2026-11-02T18:15:00+05:30",
     {"overall_status": "red", "observations": 230, "segments": 64},
     [route(5100, 41, 24.6, 71, 0.41, "conditional", 6), route(5300, 47, 27.9, 69, 0.38, "conditional", 4)]),
    ("pm-shivajipark-parade-z", "Z", "2027-01-26T07:00:00+05:30",
     {"overall_status": "green", "observations": 96, "segments": 22},
     [route(6100, 12, 5.4, 11, 0.91, "compliant"), route(6200, 15, 6.8, 14, 0.79, "compliant")]),
    ("pm-wankhede-match-y", "Y", "2026-11-08T21:40:00+05:30",
     {"overall_status": "red", "observations": 140, "segments": 30},
     [route(6300, 18, 7.2, 26, 0.55, "compliant"), route(6400, 21, 8.9, 24, 0.58, "compliant"),
      route(6500, 16, 6.6, 31, 0.44, "conditional", 2)]),
    ("pm-kem-hospital-x", "X", "2026-11-03T11:00:00+05:30",
     {"overall_status": "amber", "observations": 75, "segments": 18},
     [route(6600, 10, 4.1, 13, 0.77, "compliant"), route(6700, 13, 5.0, 12, 0.80, "conditional", 1)]),
    ("pm-bkc-summit-z", "Z", "2026-11-12T09:45:00+05:30",
     {"overall_status": "amber", "observations": 180, "segments": 40},
     [route(6800, 22, 13.2, 29, 0.73, "compliant"), route(6900, 25, 14.8, 27, 0.75, "compliant"),
      route(7000, 20, 12.9, 33, 0.66, "compliant"), route(7100, 28, 16.1, 35, 0.52, "conditional", 2)]),
    ("pm-csmt-transfer-y", "Y", "2026-11-05T06:20:00+05:30",
     {"overall_status": "green", "observations": 58, "segments": 26},
     [route(7200, 14, 6.3, 15, 0.86, "compliant"), route(7300, 17, 7.5, 18, 0.71, "compliant")]),
    ("pm-ganeshotsav-visarjan-zplus", "Z+", "2026-09-25T20:00:00+05:30",
     {"overall_status": "red", "observations": 260, "segments": 52},
     [route(7400, 30, 15.5, 52, 0.47, "compliant"), route(7500, 33, 17.0, 49, 0.49, "conditional", 5)]),
    ("pm-gateway-ceremony-z", "Z", "2026-12-16T08:00:00+05:30",
     {"overall_status": "green", "observations": 88, "segments": 20},
     [route(7600, 9, 3.8, 9, 0.92, "compliant"), route(7700, 11, 4.4, 10, 0.88, "compliant"),
      route(7800, 12, 4.9, 12, 0.81, "compliant")]),
    ("pm-brabourne-stadium-x-unknown", "X", "2026-11-20T16:30:00+05:30",
     {"overall_status": "unknown", "observations": 0, "segments": "n/a"},
     [route(7900, 19, 9.6, 22, 0.64, "compliant")]),
    ("pm-airport-mantralaya-night-zplus", "Z+", "2026-11-04T23:10:00+05:30",
     {"overall_status": "green", "observations": 120, "segments": 64},
     [route(5300, 47, 27.9, 33, 0.88, "compliant"), route(5100, 41, 24.6, 31, 0.86, "compliant")]),
    ("pm-high-tide-waterlogging-z", "Z", "2026-09-14T17:30:00+05:30",
     {"overall_status": "red", "observations": 150, "segments": 34},
     [route(8000, 20, 9.1, 47, 0.36, "conditional", 4), route(8100, 24, 11.3, 39, 0.43, "conditional", 2)]),
]

for rid, cls, dep, corridor, routes in PRE_MOVEMENT:
    options = _route_options(routes)
    summary = _route_state_doc(vvip_class=cls, planned_departure=dep, corridor=corridor, options=options)
    state = DeciderBrain.build_state_doc(
        trigger="pre_movement", summary=summary,
        context={"phase": "pre_movement", "vvip_class": cls}, pre_movement=True,
    )
    add(rid, "pre_movement", state, _route_questions(options))


# ── 2. operator chat tool selection ─────────────────────────────────────────

TOOL_CHAT = [
    ("tool-fly-sea-link", "Fly the map to the Bandra–Worli Sea Link.", [], "Z+", "canvas_fly_to"),
    ("tool-live-ambedkar-road", "What is the live traffic like on Dr Ambedkar Road near Dadar TT right now?",
     [], "none", "get_live_traffic"),
    ("tool-routes-mantralaya-airport",
     "Find convoy routes for the Z+ movement from Mantralaya to Mumbai Airport T2 that avoid the Sea Link.",
     [], "Z+", "find_convoy_routes"),
    ("tool-forecast-weh", "Predict the traffic flow on the Western Express Highway near Andheri for the next 30 minutes.",
     [], "none", "predict_traffic_flow"),
    ("tool-eta-marinedrive-wankhede", "What is the ETA for the convoy from Marine Drive to Wankhede Stadium?",
     [], "Z", "predict_eta"),
    ("tool-diversions-lalbaug",
     "Plan traffic diversions around Lalbaug for the visarjan crowd tonight.",
     [], "none", "plan_diversions"),
    ("tool-units-csmt", "Which units are available near CSMT?", [], "none", "list_units"),
    ("tool-signal-sion-circle", "Show me the signal state at Sion Circle.",
     [], "none", "get_signal_state"),
    ("tool-situation-log", "Summarise what happened in the last hour from the situation log.",
     [], "none", "get_situation_log"),
    ("tool-highlight-hindmata", "Highlight the waterlogged segments near Hindmata on the map.",
     [], "none", "canvas_highlight"),
    ("tool-scenarios-kalanagar",
     "Compare two scenarios for the Z convoy: hold at Kalanagar junction for 10 minutes, or re-route via the BKC connector.",
     [], "Z", "evaluate_scenarios"),
    ("tool-history-worli-naka", "How does Worli Naka usually look on a Friday evening?",
     [], "none", "get_historical_pattern"),
    ("tool-final-after-routes",
     "Find routes from Mantralaya to the airport and tell me the ETA of the best one.",
     ["find_convoy_routes", "predict_eta"], "Z+", "final_answer"),
    ("tool-corridor-events-girgaon",
     "Are there active corridor events near Girgaon Chowpatty for the visarjan processions?",
     [], "none", "get_active_corridor_events"),
]

for rid, text, called, cls, expected in TOOL_CHAT:
    state = DeciderBrain.build_state_doc(
        trigger="operator_chat",
        summary="Operator request: " + text[:600],
        context={"tools_already_called": called, "vvip_class": cls},
    )
    add(rid, "tool_selection", state, DeciderBrain.tool_selection_question(_TOOL_MENU),
        {"next_tool": expected})


# ── 3. DSS course-of-action strategy (OSINT situations: places, not persons) ─

DSS = [
    ("dss-waterlogging-hindmata-high-tide",
     {"summary": "Knee-deep waterlogging on Dr Ambedkar Road at Hindmata between Parel and Dadar TT at high tide; "
                 "outfalls closed until the tide turns in about 2 hours; BEST buses crawling, two cars stalled",
      "event_class": "waterlogging", "subtype": "high_tide", "toponym": "Hindmata",
      "credibility": 0.92, "verification_state": "OFFICIAL-VERIFIED",
      "second_order": ["KEM Hospital approach slowed"]}, "standard"),
    ("dss-sea-link-breakdown",
     {"summary": "A minibus broke down on the Bandra–Worli Sea Link in the Worli-bound lanes during the evening "
                 "peak; one lane open, queue reaching the Bandra end",
      "event_class": "road_closure", "subtype": "vehicle_breakdown", "toponym": "Bandra–Worli Sea Link",
      "credibility": 0.88, "verification_state": "OFFICIAL-VERIFIED", "second_order": []}, "standard"),
    ("dss-ganeshotsav-crowd-lalbaug",
     {"summary": "Ganeshotsav crowd for Lalbaugcha Raja spilling onto the carriageway at Lalbaug on visarjan eve; "
                 "pedestrian density rising, vehicles at walking pace",
      "event_class": "mass_gathering", "subtype": "festival_crowd", "toponym": "Lalbaug",
      "credibility": 0.85, "verification_state": "CONFIRMED",
      "second_order": ["ambulance (108) corridor to KEM Hospital slowed"]}, "aggressive"),
    ("dss-unverified-flooding-chembur",
     {"summary": "A single social post claims a road is flooded near Chembur; no photo, no corroborating report, "
                 "rain gauges in the area show light rain",
      "event_class": "weather_hazard", "subtype": "flooding_claim", "toponym": "Chembur",
      "credibility": 0.18, "verification_state": "UNVERIFIED-OSINT", "second_order": []}, "information"),
    ("dss-collision-bkc",
     {"summary": "Two cars collided near Bandra Kurla Complex; the service lane is blocked, main carriageway moving",
      "event_class": "road_accident", "subtype": "collision", "toponym": "Bandra Kurla Complex",
      "credibility": 0.55, "verification_state": "NEWS-REPORTED", "second_order": []}, None),
    ("dss-wankhede-egress",
     {"summary": "Match ended at Wankhede Stadium; about 30,000 spectators leaving towards Churchgate and Marine "
                 "Lines; Marine Drive northbound saturated",
      "event_class": "mass_gathering", "subtype": "egress_surge", "toponym": "Wankhede Stadium",
      "credibility": 0.95, "verification_state": "CONFIRMED", "second_order": []}, "aggressive"),
    ("dss-tree-fall-weh",
     {"summary": "A large tree fell across two lanes of the Western Express Highway near Vile Parle after a squall; "
                 "one lane passable, BMC crew requested",
      "event_class": "road_closure", "subtype": "tree_fall", "toponym": "Western Express Highway, Vile Parle",
      "credibility": 0.8, "verification_state": "OFFICIAL-VERIFIED", "second_order": []}, "standard"),
    ("dss-mount-mary-bandra",
     {"summary": "Pilgrims for the Mount Mary fair at Bandra: BEST buses queueing on Hill Road, "
                 "footfall steady, no incident reported",
      "event_class": "mass_gathering", "subtype": "pilgrim_transit", "toponym": "Mount Mary, Bandra",
      "credibility": 0.9, "verification_state": "OFFICIAL-VERIFIED", "second_order": []}, None),
    ("dss-fire-kalbadevi",
     {"summary": "Fire reported in a godown near Kalbadevi; fire tenders on the way; smoke over the adjoining road",
      "event_class": "fire", "subtype": "structure_fire", "toponym": "Kalbadevi",
      "credibility": 0.7, "verification_state": "NEWS-REPORTED",
      "second_order": ["fire tender access needed"]}, "aggressive"),
    ("dss-signal-failure-sion-circle",
     {"summary": "Signals dark at Sion Circle after a power cut; traffic police managing manually",
      "event_class": "road_closure", "subtype": "signal_failure", "toponym": "Sion Circle",
      "credibility": 0.75, "verification_state": "NEWS-REPORTED", "second_order": []}, None),
    ("dss-general-news-no-traffic",
     {"summary": "A news item about a book fair schedule announcement; no road impact mentioned",
      "event_class": "general_news", "subtype": "announcement", "toponym": "Dadar",
      "credibility": 0.6, "verification_state": "NEWS-REPORTED", "second_order": []}, "baseline"),
    ("dss-marathon-marine-drive",
     {"summary": "City marathon on Sunday morning: Marine Drive and the Sea Link closed 05:00-10:00 as notified",
      "event_class": "road_closure", "subtype": "planned_event", "toponym": "Marine Drive",
      "credibility": 0.97, "verification_state": "OFFICIAL-VERIFIED", "second_order": []}, None),
]

for rid, situation, expected in DSS:
    context = {key: situation.get(key) for key in _CONTEXT_KEYS}
    state = DeciderBrain.build_state_doc(
        trigger="incident_detected", summary=str(situation.get("summary") or ""), context=context,
    )
    add(rid, "dss_coa", state, dss_questions(situation), {"coa_strategy": expected} if expected else None)


# ── 4. live escort: incident checkpoint (question set as in live_escort.py) ─

INCIDENT_QUESTIONS = {
    "action": {
        "type": "choice",
        "instructions": (
            "Congestion on the convoy's route is above the spike threshold "
            "(see the summary). Choose the immediate action: keep monitoring, "
            "hold the convoy at its position, activate the pre-sanitised Plan B "
            "route, re-route around the congested segments, or escalate to the "
            "operator."
        ),
        "options": list(INCIDENT_ACTIONS),
    },
    "urgency": {
        "type": "noul",
        "instructions": (
            "Probability that none of the listed actions fit "
            "this incident (escalate to operator)."
        ),
    },
}

INCIDENTS = [
    ("esc-inc-kalanagar-crossing", "Z+", 0.91, 0.75, "crossing", 0.42, 9.8, 38.0, "yes"),
    ("esc-inc-hold-expired-worli-naka", "Z", 0.84, 0.75, "hold_expired", 0.61, 3.2, 0.0, "yes"),
    ("esc-inc-deferred-sea-link", "Z+", 0.97, 0.7, "deferred_crossing", 0.18, 21.5, 24.0, "yes"),
    ("esc-inc-mild-vile-parle", "Y", 0.78, 0.75, "crossing", 0.70, 4.1, 41.0, "none"),
    ("esc-inc-no-planb-sion", "Z", 0.95, 0.7, "crossing", 0.33, 8.7, 12.0, "none"),
    ("esc-inc-near-destination-airport", "Z+", 0.80, 0.75, "crossing", 0.93, 1.6, 45.0, "yes"),
    ("esc-inc-holding-kings-circle", "X", 0.88, 0.75, "hold_expired", 0.48, 6.0, 0.0, "none"),
    ("esc-inc-severe-csmt", "Z+", 0.99, 0.7, "crossing", 0.25, 12.4, 5.0, "yes"),
]

for rid, cls, peak, thr, origin, prog, rem_km, speed, planb in INCIDENTS:
    if origin == "hold_expired":
        lead = (f"A hold ran out (held 120 s at the current segment) with congestion {peak:.2f} still above "
                f"the spike threshold {thr:.2f} on the held segment(s) of the {cls} convoy")
    elif origin == "deferred_crossing":
        lead = (f"Congestion {peak:.2f} crossed the spike threshold {thr:.2f} during the incident cooldown and "
                f"is still above it on segment(s) ahead of the {cls} convoy")
    else:
        lead = (f"Congestion {peak:.2f} crossed the spike threshold {thr:.2f} on segment(s) ahead of the "
                f"{cls} convoy")
    seg = 5100 + int(prog * 40)
    state = DeciderBrain.build_state_doc(
        trigger="incident_detected",
        summary=f"{lead}, at {prog:.0%} of the route, {rem_km:.1f} km to go.",
        context={
            "movement_id": f"mv-sim-{rid}", "vvip_class": cls, "event_kind": "protected_movement",
            "incident_origin": origin, "current_segment": seg,
            "segments_ahead": [seg + i for i in range(1, 9)],
            "hot_segments": f"{seg + 2}={peak:.2f}, {seg + 3}={max(thr, peak - 0.07):.2f}",
            "convoy_speed_kmh": speed, "convoy_holding": "yes" if speed == 0.0 else "no",
            "plan_b_spine": "available" if planb == "yes" else "none",
            "closures_active": 3, "folded_crossings": 1 if origin == "deferred_crossing" else 0,
            "gps": "emulated",
        },
    )
    add(rid, "escort_incident", state, INCIDENT_QUESTIONS)


# ── 5. live escort: departure posture ───────────────────────────────────────

DEPARTURE_QUESTIONS = {
    "departure": {
        "type": "choice",
        "instructions": (
            "The convoy is rolling onto its planned primary route. Choose the "
            "departure posture: proceed now, hold the departure until the "
            "corridor ahead clears, or switch to the pre-sanitised Plan B route."
        ),
        "options": list(DEPARTURE_ACTIONS),
    },
}

DEPARTURES = [
    ("esc-dep-clear", "Z+", 41, 24.6, 0.31, 0.75, [], "available", "proceed"),
    ("esc-dep-hot-ahead", "Z+", 41, 24.6, 0.93, 0.75, [5103, 5104, 5105], "available", None),
    ("esc-dep-hot-no-planb", "Z", 22, 13.2, 0.88, 0.7, [6802, 6803], "none", None),
    ("esc-dep-not-reporting", "Y", 18, 7.2, None, 0.75, [], "available", None),
    ("esc-dep-borderline", "X", 12, 5.4, 0.74, 0.75, [], "none", "proceed"),
    ("esc-dep-resume-midway", "Z", 30, 15.5, 0.82, 0.75, [7415], "available", None),
]

for rid, cls, nseg, km, peak, thr, hot, planb, expected in DEPARTURES:
    speed = 40.0
    where = f"{km:.1f} km to go" if rid != "esc-dep-resume-midway" else f"resuming at 45% of the route, {km * 0.55:.1f} km to go"
    rem = km if rid != "esc-dep-resume-midway" else km * 0.55
    eta_min = rem * 1000 / (speed / 3.6) / 60
    summary = (
        f"Live escort start for the {cls} convoy (protected_movement) on its {nseg}-segment primary route, {where}"
        + f", about {eta_min:.0f} min at {speed:.0f} km/h"
        + ". Live congestion on the route "
        + (f"peaks at {peak:.2f}" if peak is not None else "is not reporting")
        + f" (spike threshold {thr:.2f})"
        + (f"; above it: {hot[:6]}" if hot else "") + "."
    )
    state = DeciderBrain.build_state_doc(
        trigger="phase_transition", summary=summary,
        context={
            "movement_id": f"mv-sim-{rid}", "vvip_class": cls, "event_kind": "protected_movement",
            "plan_status": "approved", "route_segments": list(range(5100, 5100 + min(nseg, 12))),
            "segments_reporting": f"{0 if peak is None else nseg - 2}/{nseg}",
            "closures_active": 4, "plan_b_spine": planb, "gps": "emulated",
        },
    )
    add(rid, "escort_departure", state, DEPARTURE_QUESTIONS, {"departure": expected} if expected else None)


# ── 6. post-clearance restoration posture ───────────────────────────────────

RESTORE_Q = {
    "restoration_posture": {
        "type": "choice",
        "instructions": "The convoy has passed. Choose the public-traffic restoration posture.",
        "options": list(RESTORATION_POSTURES),
    },
}
RESTORES = [
    ("pc-mantralaya-airport", "Convoy movement mv-sim-mantralaya-airport entering post-clearance restoration.",
     {"phase": "clear"}),
    ("pc-wankhede-egress", "Convoy movement mv-sim-wankhede-y entering post-clearance restoration.",
     {"phase": "clear", "closures_active": 6, "queue_on_marine_drive_m": 900}),
    ("pc-gateway-short", "Convoy movement mv-sim-gateway-z entering post-clearance restoration.",
     {"phase": "clear", "closures_active": 2, "queue_m": 120}),
    ("pc-visarjan-night", "Convoy movement mv-sim-visarjan-zplus entering post-clearance restoration.",
     {"phase": "clear", "closures_active": 9, "pedestrian_density": "high (visarjan crowds)"}),
    ("pc-signals-ready", "Convoy movement mv-sim-bkc entering post-clearance restoration.",
     {"phase": "clear", "closures_active": 5, "adaptive_signals": "online on 5 of 5 junctions"}),
]
for rid, summary, context in RESTORES:
    state = DeciderBrain.build_state_doc(trigger="phase_transition", summary=summary, context=context)
    add(rid, "post_clearance", state, RESTORE_Q)


# ── 7. probes: the brain's health probe and the C1 smoke shape ──────────────

add("probe-health", "probe", "TRIGGER: health_probe\nstrategic-tier latency probe", {
    "probe": {
        "type": "noul",
        "instructions": ("Health probe (none-of-the-above likelihood): "
                         "is an unscheduled strategic checkpoint needed now?"),
    },
})

SMOKE_QUESTIONS = {
    "urgency": {"type": "noul",
                "instructions": "Based on this corridor state, must the departure window be locked now rather than delayed?"},
    "reroute": {"type": "choice", "instructions": "Which corridor should the route use?",
                "options": {"weh": "Western Express Highway, moderate flow",
                            "ambedkar_road": "Dr Ambedkar Road, heavy congestion",
                            "coastal_road": "Coastal Road, light flow"}},
    "readiness": {"type": "score", "instructions": "Rate readiness to lock the departure window",
                  "scale": ["not ready", "barely ready", "partially ready", "mostly ready", "fully ready"]},
}
add("probe-corridor-checkpoint", "probe",
    "CORRIDOR CHECKPOINT (SIMULATED): Z+ convoy staged at Mantralaya. Three corridors under watch: "
    "Western Express Highway (moderate flow, 42 km/h average), Dr Ambedkar Road (heavy congestion near Dadar TT, "
    "14 km/h), Coastal Road (light flow, 55 km/h). Movement window 19:45-20:30 IST. Two signal failures reported "
    "on Dr Ambedkar Road in the last 20 minutes; weather clear; feed EMULATED. Advance closure 150 seconds.",
    SMOKE_QUESTIONS, {"reroute": "coastal_road"})
add("probe-corridor-checkpoint-rain", "probe",
    "CORRIDOR CHECKPOINT (SIMULATED): Z convoy staged at Mumbai Airport T2 for Mantralaya. High tide at 18:40 "
    "IST with heavy rain: waterlogging reported on the Western Express Highway near Andheri Subway (8 km/h), "
    "Dr Ambedkar Road moderate (30 km/h), Coastal Road light (48 km/h). Movement window 18:30-19:15 IST. "
    "Feed EMULATED.",
    SMOKE_QUESTIONS, {"reroute": "coastal_road"})


def main() -> None:
    out = HERE / "requests.json"
    ids = [r["id"] for r in REQUESTS]
    assert len(ids) == len(set(ids)), "duplicate request ids"
    for r in REQUESTS:
        assert 1 <= len(r["questions"]) <= 6
    out.write_text(json.dumps({"label": "SIMULATED", "requests": REQUESTS}, indent=1, ensure_ascii=False))
    kinds: dict[str, int] = {}
    for r in REQUESTS:
        kinds[r["kind"]] = kinds.get(r["kind"], 0) + 1
    print(f"wrote {len(REQUESTS)} requests to {out}: {kinds}")


if __name__ == "__main__":
    main()
