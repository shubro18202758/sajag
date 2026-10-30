"""run_pipeline(): the counts on the synthetic fixtures; held social; the state-wide nowcast held as outside the city;
fused_event_id stable as a member is added; labels and summaries; determinism; the optional embedder; resolver
faults; the ethics rails on the whole output."""

from __future__ import annotations

import hashlib
import json
import random
from datetime import timedelta

import pytest

from analysis_fixtures import (
    AREA_SOCIAL_CASES,
    PARK_CIRCUS_CROSSING,
    ROUTE_FLOODING_URN,
    RUBY_HOSPITAL,
    FakeResolver,
    area_social_case,
    at,
    canonical_resolver,
    canonical_signals,
    em_bypass_geocodes,
    independent_report,
    make_signal,
    point,
    route_live_state,
    ruby_hospital,
)
from osint_common import ethics, testing
from osint_common.types import PipelineResult
from osint_analysis.classify import classify
from osint_analysis.fusion import make_member
from osint_analysis.pipeline import (
    CONTEXT_ROLE,
    HELD_NOT_EVENT,
    HELD_SINGLE_SOCIAL,
    HELD_STATE_LEVEL,
    SOURCE_TITLE_MAX,
    SUMMARY_MAX,
    fit_text,
    fused_event_id,
    run_pipeline,
)


def run(signals=None, resolver=None, **kw) -> PipelineResult:
    return run_pipeline(signals or canonical_signals(), resolver=resolver or canonical_resolver(), **kw)


def test_counts_on_the_synthetic_fixtures():
    result = run(live=testing.live_state_sealdah_pursuit())
    assert result.counts.model_dump() == {
        "signals": 9,
        "geotagged": 9,
        "incident_geotagged": 8,  # 5 EM Bypass + the robbery + the two SACHET alerts; the closure is operational
        "fused": 5,
        "surfaced": 3,
        "correlated": 1,
        "cross_type_corroborated": 0,
        "social_held": 1,
        "outside_city_held": 1,
        "pii_redactions": 2,
        "attached_to_live": 0,
    }
    surfaced = [r for r in result.resolved if r.is_event]
    assert [r.event_class for r in surfaced] == ["road_accident", "reported_crime", "weather_hazard"]
    assert all(not r.is_event for r in result.resolved[3:])  # surfaced first


def test_the_three_surfaced_situations():
    by_class = {r.event_class: r for r in run().resolved if r.is_event}
    em = by_class["road_accident"]
    assert (em.subtype, em.segment_id, em.credibility, em.verification_state) == ("affray+collision", 1035, 0.65,
                                                                                  "NEWS-REPORTED")
    assert em.source_count == 5 and em.independent_publishers == 2 and em.source_tiers == ["aggregator"]
    assert em.label == "Road accident · Eastern Metropolitan Bypass"
    assert em.toponym == "Eastern Metropolitan Bypass" and em.junction_id is None and not em.area_level
    assert em.summary == testing.em_bypass_signals()[0].title
    assert [s.role for s in em.sources].count("primary") == 1 and em.sources[0].role == "primary"
    robbery = by_class["reported_crime"]
    assert (robbery.subtype, robbery.junction_id, robbery.credibility) == ("daylight_robbery", 23, 0.6)
    assert robbery.sajag_incident_kind == "robbery"
    alert = by_class["weather_hazard"]
    assert alert.area_level and alert.rep_lon is not None and alert.segment_id is None
    assert (alert.credibility, alert.verification_state, alert.source_count) == (0.95, "OFFICIAL-VERIFIED", 1)
    assert alert.label == "Weather hazard · Kolkata district"


def test_a_single_social_post_is_held_never_an_event():
    result = run()
    (held,) = [r for r in result.resolved if testing.social_single_signal().signal_id in r.member_signal_ids]
    assert not held.is_event and held.held_reason == HELD_SINGLE_SOCIAL
    assert held.credibility <= 0.30 and held.verification_state == "UNVERIFIED-OSINT"
    assert held.second_order == []
    assert result.counts.social_held == 1


_PARK_CIRCUS = "Park Circus seven-point crossing"
#: Genuinely different posts about one waterlogging (each pair links in Stage 1, none is a near-duplicate). The
#: helper once numbered ONE text ("..., update 0", "..., update 1"): near-identical, so under the cross-post rule
#: (orchestrator decision, OS-4 round 4) one source, which the two-community test below no longer meant to test.
_PARK_CIRCUS_TEXTS = (
    "Waterlogging at Park Circus crossing after heavy rain",
    "Park Circus crossing waterlogged again, two-wheelers stalled, avoid Park Street",
    "Knee-deep water at the Park Circus crossing after the heavy rain, buses diverted",
)


def _park_circus_posts(*communities: str):
    posts = [
        make_signal("reddit_rss", title=_PARK_CIRCUS_TEXTS[i], publisher=f"{c}", published_at=at(i * 20))
        for i, c in enumerate(communities)
    ]
    return posts, FakeResolver([point(p, PARK_CIRCUS_CROSSING, toponym=_PARK_CIRCUS) for p in posts])


def test_posts_of_one_social_community_are_one_source_and_held():
    # two posts in one community may be one poster: one source, never an event (credibility counts it so too)
    posts, resolver = _park_circus_posts("social-a.example/r/example_city", "social-a.example/r/example_city")
    result = run_pipeline(posts, resolver=resolver)
    (held,) = result.resolved
    assert not held.is_event and held.held_reason == HELD_SINGLE_SOCIAL and held.source_count == 2
    assert held.independent_publishers == 1 and held.credibility <= 0.30
    assert result.counts.social_held == 1 and result.counts.surfaced == 0


