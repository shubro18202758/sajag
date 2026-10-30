"""The OSINT vocabulary every WP shares: event kinds (contract C3 lockstep), verification states, source kinds,
the situation classes of the PoC classifier, related-class pairs, response priorities and per-source priors.

Each tuple here equals the ``Literal`` of the same name in :mod:`osint_common.types` (tests pin it). The order of
:data:`ALL_EVENT_KINDS` is the order of ``traffic_oracle.events.EVENT_KINDS``.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from pydantic import BaseModel, ConfigDict, Field, field_validator

__all__ = [
    "ACTUATING_VERBS",
    "ALL_EVENT_KINDS",
    "ANCHOR_VERBS",
    "EVENT_CLASSES",
    "EVENT_CLASS_NAMES",
    "AREA_DISTRICTS",
    "AREA_STATE_CODE",
    "AREA_STATE_CODE_MAHARASHTRA",
    "CITY_DISTRICTS",
    "GDELT_ADM1_MAHARASHTRA",
    "GDELT_ADM1_WEST_BENGAL",
    "INCIDENT_CLASSES",
    "INCIDENT_KINDS",
    "LEGACY_EVENT_KINDS",
    "NEW_EVENT_KINDS",
    "OPERATIONAL_CLASSES",
    "OSINT_EVENT_KINDS",
    "PROVENANCE_LABELS",
    "RELATED_CLASSES",
    "RESPONSE_PRIORITY",
    "SOURCE_KINDS",
    "SOURCE_NAMES",
    "SOURCE_PRIORS",
    "SOURCE_TIERS",
    "SourcePrior",
    "VERIFICATION_STATES",
]

# ── Corridor event kinds (C3 lockstep: migration 021 CHECKs, traffic_oracle.events.EVENT_KINDS, the emulator's
#    profiles.EVENT_KINDS, the deck's ops/types.ts EventKind and ops/client.ts KINDS) ──────────────────────────────

#: The ten kinds before migration 021 (007's eight archetypes + 010's crime_incident and vehicle_pursuit).
LEGACY_EVENT_KINDS: tuple[str, ...] = (
    "protected_movement",
    "procession",
    "mass_gathering",
    "race",
    "ceremonial",
    "egress_surge",
    "emergency_evacuation",
    "work_zone",
    "crime_incident",
    "vehicle_pursuit",
)

#: The six reported-situation kinds of migration 021: a REPORTED situation geo-tagged for RESPONSE. Reported crime
#: is ``reported_crime`` here and never ``crime_incident`` (ANPR/watchlist origin).
NEW_EVENT_KINDS: tuple[str, ...] = (
    "reported_crime",
    "public_disorder",
    "road_accident",
    "hazard",
    "flooding",
    "infra_failure",
)

#: All sixteen, in ``traffic_oracle.events.EVENT_KINDS`` order.
ALL_EVENT_KINDS: tuple[str, ...] = LEGACY_EVENT_KINDS + NEW_EVENT_KINDS

#: The kinds an OSINT situation may carry (``osint.resolved_events`` CHECK, ``Classification.sajag_event_kind``):
#: all but ``crime_incident`` (ANPR/watchlist origin only) and ``vehicle_pursuit`` (human-initiated only).
OSINT_EVENT_KINDS: tuple[str, ...] = tuple(k for k in ALL_EVENT_KINDS if k not in ("crime_incident", "vehicle_pursuit"))

#: ``traffic.incidents.incident_kind`` as relaxed by migration 021 (004 + 007 + road_rage, robbery, public_disorder).
INCIDENT_KINDS: tuple[str, ...] = (
    "congestion_spike",
    "route_blockage",
    "signal_failure",
    "protest",
    "accident",
    "weather",
    "vvip_hold",
    "other",
    "crowd_surge",
    "egress_surge",
    "ambulance_hold",
    "work_zone",
    "road_rage",
    "robbery",
    "public_disorder",
)

#: The honest labels (021 CHECKs on corridor_events and osint.resolved_events). ``CONFIRMED`` is reserved: nothing
#: in this programme sets it (plan R29).
VERIFICATION_STATES: tuple[str, ...] = (
    "EMULATED",
    "SIMULATED",
    "UNVERIFIED-OSINT",
    "NEWS-REPORTED",
    "OFFICIAL-VERIFIED",
    "CONFIRMED",
)

#: ``events.corridor_events.source_kind`` (021): who created the event.
SOURCE_KINDS: tuple[str, ...] = ("operator", "brain", "emulator", "osint")

# ── Sources ───────────────────────────────────────────────────────────────────────────────────────────────────────

#: The connector ids. Three keep the names of the Kolkata pack's official connectors (``kmc_scrape``,
#: ``wbsdma``, ``mumbai_police_scrape``) because the connectors, the oracle's trust boundary and migration 021
#: CHECKs key on them; Mumbai's official sources (BMC 1916 disaster-control notices, Maharashtra SDMA, Mumbai
#: Traffic Police advisories) reach Sajag through SACHET CAP and IMD (``sachet_cap``, ``imd``) and the news feeds.
SOURCE_NAMES: tuple[str, ...] = (
    "gdelt_events",
    "gdelt_doc",
    "google_news_rss",
    "news_rss",
    "sachet_cap",
    "imd",
    "kmc_scrape",
    "wbsdma",
    "mumbai_police_scrape",
    "common_crawl",
    "reddit_rss",
)

SOURCE_TIERS: tuple[str, ...] = (
    "official",
    "news_wire",
    "news_regional",
    "aggregator",
    "archive",
    "social_unverified",
)

PROVENANCE_LABELS: tuple[str, ...] = (
    "OFFICIAL-VERIFIED",
    "NEWS-REPORTED",
    "UNVERIFIED-OSINT",
    "SIMULATED",
    "EMULATED",
)

#: GDELT ``ActionGeo_ADM1Code`` for Maharashtra. GDELT ADM1 codes are FIPS 10-4, and Maharashtra is ``IN16`` (the
#: census code 27 is not GDELT's). A state code is never a Mumbai location: it only scopes a signal to the state.
GDELT_ADM1_MAHARASHTRA = "IN16"

#: The state-level admin code for an alert or report that names Maharashtra but no Mumbai district (a state-wide
#: nowcast for the ghats, Pune or Konkan districts). Never a point.
AREA_STATE_CODE_MAHARASHTRA = "LGD:MAHARASHTRA"

#: The Kolkata pack's state codes (the second city pack): GDELT's FIPS 10-4 ``IN28`` for West Bengal (plan R28) and
#: the state-level admin code a connector writes for a West Bengal alert naming no metro district. The names stay
#: because osint-ingress and osint-geo import them; :data:`AREA_STATE_CODE` is still the West Bengal code until
#: those packages move to :data:`AREA_STATE_CODE_MAHARASHTRA`.
GDELT_ADM1_WEST_BENGAL = "IN28"
AREA_STATE_CODE = "LGD:WEST_BENGAL"

#: The city districts a connector may name as an admin code (``RawGeoHint.admin_codes``), with the names and
#: spellings (English, Marathi, Hindi) that identify each one in an alert's area text. Mumbai's two revenue
#: districts come first: Mumbai City (the island city, Colaba to Mahim and Sion) and Mumbai Suburban (Bandra to
#: Dahisar and Kurla to Mulund), together the BMC area (``cities/mumbai/city.json``). The Kolkata pack's metro
#: districts follow (the second city pack): Kolkata and Howrah are city districts; North and South 24 Parganas hold
#: city areas but also the Sundarbans, so an alert naming only the district carries no point. The spellings are
#: matched after NFKC (so a nukta letter written as one code point or as letter + nukta is the same letter).
AREA_DISTRICTS: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        "LGD:MUMBAI": ("mumbai", "bombay", "greater mumbai", "brihanmumbai", "mumbai city", "मुंबई", "मुम्बई",
                       "बृहन्मुंबई", "मुंबई शहर"),
        "LGD:MUMBAI_SUBURBAN": ("mumbai suburban", "mumbai suburbs", "मुंबई उपनगर", "मुंबई उपनगरीय"),
        "LGD:KOLKATA": ("kolkata", "calcutta", "কলকাতা", "कोलकाता"),
        "LGD:HOWRAH": ("howrah", "হাওড়া", "हावड़ा"),
        "LGD:NORTH_24_PARGANAS": (
            "north 24 parganas", "north twenty four parganas", "উত্তর ২৪ পরগনা", "উত্তর চব্বিশ পরগনা",
            "उत्तर 24 परगना",
        ),
        "LGD:SOUTH_24_PARGANAS": (
            "south 24 parganas", "south twenty four parganas", "দক্ষিণ ২৪ পরগনা", "দক্ষিণ চব্বিশ পরগনা",
            "दक्षिण 24 परगना",
        ),
    }
)


#: The two districts of the city this deployment serves (Mumbai): the BMC area, in :data:`AREA_DISTRICTS` order.
CITY_DISTRICTS: tuple[str, ...] = ("LGD:MUMBAI", "LGD:MUMBAI_SUBURBAN")


class SourcePrior(BaseModel):
    """A source's base trust, set by connector type (OSINT_SOURCES.md §6): never trusted from a payload (plan R26).

    Read it either way: ``SOURCE_PRIORS[s].tier`` or, as X18 writes the value, the mapping style
    ``SOURCE_PRIORS[s]["tier"]`` (also ``dict(SOURCE_PRIORS[s])`` and ``{**SOURCE_PRIORS[s]}``). It is frozen.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    tier: str
    provenance_label: str
    credibility_prior: float = Field(ge=0.0, le=1.0)
    license: str
    redistributable: bool

    def keys(self) -> tuple[str, ...]:
        """The field names, in declaration order (the mapping protocol)."""
        return tuple(type(self).model_fields)

    def __getitem__(self, key: str) -> object:
        """``prior["tier"]`` is ``prior.tier``; an unknown key is a ``KeyError``."""
        if key not in type(self).model_fields:
            raise KeyError(key)
        return getattr(self, key)

    @field_validator("tier")
    @classmethod
    def _tier(cls, v: str) -> str:
        if v not in SOURCE_TIERS:
            raise ValueError(f"tier must be one of {SOURCE_TIERS}")
        return v

    @field_validator("provenance_label")
    @classmethod
    def _label(cls, v: str) -> str:
        if v not in PROVENANCE_LABELS:
            raise ValueError(f"provenance_label must be one of {PROVENANCE_LABELS}")
        return v


