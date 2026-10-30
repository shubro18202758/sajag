"""Parse-time person redaction (OSINT SPEC §0.1(b), §4 "free text"): names → ``[PERSON]``, ages → ``[AGE]``.

Every connector runs its titles and texts through here BEFORE a :class:`~osint_common.types.RawOsintSignal` is
built, so nothing downstream (the oracle, the deck, a log) ever holds the name. The rules, in order:

1. **Ages and cue- or honorific-introduced names** (every tier): every span of
   :func:`osint_common.ethics.pii_spans` (the PoC's age patterns and ``_NAME_CUE_RE``, plus initials, "ASI",
   parenthesised ages, "[PERSON], 45,", zero-width or fullwidth disguises), place-aware through the gazetteer
   protect-set. Replacing every span is what makes ``ethics.find_pii(result) == []`` hold by construction. This
   module then redacts past where those spans stop:

   * a cue span runs on over up to two more name words: a fourth one ("Mr <A> <B> <C> <D>"), an initialled one
     ("Inspector <Given> D. <Surname>") or a hyphenated one ("<Surname>-<Surname>"). It stops at an ordinary,
     generic, headline (:data:`HEADLINE_WORDS`) or gazetteer word;
   * cue forms the shared pattern does not read: a comma after a role cue ("the victim, <Name>,"), "<role> as
     <Name>" ("identified the deceased as <Name>"), an honorific with no space ("Mr.<Name>", read exactly as
     "Mr. <Name>" is), and a Title-Case role cue before two or more name words ("Accused <Given> <Surname> Held");
   * the name right before an age ("<Given> <Surname>, [AGE]," / "<Given> <Surname> ([AGE])" / "..., aged 45"):
     the capitalised run up to the age, without its leading context words ("Behala Resident", "Elderly Woman";
     :data:`AGE_CONTEXT_WORDS`), so an occupational surname at its end stays inside the name;
   * two more age forms: "45 years of age" and "aged about 45", and Indic ones: Marathi ("३५ वर्षीय",
     "४२ वर्षांचा", "वय ६०", "<name> (६०)", "<name>, ४५,"; Devanagari or Western digits), Hindi ("28 वर्षीय",
     "45 साल के", "उम्र 60") and the second city pack's Bengali forms;
   * **cue-less names** (F-HONEST OSINT-2; :func:`_cueless_spans`): a role, kin or occupation noun before a name
     ("Biker <Given> <Surname> dies", "husband <Given> <Surname>", "Daughter of <Given> <Surname>"), a given name or
     initials before a common surname (:data:`SURNAMES`: Maharashtrian, Gujarati, East Indian and Goan, North
     Indian; a surname alone stays: "Patil family"), a name with an honorific suffix ("<Given>rao", "<Given>bhau",
     "<Given>-ji", "<Given>bhai") or an address term written apart ("<Name> saheb", "<Name> tai", "<Name> ji"), a
     Mumbai Police rank or Marathi honorific ("PSI <Name>", "Sau. <Name>"), both sides of "alias"/"urf"/"@",
     "<Given>, a <role>," and "<Name>'s body/family". No name word is a place, common, generic, headline or
     organisation word, so gazetteer and city-pack phrases ("Senapati Bapat Marg", "Bhulabhai Desai Road") and
     Title-Case headlines ("Five More Trains Cancelled") survive;
   * Marathi and Hindi cues in Devanagari (:func:`_indic_cue_spans`): the words after an honorific (श्री, श्रीमती,
     सौ., कु., डॉ., प्रा., ॲड.; Hindi सुश्री) are a name even when they are also ordinary words, unless a place noun
     follows them ("डॉ. आंबेडकर मार्ग" is a road); the unknown words after a role cue (आरोपी, मृताचे नाव, जखमी,
     रहिवासी, रिक्षाचालक; मृतक, पीड़ित) are a name; a word before an address term (साहेब, भाऊ, ताई, दादा, जी, शेठ)
     or with one written onto it ("शंकरराव", "<name>जी", "<name>बाई") is a name, unless it is an ordinary word or a
     place ("तिचा भाऊ", her brother). The second city pack's Bengali cues stay. These become ``[PERSON]``.
2. **Names learned in the same document** (every tier, :class:`DocumentRedactor`): a multi-word name that a cue
   introduced anywhere in one feed document ("content creator <Given> <Surname>") is also redacted where that
   document repeats it without the cue, and so is its surname written alone and capitalised ("<Surname> taught
   there"), unless that word is an ordinary, generic or gazetteer word. The names live in memory for one
   ``parse()`` and are never stored or logged. (This replaces the PoC's hard-coded ``_NAME_DENYLIST``, which named
   a real person and is not ported.)
3. **Reddit users** (every tier, ``official`` included): a Reddit user mention (``u/<name>``, ``/u/<name>``,
   ``/user/<name>``, ``r/u_<name>``) and a Reddit user page (``reddit.com/u/<name>``, ``/user/<name>``,
   ``/r/u_<name>``, any reddit.com host; the whole URL when one holds it) → ``[PERSON]``, wherever they appear: a
   news headline quoting "Reddit user u/<name>" names a poster as surely as a post does. These are exactly the
   forms :func:`has_poster_handle` reads in every tier, so no emitted title or text keeps one.
4. **URLs** (every tier but ``official``): a news or social URL can carry a person in its path (a slug made from
   an unredacted headline, a profile link) and is never stored (the orchestrator's URL decision), so every URL in
   a title or text is replaced. A Reddit user page becomes ``[PERSON]`` (rule 3); any other ``http(s)://…``,
   ``www.…`` or ``<host>.<tld>/<path>`` becomes ``[URL]`` (not "[LINK]": the analysis pipeline strips Reddit's
   "[link]" boilerplate case-blind). Official sources keep theirs (identifier-only paths), except a Reddit user
   page.
5. **Social tier only** (``social_unverified``, the most aggressively redacted tier):

   * a poster handle in the text beyond rule 3 (``@<name>``, and a handle named after a platform cue: "insta:
     <handle>", "IG id - <handle>") → ``[PERSON]``; an e-mail address or a mobile number → ``[CONTACT]``;
   * a poster's age and sex shorthand ("F(28)", "22M", "27/F", "(24F)") → ``[AGE]`` (F-HONEST OSINT-6), and a single
     given name after a social cue ("my neighbour <Given>", "contact <Given>") or before an address term
     ("<Given> bhai");
   * capitalised name runs (two or more name tokens, a token being an ``Xxx`` word or an initial such as "K.", so
     "<Given> K. <Surname>" and "R. K. <Surname>" are runs, and so are "<Given>-<Surname>" and "<Given> de
     <Surname>"; the PoC's bigram rule widened to whole runs so a third name word cannot survive) → ``[PERSON]``,
     unless the words are a place or ordinary words: a word is kept when
     a multi-word gazetteer phrase covers it **in the text** (so "Senapati Bapat Marg" survives while "Senapati
     Mitra" alone does not), or when it is itself a generic place, civic or common English word (``road``,
     ``club``, ``school``, ``near``, ...); a lone unkept word that is a gazetteer place alias ("Visit Matunga")
     is kept too, and initials next to kept words only stay ("B. T. Road"). A place noun never vouches for the
     words before it: "<Given> <Surname> Road" becomes "[PERSON] Road" unless the gazetteer knows the whole
     phrase, and a place noun that is not a generic word (``nagar``, ``park``, ``society``, ...; "Nagar" is also a
     surname) is redacted with the name.

6. **Indic script** (every tier; :func:`osint_common.ethics.unredactable_spans`): a Marathi or Devanagari word that
   is neither a gazetteer place (with a case ending or not) nor an ordinary word
   (``ethics.INDIC_COMMON_WORDS``) → ``[WITHHELD]``, consecutive words as one token. No Indic NER runs here, so an
   unknown word may be a name and is never guessed harmless.
7. **Model spans** (optional, OFF by default; :mod:`._model_pii`): with ``OSINT_PII_MODEL=1`` the PII-Tracer
   spans of the embedding service are merged into the first pass (``extra``): names → ``[PERSON]``, contacts
   outside the ``official`` tier → ``[CONTACT]``, never over a protected place. They only add to the rules above;
   when the service is down the rules run alone.

``n_redactions`` (a signal's ``pii_redactions``) counts every replacement: ``[PERSON]``, ``[AGE]``, ``[CONTACT]``,
``[URL]`` and ``[WITHHELD]``. No NER runs here (production swaps in IndicNER/spaCy): a Latin-script name with no
cue, no listed surname and no role noun, a single given name after an unlisted verb, an ALL-CAPS headline or a name
with non-ASCII Latin letters can survive. ``ethics.find_pii`` cannot tell (it reads the same patterns); the honest
measure is the held-out recall of ``tests/test_heldout_recall.py``. That limit is reported, never hidden.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from functools import lru_cache

from osint_common import ethics
from osint_ingress.connectors._protect import city_indic_places, norm_phrase

__all__ = [
    "AGE_CONTEXT_WORDS",
    "AT_HANDLE_RE",
    "COMMON_WORDS",
    "HANDLE_RE",
    "HEADLINE_WORDS",
    "PLATFORM_HANDLE_RE",
    "PROFILE_URL_RE",
    "REDDIT_USER_URL_RE",
    "SURNAMES",
    "TOKEN_AGE",
    "TOKEN_CONTACT",
    "TOKEN_PERSON",
    "TOKEN_URL",
    "TOKEN_WITHHELD",
    "TOKENS",
    "URL_RE",
    "DocumentRedactor",
    "Span",
    "has_poster_handle",
    "has_url",
    "redact_persons",
    "redaction_spans",
]

TOKEN_PERSON = "[PERSON]"
TOKEN_AGE = "[AGE]"
TOKEN_CONTACT = "[CONTACT]"
TOKEN_URL = "[URL]"
#: Indic-script words the redactor cannot read for names (no Indic NER yet): withheld, never guessed harmless.
TOKEN_WITHHELD = "[WITHHELD]"
_TOKENS = {
    "name": TOKEN_PERSON, "age": TOKEN_AGE, "contact": TOKEN_CONTACT, "url": TOKEN_URL, "script": TOKEN_WITHHELD,
}
#: Every token this module writes (``pii_redactions`` counts them).
TOKENS: tuple[str, ...] = tuple(_TOKENS.values())
_SOCIAL = "social_unverified"
_OFFICIAL = "official"
_MAX_PASSES = 4

#: Ordinary English words that are never a person's name on their own (sentence-case Reddit titles capitalise
#: them). Words that double as common given names (Will, Mark, Rose, Grace, Joy, Sunny, ...) are left out on
#: purpose: when in doubt, the word is redacted.
COMMON_WORDS: frozenset[str] = frozenset(
    """
    about above after again against all almost also always among and another any anybody anyone anything anywhere
    are around ask asked asking available away back bad bank based because been before being below best better
    between big both bring but buy buying can cannot cant care cheap check city clean close closed come coming
    could cut daily day days dear does doing done down during each early easy either else even evening ever every
    everyone everything excellent experience experiences fast few find finding fine first food for found free
    fresh from full fun get gets getting give given going gone good got great had happening hard has have having
    heavy help here high home hot how however huge important into issue issues its just keep kind know known last
    late later latest least less let lets life like little live living local long look looking lost lot lots love
    made main make makes making many may maybe meet more morning most much must near nearby need needed needs
    never new news next nice night none not nothing now offline old once one online only open opinion opinions
    other others our out over own part people perfect place places plan plans please plus post posts price
    problem problems public quick quiet quite rain rains rainy rather real really recommend recommendation
    recommendations regarding request review reviews right safe same say see seeking seen sell selling serious
    service services several shop shopping should show since small some someone something soon sorry spot spots
    start still stop such suggest suggestion suggestions support sure take taking than thank thanks that the their
    them then there these they thing things think this those though thread through time tips today together
    tomorrow tonight too top total traffic trip trying two under until update updates upon urgent used useful
    very visit visiting wanted wants water way week weekend weekly well went were what when where whether which
    while who whole why with within without work working worst would year years yes yesterday yet your
    chat discussion question questions query queries meetup event events group groups community festival fest
    concert game games match movie movies show shows sale deal deals job jobs rent room rooms flat flats house
    cafe cafes restaurant restaurants weather power outage signal jam social media
    monday tuesday wednesday thursday friday saturday sunday january february march april june july august
    september october november december
    no three four five six seven eight nine ten eleven twelve dozen dozens hundreds thousands lakh lakhs crore
    """.split()
)

#: Words a news headline puts right after a name ("... Held", "... Dies", "... Says"): never a name word, so a
#: name span never runs on over one. Only verbs and prepositions: no noun that is also a surname (occupational
#: surnames include Engineer, Contractor, Doctor, Merchant and Captain).
HEADLINE_WORDS: frozenset[str] = frozenset(
    """
    held nabbed detained caught killed kills dies died dead death hurt rescued missing drowns drowned electrocuted
    stabbed murdered attacked assaulted robbed looted duped cheated thrashed slapped hit rammed mowed crushed says
    said tells told visits visited inaugurates inaugurated opens opened launches launched meets met urges slams
    warns announces announced orders ordered directs seeks demands alleges claims denies appears surrenders escapes
    flees absconds absconding jailed sentenced convicted acquitted released granted bail remanded charged sworn
    appointed elected resigns quits joins wins loses honoured felicitated awarded gets takes suspended dismissed
    transferred questioned summoned raided seized recovered lodged registers registered hospitalised hospitalized
    admitted discharged critical stable succumbs succumbed amid outside inside behind along across via till
    """.split()
)

#: Context nouns a report puts before an age ("Elderly Woman, 80,", "Behala Resident, 45,"): stripped from the
#: FRONT of the run before an age, never from its end, so "<Given> <occupational surname>, 45," stays one name.
AGE_CONTEXT_WORDS: frozenset[str] = frozenset(
    """
    resident residents youth youths teen teenager boy boys girl girls child children kid kids baby infant toddler
    minor student students elderly senior citizen citizens wife husband mother father daughter brother sister
    grandmother grandfather neighbour neighbor couple rider biker motorist cyclist pedestrian passenger commuter
    worker workers guard watchman vendor hawker shopkeeper trader businessman businesswoman techie employee cop
    policeman patient devotee pilgrim tourist victim accused deceased complainant suspect person
    """.split()
)

_CAP = r"[A-Z][a-z]{2,}"
_INIT = r"(?:[A-Z]\.\s?)"
#: One to four capitalised name words, each optionally after up to three initials.
_NAME = rf"{_INIT}{{0,3}}{_CAP}(?:\s+{_INIT}{{0,3}}{_CAP}){{0,3}}"
_WORD_RE = re.compile(r"[A-Za-z0-9]+")
#: A name token: a capitalised word (group ``word``) or an initial such as "K." (group ``init``).
_NAME_TOKEN_RE = re.compile(rf"(?<![A-Za-z])(?:(?P<word>{_CAP})(?![A-Za-z])|(?P<init>[A-Z])\.)")
#: The next name word right after a name span: a space and an (optionally initialled) capitalised word, or a
#: hyphen and one. A sentence end, a comma or a " - " separator stops it.
_NEXT_NAME_WORD_RE = re.compile(rf"(?:\s+{_INIT}{{0,3}}|-)(?P<w>{_CAP})(?![A-Za-z])")
_MAX_EXTRA_WORDS = 2

_ROLES = r"victims?|deceased|accused|complainants?|injured|drivers?|riders?|pedestrians?|suspects?"
#: "the victim, <Name>," (a comma between a role cue and the name; the cue in any case).
_CUE_COMMA_RE = re.compile(rf"\b(?i:{_ROLES})\s*,\s*(?P<name>{_NAME})")
#: "<role> as <Name>": "identified the deceased as <Name>", "named as <Name>", "identified him as <Name>".
_CUE_AS_RE = re.compile(rf"\b(?i:{_ROLES}|named|identified\s+(?:him|her|them))\s+as\s+(?P<name>{_NAME})")
#: A Title-Case role cue in a headline ("Accused <Given> <Surname> Held"); taken only before two name words.
_TITLE_CUE_RE = re.compile(
    rf"\b(?:Accused|Victim|Deceased|Complainant|Identified\s+As|Driver\s+Named)\s+(?P<name>{_NAME})"
)
#: Honorifics and ranks that the shared cue list does not hold: Marathi "Sau." (a married woman), "Ku."/"Kum."/
#: "Kumari", "Shree"/"Shrimati", "Adv." (an advocate), Mumbai Police ranks ("API", "PSI", "PI", "Sr PI", "ACP",
#: "DCP", "Hawaldar") and the second city pack's "Sri"/"Srimati", "Sergeant" and "OC".
_LOCAL_CUE_RE = re.compile(
    rf"\b(?:Sau|Ku|Kum|Kumari|Shree|Sri|Sree|Srimati|Sreemati|Shrimati|Adv|API|PSI|Sr\.?\s?PI|PI|ACP|DCP|Hawaldar"
    rf"|Havaldar|Sergeant|Sgt|OC)\.?\s+(?P<name>{_NAME})"
)
#: "<Name> saheb" / "<Name> bhau" / "<Name> tai" / "<Name> ji": a Marathi or Hindi address term written apart
#: after a name (every tier): the one or two capitalised words before it are the person.
_ADDRESS_AFTER_RE = re.compile(
    rf"(?<![A-Za-z])(?P<name>(?:{_CAP}\s+)?{_CAP})\s+(?:saheb|sahab|bhau|tai|kaka|kaki|mama|anna|aaba|dada|ji|seth"
    r"|sheth)(?![A-Za-z])"
)
#: An honorific with no space before the name ("Mr.<Name>", "Dr.R. K. <Name>"); read as "Mr. <Name>" is.
_TIGHT_HONORIFIC_RE = re.compile(r"\b(?:Mr|Mrs|Ms|Shri|Smt|Dr)\.(?=(?:[A-Z]\.\s?){0,3}[A-Z][a-z]{2})")
#: Up to five capitalised words (each optionally initialled) that end right before an age: "<Name>, 45,",
#: "<Name> (45)", "<Name>, aged 45", "<Name>, a 45-year-old".
_RUN_BEFORE_AGE_RE = re.compile(
    rf"(?<![A-Za-z])(?:{_INIT}{{0,3}}{_CAP}\s+){{0,4}}{_INIT}{{0,3}}{_CAP}(?=(?:\s*,\s*(?:(?:a|an)\s+)?|\s*\(\s*)$)"
)
_BEFORE_AGE_WINDOW = 200
#: Digits an Indic-script report writes: ASCII, Devanagari (०-९) and Marathi (০-৯).
_IDIGIT = r"[0-9\u0966-\u096f\u09e6-\u09ef]"
#: Marathi "য়" written as one code point (U+09DF) or as "য" + nukta (its NFC/NFKC form): feeds use both.
_MR_YA = "(?:\u09df|\u09af\u09bc)"
#: Age forms the shared patterns do not read ("45 years of age", "aged about 45", and the Marathi and Hindi forms).
_EXTRA_AGE_RES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("age:years_of_age", re.compile(r"\b\d{1,3}\s*(?:years?|yrs?)\s+of\s+age\b", re.IGNORECASE)),
    ("age:aged_about", re.compile(r"\baged\s+(?:about|around|nearly|approximately|approx\.?)\s+\d{1,3}\b", re.I)),
    # Marathi: "३५ वर्षीय", "४२ वर्षांचा" / "वर्षांची" / "वर्षांच्या", "६० वर्षे वयाचा"; Hindi: "28 वर्षीय", "45 साल
    # के", "28 साला"; the second city pack's Bengali "৩৫ বছরের", "৪২ বছর বয়সী". Any digits. ("३५ वर्षे", for 35 years,
    # is a duration: not read.)
    ("age:indic_years", re.compile(
        rf"(?<!{_IDIGIT}){_IDIGIT}{{1,3}}\s*-?\s*"
        rf"(?:বছরের|বছর\s*ব{_MR_YA}(?:সী|সি|স্ক|স্কা|সের|সে)|বর্ষী{_MR_YA}|"
        r"वर्षीय|वर्ष\s+(?:के|की|का)|साल\s+(?:के|की|का)|साला|"
        r"वर्षांच्या|वर्षाच्या|वर्षांचा|वर्षांची|वर्षांचे|वर्षाचा|वर्षाची|वर्षाचे|वर्षे\s+वयाच्या|वर्षे\s+वयाचा)"
    )),
    # Marathi "वय ६०", "वय सुमारे ६० वर्षे", "वय वर्षे ६०"; Hindi "उम्र 60" / "उम्र 60 साल"; Bengali "বয়স ৬০"
    ("age:indic_aged", re.compile(
        rf"(?:ব{_MR_YA}স|उम्र|(?<![\u0900-\u097f])वय)\s*(?:প্রা{_MR_YA}\s*|करीब\s*|लगभग\s*|सुमारे\s*|अंदाजे\s*"
        rf"|वर्षे\s*)?:?\s*{_IDIGIT}{{1,3}}"
        r"(?:\s*(?:বছর|वर्ष|वर्षे|साल))?(?!\d)"
    )),
    # a parenthesised number after an Indic word ("<name> (৬০)", "<name> (45)"), and any number written in Indic
    # digits in parentheses
    ("age:indic_paren", re.compile(
        rf"(?:(?<=[\u0900-\u0d7f])|(?<=[\u0900-\u0d7f]\s))\(\s*{_IDIGIT}{{1,3}}\s*\)"
        r"|\(\s*[\u0966-\u096f\u09e6-\u09ef]{1,3}\s*\)"
    )),
    # "<name>, ৪৫," after an Indic word (the shared comma rule reads Latin names only)
    ("age:indic_comma", re.compile(rf"(?<=[\u0900-\u0d7f])\s*,\s*{_IDIGIT}{{1,3}}(?=\s*,)")),
)

_URL_CHAR = r"[^\s<>\"'`{}|\\^\[\]]"
#: A URL in free text: ``http(s)://…`` or ``ftp://…``, ``www.…``, or ``<host>.<tld>/<path>`` (no scheme).
URL_RE = re.compile(
    rf"(?:\b(?:https?|ftp)://|\bwww\d{{0,3}}\.){_URL_CHAR}+"
    rf"|(?<![\w.@-])(?:[a-z0-9](?:[a-z0-9-]{{0,61}}[a-z0-9])?\.)+[a-z]{{2,24}}/{_URL_CHAR}*",
    re.IGNORECASE,
)
_URL_TRAIL = ".,;:!?)"
#: A Reddit user page inside a URL, on any reddit.com host: ``reddit.com/u/<name>``, ``/user/<name>``,
#: ``/r/u_<name>`` (a user's profile community).
REDDIT_USER_URL_RE = re.compile(
    r"(?<![\w.-])(?:[a-z0-9-]+\.)*reddit\.com/+(?:u/+|user/+|r/+u_)[A-Za-z0-9_-]", re.IGNORECASE
)
#: A social-platform profile link (what the parity checks count as a poster handle when one is left in a text;
#: every URL is redacted anyway): Instagram, X/Twitter, Facebook, TikTok, Threads, Telegram, LinkedIn ``/in/``,
#: YouTube ``@``/channel paths and Snapchat ``/add/``.
PROFILE_URL_RE = re.compile(
    r"(?<![\w.-])(?:[a-z0-9-]+\.)*(?:instagram\.com|instagr\.am|x\.com|twitter\.com|facebook\.com|fb\.com"
    r"|tiktok\.com|threads\.net|t\.me|telegram\.me|linkedin\.com/in|snapchat\.com/add"
    r"|youtube\.com/(?:c|user|channel)|youtube\.com(?=/@))/+@?[A-Za-z0-9_][A-Za-z0-9_.-]",
    re.IGNORECASE,
)
#: The rest of a user name after a :data:`REDDIT_USER_URL_RE` match (which reads only its first character).
_REDDIT_USER_TAIL_RE = re.compile(r"[A-Za-z0-9_-]*")
#: A Reddit user mention: ``u/<name>``, ``/u/<name>``, ``/user/<name>`` or ``r/u_<name>`` (a profile community).
#: Redacted in every tier (module docstring, rule 3).
HANDLE_RE = re.compile(r"(?<![\w/])(?:/?u/|/user/|/?r/u_)[A-Za-z0-9_-]{3,20}(?![\w-])")
#: An ``@<name>`` mention (Instagram, X and the like: 3 to 30 letters, digits, ``_`` or inner ``.``). Not the
#: ``@`` of an e-mail address (a word character precedes it) and not a time written "@5pm" or "@10:30".
AT_HANDLE_RE = re.compile(
    r"(?<![\w.@/])@(?!\d{1,2}(?:[:.]\d{2})?\s?(?:am|pm|hrs?)?(?!\w))"
    r"[A-Za-z0-9_][A-Za-z0-9_.]{2,29}(?<!\.)(?![A-Za-z0-9_])",
    re.IGNORECASE,
)
_PLATFORMS = r"insta(?:gram)?|ig|snap(?:chat)?|twitter|tiktok|telegram|threads|fb|facebook|yt|youtube|linkedin"
#: A handle named after a platform cue in a social post: "insta: <handle>", "IG id - <handle>", "fb page: <h>".
PLATFORM_HANDLE_RE = re.compile(
    rf"\b(?:{_PLATFORMS})\b\s*(?:(?:id|handle|username|user\s?name|account|page|profile)\b\s*[:=\-–—]?|[:=\-–—])"
    r"\s*@?(?P<h>[A-Za-z0-9_](?:[A-Za-z0-9_.]{1,28}[A-Za-z0-9_])?)(?![A-Za-z0-9_@])",
    re.IGNORECASE,
)
#: What follows a platform cue without being a handle ("insta: link in bio", "IG - DM me").
_NOT_HANDLES = frozenset(
    "link links bio dm dms inbox story stories reel reels page account profile handle id comments comment".split()
)
#: Lower-case particles inside a person's name ("<Given> de <Surname>", "<Given> bin <Surname>").
_NAME_PARTICLES = frozenset("de da di du del dos das van von der bin bint ibn".split())
_EMAIL_RE = re.compile(r"(?<![\w.+-])[\w.+-]{1,64}@[A-Za-z0-9-]{1,63}(?:\.[A-Za-z0-9-]{1,63})+")
_PHONE_RE = re.compile(r"(?<![\d+])(?:\+?91[\s-]?)?[6-9]\d{4}[\s-]?\d{5}(?!\d)")

# ── cue-less names (every tier; F-HONEST OSINT-2) ──────────────────────────────────────────────────────────────

#: Common surnames of Maharashtra, Mumbai's other communities and India (lower case), a general list by community,
#: never a list of particular people. A capitalised word before one of them makes a name ("<Given> <Surname>"); a
#: surname alone does not (a family, a community or a firm is named that way: "Patil family", "Joshi Wada"). Left
#: out on purpose: surnames that are Mumbai place words (Wankhede: the stadium; Wadia: the hospitals; Tilak, Phule,
#: Ambedkar, Savarkar, Gandhi, Nehru: the city's roads, markets and terminus are named after them, and the protect
#: set keeps those places) and ordinary English words (Gala, Dave). The second city pack's surnames stay listed.
SURNAMES: frozenset[str] = frozenset(
    """
    banerjee bandyopadhyay banerji mukherjee mukhopadhyay mukherji chatterjee chattopadhyay chatterji ganguly
    gangopadhyay ganguli bhattacharya bhattacharjee bhattacharyya chakraborty chakrabarty chakravarty chakrabarti
    das dey dutta datta sen sengupta dasgupta duttagupta sarkar sircar saha paul pal roy roychowdhury
    majumdar mazumdar mitra mallick mallik mullick naskar halder haldar sardar biswas pramanik adhikari maity
    maiti jana bera barman burman debnath karmakar kundu nandi guha ghoshal lahiri sanyal bagchi maitra moitra
    chowdhury choudhury chaudhuri talukdar samanta mondal mandal ghosh bose basu dhar kar nath bhowmick bhowmik
    bhaumik goswami acharya chanda mahato mahata hembram murmu tudu soren kisku hansda besra sinha sinharoy
    mukhuti purkait patra pradhan giri hati santra manna samui dhara khan khatun bibi begum molla mollah laskar
    gazi gayen shaikh sheikh ahmed ahmad hossain hussain hosain rahaman rahman ali ansari siddiqui alam haque
    haq islam uddin mirza qureshi
    agarwal agrawal aggarwal jain saraf goenka jhunjhunwala kejriwal poddar bajaj kothari daga mohta bagri
    sureka kanoria birla maheshwari somani bansal mittal
    sharma verma gupta mishra tiwari tripathi pandey dubey shukla yadav singh kumar thakur rai prasad shaw
    sah sahu rajak paswan chaudhary choudhary srivastava saxena sinha jha thakur pathak upadhyay
    nair pillai menon iyer reddy rao shetty patil pawar jadhav shinde kulkarni deshmukh
    patel shah desai mehta joshi parikh trivedi
    gaikwad gaekwad chavan chauhan kadam sawant more bhosale bhonsle naik nayak rane parab salunkhe mhatre kamble
    lokhande thorat shelar dalvi gawde gawade satam deshpande gokhale apte karve bapat phadke kale gore jagtap
    waghmare shewale dhuri patkar nikam mhaske sathe bhide khare ranade gadgil kher tendulkar salvi chougule
    mohite ghadge nalawade jagdale ingle dongre mestry tawde rawool sarnaik shirke mane mahadik ghorpade
    kshirsagar khot kelkar bhagat surve sakpal tambe adsul bhalerao kamat prabhu sabnis hegde mhaskar sakpal
    gurav ghag sable pednekar gawas kocharekar shinde kamath kini rathod solanki parmar rajput pathan sayyed syed
    momin maurya vishwakarma bhatt vora doshi sanghvi thakkar panchal pandya chheda savla dedhia vyas
    almeida dsilva desouza correia pinto mascarenhas rebello lopes dias colaco menezes noronha coutinho
    carvalho monteiro dcosta dcruz dmello
    gill sandhu dhillon kaur arora khanna kapoor malhotra chopra bhatia ahuja
    dsouza rozario rodrigues pereira gomes fernandes lobo
    """.split()
)

#: Given-name suffixes that make a word a person: the Marathi honorific "-rao" written onto a name ("<Given>rao",
#: "<Given>-rao"), "<Given>bhau", "<Given>-ji" (hyphenated only: a joined "-ji" also ends Shivaji, Sambhaji and
#: Tanaji, whose names Mumbai's parks, terminus and roads carry), the Gujarati and Hindi ones ("<Given>bhai",
#: "<Given>ben"), and the second city pack's ("<Given>babu", "<Given>-da", "<Given>-di"). A joined "-da" is not read
#: ("Agenda", "Veranda" end the same way).
_HONORIFIC_SUFFIX_RE = re.compile(
    r"(?<![A-Za-z])[A-Z][a-z]+(?:babu|bhai|ben|bahen|behen|bhau|bapu|rao|-(?:da|di|dada|didi|babu|boudi|rao|ji))"
    r"(?![A-Za-z])"
)

#: Role, kin and occupation nouns that introduce a name in news copy without a cue word ("Biker <Given>
#: <Surname> dies", "husband <Given> <Surname>", "Daughter of <Given> <Surname>"), any case.
_ROLE_NOUNS = (
    r"bikers?|riders?|motorists?|cyclists?|pedestrians?|drivers?|teens?|teenagers?|youths?|boys?|girls?|man|woman"
    r"|businessm[ae]n|businesswom[ae]n|traders?|jewell?ers?|shopkeepers?|vendors?|hawkers?|workers?|labou?rers?"
    r"|supervisors?|managers?|employees?|techies?|doctors?|nurses?|teachers?|professors?|principals?|students?"
    r"|husbands?|wives|wife|sons?|daughters?|mothers?|fathers?|brothers?|sisters?|uncles?|aunts?|nephews?"
    r"|nieces?|grandsons?|granddaughters?|neighbou?rs?|friends?|colleagues?|tenants?|landlords?|residents?"
    r"|ex-corporators?|corporators?|councill?ors?|sarpanch|inspectors?|constables?|cops?|officers?|guards?"
    r"|watchm[ae]n|septuagenarians?|octogenarians?|nonagenarians?|elderly|couples?|victims?|accused|deceased"
    r"|complainants?|suspects?|gangsters?|bootleggers?|history-sheeters?|priests?|activists?|lawyers?"
    r"|advocates?|influencers?|creators?|actors?|actress(?:es)?|singers?|players?|cricketers?|athletes?"
    r"|families|family|kin|relatives?|widows?|widowers?|owners?"
)
_ROLE_CUE_RE = re.compile(rf"(?<![A-Za-z-])(?i:{_ROLE_NOUNS})(?:\s+(?i:of))?\s+(?P<name>{_NAME})")
#: "<Given> alias <Nickname> <Surname>" / "urf" / "<Given> @ <Nickname>": both sides of the alias are the person.
_ALIAS_RE = re.compile(
    rf"(?P<left>(?:{_CAP}\s+){{0,2}}{_CAP})\s+(?:(?i:alias|urf|a\.k\.a\.?|aka)|@)\s+(?P<right>{_NAME})"
)
#: "<Given>, a vegetable vendor," / "<Given>, an employee": a name, then a comma and an indefinite article.
_NAME_COMMA_ARTICLE_RE = re.compile(rf"(?<![A-Za-z])(?P<name>(?:{_CAP}\s+){{0,2}}{_CAP})\s*,\s+(?:a|an)\s+(?=[a-z])")
#: An apostrophe surname ("D'Souza", "O'Brien") with the given name before it: a person, not a place.
_APOSTROPHE_NAME_RE = re.compile(rf"(?<![A-Za-z])(?:{_CAP}\s+)?[A-Z]['’][A-Z][a-z]{{2,}}(?![A-Za-z])")
#: "<Name>'s body / family / killers": a possessive before a noun only a person has.
_POSSESSIVE_PERSON_RE = re.compile(
    rf"(?<![A-Za-z])(?P<name>(?:{_CAP}\s+){{0,2}}{_CAP})['’]s\s+(?:dead\s+)?(?:body|bodies|family|death|murder"
    r"|killers?|killing|husband|wife|son|daughter|mother|father|parents|brother|sister|kin|relatives|in-laws"
    r"|post-?mortem|autopsy|funeral|cremation|last\s+rites)(?![A-Za-z])"
)
#: "<Given> and <Given> <Surname>" (a couple, siblings): the first given name shares the surname.
_AND_BEFORE_RE = re.compile(rf"(?<![A-Za-z])(?P<w>{_CAP})\s+(?:and|&)\s+$")
#: Title-Case words that follow a role noun or precede a surname without being a name: organisations, sentence
#: adverbs and reporting words ("Youth Congress", "Meanwhile, a ...", "Police Commissioner").
_NOT_NAME_WORDS: frozenset[str] = frozenset(
    """
    congress union commission council party wing federation association board committee cell front sena dal
    samaj team squad brigade department ministry corporation company group trust society foundation academy
    meanwhile earlier additionally besides moreover separately elsewhere initially eventually finally recently
    reportedly apparently unfortunately luckily fortunately interestingly notably officials sources reports
    sunday monday tuesday wednesday thursday friday saturday viral video photo watch exclusive breaking live
    commissioner collector minister mayor chief deputy superintendent director secretary chairman president
    high court bench sessions metropolitan
    """.split()
)
_MAX_GIVEN_WORDS = 2

# ── the social tier: age and sex self-descriptions (F-HONEST OSINT-6) and single-word name cues ──────────────

#: A poster's age and sex shorthand: "F(28)", "M (34)", "28F", "22M", "27/F", "F/27", "(24F)", "26 M," (spaced
#: only before punctuation or the end). Upper-case M/F
#: only, and never after a currency sign or "Rs" ("Rs 22M" is an amount).
_AGE_SEX_RE = re.compile(
    r"(?<![\w₹$£€])(?<!Rs )(?<!Rs\. )(?<!INR )"
    r"(?:\(\s?\d{2}\s?[MF]\s?\)|[MF]\s?\(\s?\d{2}\s?\)|\d{2}\s?/\s?[MF]|[MF]\s?/\s?\d{2}|\d{2}[MF]|[MF]\d{2}"
    r"|(?<![\w,.])\d{2}\s[MF](?=\s*[,.;:!?)]|\s*$))"
    r"(?![\w/])"
)
#: Social-post cues before a single given name ("my neighbour <Given>", "contact <Given>", "shoutout to <Given>").
_SOCIAL_NAME_CUE_RE = re.compile(
    r"(?<![A-Za-z])(?i:neighbou?r|friend|cousin|bro|brother|sister|uncle|aunty|auntie|aunt|colleague|classmate"
    r"|roommate|flatmate|landlord|tenant|maid|driver|contact|call|ask|ping|message|text|dm|thank|thanks"
    r"|thanks\s+to|shout\s?out\s+to|kudos\s+to|credit\s+to|called|named|name\s+(?:is|was))"
    r"\s+(?P<name>[A-Z][a-z]{2,})(?![A-Za-z])"
)
#: "<Given> bhai" / "<Given> ben" / "<Given> sir" written apart: the word before the address term is a name.
_SOCIAL_ADDRESS_RE = re.compile(
    r"(?<![A-Za-z])(?P<name>[A-Z][a-z]{2,})\s+(?:bhai|bhaiya|ben|didi|sir|madam|ji|uncle|aunty|kaka|kaki|da|dada|di"
    r"|babu|boudi|kaku|jethu|mashi|mama|pishi)\b"
)


@dataclass(frozen=True)
class Span:
    """One replacement: ``text[start:end]`` → the token of ``kind`` (``name``, ``age``, ``contact`` or ``url``)."""

    start: int
    end: int
    kind: str
    rule: str


@lru_cache(maxsize=8)
def _phrase_index(protect: frozenset[str]) -> tuple[frozenset[str], frozenset[str], int]:
    """(multi-word phrases, single-word aliases, longest phrase in words) of a protect-set."""
    multi = frozenset(p for p in protect if " " in p)
    single = frozenset(p for p in protect if p and " " not in p)
    longest = max((p.count(" ") + 1 for p in multi), default=0)
    return multi, single, longest


def _norm_ws(name: str) -> str:
    return " ".join(name.split())


def _covered(words: list[str], i: int, multi: frozenset[str], longest: int) -> bool:
    """Is ``words[i]`` inside a multi-word gazetteer phrase that occurs in the text at this position?"""
    if longest < 2 or i < 0:
        return False
    for j in range(max(0, i - longest + 1), i + 1):
        for k in range(max(i + 1, j + 2), min(len(words), j + longest) + 1):
            if " ".join(words[j:k]) in multi:
                return True
    return False


def _word_positions(text: str) -> tuple[list[str], dict[int, int]]:
    """The lower-cased ASCII words of ``text`` and a map from each word's start offset to its index."""
    words: list[str] = []
    index: dict[int, int] = {}
    for m in _WORD_RE.finditer(text):
        index[m.start()] = len(words)
        words.append(m.group(0).lower())
    return words, index


