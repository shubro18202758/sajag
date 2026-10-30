"""OBSERVED air quality at Mumbai's monitoring stations, from three free keyed services.

The air layer's own values (``air.py``) are the CAMS model's, labelled MODELLED. When any of the services below has
its key, the stations' own measurements are added beside them, labelled OBSERVED, matched to the ten sites in
``air.STATIONS`` by distance (within :data:`MATCH_KM`) or by name. Without a key a service makes no call and says
``needs <ENV_VAR>``; the modelled values stay as they are, labelled MODELLED.

* **CPCB via data.gov.in** (``DATA_GOV_IN_API_KEY``; resource ``3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69``, "Real time
  Air Quality Index from various locations"). One row per station and pollutant with ``avg_value`` (the CPCB
  bulletin's average), ``min_value``, ``max_value`` and ``last_update`` (IST). PM2.5 and PM10 averages give the
  National AQI here with the same breakpoints as ``air.naqi`` (still only two pollutants, so INDICATIVE).
* **WAQI** (``WAQI_TOKEN``; ``/v2/map/bounds``, and ``/search/?keyword=mumbai`` when the bounds query lists nothing
  for the box, as it does for Mumbai on 30 Oct 2026): the World Air Quality Index project's AQI per station, on the US
  EPA scale WAQI publishes. For Mumbai WAQI lists the same CPCB/MPCB stations, matched by name or distance. Shown as
  WAQI's number, never as the National AQI.
* **OpenAQ v3** (``OPENAQ_API_KEY``, sent as the ``X-API-Key`` header): the stations in the box
  (``/v3/locations?bbox=``), each one's latest PM2.5 and PM10 (``/v3/locations/{id}/latest``) and the last 24 hours
  of those two sensors (``/v3/sensors/{id}/hours``). OpenAQ's provider for these stations is CPCB, so this is the
  same CAAQMS data data.gov.in republishes: with at least :data:`MIN_HOURS_24H` hourly values (CPCB's rule for a
  24-hour average) the 24-hour means give the indicative National AQI, as the CPCB averages do. OpenAQ keeps a
  retired sensor's last value beside its replacement's, so per pollutant only the newest reading counts, and only
  when it is less than :data:`FRESH_H` hours old and above zero.

Every value is the station's own reported number with its time; nothing is interpolated or invented.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from cityfeeds.air import STATIONS, naqi
from cityfeeds.geo import haversine_km

__all__ = ["CPCB_URL", "WAQI_URL", "OPENAQ_URL", "MATCH_KM", "BOX", "FRESH_H", "MIN_HOURS_24H", "fetch_cpcb",
           "fetch_waqi", "fetch_openaq", "parse_cpcb", "parse_waqi", "parse_openaq", "match_stations"]

CPCB_URL = "https://api.data.gov.in/resource/3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69"
WAQI_URL = "https://api.waqi.info/v2/map/bounds"
WAQI_SEARCH_URL = "https://api.waqi.info/search/"
OPENAQ_URL = "https://api.openaq.org/v3"
#: an upstream station within this distance of a site is that site (the sites' own coordinates are ±1 km)
MATCH_KM = 2.0
#: (south, west, north, east): Greater Mumbai (cities/mumbai/city.json "bbox")
BOX = (18.89, 72.77, 19.28, 72.99)
_MAX_OPENAQ_LOCATIONS = 20
#: a reading older than this is not the station's current value (OpenAQ still lists sensors retired in 2022)
FRESH_H = 24
#: CPCB's rule for a 24-hour average: at least 16 of its hourly values
MIN_HOURS_24H = 16


def _iso(t: datetime) -> str:
    return t.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _num(x: Any) -> float | None:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if v == v else None  # NaN → None


def _norm(s: str) -> str:
    return re.sub(r"[^a-z]", "", s.lower())


#: words in an upstream station name that identify a site (CPCB writes "Colaba, Mumbai - MPCB"). Order matters:
#: "Bandra Kurla Complex" is tried before "Kurla"
_NAME_KEYS = {
    "colaba": ("colaba",), "worli": ("worli",), "byculla": ("byculla",), "sewri": ("sewri",), "sion": ("sionmumbai",),
    "bkc": ("bandrakurlacomplex",), "kurla": ("kurla",), "chembur": ("chembur",), "deonar": ("deonar",),
    "chakala_andheri": ("chakala",), "powai": ("powai",), "borivali": ("borivali",),
}


def _site_for(name: str, lat: float | None, lon: float | None) -> tuple[str | None, float | None]:
    """The site an upstream station is (by name first, then by distance), with the distance when known."""
    n = _norm(name or "")
    by_name = next((sid for sid, keys in _NAME_KEYS.items() if any(k in n for k in keys)), None)
    dist = {s["id"]: haversine_km(lat, lon, s["lat"], s["lon"]) for s in STATIONS} if (
        lat is not None and lon is not None) else {}
    if by_name:
        return by_name, (round(dist[by_name], 2) if by_name in dist else None)
    if dist:
        sid = min(dist, key=dist.get)
        if dist[sid] <= MATCH_KM:
            return sid, round(dist[sid], 2)
    return None, None


# ── CPCB (data.gov.in) ──────────────────────────────────────────────────────────────────────────────────────────


async def fetch_cpcb(client: httpx.AsyncClient, api_key: str) -> dict[str, Any]:
    out: list[dict[str, Any]] = []
    for city in ("Mumbai",):
        r = await client.get(CPCB_URL, params={"api-key": api_key, "format": "json", "limit": 500,
                                               "filters[city]": city})
        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code} from data.gov.in")
        body = r.json()
        if not isinstance(body, dict) or not isinstance(body.get("records"), list):
            raise RuntimeError("data.gov.in answered without records")
        out += body["records"]
    return {"records": out}


def parse_cpcb(raw: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    """Per site: the CPCB station's pollutant averages, its time and the indicative National AQI from PM."""
    by_station: dict[str, dict[str, Any]] = {}
    for rec in (raw or {}).get("records") or []:
        if not isinstance(rec, dict):
            continue
        name = str(rec.get("station") or "")
        st = by_station.setdefault(name, {"name": name, "lat": _num(rec.get("latitude")),
                                          "lon": _num(rec.get("longitude")), "at": rec.get("last_update"),
                                          "pollutants": {}})
        pid = str(rec.get("pollutant_id") or "").upper().replace(".", "")
        # the resource has used both spellings: avg_value / pollutant_avg (min, max likewise)
        st["pollutants"][pid] = {k: _num(rec.get(f"{k}_value", rec.get(f"pollutant_{k}"))) for k in ("avg", "min", "max")}
    sites: dict[str, dict[str, Any]] = {}
    for st in by_station.values():
        sid, dist = _site_for(st["name"], st["lat"], st["lon"])
        if sid is None:
            continue
        pm25 = (st["pollutants"].get("PM25") or {}).get("avg")
        pm10 = (st["pollutants"].get("PM10") or {}).get("avg")
        sites[sid] = {"provider": "cpcb", "label": "OBSERVED", "upstream_name": st["name"], "distance_km": dist,
                      "at": st["at"], "at_tz": "IST", "pm25": pm25, "pm10": pm10,
                      "pollutants": st["pollutants"], "naqi": naqi(pm25, pm10),
                      "source": "CPCB CAAQMS via data.gov.in (station averages as CPCB publishes them)"}
    return sites


