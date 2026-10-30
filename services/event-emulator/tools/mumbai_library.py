"""Build the emulator's Mumbai scenario library from the city network.

    python tools/mumbai_library.py --network cities/mumbai/network.json [--write]

The scenarios live in ``tools/mumbai_scenarios.json``, written in terms of
the network's junction keys (``cities/mumbai/network.json`` junction
``key``s; the places they name are ``cities/mumbai/landmarks.json`` ids): a
route is a walk from crossing to crossing, a cause sits ``on`` the road
between two crossings.  This tool resolves every walk against the network
into segment ids, checks that each route is a LEGAL directed path (one-ways
driven their own way), finds the watchlist sweep's path through the
registered sweep cameras, and writes ``src/event_emulator/
use_case_library.json``.  When the network is regenerated with new ids,
re-run it: the scenarios follow.

Every scenario is SIMULATED.  Times, speeds, crowd loads and demand figures
are MODELLED assumptions (stated in each description); no number here is a
real-world statistic.  Events are about places, never people: no person is
named, tracked or described.

``--slim-out`` writes the small network snapshot the emulator's tests check
the library, the profiles and the living city's sites against.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
LIBRARY = HERE.parent / "src" / "event_emulator" / "use_case_library.json"
LANDMARKS = HERE.parents[2] / "cities" / "mumbai" / "landmarks.json"
SCENARIOS = HERE / "mumbai_scenarios.json"

_R_EARTH_M = 6371008.8


# ── the network ─────────────────────────────────────────────────────────────


class Network:
    """Junctions by key, segments with ends, one-way flags and lengths."""

    def __init__(self, doc: dict) -> None:
        self.doc = doc
        marks = {}
        if LANDMARKS.is_file():
            marks = {m["id"]: m for m in
                     json.loads(LANDMARKS.read_text(encoding="utf-8"))["landmarks"]}
        self.key_to_jid: dict[str, int] = {}
        self.jid_to_key: dict[int, str] = {}
        self.jpos: dict[int, tuple[float, float]] = {}
        self.jname: dict[int, tuple[str, str]] = {}
        for j in doc["junctions"]:
            jid = int(j["junction_id"])
            key = j.get("key") or j.get("landmark")
            if key:
                self.key_to_jid[str(key)] = jid
                self.jid_to_key[jid] = str(key)
            mark = marks.get(str(j.get("landmark") or key or ""))
            if "lon" in j and "lat" in j:
                self.jpos[jid] = (float(j["lon"]), float(j["lat"]))
            elif "at" in j:
                self.jpos[jid] = (float(j["at"][1]), float(j["at"][0]))
            elif mark:
                self.jpos[jid] = (float(mark["lon"]), float(mark["lat"]))
            self.jname[jid] = (str(j.get("name") or (mark or {}).get("en") or key or jid),
                               str(j.get("name_mr") or (mark or {}).get("mr") or ""))
        self.segs: dict[int, dict] = {}
        for s in doc["segments"]:
            sid = int(s["segment_id"])
            a = s.get("from_junction")
            b = s.get("to_junction")
            if a is None and "from" in s:
                a = self.key_to_jid[s["from"]]
            if b is None and "to" in s:
                b = self.key_to_jid[s["to"]]
            line = [tuple(map(float, p)) for p in (s.get("line") or [])]
            self.segs[sid] = {
                "id": sid, "name": s.get("road_name", ""), "a": int(a),
                "b": int(b) if b is not None else None,
                "oneway": bool(s.get("oneway")), "line": line,
                "length_m": float(s.get("length_m") or 0.0) or None,
                "limit": s.get("speed_limit_kmh"), "road_class": s.get("road_class"),
            }

    # geometry -------------------------------------------------------------

    @staticmethod
    def dist_m(p: tuple[float, float], q: tuple[float, float]) -> float:
        lat0 = math.radians((p[1] + q[1]) / 2.0)
        dx = math.radians(q[0] - p[0]) * math.cos(lat0) * _R_EARTH_M
        dy = math.radians(q[1] - p[1]) * _R_EARTH_M
        return math.hypot(dx, dy)

    def length_m(self, sid: int) -> float:
        s = self.segs[sid]
        if s["length_m"]:
            return s["length_m"]
        if len(s["line"]) >= 2:
            return sum(self.dist_m(p, q) for p, q in zip(s["line"], s["line"][1:]))
        # draft spec without geometry: the crossings' distance × a detour factor
        return 1.3 * self.dist_m(self.jpos[s["a"]], self.jpos[s["b"]])

    def line(self, sid: int) -> list[list[float]]:
        s = self.segs[sid]
        if len(s["line"]) >= 2:
            return [[round(p[0], 7), round(p[1], 7)] for p in s["line"]]
        a, b = self.jpos[s["a"]], self.jpos[s["b"]]
        return [[round(a[0], 7), round(a[1], 7)], [round(b[0], 7), round(b[1], 7)]]

    # walks ----------------------------------------------------------------

    def jid(self, key: str) -> int:
        try:
            return self.key_to_jid[key]
        except KeyError:
            raise SystemExit(f"ERROR: no junction keyed {key!r} in the network") from None

    def between(self, a: str, b: str, *, directed: bool = True) -> int:
        """The segment that runs from crossing ``a`` to crossing ``b``
        (legal in that direction when ``directed``)."""
        ja, jb = self.jid(a), self.jid(b)
        found = []
        for s in self.segs.values():
            if (s["a"], s["b"]) == (ja, jb):
                found.append(s["id"])
            elif (s["a"], s["b"]) == (jb, ja) and not (directed and s["oneway"]):
                found.append(s["id"])
        if not found:
            raise SystemExit(f"ERROR: no {'legal ' if directed else ''}segment {a} -> {b}")
        return min(found)

    def _moves(self, at: int) -> list[tuple[int, int]]:
        """(segment, next junction) legal from junction ``at``."""
        out = []
        for s in self.segs.values():
            if s["b"] is None:
                continue
            if s["a"] == at:
                out.append((s["id"], s["b"]))
            elif s["b"] == at and not s["oneway"]:
                out.append((s["id"], s["a"]))
        return out

    def shortest(self, a: int, b: int, avoid: set[int]) -> list[int]:
        """Shortest legal drive (metres) from junction ``a`` to ``b``."""
        import heapq

        best = {a: 0.0}
        prev: dict[int, tuple[int, int]] = {}
        heap = [(0.0, a)]
        while heap:
            d, at = heapq.heappop(heap)
            if at == b:
                break
            if d > best.get(at, math.inf):
                continue
            for sid, nxt in self._moves(at):
                if sid in avoid:
                    continue
                nd = d + self.length_m(sid)
                if nd < best.get(nxt, math.inf):
                    best[nxt] = nd
                    prev[nxt] = (sid, at)
                    heapq.heappush(heap, (nd, nxt))
        if b not in best:
            raise SystemExit(f"ERROR: no legal drive {self.jid_to_key.get(a, a)} -> "
                             f"{self.jid_to_key.get(b, b)}")
        out: list[int] = []
        at = b
        while at != a:
            sid, at = prev[at]
            out.append(sid)
        return out[::-1]

    def walk(self, *keys: str) -> list[int]:
        """The legal route through crossings ``keys`` in order: the shortest
        legal drive between each consecutive pair (one-ways their own way),
        never the same segment twice."""
        out: list[int] = []
        for a, b in zip(keys, keys[1:]):
            out += self.shortest(self.jid(a), self.jid(b), set(out))
        if len(set(out)) != len(out):
            raise SystemExit(f"ERROR: walk {keys} uses a segment twice")
        return out

    def near(self, place: str, among: list[int] | None = None) -> int:
        """The segment nearest a landmark (``among`` restricts the choice)."""
        marks = {}
        if LANDMARKS.is_file():
            marks = {m["id"]: m for m in
                     json.loads(LANDMARKS.read_text(encoding="utf-8"))["landmarks"]}
        if place in marks:
            pt = (float(marks[place]["lon"]), float(marks[place]["lat"]))
        else:
            pt = self.jpos[self.jid(place)]
        pool = among if among is not None else list(self.segs)

        def gap(sid: int) -> float:
            line = self.line(sid)
            return min(self._point_seg_m(pt, tuple(p), tuple(q))
                       for p, q in zip(line, line[1:]))
        return min(pool, key=lambda sid: (gap(sid), sid))

    def _point_seg_m(self, p: tuple[float, float], a: tuple[float, float],
                     b: tuple[float, float]) -> float:
        kx = math.cos(math.radians(p[1])) * 111320.0
        ky = 111320.0
        ax, ay = (a[0] - p[0]) * kx, (a[1] - p[1]) * ky
        bx, by = (b[0] - p[0]) * kx, (b[1] - p[1]) * ky
        dx, dy = bx - ax, by - ay
        L = dx * dx + dy * dy
        t = 0.0 if L == 0 else max(0.0, min(1.0, -(ax * dx + ay * dy) / L))
        return math.hypot(ax + t * dx, ay + t * dy)

    def exit_junction(self, route: list[int]) -> list[int]:
        """The crossings a route passes, in order (its start first)."""
        if len(route) == 1:
            s = self.segs[route[0]]
            return [s["a"], s["b"]]
        first, second = self.segs[route[0]], self.segs[route[1]]
        start = first["a"] if first["b"] in (second["a"], second["b"]) else first["b"]
        out = [start]
        for sid in route:
            s = self.segs[sid]
            nxt = s["b"] if s["a"] == out[-1] else s["a"]
            out.append(nxt)
        return out

    def slim(self) -> dict:
        return {
            "about": ("Slim snapshot of the Mumbai road network the emulator's library, "
                      "profiles and living-city sites are built on (ids, ends, one-way "
                      "flags, names, lengths). GENERATED by tools/mumbai_library.py from "
                      "the city network; the emulator's tests check against it."),
            "junctions": [
                {"junction_id": jid, "key": self.jid_to_key.get(jid),
                 "name": self.jname[jid][0], "name_mr": self.jname[jid][1],
                 "lon": round(self.jpos[jid][0], 6) if jid in self.jpos else None,
                 "lat": round(self.jpos[jid][1], 6) if jid in self.jpos else None,
                 "signal_control": next((bool(j.get("signal_control")) for j in
                                         self.doc["junctions"]
                                         if int(j["junction_id"]) == jid), False)}
                for jid in sorted(self.jname)
            ],
            "segments": [
                {"segment_id": s["id"], "road_name": s["name"], "from_junction": s["a"],
                 "to_junction": s["b"], "oneway": s["oneway"],
                 "length_m": round(self.length_m(s["id"]), 1),
                 "speed_limit_kmh": s["limit"], "road_class": s["road_class"]}
                for s in sorted(self.segs.values(), key=lambda x: x["id"])
            ],
            "signal_programs": sorted(int(k) for k in (self.doc.get("signal_programs") or {})),
            "cameras": [
                {k: c.get(k) for k in ("camera_id", "kind", "junction_id", "segment_id",
                                       "lon", "lat", "heading_deg", "label") if k in c}
                for c in self.doc.get("cameras") or [] if isinstance(c, dict)
                and c.get("camera_id")
            ],
        }


# ── scenario helpers ────────────────────────────────────────────────────────


def ev_windows(net: Network, route: list[int], *, start_sec: float, speed_kmh: float,
               label: str, places: list[str], window_sec: float = 300.0,
               severity: float = 0.9) -> list[dict]:
    """Green-corridor windows for an ambulance (108) or a fire tender, one
    per route segment, each opening when the vehicle (at ``speed_kmh``)
    reaches that segment and held until it has cleared it (its travel time
    on the road's length plus two minutes' margin, never under
    ``window_sec``)."""
    if len(places) != len(route):
        raise SystemExit(f"ERROR: {label!r}: {len(route)} segments but {len(places)} places")
    out: list[dict] = []
    t = float(start_sec)
    for sid, place in zip(route, places):
        travel = net.length_m(sid) / (speed_kmh / 3.6)
        out.append({
            "type": "emergency_vehicle", "segment_id": sid,
            "start_sec": round(t, 1),
            "duration_sec": float(max(window_sec, round(travel + 120.0))),
            "severity": severity, "label": f"{label} — {place}",
        })
        t += travel
    return out


def fe(kind: str, sid: int, start: float, dur: float, sev: float, label: str,
       demand: float | None = None) -> dict:
    doc: dict[str, Any] = {"type": kind, "segment_id": sid, "start_sec": float(start),
                           "duration_sec": float(dur), "severity": sev, "label": label}
    if demand is not None:
        doc["extra_demand_veh_h"] = float(demand)
    return doc


def scenario(**kw: Any) -> dict:
    """One library entry in its canonical key order."""
    order = ("scenario_id", "name", "name_mr", "name_hi", "label", "category",
             "description", "places", "route_segment_ids", "departure_time", "vvip_class",
             "closure_policy", "horizon_min", "n_replications", "seed", "convoy_speed_kmh",
             "weather", "event_overrides", "forced_events", "expected_features",
             "event_kind", "crowd_class", "duration_class", "stolen_fir_ref", "unit_tracks")
    kw.setdefault("label", "SIMULATED")
    cfg = {k: kw[k] for k in order if k in kw}
    extra = set(kw) - set(order)
    if extra:
        raise SystemExit(f"ERROR: unknown scenario keys {sorted(extra)}")
    return {"id": cfg["scenario_id"], "scenarioConfig": cfg}


# ── route helpers ───────────────────────────────────────────────────────────


def first_leg(net: Network, a: str, b: str) -> int:
    """The segment a legal drive from crossing ``a`` towards ``b`` starts on
    (the road joining them when they are neighbours)."""
    return net.shortest(net.jid(a), net.jid(b), set())[0]


def out_of(net: Network, route: list[int], key: str) -> int:
    """The route segment that leaves crossing ``key``."""
    passes = net.exit_junction(route)
    jid = net.jid(key)
    if jid not in passes[:-1]:
        raise SystemExit(f"ERROR: the route {route} does not leave {key}")
    return route[passes.index(jid)]


def into(net: Network, route: list[int], key: str) -> int:
    """The route segment that arrives at crossing ``key``."""
    passes = net.exit_junction(route)
    jid = net.jid(key)
    if jid not in passes[1:]:
        raise SystemExit(f"ERROR: the route {route} does not reach {key}")
    return route[passes.index(jid, 1) - 1]


def named(net: Network, sid: int, *fragments: str) -> int:
    """``sid``, checked to be a road whose OSM name carries one of
    ``fragments`` (a lookup by landmark must land on the road it means)."""
    name = net.segs[sid]["name"]
    if not any(f.lower() in name.lower() for f in fragments):
        raise SystemExit(f"ERROR: segment {sid} is {name!r}, expected one of {fragments}")
    return sid


def road_names(net: Network, route: list[int]) -> str:
    out: list[str] = []
    for sid in route:
        n = net.segs[sid]["name"]
        if not out or out[-1] != n:
            out.append(n)
    return " > ".join(out)



# ── the scenarios ───────────────────────────────────────────────────────────

#: The order and the fields of a library entry (``scenario`` checks them).
_SPEC_ONLY = ("route", "forced_events", "unit_tracks")


def _resolve_events(net: Network, events: list[dict]) -> list[dict]:
    out = []
    for e in events:
        e = dict(e)
        a, b = e.pop("on")
        sid = net.between(a, b, directed=False)
        doc = {"type": e["type"], "segment_id": sid}
        doc.update({k: v for k, v in e.items() if k != "type"})
        out.append(doc)
    return out


def _route(net: Network, keys: list[str]) -> list[int]:
    """The route through crossings ``keys``: each consecutive pair joined by
    the road between them, driven its legal way."""
    return [net.between(a, b) for a, b in zip(keys, keys[1:])]


def build(net: Network) -> list[dict]:
    """The library: every spec in ``mumbai_scenarios.json`` on this network."""
    specs = json.loads(SCENARIOS.read_text(encoding="utf-8"))
    lib: list[dict] = []
    for spec in specs:
        kw = {k: v for k, v in spec.items() if k not in _SPEC_ONLY}
        if spec["route"] == "SWEEP":
            route = sweep_route(net)
            kw["description"] = sweep_description(net, route, spec["stolen_fir_ref"])
            kw["places"] = sweep_places(net, route)
        else:
            route = _route(net, spec["route"])
        kw["route_segment_ids"] = route
        kw["forced_events"] = _resolve_events(net, spec.get("forced_events") or [])
        tracks = spec.get("unit_tracks")
        if tracks:
            units, segs = [], set()
            for u in tracks["units"]:
                u = dict(u)
                ids = _route(net, u.pop("walk"))
                segs |= set(ids)
                doc = {k: u[k] for k in ("unit_id", "agency", "label", "status")}
                if "arrival_status" in u:
                    doc["arrival_status"] = u["arrival_status"]
                doc["mode"] = u["mode"]
                doc["segment_ids"] = ids
                doc.update({k: u[k] for k in ("speed_kmh", "offset", "start_sec") if k in u})
                units.append(doc)
            kw["unit_tracks"] = {"note": tracks["note"], "units": units,
                                 "route_geometry": {str(s): net.line(s)
                                                    for s in sorted(segs | set(route))}}
        missing = [p for p in kw.get("places") or [] if LANDMARK_IDS and p not in LANDMARK_IDS]
        if missing:
            raise SystemExit(f"ERROR: {spec['scenario_id']}: places not in landmarks.json: {missing}")
        lib.append(scenario(**kw))
    return lib


def profile_segments(net: Network, lib: list[dict]) -> dict[str, int]:
    """The segments profiles.py's added causes name (by role)."""
    by = {u["id"]: u["scenarioConfig"]["route_segment_ids"] for u in lib}
    base, cloud, egress, sweep = (by["vvip_convoy_base"], by["cloudburst_high_tide"],
                                  by["wankhede_egress"], by["watchlist_anpr_sweep"])
    out = {
        "weh_vakola": named(net, out_of(net, base, "vakola"), "Western Express"),
        "marine_drive_wankhede": named(net, into(net, egress, "marine_lines"), "Marine Drive"),
        "dn_road_csmt": named(net, out_of(net, egress, "csmt"), "D N Road"),
        "dr_ambedkar_hindmata": named(net, out_of(net, cloud, "hindmata"), "Ambedkar"),
        "dr_ambedkar_sion": named(net, into(net, cloud, "sion_circle"), "Ambedkar"),
    }
    market = [s for s in sweep if "Swami Vivekanand" in net.segs[s]["name"]
              or "Andheri-Kurla" in net.segs[s]["name"]]
    out["sweep_market_road"] = market[0] if market else sweep[0]
    return out


