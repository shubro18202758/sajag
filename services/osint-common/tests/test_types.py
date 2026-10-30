"""The canonical models: extra="forbid" everywhere, the RawOsintSignal rails, area levels (plan R28), situations."""

from __future__ import annotations

import hashlib
import inspect
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import BaseModel, ValidationError

from osint_common import testing, types
from osint_common.types import (
    AttachResult,
    Classification,
    DssSummary,
    Geocode,
    OsintEventRow,
    PipelineResult,
    RawOsintSignal,
    ResolvedEvent,
    SourceRef,
    effective_dss_state,
    signal_id_for,
    signal_rejection_reason,
)


def _models() -> list[type[BaseModel]]:
    return [
        obj
        for name, obj in vars(types).items()
        if inspect.isclass(obj) and issubclass(obj, BaseModel) and obj.__module__ == types.__name__
    ]


def _signal_dict(**over) -> dict:
    d = testing.dadar_robbery_signal().model_dump(mode="json")
    d.update(over)
    return d


# ── every model ──────────────────────────────────────────────────────────────


def test_every_model_forbids_extra_fields():
    models = _models()
    assert len(models) >= 40
    for m in models:
        assert m.model_config.get("extra") == "forbid", m.__name__


def test_x18_names_exist():
    for name in (
        "SourceName", "SourceTier", "ProvenanceLabel", "VerificationState", "EventClass", "RawGeoHint",
        "RawOsintSignal", "Geocode", "Classification", "SourceRef", "AttachResult", "SecondOrderFlag",
        "ResolvedEvent", "LiveEventRef", "LiveStateSnapshot", "PipelineCounts", "PipelineResult", "CoaKind",
        "ActionVerb", "CoaAction", "Criterion", "Coa", "Recommendation", "StrategyPrior", "DecisionSupport",
        "DssDecisionRequest", "DssDecisionResult", "NextStep",
    ):
        assert hasattr(types, name), name
        assert name in types.__all__, name


def test_extra_key_is_refused():
    with pytest.raises(ValidationError):
        RawOsintSignal.model_validate(_signal_dict(extra_field="x"))


# ── RawOsintSignal ───────────────────────────────────────────────────────────


def test_fixture_signal_round_trips():
    sig = testing.dadar_robbery_signal()
    again = RawOsintSignal.model_validate_json(sig.model_dump_json())
    assert again == sig
    assert sig.signal_id == signal_id_for(sig.source, sig.source_id)


@pytest.mark.parametrize(
    "over",
    [
        {"author": "someone"},
        {"raw_geo_hint": {"place_names": [], "admin_codes": [], "points": [], "confidence": 0.0, "persons": []}},
        {"raw": {"post_author": "x"}},
        {"raw": {"guid": "g", "uploader": "x"}},
    ],
)
def test_forbidden_key_at_any_depth_is_refused(over):
    d = _signal_dict(**over)
    with pytest.raises(ValidationError) as exc:
        RawOsintSignal.model_validate(d)
    assert signal_rejection_reason(exc.value) == "forbidden_key"
    assert "forbidden_key:" in str(exc.value)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("title", "Mr Varnel Ostrik held near Gariahat crossing"),
        ("text", "a 41-year-old man was questioned near Kasba"),
        ("text", "the accused Zorvan Quillet fled towards Garia"),
    ],
)
def test_surviving_pii_is_refused(field, value):
    with pytest.raises(ValidationError) as exc:
        RawOsintSignal.model_validate(_signal_dict(**{field: value}))
    assert signal_rejection_reason(exc.value) == "pii_unredacted"
    # the error never repeats the name or the age
    msg = str(exc.value)
    for word in ("Varnel", "Ostrik", "Zorvan", "Quillet", "41-year"):
        assert word not in msg.split("input_value")[0]


