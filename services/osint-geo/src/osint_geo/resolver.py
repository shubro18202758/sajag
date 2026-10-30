"""The geo-resolver (OSINT SPEC §1.4; research A2–A8): a :class:`RawOsintSignal` → a :class:`Geocode`, or ``None``.

:class:`GazetteerResolver` implements ``osint_common.pipeline.GeoResolver``. Offline and deterministic: it reads the
gazetteer and the network once and calls nothing else. For one signal (its title, its text and the connector's
place-name hints, read together in the PoC's order):

1. **Extract** (:meth:`GazetteerResolver.mentions`): the gazetteer's longest-match scan, plus the place grammar's
   rewrites of short place words ("Matunga stn" → Matunga station). Every non-overlapping occurrence is a
   mention. The text is the title, the text and the first :data:`MAX_HINTS` geo hints (:data:`MAX_HINT_CHARS`
   characters each: connectors send one to three short names). No form, rewrite or fuzzy window spans a sentence
   end (:meth:`GazetteerResolver.tokens`): "Fire at Worli. Naka traders shut shops" names the area, never "Worli
   Naka", the junction.
2. **Candidates**: each mention reads as every place its form names (exact alias, match 1.0). Only when nothing
   matches exactly, fuzzy matching (``difflib`` ratio ≥ 0.90, trigram-prefiltered): first the grammar's cue-bound
   names ("near Rajawadi Hopsital"), then three-word and then two-word windows; every occurrence of a matching name is
   a mention, so a misspelt place never reads as surer than the same place spelt right. **Stoplist guard** (the
   PoC's "India" ↔ "indira" fix): fuzzy matching is multi-word only (a window of at least two words and eight
   characters, against multi-word forms), never on a window holding a locality or newsroom word
   (:data:`FUZZY_STOP`) or made only of generic words (``gazetteer.GENERIC_STOPWORDS``), and no single generic
   word is ever a surface form. **Context gate**: a form that names a Mumbai place only in a text about Mumbai
   (:data:`CONTEXT_FORMS`: a common word, "fort" or "khar"; a name other cities share, "Marine Drive" (Kochi),
   "Coastal Road", "Atal Setu" (Goa), "LBS Marg", "Santacruz", "Shivaji Park", "Mahalaxmi" (Kolhapur); and every
   bare route code) is a mention only when the signal is placed in the city: by its own metadata
   (:meth:`GazetteerResolver.city_scoped`: r/mumbai, the BMC slot or the Mumbai Traffic Police notices as the
   source, a geo hint naming Mumbai or Bombay, a city district code ``LGD:MUMBAI``/``LGD:MUMBAI_SUBURBAN``, a
   Mumbai PIN) or by its text naming the city (:data:`CITY_WORDS`). State-level evidence never opens the gate
   (SACHET or the state SDMA slot as the source, ``LGD:MAHARASHTRA``, ``GDELT_ADM1:IN16``, a hint naming only
   Maharashtra: Pune has a Shivaji Park too). With the gate closed such a form is not read at all, exactly or
   fuzzily (a window that is a gated form never fuzzy-matches a longer one). The longer forms that carry the place
   ("Marine Lines station", "Khar Police Station", "Netaji Subhash Chandra Bose Road") are never gated. **Another
   thing of the same name** (:data:`NOT_A_PLACE_BEFORE`): "Dadar Express" and "LTT Duronto" are trains and "Kurla
   taluka" is the taluka, never the place. **The state gate** (:data:`STATE_GATED_FORMS`): a signal with
   state-level evidence (:meth:`GazetteerResolver.state_scoped`) and no city-level evidence (the context gate
   closed) does not read the bare "Andheri", "Borivali" or "Kurla" in any spelling: a state-wide alert names
   districts and talukas, not the city's areas.
3. **Disambiguation**: each reading scores
   ``R = 0.25·in_bbox + 0.15·specificity + 0.20·coherence + 0.10·importance + 0.10·source_locality + 0.10·match``
   (research A6's weights, the embedding-context term left off: the Embedder is OS-4's). Coherence is the share of
   the other readings (at another point) within 8 km. The best R wins; ties go to the longer, then earlier mention.
4. **Snap** (:mod:`osint_geo.snap`): a junction toponym keeps its ``junction_id``, a road its ``segment_id``; a
   landmark attaches to the segment whose anchor is nearest (residual = geodesic metres to that anchor), or with
   no anchor in reach to the nearest road line, but only within 900 m (``confidence.SNAP_ANCHOR_MAX_M``, fusion's
   on-segment limit): farther it has no road anchor and no snap quality. A **neighbourhood is an area** and never
   gets a road anchor (F-HONEST OSINT-3: a bare area word is not a street; it was snapped up to 2.5 km away).
5. **Confidence** (:mod:`osint_geo.confidence`), with the margin between the best and the runner-up reading. Every
   mention is a reading (the PoC's semantics, on which the R23 figures are calibrated): a place named twice ties
   with itself, so the margin term pays out only for a single unambiguous mention; repetition never inflates it.

**Area level** (plan R28), only for an official source or GDELT, and only when no toponym resolved: a city
district code (``LGD:MUMBAI`` or ``LGD:MUMBAI_SUBURBAN``, or a GDELT ``ActionGeo_FullName`` naming Mumbai/Bombay)
gives that district's representative point, ``area_scope "district"``, confidence 0.40 (a district with no point
would be ``None`` until C-T accepts one, :data:`DISTRICT_WITHOUT_POINT`); a state code (``LGD:MAHARASHTRA``,
``GDELT_ADM1:IN16``) gives ``area_scope "state"`` with **no point** (a state-wide alert is not a Mumbai location),
confidence 0.25; any other code gives ``None``. Otherwise the honest ``None``: never a city centroid dressed as precise. A source's tier is
read from ``SOURCE_PRIORS``, never from the payload (plan R26).

Places only: a geocode names a place, never a person; the resolver keeps no signal text.
"""

from __future__ import annotations

import os
import re
import threading
from collections.abc import Collection, Iterator, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Literal, get_args

import numpy as np

