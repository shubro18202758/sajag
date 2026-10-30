"""Stage 1 (fusion.stage1): deduplication within a class, never across classes; area blocking by level (plan R28);
the time windows; the text gate; line geocodes; held aggregates; determinism; the vectorised linking against its
pairwise definition, and its cost on a dense block."""

from __future__ import annotations

import random

import numpy as np
import pytest

from analysis_fixtures import (
    AJC_BOSE_ROAD,
    AREA_SOCIAL_CASES,
    BEHALA_CHOWRASTA,
    GARIA,
    GARIAHAT_CROSSING,
    PARK_CIRCUS_CROSSING,
    RUBY_HOSPITAL,
    SHYAMBAZAR,
    FakeResolver,
    area_social_case,
    at,
    district,
    em_bypass_geocodes,
    independent_report,
    make_signal,
    offset,
    point,
    road,
    ruby_hospital,
    state,
)
from osint_common import testing
from osint_analysis import fusion
from osint_analysis.classify import classify
from osint_analysis.fusion import (
    CLUSTER_SPAN_M,
    LEXICAL_THRESHOLD,
    POINT_EPS_M,
    POINT_WINDOW,
    BaseCluster,
    UnionFind,
    area_key_for,
    colocated,
    content_tokens,
    haversine_m,
    interval_gap,
    jaccard,
    link_strength,
    make_member,
    social_only,
    stage1,
)
from osint_analysis.pipeline import fused_event_id, run_pipeline


def members_of(signals, geocodes):
    by_id = {g.signal_id: g for g in geocodes}
    return [make_member(s, by_id[s.signal_id], classify(s)) for s in signals]


def cluster_sets(clusters):
    return sorted(sorted(m.signal_id for m in c.members) for c in clusters)


def _park_circus(signal):
    """Park Circus seven-point crossing, junction 17."""
    return point(signal, PARK_CIRCUS_CROSSING, toponym="Park Circus seven-point crossing", feature_type="junction",
                 junction_id=17)


def test_the_four_em_bypass_collision_reports_deduplicate_into_one_base_cluster():
    em = testing.em_bypass_signals()
    clusters = stage1(members_of(em, em_bypass_geocodes(em)))
    by_class = {}
    for c in clusters:
        by_class.setdefault(c.event_class, []).append(c)
    assert len(by_class["road_accident"]) == 1
    assert {m.signal_id for m in by_class["road_accident"][0].members} == {s.signal_id for s in em[:4]}
    # Stage 1 never merges across classes: the "beaten by mob" report is its own public_conflict cluster
    assert [[m.signal_id for m in c.members] for c in by_class["public_conflict"]] == [[em[4].signal_id]]
    assert all(len({m.event_class for m in c.members}) == 1 for c in clusters)


def test_no_merge_across_classes_even_at_one_point_with_the_same_words():
    a = make_signal(title="Fire at a showroom on EM Bypass near Ruby General Hospital, traffic slowed")
    b = make_signal(title="Car crash at a showroom on EM Bypass near Ruby General Hospital, traffic slowed")
    assert classify(a).event_class == "fire" and classify(b).event_class == "road_accident"
    clusters = stage1(members_of([a, b], [ruby_hospital(a), ruby_hospital(b)]))
    assert cluster_sets(clusters) == sorted([[a.signal_id], [b.signal_id]])


def test_same_class_far_apart_or_beyond_the_window_stays_separate():
    title = "Multi-vehicle crash on EM Bypass near Ruby General Hospital, three injured"
    a = make_signal(title=title, published_at=at(0))
    far = make_signal(title=title, published_at=at(10))
    late = make_signal(title=title, published_at=at(7 * 60))  # point incidents: 6 h window
    geos = [ruby_hospital(a), point(far, offset(RUBY_HOSPITAL, north_m=1500)), ruby_hospital(late)]
    clusters = stage1(members_of([a, far, late], geos))
    assert cluster_sets(clusters) == sorted([[a.signal_id], [far.signal_id], [late.signal_id]])


def test_within_900_m_and_6_h_links():
    title = "Multi-vehicle crash on EM Bypass near Ruby General Hospital, three injured"
    a = make_signal(title=title, published_at=at(0))
    b = make_signal(title=title, publisher="news-b.example", published_at=at(5 * 60))
    geos = [ruby_hospital(a), point(b, offset(RUBY_HOSPITAL, east_m=800))]
    assert 790 < haversine_m(geos[0].lat, geos[0].lon, geos[1].lat, geos[1].lon) < POINT_EPS_M
    clusters = stage1(members_of([a, b], geos))
    assert cluster_sets(clusters) == [sorted([a.signal_id, b.signal_id])]


def test_ongoing_situations_use_the_48_h_window():
    a = make_signal(title="Waterlogging at Park Circus crossing after heavy rain", published_at=at(0))
    b = make_signal(title="Park Circus crossing waterlogging persists after heavy rain", publisher="news-b.example",
                    published_at=at(30 * 60))
    c = make_signal(title="Waterlogging at Park Circus crossing after heavy rain", published_at=at(80 * 60))
    geos = [_park_circus(s) for s in (a, b, c)]
    clusters = stage1(members_of([a, b, c], geos))
    assert cluster_sets(clusters) == sorted([sorted([a.signal_id, b.signal_id]), [c.signal_id]])