def test_social_posts_of_two_communities_may_surface_but_stay_unverified():
    posts, resolver = _park_circus_posts("social-a.example/r/example_city", "social-b.example/r/example_town")
    (event,) = run_pipeline(posts, resolver=resolver).resolved
    assert event.is_event and event.source_count == 2 and event.independent_publishers == 2
    assert event.verification_state == "UNVERIFIED-OSINT" and event.credibility == 0.30


def test_one_community_chatter_keeps_its_not_an_event_reason():
    posts = [make_signal("reddit_rss", title=t, publisher="social-a.example/r/example_city", published_at=at(m))
             for t, m in (("Weekend plans at Prinsep Ghat", 0), ("Any good tea stall nearby", 30))]
    resolver = FakeResolver([point(p, PARK_CIRCUS_CROSSING, toponym=_PARK_CIRCUS) for p in posts])
    (held,) = run_pipeline(posts, resolver=resolver).resolved
    assert held.held_reason == HELD_NOT_EVENT


def test_the_state_wide_nowcast_is_held_as_outside_the_city():
    nowcast = testing.sachet_state_signal()
    result = run()
    (held,) = [r for r in result.resolved if nowcast.signal_id in r.member_signal_ids]
    assert not held.is_event and held.held_reason == HELD_STATE_LEVEL
    assert held.rep_lon is None and held.area_level
    assert result.counts.outside_city_held == 1
    alone = run_pipeline([nowcast], resolver=canonical_resolver())
    assert alone.counts.outside_city_held == 1 and alone.counts.surfaced == 0


def test_not_an_event_class_is_held():
    chatter = make_signal(title="City library extends evening hours near Ruby General Hospital")
    (held,) = run_pipeline([chatter], resolver=FakeResolver([ruby_hospital(chatter)])).resolved
    assert not held.is_event and held.held_reason == HELD_NOT_EVENT and held.sajag_event_kind is None


def test_fused_event_id_is_the_anchor_hash_and_stable_as_a_member_is_added():
    em = testing.em_bypass_signals()
    first = min(em, key=lambda s: (s.published_at, s.signal_id))
    expected = hashlib.sha1(("anchor:" + first.signal_id).encode()).hexdigest()
    base = run_pipeline(em, resolver=FakeResolver(em_bypass_geocodes(em)))
    assert base.resolved[0].fused_event_id == expected == fused_event_id(em)
    later = make_signal(title="Car rammed vehicles near Ruby General Hospital on EM Bypass; three injured",
                        publisher="news-b.example", published_at=at(70))
    grown = run_pipeline([*em, later], resolver=FakeResolver([*em_bypass_geocodes(em), ruby_hospital(later)]))
    (event,) = grown.resolved
    assert later.signal_id in event.member_signal_ids and event.source_count == 6
    assert event.fused_event_id == expected  # a later member keeps the identity
    earlier = make_signal(title="Car crashes into vehicles near Ruby General Hospital on EM Bypass; 3 injured",
                          publisher="news-b.example", published_at=at(30))
    moved = run_pipeline([*em, earlier], resolver=FakeResolver([*em_bypass_geocodes(em), ruby_hospital(earlier)]))
    assert moved.resolved[0].fused_event_id == hashlib.sha1(("anchor:" + earlier.signal_id).encode()).hexdigest()
    assert moved.resolved[0].member_signal_ids[0] == earlier.signal_id  # members in anchor order


def _alert_cycles():
    """The review's identity probe: a district alert, a Shyambazar and a Garia report (cycle 1); cycle 2 adds a later
    Garia report that shares more words with the alert, so the alert re-attaches from Shyambazar to Garia."""
    from analysis_fixtures import GARIA, SHYAMBAZAR, district

    alert = make_signal("sachet_cap", title="Heavy rain and waterlogging alert for Kolkata district",
                        publisher="sachet.ndma.gov.in", admin_codes=["LGD:KOLKATA"], published_at=at(0))
    north = make_signal(title="Waterlogging at Shyambazar after heavy rain", publisher="news-a.example",
                        published_at=at(30))
    south = make_signal(title="Waterlogging at Garia after heavy rain", publisher="news-b.example", published_at=at(40))
    closer = make_signal(title="Heavy rain and waterlogging alert: Garia crossing closed", publisher="news-d.example",
                         published_at=at(45))
    geos = [district(alert), point(north, SHYAMBAZAR, toponym="Shyambazar"), point(south, GARIA, toponym="Garia"),
            point(closer, GARIA, toponym="Garia")]
    return (alert, north, south, closer), FakeResolver(geos)


def test_a_point_situation_keeps_its_id_at_its_place_when_a_district_alert_re_attaches():
    (alert, north, south, closer), resolver = _alert_cycles()
    cycle1 = run_pipeline([alert, north, south], resolver=resolver)
    cycle2 = run_pipeline([alert, north, south, closer], resolver=resolver)
    where1 = {r.fused_event_id: r.toponym for r in cycle1.resolved}
    where2 = {r.fused_event_id: r.toponym for r in cycle2.resolved}
    alert_at = {
        n: next(r.toponym for r in c.resolved if alert.signal_id in r.member_signal_ids)
        for n, c in ((1, cycle1), (2, cycle2))
    }
    assert alert_at == {1: "Shyambazar", 2: "Garia"}  # the alert really moved 15 km
    assert sorted(where1.values()) == sorted(where2.values()) == ["Garia", "Shyambazar"]
    for fid, place in where1.items():
        assert where2.get(fid, place) == place, (fid, place, where2.get(fid))  # an id never names another place
    assert set(where1) == set(where2)  # and here both ids carry on
    # each id is anchored on its earliest POINT member, never on the (earlier) area alert
    by_place = {r.toponym: r.fused_event_id for r in cycle2.resolved}
    assert by_place["Shyambazar"] == fused_event_id([north]) and by_place["Garia"] == fused_event_id([south])
    assert fused_event_id([alert]) not in where1 | where2