class _Words:
    """One text's words and the gazetteer index: judges the capitalised word that starts at an offset."""

    def __init__(self, text: str, protect: frozenset[str]) -> None:
        self.words, self.index = _word_positions(text)
        self.multi, self.single, self.longest = _phrase_index(protect)

    def covered(self, offset: int) -> bool:
        """Inside a multi-word gazetteer phrase that occurs in the text here."""
        return _covered(self.words, self.index.get(offset, -1), self.multi, self.longest)

    def plain(self, word: str, offset: int, *extra: frozenset[str]) -> bool:
        """An ordinary, generic (or ``extra``) word or a gazetteer place: never a name word in a news text."""
        low = word.lower()
        return (
            low in COMMON_WORDS
            or low in ethics.GENERIC_PLACE_WORDS
            or any(low in s for s in extra)
            or low in self.single
            or self.covered(offset)
        )


# ── names and ages (every tier) ───────────────────────────────────────────────────────────────────────────────


def _run_on(text: str, end: int, w: _Words, *extra: frozenset[str]) -> int:
    """The end of a name span after it runs on over up to two more name words (module docstring, rule 1)."""
    for _ in range(_MAX_EXTRA_WORDS):
        m = _NEXT_NAME_WORD_RE.match(text, end)
        if m is None or w.plain(m.group("w"), m.start("w"), HEADLINE_WORDS, *extra):
            break
        end = m.end()
    return end


