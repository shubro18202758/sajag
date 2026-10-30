"""credibility.score(): independent corroboration only — two publishers in one tier give the capped bump (0.65), a
single social post stays <= 0.30, cross-type is the strong bump, a URL (prefix) never counts as independence, and
SIMULATED / EMULATED inputs pass through, never upgraded."""

from __future__ import annotations

import pytest

from analysis_fixtures import make_signal
from osint_common import testing
from osint_analysis.credibility import (
    CREDIBILITY_CEILING,
    CROSS_POST_JACCARD,
    CROSS_POST_MIN_TOKENS,
    SINGLE_SOCIAL_CAP,
    near_duplicate,
    post_views,
    resolve_publisher,
    score,
    social_sources,
    verification_state,
)

SOCIAL = "social-a.example/r/example_city"
SOCIAL_B = "social-b.example/r/example_town"
SOCIAL_C = "social-c.example/r/example_ward"


def news(publisher="news-a.example", **kw):
    return make_signal("google_news_rss", title=kw.pop("title", "Multi-vehicle crash near Andheri on the WEH"),
                       publisher=publisher, **kw)


def test_the_weh_case_two_publishers_in_one_tier_give_the_capped_bump():
    em = testing.weh_signals()  # news-a.example and news-b.example, both aggregator
    c = score(em)
    assert c.credibility == 0.65  # 0.60 -> 0.65
    assert c.verification_state == "NEWS-REPORTED"
    assert c.independent_publishers == 2
    assert c.source_tiers == ("aggregator",) and c.source_types == ("news",)
    assert c.cross_type_corroborated is False
    assert c.labels == ("NEWS-REPORTED",)


def test_the_publisher_bump_is_capped():
    # five independently written reports (not one syndicated text: see test_syndicated_copies_are_one_source)
    texts = ["Multi-vehicle crash near Andheri station", "Car rams scooter on the WEH, rider hurt",
             "Three hurt as vehicles collide by the club", "Pile-up slows evening traffic towards Jogeshwari",
             "Ambulance reaches injured after collision at Andheri"]
    three = [news(f"news-{c}.example", title=t) for c, t in zip("abc", texts, strict=False)]
    assert score(three).credibility == 0.70
    five = three + [news(f"news-{c}.example", title=t) for c, t in zip("de", texts[3:], strict=True)]
    assert score(five).credibility == 0.70  # +0.05 per extra publisher, capped at +0.10


def test_more_reports_from_one_publisher_add_nothing():
    same = [news("news-a.example"), news("news-a.example"), news("news-a.example")]
    c = score(same)
    assert c.credibility == 0.60 and c.independent_publishers == 1


def test_a_url_or_url_prefix_never_counts_as_independence():
    # one outlet, different URL paths and prefixes: still one publisher
    a = news("news-a.example", url="https://news-a.example/city/one")
    b = news("news-a.example", url="https://news-a.example/amp/city/two")
    c = news("news-a.example", url="https://m.news-a.example/three")
    assert score([a, b, c]).credibility == 0.60
    # no resolved publisher at all: different URLs prove nothing
    d = news(None, url="https://news-a.example/x")
    e = news(None, url="https://news-b.example/y")
    s = score([d, e])
    assert s.independent_publishers == 0 and s.credibility == 0.60


def test_publisher_domains_resolve_to_one_outlet():
    assert resolve_publisher("m.news-a.example") == resolve_publisher("news-a.example") == "news-a.example"
    assert resolve_publisher("www.news-a.example") == "news-a.example"
    assert resolve_publisher("city.news-a.example") == "news-a.example"
    assert resolve_publisher("edition.news-c.example") == "news-c.example"
    assert resolve_publisher("city.news-c.co.in") == "news-c.co.in"  # a two-level public suffix
    assert resolve_publisher("sachet.ndma.gov.in") == "ndma.gov.in"
    assert resolve_publisher("Social-A.example/r/Example_City") == "social-a.example/r/example_city"
    assert resolve_publisher(None) is None and resolve_publisher("  ") is None
    # sub-domains of one outlet are one publisher in the score
    assert score([news("m.news-a.example"), news("news-a.example")]).credibility == 0.60


