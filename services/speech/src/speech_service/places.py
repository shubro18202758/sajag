"""Place matching for field reports: which Mumbai place did the officer name?

Sources, in precedence order:
1. ``cities/mumbai/landmarks.json``: the canonical ids and spellings (en/mr/hi).
2. ``cities/mumbai/gazetteer.json`` (events stream), when present. Its shape
   is read tolerantly; entries without coordinates are skipped and a
   landmark id always wins over a gazetteer entry with the same id.
3. :data:`ALIASES` below: everyday names officers actually say
   ("दादर टीटी", "सीएसटी" / "VT" for CSMT, "बीकेसी", "शीव" for Sion,
   "WEH" for the Western Express Highway …).

Matching works across scripts. A transcript in Devanagari (Marathi or
Hindi), a romanised one ("Andheri subway band hai") or an English one is
cut into word windows, and each window is compared with every name in two
ways:

* a light same-script comparison (Devanagari spelling variants that ASR
  mixes up — ी/ि, ू/ु, ळ/ल, ण/न, श/ष/स, nukta, anusvara/chandrabindu,
  ॅ/े, ॉ/ो — are folded first);
* a cross-script **consonant skeleton**: both scripts are mapped to a loose
  Latin consonant string with vowels dropped (हिंदमाता → ``hndmt``,
  "Hindmata" → ``hndmt``; वरळी → ``brl``, "Worli" → ``brl``: व/v/w and b
  are one letter, as ASR and speakers use them). Vowels are
  what ASR gets wrong most often and what romanisation varies most in, so
  the skeleton ignores them.

Marathi postpositions ride on the last word ("सर्कलजवळ", "सबवेमध्ये",
"नाक्यावर") and are tried with and without; Hindi ones are separate words
("में", "पर", "के पास") and are skipped as generic.

The best window/name pair gives ``match_score`` in [0, 1]. Below the
threshold (0.80 by default) no place is asserted; the top candidates are
still returned for the officer to pick from.
"""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterable

__all__ = [
    "Place",
    "PlaceMatch",
    "Gazetteer",
    "skeleton",
    "fold_mr",
    "ALIASES",
    "load_gazetteer",
]

log = logging.getLogger("speech.places")

_MR_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")