def _leading_name(text: str, start: int, end: int, w: _Words, *, min_words: int) -> int | None:
    """The end of the leading name words of ``text[start:end]`` (tokens up to the first plain word), or ``None``
    when fewer than ``min_words`` name words lead."""
    name_end, n = None, 0
    for t in _NAME_TOKEN_RE.finditer(text, start, end):
        if t.group("word") is None:
            continue
        if w.plain(t.group("word"), t.start(), HEADLINE_WORDS, AGE_CONTEXT_WORDS):
            break
        name_end, n = t.end(), n + 1
    return name_end if n >= min_words else None


def _local_cue_spans(text: str, protect: frozenset[str], w: _Words) -> list[Span]:
    """The cue forms ``ethics.pii_spans`` does not read (module docstring, rule 1)."""
    spans: list[Span] = []
    for rx, rule, min_words in (
        (_CUE_COMMA_RE, "name:cue_comma", 1),
        (_CUE_AS_RE, "name:cue_as", 1),
        (_TITLE_CUE_RE, "name:title_cue", 2),
        (_LOCAL_CUE_RE, "name:local_cue", 1),
    ):
        for m in rx.finditer(text):
            end = _leading_name(text, m.start("name"), m.end("name"), w, min_words=min_words)
            if end is not None:
                spans.append(Span(m.start("name"), _run_on(text, end, w), "name", rule))
    for m in _TIGHT_HONORIFIC_RE.finditer(text):
        # "Mr.<Name>" is read exactly as "Mr. <Name>" is (the shared place rules included): one space inserted
        cut = m.end()
        for s in ethics.pii_spans(text[:cut] + " " + text[cut:], protect=protect):
            if s.kind == "name" and s.start == cut + 1:
                spans.append(Span(cut, _run_on(text, s.end - 1, w), "name", "name:honorific_tight"))
    return spans