# ── the watchlist sweep route ───────────────────────────────────────────────

#: Without registered sweep cameras the sweep runs this walk.
SWEEP_WALK = ("bandra_sv", "santacruz_sv", "santacruz_milan", "vileparle_sv", "andheri_sv")
#: Longest sweep the search accepts (metres).
SWEEP_MAX_M = 12000.0


def sweep_route(net: Network) -> list[int]:
    """One legal path through as many registered sweep cameras' roads
    (EM-CAM-nn) as it can, then the most stop-line cameras, then the
    shortest; the fixed walk when the network registers none."""
    import itertools

    cams = [c for c in net.doc.get("cameras") or []
            if str(c.get("camera_id", "")).startswith("EM-CAM-")]
    sweep = sorted({int(c["segment_id"]) for c in cams})
    stop = {int(c["segment_id"]) for c in net.doc.get("cameras") or []
            if c.get("junction_id") is not None and c.get("heading_deg") is not None}
    if not sweep:
        return net.walk(*SWEEP_WALK)
    best: tuple | None = None
    for k in range(len(sweep), 0, -1):
        for subset in itertools.combinations(sweep, k):
            for order in itertools.permutations(subset):
                for flips in itertools.product((0, 1), repeat=len(order)):
                    route: list[int] = []
                    ok = True
                    for sid, flip in zip(order, flips):
                        s = net.segs[sid]
                        if flip and s["oneway"]:
                            ok = False
                            break
                        a, b = (s["b"], s["a"]) if flip else (s["a"], s["b"])
                        if route:
                            at = net.exit_junction(route)[-1]
                            try:
                                route += net.shortest(at, a, set(route) | set(order))
                            except SystemExit:
                                ok = False
                                break
                        if sid in route:
                            ok = False
                            break
                        route.append(sid)
                        if legal(net, route):
                            ok = False
                            break
                    if not ok or len(set(route)) != len(route):
                        continue
                    length = sum(net.length_m(s) for s in route)
                    if length > SWEEP_MAX_M:
                        continue
                    score = (k, len(stop & set(route)), -length)
                    if best is None or score > best[0]:
                        best = (score, route)
        if best is not None:
            return best[1]
    return net.walk(*SWEEP_WALK)