def test_pii_in_a_raw_value_is_refused():
    with pytest.raises(ValidationError) as exc:
        RawOsintSignal.model_validate(_signal_dict(raw={"guid": "Mr Varnel Ostrik"}))
    assert signal_rejection_reason(exc.value) == "pii_unredacted"


def test_raw_keys_are_whitelisted_scalars():
    RawOsintSignal.model_validate(_signal_dict(raw={"guid": "g1", "source_domain": "news-b.example"}))
    for raw in ({"title_full": "x"}, {"guid": {"nested": 1}}, {"guid": [1, 2]}):
        with pytest.raises(ValidationError) as exc:
            RawOsintSignal.model_validate(_signal_dict(raw=raw))
        assert signal_rejection_reason(exc.value) == "invalid"


def test_signal_id_is_sha1_of_source_and_source_id():
    with pytest.raises(ValidationError) as exc:
        RawOsintSignal.model_validate(_signal_dict(signal_id="0" * 40))
    assert signal_rejection_reason(exc.value) == "invalid"
    assert signal_id_for("reddit_rss", "t3_x") == hashlib.sha1(b"reddit_rss:t3_x").hexdigest()


def _ref(publisher: str | None) -> dict:
    return {
        "signal_id": "a" * 40, "source": "google_news_rss", "publisher": publisher, "url": None, "title": "t",
        "event_class": "road_accident", "credibility": 0.6, "fetch_mode": "cached-sample", "role": "primary",
    }


@pytest.mark.parametrize(
    ("value", "stored"),
    [
        ("news-a.example", "news-a.example"),
        ("sachet.ndma.gov.in", "sachet.ndma.gov.in"),
        ("social-a.example/r/example_city", "social-a.example/r/example_city"),
        ("reddit.com/r/x", "reddit.com/r/x"),  # a community on the community host
        ("www.reddit.com/r/example_city", "www.reddit.com/r/example_city"),
        ("  News-B.EXAMPLE ", "news-b.example"),  # the host is lower-cased, the domain kept
        ("Social-A.EXAMPLE/r/Example_City", "social-a.example/r/Example_City"),  # the community name kept
        ("xn--fsqu00a.example", "xn--fsqu00a.example"),
        (None, None),
    ],
)
def test_publisher_is_an_outlet_domain_or_a_community(value, stored):
    assert RawOsintSignal.model_validate(_signal_dict(publisher=value)).publisher == stored
    assert SourceRef.model_validate(_ref(value)).publisher == stored


@pytest.mark.parametrize(
    "value",
    [
        "Varnel Ostrik",  # a person, never a publisher
        "@varnel",
        "u/varnel",
        "varnel",  # no domain
        # a poster's profile path is a handle, never a publisher (ethics rule 2)
        "reddit.com/u/x",
        "reddit.com/user/x",
        "x.com/x",
        "instagram.com/x",
        "reddit.com/r/u_x",  # on Reddit, the community u_<name> is that user's profile
        "reddit.com/r/U_x",
        "x.com/r/x",  # /r/ is a community only on a community host (on x.com it is the profile "r")
        "reddit.com/r/x/comments",
        "reddit.com/r/",
        "news-a.example/city",  # any other path
        "news-a.example/",
        "https://news-a.example",
        "news a.example",
        "-news.example",
        "news-a.example/a/b/c/d/e",
        "",
    ],
)
def test_publisher_that_is_not_an_outlet_or_a_community_is_refused(value):
    with pytest.raises(ValidationError) as exc:
        RawOsintSignal.model_validate(_signal_dict(publisher=value))
    assert signal_rejection_reason(exc.value) == "invalid"
    with pytest.raises(ValidationError):
        SourceRef.model_validate(_ref(value))


@pytest.mark.parametrize(
    "hint",
    ["author:x", "Author:x", "username:x", "byline:x", "post_author:x", "reporter:x", "author", "uploader"],
)
def test_category_hint_kind_is_never_a_person_key(hint):
    with pytest.raises(ValidationError) as exc:
        RawOsintSignal.model_validate(_signal_dict(category_hint=["domain:news-b.example", hint]))
    assert signal_rejection_reason(exc.value) == "forbidden_key"


