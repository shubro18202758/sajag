"""The road network the twin runs on, read from the City Pack's network JSON.

Two shapes are accepted, both written by ``scripts/gen_osm_network.py``:
the compact ``cities/<city>/network.json`` (schema ``sajag.network/1``)
and the evidence file ``scripts/data/osm_network.json``. Both carry
``junctions``, ``segments`` and ``signal_programs`` in the platform's own
vocabulary:

* a segment joins ``from_junction`` to ``to_junction``; a two-way segment
  becomes two directed links (``<id>:f`` and ``<id>:r``);
* ``lanes`` counts both directions on a two-way road;
* a signal program is ``{cycle_sec, offset_sec, phases: [{green_sec,
  movements: ["through"] | ["cross"]}]}``; phases run back to back from
  cycle position 0 and the rest of the cycle is lost time; the phase clock
  is ``(epoch - offset_sec) mod cycle_sec`` (traffic-oracle
  ``signals/plans.py``).

Each approach is mapped to a movement label the way the platform does it
(traffic-oracle ``enforcement/rules.py`` ``through_legs``): the junction's
through pair is the best-ranked pair of legs within 75 deg of straight; an
approach on a through leg is served by the ``through`` movement, any other
leg by ``cross``.

Control classes (reported on every junction):

* ``programmed``: the network carries a signal program for it;
* ``assumed``: a crossing with no program (named a "crossing", or three or
  more legs and not a grade-separated interchange); the twin gives it the
  network's own fixed-time template and says so;
* ``uncontrolled``: a node where one road continues into the next;
* ``boundary``: a dead end of the modelled network (traffic enters/leaves).
"""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from sajag_twin import params as P

__all__ = [
    "Junction",
    "Leg",
    "Link",
    "Network",
    "NetworkError",
    "Program",
    "default_network_path",
    "load_network",
    "network_from_dict",
]


class NetworkError(ValueError):
    """The network JSON cannot be used."""


# ---------------------------------------------------------------------------
# Signal program (the platform's vocabulary)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Program:
    cycle_sec: int
    offset_sec: int
    phases: tuple[tuple[int, tuple[str, ...]], ...]  # ((green_sec, movements), ...)
    source: str = "osm_assumed (MODELLED)"

    @staticmethod
    def from_dict(d: Mapping[str, Any], source: str | None = None) -> "Program":
        phases = []
        for p in d.get("phases") or []:
            if isinstance(p, Mapping):
                phases.append((int(p.get("green_sec", 0) or 0), tuple(str(m) for m in p.get("movements") or ())))
        return Program(
            cycle_sec=int(d.get("cycle_sec", 0) or 0),
            offset_sec=int(d.get("offset_sec", 0) or 0),
            phases=tuple(phases),
            source=str(source or d.get("source") or "osm_assumed (MODELLED)"),
        )

    def to_dict(self) -> dict:
        return {
            "cycle_sec": self.cycle_sec,
            "offset_sec": self.offset_sec,
            "phases": [{"green_sec": g, "movements": list(m)} for g, m in self.phases],
            "source": self.source,
        }

    @property
    def labels(self) -> list[str]:
        out: list[str] = []
        for _, ms in self.phases:
            for m in ms:
                if m not in out:
                    out.append(m)
        return out

    @property
    def lost_sec(self) -> int:
        return max(0, self.cycle_sec - sum(g for g, _ in self.phases))

    def green_of(self, label: str) -> int:
        return sum(g for g, ms in self.phases if label in ms)

    def green_ratio(self, label: str) -> float:
        return self.green_of(label) / self.cycle_sec if self.cycle_sec > 0 else 1.0

    def with_greens(self, greens: list[int], source: str) -> "Program":
        return Program(
            cycle_sec=self.cycle_sec,
            offset_sec=self.offset_sec,
            phases=tuple((int(g), ms) for g, (_, ms) in zip(greens, self.phases)),
            source=source,
        )

    def with_offset(self, offset: int, source: str) -> "Program":
        return Program(self.cycle_sec, int(offset) % max(1, self.cycle_sec), self.phases, source)

    def validate(self) -> None:
        if self.cycle_sec < P.MIN_CYCLE_S or self.cycle_sec > P.MAX_CYCLE_S:
            raise NetworkError(f"cycle_sec {self.cycle_sec} outside [{P.MIN_CYCLE_S}, {P.MAX_CYCLE_S}]")
        if not self.phases:
            raise NetworkError("a program needs at least one phase")
        if sum(g for g, _ in self.phases) > self.cycle_sec:
            raise NetworkError("greens exceed the cycle")
        for g, ms in self.phases:
            if g < 0 or not ms:
                raise NetworkError("each phase needs a green >= 0 and a movement")


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------