from osint_common.kinds import AREA_DISTRICTS, AREA_STATE_CODE_MAHARASHTRA, GDELT_ADM1_MAHARASHTRA, SOURCE_PRIORS
from osint_common.types import AreaScope, Geocode, RawOsintSignal
from osint_geo import confidence, grammar, translit
from osint_geo.gazetteer import GENERIC_STOPWORDS, Gazetteer, GazetteerEntry, Hit, norm, select_longest
from osint_geo.gazetteer import load as load_gazetteer
from osint_geo.snap import GEOD, Network, load_network

__all__ = [
    "CITY_BBOX",
    "CITY_SOURCES",
    "CITY_WORDS",
    "CONTEXT_FORMS",
    "DISTRICT_MUMBAI_SUBURBAN",
    "DISTRICT_MUMBAI",
    "DISTRICT_WITHOUT_POINT",
    "FUZZY_CUTOFF",
    "FUZZY_STOP",
    "LOCAL_SOURCES",
    "MAX_HINTS",
    "MAX_HINT_CHARS",
    "NOT_A_PLACE_BEFORE",
    "R_WEIGHTS",
    "SENTENCE_BREAK",
    "STATE_GATED_FORMS",
    "STATE_MAHARASHTRA",
    "STATE_SOURCES",
    "AreaLevel",
    "GazetteerResolver",
    "Mention",
    "Reading",
    "default_resolver",
    "resolve_text",
]

Method = Literal["gazetteer_exact", "gazetteer_fuzzy", "grammar"]

#: The area scope a neighbourhood geocode carries: ``"neighbourhood"`` once C-T's ``AreaScope`` has it (requested
#: of OS-1, F-HONEST OSINT-3), else ``None`` (a point with no road anchor; the pipeline reads the feature type).
NEIGHBOURHOOD_SCOPE: str | None = "neighbourhood" if "neighbourhood" in get_args(AreaScope) else None

#: The Mumbai bbox (``cities/mumbai/city.json``: 18.89-19.28 N, 72.77-72.99 E): (lon_min, lat_min, lon_max, lat_max).
CITY_BBOX: tuple[float, float, float, float] = (72.77, 18.89, 72.99, 19.28)
#: Disambiguation weights (research A6, without the embedding-context term: the Embedder is OS-4's).
R_WEIGHTS: Mapping[str, float] = MappingProxyType(
    {"bbox": 0.25, "specificity": 0.15, "coherence": 0.20, "importance": 0.10, "locality": 0.10, "match": 0.10}
)
COHERENCE_RADIUS_M = 8000.0
FUZZY_CUTOFF = 0.90
FUZZY_MIN_CHARS = 8
#: Words that never take part in a fuzzy window: the city, state and country names and the newsroom words of
#: headlines (the PoC's ``FUZZY_STOP``, plus newspaper words). "India" is here, which is why it never meets "indira".
FUZZY_STOP: frozenset[str] = frozenset(
    {
        "india", "indian", "indias", "maharashtra", "marathi", "mumbai", "bombay", "mumbaikar", "mumbaikars",
        "brihanmumbai", "bharat", "city", "state", "national", "news", "today", "police", "court", "river", "times",
        "express", "post", "lokmat", "loksatta", "maharashtra", "midday", "journal", "press", "majha", "english",
        "live", "update", "updates", "weather",
    }
)
#: Sources scoped to the city: what they report is in Mumbai (r/mumbai, the BMC slot, the Mumbai Traffic Police
#: public notices). They open the context gate.
CITY_SOURCES: frozenset[str] = frozenset({"reddit_rss", "kmc_scrape", "mumbai_police_scrape"})
#: Sources scoped to the state (the SACHET and IMD feeds, filtered to Maharashtra; the state SDMA slot): their
#: alerts name every district. They never open the context gate.
STATE_SOURCES: frozenset[str] = frozenset({"sachet_cap", "imd", "wbsdma"})
#: Sources scoped to the city or the state: full source locality, the confidence term (the PoC counted the city
#: subreddit and the state's SACHET feed as local).
LOCAL_SOURCES: frozenset[str] = CITY_SOURCES | STATE_SOURCES
#: Geo-hint words naming the city (GDELT's FullName spells it "Calcutta"; a connector's ``area:`` hints name the
#: metro districts) and, for source locality only, the state.
_CITY_HINT_WORDS = frozenset({"mumbai", "bombay", "brihanmumbai"})
_STATE_HINT_WORDS = frozenset({"maharashtra"})
_LOCAL_HINT_WORDS = _CITY_HINT_WORDS | _STATE_HINT_WORDS
_GDELT = frozenset({"gdelt_events", "gdelt_doc"})
#: The geo hints read per signal: the first ``MAX_HINTS``, ``MAX_HINT_CHARS`` characters each. Connectors send one
#: to three short names (a GDELT FullName of at most 200 characters, "Mumbai", a URL's place words);
#: ``RawOsintSignal`` allows 64 of 1000 characters, and such a payload must not cost a fuzzy scan of 64 kB.
MAX_HINTS = 8
MAX_HINT_CHARS = 200