def test_a_district_situation_is_anchored_on_its_alert_until_a_point_report_joins():
    (alert, north, _, _), resolver = _alert_cycles()
    (alone,) = run_pipeline([alert], resolver=resolver).resolved
    assert alone.fused_event_id == fused_event_id([alert]) and alone.area_level
    (joined,) = run_pipeline([alert, north], resolver=resolver).resolved
    assert joined.toponym == "Shyambazar" and joined.fused_event_id == fused_event_id([north])


def test_a_held_situation_is_never_attached_to_a_live_event():
    from analysis_fixtures import live_event, live_state, offset

    urn = "event:00000000-0000-4000-8000-0000000000aa"
    live = live_state(live_event(urn, kind="road_accident", lonlat=offset(RUBY_HOSPITAL, east_m=300)))
    post = make_signal("reddit_rss", title="Crash near Ruby General Hospital, traffic stuck",
                       publisher="social-a.example/r/example_city", published_at=at(60))
    result = run_pipeline([post], resolver=FakeResolver([ruby_hospital(post)]), live=live)
    (held,) = result.resolved
    assert not held.is_event and held.held_reason == HELD_SINGLE_SOCIAL
    assert held.attach.novel and held.attach.corroborates_live_urn is None
    assert result.counts.attached_to_live == 0
    # the same report from a news outlet surfaces, and is attached
    news = make_signal(title="Crash near Ruby General Hospital, traffic stuck", published_at=at(60))
    surfaced = run_pipeline([news], resolver=FakeResolver([ruby_hospital(news)]), live=live)
    assert surfaced.resolved[0].attach.corroborates_live_urn == urn and surfaced.counts.attached_to_live == 1


def _held_posts_and_lone_area(result: PipelineResult, area, posts) -> None:
    """The review-3 invariants: the posts' situation is held as a single social source, unchecked against the live
    state and unflagged, counted in ``social_held``; the area member surfaces alone as a district situation."""
    post_ids = sorted(p.signal_id for p in posts)
    (held,) = [r for r in result.resolved if set(r.member_signal_ids) & set(post_ids)]
    assert sorted(held.member_signal_ids) == post_ids  # the area member never joined the posts
    assert not held.is_event and held.held_reason == HELD_SINGLE_SOCIAL
    assert held.verification_state == "UNVERIFIED-OSINT" and held.credibility <= 0.30
    assert held.source_tiers == ["social_unverified"] and not held.cross_type_corroborated
    assert held.attach.novel and held.attach.corroborates_live_urn is None  # never checked
    assert held.second_order == []
    (alone,) = [r for r in result.resolved if area.signal_id in r.member_signal_ids]
    assert alone.member_signal_ids == [area.signal_id] and alone.source_count == 1
    assert alone.is_event and alone.held_reason is None and alone.area_level
    assert alone.label.endswith("· Kolkata district") and alone.segment_id is None and alone.junction_id is None
    assert alone.attach.novel and alone.second_order == []
    assert result.counts.fused == 2 and result.counts.surfaced == 1
    assert result.counts.social_held == 1 and result.counts.cross_type_corroborated == 0
    assert result.counts.attached_to_live == 0


@pytest.mark.parametrize("case", AREA_SOCIAL_CASES)
def test_an_area_member_never_lifts_a_single_social_source_into_an_event(case):
    # review 3, cases 1, 3 and 4: a SACHET district alert + one post, a district-level GDELT report + one post, and
    # an alert + two posts of one community. The posts alone are held; the area member must not change that.
    area, posts, resolver = area_social_case(case)
    (alone,) = run_pipeline(posts, resolver=resolver).resolved
    assert not alone.is_event and alone.held_reason == HELD_SINGLE_SOCIAL
    result = run_pipeline([area, *posts], resolver=resolver)
    _held_posts_and_lone_area(result, area, posts)
    if case == "sachet_alert_one_post":  # the review's exact text
        assert posts[0].title == "Heavy rain, waterlogging at Park Circus crossing right now"
        (alert,) = [r for r in result.resolved if r.is_event]
        assert (alert.verification_state, alert.credibility) == ("OFFICIAL-VERIFIED", 0.95)


@pytest.mark.parametrize("case", AREA_SOCIAL_CASES)
def test_an_area_member_never_links_a_social_post_to_the_live_state(case):
    # review 3, case 2: the posts on segment 1025, a live flooding event and a live accident 200 m away, a protected
    # movement, a 108 route and a closure on the segment. Nothing may be attached and nothing flagged.
    area, posts, resolver = area_social_case(case, on_route=True)
    live = route_live_state()
    result = run_pipeline([area, *posts], resolver=resolver, live=live)
    _held_posts_and_lone_area(result, area, posts)
    assert all(r.second_order == [] for r in result.resolved)
    assert all(r.attach.corroborates_live_urn is None for r in result.resolved)