# ── WAQI ────────────────────────────────────────────────────────────────────────────────────────────────────────


async def fetch_waqi(client: httpx.AsyncClient, token: str) -> dict[str, Any]:
    s, w, n, e = BOX
    r = await client.get(WAQI_URL, params={"latlng": f"{s},{w},{n},{e}", "networks": "all", "token": token})
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code} from WAQI")
    body = r.json()
    if not isinstance(body, dict) or body.get("status") != "ok":
        raise RuntimeError(f"WAQI: {str((body or {}).get('data') if isinstance(body, dict) else body)[:60]}")
    if body.get("data"):
        return body
    # the bounds query lists no Mumbai station (30 Oct 2026); WAQI's keyword search does
    r = await client.get(WAQI_SEARCH_URL, params={"keyword": "mumbai", "token": token})
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code} from WAQI search")
    found = r.json()
    if not isinstance(found, dict) or found.get("status") != "ok":
        raise RuntimeError("WAQI search answered without data")
    rows = []
    for x in found.get("data") or []:
        if not isinstance(x, dict):
            continue
        st, geo = x.get("station") or {}, (x.get("station") or {}).get("geo") or [None, None]
        t = x.get("time") or {}
        rows.append({"lat": geo[0], "lon": geo[1], "uid": x.get("uid"), "aqi": x.get("aqi"),
                     "station": {"name": st.get("name"), "time": t.get("stime") if isinstance(t, dict) else t}})
    return {"status": "ok", "data": rows, "via": "search"}