@pytest.mark.parametrize("hint", ["subreddit:u_x", "subreddit:U_varnel", "subreddit:a b", "subreddit:"])
def test_subreddit_hint_names_a_community(hint):
    with pytest.raises(ValidationError) as exc:
        RawOsintSignal.model_validate(_signal_dict(category_hint=[hint]))
    assert signal_rejection_reason(exc.value) == "invalid"


@pytest.mark.parametrize("hint", ["publisher:Mr Varnel Ostrik", "area:a resident Kemlo Daravin"])
def test_category_hint_is_scanned_for_surviving_pii(hint):
    with pytest.raises(ValidationError) as exc:
        RawOsintSignal.model_validate(_signal_dict(category_hint=[hint]))
    assert signal_rejection_reason(exc.value) == "pii_unredacted"


def test_ordinary_category_hints_are_accepted():
    hints = ["CAP", "area:mumbai", "domain:news-b.example", "publisher:News B Daily", "subreddit:example_city"]
    assert RawOsintSignal.model_validate(_signal_dict(category_hint=hints)).category_hint == hints


def test_place_names_are_scanned_for_surviving_pii():
    geo = {"place_names": ["Dadar TT Circle", "Mr Varnel Ostrik"], "admin_codes": [], "points": [],
           "confidence": 0.5}
    with pytest.raises(ValidationError) as exc:
        RawOsintSignal.model_validate(_signal_dict(raw_geo_hint=geo))
    assert signal_rejection_reason(exc.value) == "pii_unredacted"
    geo["place_names"] = ["Dadar TT Circle", "Dr. Ambedkar Road", "Mumbai, Maharashtra, India"]
    assert RawOsintSignal.model_validate(_signal_dict(raw_geo_hint=geo)).raw_geo_hint.place_names[1] == (
        "Dr. Ambedkar Road"
    )


@pytest.mark.parametrize(
    "raw",
    [
        {"source_domain": "reddit.com/user/x"},
        {"domain": "x.com/x"},
        {"page_url_domain": "news-a.example/city"},
        {"source_url_domain": "Varnel Ostrik"},
        {"domain": 7},
    ],
)
def test_raw_domain_keys_hold_a_bare_domain(raw):
    with pytest.raises(ValidationError) as exc:
        RawOsintSignal.model_validate(_signal_dict(raw=raw))
    assert signal_rejection_reason(exc.value) == "invalid"
    ok = {"domain": "news-a.example", "source_domain": "News-B.example", "source_url_domain": None}
    assert RawOsintSignal.model_validate(_signal_dict(raw=ok)).raw == ok


@pytest.mark.parametrize("value", ["u_x", "U_varnel", 7, True, "a b"])
def test_raw_subreddit_is_a_community(value):
    with pytest.raises(ValidationError) as exc:
        RawOsintSignal.model_validate(_signal_dict(raw={"subreddit": value}))
    assert signal_rejection_reason(exc.value) == "invalid"
    assert RawOsintSignal.model_validate(_signal_dict(raw={"subreddit": "example_city"})).raw["subreddit"] == (
        "example_city"
    )


