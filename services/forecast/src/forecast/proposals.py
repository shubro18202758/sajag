"""Pre-emptive diversion PROPOSALS — never actions.

For every forecast crossing (p50 V/C reaching the threshold within the horizon) one proposal object is
produced in the platform's decision-support vocabulary (osint_common C-U): ``state: proposed``, actions
in the ``CoaAction`` shape (verb, target_urn, params, requires_officer, reversible), a
``recommendation.decision: await_officer`` and a ``human_gate`` naming the role that decides
(``duty_officer``) with no officer and no decision time. Nothing here changes a signal, a road or a
message: a named officer approves, rejects or lets the proposal lapse, and if no one answers the current
plan holds.

The detour is the shortest path between the segment's end junctions on the city network that avoids the
segment itself and, where it can, every other segment forecast at or over the threshold.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from forecast.network import Network

__all__ = ["crossing_proposal"]


_DEVANAGARI_DIGITS = str.maketrans("0123456789", "०१२३४५६७८९")


def _r(x: float) -> float:
    return round(float(x), 2)


def crossing_proposal(net: Network, fc: dict, hot: set[int], generated_at: datetime, threshold: float,
                      horizon_min: int, labels: list[str], model: str) -> dict[str, Any]:
    sid = int(fc["segment_id"])
    seg = net.segments[sid]
    c = fc["crossing"]
    place = net.junction_name(seg.to_junction)
    path = net.alternative_path(sid, avoid=hot - {sid})
    vc50, vc10, vc90 = c["vc_p50"], c["vc_p10"], c["vc_p90"]
    head = (f"{place}: V/C forecast {vc50:.2f} in {c['in_min']} min "
            f"(p10–p90 {vc10:.2f}–{vc90:.2f}) on {seg.road_name}")
    # the share of the flow that would have to divert to hold p50 just under the threshold (MODELLED)
    share = min(0.35, max(0.05, 1.0 - (threshold - 0.02) / max(vc50, 1e-6)))
    actions: list[dict[str, Any]] = []
    if path:
        via_names: list[str] = []
        for p in path:
            name = net.segments[p].road_name
            if not via_names or via_names[-1] != name:
                via_names.append(name)
        via = " → ".join(via_names)
        detour_m = sum(net.segments[p].length_m for p in path)
        summary = f"{head}; propose diversion via {via}."
        actions.append({
            "verb": "diversion", "target_urn": f"segment:{sid}",
            "params": {"via_segment_ids": path, "via_names": via_names, "detour_length_m": round(detour_m),
                       "direct_length_m": round(seg.length_m), "suggested_share": round(share, 2),
                       "window_min": horizon_min, "starts_before_min": max(0, int(c["in_min"]) - 10)},
            "requires_officer": True, "reversible": True,
        })
    else:
        summary = f"{head}; no reasonable detour on the city network — propose a signal-timing review."
        actions.append({
            "verb": "monitor", "target_urn": f"segment:{sid}",
            "params": {"review": "signal timing at " + place, "window_min": horizon_min},
            "requires_officer": True, "reversible": True,
        })
    advisory = {"draft_en": f"Heavy traffic expected near {place} in about {c['in_min']} minutes. "
                            "Please plan ahead.",
                "channel": "public advisory (after officer approval)"}
    j = net.junctions.get(seg.to_junction)
    if j is not None and j.name_mr:
        # Marathi draft (the city's state language); numerals in Devanagari as in public notices
        mins = str(int(c["in_min"])).translate(_DEVANAGARI_DIGITS)
        advisory["draft_mr"] = (f"{j.name_mr} जवळ सुमारे {mins} मिनिटांत मोठी वाहतूक कोंडी अपेक्षित आहे. "
                                "कृपया प्रवासाचे नियोजन करा.")
    actions.append({
        "verb": "advisory", "target_urn": f"junction:{seg.to_junction}",
        "params": advisory,
        "requires_officer": True, "reversible": True,
    })
    stamp = generated_at.strftime("%Y%m%dT%H%MZ")
    return {
        "proposal_id": f"fc-{sid}-{stamp}",
        "kind": "pre_emptive_diversion",
        "subject_urn": f"segment:{sid}",
        "state": "proposed",
        "generated_at": generated_at.isoformat(),
        "expires_at": c["at"],
        "horizon_min": horizon_min,
        "summary": summary,
        "situation": {
            "segment_id": sid, "road_name": seg.road_name, "place": place,
            "junction_id": seg.to_junction, "vc_now": fc["now"]["vc"],
            "crossing_at": c["at"], "in_min": c["in_min"],
            "vc_p10": _r(vc10), "vc_p50": _r(vc50), "vc_p90": _r(vc90), "threshold": threshold,
            "baseline_vc_p50": c.get("baseline_vc_p50"),
        },
        "actions": actions,
        "expected_effect": {
            "suggested_share": round(share, 2),
            "note": "share of the flow that would have to divert to hold the forecast median just under the "
                    "threshold (MODELLED, proportional; not simulated in the twin)",
        },
        "recommendation": {"decision": "await_officer"},
        "human_gate": {"state": "proposed", "required_role": "duty_officer", "officer": None, "decided_at": None},
        "labels": labels,
        "provenance": {"model": model, "data": fc.get("data_label"), "history_source": fc.get("history_source")},
    }
