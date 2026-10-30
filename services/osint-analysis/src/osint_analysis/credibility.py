"""Independence-aware credibility and an honest verification state (OSINT SPEC §1.5, §4 "credibility").

Credibility rises ONLY on independent corroboration:

* the base is the strongest member prior (``credibility_prior``: official 0.95, news 0.60, social 0.25);
* **cross-type** corroboration — members of more than one trust type (official, news, social; every news tier,
  wire, regional, aggregator or archive, is one type) — adds :data:`CROSS_TYPE_BUMP` per extra type;
* **cross-publisher within a type** adds :data:`PUBLISHER_BUMP` per extra independent publisher of the same type,
  capped at :data:`PUBLISHER_BUMP_CAP` in all;
* independence is judged by the RESOLVED publisher domain (:func:`resolve_publisher`: the registrable domain, so
  ``m.``/``www.`` and sub-sites of one outlet are one publisher; a community stays ``host/r/<name>``) and the trust
  type, NEVER by a URL or a URL prefix: an aggregator's links all share its host, and one outlet's links differ
  by path, so a URL proves nothing. A member without a resolved publisher adds no publisher independence;
* a single social source is capped at :data:`SINGLE_SOCIAL_CAP` (0.30), and so is a social-only situation from
  one community, however many posts it has;
* **cross-posts are one source** (orchestrator decision, OS-4 round 4): the posts of one community are one source,
  and two communities are one source when a post of one is a near-duplicate of a post of the other
  (:func:`near_duplicate`: the same text posted twice may be one poster). Independence between social sources
  is therefore only ever shown by posts whose texts are NOT near-duplicates (:func:`social_sources`);
* **syndicated copies are one source** (F-HONEST OSINT-4): the same rule across every news tier. One wire story
  carried by N outlets (a PTI text, an aggregator's copy) is one source, so it neither raises credibility nor
  shows as "N independent publishers" (:func:`news_sources`);
* the result never exceeds :data:`CREDIBILITY_CEILING` (0.99): certainty is an officer's call (``CONFIRMED``).

The verification state is ``OFFICIAL-VERIFIED`` when an official member exists, else ``NEWS-REPORTED`` with a
news member, else ``UNVERIFIED-OSINT``; a member counts at the LOWER of what its tier and its provenance label
say. ``SIMULATED`` and ``EMULATED`` inputs pass through unchanged and are never upgraded: their state stays, their
credibility is the base prior with no corroboration bump, and they never claim cross-type corroboration (fusion
keeps them in their own partitions, so they never mix with real reports).

The Western Express Highway case (two aggregator publishers) scores 0.60 → 0.65, ``NEWS-REPORTED``.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType

from osint_common.types import RawOsintSignal

__all__ = [
    "CREDIBILITY_CEILING",
    "CROSS_POST_JACCARD",
    "CROSS_POST_MIN_TOKENS",
    "CROSS_TYPE_BUMP",
    "PUBLISHER_BUMP",
    "PUBLISHER_BUMP_CAP",
    "SINGLE_SOCIAL_CAP",
    "TIER_TYPES",
    "Credibility",
    "member_state",
    "near_duplicate",
    "news_sources",
    "post_views",
    "resolve_publisher",
    "score",
    "social_sources",
    "verification_state",
]

#: Trust type of each source tier.
TIER_TYPES: Mapping[str, str] = MappingProxyType(
    {
        "official": "official",
        "news_wire": "news",
        "news_regional": "news",
        "aggregator": "news",
        "archive": "news",
        "social_unverified": "social",
    }
)
_TYPE_ORDER = {"official": 0, "news": 1, "social": 2}
_TYPE_STATE = {"official": "OFFICIAL-VERIFIED", "news": "NEWS-REPORTED", "social": "UNVERIFIED-OSINT"}
_STATE_RANK = {"UNVERIFIED-OSINT": 0, "NEWS-REPORTED": 1, "OFFICIAL-VERIFIED": 2}
_PASS_THROUGH = ("EMULATED", "SIMULATED")

CROSS_TYPE_BUMP = 0.15
PUBLISHER_BUMP = 0.05
PUBLISHER_BUMP_CAP = 0.10
SINGLE_SOCIAL_CAP = 0.30
CREDIBILITY_CEILING = 0.99
#: Two social posts are near-duplicates when the token Jaccard of their titles, or of their whole texts, is at least
#: this. Same-situation reports from independent writers score 0.15-0.65 (the Stage-1 calibration); a cross-post
#: scores 1.0, and a one-word edit of a seven-word post 0.75.
CROSS_POST_JACCARD = 0.75
#: ... or when EVERY token of the shorter view, at least this many, is in the other's: a cross-post that kept the
#: text and added or dropped a line (a Reddit cross-post often carries the title only, the original its body too).
CROSS_POST_MIN_TOKENS = 3
#: Cross-post markers and community mentions say nothing about the situation ("x-post from r/<name>").
_CROSS_POST_MARKERS = re.compile(r"\b(?:x-?post(?:ed)?|cross-?post(?:ed)?)\b|(?<![\w/])/?\br/\w+", re.IGNORECASE)

#: Second-level public suffixes under which the registrable domain has three labels (``ndma.gov.in``).
_TWO_LEVEL_SUFFIXES: frozenset[str] = frozenset(
    {
        "ac.in", "co.in", "edu.in", "firm.in", "gen.in", "gov.in", "ind.in", "net.in", "nic.in", "org.in",
        "res.in", "ac.uk", "co.uk", "gov.uk", "org.uk", "com.au", "net.au", "org.au", "co.nz", "com.sg",
        "com.pk", "com.bd", "com.np", "com.lk", "co.jp", "com.br",
    }
)
_HOST_PREFIXES = ("www.", "m.", "amp.", "mobile.")


def resolve_publisher(publisher: str | None) -> str | None:
    """The independence key of a publisher: its registrable domain (``city.news-c.example`` → ``news-c.example``,
    ``m.news-a.example`` → ``news-a.example``, ``sachet.ndma.gov.in`` → ``ndma.gov.in``), or
    ``host/r/<community>`` (lower-case) for a community. ``None`` when there is no publisher."""
    if not publisher or not publisher.strip():
        return None
    host, sep, path = publisher.strip().lower().partition("/")
    changed = True
    while changed:
        changed = False
        for prefix in _HOST_PREFIXES:
            if host.startswith(prefix) and host.count(".") > 1:
                host, changed = host[len(prefix) :], True
    labels = [x for x in host.split(".") if x]
    if len(labels) >= 3 and ".".join(labels[-2:]) in _TWO_LEVEL_SUFFIXES:
        registrable = ".".join(labels[-3:])
    elif len(labels) >= 2:
        registrable = ".".join(labels[-2:])
    else:
        registrable = host
    if sep and path.startswith("r/") and len(path) > 2:
        return f"{registrable}/{path.rstrip('/')}"
    return registrable


def post_views(signal: RawOsintSignal) -> tuple[frozenset[str], frozenset[str]]:
    """The two views :func:`near_duplicate` compares: the content tokens of a post's title, and of its title and
    text (the Stage-1 tokens, :func:`osint_analysis.fusion.text_tokens`: handles, stop words, the post's own
    community name and the redaction tokens removed, number words as digits, lightly stemmed), with cross-post
    markers and community mentions removed first."""
    from osint_analysis.fusion import publisher_words, text_tokens  # deferred: fusion imports TIER_TYPES from here

    drop = publisher_words(signal)
    title = _CROSS_POST_MARKERS.sub(" ", signal.title or "")
    whole = _CROSS_POST_MARKERS.sub(" ", f"{signal.title} {signal.text}")
    return text_tokens(title, drop), text_tokens(whole, drop)


def _near(a: frozenset[str], b: frozenset[str]) -> bool:
    if not a or not b:
        return False
    inter = len(a & b)
    if inter / (len(a) + len(b) - inter) >= CROSS_POST_JACCARD:
        return True
    smaller = min(len(a), len(b))
    return smaller >= CROSS_POST_MIN_TOKENS and inter == smaller


def near_duplicate(
    a: RawOsintSignal | tuple[frozenset[str], frozenset[str]], b: RawOsintSignal | tuple[frozenset[str], frozenset[str]]
) -> bool:
    """Whether two posts are near-duplicates, so possibly one poster's cross-post: their titles, or their whole
    texts, have token Jaccard >= :data:`CROSS_POST_JACCARD`, or one's tokens (at least
    :data:`CROSS_POST_MIN_TOKENS`) all appear in the other's. Takes signals or their :func:`post_views`."""
    va = a if isinstance(a, tuple) else post_views(a)
    vb = b if isinstance(b, tuple) else post_views(b)
    return any(_near(x, y) for x, y in zip(va, vb, strict=True))


