"""Waterlogging PROPOSALS — never actions. A named officer approves each one; if no one answers, nothing
changes.

The shape follows the platform's decision-support vocabulary (osint_common C-U): ``state: proposed``,
actions as ``CoaAction`` (verb, target_urn, params, requires_officer, reversible), ``recommendation.decision:
await_officer`` and a ``human_gate`` naming the deciding role with no officer and no decision time.

* **reroute** (risk ≥ 2) — a diversion around the segment on the city network, avoiding other flagged
  segments where it can; Mumbai Traffic Police and BEST (bus routes on the road) are the agencies to notify;
* **ambulance window** (risk ≥ 2) — a note for ambulance (108) crews: how long the road stays passable
  (the lead time before it turns deep), the detour, and the nearest major hospital (KEM, Sion, Nair, JJ,
  Cooper — cities/mumbai/landmarks.json);
* **pump request** (one, when anything is flagged) — ask BMC disaster control (1916) to stage mobile
  dewatering pumps at the flagged places, naming the serving pumping station (its state is EMULATED);
* **advisory draft** — one public advisory in English, Marathi and Hindi naming the flagged places (Western
  digits; the public page's formatter renders local digits);
* **live-wire hazard** (risk ≥ 2) — a request to the area's power distribution utility to inspect and,
  where needed, isolate street-light and overhead supply along the flagged road: standing water around poles
  and feeder pillars is an electrocution risk. Proposal for officer approval.
"""

from __future__ import annotations

import json
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from hydro.network import Network, haversine_m

__all__ = ["reroute", "ambulance_window", "advisory_draft", "live_wire", "pump_request", "nearest_hospital",
           "GATE", "HOSPITAL_IDS"]

#: the major public hospitals an ambulance window names (canonical landmark ids)
HOSPITAL_IDS = ("kem", "sion_hospital", "nair_hospital", "jj_hospital", "cooper_hospital")


@lru_cache(maxsize=1)
def _hospitals() -> list[dict[str, Any]]:
    path = Path(__file__).with_name("data") / "mumbai_landmarks.json"
    lms = json.loads(path.read_text(encoding="utf-8"))["landmarks"]
    return [lm for lm in lms if lm["id"] in HOSPITAL_IDS]


def nearest_hospital(lat: float, lon: float) -> dict[str, Any]:
    best = min(_hospitals(), key=lambda h: haversine_m(lat, lon, h["lat"], h["lon"]))
    return {"id": best["id"], "name": best["en"], "name_mr": best.get("mr"), "name_hi": best.get("hi"),
            "distance_m": round(haversine_m(lat, lon, best["lat"], best["lon"]))}

GATE = {"state": "proposed", "required_role": "duty_officer", "officer": None, "decided_at": None}


def _base(pid: str, kind: str, subject: str, at: datetime, summary: str, actions: list[dict],
          labels: list[str]) -> dict[str, Any]:
    return {"proposal_id": pid, "kind": kind, "subject_urn": subject, "state": "proposed",
            "generated_at": at.isoformat(), "summary": summary, "actions": actions,
            "recommendation": {"decision": "await_officer"}, "human_gate": dict(GATE), "labels": labels}


def _via(net: Network, path: list[int]) -> list[str]:
    names: list[str] = []
    for p in path:
        n = net.segments[p].road_name
        if not names or names[-1] != n:
            names.append(n)
    return names