def test_a_single_social_post_is_capped_at_0_30():
    post = make_signal("reddit_rss", title="Road closed near Hindmata", publisher=SOCIAL)
    assert score([post]).credibility <= SINGLE_SOCIAL_CAP
    assert score([post]).verification_state == "UNVERIFIED-OSINT"
    loud = make_signal("reddit_rss", title="Road closed near Hindmata", publisher=SOCIAL, credibility_prior=0.9)
    assert score([loud]).credibility == SINGLE_SOCIAL_CAP  # whatever its prior says


def test_social_posts_from_one_community_stay_capped():
    posts = [make_signal("reddit_rss", title="Road closed near Hindmata", publisher=SOCIAL) for _ in range(4)]
    c = score(posts)
    assert c.credibility <= SINGLE_SOCIAL_CAP and c.verification_state == "UNVERIFIED-OSINT"
    # a second community counts only with a text of its own: the SAME text there is a cross-post, one source
    # (orchestrator decision, OS-4 round 4; this test once counted it as a second source, 0.30)
    cross = make_signal("reddit_rss", title="Road closed near Hindmata", publisher="social-b.example/r/example_town")
    assert score([*posts, cross]).credibility == 0.25 and score([*posts, cross]).independent_publishers == 1
    other = make_signal("reddit_rss", title="Barricades at the Hindmata junction, buses turned back to Dadar TT",
                        publisher="social-b.example/r/example_town")
    assert score([*posts, other]).credibility == 0.30  # 0.25 + 0.05 for a second, independent community


def post(title, publisher=SOCIAL, **kw):
    return make_signal("reddit_rss", title=title, publisher=publisher, **kw)


CRASH = "Car crash at Hindmata junction, two injured"


@pytest.mark.parametrize(
    ("first", "second"),
    [
        (post(CRASH), post(CRASH, SOCIAL_B)),  # the review's case: the same text in two communities
        (post(CRASH), post(f"[x-post from r/example_city] {CRASH}", SOCIAL_B)),  # a marked cross-post
        (post(CRASH), post("Car crash at Hindmata junction, 2 injured!", SOCIAL_B)),  # number word, punctuation
        (post(CRASH), post(f"{CRASH}, avoid the area", SOCIAL_B)),  # a line added
        # the original carries its body, the cross-post its title only (a Reddit cross-post's usual shape)
        (post(CRASH, text=f"{CRASH}. Two cars and an auto, police on the spot"), post(CRASH, SOCIAL_B)),
        (post("Waterlogging at Hindmata junction after heavy rain, update 0"),
         post("Waterlogging at Hindmata junction after heavy rain, update 1", SOCIAL_B)),  # a one-word edit
    ],
    ids=["identical", "x-post", "edited", "line-added", "title-only", "one-word"],
)
def test_cross_posts_in_two_communities_are_one_social_source(first, second):
    # orchestrator decision (OS-4 round 4): the same or a near-identical text in two communities may be one poster
    assert near_duplicate(first, second) and near_duplicate(second, first)
    assert social_sources([first, second]) == [resolve_publisher(SOCIAL)]
    c = score([first, second])
    assert c.independent_publishers == 1
    assert c.credibility <= SINGLE_SOCIAL_CAP and c.credibility == 0.25
    assert c.verification_state == "UNVERIFIED-OSINT"


def test_genuinely_different_posts_in_two_communities_stay_two_sources():
    # the positive control: independent texts about one situation (they share the place, not the wording)
    a = post(CRASH)
    b = post("Accident near Hindmata junction, an auto overturned, traffic backed up to Dadar TT", SOCIAL_B)
    assert not near_duplicate(a, b)
    assert social_sources([a, b]) == sorted([resolve_publisher(SOCIAL), resolve_publisher(SOCIAL_B)])
    c = score([a, b])
    assert c.independent_publishers == 2 and c.credibility == 0.30  # 0.25 + 0.05, as before the decision