# Everyday names, keyed by cities/mumbai/landmarks.json id. Spoken forms only;
# the canonical names (en/mr/hi) come from landmarks.json itself.
ALIASES: dict[str, list[str]] = {
    "csmt": ["सीएसएमटी", "सीएसटी", "CSMT", "CST", "व्हीटी", "VT", "Victoria Terminus",
             "शिवाजी टर्मिनस", "CST station"],
    "churchgate": ["Churchgate station", "चर्चगेट स्टेशन"],
    "dadar": ["दादर", "Dadar", "दादर स्टेशन", "Dadar station", "दादर रेल्वे स्थानक"],
    "dadar_tt": ["दादर टीटी", "दादर टी टी", "Dadar TT", "Dadar T T", "टीटी सर्कल", "TT circle"],
    "hindmata": ["हिंदमाता", "हिंद माता", "Hindmata", "Hind Mata", "हिंदमाता चौक", "हिंदमाता सिनेमा"],
    "parel": ["Parel", "परेल"],
    "lalbaug": ["Lalbag", "लालबाग मार्केट"],
    "kings_circle": ["किंग्ज सर्कल", "किंग्स सर्कल", "Kings Circle", "King Circle",
                     "महेश्वरी उद्यान", "Maheshwari Udyan"],
    "sion_circle": ["सायन", "Sion", "शीव", "सायन सर्कल", "शीव सर्कल", "सायन जंक्शन"],
    "mahim_causeway": ["माहीम कॉजवे", "माहिम कॉजवे", "Mahim Causeway", "माहीम", "Mahim"],
    "kalanagar": ["कलानगर", "कला नगर", "Kalanagar", "Kala Nagar", "कलानगर जंक्शन"],
    "bkc": ["बीकेसी", "बी के सी", "BKC", "B K C", "बांद्रा कुर्ला कॉम्प्लेक्स", "Bandra Kurla Complex"],
    "haji_ali": ["हाजी अली", "हाजीअली", "Haji Ali"],
    "worli_naka": ["वरळी नाका", "वर्ली नाका", "Worli Naka", "वरळी", "वर्ली", "Worli"],
    "acharya_atre_chowk": ["आचार्य अत्रे चौक", "अत्रे चौक", "Acharya Atre Chowk", "Atre Chowk"],
    "milan_subway": ["मिलन सबवे", "मिलन सब वे", "Milan Subway", "Milan sub way"],
    "andheri_subway": ["अंधेरी सबवे", "अंधेरी सब वे", "Andheri Subway", "Andheri sub way"],
    "andheri": ["अंधेरी", "Andheri", "अंधेरी स्टेशन", "Andheri station"],
    "weh_andheri": ["पश्चिम द्रुतगती महामार्ग", "वेस्टर्न एक्सप्रेस हायवे", "वेस्टर्न एक्सप्रेस हाईवे",
                    "Western Express Highway", "Western Express", "WEH", "डब्ल्यूईएच"],
    "bandra": ["वांद्रे", "बांद्रा", "Bandra", "वांद्रे स्टेशन", "बांद्रा स्टेशन", "Bandra station"],
    "kurla": ["कुर्ला", "Kurla", "कुर्ला स्टेशन", "Kurla station"],
    "ltt": ["एलटीटी", "LTT", "लोकमान्य टिळक टर्मिनस", "Lokmanya Tilak Terminus"],
    "ghatkopar": ["Ghatkopar", "घाटकोपर स्टेशन"],
    "chembur": ["चेम्बूर", "Chembur"],
    "powai": ["पवई", "Powai", "जेव्हीएलआर", "जेवीएलआर", "JVLR", "जोगेश्वरी विक्रोळी लिंक रोड",
              "Jogeshwari Vikhroli Link Road"],
    "borivali": ["बोरीवली", "Borivali", "बोरिवली स्टेशन"],
    "airport_t2": ["विमानतळ", "एअरपोर्ट", "एयरपोर्ट", "Airport", "टर्मिनल दोन", "Terminal 2",
                   "सहार विमानतळ", "Sahar airport"],
    "airport_t1": ["टर्मिनल एक", "Terminal 1", "सांताक्रूझ विमानतळ", "Santacruz airport",
                   "डोमेस्टिक एअरपोर्ट", "domestic airport"],
    "sea_link": ["सी लिंक", "सीलिंक", "Sea Link", "वांद्रे वरळी सी लिंक", "बांद्रा वर्ली सी लिंक",
                 "Bandra Worli Sea Link", "राजीव गांधी सागरी सेतू"],
    "atal_setu": ["अटल सेतू", "अटल सेतु", "Atal Setu", "एमटीएचएल", "MTHL", "ट्रान्स हार्बर लिंक",
                  "Trans Harbour Link"],
    "mantralaya": ["Mantralaya"],
    "raj_bhavan": ["Raj Bhavan", "राज भवन", "Malabar Hill", "मलबार हिल"],
    "bmc_hq": ["महापालिका मुख्यालय", "बीएमसी मुख्यालय", "BMC headquarters", "BMC HQ"],
    "police_hq": ["पोलीस मुख्यालय", "पुलिस मुख्यालय", "Police headquarters", "क्रॉफर्ड मार्केट",
                  "Crawford Market"],
    "traffic_hq": ["वाहतूक पोलीस मुख्यालय", "ट्रैफिक पुलिस मुख्यालय", "Traffic police headquarters"],
    "wankhede": ["वानखेडे", "वानखेड़े", "Wankhede"],
    "marine_drive": ["मरीन ड्राइव्ह", "मरीन ड्राइव", "Marine Drive", "क्वीन्स नेकलेस", "Queens Necklace"],
    "girgaon_chowpatty": ["गिरगाव चौपाटी", "गिरगांव चौपाटी", "Girgaon Chowpatty", "Girgaum Chowpatty",
                          "गिरगाव", "Girgaon"],
    "gateway": ["गेटवे", "Gateway", "गेटवे ऑफ इंडिया", "Gateway of India"],
    "shivaji_park": ["शिवाजी पार्क", "Shivaji Park", "शिवाजी उद्यान"],
    "juhu_beach": ["जुहू", "Juhu", "जुहू बीच", "जुहू चौपाटी", "Juhu Beach", "Juhu Chowpatty"],
    "lalbaugcha_raja": ["लालबागचा राजा", "लालबाग चा राजा", "Lalbaugcha Raja", "Lalbaug cha Raja"],
    "gsb_kings_circle": ["जीएसबी", "GSB", "जीएसबी गणपती", "GSB Ganpati", "जीएसबी सेवा मंडळ"],
    "kem": ["केईएम", "के ई एम", "KEM", "K E M", "केईएम हॉस्पिटल", "KEM Hospital"],
    "sion_hospital": ["सायन हॉस्पिटल", "सायन अस्पताल", "Sion Hospital", "LTMGH",
                      "लोकमान्य टिळक रुग्णालय"],
    "jj_hospital": ["जेजे", "जे जे", "JJ", "J J", "जेजे हॉस्पिटल", "JJ Hospital"],
    "nair_hospital": ["नायर", "Nair", "नायर हॉस्पिटल", "Nair Hospital"],
    "cooper_hospital": ["कूपर", "Cooper", "कूपर हॉस्पिटल", "Cooper Hospital"],
    "haji_ali_ps": ["हाजी अली पंपिंग स्टेशन", "Haji Ali pumping station"],
    "irla_ps": ["इर्ला पंपिंग स्टेशन", "Irla pumping station", "इर्ला", "Irla"],
    "love_grove_ps": ["लव्ह ग्रोव्ह", "लव ग्रोव", "Love Grove", "Love Grove pumping station"],
    "cleveland_bunder_ps": ["क्लीव्हलँड बंदर", "क्लीवलैंड बंदर", "Cleveland Bunder"],
    "britannia_ps": ["ब्रिटानिया पंपिंग स्टेशन", "Britannia pumping station", "ब्रिटानिया", "Britannia"],
    "gazdarbandh_ps": ["गझदरबंध", "गजदरबंध", "Gazdarbandh", "Gazdar Bandh"],
    "mithi_kurla": ["मिठी नदी", "मीठी नदी", "Mithi river", "मिठी", "Mithi"],
    "apollo_bunder": ["अपोलो बंदर", "Apollo Bunder"],
}

