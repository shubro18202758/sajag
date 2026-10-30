"""Test helpers for osint-analysis: SYNTHETIC signals and a fake resolver (plan R13).

Every signal here is a synthetic replica: fictional publishers on reserved ``*.example`` hosts (the canonical
``osint_common.testing`` fixtures, plus ad-hoc ones built by :func:`make_signal`), the public-domain SACHET
publisher for official alerts with texts written here, and no real person's name anywhere.

Mumbai (the city this deployment serves): :func:`mumbai_signals` and :func:`mumbai_resolver` place the
``osint_common.testing`` Mumbai replicas at ``cities/mumbai/landmarks.json`` coordinates with SYNTHETIC segment and
junction ids (no Mumbai road graph is assumed): the Western Express Highway at Andheri (segment 4101), Dadar TT
Circle (junction 4023), Ghatkopar (junction 4027), the Mumbai district point and the Maharashtra state level.

The Kolkata pack (the second city pack): the rule tests of fusion, correlation, attach and second order still replay
the committed Kolkata network's and gazetteer's geometry (``scripts/data/osm_network.json``,
``scripts/data/osint_gazetteer.json``) until the Mumbai network is generated: Ruby General Hospital snapped to the EM
Bypass (segment 1035, Ruby crossing to Science City), Gariahat crossing (junction 23), Park Circus seven-point
crossing (junction 17), AJC Bose Road between Moulali and Sealdah (segment 1025, on the Sealdah pursuit's route),
Garia, Behala Chowrasta (junction 28) and Kasba.
"""

from __future__ import annotations

import itertools
from datetime import UTC, datetime, timedelta

from osint_common import testing
from osint_common.kinds import SOURCE_PRIORS
from osint_common.types import Geocode, LiveEventRef, LiveStateSnapshot, RawGeoHint, RawOsintSignal, signal_id_for

#: (lon, lat) of Mumbai places (``cities/mumbai/landmarks.json``)
WEH_ANDHERI = (72.856, 19.116)  # the Western Express Highway at Andheri (synthetic segment 4101)
DADAR_TT = (72.848, 19.0176)  # Dadar TT Circle (synthetic junction 4023)
GHATKOPAR = (72.9081, 19.086)  # Ghatkopar (synthetic junction 4027)
MUMBAI_DISTRICT_POINT = (72.8777, 19.076)  # the Mumbai district representative point (the city's conventional centre)

#: (lon, lat) of the Kolkata pack's gazetteer places used by the rule tests
RUBY_HOSPITAL = (88.403, 22.513)  # landmark, snapped to the EM Bypass (Ruby crossing - Science City), 1035, 155 m
EM_BYPASS_KASBA = (88.3957601, 22.5255148)  # road, segment 1035 (its representative point, 1.6 km north of Ruby)
GARIAHAT_CROSSING = (88.3653392, 22.5197455)  # junction 23
PARK_CIRCUS_CROSSING = (88.3658485, 22.5430761)  # junction 17 (Park Circus seven-point crossing)
AJC_BOSE_ROAD = (88.3684391, 22.5650939)  # road, segment 1025 (Moulali - Sealdah, on the Sealdah pursuit's route)
SEALDAH_PURSUIT = (88.3667, 22.56065)  # the live pursuit's representative point
DISTRICT_POINT = (88.3639, 22.5726)  # the Kolkata district representative point
GARIA = (88.39, 22.463)  # neighbourhood, ~9 km south of Park Circus
BEHALA_CHOWRASTA = (88.3131057, 22.4869894)  # junction 28, ~8 km south-west of Park Circus and of Garia
KASBA = (88.387, 22.516)  # neighbourhood
SHYAMBAZAR = (88.372, 22.6)  # neighbourhood, ~15 km north of Garia and ~13 km north-east of Behala Chowrasta
TARATALA = (88.3212219, 22.5101057)  # junction 27 (Taratala, Diamond Harbour Road)