@pytest.mark.parametrize(
    "title",
    [
        # each of these hides the name from a scan of the raw text (the review's "Ra<ZWSP>mesh" shape)
        "the accused Va​rnel Ostrik fled towards Garia",  # a zero-width space inside the name
        "the accused Va­rnel Ostrik fled towards Garia",  # a soft hyphen (common in scraped HTML)
        "the accused Va⁠rnel Ostrik fled towards Garia",  # a word joiner
        "the accused Va﻿rnel Ostrik fled towards Garia",  # a BOM
        "the accused Ｖａｒｎｅｌ Ostrik fled",  # fullwidth letters
        "the acc​used Varnel Ostrik fled towards Garia",  # the cue split instead
        "Mr​ Varnel Ostrik was detained",  # the gap after the cue
        "a forty-year-old, ag​ed 41, was questioned near Kasba",  # an age cue split
    ],
)
def test_a_name_hidden_by_format_or_fullwidth_characters_is_refused(title):
    with pytest.raises(ValidationError) as exc:
        RawOsintSignal.model_validate(_signal_dict(title=title))
    assert signal_rejection_reason(exc.value) == "pii_unredacted"


def test_zero_width_joiners_in_indic_text_are_kept_unchanged():
    text = "Jewellery shop robbed near Dadar TT Circle. क\u094d\u200cष क\u094d\u200dष traffic diverted."
    sig = RawOsintSignal.model_validate(_signal_dict(text=text))
    assert sig.text == text and "‌" in sig.text and "‍" in sig.text


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        ("Tue, 20 Oct 2026 09:42:22 GMT", datetime(2026, 10, 20, 9, 42, 22, tzinfo=UTC)),
        ("2026-10-20T15:12:22+05:30", datetime(2026, 10, 20, 9, 42, 22, tzinfo=UTC)),
        ("2026-10-20T09:42:22Z", datetime(2026, 10, 20, 9, 42, 22, tzinfo=UTC)),
        ("20261020T094222Z", datetime(2026, 10, 20, 9, 42, 22, tzinfo=UTC)),
        ("20261020094222", datetime(2026, 10, 20, 9, 42, 22, tzinfo=UTC)),
        ("2026-10-20T09:42:22", datetime(2026, 10, 20, 9, 42, 22, tzinfo=UTC)),
        ("", None),
        (None, None),
    ],
)
def test_published_at_accepts_the_feed_formats_as_utc(raw_value, expected):
    sig = RawOsintSignal.model_validate(_signal_dict(published_at=raw_value))
    assert sig.published_at == expected
    if expected is not None:
        assert sig.published_at.tzinfo is not None and sig.published_at.utcoffset() == timedelta(0)


@pytest.mark.parametrize("bad", ["nul\x00here", "bell\x07", "spoof \u202etxt.exe", "isolate \u2066x\u2069"])
def test_control_and_bidi_characters_are_refused(bad):
    with pytest.raises(ValidationError):
        RawOsintSignal.model_validate(_signal_dict(title=bad))
    RawOsintSignal.model_validate(_signal_dict(text="line one\nline two\ttabbed"))


def test_numbers_are_bounded_and_finite():
    for over in ({"credibility_prior": 1.2}, {"credibility_prior": float("nan")}, {"pii_redactions": -1}):
        with pytest.raises(ValidationError):
            RawOsintSignal.model_validate(_signal_dict(**over))


def test_rejection_reason_defaults_to_invalid():
    with pytest.raises(ValidationError) as exc:
        RawOsintSignal.model_validate(_signal_dict(source="twitter"))
    assert signal_rejection_reason(exc.value) == "invalid"


# ── Geocode area levels (plan R28) ───────────────────────────────────────────


def _geo(**over) -> dict:
    d = {
        "signal_id": testing.sachet_maharashtra_signal().signal_id,
        "toponym": "Maharashtra (state)",
        "feature_type": "admin",
        "lon": None,
        "lat": None,
        "method": "area_fallback",
        "confidence": 0.25,
        "bucket": "low",
        "area_level": True,
        "area_scope": "state",
    }
    d.update(over)
    return d


def test_state_and_district_geocodes():
    Geocode.model_validate(_geo())
    Geocode.model_validate(
        _geo(toponym="Mumbai (district)", area_scope="district", lon=72.8777, lat=19.076, confidence=0.4)
    )