def sweep_text(net: Network, route: list[int]) -> str:
    return "along " + road_names(net, route).replace(" > ", ", ") + "."


def sweep_places(net: Network, route: list[int]) -> list[str]:
    keys = [net.jid_to_key.get(j) for j in net.exit_junction(route)]
    return list(dict.fromkeys(k for k in keys if k and k in LANDMARK_IDS))



def sweep_description(net: Network, route: list[int], fir: str) -> str:
    return (
        "EMULATED WATCHLIST SCENARIO (clearly labelled, never a live feed). A stolen-vehicle FIR "
        "drives an ANPR camera sweep through the western suburbs " + sweep_text(net, route)
        + " Deterministic camera reads cover background traffic, the FIR-named STOLEN plate "
        "MH01EM9001 and the earmark-exercise plate MH02EM4321 — every synthetic plate carries an "
        "EM series, every sighting lands with source emulated_anpr, and the oracle, never the "
        "tape, computes each hit and rule. The FIR (" + fir + ", an emulated scenario reference) "
        "is the scenario's premise, stated at t0 as a labelled EMULATED precondition (a "
        "stolen_vehicle_fir earmark on MH01EM9001 by 'event-emulator (system) — scenario "
        "precondition'; if the oracle cannot take it, that plate's reads are skipped): the stolen "
        "car's reads hit as stolen_vehicle and file evidence-only R_STOLEN_SIGHTING "
        "recommendations, never a fine. MH02EM4321 is an OPERATOR EXERCISE: the emulator never "
        "earmarks it, so its reads hit as earmarked_plate only when a duty officer has earmarked "
        "MH02EM4321 (Watchlist: a lawful basis and their name) before the run — on a fresh "
        "install they are ordinary sightings. Only a named human officer acts on any "
        "recommendation. Two Mumbai Traffic Police patrol units animate alongside (agency_unit "
        "frames). Vehicles only, never persons.")