T0 = datetime(2026, 10, 20, 13, 0, 0, tzinfo=UTC)
FETCHED = datetime(2026, 10, 20, 15, 0, 0, tzinfo=UTC)

_SEQ = itertools.count(1)


def make_signal(
    source: str = "google_news_rss",
    *,
    title: str,
    text: str | None = None,
    published_at: datetime | None = T0,
    publisher: str | None = "news-a.example",
    url: str | None = None,
    pii: int = 0,
    place_names: list[str] | None = None,
    admin_codes: list[str] | None = None,
    category_hint: list[str] | None = None,
    valid_until: datetime | None = None,
    provenance_label: str | None = None,
    source_tier: str | None = None,
    credibility_prior: float | None = None,
    fetched_at: datetime | None = None,
    source_id: str | None = None,
) -> RawOsintSignal:
    """A synthetic signal with the source's priors (overridable, to test pass-through and tier rules)."""
    prior = SOURCE_PRIORS[source]
    sid = source_id or f"synthetic:test-{next(_SEQ)}"
    if url is None and publisher and publisher.endswith(".example"):
        url = f"https://{publisher.split('/', 1)[0]}/city/{sid.split(':', 1)[-1]}"
    return RawOsintSignal(
        signal_id=signal_id_for(source, sid),
        source=source,  # type: ignore[arg-type]
        source_id=sid,
        source_tier=source_tier or prior.tier,  # type: ignore[arg-type]
        publisher=publisher,
        url=url,
        title=title,
        text=text if text is not None else title,
        language="en",
        published_at=published_at,
        fetched_at=fetched_at or max(FETCHED, published_at or FETCHED),
        valid_until=valid_until,
        fetch_mode="cached-sample",
        pii_redactions=pii,
        raw_geo_hint=RawGeoHint(place_names=place_names or [], admin_codes=admin_codes or []),
        category_hint=category_hint or [],
        tone=None,
        provenance_label=provenance_label or prior.provenance_label,  # type: ignore[arg-type]
        credibility_prior=prior.credibility_prior if credibility_prior is None else credibility_prior,
        license=prior.license,
        redistributable=prior.redistributable,
        raw={},
    )


def at(minutes: float) -> datetime:
    """``T0`` plus some minutes."""
    return T0 + timedelta(minutes=minutes)


def point(
    signal: RawOsintSignal,
    lonlat: tuple[float, float] = RUBY_HOSPITAL,
    *,
    toponym: str = "Ruby General Hospital (EM Bypass)",
    feature_type: str = "landmark",
    segment_id: int | None = None,
    junction_id: int | None = None,
    residual_m: float | None = 0.0,
    confidence: float = 0.7,
    snapped_to: str | None = None,
) -> Geocode:
    """A point, junction or snapped-landmark geocode."""
    return Geocode(
        signal_id=signal.signal_id,
        toponym=toponym,
        feature_type=feature_type,  # type: ignore[arg-type]
        lon=lonlat[0],
        lat=lonlat[1],
        segment_id=segment_id,
        junction_id=junction_id,
        snapped_to=snapped_to,
        method="gazetteer_exact",
        residual_m=residual_m,
        confidence=confidence,
        bucket="high" if confidence >= 0.75 else "medium" if confidence >= 0.5 else "low",
    )


def ruby_hospital(signal: RawOsintSignal, confidence: float = 0.719) -> Geocode:
    """The Ruby General Hospital landmark snapped to the EM Bypass, segment 1035 (155 m)."""
    return point(
        signal,
        RUBY_HOSPITAL,
        segment_id=1035,
        residual_m=155.0,
        confidence=confidence,
        snapped_to="Eastern Metropolitan Bypass",
    )


