"""Marathi and Hindi place words and transliterations for the gazetteer (stdlib only).

Mumbai text mixes English, Marathi, Hindi and Latin transliteration. The gazetteer's full place names in all three
scripts live in the City Pack (``cities/mumbai/gazetteer.json``) and the network (junction names in English and
Marathi); this module holds the reviewable word tables the matcher and the generator need besides them:

* :data:`MR_LATIN_SEED` — Marathi place names → their Latin form (junction and area names);
* :data:`PLACE_SCRIPTS` — for a Latin place word, its Marathi and Devanagari spellings (so a compositional name the
  pack does not list, "दादर स्थानक", reads as "dadar station");
* :data:`LATIN_VARIANTS` — Latin spelling variants seen in local text ("ghatkoper" for "ghatkopar").

:data:`GENERIC_MR` and :data:`GENERIC_HI` map the generic place words of both scripts ("स्थानक", "चौक", "चौराहा") to
the gazetteer's Latin generic ("station", "chowk", "crossing"), so :func:`to_latin` can read a compositional name
("दादर स्थानक" → "dadar station"). :data:`MR_SUFFIXES` lists the Marathi case endings written onto a place name
("मुंबईत", in Mumbai; "दादरहून", from Dadar), which the gazetteer's scanner strips when the stem is a known place
word.

Deliberately absent: script spellings of a place whose name is a common word in that script, and any person's name
on its own. Every multi-word Latin variant keeps a place-type word, like every gazetteer phrase.

The module also holds :func:`norm`, the one normal form of the package (``osint_geo.gazetteer`` re-exports it), so
the tables and the matcher can never disagree. Stdlib only, so ``scripts/gen_osint_gazetteer.py`` imports it
without a virtual environment change.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping
from types import MappingProxyType

__all__ = [
    "GENERIC_MR",
    "GENERIC_HI",
    "MR_LATIN_SEED",
    "MR_SUFFIXES",
    "LATIN_VARIANTS",
    "PLACE_SCRIPTS",
    "is_indic",
    "latin_variants",
    "norm",
    "script_aliases",
    "to_latin",
]


_NON_WORD = re.compile(r"[^\w\u0900-\u097F\u0980-\u09FF ]+")
_SPACES = re.compile(r"\s+")
_ROAD_CODE = re.compile(r"\b(nh|sh|ne)\s(\d{1,4})\b")


def _fold_latin(s: str) -> str:
    """Drop the diacritics of Latin letters ("Vastrāpur" → "Vastrapur"); every other script is left untouched
    (Marathi and Devanagari vowel signs are letters of their word, not decoration)."""
    out: list[str] = []
    for ch in s:
        if "\u00c0" <= ch <= "\u024f" or "\u1e00" <= ch <= "\u1eff":
            base = "".join(c for c in unicodedata.normalize("NFKD", ch) if not unicodedata.combining(c))
            out.append(base or ch)
        else:
            out.append(ch)
    return "".join(out)


def norm(s: object) -> str:
    """The gazetteer's normal form of a text or a surface form (re-exported as ``osint_geo.gazetteer.norm``):
    NFKC, lower case, Unicode format characters removed (a zero-width joiner never splits a word), Latin
    diacritics folded, every run of punctuation one space (Marathi and Devanagari letters and vowel signs kept),
    and a split road code joined ("NH-147" → ``nh147``)."""
    t = unicodedata.normalize("NFKC", "" if s is None else str(s)).lower()
    if not t.isascii():
        t = "".join(ch for ch in t if unicodedata.category(ch) != "Cf")
        t = _fold_latin(t)
    t = _NON_WORD.sub(" ", t).replace("_", " ")
    t = _SPACES.sub(" ", t).strip()
    return _ROAD_CODE.sub(r"\1\2", t)


_n = norm


#: Marathi place names → their Latin form (the network's junction names and the areas they are named after).
MR_LATIN_SEED: Mapping[str, str] = MappingProxyType(
    {
        _n(mr): latin
        for mr, latin in (
            ("मुंबई", "mumbai"),
            ("सीएसएमटी", "csmt"),
            ("चर्चगेट", "churchgate"),
            ("दादर", "dadar"),
            ("वांद्रे", "bandra"),
            ("कुर्ला", "kurla"),
            ("अंधेरी", "andheri"),
            ("घाटकोपर", "ghatkopar"),
            ("बोरिवली", "borivali"),
            ("परळ", "parel"),
            ("वरळी", "worli"),
            ("सायन", "sion"),
            ("शीव", "sion"),
            ("माटुंगा", "matunga"),
            ("माहीम", "mahim"),
            ("हिंदमाता", "hindmata"),
            ("लालबाग", "lalbaug"),
            ("भायखळा", "byculla"),
            ("चेंबूर", "chembur"),
            ("पवई", "powai"),
            ("सांताक्रूझ", "santacruz"),
        )
    }
)

#: Latin place word (as the gazetteer carries it) → (Marathi spellings, Devanagari/Hindi spellings). Full names of
#: every place are in the City Pack; these are the words a compositional name is made of, and the spellings of the
#: resolver's gated forms (``resolver.CONTEXT_FORMS``, ``STATE_GATED_FORMS``), so a gate holds in every script.
_PLACE_SCRIPTS_SRC: tuple[tuple[str, tuple[str, ...], tuple[str, ...]], ...] = (
    ("dadar", ("दादर",), ("दादर",)),
    ("parel", ("परळ",), ("परेल",)),
    ("lalbaug", ("लालबाग",), ("लालबाग",)),
    ("hindmata", ("हिंदमाता",), ("हिंदमाता",)),
    ("worli", ("वरळी",), ("वर्ली",)),
    ("bandra", ("वांद्रे",), ("बांद्रा",)),
    ("kurla", ("कुर्ला",), ("कुर्ला",)),
    ("andheri", ("अंधेरी",), ("अंधेरी",)),
    ("borivali", ("बोरिवली",), ("बोरीवली",)),
    ("sion", ("सायन", "शीव"), ("सायन",)),
    ("matunga", ("माटुंगा",), ("माटुंगा",)),
    ("mahim", ("माहीम", "माहिम"), ("माहिम",)),
    ("byculla", ("भायखळा",), ("भायखला",)),
    ("chembur", ("चेंबूर",), ("चेंबूर", "चेम्बूर")),
    ("ghatkopar", ("घाटकोपर",), ("घाटकोपर",)),
    ("powai", ("पवई",), ("पवई",)),
    ("santacruz", ("सांताक्रूझ", "सांताक्रुझ"), ("सांताक्रूज़", "सांताक्रुज")),
    ("vile parle", ("विलेपार्ले", "विले पार्ले"), ("विले पार्ले",)),
    ("goregaon", ("गोरेगाव",), ("गोरेगांव",)),
    ("malad", ("मालाड",), ("मलाड",)),
    ("milan subway", ("मिलन सबवे",), ("मिलन सबवे",)),
    ("andheri subway", ("अंधेरी सबवे",), ("अंधेरी सबवे",)),
    ("kings circle", ("किंग्ज सर्कल",), ("किंग्स सर्कल",)),
    ("western express highway", ("पश्चिम द्रुतगती महामार्ग",), ("वेस्टर्न एक्सप्रेस हाईवे",)),
    ("eastern express highway", ("पूर्व द्रुतगती महामार्ग",), ("ईस्टर्न एक्सप्रेस हाईवे",)),
    # the gated forms (resolver.CONTEXT_FORMS, STATE_GATED_FORMS) in both scripts
    ("maidan", ("मैदान",), ("मैदान",)),
    ("fort", ("फोर्ट",), ("फोर्ट",)),
    ("khar", ("खार",), ("खार",)),
    ("national park", ("राष्ट्रीय उद्यान",), ("राष्ट्रीय उद्यान",)),
    ("marine drive", ("मरीन ड्राइव्ह", "मरीन ड्राईव्ह"), ("मरीन ड्राइव",)),
    ("coastal road", ("कोस्टल रोड", "सागरी किनारा मार्ग"), ("कोस्टल रोड",)),
    ("coastal", ("कोस्टल",), ("कोस्टल",)),
    ("atal setu", ("अटल सेतू",), ("अटल सेतु",)),
    ("mg road", ("एमजी रोड",), ("एमजी रोड",)),
    ("mahatma gandhi road", ("महात्मा गांधी मार्ग",), ("महात्मा गांधी रोड",)),
    ("sv road", ("एस. व्ही. रोड",), ("एसवी रोड",)),
    ("lbs marg", ("एलबीएस मार्ग",), ("एलबीएस मार्ग",)),
    ("shivaji park", ("शिवाजी पार्क",), ("शिवाजी पार्क",)),
    ("mahalaxmi temple", ("महालक्ष्मी मंदिर",), ("महालक्ष्मी मंदिर",)),
)

PLACE_SCRIPTS: Mapping[str, tuple[tuple[str, ...], tuple[str, ...]]] = MappingProxyType(
    {latin: (tuple(_n(g) for g in mr), tuple(_n(h) for h in hi)) for latin, mr, hi in _PLACE_SCRIPTS_SRC}
)

#: Latin spelling variants seen in Mumbai text, per Latin form the gazetteer carries (the City Pack lists each
#: place's own variants; these are the ones that apply to every name a word appears in).
LATIN_VARIANTS: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        "lalbaug": ("lalbag",),
        "hindmata": ("hind mata",),
        "ghatkopar": ("ghatkoper",),
        "borivali": ("borivli",),
        "kandivali": ("kandivli",),
        "santacruz": ("santa cruz",),
        "vile parle": ("vileparle",),
        "mazgaon": ("mazagaon",),
        "girgaon": ("girgaum",),
        "worli": ("varli",),
        "western express highway": ("western express hwy",),
        "eastern express highway": ("eastern express hwy",),
        "kings circle": ("king circle",),
        "mahalaxmi": ("mahalakshmi",),
    }
)

#: Marathi generic place words → the gazetteer's Latin generic.
GENERIC_MR: Mapping[str, str] = MappingProxyType(
    {
        _n(mr): latin
        for mr, latin in (
            ("चौक", "chowk"),
            ("नाका", "naka"),
            ("सर्कल", "circle"),
            ("जंक्शन", "junction"),
            ("रोड", "road"),
            ("रस्ता", "road"),
            ("मार्ग", "marg"),
            ("महामार्ग", "highway"),
            ("पूल", "bridge"),
            ("सेतू", "setu"),
            ("उड्डाणपूल", "flyover"),
            ("सबवे", "subway"),
            ("भुयारी मार्ग", "subway"),
            ("स्थानक", "station"),
            ("स्टेशन", "station"),
            ("रुग्णालय", "hospital"),
            ("हॉस्पिटल", "hospital"),
            ("मंदिर", "temple"),
            ("पार्क", "park"),
            ("उद्यान", "garden"),
            ("चौपाटी", "chowpatty"),
            ("मार्केट", "market"),
            ("बाजार", "market"),
            ("पोलीस ठाणे", "police station"),
            ("स्टेडियम", "stadium"),
            ("मैदान", "maidan"),
            ("तलाव", "lake"),
        )
    }
)

#: Hindi (Devanagari) generic place words → the gazetteer's Latin generic.
GENERIC_HI: Mapping[str, str] = MappingProxyType(
    {
        _n(hi): latin
        for hi, latin in (
            ("चौक", "chowk"),
            ("चौराहा", "crossing"),
            ("नाका", "naka"),
            ("सर्कल", "circle"),
            ("जंक्शन", "junction"),
            ("रोड", "road"),
            ("मार्ग", "marg"),
            ("हाईवे", "highway"),
            ("सेतु", "setu"),
            ("पुल", "bridge"),
            ("ब्रिज", "bridge"),
            ("फ्लाईओवर", "flyover"),
            ("सबवे", "subway"),
            ("अंडरपास", "underpass"),
            ("स्टेशन", "station"),
            ("अस्पताल", "hospital"),
            ("मंदिर", "temple"),
            ("पार्क", "park"),
            ("चौपाटी", "chowpatty"),
            ("मार्केट", "market"),
            ("थाना", "police station"),
            ("स्टेडियम", "stadium"),
            ("मैदान", "maidan"),
        )
    }
)

#: Marathi case endings and postpositions written onto a noun: "मुंबईत" (in Mumbai), "अंधेरीतील" (in Andheri,
#: adjectival), "दादरहून" (from Dadar), "रस्त्यावर" (on the road), "पोलिसांना" (to the police); and the Kolkata
#: pack's Bengali endings ("কলকাতায়", "বেহালার"), longest first. The scanner strips one only when what remains is a
#: gazetteer word. "য়" may be one code point or "য" + nukta; NFKC makes them one form. The same list, in the same
#: order, as ``osint_common.ethics.INDIC_SUFFIXES`` (a lockstep test pins the two equal; this module stays
#: standard-library only, so the list is written out here).
_MR_ENDINGS: tuple[str, ...] = (
    "ांमध्ये", "ामध्ये", "मध्ये", "ांच्या", "ाच्या", "च्या", "मधील", "मधून", "ातील", "तील", "ावरील", "वरील",
    "ावरून", "वरून", "ातून", "तून", "ाहून", "हून", "ामुळे", "मुळे", "ाजवळ", "जवळ", "साठी", "पर्यंत", "कडे",
    "ांचा", "ांची", "ांचे", "ांना", "ांनी", "ांत", "ांवर", "ावर", "वर", "ाचा", "ाची", "ाचे", "ाला", "ाने",
    "ात", "चा", "ची", "चे", "ला", "ना", "ने", "नी", "ही", "त", "ां", "च",
)
_BN_ENDINGS: tuple[str, ...] = (
    "য়ের", "য়ে", "য়", "তেই", "তে", "দের", "গুলো", "গুলি", "টির", "টি", "টা", "কে", "রা", "এর", "ের", "র", "এ", "ে", "েই", "ই",
)
MR_SUFFIXES: tuple[str, ...] = tuple(
    sorted({_n(s) for s in (*_MR_ENDINGS, *_BN_ENDINGS)}, key=lambda s: (-len(s), s))
)


def _script_words() -> Mapping[str, str]:
    """Script word or phrase → Latin, for :func:`to_latin`: place names and generics of both scripts, the PoC seed
    winning on a clash."""
    words: dict[str, str] = {}
    for latin, (mr, hi) in PLACE_SCRIPTS.items():
        for s in mr + hi:
            words.setdefault(s, latin)
    for s, latin in (*GENERIC_MR.items(), *GENERIC_HI.items()):
        words.setdefault(s, latin)
    words.update(MR_LATIN_SEED)
    return MappingProxyType(words)


def _aliases() -> Mapping[str, tuple[str, ...]]:
    """Latin form → its Marathi and Devanagari spellings (the place table, then the PoC seed)."""
    out: dict[str, tuple[str, ...]] = {
        latin: tuple(dict.fromkeys(mr + hi)) for latin, (mr, hi) in PLACE_SCRIPTS.items()
    }
    for mr, latin in MR_LATIN_SEED.items():
        out[latin] = tuple(dict.fromkeys((*out.get(latin, ()), mr)))
    return MappingProxyType(out)


_WORDS = _script_words()
_MAX_WORD_TOKENS = max(k.count(" ") + 1 for k in _WORDS)
_ALIASES = _aliases()
_INDIC = re.compile(r"[\u0900-\u097F\u0980-\u09FF]")


def is_indic(s: str) -> bool:
    """True when ``s`` contains a Devanagari or Marathi character."""
    return _INDIC.search(s) is not None


def script_aliases(latin_form: str) -> tuple[str, ...]:
    """The Marathi and Devanagari spellings of a Latin gazetteer form (normalised), or ``()``."""
    return _ALIASES.get(_n(latin_form), ())


def latin_variants(latin_form: str) -> tuple[str, ...]:
    """The Latin spelling variants of a Latin gazetteer form (normalised), or ``()``."""
    return LATIN_VARIANTS.get(_n(latin_form), ())


def to_latin(name: str) -> str | None:
    """A Marathi or Hindi place name → its Latin form: a whole-name lookup, else word by word over the place and
    generic tables ("दादर स्थानक" → "dadar station"). ``None`` unless every word is known: a partial transliteration
    would be a guess."""
    key = _n(name or "")
    if not key:
        return None
    if key in _WORDS:
        return _WORDS[key]
    toks = key.split(" ")
    out: list[str] = []
    i = 0
    while i < len(toks):
        for j in range(min(len(toks), i + _MAX_WORD_TOKENS), i, -1):
            latin = _WORDS.get(" ".join(toks[i:j]))
            if latin is not None:
                out.append(latin)
                i = j
                break
        else:
            return None
    return " ".join(out)