# ── the living city's sites and beats ───────────────────────────────────────

#: (kind, EN name, MR name, segment spec, place, detail EN, detail MR, festival)
#: A segment spec is (a, b): the road a legal drive from crossing a towards b
#: starts on; or ("near", landmark): the road nearest the landmark.
SITE_SPECS: list[tuple] = [
    # breakdowns on the arterials, bridges and highways (lane loss until the tow)
    ("breakdown", "Bandra–Worli Sea Link (northbound)", "वांद्रे–वरळी सागरी सेतू (उत्तरेकडे)",
     ("sealink_worli_n", "sealink_bandra_n"), "sea_link", "BEST bus breakdown", "बेस्ट बस बंद पडली", None),
    ("breakdown", "Western Express Highway (Vakola–Sahar)", "पश्चिम द्रुतगती महामार्ग (वाकोला–सहार)",
     ("vakola", "airport_weh"), None, "Container truck breakdown", "कंटेनर ट्रक बंद पडला", None),
    ("breakdown", "Eastern Express Highway (Sion–Chunabhatti)", "पूर्व द्रुतगती महामार्ग (सायन–चुनाभट्टी)",
     ("lbs_fork", "priyadarshini"), "sion_circle", "Goods tempo breakdown", "मालवाहू टेम्पो बंद पडला", None),
    ("breakdown", "JVLR (Powai–Gandhinagar)", "जेव्हीएलआर (पवई–गांधीनगर)",
     ("powai", "gandhinagar"), "powai", "Kaali-peeli taxi breakdown", "काळी-पिवळी टॅक्सी बंद पडली", None),
    ("breakdown", "Santacruz–Chembur Link Road (Kurla)", "सांताक्रूझ–चेंबूर जोड रस्ता (कुर्ला)",
     ("vakola", "sclr_ramp"), "kurla", "Truck breakdown", "ट्रक बंद पडला", None),
    ("breakdown", "Eastern Freeway (Orange Gate–Sewri)", "पूर्व मुक्त मार्ग (ऑरेंज गेट–शिवडी)",
     ("orange_gate", "atal_setu"), "atal_setu", "Stalled car", "कार बंद पडली", None),
    ("breakdown", "Peddar Road", "पेडर रोड", ("kemps_corner", "haji_ali"), "haji_ali",
     "Stalled car", "कार बंद पडली", None),
    ("breakdown", "LBS Marg (Kamani–Ghatkopar)", "लालबहादूर शास्त्री मार्ग (कमानी–घाटकोपर)",
     ("kamani", "ghatkopar_lbs"), "ghatkopar", "Private bus breakdown", "खासगी बस बंद पडली", None),
    ("breakdown", "Mumbai Coastal Road (northbound)", "मुंबई किनारी रस्ता (उत्तरेकडे)",
     ("marine_lines", "sealink_worli_n"), None, "App-cab breakdown", "ॲप कॅब बंद पडली", None),
    ("breakdown", "Andheri–Kurla Road (Marol)", "अंधेरी–कुर्ला रस्ता (मरोळ)",
     ("weh_andheri", "saki_naka"), "weh_andheri", "Tanker breakdown", "टँकर बंद पडला", None),
    ("breakdown", "Sion–Panvel Highway (Chembur–Mankhurd)", "सायन–पनवेल महामार्ग (चेंबूर–मानखुर्द)",
     ("chembur", "mankhurd"), "chembur", "Container truck breakdown", "कंटेनर ट्रक बंद पडला", None),
    ("breakdown", "Gokhale Bridge (Andheri)", "गोखले पूल (अंधेरी)", ("andheri_sv", "gokhale_east"),
     "andheri", "BEST bus breakdown", "बेस्ट बस बंद पडली", None),
    ("breakdown", "Tilak Bridge (Dadar)", "टिळक पूल (दादर)", ("dadar_west", "dadar_tt"), "dadar",
     "Auto-rickshaw breakdown", "रिक्षा बंद पडली", None),
    ("breakdown", "JJ Flyover (Mohammed Ali Road)", "जे.जे. उड्डाणपूल (मोहम्मद अली रोड)",
     ("csmt", "jj"), "jj_hospital", "Truck breakdown", "ट्रक बंद पडला", None),
    # hawkers and markets on the kerb
    ("market_spillover", "Dadar West market (Lady Jamshetji Road)", "दादर पश्चिम बाजार (लेडी जमशेटजी रोड)",
     ("dadar_west", "mahim"), "dadar", "", "", None),
    ("market_spillover", "Crawford Market (Mohammed Ali Road)", "क्रॉफर्ड मार्केट (मोहम्मद अली रोड)",
     ("jj", "csmt"), "police_hq", "", "", None),
    ("market_spillover", "Bandra (Hill Road – SV Road)", "वांद्रे (हिल रोड – एस. व्ही. रोड)",
     ("bandra_sv", "santacruz_sv"), "bandra", "", "", None),
    ("market_spillover", "Lalbaug market (Dr Ambedkar Road)", "लालबाग बाजार (डॉ. आंबेडकर रोड)",
     ("lalbaug", "parel"), "lalbaug", "", "", None),
    ("market_spillover", "Kurla market (LBS Marg)", "कुर्ला बाजार (एलबीएस मार्ग)",
     ("kurla", "kurla_sclr"), "kurla", "", "", None),
    ("market_spillover", "Andheri West market (SV Road)", "अंधेरी पश्चिम बाजार (एस. व्ही. रोड)",
     ("vileparle_sv", "andheri_sv"), "andheri", "", "", None),
    ("market_spillover", "Mahim (causeway market)", "माहीम (कॉजवे बाजार)", ("mahim", "mahim_causeway"),
     "mahim_causeway", "", "", None),
    # school runs
    ("school_egress", "Walkeshwar Road (Malabar Hill)", "वाळकेश्वर रोड (मलबार हिल)",
     ("girgaon_chowpatty", "raj_bhavan"), None, "", "", None),
    ("school_egress", "N S Patkar Marg – Hughes Road", "ना. सी. पाटकर मार्ग – ह्यूजेस रोड",
     ("girgaon_chowpatty", "kemps_corner"), None, "", "", None),
    ("school_egress", "Keshavrao Khadye Marg (Jacob Circle)", "केशवराव खाडये मार्ग (जेकब सर्कल)",
     ("jacob_circle", "byculla"), None, "", "", None),
    ("school_egress", "Dr A R Nair Road (Mumbai Central)", "डॉ. ए. आर. नायर रोड (मुंबई सेंट्रल)",
     ("jacob_circle", "nair"), "nair_hospital", "", "", None),
    ("school_egress", "Pandurang Budhkar Marg (Worli)", "पांडुरंग बुधकर मार्ग (वरळी)",
     ("worli_naka", "lower_parel"), None, "", "", None),
    ("school_egress", "SV Road (Santacruz)", "एस. व्ही. रोड (सांताक्रूझ)",
     ("santacruz_sv", "santacruz_milan"), None, "", "", None),
    # office peaks into and out of Nariman Point–Fort, Lower Parel and BKC
    ("office_rush", "Veer Nariman Road – D N Road (CSMT)", "वीर नरिमन रोड – दादाभाई नौरोजी रोड (सीएसएमटी)",
     ("churchgate", "csmt"), "csmt", "", "", None),
    ("office_rush", "Marine Drive (Churchgate–Nariman Point)", "मरीन ड्राइव्ह (चर्चगेट–नरिमन पॉइंट)",
     ("churchgate_md", "mantralaya"), "marine_drive", "", "", None),
    ("office_rush", "Bandra Kurla Complex Road (Kalanagar–BKC)", "वांद्रे कुर्ला संकुल रस्ता (कलानगर–बीकेसी)",
     ("kalanagar", "bkc"), "bkc", "", "", None),
    ("office_rush", "Bandra Kurla Complex Road (BKC–Kurla)", "वांद्रे कुर्ला संकुल रस्ता (बीकेसी–कुर्ला)",
     ("bkc", "kurla"), "bkc", "", "", None),
    ("office_rush", "Senapati Bapat Marg (Lower Parel)", "सेनापती बापट मार्ग (लोअर परळ)",
     ("lower_parel", "dadar_west"), None, "", "", None),
    ("office_rush", "Western Express Highway (Kalanagar)", "पश्चिम द्रुतगती महामार्ग (कलानगर)",
     ("bwsl_merge", "kalanagar"), "kalanagar", "", "", None),
    ("office_rush", "Annie Besant Road (Worli)", "ॲनी बेझंट रोड (वरळी)", ("atre_chowk", "worli_naka"),
     "worli_naka", "", "", None),
    ("office_rush", "Mumbai Coastal Road (southbound)", "मुंबई किनारी रस्ता (दक्षिणेकडे)",
     ("sealink_worli_s", "marine_lines"), None, "", "", None),
    # Powai / Andheri East / Goregaon office and IT shift changes
    ("it_shift_change", "Saki Vihar Road (Powai)", "साकी विहार रोड (पवई)", ("saki_naka", "powai"),
     "powai", "", "", None),
    ("it_shift_change", "JVLR (Jogeshwari–Powai)", "जेव्हीएलआर (जोगेश्वरी–पवई)", ("jvlr_weh", "powai"),
     "powai", "", "", None),
    ("it_shift_change", "Andheri–Kurla Road (Saki Naka–Kurla)", "अंधेरी–कुर्ला रस्ता (साकी नाका–कुर्ला)",
     ("saki_naka", "kamani"), None, "", "", None),
    ("it_shift_change", "Western Express Highway (Goregaon)", "पश्चिम द्रुतगती महामार्ग (गोरेगाव)",
     ("jvlr_weh", "goregaon_weh"), None, "", "", None),
    # the chronic flooding spots on the network (MODELLED susceptibility;
    # the spots are the ones BMC and news reporting name, MUMBAI.md §2)
    ("waterlogging", "Dr Ambedkar Road (Hindmata)", "डॉ. आंबेडकर रोड (हिंदमाता)", ("hindmata", "dadar_tt"),
     "hindmata", "", "", None),
    ("waterlogging", "Dr Ambedkar Road (King's Circle, Gandhi Market)",
     "डॉ. आंबेडकर रोड (किंग्ज सर्कल, गांधी मार्केट)", ("dadar_tt", "kings_circle"), "kings_circle",
     "", "", None),
    ("waterlogging", "Dr Ambedkar Road (Sion)", "डॉ. आंबेडकर रोड (सायन)", ("sion_hospital", "sion_circle"),
     "sion_circle", "", "", None),
    ("waterlogging", "Milan Subway road (Santacruz)", "मिलन सबवे रस्ता (सांताक्रूझ)",
     ("santacruz_milan", "milan_subway"), "milan_subway", "", "", None),
    ("waterlogging", "Andheri Subway approach (Sahar Road)", "अंधेरी सबवे मार्ग (सहार रोड)",
     ("gokhale_east", "andheri_subway"), "andheri_subway", "", "", None),
    ("waterlogging", "LBS Marg (Kurla, by the Mithi)", "एलबीएस मार्ग (कुर्ला, मिठी नदीजवळ)",
     ("lbs_fork", "kurla"), "mithi_kurla", "", "", None),
    ("waterlogging", "Dr Ambedkar Road (Parel)", "डॉ. आंबेडकर रोड (परळ)", ("parel", "hindmata"), "parel",
     "", "", None),
    ("waterlogging", "Eastern Express Highway (Chunabhatti)", "पूर्व द्रुतगती महामार्ग (चुनाभट्टी)",
     ("lbs_fork", "priyadarshini"), None, "", "", None),
    ("waterlogging", "Dr Ambedkar Road (Byculla)", "डॉ. आंबेडकर रोड (भायखळा)", ("byculla", "lalbaug"),
     None, "", "", None),
    ("waterlogging", "Bandra Kurla Complex Road (Kurla end)", "वांद्रे कुर्ला संकुल रस्ता (कुर्ला टोक)",
     ("bkc", "kurla"), "mithi_kurla", "", "", None),
    # Ganeshotsav nights around the mandals and on the visarjan route
    ("festival_crowd", "Dr Ambedkar Road (Lalbaugcha Raja)", "डॉ. आंबेडकर रोड (लालबागचा राजा)",
     ("lalbaug", "parel"), "lalbaugcha_raja", "", "", "puja"),
    ("festival_crowd", "Dr Ambedkar Road (Parel)", "डॉ. आंबेडकर रोड (परळ)", ("parel", "hindmata"),
     "parel", "", "", "puja"),
    ("festival_crowd", "Jagannath Shankarsheth Marg (Girgaon Chowpatty)",
     "जगन्नाथ शंकरशेट मार्ग (गिरगाव चौपाटी)", ("opera_house", "girgaon_chowpatty"),
     "girgaon_chowpatty", "", "", "puja"),
    ("festival_crowd", "Dr Ambedkar Road (GSB Seva Mandal, King's Circle)",
     "डॉ. आंबेडकर रोड (जीएसबी सेवा मंडळ, किंग्ज सर्कल)", ("kings_circle", "sion_hospital"),
     "gsb_kings_circle", "", "", "puja"),
    ("festival_crowd", "Sir JJ Road (JJ, visarjan route)", "सर जे.जे. रोड (जे.जे., विसर्जन मार्ग)",
     ("jj", "byculla"), "jj_hospital", "", "", "puja"),
    ("festival_crowd", "Dr Ambedkar Road (Byculla, visarjan route)",
     "डॉ. आंबेडकर रोड (भायखळा, विसर्जन मार्ग)", ("byculla", "lalbaug"), "lalbaug", "", "", "puja"),
    # Christmas to New Year evenings on Marine Drive
    ("festival_crowd", "Marine Drive (Churchgate–Marine Lines)", "मरीन ड्राइव्ह (चर्चगेट–मरीन लाइन्स)",
     ("churchgate_md", "marine_lines"), "marine_drive", "", "", "year_end"),
    ("festival_crowd", "Marine Drive (Marine Lines–Girgaon Chowpatty)",
     "मरीन ड्राइव्ह (मरीन लाइन्स–गिरगाव चौपाटी)", ("marine_lines", "girgaon_chowpatty"),
     "girgaon_chowpatty", "", "", "year_end"),
    ("festival_crowd", "Veer Nariman Road (Churchgate)", "वीर नरिमन रोड (चर्चगेट)",
     ("churchgate_md", "churchgate"), "churchgate", "", "", "year_end"),
]