@pytest.mark.parametrize(
    "over",
    [
        {"lon": 72.5714, "lat": 23.0225},  # a state geocode with a point in the city
        {"confidence": 0.3},  # a state geocode above 0.25
        {"area_scope": "district", "confidence": 0.4},  # a district geocode without its point
        {"area_scope": "district", "lon": 88.36, "lat": 22.57, "confidence": 0.41},  # district above 0.4
        {"area_scope": None},  # area_level without a scope
        {"area_level": False},  # a scope without area_level
        {"area_scope": "district", "lon": 88.36, "lat": 22.57, "confidence": 0.4, "segment_id": 1035},
        {"lon": 72.57},  # half a point
    ],
)
def test_area_scope_validators_refuse(over):
    with pytest.raises(ValidationError):
        Geocode.model_validate(_geo(**over))


def test_point_geocode_carries_its_point():
    geo = testing.weh_geocode()
    assert (geo.segment_id, geo.residual_m, geo.area_scope, geo.bucket) == (testing.WEH_SEGMENT, 0.0, None, "medium")
    with pytest.raises(ValidationError):
        Geocode.model_validate({**geo.model_dump(), "lon": None, "lat": None})
    with pytest.raises(ValidationError):
        Geocode.model_validate({**geo.model_dump(), "bucket": "area"})


# ── Classification ───────────────────────────────────────────────────────────


@pytest.mark.parametrize("kind", ["crime_incident", "vehicle_pursuit"])
def test_osint_never_emits_crime_incident_or_a_pursuit(kind):
    with pytest.raises(ValidationError, match="OSINT never emits"):
        Classification(event_class="reported_crime", subtype="daylight_robbery", sajag_event_kind=kind)


def test_general_news_carries_no_kind():
    Classification(event_class="general_news")
    with pytest.raises(ValidationError):
        Classification(event_class="general_news", sajag_event_kind="hazard")


# ── attach, situations ───────────────────────────────────────────────────────


def test_attach_is_novel_or_corroborates():
    AttachResult(novel=True)
    AttachResult(novel=False, corroborates_live_urn="event:4508d86d-566b-438f-8414-b3d67fd7e6e4", distance_m=120.0)
    for bad in ({"novel": True, "corroborates_live_urn": "event:x1"}, {"novel": False}):
        with pytest.raises(ValidationError):
            AttachResult.model_validate(bad)


def _sources(signals, classes) -> list[dict]:
    return [
        SourceRef(
            signal_id=s.signal_id,
            source=s.source,
            publisher=s.publisher,
            url=s.url,
            title=s.title,
            event_class=c,
            credibility=s.credibility_prior,
            fetch_mode=s.fetch_mode,
            role="primary" if i == 0 else "corroborating",
        ).model_dump()
        for i, (s, c) in enumerate(zip(signals, classes, strict=True))
    ]


def _sg_situation(**over) -> dict:
    sigs = testing.weh_signals()
    classes = ["road_accident"] * 4 + ["public_conflict"]
    d = {
        "fused_event_id": "a" * 40,
        "event_class": "road_accident",
        "correlated_classes": ["road_accident", "public_conflict"],
        "subtype": "affray+collision",
        "sajag_event_kind": "road_accident",
        "sajag_incident_kind": "accident",
        "label": "Road accident · Eastern Metropolitan Bypass",
        "summary": sigs[0].title,
        "rep_lon": 72.503,
        "rep_lat": 23.009,
        "toponym": "Eastern Metropolitan Bypass",
        "segment_id": 1035,
        "geocode_confidence": 0.719,
        "window_start": "2026-10-20T13:40:00Z",
        "window_end": "2026-10-20T13:59:00Z",
        "credibility": 0.65,
        "verification_state": "NEWS-REPORTED",
        "source_count": 5,
        "source_tiers": ["aggregator"],
        "independent_publishers": 2,
        "cross_type_corroborated": False,
        "attach": {"novel": True},
        "second_order": [],
        "labels": ["NEWS-REPORTED"],
        "is_event": True,
        "held_reason": None,
        "sources": _sources(sigs, classes),
        "member_signal_ids": [s.signal_id for s in sigs],
    }
    d.update(over)
    return d