def _bearing(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Initial bearing from point 1 to point 2, degrees clockwise from north."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    x = math.sin(dl) * math.cos(p2)
    y = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(x, y)) + 360.0) % 360.0


def _dist_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def angle_diff(a: float, b: float) -> float:
    """Smallest absolute difference between two bearings, in [0, 180]."""
    d = (float(a) - float(b)) % 360.0
    return min(d, 360.0 - d)


def _polyline_length(line: list[list[float]]) -> float:
    return sum(_dist_m(*line[i], *line[i + 1]) for i in range(len(line) - 1))


# ---------------------------------------------------------------------------
# Model objects
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Leg:
    segment_id: int
    road_class: str
    bearing_deg: float  # pointing AWAY from the junction along the segment
    road_name: str


@dataclass
class Link:
    idx: int
    link_id: str
    segment_id: int
    direction: str  # "f" (from->to as drawn) or "r"
    from_j: int
    to_j: int
    length_m: float
    lanes: int
    vf_kmh: float
    sat_pcu_h_lane: float
    jam_pcu_km_lane: float
    road_class: str
    road_name: str
    cbd_sign: float = 0.0  # +1 heading away from the centre, -1 towards

    @property
    def sat_pcu_h(self) -> float:
        return self.sat_pcu_h_lane * self.lanes

    def to_dict(self) -> dict:
        return {
            "link_id": self.link_id,
            "segment_id": self.segment_id,
            "from_junction": self.from_j,
            "to_junction": self.to_j,
            "road_name": self.road_name,
            "road_class": self.road_class,
            "lanes": self.lanes,
            "length_m": round(self.length_m, 1),
            "free_flow_kmh": round(self.vf_kmh, 1),
        }


@dataclass
class Junction:
    junction_id: int
    key: str
    name: str
    name_mr: str
    lat: float
    lon: float
    legs: list[Leg] = field(default_factory=list)
    in_links: list[int] = field(default_factory=list)
    out_links: list[int] = field(default_factory=list)
    control: str = "uncontrolled"
    program: Program | None = None
    through_segments: frozenset[int] = frozenset()
    approach_label: dict[int, str] = field(default_factory=dict)  # in-link idx -> movement
    virtual_cross: bool = False

    @property
    def signalised(self) -> bool:
        return self.control in ("programmed", "assumed") and self.program is not None

    def leg_of(self, segment_id: int) -> Leg | None:
        for leg in self.legs:
            if leg.segment_id == segment_id:
                return leg
        return None

    def to_dict(self, links: list[Link] | None = None) -> dict:
        d = {
            "junction_id": self.junction_id,
            "key": self.key,
            "name": self.name,
            "name_mr": self.name_mr,
            "lat": self.lat,
            "lon": self.lon,
            "control": self.control,
            "legs": len(self.legs),
            "program": self.program.to_dict() if self.program else None,
            "virtual_cross_street": self.virtual_cross,
        }
        if links is not None:
            d["approaches"] = [
                {
                    "link_id": links[i].link_id,
                    "segment_id": links[i].segment_id,
                    "road_name": links[i].road_name,
                    "from_junction": links[i].from_j,
                    "movement": self.approach_label.get(i),
                }
                for i in self.in_links
            ]
        return d