# Words that name a kind of place or a direction, not a place. A window made
# only of these never matches (a window may not start with one), and they are
# dropped from a name to form its short form.
GENERIC = {
    # Marathi
    "येथे", "इथे", "तेथे", "जवळ", "जवळच", "समोर", "बाहेर", "मागे", "रस्ता", "रस्त्यावर", "रस्त्यात",
    "रोड", "रोडवर", "मार्ग", "मार्गावर", "पूल", "पुलावर", "स्थानक", "स्थानकात", "स्थानकाबाहेर",
    "स्टेशन", "स्टेशनवर", "स्टेशनजवळ", "परिसर", "परिसरात", "भाग", "भागात", "सर्कल", "सर्कलवर",
    "जंक्शन", "जंक्शनवर", "चौकात", "कडे", "आणि", "व", "एक", "दोन",
    # Hindi
    "में", "पर", "के", "का", "की", "को", "से", "पास", "तरफ", "सामने", "बाहर", "सड़क", "रास्ता",
    "रास्ते", "इलाके", "इलाका", "चौराहा", "चौराहे", "और", "है", "हैं",
    # English and romanised
    "crossing", "junction", "circle", "road", "rd", "bridge", "station", "area", "near", "the",
    "at", "on", "in", "of", "towards", "outside", "point", "and", "a", "an", "is", "pe", "par",
    "mein", "ke", "paas", "ki", "ka", "jawal", "yethe",
}

# Devanagari letters and marks (the danda ।/॥ are punctuation and excluded)
_DEVA = "\u0900-\u0963\u0966-\u097f"
_WORD_RE = re.compile(rf"[\w{_DEVA}\u200c\u200d]+", re.UNICODE)
_APOS_RE = re.compile(r"(?<=\w)['’](?=\w)")
_PAREN_RE = re.compile(r"\s*\([^)]*\)")

# --- script folding ----------------------------------------------------------

_NUKTA = "\u093c"

_MR_FOLD = str.maketrans({
    "ी": "ि", "ू": "ु", "ई": "इ", "ऊ": "उ", "ण": "न", "ष": "स", "श": "स", "ळ": "ल",
    "ॅ": "े", "ॉ": "ो", "ऍ": "ए", "ऑ": "ओ", "ॆ": "े", "ॊ": "ो", "ँ": None, "ं": None,
    "ः": None, _NUKTA: None, "\u200c": None, "\u200d": None,
})


