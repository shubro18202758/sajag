"""Ethics rails enforced in code (OSINT SPEC §0 and §4): events are about PLACES and SITUATIONS, never persons.

Two checks every OSINT record passes before it is stored or displayed:

* :func:`assert_no_person_keys` — no key at any depth names a person: author, handle, username, byline,
  reporter, poster, uploader, suspect, accused, victim, owner, driver_name, face, biometric or individual_*
  (:data:`FORBIDDEN_KEY_RE`, the spec §4 denylist, frozen). It raises ``ValueError("forbidden_key:<key>")``.
* :func:`find_pii` — no person name or age survived redaction: the age expressions and the cue- or
  honorific-introduced names of the PoC's parse-time redactor (``_AGE_RES`` and ``_NAME_CUE_RE``), also when the
  name is written with initials ("Mr R. K. <surname>"), an age right after a redacted name ("[PERSON], 45,") and a
  parenthesised age ("<Name> (45)"). It returns ``[]`` when the text is clean, otherwise one short descriptor per
  hit (``"age:years_old"``, ``"age:paren"``, ``"name:Mr"``). A descriptor never repeats the name or the age, so it
  is safe in an error message or a log line. The cues are case-sensitive, as in the PoC, so a Title Case headline
  ("Accused Held For Robbery") is not mangled. A text that is not plain ASCII is also read through its detection
  view (NFKC, Unicode format characters removed), so a zero-width space, a soft hyphen or fullwidth letters
  cannot hide a name; the stored text is never changed.

Key matching fails closed. A key (as given, and NFKC-normalised) is a person key when the frozen denylist matches
it ANYWHERE, case-insensitively (``authorname``, ``userName``, ``faceprint``, ``victimname``, and also
``interface``, ``authority``, ``handler`` or ``ownership``: a lookalike is refused, never guessed harmless), OR
when one of its tokens does after splitting on ``_``, non-alphanumerics and camelCase (``driverName`` →
``driver_name``, ``individualId`` → ``individual_id``). Two things escape. One is a whole opaque id
(:data:`OPAQUE_ID_RE`: a 40-hex sha1 signal id or a canonical uuid, whose hex digits can spell ``face`` by chance).
The other is :data:`EXEMPT_KEYS`, exactly the contract keys that collide with the denylist and name no person:
``touches_persons`` (the C-U COA ethics assertion that a course of action touches NO person), ``surfaced``
(``PipelineCounts.surfaced``) and ``surface_forms`` (the X19 gazetteer's spellings of a place).
:func:`assert_no_person_keys` allows each exempt key only with its contract value type (a bool, an int, a list of
strings), so an exempt key cannot carry a name either.

Place protection (so toponyms are never flagged): a cue-introduced capitalised name is not PII when it is a
gazetteer place, e.g. "resident of Marine Drive" or "Dr. Ambedkar Road". The captured words must be covered
by gazetteer phrases (multi-word phrases always; single-word aliases only after a residence cue, so "Mr Khar" is
still flagged although "khar" names the suburb) and generic place or newsroom words; after an honorific
(:data:`HONORIFIC_CUES`) generic words alone are not enough, so "Mr Patil" or "Dr Ward" is a name. A phrase is
matched against the source text, so it may run past the 1-3 captured words: "resident of Netaji Subhash Chandra
Bose Road" and "resident of Senapati Bapat Marg" are places. The gazetteer is read
once, lazily, from ``OSINT_GAZETTEER_PATH``, else the repo's ``scripts/data/osint_gazetteer.json`` (walking up from
this file), else ``/repo/VVIP/scripts/data/...`` (the images). Without it, protection falls back to the generic
words only, which can only flag MORE, never less.

Redaction that always passes :func:`find_pii`: replace every :func:`pii_spans` span with ``[PERSON]`` (kind
``"name"``) or ``[AGE]`` (kind ``"age"``). The spans are offsets into the text as given, also for a hit found
through the detection view. ``[PERSON]`` and ``[AGE]`` are never flagged.

This module depends on the standard library only.
"""

from __future__ import annotations

import json
import os
import re
import unicodedata
from collections.abc import Iterable, Mapping
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Any, NamedTuple

from osint_common.marathi_words import MARATHI_COMMON_WORDS

__all__ = [
    "AGE_PATTERNS",
    "EXEMPT_KEYS",
    "FORBIDDEN_KEYS",
    "FORBIDDEN_KEY_RE",
    "GAZETTEER_ENV",
    "GENERIC_PLACE_WORDS",
    "HONORIFIC_CUES",
    "BENGALI_SUFFIXES",
    "INDIC_COMMON_WORDS",
    "INDIC_SUFFIXES",
    "MARATHI_SUFFIXES",
    "NAME_CUES",
    "NAME_CUE_RE",
    "OPAQUE_ID_RE",
    "PiiSpan",
    "RAW_ALLOWED_KEYS",
    "assert_no_person_keys",
    "find_pii",
    "find_unredactable",
    "gazetteer_path",
    "indic_place_forms",
    "is_forbidden_key",
    "pii_spans",
    "place_phrases",
    "reset_place_phrases",
    "unredactable_spans",
]