def _before_age_spans(text: str, ages: list[Span], w: _Words) -> list[Span]:
    """The name right before an age, without its leading context words (module docstring, rule 1)."""
    spans: list[Span] = []
    for a in ages:
        m = _RUN_BEFORE_AGE_RE.search(text, max(0, a.start - _BEFORE_AGE_WINDOW), a.start)
        if m is None:
            continue
        toks = list(_NAME_TOKEN_RE.finditer(text, m.start(), m.end()))
        first = next(
            (k for k, t in enumerate(toks) if t.group("word") and not w.plain(
                t.group("word"), t.start(), HEADLINE_WORDS, AGE_CONTEXT_WORDS)),
            None,
        )
        if first is None:
            continue  # "Elderly Woman, 80,": context words only
        while first > 0 and toks[first - 1].group("init"):
            first -= 1  # the initials of the first name word belong to the name
        spans.append(Span(toks[first].start(), m.end(), "name", "name:before_age"))
    return spans


_ROLE_WORD_RE = re.compile(rf"(?i:{_ROLE_NOUNS})")
_NOT_NAME_SETS = (HEADLINE_WORDS, AGE_CONTEXT_WORDS, _NOT_NAME_WORDS)


def _not_name(word: str, offset: int, w: _Words) -> bool:
    """A word the cue-less rules never take as a name word: plain (common, generic, gazetteer), a headline verb,
    an age-context or role noun, an organisation or sentence word."""
    return w.plain(word, offset, *_NOT_NAME_SETS) or _ROLE_WORD_RE.fullmatch(word) is not None