def test_the_text_gate_keeps_unrelated_reports_of_one_class_apart():
    a = make_signal(title="Car crashes into three vehicles near Ruby General Hospital on EM Bypass; 3 injured")
    b = make_signal(title="Truck overturns on EM Bypass near Kasba, cleaner hurt", publisher="news-b.example")
    ma, mb = members_of([a, b], [ruby_hospital(a), ruby_hospital(b)])
    assert jaccard(ma.tokens, mb.tokens) < LEXICAL_THRESHOLD
    assert cluster_sets(stage1([ma, mb])) == sorted([[a.signal_id], [b.signal_id]])


def test_with_an_embedder_the_text_gate_is_cosine():
    a = make_signal(title="Car crashes into three vehicles near Ruby General Hospital on EM Bypass; 3 injured")
    b = make_signal(title="Truck overturns on EM Bypass near Kasba, cleaner hurt", publisher="news-b.example")
    ms = members_of([a, b], [ruby_hospital(a), ruby_hospital(b)])
    same = {a.signal_id: np.array([1.0, 0.0]), b.signal_id: np.array([0.8, 0.6])}  # cosine 0.80
    apart = {a.signal_id: np.array([1.0, 0.0]), b.signal_id: np.array([0.6, 0.8])}  # cosine 0.60
    assert cluster_sets(stage1(ms, vectors=same)) == [sorted([a.signal_id, b.signal_id])]
    assert cluster_sets(stage1(ms, vectors=apart)) == sorted([[a.signal_id], [b.signal_id]])


def test_line_geocodes_block_by_shared_segment():
    # a report geocoded to the road itself (segment 1035, its representative point 1.6 km away) and a landmark
    # snapped onto that segment (190.5 m): one place
    title = "Multi-vehicle crash on EM Bypass near Ruby General Hospital, three injured"
    lm = make_signal(title=title)
    rd = make_signal(title=title, publisher="news-b.example")
    geos = [ruby_hospital(lm), road(rd, 1035, offset(RUBY_HOSPITAL, north_m=1600))]
    assert cluster_sets(stage1(members_of([lm, rd], geos))) == [sorted([lm.signal_id, rd.signal_id])]
    # two landmarks 1.6 km apart that merely snap to the same segment are not one place without a line report
    other = make_signal(title=title, publisher="news-b.example")
    far = point(other, offset(RUBY_HOSPITAL, north_m=1600), segment_id=1035, residual_m=300.0)
    assert len(stage1(members_of([lm, other], [ruby_hospital(lm), far]))) == 2
    # a point snapped from beyond 900 m is not ON its segment
    loose = make_signal(title=title, publisher="news-b.example")
    loose_geo = point(loose, offset(RUBY_HOSPITAL, north_m=1600), segment_id=1035, residual_m=1400.0)
    rd2 = make_signal(title=title)
    rd2_geo = road(rd2, 1035, offset(RUBY_HOSPITAL, north_m=-1400))
    assert len(stage1(members_of([loose, rd2], [loose_geo, rd2_geo]))) == 2


def test_a_dense_field_of_similar_reports_never_chains_across_the_city():
    # one waterlogging report every 500 m along 6 km: each neighbour pair links, but no cluster may span more than
    # CLUSTER_SPAN_M between two point reports (single linkage would make one 6 km situation)
    reports = [make_signal(title="Waterlogging after heavy rain, traffic slow", publisher=f"news-{c}.example",
                           published_at=at(k)) for k, c in enumerate("abcdefghijklm")]
    geos = [point(r, offset(PARK_CIRCUS_CROSSING, north_m=500 * k), toponym=f"Spot {k}", feature_type="poi")
            for k, r in enumerate(reports)]
    clusters = stage1(members_of(reports, geos))
    assert len(clusters) > 1
    for c in clusters:
        pts = [m for m in c.members if m.scope == "point"]
        assert max(haversine_m(a.lat, a.lon, b.lat, b.lon) for a in pts for b in pts) <= CLUSTER_SPAN_M + 1e-6
    assert sum(len(c.members) for c in clusters) == len(reports)
    # and in any order
    rng = random.Random(9)
    order = reports[:]
    rng.shuffle(order)
    assert cluster_sets(stage1(members_of(order, geos))) == cluster_sets(clusters)


def test_a_road_report_never_bridges_two_points_far_apart_on_its_segment():
    # two crash reports 2.5 km apart, both snapped onto segment 1035, and one report geocoded to the road itself:
    # the road report links with each, but joins only one of them
    title = "Multi-vehicle crash on EM Bypass, three injured"
    p1 = make_signal(title=title, published_at=at(0))
    p2 = make_signal(title=title, publisher="news-b.example", published_at=at(5))
    rd = make_signal(title=title, publisher="news-c.example", published_at=at(10))
    geos = [
        ruby_hospital(p1),
        point(p2, offset(RUBY_HOSPITAL, north_m=2500), segment_id=1035, residual_m=150.0),
        road(rd, 1035, offset(RUBY_HOSPITAL, north_m=1250)),
    ]
    clusters = stage1(members_of([p1, p2, rd], geos))
    assert len(clusters) == 2
    assert all(not {p1.signal_id, p2.signal_id} <= {m.signal_id for m in c.members} for c in clusters)
    # close together (1.2 km), the three are one cluster as before
    near = point(p2, offset(RUBY_HOSPITAL, north_m=1200), segment_id=1035, residual_m=150.0)
    assert len(stage1(members_of([p1, p2, rd], [geos[0], near, geos[2]]))) == 1