def _mr_compose(s: str) -> str:
    """NFC, apostrophes inside words dropped ("King's" → "Kings")."""
    return _APOS_RE.sub("", unicodedata.normalize("NFC", s))


_GEMINATE_RE = re.compile(r"([\u0915-\u0939])\u094d\1")


def fold_mr(s: str) -> str:
    """Devanagari (Marathi/Hindi) spelling folding used for same-script
    comparison. A doubled consonant is folded to one ("टक्कर" ~ "टकर",
    "सव्वे" ~ "सवे"): ASR drops and adds gemination freely."""
    return _GEMINATE_RE.sub(r"\1", _mr_compose(s)).translate(_MR_FOLD).translate(_MR_DIGITS)


_MR_CONS = {
    "क": "k", "ख": "k", "ग": "g", "घ": "g", "ङ": "n", "च": "c", "छ": "c", "ज": "j", "झ": "j",
    "ञ": "n", "ट": "t", "ठ": "t", "ड": "d", "ढ": "d", "ण": "n", "त": "t", "थ": "t", "द": "d",
    "ध": "d", "न": "n", "प": "p", "फ": "f", "ब": "b", "भ": "b", "म": "m", "य": "", "र": "r",
    "ल": "l", "ळ": "l", "व": "b", "श": "s", "ष": "s", "स": "s", "ह": "h",
}
_MR_VOWELS = set("अआइईउऊऋएऐओऔऍऑऎऒािीुूृेैोौॅॉॆॊॢॣ")
_HALANT = "्"
_LABIAL = set("पफबभम")

_LAT_DIGRAPHS = [
    ("chh", "C"), ("ch", "C"), ("sh", "s"), ("kh", "k"), ("gh", "g"), ("jh", "j"),
    ("th", "t"), ("dh", "d"), ("ph", "f"), ("bh", "b"), ("ng", "n"), ("ck", "k"),
    ("qu", "k"), ("x", "ks"), ("z", "j"), ("q", "k"), ("y", ""),
]


def _mr_skeleton_word(w: str) -> str:
    """Consonant skeleton of one Devanagari word."""
    out: list[str] = []
    prev = ""
    n = len(w)
    for i, ch in enumerate(w):
        if ch in _MR_VOWELS or ch in (_HALANT, "ँ", "ः", "\u200c", "\u200d"):
            continue
        if ch == _NUKTA:  # ड़/ढ़ read as a flap r; ज़, फ़, क़ … keep their base sound
            if out and i > 0 and w[i - 1] in "डढ":
                out[-1] = "r"
                prev = "r"
            continue
        if ch == "ह" and i > 1 and w[i - 1] == _HALANT:
            continue  # व्ह, न्ह, म्ह: the conjunct marks aspiration, not an h
        if ch == "ं":  # anusvara: m before a labial ("चेंबूर" = Chembur), else n
            c = "m" if (w[i + 1] if i + 1 < n else "") in _LABIAL else "n"
        elif ch in _MR_CONS:
            c = _MR_CONS[ch]
            if c == "g" and i > 0 and w[i - 1] == "ं":
                continue  # "ंग" is the Latin "ng", which the Latin side reads as n
        elif ch.isdigit():
            c = ch
        else:
            continue
        if c and c != prev:
            out.append(c)
            prev = c
    s = "".join(out)
    if s.endswith("h") and len(s) > 2:  # a word-final h is barely heard
        s = s[:-1]
    return s


def _lat_skeleton_word(w: str) -> str:
    w = w.lower()
    if w.isdigit():
        return w
    # soft c before e/i/y reads as s ("Circle", "Science")
    w = re.sub(r"c(?=[eiy])", "s", w)
    # w before a vowel is the Marathi/Hindi व ("Worli", "Subway"); otherwise a vowel glide ("Chowpatty")
    w = re.sub(r"w(?=[aeiou])", "v", w).replace("w", "")
    # व is heard and written as b as often as v (वांद्रे = Bandra; ASR "सभ्भे" for सबवे): one letter
    w = w.replace("v", "b")
    for a, b in _LAT_DIGRAPHS:
        w = w.replace(a, b)
    w = w.replace("c", "k").replace("C", "c")
    out: list[str] = []
    prev = ""
    for ch in w:
        if ch in "aeiou" or not ch.isalnum():
            continue
        if ch != prev:
            out.append(ch)
            prev = ch
    s = "".join(out)
    if s.endswith("h") and len(s) > 2:
        s = s[:-1]
    return s