def _lead(text: str, start: int, end: int, w: _Words) -> int | None:
    """The end of the leading name words of ``text[start:end]`` (initials allowed), or ``None`` when none lead."""
    name_end = None
    for t in _NAME_TOKEN_RE.finditer(text, start, end):
        if t.group("word") is None:
            continue
        if _not_name(t.group("word"), t.start(), w):
            break
        name_end = t.end()
    return name_end


def _trail(text: str, start: int, end: int, w: _Words) -> int | None:
    """The start of the trailing name words of ``text[start:end]`` (the words after its last non-name word), or
    ``None`` when the last word is not a name word."""
    toks = [t for t in _NAME_TOKEN_RE.finditer(text, start, end) if t.group("word") is not None]
    first = None
    for t in reversed(toks):
        if _not_name(t.group("word"), t.start(), w):
            break
        first = t.start()
    return _with_initials(text, first) if first is not None else None


#: Initials right before a name word ("K. R. <Surname>").
_INITIALS_BEFORE_RE = re.compile(r"(?<![A-Za-z])(?:[A-Z]\.\s?){1,3}$")


def _with_initials(text: str, start: int) -> int:
    """``start`` moved back over the initials written right before it."""
    m = _INITIALS_BEFORE_RE.search(text, max(0, start - 12), start)
    return m.start() if m is not None else start