def test_an_accident_hotspot_never_chains_into_one_day_long_situation():
    # a crash report at one junction every 5 h for 25 h: each neighbour pair is within the 6 h point window, but a
    # point incident's cluster never spans more than 12 h, so later accidents are not swallowed by the first
    reports = [make_signal(title="Multi-vehicle crash at Park Circus crossing, traffic slow",
                           publisher=f"news-{c}.example", published_at=at(k * 300)) for k, c in enumerate("abcdef")]
    geos = [_park_circus(r) for r in reports]
    clusters = stage1(members_of(reports, geos))
    assert len(clusters) > 1 and sum(len(c.members) for c in clusters) == len(reports)
    assert all(c.t1 - c.t0 <= 2 * POINT_WINDOW for c in clusters)
    # an ongoing situation keeps the same reports together (twice its 48 h window)
    floods = [make_signal(title="Waterlogging at Park Circus crossing after heavy rain", publisher=f"news-{c}.example",
                          published_at=at(k * 300)) for k, c in enumerate("abcdef")]
    flood_geos = [_park_circus(r) for r in floods]
    assert len(stage1(members_of(floods, flood_geos))) == 1


def test_long_valid_alerts_reissued_a_day_apart_are_one_situation():
    # the time bound reads REPORT times: two identical 4-day district warnings issued 24 h apart are one situation
    # (validity-based spans once made them two surfaced duplicates; 3-hour validity always merged them)
    from datetime import timedelta

    def warning(minutes: float, valid: timedelta):
        return make_signal("sachet_cap", title="Heavy rain warning for Kolkata district for the next four days",
                           publisher="sachet.ndma.gov.in", admin_codes=["LGD:KOLKATA"], published_at=at(minutes),
                           valid_until=at(minutes) + valid)

    for valid in (timedelta(days=4), timedelta(hours=3), timedelta(days=6)):
        a, b = warning(0, valid), warning(24 * 60, valid)
        clusters = stage1(members_of([a, b], [district(a), district(b)]))
        assert cluster_sets(clusters) == [sorted([a.signal_id, b.signal_id])], valid
        result = run_pipeline([a, b], resolver=FakeResolver([district(a), district(b)]))
        assert result.counts.fused == 1 and result.counts.surfaced == 1
        assert result.resolved[0].source_count == 2 and result.resolved[0].window_end == b.valid_until
    # report times more than twice the 48 h window apart still split, however long the validity
    late = [warning(0, timedelta(days=6)), warning(30 * 60, timedelta(days=6)), warning(60 * 60, timedelta(days=6)),
            warning(100 * 60, timedelta(days=6))]
    clusters = stage1(members_of(late, [district(s) for s in late]))
    assert len(clusters) > 1
    assert all(max(m.t0 for m in c.members) - min(m.t0 for m in c.members) <= 2 * fusion.ONGOING_WINDOW
               for c in clusters)


def test_the_strongest_links_win_when_the_span_forbids_a_chain():
    # A-B-C-D 850 m apart on a line: each neighbour pair links (A-B strongest, C-D weakest), but A-D would be 2.55 km:
    # A-B and B-C are taken (A-C 1.7 km, within the span), C-D is not
    titles = [
        "Wall collapse near the old market gate, two hurt",
        "Wall collapse near the old market gate, two hurt, lane shut",
        "Wall collapse near the market lane, shops shut",
        "Wall collapse reported near shops, traffic slow",
    ]
    sigs = [make_signal(title=t, publisher=f"news-{c}.example", published_at=at(k))
            for k, (t, c) in enumerate(zip(titles, "abcd", strict=True))]
    geos = [point(s, offset(PARK_CIRCUS_CROSSING, north_m=850 * k)) for k, s in enumerate(sigs)]
    ms = members_of(sigs, geos)
    strengths = [jaccard(ms[k].tokens, ms[k + 1].tokens) for k in range(3)]
    assert strengths[0] > strengths[1] > strengths[2] >= LEXICAL_THRESHOLD
    a, b, c, d = (s.signal_id for s in sigs)
    assert cluster_sets(stage1(ms)) == sorted([sorted([a, b, c]), [d]])
    assert cluster_sets(stage1(list(reversed(ms)))) == sorted([sorted([a, b, c]), [d]])


def test_a_state_member_never_joins_a_district_or_point_cluster():
    text = "Thunderstorm with lightning likely over Kolkata during the next 3 hours"
    st = make_signal("sachet_cap", title=text, publisher="sachet.ndma.gov.in", admin_codes=["LGD:WEST_BENGAL"])
    dt = make_signal("sachet_cap", title=text, publisher="sachet.ndma.gov.in", admin_codes=["LGD:KOLKATA"])
    pt = make_signal(title=text)
    clusters = stage1(members_of([st, dt, pt], [state(st), district(dt), ruby_hospital(pt)]))
    state_clusters = [c for c in clusters if c.scope == "state"]
    assert [[m.signal_id for m in c.members] for c in state_clusters] == [[st.signal_id]]
    assert all(st.signal_id not in {m.signal_id for m in c.members} for c in clusters if c.scope != "state")