def test_a_cross_post_chain_is_one_source_and_independent_communities_still_count():
    # community A's post is cross-posted to B; B also has its own post; C writes independently: two sources
    a = post(CRASH)
    b_cross = post(CRASH, SOCIAL_B)
    b_own = post("Ambulance stuck at Hindmata, the junction is jammed", SOCIAL_B)
    c_own = post("Accident near Hindmata junction, an auto overturned, traffic backed up to Dadar TT", SOCIAL_C)
    assert social_sources([a, b_cross, b_own, c_own]) == sorted([resolve_publisher(SOCIAL),
                                                                 resolve_publisher(SOCIAL_C)])
    assert score([a, b_cross, b_own, c_own]).independent_publishers == 2


def test_a_cross_post_adds_no_social_bump_beside_news():
    report = news("news-a.example", title="Car crash at Hindmata junction injures two")
    cross = score([report, post(CRASH), post(CRASH, SOCIAL_B)])
    assert cross.credibility == 0.75 and cross.independent_publishers == 2  # 0.60 + 0.15 cross-type, one social
    other = post("Accident near Hindmata junction, an auto overturned, traffic backed up to Dadar TT", SOCIAL_B)
    two = score([report, post(CRASH), other])
    assert two.credibility == 0.80 and two.independent_publishers == 3  # + 0.05 for a second social source


def test_the_cross_post_thresholds():
    # Jaccard over the content tokens (titles, then whole texts) at CROSS_POST_JACCARD; or full containment of the
    # shorter view when it has at least CROSS_POST_MIN_TOKENS tokens
    assert (CROSS_POST_JACCARD, CROSS_POST_MIN_TOKENS) == (0.75, 3)
    base = post("crash kurla 1 2 3 4 5")
    assert post_views(base)[0] == frozenset({"crash", "kurla", "1", "2", "3", "4", "5"})
    assert near_duplicate(base, post("crash kurla 1 2 3 4 6", SOCIAL_B))  # 6 / 8 = 0.75
    assert not near_duplicate(base, post("crash kurla 1 2 3 7 8", SOCIAL_B))  # 5 / 9
    assert near_duplicate(post("crash kurla 9"), post("crash kurla 9 and several more words here", SOCIAL_B))
    assert not near_duplicate(post("crash 9"), post("crash 9 and several more words here", SOCIAL_B))  # 2 < 3
    # the community names and the cross-post marker are not content: a mention of r/<community> changes nothing
    assert post_views(post("r/example_town crosspost: crash kurla 9", SOCIAL)) == post_views(post("crash kurla 9"))
    # F-HONEST OSINT-4: the rule holds for news too: two outlets carrying one wire text are ONE source
    wire = score([news("news-a.example", title=CRASH), news("news-b.example", title=CRASH)])
    assert wire.credibility == 0.60 and wire.independent_publishers == 1


def test_cross_type_corroboration_is_the_strong_bump():
    official = make_signal("sachet_cap", title="Heavy rain warning for Mumbai district",
                           publisher="sachet.ndma.gov.in")
    report = news("news-a.example", title="Waterlogging at Hindmata after heavy rain")
    c = score([official, report])
    assert c.cross_type_corroborated and c.source_types == ("official", "news")
    assert c.verification_state == "OFFICIAL-VERIFIED"
    assert c.credibility == CREDIBILITY_CEILING  # 0.95 + 0.15, never above 0.99
    post = make_signal("reddit_rss", title="Waterlogging at Hindmata", publisher=SOCIAL)
    n = score([report, post])
    assert n.cross_type_corroborated and n.credibility == 0.75  # 0.60 + 0.15
    assert n.verification_state == "NEWS-REPORTED"


def test_news_tiers_are_one_type():
    agg = news("news-a.example")  # aggregator
    doc = make_signal("gdelt_doc", title="Three hurt as cars collide on the WEH by the club",
                      publisher="news-b.example")
    c = score([agg, doc])
    assert c.source_tiers == ("aggregator", "news_regional") and c.source_types == ("news",)
    assert not c.cross_type_corroborated
    assert c.credibility == 0.65  # two independent news publishers, not a cross-type bump