# ---------------------------------------------------------------------------
# Person keys
# ---------------------------------------------------------------------------

#: The person-key denylist (OSINT SPEC §4; frozen, X18). ``traffic_oracle.events`` keeps a local copy (the oracle
#: core never imports ``osint_*``); tests/test_osint_lockstep.py pins the two equal.
FORBIDDEN_KEY_RE = (
    r"author|person|handle|username|byline|reporter|poster|uploader|suspect|accused|victim|owner|driver_name"
    r"|face|biometric|individual_"
)

_TERMS: tuple[str, ...] = tuple(FORBIDDEN_KEY_RE.split("|"))
_WORD_TERMS: tuple[str, ...] = tuple(t for t in _TERMS if not t.endswith("_"))
_PREFIX_TERMS: tuple[str, ...] = tuple(t for t in _TERMS if t.endswith("_"))

#: Every exact key the denylist forbids (each term and its plural); ``individual_*`` is a prefix and is matched by
#: :func:`is_forbidden_key`, so it cannot be enumerated here.
FORBIDDEN_KEYS: frozenset[str] = frozenset(
    {t for t in _WORD_TERMS} | {t + ("es" if t.endswith("s") else "s") for t in _WORD_TERMS}
)

#: The only keys that contain a denylist term and are still allowed: contract keys that name no person, each with
#: the one value type the contract gives it (:func:`assert_no_person_keys` refuses any other value). They are
#: exactly the collisions across every osint_common model field, ``RAW_ALLOWED_KEYS``, the X19 gazetteer and the
#: PoC outputs (tests/test_ethics.py pins the equality).
_EXEMPT_VALUE_TYPES: Mapping[str, tuple[type, ...]] = MappingProxyType(
    {
        "surface_forms": (list, tuple),  # X19 gazetteer: the spellings of a PLACE (a list of strings)
        "surfaced": (int,),  # C-T PipelineCounts.surfaced: a count of situations (a bool is an int too)
        "touches_persons": (bool,),  # C-U CoaEthics: asserts that a course of action touches NO person
    }
)
EXEMPT_KEYS: frozenset[str] = frozenset(_EXEMPT_VALUE_TYPES)

#: Opaque machine ids are never person keys, even when their hex digits happen to spell a term (``face``: about
#: one sha1 signal id in 2,000 does, so a map keyed by signal id would otherwise fail at random): a whole 40-hex
#: sha1 (a signal id, ``sha1(f"{source}:{source_id}")``) or a whole canonical lower-case uuid. Matched in full on
#: the key as given, before both rules; anything that merely looks like an id (upper case, a URN, a truncated or
#: padded hash, a trailing newline) is still checked. ``traffic_oracle.events`` mirrors it (lockstep-pinned).
OPAQUE_ID_RE = r"[0-9a-f]{40}|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
_OPAQUE_ID = re.compile(OPAQUE_ID_RE)

#: The denylist anywhere in the key, case-insensitive (fail closed).
_ANYWHERE_RE = re.compile(FORBIDDEN_KEY_RE, re.IGNORECASE)

_KEY_RE = re.compile(
    r"(?:^|_)(?:" + "|".join(re.escape(t) for t in _WORD_TERMS) + r")(?:e?s)?(?=_|$)"
    r"|(?:^|_)(?:" + "|".join(re.escape(t) for t in _PREFIX_TERMS) + r")"
)

#: Keys allowed inside ``RawOsintSignal.raw``: scalar ids, codes, timestamps and domains of the source record
#: (OSINT SPEC §1.2: a sanitised whitelist, never the untouched record). Anything else is refused at the model.
RAW_ALLOWED_KEYS: frozenset[str] = frozenset(
    {
        # GDELT 2.1 events / GKG bulk rows (ids, CAMEO codes, scores, ActionGeo codes; never Actor names or PERSONS)
        "global_event_id",
        "gkg_record_id",
        "sql_date",
        "date_added",
        "event_code",
        "event_base_code",
        "event_root_code",
        "quad_class",
        "goldstein_scale",
        "num_mentions",
        "num_sources",
        "num_articles",
        "avg_tone",
        "action_geo_type",
        "action_geo_country_code",
        "action_geo_adm1_code",
        "action_geo_feature_id",
        "source_url_domain",
        # GDELT DOC 2.0 article list
        "seendate",
        "domain",
        "source_country",
        "doc_language",
        # Google News RSS (pointer layer)
        "guid",
        "source_domain",
        "pub_date",
        # NDMA SACHET CAP 1.2
        "cap_identifier",
        "cap_sent",
        "cap_status",
        "cap_msg_type",
        "cap_scope",
        "cap_category",
        "cap_event",
        "cap_urgency",
        "cap_severity",
        "cap_certainty",
        "cap_effective",
        "cap_onset",
        "cap_expires",
        "cap_area_code",
        "cap_polygon_id",
        # Reddit Atom (the entry, never its author)
        "subreddit",
        "entry_updated",
        # Common Crawl CDX / WARC
        "cc_index",
        "cc_digest",
        "warc_filename",
        "warc_offset",
        "warc_length",
        "http_status",
        "mime",
        # official page scrapes
        "page_hash",
        "page_url_domain",
    }
)