def test_a_district_area_joins_points_inside_the_district():
    alert = make_signal(
        "sachet_cap",
        title="Thunderstorm and lightning warning for Kolkata district",
        text="Thunderstorm and lightning warning for Kolkata district: lightning and gusty winds likely",
        publisher="sachet.ndma.gov.in",
        admin_codes=["LGD:KOLKATA"],
    )
    report = make_signal(title="Thunderstorm and lightning hit Kolkata: gusty winds near Park Circus")
    assert classify(report).event_class == "weather_hazard"
    clusters = stage1(members_of([alert, report], [district(alert), point(report, PARK_CIRCUS_CROSSING)]))
    assert cluster_sets(clusters) == [sorted([alert.signal_id, report.signal_id])]
    assert clusters[0].scope == "point"  # located by its point member, the area level kept honest


def _rain_alert_and_three_reports(alert_title: str = "Heavy rain and waterlogging alert for Kolkata district"):
    """A district alert and three text-similar waterlogging reports at Shyambazar, Garia and Behala (8-15 km apart,
    each a one-word place, so the three reports are equally similar to the alert)."""
    alert = make_signal("sachet_cap", title=alert_title, publisher="sachet.ndma.gov.in",
                        admin_codes=["LGD:KOLKATA"], published_at=at(0))
    places = [("Shyambazar", SHYAMBAZAR), ("Garia", GARIA), ("Behala", BEHALA_CHOWRASTA)]
    reports = [
        make_signal(title=f"Waterlogging at {name} after heavy rain", publisher=f"news-{c}.example", published_at=at(m))
        for (name, _), c, m in zip(places, "abc", (30, 40, 50), strict=True)
    ]
    geos = [district(alert)] + [
        point(r, lonlat, toponym=name, feature_type="poi") for r, (name, lonlat) in zip(reports, places, strict=True)
    ]
    return alert, reports, geos


def test_a_district_alert_never_merges_point_clusters_and_joins_at_most_one():
    alert, reports, geos = _rain_alert_and_three_reports()
    assert classify(alert).event_class == "urban_flooding"
    assert all(classify(r).event_class == "urban_flooding" for r in reports)
    for a, b in ((SHYAMBAZAR, GARIA), (SHYAMBAZAR, BEHALA_CHOWRASTA), (GARIA, BEHALA_CHOWRASTA)):
        assert haversine_m(a[1], a[0], b[1], b[0]) > 8_000
        assert all(fusion.inside_district(p[1], p[0], members_of([alert], geos[:1])[0]) for p in (a, b))
    members = members_of([alert, *reports], geos)
    assert all(jaccard(members[0].tokens, m.tokens) >= LEXICAL_THRESHOLD for m in members[1:])  # each one links
    clusters = stage1(members)
    # three point clusters, one per place; the alert joined exactly one of them, never two
    assert len(clusters) == 3
    for c in clusters:
        assert sum(1 for m in c.members if m.scope == "point") == 1
    with_alert = [c for c in clusters if alert.signal_id in {m.signal_id for m in c.members}]
    assert len(with_alert) == 1 and with_alert[0].scope == "point"
    # without the alert: the same three point clusters
    alone = stage1(members_of(reports, geos[1:]))
    point_sets = sorted(sorted(m.signal_id for m in c.members if m.scope == "point") for c in clusters)
    assert cluster_sets(alone) == point_sets
    # through the pipeline: three surfaced situations, each located at its own place
    result = run_pipeline([alert, *reports], resolver=FakeResolver(geos))
    assert result.counts.fused == 3 and result.counts.surfaced == 3
    assert sorted(r.toponym for r in result.resolved) == ["Behala", "Garia", "Shyambazar"]


def test_a_district_alert_joins_the_most_similar_point_cluster_ties_to_the_earliest():
    alert, reports, geos = _rain_alert_and_three_reports()
    clusters = stage1(members_of([alert, *reports], geos))
    (joined,) = [c for c in clusters if any(m.scope == "district" for m in c.members)]
    # the three reports are equally similar to the alert: the earliest (Shyambazar, 30 min) takes it
    assert {m.signal_id for m in joined.members} == {alert.signal_id, reports[0].signal_id}
    # a report that shares more words with the alert takes it instead
    alert2, reports2, geos2 = _rain_alert_and_three_reports()
    closer = make_signal(title="Heavy rain and waterlogging alert: Garia crossing closed",
                         publisher="news-d.example", published_at=at(45))
    members = members_of([alert2, *reports2, closer], [*geos2, point(closer, GARIA, toponym="Garia")])
    (joined,) = [c for c in stage1(members) if any(m.scope == "district" for m in c.members)]
    assert alert2.signal_id in {m.signal_id for m in joined.members}
    assert closer.signal_id in {m.signal_id for m in joined.members}