def reroute(net: Network, r: dict, flagged: set[int], at: datetime, labels: list[str]) -> dict[str, Any]:
    sid = r["segment_id"]
    path = net.alternative_path(sid, avoid=flagged - {sid})
    stamp = at.strftime("%Y%m%dT%H%MZ")
    deep = r.get("lead_time_deep_min")
    deep = r["lead_time_min"] if deep is None else deep
    when = "deep water now" if deep == 0 else f"deep water in about {deep} min"
    head = (f"{r['place']} ({r['road_name']}): waterlogging risk {r['risk_class']} "
            f"({r['expected_depth_band']}), {when}")
    if path:
        via = _via(net, path)
        summary = (f"{head}; propose diverting traffic via {' → '.join(via)}, and asking BEST to divert the bus "
                   "routes on this road the same way.")
        act = {"verb": "diversion", "target_urn": f"segment:{sid}",
               "params": {"via_segment_ids": path, "via_names": via,
                          "detour_length_m": round(sum(net.segments[p].length_m for p in path)),
                          "reason": "waterlogging", "notify_agencies": ["mtp", "best"]},
               "requires_officer": True, "reversible": True}
    else:
        summary = f"{head}; no detour on the city network that avoids flagged roads — propose closing to " \
                  "small vehicles with officer judgement on site."
        act = {"verb": "monitor", "target_urn": f"segment:{sid}",
               "params": {"reason": "waterlogging", "notify_agencies": ["mtp", "best"]},
               "requires_officer": True, "reversible": True}
    p = _base(f"hy-reroute-{sid}-{stamp}", "waterlogging_reroute", f"segment:{sid}", at, summary, [act], labels)
    p["situation"] = {k: r[k] for k in ("segment_id", "road_name", "place", "risk_class", "expected_depth_band",
                                        "lead_time_min", "lead_time_deep_min")}
    return p


def ambulance_window(net: Network, r: dict, flagged: set[int], at: datetime, labels: list[str]) -> dict[str, Any]:
    sid = r["segment_id"]
    path = net.alternative_path(sid, avoid=flagged - {sid})
    stamp = at.strftime("%Y%m%dT%H%MZ")
    lead = r.get("lead_time_deep_min")
    lead = r["lead_time_min"] if lead is None else lead
    window = f"passable for about {lead} min more" if lead > 0 else "already deep"
    detour = f"; use {' → '.join(_via(net, path))}" if path else "; no detour avoiding flagged roads"
    hosp = nearest_hospital(r["lat"], r["lon"]) if "lat" in r and "lon" in r else None
    to = f" Nearest major hospital: {hosp['name']} ({hosp['distance_m'] / 1000:.1f} km)." if hosp else ""
    summary = f"Ambulance (108) note — {r['place']} ({r['road_name']}): {window}{detour}.{to}"
    act = {"verb": "advisory", "target_urn": f"segment:{sid}",
           "params": {"to_agency": "amb108", "passable_for_min": lead,
                      "via_segment_ids": path or [], "nearest_hospital": hosp, "note": summary},
           "requires_officer": True, "reversible": True}
    return _base(f"hy-amb-{sid}-{stamp}", "ambulance_window", f"segment:{sid}", at, summary, [act], labels)