@dataclass
class Network:
    junctions: dict[int, Junction]
    links: list[Link]
    source_path: str
    meta: dict

    _key_index: dict[str, int] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        self._key_index = {j.key: jid for jid, j in self.junctions.items() if j.key}
        self._link_index = {l.link_id: l.idx for l in self.links}
        self._seg_links: dict[int, list[int]] = {}
        for l in self.links:
            self._seg_links.setdefault(l.segment_id, []).append(l.idx)

    # -- lookups ---------------------------------------------------------
    def resolve_junction(self, ref: int | str) -> int:
        """A junction id from an int id, a numeric string or a landmark key."""
        if isinstance(ref, bool):
            raise NetworkError(f"unknown junction {ref!r}")
        if isinstance(ref, int) or (isinstance(ref, str) and ref.strip().isdigit()):
            jid = int(ref)
            if jid in self.junctions:
                return jid
        elif isinstance(ref, str) and ref.strip() in self._key_index:
            return self._key_index[ref.strip()]
        raise NetworkError(f"unknown junction {ref!r}")

    def links_of_segment(self, segment_id: int) -> list[int]:
        return list(self._seg_links.get(int(segment_id), []))

    def link_between(self, a: int, b: int) -> int | None:
        """The directed link from junction a to junction b, if any (shortest)."""
        best = None
        for i in self.junctions[a].out_links:
            if self.links[i].to_j == b and (best is None or self.links[i].length_m < self.links[best].length_m):
                best = i
        return best

    @property
    def signalised_ids(self) -> list[int]:
        return [jid for jid, j in sorted(self.junctions.items()) if j.signalised]

    def summary(self) -> dict:
        ctrl: dict[str, int] = {}
        for j in self.junctions.values():
            ctrl[j.control] = ctrl.get(j.control, 0) + 1
        return {
            "city": self.meta.get("city"),
            "schema": self.meta.get("schema"),
            "source_path": self.source_path,
            "junctions": len(self.junctions),
            "segments": len(self._seg_links),
            "directed_links": len(self.links),
            "total_km": round(sum(l.length_m for l in self.links) / 1000.0, 2),
            "control": ctrl,
            "programmed_junctions": [jid for jid, j in sorted(self.junctions.items()) if j.control == "programmed"],
            "assumed_junctions": [jid for jid, j in sorted(self.junctions.items()) if j.control == "assumed"],
            "virtual_cross_streets": [jid for jid, j in sorted(self.junctions.items()) if j.virtual_cross],
            "attribution": self.meta.get("attribution"),
        }


# ---------------------------------------------------------------------------
# Through legs (the platform's rule, re-stated)
# ---------------------------------------------------------------------------


def through_legs(legs: list[Leg]) -> frozenset[int]:
    """Segment ids of the junction's through pair (traffic-oracle's rule)."""
    if not legs:
        return frozenset()
    ordered = sorted(legs, key=lambda leg: leg.segment_id)
    best_score: float | None = None
    best_pair: tuple[int, int] | None = None
    for i, a in enumerate(ordered):
        for b in ordered[i + 1:]:
            deflection = 180.0 - angle_diff(a.bearing_deg, b.bearing_deg)
            if deflection > P.THROUGH_MAX_DEFLECTION_DEG:
                continue
            score = P.CLASS_RANK.get(a.road_class, 0) + P.CLASS_RANK.get(b.road_class, 0) - deflection / 45.0
            if best_score is None or score > best_score + 1e-9:
                best_score, best_pair = score, (a.segment_id, b.segment_id)
    if best_pair is not None:
        return frozenset(best_pair)
    top = max(ordered, key=lambda leg: (P.CLASS_RANK.get(leg.road_class, 0), -leg.segment_id))
    return frozenset({top.segment_id})


def _compass_axis(heading: float) -> str:
    h = float(heading) % 360.0
    if 315.0 <= h or h < 45.0 or 135.0 <= h < 225.0:
        return "NS"
    return "EW"