def test_district_alerts_of_one_district_join_one_point_cluster_together_or_none():
    # two similar alerts link in Stage 1 (one district cluster): together they still join at most one point cluster
    alert, reports, geos = _rain_alert_and_three_reports()
    second = make_signal("sachet_cap", title="Heavy rain and waterlogging alert for Kolkata district, update",
                         publisher="sachet.ndma.gov.in", admin_codes=["LGD:KOLKATA"], published_at=at(5))
    clusters = stage1(members_of([alert, second, *reports], [*geos, district(second)]))
    assert len(clusters) == 3
    areas = [sum(1 for m in c.members if m.scope == "district") for c in clusters]
    assert sorted(areas) == [0, 0, 2]
    # an alert whose text links no report stays its own district-level cluster
    other = make_signal("sachet_cap", title="Thunderstorm and squall warning", publisher="sachet.ndma.gov.in",
                        admin_codes=["LGD:KOLKATA"], published_at=at(0))
    assert classify(other).event_class == "weather_hazard"
    storm_report = make_signal(title="Thunderstorm lashes Park Circus, trees uprooted", published_at=at(30))
    clusters = stage1(members_of([other, storm_report], [district(other), point(storm_report, PARK_CIRCUS_CROSSING)]))
    assert sorted(c.scope for c in clusters) == ["district", "point"]


def test_a_district_alert_beyond_the_window_does_not_join():
    alert, reports, geos = _rain_alert_and_three_reports()
    late = make_signal(title="Waterlogging at Park Circus after heavy rain", publisher="news-d.example",
                       published_at=at(3 * 24 * 60))  # 3 days after the alert: beyond the 48 h window
    clusters = stage1(members_of([alert, late], [geos[0], point(late, PARK_CIRCUS_CROSSING, toponym="Park Circus")]))
    assert sorted(c.scope for c in clusters) == ["district", "point"]


def test_the_area_rule_is_order_independent():
    alert, reports, geos = _rain_alert_and_three_reports()
    signals = [alert, *reports]
    base = cluster_sets(stage1(members_of(signals, geos)))
    rng = random.Random(5)
    for _ in range(5):
        order = signals[:]
        rng.shuffle(order)
        assert cluster_sets(stage1(members_of(order, geos))) == base


def test_a_district_area_does_not_join_a_point_outside_the_district():
    alert = make_signal("sachet_cap", title="Thunderstorm and lightning warning for Kolkata district",
                        publisher="sachet.ndma.gov.in", admin_codes=["LGD:KOLKATA"])
    outside = make_signal(title="Thunderstorm and lightning warning for Kolkata district")
    far = point(outside, (87.51, 21.63), toponym="Digha", feature_type="poi")  # Purba Medinipur: well outside
    clusters = stage1(members_of([alert, outside], [district(alert), far]))
    assert len(clusters) == 2


@pytest.mark.parametrize("on_route", [False, True], ids=["park_circus", "segment_1025"])
@pytest.mark.parametrize("case", AREA_SOCIAL_CASES)
def test_an_area_member_never_joins_a_social_only_point_cluster(case, on_route):
    # review 3: an area-level member says nothing about the street, so it never corroborates a social post
    area, posts, resolver = area_social_case(case, on_route=on_route)
    members = members_of([area, *posts], [resolver.by_id[s.signal_id] for s in (area, *posts)])
    (area_m, *post_ms) = members
    assert area_m.scope == "district" and all(m.scope == "point" for m in post_ms)
    assert all(link_strength(area_m, m) is not None for m in post_ms)  # the text would link: only the rule stops it
    assert all(colocated(area_m, m) for m in post_ms)  # and every post is inside the district
    assert social_only(post_ms) and not social_only([area_m])
    clusters = stage1(members)
    assert cluster_sets(clusters) == sorted([[area.signal_id], sorted(p.signal_id for p in posts)])
    by_scope = {c.scope: c for c in clusters}
    assert sorted(by_scope) == ["district", "point"]  # the area stays its own district situation
    assert all(m.scope == "point" for m in by_scope["point"].members)


def test_social_only_reads_the_trust_type_of_every_member():
    post = make_signal("reddit_rss", title="Waterlogging at Park Circus", publisher="social-a.example/r/example_city")
    other = make_signal("reddit_rss", title="Waterlogging at Park Circus", publisher="social-b.example/r/example_town")
    news = make_signal(title="Waterlogging at Park Circus")
    alert = make_signal("sachet_cap", title="Waterlogging alert", publisher="sachet.ndma.gov.in",
                        admin_codes=["LGD:KOLKATA"])
    m = {s.signal_id: x for s, x in zip(
        (post, other, news, alert),
        members_of([post, other, news, alert], [point(post, PARK_CIRCUS_CROSSING), point(other, PARK_CIRCUS_CROSSING),
                                                 point(news, PARK_CIRCUS_CROSSING), district(alert)]),
        strict=True)}
    assert social_only([m[post.signal_id]]) and social_only([m[post.signal_id], m[other.signal_id]])
    assert not social_only([m[post.signal_id], m[news.signal_id]])
    assert not social_only([m[post.signal_id], m[alert.signal_id]])
    assert not social_only([])


@pytest.mark.parametrize("tier", ["news", "official"])
@pytest.mark.parametrize("case", AREA_SOCIAL_CASES)
def test_an_area_member_still_joins_a_point_cluster_with_an_independent_report(case, tier):
    # the positive control: an independent point-level news or official report makes the cluster a candidate
    area, posts, resolver = area_social_case(case)
    report, report_geo = independent_report(case, tier)
    resolver.add(report_geo)
    signals = [area, *posts, report]
    (cluster,) = stage1(members_of(signals, [resolver.by_id[s.signal_id] for s in signals]))
    assert cluster.scope == "point"
    assert {m.signal_id for m in cluster.members} == {s.signal_id for s in signals}


