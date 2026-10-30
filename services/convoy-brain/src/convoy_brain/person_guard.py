"""Vehicles and places, never people: the operator-chat screen for person identification.

Sajag works with vehicles (number plates, masked until a named officer is on
duty) and places. It never identifies, recognises, tracks or describes a
person, and it holds no face data. The models are asked to respect that, but a
question like "identify the person standing at Dadar TT in camera 3" used to
reach the tools: the strategic tier looked the "person" up, found nothing, and
the answer read "I cannot identify the person" — as if a match would have been
named. :func:`screen_person_question` refuses such a question in code, before
any tool runs, with the reason.

It is deliberately narrow. Crowd and aggregate questions are the product's job
and pass: "how many people are at Dadar TT", "crowd at Wankhede", "is it
safe for pedestrians on Marine Drive", "track the convoy", "identify the
vehicle". Questions about an owner, a driver's name or a phone number are
answered by the existing personal-details fact (Sajag holds none).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

__all__ = ["PersonScreen", "screen_person_question", "REFUSAL_TEXT"]

REFUSAL_TEXT = (
    "Sajag does not identify, recognise, track or describe people — it works with "
    "vehicles (number plates, masked until a named officer is on duty) and places, "
    "and it holds no face data. Ask about a vehicle, a road, a junction or a crowd "
    "at a place instead."
)

# a person (or a face) as the object of an identifying or tracking verb
_PERSON_NOUNS = (
    r"person|persons|people|man|men|woman|women|boy|boys|girl|girls|child|children|kid|kids|"
    r"lady|ladies|gentleman|individual|individuals|pedestrian|pedestrians|passenger|passengers|"
    r"protester|protesters|protestor|protestors|demonstrator|demonstrators|suspect|suspects|"
    r"someone|somebody|face|faces|biker|rider|cyclist|hawker|vendor|beggar|stranger|strangers"
)
_ACT_VERBS = (
    r"identify|identifies|identifying|recogni[sz]e|recogni[sz]es|recogni[sz]ing|unmask|"
    r"profile|profiling|describe|describes|describing|track|tracks|tracking|trace|tracing|"
    r"follow|following|tail|tailing|locate|locating|stalk|stalking|surveil|surveilling"
)
_DETERMINER = r"(?:the|that|this|those|these|a|an|any|every|each|all)\s+"
# up to two adjectives / numbers between the verb and the noun — never a preposition, so
# "describe the situation FOR pedestrians" or "identify the route TO the people" pass
_MODIFIERS = r"(?:(?!(?:for|to|on|at|of|in|near|with|from|by|and|or|around|across)\b)[\w'-]+\s+){0,2}?"

# "identify the man in camera 3", "track the woman in the red saree", "describe the suspect"
_ACT_ON_PERSON_RE = re.compile(
    rf"\b(?:{_ACT_VERBS})\s+(?:{_DETERMINER})?{_MODIFIERS}(?:{_PERSON_NOUNS})\b", re.IGNORECASE)
# "who is the man at …", "who is in camera 3", "who was standing at …", "whose face …",
# "the name of the man …"
_WHO_RE = re.compile(
    rf"\bwho\s+(?:is|was|are|were)\s+(?:{_DETERMINER})?{_MODIFIERS}(?:{_PERSON_NOUNS})\b"
    r"|\bwho\s+(?:is|was|are|were)\s+(?:in|on|at)\s+(?:the\s+|this\s+|that\s+)?"
    r"(?:camera|cctv|photo|image|picture|frame|footage|video|feed|clip)\b"
    r"|\bwho\s+(?:is|was|are|were)\s+(?:standing|walking|sitting|running|riding)\b"
    r"|\bwhose\s+face\b"
    rf"|\bname\s+of\s+(?:{_DETERMINER})?{_MODIFIERS}(?:{_PERSON_NOUNS})\b",
    re.IGNORECASE)
# "facial recognition", "face match", "run a face search"
_FACE_TECH_RE = re.compile(
    r"\b(?:facial|face)[\s-]*(?:recognition|recognise|recognize|match|matching|search|scan|id|"
    r"identification|detection|lookup)\b", re.IGNORECASE)

# Marathi and Hindi: a person word together with an identify / recognise / track / who word
_INDIC_PERSON = ("ব্যক্তি", "লোকটি", "লোকটা", "মহিলা", "ছেলেটি", "মেয়েটি", "চেহারা",
                 "व्यक्ति", "आदमी", "औरत", "महिला", "लड़का", "लड़की", "चेहरा", "चेहरे")
_INDIC_ACT_RE = re.compile(
    r"(?:শনাক্ত|চিনুন|চিনে|ট্র্যাক|অনুসরণ|पहचान|ट्रैक|पीछा)"
    r"|(?:^|[\s,।?!])(?:কে|কারা|कौन)(?=$|[\s,।?!])")


@dataclass(frozen=True)
class PersonScreen:
    refused: bool
    reason: str | None = None
    rule: str | None = None


def screen_person_question(text: str | None) -> PersonScreen:
    """Refuse a question that asks to identify, recognise, track or describe a person."""
    if not text or not text.strip():
        return PersonScreen(False)
    q = " ".join(text.split())
    for rule, rx in (("face-technology", _FACE_TECH_RE), ("act-on-person", _ACT_ON_PERSON_RE),
                     ("who-is-person", _WHO_RE)):
        if rx.search(q):
            return PersonScreen(True, REFUSAL_TEXT, rule)
    if any(p in q for p in _INDIC_PERSON) and _INDIC_ACT_RE.search(q):
        return PersonScreen(True, REFUSAL_TEXT, "person-indic")
    return PersonScreen(False)