_MAX_DEPTH = 64


def _key_tokens(key: str) -> str:
    """``authorName`` → ``author_name``; ``URLAuthor`` → ``url_author``; ``post-author`` → ``post_author``."""
    s = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", key)
    s = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", "_", s)
    return re.sub(r"[^a-z0-9]+", "_", s.lower())


def is_forbidden_key(key: object) -> bool:
    """True when ``key`` names a person. Fails closed (module docstring): the denylist anywhere in the key,
    case-insensitive, or in one of its tokens, checked on the key as given AND on its NFKC form (fullwidth letters
    fold to ASCII; a combining mark NFKC composes into a letter cannot hide a term); only :data:`EXEMPT_KEYS` and
    whole opaque ids (:data:`OPAQUE_ID_RE`: a 40-hex sha1 or a canonical uuid) escape."""
    raw = str(key)
    if raw in EXEMPT_KEYS or _OPAQUE_ID.fullmatch(raw) is not None:
        return False
    for s in (raw, unicodedata.normalize("NFKC", raw)):
        if _ANYWHERE_RE.search(s) is not None or _KEY_RE.search(_key_tokens(s)) is not None:
            return True
    return False


def _exempt_value_ok(key: str, value: Any) -> bool:
    """An exempt key carries only its contract value type (a gazetteer's ``surface_forms`` only strings)."""
    if not isinstance(value, _EXEMPT_VALUE_TYPES[key]):
        return False
    return key != "surface_forms" or all(isinstance(x, str) for x in value)


def assert_no_person_keys(obj: Any) -> None:
    """Recursive over mapping keys (and list, tuple and set items, and pydantic models through ``model_dump``).

    Raises ``ValueError("forbidden_key:<key>")`` at the first person key (or an exempt key carrying anything but
    its contract value type), and ``ValueError("invalid:...")`` for a structure nested deeper than 64 levels (a
    cycle or a hostile payload).
    """
    _walk_keys(obj, 0)


def _walk_keys(obj: Any, depth: int) -> None:
    if depth > _MAX_DEPTH:
        raise ValueError(f"invalid:nesting deeper than {_MAX_DEPTH} levels")
    dump = getattr(obj, "model_dump", None)
    if callable(dump) and not isinstance(obj, type):
        obj = dump()
    if isinstance(obj, Mapping):
        for k, v in obj.items():
            if is_forbidden_key(k) or (str(k) in EXEMPT_KEYS and not _exempt_value_ok(str(k), v)):
                raise ValueError(f"forbidden_key:{str(k)[:64]}")
            _walk_keys(v, depth + 1)
    elif isinstance(obj, (list, tuple, set, frozenset)):
        for v in obj:
            _walk_keys(v, depth + 1)


# ---------------------------------------------------------------------------
# Surviving PII in free text
# ---------------------------------------------------------------------------

#: The PoC's ``_AGE_RES``: "45-year-old", "45 yrs old", "aged 45", and "<word>, 45," (span = the number only),
#: the last also right after a redacted name ("[PERSON], 45,": exactly what a name-first redaction pass leaves
#: behind); plus the parenthesised form "<Name> (45)" / "[PERSON] (45)" (span = the number only).
AGE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("age:years_old", re.compile(r"\b\d{1,3}[\s-]?(?:year|yr)s?[\s-]?old\b", re.I)),
    ("age:aged", re.compile(r"\b(?:aged|age)\s+\d{1,3}\b", re.I)),
    ("age:comma", re.compile(r"(?<=[A-Za-z\]])\s*,\s*(?P<age>\d{1,3})(?=\s*,)")),
    ("age:paren", re.compile(r"(?:\b[A-Z][a-z]+|\[PERSON\])\s*\(\s*(?P<age>\d{1,3})\s*\)")),
)

#: Role cues and honorifics that in Indian news reliably precede a person name (the PoC's ``_NAME_CUE``, plus
#: "ASI", the rank the PoC caught only because it had no word boundary before "SI"). Case-sensitive, as in the
#: PoC, so Title-Case headlines are not mangled.
NAME_CUES: tuple[str, ...] = (
    "content creator",
    "creator",
    "the accused",
    "accused",
    "resident of",
    "resident",
    "deceased",
    "victim",
    "complainant",
    "named",
    "identified as",
    "one",
    "driver named",
    "Mr",
    "Mrs",
    "Ms",
    "Shri",
    "Smt",
    "Sri",
    "Srimati",
    "Dr",
    "Advocate",
    "advocate",
    "Constable",
    "constable",
    "Sergeant",
    "OC",
    "Inspector",
    "SI",
    "ASI",
    "PSI",
    "PI",
    "DCP",
    "ACP",
    "DySP",
)