def _surname_spans(text: str, w: _Words) -> list[Span]:
    """"<Given> <Surname>" (up to two given words or initials before a :data:`SURNAMES` word), and the first given
    name of "<Given> and <Given> <Surname>"."""
    spans: list[Span] = []
    for group in _token_groups(text):
        for k, t in enumerate(group):
            word = t.group("word")
            if word is None or word.lower() not in SURNAMES or w.covered(t.start()):
                continue
            j, given = k, 0
            while j > 0 and given < _MAX_GIVEN_WORDS:
                prev = group[j - 1]
                if prev.group("init") is not None:
                    j -= 1
                    continue
                if _not_name(prev.group("word"), prev.start(), w) or w.covered(prev.start()):
                    break
                j -= 1
                given += 1
            if j == k:
                continue  # a surname alone names a community or a firm as often as a person
            # a compound surname runs on ("<Given> Singh <Surname>"); initials before the name belong to it
            end = _run_on(text, t.end(), w, *_NOT_NAME_SETS)
            spans.append(Span(_with_initials(text, group[j].start()), end, "name", "name:surname"))
            before = _AND_BEFORE_RE.search(text, max(0, group[j].start() - 40), group[j].start())
            if before is not None and not _not_name(before.group("w"), before.start("w"), w):
                spans.append(Span(before.start("w"), before.end("w"), "name", "name:surname_and"))
    return spans


def _cueless_spans(text: str, w: _Words) -> list[Span]:
    """Names with no cue word of :data:`osint_common.ethics.NAME_CUES` (F-HONEST OSINT-2): a role, kin or
    occupation noun before a name, a known surname after a given name, a name with an address suffix
    ("<Given>babu", "<Given>-da", "<Given>bhai"), both sides of an "alias", and "<Given>, a <role>". Every name word
    must not be a place, a common, generic, headline or organisation word (:func:`_not_name`), so a gazetteer
    phrase ("Senapati Bapat Marg") survives."""
    spans: list[Span] = []
    for m in _ROLE_CUE_RE.finditer(text):
        end = _lead(text, m.start("name"), m.end("name"), w)
        if end is not None:
            spans.append(Span(m.start("name"), _run_on(text, end, w, *_NOT_NAME_SETS), "name", "name:role"))
    spans.extend(_surname_spans(text, w))
    for m in _HONORIFIC_SUFFIX_RE.finditer(text):
        if not w.covered(m.start()):
            spans.append(Span(m.start(), _run_on(text, m.end(), w, *_NOT_NAME_SETS), "name", "name:suffix"))
    for m in _ADDRESS_AFTER_RE.finditer(text):
        first = _trail(text, m.start("name"), m.end("name"), w)
        if first is not None:
            spans.append(Span(first, m.end("name"), "name", "name:address_after"))
    for m in _ALIAS_RE.finditer(text):
        first = _trail(text, m.start("left"), m.end("left"), w)
        if first is not None:
            spans.append(Span(first, m.end("left"), "name", "name:alias"))
        end = _lead(text, m.start("right"), m.end("right"), w)
        if end is not None:
            spans.append(Span(m.start("right"), _run_on(text, end, w, *_NOT_NAME_SETS), "name", "name:alias"))
    for m in _APOSTROPHE_NAME_RE.finditer(text):
        if not w.covered(m.start()):
            spans.append(Span(m.start(), m.end(), "name", "name:apostrophe"))
    for m in _POSSESSIVE_PERSON_RE.finditer(text):
        first = _trail(text, m.start("name"), m.end("name"), w)
        if first is not None:
            spans.append(Span(first, m.end("name"), "name", "name:possessive"))
    for m in _NAME_COMMA_ARTICLE_RE.finditer(text):
        first = _trail(text, m.start("name"), m.end("name"), w)
        if first is not None:
            spans.append(Span(first, m.end("name"), "name", "name:comma_article"))
    return spans


# ── Marathi and Hindi cues in Indic script (every tier) ─────────────────────────────────────────────────────────

#: A run of Marathi or Devanagari letters and vowel signs (digits, dandas and punctuation end a word).
_INDIC_WORD_RE = re.compile("[\u0980-\u09e3\u09f0\u09f1\u0900-\u0963\u0971-\u097f\u200c\u200d]+")


def _ikey(word: str) -> str:
    """An Indic word's comparison form (the ``osint_common.ethics`` rule): NFKC, format characters dropped."""
    return "".join(c for c in unicodedata.normalize("NFKC", word) if unicodedata.category(c) != "Cf")


def _ikeys(*words: str) -> frozenset[str]:
    return frozenset(_ikey(w) for w in words)


#: Honorifics: the word after one is a name even when it is also an ordinary word or a place ("श्री विजय पाटील"):
#: Marathi श्री, श्रीमती, सौ. (a married woman), कु. / कुमारी, श्रीयुत, श्रीमान, डॉ., प्रा. (professor), ॲड. (an
#: advocate), कै. / स्व. (the late); Hindi श्री, श्रीमती, सुश्री, डॉ.; the second city pack's Bengali ones. Unless a
#: place noun follows the run ("डॉ. आंबेडकर मार्ग" is a road, :data:`_INDIC_PLACE_NOUNS`).
_INDIC_HONORIFICS = _ikeys(
    "श्री", "श्रीमती", "सौ", "कु", "कुमारी", "श्रीयुत", "श्रीमान", "डॉ", "डॉक्टर", "प्रा", "प्राध्यापक", "प्रोफेसर",
    "ॲड", "अॅड", "ॲडव्होकेट", "कै", "स्व", "सुश्री",
    "শ্রী", "শ্রীমতী", "শ্রীমতি", "শ্রীযুক্ত", "শ্রীযুক্তা", "ডাঃ", "ডা", "ডাক্তার", "অধ্যাপক", "অধ্যাপিকা",
)
#: Place nouns (a word that starts with one, any case ending: "मार्गावर", "चौकात", "स्थानकाजवळ"): an honorific run
#: that ends right before one names a place after a person, never the person.
_INDIC_PLACE_NOUNS: tuple[str, ...] = tuple(_ikey(w) for w in (
    "मार्ग", "रोड", "चौक", "पथ", "उद्यान", "पूल", "उड्डाणपूल", "नगर", "स्थानक", "टर्मिनस", "रुग्णालय", "हॉस्पिटल",
    "मैदान", "पार्क", "सेतू", "सेतु", "पुल", "महाविद्यालय", "कॉलेज", "विद्यालय", "शाळा", "स्मारक", "पुतळा",
    "सभागृह", "नाका", "चौपाटी", "बाग", "क्रीडांगण", "स्टेडियम", "विमानतळ", "अस्पताल", "सड़क", "चौराहा",
))
#: Role cues: the unknown words right after one are a name ("आरोपी <name>", "मृताचे नाव <name>", "जखमी <name>",
#: "रिक्षाचालक <name>"; Hindi "मृतक <name>"). An ordinary word after a cue ends it ("जखमी तीन जण": three injured),
#: so a cue alone never redacts.
_INDIC_ROLE_CUES = _ikeys(
    "आरोपी", "मृत", "मृताचे", "मृताचा", "मृताची", "मृतांची", "मृतांचे", "जखमी", "रहिवासी", "चालक", "वाहनचालक",
    "रिक्षाचालक", "टॅक्सीचालक", "दुचाकीस्वार", "पादचारी", "तक्रारदार", "पीडित", "पीडिता", "संशयित", "नाव",
    "विक्रेता", "दुकानदार", "हवालदार", "शिपाई", "कॉन्स्टेबल", "उपनिरीक्षक", "निरीक्षक",
    "मृतक", "घायल", "निवासी", "पीड़ित", "पीड़िता", "संदिग्ध", "ड्राइवर", "सिपाही", "हवलदार", "नाम",
    "অভিযুক্ত", "ধৃত", "মৃত", "নিহত", "আহত", "বাসিন্দা", "চালক", "অভিযোগকারী", "আক্রান্ত", "নাম", "ওসি",
)
#: Address terms written after a name ("<name> साहेब", "<name> भाऊ", "<name> ताई", "<name> जी"): the word before
#: one is a name, unless it is an ordinary word ("तिचा भाऊ", her brother) or a place.
_INDIC_ADDRESS = _ikeys(
    "साहेब", "साहेबांनी", "साहेबांना", "भाऊ", "ताई", "दादा", "काका", "मामा", "अण्णा", "आबा", "जी", "शेठ", "सेठ",
    "राव", "बाई", "बाबू", "भैया", "दीदी",
    "বাবু", "দা", "দি", "দিদি", "কাকু", "জেঠু", "মাসি", "বৌদি", "বউদি",
)
#: A name with an honorific written onto it, with or without a case ending: Marathi "-राव" ("शंकरराव"), "-जी",
#: "-बाई", "-साहेब", "-भाऊ", "-ताई", "-शेठ" (a stem of three letters at least: "भाजी", vegetables, and "ठराव", a
#: resolution, are words), and the second city pack's "-বাবু".
_INDIC_BABU_RE = re.compile(_ikey(
    "^(?:(.{3,})(?:राव|जी|बाई|साहेब|भाऊ|ताई|शेठ)(?:ांनी|ांना|ांचा|ांची|ांचे|ने|ला|चा|ची|चे|ना|नी|कडे|के|की|का|को|से)?"
    "|(.{2,})বাবু(?:র|কে|রা|দের|ের)?)$"
))
_INDIC_GAP_RE = re.compile(r"^[\s.\-]{1,3}$")
_INDIC_MAX_NAME_WORDS = 3