def road(
    signal: RawOsintSignal,
    segment_id: int = 1035,
    lonlat: tuple[float, float] = EM_BYPASS_KASBA,
    *,
    toponym: str = "Eastern Metropolitan Bypass",
    confidence: float = 0.68,
) -> Geocode:
    """A road (line) geocode on its own segment."""
    return point(signal, lonlat, toponym=toponym, feature_type="road", segment_id=segment_id, confidence=confidence)


def district(
    signal: RawOsintSignal, toponym: str = "Kolkata (district)", lonlat: tuple[float, float] = DISTRICT_POINT
) -> Geocode:
    """A district-level area: the district point, confidence 0.4 (plan R28)."""
    return Geocode(
        signal_id=signal.signal_id,
        toponym=toponym,
        feature_type="admin",
        lon=lonlat[0],
        lat=lonlat[1],
        method="area_fallback",
        confidence=0.4,
        bucket="low",
        area_level=True,
        area_scope="district",
    )


def state(signal: RawOsintSignal, toponym: str = "West Bengal (state)") -> Geocode:
    """A state-level area: no point, confidence 0.25 (plan R28)."""
    return Geocode(
        signal_id=signal.signal_id,
        toponym=toponym,
        feature_type="admin",
        method="area_fallback",
        confidence=0.25,
        bucket="low",
        area_level=True,
        area_scope="state",
    )


class FakeResolver:
    """A :class:`osint_common.pipeline.GeoResolver` that answers from a mapping (``None`` otherwise)."""

    def __init__(self, geocodes: list[Geocode] | None = None) -> None:
        self.by_id: dict[str, Geocode] = {g.signal_id: g for g in geocodes or []}
        self.calls: list[str] = []

    def add(self, *geocodes: Geocode) -> FakeResolver:
        for g in geocodes:
            self.by_id[g.signal_id] = g
        return self

    def resolve(self, signal: RawOsintSignal) -> Geocode | None:
        self.calls.append(signal.signal_id)
        return self.by_id.get(signal.signal_id)


def em_bypass_geocodes(signals: list[RawOsintSignal] | None = None) -> list[Geocode]:
    """The synthetic EM Bypass reports geocoded as the Kolkata resolver geocodes them: "EM Bypass near Kasba" is the
    road itself (segment 1035, :func:`osint_common.testing.em_bypass_geocode`), a report naming Ruby General
    Hospital the landmark snapped onto that segment (155 m)."""
    em = signals or testing.em_bypass_signals()
    return [ruby_hospital(s) if "Ruby" in s.title else road(s) for s in em]


def canonical_signals() -> list[RawOsintSignal]:
    """Every canonical ``osint_common.testing`` signal: the EM Bypass five, the Gariahat robbery, the two SACHET
    alerts (Kolkata district and West Bengal state-wide) and the single social post (Taratala)."""
    return [
        *testing.em_bypass_signals(),
        testing.gariahat_robbery_signal(),
        testing.sachet_district_signal(),
        testing.sachet_state_signal(),
        testing.social_single_signal(),
    ]


def canonical_resolver() -> FakeResolver:
    """A resolver for :func:`canonical_signals`, at the precision OS-3 gives each (plan R28 for the areas)."""
    robbery = testing.gariahat_robbery_signal()
    social = testing.social_single_signal()
    return FakeResolver(
        [
            *em_bypass_geocodes(),
            point(
                robbery,
                GARIAHAT_CROSSING,
                toponym="Gariahat crossing",
                feature_type="junction",
                junction_id=23,
                confidence=0.718,
            ),
            district(testing.sachet_district_signal()),
            state(testing.sachet_state_signal()),
            point(
                social,
                TARATALA,
                toponym="Taratala (Diamond Harbour Road)",
                feature_type="junction",
                junction_id=27,
                confidence=0.8,
            ),
        ]
    )