@pytest.mark.parametrize("tier", ["news", "official"])
@pytest.mark.parametrize("case", AREA_SOCIAL_CASES)
def test_an_independent_point_level_report_still_surfaces_the_situation(case, tier):
    # the positive control: legitimate corroboration of the posts is a POINT-level report of the same situation
    area, posts, resolver = area_social_case(case)
    report, report_geo = independent_report(case, tier)
    resolver.add(report_geo)
    (event,) = run_pipeline([*posts, report], resolver=resolver).resolved
    assert event.is_event and event.held_reason is None and event.cross_type_corroborated
    assert sorted(event.member_signal_ids) == sorted(s.signal_id for s in (*posts, report))
    # news 0.60 + 0.15 cross-type; official 0.90 + 0.15, at the 0.99 ceiling
    expected = {"news": ("NEWS-REPORTED", 0.75), "official": ("OFFICIAL-VERIFIED", 0.99)}[tier]
    assert (event.verification_state, event.credibility) == expected
    assert event.junction_id == 17 and not event.area_level
    # with the area member too, the street situation still surfaces (the area joins it: it is no longer social-only)
    result = run_pipeline([area, *posts, report], resolver=resolver)
    (street,) = [r for r in result.resolved if report.signal_id in r.member_signal_ids]
    assert street.is_event and street.held_reason is None and street.junction_id == 17
    assert set(street.member_signal_ids) == {s.signal_id for s in (area, *posts, report)}
    assert result.counts.social_held == 0 and result.counts.surfaced == 1
    # ... but the area member is context, never verification (orchestrator decision, OS-4 round 4): the street
    # situation keeps the point-level state and credibility (a SACHET alert never makes a news report
    # OFFICIAL-VERIFIED 0.99, nor a district-level GDELT report add a publisher bump), and the area member is
    # listed last, as context
    assert (street.verification_state, street.credibility) == expected
    assert street.source_tiers == event.source_tiers and street.labels == event.labels
    assert street.independent_publishers == event.independent_publishers
    assert (street.window_start, street.window_end) == (event.window_start, event.window_end)
    assert street.sources[-1].signal_id == area.signal_id and street.sources[-1].role == CONTEXT_ROLE
    assert [s.signal_id for s in street.sources[:-1]] == [s.signal_id for s in event.sources]


def _rain_alert_at_park_circus(source: str = "google_news_rss", publisher: str = "news-a.example"):
    """A district SACHET alert (valid 10 h) and one point-level report at Park Circus that the alert joins."""
    from analysis_fixtures import district

    alert = make_signal("sachet_cap", title="Heavy rain and waterlogging alert for Kolkata district",
                        publisher="sachet.ndma.gov.in", admin_codes=["LGD:KOLKATA"], published_at=at(0),
                        valid_until=at(600))
    report = make_signal(source, title="Waterlogging at Park Circus after heavy rain", publisher=publisher,
                         published_at=at(30))
    return alert, report, FakeResolver([district(alert), point(report, PARK_CIRCUS_CROSSING, toponym="Park Circus")])


@pytest.mark.parametrize(
    ("source", "publisher", "expected"),
    [
        ("google_news_rss", "news-a.example", ("NEWS-REPORTED", 0.6, ["aggregator"])),
        ("gdelt_doc", "news-b.example", ("NEWS-REPORTED", 0.6, ["news_regional"])),
        # an official source reporting the point-level situation itself: the one way to OFFICIAL-VERIFIED
        ("kmc_scrape", "civic-body.example", ("OFFICIAL-VERIFIED", 0.9, ["official"])),
    ],
)
def test_an_area_alert_is_context_never_verification(source, publisher, expected):
    # orchestrator decision (OS-4 round 4): a district alert attached to a point situation raises neither its
    # credibility nor its verification state (before: a news report + the alert = OFFICIAL-VERIFIED 0.99,
    # cross-type corroborated), and it stays attached and visible as context
    alert, report, resolver = _rain_alert_at_park_circus(source, publisher)
    (alone,) = run_pipeline([report], resolver=resolver).resolved
    result = run_pipeline([alert, report], resolver=resolver)
    (event,) = result.resolved
    assert event.member_signal_ids == [alert.signal_id, report.signal_id] and event.source_count == 2
    assert event.is_event and event.toponym == "Park Circus" and not event.area_level
    assert (event.verification_state, event.credibility, event.source_tiers) == expected
    assert (alone.verification_state, alone.credibility, alone.source_tiers) == expected  # the same as without it
    assert not event.cross_type_corroborated and result.counts.cross_type_corroborated == 0
    assert event.independent_publishers == 1 and event.labels == [expected[0]]
    assert event.fused_event_id == alone.fused_event_id == fused_event_id([report])
    # visible as context: a source, after the point-level ones, with the context role (its URL kept: official)
    assert [(s.signal_id, s.role) for s in event.sources] == [(report.signal_id, "primary"),
                                                             (alert.signal_id, CONTEXT_ROLE)]
    assert event.sources[-1].source == "sachet_cap" and event.sources[-1].url == alert.url
    # the alert's validity (10 h) never extends the street situation's window
    assert (event.window_start, event.window_end) == (at(30), at(30)) == (alone.window_start, alone.window_end)


def test_context_role_is_context_once_the_contract_has_it():
    from typing import get_args

    from osint_common.types import SourceRole

    assert CONTEXT_ROLE == ("context" if "context" in get_args(SourceRole) else "corroborating")
    assert CONTEXT_ROLE in get_args(SourceRole)