def _indic_common(key: str) -> bool:
    """An ordinary word or a place (the gazetteer's, or the city pack's Marathi and Hindi spellings), with or
    without a case ending: never read as a name word."""
    single = ethics.indic_place_forms()[0]
    pack = city_indic_places()
    stems = [key] + [key[: -len(suf)] for suf in ethics.INDIC_SUFFIXES if key.endswith(suf) and len(key) > len(suf) + 1]
    return any(st in ethics.INDIC_COMMON_WORDS or st in single or st in pack for st in stems)


def _indic_place_noun(key: str) -> bool:
    return key.startswith(_INDIC_PLACE_NOUNS)


def _indic_cue_spans(text: str) -> list[Span]:
    """Names introduced by a Marathi or Hindi cue in Indic script (module docstring, rule 1): after an honorific,
    after a role cue, before an address term, and a word ending in "বাবু". Every unknown Indic word is withheld
    anyway (rule 6); these rules also catch a name that is an ordinary word or a place, and say ``[PERSON]``."""
    if text.isascii():
        return []
    words = [(m.start(), m.end(), _ikey(m.group())) for m in _INDIC_WORD_RE.finditer(text)]
    spans: list[Span] = []

    def adjacent(a: int, b: int) -> bool:
        return _INDIC_GAP_RE.match(text[words[a][1] : words[b][0]]) is not None

    for i, (start, end, key) in enumerate(words):
        if key in _INDIC_HONORIFICS or key in _INDIC_ROLE_CUES:
            forced = key in _INDIC_HONORIFICS
            j = i + 1
            while j < len(words) and j - i <= _INDIC_MAX_NAME_WORDS and adjacent(j - 1, j):
                if not (forced and j == i + 1) and (_indic_common(words[j][2]) or words[j][2] in _INDIC_ROLE_CUES):
                    break
                j += 1
            # "डॉ. आंबेडकर मार्ग": the run ends before (or holds) a place noun, so it names a place
            place = any(_indic_place_noun(words[t][2]) for t in range(i + 1, min(j + 1, len(words)))
                        if t == i + 1 or adjacent(t - 1, t))
            if j > i + 1 and not (forced and place):
                spans.append(Span(words[i + 1][0], words[j - 1][1], "name", "name:indic_cue"))
        elif (key in _INDIC_ADDRESS and i > 0 and adjacent(i - 1, i) and words[i - 1][2] not in _INDIC_ROLE_CUES
              and not _indic_common(words[i - 1][2]) and words[i - 1][2] not in _INDIC_ADDRESS):
            spans.append(Span(words[i - 1][0], words[i - 1][1], "name", "name:indic_address"))
        elif key not in _INDIC_ADDRESS and (m := _INDIC_BABU_RE.match(key)) and not _indic_common(m.group(1) or ""):
            spans.append(Span(start, end, "name", "name:indic_babu"))
    return spans


def _person_spans(text: str, protect: frozenset[str], w: _Words | None = None) -> list[Span]:
    """Ages and names: the shared spans (cue spans run on), the local cue forms and age forms, the names right
    before ages and the cue-less names (:func:`_cueless_spans`). Unmerged."""
    w = w or _Words(text, protect)
    spans: list[Span] = []
    ages: list[Span] = []
    for s in ethics.pii_spans(text, protect=protect):
        if s.kind == "name":
            spans.append(Span(s.start, _run_on(text, s.end, w), "name", s.label))
        else:
            ages.append(Span(s.start, s.end, s.kind, s.label))
    for label, rx in _EXTRA_AGE_RES:
        ages.extend(Span(m.start(), m.end(), "age", label) for m in rx.finditer(text))
    spans.extend(ages)
    spans.extend(_local_cue_spans(text, protect, w))
    spans.extend(_before_age_spans(text, ages, w))
    spans.extend(_cueless_spans(text, w))
    spans.extend(_indic_cue_spans(text))
    return spans


def _script_spans(text: str) -> list[Span]:
    """Indic-script words no rule here can read for names (:func:`osint_common.ethics.unredactable_spans`):
    withheld as ``[WITHHELD]`` in every tier (F-HONEST OSINT-2; no Indic NER runs at parse)."""
    return [Span(s.start, s.end, "script", s.label) for s in ethics.unredactable_spans(text)]


def _learned_spans(text: str, learned: Iterable[str], w: _Words) -> list[Span]:
    spans: list[Span] = []
    for name in sorted(set(learned), key=len, reverse=True):
        parts = name.split()
        if len(parts) < 2:
            continue
        # case-insensitive: a document may repeat the name in lower case (a hashtag, a slug-like headline)
        rx = re.compile(
            r"(?<![A-Za-z])" + r"\s+".join(re.escape(p) for p in parts) + r"(?![A-Za-z])", re.IGNORECASE
        )
        for m in rx.finditer(text):
            first = w.index.get(m.start(), -1)
            if first >= 0 and all(_covered(w.words, first + n, w.multi, w.longest) for n in range(len(parts))):
                continue  # the same words form a gazetteer place here
            spans.append(Span(m.start(), m.end(), "name", "learned"))
        # the surname alone, as a report refers back to the person ("<Given> <Surname>, 71, ... <Surname> taught"):
        # capitalised as written, in sentence-case copy only (in a Title-Case headline every word is capitalised, so
        # a word wrongly learned there would spread), never an ordinary, generic or gazetteer word
        last = parts[-1]
        if len(last) >= 4 and last.isalpha() and last[0].isupper():
            for m in re.finditer(r"(?<![A-Za-z])" + re.escape(last) + r"(?![A-Za-z])", text):
                if _CAP_WORD_BEFORE_RE.search(text, 0, m.start()) or _CAP_WORD_AFTER_RE.match(text, m.end()):
                    continue
                if not w.plain(last, m.start(), HEADLINE_WORDS):
                    spans.append(Span(m.start(), m.end(), "name", "learned_surname"))
    return spans


#: A capitalised word right before / after a position (only spaces between): a Title-Case context.
_CAP_WORD_BEFORE_RE = re.compile(r"[A-Z][a-z]+[ \t]+$")
_CAP_WORD_AFTER_RE = re.compile(r"[ \t]+[A-Z][a-z]+")


# ── Reddit users (every tier) and URLs (every tier but official) ──────────────────────────────────────────────


def _url_matches(text: str) -> Iterable[tuple[int, int]]:
    for m in URL_RE.finditer(text):
        start, end = m.start(), m.end()
        while end > start and text[end - 1] in _URL_TRAIL:
            end -= 1  # sentence punctuation after a URL is not part of it
        if end - start >= 4:
            yield start, end


def _url_spans(text: str, *, reddit_users_only: bool = False) -> list[Span]:
    """Every URL: a Reddit user page → a ``name`` span, any other → a ``url`` span (dropped when
    ``reddit_users_only``: the official tier keeps its URLs, never a Reddit user page)."""
    spans: list[Span] = []
    for start, end in _url_matches(text):
        if REDDIT_USER_URL_RE.search(text[start:end]):
            spans.append(Span(start, end, "name", "reddit_user_url"))
        elif not reddit_users_only:
            spans.append(Span(start, end, "url", "url"))
    return spans


def _reddit_user_spans(text: str) -> list[Span]:
    """Reddit user mentions and user pages, in every tier (module docstring, rule 3): what
    :func:`has_poster_handle` reads in any tier, even where :data:`URL_RE` reads no URL ("@reddit.com/u/<name>").
    A user page inside a URL is widened to the whole URL by :func:`_url_spans` and :func:`_merge`."""
    spans = [Span(m.start(), m.end(), "name", "handle") for m in HANDLE_RE.finditer(text)]
    for m in REDDIT_USER_URL_RE.finditer(text):
        tail = _REDDIT_USER_TAIL_RE.match(text, m.end())
        spans.append(Span(m.start(), tail.end() if tail else m.end(), "name", "reddit_user_url"))
    return spans


def has_url(text: str | None) -> bool:
    """Is a URL (as :data:`URL_RE` reads one) left in ``text``? (The parity checks: never in a non-official text.)"""
    return bool(text) and any(True for _ in _url_matches(text or ""))


def _platform_handles(text: str) -> Iterable[re.Match[str]]:
    """Platform-cue handles, without what follows a cue and is no handle: an ordinary or generic word ("insta:
    link in bio", "fb page: Mumbai ...")."""
    for m in PLATFORM_HANDLE_RE.finditer(text):
        low = m.group("h").lower()
        if low not in COMMON_WORDS and low not in _NOT_HANDLES and low not in ethics.GENERIC_PLACE_WORDS:
            yield m