#: Surface forms that name a Mumbai place only in a text about Mumbai, each with the reason: elsewhere the same
#: words mean something else, and a wrong-city pin at high confidence is worse than an honest ``None``. Such a form
#: is a mention only when the signal is placed in the city (:meth:`GazetteerResolver.city_scoped`: a city-scoped
#: source, a geo hint naming Mumbai, a city district code, a Mumbai PIN) or its text names the city
#: (:data:`CITY_WORDS`); state-level evidence never opens the gate. Gated with them: their Latin variants and
#: Marathi and Devanagari spellings (``osint_geo.translit``), and every bare route code form (``nh12``, ``nh16``:
#: a highway runs on through other towns and states).
CONTEXT_FORMS: Mapping[str, str] = MappingProxyType(
    {
        # common words
        "fort": "a common word: any fort (Mumbai's Fort is an area only in a text about Mumbai)",
        "khar": "a common word (thorn, salt) and town names in other states",
        "national park": "every state has a national park",
        "gandhi market": "a market name of many cities",
        "coastal road": "a road name of other coastal cities (Chennai, Goa, Kochi)",
        "marine drive": "Kochi's Marine Drive",
        "atal setu": "a bridge name of other states (Goa's Atal Setu)",
        # names many places share
        "sv road": "a road name of other cities",
        "lbs marg": "Lal Bahadur Shastri Marg names roads in Delhi and Pune too",
        "lbs road": "LBS Road names roads in other cities",
        "santacruz": "Santa Cruz names places in Goa and abroad",
        "santa cruz": "Santa Cruz names places in Goa and abroad",
        "lalbag": "Lalbagh names gardens in Bengaluru and Lucknow",
        "kasturba hospital": "a hospital name of other cities (Delhi, Manipal)",
        "tata memorial hospital": "the hospital has centres in other cities",
        "holy family hospital": "a hospital name of other cities (Delhi)",
        "seven hills hospital": "a hospital name of other cities (Visakhapatnam)",
        "st george hospital": "a hospital name of other cities",
        "mahalaxmi temple": "Kolhapur's Mahalaxmi Temple",
        "mahalaxmi": "a goddess's name: temples and areas of other cities (Kolhapur)",
        "mahalakshmi": "a goddess's name: temples and areas of other cities (Kolhapur)",
        "shivaji park": "a park name of other cities in Maharashtra",
    }
)
_ROUTE_CODE = re.compile(r"(?:nh|ne|sh)\d+")
#: A form that names something else when the next word is one of these, whatever the source: "Dadar Express",
#: "Bandra Express" and "LTT Duronto" are trains (an accident report along their route is not the place), "Kurla
#: taluka" is the taluka (area level, never the city's point). Its Latin variants and script spellings follow the
#: same rule; a Marathi or Devanagari next word may carry a case ending. The longer forms are read first and are
#: unaffected ("Dadar station", "Kurla station").
_TRAIN_WORDS = frozenset(
    {
        "mail", "express", "rajdhani", "shatabdi", "duronto", "superfast", "garib", "rath", "vande", "bharat",
        "district", "zilla", "division", "taluka", norm("एक्सप्रेस"), norm("मेल"), norm("जिल्हा"), norm("जिला"),
        norm("तालुका"),
    }
)
NOT_A_PLACE_BEFORE: Mapping[str, frozenset[str]] = MappingProxyType(
    {"dadar": _TRAIN_WORDS, "bandra": _TRAIN_WORDS, "kurla": _TRAIN_WORDS, "andheri": _TRAIN_WORDS,
     "borivali": _TRAIN_WORDS, "csmt": _TRAIN_WORDS, "ltt": _TRAIN_WORDS}
)
#: Forms a signal with state-level evidence (:meth:`GazetteerResolver.state_scoped`: SACHET, IMD or the state SDMA
#: slot as the source, ``LGD:MAHARASHTRA``, ``GDELT_ADM1:IN16``, a hint naming Maharashtra) does not read unless it
#: also carries
#: city-level evidence (the context gate open: :meth:`GazetteerResolver.city_scoped` or a city word in the text),
#: each with the reason. Their Latin variants and Marathi and Devanagari spellings follow. A state alert names
#: districts and talukas: "Kurla" in it is the taluka, never the city's area pin.
STATE_GATED_FORMS: Mapping[str, str] = MappingProxyType(
    {
        "andheri": "a state-wide alert listing talukas names the Andheri taluka, not the city's area pin",
        "borivali": "a state-wide alert listing talukas names the Borivali taluka, not the city's area pin",
        "kurla": "a state-wide alert listing talukas names the Kurla taluka, not the city's area pin",
    }
)
#: The city's name, in Latin, Marathi and Devanagari spellings: a text naming it opens the context gate (a Marathi
#: case ending is allowed, "मुंबईत"). The state's name does not: Pune has a Shivaji Park too. Opening the gate
#: only lets a context form count; it never raises the source-locality term, which stays the source's scope (the
#: PoC calibration).
CITY_WORDS: frozenset[str] = frozenset(
    {
        "mumbai", "bombay", "mumbais", "brihanmumbai", "mumbaikar", "mumbaikars",
        norm("मुंबई"), norm("मुम्बई"), norm("बॉम्बे"), norm("बृहन्मुंबई"), norm("मुंबईकर"),
    }
)
#: The sign-off a state-scoped alert ends with: Maharashtra SDMA signs every Marathi nowcast "मंत्रालय, मुंबई"
#: (Mantralaya, Mumbai: the issuer's office). In a state source it is neither a place of the event nor a city word,
#: so a Thane-and-Palghar nowcast never becomes a Mantralaya pin or opens the city gate (osint-ingress cuts it from
#: its area matching the same way).
_ISSUER_SIGN_OFF = re.compile(r"(?:मंत्रालय|mantralaya)[\s,.।:;-]*(?:मुंबई|mumbai)", re.IGNORECASE)
_INDIC_CITY_WORDS: tuple[str, ...] = tuple(sorted(w for w in CITY_WORDS if translit.is_indic(w)))

#: What ends a sentence: "." "!" "?" or a danda ("।", Marathi and Hindi) before a space or the end. A full stop after
#: a single letter (an initial, "A.J.C. Bose Road") or a known abbreviation ("Dr.", "Rd.", "opp.") does not (the
#: grammar's rule).
_SENTENCE_END = re.compile(r"[.!?।॥]+(?=\s|$)")
_LAST_WORD = re.compile(r"[\wऀ-ॿঀ-৿]+$")
#: The token between two sentences (:meth:`GazetteerResolver.tokens`): never a gazetteer word (``norm`` turns every
#: "." into a space), so no form, grammar rewrite or fuzzy window spans it.
SENTENCE_BREAK = "."
#: A place word that is also an English word, and the next word that makes it that word: "more than" is the
#: comparative, never "more" (the Kolkata pack's crossing word): "... more than knee deep" names no crossing.
_ENGLISH_BEFORE: Mapping[str, str] = MappingProxyType({"more": "than"})


def _sentences(text: str) -> list[str]:
    """``text`` split at its sentence ends (:data:`_SENTENCE_END`)."""
    out: list[str] = []
    start = 0
    for m in _SENTENCE_END.finditer(text):
        if m.group(0) == ".":
            w = _LAST_WORD.search(text, start, m.start())
            if w is not None and (len(w.group(0)) == 1 or w.group(0).lower() in grammar._ABBREVIATIONS):
                continue
        out.append(text[start : m.start()])
        start = m.end()
    out.append(text[start:])
    return out


