"""Grounding enforced in code — the assistant states only what it was told.

The tactical model is asked (by prompt) to state only what the tool results
contain; this module makes that a rule the code applies, whatever the model
writes. Three layers, all deterministic and pure:

1. PROVENANCE of tool arguments (before a tool runs). Every road-segment id
   a drafted call carries must come from somewhere real — the operator's
   message, the session context (the selected event's spines, the movement's
   plan) or an earlier tool result in the session. An ETA asked of
   ``predict_eta`` must stand on a route length and a speed that a tool
   reported; softer inputs that nobody reported are labelled ASSUMED INPUTS.
   A call that fails the check is refused and the refusal is shown.

2. ROAD NAMES the operator types are resolved against the city road network
   (one read of the segments in the city bounding box): "Strand Road" names
   its segments, and the short forms the city uses ("WEH", "LBS Marg",
   "SV Road") name the roads the network spells in full; a name the
   network does not carry is said plainly — "no road segment named X" — and
   never answered with another road's data.

3. The FINAL PROSE is checked sentence by sentence against the evidence —
   this turn's tool results, the session context and the operator's own
   words. A sentence is removed when it names a road or place no tool
   reported (or one only the question named, attached to a reading, a time
   or a position), quotes a figure with a unit, a decimal reading, a clock
   time or a segment id that no tool returned, places a vehicle the lookups
   did not find, or gives a unit ETA while no unit is fielded. The answer
   says how many statements were removed and why, and states the
   deterministic facts instead (the vehicle is not in the city picture, no
   segment carries that name, no unit is fielded). A position quoted for a
   "right now" question from a stale sighting carries the sighting's age.
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

# ---------------------------------------------------------------------------
# Evidence: the numbers and the text the tools and the session reported
# ---------------------------------------------------------------------------

#: Keys whose numbers are positions / identifiers, never a reading the prose
#: may quote (coordinates would otherwise ground almost any decimal).
_NUMERIC_SKIP_KEYS = frozenset({
    "lon", "lat", "coordinates", "geometry", "geojson", "zone_geojson", "bbox",
    "osm_way_id", "min_lon", "min_lat", "max_lon", "max_lat",
})
#: A number inside free text (not a fragment of a uuid, plate or word).
_NUMBER_IN_TEXT_RE = re.compile(r"(?<![\w.•-])\d+(?:\.\d+)?(?![\w•])")


def numbers_in(value: Any, into: set[float] | None = None, depth: int = 0) -> set[float]:
    """Every finite number a payload carries (strings scanned too), bounded."""
    out = into if into is not None else set()
    if depth > 8 or len(out) > 20_000:
        return out
    if isinstance(value, bool):
        return out
    if isinstance(value, (int, float)):
        if math.isfinite(value):
            out.add(float(value))
        return out
    if isinstance(value, str):
        for match in _NUMBER_IN_TEXT_RE.findall(value[:20_000]):
            out.add(float(match))
        return out
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key) in _NUMERIC_SKIP_KEYS:
                continue
            if isinstance(key, str) and re.fullmatch(r"\d+(?:\.\d+)?", key):
                out.add(float(key))  # horizon-keyed rows ({"30": {...}})
            numbers_in(item, out, depth + 1)
        return out
    if isinstance(value, (list, tuple)):
        for item in value[:500]:
            numbers_in(item, out, depth + 1)
    return out


def text_of(value: Any, depth: int = 0, limit: int = 200_000) -> str:
    """The strings a payload carries, space-joined (for name evidence)."""
    parts: list[str] = []
    size = [0]

    def walk(item: Any, level: int) -> None:
        if level > 8 or size[0] > limit:
            return
        if isinstance(item, str):
            parts.append(item)
            size[0] += len(item)
        elif isinstance(item, dict):
            for key, sub in item.items():
                if str(key) in _NUMERIC_SKIP_KEYS:
                    continue
                walk(sub, level + 1)
        elif isinstance(item, (list, tuple)):
            for sub in item[:500]:
                walk(sub, level + 1)

    walk(value, depth)
    return " ".join(parts)


#: The unit changes a prose figure may have gone through from a tool's number
#: (seconds -> minutes, metres -> km, fraction -> percent ...), per prose unit.
_UNIT_SCALES = {
    "min": (1.0, 1 / 60.0),
    "s": (1.0, 60.0),
    "h": (1.0, 1 / 60.0, 1 / 3600.0),
    "km": (1.0, 1 / 1000.0),
    "m": (1.0, 1000.0),
    "%": (1.0, 100.0),
    None: (1.0, 1 / 100.0, 1 / 60.0, 1 / 1000.0),  # a bare decimal / unknown
}


def _unit_key(unit: str | None) -> str | None:
    u = (unit or "").lower().replace(" ", "")
    if not u:
        return None
    if u.startswith(("km/h", "kmph", "kph", "km/hr")) or u.startswith(("vehicle", "lane")):
        return "same"
    if u.startswith(("km", "kilomet")):
        return "km"
    if u.startswith(("min",)):
        return "min"
    if u.startswith(("sec",)) or u == "s":
        return "s"
    if u.startswith(("hour", "hr")) or u == "h":
        return "h"
    if u.startswith(("m", "met")):
        return "m"
    if u.startswith(("%", "percent", "per")):
        return "%"
    return None


def number_grounded(value: float, evidence: Iterable[float], unit: str | None = None) -> bool:
    """True when ``value`` is one of the evidence numbers — directly, rounded
    or truncated, or through the plain unit change its prose unit allows
    (seconds -> minutes for 'min', metres -> km for 'km', fraction -> percent
    for '%'); a reading in km/h, lanes or vehicles must match as it stands."""
    key = _unit_key(unit)
    scales = (1.0,) if key == "same" else _UNIT_SCALES.get(key, _UNIT_SCALES[None])
    for base in evidence:
        for scale in scales:
            cand = base * scale
            if abs(cand - value) <= max(0.051, 0.015 * abs(cand)):
                return True
            if value == int(value) and cand >= 1 and abs(cand - value) < 1 and (
                    math.floor(cand) == value or round(cand) == value):
                return True
    return False


# ---------------------------------------------------------------------------
# Road / place names
# ---------------------------------------------------------------------------

#: Suffixes that make a phrase a ROAD the network may carry (resolved) —
#: Mumbai's roads end in Road, Marg, Highway, Setu, Flyover ... (a second
#: pack's in Street, Avenue, Sarani, Bypass)
ROAD_SUFFIXES = (
    "road", "rd", "street", "avenue", "sarani", "setu", "bypass", "marg", "flyover",
    "bridge", "highway", "expressway", "underpass", "overbridge",
)
#: Further suffixes that make a phrase a PLACE (checked in prose, not resolved).
PLACE_SUFFIXES = ROAD_SUFFIXES + (
    "crossing", "circle", "chowk", "crossroads", "crossroad", "junction", "station",
    "ghat", "phari", "chowrasta", "gate", "lake", "stadium", "market", "bazar", "bazaar",
)
#: The short forms a city writes road names with: Mumbai's (the live city —
#: "WEH" names the Western Express Highway, "LBS Marg" Lal Bahadur Shastri
#: Marg, "SV Road" Swami Vivekanand Road) and the second pack's, as each City
#: Pack lists them (cities/<city>/corridors.json ``name_aliases`` — pinned in
#: lockstep by the tests — plus "JL", "SN" and "RG"): a token expands to the
#: words the network spells, on either side of a comparison.
NAME_ALIASES: dict[str, tuple[str, ...]] = {
    "weh": ("western", "express"),
    "eeh": ("eastern", "express"),
    "lbs": ("lal", "bahadur", "shastri"),
    "sv": ("swami", "vivekanand"),
    "jvlr": ("jogeshwari", "vikhroli"),
    "sclr": ("santacruz", "chembur"),
    "bkc": ("bandra", "kurla", "complex"),
    "ajc": ("acharya", "jagadish", "chandra"),
    "apc": ("acharya", "prafulla", "chandra"),
    "sp": ("shyama", "prasad"),
    "em": ("eastern", "metropolitan"),
    "vip": ("kazi", "nazrul", "islam"),
    "cr": ("chittaranjan",),
    "mg": ("mahatma", "gandhi"),
    "dh": ("diamond", "harbour"),
    "gt": ("grand", "trunk"),
    "jl": ("jawaharlal",),
    "sn": ("surendra", "nath"),
    "rg": ("radha", "gobinda"),
}
#: Words that end a name when walking back from its suffix.
_STOP_WORDS = frozenset("""
a an the on at near of for in into onto to from via along and or but is are was were be been
what whats how which where when why who whom whose live current currently congestion congested
traffic speed speeds average avg flow status right now today tonight this that these those my our
your its their his her nearest closest same main service any every each other one two both all
there here it they we you i me us show tell give get find check please about around between
across through over under by with without towards toward heading moving seen last next
forecast predict prediction eta time travel jam jams delay delays closure closures closed
diversion diversions the reading readings data no not
""".split())
_WORD_RE = re.compile(r"[A-Za-z0-9][\w.'’-]*")


def _norm_name(text: str) -> str:
    """lower-case, punctuation to spaces, 'rd' -> 'road', initials joined
    ('A.J.C.' -> 'ajc'), short forms spelled out ('em' -> 'eastern
    metropolitan', :data:`NAME_ALIASES`), spaces collapsed."""
    lowered = re.sub(r"[^\w\s]", " ", str(text).lower().replace("’", "'"))
    joined: list[str] = []
    run: list[str] = []
    for w in lowered.split() + [""]:
        if len(w) == 1 and w.isalpha():
            run.append(w)
            continue
        joined.extend(["".join(run)] if len(run) > 1 else run)
        run = []
        if w:
            joined.append(w)
    words: list[str] = []
    for w in joined:
        if w == "rd":
            words.append("road")
        else:
            words.extend(NAME_ALIASES.get(w, (w,)))
    return " ".join(words)


def place_names(text: str, *, roads_only: bool = False, require_capital: bool = True) -> list[str]:
    """Road / place names in ``text`` ('Strand Road', 'Park Circus seven-point crossing').

    A name is up to four words before a road or place suffix, walking back
    until a stop word. ``require_capital`` (prose) keeps only names whose
    words start upper-case or are numbers; the operator's own message is
    read case-insensitively.
    """
    suffixes = ROAD_SUFFIXES if roads_only else PLACE_SUFFIXES
    tokens = [(m.group(0), m.start(), m.end()) for m in _WORD_RE.finditer(str(text))]
    names: list[str] = []
    for i, (word, _start, end) in enumerate(tokens):
        bare = word.rstrip(".'’-").lower()
        if bare not in suffixes:
            continue
        if require_capital and not word[:1].isupper():
            continue
        picked: list[str] = []
        j = i - 1
        while j >= 0 and len(picked) < 4:
            prev, _ps, pe = tokens[j]
            gap = text[pe:tokens[j + 1][1]]
            if any(c in gap for c in ",;:!?()\n") or "." in gap.strip():
                break
            low = prev.lower().rstrip(".'’-")
            if low in _STOP_WORDS or low in suffixes:
                break
            if require_capital and not (prev[:1].isupper() or prev[:1].isdigit()):
                break
            picked.insert(0, prev)
            j -= 1
        if not picked:
            continue
        start = tokens[j + 1][1]
        names.append(str(text)[start:end].strip(" .'’-"))
    return list(dict.fromkeys(names))


def name_in(name: str, corpus_norm: str) -> bool:
    """True when the normalized name occurs as whole words in the corpus."""
    needle = _norm_name(name)
    return bool(needle) and f" {needle} " in f" {corpus_norm} "


def resolve_road_name(name: str, segments: list[dict]) -> list[dict]:
    """The segments a road name the operator typed names (best first).

    'Strand Road' matches 'Strand Road' and 'Strand Road - Strand Bank Road';
    'Red Road' matches 'Indira Gandhi Sarani (Red Road)' (a bracket holds the
    road's other name) and 'EM Bypass' matches 'Eastern Metropolitan Bypass'
    (:data:`NAME_ALIASES`); a name the network does not carry matches nothing
    (never the nearest spelling).
    """
    want = _norm_name(name)
    if not want:
        return []
    out = []
    for row in segments:
        if not isinstance(row, dict) or not isinstance(row.get("road_name"), str):
            continue
        full = _norm_name(row["road_name"])
        # the name outside the brackets ('Mother Teresa Sarani') and the other
        # names inside them ('(Park Street)', '(NH12, Vidyasagar Flyover)'),
        # never the endpoints a bracket names ('(Red Road–Hastings)')
        core = _norm_name(re.sub(r"\(.*?\)", " ", row["road_name"]))
        others = [
            _norm_name(part)
            for inner in re.findall(r"\((.*?)\)", row["road_name"])
            if not re.search(r"[–—]|\bto\b", inner)
            for part in inner.split(",")
        ]
        if want == full or any(f" {want} " in f" {c} " for c in (core, *others) if c) or (
            full.startswith(want + " ")
        ) or (
            len(core) >= 6 and f" {core} " in f" {want} "
            and set(want.split()) <= set(full.split())
        ):
            out.append({"segment_id": row.get("segment_id"), "road_name": row["road_name"]})
    return out


# ---------------------------------------------------------------------------
# Claims in a sentence
# ---------------------------------------------------------------------------

_UNIT = (
    r"km\s*/\s*h|kmph|kph|km/hr|kms?\b|kilomet(?:re|er)s?|m\b|met(?:re|er)s?|"
    r"min(?:ute)?s?\b|sec(?:ond)?s?\b|s\b|hours?\b|hrs?\b|h\b|%|per\s*cent|percent|"
    r"vehicles?\b|lanes?\b"
)
_MEASURE_RE = re.compile(rf"(?<![\w.•])(\d+(?:\.\d+)?)\s*({_UNIT})", re.IGNORECASE)
_DURATION_RE = re.compile(
    r"(?<![\w.])(\d+)\s*min(?:ute)?s?\s*(?:and\s*)?(\d+)\s*sec(?:ond)?s?\b", re.IGNORECASE)
_DECIMAL_RE = re.compile(r"(?<![\w.•])(\d+\.\d+)(?![\w.•])")
_CLOCK_RE = re.compile(r"\b([01]?\d|2[0-3]):([0-5]\d)\b")
_SEGMENT_IDS_RE = re.compile(
    r"\bsegments?\s+((?:\d{3,8})(?:\s*(?:,|and|&|/|-|to)\s*\d{3,8})*)|\((\d{3,8})\)",
    re.IGNORECASE,
)
_LOCATION_CLAIM_RE = re.compile(
    r"\b(seen|spotted|sighted|located|locate|is at|was at|is on|was on|heading|moving|"
    r"travell?ing|parked|stationed|passed|crossing|last read|positioned)\b",
    re.IGNORECASE,
)
_NEGATION_RE = re.compile(
    r"\b(no|not|none|never|nothing|cannot|can't|couldn't|unknown|unavailable|isn't|wasn't|"
    r"doesn't|didn't|without|neither|nor|absent|missing)\b",
    re.IGNORECASE,
)
_UNIT_WORDS_RE = re.compile(
    r"\b(ambulances?|units?|patrols?|police|fire tenders?|tenders?|pcr|civic volunteers?)\b",
    re.IGNORECASE,
)
_ETA_WORDS_RE = re.compile(r"\b(eta|arriv\w*|reach\w*|minutes?|mins?|away|en route)\b",
                           re.IGNORECASE)
#: Abbreviations a sentence never ends on ('Dr. Sundari Mohan Avenue', 'St. Paul's Cathedral').
_ABBREV_RE = re.compile(r"\b(?:Dr|Ft|No|St|Mr|Ms|Mrs|Sr|Jr|vs|approx|e\.g|i\.e)\.$", re.IGNORECASE)


def sentences(prose: str) -> list[str]:
    """Split prose into sentences (not after 'Dr.' / 'Ft.' or inside a number)."""
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9(\"'])", prose.strip())
    out: list[str] = []
    for part in parts:
        if out and _ABBREV_RE.search(out[-1]):
            out[-1] = out[-1] + " " + part
        else:
            out.append(part)
    return [p for p in out if p.strip()]


def masked_plate_prefixes(text: str) -> list[str]:
    """'MH02AB' for each masked mark ('MH02AB•••4') in text."""
    return [m.upper() for m in re.findall(r"\b([A-Za-z]{2}\d{1,2}[A-Za-z]{0,3})•••\w", text)]


def plate_prefix(raw: str) -> str:
    """The masked-form prefix of a typed mark: series up to the last four digits."""
    compact = re.sub(r"[\s.-]", "", raw).upper()
    return compact[:-4] if len(compact) > 4 else compact


class Evidence:
    """What the prose may stand on: tool results, session context, question."""

    def __init__(
        self,
        *,
        tool_payloads: Iterable[Any] = (),
        tool_summaries: Iterable[str] = (),
        context_text: str = "",
        question: str = "",
        earlier: str = "",
        extra_numbers: Iterable[float] = (),
    ) -> None:
        payloads = list(tool_payloads)
        summaries = [s for s in tool_summaries if isinstance(s, str)]
        tool_text = " ".join([text_of(p) for p in payloads] + summaries)
        self.tool_norm = _norm_name(tool_text + " " + context_text + " " + earlier)
        self.question = question or ""
        self.question_norm = _norm_name(self.question)
        nums: set[float] = set(extra_numbers)
        for payload in payloads:
            numbers_in(payload, nums)
        for text in summaries + [context_text, earlier, self.question]:
            numbers_in(text, nums)
        self.numbers = nums
        self.integers = {int(n) for n in nums if n == int(n)}

    def place_status(self, name: str) -> str:
        """'tool' (reported), 'question' (only the operator named it) or 'none'."""
        if name_in(name, self.tool_norm):
            return "tool"
        # 'Indira Gandhi Sarani' in prose is grounded by 'Indira Gandhi Sarani
        # (Red Road)' in a result
        if name_in(re.sub(r"\(.*?\)", " ", name), self.tool_norm):
            return "tool"
        if name_in(name, self.question_norm):
            return "question"
        return "none"


def sentence_claims(sentence: str, ev: Evidence, *, unfound_plates: Iterable[str] = (),
                    zero_units: bool = False) -> list[str]:
    """The ungrounded claims one sentence makes ([] when it may stand)."""
    reasons: list[str] = []
    negated = bool(_NEGATION_RE.search(sentence))
    measured = bool(_MEASURE_RE.search(sentence) or _DECIMAL_RE.search(sentence)
                    or _CLOCK_RE.search(sentence))
    locating = bool(_LOCATION_CLAIM_RE.search(sentence))

    for name in place_names(sentence):
        status = ev.place_status(name)
        if status == "tool":
            continue
        if status == "question":
            if (measured or locating) and not negated:
                reasons.append(f"'{name}' (no tool reported it)")
        elif not negated:
            reasons.append(f"'{name}' (no tool reported it)")

    scratch = sentence
    for m in _DURATION_RE.finditer(sentence):
        total = int(m.group(1)) * 60 + int(m.group(2))
        if not number_grounded(float(total), ev.numbers, "s"):
            reasons.append(f"'{m.group(0)}' (no tool returned it)")
        scratch = scratch.replace(m.group(0), " ")
    for m in _MEASURE_RE.finditer(scratch):
        if not number_grounded(float(m.group(1)), ev.numbers, m.group(2)):
            reasons.append(f"'{m.group(0).strip()}' (no tool returned it)")
    for m in _DECIMAL_RE.finditer(_MEASURE_RE.sub(" ", scratch)):
        if not number_grounded(float(m.group(1)), ev.numbers):
            reasons.append(f"'{m.group(1)}' (no tool returned it)")
    for m in _CLOCK_RE.finditer(sentence):
        if not _clock_in(m.group(0), ev):
            reasons.append(f"'{m.group(0)}' (no tool reported that time)")
    for m in _SEGMENT_IDS_RE.finditer(sentence):
        ids = [int(x) for x in re.findall(r"\d{3,8}", m.group(1) or m.group(2) or "")]
        bad = [i for i in ids if i not in ev.integers]
        if bad:
            reasons.append("segment " + ", ".join(str(i) for i in bad) + " (no tool returned it)")

    if not negated:
        named = set(masked_plate_prefixes(sentence)) | {
            plate_prefix(p) for p in re.findall(
                r"\b[A-Za-z]{2}[ -]?\d{1,2}[ -]?[A-Za-z]{0,3}[ -]?\d{4}\b", sentence)
        }
        for prefix in unfound_plates:
            if prefix in named and (locating or measured or place_names(sentence)):
                reasons.append("a position for a vehicle the lookups did not find")
                break
        for prefix in named - set(unfound_plates):
            if not _plate_in(prefix, ev):
                reasons.append(f"vehicle {prefix}••• (no tool reported it)")
        if zero_units and _UNIT_WORDS_RE.search(sentence) and _ETA_WORDS_RE.search(sentence) \
                and (measured or re.search(r"\barriv|\breach|\beta\b", sentence, re.I)):
            reasons.append("a unit ETA while no unit is fielded")
    return list(dict.fromkeys(reasons))


def _plate_in(prefix: str, ev: Evidence) -> bool:
    """A registration-mark series a tool (or the operator) reported, masked or raw."""
    corpus = f" {ev.tool_norm} {ev.question_norm} "
    return re.search(rf"\s{re.escape(prefix.lower())}(?:\s|\d{{4}}\b)", corpus) is not None


def _clock_in(clock: str, ev: Evidence) -> bool:
    """A clock time a tool (or the operator) reported — '22:08' or '22 08' normalized."""
    hh, mm = clock.split(":")
    corpus = f" {ev.tool_norm} {ev.question_norm} "
    return any(f" {h} {mm} " in corpus for h in (f"{int(hh):02d}", str(int(hh))))


def enforce(prose: str, ev: Evidence, *, unfound_plates: Iterable[str] = (),
            zero_units: bool = False) -> tuple[str, list[str]]:
    """``(kept prose, removed claims)`` — every failing sentence dropped."""
    kept: list[str] = []
    removed: list[str] = []
    plates = list(unfound_plates)
    for sentence in sentences(prose):
        claims = sentence_claims(sentence, ev, unfound_plates=plates, zero_units=zero_units)
        if claims:
            removed.extend(claims)
        else:
            kept.append(sentence)
    return " ".join(kept).strip(), list(dict.fromkeys(removed))


#: What each kind of removed claim is called in the operator's note (the
#: removed values themselves are never repeated there — only audited).
_CLAIM_KINDS = (
    ("••• (no tool reported it)", "a vehicle"),
    ("no tool reported it", "a place"),
    ("no tool returned it", "a figure"),
    ("no tool reported that time", "a time"),
    ("vehicle the lookups did not find", "a position for a vehicle not found"),
    ("no unit is fielded", "a unit ETA with no unit fielded"),
)


def removal_note(removed: list[str], count: int) -> str:
    """The sentence that tells the operator what the check took out — by
    kind ('a place', 'a figure'), never repeating the invented value."""
    kinds = []
    for claim in removed:
        kind = next((name for marker, name in _CLAIM_KINDS if marker in claim), "a claim")
        if claim.startswith("segment "):
            kind = "a segment id"
        if kind not in kinds:
            kinds.append(kind)
    noun = "statement" if count == 1 else "statements"
    return (
        f"(Grounding check: {count} {noun} removed — naming {', '.join(kinds)} that no "
        "tool or the session context reports. Sajag states only what its tools report.)"
    )


# ---------------------------------------------------------------------------
# Tool-argument provenance
# ---------------------------------------------------------------------------

#: Arguments that carry road-segment ids, per tool (nested scenarios too).
SEGMENT_ARG_KEYS = (
    "segment_ids", "route_segment_ids", "avoid_segments", "segment_id",
    "origin_segment", "destination_segment", "source_segment", "target_segment",
)
#: Tools that read or plan over named segments: their ids must be grounded.
SEGMENT_TOOLS = frozenset({
    "predict_traffic_flow", "get_live_traffic", "get_historical_pattern",
    "query_segment_details", "find_convoy_routes", "find_corridor_routes", "plan_diversions",
    "plan_event_diversions", "evaluate_scenarios", "query_shortest_path",
    "query_k_shortest_paths", "simulate_twin", "predict_eta",
})
#: Tools whose arguments the by-name resolver may fill with resolved ids.
SEGMENT_LIST_TOOLS = frozenset({"predict_traffic_flow", "get_live_traffic"})
SINGLE_SEGMENT_TOOLS = frozenset({"query_segment_details", "get_historical_pattern"})


def segment_ids_of(arguments: dict) -> list[Any]:
    """Every segment id a drafted call carries (values as drafted)."""
    found: list[Any] = []

    def take(value: Any) -> None:
        if isinstance(value, list):
            found.extend(value)
        elif value is not None:
            found.append(value)

    for key in SEGMENT_ARG_KEYS:
        if key in arguments:
            take(arguments[key])
    for scenario in arguments.get("scenarios") or []:
        if isinstance(scenario, dict):
            take(scenario.get("route_segment_ids"))
    return found


def ungrounded_ids(arguments: dict, grounded: set[int]) -> list[Any]:
    """The drafted segment ids that no source reported (non-integers too)."""
    bad = []
    for value in segment_ids_of(arguments):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value != int(value):
            bad.append(value)
        elif int(value) not in grounded:
            bad.append(int(value))
    return bad


#: predict_eta inputs that must be reported by a tool (or typed by the operator).
ETA_CORE_INPUTS = ("route_length_m", "avg_predicted_speed")
#: predict_eta inputs that are labelled ASSUMED when nothing reported them.
ETA_SOFT_INPUTS = ("num_segments", "avg_predicted_congestion", "num_signals",
                   "road_class_score", "hour", "day_of_week")
IST = timezone(timedelta(hours=5, minutes=30))


def eta_input_check(arguments: dict, numbers: set[float],
                    now: datetime | None = None) -> tuple[list[str], list[str]]:
    """``(ungrounded core inputs, assumed soft inputs)`` of a predict_eta draft."""
    core = []
    for key, unit in zip(ETA_CORE_INPUTS, ("m", "km/h")):
        value = arguments.get(key)
        if not isinstance(value, (int, float)) or isinstance(value, bool) \
                or not number_grounded(float(value), numbers, unit):
            core.append(key)
    moment = (now or datetime.now(UTC)).astimezone(IST)
    assumed = []
    for key in ETA_SOFT_INPUTS:
        value = arguments.get(key)
        if value is None:
            continue
        if key == "hour" and value == moment.hour:
            continue
        if key == "day_of_week" and value == moment.weekday():
            continue
        if isinstance(value, (int, float)) and not isinstance(value, bool) \
                and number_grounded(float(value), numbers):
            continue
        assumed.append(key)
    return core, assumed


# ---------------------------------------------------------------------------
# Lookups that found nothing
# ---------------------------------------------------------------------------

#: List-valued keys that carry a tool's data rows.
_DATA_KEYS = (
    "entities", "observations", "units", "dispatches", "events", "predictions", "segments",
    "rows", "items", "routes", "recommendations", "entries", "aggregates",
    "synthetic_aggregates", "diversions", "results", "paths", "path", "junctions", "chokes",
    "matches",
)


def payload_empty(payload: Any, ok: bool) -> bool:
    """True when a tool failed or answered with no data rows at all."""
    if not ok:
        return True
    if not isinstance(payload, dict):
        return payload in (None, [], "")
    if isinstance(payload.get("road_names"), list):  # the road-name resolution
        return not any(isinstance(r, dict) and r.get("found") for r in payload["road_names"])
    if "entity" in payload and not payload.get("entity") and not payload.get("related"):
        return True
    present = [k for k in _DATA_KEYS if k in payload]
    if not present:
        return False
    if payload.get("eta_seconds") is not None:
        return False
    return all(not payload.get(k) for k in present)


def age_text(age_sec: float) -> str:
    """'2.6 days' / '5 h' / '12 min' — an observation's age, plainly."""
    if age_sec >= 2 * 86400:
        return f"{age_sec / 86400:.1f} days"
    if age_sec >= 2 * 3600:
        return f"{age_sec / 3600:.0f} h"
    if age_sec >= 120:
        return f"{age_sec / 60:.0f} min"
    return f"{age_sec:.0f} s"