def has_poster_handle(text: str | None, tier: str) -> bool:
    """Is a poster handle left in ``text``? A Reddit user mention or page in any tier (the redactor removes both in
    every tier, so an emitted signal never has one); a social-platform profile link in any tier but ``official``
    (an official alert may link its office's own account); an ``@<name>`` mention or a platform-cue handle
    ("insta: <handle>") in a social post (in news an ``@``-account is usually an outlet's or an office's)."""
    if not text:
        return False
    if HANDLE_RE.search(text) or REDDIT_USER_URL_RE.search(text):
        return True
    if tier != _OFFICIAL and PROFILE_URL_RE.search(text):
        return True
    if tier == _SOCIAL:
        return AT_HANDLE_RE.search(text) is not None or next(iter(_platform_handles(text)), None) is not None
    return False


# ── the social tier ───────────────────────────────────────────────────────────────────────────────────────────


def _joins(gap: str, after_initial: bool) -> bool:
    """Does ``gap`` keep two name tokens in one run? Whitespace; nothing after an initial ("R.K.<Surname>"); a bare
    hyphen ("<Given>-<Surname>"; a spaced " - " is a separator); or a lower-case name particle between spaces
    ("<Given> de <Surname>")."""
    if not gap:
        return after_initial
    if gap.isspace() or gap == "-":
        return True
    return gap[0].isspace() and gap[-1].isspace() and gap.strip() in _NAME_PARTICLES


def _token_groups(text: str) -> list[list[re.Match[str]]]:
    """Name tokens joined into runs (see :func:`_joins`)."""
    groups: list[list[re.Match[str]]] = []
    cur: list[re.Match[str]] = []
    for t in _NAME_TOKEN_RE.finditer(text):
        if cur and not _joins(text[cur[-1].end() : t.start()], cur[-1].group("init") is not None):
            groups.append(cur)
            cur = []
        cur.append(t)
    if cur:
        groups.append(cur)
    return groups


def _social_spans(text: str, w: _Words) -> list[Span]:
    spans: list[Span] = []
    # Reddit user mentions are redacted in every tier (redaction_spans); here only the social-tier forms
    for rx, kind, rule in ((AT_HANDLE_RE, "name", "at_handle"),
                           (_EMAIL_RE, "contact", "email"), (_PHONE_RE, "contact", "phone")):
        spans.extend(Span(m.start(), m.end(), kind, rule) for m in rx.finditer(text))
    spans.extend(Span(m.start("h"), m.end("h"), "name", "platform_handle") for m in _platform_handles(text))
    # a poster's age and sex shorthand ("F(28)", "22M", "27/F") is a self-description: never stored (OSINT-6)
    spans.extend(Span(m.start(), m.end(), "age", "social:age_sex") for m in _AGE_SEX_RE.finditer(text))
    # a single given name after a social cue ("my neighbour <Given>", "contact <Given>") or before an address
    # term ("<Given> bhai"): the capitalised-run rule below needs two words
    for rx in (_SOCIAL_NAME_CUE_RE, _SOCIAL_ADDRESS_RE):
        for m in rx.finditer(text):
            if not _not_name(m.group("name"), m.start("name"), w):
                spans.append(Span(m.start("name"), m.end("name"), "name", "social:single_name"))
    generic = ethics.GENERIC_PLACE_WORDS
    for group in _token_groups(text):
        if len(group) < 2 or not any(t.group("word") for t in group):
            continue  # a run is two name tokens or more (the PoC's bigram rule), one of them a word
        # each word is judged on its own: a place noun ("Road", "Club") is kept, never the name before it
        safe = [
            t.group("word") is not None
            and (t.group("word").lower() in COMMON_WORDS or t.group("word").lower() in generic or w.covered(t.start()))
            for t in group
        ]
        k = 0
        while k < len(group):
            if safe[k]:
                k += 1
                continue
            end = k
            while end + 1 < len(group) and not safe[end + 1]:
                end += 1
            stretch = group[k : end + 1]
            words = [t.group("word") for t in stretch if t.group("word")]
            # initials alone ("B. T." before "Road") and a lone gazetteer alias ("Visit Matunga") are kept
            if words and not (len(stretch) == 1 and words[0].lower() in w.single):
                spans.append(Span(stretch[0].start(), stretch[-1].end(), "name", "social:capitalised"))
            k = end + 1
    return spans


# ── redaction ─────────────────────────────────────────────────────────────────────────────────────────────────


def _merge(spans: list[Span]) -> list[Span]:
    """Sorted, non-overlapping spans. Overlapping spans are joined into one (a ``name`` when either is), so a span
    that starts inside another never leaves its tail behind: in "@Fictus Dummyvala" the handle and the capitalised
    run overlap, and dropping the run would keep the surname."""
    spans = sorted(spans, key=lambda s: (s.start, -(s.end - s.start)))
    out: list[Span] = []
    for s in spans:
        if out and s.start < out[-1].end:
            last = out[-1]
            if s.end > last.end:
                kind = next((k for k in ("name", "script") if k in (last.kind, s.kind)), last.kind)
                out[-1] = Span(last.start, s.end, kind, last.rule)
            continue
        out.append(s)
    return out


def redaction_spans(
    text: str, tier: str, protect: frozenset[str], *, learned: Iterable[str] = (), extra: Iterable[Span] = ()
) -> list[Span]:
    """The spans one redaction pass replaces in ``text`` (sorted, non-overlapping). ``extra`` adds spans found
    elsewhere for this exact text (the optional model check, rule 7): they only ever add to the rules."""
    if not text:
        return []
    w = _Words(text, protect)
    spans = _person_spans(text, protect, w)
    spans.extend(s for s in extra if 0 <= s.start < s.end <= len(text) and s.kind in _TOKENS)
    spans.extend(_learned_spans(text, learned, w))
    # a Reddit user mention or page is a poster handle in every tier (rule 3); other URLs only outside official
    spans.extend(_reddit_user_spans(text))
    spans.extend(_url_spans(text, reddit_users_only=tier == _OFFICIAL))
    spans.extend(_script_spans(text))
    if tier == _SOCIAL:
        spans.extend(_social_spans(text, w))
    return _merge(spans)


def _apply(text: str, spans: list[Span]) -> str:
    """Replace ``spans`` (sorted, non-overlapping) right to left. The single place a redaction is written."""
    out = text
    for s in reversed(spans):
        out = out[: s.start] + _TOKENS[s.kind] + out[s.end :]
    return out


def redact_persons(
    text: str, tier: str, protect: frozenset[str], *, learned: Iterable[str] = (), extra: Iterable[Span] = ()
) -> tuple[str, int]:
    """``(redacted_text, n_redactions)``: names → ``[PERSON]``, ages → ``[AGE]`` (module docstring).

    The result always passes ``osint_common.ethics.find_pii`` (the passes repeat until no span is left), as the
    contract validates it: with the shared gazetteer alone. This service's protect-set also holds the city pack, so
    a place the shared gazetteer does not hold yet, after a residence cue ("resident of <place>"), is redacted by a
    last pass rather than refused at validation (stricter, never laxer).
    ``learned`` adds names a cue introduced elsewhere in the same document (see :class:`DocumentRedactor`).
    ``extra`` adds spans for ``text`` as given (the model check, rule 7); they join the first pass only.
    """
    if not text:
        return text, 0
    learned = tuple(learned)
    pending = tuple(extra)
    out, n = text, 0
    for _ in range(_MAX_PASSES):
        spans = redaction_spans(out, tier, protect, learned=learned, extra=pending)
        pending = ()
        if not spans:
            break
        out = _apply(out, spans)
        n += len(spans)
    for _ in range(_MAX_PASSES):
        left = [Span(s.start, s.end, s.kind if s.kind == "age" else "name", s.label) for s in ethics.pii_spans(out)]
        if not left:
            break
        out = _apply(out, left)
        n += len(left)
    return out, n


class DocumentRedactor:
    """Redaction for one feed document: :meth:`learn` every item first, then :meth:`redact` each one.

    Names are kept in memory for this object's life (one ``parse()``), never stored, returned or logged.
    """

    def __init__(self, tier: str, protect: frozenset[str]) -> None:
        self.tier = tier
        self.protect = protect
        self._names: set[str] = set()

    def learn(self, *texts: str | None) -> None:
        multi, _single, _longest = _phrase_index(self.protect)
        for text in texts:
            if not text:
                continue
            for s in _person_spans(text, self.protect):
                if s.kind != "name":
                    continue
                name = _norm_ws(text[s.start : s.end])
                if len(name.split()) >= 2 and norm_phrase(name) not in multi:
                    self._names.add(name)

    @property
    def learned_count(self) -> int:
        return len(self._names)

    def redact(self, text: str, extra: Iterable[Span] = ()) -> tuple[str, int]:
        return redact_persons(text, self.tier, self.protect, learned=self._names, extra=extra)
