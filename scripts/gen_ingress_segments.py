#!/usr/bin/env python3
"""gen_ingress_segments.py — signal-ingress Mumbai network codegen.

signal-ingress (Rust, NATS publisher) has no database connection: it runs on
the compose bridge network and must keep publishing when PostGIS is still
starting. Its edge-synthetic feeds therefore carry the Mumbai road network
as a BUILD-TIME constant:

    services/signal-ingress/src/feeds/segments_mumbai.rs

For every segment the module records the identity and road attributes
(name, class, lanes, speed limit, one-way), the geodesic length, the midpoint
(ST_LineInterpolatePoint(geom, 0.5)), the full LINESTRING (so readings land
on the actual roadway) and the endpoint node ids (endpoints snapped to 1e-6
deg; a shared endpoint is one node). The generated text carries a content
fingerprint and no timestamp, so regeneration is byte-reproducible.

Two sources give the same rows, byte for byte:

* OFFLINE (the default; no database): the network evidence
  scripts/data/osm_network.json written by scripts/gen_osm_network.py (or
  the compact cities/mumbai/network.json). Each segment's stored ``line``
  IS the geom the corridor-store seed writes (reanchor_osm_network.sql), and
  the derived fields are computed the way the SQL below computes them:
  ``length_m`` is the geodesic length on the WGS84 ellipsoid summed over the
  line's pieces (as ST_Length(geom::geography) does; Vincenty's inverse
  formula iterated to 1e-13 rad, sub-micrometre on these short pieces),
  ``mid`` is ST_LineInterpolatePoint(geom, 0.5) (planar interpolation in
  degrees at half the planar length), both rounded like
  ``round(x::numeric, n)`` (15 significant digits, then half away from
  zero); the extent is the min/max over every vertex (ST_Extent).
* DATABASE (``--db`` / ``--container NAME`` via docker exec psql, or
  ``--dsn``): corridor.road_segments of a seeded store, READ ONLY — the psql
  session sets default_transaction_read_only and the psycopg path opens a
  read-only connection, so the script cannot write even if the SQL were
  wrong. ``--dsn`` needs psycopg: an interpreter without it re-runs the
  script under the repo's migrate venv (the one scripts/migrate.py uses)
  when one exists.

Usage (from anywhere; default paths resolve from the repo root):
    python3 scripts/gen_ingress_segments.py                    # offline
    python3 scripts/gen_ingress_segments.py --network N.json --out /tmp/x.rs
    python3 scripts/gen_ingress_segments.py --check            # exit 1 on drift
    python3 scripts/gen_ingress_segments.py --check --container sajag-postgis
    python3 scripts/gen_ingress_segments.py --dsn "$SAJAG_DATABASE_URL"

Re-run (and rebuild signal-ingress) whenever the corridor network changes,
e.g. after scripts/gen_osm_network.py regenerates the evidence, the seed and
the network step (services/corridor-store/seed/reanchor_osm_network.sql).
The table carries geom — the routing geometry every attribution uses, the
OpenStreetMap road itself ((c) OpenStreetMap contributors, ODbL 1.0, stated
in the generated header) — never a display_geom a map may draw (contract
C-K).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import subprocess
import sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TARGET = (REPO_ROOT / "services" / "signal-ingress" / "src" / "feeds"
          / "segments_mumbai.rs")
DEFAULT_NETWORK = REPO_ROOT / "scripts" / "data" / "osm_network.json"

#: The ingress table is Mumbai's (module name and wording); a network file
#: that declares another city is refused rather than mislabelled.
CITY = "mumbai"

# Repo constants (infra/compose.argus-override.yml) — identity, not secrets.
DEFAULT_CONTAINER = os.environ.get("POSTGIS_CONTAINER", "sajag-postgis")
PG_USER = "corridor_admin"
PG_DB = "corridor_db"

# Single read-only query; the whole result is one JSON document so no text
# parsing of psql output is needed.
QUERY = """
SELECT json_build_object(
  'segments', (
    SELECT json_agg(json_build_object(
        'id', segment_id,
        'name', coalesce(road_name, ''),
        'road_class', road_class,
        'lanes', coalesce(lanes, 2),
        'speed_limit_kmh', coalesce(speed_limit_kmh, 50),
        'oneway', coalesce(oneway, false),
        'length_m', round(ST_Length(geom::geography)::numeric, 1),
        'mid', json_build_array(
            round(ST_X(ST_LineInterpolatePoint(geom, 0.5))::numeric, 7),
            round(ST_Y(ST_LineInterpolatePoint(geom, 0.5))::numeric, 7)),
        'path', (ST_AsGeoJSON(geom, 7)::json) -> 'coordinates'
      ) ORDER BY segment_id)
    FROM corridor.road_segments),
  'extent', (
    SELECT json_build_array(ST_XMin(e), ST_YMin(e), ST_XMax(e), ST_YMax(e))
    FROM (SELECT ST_Extent(geom) AS e FROM corridor.road_segments) x)
)
"""

ROAD_CLASSES = {
    "motorway": "Motorway",
    "trunk": "Trunk",
    "primary": "Primary",
    "secondary": "Secondary",
    "tertiary": "Tertiary",
    "residential": "Residential",
    "service": "Service",
}

NODE_SNAP_DP = 6  # 1e-6 deg ≈ 0.1 m: endpoints closer than this are one node

# WGS84 ellipsoid (EPSG:7030), the spheroid of geography(4326).
WGS84_A = 6378137.0
WGS84_F = 1.0 / 298.257223563
WGS84_B = WGS84_A * (1.0 - WGS84_F)


# ─── database sources (read-only) ───────────────────────────────────────────

def fetch_via_container(container: str) -> dict:
    cmd = [
        "docker", "exec", "-i", container,
        "psql", "-X", "-q", "-A", "-t", "-v", "ON_ERROR_STOP=1",
        "-U", PG_USER, "-d", PG_DB,
        "-c", "SET default_transaction_read_only = on",
        "-c", QUERY,
    ]
    proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if proc.returncode != 0:
        raise SystemExit(f"ERROR: psql via {container} failed (exit {proc.returncode}):\n"
                         f"{proc.stderr.strip()}")
    return json.loads(proc.stdout.strip())


#: Interpreters with psycopg, in the order scripts/sajag_up.sh looks for them.
MIGRATE_PYTHONS = (
    os.environ.get("SAJAG_MIGRATE_PY", ""),
    os.path.join(os.environ.get("SAJAG_VENV_DIR", ""), "migrate", "bin", "python")
    if os.environ.get("SAJAG_VENV_DIR") else "",
    str(REPO_ROOT / ".venvs" / "migrate" / "bin" / "python"),
    str(REPO_ROOT / "models" / ".venvs" / "migrate" / "bin" / "python"),
)


def _reexec_with_psycopg() -> None:
    """Re-run this script under a venv that has psycopg (never loops)."""
    if os.environ.get("SAJAG_GEN_INGRESS_REEXEC"):
        return
    for py in MIGRATE_PYTHONS:
        if py and os.path.isfile(py) and os.access(py, os.X_OK):
            os.environ["SAJAG_GEN_INGRESS_REEXEC"] = "1"
            os.execv(py, [py, os.path.abspath(__file__), *sys.argv[1:]])


def fetch_via_dsn(dsn: str) -> dict:
    try:
        import psycopg
    except ImportError as exc:  # pragma: no cover - operational guard
        _reexec_with_psycopg()
        raise SystemExit("ERROR: --dsn needs psycopg (use the docker exec path instead)") from exc
    with psycopg.connect(dsn) as conn:
        conn.read_only = True
        with conn.cursor() as cur:
            cur.execute(QUERY)
            row = cur.fetchone()
    doc = row[0]
    return doc if isinstance(doc, dict) else json.loads(doc)


# ─── offline source: the same fields from the stored lines ──────────────────

def pg_round(value: float, places: int) -> float:
    """``round(value::numeric, places)`` as PostgreSQL computes it: float8 ->
    numeric keeps 15 significant digits (DBL_DIG), and numeric round() rounds
    half away from zero."""
    exact = Decimal(f"{float(value):.15g}")
    return float(exact.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP))


def geodesic_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Inverse geodesic distance on the WGS84 ellipsoid, metres (Vincenty
    1975, iterated to 1e-13 rad). On city-scale pieces it agrees with
    Karney's algorithm (GeographicLib's geod_inverse, which PostGIS's
    spheroid_distance calls) to far below the 0.1 m the table keeps."""
    if lon1 == lon2 and lat1 == lat2:
        return 0.0
    a, b, f = WGS84_A, WGS84_B, WGS84_F
    big_l = math.radians(lon2 - lon1)
    u1 = math.atan((1.0 - f) * math.tan(math.radians(lat1)))
    u2 = math.atan((1.0 - f) * math.tan(math.radians(lat2)))
    sin_u1, cos_u1 = math.sin(u1), math.cos(u1)
    sin_u2, cos_u2 = math.sin(u2), math.cos(u2)
    sin_du = math.sin(u2 - u1)
    lam = big_l
    for _ in range(200):
        sin_lam, cos_lam = math.sin(lam), math.cos(lam)
        # cos_u1·sin_u2 − sin_u1·cos_u2·cos_lam, written without the
        # cancellation that costs precision on pieces a few metres long
        sin_half = math.sin(lam / 2.0)
        sin_sigma = math.hypot(cos_u2 * sin_lam,
                               sin_du + 2.0 * sin_u1 * cos_u2 * sin_half * sin_half)
        if sin_sigma == 0.0:
            return 0.0  # coincident points
        cos_sigma = sin_u1 * sin_u2 + cos_u1 * cos_u2 * cos_lam
        sigma = math.atan2(sin_sigma, cos_sigma)
        sin_alpha = cos_u1 * cos_u2 * sin_lam / sin_sigma
        cos2_alpha = 1.0 - sin_alpha * sin_alpha
        cos_2sm = (cos_sigma - 2.0 * sin_u1 * sin_u2 / cos2_alpha) if cos2_alpha != 0.0 else 0.0
        c = f / 16.0 * cos2_alpha * (4.0 + f * (4.0 - 3.0 * cos2_alpha))
        lam_prev = lam
        lam = big_l + (1.0 - c) * f * sin_alpha * (
            sigma + c * sin_sigma * (cos_2sm + c * cos_sigma * (-1.0 + 2.0 * cos_2sm * cos_2sm)))
        if abs(lam - lam_prev) < 1e-13:
            break
    else:  # only near-antipodal points fail to converge; never on a city network
        raise SystemExit(f"ERROR: geodesic did not converge for ({lon1},{lat1})-({lon2},{lat2})")
    u_sq = cos2_alpha * (a * a - b * b) / (b * b)
    big_a = 1.0 + u_sq / 16384.0 * (4096.0 + u_sq * (-768.0 + u_sq * (320.0 - 175.0 * u_sq)))
    big_b = u_sq / 1024.0 * (256.0 + u_sq * (-128.0 + u_sq * (74.0 - 47.0 * u_sq)))
    delta_sigma = big_b * sin_sigma * (cos_2sm + big_b / 4.0 * (
        cos_sigma * (-1.0 + 2.0 * cos_2sm * cos_2sm)
        - big_b / 6.0 * cos_2sm * (-3.0 + 4.0 * sin_sigma * sin_sigma)
        * (-3.0 + 4.0 * cos_2sm * cos_2sm)))
    return b * big_a * (sigma - delta_sigma)


