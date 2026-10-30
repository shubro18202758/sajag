"""The Mumbai road network the forecasts are made for.

Source order: a city-pack ``network.json`` (``cities/mumbai/network.json`` in the repo, or
``SAJAG_FORECAST_CITY_DIR``), else the snapshot bundled with the package (``data/mumbai_network.json``,
the junctions and segments of the network stream's committed v1 ids: 72 junctions, 86 segments —
© OpenStreetMap contributors, ODbL 1.0).

The graph is directed: a two-way segment is two links, a one-way segment one. ``alternative_path`` finds
the shortest detour between a segment's end junctions that does not use the segment itself — the
diversion a pre-emptive proposal names.
"""

from __future__ import annotations

import heapq
import json
import math
from dataclasses import dataclass, field
from pathlib import Path

__all__ = ["Junction", "Segment", "Network", "load_network", "haversine_m"]

_BUNDLED = Path(__file__).with_name("data") / "mumbai_network.json"


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371008.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


@dataclass(frozen=True)
class Junction:
    junction_id: int
    key: str
    name: str
    name_mr: str
    lat: float
    lon: float


@dataclass(frozen=True)
class Segment:
    segment_id: int
    road_name: str
    from_junction: int
    to_junction: int
    oneway: bool
    road_class: str
    lanes: int
    speed_limit_kmh: float
    length_m: float
    line: tuple[tuple[float, float], ...] = field(default=())  # (lon, lat)

    @property
    def midpoint(self) -> tuple[float, float]:
        """(lat, lon) of the line's middle vertex (or the mean of the ends)."""
        if not self.line:
            return (0.0, 0.0)
        lon, lat = self.line[len(self.line) // 2]
        return (lat, lon)


@dataclass
class Network:
    junctions: dict[int, Junction]
    segments: dict[int, Segment]
    source: str
    attribution: str

    def junction_name(self, jid: int) -> str:
        j = self.junctions.get(jid)
        return j.name if j else f"junction {jid}"

    def describe(self, sid: int) -> str:
        """'<to-junction name> approach (<road name>)' — where a queue on the segment forms."""
        s = self.segments[sid]
        return f"{self.junction_name(s.to_junction)} ({s.road_name})"

    def links(self) -> list[tuple[int, int, int, float]]:
        """Directed links (from, to, segment_id, length_m)."""
        out = []
        for s in self.segments.values():
            out.append((s.from_junction, s.to_junction, s.segment_id, s.length_m))
            if not s.oneway:
                out.append((s.to_junction, s.from_junction, s.segment_id, s.length_m))
        return out

    def alternative_path(
        self, sid: int, avoid: set[int] | None = None, max_detour_ratio: float = 4.0
    ) -> list[int] | None:
        """Shortest path from the segment's start to its end junction without it (and without
        ``avoid`` when possible). Returns segment ids, or None when there is no reasonable detour."""
        seg = self.segments[sid]
        banned = {sid}
        for extra in (avoid or set(), set()):
            path = self._dijkstra(seg.from_junction, seg.to_junction, banned | (extra - {sid}))
            if path is not None:
                length = sum(self.segments[p].length_m for p in path)
                # the curated network is arterial-only, so detours are long: the proposal states the
                # detour length and the officer judges it
                if length <= max_detour_ratio * max(seg.length_m, 300.0) + 8000.0:
                    return path
        return None

    def _dijkstra(self, src: int, dst: int, banned: set[int]) -> list[int] | None:
        adj: dict[int, list[tuple[int, int, float]]] = {}
        for a, b, s, w in self.links():
            if s in banned:
                continue
            adj.setdefault(a, []).append((b, s, w))
        dist = {src: 0.0}
        prev: dict[int, tuple[int, int]] = {}
        pq = [(0.0, src)]
        while pq:
            d, u = heapq.heappop(pq)
            if u == dst:
                break
            if d > dist.get(u, math.inf):
                continue
            for v, s, w in adj.get(u, []):
                nd = d + w
                if nd < dist.get(v, math.inf):
                    dist[v] = nd
                    prev[v] = (u, s)
                    heapq.heappush(pq, (nd, v))
        if dst not in dist:
            return None
        path: list[int] = []
        node = dst
        while node != src:
            u, s = prev[node]
            path.append(s)
            node = u
        return list(reversed(path))


def _parse(d: dict, source: str) -> Network:
    junctions = {
        int(j["junction_id"]): Junction(
            junction_id=int(j["junction_id"]),
            key=str(j.get("key") or j["junction_id"]),
            name=str(j.get("name") or j.get("key") or j["junction_id"]),
            name_mr=str(j.get("name_mr") or ""),
            lat=float(j["lat"]),
            lon=float(j["lon"]),
        )
        for j in d.get("junctions", [])
    }
    segments = {}
    for s in d.get("segments", []):
        line = tuple((float(p[0]), float(p[1])) for p in (s.get("line") or []))
        segments[int(s["segment_id"])] = Segment(
            segment_id=int(s["segment_id"]),
            road_name=str(s.get("road_name") or f"segment {s['segment_id']}"),
            from_junction=int(s["from_junction"]),
            to_junction=int(s["to_junction"]),
            oneway=bool(s.get("oneway", False)),
            road_class=str(s.get("road_class") or "secondary"),
            lanes=int(s.get("lanes") or 2),
            speed_limit_kmh=float(s.get("speed_limit_kmh") or 40),
            length_m=float(s.get("length_m") or 500.0),
            line=line,
        )
    return Network(junctions=junctions, segments=segments, source=source,
                   attribution=str(d.get("attribution") or "© OpenStreetMap contributors, ODbL 1.0"))


def display_source(path: Path) -> str:
    """The network file as an answer names it: ``cities/mumbai/network.json``.

    Never the absolute path — it went out in public, unauthenticated answers
    (``/hydro/nowcast``, ``/forecast/segments``) carrying the host's user name.
    """
    parts = Path(path).parts
    if "cities" in parts:
        i = len(parts) - 1 - parts[::-1].index("cities")
        return "/".join(parts[i:])
    return Path(path).name


def load_network(city_dir: Path | None = None) -> Network:
    if city_dir is not None and (city_dir / "network.json").is_file():
        path = city_dir / "network.json"
        return _parse(json.loads(path.read_text(encoding="utf-8")), source=display_source(path))
    d = json.loads(_BUNDLED.read_text(encoding="utf-8"))
    return _parse(d, source=f"bundled snapshot: {d.get('source', _BUNDLED.name)}")