def parse_waqi(raw: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    sites: dict[str, dict[str, Any]] = {}
    for st in (raw or {}).get("data") or []:
        if not isinstance(st, dict):
            continue
        aqi = _num(st.get("aqi"))  # WAQI writes "-" for a station with no current value
        info = st.get("station") or {}
        sid, dist = _site_for(str(info.get("name") or ""), _num(st.get("lat")), _num(st.get("lon")))
        if sid is None or aqi is None:
            continue
        sites[sid] = {"provider": "waqi", "label": "OBSERVED", "upstream_name": str(info.get("name") or "")[:120],
                      "distance_km": dist, "at": info.get("time"), "waqi_aqi": int(aqi), "scale": "US EPA (WAQI)",
                      "source": "World Air Quality Index project (aqicn.org): the CPCB/MPCB station WAQI lists, "
                                "on WAQI's US EPA scale"}
    return sites


# ── OpenAQ v3 ───────────────────────────────────────────────────────────────────────────────────────────────────


def _pm_sensors(loc: dict[str, Any]) -> dict[str, str]:
    """Sensor id → parameter name (pm25 or pm10) from the location's own sensor list."""
    out = {}
    for s in loc.get("sensors") or []:
        p = str(((s.get("parameter") or {}) if isinstance(s, dict) else {}).get("name") or "")
        if p in ("pm25", "pm10"):
            out[str(s.get("id"))] = p
    return out


def _newest_pm(loc: dict[str, Any], latest: list[Any], fresh: str) -> dict[str, tuple[str, float, str]]:
    """Per pollutant, the newest reading (time, value, sensor id) that is fresh and above zero."""
    pm = _pm_sensors(loc)
    out: dict[str, tuple[str, float, str]] = {}
    for m in latest:
        if not isinstance(m, dict):
            continue
        p, v, t = pm.get(str(m.get("sensorsId"))), _num(m.get("value")), (m.get("datetime") or {}).get("utc")
        # a zero is a stopped analyser, never clean air; an old value is a retired sensor's last one
        if p is None or v is None or v <= 0 or not isinstance(t, str) or t < fresh:
            continue
        if p not in out or t > out[p][0]:
            out[p] = (t, v, str(m.get("sensorsId")))
    return out


async def fetch_openaq(client: httpx.AsyncClient, api_key: str, now: datetime | None = None) -> dict[str, Any]:
    h = {"X-API-Key": api_key}
    now = now or datetime.now(UTC)
    fresh, since = _iso(now - timedelta(hours=FRESH_H)), _iso(now - timedelta(hours=24))
    s, w, n, e = BOX
    r = await client.get(f"{OPENAQ_URL}/locations", params={"bbox": f"{w},{s},{e},{n}", "limit": 100}, headers=h)
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code} from OpenAQ")
    locs = [loc for loc in (r.json().get("results") or []) if isinstance(loc, dict)]
    wanted = []
    for loc in locs:
        c = loc.get("coordinates") or {}
        sid, _d = _site_for(str(loc.get("name") or ""), _num(c.get("latitude")), _num(c.get("longitude")))
        last = (loc.get("datetimeLast") or {}).get("utc")
        if sid is not None and not (isinstance(last, str) and last < fresh):  # a station silent for a day: no calls
            wanted.append(loc)
    latest, hours = {}, {}
    for loc in wanted[:_MAX_OPENAQ_LOCATIONS]:
        lr = await client.get(f"{OPENAQ_URL}/locations/{int(loc['id'])}/latest", headers=h)
        if lr.status_code != 200:
            continue
        latest[str(loc["id"])] = lr.json().get("results") or []
        # the last 24 hours of the sensors that are reporting now, for the 24-hour means
        for _t, _v, sensor in _newest_pm(loc, latest[str(loc["id"])], fresh).values():
            hr = await client.get(f"{OPENAQ_URL}/sensors/{int(sensor)}/hours",
                                  params={"datetime_from": since, "limit": 48}, headers=h)
            if hr.status_code == 200:
                hours[sensor] = hr.json().get("results") or []
    return {"locations": wanted, "latest": latest, "hours": hours, "now": _iso(now)}


