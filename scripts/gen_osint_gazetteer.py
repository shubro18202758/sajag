#!/usr/bin/env python3
"""gen_osint_gazetteer.py — Sajag's offline OSINT place gazetteer (contract X19), rebuilt deterministically.

Writes ``scripts/data/osint_gazetteer.json``: the places the geo-resolver (``services/osint-geo``) can name, each
with its spellings, a point, an importance prior and, for the network's own features, its id. Places only: no
field outside the X19 list exists, and no person's name ever becomes a phrase on its own.

Inputs (all in the repo, offline):

* ``scripts/data/osm_network.json`` (read only; ``gen_osm_network.py`` owns it): the city's ``junctions`` (English
  and Marathi names, OSM node points) and road ``segments`` (road names, the OSM names along each, the stored
  line). © OpenStreetMap contributors, ODbL 1.0;
* ``cities/<city>/gazetteer.json``, the City Pack's place table (the source of truth for every place that is not
  a network feature): neighbourhoods, low-lying spots, off-network streets, terminals, bridges, ghats, hospitals,
  venues, Durga Puja pandals and police stations, each with English, Marathi and Hindi names and the romanised
  variants and misspellings seen in local text; plus extra forms for the network's junctions (``junction_aliases``,
  by junction key) and roads (``road_aliases``, by base road name). Hand rows carry approximate, reviewable
  points; police stations come from the pack's OSM extract (ODbL);
* ``cities/<city>/landmarks.json``: the canonical names (the Hindi name of a junction named after a landmark);
* ``osint_geo.translit``: the Marathi and Hindi place-word tables and Latin variants.

What each entry's ``surface_forms`` hold (every form in the resolver's normal form, ``osint_geo.gazetteer.norm``):

* junction (gaz_ids 1..J, the network's ids): its name, the name without the parenthesis ("Kalighat (SP Mukherjee
  Road)" → "Kalighat"), the Marathi name with and without its parenthesis, its Latin transliteration, its Hindi
  name (landmarks.json) and the pack's aliases ("gariahat more", "গড়িয়াহাটের মোড়"). A junction never carries a
  form a pack place carries (F-HONEST OSINT-1: "Gariahat" alone is the neighbourhood, "Sealdah" the station, never
  a junction pin), nor a bare word two junctions share. Unlike the first build, no bare first word of a junction
  name is added: in Kolkata it is a surname ("Hazra"), a person's name ("Rashbehari"), a company ("Exide") or an
  area;
* road (the network's segments, gaz_ids J+1..): its name, its base name, the OSM names along it — a linear name
  covering at least 10 % (and 100 m) or 200 m of it, a point-like name (a crossing, circle or bridge) at any length
  unless it is a junction's own name; ``(unnamed)`` and generic-only names left out — and the pack's colloquial
  forms of the road ("em bypass", "chowringhee", "ইএম বাইপাস", "ajc bose road"). Its point is the segment's anchor,
  ``ST_PointOnSurface`` of the line (``osint_geo.geom.interior_point``), where the oracle places the segment;
* pack place (gaz_ids after the roads, in pack order): its English name and base name, its variants, its Marathi
  and Hindi names and variants, and the Latin variants of ``translit``. ``anchor`` sets how it meets the network:
  ``area`` → X19 ``neighbourhood`` semantics (no road anchor; an off-network street is never pinned to another
  road), ``snap`` (the resolver snaps it to the nearest segment within 900 m), ``J<id>`` / ``S<id>`` (pre-linked
  to that junction or segment).

The gaz_ids are positional (network order, then pack order), so a regenerated file keeps every id while the inputs
keep their order. The city is ``SAJAG_CITY`` (default ``mumbai``; the Kolkata pack still builds with ``SAJAG_CITY=kolkata``). A lint (:func:`lint`) refuses a build in which a multi-word Latin phrase carries no place-type
word or road code (the rule of ``osint-common``'s ``test_gazetteer_phrases_are_places_never_bare_person_names``),
a form is not in normal form, a form is a bare generic word, or a junction shares a form with a pack place.
``generated_at`` is the OpenStreetMap extract time of the network it was built from, so the same inputs give a
byte-identical file.

Usage (the standard library alone: ``osint_geo.gazetteer``, ``translit`` and ``geom`` import nothing else, so any
Python 3.12 runs it, gates included; paths resolve from the repo root):

    python scripts/gen_osint_gazetteer.py            # build in memory, report counts and whether the file differs
    python scripts/gen_osint_gazetteer.py --check    # exit 1 when the committed file differs from a rebuild
    python scripts/gen_osint_gazetteer.py --write    # rewrite scripts/data/osint_gazetteer.json
    python scripts/gen_osint_gazetteer.py --overpass [--overpass-json FILE]
        # opt-in, never used by gates: list OSM place nodes in the city bbox that the gazetteer lacks, for a
        # reviewer to add to the pack by hand (one Overpass request, or a saved response with --overpass-json)
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import sys
import tempfile
import urllib.parse
import urllib.request
from collections import OrderedDict
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "services" / "osint-geo" / "src"))

from osint_geo import translit  # noqa: E402
from osint_geo.gazetteer import GENERIC_STOPWORDS, LICENCE, Gazetteer, norm  # noqa: E402
from osint_geo.geom import interior_point  # noqa: E402

CITY = os.environ.get("SAJAG_CITY", "mumbai").strip() or "mumbai"
NETWORK_JSON = REPO_ROOT / "scripts" / "data" / "osm_network.json"
PACK_JSON = REPO_ROOT / "cities" / CITY / "gazetteer.json"
LANDMARKS_JSON = REPO_ROOT / "cities" / CITY / "landmarks.json"
CITY_JSON = REPO_ROOT / "cities" / CITY / "city.json"
OUT_JSON = REPO_ROOT / "scripts" / "data" / "osint_gazetteer.json"

#: Road importance by OSM class (the PoC's priors).
ROAD_IMPORTANCE = {"motorway": 0.8, "trunk": 0.8, "primary": 0.7, "secondary": 0.55, "tertiary": 0.45}
#: A junction's importance: signalised 0.85, else 0.7 (the PoC's priors).
JUNCTION_IMPORTANCE = {True: 0.85, False: 0.7}
#: A pack place's X19 feature type by its anchor: an area is a neighbourhood (no road anchor), the rest keep theirs.
ANCHOR_RE = re.compile(r"^(?:area|snap|J\d+|S\d+)$")

#: A linear OSM name (a road, flyover, underpass) becomes a road's alias when it covers at least this share of the
#: segment (and this length), or at least OSM_NAME_LONG_M of it: a few metres of another road where it touches the
#: segment ("Strand Road", 33 m of Howrah Bridge) would attach that road's reports to the wrong segment.
OSM_NAME_MIN_SHARE = 0.10
OSM_NAME_MIN_M = 100.0
OSM_NAME_LONG_M = 200.0
#: A point-like OSM name (a crossing, circle, bridge or setu) marks a place ON the segment, so it is an alias at any
#: length ("Parama Circle", 50 m of EM Bypass) unless it is one of the junctions' own names ("Ruby Crossing").
POINT_WORDS = frozenset({"circle", "crossing", "junction", "bridge", "setu", "more", "circus"})

#: Words that make a multi-word phrase a PLACE (mirrors osint-common's lint): a place type, or a generic place word.
PLACE_TYPE_WORDS = frozenset(
    {
        "road", "roads", "rd", "highway", "circle", "circus", "junction", "bridge", "setu", "flyover", "underpass",
        "overbridge", "ramp", "link", "connector", "approach", "crossing", "more", "phari", "chowrasta", "street",
        "st", "lane", "sarani", "avenue", "bypass", "station", "stn", "railway", "metro", "terminus", "bus",
        "airport", "terminal", "gate", "forecourt", "end", "market", "bazar", "square", "park", "gardens", "garden",
        "lake", "sarobar", "ghat", "temple", "mandir", "math", "masjid", "cathedral", "hospital", "college",
        "medical", "university", "school", "club", "sangha", "sammilani", "sarbojanin", "durgotsav", "puja",
        "pally", "stadium", "indoor", "krirangan", "ground", "grounds", "maidan", "mela", "prangan", "centre",
        "memorial", "hall", "building", "buildings", "bhavan", "bhawan", "sadan", "court", "headquarters", "police",
        "thana", "ps", "kalibari", "town", "city", "sector", "nagar", "para", "bag", "kolkata", "calcutta",
        "howrah", "bengal", "india", "salt", "new", "point", "phanri", "chourasta", "ave", "pass", "area", "lakes",
        # Mumbai's place words: roads (marg, drive, naka, chowk), coast and water (chowpatty, beach, bunder, creek,
        # river, causeway), areas (east/west halves, wadi, koliwada, colony, village, estate), rail (lines, central,
        # terminus, subway), and the BMC's administrative wards
        "marg", "drive", "naka", "chowk", "corner", "chowpatty", "beach", "bunder", "creek", "river", "causeway",
        "subway", "underpass", "expressway", "freeway", "elevated", "east", "west", "north", "south", "wadi",
        "koliwada", "gaothan", "colony", "village", "estate", "lines", "central", "mumbai", "bombay", "maharashtra",
        "ward", "office", "hill", "hills", "parade", "complex", "promenade", "basilica", "church", "dargah",
        "racecourse", "dome", "exhibition", "galli", "pandal", "mandal", "ganpati", "visarjan", "rob", "interchange",
        "plaza", "toll", "seaface", "fork", "merge", "exit", "landing", "forecourt", "metro", "airport", "flyover",
        "basti", "chawl", "tank", "talao", "thane", "line", "rd", "nagar", "house", "center", "bandstand", "hq", "hwy",
        "nadi", "weh", "eeh", "jvlr", "sclr", "gmlr", "ltt", "csmt", "bkc", "mthl", "bwsl",
    }
)
_ROAD_CODE = re.compile(r"(?:nh|ne|sh)\d+")
#: Reviewed multi-word phrases with no place-type word: two-word place names of Kolkata.
REVIEWED_PHRASES = frozenset(
    {"dum dum", "behala notun dal", "badamtala ashar sangha", "prakriti tirtha", "ipgmer sskm", "amri dhakuria",
     "thanthania kali bari", "sixty six pally", "boipara", "ekdalia evergreen", "rajarhat new town",
     "chetla agrani",
     # Mumbai: two-word place names with no place-type word
     "vile parle", "lower parel", "antop hill", "saki naka", "haji ali", "lalbaugcha raja", "kemps corner",
     "lalbaug raja", "gsb seva", "opera house", "jacob circle", "amar mahal", "queens necklace", "saat rasta",
     "kala nagar", "khar danda", "chheda nagar", "andhericha raja", "chinchpoklicha chintamani", "khetwadi ganraj",
     "mumbaicha raja", "tata memorial", "seven hills", "holy family", "bhakti park", "shell colony",
     "kranti nagar", "nariman point", "cuffe parade", "malabar hill", "wadala bridge", "parel tt", "dadar tt",
     "gandhi market", "yellow gate", "national college", "national park", "lal baug", "santa cruz", "hind mata",
     "teli gali", "hindmata dadar tt", "hindmata dadar"}
)

_PARENS = re.compile(r"\s*\(.*?\)\s*")


def _base(name: str) -> str:
    """A name without its parenthesised part ("Kalighat (SP Mukherjee Road)" → "Kalighat")."""
    return _PARENS.sub(" ", name).strip()


def _good(form: str) -> bool:
    """A form worth carrying: three characters or more, not only generic words."""
    return len(form) >= 3 and not all(t in GENERIC_STOPWORDS for t in form.split(" "))


def _expand(forms: list[str]) -> list[str]:
    """Each Latin form plus its script aliases and Latin variants (``osint_geo.translit``). A form dropped as
    generic brings no alias either, so the scripts never say more than the Latin does."""
    out = list(forms)
    for f in forms:
        n = norm(f)
        if not (n and _good(n)):
            continue
        out.extend(translit.script_aliases(n))
        out.extend(translit.latin_variants(n))
    return out


def _finish(forms: list[str]) -> list[str]:
    return sorted({n for n in (norm(f) for f in forms) if n and _good(n)})


def _aliases(table: dict[str, Any] | None) -> list[str]:
    if not table:
        return []
    return [*table.get("aka", []), *table.get("aka_mr", []), *table.get("aka_hi", [])]


def load_pack(path: Path = PACK_JSON) -> dict[str, Any]:
    pack = json.loads(path.read_text(encoding="utf-8"))
    if pack.get("schema") != "sajag.gazetteer/1" or not isinstance(pack.get("places"), list):
        raise SystemExit(f"{path}: not a sajag.gazetteer/1 pack")
    ids = [p.get("id") for p in pack["places"]]
    if len(ids) != len(set(ids)):
        raise SystemExit(f"{path}: duplicate place ids")
    for p in pack["places"]:
        if not ANCHOR_RE.match(str(p.get("anchor"))):
            raise SystemExit(f"{path}: place {p.get('id')}: anchor must be area, snap, J<id> or S<id>")
    return pack


def place_forms(p: dict[str, Any]) -> list[str]:
    """A pack place's forms: English name and base, variants, Marathi and Hindi names and variants."""
    forms = [p["en"], _base(p["en"]), *p.get("aka", [])]
    scripts = [p.get("mr") or "", p.get("hi") or "", *p.get("aka_mr", []), *p.get("aka_hi", [])]
    return _finish(_expand(forms) + [x for x in scripts if x] + [_base(x) for x in scripts if x])


