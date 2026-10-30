"""Canonical SYNTHETIC fixtures for every OSINT WP (X18; plan R13).

Synthetic replicas of the PoC's cases, never real captures:

* the publishers are fictional (``news-a.example``, ``news-b.example``, and ``social-a.example`` for the Reddit
  replica, whose community ``example_city`` is fictional too): no fabricated text is attributed to a real outlet
  or community. Only the official alerts name a real publisher, ``sachet.ndma.gov.in`` (public-domain NDMA CAP),
  and their text is written here;
* no real person's name appears anywhere: the person names and ages the replicas "had" are already redacted to
  ``[PERSON]`` / ``[AGE]``, exactly as a connector emits them (``pii_redactions`` counts them);
* the toponyms are Mumbai's (spelled as in ``cities/mumbai/landmarks.json``) and the class cues the PoC's: a
  crash on the Western Express Highway near Andheri (synthetic segment 4101), a robbery near Dadar TT Circle
  (synthetic junction 4023), a Mumbai-district SACHET alert, a Maharashtra state-wide SACHET nowcast naming other
  districts, a single social post about metro work near Ghatkopar and a vehicle pursuit near Dadar. The segment
  and junction ids are SYNTHETIC (no Mumbai road graph is assumed): they only have to agree across the kit;
* the Kolkata pack (the second city pack) keeps its replicas below the Mumbai ones under their old names
  (``em_bypass_signals`` …), because the oracle, osint-geo and osint-ingress suites still replay them on the
  Kolkata road graph.

Every function returns fresh objects (mutating one never leaks into another test) and is deterministic: fixed
timestamps, ids derived with :func:`osint_common.types.signal_id_for` and ``uuid5``.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from osint_common.kinds import AREA_STATE_CODE_MAHARASHTRA, SOURCE_PRIORS
from osint_common.types import (
    Ahp,
    AttachResult,
    Cascade,
    Coa,
    CoaAction,
    CoaEthics,
    CoaScore,
    Criterion,
    DecisionSupport,
    DisruptionStats,
    DssProvenance,
    DssSituation,
    EmergencyImpact,
    Geocode,
    HumanGate,
    LiveEventRef,
    LiveStateSnapshot,
    PredictedOutcome,
    RawGeoHint,
    RawOsintSignal,
    Recommendation,
    ResourceFeasibility,
    Sensitivity,
    SourceRef,
    SpilloverStats,
    ValueOfInformation,
    signal_id_for,
)

__all__ = [
    "NEWS_A",
    "NEWS_B",
    "SACHET",
    "SOCIAL_A",
    "SYNTHETIC_NAMESPACE",
    "dadar_robbery_signal",
    "em_bypass_geocode",
    "em_bypass_signals",
    "gariahat_robbery_signal",
    "live_state_dadar_pursuit",
    "live_state_sealdah_pursuit",
    "sachet_district_signal",
    "sachet_maharashtra_signal",
    "sachet_mumbai_signal",
    "sachet_state_signal",
    "social_ghatkopar_signal",
    "social_single_signal",
    "weh_dss",
    "weh_geocode",
    "weh_signals",
]

#: Fictional publishers (synthetic replicas only, plan R13).
NEWS_A = "news-a.example"
NEWS_B = "news-b.example"
#: The fictional social host of the synthetic Reddit replica (never a real community).
SOCIAL_A = "social-a.example"
#: The official CAP publisher (public domain); the alert texts below are synthetic.
SACHET = "sachet.ndma.gov.in"

#: Namespace of every synthetic uuid in this kit.
SYNTHETIC_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "https://sajag.example/osint/testing")

_FETCHED = datetime(2026, 10, 20, 15, 0, 0, tzinfo=UTC)


def _uuid(name: str) -> str:
    return str(uuid.uuid5(SYNTHETIC_NAMESPACE, name))


def _signal(
    source: str,
    source_id: str,
    *,
    title: str,
    text: str,
    published_at: datetime,
    publisher: str | None,
    url: str | None,
    pii_redactions: int = 0,
    place_names: list[str] | None = None,
    admin_codes: list[str] | None = None,
    category_hint: list[str] | None = None,
    valid_until: datetime | None = None,
    raw: dict | None = None,
) -> RawOsintSignal:
    prior = SOURCE_PRIORS[source]
    return RawOsintSignal(
        signal_id=signal_id_for(source, source_id),
        source=source,  # type: ignore[arg-type]
        source_id=source_id,
        source_tier=prior.tier,  # type: ignore[arg-type]
        publisher=publisher,
        url=url,
        title=title,
        text=text,
        language="en",
        published_at=published_at,
        fetched_at=_FETCHED,
        valid_until=valid_until,
        fetch_mode="cached-sample",
        pii_redactions=pii_redactions,
        raw_geo_hint=RawGeoHint(place_names=place_names or [], admin_codes=admin_codes or []),
        category_hint=category_hint or [],
        tone=None,
        provenance_label=prior.provenance_label,  # type: ignore[arg-type]
        credibility_prior=prior.credibility_prior,
        license=prior.license,
        redistributable=prior.redistributable,
        raw=raw or {},
    )


def _news(
    n: int, publisher: str, minute: int, title: str, body: str, *, pii: int = 0, slug: str = "em-bypass"
) -> RawOsintSignal:
    return _signal(
        "google_news_rss",
        f"synthetic:{slug}-{n}",
        title=title,
        text=f"{title}. {body}",
        published_at=datetime(2026, 10, 20, 13, minute, 0, tzinfo=UTC),
        publisher=publisher,
        url=f"https://{publisher}/city/{slug}-report-{n}",
        pii_redactions=pii,
        category_hint=[f"publisher:{publisher}", f"domain:{publisher}"],
        raw={"guid": f"synthetic:{slug}-{n}", "source_domain": publisher},
    )


def _cap(
    identifier: str, *, title: str, text: str, place: str, admin: str, area: str, minute: int
) -> RawOsintSignal:
    return _signal(
        "sachet_cap",
        identifier,
        title=title,
        text=f"{title}. {text}",
        published_at=datetime(2026, 10, 20, 12, minute, 0, tzinfo=UTC),
        publisher=SACHET,
        url=None,
        place_names=[place],
        admin_codes=[admin],
        category_hint=["CAP", f"area:{area}"],
        valid_until=datetime(2026, 10, 20, 15, minute, 0, tzinfo=UTC),
        raw={
            "cap_identifier": identifier,
            "cap_event": "Thunderstorm",
            "cap_severity": "Moderate",
            "cap_urgency": "Expected",
            "cap_certainty": "Likely",
        },
    )


# ---------------------------------------------------------------------------
# Mumbai (the city this deployment serves)
# ---------------------------------------------------------------------------

#: The Western Express Highway case's synthetic road anchor (no Mumbai road graph is assumed).
WEH_SEGMENT = 4101
_WEH_LONLAT = (72.856, 19.116)  # cities/mumbai/landmarks.json "weh_andheri"


def weh_signals() -> list[RawOsintSignal]:
    """The Western Express Highway case: four news reports of a multi-vehicle collision on the WEH near Andheri
    (synthetic segment 4101) and one report of a crowd assaulting a driver at the scene — two fictional
    publishers, one tier.

    The four collision reports classify ``road_accident`` and the fifth ``public_conflict``; co-located, they
    correlate into one ``affray+collision`` situation at credibility 0.65, ``NEWS-REPORTED`` (no official source).
    """
    return [
        _news(
            1,
            NEWS_A,
            40,
            "Car crashes into three vehicles on the Western Express Highway near Andheri; 3 injured",
            "A speeding car hit three vehicles on the Western Express Highway near Andheri on Tuesday evening, "
            "injuring three people including a [AGE] scooter rider, traffic police said.",
            pii=1,
            slug="weh",
        ),
        _news(
            2,
            NEWS_B,
            55,
            "Multi-vehicle crash on the Western Express Highway near Andheri leaves three injured",
            "Traffic slowed on the Western Express Highway near Andheri after the multi-vehicle crash; the injured "
            "were taken to a hospital.",
            slug="weh",
        ),
        _news(
            3,
            NEWS_B,
            58,
            "Western Express Highway accident: vehicles collided near Andheri, one lane blocked",
            "One lane of the Western Express Highway near Andheri stayed blocked while the damaged vehicles were "
            "cleared.",
            slug="weh",
        ),
        _news(
            4,
            NEWS_A,
            59,
            "Three injured after car rammed vehicles on the Western Express Highway near Andheri",
            "The car rammed vehicles waiting on the Western Express Highway near Andheri; police are recording "
            "statements.",
            slug="weh",
        ),
        _news(
            5,
            NEWS_B,
            50,
            "Driver beaten by mob after Western Express Highway crash near Andheri",
            "Locals surrounded the car on the Western Express Highway near Andheri after the crash and the driver, "
            "identified as [PERSON], was beaten by the mob before police arrived.",
            pii=1,
            slug="weh",
        ),
    ]


def dadar_robbery_signal() -> RawOsintSignal:
    """A reported daylight robbery near Dadar TT Circle (synthetic junction 4023): ``reported_crime``, credibility
    0.60."""
    title = "Jewellery shop robbed at gunpoint near Dadar TT Circle"
    return _signal(
        "google_news_rss",
        "synthetic:dadar-robbery-1",
        title=title,
        text=f"{title}. A jewellery shop near Dadar TT Circle was robbed at gunpoint in broad daylight, "
        "police said; the area was cordoned off for an hour.",
        published_at=datetime(2026, 10, 20, 10, 15, 0, tzinfo=UTC),
        publisher=NEWS_B,
        url=f"https://{NEWS_B}/city/dadar-robbery",
        category_hint=[f"publisher:{NEWS_B}", f"domain:{NEWS_B}"],
        raw={"guid": "synthetic:dadar-robbery-1", "source_domain": NEWS_B},
    )


def sachet_mumbai_signal() -> RawOsintSignal:
    """An official SACHET CAP alert naming Mumbai: a DISTRICT-level area (``LGD:MUMBAI``), credibility 0.95,
    ``OFFICIAL-VERIFIED``; a thunderstorm warning, so ``weather_hazard`` (not a flood)."""
    return _cap(
        "synthetic.sachet.mumbai.20261020T1200",
        title="Thunderstorm and lightning warning for Mumbai district",
        text="Thunderstorm with lightning and gusty winds of 40-50 km/h is likely at isolated places in "
        "Mumbai district during the next 3 hours.",
        place="Mumbai",
        admin="LGD:MUMBAI",
        area="mumbai",
        minute=0,
    )


def sachet_maharashtra_signal() -> RawOsintSignal:
    """A state-wide SACHET nowcast (``LGD:MAHARASHTRA``) naming OTHER districts: a STATE-level area with no point in
    the city, so its situation is held and counted in ``held.outside_city`` (plan R28), never a Mumbai event."""
    return _cap(
        "synthetic.sachet.maharashtra-nowcast.20261020T1210",
        title="Nowcast warning: thunderstorm likely over Pune, Satara and Kolhapur districts",
        text="Thunderstorm with lightning is likely over the ghat areas of Pune, Satara, Kolhapur and Sindhudurg "
        "districts of Maharashtra during the next 3 hours.",
        place="Maharashtra",
        admin=AREA_STATE_CODE_MAHARASHTRA,
        area="maharashtra",
        minute=10,
    )


def social_ghatkopar_signal() -> RawOsintSignal:
    """One synthetic Reddit-replica post about a road narrowed for metro work near Ghatkopar on LBS Marg:
    ``social_unverified``, credibility 0.25, on the fictional host ``social-a.example`` in the fictional community
    ``example_city``.

    Its class (``road_closure``) is an event class related to none of the other fixtures, so the ONLY reason it is
    held is the aggregate-only rule: a single social source is never an event. Its author handle never existed in
    the record (dropped at parse)."""
    title = "Road closed for metro work near Ghatkopar on LBS Marg, traffic diverted"
    return _signal(
        "reddit_rss",
        "synthetic:t3_ghatkopar01",
        title=title,
        text=f"{title}. Expect a slow crawl around Ghatkopar this evening.",
        published_at=datetime(2026, 10, 20, 14, 30, 0, tzinfo=UTC),
        publisher=SOCIAL_A,
        url=f"https://{SOCIAL_A}/r/example_city/comments/ghatkopar01/",
        category_hint=["subreddit:example_city"],
        raw={"subreddit": "example_city"},
    )


def live_state_dadar_pursuit() -> LiveStateSnapshot:
    """The live corridor state with one active, human-initiated vehicle pursuit near Dadar (Dr Ambedkar Road →
    Dadar TT Circle → Senapati Bapat Marg; synthetic segments 4201-4203); about 11 km from the WEH case."""
    return LiveStateSnapshot(
        as_of=datetime(2026, 10, 20, 15, 0, 0, tzinfo=UTC),
        live_events=[
            LiveEventRef(
                urn=f"event:{_uuid('live-dadar-pursuit')}",
                event_kind="vehicle_pursuit",
                status="active",
                lon=72.8436,
                lat=19.0186,
                segment_ids=[4201, 4202, 4203],
            )
        ],
        ambulance_routes=[],
        closures=[],
    )


def weh_geocode() -> Geocode:
    """The primary WEH report resolved to the road itself: synthetic segment 4101 (the Western Express Highway at
    Andheri), the reading nearest Andheri."""
    return Geocode(
        signal_id=weh_signals()[0].signal_id,
        toponym="Western Express Highway",
        feature_type="road",
        lon=_WEH_LONLAT[0],
        lat=_WEH_LONLAT[1],
        segment_id=WEH_SEGMENT,
        junction_id=None,
        snapped_to=None,
        method="gazetteer_exact",
        residual_m=0.0,
        confidence=0.68,
        bucket="medium",
        area_level=False,
        area_scope=None,
        alternatives=["Andheri"],
    )


# ---------------------------------------------------------------------------
# The Kolkata pack (the second city pack): replicas the oracle, osint-geo and osint-ingress suites replay on the
# Kolkata road graph (EM Bypass segment 1035, Gariahat crossing junction 23)
# ---------------------------------------------------------------------------


def em_bypass_signals() -> list[RawOsintSignal]:
    """The Kolkata pack's EM Bypass case: four news reports of a multi-vehicle collision on EM Bypass near Kasba
    (segment 1035, Ruby crossing to Science City) and one report of a crowd assaulting a driver at the scene — two
    fictional publishers, one tier.

    The four collision reports classify ``road_accident`` and the fifth ``public_conflict``; co-located, they
    correlate into one ``affray+collision`` situation at credibility 0.65, ``NEWS-REPORTED`` (no official source).
    """
    return [
        _news(
            1,
            NEWS_A,
            40,
            "Car crashes into three vehicles on EM Bypass near Kasba; 3 injured",
            "A speeding car hit three vehicles on EM Bypass near Kasba on Tuesday evening, injuring three people "
            "including a [AGE] scooter rider, traffic police said.",
            pii=1,
        ),
        _news(
            2,
            NEWS_B,
            55,
            "Multi-vehicle crash on EM Bypass near Kasba leaves three injured",
            "Traffic slowed on EM Bypass near Kasba after the multi-vehicle crash; the injured were taken to a "
            "hospital.",
        ),
        _news(
            3,
            NEWS_B,
            58,
            "EM Bypass accident: vehicles collided near Kasba, one lane blocked",
            "One lane of EM Bypass near Kasba stayed blocked while the damaged vehicles were cleared.",
        ),
        _news(
            4,
            NEWS_A,
            59,
            "Three injured after car rammed vehicles on EM Bypass near Kasba",
            "The car rammed vehicles waiting on EM Bypass near Kasba; police are recording statements.",
        ),
        _news(
            5,
            NEWS_B,
            50,
            "Driver beaten by mob after EM Bypass crash near Kasba",
            "Locals surrounded the car on EM Bypass near Kasba after the crash and the driver, identified as "
            "[PERSON], was beaten by the mob before police arrived.",
            pii=1,
        ),
    ]


def gariahat_robbery_signal() -> RawOsintSignal:
    """A reported daylight robbery at Gariahat crossing (junction 23): ``reported_crime``, credibility 0.60."""
    title = "Jewellery shop robbed at gunpoint near Gariahat crossing"
    return _signal(
        "google_news_rss",
        "synthetic:gariahat-robbery-1",
        title=title,
        text=f"{title}. A jewellery shop near Gariahat crossing was robbed at gunpoint in broad daylight, "
        "police said; the area was cordoned off for an hour.",
        published_at=datetime(2026, 10, 20, 10, 15, 0, tzinfo=UTC),
        publisher=NEWS_B,
        url=f"https://{NEWS_B}/city/gariahat-robbery",
        category_hint=[f"publisher:{NEWS_B}", f"domain:{NEWS_B}"],
        raw={"guid": "synthetic:gariahat-robbery-1", "source_domain": NEWS_B},
    )


def sachet_district_signal() -> RawOsintSignal:
    """An official SACHET CAP alert naming Kolkata: a DISTRICT-level area (``LGD:KOLKATA``), credibility 0.95,
    ``OFFICIAL-VERIFIED``; a thunderstorm warning, so ``weather_hazard`` (not a flood)."""
    return _cap(
        "synthetic.sachet.kolkata.20261020T1200",
        title="Thunderstorm and lightning warning for Kolkata district",
        text="Thunderstorm with lightning and gusty winds of 40-50 km/h is likely at isolated places in "
        "Kolkata district during the next 3 hours.",
        place="Kolkata",
        admin="LGD:KOLKATA",
        area="kolkata",
        minute=0,
    )


def sachet_state_signal() -> RawOsintSignal:
    """A state-wide SACHET nowcast (``LGD:WEST_BENGAL``) naming OTHER districts: a STATE-level area with no point in
    the city, so its situation is held and counted in ``held.outside_city`` (plan R28), never a Kolkata event."""
    return _cap(
        "synthetic.sachet.westbengal-nowcast.20261020T1210",
        title="Nowcast warning: thunderstorm likely over Purba Medinipur, Paschim Medinipur and Bankura districts",
        text="Thunderstorm with lightning is likely over Purba Medinipur, Paschim Medinipur, Bankura and Purulia "
        "districts of West Bengal during the next 3 hours.",
        place="West Bengal",
        admin="LGD:WEST_BENGAL",
        area="west_bengal",
        minute=10,
    )


def social_single_signal() -> RawOsintSignal:
    """One synthetic Reddit-replica post about a road narrowed for metro work at Taratala: ``social_unverified``,
    credibility 0.25, on the fictional host ``social-a.example`` in the fictional community ``example_city``.

    Its class (``road_closure``) is an event class related to none of the other fixtures, so the ONLY reason it is
    held is the aggregate-only rule: a single social source is never an event. Its author handle never existed in
    the record (dropped at parse)."""
    title = "Road closed for metro work near Taratala on Diamond Harbour Road, traffic diverted"
    return _signal(
        "reddit_rss",
        "synthetic:t3_taratala01",
        title=title,
        text=f"{title}. Expect a slow crawl around Taratala this evening.",
        published_at=datetime(2026, 10, 20, 14, 30, 0, tzinfo=UTC),
        publisher=SOCIAL_A,
        url=f"https://{SOCIAL_A}/r/example_city/comments/taratala01/",
        category_hint=["subreddit:example_city"],
        raw={"subreddit": "example_city"},
    )


def live_state_sealdah_pursuit() -> LiveStateSnapshot:
    """The live corridor state with one active, human-initiated vehicle pursuit in central Kolkata near Sealdah
    (Lenin Sarani → AJC Bose Road → Sealdah → APC Road); about 5 km from the EM Bypass case."""
    return LiveStateSnapshot(
        as_of=datetime(2026, 10, 20, 15, 0, 0, tzinfo=UTC),
        live_events=[
            LiveEventRef(
                urn=f"event:{_uuid('live-sealdah-pursuit')}",
                event_kind="vehicle_pursuit",
                status="active",
                lon=88.366700,
                lat=22.560650,
                segment_ids=[1063, 1025, 1056],
            )
        ],
        ambulance_routes=[],
        closures=[],
    )


def em_bypass_geocode() -> Geocode:
    """The primary EM Bypass report resolved to the road itself: segment 1035 (EM Bypass, Ruby crossing to Science
    City), the reading nearest Kasba."""
    return Geocode(
        signal_id=em_bypass_signals()[0].signal_id,
        toponym="Eastern Metropolitan Bypass",
        feature_type="road",
        lon=88.3957601,
        lat=22.5255148,
        segment_id=1035,
        junction_id=None,
        snapped_to=None,
        method="gazetteer_exact",
        residual_m=0.0,
        confidence=0.68,
        bucket="medium",
        area_level=False,
        area_scope=None,
        alternatives=["Kasba"],
    )


# ---------------------------------------------------------------------------
# A synthetic DecisionSupport with the PoC dss_output.json structure (C-U)
# ---------------------------------------------------------------------------

_SURROGATE = (
    "DSS Monte-Carlo surrogate (SIMULATED, 240 replications, seeded); production: the seeded corridor twin for "
    "per-route disruption plus the DSS-layer cascade over the segment neighbours"
)
_CRITERIA = (
    ("safety_risk_reduction", "Public-safety risk reduction (fixed prior by COA actions, not simulated)", "benefit",
     0.3121, True),
    ("time_to_effect", "Speed of effect (nominal time by COA kind, not a unit ETA)", "benefit", 0.1075, True),
    ("resource_cost", "Resource cost", "cost", 0.0247, True),
    ("public_disruption", "Public traffic disruption", "cost", 0.0507, True),
    ("cascade_risk", "Cascade / spillover risk", "cost", 0.0739, True),
    ("reversibility", "Reversibility", "benefit", 0.0183, True),
    ("affected_population", "Affected population", "cost", 0.035, True),
    ("protocol_compliance", "Protocol compliance", "benefit", 0.2223, False),
    ("legality", "Legality", "benefit", 0.1555, False),
)
_AHP_ORDER = [
    "safety_risk_reduction",
    "protocol_compliance",
    "legality",
    "time_to_effect",
    "cascade_risk",
    "public_disruption",
    "affected_population",
    "resource_cost",
    "reversibility",
]
_CLEAN = CoaEthics(
    touches_persons=False,
    legal=True,
    protocol_ok=True,
    irreversible_without_officer=False,
    vetoed=False,
    veto_reason=None,
)


def _attrs(*values: float) -> dict[str, float]:
    return {c[0]: v for c, v in zip(_CRITERIA, values, strict=True)}


def _outcome(
    response: float | None,
    disruption: tuple[float, float, float | None],
    spill: tuple[float, float],
    neighbourhoods: list[str],
    routes: list[str],
    delay: float,
    tte: float,
    resolution: float,
) -> PredictedOutcome:
    return PredictedOutcome(
        response_time_to_scene_sec=response,
        total_disruption_vehicle_hours=DisruptionStats(
            mean=disruption[0], p90=disruption[1], p90_mean_ratio=disruption[2], replications=240
        ),
        cascade=Cascade(
            spillover_vehicle_hours=SpilloverStats(mean=spill[0], p90=spill[1]),
            neighbourhoods_touched=neighbourhoods,
            parallel_routes_loaded=routes,
            affected_segment_ids=[WEH_SEGMENT] if neighbourhoods else [],
        ),
        emergency_impact=EmergencyImpact(ambulance_delay_sec=delay, green_corridor_ok=delay <= 0),
        time_to_effect_sec=tte,
        event_resolution_prob=resolution,
        method=_SURROGATE,
    )


def _feasibility(need: dict[str, int], free: dict[str, int], eta: float | None) -> ResourceFeasibility:
    shortfalls = [f"{k}: need {n}, {free.get(k, 0)} free" for k, n in need.items() if n > free.get(k, 0)]
    return ResourceFeasibility(
        required_resources=need or {"none": 0},
        availability={k: free.get(k, 0) for k in need},
        eta_to_scene_sec=eta,
        feasible=not shortfalls,
        shortfalls=shortfalls,
    )


def _act(verb: str, target: str | None = None, requires_officer: bool = False, **params: object) -> CoaAction:
    return CoaAction(
        verb=verb,  # type: ignore[arg-type]
        target_urn=target,
        params=dict(params),
        requires_officer=requires_officer,
        reversible=True,
    )


def weh_dss() -> DecisionSupport:
    """A proposed decision support for the Western Express Highway situation near Andheri: five COAs (baseline,
    minimal, standard, aggressive, information), the full-closure COA resource-infeasible (one patrol is on the
    Dadar pursuit) and ranked last, the standard response recommended, EVOI below the information cost (act now).
    The numbers mirror the proof-of-concept run (a synthetic replica, labelled ``SIMULATED``)."""
    signals = weh_signals()
    sources = [
        SourceRef(
            signal_id=s.signal_id,
            source=s.source,
            publisher=s.publisher,
            url=s.url,
            title=s.title,
            event_class="public_conflict" if i == 4 else "road_accident",
            credibility=s.credibility_prior,
            fetch_mode=s.fetch_mode,
            role="primary" if i == 0 else "corroborating",
        )
        for i, s in enumerate(signals)
    ]
    free = {"ambulance_108": 1, "police_patrol": 1}
    place = "place:weh_andheri"
    seg = f"segment:{WEH_SEGMENT}"
    junction = "junction:4129"
    parallel = ["SV Road", "New Link Road"]
    coas = [
        Coa(
            coa_id="coa_base",
            kind="baseline",
            label="Monitor only (do nothing)",
            actions=[_act("monitor")],
            predicted_outcome=_outcome(None, (0.0, 0.0, None), (0.0, 0.0), [], [], 0, 0, 0.3),
            resource_feasibility=_feasibility({}, free, None),
            attributes=_attrs(0.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0),
            score=CoaScore(method="topsis", closeness=0.2192, rank=3, feasible=True),
            ethics=_CLEAN,
        ),
        Coa(
            coa_id="coa_min",
            kind="minimal",
            label="Driver and citizen advisory only (VMS + app push)",
            actions=[_act("advisory", place)],
            predicted_outcome=_outcome(None, (98.8, 115.1, 1.165), (40.3, 47.1), [], [], 0, 120, 0.38),
            resource_feasibility=_feasibility({}, free, None),
            attributes=_attrs(0.0, 0.8, 1.0, 0.962, 0.973, 1.0, 1.0, 1.0, 1.0),
            score=CoaScore(method="topsis", closeness=0.19, rank=4, feasible=True),
            ethics=_CLEAN,
        ),
        Coa(
            coa_id="coa_std",
            kind="standard",
            label="Advisory + ambulance (108) + 1 patrol + signal priority",
            actions=[
                _act("advisory", place),
                _act("dispatch", seg, True, agency="ambulance", count=1),
                _act("dispatch", seg, True, agency="police", count=1),
                _act("signal_hold", junction, True, mode="emergency_priority"),
            ],
            predicted_outcome=_outcome(
                393,
                (866.7, 1062.0, 1.225),
                (353.6, 433.9),
                ["Andheri East", "Vile Parle"],
                parallel,
                -60,
                300,
                0.88,
            ),
            resource_feasibility=_feasibility({"ambulance_108": 1, "police_patrol": 1}, free, 480),
            attributes=_attrs(0.88, 0.5, 0.5, 0.667, 0.764, 1.0, 0.4, 1.0, 1.0),
            score=CoaScore(method="topsis", closeness=0.8555, rank=1, feasible=True),
            ethics=_CLEAN,
        ),
        Coa(
            coa_id="coa_agg",
            kind="aggressive",
            label="Close carriageway + full diversion + ambulance (108) + 2 police units",
            actions=[
                _act("closure", seg, True),
                _act("diversion", seg, True, via=parallel),
                _act("dispatch", seg, True, agency="ambulance", count=1),
                _act("dispatch", seg, True, agency="police", count=2),
            ],
            predicted_outcome=_outcome(
                480,
                (2514.9, 3566.7, 1.418),
                (1026.7, 1467.0),
                ["Andheri East", "Vile Parle", "Jogeshwari"],
                parallel,
                180,
                420,
                0.97,
            ),
            resource_feasibility=_feasibility({"ambulance_108": 1, "police_patrol": 2}, free, 480),
            attributes=_attrs(0.72, 0.3, 0.08, 0.033, 0.316, 0.75, 0.1, 1.0, 1.0),
            score=CoaScore(method="topsis", closeness=0.7098, rank=5, feasible=False),
            ethics=_CLEAN,
        ),
        Coa(
            coa_id="coa_info",
            kind="information",
            label=(
                "Verify first: 1 patrol to confirm + traffic control-room camera check (no identification) "
                "+ 10-min hold"
            ),
            actions=[
                _act("dispatch", seg, True, agency="police", count=1, role="verify"),
                _act("request_cctv", junction),
            ],
            predicted_outcome=_outcome(None, (22.1, 25.9, 1.171), (9.0, 10.6), [], [], 0, 240, 0.68),
            resource_feasibility=_feasibility({"police_patrol": 1}, free, 420),
            attributes=_attrs(0.28, 0.6, 0.82, 0.992, 0.994, 1.0, 1.0, 1.0, 1.0),
            score=CoaScore(method="topsis", closeness=0.3529, rank=2, feasible=True),
            ethics=_CLEAN,
        ),
    ]
    discriminating = [c[0] for c in _CRITERIA if c[4]]
    gate = [c[0] for c in _CRITERIA if not c[4]]
    return DecisionSupport(
        dss_id=_uuid("dss-weh"),
        event_urn=f"osint_event:{_uuid('osint-event-weh')}",
        state="proposed",
        generated_at=datetime(2026, 10, 20, 15, 5, 0, tzinfo=UTC),
        horizon_min=45,
        seed=20261024,
        situation=DssSituation(
            summary=(
                "5 reports across 2 related classes (road_accident, public_conflict) correlated into one "
                "situation on the Western Express Highway near Andheri: " + signals[0].title
            ),
            event_class="road_accident",
            correlated_classes=["road_accident", "public_conflict"],
            subtype="affray+collision",
            sajag_event_kind="road_accident",
            toponym="Western Express Highway",
            segment_id=WEH_SEGMENT,
            junction_id=None,
            rep_lonlat=_WEH_LONLAT,
            credibility=0.65,
            independent_publishers=2,
            source_tiers=["aggregator"],
            cross_type_corroborated=False,
            attach=AttachResult(novel=True),
            verification_state="NEWS-REPORTED",
            geocode_confidence=0.68,
            composite_confidence=0.688,
        ),
        criteria=[
            Criterion(
                id=cid,
                label=label,
                direction=direction,  # type: ignore[arg-type]
                weight=weight,
                weight_source="ahp",
                role="discriminating" if disc else "gate (non-discriminating)",
            )
            for cid, label, direction, weight, disc in _CRITERIA
        ],
        ahp=Ahp(consistency_ratio=0.0346, acceptable=True, rank_order=_AHP_ORDER),
        scoring_note=(
            f"TOPSIS runs over the {len(discriminating)} discriminating criteria {discriminating}; the "
            f"{len(gate)} gate criteria {gate} are constant across the surviving COAs (handled by the lexical "
            "veto) and are reported as gate-passed."
        ),
        coa_set=coas,
        # This replica mirrors the PoC's pre-floor ranking (coa_base above coa_min) for parity, so it keeps
        # public_safety_floor at its default "none"; the engine itself would hold the baseline here ("hold").
        recommendation=Recommendation(
            ranked_coa_ids=["coa_std", "coa_info", "coa_base", "coa_min", "coa_agg"],
            top_coa_id="coa_std",
            margin=0.5026,
            sensitivity=Sensitivity(rank_stability=1.0, flips_to={}),
            value_of_information=ValueOfInformation(
                evoi=-0.0105,
                L_act_now=0.36,
                L_gather_then_act=0.3705,
                info_cost=0.2,
                advise_gather=False,
                info_coa_id="coa_info",
                why=(
                    "acting now dominates: EVOI -0.011 <= info cost 0.200 (credibility 0.65 and margin 0.503 "
                    "already justify committing to the recommended feasible COA)"
                ),
            ),
            dissent=(
                "Runner-up is coa_info (verify first, closeness 0.353 vs 0.855). It is not chosen because it is "
                "dominated on the heavily weighted safety and cascade criteria, with 100% rank stability under "
                "weight perturbation. It would flip if the weighting moved toward time to effect, or if an "
                "official source (Mumbai Traffic Police or BMC control-room confirmation) changed the "
                "credibility. Corroboration is real but within one tier: 2 independent news publishers, no "
                "official confirmation yet, so the report stays NEWS-REPORTED. The full-closure COA is "
                "resource-infeasible this cycle (police_patrol: need 2, 1 free) and is ranked last and labelled, "
                "not hidden."
            ),
            decision="await_officer",
            strategy_prior=None,
        ),
        provenance=DssProvenance(
            feeds=["google_news_rss"],
            publishers=[NEWS_A, NEWS_B],
            sources=sources,
            sim_run_ids=[],
            model_tiers=[],
            wargame_method="surrogate",
            brain_degraded=False,
        ),
        human_gate=HumanGate(state="proposed", required_role="duty_officer", officer=None, decided_at=None),
        labels=["NEWS-REPORTED", "SIMULATED"],
    )