#: A cue (word-bounded, so "zone" or "API" never read as "one" or "PI") then one to three capitalised words,
#: optionally after one to three initials ("Mr R. K. <surname>", "Shri A.B. <surname>": Indian news often writes
#: names that way, and an honorific before initials is a person). Groups: ``cue`` and ``name``.
NAME_CUE_RE = re.compile(
    r"\b(?P<cue>" + "|".join(re.escape(c) for c in sorted(NAME_CUES, key=len, reverse=True)) + r")\.?\s+"
    r"(?P<name>(?:[A-Z]\.\s?){0,3}[A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,}){0,2})"
)

_RESIDENCE_CUES = frozenset({"resident of", "resident"})

#: The honorifics: what follows one is a person unless a gazetteer phrase says otherwise ("Dr. Ambedkar Road").
#: Generic words alone never make it a place, so a surname that is also a place word ("Mr Rath", "Dr Ward",
#: "Mr Cross") is still a name. (After a rank cue they may: "DCP Zone 7" is a unit, not a person.)
HONORIFIC_CUES: frozenset[str] = frozenset({"Mr", "Mrs", "Ms", "Shri", "Smt", "Sri", "Srimati", "Dr"})

#: Generic place, civic and newsroom words that are never a person's name on their own (the PoC's protect words,
#: without the one that is also a common given name, plus a few civic nouns).
GENERIC_PLACE_WORDS: frozenset[str] = frozenset(
    {
        "mumbai", "bombay", "maharashtra", "thane", "india", "delhi",
        "bmc", "mmrda", "msrdc", "mmrcl", "imd", "ndrf",
        # the Kolkata pack's place and agency words (the second city pack)
        "kolkata", "calcutta", "howrah", "bengal", "bidhannagar",
        "bmw", "kmc", "wbtc", "nkda", "kmda", "cesc", "iim", "apk",
        "police", "inspector", "constable", "sergeant", "court", "case", "fir", "rs", "lakh",
        "crore", "road", "highway", "circle", "junction", "bridge", "flyover",
        "accident", "crash", "fire", "flood", "robbery", "burglary", "mob", "times",
        "samachar", "acres", "urban", "hospital", "civil", "club",
        "news", "english", "report", "arrested", "booked", "injured", "after",
        "near", "three", "multi", "vehicle", "beaten", "driver", "file", "filed",
        "man", "woman", "son", "allegedly", "attacks", "iron", "rod", "leaves",
        "unconscious", "labourer", "thrown", "feet", "two", "wheeler", "him",
        "posing", "cheating", "jeweller", "gallstones", "doctors", "cyberfraud",
        "drug", "trail", "haul", "puja", "pujo", "durga", "pandal", "dussehra",
        "ganeshotsav", "visarjan", "monorail",
        # civic nouns and place words (the Kolkata pack's: sarani, more, para). A place noun that can follow a name
        # ("nagar", "marg", "naka", "east", "west") is deliberately absent: "<Name> Nagar" must stay a name unless the
        # gazetteer names the place.
        "station", "district", "city", "state", "market", "temple", "university", "college", "school",
        "airport", "metro", "railway", "underpass", "cross", "roads", "chowk", "ring", "stadium",
        "zone", "ward", "street", "sarani", "avenue", "lane", "crossing", "bypass", "setu", "ghat", "bazar",
        "more", "para",
    }
)

GAZETTEER_ENV = "OSINT_GAZETTEER_PATH"
_REPO_GAZETTEER = ("scripts", "data", "osint_gazetteer.json")
_IMAGE_GAZETTEER = Path("/repo/VVIP/scripts/data/osint_gazetteer.json")
_MAX_GAZETTEER_BYTES = 8 * 1024 * 1024


class PiiSpan(NamedTuple):
    """One surviving PII hit: replace ``text[start:end]`` with ``[PERSON]`` (kind ``name``) or ``[AGE]``."""

    start: int
    end: int
    kind: str  # "name" | "age"
    label: str  # the find_pii descriptor: "age:years_old" | "age:aged" | "age:comma" | "age:paren" | "name:<cue>"


def _norm_phrase(s: str) -> str:
    """NFKC, lower case, every run of non [a-z0-9] → one space ("Dr. Ambedkar Road" → "dr ambedkar road")."""
    s = unicodedata.normalize("NFKC", str(s)).lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def gazetteer_path() -> Path | None:
    """Where the place gazetteer is: ``$OSINT_GAZETTEER_PATH``, else repo-rooted, else the image path."""
    env = os.environ.get(GAZETTEER_ENV)
    if env:
        p = Path(env)
        return p if p.is_file() else None
    here = Path(__file__).resolve()
    for parent in here.parents:
        cand = parent.joinpath(*_REPO_GAZETTEER)
        if cand.is_file():
            return cand
    return _IMAGE_GAZETTEER if _IMAGE_GAZETTEER.is_file() else None