def _junction_forms(j: dict[str, Any], landmarks: dict[str, Any], aliases: dict[str, Any]) -> list[str]:
    name = j["name"]
    forms = [name, _base(name)]
    mr = j.get("name_mr") or ""
    if mr:
        forms += [mr, _base(mr)]
        latin = translit.to_latin(_base(mr))
        if latin:
            forms.append(latin)
    key = j.get("key")
    lm = landmarks.get(j.get("landmark") or "")
    # the landmark's Hindi name belongs to the junction only when the junction is that landmark ("Esplanade"), not a
    # gate or a forecourt of it (the airport's two junctions)
    if lm and key == lm.get("id") and lm.get("hi"):
        forms.append(lm["hi"])
    forms += _aliases(aliases.get(key or ""))
    return _finish(_expand(forms))


def junction_forms(
    j: dict[str, Any],
    landmarks: dict[str, Any],
    aliases: dict[str, Any],
    place_forms_all: frozenset[str] = frozenset(),
    shared_bare: frozenset[str] = frozenset(),
) -> list[str]:
    """A junction's forms (module docstring), less every form a pack place carries and every bare word two
    junctions share (F-HONEST OSINT-1)."""
    return [
        f for f in _junction_forms(j, landmarks, aliases)
        if f not in place_forms_all and not (" " not in f and f in shared_bare)
    ]