def _english_word(toks: Sequence[str], end: int) -> bool:
    """True when the span ending at ``end`` ends on a place word the next token makes English ("more than")."""
    return 0 < end < len(toks) and _ENGLISH_BEFORE.get(toks[end - 1]) == toks[end]


@dataclass(frozen=True, slots=True)
class AreaLevel:
    """An area at its real precision (plan R28)."""

    scope: Literal["district", "state"]
    toponym: str
    lon: float | None
    lat: float | None
    confidence: float


#: The city districts (``osint_common.kinds.AREA_DISTRICTS``): Mumbai City (its point: CSMT, the island city's
#: conventional centre, ``cities/mumbai/landmarks.json``) and Mumbai Suburban (its point: the Bandra East collectorate
#: area), each with the district cap 0.40. Never a street pin: no segment, junction or snap.
DISTRICT_MUMBAI = AreaLevel("district", "Mumbai City (district)", 72.8355, 18.9398, 0.40)
DISTRICT_MUMBAI_SUBURBAN = AreaLevel("district", "Mumbai Suburban (district)", 72.8480, 19.0590, 0.40)


def _contract_accepts_a_district_without_point() -> bool:
    """Whether C-T (``osint_common.types.Geocode``) accepts a district-level geocode with no point. Today it
    requires the district's representative point, so a district with no point must not become a geocode (building one
    raises); the resolver returns ``None`` for it instead, and gives the district level as soon as C-T allows it."""
    try:
        Geocode(signal_id="0" * 40, toponym="probe", feature_type="admin", lon=None, lat=None, method="area_fallback",
                confidence=0.30, bucket="low", area_level=True, area_scope="district")
    except ValueError:
        return False
    return True


#: True when a district without a point can be a district-level geocode (C-T); else such an
#: alert resolves to ``None``: never an exception, never a borrowed point.
DISTRICT_WITHOUT_POINT: bool = _contract_accepts_a_district_without_point()
#: Maharashtra: no point at all (a state-wide alert is not a city location), the state cap 0.25.
STATE_MAHARASHTRA = AreaLevel("state", "Maharashtra (state)", None, None, 0.25)
#: District code → its area, the island city first: an alert naming both districts reads as Mumbai City.
_DISTRICTS: Mapping[str, AreaLevel] = MappingProxyType(
    {
        "LGD:MUMBAI": DISTRICT_MUMBAI,
        "LGD:MUMBAI_SUBURBAN": DISTRICT_MUMBAI_SUBURBAN,
    }
)
_DISTRICT_CODES = frozenset(_DISTRICTS)
#: The districts whose code places a signal in the city (the context gate): both Mumbai districts.
_CITY_DISTRICT_CODES = frozenset({"LGD:MUMBAI", "LGD:MUMBAI_SUBURBAN"})
_STATE_CODES = frozenset({AREA_STATE_CODE_MAHARASHTRA, f"GDELT_ADM1:{GDELT_ADM1_MAHARASHTRA}"})


@dataclass(frozen=True, slots=True)
class Mention:
    """A place named in a text: tokens ``[start, end)`` read as the surface form ``form``, which names
    ``gaz_ids``; ``score`` is the match component (1.0 exact, the ratio when fuzzy)."""

    start: int
    end: int
    form: str
    gaz_ids: tuple[int, ...]
    method: Method
    score: float


@dataclass(frozen=True, slots=True)
class Reading:
    """One candidate place for one mention, with its disambiguation score ``r``."""

    entry: GazetteerEntry
    mention: Mention
    r: float
    order: int


def _in_bbox(e: GazetteerEntry) -> float:
    lon_min, lat_min, lon_max, lat_max = CITY_BBOX
    return 1.0 if (lon_min <= e.lon <= lon_max and lat_min <= e.lat <= lat_max) else 0.0


def _codes(signal: RawOsintSignal) -> set[str]:
    out = set()
    for c in signal.raw_geo_hint.admin_codes:
        kind, _, value = c.partition(":")
        out.add(f"{kind.upper()}:{value.upper()}")
    return out


def _hints(signal: RawOsintSignal) -> list[str]:
    """The geo hints read: the first :data:`MAX_HINTS`, :data:`MAX_HINT_CHARS` characters each."""
    return [p[:MAX_HINT_CHARS] for p in signal.raw_geo_hint.place_names[:MAX_HINTS]]


#: A geo hint that is only a metro district's name (``osint_common.kinds.AREA_DISTRICTS``: a CAP alert's area
#: "Mumbai Suburban", a news URL's "mumbai") names the district, not a place in it: it scopes the signal
#: (:meth:`GazetteerResolver.city_scoped`, :meth:`GazetteerResolver.area_level`) but is never read as text, so a
#: district alert stays the district and is never an area pin at a higher confidence.
_DISTRICT_NAMES: frozenset[str] = frozenset(norm(n) for names in AREA_DISTRICTS.values() for n in names)


#: A connector's area hint (``category_hint``): ``area:mumbai`` and ``area:mumbai_suburban`` place a signal in the
#: city (an alert naming the district, a news item from an outlet's Mumbai section); ``area:maharashtra`` is state
#: level only.
_CITY_AREA_HINTS = frozenset({"area:mumbai", "area:mumbai_suburban"})
_STATE_AREA_HINTS = frozenset({"area:maharashtra"})


def _area_hints(signal: RawOsintSignal) -> frozenset[str]:
    return frozenset(h.strip().lower() for h in signal.category_hint[:32] if h.lower().startswith("area:"))


def _hint_names(signal: RawOsintSignal, words: frozenset[str]) -> bool:
    """True when a geo hint holds one of ``words`` ("Pune, Maharashtra, India" holds "maharashtra")."""
    return any(words.intersection(norm(p).split(" ")) for p in _hints(signal))


def _spellings(form: str) -> Iterator[str]:
    """A Latin form, its Latin variants and its Marathi and Devanagari spellings (``osint_geo.translit``)."""
    yield form
    yield from translit.latin_variants(form)
    yield from translit.script_aliases(form)


