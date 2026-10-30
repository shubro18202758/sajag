"""What kind of road problem is the field report about, and how bad is it?

Rule based and explainable on purpose: an officer sees exactly which words
decided the label (``kind_cues`` / ``severity_cues``). Keywords are Marathi
and Hindi (Devanagari, compared after the same spelling folding the place
matcher uses), English, and common romanised Hindi/Marathi.

Kinds: waterlogging | jam | accident | tree_fall | blockade | procession |
fire | live_wire | other.

A jam is usually a symptom. When a cause (water, a fallen tree, an accident
…) is also reported, the cause names the report and the jam only raises the
severity.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from difflib import SequenceMatcher

from .places import _mr_skeleton_word, _words, fold_mr

__all__ = ["KINDS", "SEVERITIES", "Classification", "classify"]

KINDS = (
    "waterlogging", "jam", "accident", "tree_fall", "blockade", "procession",
    "fire", "live_wire", "other",
)
SEVERITIES = ("low", "medium", "high")

# Tie-break order (most safety-critical first).
_PRIORITY = ("live_wire", "fire", "accident", "tree_fall", "waterlogging", "blockade",
             "procession", "jam")

# (term, weight). Devanagari terms are matched where a word starts (Marathi
# writes its postpositions onto the word, so the end stays open); a term
# ending in "$" must also end the word ("आग$" = fire, never "आगे" = ahead).
# Latin terms are matched on word boundaries.
_TERMS: dict[str, list[tuple[str, int]]] = {
    "waterlogging": [
        # Marathi
        ("पाणी साच", 3), ("पाणी भरल", 3), ("पाणी तुंब", 3), ("पाणी शिरल", 3), ("पाणी जमा", 3),
        ("गुडघाभर", 3), ("गुडघ्याइतके", 3), ("गुडघ्यापर्यंत", 3), ("कमरेइतके", 3), ("कमरेपर्यंत", 3),
        ("कंबरभर", 3), ("घोट्याइतके", 3), ("घोट्यापर्यंत", 3), ("पाण्याखाली", 3), ("जलमय", 3),
        ("पूरस्थिती", 3), ("पूर आला", 3), ("साचल", 2), ("तुंबल", 2), ("पाणी", 1), ("पाण्या", 1),
        # Hindi
        ("पानी भर", 3), ("पानी जमा", 3), ("जलभराव", 3), ("जल भराव", 3), ("घुटनों तक", 3),
        ("घुटने तक", 3), ("कमर तक", 3), ("टखने तक", 3), ("पानी में डूब", 3), ("बाढ़", 2),
        ("पानी", 1),
        # English
        ("waterlogging", 3), ("waterlogged", 3), ("water-logged", 3), ("water logging", 3),
        ("flooded", 3), ("flooding", 3), ("flood", 2), ("knee-deep", 3), ("knee deep", 3),
        ("waist-deep", 3), ("waist deep", 3), ("ankle-deep", 3), ("ankle deep", 3),
        ("inundated", 3), ("submerged", 3), ("standing water", 2), ("deep water", 3), ("water", 1),
        # romanised
        ("paani bhar", 3), ("pani bhar", 3), ("paani jama", 3), ("pani jama", 3),
        ("pani sachle", 3), ("paani sachle", 3), ("pani sachla", 3), ("gudghabhar", 3),
        ("ghutno tak", 3), ("ghutne tak", 3), ("kamar tak", 3), ("pani bharla", 3),
        ("paani bharla", 3), ("pani bharle", 3), ("pani bharli", 3), ("pani tumbla", 3),
        ("paani", 1), ("pani", 1),
    ],
    "jam": [
        ("वाहतूक कोंडी", 3), ("कोंडी", 3), ("ट्रॅफिक जाम", 3), ("ट्रैफिक जाम", 3), ("जाम$", 3),
        ("वाहतूक ठप्प", 3), ("ठप्प", 2), ("सरकत नाहीत", 2), ("सरकत नाही", 2),
        ("गाड्यांच्या रांगा", 3), ("रांगा", 1), ("गाड्या अडकल्या", 2), ("संथ", 1), ("अडकल", 1),
        ("गाड़ियां नहीं चल", 2), ("गाड़ियाँ नहीं चल", 2), ("गाडियां नहीं चल", 2), ("लंबी कतार", 2),
        ("यातायात बाधित", 2), ("फंस", 1),
        ("traffic jam", 3), ("jam", 3), ("jammed", 3), ("gridlock", 3), ("congestion", 3),
        ("congested", 3), ("standstill", 2), ("tailback", 2), ("backed up", 2), ("slow moving", 1),
        ("slow-moving", 1), ("stuck", 1), ("queue", 1), ("kondi", 3), ("gaadi nahi chal", 2),
        ("heavy traffic", 3), ("khup traffic", 3), ("bhari traffic", 3),
    ],
    "accident": [
        ("अपघात", 3), ("धडक", 3), ("उलटल", 3), ("ॲक्सिडेंट", 3), ("अॅक्सिडेंट", 3), ("एक्सिडेंट", 3),
        ("दुर्घटना", 3), ("हादसा", 3), ("टक्कर", 3), ("पलट गई", 3), ("पलट गया", 3), ("एक्सीडेंट", 3),
        ("जखमी", 1), ("घायल", 1),
        ("accident", 3), ("collision", 3), ("collided", 3), ("crash", 3), ("crashed", 3),
        ("overturned", 3), ("pile-up", 3), ("hit by", 2), ("rammed", 2), ("takkar", 3),
        ("apghat", 3),
    ],
    "tree_fall": [
        ("झाड पडल", 3), ("झाड कोसळ", 3), ("झाड उन्मळ", 3), ("उन्मळून पडल", 3), ("फांदी तुटून", 2),
        ("फांदी", 1), ("झाड", 1),
        ("पेड़ गिर", 3), ("पेड़ उखड़", 3), ("डाल टूट", 2), ("पेड़", 1),
        ("tree fell", 3), ("fallen tree", 3), ("tree fallen", 3), ("tree fall", 3), ("tree down", 3),
        ("uprooted", 3), ("tree has fallen", 3), ("branch", 1), ("tree", 1), ("ped gir", 3),
        ("zaad padle", 3), ("zaad padla", 3), ("zad padla", 3), ("jhaad padla", 3), ("ped gira", 3),
    ],
    "blockade": [
        ("रस्ता अडवला", 3), ("बॅरिकेड", 2), ("रस्ता बंद", 2), ("अडथळा", 1),
        ("सड़क बंद", 2), ("रास्ता बंद", 2), ("बैरिकेड", 2), ("नाकाबंदी", 3),
        ("blockade", 3), ("roadblock", 2), ("road block", 2), ("blocked", 2), ("barricade", 2),
        ("barricades", 2), ("barricaded", 2), ("road closed", 2), ("rasta band", 2),
    ],
    "procession": [
        ("मिरवणूक", 3), ("मिरवणुक", 3), ("विसर्जन", 3), ("शोभायात्रा", 3), ("दिंडी", 2), ("पालखी", 2),
        ("गणपती", 1), ("जुलूस", 3), ("शोभा यात्रा", 3), ("यात्रा", 1),
        ("procession", 3), ("rally", 3), ("immersion", 3), ("visarjan", 3), ("parade", 2),
        ("march", 1), ("julus", 3), ("juloos", 3), ("miravnuk", 3),
    ],
    "fire": [
        ("आग$", 3), ("आग लाग", 3), ("आग लग", 3), ("आगीत", 3), ("आगीमुळे", 3), ("आगीचा", 3),
        ("अग्निशमन", 2), ("दमकल", 2), ("धूर", 2), ("धुआं", 2), ("धुआँ", 2), ("जळून", 2), ("जळत", 2),
        ("fire", 3), ("blaze", 3), ("burning", 2), ("smoke", 2), ("aag", 3),
    ],
    "live_wire": [
        ("विजेची तार", 3), ("विजेच्या तार", 3), ("वीज तार", 3), ("तार तुट", 3), ("तुटलेली तार", 3),
        ("उघडी तार", 3), ("विजेचा धक्का", 3), ("विजेचा खांब", 2), ("करंट", 2), ("शॉक", 2),
        ("बिजली का तार", 3), ("बिजली के तार", 3), ("तार टूट", 3), ("टूटा तार", 3), ("नंगा तार", 3),
        ("खुला तार", 3), ("बिजली का खंभा", 2), ("तार", 1),
        ("live wire", 3), ("electric wire", 3), ("power line", 3), ("power cable", 3),
        ("snapped wire", 3), ("electrocuted", 3), ("electrocution", 3), ("lamp post", 2),
        ("wire hanging", 3), ("hanging wire", 3), ("wire", 2),
        ("lamppost", 2), ("bijli ka taar", 3), ("taar toot", 3), ("current", 1),
    ],
}

# Severity cues: (term, level). The highest level found wins; a low cue only
# lowers a default when nothing points higher.
_SEVERITY_CUES: list[tuple[str, str]] = [
    # high
    ("कमरेइतके", "high"), ("कमरेपर्यंत", "high"), ("कंबरभर", "high"), ("छातीइतके", "high"),
    ("गंभीर", "high"), ("जखमी", "high"), ("मृत", "high"), ("पूर्ण बंद", "high"),
    ("पूर्णपणे बंद", "high"), ("रुग्णवाहिका अडकली", "high"), ("गाड्या बुडाल्या", "high"),
    ("कमर तक", "high"), ("सीने तक", "high"), ("घायल", "high"), ("मौत", "high"),
    ("पूरी तरह बंद", "high"), ("एम्बुलेंस फंसी", "high"), ("एंबुलेंस फंसी", "high"),
    ("waist", "high"), ("chest", "high"), ("injured", "high"), ("serious", "high"),
    ("completely blocked", "high"), ("fully blocked", "high"), ("ambulance stuck", "high"),
    ("ambulance is stuck", "high"), ("submerged", "high"),
    # medium
    ("गुडघाभर", "medium"), ("गुडघ्याइतके", "medium"), ("गुडघ्यापर्यंत", "medium"),
    ("बस अडकल", "medium"), ("गाड्या अडकल", "medium"), ("रस्ता बंद", "medium"), ("एक लेन", "medium"),
    ("प्रचंड", "medium"), ("बराच वेळ", "medium"), ("घुटनों तक", "medium"), ("घुटने तक", "medium"),
    ("बसें फंसी", "medium"), ("बस फंसी", "medium"), ("सड़क बंद", "medium"), ("रास्ता बंद", "medium"),
    ("भारी", "medium"), ("heavy", "medium"), ("massive", "medium"), ("huge", "medium"),
    ("knee", "medium"), ("bus stuck", "medium"), ("buses stuck", "medium"), ("buses are stuck", "medium"),
    ("one lane", "medium"), ("blocked", "medium"),
    # low
    ("घोट्याइतके", "low"), ("घोट्यापर्यंत", "low"), ("थोडे", "low"), ("किरकोळ", "low"), ("संथ", "low"),
    ("टखने तक", "low"), ("थोड़ा", "low"), ("मामूली", "low"), ("धीमा", "low"), ("ankle", "low"),
    ("slight", "low"), ("minor", "low"), ("slow", "low"),
]

_BASE = {
    "fire": "high", "live_wire": "high", "accident": "medium", "tree_fall": "medium",
    "waterlogging": "medium", "blockade": "medium", "procession": "low", "jam": "low",
    "other": "low",
}
_FLOOR = {"fire": "high", "live_wire": "high"}  # never reported below this

_LEVEL = {s: i for i, s in enumerate(SEVERITIES)}


def _is_latin(term: str) -> bool:
    return all(ord(c) < 0x0900 for c in term)


def _fold(text: str) -> str:
    return " ".join(fold_mr(text).lower().split())


# the text is folded before matching, so the negation words are folded too
_MR_NEG_WORDS = ("नाहीत", "नाहीये", "नाही", "नव्हते", "नव्हता", "नहीं", "नही")
_MR_NEG = re.compile(r"^\S*\s*(?:\S+\s+)?(?:"
                     + "|".join(re.escape(fold_mr(w)) for w in _MR_NEG_WORDS)
                     + r")(?:$|[\s,।.!?])")
_EN_NEG = re.compile(r"(?:\bno|\bnot|\bwithout|\bzero)\s+(?:\w+\s+)?$")


_DEVA = "\u0900-\u0963\u0966-\u097f"


def _hits(text_folded: str, term: str) -> bool | None:
    """True: present and not negated. False: present but only negated ("पाणी
    साचले नाही", "जाम नहीं है", "no water", "not blocked"). None: absent."""
    whole = term.endswith("$")
    term = term.rstrip("$")
    if _is_latin(term):
        pat = rf"(?<![a-z]){re.escape(term)}(?![a-z])"
    else:
        # a term must start a word (otherwise "धूर" = smoke would fire inside
        # a longer word); Marathi postpositions are suffixes, so the end stays
        # open unless the term asks for a whole word
        pat = rf"(?:^|(?<=[^{_DEVA}])){re.escape(fold_mr(term))}" + (rf"(?![{_DEVA}])" if whole else "")
    seen = False
    for m in re.finditer(pat, text_folded):
        seen = True
        before, after = text_folded[: m.start()], text_folded[m.end():]
        if _EN_NEG.search(before) or _MR_NEG.search(after):
            continue
        return True
    return False if seen else None


_NEG_WORDS = {fold_mr(w) for w in ("नाही", "नाहीत", "नहीं", "नही", "ना", "न")}


def _fuzzy_hit(words: list[str], term: str) -> bool:
    """ASR-tolerant match for a strong Devanagari cue ("वाहतुक कोन्डी",
    "मिरवनूक" for "मिरवणूक"; "विसरजन" for "विसर्जन"): consonant skeletons of
    one- and two-word windows against the term's, same first consonant,
    ratio ≥ 0.85."""
    term = term.rstrip("$")
    target = "".join(_mr_skeleton_word(w) for w in term.split())
    if len(target) < 4:
        return False
    for n in (1, 2):
        for i in range(len(words) - n + 1):
            win = words[i:i + n]
            nxt = words[i + n] if i + n < len(words) else ""
            if fold_mr(nxt) in _NEG_WORDS or any(fold_mr(w) in _NEG_WORDS for w in win[1:]):
                continue  # "… नाही", "… नहीं": negated
            cand = "".join(_mr_skeleton_word(w) for w in win)
            if len(cand) < 4 or cand[0] != target[0]:
                continue
            if cand == target or (len(target) >= 6
                                  and SequenceMatcher(None, cand, target).ratio() >= 0.85):
                return True
    return False


def _cue_skeleton(term: str) -> str:
    return "".join(_mr_skeleton_word(w) for w in term.rstrip("$").split())


def _same_cue(term: str, found: list[str]) -> bool:
    """The Marathi and Hindi spellings of one cue ("बॅरिकेड"/"बैरिकेड") are
    one cue: a term whose skeleton is already among the cues found adds nothing."""
    sk = _cue_skeleton(term)
    return any(_is_latin(f) is False and SequenceMatcher(None, sk, _cue_skeleton(f.replace(" (≈)", ""))).ratio() >= 0.8
               for f in found)


@dataclass(frozen=True)
class Classification:
    kind: str
    kind_cues: tuple[str, ...]
    severity: str
    severity_cues: tuple[str, ...]
    scores: dict[str, int]


def classify(text: str) -> Classification:
    t = _fold(text)
    scores: dict[str, int] = {}
    cues: dict[str, list[str]] = {}
    words = [w for w in _words(text) if any("\u0900" <= c <= "\u097f" for c in w)]
    for kind, terms in _TERMS.items():
        found: list[str] = []
        total = 0
        absent: list[tuple[str, int]] = []
        for term, w in sorted(terms, key=lambda x: -len(x[0])):
            if any(fold_mr(term.rstrip("$")) in fold_mr(f) for f in found):
                continue
            hit = _hits(t, term)
            if hit:
                found.append(term.rstrip("$"))
                total += w
            elif hit is None and w >= 2 and not _is_latin(term):
                absent.append((term, w))
        for term, w in absent:  # only then the close spellings of what was not found as written
            if not _same_cue(term, found) and _fuzzy_hit(words, term):
                found.append(term.rstrip("$") + " (≈)")  # close spelling, shown as such
                total += w - 1
        if total:
            scores[kind] = total
            cues[kind] = found
    jam = scores.get("jam", 0)
    if jam and any(scores.get(k, 0) >= 2 for k in _PRIORITY if k != "jam"):
        scores["jam"] = jam // 2  # a symptom of the reported cause
    if not scores or max(scores.values()) < 2:
        # a single weak word ("पाणी", "tree") is not enough to label the report
        kind = "other"
    else:
        best = max(scores.values())
        kind = next(k for k in _PRIORITY if scores.get(k, 0) == best)

    level = _BASE[kind]
    sev_found: list[str] = []
    top_cue = None
    for term, lv in _SEVERITY_CUES:
        if _hits(t, term):
            sev_found.append(term)
            if top_cue is None or _LEVEL[lv] > _LEVEL[top_cue]:
                top_cue = lv
    if top_cue == "high":
        level = "high"
    elif top_cue == "medium":
        level = SEVERITIES[max(_LEVEL[level], _LEVEL["medium"])]
    elif top_cue == "low" and kind not in _FLOOR:
        level = "low"
    if kind in ("waterlogging", "tree_fall", "accident", "blockade") and "jam" in cues \
            and level == "low":
        level = "medium"  # the cause is already stopping traffic
    if kind in _FLOOR:
        level = SEVERITIES[max(_LEVEL[level], _LEVEL[_FLOOR[kind]])]
    return Classification(
        kind=kind,
        kind_cues=tuple(cues.get(kind, ())),
        severity=level,
        severity_cues=tuple(sev_found),
        scores=dict(scores),
    )