def _point_like(name: str) -> bool:
    return bool(POINT_WORDS.intersection(name.split(" ")))


def _own_names(s: dict[str, Any]) -> frozenset[str]:
    return frozenset(norm(x) for x in (s["road_name"], _base(s["road_name"])))


def road_forms(s: dict[str, Any], road_aliases: dict[str, Any], junction_names: frozenset[str] = frozenset(),
               other_roads: frozenset[str] = frozenset()) -> list[str]:
    name = s["road_name"]
    base = _base(name)
    forms = [name, base]
    # a parenthesised part of a road name is that road's other name ("VIP Road (Kazi Nazrul Islam Avenue)")
    forms += [m.strip() for m in re.findall(r"\(([^)]*)\)", name) if any(
        w in PLACE_TYPE_WORDS for w in norm(m).split(" "))]
    totals: OrderedDict[str, float] = OrderedDict()
    whole = 0.0  # the segment's whole OSM length, its unnamed stretches included
    for pair in s.get("osm_names") or []:
        raw, length = (pair[0], float(pair[1])) if isinstance(pair, list) else (pair, 0.0)
        whole += length
        if not isinstance(raw, str) or raw.strip().lower() == "(unnamed)":
            continue
        for part in re.split(r"[,;]", raw):
            n = norm(part)
            if n:
                totals[n] = totals.get(n, 0.0) + length
    whole = whole or 1.0
    for n, length in totals.items():
        if n in other_roads:
            continue
        if _point_like(n):
            if n not in junction_names:
                forms.append(n)
        elif (length >= OSM_NAME_MIN_M and length / whole >= OSM_NAME_MIN_SHARE) or length >= OSM_NAME_LONG_M:
            forms.append(n)
    # the pack's colloquial forms: by any of the road's own Latin names ("Indira Gandhi Sarani" is Red Road)
    own = {norm(f) for f in forms}
    for split in [norm(x) for f in forms for x in re.split(r"\s+-\s+", _base(f))]:
        own.add(split)
    for key, table in road_aliases.items():
        if norm(key) in own:
            forms.extend(_aliases(table))
    return _finish(_expand(forms))


