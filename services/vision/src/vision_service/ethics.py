"""Road and vehicles only: the person filter and the query screen.

Two guards sit around the model, both in code, so they hold whatever the
model does:

1. :func:`screen_query` refuses a person-centric or plate-reading question
   *before* the model is called ("who is in this image", "how old is the
   man", "read the number plate"). Plates are read only by the existing
   ANPR path, masked; faces and persons are never analysed.
2. :func:`scrub` removes from the model's free text every sentence that
   refers to a person at all — appearance, identity, gender, age, clothing,
   faces, ethnicity, religion, or simply "a man", "pedestrians", "a crowd".
   What remains describes the road and the vehicles. If nothing remains,
   a neutral sentence built from the road state replaces it.

The system prompt asks the model for the same thing; these functions make
sure a model that ignores the prompt still cannot put a person description
on an officer's screen.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

__all__ = [
    "PERSON_TERMS",
    "ScreenResult",
    "screen_query",
    "mentions_person",
    "scrub",
    "neutral_rationale",
]

# English words that refer to people, their bodies or their attributes.
PERSON_TERMS: tuple[str, ...] = (
    # people in general
    "person", "persons", "people", "peoples", "human", "humans", "individual", "individuals",
    "someone", "somebody", "anyone", "anybody", "everyone", "pedestrian", "pedestrians",
    "passerby", "passersby", "passer-by", "passers-by", "crowd", "crowds", "onlooker",
    "onlookers", "bystander", "bystanders", "figure", "figures", "silhouette", "silhouettes",
    "commuter", "commuters", "passenger", "passengers", "resident", "residents", "worker",
    "workers", "vendor", "vendors", "hawker", "hawkers", "rider", "riders", "cyclist",
    "cyclists", "driver", "drivers", "puller", "pullers", "volunteer", "volunteers",
    "policeman", "policemen", "policewoman", "constable", "constables", "officer", "officers",
    "marshal", "marshals", "staff", "student", "students", "tourist", "tourists",
    # gender and age
    "man", "men", "woman", "women", "male", "males", "female", "females", "boy", "boys",
    "girl", "girls", "gentleman", "gentlemen", "lady", "ladies", "child", "children", "kid",
    "kids", "baby", "babies", "toddler", "teen", "teens", "teenager", "teenagers", "adult",
    "adults", "elderly", "aged", "gender", "age", "ages", "old-aged", "youth", "youths",
    "he", "she", "him", "her", "his", "hers", "himself", "herself",
    # bodies, faces, identity
    "face", "faces", "facial", "head", "heads", "hair", "beard", "bald", "skin",
    "complexion", "body", "bodies", "identity", "identify", "identified", "recognise",
    "recognize", "name", "named",
    # clothing
    "wearing", "wears", "worn", "dressed", "dress", "clothes", "clothing", "outfit", "shirt",
    "shirts", "t-shirt", "trousers", "pants", "shorts", "jeans", "saree", "sarees", "sari",
    "saris", "kurta", "dhoti", "lungi", "burqa", "hijab", "turban", "cap", "hat", "helmet",
    "helmets", "jacket", "vest", "vests", "uniform", "uniforms", "umbrella", "umbrellas",
    # ethnicity, religion, caste
    "ethnic", "ethnicity", "race", "racial", "caste", "religion", "religious", "hindu",
    "muslim", "sikh", "christian", "jain", "buddhist",
)

# Hindi (and, for the Kolkata pack, Bengali) equivalents for screening questions;
# matched anywhere in the question.
_PERSON_TERMS_INDIC: tuple[str, ...] = (
    "মানুষ", "লোক", "লোকজন", "মহিলা", "পুরুষ", "ছেলে", "মেয়ে", "শিশু",
    "বাচ্চা", "মুখ", "চেহারা", "পোশাক", "জামা", "বয়স", "পথচারী", "ভিড়",
    "कौन", "आदमी", "औरत", "महिला", "पुरुष", "लड़का", "लड़की", "बच्चा", "चेहरा", "कपड़े",
    "उम्र", "लोग", "व्यक्ति", "भीड़",
)
# Marathi person words. Marathi adds case endings to the stem ("माणसांचे", "गर्दीत"),
# so these match at the START of a word; a stem that also begins an everyday road word
# ("लोक" / "लोकल" train, "मूल" / "मूलभूत") is listed only as whole words below.
_PERSON_STEMS_MR: tuple[str, ...] = (
    "माणूस", "माणस", "व्यक्ती", "स्त्री", "स्त्रिया", "बाई", "बायका", "पुरुष", "मुलगा", "मुलगी",
    "मुलगे", "मुली", "मुलां", "चेहर", "कपड", "पादचार", "पादचाऱ", "गर्दी", "प्रवासी", "प्रवाश",
)
_PERSON_WORDS_MR: tuple[str, ...] = (
    "लोक", "लोकं", "लोकांना", "लोकांचे", "लोकांची", "लोकांचा", "मूल", "मुले", "मुलं", "वय", "वयाचा",
    "वयाची", "वयाचे",
)
_PLATE_TERMS: tuple[str, ...] = (
    "plate", "plates", "number plate", "licence plate", "license plate", "registration",
    "reg number", "vehicle number", "নম্বর প্লেট", "গাড়ির নম্বর", "नंबर प्लेट", "गाड़ी नंबर",
    "गाडीचा नंबर", "गाडी नंबर", "गाडीचा क्रमांक", "वाहन क्रमांक", "नोंदणी क्रमांक",
)
# "who" words are whole words (Bengali "কে" is also a case ending). Marathi: कोण / कोणी /
# कोणाचा… ("who", "whose"); not कोणता/कोणते ("which road?" is a road question).
_INDIC_WHO_RE = re.compile(r"(?:^|[\s,।?!])(কে|কারা|কার|कौन|किसका|किसकी|कोण|कोणी|कोणाचा|कोणाची"
                           r"|कोणाचे|कोणाला)(?=$|[\s,।?!])")
_WB = r"(?:^|[\s,।?!.\"'(])"  # a word start in Devanagari text (\b does not work for matras)
_MR_PERSON_RE = re.compile(
    _WB + r"(?:(?:" + "|".join(_PERSON_STEMS_MR) + r")\S*|(?:" + "|".join(_PERSON_WORDS_MR)
    + r")(?=$|[\s,।?!.\"')]))"
)
_WHO_RE = re.compile(r"\b(who|whom|whose|how old|what age|which gender|identify|recogni[sz]e)\b",
                     re.I)

_PERSON_RE = re.compile(
    r"(?<![a-z])(" + "|".join(sorted((re.escape(t) for t in PERSON_TERMS), key=len, reverse=True))
    + r")(?![a-z])",
    re.I,
)


def mentions_person(text: str) -> bool:
    return _PERSON_RE.search(text or "") is not None


@dataclass(frozen=True)
class ScreenResult:
    allowed: bool
    reason: str | None = None
    policy: str | None = None


def screen_query(question: str | None) -> ScreenResult:
    """Refuse questions about persons, faces or plates; allow road questions."""
    if not question or not question.strip():
        return ScreenResult(True)
    q = " ".join(question.split())
    ql = q.lower()
    if any(t in ql for t in _PLATE_TERMS):
        return ScreenResult(False, "Number plates are not read by this service. Plates go only "
                                   "through the ANPR path, masked until a named officer is on duty.",
                            "no-plate-reading")
    if (_WHO_RE.search(ql) or mentions_person(ql) or _INDIC_WHO_RE.search(q)
            or any(t in q for t in _PERSON_TERMS_INDIC) or _MR_PERSON_RE.search(q)):
        return ScreenResult(False, "This service describes road and vehicle conditions only. "
                                   "It does not describe, count or identify people.",
                            "vehicles-and-roads-only")
    return ScreenResult(True)


_SENTENCE_SPLIT = re.compile(r"(?<=[.;!?])\s+|\s+[—–]\s+")


def neutral_rationale(state: str) -> str:
    return {
        "waterlogged": "Standing water covers the carriageway.",
        "blocked": "The carriageway is obstructed.",
        "tree_fall": "A fallen tree or branches lie on the road.",
        "stalled_vehicle": "A vehicle is stopped in the carriageway.",
        "crash_debris": "Debris from a collision lies on the road.",
        "congested": "Vehicles are queued and moving slowly.",
        "clear": "The carriageway is open and traffic is light.",
    }.get(state, "Road state could not be determined from this image.")


def scrub(text: str, state: str, max_words: int = 25) -> tuple[str, int]:
    """Drop every sentence that mentions a person; cap at ``max_words``.

    Whole sentences go, not just the offending words: a sentence about a
    person stays about that person after word deletion ("… likely performing
    cleanup duties"), and half-sentences read as garbage on an officer's
    screen. If nothing is left, a neutral sentence for the road state
    replaces the text.

    Returns (clean text, number of sentences removed).
    """
    text = " ".join((text or "").split())
    kept: list[str] = []
    removed = 0
    for sent in (x.strip() for x in _SENTENCE_SPLIT.split(text)):
        if not sent:
            continue
        if mentions_person(sent):
            removed += 1
            continue
        sent = sent[:1].upper() + sent[1:]
        kept.append(sent if sent[-1] in ".!?" else sent.rstrip(";,") + ".")
    # keep whole sentences within the word budget; cut only a lone first one
    budget: list[str] = []
    for sent in kept:
        if len(" ".join(budget + [sent]).split()) <= max_words:
            budget.append(sent)
        else:
            if not budget:
                budget.append(" ".join(sent.split()[:max_words]).rstrip(",;.") + ".")
            break
    out = " ".join(budget)
    if not out or mentions_person(out):
        out = neutral_rationale(state)
    return out, removed