def geodesic_length_m(line: list[tuple[float, float]]) -> float:
    """ST_Length(geom::geography): the pieces' geodesic lengths, summed in order."""
    total = 0.0
    for (x1, y1), (x2, y2) in zip(line, line[1:]):
        total += geodesic_m(x1, y1, x2, y2)
    return total


def line_interpolate_point(line: list[tuple[float, float]], fraction: float) -> tuple[float, float]:
    """ST_LineInterpolatePoint(geom, fraction): planar, in degrees — the same
    walk as liblwgeom's lwline_interpolate_points (fractions of the planar
    length, piece by piece)."""
    if fraction == 0.0:
        return line[0]
    if fraction == 1.0:
        return line[-1]
    length = 0.0
    for (x1, y1), (x2, y2) in zip(line, line[1:]):
        length += math.sqrt((x1 - x2) * (x1 - x2) + (y1 - y2) * (y1 - y2))
    if length <= 0.0:
        raise SystemExit("ERROR: zero-length line")
    consumed = 0.0
    for (x1, y1), (x2, y2) in zip(line, line[1:]):
        hside, vside = x2 - x1, y2 - y1
        piece = math.sqrt(hside * hside + vside * vside) / length
        if fraction < consumed + piece:
            f = (fraction - consumed) / piece
            return (x1 + (x2 - x1) * f, y1 + (y2 - y1) * f)
        consumed += piece
    return line[-1]  # floating-point rounding at the far end