_SITE_PREFIX = {"breakdown": "BD", "market_spillover": "MK", "school_egress": "SE",
                "office_rush": "OR", "it_shift_change": "IT", "waterlogging": "WL",
                "festival_crowd": "FC"}

#: The living city's emulated field units (connected chains, each one-way
#: driven its own way): (unit id, beat, walk through crossings).  The unit
#: id's prefix names the agency (event_emulator.city.unit_role): MTP-EM
#: Mumbai Traffic Police beats, MP-EM-PCR Mumbai Police patrol cars,
#: 108-EM-LC ambulance (108) standby circuits.  The first two beats ride at
#: every density; the rest join at EMULATOR_LIVING_DENSITY >= 2.  The beats
#: added after the first two use two-way roads only (a beat is driven back
#: and forth).  Beat names stay short: the oracle caps a unit label at 80
#: characters.
PATROL_SPECS = (
    ("MTP-EM-LC1", "Marine Drive–Churchgate–CSMT",
     ("mantralaya", "churchgate_md", "churchgate", "csmt")),
    ("MTP-EM-LC2", "WEH (Kalanagar–Andheri)",
     ("kalanagar", "vakola", "airport_weh", "weh_andheri")),
    ("MTP-EM-LC3", "Dr Ambedkar Road (Byculla–Dadar TT)",
     ("byculla", "lalbaug", "parel", "hindmata", "dadar_tt")),
    ("MTP-EM-LC4", "Annie Besant Road (Haji Ali–Worli Naka)",
     ("haji_ali", "atre_chowk", "worli_naka")),
    ("MTP-EM-LC5", "SV Road (Bandra–Santacruz)",
     ("bandra_sv", "santacruz_sv", "santacruz_milan")),
    ("MTP-EM-LC6", "Dr Ambedkar Road (Dadar TT–Sion)",
     ("dadar_tt", "kings_circle", "sion_hospital", "sion_circle")),
    ("MTP-EM-LC7", "Senapati Bapat Marg (Lower Parel–Mahim)",
     ("lower_parel", "dadar_west", "mahim")),
    ("MTP-EM-LC8", "LBS Marg (Kurla–Ghatkopar)",
     ("kurla", "kurla_sclr", "kamani", "ghatkopar_lbs")),
    ("MTP-EM-LC9", "BKC Road (Kalanagar–Kurla)",
     ("kalanagar", "bkc", "kurla")),
    ("MTP-EM-LC10", "EEH (Sion–Chembur)",
     ("sion_circle", "lbs_fork", "priyadarshini", "chembur")),
    ("MTP-EM-LC11", "Andheri–Kurla Road (Andheri–Saki Naka)",
     ("andheri_east", "weh_andheri", "saki_naka")),
    ("MP-EM-PCR1", "Hughes Road–Peddar Road (to Haji Ali)",
     ("girgaon_chowpatty", "kemps_corner", "haji_ali")),
    ("MP-EM-PCR2", "JVLR (Powai–Vikhroli)",
     ("powai", "gandhinagar", "vikhroli_eeh")),
    ("MP-EM-PCR3", "Mohammed Ali Road–Nagpada",
     ("csmt", "jj", "nagpada")),
    ("108-EM-LC1", "Hindmata–KEM Hospital",
     ("dadar_tt", "hindmata", "kem")),
    ("108-EM-LC2", "Mahim Causeway–Bandra (SV Road)",
     ("mahim", "mahim_causeway", "bandra_sv")),
    ("108-EM-LC3", "SV Road (Irla–Andheri)",
     ("santacruz_milan", "vileparle_sv", "andheri_sv")),
    ("108-EM-LC4", "Nair Hospital–Jacob Circle–Byculla",
     ("nair", "jacob_circle", "byculla")),
)