def _osm_extract_time(net: dict[str, Any]) -> str:
    base = net.get("osm_base")
    stamps = sorted(v for v in base.values() if isinstance(v, str)) if isinstance(base, dict) else []
    if not stamps:
        raise SystemExit("osm_network.json carries no osm_base extract time")
    return stamps[-1]


def _anchor_ids(anchor: str) -> tuple[int | None, int | None]:
    if anchor.startswith("J"):
        return int(anchor[1:]), None
    if anchor.startswith("S"):
        return None, int(anchor[1:])
    return None, None


def build(network_path: Path = NETWORK_JSON, pack_path: Path = PACK_JSON) -> dict[str, Any]:
    """The X19 document, built in memory from the network and the City Pack (deterministic)."""
    net = json.loads(network_path.read_text(encoding="utf-8"))
    pack = load_pack(pack_path)
    landmarks = {
        lm["id"]: lm for lm in json.loads(LANDMARKS_JSON.read_text(encoding="utf-8")).get("landmarks", [])
    }
    junctions = net.get("junctions") or []
    segments = net.get("segments") or []
    if not junctions or not segments:
        raise SystemExit("osm_network.json carries no junctions or segments")
    jids = {int(j["junction_id"]) for j in junctions}
    sids = {int(s["segment_id"]) for s in segments}
    j_aliases = pack.get("junction_aliases") or {}
    r_aliases = pack.get("road_aliases") or {}
    places = pack["places"]
    place_forms_all = frozenset(f for p in places for f in place_forms(p))
    seen: dict[str, int] = {}
    for j in junctions:
        for f in set(_junction_forms(j, landmarks, j_aliases)):
            if " " not in f:
                seen[f] = seen.get(f, 0) + 1
    shared_bare = frozenset(f for f, n in seen.items() if n > 1)
    entries: list[dict[str, Any]] = []
    # every road's own names (its name and base name): a junction named after the road it sits on ("Western Express
    # Highway (Sahar Elevated Road)", "Marine Drive (Veer Nariman Road, Churchgate)") never carries the road's bare
    # name, and a road never borrows another network road's own name from the OSM names along it (a short shared
    # stretch of "Lal Bahadur Shastri Marg" on the Eastern Express Highway)
    road_own = frozenset(norm(x) for s in segments for x in (s["road_name"], _base(s["road_name"])))
    jraw = {
        int(j["junction_id"]): junction_forms(j, landmarks, j_aliases, place_forms_all, shared_bare) for j in junctions
    }
    # every Latin form of the junctions: an OSM crossing named like one of them stays the junction's alone
    junction_names = frozenset(f for fs in jraw.values() for f in fs if f.isascii())
    rforms = {
        int(s["segment_id"]): [f for f in road_forms(s, r_aliases, junction_names, road_own - _own_names(s))
                               if f not in place_forms_all]
        for s in segments
    }
    road_all = frozenset(f for fs in rforms.values() for f in fs)
    jforms = {jid: [f for f in fs if f not in road_all] for jid, fs in jraw.items()}
    gid = 0
    for j in junctions:
        gid += 1
        entries.append(
            {
                "gaz_id": gid,
                "canonical_name": j["name"],
                "feature_type": "junction",
                "surface_forms": jforms[int(j["junction_id"])],
                "lon": round(float(j["lon"]), 7),
                "lat": round(float(j["lat"]), 7),
                "junction_id": int(j["junction_id"]),
                "segment_id": None,
                "importance": JUNCTION_IMPORTANCE[bool(j.get("signal_control"))],
                "source": "osm_network.junctions",
                "lang_primary": "en",
            }
        )
    for s in segments:
        gid += 1
        lon, lat = interior_point(s["line"])
        entries.append(
            {
                "gaz_id": gid,
                "canonical_name": s["road_name"],
                "feature_type": "road",
                "surface_forms": rforms[int(s["segment_id"])],
                "lon": round(lon, 7),
                "lat": round(lat, 7),
                "junction_id": None,
                "segment_id": int(s["segment_id"]),
                "importance": ROAD_IMPORTANCE.get(s.get("road_class"), 0.5),
                "source": "osm_network.segments",
                "lang_primary": "en",
            }
        )
    for p in places:
        gid += 1
        jid, sid = _anchor_ids(p["anchor"])
        if (jid is not None and jid not in jids) or (sid is not None and sid not in sids):
            raise SystemExit(f"pack place {p['id']}: anchor {p['anchor']} is not in the network")
        ftype = "neighbourhood" if p["anchor"] == "area" else p["feature_type"]
        if ftype in ("junction", "road"):
            raise SystemExit(f"pack place {p['id']}: a pack place is never a network junction or road")
        entries.append(
            {
                "gaz_id": gid,
                "canonical_name": p["en"],
                "feature_type": ftype,
                "surface_forms": place_forms(p),
                "lon": round(float(p["lon"]), 7),
                "lat": round(float(p["lat"]), 7),
                "junction_id": jid,
                "segment_id": sid,
                "importance": float(p["importance"]),
                "source": "city_pack." + str(p.get("source") or "hand").split(":")[0].replace(".json", ""),
                "lang_primary": "en",
            }
        )
    counts: dict[str, int] = {}
    for e in entries:
        counts[e["feature_type"]] = counts.get(e["feature_type"], 0) + 1
    doc = {
        "meta": {
            "generated_at": _osm_extract_time(net),
            "source": (
                f"Sajag OSINT place gazetteer ({CITY.title()}), generated by scripts/gen_osint_gazetteer.py: "
                f"{counts.get('road', 0)} roads and {counts.get('junction', 0)} junctions from "
                "scripts/data/osm_network.json (OpenStreetMap, English and Marathi names), "
                f"{len(places)} places of the City Pack cities/{CITY}/gazetteer.json "
                f"({counts.get('neighbourhood', 0)} areas, {counts.get('landmark', 0)} landmarks, "
                f"{counts.get('poi', 0)} police stations) in English, Marathi and Hindi with local variants; "
                "generated_at is the OpenStreetMap extract time; places only, no person or biometric field"
            ),
            "licence": LICENCE,
            "entries": len(entries),
        },
        "entries": entries,
    }
    problems = lint(doc)
    if problems:
        raise SystemExit("gazetteer lint failed:\n  " + "\n  ".join(problems[:60]))
    Gazetteer.from_document(doc)  # the loader's own X19 / places-only check
    return doc