def test_an_area_member_passes_over_a_social_only_cluster_to_the_next_candidate():
    # the alert fits the Park Circus posts best, but they are social only: it takes the Garia news report instead
    area, posts, resolver = area_social_case("sachet_alert_one_post")
    garia = make_signal(title="Heavy rain: waterlogging at Garia, traffic slow, buses diverted, shops shut",
                        publisher="news-d.example", published_at=at(50))
    resolver.add(point(garia, GARIA, toponym="Garia", feature_type="poi"))
    members = members_of([area, *posts, garia], [resolver.by_id[s.signal_id] for s in (area, *posts, garia)])
    assert jaccard(members[0].tokens, members[1].tokens) > jaccard(members[0].tokens, members[2].tokens)
    assert link_strength(members[0], members[2]) is not None  # Garia links too, less strongly
    clusters = stage1(members)
    assert cluster_sets(clusters) == sorted([[p.signal_id for p in posts], sorted([area.signal_id, garia.signal_id])])


def test_state_alerts_aggregate_by_state_across_days_and_never_by_district():
    days = [make_signal("sachet_cap", title=f"Light rain likely over several districts, day {d}",
                        publisher="sachet.ndma.gov.in", admin_codes=["LGD:WEST_BENGAL"], published_at=at(d * 24 * 60))
            for d in range(0, 21, 4)]
    other = make_signal("sachet_cap", title="Light rain likely over several districts", publisher="sachet.ndma.gov.in",
                        admin_codes=["LGD:ODISHA"])
    geos = [state(s) for s in days] + [state(other, toponym="Odisha (state)")]
    clusters = stage1(members_of([*days, other], geos))
    assert cluster_sets(clusters) == sorted([sorted(s.signal_id for s in days), [other.signal_id]])
    assert {c.area_key for c in clusters} == {"west bengal", "odisha"}


def test_chatter_aggregates_by_place_and_time_without_the_text_gate():
    posts = [
        make_signal("reddit_rss", title=t, publisher="social-a.example/r/example_city", published_at=at(m))
        for t, m in (
            ("Weekend plans at Prinsep Ghat", 0), ("Any good tea stall nearby", 90), ("Book shop open late?", 200)
        )
    ]
    assert all(classify(p).event_class == "general_news" for p in posts)
    geos = [road(p, 1025, AJC_BOSE_ROAD, toponym="AJC Bose Road") for p in posts]
    clusters = stage1(members_of(posts, geos))
    assert cluster_sets(clusters) == [sorted(p.signal_id for p in posts)]
    late = make_signal("reddit_rss", title="Late night walk", publisher="social-a.example/r/example_city",
                       published_at=at(200 + 7 * 60))
    late_geo = road(late, 1025, AJC_BOSE_ROAD, toponym="AJC Bose Road")
    clusters = stage1(members_of([*posts, late], [*geos, late_geo]))
    assert len(clusters) == 2


def test_simulated_signals_never_fuse_with_real_ones():
    title = "Multi-vehicle crash on EM Bypass near Ruby General Hospital, three injured"
    real = make_signal(title=title)
    sim = make_signal(title=title, publisher="news-b.example", provenance_label="SIMULATED")
    assert len(stage1(members_of([real, sim], [ruby_hospital(real), ruby_hospital(sim)]))) == 2


def test_determinism_same_input_same_clusters_and_ids_in_any_order():
    em = testing.em_bypass_signals()
    extra = [make_signal(title="Waterlogging at Park Circus crossing after heavy rain", published_at=at(m))
             for m in (0, 30)]
    signals = em + extra
    geos = em_bypass_geocodes(em) + [point(s, PARK_CIRCUS_CROSSING) for s in extra]

    def ids(clusters):
        return [fused_event_id(m.signal for m in c.members) for c in clusters]

    first = stage1(members_of(signals, geos))
    base, base_ids = cluster_sets(first), ids(first)
    assert stage1(members_of(signals, geos)) and ids(stage1(members_of(signals, geos))) == base_ids  # run twice
    rng = random.Random(7)
    for _ in range(5):
        order = signals[:]
        rng.shuffle(order)
        again = stage1(members_of(order, geos))
        assert cluster_sets(again) == base and ids(again) == base_ids


def test_area_keys_name_the_area_not_the_level():
    alert = make_signal("sachet_cap", title="Heavy rain warning", publisher="sachet.ndma.gov.in",
                        admin_codes=["LGD:KOLKATA"])
    gdelt = make_signal("gdelt_doc", title="Heavy rain in the city", publisher="news-b.example",
                        admin_codes=["GDELT_ADM1:IN28"])
    assert area_key_for(district(alert), alert) == "kolkata"
    assert area_key_for(district(alert, toponym="Kolkata, West Bengal, India"), alert) == "kolkata"
    assert area_key_for(district(alert, toponym="Kolkata district"), alert) == "kolkata"
    assert area_key_for(state(gdelt), gdelt) == "west bengal"
    nameless = state(gdelt).model_copy(update={"toponym": None})
    assert area_key_for(nameless, gdelt) == "west bengal"  # from GDELT_ADM1:IN28
    assert area_key_for(district(alert).model_copy(update={"toponym": None}), alert) == "kolkata"  # LGD code
    # the other metro districts and the state code, from the resolver's toponyms or the connectors' codes
    howrah = make_signal("sachet_cap", title="Heavy rain warning", publisher="sachet.ndma.gov.in",
                         admin_codes=["LGD:HOWRAH"])
    assert area_key_for(district(howrah, toponym="Howrah (district)"), howrah) == "howrah"
    for code, key in (("LGD:NORTH_24_PARGANAS", "north 24 parganas"), ("LGD:SOUTH_24_PARGANAS", "south 24 parganas"),
                      ("LGD:WEST_BENGAL", "west bengal")):
        sig = make_signal("sachet_cap", title="Heavy rain warning", publisher="sachet.ndma.gov.in", admin_codes=[code])
        assert area_key_for(state(sig).model_copy(update={"toponym": None}), sig) == key, code