def assumed_program(through_class: str) -> Program:
    """The fixed-time template for a crossing with no program (labelled)."""
    cycle = P.ASSUMED_CYCLE_S.get(through_class, 110)
    usable = cycle - P.ASSUMED_LOST_S
    g_through = int(round(usable * P.ASSUMED_THROUGH_SHARE))
    return Program(
        cycle_sec=cycle,
        offset_sec=0,
        phases=((g_through, ("through",)), (usable - g_through, ("cross",))),
        source="twin-assumed template (MODELLED; no program in the network)",
    )


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def _repo_root() -> Path | None:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "cities").is_dir() and (parent / "services").is_dir():
            return parent
    return None


def default_network_path(city: str | None = None) -> Path:
    """SAJAG_TWIN_NETWORK, else the repo's City Pack network, else the evidence file."""
    env = os.environ.get("SAJAG_TWIN_NETWORK", "").strip()
    if env:
        return Path(env)
    city = city or os.environ.get("SAJAG_CITY", "mumbai").strip() or "mumbai"
    root = _repo_root()
    candidates = []
    if root is not None:
        candidates += [root / "cities" / city / "network.json", root / "scripts" / "data" / "osm_network.json"]
    candidates.append(Path("/app/cities") / city / "network.json")
    for c in candidates:
        if c.is_file():
            return c
    raise NetworkError("no network JSON found: set SAJAG_TWIN_NETWORK")


def load_network(path: str | Path | None = None, *, assume_signals: bool = True) -> Network:
    p = Path(path) if path else default_network_path()
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise NetworkError(f"cannot read network {p}: {exc}") from exc
    return network_from_dict(doc, source_path=display_source(p), assume_signals=assume_signals)


def display_source(path: str | Path) -> str:
    """The network file as an answer names it: ``cities/mumbai/network.json``.

    Never the absolute path (``/twin/network`` carried the host's user name).
    """
    parts = Path(path).parts
    if "cities" in parts:
        i = len(parts) - 1 - parts[::-1].index("cities")
        return "/".join(parts[i:])
    return Path(path).name


def _leg_bearing(seg: Mapping[str, Any], at_from: bool, jpos: dict[int, tuple[float, float]]) -> float:
    line = seg.get("line") or []
    pts = [tuple(map(float, xy[:2])) for xy in line] if len(line) >= 2 else []
    if not pts:
        a = jpos[int(seg["from_junction"])]
        b = jpos[int(seg["to_junction"])]
        pts = [a, b]
    if not at_from:
        pts = pts[::-1]
    lon0, lat0 = pts[0]
    target = pts[-1]
    for q in pts[1:]:
        if _dist_m(lon0, lat0, *q) >= 30.0:
            target = q
            break
    return _bearing(lon0, lat0, *target)