def _phrase(s: str) -> str:
    """osint-common's phrase normal form (ASCII words only), for the place-phrase lint."""
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def lint(doc: dict[str, Any]) -> list[str]:
    """Places-only lints over a built document: every form in normal form and not a bare generic word, every
    multi-word Latin phrase (canonical name, its parenthesised parts, each form) carrying a place-type word or a
    road code, unless reviewed, no junction form that a pack place also carries, and no bare junction form two
    junctions share (F-HONEST OSINT-1: an area word is never a junction pin)."""
    problems: list[str] = []
    place_forms_all = {f for e in doc["entries"] if e["feature_type"] not in ("junction", "road")
                       for f in e["surface_forms"]}
    junction_bare: dict[str, int] = {}
    for e in doc["entries"]:
        if e["feature_type"] == "junction":
            for f in e["surface_forms"]:
                if " " not in f:
                    junction_bare[f] = junction_bare.get(f, 0) + 1
    for e in doc["entries"]:
        gid = e["gaz_id"]
        for f in e["surface_forms"]:
            if norm(f) != f:
                problems.append(f"gaz_id {gid}: form not in normal form: {f!r}")
            if not _good(f):
                problems.append(f"gaz_id {gid}: form is a bare generic word or too short: {f!r}")
        names = [e["canonical_name"], *(p for p in re.split(r"[()]", e["canonical_name"]) if p.strip())]
        if e["feature_type"] == "junction":
            for f in e["surface_forms"]:
                if f in place_forms_all:
                    problems.append(f"gaz_id {gid}: junction form shared with a pack place: {f!r}")
                if " " not in f and junction_bare.get(f, 0) > 1:
                    problems.append(f"gaz_id {gid}: bare junction form shared with another junction: {f!r}")
        for phrase in {_phrase(x) for x in (*names, *e["surface_forms"])}:
            if " " not in phrase or phrase in REVIEWED_PHRASES:
                continue
            if not any(w in PLACE_TYPE_WORDS or _ROAD_CODE.fullmatch(w) for w in phrase.split(" ")):
                problems.append(f"gaz_id {gid}: phrase without a place-type word: {phrase!r}")
    return problems