def test_an_area_alerts_validity_never_keeps_a_street_report_current_for_the_live_state():
    # decision 2 on the live checks: the alert (valid to +10 h) is context, so the report alone times the situation.
    # At 49 h after the report (beyond its 48 h window, within the alert's validity + 48 h) nothing is attached or
    # flagged; at +60 min the same situation is attached and flagged.
    from analysis_fixtures import AJC_BOSE_ROAD, district, road

    alert, _, _ = _rain_alert_at_park_circus()
    report = make_signal(title="Waterlogging on AJC Bose road after heavy rain", published_at=at(40))
    resolver = FakeResolver([district(alert), road(report, 1025, AJC_BOSE_ROAD, toponym="AJC Bose Road")])
    late = route_live_state(as_of=at(40 + 49 * 60))
    (event,) = run_pipeline([alert, report], resolver=resolver, live=late).resolved
    assert alert.signal_id in event.member_signal_ids and event.window_end == at(40)
    assert event.attach.novel and event.attach.corroborates_live_urn is None and event.second_order == []
    (current,) = run_pipeline([alert, report], resolver=resolver, live=route_live_state()).resolved
    assert current.attach.corroborates_live_urn == ROUTE_FLOODING_URN
    assert [f.kind for f in current.second_order] == ["protected_corridor", "ambulance_route", "closure"]


def test_a_cross_post_in_two_communities_is_held_as_a_single_social_source():
    # orchestrator decision (OS-4 round 4), the review's p_social_alert.py case 3: the same text in two communities
    # three minutes apart was surfaced as a road_accident event (UNVERIFIED-OSINT 0.30); it may be one poster
    text = "Car crash at Park Circus crossing, two injured"
    a = make_signal("reddit_rss", title=text, publisher="social-a.example/r/example_city", published_at=at(0))
    b = make_signal("reddit_rss", title=text, publisher="social-b.example/r/example_town", published_at=at(3))
    resolver = FakeResolver([point(x, PARK_CIRCUS_CROSSING, toponym=_PARK_CIRCUS, feature_type="junction",
                                   junction_id=17) for x in (a, b)])
    result = run_pipeline([a, b], resolver=resolver)
    (held,) = result.resolved
    assert held.source_count == 2 and held.event_class == "road_accident"
    assert not held.is_event and held.held_reason == HELD_SINGLE_SOCIAL
    assert held.credibility <= 0.30 and held.verification_state == "UNVERIFIED-OSINT"
    assert held.independent_publishers == 1 and held.attach.novel and held.second_order == []
    assert result.counts.social_held == 1 and result.counts.surfaced == 0
    # the positive control: a genuinely different post in the second community surfaces as before
    c = make_signal("reddit_rss", title="Crash at Park Circus crossing: an auto overturned, two hurt, traffic slow",
                    publisher="social-b.example/r/example_town", published_at=at(3))  # links, not a near-duplicate
    resolver.add(point(c, PARK_CIRCUS_CROSSING, toponym=_PARK_CIRCUS, feature_type="junction", junction_id=17))
    (event,) = run_pipeline([a, c], resolver=resolver).resolved
    assert event.is_event and event.independent_publishers == 2
    assert (event.verification_state, event.credibility) == ("UNVERIFIED-OSINT", 0.30)


def test_an_independent_report_on_the_route_is_attached_and_flagged():
    # the positive control on the live state: a news report with the post is checked, attached and flagged
    area, posts, resolver = area_social_case("sachet_alert_one_post", on_route=True)
    report, report_geo = independent_report("sachet_alert_one_post", on_route=True)
    resolver.add(report_geo)
    result = run_pipeline([*posts, report], resolver=resolver, live=route_live_state())
    (event,) = result.resolved
    assert event.is_event and event.attach.corroborates_live_urn == ROUTE_FLOODING_URN
    assert [f.kind for f in event.second_order] == ["protected_corridor", "ambulance_route", "closure"]
    assert result.counts.attached_to_live == 1


@pytest.mark.parametrize("case", AREA_SOCIAL_CASES)
def test_held_reason_reads_the_point_level_members_whatever_fusion_did(case):
    # defence in depth: even a situation in which an area member DID join the posts (fusion no longer builds one)
    # is held as a single social source, never checked against the live state and never flagged
    from osint_analysis.correlate import correlate
    from osint_analysis.fusion import BaseCluster
    from osint_analysis.pipeline import _resolved_event

    area, posts, resolver = area_social_case(case, on_route=True)
    members = sorted(
        (make_member(s, resolver.by_id[s.signal_id], classify(s)) for s in (area, *posts)), key=lambda m: m.sort_key
    )
    (situation,) = correlate([BaseCluster(tuple(members))])
    assert {m.scope for m in situation.members} == {"district", "point"}
    event = _resolved_event(situation, route_live_state())
    assert not event.is_event and event.held_reason == HELD_SINGLE_SOCIAL
    assert event.attach.novel and event.attach.corroborates_live_urn is None and event.second_order == []
    # an independent point-level report lifts it, the area member present or not
    report, report_geo = independent_report(case, on_route=True)
    with_report = sorted([*members, make_member(report, report_geo, classify(report))], key=lambda m: m.sort_key)
    (situation,) = correlate([BaseCluster(tuple(with_report))])
    assert _resolved_event(situation, None).is_event
    # an area-only situation is anchored (and judged) on all its members: the alert alone still surfaces
    (area_only,) = correlate([BaseCluster((make_member(area, resolver.by_id[area.signal_id], classify(area)),))])
    assert _resolved_event(area_only, None).is_event


@pytest.mark.parametrize("toponym", ["Kolkata (district)", "Kolkata, West Bengal, India", "Kolkata district"])
def test_a_district_label_names_the_district_once(toponym):
    from analysis_fixtures import district

    s = make_signal("gdelt_doc", title="Thunderstorm warning issued for the city", publisher="news-b.example")
    (event,) = run_pipeline([s], resolver=FakeResolver([district(s, toponym=toponym)])).resolved
    assert event.label == "Weather hazard · Kolkata district"