def mumbai_signals() -> list[RawOsintSignal]:
    """Every Mumbai ``osint_common.testing`` signal: the WEH five, the Dadar robbery, the Mumbai district and the
    Maharashtra state-wide SACHET alerts, and the single social post (Ghatkopar)."""
    return [
        *testing.weh_signals(),
        testing.dadar_robbery_signal(),
        testing.sachet_mumbai_signal(),
        testing.sachet_maharashtra_signal(),
        testing.social_ghatkopar_signal(),
    ]


def mumbai_resolver() -> FakeResolver:
    """A resolver for :func:`mumbai_signals`, at the precision OS-3 gives each (plan R28 for the areas)."""
    weh = [
        road(s, testing.WEH_SEGMENT, WEH_ANDHERI, toponym="Western Express Highway") for s in testing.weh_signals()
    ]
    return FakeResolver(
        [
            *weh,
            point(testing.dadar_robbery_signal(), DADAR_TT, toponym="Dadar TT Circle", feature_type="junction",
                  junction_id=4023, confidence=0.718),
            district(testing.sachet_mumbai_signal(), toponym="Mumbai (district)", lonlat=MUMBAI_DISTRICT_POINT),
            state(testing.sachet_maharashtra_signal(), toponym="Maharashtra (state)"),
            point(testing.social_ghatkopar_signal(), GHATKOPAR, toponym="Ghatkopar (LBS Marg)",
                  feature_type="junction", junction_id=4027, confidence=0.8),
        ]
    )


def live_state(
    *events: LiveEventRef,
    as_of: datetime = FETCHED,
    ambulance: list[tuple[str, list[int]]] | None = None,
    closures: list[tuple[int, str]] | None = None,
) -> LiveStateSnapshot:
    """A live snapshot for the attach and second-order tests."""
    return LiveStateSnapshot.model_validate(
        {
            "as_of": as_of,
            "live_events": [e.model_dump() for e in events],
            "ambulance_routes": [{"dispatch_urn": u, "segment_ids": s} for u, s in ambulance or []],
            "closures": [{"segment_id": s, "event_urn": u} for s, u in closures or []],
        }
    )


def live_event(
    urn: str = "event:00000000-0000-4000-8000-000000000001",
    *,
    kind: str = "procession",
    status: str = "active",
    lonlat: tuple[float, float] | None = None,
    segments: list[int] | None = None,
) -> LiveEventRef:
    return LiveEventRef(
        urn=urn,
        event_kind=kind,  # type: ignore[arg-type]
        status=status,  # type: ignore[arg-type]
        lon=None if lonlat is None else lonlat[0],
        lat=None if lonlat is None else lonlat[1],
        segment_ids=segments or [],
    )


def offset(lonlat: tuple[float, float], north_m: float = 0.0, east_m: float = 0.0) -> tuple[float, float]:
    """A point moved by some metres north and east (small-distance approximation)."""
    import math

    lon, lat = lonlat
    dlat = north_m / 111_195.0
    dlon = east_m / (111_195.0 * math.cos(math.radians(lat)))
    return (lon + dlon, lat + dlat)


#: The OS-4 review-3 laundering cases: an AREA-level member that says nothing about the street (a SACHET Kolkata
#: alert, or a district-level GDELT report), and point-level social posts it must never corroborate.
AREA_SOCIAL_CASES = ("sachet_alert_one_post", "gdelt_district_one_post", "sachet_alert_one_community")
#: The live refs of :func:`route_live_state` (synthetic URNs).
ROUTE_FLOODING_URN = "event:00000000-0000-4000-8000-0000000000f1"
ROUTE_MOVEMENT_URN = "event:00000000-0000-4000-8000-0000000000f2"
ROUTE_ACCIDENT_URN = "event:00000000-0000-4000-8000-0000000000f3"
ROUTE_CLOSURE_URN = "event:00000000-0000-4000-8000-0000000000f4"
ROUTE_DISPATCH_URN = "dispatch:00000000-0000-4000-8000-0000000000a1"