def living_sites(net: Network) -> tuple[list[dict], list[tuple], list[int]]:
    """(sites, patrols, signalised junctions) on this network."""
    sites: list[dict] = []
    seen: set[str] = set()
    for kind, name, name_mr, spec, place, detail, detail_mr, festival in SITE_SPECS:
        if spec[0] == "near":
            sid = net.near(spec[1])
        else:
            sid = first_leg(net, spec[0], spec[1])
        s = net.segs[sid]
        site_id = f"{_SITE_PREFIX[kind]}-{sid}"
        if site_id in seen:
            raise SystemExit(f"ERROR: two {kind} sites on segment {sid}")
        seen.add(site_id)
        sites.append({"site_id": site_id, "kind": kind, "name": name, "name_mr": name_mr,
                      "segments": [sid], "junctions": sorted(j for j in (s["a"], s["b"])
                                                             if j is not None),
                      "detail": detail, "detail_mr": detail_mr, "place": place,
                      "festival": festival, "road": s["name"]})
    signalised = sorted(int(k) for k in (net.doc.get("signal_programs") or {}))
    for jid in signalised:
        legs = sorted(s["id"] for s in net.segs.values() if jid in (s["a"], s["b"]))
        name, name_mr = net.jname[jid]
        sites.append({"site_id": f"SF-J{jid}", "kind": "signal_fault", "name": name,
                      "name_mr": name_mr or name, "segments": legs, "junctions": [jid],
                      "detail": "", "detail_mr": "", "place": net.jid_to_key.get(jid)
                      if net.jid_to_key.get(jid) in LANDMARK_IDS else None,
                      "festival": None, "road": ""})
    patrols = [(uid, beat, net.walk(*walk)) for uid, beat, walk in PATROL_SPECS]
    return sites, patrols, signalised