def network_from_dict(doc: Mapping[str, Any], *, source_path: str = "<dict>", assume_signals: bool = True) -> Network:
    jrows = doc.get("junctions") or []
    srows = doc.get("segments") or []
    if not jrows or not srows:
        raise NetworkError("network has no junctions or segments")

    junctions: dict[int, Junction] = {}
    jpos: dict[int, tuple[float, float]] = {}
    for j in jrows:
        jid = int(j["junction_id"])
        junctions[jid] = Junction(
            junction_id=jid,
            key=str(j.get("key") or ""),
            name=str(j.get("name") or f"Junction {jid}"),
            name_mr=str(j.get("name_mr") or ""),
            lat=float(j["lat"]),
            lon=float(j["lon"]),
        )
        jpos[jid] = (float(j["lon"]), float(j["lat"]))

    links: list[Link] = []
    for s in srows:
        sid = int(s["segment_id"])
        a, b = int(s["from_junction"]), int(s["to_junction"])
        if a not in junctions or b not in junctions or a == b:
            continue
        rc = str(s.get("road_class") or "secondary")
        cp = P.class_params(rc)
        lanes_total = max(1, int(s.get("lanes") or 2))
        oneway = bool(s.get("oneway"))
        lanes_dir = lanes_total if oneway else max(1, lanes_total // 2)
        length = float(s.get("length_m") or 0.0)
        if length <= 0:
            line = s.get("line") or []
            length = _polyline_length(line) if len(line) >= 2 else _dist_m(*jpos[a], *jpos[b])
        vf = float(s.get("speed_limit_kmh") or P.DEFAULT_SPEED_KMH) * P.FREE_FLOW_FACTOR
        name = str(s.get("road_name") or f"Segment {sid}")
        for direction, (u, v) in (("f", (a, b)), ("r", (b, a))):
            if direction == "r" and oneway:
                continue
            d0 = _dist_m(*jpos[u], P.CBD_LON, P.CBD_LAT)
            d1 = _dist_m(*jpos[v], P.CBD_LON, P.CBD_LAT)
            sign = 0.0 if abs(d1 - d0) < 150 else (1.0 if d1 > d0 else -1.0)
            links.append(
                Link(
                    idx=len(links),
                    link_id=f"{sid}:{direction}",
                    segment_id=sid,
                    direction=direction,
                    from_j=u,
                    to_j=v,
                    length_m=length,
                    lanes=lanes_dir,
                    vf_kmh=vf,
                    sat_pcu_h_lane=cp.sat_pcu_h_lane,
                    jam_pcu_km_lane=cp.jam_pcu_km_lane,
                    road_class=rc,
                    road_name=name,
                    cbd_sign=sign,
                )
            )
        junctions[a].legs.append(Leg(sid, rc, _leg_bearing(s, True, jpos), name))
        junctions[b].legs.append(Leg(sid, rc, _leg_bearing(s, False, jpos), name))

    for l in links:
        junctions[l.from_j].out_links.append(l.idx)
        junctions[l.to_j].in_links.append(l.idx)

    programs_raw = doc.get("signal_programs") or {}
    for jid, j in junctions.items():
        j.through_segments = through_legs(j.legs)
        raw = programs_raw.get(str(jid)) or programs_raw.get(jid)  # type: ignore[call-overload]
        if raw:
            j.control, j.program = "programmed", Program.from_dict(raw)
        elif len(j.legs) <= 1:
            j.control = "boundary"
        elif assume_signals and (
            "crossing" in j.name.lower()
            or (len(j.legs) >= 3 and sum(leg.road_class == "motorway" for leg in j.legs) < 2)
        ):
            # a named crossing, or a 3+ leg junction that is not a grade-separated
            # interchange (two or more flyover/ramp legs)
            through_cls = max(
                (leg.road_class for leg in j.legs if leg.segment_id in j.through_segments),
                key=lambda c: P.CLASS_RANK.get(c, 0),
                default="primary",
            )
            j.control, j.program = "assumed", assumed_program(through_cls)
        else:
            j.control = "uncontrolled"
        if j.program is None:
            continue
        labels = j.program.labels
        compass = bool(labels) and set(labels) <= {"NS", "EW"}
        major = labels[0] if labels else "through"
        minor = "cross" if "cross" in labels else next((m for m in labels if m != major), major)
        for i in j.in_links:
            leg = j.leg_of(links[i].segment_id)
            if compass and leg is not None:
                j.approach_label[i] = _compass_axis(leg.bearing_deg + 180.0)
            else:
                j.approach_label[i] = major if links[i].segment_id in j.through_segments else minor
        served = set(j.approach_label.values())
        j.virtual_cross = (not compass) and minor != major and minor not in served

    meta = {
        "schema": doc.get("schema") or "osm_network (evidence)",
        "city": doc.get("city") or (doc.get("about", "")[:40] if isinstance(doc.get("about"), str) else None),
        "about": doc.get("about"),
        "attribution": doc.get("attribution"),
        "osm_base": doc.get("osm_base"),
    }
    return Network(junctions=junctions, links=links, source_path=source_path, meta=meta)