@lru_cache(maxsize=1)
def place_phrases() -> frozenset[str]:
    """Normalised gazetteer place phrases (canonical names, their parts, surface forms); empty when absent.

    Never raises: an unreadable or malformed gazetteer gives the empty set (stricter, never laxer).
    """
    path = gazetteer_path()
    if path is None:
        return frozenset()
    try:
        if path.stat().st_size > _MAX_GAZETTEER_BYTES:
            return frozenset()
        doc = json.loads(path.read_text(encoding="utf-8"))
        entries = doc.get("entries", []) if isinstance(doc, Mapping) else []
        out: set[str] = set()
        for e in entries if isinstance(entries, list) else []:
            if not isinstance(e, Mapping):
                continue
            names: list[str] = []
            canon = e.get("canonical_name")
            if isinstance(canon, str):
                names.append(canon)
                # "Salt Lake Stadium (EM Bypass)" → also "Salt Lake Stadium" and "EM Bypass"
                names.extend(part for part in re.split(r"[()]", canon) if part.strip())
            forms = e.get("surface_forms")
            if isinstance(forms, list):
                names.extend(f for f in forms if isinstance(f, str))
            for n in names:
                p = _norm_phrase(n[:200])
                if p:
                    out.add(p)
        return frozenset(out)
    except (OSError, ValueError, TypeError):
        return frozenset()


def reset_place_phrases() -> None:
    """Forget the cached gazetteer phrases (tests, or after the gazetteer is regenerated)."""
    place_phrases.cache_clear()
    indic_place_forms.cache_clear()


#: How much of the text after a captured name a gazetteer phrase may run into (a place name longer than the 1-3
#: captured words, or one the capture stopped inside at a hyphen: "Netaji Subhash Chandra Bose Road",
#: "Sion-Koliwada").
#: Phrases are at most 200 characters (see :func:`place_phrases`).
_PLACE_LOOKAHEAD = 256


def _following_tokens(text: str, end: int) -> list[str]:
    """The normalised words of ``text`` after ``end`` (bounded; a word the window cut in two is dropped)."""
    toks = _norm_phrase(text[end : end + _PLACE_LOOKAHEAD]).split()
    if end + _PLACE_LOOKAHEAD < len(text) and toks:
        toks.pop()
    return toks


def _longest_phrase(toks: list[str], i: int, phrases: frozenset[str], max_len: int, allow_single: bool) -> int:
    """The end of the longest gazetteer phrase that starts at ``toks[i]``, else 0."""
    for j in range(min(len(toks), i + max_len), i, -1):
        if (j - i >= 2 or allow_single) and " ".join(toks[i:j]) in phrases:
            return j
    return 0


def _covered(
    toks: list[str],
    start: int,
    stop: int,
    phrases: frozenset[str],
    max_len: int,
    allow_single: bool,
    need_phrase: bool = False,
) -> bool:
    """Every captured word ``toks[start:stop]`` is consumed by a gazetteer phrase (longest first; a phrase may run
    past ``stop`` into the text that follows) or is a generic place word. With ``need_phrase`` (after an
    honorific) at least one gazetteer phrase must take part: generic words alone are not a place."""
    i = start
    used_phrase = False
    while i < stop:
        j = _longest_phrase(toks, i, phrases, max_len, allow_single)
        if j:
            i = j
            used_phrase = True
        elif toks[i] in GENERIC_PLACE_WORDS:
            i += 1
        else:
            return False
    return used_phrase or not need_phrase


def _is_place(text: str, m: re.Match[str], phrases: frozenset[str], max_len: int) -> bool:
    """Is the cue-introduced capture ``m`` a place? Matched as words of the source text from the cue on, so a
    gazetteer phrase may be longer than the capture (or run on past a hyphen the capture stopped at)."""
    cue = m.group("cue")
    cue_t = _norm_phrase(cue).split()
    name_t = _norm_phrase(m.group("name")).split()
    start, stop = len(cue_t), len(cue_t) + len(name_t)
    toks = cue_t + name_t + _following_tokens(text, m.end("name"))
    # a place whose name starts with the cue word ("Dr. Ambedkar Road", optionally followed by generic words)
    j = _longest_phrase(toks, 0, phrases, max_len, True)
    if j > start and _covered(toks, j, stop, phrases, max_len, False):
        return True
    return _covered(
        toks, start, stop, phrases, max_len, cue in _RESIDENCE_CUES, need_phrase=cue in HONORIFIC_CUES
    )


def _detection_view(text: str) -> tuple[str, list[int]] | None:
    """``text`` as the detector also reads it, and the raw index each view character came from: every character
    NFKC-folded (fullwidth letters and digits → ASCII) and the Unicode format characters (category Cf: zero-width
    space and joiners, soft hyphen, word joiner, BOM, bidi marks) removed, so they cannot split a cue or a name.
    ``None`` when the view is the text itself (always for ASCII). Only detection reads the view: stored text is
    never changed (ZWJ and ZWNJ carry meaning in Indic scripts)."""
    if text.isascii():
        return None
    chars: list[str] = []
    origin: list[int] = []
    for i, ch in enumerate(text):
        for c in unicodedata.normalize("NFKC", ch):
            if unicodedata.category(c) != "Cf":
                chars.append(c)
                origin.append(i)
    view = "".join(chars)
    return None if view == text else (view, origin)