def _prior(tier: str, label: str, credibility: float, license_: str, redistributable: bool) -> SourcePrior:
    return SourcePrior(
        tier=tier,
        provenance_label=label,
        credibility_prior=credibility,
        license=license_,
        redistributable=redistributable,
    )


#: Per-source priors: OSINT_SOURCES.md §6 and the PoC connectors (tier as the PoC sets it). The oracle re-derives
#: tier, label, prior, licence and redistributability from this table at its trust boundary (plan R26).
SOURCE_PRIORS: Mapping[str, SourcePrior] = MappingProxyType(
    {
        "gdelt_events": _prior("news_wire", "NEWS-REPORTED", 0.60, "gdelt_tos", True),
        "gdelt_doc": _prior("news_regional", "NEWS-REPORTED", 0.60, "gdelt_tos", True),
        # pointer layer only: Google News terms are personal use, so nothing is redistributed
        "google_news_rss": _prior("aggregator", "NEWS-REPORTED", 0.60, "google_news_personal_use", False),
        # Mumbai outlets' own RSS feeds (Marathi, English and Hindi): a pointer layer like Google News, read for our
        # own redacted headline and classification; the publisher's text is never re-served
        "news_rss": _prior("news_regional", "NEWS-REPORTED", 0.60, "publisher_rss_terms", False),
        # public domain; SDMA alerts reach Sajag through SACHET
        "sachet_cap": _prior("official", "OFFICIAL-VERIFIED", 0.95, "public_domain", True),
        # IMD's own CAP alerts (public domain; read from the WMO Alert Hub's mirror of the IMD feed)
        "imd": _prior("official", "OFFICIAL-VERIFIED", 0.95, "imd_terms", False),
        # the Kolkata pack's official page scrapes (municipal notices, the state SDMA page, the city police's
        # traffic advisories); Mumbai's official alerts arrive through SACHET and IMD
        "kmc_scrape": _prior("official", "OFFICIAL-VERIFIED", 0.90, "gov_scrape", False),
        "wbsdma": _prior("official", "OFFICIAL-VERIFIED", 0.95, "gov_scrape", False),
        "mumbai_police_scrape": _prior("official", "OFFICIAL-VERIFIED", 0.90, "gov_scrape", False),
        "common_crawl": _prior("archive", "NEWS-REPORTED", 0.50, "cc_common_crawl", False),
        # aggregate situational signal only; a single social post is never an event
        "reddit_rss": _prior("social_unverified", "UNVERIFIED-OSINT", 0.25, "reddit_api_terms", False),
    }
)