def _social(**over) -> dict:
    s = testing.social_ghatkopar_signal()
    d = {
        "fused_event_id": "b" * 40,
        "event_class": "road_closure",
        "correlated_classes": ["road_closure"],
        "subtype": "closure",
        "sajag_event_kind": "work_zone",
        "label": "Road closure · Park Circus seven-point crossing",
        "summary": s.title,
        "rep_lon": 72.5636,
        "rep_lat": 23.0105,
        "junction_id": 4,
        "credibility": 0.25,
        "verification_state": "UNVERIFIED-OSINT",
        "source_count": 1,
        "source_tiers": ["social_unverified"],
        "independent_publishers": 1,
        "cross_type_corroborated": False,
        "attach": {"novel": True},
        "labels": ["UNVERIFIED-OSINT"],
        "is_event": False,
        "held_reason": "single social source (aggregate-only rule)",
        "sources": _sources([s], ["road_closure"]),
        "member_signal_ids": [s.signal_id],
    }
    d.update(over)
    return d


def test_resolved_situations_validate():
    ev = ResolvedEvent.model_validate(_sg_situation())
    assert ev.is_event and ev.source_count == 5
    held = ResolvedEvent.model_validate(_social())
    assert not held.is_event


@pytest.mark.parametrize(
    "over",
    [
        {"is_event": True, "held_reason": None},  # a single social post surfaced
        {"credibility": 0.4},  # a single social post above the 0.30 cap
        {"verification_state": "NEWS-REPORTED"},  # a social-only situation labelled news
        {"held_reason": None},  # held without a reason
    ],
)
def test_single_social_source_is_never_an_event(over):
    with pytest.raises(ValidationError):
        ResolvedEvent.model_validate(_social(**over))


@pytest.mark.parametrize(
    "over",
    [
        {"sajag_event_kind": "crime_incident"},
        {"verification_state": "OFFICIAL-VERIFIED"},  # official grade without an official source
        {"rep_lon": None, "rep_lat": None},  # surfaced but not located in the city
        {"source_count": 4},  # count disagrees with the members
        {"correlated_classes": ["public_conflict", "road_accident"]},  # primary not first
        {"event_class": "general_news", "correlated_classes": ["general_news"], "sajag_event_kind": None},
        {"summary": "Mr Varnel Ostrik detained after the crash"},
        {"held_reason": "not an event class"},  # surfaced and held at once
        {"labels": []},
    ],
)
def test_situation_rails(over):
    with pytest.raises(ValidationError):
        ResolvedEvent.model_validate(_sg_situation(**over))


def test_state_level_situation_is_held_with_no_point():
    s = testing.sachet_maharashtra_signal()
    held = ResolvedEvent.model_validate(
        _sg_situation(
            event_class="weather_hazard",
            correlated_classes=["weather_hazard"],
            subtype="storm",
            sajag_event_kind="hazard",
            sajag_incident_kind="weather",
            label="Weather hazard · West Bengal (state)",
            summary=s.title,
            rep_lon=None,
            rep_lat=None,
            toponym="West Bengal (state)",
            segment_id=None,
            geocode_confidence=0.25,
            area_level=True,
            credibility=0.95,
            verification_state="OFFICIAL-VERIFIED",
            source_count=1,
            source_tiers=["official"],
            independent_publishers=1,
            labels=["OFFICIAL-VERIFIED"],
            is_event=False,
            held_reason="state-level area: not located in the city",
            sources=_sources([s], ["weather_hazard"]),
            member_signal_ids=[s.signal_id],
        )
    )
    assert held.area_level and held.rep_lon is None
    with pytest.raises(ValidationError):
        ResolvedEvent.model_validate({**held.model_dump(), "is_event": True, "held_reason": None})