def advisory_draft(results: list[dict], at: datetime, horizon_min: int, labels: list[str]) -> dict[str, Any] | None:
    hit = [r for r in results if r["risk_class"] >= 2]
    if not hit:
        return None
    hit.sort(key=lambda r: (-r["risk_class"], r["lead_time_min"]))
    places_en: list[str] = []
    places_mr: list[str] = []
    places_hi: list[str] = []
    for r in hit:
        if r["place"] not in places_en:
            places_en.append(r["place"])
            places_mr.append(r.get("place_mr") or r["place"])
            places_hi.append(r.get("place_hi") or r["place"])
        if len(places_en) == 6:
            break
    en = (f"Traffic advisory (draft): waterlogging is likely within the next {horizon_min} minutes at these "
          f"places: {'; '.join(places_en)}. Please avoid these roads if you can. Do not touch electric poles or "
          "wires in standing water. Emergency: 112; BMC disaster control: 1916; ambulance (108).")
    mr = (f"वाहतूक सूचना (मसुदा): पुढील {horizon_min} मिनिटांत या ठिकाणी पाणी साचण्याची शक्यता आहे: "
          f"{'; '.join(places_mr)}. शक्य असल्यास हे रस्ते टाळा. साचलेल्या पाण्यात विजेचे खांब किंवा तारांना स्पर्श "
          "करू नका. आपत्कालीन क्रमांक: 112; बृहन्मुंबई महानगरपालिका आपत्ती नियंत्रण: 1916; रुग्णवाहिका (108).")
    hi = (f"यातायात सलाह (मसौदा): अगले {horizon_min} मिनट में इन जगहों पर जलभराव की आशंका है: "
          f"{'; '.join(places_hi)}। हो सके तो इन सड़कों से बचें। जमा पानी में बिजली के खंभों या तारों को न छुएँ। "
          "आपातकालीन: 112; बीएमसी आपदा नियंत्रण: 1916; एम्बुलेंस (108)।")
    stamp = at.strftime("%Y%m%dT%H%MZ")
    act = {"verb": "advisory", "target_urn": "place:mumbai",
           "params": {"text_en": en, "text_mr": mr, "text_hi": hi,
                      "channel": "public advisory (after officer approval)",
                      "segment_ids": [r["segment_id"] for r in hit]},
           "requires_officer": True, "reversible": True}
    p = _base(f"hy-advisory-{stamp}", "public_advisory_draft", "place:mumbai", at,
              f"Public advisory draft (English, Marathi, Hindi) for {len(places_en)} place(s).", [act], labels)
    p["text"] = {"en": en, "mr": mr, "hi": hi}
    return p


def pump_request(hot: list[dict], at: datetime, labels: list[str]) -> dict[str, Any] | None:
    """One request to BMC disaster control (1916): stage mobile dewatering pumps at the flagged places, most
    urgent first (at most 8), naming the serving pumping station and its (EMULATED) availability."""
    if not hot:
        return None
    seen: list[str] = []
    sites: list[dict[str, Any]] = []
    for r in hot:
        if r["place"] in seen:
            continue
        seen.append(r["place"])
        pumps = (r.get("drivers") or {}).get("pumps") or {}
        sites.append({"segment_id": r["segment_id"], "place": r["place"], "risk_class": r["risk_class"],
                      "lead_time_deep_min": r.get("lead_time_deep_min"),
                      "pumping_station": pumps.get("station"), "station_availability": pumps.get("availability"),
                      "station_label": pumps.get("label")})
        if len(sites) == 8:
            break
    stamp = at.strftime("%Y%m%dT%H%MZ")
    names = ", ".join(s["place"] for s in sites)
    summary = (f"Ask BMC disaster control (1916) to stage mobile dewatering pumps at {len(sites)} place(s), most "
               f"urgent first: {names}. Pumping-station state shown is EMULATED.")
    act = {"verb": "request", "target_urn": "agency:bmc_dm",
           "params": {"to_agency": "bmc_dm", "helpline": "1916", "request": "stage mobile dewatering pumps",
                      "sites": sites},
           "requires_officer": True, "reversible": True}
    return _base(f"hy-pumps-{stamp}", "pump_request", "agency:bmc_dm", at, summary, [act], labels)


def live_wire(r: dict, at: datetime, labels: list[str]) -> dict[str, Any]:
    sid = r["segment_id"]
    stamp = at.strftime("%Y%m%dT%H%MZ")
    summary = (f"Live-wire hazard — {r['place']} ({r['road_name']}): waterlogging risk {r['risk_class']} "
               f"({r['expected_depth_band']}). Propose asking the area's power distribution utility to inspect "
               "and, where needed, isolate street-light and overhead supply along this road.")
    act = {"verb": "advisory", "target_urn": f"segment:{sid}",
           "params": {"to_agency": "power", "request": "inspect and, where needed, isolate supply",
                      "why": "standing water around poles and feeder pillars: electrocution risk"},
           "requires_officer": True, "reversible": True}
    p = _base(f"hy-wire-{sid}-{stamp}", "live_wire_hazard", f"segment:{sid}", at, summary, [act], labels)
    p["for_officer_approval"] = True
    return p