def load_network(path: Path) -> dict:
    """The offline equivalent of QUERY's document, from a network JSON."""
    try:
        net = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit(f"ERROR: network file {path} not found") from None
    city = net.get("city")
    if city is not None and city != CITY:
        raise SystemExit(f"ERROR: {path} is the {city!r} network; this table is for {CITY!r}")
    segs = net.get("segments")
    if not isinstance(segs, list) or not segs:
        raise SystemExit(f"ERROR: {path} has no 'segments' list")

    rows, seen = [], set()
    for s in sorted(segs, key=lambda s: int(s["segment_id"])):
        sid = int(s["segment_id"])
        if sid in seen:
            raise SystemExit(f"ERROR: {path}: segment {sid} appears twice")
        seen.add(sid)
        line = [(float(x), float(y)) for x, y in (s.get("line") or [])]
        if len(line) < 2:
            raise SystemExit(f"ERROR: {path}: segment {sid} has no line")
        mid = line_interpolate_point(line, 0.5)
        rows.append({
            "id": sid,
            "name": s.get("road_name") or "",
            "road_class": s.get("road_class"),
            "lanes": 2 if s.get("lanes") is None else s["lanes"],
            "speed_limit_kmh": 50 if s.get("speed_limit_kmh") is None else s["speed_limit_kmh"],
            "oneway": bool(s.get("oneway") or False),
            "length_m": pg_round(geodesic_length_m(line), 1),
            "mid": [pg_round(mid[0], 7), pg_round(mid[1], 7)],
            "path": [[round(x, 7), round(y, 7)] for x, y in line],  # ST_AsGeoJSON(geom, 7)
        })
    xs = [float(x) for s in segs for x, _ in s["line"]]
    ys = [float(y) for s in segs for _, y in s["line"]]
    return {"segments": rows, "extent": [min(xs), min(ys), max(xs), max(ys)]}