# ── Situation classes (the PoC classifier; OSINT SPEC §1.6) ───────────────────────────────────────────────────────

EVENT_CLASS_NAMES: tuple[str, ...] = (
    "reported_crime",
    "public_conflict",
    "road_accident",
    "fire",
    "urban_flooding",
    "infra_failure",
    "hazard",
    "public_gathering",
    "procession",
    "unrest",
    "road_closure",
    "weather_hazard",
    "general_news",
)

#: Classes that are real incidents (surfaced as events).
INCIDENT_CLASSES: frozenset[str] = frozenset(
    {
        "reported_crime",
        "public_conflict",
        "road_accident",
        "fire",
        "urban_flooding",
        "infra_failure",
        "hazard",
        "unrest",
        "weather_hazard",
    }
)

#: Planned or operational situations (surfaced as events too).
OPERATIONAL_CLASSES: frozenset[str] = frozenset({"public_gathering", "procession", "road_closure"})

#: Every class that may surface; ``general_news`` never does.
EVENT_CLASSES: frozenset[str] = INCIDENT_CLASSES | OPERATIONAL_CLASSES

#: Response priority (higher = more urgent): the primary class of a correlated situation.
RESPONSE_PRIORITY: Mapping[str, int] = MappingProxyType(
    {
        "infra_failure": 9,
        "fire": 9,
        "road_accident": 8,
        "public_conflict": 8,
        "urban_flooding": 7,
        "hazard": 7,
        "unrest": 6,
        "reported_crime": 6,
        "weather_hazard": 5,
        "public_gathering": 4,
        "procession": 3,
        "road_closure": 3,
        "general_news": 0,
    }
)