def _mean_24h(rows: list[Any]) -> tuple[float | None, int]:
    """The 24-hour mean of a sensor's hourly values and how many hours it rests on (None below CPCB's 16)."""
    vals = [v for v in (_num(x.get("value")) for x in rows if isinstance(x, dict)) if v is not None and v > 0]
    return (round(sum(vals) / len(vals), 1) if len(vals) >= MIN_HOURS_24H else None), len(vals)


def parse_openaq(raw: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    raw = raw or {}
    try:
        now = datetime.fromisoformat(str(raw.get("now")).replace("Z", "+00:00"))
    except ValueError:
        now = datetime.now(UTC)
    fresh = _iso(now - timedelta(hours=FRESH_H))
    sites: dict[str, dict[str, Any]] = {}
    for loc in raw.get("locations") or []:
        c = loc.get("coordinates") or {}
        sid, dist = _site_for(str(loc.get("name") or ""), _num(c.get("latitude")), _num(c.get("longitude")))
        if sid is None:
            continue
        newest = _newest_pm(loc, raw.get("latest", {}).get(str(loc.get("id")), []), fresh)
        if not newest:
            continue
        at = max(t for t, _v, _s in newest.values())
        if sid in sites and sites[sid]["at"] >= at:  # two OpenAQ locations for one site: the one reporting latest
            continue
        means = {p: _mean_24h(raw.get("hours", {}).get(sensor) or []) for p, (_t, _v, sensor) in newest.items()}
        pm25_24h, pm10_24h = (means.get("pm25") or (None, 0))[0], (means.get("pm10") or (None, 0))[0]
        # OpenAQ's provider for the CAAQMS stations is CPCB: their 24-hour means are the National AQI's own inputs
        is_cpcb = str((loc.get("provider") or {}).get("name") or "").upper() == "CPCB"
        sites[sid] = {"provider": "openaq", "label": "OBSERVED", "upstream_name": str(loc.get("name") or "")[:120],
                      "upstream_provider": str((loc.get("provider") or {}).get("name") or "")[:40] or None,
                      "distance_km": dist, "at": at, "at_tz": "UTC",
                      "pm25_latest": round(newest["pm25"][1], 1) if "pm25" in newest else None,
                      "pm10_latest": round(newest["pm10"][1], 1) if "pm10" in newest else None,
                      "pm25_24h": pm25_24h, "pm10_24h": pm10_24h, "hours_24h": {p: m[1] for p, m in means.items()},
                      "naqi": naqi(pm25_24h, pm10_24h) if is_cpcb else None,
                      "averaging": f"latest value; 24-hour means of the hourly values (at least {MIN_HOURS_24H} hours)",
                      "source": "OpenAQ v3, from the CPCB/MPCB CAAQMS station" if is_cpcb else "OpenAQ v3"}
    return sites


def match_stations(per_provider: dict[str, dict[str, dict[str, Any]]]) -> dict[str, dict[str, Any]]:
    """Site id → {provider: observation}, for the sites at least one provider observed."""
    out: dict[str, dict[str, Any]] = {}
    for prov, sites in per_provider.items():
        for sid, obs in sites.items():
            out.setdefault(sid, {})[prov] = obs
    return out
