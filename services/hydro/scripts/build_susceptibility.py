#!/usr/bin/env python3
"""Build ``src/hydro/data/susceptibility.json`` — per road segment (and per landmark) terrain and drainage
features plus the MODELLED susceptibility score the nowcast uses.

Inputs (all public, fetched once by the operator and passed as paths; the script never fetches):

* Copernicus DEM GLO-30 tiles ``Copernicus_DSM_COG_10_N18_00_E072_00_DEM`` and ``…_N19_00_E072_00_DEM``
  (Mumbai spans 18.89–19.28 N; AWS open data bucket ``copernicus-dem-30m``; © DLR e.V. 2010–2014 and ©
  Airbus Defence and Space GmbH 2014–2018, provided under COPERNICUS by the European Union and ESA; free
  licence). It is a *surface* model (buildings included), so a segment's ground is approximated by the 10th
  percentile of samples along it. Sea and creek water (≤ 0.5 m) is left out of the city distribution.
* An OpenStreetMap Overpass extract of ``waterway=canal|drain|river|stream|ditch`` in the city bbox
  (© OpenStreetMap contributors, ODbL 1.0).
* The road network (``src/hydro/data/mumbai_network.json``), landmarks and the sourced hotspot list.

Features per segment: ground elevation (p10 / median of samples every ~30 m), the neighbourhood median
within 1.5 km, the relative elevation (segment p10 − neighbourhood median), the city percentile of the
segment's ground, distance to the nearest mapped canal/drain/stream and to a river, and distance to the
nearest reported hotspot.

Score (MODELLED, weights documented in docs/ai/hydro.md):
    S = 0.30·(1 − city_percentile) + 0.20·σ(−rel_elev / 1 m) + 0.20·min(1, d_drain / 2 km) + 0.30·h
where h = exp(−d_hotspot / 400 m) (half weight for an unverified hotspot). An ELEVATED segment (a bridge
deck or a flyover: road class motorway, or "Bridge"/"Setu"/"Flyover" in its name before any bracket)
keeps 15 % of its score — its deck does not pond (approach ramps can), and the DEM under a bridge is the
sea, a creek or the railway. In Mumbai that is a name rule: "Bridge", "Setu", "Flyover", "Elevated", "Sea
Link", "Coastal Road" or "Freeway" before any bracket (the Sea Link and its approaches, the Coastal Road, the
Eastern Freeway, Sahar Elevated Road, Gokhale and Tilak bridges, the JJ flyover). The Western Express
Highway is tagged motorway but runs at grade, so road class alone does not decide.

A road SUBWAY (an underpass under the railway: "Subway" or "Underpass" in the name, e.g. the Milan and
Andheri subway approaches) dips metres below grade, which a 30 m surface model cannot resolve: its score is
floored at 0.9 (MODELLED rule; the terrain score is kept as ``score_terrain``).

Usage (from services/hydro):
    python scripts/build_susceptibility.py --dem N18E072.tif --dem N19E072.tif --waterways waterways.json
"""

from __future__ import annotations

import argparse
import gzip
import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "src" / "hydro" / "data"
BBOX = (18.89, 72.77, 19.28, 72.99)  # S, W, N, E (cities/mumbai/city.json)
LAT0 = 19.08  # local equirectangular frame
LAND_MIN_M = 0.5  # DEM cells at or below this are sea / creek water
UNDERPASS_FLOOR = 0.9  # a road subway under the railway (name rule) is at least this susceptible


def _hav(lat1, lon1, lat2, lon2):
    r = 6371008.8
    p1, p2 = np.radians(lat1), np.radians(lat2)
    a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(np.radians(lon2 - lon1) / 2) ** 2
    return 2 * r * np.arcsin(np.minimum(1.0, np.sqrt(a)))


