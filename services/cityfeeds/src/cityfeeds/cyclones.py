"""Tropical cyclones and floods over the Arabian Sea and India's west coast, from GDACS (LIVE, third-party open feed).

GDACS (the Global Disaster Alert and Coordination System, a cooperation of the European Commission's Joint Research
Centre and UN OCHA) publishes an open JSON API:

* ``/gdacsapi/api/events/geteventlist/SEARCH?eventlist=TC;FL&fromDate=…&toDate=…`` — the event list (a GeoJSON
  FeatureCollection of centroids with alert level Green / Orange / Red, severity, dates, ``iscurrent``);
* ``/gdacsapi/api/polygons/getgeometry?eventtype=TC&eventid=…&episodeid=…`` — one cyclone's geometry: the track
  (``Line_Line_*``, each leg with its storm category), the positions (``Point_Polygon_Point_*``, labelled with
  their UTC time; past and forecast), the cumulative wind buffers (``Poly_Green`` 60 km/h, ``Poly_Orange``
  90 km/h, ``Poly_Red`` 120 km/h) and the forecast uncertainty cone (``Poly_Cones``).

An event is REGIONAL when its centroid lies in the configured box (the Arabian Sea and the west coast, 5–28 N,
55–80 E by default). For each current regional cyclone (at most three) the geometry is fetched and turned into one
GeoJSON FeatureCollection (flood events only within 800 km of Mumbai); the distance and bearing from Mumbai, the
closest approach of the track, and whether Mumbai lies inside any wind buffer are computed here (MODELLED from GDACS
geometry). For scale: Tauktae (May 2021) passed off Mumbai's coast, and Nisarga (June 2020) crossed the coast near
Alibag, about 95 km south.

IMD's RSMC New Delhi is the official cyclone authority for the North Indian Ocean; its bulletins are PDF and text
pages (https://rsmcnewdelhi.imd.gov.in/), not a machine-readable feed, so they are linked, not parsed.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from cityfeeds.geo import MUMBAI, bearing_deg, compass, decimate, haversine_km, point_in_ring

__all__ = ["fetch_cyclones", "cyclones_view", "BUFFER_KMH", "RSMC"]

BUFFER_KMH = {"Poly_Green": 60, "Poly_Orange": 90, "Poly_Red": 120}
LEVEL_OF = {"Poly_Green": "green", "Poly_Orange": "orange", "Poly_Red": "red"}
#: GDACS flood events count when their centroid is within this distance of Mumbai (Maharashtra, Gujarat, Goa,
#: Karnataka, Madhya Pradesh); a cyclone counts anywhere in the regional box
FLOOD_RADIUS_KM = 800

RSMC = {"publisher": "IMD, Regional Specialised Meteorological Centre (RSMC) New Delhi",
        "url": "https://rsmcnewdelhi.imd.gov.in/", "note": "official bulletins: PDF and text, linked not parsed"}


def _regional(f: dict, box: tuple[float, float, float, float]) -> bool:
    g = f.get("geometry") or {}
    if g.get("type") != "Point":
        return False
    lon, lat = g["coordinates"][:2]
    s, w, n, e = box
    return s <= lat <= n and w <= lon <= e


async def fetch_cyclones(client: httpx.AsyncClient, list_url: str, geom_url: str,
                         box: tuple[float, float, float, float], now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    params = {"eventlist": "TC;FL", "fromDate": (now - timedelta(days=30)).strftime("%Y-%m-%d"),
              "toDate": now.strftime("%Y-%m-%d"), "alertlevel": "Green;Orange;Red"}
    events = None
    last: Exception | None = None
    for _attempt in range(2):  # GDACS's list API answers 400 "Timeout expired" when its pool is busy: once more
        try:
            r = await client.get(list_url, params=params, timeout=45.0)
            r.raise_for_status()
            events = r.json()
            break
        except Exception as exc:  # noqa: BLE001
            last = exc
    if events is None:
        raise RuntimeError(f"GDACS list: {last}")
    feats = [f for f in events.get("features", []) if _regional(f, box)]
    geoms: dict[str, Any] = {}
    tcs = [f for f in feats if f["properties"].get("eventtype") == "TC" and str(f["properties"].get("iscurrent")).lower() == "true"]
    for f in tcs[:3]:
        p = f["properties"]
        g = await client.get(geom_url, params={"eventtype": "TC", "eventid": p["eventid"], "episodeid": p["episodeid"]},
                             timeout=45.0)
        g.raise_for_status()
        geoms[f"{p['eventid']}:{p['episodeid']}"] = g.json()
    return {"events": {"type": "FeatureCollection", "features": feats}, "geometry": geoms,
            "query": {**params, "box": list(box)}}


def _centroid(coords: list) -> tuple[float, float]:
    ring = coords[0] if coords and isinstance(coords[0][0], list) else coords
    xs = [p[0] for p in ring]
    ys = [p[1] for p in ring]
    return sum(xs) / len(xs), sum(ys) / len(ys)


def _pos_time(label: str, year: int) -> str | None:
    # "26/10 00:00 UTC" → ISO
    try:
        d, hm = label.replace(" UTC", "").split(" ")
        day, mon = d.split("/")
        return datetime(year, int(mon), int(day), int(hm[:2]), int(hm[3:5]), tzinfo=UTC).isoformat()
    except Exception:  # noqa: BLE001
        return None


def cyclones_view(raw: dict | None, now: datetime | None = None) -> dict[str, Any]:
    """A GeoJSON FeatureCollection for the map (tracks, positions, wind buffers, cones, flood points) with the
    regional summary as foreign members."""
    now = now or datetime.now(UTC)
    klat, klon = MUMBAI
    feats: list[dict[str, Any]] = []
    active: list[dict[str, Any]] = []
    floods: list[dict[str, Any]] = []
    for f in (raw or {}).get("events", {}).get("features", []):
        p = f["properties"]
        lon, lat = f["geometry"]["coordinates"][:2]
        current = str(p.get("iscurrent")).lower() == "true"
        base = {"eventtype": p.get("eventtype"), "eventid": p.get("eventid"), "episodeid": p.get("episodeid"),
                "name": p.get("eventname") or p.get("name"), "alertlevel": (p.get("alertlevel") or "").lower(),
                "country": p.get("country"), "fromdate": p.get("fromdate"), "todate": p.get("todate"),
                "current": current, "report": (p.get("url") or {}).get("report"),
                "severity": (p.get("severitydata") or {}).get("severitytext"),
                "distance_km": round(haversine_km(klat, klon, lat, lon)),
                "bearing": compass(bearing_deg(klat, klon, lat, lon))}
        if p.get("eventtype") == "FL":
            if base["distance_km"] > FLOOD_RADIUS_KM:  # a flood elsewhere in the box is not Mumbai's
                continue
            floods.append(base | {"lat": lat, "lon": lon})
            feats.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [lon, lat]},
                          "properties": base | {"kind": "flood"}})
            continue
        if not current:
            continue
        key = f"{p['eventid']}:{p['episodeid']}"
        g = (raw or {}).get("geometry", {}).get(key) or {}
        year = int((p.get("todate") or now.isoformat())[:4])
        positions: list[dict[str, Any]] = []
        track_pts: list[tuple[float, float]] = []
        inside: list[int] = []
        for gf in g.get("features", []):
            gp = gf.get("properties") or {}
            cls = gp.get("Class") or ""
            label = gp.get("polygonlabel") or ""
            geom = gf.get("geometry") or {}
            if cls.startswith("Line_") and geom.get("type") == "LineString":
                pts = [[round(x, 3), round(y, 3)] for x, y, *_ in geom["coordinates"]]
                track_pts += [(y, x) for x, y in pts]
                feats.append({"type": "Feature", "geometry": {"type": "LineString", "coordinates": pts},
                              "properties": {"kind": "track", "category": label, "eventid": p["eventid"],
                                             "name": base["name"]}})
            elif cls.startswith("Point_Polygon") and geom.get("type") == "Polygon":
                x, y = _centroid(geom["coordinates"])
                at = _pos_time(label, year)
                positions.append({"at": at, "lat": round(y, 2), "lon": round(x, 2)})
                track_pts.append((y, x))
                feats.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [round(x, 3), round(y, 3)]},
                              "properties": {"kind": "position", "at": at, "label": label, "eventid": p["eventid"],
                                             "forecast": bool(at and at > now.isoformat())}})
            elif cls in BUFFER_KMH and geom.get("type") == "Polygon" and label.endswith("km/h"):
                ring = decimate(geom["coordinates"][0])
                if point_in_ring(klon, klat, ring):
                    inside.append(BUFFER_KMH[cls])
                feats.append({"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [ring]},
                              "properties": {"kind": "wind_buffer", "level": LEVEL_OF[cls], "wind_kmh": BUFFER_KMH[cls],
                                             "eventid": p["eventid"], "name": base["name"]}})
            elif cls == "Poly_Cones" and geom.get("type") == "Polygon":
                feats.append({"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [decimate(geom["coordinates"][0])]},
                              "properties": {"kind": "cone", "eventid": p["eventid"], "name": base["name"]}})
        positions.sort(key=lambda x: x["at"] or "")
        past = [x for x in positions if x["at"] and x["at"] <= now.isoformat()]
        nowpos = past[-1] if past else {"lat": lat, "lon": lon, "at": p.get("todate")}
        closest = None
        for y, x in track_pts:
            d = haversine_km(klat, klon, y, x)
            if closest is None or d < closest["distance_km"]:
                closest = {"distance_km": round(d), "lat": round(y, 2), "lon": round(x, 2)}
        cur_d = haversine_km(klat, klon, nowpos["lat"], nowpos["lon"])
        active.append(base | {
            "position": nowpos, "distance_km": round(cur_d),
            "bearing": compass(bearing_deg(klat, klon, nowpos["lat"], nowpos["lon"])),
            "bearing_deg": round(bearing_deg(klat, klon, nowpos["lat"], nowpos["lon"])),
            "closest_approach": closest, "city_in_wind_buffer_kmh": max(inside) if inside else None,
            # the deck's cyclone layer still reads the old key name; same value (compatibility only)
            "kolkata_in_wind_buffer_kmh": max(inside) if inside else None,
            "positions": positions, "geometry_loaded": bool(g),
        })
    active.sort(key=lambda a: a["distance_km"])
    return {
        "type": "FeatureCollection", "features": feats,
        "label": "LIVE", "derived_label": "MODELLED",
        "what": "GDACS tropical-cyclone and flood events over the Arabian Sea and the west coast: track, positions, wind buffers "
                "(60/90/120 km/h), uncertainty cone; distances from Mumbai computed here",
        "active": active, "floods": floods,
        "nearest": active[0] if active else None,
        "sources": {"gdacs": {"publisher": "GDACS (European Commission JRC and UN OCHA)", "url": "https://www.gdacs.org/",
                              "terms": "https://www.gdacs.org/About/termsofuse.aspx"},
                    "official": RSMC},
    }