def test_verification_state_levels():
    assert verification_state([testing.sachet_mumbai_signal()]) == "OFFICIAL-VERIFIED"
    assert verification_state([testing.dadar_robbery_signal()]) == "NEWS-REPORTED"
    assert verification_state([testing.social_ghatkopar_signal()]) == "UNVERIFIED-OSINT"
    # a member counts at the lower of its tier and its label: an "official" tier labelled news is news
    odd = make_signal("sachet_cap", title="Heavy rain warning", publisher="sachet.ndma.gov.in",
                      provenance_label="NEWS-REPORTED")
    assert verification_state([odd]) == "NEWS-REPORTED"
    mislabelled = make_signal("reddit_rss", title="Road closed", publisher=SOCIAL, provenance_label="OFFICIAL-VERIFIED")
    assert verification_state([mislabelled]) == "UNVERIFIED-OSINT"


@pytest.mark.parametrize("label", ["SIMULATED", "EMULATED"])
def test_simulated_and_emulated_pass_through_never_upgraded(label):
    official = make_signal("sachet_cap", title="Heavy rain warning", publisher="sachet.ndma.gov.in",
                           provenance_label=label)
    a = news("news-a.example", provenance_label=label)
    b = news("news-b.example", provenance_label=label)
    c = score([official, a, b])
    assert c.verification_state == label  # never OFFICIAL-VERIFIED
    assert c.credibility == 0.95  # the base prior: no corroboration bump
    assert c.cross_type_corroborated is False
    assert c.labels == (label,)


@pytest.mark.parametrize("label", ["SIMULATED", "EMULATED"])
def test_the_single_social_cap_holds_in_every_realm(label):
    post = make_signal("reddit_rss", title="Road closed near Hindmata", publisher=SOCIAL, provenance_label=label,
                       credibility_prior=0.9)
    c = score([post])
    assert c.verification_state == label and c.credibility == SINGLE_SOCIAL_CAP


def test_score_needs_a_member():
    with pytest.raises(ValueError):
        score([])


# ── F-HONEST OSINT-4: syndicated copies are one source in every news tier ─────────────────────────────────────

WIRE = "Three injured as car rams vehicles on the WEH near Andheri station, police said (PTI)"


@pytest.mark.parametrize("n", [2, 4])
def test_syndicated_copies_are_one_source(n):
    # the audit probe: the same PTI text from N outlets gave independent=N and credibility 0.65 / 0.70
    c = score([news(f"outlet-{i}.example", title=WIRE, text=WIRE) for i in range(n)])
    assert c.independent_publishers == 1 and c.credibility == 0.60


def test_syndication_collapses_across_news_tiers():
    gdelt = make_signal("gdelt_doc", title=WIRE, text=WIRE, publisher="outlet-b.example")
    c = score([news("outlet-a.example", title=WIRE, text=WIRE), gdelt])
    assert c.source_tiers == ("aggregator", "news_regional") and c.independent_publishers == 1
    assert c.credibility == 0.60


def test_a_rewritten_independent_report_still_counts():
    other = "Pile-up near Andheri station: scooter rider among three hurt, traffic crawls towards Jogeshwari"
    c = score([news("outlet-a.example", title=WIRE, text=WIRE), news("outlet-b.example", title=other, text=other)])
    assert c.independent_publishers == 2 and c.credibility == 0.65


def test_a_syndicated_group_plus_an_independent_report_is_two_sources():
    other = "Pile-up near Andheri station: scooter rider among three hurt, traffic crawls towards Jogeshwari"
    sigs = [news(f"outlet-{i}.example", title=WIRE, text=WIRE) for i in range(3)]
    sigs.append(news("outlet-z.example", title=other, text=other))
    c = score(sigs)
    assert c.independent_publishers == 2 and c.credibility == 0.65