def _post_geocode(signal: RawOsintSignal, k: int, on_route: bool) -> Geocode:
    if on_route:
        return road(signal, 1025, offset(AJC_BOSE_ROAD, north_m=20 * k), toponym="Acharya Jagadish Chandra Bose Road")
    return point(
        signal,
        offset(PARK_CIRCUS_CROSSING, north_m=20 * k),
        toponym="Park Circus seven-point crossing",
        feature_type="junction",
        junction_id=17,
        confidence=0.8,
    )


def area_social_case(
    case: str, *, on_route: bool = False
) -> tuple[RawOsintSignal, list[RawOsintSignal], FakeResolver]:
    """``(area member, posts, resolver)`` for one of :data:`AREA_SOCIAL_CASES`. The posts are at Park Circus
    seven-point crossing (junction 17), or with ``on_route`` on AJC Bose Road (segment 1025, the segment of
    :func:`route_live_state`). The area member and the posts share their words (each pair links on text)."""
    place = "on AJC Bose road" if on_route else "at Park Circus crossing"
    if case == "gdelt_district_one_post":
        area = make_signal("gdelt_doc", title="Road accident in Kolkata, two injured", publisher="news-b.example",
                           published_at=at(0))
        area_geo = district(area, toponym="Kolkata, West Bengal, India")
        titles = [f"Road accident {place}, two injured"]
    elif case in ("sachet_alert_one_post", "sachet_alert_one_community"):
        area = make_signal("sachet_cap", title="Heavy rain and waterlogging alert for Kolkata district",
                           publisher="sachet.ndma.gov.in", admin_codes=["LGD:KOLKATA"], published_at=at(0),
                           valid_until=at(600))
        area_geo = district(area)
        titles = [f"Heavy rain, waterlogging {place} right now"]
        if case == "sachet_alert_one_community":
            titles.append(f"Heavy rain, waterlogging {place} right now, still rising")
    else:  # pragma: no cover - a typo in a test
        raise ValueError(case)
    posts = [
        make_signal("reddit_rss", title=t, publisher="social-a.example/r/example_city", published_at=at(30 + 10 * k))
        for k, t in enumerate(titles)
    ]
    resolver = FakeResolver([area_geo, *(_post_geocode(p, k, on_route) for k, p in enumerate(posts))])
    return area, posts, resolver


def independent_report(case: str, tier: str = "news", *, on_route: bool = False) -> tuple[RawOsintSignal, Geocode]:
    """A point-level report of the same situation as :func:`area_social_case`'s posts, at the same place, from an
    independent publisher: a news outlet (``tier="news"``) or a civic body (``tier="official"``)."""
    place = "on AJC Bose road" if on_route else "at Park Circus crossing"
    if case == "gdelt_district_one_post":
        title = f"Road accident {place}: two injured, traffic slow"
    else:
        title = f"Waterlogging {place} after heavy rain right now"
    if tier == "official":
        report = make_signal("kmc_scrape", title=title, publisher="civic-body.example", published_at=at(40))
    else:
        report = make_signal("google_news_rss", title=title, publisher="news-c.example", published_at=at(40))
    return report, _post_geocode(report, 3, on_route)


def route_live_state(as_of: datetime | None = None) -> LiveStateSnapshot:
    """Live state on and around AJC Bose Road (segment 1025): an active flooding event and an active road accident
    200 m away, an active protected movement on the segment, an ambulance (108) route on it, and a closure of it."""
    near = offset(AJC_BOSE_ROAD, east_m=200)
    return live_state(
        live_event(ROUTE_FLOODING_URN, kind="flooding", lonlat=near),
        live_event(ROUTE_ACCIDENT_URN, kind="road_accident", lonlat=near),
        live_event(ROUTE_MOVEMENT_URN, kind="protected_movement", segments=[1025]),
        as_of=as_of or at(60),
        ambulance=[(ROUTE_DISPATCH_URN, [1025])],
        closures=[(1025, ROUTE_CLOSURE_URN)],
    )
