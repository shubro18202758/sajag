"""The shared vocabulary: the C3 lockstep kinds, the classes, the related pairs and the per-source priors."""

from __future__ import annotations

from typing import get_args

import pytest

from osint_common import kinds, types


def test_gdelt_adm1_codes_are_fips():
    """GDELT ADM1 codes are FIPS 10-4: Maharashtra is IN16 (its census code 27 is not GDELT's); the Kolkata pack's
    West Bengal is IN28."""
    assert kinds.GDELT_ADM1_MAHARASHTRA == "IN16"
    assert kinds.GDELT_ADM1_WEST_BENGAL == "IN28"


def test_area_codes_are_the_city_districts_and_the_states():
    """The admin codes connectors write: Mumbai's two districts first (with the spellings that identify each one in
    English, Marathi and Hindi alert text), then the Kolkata pack's four metro-area districts, and the state codes;
    each code fits RawGeoHint's admin-code pattern."""
    assert list(kinds.AREA_DISTRICTS) == [
        "LGD:MUMBAI", "LGD:MUMBAI_SUBURBAN",
        "LGD:KOLKATA", "LGD:HOWRAH", "LGD:NORTH_24_PARGANAS", "LGD:SOUTH_24_PARGANAS",
    ]
    assert kinds.CITY_DISTRICTS == ("LGD:MUMBAI", "LGD:MUMBAI_SUBURBAN")
    assert {"mumbai", "bombay", "मुंबई", "मुम्बई"} <= set(kinds.AREA_DISTRICTS["LGD:MUMBAI"])
    assert {"mumbai suburban", "मुंबई उपनगर"} <= set(kinds.AREA_DISTRICTS["LGD:MUMBAI_SUBURBAN"])
    assert kinds.AREA_STATE_CODE_MAHARASHTRA == "LGD:MAHARASHTRA"
    assert kinds.AREA_STATE_CODE == "LGD:WEST_BENGAL"  # the Kolkata pack's, until ingress and geo move
    assert "calcutta" in kinds.AREA_DISTRICTS["LGD:KOLKATA"]
    for code in (
        *kinds.AREA_DISTRICTS, kinds.AREA_STATE_CODE, kinds.AREA_STATE_CODE_MAHARASHTRA,
        f"GDELT_ADM1:{kinds.GDELT_ADM1_WEST_BENGAL}", f"GDELT_ADM1:{kinds.GDELT_ADM1_MAHARASHTRA}",
    ):
        types.RawGeoHint(admin_codes=[code])


@pytest.mark.parametrize(
    ("literal", "values"),
    [
        (types.EventKind, kinds.ALL_EVENT_KINDS),
        (types.OsintEventKind, kinds.OSINT_EVENT_KINDS),
        (types.IncidentKind, kinds.INCIDENT_KINDS),
        (types.VerificationState, kinds.VERIFICATION_STATES),
        (types.SourceKind, kinds.SOURCE_KINDS),
        (types.SourceName, kinds.SOURCE_NAMES),
        (types.SourceTier, kinds.SOURCE_TIERS),
        (types.ProvenanceLabel, kinds.PROVENANCE_LABELS),
        (types.EventClass, kinds.EVENT_CLASS_NAMES),
    ],
)
def test_literals_equal_the_tuples(literal, values):
    assert get_args(literal) == tuple(values)


def test_sixteen_event_kinds_with_the_six_new_last():
    assert len(kinds.ALL_EVENT_KINDS) == 16 and len(set(kinds.ALL_EVENT_KINDS)) == 16
    assert kinds.NEW_EVENT_KINDS == (
        "reported_crime", "public_disorder", "road_accident", "hazard", "flooding", "infra_failure",
    )
    assert kinds.ALL_EVENT_KINDS[:10] == kinds.LEGACY_EVENT_KINDS
    assert kinds.ALL_EVENT_KINDS[10:] == kinds.NEW_EVENT_KINDS


def test_osint_never_carries_crime_incident_or_a_pursuit():
    assert "crime_incident" not in kinds.OSINT_EVENT_KINDS
    assert "vehicle_pursuit" not in kinds.OSINT_EVENT_KINDS
    assert len(kinds.OSINT_EVENT_KINDS) == 14
    assert set(kinds.NEW_EVENT_KINDS) <= set(kinds.OSINT_EVENT_KINDS)


def test_incident_kinds_relaxed_by_021():
    assert {"road_rage", "robbery", "public_disorder"} <= set(kinds.INCIDENT_KINDS)
    assert len(kinds.INCIDENT_KINDS) == 15


