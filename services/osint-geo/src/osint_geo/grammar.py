"""The regex place grammar (OSINT SPEC §1.4 step 2; research A4): candidate place spans the dictionary scan misses.

Three span kinds, read from the text as given (:func:`find_spans`):

* **relational** — a cue then a capitalised name: "near Hinduja Hospital", "opp. Gandhi Market", "outside Dadar";
* **feature** — one to three words then a place word: "Hindmata chowk", "Worli naka", "Gokhale setu", "LBS Rd",
  "Andheri under pass"; Marathi and Hindi place words too ("दादर स्थानक", "सायन सर्कल");
* **pin** — a Mumbai PIN code, ``400001``-``400104`` (written "400 014" too).

A span never crosses a clause boundary (``, ; : ! ? ( ) [ ] |`` or a sentence stop). Each carries normalised lookup
``keys``, most specific first: for a feature span every head length (three words down to one) with the place word
as written and rewritten to the gazetteer's own generic ("more" → "crossing", "setu" → "bridge", "rd" → "road"),
a Marathi or Hindi head also transliterated (:func:`osint_geo.translit.to_latin`).

How the resolver uses them: :func:`feature_hits` applies the same rewrite on the token list against the gazetteer
index, so "kalanagar chowk" resolves to the one junction, Kalanagar junction, and "dadar स्थानक" to the station,
not to the bare "dadar" (which names the neighbourhood); relational and feature keys are the first candidates of the fuzzy stage (multi-word
only); a PIN is evidence that the text is about Mumbai (source locality), never a location by itself — no PIN to
area table is committed, and the resolver does not guess one.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING, Literal

from osint_geo import translit
from osint_geo.gazetteer import Hit, norm

if TYPE_CHECKING:
    from osint_geo.gazetteer import Gazetteer

__all__ = [
    "PIN_RE",
    "SYNONYMS",
    "PlaceSpan",
    "SpanKind",
    "feature_hits",
    "find_spans",
    "lookup_keys",
    "pin_codes",
]

SpanKind = Literal["relational", "feature", "pin"]

#: Place words as written → the gazetteer's own generic(s), most likely first.
_LATIN_SYNONYMS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("more", ("crossing",)),
    ("mor", ("crossing",)),
    ("moor", ("crossing",)),
    ("crossings", ("crossing",)),
    ("xing", ("crossing",)),
    ("x ing", ("crossing",)),
    ("chowrasta", ("crossing", "chowrasta")),
    ("chourasta", ("chowrasta", "crossing")),
    ("phanri", ("phari",)),
    ("setu", ("bridge",)),
    ("bridge", ("setu",)),
    ("fly over", ("flyover",)),
    ("over bridge", ("flyover", "bridge")),
    ("overbridge", ("flyover",)),
    ("under pass", ("underpass",)),
    ("rd", ("road",)),
    ("st", ("street",)),
    ("str", ("street",)),
    ("ave", ("avenue",)),
    ("av", ("avenue",)),
    ("sarani", ("sarani",)),
    ("by pass", ("bypass",)),
    ("stn", ("station",)),
    ("ps", ("police station",)),
    ("thana", ("police station",)),
    ("p s", ("police station",)),
    ("hosp", ("hospital",)),
    # Mumbai's place words: a chowk or naka is a junction, a marg a road, an underpass a subway
    ("chowk", ("chowk", "junction")),
    ("naka", ("naka", "junction")),
    ("marg", ("marg", "road")),
    ("subway", ("subway", "underpass")),
    ("underpass", ("subway", "underpass")),
    ("hwy", ("highway",)),
    ("highway", ("highway",)),
    ("chowpaty", ("chowpatty",)),
    ("chaupati", ("chowpatty",)),
)

#: Place word (token tuple) → the gazetteer generic(s) it may be rewritten to (Latin, Marathi and Hindi words).
SYNONYMS: Mapping[tuple[str, ...], tuple[str, ...]] = MappingProxyType(
    {
        **{tuple(k.split(" ")): v for k, v in _LATIN_SYNONYMS},
        **{tuple(k.split(" ")): (v,) for k, v in translit.GENERIC_MR.items()},
        **{tuple(k.split(" ")): (v,) for k, v in translit.GENERIC_HI.items()},
    }
)
_MAX_SYN = max(len(k) for k in SYNONYMS)

#: The gazetteer generics a feature span may end on, as written (beside every synonym above).
_GENERICS: frozenset[tuple[str, ...]] = frozenset(
    tuple(g.split(" "))
    for g in (
        "crossing", "flyover", "underpass", "bridge", "road", "street", "avenue", "sarani", "lane", "bypass",
        "highway", "junction", "ghat", "phari", "station", "police station", "hospital", "park", "market",
        "chowk", "naka", "circle", "marg", "subway", "chowpatty", "setu", "terminus",
    )
)
_FEATURE_WORDS: frozenset[tuple[str, ...]] = frozenset(SYNONYMS) | _GENERICS
_MAX_FEATURE = max(len(k) for k in _FEATURE_WORDS)

#: A Mumbai PIN code (``400\d\d\d``: 400001 to 400104 for Greater Mumbai; addresses also write it "400 014"),
#: standing alone: never a run of a longer number or of a hyphenated one ("1800-400014-99" is a phone number,
#: "Mumbai-400014" is a PIN). Navi Mumbai and Thane PINs (4006xx-4007xx) are outside the range.
PIN_RE = re.compile(r"(?<!\d)(?<!\d-)400 ?(?:0\d{2}|10[0-4])(?!-?\d)")

_LETTERS = r"[\w\u0900-\u097F\u0980-\u09FF]"
_WORD_RE = re.compile(rf"{_LETTERS}+(?:['’\-]{_LETTERS}+)*")
#: Punctuation that ends a clause between two words (a full stop is handled apart: abbreviations keep the clause).
_CLAUSE_BREAK = re.compile(r"[,;:!?()\[\]|]|\s[-–—]\s|[–—]")
#: Words a full stop abbreviates without ending the clause ("opp. New Market", "Dr. Suresh Sarkar Road", "A.J.C. Bose
#: Road", "St. Paul's Cathedral").
_ABBREVIATIONS = frozenset(
    {"opp", "nr", "dr", "st", "no", "rd", "mr", "mrs", "ms", "sh", "nh", "ft", "ave", "stn", "ps", "a", "j", "c", "s",
     "p", "m", "g", "n", "r", "l"}
)
_CUES: tuple[tuple[str, ...], ...] = (
    ("near",), ("nr",), ("at",), ("opposite",), ("opp",), ("outside",), ("towards",), ("behind",), ("beside",),
    ("next", "to"), ("close", "to"),
)
_CUE_WORDS = frozenset(w for c in _CUES for w in c)


@dataclass(frozen=True, slots=True)
class PlaceSpan:
    """A candidate place in a text: characters ``[start, end)`` of the text as given."""

    start: int
    end: int
    surface: str
    kind: SpanKind
    #: the name part, normalised ("hinduja hospital", "hindmata", "400012")
    head: str
    #: the gazetteer generic the place word reads as ("crossing", "bridge"), for a feature span
    feature: str | None
    #: normalised lookup keys, most specific first
    keys: tuple[str, ...]


def lookup_keys(head: str, generic_as_written: str) -> tuple[str, ...]:
    """The gazetteer keys a head plus a place word may stand for: as written, then rewritten to the gazetteer's
    generic; a Marathi or Hindi head also in its Latin form."""
    h = norm(head)
    g = norm(generic_as_written)
    if not h or not g:
        return ()
    heads = [h]
    if translit.is_indic(h):
        latin = translit.to_latin(h)
        if latin:
            heads.append(latin)
    targets = [g, *SYNONYMS.get(tuple(g.split(" ")), ())]
    out: list[str] = []
    for hh in heads:
        for t in targets:
            k = f"{hh} {t}"
            if k not in out:
                out.append(k)
    return tuple(out)


def _words(text: str) -> list[tuple[str, int, int, int]]:
    """``(normalised token, start, end, clause)`` for every token of every word (a word like "Kasba’s" or
    "Sector-V" gives two tokens with the word's offsets); the clause number grows at each break. A full stop ends
    the clause unless it follows a single letter (an initial) or a known abbreviation."""
    out: list[tuple[str, int, int, int]] = []
    clause = 0
    prev: str | None = None
    last_end = 0
    for m in _WORD_RE.finditer(text):
        gap = text[last_end : m.start()]
        if prev is not None and (
            _CLAUSE_BREAK.search(gap) or ("." in gap and not (len(prev) == 1 or prev in _ABBREVIATIONS))
        ):
            clause += 1
        w = norm(m.group(0))
        for part in w.split(" ") if w else ():
            out.append((part, m.start(), m.end(), clause))
        prev = w.split(" ")[-1] if w else prev
        last_end = m.end()
    return out


def find_spans(text: str) -> list[PlaceSpan]:
    """Every relational, feature and PIN span in ``text``, in text order (spans of different kinds may overlap)."""
    if not text:
        return []
    words = _words(text)
    toks = [w[0] for w in words]
    out: list[PlaceSpan] = []
    raw_words = [text[w[1] : w[2]] for w in words]
    n = len(words)
    # relational: a cue, then one to four capitalised (or numeric) words of the same clause
    i = 0
    while i < n:
        cue_len = next((len(c) for c in _CUES if tuple(toks[i : i + len(c)]) == c), 0)
        if cue_len and words[i][3] == words[min(i + cue_len, n - 1)][3]:
            j = i + cue_len
            k = j
            while k < n and k - j < 4 and words[k][3] == words[j][3] and (
                raw_words[k][:1].isupper() or raw_words[k][:1].isdigit()
            ):
                k += 1
            if k > j:
                head = " ".join(toks[j:k])
                s, e = words[j][1], words[k - 1][2]
                out.append(PlaceSpan(s, e, text[s:e], "relational", head, None, (head,)))
            i = j
            continue
        i += 1
    # feature: one to three head words of the same clause, then a place word
    k = 0
    while k < n:
        m = next((m for m in range(min(_MAX_FEATURE, n - k), 0, -1) if tuple(toks[k : k + m]) in _FEATURE_WORDS), 0)
        if not m or k == 0:
            k += max(m, 1)
            continue
        clause = words[k][3]
        h = 0
        while h < 3 and k - h - 1 >= 0 and words[k - h - 1][3] == clause and toks[k - h - 1] not in _CUE_WORDS:
            h += 1
        if h:
            feat = " ".join(toks[k : k + m])
            keys: list[str] = []
            for hl in range(h, 0, -1):
                for key in lookup_keys(" ".join(toks[k - hl : k]), feat):
                    if key not in keys:
                        keys.append(key)
            generic = next(iter(SYNONYMS.get(tuple(toks[k : k + m]), ())), feat)
            s, e = words[k - h][1], words[k + m - 1][2]
            out.append(PlaceSpan(s, e, text[s:e], "feature", " ".join(toks[k - h : k]), generic, tuple(keys)))
        k += m
    for pm in PIN_RE.finditer(text):
        pin = pm.group(0).replace(" ", "")
        out.append(PlaceSpan(pm.start(), pm.end(), pm.group(0), "pin", pin, None, (pin,)))
    out.sort(key=lambda s: (s.start, s.end, s.kind))
    return out


def pin_codes(text: str) -> list[str]:
    """The Mumbai PIN codes in ``text`` (``400001``-``400104``, written with or without the space), in order."""
    return [m.replace(" ", "") for m in PIN_RE.findall(text or "")]


def feature_hits(tokens: Sequence[str], gazetteer: Gazetteer) -> list[Hit]:
    """Grammar hits on a token list: a place word written another way ("more", "setu", "rd", "মোড়")
    after one to three head tokens, rewritten to the gazetteer's generic where the result is a surface form. At each
    place word the longest head wins; the hit covers the head and the place word as written."""
    out: list[Hit] = []
    n = len(tokens)
    k = 0
    while k < n:
        step = 1
        for m in range(min(_MAX_SYN, n - k), 0, -1):
            targets = SYNONYMS.get(tuple(tokens[k : k + m]))
            if not targets:
                continue
            for h in (3, 2, 1):
                if h > k or any(norm(t) != t for t in tokens[k - h : k]):
                    continue  # a head is made of real tokens: never across the resolver's sentence break
                head = " ".join(tokens[k - h : k])
                heads = [head]
                if translit.is_indic(head):
                    latin = translit.to_latin(head)
                    if latin:
                        heads.append(latin)
                key = next((f"{hh} {t}" for hh in heads for t in targets if f"{hh} {t}" in gazetteer.forms), None)
                if key is not None:
                    out.append(Hit(k - h, k + m, key, "grammar"))
                    break
            step = m
            break
        k += step
    return out