def test_the_kolkata_district_envelope_holds_the_city_and_not_the_salt_lake_sector_or_the_airport():
    alert = make_signal("sachet_cap", title="Heavy rain warning for Kolkata district", publisher="sachet.ndma.gov.in",
                        admin_codes=["LGD:KOLKATA"])
    (area,) = members_of([alert], [district(alert)])
    inside = (RUBY_HOSPITAL, GARIAHAT_CROSSING, PARK_CIRCUS_CROSSING, AJC_BOSE_ROAD, GARIA, BEHALA_CHOWRASTA,
              SHYAMBAZAR, (88.362, 22.577))  # ... and Thanthania
    assert all(fusion.inside_district(lat, lon, area) for lon, lat in inside)
    outside = ((88.4324, 22.5753), (88.4412, 22.6510), (87.51, 21.63))  # Sector V, the airport forecourt, Digha
    assert not any(fusion.inside_district(lat, lon, area) for lon, lat in outside)


def test_content_tokens_drop_stop_words_publisher_names_and_redaction_tokens():
    sig = make_signal(
        title="Driver, [AGE], beaten by mob near the circle - News A",
        publisher="news-a.example",
        category_hint=["publisher:News A", "domain:news-a.example"],
    )
    toks = content_tokens(sig)
    assert {"news", "a", "the", "near", "age", "person"}.isdisjoint(toks)
    assert {"driver", "beaten", "mob", "circl"} <= toks


# --- the vectorised Stage 1 against its pairwise definition ---------------------------------------------------------


def _reference_link(block, window, vectors):
    """Stage-1 linking as it is DEFINED, pair by pair (what fusion._link computes with arrays): every pair within the
    window, co-located and similar is a link; links strongest first (score, distance to the metre, report order),
    each joined unless two pinned point reports would be more than CLUSTER_SPAN_M apart or the report times would
    spread over more than twice the window."""
    n = len(block)
    links = []
    for i in range(n):
        for j in range(i + 1, n):
            a, b = block[i], block[j]
            if interval_gap(a.t0, a.t1, b.t0, b.t1) > window or not colocated(a, b):
                continue
            score = link_strength(a, b, vectors)
            if score is not None:
                links.append((-score, round(haversine_m(a.lat, a.lon, b.lat, b.lon)), i, j))
    links.sort()
    uf = UnionFind(n)
    spots = {k: [(m.lat, m.lon)] if m.scope == "point" and not m.is_line else [] for k, m in enumerate(block)}
    spans = {k: (m.t0, m.t0) for k, m in enumerate(block)}
    for _, _, i, j in links:
        ri, rj = uf.find(i), uf.find(j)
        if ri == rj:
            continue
        if not all(haversine_m(p[0], p[1], q[0], q[1]) <= CLUSTER_SPAN_M for p in spots[ri] for q in spots[rj]):
            continue
        start, end = min(spans[ri][0], spans[rj][0]), max(spans[ri][1], spans[rj][1])
        if end - start > 2 * window:
            continue
        uf.union(ri, rj)
        root = uf.find(ri)
        spots[root], spans[root] = spots[ri] + spots[rj], (start, end)
    return [BaseCluster(tuple(sorted((block[k] for k in g), key=lambda m: m.sort_key))) for g in uf.groups()]


_CRASH_TITLES = [
    "Multi-vehicle crash on EM Bypass near Ruby General Hospital, three injured",
    "Multi-vehicle crash near Ruby General Hospital, traffic slow",
    "Crash on EM Bypass: three injured near the club",
    "Truck overturns on the highway near the club, cleaner hurt",
    "Car rammed vehicles near the circle; two injured",
    "Crash near the circle, traffic slow",
]


def _random_layout(seed, n, radius_m, minutes, titles=_CRASH_TITLES):
    rng = random.Random(seed)
    signals, geos = [], []
    for i in range(n):
        s = make_signal(title=rng.choice(titles), publisher=f"news-{i % 7}.example",
                        published_at=at(rng.uniform(0, minutes)))
        where = offset(PARK_CIRCUS_CROSSING, north_m=rng.uniform(-radius_m, radius_m),
                       east_m=rng.uniform(-radius_m, radius_m))
        kind = rng.random()
        if kind < 0.15:
            geos.append(road(s, 1025, where, toponym="AJC Bose Road"))
        elif kind < 0.25:
            geos.append(point(s, where, segment_id=1025, residual_m=rng.uniform(0, 1200)))
        else:
            geos.append(point(s, where, feature_type=rng.choice(["landmark", "junction", "poi"])))
        signals.append(s)
    return members_of(signals, geos)