class GazetteerResolver:
    """``osint_common.pipeline.GeoResolver`` over the offline gazetteer and the OSM network (module docstring).

    ``GazetteerResolver(gazetteer=None, network=None)``: each is the loaded object, a path, or ``None`` for the
    path rules. Immutable after construction; safe to share between threads."""

    def __init__(
        self,
        gazetteer: Gazetteer | str | os.PathLike[str] | None = None,
        network: Network | str | os.PathLike[str] | None = None,
    ) -> None:
        self.gazetteer: Gazetteer = gazetteer if isinstance(gazetteer, Gazetteer) else load_gazetteer(gazetteer)
        self.network: Network = network if isinstance(network, Network) else load_network(network)
        gaz = self.gazetteer
        gated = {norm(f) for form in CONTEXT_FORMS for f in _spellings(form) if gaz.lookup(f)}
        gated_latin = {f for f in gated if not translit.is_indic(f)}
        for f in gaz.forms:
            if _ROUTE_CODE.fullmatch(f):
                gated.add(f)  # a bare route code: the highway runs on through other towns and states
            elif translit.is_indic(f) and translit.to_latin(f) in gated_latin:
                gated.add(f)  # a script spelling of a gated form, from osm_network.json's Marathi names
        #: the gazetteer's forms under the context gate (:data:`CONTEXT_FORMS`, their spellings, the route codes)
        self.context_forms: frozenset[str] = frozenset(gated)
        state = {norm(f) for form in STATE_GATED_FORMS for f in _spellings(form) if gaz.lookup(f)}
        state_latin = {f for f in state if not translit.is_indic(f)}
        state |= {f for f in gaz.forms if translit.is_indic(f) and translit.to_latin(f) in state_latin}
        #: the gazetteer's forms a state-level signal does not read (:data:`STATE_GATED_FORMS`, their spellings)
        self.state_forms: frozenset[str] = frozenset(state)
        not_before: dict[str, tuple[frozenset[str], tuple[str, ...]]] = {}
        for form, words in NOT_A_PLACE_BEFORE.items():
            indic = tuple(sorted(w for w in words if translit.is_indic(w)))
            for f in _spellings(form):
                if gaz.lookup(f):
                    not_before[norm(f)] = (words, indic)
        #: form → (next words, their Marathi and Devanagari stems) that make it name something else
        self._not_before: Mapping[str, tuple[frozenset[str], tuple[str, ...]]] = MappingProxyType(not_before)

    # ---------------------------------------------------------------- the protocol
    def resolve(self, signal: RawOsintSignal | Mapping[str, Any]) -> Geocode | None:
        """The signal's geocode: a place snapped onto the network, an area at its real level, or ``None``."""
        sig = signal if isinstance(signal, RawOsintSignal) else RawOsintSignal.model_validate(signal)
        locality = self.source_locality(sig)
        mentions = self.mentions(self._text(sig), city=self.city_scoped(sig), state=self.state_scoped(sig))
        readings = self.readings(mentions, locality)
        if readings:
            return self._geocode(sig.signal_id, readings, locality)
        return self._area_geocode(sig)

    # ---------------------------------------------------------------- stages
    @staticmethod
    def _text(sig: RawOsintSignal) -> str:
        # the PoC's order: title, text, then the connector's place-name hints (the first MAX_HINTS); a hint that is
        # only a district's name scopes the signal and is not read as a place
        title, text = sig.title, sig.text
        if sig.source in STATE_SOURCES:  # the issuer's sign-off ("मंत्रालय, मुंबई") is its office, not a place
            title, text = _ISSUER_SIGN_OFF.sub(" ", title), _ISSUER_SIGN_OFF.sub(" ", text)
        return f"{title}. {text}" + "".join(f" {p}" for p in _hints(sig) if norm(p) not in _DISTRICT_NAMES)

    @staticmethod
    def source_locality(sig: RawOsintSignal) -> float:
        """1.0 for a city- or state-scoped source, a hint naming Mumbai or Maharashtra, a district or state admin
        code, or a Mumbai PIN in the text; else 0.3. Never from a word of the free text: national outlets name the
        city in passing (and the PoC calibration reads it this way). This is the confidence term only; the
        context gate reads :meth:`city_scoped`."""
        if sig.source in LOCAL_SOURCES:
            return confidence.LOCAL
        if _hint_names(sig, _LOCAL_HINT_WORDS) or _area_hints(sig) & (_CITY_AREA_HINTS | _STATE_AREA_HINTS):
            return confidence.LOCAL
        if _codes(sig) & (_DISTRICT_CODES | _STATE_CODES):
            return confidence.LOCAL
        if grammar.pin_codes(sig.title) or grammar.pin_codes(sig.text):
            return confidence.LOCAL
        return confidence.NON_LOCAL

    @staticmethod
    def city_scoped(sig: RawOsintSignal) -> bool:
        """True when the signal's own metadata places it in the city: a city-scoped source (:data:`CITY_SOURCES`),
        a geo hint naming Mumbai (a GDELT FullName "Bombay, Maharashtra, India", a connector's ``area:mumbai``),
        the district code ``LGD:MUMBAI`` or ``LGD:MUMBAI_SUBURBAN``, or a Mumbai PIN. State-level evidence is not:
        SACHET, IMD or the state SDMA slot as the source, ``LGD:MAHARASHTRA``, ``GDELT_ADM1:IN16`` or a hint naming
        only Maharashtra (Pune has a Shivaji Park too). It opens the context gate; it never changes :meth:`source_locality`."""
        if sig.source in CITY_SOURCES:
            return True
        if _hint_names(sig, _CITY_HINT_WORDS) or _area_hints(sig) & _CITY_AREA_HINTS:
            return True
        if _codes(sig) & _CITY_DISTRICT_CODES:
            return True
        return bool(grammar.pin_codes(sig.title) or grammar.pin_codes(sig.text))

    @staticmethod
    def state_scoped(sig: RawOsintSignal) -> bool:
        """True when the signal carries state-level evidence: a state-scoped source (:data:`STATE_SOURCES`), a
        state code (``LGD:MAHARASHTRA``, ``GDELT_ADM1:IN16``) or a geo hint naming Maharashtra. With no city-level
        evidence
        (the context gate closed) such a signal does not read :attr:`state_forms`; city-level evidence wins."""
        if sig.source in STATE_SOURCES:
            return True
        if _codes(sig) & (_STATE_CODES | (_DISTRICT_CODES - _CITY_DISTRICT_CODES)):
            return True
        if _area_hints(sig) & _STATE_AREA_HINTS:
            return True
        return _hint_names(sig, _STATE_HINT_WORDS)

    def mentions(self, text: str, *, city: bool = False, state: bool = False) -> list[Mention]:
        """The places ``text`` names: exact mentions (the longest-match scan and the grammar's rewrites), else the
        fuzzy mentions; in selection order (longest first, then position).

        ``city`` says the signal is placed in the city by its metadata (:meth:`city_scoped`; :meth:`resolve`
        passes it). Unless it is, or the text names the city, the context forms (:attr:`context_forms`) are no
        mention, exact or fuzzy, and never block another form; and when ``state`` says the signal carries
        state-level evidence (:meth:`state_scoped`), neither are the state forms (:attr:`state_forms`, the bare
        "Kurla"). A form followed by a word that makes it name something else (:data:`NOT_A_PLACE_BEFORE`,
        "Dadar Express", "Kurla taluka") is no mention either, and no mention spans a sentence end (:meth:`tokens`)."""
        gaz = self.gazetteer
        toks = self.tokens(text)
        if self.context_open(toks, city=city, state=state):
            gated: frozenset[str] = frozenset()
        else:
            gated = (self.context_forms | self.state_forms) if state else self.context_forms
        hits = [
            h for h in gaz.hits(toks) + grammar.feature_hits(toks, gaz)
            if h.form not in gated and not self._names_something_else(h, toks)
        ]
        chosen = select_longest(hits, toks, gaz.form_order)
        if chosen:
            return [
                Mention(h.start, h.end, h.form, gaz.forms[h.form], "gazetteer_exact" if h.via == "gazetteer" else
                        "grammar", 1.0)
                for h in chosen
            ]
        return self._fuzzy_mentions(toks, text, exclude=gated)

    def tokens(self, text: str) -> list[str]:
        """``text``'s tokens (:meth:`Gazetteer.tokens`, Marathi case endings read), sentence by sentence with
        :data:`SENTENCE_BREAK` between sentences, so no form, grammar rewrite or fuzzy window spans a sentence end:
        "Fire at Worli. Naka traders shut shops" is the area, never "Worli Naka" (the junction)."""
        toks: list[str] = []
        for i, sentence in enumerate(_sentences(text)):
            if i:
                toks.append(SENTENCE_BREAK)
            toks.extend(self.gazetteer.tokens(sentence))
        return toks

    def _names_something_else(self, h: Hit, toks: Sequence[str]) -> bool:
        """True when the word after the hit makes its form name something else (:data:`NOT_A_PLACE_BEFORE`), or
        makes its last place word an English one ("more than")."""
        if _english_word(toks, h.end):
            return True
        rule = self._not_before.get(h.form)
        if rule is None or h.end >= len(toks):
            return False
        words, indic = rule
        nxt = toks[h.end]
        return nxt in words or (bool(indic) and translit.is_indic(nxt) and nxt.startswith(indic))

    @staticmethod
    def names_city(tokens: Sequence[str], exclude: Collection[str] = frozenset()) -> bool:
        """True when a token is the city's name (:data:`CITY_WORDS`; a Marathi case ending allowed), other than the
        words in ``exclude``."""
        indic = tuple(w for w in _INDIC_CITY_WORDS if w not in exclude) if exclude else _INDIC_CITY_WORDS
        return any(
            t not in exclude and (t in CITY_WORDS or (translit.is_indic(t) and t.startswith(indic)))
            for t in tokens
        )

    def context_open(self, tokens: Sequence[str], *, city: bool = False, state: bool = False) -> bool:
        """The context gate: the context forms count when the signal's metadata places it in the city (``city``,
        :meth:`city_scoped`) or its text names the city. The state's name, scope or code never opens it, and in a
        signal with state-level evidence (``state``) a city word that is a state form ("Kurla", the taluka in a
        state-wide alert) does not either."""
        return city or self.names_city(tokens, exclude=self.state_forms if state else frozenset())

    @staticmethod
    def _fuzzy_ok(window: Sequence[str]) -> bool:
        """The stoplist guard on a fuzzy window: two words or more, no locality or newsroom word, not only generic
        words, no sentence end (the eight-character minimum is checked on each candidate string)."""
        return (
            len(window) >= 2
            and SENTENCE_BREAK not in window
            and not any(t in FUZZY_STOP for t in window)
            and not all(t in GENERIC_STOPWORDS for t in window)
        )

    def _grammar_names(self, text: str) -> list[tuple[tuple[str, ...], tuple[str, ...]]]:
        """The grammar's relational and feature spans as ``(name tokens, lookup keys)``, distinct names in text
        order: a cue-bound name ("near Ruby Hopsital") is the likeliest place in a text, so it is tried
        first."""
        out: dict[tuple[str, ...], tuple[str, ...]] = {}
        for span in grammar.find_spans(text):
            if span.kind == "pin":
                continue
            stoks = tuple(norm(span.surface).split(" "))
            if self._fuzzy_ok(stoks) and stoks not in out:
                out[stoks] = span.keys
        return list(out.items())

    def _fuzzy_mentions(
        self, toks: Sequence[str], text: str = "", exclude: frozenset[str] = frozenset()
    ) -> list[Mention]:
        """Fuzzy mentions, only when nothing matched exactly: the grammar's names first, then three-word and then
        two-word windows (the PoC's order). Every occurrence of a matching name is a mention, as with exact
        matches, so a misspelt place never reads as surer than the same place spelt right; the best ratio wins
        where windows overlap. A form in ``exclude`` (the closed context gate) is never a fuzzy target, and a window
        that is such a form is not read fuzzily either (it would reach a longer form that carries a place the text
        does not name: "medical college hospital" is not "NRS Medical College Hospital")."""
        gaz = self.gazetteer
        seen: dict[str, tuple[str, float] | None] = {}

        def best_hit(cands: Sequence[str]) -> tuple[str, float] | None:
            for cand in cands:
                if len(cand) < FUZZY_MIN_CHARS or " " not in cand or cand in exclude:
                    continue
                if cand not in seen:
                    seen[cand] = gaz.fuzzy(cand, FUZZY_CUTOFF, exclude=exclude)
                if seen[cand] is not None:
                    return seen[cand]
            return None

        def select(found: list[tuple[float, int, int, str]]) -> list[Mention]:
            used = [False] * len(toks)
            out: list[Mention] = []
            for ratio, i, j, form in sorted(found, key=lambda t: (-t[0], -(t[2] - t[1]), t[1], t[3])):
                if any(used[i:j]):
                    continue
                for k in range(i, j):
                    used[k] = True
                out.append(Mention(i, j, form, gaz.forms[form], "gazetteer_fuzzy", ratio))
            return sorted(out, key=lambda m: m.start)

        found: list[tuple[float, int, int, str]] = []
        for stoks, keys in self._grammar_names(text) if text else ():
            hit = best_hit(keys)
            if hit is None:
                continue
            n = len(stoks)
            for i in range(len(toks) - n + 1):
                if tuple(toks[i : i + n]) == stoks and not _english_word(toks, i + n):
                    found.append((hit[1], i, i + n, hit[0]))
        if found:
            return select(found)
        for n in (3, 2):
            for i in range(len(toks) - n + 1):
                window = toks[i : i + n]
                if self._fuzzy_ok(window) and not _english_word(toks, i + n):
                    hit = best_hit(self._window_variants(window))
                    if hit is not None:
                        found.append((hit[1], i, i + n, hit[0]))
            if found:
                return select(found)
        return []

    @staticmethod
    def _window_variants(window: Sequence[str]) -> list[str]:
        """A fuzzy window as written, then with a trailing generic word rewritten ("rashbehri more" →
        "rashbehri crossing")."""
        out = [" ".join(window)]
        for m in (2, 1):
            if len(window) > m:
                for target in grammar.SYNONYMS.get(tuple(window[-m:]), ()):
                    v = " ".join((*window[:-m], target))
                    if v not in out:
                        out.append(v)
        return out

    def readings(self, mentions: Sequence[Mention], locality: float) -> list[Reading]:
        """Every (mention, place) reading scored by R, best first (ties: the earlier reading).

        Coherence is the share of the other readings that stand at another point and lie within 8 km (the PoC's
        definition), computed over the distinct points weighted by their reading counts, so a text that repeats a
        name hundreds of times costs no more than the places it names."""
        gaz = self.gazetteer
        cands = [(gaz.by_id[g], m) for m in mentions for g in m.gaz_ids]
        if not cands:
            return []
        n = len(cands)
        point_index: dict[tuple[float, float], int] = {}
        idx = np.array([point_index.setdefault((e.lon, e.lat), len(point_index)) for e, _ in cands])
        u = len(point_index)
        counts = np.bincount(idx, minlength=u).astype(float)
        near = np.zeros((u, u), dtype=bool)
        if u > 1:
            pts = np.array(list(point_index))
            ii, jj = np.triu_indices(u, k=1)
            _, _, d = GEOD.inv(pts[ii, 0], pts[ii, 1], pts[jj, 0], pts[jj, 1])
            near[ii, jj] = near[jj, ii] = d < COHERENCE_RADIUS_M
        near_counts = near.astype(float) @ counts  # per point: readings at OTHER points within the radius
        others = n - counts  # per point: readings at other points
        w = R_WEIGHTS
        out: list[Reading] = []
        for i, (e, m) in enumerate(cands):
            p = idx[i]
            coh = float(near_counts[p] / others[p]) if others[p] > 0 else 0.0
            r = (
                w["bbox"] * _in_bbox(e)
                + w["specificity"] * confidence.specificity(e.feature_type)
                + w["coherence"] * coh
                + w["importance"] * e.importance
                + w["locality"] * locality
                + w["match"] * m.score
            )
            out.append(Reading(e, m, r, i))
        out.sort(key=lambda rd: (-rd.r, rd.order))
        return out

    # ---------------------------------------------------------------- geocodes
    def _anchor(self, e: GazetteerEntry) -> tuple[int | None, int | None, str | None, float | None, float]:
        """``(segment_id, junction_id, snapped_to, residual_m, snap_quality)`` for the chosen place.

        A neighbourhood is an area: it gets no road anchor at all (F-HONEST OSINT-3: a bare area word was snapped up to
        2.5 km away and carried as that segment). A landmark keeps the segment it snaps to only within
        :data:`confidence.SNAP_ANCHOR_MAX_M` (900 m): farther, it is not on that road."""
        if e.feature_type == "junction" and e.junction_id is not None:
            return None, e.junction_id, None, 0.0, 1.0
        if e.feature_type == "road" and e.segment_id is not None:
            return e.segment_id, None, None, 0.0, 1.0
        if e.segment_id is not None or e.junction_id is not None:  # a place pre-linked to the network
            return e.segment_id, e.junction_id, None, 0.0, 1.0
        if e.feature_type == "neighbourhood":
            return None, None, None, None, 0.0
        s = self.network.snap(e.lon, e.lat, junction_tol_m=0.0)
        if s.segment_id is None or s.residual_m is None or s.residual_m > confidence.SNAP_ANCHOR_MAX_M:
            return None, None, None, None, 0.0
        return s.segment_id, None, s.snapped_to, s.residual_m, confidence.snap_quality(s.residual_m)

    def _geocode(self, signal_id: str, readings: Sequence[Reading], locality: float) -> Geocode:
        top = readings[0]
        e = top.entry
        seg, jct, snapped_to, residual, sq = self._anchor(e)
        area_scope = NEIGHBOURHOOD_SCOPE if e.feature_type == "neighbourhood" else None
        mg = confidence.margin(top.r, readings[1].r if len(readings) > 1 else None)
        conf = round(confidence.score(top.mention.score, confidence.specificity(e.feature_type), mg, sq, locality), 3)
        alternatives: list[str] = []
        for rd in readings[1:]:
            name = rd.entry.canonical_name
            if name != e.canonical_name and name not in alternatives:
                alternatives.append(name)
            if len(alternatives) == 3:
                break
        return Geocode(
            signal_id=signal_id,
            toponym=e.canonical_name,
            feature_type=e.feature_type,  # type: ignore[arg-type]
            lon=e.lon,
            lat=e.lat,
            segment_id=seg,
            junction_id=jct,
            snapped_to=snapped_to,
            method=top.mention.method,
            residual_m=residual,
            confidence=conf,
            bucket=confidence.bucket(conf),
            # a neighbourhood is an area (F-HONEST OSINT-3); C-T's AreaScope carries "neighbourhood" once OS-1 adds
            # it (a cross-WP request): until then the geocode is a point with no road anchor, and the pipeline
            # marks the situation area-level from its feature type
            area_level=area_scope is not None,
            area_scope=area_scope,  # type: ignore[arg-type]
            alternatives=alternatives,
        )

    @staticmethod
    def area_level(signal: RawOsintSignal) -> AreaLevel | None:
        """The area an official or GDELT signal's admin code (or GDELT FullName) places it in, at its real level (a
        district without a point only when C-T can carry one, :data:`DISTRICT_WITHOUT_POINT`)."""
        prior = SOURCE_PRIORS.get(signal.source)
        if prior is None or not (prior.tier == "official" or signal.source in _GDELT):
            return None
        codes = _codes(signal)
        for code, level in _DISTRICTS.items():  # most specific first: Mumbai City, then Mumbai Suburban
            if code in codes and (level.lon is not None or DISTRICT_WITHOUT_POINT):
                return level
        if signal.source == "gdelt_events" and _hint_names(signal, frozenset({"mumbai", "bombay"})):
            return DISTRICT_MUMBAI  # an ActionGeo_FullName naming the city ("Bombay" is a GNS spelling)
        if codes & _STATE_CODES:
            return STATE_MAHARASHTRA
        return None

    def _area_geocode(self, signal: RawOsintSignal) -> Geocode | None:
        level = self.area_level(signal)
        if level is None:
            return None
        return Geocode(
            signal_id=signal.signal_id,
            toponym=level.toponym,
            feature_type="admin",
            lon=level.lon,
            lat=level.lat,
            segment_id=None,
            junction_id=None,
            snapped_to=None,
            method="area_fallback",
            residual_m=None,
            confidence=level.confidence,
            bucket=confidence.bucket(level.confidence),
            area_level=True,
            area_scope=level.scope,
            alternatives=[],
        )

    # ---------------------------------------------------------------- explain and lookup
    def explain(self, signal: RawOsintSignal | Mapping[str, Any]) -> dict[str, Any]:
        """How a signal resolves: its locality, whether its metadata places it in the city, whether it carries
        state-level evidence and whether the context gate is open, its mentions (gazetteer forms, never the
        signal's text), the scored readings and the geocode. For audits and the parity report."""
        sig = signal if isinstance(signal, RawOsintSignal) else RawOsintSignal.model_validate(signal)
        locality = self.source_locality(sig)
        city = self.city_scoped(sig)
        state = self.state_scoped(sig)
        text = self._text(sig)
        mentions = self.mentions(text, city=city, state=state)
        readings = self.readings(mentions, locality)
        geo = self._geocode(sig.signal_id, readings, locality) if readings else self._area_geocode(sig)
        return {
            "signal_id": sig.signal_id,
            "locality": locality,
            "city_scoped": city,
            "state_scoped": state,
            "context_open": self.context_open(self.tokens(text), city=city, state=state),
            "mentions": [
                {"form": m.form, "gaz_ids": list(m.gaz_ids), "method": m.method, "score": round(m.score, 4)}
                for m in mentions
            ],
            "readings": [
                {"gaz_id": rd.entry.gaz_id, "canonical_name": rd.entry.canonical_name, "r": round(rd.r, 4)}
                for rd in readings
            ],
            "geocode": geo.model_dump(mode="json") if geo is not None else None,
        }

    def resolve_text(self, q: str, limit: int = 5) -> list[dict[str, Any]]:
        """Gazetteer lookup for ``GET /osint/gazetteer/resolve?q=``: ranked candidates
        ``{gaz_id, canonical_name, feature_type, lon, lat, segment_id, junction_id, confidence, method}``.

        The resolver's own candidate stages on the query text: exact and grammar matches, else multi-word fuzzy;
        nothing else (no prefix guess: a lookup answers what Sajag would resolve, or nothing). An operator's query is
        about the city, so source locality is 1.0 and the context gate is open; the margin is the top candidate's
        over the next, 0 for the others. ``limit`` is capped at 50; below 1 the answer is ``[]``. Read-only."""
        limit = int(limit)
        if limit < 1:
            return []
        limit = min(limit, 50)
        query = (q or "")[:200]
        mentions = self.mentions(query, city=True)
        readings = self.readings(mentions, confidence.LOCAL)
        unique: list[Reading] = []
        seen: set[int] = set()
        for rd in readings:
            if rd.entry.gaz_id not in seen:
                seen.add(rd.entry.gaz_id)
                unique.append(rd)
        out: list[dict[str, Any]] = []
        for k, rd in enumerate(unique[:limit]):
            e = rd.entry
            seg, jct, _snapped, _residual, sq = self._anchor(e)
            if k == 0:
                mg = confidence.margin(rd.r, unique[1].r if len(unique) > 1 else None)
            else:
                mg = 0.0
            conf = round(confidence.score(rd.mention.score, confidence.specificity(e.feature_type), mg, sq,
                                          confidence.LOCAL), 3)
            out.append(
                {
                    "gaz_id": e.gaz_id,
                    "canonical_name": e.canonical_name,
                    "feature_type": e.feature_type,
                    "lon": e.lon,
                    "lat": e.lat,
                    "segment_id": seg,
                    "junction_id": jct,
                    "confidence": conf,
                    "method": rd.mention.method,
                }
            )
        return out


_DEFAULT: GazetteerResolver | None = None
_DEFAULT_LOCK = threading.Lock()


def default_resolver() -> GazetteerResolver:
    """The process-wide resolver over the default gazetteer and network (built once)."""
    global _DEFAULT
    with _DEFAULT_LOCK:
        if _DEFAULT is None:
            _DEFAULT = GazetteerResolver()
        return _DEFAULT


def resolve_text(q: str, limit: int = 5) -> list[dict[str, Any]]:
    """``GET /osint/gazetteer/resolve?q=``: :meth:`GazetteerResolver.resolve_text` on the default resolver."""
    return default_resolver().resolve_text(q, limit)
