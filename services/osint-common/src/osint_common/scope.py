"""What an OSINT item may be about: roads, crowds, weather, hazards, closures and services. Nothing else.

Events are about PLACES and ROAD SITUATIONS, never persons, never crime incidents, and nothing political. This
module is the deterministic scope gate every stage shares (no model, no network, no state):

* :func:`screen` reads a signal's (already redacted) title and text and answers one :class:`Screen`:

  - ``reason="crime"`` — a person-crime report (a theft, a robbery, an assault, an arrest, a case, a death that is
    not a road accident): dropped;
  - ``reason="conflict"`` — a clash between groups, a riot, vandalism, bombs, stone-pelting: dropped;
  - ``reason="political"`` — elections, polls, votes, candidates, party workers, political framing: dropped,
    UNLESS the item is a procession, rally or gathering that bears on a road (a road, traffic, a blockade, a
    diversion …): then it is KEPT as a crowd or closure situation, with every political term replaced by
    ``[WITHHELD]`` (``masked`` counts them), so only the place and the road impact remain;
  - ``reason=None`` — in scope (the title and text come back unchanged unless political terms were withheld).

* :func:`screen_class` refuses the classifier classes that are out of scope whatever the wording:
  ``reported_crime`` (crime), ``public_conflict`` (conflict) and ``unrest`` (political: protests, bandhs, strikes,
  gheraos). The other classes (road accidents, fires, flooding, infrastructure failures, hazards, public
  gatherings, processions, road closures, weather) are the scope.

The cue lists are English, Marathi and Hindi words (Mumbai reads its news in all three), plus the Bengali cues of
the Kolkata pack, which stays in the repo as the second city pack. They name kinds of situation only: no person,
and no party or organisation name in clear (generic political words carry the rule, and party names, their short
forms and their election symbols are matched by hash: :data:`PARTY_HASHES`, :data:`SYMBOL_HASHES`). Devanagari and
Bengali cues match as substrings (they inflect by suffix: "निवडणुकीत", "मतदानाच्या"); Latin cues match whole words.
A cue list is a floor, not a guarantee: an unforeseen wording can pass, which is why the classifier's classes are
screened again after classification (:func:`screen_class`) and the oracle re-screens what it stores.

An election symbol is usually an everyday noun, so a symbol word alone never makes an item political: it does when
the item is political anyway (then it is withheld with the party names) or when a word for "symbol" stands within
three words of it ("<symbol> चिन्हावर", "on the <symbol> symbol").

Callers count each reason and log the counts only; the text of a dropped item is never logged or stored.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass

from osint_common.ethics import INDIC_SUFFIXES

__all__ = [
    "OUT_OF_SCOPE_CLASSES",
    "PARTY_HASHES",
    "REASONS",
    "SYMBOL_HASHES",
    "WITHHELD",
    "Screen",
    "screen",
    "screen_class",
]

#: The token that replaces a political term in a kept item (the redactor's own withheld token).
WITHHELD = "[WITHHELD]"

#: The drop reasons, in the order they are tested.
REASONS: tuple[str, ...] = ("crime", "conflict", "political")

#: Classifier classes that are out of scope, with their reason.
OUT_OF_SCOPE_CLASSES: dict[str, str] = {
    "reported_crime": "crime",
    "public_conflict": "conflict",
    "unrest": "political",
}

# ── cue lists ─────────────────────────────────────────────────────────────────────────────────────────────────────

_CRIME_LATIN = (
    r"murder(?:ed|s)?", r"robbery", r"robbed", r"robbers?", r"theft", r"thie(?:f|ves)", r"stolen",
    r"snatch(?:ing|ed|er|ers)?", r"loot(?:ed|ing)?", r"dacoity", r"burglary", r"burglars?", r"rape[ds]?",
    r"molest(?:ed|ation)?", r"assault(?:ed)?", r"stabb(?:ed|ing)", r"shot\s+dead", r"arrest(?:ed|s)?",
    r"abduct(?:ed|ion)?", r"kidnap(?:ped|ping)?", r"extortion", r"fraud", r"scam", r"smuggl(?:ing|ed|ers?)",
    r"drug\s+(?:peddl\w*|racket|seizure|haul)", r"accused", r"chargesheet", r"custody", r"suicide",
    r"dead\s+body", r"lynch(?:ed|ing)?", r"fir\s+(?:lodged|filed|registered)", r"police\s+case",
)
_CRIME_INDIC = (
    # Marathi: murder, dacoity, dacoits, looted, robbery, thieves, theft (two words), gold-chain snatching, rape,
    # molestation, abduction, fraud, extortion, a case registered, accused, suicide, narcotics, drugs, smuggling,
    # dead body, arrested (four constructions, never the bare stem: "अटकाव" is prevention), knife attack, firing,
    # criminal
    "खून", "दरोडा", "दरोडेखोर", "लुटले", "लुटमार", "लूटमार", "चोरटे", "चोरट्यां", "चोरी", "सोनसाखळी", "बलात्कार",
    "विनयभंग", "अपहरण", "फसवणूक", "खंडणी", "गुन्हा दाखल", "गुन्हे दाखल", "आरोपी", "आत्महत्या", "अमली पदार्थ",
    "ड्रग्ज", "तस्करी", "मृतदेह", "अटक केली", "अटक केले", "अटक करण्यात", "अटकेत", "ला अटक", "ना अटक",
    "चाकूहल्ला", "चाकू हल्ला", "गोळीबार", "गुन्हेगार",
    # Hindi: murder, loot, theft, dacoity, rape, molestation, arrest, abduction, cheating, fraud, suicide,
    # smuggling, accused, chain snatching, firing, custody, a case registered
    "हत्या", "लूट", "चोरी", "डकैती", "बलात्कार", "छेड़छाड़", "गिरफ्तार", "अपहरण", "ठगी", "धोखाधड़ी",
    "आत्महत्या", "तस्करी", "आरोपी", "चेन स्नैचिंग", "गोलीबारी", "हिरासत", "मामला दर्ज", "केस दर्ज",
    # Bengali (the Kolkata pack): murder, killing, snatching, dacoity, theft, loot, rape, molestation, arrest (two
    # spellings), abduction, fraud, extortion, a case, accused, suicide, drugs, smuggling, hacked, dead body
    "খুন", "হত্যা", "ছিনতাই", "ডাকাতি", "চুরি", "লুট", "ধর্ষণ", "শ্লীলতাহানি", "গ্রেফতার", "গ্রেপ্তার",
    "অপহরণ", "প্রতারণা", "তোলাবাজি", "মামলা", "অভিযুক্ত", "আত্মহত্যা", "মাদক", "পাচার", "কুপিয়ে", "মৃতদেহ",
)
_CONFLICT_LATIN = (
    r"clash(?:es|ed)?", r"scuffles?", r"brawls?", r"riots?", r"rioting", r"mobs?", r"violence", r"violent",
    r"stone[- ]?pelting", r"pelted\s+stones", r"bomb(?:s|ing|ed|ings)?", r"crude\s+bombs?", r"lathi[- ]?charge[d]?",
    r"tear\s+gas", r"communal", r"vandal(?:ism|ised|ized)", r"ransack(?:ed)?", r"group\s+fight", r"turf\s+war",
)
_CONFLICT_INDIC = (
    # Marathi: a fight, a beating, a ruckus, a riot, stone-pelting, vandalism, a baton charge (two words), tear gas,
    # communal or religious tension, an angry mob, an attack, a bomb ("संघर्ष", a clash and also a collision, is read
    # in context: see _CLASH)
    "हाणामारी", "मारहाण", "राडा", "दंगल", "दगडफेक", "तोडफोड", "लाठीमार", "लाठीचार्ज", "अश्रुधूर", "अश्रुधुरा",
    "जातीय तणाव", "धार्मिक तणाव", "संतप्त जमाव", "हल्ला", "बॉम्ब",
    # Hindi: clash, fight, violence, riot, stone-pelting, bombing, vandalism, baton charge, communal, attack,
    # uproar, arson
    "झड़प", "मारपीट", "हिंसा", "दंगा", "पथराव", "बमबाजी", "तोड़फोड़", "लाठीचार्ज", "सांप्रदायिक", "हमला",
    "बवाल", "आगजनी",
    # Bengali (the Kolkata pack): fight, scuffle, unrest, attack, bomb, stone-pelting, vandalism, baton charge,
    # tear gas, communal, riot
    "মারপিট", "হাতাহাতি", "অশান্তি", "হামলা", "বোমা", "ইটবৃষ্টি", "ভাঙচুর", "লাঠিচার্জ",
    "কাঁদানে গ্যাস", "সাম্প্রদায়িক", "দাঙ্গা",
)
_POLITICAL_LATIN = (
    r"elections?", r"electoral", r"pre-?polls?", r"post-?polls?", r"by-?polls?", r"polls?", r"polling",
    r"votes?", r"voters?", r"voting", r"ballots?", r"evms?", r"candidates?", r"manifesto", r"mlas?",
    r"councillors?", r"corporators?", r"political", r"politics",
    r"party\s+(?:workers?|supporters?|office|flags?|activists?|symbol)", r"(?:ruling|opposition)\s+party",
    r"lok\s+sabha", r"vidhan\s+sabha", r"assembly\s+(?:polls?|elections?|seat)", r"civic\s+polls?",
)
_POLITICAL_INDIC = (
    # Marathi: election (two stems), counting of votes, polling, voter, candidate, candidacy, political, politics,
    # MLA, MP, corporator, manifesto, a campaign meeting (two spellings), party workers (two constructions),
    # opposition party, ruling side, assembly, parliament
    "निवडणूक", "निवडणुक", "मतमोजणी", "मतदान", "मतदार", "उमेदवार", "राजकीय", "राजकारण", "आमदार", "खासदार",
    "नगरसेवक", "जाहीरनामा", "प्रचारसभा", "प्रचार सभा", "पक्ष कार्यकर्त", "पक्षाचे कार्यकर्ते", "विरोधी पक्ष",
    "सत्ताधारी", "विधानसभा", "लोकसभा",
    # Hindi: election, electoral, by-election, polling, voter, vote, candidate (two words), political, politics,
    # MLA, MP, party worker, counting, opposition, ruling, assembly, parliament
    "चुनाव", "चुनावी", "उपचुनाव", "मतदान", "मतदाता", "वोट", "प्रत्याशी", "उम्मीदवार", "राजनीतिक", "राजनीति",
    "विधायक", "सांसद", "पार्टी कार्यकर्ता", "मतगणना", "विपक्ष", "सत्तारूढ़", "विधानसभा", "लोकसभा",
    # Bengali (the Kolkata pack): vote, election, by-election, voter, candidate, political, politics, MLA, MP,
    # councillor, party (adj.), party workers, workers-supporters, manifesto (two spellings)
    "ভোট", "নির্বাচন", "উপনির্বাচন", "ভোটার", "প্রার্থী", "রাজনৈতিক", "রাজনীতি", "বিধায়ক", "সাংসদ", "কাউন্সিলর",
    "দলীয়", "দলের কর্মী", "কর্মী-সমর্থক", "ইস্তাহার", "ইস্তেহার",
)
#: "संघर्ष" (Marathi, Hindi) and "সংঘর্ষ" (Bengali) mean a clash between groups AND a collision of vehicles: each is
#: a conflict cue only when the text names no vehicle and no accident (two trains, a bus and a lorry: a collision,
#: in scope).
_CLASH: tuple[str, ...] = ("संघर्ष", "সংঘর্ষ")
_COLLISION_CONTEXT = re.compile(
    "|".join(
        (
            # Marathi and Hindi: accident (three words), train, railway, local, bus, truck, car (two words), auto,
            # taxi, two-wheeler, tempo, dumper, tanker, collision (two words)
            "अपघात", "दुर्घटना", "हादसा", "ट्रेन", "रेल्वे", "लोकल", "बस", "ट्रक", "गाडी", "गाड्या", "कार", "रिक्षा",
            "टॅक्सी", "टैक्सी", "दुचाकी", "टेम्पो", "डंपर", "टँकर", "धडक", "टक्कर",
            # Bengali (the Kolkata pack)
            "দুর্ঘটনা", "ট্রেন", "বাস", "লরি", "ট্রাক", "গাড়ি", "অটো", "ট্যাক্সি", "বাইক", "ট্রাম", "টোটো", "ডাম্পার",
        )
    )
)
#: The item bears on a road: a road, traffic, a jam, a blockade, a diversion, a closure, a bridge, a crossing.
_ROAD_LATIN = (
    r"roads?", r"traffic", r"jams?", r"congestion", r"block(?:ed|ade|s)?", r"diver(?:ted|sion|sions)",
    r"closed", r"closures?", r"snarls?", r"gridlock", r"routes?", r"bridge", r"flyover", r"crossing",
    r"junction", r"lanes?", r"street", r"avenue", r"sarani", r"bypass", r"highway", r"marg", r"chowk", r"naka",
    r"subway", r"sea\s+link",
)
_ROAD_INDIC = (
    # Marathi: road (three forms), traffic, a jam, a road blockade, closed, diverted, route, bridge, junction, signal,
    # check-post, subway, lane
    "रस्ता", "रस्त्या", "रस्ते", "वाहतूक", "कोंडी", "रास्ता रोको", "बंद", "वळव", "मार्ग", "पूल", "चौक", "सिग्नल",
    "जंक्शन", "नाका", "सबवे", "लेन",
    # Hindi
    "सड़क", "जाम", "यातायात", "ट्रैफिक", "रास्ता", "डायवर्जन", "पुल", "हाईवे", "चौराहा", "फ्लाईओवर",
    # Bengali (the Kolkata pack)
    "রাস্তা", "যানজট", "যান চলাচল", "ট্রাফিক", "অবরোধ", "বন্ধ", "ডাইভারশন", "মোড়", "সেতু", "উড়ালপুল", "সরণি",
)
#: The item is a procession, rally or gathering (what may stay as a crowd or closure situation).
_GATHERING_LATIN = (
    r"rall(?:y|ies)", r"processions?", r"march(?:es)?", r"gatherings?", r"meetings?", r"sabha", r"crowds?",
    r"road\s*show", r"padayatra", r"morcha",
)
_GATHERING_INDIC = (
    # Marathi: procession (two stems), march, meeting, rally (two words), crowd, foot march, road show
    "मिरवणूक", "मिरवणुक", "मोर्चा", "सभा", "मेळावा", "रॅली", "गर्दी", "पदयात्रा", "शोभायात्रा", "रोड शो",
    # Hindi
    "जुलूस", "रैली", "भीड़", "रोड शो",
    # Bengali (the Kolkata pack)
    "মিছিল", "শোভাযাত্রা", "সমাবেশ", "সভা", "জমায়েত", "ভিড়", "পদযাত্রা",
)


#: Party and alliance names and their short forms, as the first 16 hex digits of the sha256 of the lower-cased NFKC
#: name (English, Marathi and Hindi spellings: the national parties, Maharashtra's regional parties and their
#: factions, Mumbai's civic-poll alliances, and the Kolkata pack's West Bengal parties). Sajag never writes a party
#: name, so the names are not in the code: a token (or a two-token phrase), lower-cased and with a Marathi, Hindi or
#: Bengali case ending removed, is hashed and compared. 94 entries.
PARTY_HASHES: frozenset[str] = frozenset(
    {
        "01676093fd97a4f7", "0262b965a00cb7d1", "03bca266fc1eacad", "04659f8c11a191a5", "05bf04e1b9d2031b",
        "0851908b90e2162b", "0cf6c2d4d5bab184", "169a9e4c84668dcd", "1ce13fddac42678d", "1fb3f550bd825c3c",
        "2650b980e2b6d909", "266ca228f9afc55f", "26f976024351c2a4", "27abb1b53f5c1b18", "2aa06032916689ee",
        "362141ab70a4ea18", "37242106bee67850", "3751548b42d84d0e", "37da2aaa62ddb81e", "3a90c4ed4e4526d6",
        "3b03a55dae38bfc9", "3db20e1df89a35ea", "3e56afe2f7d17f99", "44ef4da11a721440", "46b81911abfa2fb6",
        "4a075351aa83f865", "4a911e09cb85cd08", "4fa48ad1ca8fcd94", "4fddbb2dab7dc1da", "582d98acade91596",
        "5b1f46c2866c5bcc", "5cd54627e4a5e56d", "5d2ada361b47f841", "625bbf6071ab7828", "63ac90ca4dea933b",
        "64ad19a352c5c826", "656a9bc1342a0712", "65a4c3f56a6e2107", "67a35bf9148dd38e", "692254f97905f071",
        "6af3c53bbe0d99a6", "6c97aa70dcfb0dec", "6d4bff5a3b571fdf", "6e285c9d3a9680be", "700a9ff3d8e81f05",
        "756034748df9d97d", "76ccd86e21024ff1", "784111fd9defd36d", "7994a6e44c8b9435", "79d1e1d29341cd99",
        "7c9d6ab1cd8753c8", "7eaf04078a700df3", "863afbaa73b98522", "86aaca6eeeb762bd", "8812dc09d23c42a4",
        "8a3133f3b53bc0ce", "8b04431cfc11e73a", "92d0db48d6bd2a6b", "93080e35013dc52a", "964d239474dadebf",
        "99d43dc7d8ccccde", "9a97a5ed5d7edc5b", "a20b7e8771ab206a", "a3123ca6d8809648", "a872dc9fbdc4f7ac",
        "ab60dc36bc685db5", "af420d89e2d0e2a2", "af5f269ddf697cd2", "b762ee284fc2ae29", "b8599092de69de1a",
        "b89c226c1ec0c733", "b97418704ea22e11", "bb1b3cc031d2720e", "bb43fd4e43cb8440", "bca574d78d6318f3",
        "c5bd916598d5e4b6", "c7a5346f8a6b1c63", "c9c61db581934f1d", "ca6e3462ca9f9424", "cbfe0ad179dd2d1c",
        "d57e2be3f83f4fb9", "d5c73ddecbd24395", "d9260c45fb810d64", "da078f2f314fb2b2", "dbbae1b99a4c320e",
        "dbe6023823d9c2e4", "de3a336a24d2b3cf", "dfb66fbf70a9fecf", "e5954d2cad26c638", "e8e6aa88f69f1851",
        "edc59676ecb44c11", "f4e6f4dc80f8552d", "f8a3576739752bfe", "fa8dc1631474db6e",
    }
)
#: Election symbols as words (English, Marathi and Hindi nouns of political coverage), hashed the same way. A symbol
#: is an everyday noun, so it counts only in a political item or beside a word for "symbol" (:data:`_SYMBOL_CONTEXT`,
#: within :data:`_SYMBOL_WINDOW` tokens). 32 entries.
SYMBOL_HASHES: frozenset[str] = frozenset(
    {
        "100a07d1e4368153", "1b001706a418bdfc", "1c800f4b2b5feb19", "1f5fdca5d53e4a66", "21e73870def69f29",
        "289387bd1f112a9e", "36377472bed93f08", "3c7871084652d98c", "3d668cecf389739f", "4addf5be623f059e",
        "5c45ba4f69b9b547", "6013de0381f648b7", "66d56f7d4b2829eb", "6ce4dbdc7aac3b97", "7d31270fa2eb649a",
        "8340489ffa6a1d97", "86bb1da9b0ef3dec", "8b62a857ef4820fb", "8e8c7d42b456c9e4", "8fa5624783e7e903",
        "9dbb57418ad14132", "a05eb64335617d79", "a0e0181bd4f169e5", "b9adeaf0c69a2377", "c7a1a5bba293e94c",
        "ccefcf1dcedb0ed5", "cd08c4c4316df20d", "cdc4f42e6df08395", "d29af8a2e160dd86", "d8198efa3604d164",
        "e9d267954758e652", "ed9f6f25068608ef",
    }
)
#: Words for an election symbol (English, Marathi, Hindi), read as tokens after a case ending is removed.
_SYMBOL_CONTEXT: frozenset[str] = frozenset({"symbol", "symbols", "चिन्ह", "निशाणी", "निशान", "चिह्न"})
_SYMBOL_WINDOW = 3
#: A token: a run of anything but white space and punctuation (Devanagari and Bengali vowel signs stay inside).
_TOKEN = re.compile(r"[^\s.,;:!?'\"“”‘’()\[\]{}|/\\—–-]+")
#: Case endings removed before a token is hashed: Marathi (``osint_common.ethics.INDIC_SUFFIXES``), Hindi oblique,
#: English possessive, and the Kolkata pack's Bengali possessive/plural/objective endings.
_SUFFIXES: tuple[str, ...] = tuple(
    dict.fromkeys(
        (*INDIC_SUFFIXES, "ों", "ने", "का", "की", "के", "'s", "দের", "েরা", "ের", "এর", "কে", "রা", "র")
    )
)


def _digest(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]


def _tokens(text: str) -> list[tuple[int, int, str]]:
    return [(m.start(), m.end(), m.group(0).lower()) for m in _TOKEN.finditer(text)]


def _forms(tok: str) -> set[str]:
    """The token as written and NFKC-normalised (a nukta letter may be one code point or two), each also without a
    case ending."""
    out = {tok, unicodedata.normalize("NFKC", tok)}
    for t in tuple(out):
        for suf in _SUFFIXES:
            if t.endswith(suf) and len(t) > len(suf) + 1:
                out.add(t[: -len(suf)])
    return out


def _hash_spans(toks: list[tuple[int, int, str]], hashes: frozenset[str]) -> list[tuple[int, int, int, int]]:
    """``(start, end, first token, last token)`` of every name in ``hashes`` (single tokens and two-token phrases)."""
    spans: list[tuple[int, int, int, int]] = []
    i = 0
    while i < len(toks):
        s, e, tok = toks[i]
        if i + 1 < len(toks):
            _s2, e2, tok2 = toks[i + 1]
            if any(_digest(f"{tok} {f}") in hashes for f in _forms(tok2)):
                spans.append((s, e2, i, i + 1))
                i += 2
                continue
        if any(_digest(f) in hashes for f in _forms(tok)):
            spans.append((s, e, i, i))
        i += 1
    return spans


def _party_spans(text: str) -> list[tuple[int, int]]:
    """The spans of party names in ``text`` (single tokens and two-token phrases)."""
    return [(s, e) for s, e, _a, _b in _hash_spans(_tokens(text), PARTY_HASHES)]


def _symbol_spans(text: str) -> tuple[list[tuple[int, int]], bool]:
    """The spans of election-symbol words in ``text``, and whether one stands beside a word for "symbol"."""
    toks = _tokens(text)
    spans = _hash_spans(toks, SYMBOL_HASHES)
    ctx = [i for i, (_s, _e, tok) in enumerate(toks) if _forms(tok) & _SYMBOL_CONTEXT]
    near = any(a - _SYMBOL_WINDOW <= c <= b + _SYMBOL_WINDOW for _s, _e, a, b in spans for c in ctx)
    return [(s, e) for s, e, _a, _b in spans], near


def _latin(words: tuple[str, ...]) -> re.Pattern[str]:
    return re.compile(r"(?<![\w-])(?:" + "|".join(words) + r")(?![\w-])", re.IGNORECASE)


def _indic(words: tuple[str, ...]) -> re.Pattern[str]:
    return re.compile("|".join(re.escape(w) for w in sorted(words, key=len, reverse=True)))


_CRIME = (_latin(_CRIME_LATIN), _indic(_CRIME_INDIC))
_CONFLICT = (_latin(_CONFLICT_LATIN), _indic(_CONFLICT_INDIC))
_POLITICAL = (_latin(_POLITICAL_LATIN), _indic(_POLITICAL_INDIC))
_ROAD = (_latin(_ROAD_LATIN), _indic(_ROAD_INDIC))
_GATHERING = (_latin(_GATHERING_LATIN), _indic(_GATHERING_INDIC))


def _hit(pats: tuple[re.Pattern[str], re.Pattern[str]], text: str) -> bool:
    return any(p.search(text) for p in pats)


def _political(text: str) -> bool:
    return _hit(_POLITICAL, text) or bool(_party_spans(text)) or _symbol_spans(text)[1]


def _mask(pats: tuple[re.Pattern[str], re.Pattern[str]], text: str) -> tuple[str, int]:
    spans = sorted({*_party_spans(text), *_symbol_spans(text)[0]})
    merged: list[tuple[int, int]] = []
    for s, e in spans:  # a symbol inside a two-token party phrase is one span
        if merged and s < merged[-1][1]:
            merged[-1] = (merged[-1][0], max(e, merged[-1][1]))
        else:
            merged.append((s, e))
    n = len(merged)
    for s, e in reversed(merged):
        text = text[:s] + WITHHELD + text[e:]
    for p in pats:
        text, k = p.subn(WITHHELD, text)
        n += k
    if n:
        # "[WITHHELD]-[WITHHELD]" / "[WITHHELD] [WITHHELD]" read as one withheld span
        text = re.sub(r"\[WITHHELD\](?:[\s-]*\[WITHHELD\])+", WITHHELD, text)
    return text, n


@dataclass(frozen=True)
class Screen:
    """One item's scope verdict. ``reason`` None: in scope; ``title``/``text`` are what may be kept."""

    reason: str | None
    title: str
    text: str
    #: political terms withheld from a kept item
    masked: int = 0


def screen(title: str | None, text: str | None = None) -> Screen:
    """The scope verdict for one item's title and text (see the module docstring). Pure."""
    t, x = title or "", text or ""
    both = f"{t}\n{x}"
    if _hit(_CRIME, both):
        return Screen("crime", t, x)
    if _hit(_CONFLICT, both) or (any(w in both for w in _CLASH) and not _COLLISION_CONTEXT.search(both)):
        return Screen("conflict", t, x)
    if _political(both):
        if not (_hit(_ROAD, both) and _hit(_GATHERING, both)):
            return Screen("political", t, x)
        t2, n1 = _mask(_POLITICAL, t)
        x2, n2 = _mask(_POLITICAL, x)
        return Screen(None, t2, x2, n1 + n2)
    return Screen(None, t, x)


def screen_class(event_class: str | None) -> str | None:
    """The drop reason of an out-of-scope classifier class, else None."""
    return OUT_OF_SCOPE_CLASSES.get(event_class or "")