def test_source_urls_are_kept_for_official_sources_only():
    from analysis_fixtures import district

    alert = make_signal("sachet_cap", title="Heavy rain warning for Kolkata district", publisher="sachet.ndma.gov.in",
                        url="https://sachet.ndma.gov.in/cap_public_website/FetchXMLFile?identifier=1",
                        admin_codes=["LGD:KOLKATA"])
    news = make_signal(title="Multi-vehicle crash near Ruby General Hospital", publisher="news-a.example")
    wire = make_signal("gdelt_doc", title="Multi-vehicle crash near Ruby General Hospital on EM Bypass",
                       publisher="news-b.example")
    post = make_signal("reddit_rss", title="Crash near Ruby General Hospital",
                       publisher="social-a.example/r/example_city",
                       url="https://social-a.example/r/example_city/comments/abc/crash_near_ruby_crossing/")
    signals = [alert, news, wire, post]
    assert all(s.url for s in signals)
    resolver = FakeResolver([district(alert), ruby_hospital(news), ruby_hospital(wire), ruby_hospital(post)])
    sources = {s.signal_id: s for r in run_pipeline(signals, resolver=resolver).resolved for s in r.sources}
    assert sources[alert.signal_id].url == alert.url  # official: an identifier-only path
    for s in (news, wire, post):
        assert sources[s.signal_id].url is None  # a news or social URL slug can name a person: withheld
        assert sources[s.signal_id].publisher == s.publisher  # the source stays verifiable by its outlet and id


def test_deterministic_in_any_input_order():
    signals = canonical_signals()
    live = testing.live_state_sealdah_pursuit()
    reference = run(signals, live=live).model_dump_json()
    rng = random.Random(11)
    for _ in range(5):
        order = signals[:]
        rng.shuffle(order)
        assert run(order, live=live).model_dump_json() == reference


def test_duplicate_signals_count_once():
    signals = canonical_signals()
    result = run([*signals, signals[0], signals[3]])
    assert result.counts.signals == 9 and result.counts.fused == 5


def test_an_unresolved_signal_is_counted_but_forms_no_situation():
    signals = canonical_signals()
    resolver = canonical_resolver()
    del resolver.by_id[testing.gariahat_robbery_signal().signal_id]
    result = run(signals, resolver)
    assert result.geocodes[testing.gariahat_robbery_signal().signal_id] is None
    assert result.classifications[testing.gariahat_robbery_signal().signal_id].event_class == "reported_crime"
    assert result.counts.geotagged == 8 and result.counts.surfaced == 2


def test_a_resolver_fault_never_sinks_the_batch_or_misplaces_a_report():
    signals = canonical_signals()
    good = canonical_resolver()
    robbery = testing.gariahat_robbery_signal().signal_id
    em0 = signals[0]

    state_id = testing.sachet_state_signal().signal_id

    class Faulty:
        def resolve(self, signal):
            if signal.signal_id == robbery:
                raise RuntimeError("gazetteer glitch")
            if signal.signal_id == testing.social_single_signal().signal_id:
                return good.by_id[em0.signal_id]  # someone else's geocode: refused
            if signal.signal_id == state_id:
                return {"signal_id": state_id, "method": "area_fallback", "confidence": 0.9, "bucket": "low",
                        "area_level": True, "area_scope": "state"}  # invalid: a state geocode is <= 0.25
            if signal.signal_id == em0.signal_id:
                return good.resolve(signal).model_dump()  # a valid mapping is accepted
            return good.resolve(signal)

    result = run_pipeline(signals, resolver=Faulty())
    assert result.geocodes[robbery] is None
    assert result.geocodes[testing.social_single_signal().signal_id] is None
    assert result.geocodes[state_id] is None
    assert result.geocodes[em0.signal_id] is not None
    assert result.counts.surfaced == 2 and result.counts.geotagged == 6


def test_the_resolver_is_required():
    with pytest.raises(TypeError):
        run_pipeline(canonical_signals(), resolver=None)  # type: ignore[arg-type]


@pytest.mark.parametrize("failure", ["none", "raise", "ragged", "zero"])
def test_a_failing_embedder_changes_nothing(failure):
    class Broken:
        def embed(self, texts):
            if failure == "raise":
                raise TimeoutError("embedding service slow")
            if failure == "ragged":
                return [[1.0, 0.0]] + [[1.0] for _ in texts[1:]]
            if failure == "zero":
                return [[0.0, 0.0] for _ in texts]
            return None

    assert run(embedder=Broken()).model_dump_json() == run().model_dump_json()


def test_an_answering_embedder_drives_the_text_gate():
    class Same:
        """Every report the same vector, every exemplar orthogonal to it: one situation, no zero-shot class."""

        def embed(self, texts):
            from osint_analysis.classify import ZERO_SHOT_EXEMPLARS

            ex = list(ZERO_SHOT_EXEMPLARS.values())
            dim = len(ex) + 1
            return [[1.0 if (t in ex and i == ex.index(t)) or (t not in ex and i == dim - 1) else 0.0
                     for i in range(dim)] for t in texts]

    em = testing.em_bypass_signals()
    result = run_pipeline(em, resolver=FakeResolver(em_bypass_geocodes(em)), embedder=Same())
    (event,) = result.resolved
    assert event.correlated_classes == ["road_accident", "public_conflict"] and event.source_count == 5


def test_now_bounds_future_dated_reports_but_never_the_identity():
    future = make_signal(title="Multi-vehicle crash near Ruby General Hospital", published_at=at(600),
                         fetched_at=at(700))
    resolver = FakeResolver([ruby_hospital(future)])
    free = run_pipeline([future], resolver=resolver).resolved[0]
    bounded = run_pipeline([future], resolver=resolver, now=at(120)).resolved[0]
    assert free.window_start == at(600) and bounded.window_start == at(120)
    assert free.fused_event_id == bounded.fused_event_id
    # a source clock ahead of the fetch: the report was not published after it was fetched
    skew = make_signal(title="Multi-vehicle crash near Ruby General Hospital", published_at=at(300), fetched_at=at(100))
    (r,) = run_pipeline([skew], resolver=FakeResolver([ruby_hospital(skew)])).resolved
    assert r.window_start == at(100)