# Marathi postpositions written onto the noun (tried with and without); the
# vowel endings of an oblique form ("नाक्या-", "स्थानका-") vanish in the skeleton.
_SUFFIXES = tuple(_mr_compose(x) for x in (
    "मध्ये", "मधून", "जवळच", "जवळ", "बाहेर", "समोर", "पाशी", "पर्यंत", "कडून", "कडे", "वरून",
    "वरती", "वर", "तून", "हून", "मुळे", "च्या", "चा", "ची", "चे", "ला", "ना", "ने", "नी", "त",
))
_GENERIC_FOLDED = {fold_mr(g).lower() for g in GENERIC}


def _is_mr(w: str) -> bool:
    """Devanagari (Marathi or Hindi)."""
    return any("\u0900" <= ch <= "\u097f" for ch in w)


def skeleton(text: str) -> str:
    """Cross-script consonant skeleton of a phrase (words joined by ' ')."""
    parts = []
    for w in _WORD_RE.findall(_mr_compose(text).translate(_MR_DIGITS)):
        sk = _mr_skeleton_word(w) if _is_mr(w) else _lat_skeleton_word(w)
        if sk:
            parts.append(sk)
    return " ".join(parts)


def _words(text: str) -> list[str]:
    return _WORD_RE.findall(_mr_compose(text).translate(_MR_DIGITS))


def _norm_same_script(text: str) -> str:
    return " ".join(fold_mr(w).lower() for w in _words(text))


# --- data --------------------------------------------------------------------


@dataclass
class Place:
    id: str
    name_en: str
    name_mr: str
    lat: float
    lon: float
    kind: str = ""
    source: str = "landmarks"
    names: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PlaceMatch:
    place: Place
    score: float
    matched_text: str
    matched_name: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.place.id,
            "name_en": self.place.name_en,
            "name_mr": self.place.name_mr,
            "lat": self.place.lat,
            "lon": self.place.lon,
            "match_score": round(self.score, 3),
            "matched_text": self.matched_text,
            "source": self.place.source,
        }


@dataclass(frozen=True)
class _Variant:
    place_idx: int
    name: str
    norm: str
    skel: str
    n_words: int
    deva: bool = False


def _short_form(name: str) -> str | None:
    """The name without generic words at its ends ("Sion Circle" → "Sion",
    "Haji Ali pumping station" → "Haji Ali pumping"). Words inside the name
    stay ("बी के सी" is not "बी सी", "Gateway of India" keeps its "of")."""
    words = _words(name)
    while words and words[-1].lower() in GENERIC:
        words = words[:-1]
    while words and words[0].lower() in GENERIC:
        words = words[1:]
    short = " ".join(words)
    return short if short and short != " ".join(_words(name)) else None


def _coords(e: dict[str, Any]) -> tuple[float, float] | None:
    for la, lo in (("lat", "lon"), ("lat", "lng"), ("latitude", "longitude")):
        if la in e and lo in e:
            try:
                return float(e[la]), float(e[lo])
            except (TypeError, ValueError):
                return None
    geom = e.get("geometry") or {}
    if isinstance(geom, dict) and geom.get("type") == "Point":
        c = geom.get("coordinates") or []
        if len(c) >= 2:
            return float(c[1]), float(c[0])
    c = e.get("coordinates") or e.get("centroid") or e.get("center")
    if isinstance(c, (list, tuple)) and len(c) >= 2:
        return float(c[1]), float(c[0])  # GeoJSON order [lon, lat]
    if isinstance(c, dict):
        return _coords(c)
    return None


def _entry_names(e: dict[str, Any]) -> tuple[str, str, list[str]]:
    props = e.get("properties") if isinstance(e.get("properties"), dict) else {}
    src = {**props, **e}
    names = src.get("names") if isinstance(src.get("names"), dict) else {}
    en = src.get("name_en") or src.get("en") or names.get("en") or src.get("name") or ""
    mr = src.get("name_mr") or src.get("mr") or names.get("mr") or ""
    extra: list[str] = []
    for k in ("aliases", "alt_names", "alias", "hi", "name_hi"):
        v = src.get(k)
        if isinstance(v, str):
            extra.append(v)
        elif isinstance(v, list):
            extra += [x for x in v if isinstance(x, str)]
        elif isinstance(v, dict):
            for x in v.values():
                extra += [x] if isinstance(x, str) else [y for y in x if isinstance(y, str)] if isinstance(x, list) else []
    if isinstance(names, dict):
        extra += [v for k, v in names.items() if isinstance(v, str) and k not in ("en", "mr")]
    return str(en), str(mr), extra