def social_sources(signals: Sequence[RawOsintSignal]) -> list[str]:
    """The independent social sources among ``signals``, each named by its smallest community key (sorted). The
    posts of one community are one source; two communities are one source when any post of one is a
    :func:`near_duplicate` of any post of the other (transitively: a cross-post chain is one source). A post
    without a resolved publisher adds no source, as everywhere in this module."""
    return _independent_sources(signals, "social")


def news_sources(signals: Sequence[RawOsintSignal]) -> list[str]:
    """The independent news sources among ``signals`` (every news tier: wire, regional, aggregator, archive), each
    named by its smallest publisher key (sorted). The reports of one publisher are one source, and two publishers
    are one source when a report of one is a :func:`near_duplicate` of a report of the other: one wire story
    syndicated by N outlets is ONE source, not N independent publishers (F-HONEST OSINT-4). Independent writers on
    one incident score 0.15-0.65 (the Stage-1 calibration) and stay apart."""
    return _independent_sources(signals, "news")


def _independent_sources(signals: Sequence[RawOsintSignal], trust_type: str) -> list[str]:
    by_community: dict[str, list[RawOsintSignal]] = defaultdict(list)
    for s in signals:
        if TIER_TYPES[s.source_tier] == trust_type and (key := resolve_publisher(s.publisher)) is not None:
            by_community[key].append(s)
    communities = sorted(by_community)
    if len(communities) < 2:
        return communities
    # each community's distinct views once (a community re-posting one text is compared once)
    views = {k: list(dict.fromkeys(post_views(s) for s in by_community[k])) for k in communities}
    parent = list(range(len(communities)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(len(communities)):
        for j in range(i + 1, len(communities)):
            ri, rj = find(i), find(j)
            if ri == rj:
                continue
            if any(near_duplicate(x, y) for x in views[communities[i]] for y in views[communities[j]]):
                parent[max(ri, rj)] = min(ri, rj)
    return sorted({communities[find(i)] for i in range(len(communities))})


def member_state(signal: RawOsintSignal) -> str:
    """A member's own verification level: the lower of its tier's and its label's (pass-through kept)."""
    label = signal.provenance_label
    if label in _PASS_THROUGH:
        return label
    tier_state = _TYPE_STATE[TIER_TYPES[signal.source_tier]]
    if label not in _STATE_RANK:  # pragma: no cover - every ProvenanceLabel is ranked or passed through
        return "UNVERIFIED-OSINT"
    return min(tier_state, label, key=_STATE_RANK.__getitem__)


def verification_state(signals: Sequence[RawOsintSignal]) -> str:
    """``OFFICIAL-VERIFIED`` with an official member, else ``NEWS-REPORTED`` with a news member, else
    ``UNVERIFIED-OSINT``; ``EMULATED`` / ``SIMULATED`` inputs keep their label and are never upgraded."""
    states = {member_state(s) for s in signals}
    for passed in _PASS_THROUGH:
        if passed in states:
            return passed
    for state in ("OFFICIAL-VERIFIED", "NEWS-REPORTED"):
        if state in states:
            return state
    return "UNVERIFIED-OSINT"


@dataclass(frozen=True, slots=True)
class Credibility:
    """The corroboration summary of a situation."""

    credibility: float
    verification_state: str
    #: distinct source tiers, sorted
    source_tiers: tuple[str, ...]
    #: distinct trust types (official, news, social), in that order
    source_types: tuple[str, ...]
    #: independent sources across all members: distinct resolved publishers, social communities joined by
    #: cross-posts and news publishers joined by syndicated copies counted once (:func:`social_sources`,
    #: :func:`news_sources`)
    independent_publishers: int
    cross_type_corroborated: bool
    #: distinct provenance labels of the members, sorted
    labels: tuple[str, ...]


def score(signals: Sequence[RawOsintSignal]) -> Credibility:
    """Score a situation's member signals (see the module docstring for every rule)."""
    if not signals:
        raise ValueError("a situation has at least one member signal")
    tiers = tuple(sorted({s.source_tier for s in signals}))
    types = tuple(sorted({TIER_TYPES[t] for t in tiers}, key=_TYPE_ORDER.__getitem__))
    publishers: dict[str, set[str]] = defaultdict(set)
    for s in signals:
        key = resolve_publisher(s.publisher)
        if key is not None and TIER_TYPES[s.source_tier] == "official":
            publishers["official"].add(key)
    sources = social_sources(signals)  # cross-posts are one source
    if sources:
        publishers["social"] = set(sources)
    syndicated = news_sources(signals)  # syndicated copies are one source (OSINT-4)
    if syndicated:
        publishers["news"] = set(syndicated)
    independent = len(set().union(*publishers.values())) if publishers else 0
    base = max(float(s.credibility_prior) for s in signals)
    state = verification_state(signals)
    labels = tuple(sorted({s.provenance_label for s in signals}))
    social_only = types == ("social",)
    # the social cap is an ethics rule: it holds in every realm, simulated and emulated included
    capped = social_only and (len(signals) == 1 or independent <= 1)
    if state in _PASS_THROUGH:
        cred = min(base, SINGLE_SOCIAL_CAP) if capped else base
        return Credibility(round(cred, 3), state, tiers, types, independent, False, labels)
    if len(signals) == 1:
        cred = min(base, SINGLE_SOCIAL_CAP) if social_only else base
    elif capped:
        cred = min(base, SINGLE_SOCIAL_CAP)
    else:
        bump = CROSS_TYPE_BUMP * (len(types) - 1)
        extra_publishers = sum(max(0, len(p) - 1) for p in publishers.values())
        bump += min(PUBLISHER_BUMP_CAP, PUBLISHER_BUMP * extra_publishers)
        cred = base + bump
    cred = round(min(CREDIBILITY_CEILING, max(0.0, cred)), 3)
    return Credibility(cred, state, tiers, types, independent, len(types) >= 2, labels)
