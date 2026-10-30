"""Small geometry helpers (no GIS dependency)."""

from __future__ import annotations

import math

__all__ = ["MUMBAI", "haversine_km", "bearing_deg", "compass", "point_in_ring", "decimate"]

#: the city centre (cities/mumbai/city.json "centre": Dadar / Matunga)
MUMBAI = (19.0176, 72.8562)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


def bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    x = math.sin(dl) * math.cos(p2)
    y = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


_POINTS = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]


def compass(deg: float) -> str:
    return _POINTS[int((deg % 360) / 22.5 + 0.5) % 16]


def point_in_ring(lon: float, lat: float, ring: list[list[float]]) -> bool:
    """Ray casting on a lon/lat ring (fine for buffers far from the poles and the antimeridian)."""
    inside = False
    n = len(ring)
    for i in range(n):
        x1, y1 = ring[i][0], ring[i][1]
        x2, y2 = ring[(i + 1) % n][0], ring[(i + 1) % n][1]
        if (y1 > lat) != (y2 > lat):
            x = x1 + (lat - y1) * (x2 - x1) / ((y2 - y1) or 1e-12)
            if lon < x:
                inside = not inside
    return inside


def decimate(ring: list[list[float]], max_points: int = 360, nd: int = 3) -> list[list[float]]:
    step = max(1, math.ceil(len(ring) / max_points))
    out = [[round(p[0], nd), round(p[1], nd)] for p in ring[::step]]
    if out and out[0] != out[-1]:
        out.append(out[0])
    return out