def _iter_entries(doc: Any) -> Iterable[dict[str, Any]]:
    if isinstance(doc, list):
        for x in doc:
            if isinstance(x, dict):
                if any(k in x for k in ("id", "name", "en", "name_en", "properties")):
                    yield x
                else:
                    yield from _iter_entries(list(x.values()))
            elif isinstance(x, list):
                yield from _iter_entries(x)
    elif isinstance(doc, dict):
        if doc.get("type") == "FeatureCollection":
            yield from _iter_entries(doc.get("features", []))
            return
        for k, v in doc.items():
            if k in ("schema", "note", "notes", "meta", "source", "sources", "licence", "license"):
                continue
            if isinstance(v, (list, dict)):
                yield from _iter_entries(v if isinstance(v, list) else [v] if "id" in v else list(v.values()))


class Gazetteer:
    """Places plus their name variants, indexed for fuzzy lookup."""

    def __init__(self, places: list[Place], threshold: float = 0.80) -> None:
        self.places = places
        self.threshold = threshold
        self._variants: list[_Variant] = []
        for i, p in enumerate(places):
            seen: set[str] = set()
            for n in [p.name_en, p.name_mr, *p.names]:
                bare = _PAREN_RE.sub("", n).strip() if n else ""
                for form in (n, bare, _short_form(bare) if bare else None):
                    if not form:
                        continue
                    norm = _norm_same_script(form)
                    if not norm or norm in seen:
                        continue
                    seen.add(norm)
                    sk = skeleton(form)
                    if len(sk.replace(" ", "")) < 2:
                        continue
                    self._variants.append(_Variant(i, form, norm, sk, len(_words(form)), _is_mr(form)))
        self.max_words = max((v.n_words for v in self._variants), default=1) + 1

    def __len__(self) -> int:
        return len(self.places)

    def prompt(self, lang: str, max_chars: int = 900) -> str:
        """A vocabulary prompt for a Whisper decoder: the city's place names in
        the language's script, landmarks first, in landmarks.json order, as far
        as ``max_chars`` allows. Whisper spells names it was shown ("Worli
        Naka", not "Walinaka"); the matcher still decides what was said."""
        key = {"en": "en", "hi": "hi", "mr": "mr"}.get(lang, "en")
        head = {"en": "Mumbai traffic report.", "hi": "मुंबई ट्रैफिक रिपोर्ट।",
                "mr": "मुंबई वाहतूक अहवाल."}[key]
        names: list[str] = []
        for p in self.places:
            if key == "en":
                n = p.name_en
            elif key == "mr":
                n = p.name_mr
            else:  # Hindi: the landmark's own hi spelling is the first of its names
                n = next((x for x in p.names if _is_mr(x)), p.name_mr)
            n = _PAREN_RE.sub("", n or "").strip()
            if n and n not in names:
                names.append(n)
        out = head
        for n in names:
            nxt = f"{out} {n}," if out == head else f"{out} {n},"
            if len(nxt) > max_chars:
                break
            out = nxt
        return out.rstrip(",") + ("." if key == "en" else "")

    def by_id(self, pid: str) -> Place | None:
        for p in self.places:
            if p.id == pid:
                return p
        return None

    @staticmethod
    def _windows(words: list[str], max_n: int) -> Iterable[tuple[str, int, bool, int]]:
        """(window, words, exact_only, first word's index). Almost no place name starts with
        "जवळ", "में", "road", "near" …: a window that does would only borrow
        letters from its neighbour, so it may only match a name exactly
        (spelt-out initials such as "के ई एम" for KEM start with one)."""
        for n in range(1, max_n + 1):
            for i in range(0, len(words) - n + 1):
                win = words[i:i + n]
                generic = fold_mr(win[0]).lower() in _GENERIC_FOLDED
                if generic and n == 1:
                    continue
                yield " ".join(win), n, generic, i

    @staticmethod
    def _score(win_norm: str, win_skel: str, v: _Variant) -> float:
        direct = SequenceMatcher(None, win_norm, v.norm).ratio() if win_norm and v.norm else 0.0
        if direct < 1.0 and min(len(win_norm), len(v.norm)) <= 5:
            direct *= 0.9  # one wrong letter in a five-letter word is a different word
        a_parts, b_parts = win_skel.split(), v.skel.split()
        if not a_parts or not b_parts:
            return direct
        if len(a_parts) == len(b_parts):
            # word by word, weighted by the name word's length: "Andheri Subway"
            # must not match "Milan Subway" on the shared "Subway" alone
            num = den = 0.0
            for x, y in zip(a_parts, b_parts):
                r = SequenceMatcher(None, x, y).ratio()
                if min(len(x), len(y)) <= 2 and x != y:
                    r *= 0.6
                num += r * len(y)
                den += len(y)
            sk = num / den
        else:
            # a name split or merged across words ("हाजीअली", "सब वे"): compare
            # the joined skeletons, with a discount for the looser alignment
            sk = SequenceMatcher(None, "".join(a_parts), "".join(b_parts)).ratio() * 0.88
        a, b = "".join(a_parts), "".join(b_parts)
        if min(len(a), len(b)) <= 2:
            # two consonants collide with everyday words ("सुबह" = morning and
            # "शीव" = Sion are both "sb"): a skeleton this short never asserts a
            # place on its own; the same-script comparison still can
            sk = 0.78 if a == b else sk * 0.5
        elif min(len(a), len(b)) <= 3:
            # very short skeletons collide easily: only an exact skeleton
            # counts, and it is capped below a clean same-script match
            sk = 0.86 if a == b else sk * 0.6
        return max(direct, sk)

    def _prefer_whole_name(self, ranked: list[PlaceMatch]) -> list[PlaceMatch]:
        """A name the ASR split in two ("लालबाग चा राजा") can match a shorter
        place exactly on its first part (Lalbaug) and the place that was said
        (Lalbaugcha Raja) only through the looser split-word score. When an
        above-threshold candidate covers more of the same words, those words
        spell its whole name once the split is closed (same consonant
        skeleton), and the top name is the beginning of it, the longer name
        wins. A stray following word does not promote a longer name: it has
        to spell it."""
        if len(ranked) < 2 or ranked[0].score < self.threshold:
            return ranked
        a = ranked[0]

        def joined(t: str) -> str:
            return skeleton(t).replace(" ", "")

        a_sk = joined(a.matched_name)
        for b in ranked[1:]:
            if b.score < self.threshold:
                break
            b_sk = joined(b.matched_name)
            longer = (len(_words(b.matched_text)) > len(_words(a.matched_text))
                      and a.matched_text in b.matched_text)
            if longer and len(a_sk) >= 2 and len(b_sk) > len(a_sk) and b_sk.startswith(a_sk) \
                    and joined(b.matched_text) == b_sk:
                return [b, *[m for m in ranked if m is not b]]
            if longer and b.score >= 0.92 and len(_words(b.matched_name)) >= 3:
                # a long name said with one word misheard ("बांद्रा कुला कॉम्प्लेक्स"
                # for Bandra Kurla Complex) still beats its exact first word
                return [b, *[m for m in ranked if m is not b]]
        return ranked

    @staticmethod
    def _prefer_qualified(ranked: list[PlaceMatch]) -> list[PlaceMatch]:
        """Two places matched equally well and one's full name carries the
        other's as its qualifier ("Western Express Highway (Andheri)" and
        "Andheri"; "Hindmata (Dadar East)" and "Dadar"): the report names the
        qualified, more specific place."""
        if len(ranked) < 2:
            return ranked
        a = ranked[0]
        for b in ranked[1:]:
            if b.score < a.score:
                break
            quals = " ".join(m.group(0) for n in (b.place.name_en, b.place.name_mr, *b.place.names)
                             for m in [_PAREN_RE.search(n or "")] if m)
            sk = skeleton(a.matched_name)
            if quals and sk and f" {sk} " in f" {skeleton(quals)} ":  # whole words only
                return [b, *[m for m in ranked if m is not b]]
        return ranked

    def match(self, text: str, top: int = 3) -> tuple[PlaceMatch | None, list[PlaceMatch]]:
        words = _words(text)
        if not words or not self._variants:
            return None, []
        best: dict[int, PlaceMatch] = {}
        first: dict[int, int] = {}
        windows = []
        for win, n, exact_only, at in self._windows(words, self.max_words):
            # Marathi postpositions (-मध्ये, -जवळ, -वर, -ला …) ride on the
            # last word: try the window with and without them.
            forms = {win}
            last = words and win.split(" ")[-1]
            for suf in _SUFFIXES:
                if last and last.endswith(suf) and len(last) > len(suf) + 2:
                    forms.add(win[: -len(suf)])
            for f in forms:
                windows.append((f, _norm_same_script(f), skeleton(f), n, exact_only, at))
        for v in self._variants:
            for f, wn, ws, n, exact_only, at in windows:
                if abs(n - v.n_words) > 1 or (exact_only and wn != v.norm):
                    continue
                if ws[:1] != v.skel[:1] and wn[:1] != v.norm[:1]:
                    continue
                if v.deva and not _is_mr(f):
                    # Latin words are compared with the Latin names only: every place has
                    # one, and an English word's skeleton can spell a Devanagari name
                    # ("reported" ~ "एअरपोर्ट")
                    continue
                if not v.deva and not _is_mr(f) and wn[:1] != v.norm[:1]:
                    # Latin against Latin: romanisations of one name keep its first
                    # letter; without it the vowel-less skeleton is too loose
                    # ("reported" ~ "Airport" as rprt)
                    s = SequenceMatcher(None, wn, v.norm).ratio()
                else:
                    s = self._score(wn, ws, v)
                cur = best.get(v.place_idx)
                if cur is None or s > cur.score or (s == cur.score and len(v.name) > len(cur.matched_name)):
                    best[v.place_idx] = PlaceMatch(self.places[v.place_idx], s, f, v.name)
                    first[v.place_idx] = at
        # equal scores: the longer stretch of speech, then the place named first
        ranked = sorted(best.values(), key=lambda m: (-m.score, -len(m.matched_text),
                                                      first[self.places.index(m.place)],
                                                      m.place.source != "landmarks"))
        ranked = self._prefer_whole_name(ranked)
        ranked = self._prefer_qualified(ranked)
        cands = [m for m in ranked[:top] if m.score >= 0.5]
        top1 = ranked[0] if ranked and ranked[0].score >= self.threshold else None
        return top1, cands