def _scan(text: str, phrases: frozenset[str]) -> list[PiiSpan]:
    """The raw (unmerged) age and cue+name hits in ``text``."""
    spans: list[PiiSpan] = []
    for label, rx in AGE_PATTERNS:
        for m in rx.finditer(text):
            if "age" in rx.groupindex:
                spans.append(PiiSpan(m.start("age"), m.end("age"), "age", label))
            else:
                spans.append(PiiSpan(m.start(), m.end(), "age", label))
    max_len = -1  # the longest phrase, in words (computed at the first cue)
    for m in NAME_CUE_RE.finditer(text):
        if max_len < 0:
            max_len = max((p.count(" ") + 1 for p in phrases), default=0)
        if _is_place(text, m, phrases, max_len):
            continue
        spans.append(PiiSpan(m.start("name"), m.end("name"), "name", f"name:{m.group('cue')}"))
    return spans


def pii_spans(text: str | None, *, protect: Iterable[str] | None = None) -> list[PiiSpan]:
    """Surviving PII spans in ``text``, sorted and non-overlapping (see :class:`PiiSpan`), as offsets into
    ``text`` itself.

    The text is scanned as given and, when it is not plain ASCII, also as its detection view (NFKC, format
    characters removed: see :func:`_detection_view`), so a zero-width space, a soft hyphen or fullwidth letters
    cannot hide a name or an age; a hit in the view is mapped back to the raw characters it came from, so
    replacing every span still removes the name. ``protect`` adds place phrases (for example an ingress
    protect-set) to the gazetteer's.
    """
    if not text:
        return []
    phrases = place_phrases()
    if protect:
        phrases = phrases | frozenset(p for p in (_norm_phrase(x) for x in protect) if p)
    spans = _scan(text, phrases)
    view = _detection_view(text)
    if view is not None:
        view_text, origin = view
        for s in _scan(view_text, phrases):
            spans.append(PiiSpan(origin[s.start], origin[s.end - 1] + 1, s.kind, s.label))
    spans.sort(key=lambda s: (s.start, -s.end))
    merged: list[PiiSpan] = []
    for s in spans:
        if merged and s.start < merged[-1].end:
            last = merged[-1]
            if s.end > last.end:
                merged[-1] = PiiSpan(last.start, s.end, last.kind, last.label)
            continue
        merged.append(s)
    return merged


def find_pii(text: str | None, *, protect: Iterable[str] | None = None) -> list[str]:
    """Surviving age and cue+name patterns in ``text``: ``[]`` when clean, else one descriptor per hit.

    The descriptors (``"age:years_old"``, ``"name:Mr"``) never contain the name or the age itself.

    What this does NOT see (F-HONEST OSINT-2): a name with no cue ("Biker <Given> <Surname> dies"), a single-word
    name, and any name in an Indic script. ``[]`` therefore means "none of these patterns survived", never "no
    person is named". Parse-time redaction reaches further (``osint_ingress.connectors._redact``), and its recall
    is measured on a held-out set written independently of the patterns, not by this function. Indic-script text
    is checked by :func:`find_unredactable` (a separate check: this one guards every C-T model and must not refuse
    a Marathi place name).
    """
    return [s.label for s in pii_spans(text, protect=protect)]


# ---------------------------------------------------------------------------
# Indic-script words no redactor can read for names (F-HONEST OSINT-2)
# ---------------------------------------------------------------------------

#: The Indic script blocks read here: Devanagari through Malayalam (U+0900-U+0D7F).
_INDIC_LO, _INDIC_HI = "ऀ", "ൿ"
_ZW_JOINERS = frozenset("‌‍")