def render(doc: dict[str, Any]) -> str:
    """The committed file's exact text (indent 1, UTF-8, a final newline)."""
    return json.dumps(doc, ensure_ascii=False, indent=1) + "\n"


def _summary(doc: dict[str, Any]) -> str:
    entries = doc["entries"]
    by_type: dict[str, int] = {}
    for e in entries:
        by_type[e["feature_type"]] = by_type.get(e["feature_type"], 0) + 1
    forms = sum(len(e["surface_forms"]) for e in entries)
    return (
        f"{len(entries)} entries {json.dumps(by_type, sort_keys=True)}, {forms} surface forms, "
        f"generated_at {doc['meta']['generated_at']}"
    )


# ------------------------------------------------------------------------------------------- the Overpass review
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
USER_AGENT = "sajag-osint-gazetteer/1.0 (offline gazetteer review; one request; +https://github.com/shubro18202758/sajag)"


def overpass_query() -> str:
    b = json.loads(CITY_JSON.read_text(encoding="utf-8"))["bbox"]
    box = f"{b['south']},{b['west']},{b['north']},{b['east']}"
    return f'[out:json][timeout:60];(node["place"~"^(suburb|neighbourhood|quarter)$"]({box}););out tags;'


def overpass_review(response: dict[str, Any], doc: dict[str, Any]) -> list[str]:
    """OSM place nodes in the bbox whose name the gazetteer does not carry yet: review lines for a person to add
    to the City Pack (``cities/<city>/gazetteer.json``) by hand. Nothing is written."""
    known = {f for e in doc["entries"] for f in e["surface_forms"]}
    lines: list[str] = []
    for el in response.get("elements") or []:
        tags = el.get("tags") or {}
        name = tags.get("name:en") or tags.get("name")
        if not isinstance(name, str) or not name.strip():
            continue
        n = norm(name)
        if not n or n in known:
            continue
        lat, lon = el.get("lat"), el.get("lon")
        near = difflib.get_close_matches(n, sorted(known), n=1, cutoff=0.85)
        hint = f" (close to known form {near[0]!r})" if near else ""
        lines.append(f"candidate: {name} [place={tags.get('place')}] at {lat}, {lon}{hint}")
    return sorted(set(lines))