def _landmarks(path: Path) -> list[Place]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    out = []
    for e in doc.get("landmarks", []):
        names = [e.get("hi", "")] + ALIASES.get(e["id"], [])
        out.append(Place(id=e["id"], name_en=e["en"], name_mr=e.get("mr") or e["en"], lat=float(e["lat"]),
                         lon=float(e["lon"]), kind=e.get("kind", ""), source="landmarks",
                         names=[n for n in names if n]))
    return out


def _gazetteer_entries(path: Path, taken: set[str]) -> list[Place]:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        log.warning("gazetteer unreadable (%s): %s", path, exc)
        return []
    out: list[Place] = []
    for e in _iter_entries(doc):
        pid = str(e.get("id") or (e.get("properties") or {}).get("id") or "")
        if not pid or pid in taken:
            continue
        ll = _coords(e) or _coords(e.get("properties") or {})
        if ll is None:
            continue
        en, mr, extra = _entry_names(e)
        if not (en or mr):
            continue
        taken.add(pid)
        kind = str(e.get("kind") or e.get("type") or (e.get("properties") or {}).get("kind") or "")
        out.append(Place(id=pid, name_en=en or mr, name_mr=mr or en, lat=ll[0], lon=ll[1],
                         kind=kind, source="gazetteer", names=extra + ALIASES.get(pid, [])))
    return out


def load_gazetteer(city_dir: Path, gazetteer_file: str = "gazetteer.json",
                   threshold: float = 0.80) -> Gazetteer:
    city_dir = Path(city_dir)
    places = _landmarks(city_dir / "landmarks.json")
    gz = city_dir / gazetteer_file
    if gz.is_file():
        extra = _gazetteer_entries(gz, {p.id for p in places})
        log.info("gazetteer: %d landmarks + %d gazetteer entries", len(places), len(extra))
        places += extra
    return Gazetteer(places, threshold=threshold)