LANDMARK_IDS: set[str] = set()
if LANDMARKS.is_file():
    LANDMARK_IDS = {m["id"] for m in json.loads(LANDMARKS.read_text(encoding="utf-8"))
                    ["landmarks"]}


def network_module(net: Network, sites: list[dict], patrols: list[tuple],
                   signalised: list[int], segments: dict[str, int], source: str) -> str:
    """The text of src/event_emulator/mumbai_network.py."""
    lines = [
        '"""The Mumbai network ids the emulator names — GENERATED, do not edit.',
        "",
        "Written by ``tools/mumbai_library.py`` from the city road network",
        f"(``{source}``): the living city's sites (EN + Marathi names, the",
        "landmarks.json place each sits at), its emulated field units' beats,",
        "the signalised junctions (those with a signal program) and the segments",
        "the profiles' own causes sit on.  Re-run the tool when the network is",
        "regenerated; the emulator's network check (ambient.py) and its tests",
        "(tests/data/mumbai_network_slim.json) catch any drift.",
        '"""',
        "",
        "from __future__ import annotations",
        "",
        "#: (site_id, kind, EN name, MR name, segments, junctions, detail EN,",
        "#:  detail MR, landmarks.json place, festival)",
        "SITE_ROWS: tuple[tuple, ...] = (",
    ]
    for s in sites:
        lines.append(
            f"    ({s['site_id']!r}, {s['kind']!r}, {s['name']!r}, {s['name_mr']!r}, "
            f"{tuple(s['segments'])!r}, {tuple(s['junctions'])!r}, {s['detail']!r}, "
            f"{s['detail_mr']!r}, {s['place']!r}, {s['festival']!r}),")
    lines += [")", "", "#: (unit id, beat, connected segment chain)", "PATROL_ROWS: tuple[tuple, ...] = ("]
    for uid, beat, route in patrols:
        lines.append(f"    ({uid!r}, {beat!r}, {tuple(route)!r}),")
    lines += [")", "", "#: Junctions with a signal program (corridor.signal_programs).",
              "SIGNALISED_JUNCTIONS: frozenset[int] = frozenset({"
              + ", ".join(str(j) for j in sorted(signalised)) + "})", "",
              "#: The segments the profiles' own causes sit on, by role.",
              "PROFILE_SEGMENTS: dict[str, int] = {"]
    for k in sorted(segments):
        lines.append(f"    {k!r}: {segments[k]},  # {net.segs[segments[k]]['name']}")
    lines += ["}", ""]
    return "\n".join(lines)


