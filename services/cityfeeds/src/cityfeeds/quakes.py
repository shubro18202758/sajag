"""Earthquakes within 500 km of Mumbai from the USGS catalogue (LIVE, third-party open feed).

The USGS FDSN event web service (https://earthquake.usgs.gov/fdsnws/event/1/) is asked server-side for the last
365 days, magnitude ≥ 2.5, within ``quake_radius_km`` of the city centre — one small GeoJSON answer per hour. Mumbai
lies in seismic zone III (IS 1893 (Part 1): 2016, moderate damage risk); felt events nearby have come from the Koyna
region and the Palghar (Dahanu) swarm of 2018–19. The catalogue's completeness over the region is ≈ M4, so a
quiet month is "no event in the catalogue", never "no tremor".
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from cityfeeds.geo import MUMBAI, bearing_deg, compass, haversine_km

__all__ = ["fetch_quakes", "quakes_view"]


async def fetch_quakes(client: httpx.AsyncClient, url: str, radius_km: float, now: datetime | None = None) -> Any:
    now = now or datetime.now(UTC)
    params = {"format": "geojson", "latitude": MUMBAI[0], "longitude": MUMBAI[1], "maxradiuskm": radius_km,
              "starttime": (now - timedelta(days=365)).strftime("%Y-%m-%d"), "minmagnitude": 2.5, "orderby": "time"}
    r = await client.get(url, params=params)
    r.raise_for_status()
    return r.json()


def quakes_view(raw: dict | None, radius_km: float, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    klat, klon = MUMBAI
    feats = []
    for f in (raw or {}).get("features", []):
        p = f.get("properties") or {}
        lon, lat, depth = (f.get("geometry") or {}).get("coordinates", [None, None, None])[:3]
        if lat is None:
            continue
        d = haversine_km(klat, klon, lat, lon)
        if d > radius_km:  # the server filters already; the check keeps a widened query honest
            continue
        at = datetime.fromtimestamp(p.get("time", 0) / 1000, tz=UTC)
        feats.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [lon, lat, depth]},
                      "properties": {"id": f.get("id"), "mag": p.get("mag"), "mag_type": p.get("magType"),
                                     "place": p.get("place"), "time": at.isoformat(), "depth_km": depth,
                                     "distance_km": round(d), "bearing": compass(bearing_deg(klat, klon, lat, lon)),
                                     "url": p.get("url"), "felt": p.get("felt"), "alert": p.get("alert")}})
    feats.sort(key=lambda f: f["properties"]["time"], reverse=True)
    last30 = [f for f in feats if f["properties"]["time"] >= (now - timedelta(days=30)).isoformat()]
    strongest = max(feats, key=lambda f: f["properties"]["mag"] or 0, default=None)
    return {
        "type": "FeatureCollection", "features": feats, "label": "LIVE",
        "what": f"USGS catalogue, M ≥ 2.5 within {radius_km:.0f} km of Mumbai, last 365 days",
        "radius_km": radius_km, "count_365d": len(feats), "count_30d": len(last30),
        "latest": feats[0]["properties"] if feats else None,
        "latest_30d": last30[0]["properties"] if last30 else None,
        "strongest_365d": strongest["properties"] if strongest else None,
        "zone": "Seismic zone III (IS 1893 (Part 1): 2016)",
        "note": "catalogue completeness over the region is about M4; a quiet month means none catalogued",
        "sources": {"usgs": {"publisher": "U.S. Geological Survey, Earthquake Hazards Program",
                             "url": "https://earthquake.usgs.gov/fdsnws/event/1/"}},
    }