def test_a_handle_that_slipped_through_parse_never_reaches_the_summary():
    posts = [
        make_signal("reddit_rss", title=f"Waterlogging at Park Circus crossing, submitted by /u/example_user{i}",
                    publisher="social-a.example/r/example_city", published_at=at(i))
        for i in range(2)
    ]
    resolver = FakeResolver([point(p, PARK_CIRCUS_CROSSING, toponym=_PARK_CIRCUS) for p in posts])
    (event,) = run_pipeline(posts, resolver=resolver).resolved
    # the Reddit trailer is dropped whole (the same helper the analysis reads through)
    assert event.summary == "Waterlogging at Park Circus crossing"
    assert all(s.title == "Waterlogging at Park Circus crossing" for s in event.sources)
    # any other handle is redacted
    other = make_signal("reddit_rss", title="Underpass flooded, photo by u/example_user", text="Underpass flooded",
                        publisher="social-a.example/r/example_city")
    (held,) = run_pipeline([other], resolver=FakeResolver([point(other, PARK_CIRCUS_CROSSING)])).resolved
    assert held.summary == "Underpass flooded, photo by [PERSON]"


def test_a_redaction_that_lengthens_a_full_length_title_never_sinks_the_batch():
    # '/u/abc' (6 characters) becomes '[PERSON]' (8): a 1000-character title would overflow SourceRef.title
    tail = " /u/abc"
    title = ("Waterlogging at Park Circus crossing " * 40)[: 1000 - len(tail)].rstrip() + tail
    title = title + " " * (1000 - len(title)) if len(title) < 1000 else title
    assert len(title) <= 1000
    post = make_signal("reddit_rss", title=title, text="Waterlogging at Park Circus crossing",
                       publisher="social-a.example/r/example_city", published_at=at(0))
    news = make_signal(title="Multi-vehicle crash near Ruby General Hospital", published_at=at(5))
    resolver = FakeResolver([point(post, PARK_CIRCUS_CROSSING, toponym=_PARK_CIRCUS), ruby_hospital(news)])
    result = run_pipeline([post, news], resolver=resolver)  # must not raise
    assert result.counts.fused == 2 and result.counts.surfaced == 1
    (held,) = [r for r in result.resolved if not r.is_event]
    assert all(len(s.title) <= SOURCE_TITLE_MAX and "/u/" not in s.title for s in held.sources)
    assert "/u/" not in held.summary and len(held.summary) <= SUMMARY_MAX


def test_fit_text_clips_after_redacting_and_checks_again():
    assert fit_text("short /u/abc", 1000) == "short [PERSON]"
    long = "x" * 995 + " /u/abc"
    got = fit_text(long, 1000)
    assert len(got) <= 1000 and "/u/" not in got and got.endswith("…")
    assert fit_text("a  b\n c", 200, collapse=True) == "a b c"
    assert fit_text("a  b", 200) == "a  b"  # a source title keeps its own spacing


def _honorific_place() -> tuple[str, str] | None:
    """A gazetteer place whose name starts with an honorific ("Dr. <name> Road") and its first two words, which
    alone read as a name. Read from the gazetteer AT RUN TIME and never written here (ethics rule 9: no real
    person's name in a committed file, not even inside a place name)."""
    path = ethics.gazetteer_path()
    if path is None:
        return None
    for entry in json.loads(path.read_text(encoding="utf-8")).get("entries", []):
        base = str(entry.get("canonical_name") or "").split("(")[0].strip()
        words = base.split()
        if len(words) >= 3 and words[0].rstrip(".") in ethics.HONORIFIC_CUES and base.isascii():
            fragment = " ".join(words[:2])
            if not ethics.find_pii(f"Traffic near {base} after the crash") and ethics.find_pii(f"Near {fragment}…"):
                return base, fragment
    return None


def test_a_clip_that_cuts_a_protected_place_never_leaves_a_name_fragment():
    # a protected gazetteer place "Dr. <name> Road" whose first two words alone read as a name: a clip at 200 that
    # lands between them must not fail the output model (it would sink the whole batch)
    found = _honorific_place()
    if found is None:
        pytest.skip("no gazetteer place that starts with an honorific is available here")
    place, fragment = found
    head = "Multi-vehicle crash: traffic slowed for an hour near "
    keep = SUMMARY_MAX - 1 - len(fragment)  # the clip keeps SUMMARY_MAX - 1 characters, then "…"
    body = (head + "the old market gate and the market square and " * 4)[: keep - 1].rstrip()
    prefix = body + "x" * (keep - 1 - len(body)) + " "
    title = prefix + place + " after the crash"
    assert len(prefix) == keep and "  " not in title
    cut = title[: SUMMARY_MAX - 1]
    assert cut.endswith(fragment) and ethics.find_pii(cut + "…")  # the naive clip would be refused
    crash = make_signal(title=title)
    (event,) = run_pipeline([crash], resolver=FakeResolver([ruby_hospital(crash)])).resolved
    assert len(event.summary) <= SUMMARY_MAX and ethics.find_pii(event.summary) == []
    assert event.summary.startswith(head)