def _both_ways(monkeypatch, members, vectors=None):
    fast = cluster_sets(stage1(members, vectors=vectors))
    with monkeypatch.context() as m:
        m.setattr(fusion, "_link", _reference_link)
        reference = cluster_sets(stage1(members, vectors=vectors))
    return fast, reference


@pytest.mark.parametrize("seed", [1, 2, 3])
@pytest.mark.parametrize(
    ("n", "radius_m", "minutes"),
    [
        (120, 250, 120),  # dense, no bound can refuse: the connected-components path
        (150, 1500, 120),  # wider than the span: the ordered path, spatial refusals
        (80, 100, 30 * 60),  # one place over 30 h: the ordered path, temporal refusals (point incident: 12 h)
        (100, 900, 20 * 60),  # both
    ],
)
def test_the_vectorised_linking_equals_its_pairwise_definition(monkeypatch, seed, n, radius_m, minutes):
    members = _random_layout(seed, n, radius_m, minutes)
    fast, reference = _both_ways(monkeypatch, members)
    assert fast == reference
    assert len(fast) < n  # something linked


@pytest.mark.parametrize("seed", [4, 5])
def test_the_vectorised_linking_equals_its_pairwise_definition_with_an_embedder(monkeypatch, seed):
    members = _random_layout(seed, 90, 1200, 600)
    rng = np.random.default_rng(seed)
    centres = rng.normal(size=(4, 8))
    vectors = {}
    for k, m in enumerate(members):
        v = centres[k % 4] + rng.normal(scale=0.35, size=8)
        vectors[m.signal_id] = v / np.linalg.norm(v)
    fast, reference = _both_ways(monkeypatch, members, vectors)
    assert fast == reference and len(fast) < len(members)


def test_the_vectorised_linking_equals_its_pairwise_definition_for_district_alerts(monkeypatch):
    from datetime import timedelta

    rng = random.Random(6)
    titles = ["Heavy rain warning for Kolkata district", "Heavy rain and waterlogging warning for Kolkata district",
              "Waterlogging likely in low-lying areas of Kolkata district"]
    alerts = [make_signal("sachet_cap", title=rng.choice(titles), publisher="sachet.ndma.gov.in",
                          admin_codes=["LGD:KOLKATA"], published_at=at(m),
                          valid_until=at(m) + timedelta(hours=rng.choice([3, 24, 96, 120])))
              for m in sorted(rng.uniform(0, 6 * 24 * 60) for _ in range(14))]
    members = members_of(alerts, [district(a) for a in alerts])
    fast, reference = _both_ways(monkeypatch, members)
    assert fast == reference and 1 < len(fast) < len(alerts)


def test_both_jaccard_paths_agree_exactly():
    rng = random.Random(8)
    words = [f"w{k}" for k in range(30)]
    tokens = [frozenset(rng.sample(words, rng.randint(0, 6))) for _ in range(60)]
    first, second = np.triu_indices(len(tokens), k=1)
    pairwise = fusion._jaccard_pairs(tokens, first, second, dense=False)
    dense = fusion._jaccard_pairs(tokens, first, second, dense=True)
    assert np.array_equal(pairwise, dense)
    assert np.array_equal(pairwise, np.array([jaccard(tokens[i], tokens[j]) for i, j in zip(first, second)]))


def test_connected_components_match_union_find():
    rng = np.random.default_rng(9)
    for n, edges in ((1, 0), (40, 0), (40, 25), (200, 150), (200, 2000)):
        first = rng.integers(0, n, edges)
        second = rng.integers(0, n, edges)
        labels = fusion._components(n, first, second)
        uf = UnionFind(n)
        for i, j in zip(first.tolist(), second.tolist()):
            uf.union(i, j)
        by_label = {}
        for k, label in enumerate(labels.tolist()):
            by_label.setdefault(label, []).append(k)
        assert sorted(by_label.values()) == sorted(uf.groups())


def test_a_dense_block_costs_no_python_work_per_pair(monkeypatch):
    # 1 000 reports of one procession within 300 m: about 500 000 candidate pairs. The pairwise code made a Python
    # haversine and a Jaccard call per pair (12.7 s at 2 000 reports); the array code makes neither per pair.
    calls = {"haversine": 0, "jaccard": 0}
    real_h, real_j = fusion.haversine_m, fusion.jaccard

    def counting_h(*args):
        calls["haversine"] += 1
        return real_h(*args)

    def counting_j(*args):
        calls["jaccard"] += 1
        return real_j(*args)

    monkeypatch.setattr(fusion, "haversine_m", counting_h)
    monkeypatch.setattr(fusion, "jaccard", counting_j)
    rng = random.Random(10)
    titles = [f"Immersion procession reaches Babughat, huge crowds, update {k}" for k in range(9)]
    for radius_m in (300, 1200):  # the components path, then the ordered path
        calls.update(haversine=0, jaccard=0)
        members = _random_layout(11, 1000, radius_m, 600, titles)
        clusters = stage1(members)
        assert sum(len(c.members) for c in clusters) == 1000 and len(clusters) < 50
        assert calls["haversine"] <= 2 * len(members) and calls["jaccard"] <= len(members), (radius_m, calls)
