"""Active-fire hotspots in and around Greater Mumbai (NASA FIRMS): places, never people.

**What.** NASA's Fire Information for Resource Management System publishes satellite thermal anomalies within
about three hours of each overpass: VIIRS on Suomi NPP, NOAA-20 and NOAA-21 (375 m pixels) and MODIS on Terra and
Aqua (1 km). A hotspot is a pixel that was hotter than its surroundings when the satellite passed: a landfill fire
(the Deonar and Kanjurmarg dumping grounds), a market or warehouse fire, a factory flare or stubble burning. It is never a confirmed fire and never says
who or what is burning. Label: LIVE (NASA FIRMS), each point "satellite thermal anomaly, not a confirmed fire".

**Routes.**

* No key (default, live): the public FIRMS "South Asia, last 24 hours" CSV files for the four instruments
  (``/data/active_fire/<product>/csv/<file>_South_Asia_24h.csv``, about 0.7 MB together), filtered here to the
  Mumbai box. Checked from this box on 29 Oct 2026: all four answer 200.
* With ``FIRMS_MAP_KEY`` (free, https://firms.modaps.eosdis.nasa.gov/api/map_key/): the FIRMS area API for the box
  itself, last 2 days, the same four instruments: a smaller answer and a longer window.

Polite: one refresh per 3 hours at most (FIRMS updates every few hours), at most 16 a day.

**The box** (:data:`METRO_BBOX`) is an envelope of Greater Mumbai (cities/mumbai/city.json "bbox", 18.89–19.28 N,
72.77–72.99 E) widened by a few kilometres to take in Thane creek, Trombay and the Navi Mumbai shore, approximate. Each
hotspot is named by the nearest landmark in ``cities/mumbai/landmarks.json`` within 5 km.
"""

from __future__ import annotations

import csv
import io
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx

from cityfeeds.geo import haversine_km

__all__ = ["METRO_BBOX", "PUBLIC_FILES", "AREA_SOURCES", "fetch_fires_public", "fetch_fires_area", "parse_csv",
           "fires_view"]

#: (south, west, north, east): Greater Mumbai, widened a little (approximate; module docstring)
METRO_BBOX = (18.85, 72.75, 19.32, 73.05)

_BASE = "https://firms.modaps.eosdis.nasa.gov"
#: instrument → public South Asia 24-h file (no key)
PUBLIC_FILES = {
    "VIIRS S-NPP": f"{_BASE}/data/active_fire/suomi-npp-viirs-c2/csv/SUOMI_VIIRS_C2_South_Asia_24h.csv",
    "VIIRS NOAA-20": f"{_BASE}/data/active_fire/noaa-20-viirs-c2/csv/J1_VIIRS_C2_South_Asia_24h.csv",
    "VIIRS NOAA-21": f"{_BASE}/data/active_fire/noaa-21-viirs-c2/csv/J2_VIIRS_C2_South_Asia_24h.csv",
    "MODIS": f"{_BASE}/data/active_fire/modis-c6.1/csv/MODIS_C6_1_South_Asia_24h.csv",
}
#: instrument → FIRMS area-API source name (keyed)
AREA_SOURCES = {"VIIRS S-NPP": "VIIRS_SNPP_NRT", "VIIRS NOAA-20": "VIIRS_NOAA20_NRT",
                "VIIRS NOAA-21": "VIIRS_NOAA21_NRT", "MODIS": "MODIS_NRT"}
_MAX_BYTES = 8 * 1024 * 1024

_LANDMARKS: list[dict[str, Any]] | None = None


def _landmarks() -> list[dict[str, Any]]:
    global _LANDMARKS
    if _LANDMARKS is None:
        here = Path(__file__).resolve()
        path = next((p / "cities" / "mumbai" / "landmarks.json" for p in here.parents
                     if (p / "cities" / "mumbai" / "landmarks.json").is_file()), None)
        try:
            data = json.loads(path.read_text(encoding="utf-8")) if path else {}
        except (OSError, ValueError):
            data = {}
        _LANDMARKS = [lm for lm in data.get("landmarks", []) if isinstance(lm, dict)
                      and isinstance(lm.get("lat"), (int, float)) and isinstance(lm.get("lon"), (int, float))]
    return _LANDMARKS


def _in_box(lat: float, lon: float) -> bool:
    s, w, n, e = METRO_BBOX
    return s <= lat <= n and w <= lon <= e


def parse_csv(text: str, instrument: str) -> list[dict[str, Any]]:
    """FIRMS CSV rows inside the box: position, time (UTC), instrument, confidence, FRP (MW), day/night."""
    out = []
    for r in csv.DictReader(io.StringIO(text)):
        try:
            lat, lon = float(r["latitude"]), float(r["longitude"])
        except (KeyError, TypeError, ValueError):
            continue
        if not _in_box(lat, lon):
            continue
        hhmm = str(r.get("acq_time") or "").zfill(4)
        try:
            at = datetime.strptime(f"{r.get('acq_date')} {hhmm}", "%Y-%m-%d %H%M").replace(tzinfo=UTC).isoformat()
        except ValueError:
            at = None
        try:
            frp = round(float(r.get("frp") or ""), 1)
        except ValueError:
            frp = None
        out.append({"lat": round(lat, 5), "lon": round(lon, 5), "at": at, "instrument": instrument,
                    "confidence": str(r.get("confidence") or "")[:8] or None, "frp_mw": frp,
                    "daynight": str(r.get("daynight") or "")[:1] or None})
    return out