def test_osint_event_row_and_dss_summary():
    row = _sg_situation()
    for k in ("is_event", "held_reason", "sources", "member_signal_ids"):
        row.pop(k)
    oid = "4f7a9c1e-0b5d-4c33-9e21-7d8a6b5c4e3f"
    gen = datetime(2026, 10, 20, 15, 5, tzinfo=UTC)
    dss = DssSummary(
        dss_id="0d6c2a7e-5b1f-4e8a-9c3d-2f4e6a8b0c1d",
        state="proposed",
        top_coa_id="coa_std",
        top_coa_label="Advisory + 108 ambulance + 1 patrol + signal priority",
        generated_at=gen,
        horizon_min=45,
        expires_at=gen + timedelta(minutes=45),
    )
    ok = OsintEventRow.model_validate(
        {**row, "osint_event_id": oid, "urn": f"osint_event:{oid}", "attach": {"novel": True}, "dss": dss.model_dump()}
    )
    assert ok.dss is not None and ok.promoted_event_id is None
    with pytest.raises(ValidationError):
        OsintEventRow.model_validate({**row, "osint_event_id": oid, "urn": "osint_event:" + "0" * 36,
                                      "attach": {"novel": True}})
    with pytest.raises(ValidationError):  # attach carries no distance on the row
        OsintEventRow.model_validate({**row, "osint_event_id": oid, "urn": f"osint_event:{oid}",
                                      "attach": {"novel": True, "distance_m": 3.0}})
    with pytest.raises(ValidationError):
        DssSummary.model_validate({**dss.model_dump(), "expires_at": gen + timedelta(minutes=50)})


_ROW_ID = "4f7a9c1e-0b5d-4c33-9e21-7d8a6b5c4e3f"


def _row(situation: dict, **over) -> dict:
    """A situation dict (pipeline shape) as a C-T OsintEventRow."""
    row = {k: v for k, v in situation.items() if k not in ("is_event", "held_reason", "sources", "member_signal_ids")}
    row.update(osint_event_id=_ROW_ID, urn=f"osint_event:{_ROW_ID}", attach={"novel": True})
    row.update(over)
    return row


def test_a_row_is_a_surfaced_situation():
    OsintEventRow.model_validate(_row(_sg_situation()))
    # two independent social reports may surface (still UNVERIFIED-OSINT)
    OsintEventRow.model_validate(_row(_social(), source_count=2, independent_publishers=2))


@pytest.mark.parametrize(
    ("situation", "over", "match"),
    [
        # a single social source never surfaces: not even as a row, and never above the 0.30 cap
        ("social", {"credibility": 0.9}, "capped at credibility 0.30"),
        ("social", {}, "single social source is never surfaced"),
        # not an event class
        ("sg", {"event_class": "general_news", "correlated_classes": ["general_news"], "sajag_event_kind": None},
         "not an event class"),
        # a state-level area has no point in the city
        ("sg", {"rep_lon": None, "rep_lat": None, "area_level": True, "segment_id": None}, "located in the city"),
        # a surfaced row carries its kind
        ("sg", {"sajag_event_kind": None}, "carries its sajag_event_kind"),
    ],
)
def test_a_row_obeys_every_surfacing_rule(situation, over, match):
    base = _social() if situation == "social" else _sg_situation()
    with pytest.raises(ValidationError, match=match):
        OsintEventRow.model_validate(_row(base, **over))


def test_the_single_social_cap_holds_for_every_situation_shape():
    with pytest.raises(ValidationError, match="capped at credibility 0.30"):
        ResolvedEvent.model_validate(_social(credibility=0.31))
    ResolvedEvent.model_validate(_social(credibility=0.30))