def test_a_label_never_carries_a_name_even_from_an_odd_toponym():
    crash = make_signal(title="Multi-vehicle crash near the market")
    odd = point(crash, RUBY_HOSPITAL, toponym="Dr Example Market", segment_id=1035, residual_m=50.0)
    (event,) = run_pipeline([crash], resolver=FakeResolver([odd])).resolved
    assert event.label == "Road accident · segment 1035"
    assert ethics.find_pii(event.label) == []


def test_summary_is_at_most_200_characters():
    long_title = "Multi-vehicle crash near Ruby General Hospital " + "with traffic backed up for kilometres " * 12
    crash = make_signal(title=long_title.strip())
    (event,) = run_pipeline([crash], resolver=FakeResolver([ruby_hospital(crash)])).resolved
    assert len(event.summary) <= 200 and event.summary.endswith("…")


def test_the_output_carries_no_person_key_and_never_crime_incident():
    result = run(live=testing.live_state_sealdah_pursuit())
    dumped = result.model_dump(mode="json")
    ethics.assert_no_person_keys(dumped)
    blob = json.dumps(dumped)
    assert "crime_incident" not in blob and "vehicle_pursuit" not in blob
    for r in result.resolved:
        assert ethics.find_pii(r.label) == [] and ethics.find_pii(r.summary) == []
        assert all(ethics.find_pii(s.title) == [] for s in r.sources)
    assert set(result.classifications) == set(result.geocodes) == {s.signal_id for s in canonical_signals()}


def test_the_result_round_trips_through_its_model():
    result = run(live=testing.live_state_sealdah_pursuit())
    assert PipelineResult.model_validate_json(result.model_dump_json()) == result


def test_simulated_inputs_pass_through_labelled_never_upgraded():
    sims = [make_signal(title="Multi-vehicle crash near Ruby General Hospital", publisher=p,
                        provenance_label="SIMULATED") for p in ("news-a.example", "news-b.example")]
    (event,) = run_pipeline(sims, resolver=FakeResolver([ruby_hospital(s) for s in sims])).resolved
    assert event.is_event and event.verification_state == "SIMULATED" and event.labels == ["SIMULATED"]
    assert event.credibility == 0.6 and not event.cross_type_corroborated


def test_pipeline_fuzz_never_raises_and_keeps_its_invariants():
    from analysis_fixtures import district, offset, road, state

    rng = random.Random(20261024)
    cues = ["Multi-vehicle crash", "Shop robbed", "Stone pelting", "Massive fire", "Waterlogging", "Wall collapse",
            "Huge crowd", "Traders observe bandh", "Road closed for metro work", "Thunderstorm warning",
            "City library extends hours", "Heavy rain warning"]
    sources = {
        "google_news_rss": ["news-a.example", "news-b.example", "m.news-a.example"],
        "gdelt_doc": ["news-c.example"],
        "reddit_rss": ["social-a.example/r/example_city", "social-b.example/r/example_town"],
        "sachet_cap": ["sachet.ndma.gov.in"],
    }
    signals, geos = [], []
    for i in range(300):
        src = rng.choice(list(sources))
        label = rng.choice([None, None, None, "SIMULATED", "EMULATED"])
        s = make_signal(src, title=f"{rng.choice(cues)} near the circle, update {i % 7}",
                        publisher=rng.choice(sources[src]),
                        published_at=at(rng.uniform(-600, 3000)), provenance_label=label,
                        valid_until=at(3200) if src == "sachet_cap" and rng.random() < 0.5 else None)
        signals.append(s)
        kind = rng.random()
        where = offset(RUBY_HOSPITAL, north_m=rng.uniform(-3000, 3000), east_m=rng.uniform(-3000, 3000))
        if rng.random() < 0.1:
            continue  # an honest None
        if kind < 0.08:
            geos.append(state(s))
        elif kind < 0.16:
            geos.append(district(s))
        elif kind < 0.40:
            geos.append(road(s, rng.choice([1025, 1020, 1035]), where))
        else:
            geos.append(point(s, where, segment_id=rng.choice([None, 1035]), residual_m=rng.uniform(0, 1500),
                              confidence=rng.uniform(0.3, 0.95)))
    live = testing.live_state_sealdah_pursuit()
    result = run_pipeline(signals, resolver=FakeResolver(geos), live=live)
    c = result.counts
    assert c.signals == 300 and c.geotagged == len(geos) and c.fused == len(result.resolved)
    assert sum(r.source_count for r in result.resolved) == c.geotagged  # every geocoded signal in one situation
    seen = [sid for r in result.resolved for sid in r.member_signal_ids]
    assert len(seen) == len(set(seen))
    for r in result.resolved:
        assert r.sajag_event_kind not in ("crime_incident", "vehicle_pursuit")
        assert r.is_event == (r.held_reason is None)
        if r.is_event:
            assert r.rep_lon is not None and r.sajag_event_kind is not None
            assert not (r.source_tiers == ["social_unverified"] and r.source_count == 1)
        if r.source_tiers == ["social_unverified"] and r.source_count == 1:
            assert r.credibility <= 0.30
        if r.verification_state == "OFFICIAL-VERIFIED":
            assert "official" in r.source_tiers
        assert len({lab for lab in r.labels} & {"SIMULATED", "EMULATED"}) == 0 or r.verification_state in (
            "SIMULATED", "EMULATED")
    assert c.surfaced == sum(r.is_event for r in result.resolved)
    assert run_pipeline(list(reversed(signals)), resolver=FakeResolver(geos), live=live) == result


def test_window_and_validity():
    alert = testing.sachet_district_signal()  # valid 3 h
    (event,) = [r for r in run().resolved if r.event_class == "weather_hazard" and r.is_event]
    assert event.window_start == alert.published_at
    assert event.window_end == alert.valid_until == alert.published_at + timedelta(hours=3)