def _densify(line, step_m=30.0):
    pts = []
    for (lon1, lat1), (lon2, lat2) in zip(line, line[1:]):
        d = float(_hav(lat1, lon1, lat2, lon2))
        k = max(1, int(d // step_m))
        for i in range(k):
            f = i / k
            pts.append((lon1 + f * (lon2 - lon1), lat1 + f * (lat2 - lat1)))
    pts.append(tuple(line[-1]))
    return np.array(pts)


def _seg_dist_m(px, py, ax, ay, bx, by):
    """Distance (m) from points (px, py) to segments a→b, in a local equirectangular frame (degrees in)."""
    kx = 111320.0 * math.cos(math.radians(LAT0))
    ky = 110574.0
    px, py, ax, ay, bx, by = px * kx, py * ky, ax * kx, ay * ky, bx * kx, by * ky
    dx, dy = bx - ax, by - ay
    L = dx * dx + dy * dy
    t = np.where(L > 0, ((px[:, None] - ax) * dx + (py[:, None] - ay) * dy) / np.where(L > 0, L, 1), 0)
    t = np.clip(t, 0, 1)
    cx, cy = ax + t * dx, ay + t * dy
    return np.sqrt((px[:, None] - cx) ** 2 + (py[:, None] - cy) ** 2)


def _no_nan(x):
    """Strict JSON: a point with no land cell in its sample (a shore or sea point: the Sea Link, Marine Drive,
    Apollo Bunder) gets null, never NaN, and says why."""
    if isinstance(x, float) and math.isnan(x):
        return None
    if isinstance(x, dict):
        d = {k: _no_nan(v) for k, v in x.items()}
        if any(isinstance(v, float) and math.isnan(v) for v in x.values()):
            d.setdefault("note", "no land DEM cell in the sample (shore or sea point): no ground value")
        return d
    if isinstance(x, list):
        return [_no_nan(v) for v in x]
    return x


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dem", required=True, type=Path, action="append", help="repeat for each tile")
    ap.add_argument("--waterways", required=True, type=Path)
    ap.add_argument("--out", type=Path, default=DATA / "susceptibility.json")
    ap.add_argument("--save-waterways", type=Path, default=HERE / "data" / "waterways.overpass.json.gz",
                    help="also keep a gzipped copy of the extract next to this script (ODbL)")
    a = ap.parse_args()

    import rasterio  # noqa: PLC0415 — build-time only

    net = json.loads((DATA / "mumbai_network.json").read_text(encoding="utf-8"))
    lms = json.loads((DATA / "mumbai_landmarks.json").read_text(encoding="utf-8"))["landmarks"]
    hs = json.loads((DATA / "hotspots.json").read_text(encoding="utf-8"))["hotspots"]
    ww = json.loads(a.waterways.read_text(encoding="utf-8"))

    from rasterio.merge import merge  # noqa: PLC0415

    s, w, n, e = BBOX
    srcs = [rasterio.open(p) for p in a.dem]
    try:
        z, tr = merge(srcs, bounds=(w - 0.02, s - 0.02, e + 0.02, n + 0.02), nodata=np.nan, dtype="float64")
    finally:
        for x in srcs:
            x.close()
    z = z[0].astype(float)
    z[z <= LAND_MIN_M] = np.nan  # sea and creek water: not ground a road can sit on

    def rc(lon, lat):
        col = ((np.asarray(lon) - tr.c) / tr.a).astype(int)
        row = ((np.asarray(lat) - tr.f) / tr.e).astype(int)
        return np.clip(row, 0, z.shape[0] - 1), np.clip(col, 0, z.shape[1] - 1)

    def sample(lon, lat):
        r, c = rc(lon, lat)
        return z[r, c]

    # city distribution of ground elevation (bbox cells), for the percentile feature
    city = z[np.isfinite(z)]
    city_sorted = np.sort(city)
    px_m = abs(tr.a) * 111320.0 * math.cos(math.radians(LAT0))
    rad = int(round(1500.0 / px_m))

    def neigh_median(lon, lat):
        r, c = rc([lon], [lat])
        r, c = int(r[0]), int(c[0])
        blk = z[max(0, r - rad):r + rad + 1, max(0, c - rad):c + rad + 1]
        return float(np.nanmedian(blk))

    # waterways → straight pieces
    pieces_drain, pieces_river = [], []
    names = {}
    for el in ww.get("elements", []):
        g = el.get("geometry") or []
        kind = (el.get("tags") or {}).get("waterway")
        for p, q in zip(g, g[1:]):
            item = (p["lon"], p["lat"], q["lon"], q["lat"])
            (pieces_river if kind == "river" else pieces_drain).append(item)
        if kind:
            names[kind] = names.get(kind, 0) + 1
    D = np.array(pieces_drain)
    R = np.array(pieces_river) if pieces_river else np.zeros((0, 4))

    def dmin(pts, arr):
        if arr.size == 0:
            return float("inf")
        best = np.inf
        for i in range(0, arr.shape[0], 4000):
            blk = arr[i:i + 4000]
            dd = _seg_dist_m(pts[:, 0], pts[:, 1], blk[:, 0], blk[:, 1], blk[:, 2], blk[:, 3])
            best = min(best, float(dd.min()))
        return best

    H = np.array([(h["lon"], h["lat"], 0.5 if h.get("unverified") else 1.0) for h in hs])

    def features(pts, ident):
        el = sample(pts[:, 0], pts[:, 1])
        el = el[np.isfinite(el)]
        p10 = float(np.percentile(el, 10)) if el.size else float("nan")
        med = float(np.median(el)) if el.size else float("nan")
        mid = pts[len(pts) // 2]
        nb = neigh_median(mid[0], mid[1])
        rel = p10 - nb
        pct = float(np.searchsorted(city_sorted, p10) / city_sorted.size)
        d_dr = dmin(pts, D)
        d_rv = dmin(pts, R)
        dh = _hav(pts[:, 1][:, None], pts[:, 0][:, None], H[:, 1][None, :], H[:, 0][None, :])
        j = int(np.argmin(dh.min(axis=0)))
        d_hs = float(dh.min())
        hterm = float(H[j, 2] * math.exp(-d_hs / 400.0))
        S = (0.30 * (1 - pct) + 0.20 * (1 / (1 + math.exp(rel / 1.0)))
             + 0.20 * min(1.0, d_dr / 2000.0) + 0.30 * hterm)
        return {
            "id": ident,
            "ground_p10_m": round(p10, 2), "ground_median_m": round(med, 2),
            "neighbourhood_median_m": round(nb, 2), "relative_elevation_m": round(rel, 2),
            "city_percentile": round(pct, 3),
            "dist_drain_m": round(d_dr), "dist_river_m": round(d_rv) if math.isfinite(d_rv) else None,
            "nearest_hotspot": hs[j]["id"], "dist_hotspot_m": round(d_hs),
            "hotspot_unverified": bool(hs[j].get("unverified", False)),
            "score": round(S, 3),
        }

    import re  # noqa: PLC0415

    def elevated(sgm) -> bool:
        head = sgm["road_name"].split("(")[0]
        return bool(re.search(r"\b(Bridge|Setu|Flyover|Elevated|Sea Link|Coastal Road|Freeway)\b", head))

    def underpass(sgm) -> bool:
        return bool(re.search(r"\b(Subway|Underpass)\b", sgm["road_name"]))

    segs = {}
    for sgm in net["segments"]:
        pts = _densify(sgm["line"])
        f = features(pts, sgm["segment_id"])
        f["elevated"] = elevated(sgm)
        f["underpass"] = underpass(sgm)
        if f["underpass"]:
            # a road subway dips metres below grade under the railway: a 30 m surface model cannot see it, so
            # the score is floored at UNDERPASS_FLOOR (MODELLED rule)
            f["score_terrain"] = f["score"]
            f["score"] = round(max(f["score"], UNDERPASS_FLOOR), 3)
        if f["elevated"]:
            f["score_at_grade"] = f["score"]
            f["score"] = round(0.15 * f["score"], 3)
        segs[str(sgm["segment_id"])] = f
    lmk = {}
    for lm in lms:
        if not (BBOX[0] <= lm["lat"] <= BBOX[2] and BBOX[1] <= lm["lon"] <= BBOX[3]):
            continue
        pts = np.array([(lm["lon"], lm["lat"])])
        f = features(pts, lm["id"])
        f["kind"] = lm.get("kind")
        f["elevated"] = lm.get("kind") == "bridge"
        if f["elevated"]:
            f["score"] = round(0.15 * f["score"], 3)
        lmk[lm["id"]] = f

    out = {
        "schema": "sajag.hydro.susceptibility/1",
        "label": "MODELLED",
        "built_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "inputs": {
            "dem": {"product": "Copernicus DEM GLO-30 (DSM)", "tiles": [p.name for p in a.dem],
                    "source": "s3://copernicus-dem-30m/ (Copernicus_DSM_COG_10_N18_00_E072_00_DEM, "
                              "Copernicus_DSM_COG_10_N19_00_E072_00_DEM)",
                    "licence": "© DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018, provided "
                               "under COPERNICUS by the European Union and ESA; all rights reserved (free use "
                               "licence)",
                    "note": "surface model: buildings included; ground ≈ p10 of samples along the road; cells ≤ "
                            "0.5 m (sea, creeks) excluded"},
            "waterways": {"query": "way[waterway~canal|drain|river|stream|ditch] in 18.89,72.77,19.28,72.99",
                          "osm_base": (ww.get("osm3s") or {}).get("timestamp_osm_base"),
                          "counts": names, "licence": "© OpenStreetMap contributors, ODbL 1.0"},
            "network": net.get("source"),
            "hotspots": "src/hydro/data/hotspots.json",
        },
        "weights": {"underpass_floor": UNDERPASS_FLOOR, "low_ground_city_percentile": 0.30, "relative_depression": 0.20,
                    "drain_distance": 0.20, "reported_hotspot": 0.30},
        "city_dem_stats_m": {"p05": round(float(np.percentile(city, 5)), 2),
                             "p50": round(float(np.percentile(city, 50)), 2),
                             "p95": round(float(np.percentile(city, 95)), 2)},
        "segments": segs,
        "landmarks": lmk,
    }
    a.out.write_text(json.dumps(_no_nan(out), ensure_ascii=False, indent=1, allow_nan=False), encoding="utf-8")
    if a.save_waterways:
        a.save_waterways.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(a.save_waterways, "wt", encoding="utf-8") as f:
            json.dump(ww, f, separators=(",", ":"))
    sc = sorted(segs.values(), key=lambda x: -x["score"])
    print(f"wrote {a.out} ({len(segs)} segments, {len(lmk)} landmarks)")
    for x in sc[:8]:
        print(" ", x["id"], x["score"], x["ground_p10_m"], x["relative_elevation_m"], x["nearest_hotspot"],
              x["dist_hotspot_m"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