def test_verification_and_source_kinds():
    assert kinds.VERIFICATION_STATES == (
        "EMULATED", "SIMULATED", "UNVERIFIED-OSINT", "NEWS-REPORTED", "OFFICIAL-VERIFIED", "CONFIRMED",
    )
    assert kinds.SOURCE_KINDS == ("operator", "brain", "emulator", "osint")
    assert set(kinds.PROVENANCE_LABELS) <= set(kinds.VERIFICATION_STATES)


def test_classes_partition():
    assert kinds.EVENT_CLASSES == kinds.INCIDENT_CLASSES | kinds.OPERATIONAL_CLASSES
    assert not kinds.INCIDENT_CLASSES & kinds.OPERATIONAL_CLASSES
    assert "general_news" not in kinds.EVENT_CLASSES
    assert kinds.EVENT_CLASSES | {"general_news"} == set(kinds.EVENT_CLASS_NAMES)
    assert set(kinds.RESPONSE_PRIORITY) == set(kinds.EVENT_CLASS_NAMES)
    assert kinds.RESPONSE_PRIORITY["general_news"] == 0


def test_related_classes_are_pairs_of_event_classes():
    assert len(kinds.RELATED_CLASSES) == 12
    for pair in kinds.RELATED_CLASSES:
        assert isinstance(pair, frozenset) and len(pair) == 2
        assert pair <= kinds.EVENT_CLASSES
    assert frozenset({"road_accident", "public_conflict"}) in kinds.RELATED_CLASSES


def test_source_priors_follow_osint_sources_section_6():
    priors = kinds.SOURCE_PRIORS
    assert set(priors) == set(kinds.SOURCE_NAMES)
    for name, p in priors.items():
        assert (p.tier == "official") == (p.provenance_label == "OFFICIAL-VERIFIED"), name
        assert 0 <= p.credibility_prior <= 1
    assert (priors["sachet_cap"].credibility_prior, priors["sachet_cap"].license) == (0.95, "public_domain")
    assert priors["sachet_cap"].redistributable is True
    assert priors["google_news_rss"].redistributable is False  # pointer layer (personal-use terms)
    assert priors["google_news_rss"].credibility_prior == 0.60
    reddit = priors["reddit_rss"]
    assert (reddit.tier, reddit.provenance_label, reddit.credibility_prior) == (
        "social_unverified", "UNVERIFIED-OSINT", 0.25,
    )
    assert reddit.redistributable is False
    assert priors["common_crawl"].credibility_prior == 0.50
    assert priors["kmc_scrape"].credibility_prior == 0.90
    # the outlets' own feeds are a pointer layer like Google News: news-reported, never redistributed
    news = priors["news_rss"]
    assert (news.tier, news.provenance_label, news.credibility_prior, news.redistributable) == (
        "news_regional", "NEWS-REPORTED", 0.60, False,
    )
    assert priors["imd"].tier == "official" and priors["wbsdma"].tier == "official"


def test_priors_are_immutable():
    with pytest.raises(TypeError):
        kinds.SOURCE_PRIORS["reddit_rss"] = kinds.SOURCE_PRIORS["sachet_cap"]  # type: ignore[index]
    with pytest.raises(Exception):  # noqa: B017 - pydantic frozen model
        kinds.SOURCE_PRIORS["reddit_rss"].credibility_prior = 0.95  # type: ignore[misc]
    with pytest.raises(TypeError):
        kinds.SOURCE_PRIORS["reddit_rss"]["tier"] = "official"  # type: ignore[index]


def test_priors_read_as_attributes_or_as_a_mapping():
    """X18 writes the prior as ``{tier, provenance_label, ...}``: both access styles work."""
    p = kinds.SOURCE_PRIORS["reddit_rss"]
    assert p["tier"] == p.tier == "social_unverified"
    assert p["credibility_prior"] == 0.25 and p["redistributable"] is False
    assert p.keys() == ("tier", "provenance_label", "credibility_prior", "license", "redistributable")
    expected = {
        "tier": "official", "provenance_label": "OFFICIAL-VERIFIED", "credibility_prior": 0.95,
        "license": "public_domain", "redistributable": True,
    }
    assert dict(kinds.SOURCE_PRIORS["sachet_cap"]) == {**kinds.SOURCE_PRIORS["sachet_cap"]} == expected
    with pytest.raises(KeyError):
        p["author"]


def test_decision_verbs():
    verbs = set(get_args(types.ActionVerb))
    assert kinds.ACTUATING_VERBS <= verbs and kinds.ANCHOR_VERBS <= kinds.ACTUATING_VERBS
    assert {"monitor", "advisory", "request_cctv"}.isdisjoint(kinds.ACTUATING_VERBS)
    assert kinds.ANCHOR_VERBS == {"dispatch", "closure", "diversion", "signal_hold"}