def _fetch_overpass() -> dict[str, Any]:
    body = urllib.parse.urlencode({"data": overpass_query()}).encode("ascii")
    req = urllib.request.Request(OVERPASS_URL, data=body, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=90) as r:  # noqa: S310 - fixed https endpoint, opt-in only
        return json.loads(r.read().decode("utf-8"))


def _write_atomic(path: Path, text: str) -> None:
    """Replace ``path`` atomically, keeping its permission bits (a new file gets the umask's)."""
    if path.exists():
        mode = path.stat().st_mode & 0o777
    else:
        umask = os.umask(0)
        os.umask(umask)
        mode = 0o666 & ~umask
    fd, tmp = tempfile.mkstemp(prefix=".osint_gazetteer.", suffix=".json", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true", help="rewrite scripts/data/osint_gazetteer.json")
    mode.add_argument("--check", action="store_true", help="exit 1 when the committed file differs from a rebuild")
    mode.add_argument("--overpass", action="store_true", help="opt-in review of OSM place nodes (never in gates)")
    ap.add_argument("--overpass-json", type=Path, help="a saved Overpass response for --overpass (offline)")
    ap.add_argument("--network", type=Path, default=NETWORK_JSON, help=argparse.SUPPRESS)
    ap.add_argument("--pack", type=Path, default=PACK_JSON, help=argparse.SUPPRESS)
    ap.add_argument("--out", type=Path, default=OUT_JSON, help=argparse.SUPPRESS)
    args = ap.parse_args(argv)

    doc = build(args.network, args.pack)
    text = render(doc)
    current = args.out.read_text(encoding="utf-8") if args.out.is_file() else None

    if args.overpass:
        response = (
            json.loads(args.overpass_json.read_text(encoding="utf-8")) if args.overpass_json else _fetch_overpass()
        )
        lines = overpass_review(response, doc)
        print(f"overpass review: {len(lines)} place name(s) not in the gazetteer (review by hand; nothing written)")
        for line in lines:
            print("  " + line)
        return 0
    if args.check:
        if current == text:
            print(f"gazetteer OK: {args.out.relative_to(REPO_ROOT) if args.out.is_relative_to(REPO_ROOT) else args.out}"
                  f" matches a rebuild ({_summary(doc)})")
            return 0
        print(f"gazetteer DIFFERS from a rebuild: run {Path(__file__).name} --write ({_summary(doc)})",
              file=sys.stderr)
        if current is not None:
            diff = difflib.unified_diff(
                current.splitlines(), text.splitlines(), "committed", "rebuild", lineterm="", n=1
            )
            for i, line in enumerate(diff):
                if i >= 40:
                    print("  ...", file=sys.stderr)
                    break
                print("  " + line, file=sys.stderr)
        return 1
    if args.write:
        if current == text:
            print(f"gazetteer unchanged ({_summary(doc)})")
            return 0
        _write_atomic(args.out, text)
        print(f"gazetteer written: {args.out} ({_summary(doc)})")
        return 0
    print(f"gazetteer rebuild: {_summary(doc)}; committed file {'matches' if current == text else 'DIFFERS'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