def test_lazy_expiry_rule():
    exp = datetime(2026, 10, 20, 15, 50, tzinfo=UTC)
    assert effective_dss_state("proposed", exp, exp - timedelta(seconds=1)) == "proposed"
    assert effective_dss_state("proposed", exp, exp) == "expired"
    assert effective_dss_state("approved", exp, exp + timedelta(hours=1)) == "approved"


def test_live_state_and_pipeline_result():
    live = testing.live_state_dadar_pursuit()
    assert live.live_events[0].event_kind == "vehicle_pursuit" and live.live_events[0].status == "active"
    geo = testing.weh_geocode()
    PipelineResult(geocodes={geo.signal_id: geo, "f" * 40: None})
    with pytest.raises(ValidationError):
        PipelineResult(geocodes={"e" * 40: geo})


_MUMBAI = (
    testing.weh_signals, testing.dadar_robbery_signal, testing.social_ghatkopar_signal,
    testing.sachet_mumbai_signal, testing.sachet_maharashtra_signal,
)
_KOLKATA = (
    testing.em_bypass_signals, testing.gariahat_robbery_signal, testing.social_single_signal,
    testing.sachet_district_signal, testing.sachet_state_signal,
)


@pytest.mark.parametrize("pack", [_MUMBAI, _KOLKATA], ids=["mumbai", "kolkata"])
def test_fixtures_are_deterministic_and_synthetic(pack):
    news, crime, social_fn, district, state = pack
    a, b = news(), news()
    assert a == b and a is not b
    assert len(a) == 5
    pubs = {s.publisher for s in a} | {crime().publisher}
    assert pubs == {testing.NEWS_A, testing.NEWS_B}
    for s in (district(), state()):
        assert s.publisher == testing.SACHET and s.provenance_label == "OFFICIAL-VERIFIED"
    social = social_fn()
    assert social.source_tier == "social_unverified" and social.credibility_prior <= 0.30
    # ethics rule 9 / plan R13: every replica's publisher is fictional (*.example); only the public-domain official
    # alerts name a real publisher (SACHET). No fabricated text is attributed to a real outlet or community.
    every = [*a, crime(), social, district(), state()]
    assert {s.source for s in every} == {"google_news_rss", "reddit_rss", "sachet_cap"}
    for s in every:
        assert s.publisher is not None
        assert s.publisher.endswith(".example") or s.publisher == testing.SACHET, s.publisher
        assert (s.publisher == testing.SACHET) == (s.source == "sachet_cap")
    assert social.publisher == testing.SOCIAL_A
    assert social.raw == {"subreddit": "example_city"} and social.category_hint == ["subreddit:example_city"]
    # every replica URL is on a fictional host (and there are URLs to check: the news and social replicas)
    urls = [s.url for s in every if s.url is not None]
    assert len(urls) == 7
    for url in urls:
        host = url.split("/")[2]
        assert url.startswith("https://") and host.endswith(".example"), url
    for s in (district(), state()):
        assert s.url is None


def test_the_area_codes_of_the_official_replicas():
    assert testing.sachet_mumbai_signal().raw_geo_hint.admin_codes == ["LGD:MUMBAI"]
    assert testing.sachet_maharashtra_signal().raw_geo_hint.admin_codes == ["LGD:MAHARASHTRA"]
    assert testing.sachet_district_signal().raw_geo_hint.admin_codes == ["LGD:KOLKATA"]
    assert testing.sachet_state_signal().raw_geo_hint.admin_codes == ["LGD:WEST_BENGAL"]


def test_the_dss_replica_is_synthetic_and_mumbai():
    dss = testing.weh_dss()
    assert set(dss.provenance.publishers) == {testing.NEWS_A, testing.NEWS_B}
    for ref in dss.provenance.sources:
        assert ref.publisher in (testing.NEWS_A, testing.NEWS_B)
        assert ref.url is not None and ref.url.split("/")[2].endswith(".example")
    assert dss.situation.toponym == "Western Express Highway" and dss.situation.segment_id == testing.WEH_SEGMENT