#: Marathi case endings and postpositions written onto a noun, longest first: "मुंबईत" (in Mumbai), "रस्त्यावर" (on
#: the road), "शहराच्या" (of the city), "पावसामुळे" (because of the rain), "पोलिसांना" (to the police),
#: "प्रवाशांच्या" (of the passengers), "अंधेरीतील" (in Andheri, adjectival), "दादरहून" (from Dadar). A noun that takes
#: an oblique vowel before the ending ("शहर" → "शहरा-") is read through the endings that carry it ("ाच्या", "ात").
#: The Kolkata pack (the second city pack, whose gazetteer spells places in Bengali) keeps its Bengali endings in the
#: same table ("কলকাতায়", "রাস্তার"), so a Bengali place with a case ending is still read as the place; an ending
#: only ever turns a word into its stem, and the stem must itself be a kept word. The same list, in the same order,
#: as ``osint_geo.translit.MR_SUFFIXES`` (osint-common imports nothing of osint-geo; a lockstep test in osint-geo pins
#: the two equal). "য়" is written both as one code point (U+09DF) and as "য" + nukta; NFKC makes them one form.
MARATHI_SUFFIXES: tuple[str, ...] = (
    "ांमध्ये", "ामध्ये", "मध्ये", "ांच्या", "ाच्या", "च्या", "मधील", "मधून", "ातील", "तील", "ावरील", "वरील",
    "ावरून", "वरून", "ातून", "तून", "ाहून", "हून", "ामुळे", "मुळे", "ाजवळ", "जवळ", "साठी", "पर्यंत", "कडे",
    "ांचा", "ांची", "ांचे", "ांना", "ांनी", "ांत", "ांवर", "ावर", "वर", "ाचा", "ाची", "ाचे", "ाला", "ाने",
    "ात", "चा", "ची", "चे", "ला", "ना", "ने", "नी", "ही", "त", "ां", "च",
)
#: The Kolkata pack's Bengali case endings.
BENGALI_SUFFIXES: tuple[str, ...] = (
    "য়ের", "য়ে", "য়", "তেই", "তে", "দের", "গুলো", "গুলি", "টির", "টি", "টা", "কে", "রা", "এর", "ের", "র", "এ", "ে", "েই", "ই",
)
INDIC_SUFFIXES: tuple[str, ...] = tuple(
    sorted(
        {unicodedata.normalize("NFKC", s) for s in (*MARATHI_SUFFIXES, *BENGALI_SUFFIXES)},
        key=lambda s: (-len(s), s),
    )
)

#: Ordinary Hindi and Marathi words of local news and posts (function words, numbers, civic and situation
#: nouns, common verbs) that are never a person's name on their own: the Hindi words below and
#: :data:`osint_common.marathi_words.MARATHI_COMMON_WORDS`. Deliberately absent: every given name and surname,
#: every honorific-suffixed form ("<name>राव", "<name>जी", "<name>बेन"), and words that double as names
#: ("किरण" (ray), "आशा" (hope), "विजय" (victory), "दीपक" (lamp), "प्रकाश" (light), "संध्या" (evening), "वर्षा"
#: (rain), "सागर" (sea), "पूजा" (worship), "गणेश"). An Indic word that is neither one of these nor a gazetteer place
#: is withheld at parse, so the list can only make redaction stricter by being short.
INDIC_COMMON_WORDS: frozenset[str] = frozenset(
    unicodedata.normalize("NFKC", w)
    for w in """
    में के की का को से ने पर और या है हैं था थी थे हो होगा होगी एक दो तीन चार पांच पाँच छह सात आठ नौ दस
    गया गई गए गयी किया किए की कर करके करते करने कहा बताया लिए लिया दिया मारकर हुआ हुई हुए हुआ साथ बाद पास
    पहले आज कल रात सुबह शाम दिन नहीं भी तो यह वह इस उस ये वे जो जब तक बीच दौरान तरफ ओर अब फिर बहुत सभी कई
    मुंबई महाराष्ट्र ठाणे शहर राज्य जिला जिले पुलिस थाना थाने अस्पताल सड़क सड़कों रोड मार्ग हाईवे हादसा हादसे
    दुर्घटना टक्कर आग बाढ़ बारिश जलभराव पानी हत्या मौत मृत्यु घायल गिरफ्तार गिरफ्तारी चोरी लूट डकैती ट्रक कार
    बस बाइक ऑटो रिक्शा ट्रैफिक जाम चाकू गोली हमला आरोपी आरोपियों युवक युवती महिला महिलाओं पुरुष बच्चा बच्ची
    बच्चे लोग लोगों मामला मामले दर्ज केस धारा एक्ट ब्रिज पुल फ्लाईओवर सर्कल चौराहा चौराहे स्टेशन मेट्रो
    प्रदर्शन जुलूस रैली भीड़ बंद खबर अनुसार खिलाफ शिकायत जांच अदालत कोर्ट सरकार नगर निगम बिजली गैस रिसाव
    पथराव झड़प अग्निकांड जलजमाव भारी मूसलाधार इमारत दीवार मकान गिरा गिरी गिरे गिरने ढहा ढही पेड़ उखड़ा उखड़े करंट लगने
    लगा लगी मेला शोभायात्रा रथयात्रा धरना चक्का हड़ताल रास्ता चक्रवात आंधी आकाशीय कोहरा गाड़ी डंपर टैंकर स्कूटी ट्रेलर
    दाम कीमत कीमतें कीमतों महंगाई नही न लोकल ट्रेन ट्रेनें सेवा ठप ज्वार समुद्र विसर्जन गणेशोत्सव कम बाधित
    """.split()
) | MARATHI_COMMON_WORDS

_INDIC_WITHHELD_LABEL = "script:indic"


def _indic_letter(ch: str) -> bool:
    return _INDIC_LO <= ch <= _INDIC_HI and unicodedata.category(ch)[0] in "LM"


def _indic_key(word: str) -> str:
    """A word's comparison form: NFKC, Unicode format characters (ZWJ, ZWNJ) removed."""
    return "".join(c for c in unicodedata.normalize("NFKC", word) if unicodedata.category(c) != "Cf")