# ── checks + output ─────────────────────────────────────────────────────────


def legal(net: Network, route: list[int]) -> list[str]:
    """Why ``route`` is not a legal directed path; [] when it is one."""
    if not route:
        return ["empty route"]
    if len(set(route)) != len(route):
        return ["a segment twice"]
    for sid in route:
        if sid not in net.segs:
            return [f"unknown segment {sid}"]

    def ends(sid: int) -> list[tuple[int, int]]:
        s = net.segs[sid]
        return [(s["a"], s["b"])] + ([] if s["oneway"] else [(s["b"], s["a"])])

    # every orientation of the first segment that can start a legal drive
    frontier = {e[1] for e in ends(route[0])}
    for prev, sid in zip(route, route[1:]):
        nxt = {e[1] for e in ends(sid) if e[0] in frontier}
        if not nxt:
            return [f"{prev} -> {sid} is not a legal move"]
        frontier = nxt
    return []


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--network", required=True, type=Path)
    ap.add_argument("--write", action="store_true",
                    help="write use_case_library.json, mumbai_network.py and the slim snapshot")
    args = ap.parse_args(argv)
    net = Network(json.loads(args.network.read_text(encoding="utf-8")))
    lib = build(net)
    segments = profile_segments(net, lib)
    sites, patrols, signalised = living_sites(net)
    bad = False
    for uc in lib:
        cfg = uc["scenarioConfig"]
        problems = legal(net, cfg["route_segment_ids"])
        bad |= bool(problems)
        print(f"{'OK ' if not problems else 'BAD'} {uc['id']:32s} {cfg['route_segment_ids']}"
              f"  {road_names(net, cfg['route_segment_ids'])}  {problems or ''}")
    for uid, beat, route in patrols:
        problems = legal(net, route)
        bad |= bool(problems)
        print(f"{'OK ' if not problems else 'BAD'} patrol {uid} {beat}: {route}")
    for s in sites:
        print(f"    site {s['site_id']:10s} {s['kind']:16s} {s['name']:42s} -> {s['road']}")
    print("profile segments:", {k: (v, net.segs[v]["name"]) for k, v in segments.items()})
    if bad:
        print("ERROR: a route is not a legal path", file=sys.stderr)
        return 1
    if args.write:
        LIBRARY.write_text(json.dumps(lib, indent=1, ensure_ascii=False) + "\n",
                           encoding="utf-8")
        mod = HERE.parent / "src" / "event_emulator" / "mumbai_network.py"
        parts = args.network.resolve().parts
        source = ("/".join(parts[parts.index("cities"):]) if "cities" in parts
                  else args.network.name)
        mod.write_text(network_module(net, sites, patrols, signalised, segments, source),
                       encoding="utf-8")
        slim = HERE.parent / "tests" / "data" / "mumbai_network_slim.json"
        slim.parent.mkdir(parents=True, exist_ok=True)
        slim.write_text(json.dumps(net.slim(), indent=1, ensure_ascii=False) + "\n",
                        encoding="utf-8")
        print(f"wrote {LIBRARY.name}, {mod.name}, {slim.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