async def _get_csv(client: httpx.AsyncClient, url: str) -> str:
    r = await client.get(url)
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code} from FIRMS")
    if len(r.content) > _MAX_BYTES:
        raise RuntimeError("FIRMS answer larger than the cap")
    text = r.text
    if not text.startswith("latitude,"):
        raise RuntimeError("FIRMS answered something that is not its CSV")
    return text


async def fetch_fires_public(client: httpx.AsyncClient) -> dict[str, Any]:
    """The keyless route: the four South Asia 24-h files, kept to the box. A file that fails is reported, not fatal."""
    rows: list[dict[str, Any]] = []
    status: dict[str, str] = {}
    for inst, url in PUBLIC_FILES.items():
        try:
            rows += parse_csv(await _get_csv(client, url), inst)
            status[inst] = "read"
        except (httpx.HTTPError, RuntimeError) as exc:
            status[inst] = f"failed: {type(exc).__name__}: {exc}"[:120]
    if not any(v == "read" for v in status.values()):
        raise RuntimeError("no FIRMS file answered")
    return {"route": "public South Asia 24-h files (no key)", "window_h": 24, "files": status, "hotspots": rows}


async def fetch_fires_area(client: httpx.AsyncClient, map_key: str, days: int = 2) -> dict[str, Any]:
    """The keyed route: the FIRMS area API for the box (``/api/area/csv/<key>/<source>/<w,s,e,n>/<days>``)."""
    s, w, n, e = METRO_BBOX
    rows: list[dict[str, Any]] = []
    status: dict[str, str] = {}
    for inst, src in AREA_SOURCES.items():
        url = f"{_BASE}/api/area/csv/{map_key}/{src}/{w},{s},{e},{n}/{days}"
        try:
            rows += parse_csv(await _get_csv(client, url), inst)
            status[inst] = "read"
        except (httpx.HTTPError, RuntimeError) as exc:
            # never the URL: it carries the key
            status[inst] = f"failed: {type(exc).__name__}"
    if not any(v == "read" for v in status.values()):
        raise RuntimeError("the FIRMS area API answered for no instrument (is FIRMS_MAP_KEY valid?)")
    return {"route": "FIRMS area API (FIRMS_MAP_KEY)", "window_h": 24 * days, "files": status, "hotspots": rows}


def _nearest_landmark(lat: float, lon: float) -> dict[str, Any] | None:
    best = None
    for lm in _landmarks():
        d = haversine_km(lat, lon, float(lm["lat"]), float(lm["lon"]))
        if d <= 5.0 and (best is None or d < best[0]):
            best = (d, lm)
    if best is None:
        return None
    d, lm = best
    return {"id": lm.get("id"), "name": lm.get("name") or lm.get("en"), "name_mr": lm.get("mr") or lm.get("name_mr"),
            "distance_km": round(d, 2)}


def fires_view(raw: dict[str, Any] | None, now: datetime | None = None) -> dict[str, Any]:
    """GeoJSON of the hotspots in the box, newest first, each with its nearest landmark."""
    now = now or datetime.now(UTC)
    feats = []
    for h in sorted((raw or {}).get("hotspots") or [], key=lambda x: x.get("at") or "", reverse=True):
        props = {**h, "kind": "hotspot", "near": _nearest_landmark(h["lat"], h["lon"]),
                 "label": "LIVE", "note": "satellite thermal anomaly, not a confirmed fire"}
        props.pop("lat", None), props.pop("lon", None)
        feats.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [h["lon"], h["lat"]]},
                      "properties": props})
    recent = [f for f in feats if f["properties"].get("at")
              and datetime.fromisoformat(f["properties"]["at"]) >= now - timedelta(hours=24)]
    return {
        "type": "FeatureCollection",
        "features": feats,
        "label": "LIVE" if raw is not None else "UNAVAILABLE",
        "what": "NASA FIRMS satellite thermal anomalies (VIIRS 375 m, MODIS 1 km) in the Mumbai "
                "box: places only, never who; a hotspot is not a confirmed fire",
        "bbox": {"south": METRO_BBOX[0], "west": METRO_BBOX[1], "north": METRO_BBOX[2], "east": METRO_BBOX[3],
                 "note": "Greater Mumbai, widened a little (approximate)"},
        "route": (raw or {}).get("route"),
        "window_h": (raw or {}).get("window_h"),
        "files": (raw or {}).get("files"),
        "count": len(feats),
        "count_24h": len(recent),
        "attribution": "NASA FIRMS (LANCE), VIIRS and MODIS active fire products; public domain",
    }