# ─── rendering (shared by both sources) ─────────────────────────────────────

def rust_f64(value: float) -> str:
    text = f"{float(value):.7f}".rstrip("0")
    return text + "0" if text.endswith(".") else text


def rust_str(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def canonical(doc: dict) -> list[dict]:
    """Validated, normalised rows (raises on anything the feeds cannot use)."""
    rows = doc.get("segments") or []
    if not rows:
        raise SystemExit("ERROR: no road segments in the source — seed the corridor first")
    out = []
    for r in rows:
        path = [(round(float(x), 7), round(float(y), 7)) for x, y in r["path"]]
        if len(path) < 2:
            raise SystemExit(f"ERROR: segment {r['id']} has a degenerate geometry")
        if r["road_class"] not in ROAD_CLASSES:
            raise SystemExit(f"ERROR: segment {r['id']} has unknown road_class {r['road_class']!r}")
        out.append({
            "id": int(r["id"]),
            "name": str(r["name"]),
            "road_class": str(r["road_class"]),
            "lanes": int(r["lanes"]),
            "speed_limit_kmh": int(r["speed_limit_kmh"]),
            "oneway": bool(r["oneway"]),
            "length_m": float(r["length_m"]),
            "mid": (round(float(r["mid"][0]), 7), round(float(r["mid"][1]), 7)),
            "path": path,
        })
    return out


def assign_nodes(rows: list[dict]) -> tuple[list[tuple[int, int]], int]:
    nodes: dict[tuple[float, float], int] = {}

    def node_of(pt: tuple[float, float]) -> int:
        key = (round(pt[0], NODE_SNAP_DP), round(pt[1], NODE_SNAP_DP))
        if key not in nodes:
            nodes[key] = len(nodes)
        return nodes[key]

    ends = [(node_of(r["path"][0]), node_of(r["path"][-1])) for r in rows]
    return ends, len(nodes)


def render(doc: dict) -> str:
    rows = canonical(doc)
    ends, node_count = assign_nodes(rows)
    fingerprint = hashlib.sha256(
        json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()[:16]
    min_lon, min_lat, max_lon, max_lat = (float(v) for v in doc["extent"])
    ids = [r["id"] for r in rows]

    out: list[str] = []
    w = out.append
    w("//! Mumbai corridor road network — GENERATED, DO NOT EDIT BY HAND.")
    w("//!")
    w(f"//! Source: the {len(rows)} segments (ids {ids[0]}-{ids[-1]}) of corridor.road_segments")
    w("//! as the corridor-store seed writes them, i.e. the network evidence")
    w("//! scripts/data/osm_network.json (scripts/gen_osm_network.py --city mumbai).")
    w("//! Regenerate with")
    w("//!     python3 scripts/gen_ingress_segments.py")
    w("//! (offline, no database) and check for drift with `--check`; add")
    w("//! `--container NAME` or `--dsn` to check against a seeded store (read-only).")
    w("//! Both sources give these exact bytes.")
    w("//!")
    w("//! `mid` is ST_LineInterpolatePoint(geom, 0.5), `length_m` is the geodesic")
    w("//! (WGS84 geography) length, `path` is the full LINESTRING in WGS84 lon/lat,")
    w("//! and `start_node`/`end_node` are the endpoints snapped to 1e-6 deg (a")
    w("//! shared endpoint is one node).")
    w("//!")
    w("//! Road geometry: (c) OpenStreetMap contributors, ODbL 1.0 —")
    w("//! https://www.openstreetmap.org/copyright (the network is traced on")
    w("//! OpenStreetMap by scripts/gen_osm_network.py).")
    w("")
    w("use super::city::{RoadClass, Segment};")
    w("")
    w("/// sha256 prefix of the canonical JSON of the rows below.")
    w(f'pub const SOURCE_FINGERPRINT: &str = "{fingerprint}";')
    w("")
    w("/// Network envelope (min_lon, min_lat, max_lon, max_lat) = ST_Extent(geom).")
    w(f"pub const NETWORK_BBOX: (f64, f64, f64, f64) = ({rust_f64(min_lon)}, {rust_f64(min_lat)}, "
      f"{rust_f64(max_lon)}, {rust_f64(max_lat)});")
    w("")
    w("/// Number of distinct endpoint nodes referenced by `start_node`/`end_node`.")
    w(f"pub const NODE_COUNT: usize = {node_count};")
    w("")
    w("pub static SEGMENTS: &[Segment] = &[")
    for r, (start, end) in zip(rows, ends):
        path = ", ".join(f"({rust_f64(x)}, {rust_f64(y)})" for x, y in r["path"])
        w("    Segment {")
        w(f"        id: {r['id']},")
        w(f"        name: {rust_str(r['name'])},")
        w(f"        road_class: RoadClass::{ROAD_CLASSES[r['road_class']]},")
        w(f"        lanes: {r['lanes']},")
        w(f"        speed_limit_kmh: {rust_f64(r['speed_limit_kmh'])},")
        w(f"        oneway: {'true' if r['oneway'] else 'false'},")
        w(f"        length_m: {rust_f64(r['length_m'])},")
        w(f"        mid: ({rust_f64(r['mid'][0])}, {rust_f64(r['mid'][1])}),")
        w(f"        path: &[{path}],")
        w(f"        start_node: {start},")
        w(f"        end_node: {end},")
        w("    },")
    w("];")
    return "\n".join(out) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--network", default=None, metavar="JSON",
                        help="offline source (the default): a network JSON with segments[].line "
                             f"(default {DEFAULT_NETWORK.relative_to(REPO_ROOT)})")
    source.add_argument("--db", action="store_true",
                        help="read corridor.road_segments via docker exec psql in --container "
                             f"(default {DEFAULT_CONTAINER}), read-only")
    source.add_argument("--dsn", default=None,
                        help="read corridor.road_segments via psycopg (read-only connection)")
    parser.add_argument("--container", default=None,
                        help="PostGIS container for docker exec psql (implies --db)")
    parser.add_argument("--out", default=str(TARGET), metavar="PATH",
                        help=f"output .rs path (default {TARGET.relative_to(REPO_ROOT)})")
    parser.add_argument("--check", action="store_true",
                        help="regenerate in memory; exit 1 if the file at --out differs")
    args = parser.parse_args()
    if args.container and (args.network or args.dsn):
        parser.error("--container reads the database; it cannot be combined with --network or --dsn")

    if args.dsn:
        doc, label = fetch_via_dsn(args.dsn), "corridor.road_segments (--dsn)"
    elif args.db or args.container:
        container = args.container or DEFAULT_CONTAINER
        doc, label = fetch_via_container(container), f"corridor.road_segments in {container}"
    else:
        network = Path(args.network) if args.network else DEFAULT_NETWORK
        doc, label = load_network(network), str(network)
    text = render(doc)
    out = Path(args.out)
    if args.check:
        current = out.read_text(encoding="utf-8") if out.is_file() else ""
        if current != text:
            print(f"DRIFT: {out} does not match {label} — regenerate it", file=sys.stderr)
            return 1
        print(f"OK: {out} matches {label}")
        return 0
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    n = text.count("    Segment {")
    print(f"wrote {out} ({n} segments, from {label})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