#: Related-class pairs whose co-located, time-overlapping clusters correlate into ONE situation (Stage 2).
RELATED_CLASSES: frozenset[frozenset[str]] = frozenset(
    {
        frozenset({"road_accident", "public_conflict"}),
        frozenset({"road_accident", "reported_crime"}),
        frozenset({"public_conflict", "reported_crime"}),
        frozenset({"public_conflict", "unrest"}),
        frozenset({"urban_flooding", "infra_failure"}),
        frozenset({"urban_flooding", "road_closure"}),
        frozenset({"urban_flooding", "weather_hazard"}),
        frozenset({"fire", "hazard"}),
        frozenset({"fire", "infra_failure"}),
        frozenset({"infra_failure", "road_closure"}),
        frozenset({"public_gathering", "public_conflict"}),
        frozenset({"public_gathering", "procession"}),
    }
)

# ── Decision support (C-U) ────────────────────────────────────────────────────────────────────────────────────────

#: COA verbs that act on the city: every one requires a named officer (C-U invariant).
ACTUATING_VERBS: frozenset[str] = frozenset({"signal_hold", "diversion", "dispatch", "escort_switch", "closure"})

#: COA verbs that need a road anchor (a segment or junction) and, on an unpromoted OSINT report, a corridor event:
#: approving them promotes the report first (C-U step 1); on an area-level subject they are infeasible up front.
ANCHOR_VERBS: frozenset[str] = frozenset({"dispatch", "closure", "diversion", "signal_hold"})