@lru_cache(maxsize=1)
def indic_place_forms() -> tuple[frozenset[str], Mapping[str, tuple[tuple[str, ...], ...]]]:
    """The gazetteer's Indic-script place spellings: (single-word forms, multi-word phrases by first word).

    Never raises: a missing or malformed gazetteer gives no forms (every Indic word not in
    :data:`INDIC_COMMON_WORDS` is then withheld: stricter, never laxer)."""
    path = gazetteer_path()
    single: set[str] = set()
    multi: dict[str, set[tuple[str, ...]]] = {}
    if path is None:
        return frozenset(), MappingProxyType({})
    try:
        if path.stat().st_size > _MAX_GAZETTEER_BYTES:
            return frozenset(), MappingProxyType({})
        doc = json.loads(path.read_text(encoding="utf-8"))
        entries = doc.get("entries", []) if isinstance(doc, Mapping) else []
        for e in entries if isinstance(entries, list) else []:
            forms = e.get("surface_forms") if isinstance(e, Mapping) else None
            for f in forms if isinstance(forms, list) else []:
                if not isinstance(f, str) or not any(_indic_letter(c) for c in f):
                    continue
                words = tuple(_indic_key(w) for w, _s, _e in _indic_words(f[:200]))
                if len(words) == 1:
                    single.add(words[0])
                elif words:
                    multi.setdefault(words[0], set()).add(words)
    except (OSError, ValueError, TypeError, AttributeError):
        return frozenset(), MappingProxyType({})
    return frozenset(single), MappingProxyType({k: tuple(sorted(v)) for k, v in multi.items()})


def _indic_words(text: str) -> list[tuple[str, int, int]]:
    """``(word, start, end)`` of every run of Indic letters (vowel signs and joiners included) in ``text``."""
    out: list[tuple[str, int, int]] = []
    i, n = 0, len(text)
    while i < n:
        if not _indic_letter(text[i]):
            i += 1
            continue
        j = i + 1
        while j < n and (_indic_letter(text[j]) or text[j] in _ZW_JOINERS):
            j += 1
        out.append((text[i:j], i, j))
        i = j
    return out


def _stems(key: str) -> list[str]:
    """The word and, for each Marathi case ending it carries, the stem before it."""
    out = [key]
    for suf in INDIC_SUFFIXES:
        if key.endswith(suf) and len(key) > len(suf) + 1:
            out.append(key[: -len(suf)])
    return out


def _kept_indic(key: str, single: frozenset[str]) -> bool:
    return any(s in INDIC_COMMON_WORDS or s in single for s in _stems(key))


def unredactable_spans(text: str | None) -> list[PiiSpan]:
    """Indic-script words in ``text`` that no redactor here can read for names (kind ``"script"``), merged into
    runs: every Devanagari, Marathi (or other Indic) word that is neither a gazetteer place (a single-word form,
    a word of a multi-word place phrase that occurs in the text, or a stem before a Marathi case ending) nor in
    :data:`INDIC_COMMON_WORDS`. No Indic NER runs at parse, so an unknown word may be a person's name
    ("रमेश पटेल की हत्या"): it is withheld, never guessed harmless."""
    if not text or text.isascii():
        return []
    words = _indic_words(text)
    if not words:
        return []
    single, multi = indic_place_forms()
    keys = [_indic_key(w) for w, _s, _e in words]
    kept = [_kept_indic(k, single) for k in keys]
    for i, (_w, _start, end) in enumerate(words):  # an initial ("के. डी. <surname>") is a name part, whatever word
        nxt = words[i + 1][1] if i + 1 < len(words) else None  # it spells
        if len(keys[i]) <= 3 and text[end : end + 1] == "." and nxt is not None and text[end + 1 : nxt].strip() == "":
            kept[i] = False
    for i, k in enumerate(keys):  # a multi-word place phrase that occurs here keeps all its words
        for phrase in multi.get(k, ()):
            m = len(phrase)
            if i + m <= len(keys) and all(
                keys[i + t] == phrase[t] or (t == m - 1 and phrase[t] in _stems(keys[i + t])) for t in range(m)
            ) and all(text[words[i + t][2] : words[i + t + 1][1]].strip() == "" for t in range(m - 1)):
                for t in range(m):
                    kept[i + t] = True
    spans: list[PiiSpan] = []
    for i, (_w, start, end) in enumerate(words):
        if kept[i]:
            continue
        if spans and text[spans[-1].end : start].strip() == "" and not kept[i - 1]:
            spans[-1] = PiiSpan(spans[-1].start, end, "script", _INDIC_WITHHELD_LABEL)
        else:
            spans.append(PiiSpan(start, end, "script", _INDIC_WITHHELD_LABEL))
    return spans


def find_unredactable(text: str | None) -> list[str]:
    """``[]`` when ``text`` holds no Indic-script word that could be an unread name (:func:`unredactable_spans`),
    else one ``"script:indic"`` descriptor per run (never the words themselves)."""
    return [s.label for s in unredactable_spans(text)]
