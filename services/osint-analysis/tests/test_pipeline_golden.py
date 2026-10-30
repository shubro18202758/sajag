"""The Mumbai pipeline golden: the Mumbai synthetic fixtures plus Hindi reports, through the REAL resolver
(``osint_geo.resolver.GazetteerResolver`` on the committed Mumbai gazetteer, ``scripts/data/osint_gazetteer.json``,
and the Mumbai road network), classified, fused, correlated, scored, attached and counted. Every expectation was
checked by hand against the network (segment and junction names in ``scripts/data/osm_network.json``).

Every signal is synthetic: fictional publishers (``news-*.example``, ``news-hi-*.example``, ``social-a.example``),
texts written here, no real person's name. The Hindi texts reach the pipeline as ingress leaves them: every word
that is neither a gazetteer place nor an ordinary word is ``[WITHHELD]``, and ``pii_redactions`` counts each one.

The golden, in words:

* the Western Express Highway case: four collision reports and one mob report near Andheri, one
  ``affray+collision`` situation on segment 1015 (WEH, Vakola to the Sahar Elevated Road junction at the Andheri
  East edge), two news publishers, ``NEWS-REPORTED`` 0.65;
* two Hindi reports of waterlogging at Hindmata (Dadar East) from two outlets' own feeds: ONE ``urban_flooding``
  situation at the Hindmata flooding spot (pre-linked to junction 19), two independent publishers,
  ``NEWS-REPORTED`` 0.65;
* the Dadar TT robbery: ``reported_crime`` at junction 20 (never ``crime_incident``);
* the Mumbai SACHET thunderstorm alert: a district-level ``weather_hazard`` (area, no segment), ``OFFICIAL-VERIFIED``;
* the Maharashtra state-wide nowcasts (one English, one Hindi, naming other districts): held as outside the city;
* single social posts (a road closure on Tilak Bridge in Dadar, a pandal crowd at Lalbaug in Hindi): held,
  aggregate-only;
* a Hindi "thin crowd" item at a Dadar market: ``general_news``, held.

The canonical social post near Ghatkopar (``testing.social_ghatkopar_signal``) is left out on purpose: the real
resolver reads its "LBS Marg" as the Sion-Kurla stretch (segment 1038), not the stretch at Ghatkopar, and a golden
never pins a reading that is wrong on the map.
"""

from __future__ import annotations

import json
import random

import pytest

from analysis_fixtures import at, make_signal
from osint_common import ethics, testing
from osint_common.types import RawOsintSignal
from osint_analysis.pipeline import (
    HELD_NOT_EVENT,
    HELD_SINGLE_SOCIAL,
    HELD_STATE_LEVEL,
    fused_event_id,
    run_pipeline,
)

resolver_module = pytest.importorskip("osint_geo.resolver", reason="the Mumbai resolver (osint-geo) is not importable")

WITHHELD = "[WITHHELD]"
NOW = at(240)


def _redact(text: str) -> tuple[str, int]:
    out, n = text, 0
    for span in reversed(ethics.unredactable_spans(text)):
        out, n = out[: span.start] + WITHHELD + out[span.end :], n + 1
    return out, n


def hindi(source: str, title: str, body: str, publisher: str, minutes: float, **kw) -> RawOsintSignal:
    """A Hindi signal as ingress emits it: title and text redacted, every withheld run counted."""
    t, n_title = _redact(title)
    b, n_text = _redact(f"{title}। {body}")
    sig = make_signal(source, title=t, text=b, publisher=publisher, published_at=at(minutes), pii=n_title + n_text,
                      source_id=f"synthetic:hi-{publisher.split('.')[0]}-{int(minutes)}", **kw)
    return sig.model_copy(update={"language": "hi"})


def hindmata_reports() -> list[RawOsintSignal]:
    """Two independently written Hindi reports of one waterlogging at Hindmata (Dadar East)."""
    return [
        hindi("news_rss", "हिंदमाता में डॉ. आंबेडकर रोड पर जलभराव, ट्रैफिक जाम",
              "सुबह से लगातार बारिश से हिंदमाता में घुटनों तक पानी, बस धीरे चल रही है।", "news-hi-a.example", 20),
        hindi("news_rss", "लगातार बारिश के बाद हिंदमाता में जलभराव, यात्री परेशान",
              "दादर पूर्व में पानी भरा, पंप चलाने के बाद भी पानी नहीं उतरा, नगर निगम ने बताया।", "news-hi-b.example", 45),
    ]


def social_closure() -> RawOsintSignal:
    """A single English social post: a road closure on Tilak Bridge (segment 1071) in Dadar."""
    title = "Road closed for repairs on Tilak Bridge in Dadar, traffic diverted"
    return make_signal("reddit_rss", title=title, text=f"{title}. Avoid the stretch.",
                       publisher="social-a.example/r/example_city", published_at=at(50),
                       source_id="synthetic:social-tilak-bridge")


def hindi_extras() -> list[RawOsintSignal]:
    """A single Hindi social post, a Hindi state-wide nowcast naming other districts, a Hindi chatter item."""
    return [
        hindi("reddit_rss", "लालबाग में पंडाल पर भारी भीड़", "शाम से लाइन, चलना मुश्किल।",
              "social-a.example/r/example_city", 30),
        hindi("sachet_cap", "पुणे और सातारा जिलों में आकाशीय बिजली के साथ बारिश की चेतावनी",
              "अगले तीन घंटों में आकाशीय बिजली के साथ बारिश की संभावना।", "sachet.ndma.gov.in", -30,
              admin_codes=["LGD:MAHARASHTRA"], place_names=["महाराष्ट्र"], valid_until=at(150)),
        hindi("news_rss", "दादर के बाजार में आज भीड़ कम", "त्योहार के बाद बाजार सूना।", "news-hi-a.example", 60),
    ]


def mumbai_canonical() -> list[RawOsintSignal]:
    """The Mumbai ``osint_common.testing`` signals the real resolver reads correctly: the WEH five, the Dadar TT
    robbery, the Mumbai district and the Maharashtra state-wide SACHET alerts."""
    return [
        *testing.weh_signals(),
        testing.dadar_robbery_signal(),
        testing.sachet_mumbai_signal(),
        testing.sachet_maharashtra_signal(),
    ]


def golden_signals() -> list[RawOsintSignal]:
    return [*mumbai_canonical(), social_closure(), *hindmata_reports(), *hindi_extras()]


def run(signals=None):
    return run_pipeline(signals or golden_signals(), resolver=resolver_module.GazetteerResolver(),
                        live=testing.live_state_dadar_pursuit(), now=NOW)


#: (is_event, class, subtype, toponym, segment, junction, area_level, held_reason, state, credibility,
#: independent publishers, members), in the pipeline's order (surfaced first, then by response priority).
GOLDEN = [
    (True, "road_accident", "affray+collision", "Western Express Highway", 1015, None, False, None,
     "NEWS-REPORTED", 0.65, 2, 5),
    (True, "urban_flooding", "waterlogging", "Hindmata (Dadar East)", None, 19, False, None, "NEWS-REPORTED", 0.65,
     2, 2),
    (True, "reported_crime", "daylight_robbery", "Dadar TT Circle", None, 20, False, None, "NEWS-REPORTED", 0.6,
     1, 1),
    (True, "weather_hazard", "thunderstorm", "Mumbai City (district)", None, None, True, None, "OFFICIAL-VERIFIED",
     0.95, 1, 1),
    (False, "weather_hazard", "thunderstorm", "Maharashtra (state)", None, None, True, HELD_STATE_LEVEL,
     "OFFICIAL-VERIFIED", 0.95, 1, 2),
    (False, "public_gathering", "mass_gathering", "Lalbaug", None, None, True, HELD_SINGLE_SOCIAL,
     "UNVERIFIED-OSINT", 0.25, 1, 1),
    (False, "road_closure", "closure", "Tilak Bridge", 1071, None, False, HELD_SINGLE_SOCIAL, "UNVERIFIED-OSINT",
     0.25, 1, 1),
    (False, "general_news", None, "Dadar", None, None, True, HELD_NOT_EVENT, "NEWS-REPORTED", 0.6, 1, 1),
]


def _row(r):
    return (r.is_event, r.event_class, r.subtype, r.toponym, r.segment_id, r.junction_id, r.area_level,
            r.held_reason, r.verification_state, r.credibility, r.independent_publishers, r.source_count)


def test_the_resolver_places_each_report_where_the_golden_expects():
    """A change here is the resolver's, not the analysis's: the geocodes the golden is built on."""
    geo = run().geocodes
    weh = testing.weh_signals()
    assert {(geo[s.signal_id].feature_type, geo[s.signal_id].segment_id) for s in weh} == {("road", 1015)}
    assert geo[testing.dadar_robbery_signal().signal_id].junction_id == 20
    assert geo[testing.sachet_mumbai_signal().signal_id].area_scope == "district"
    assert geo[testing.sachet_maharashtra_signal().signal_id].area_scope == "state"
    assert (geo[social_closure().signal_id].feature_type, geo[social_closure().signal_id].segment_id) == ("road", 1071)
    for s in hindmata_reports():
        g = geo[s.signal_id]
        assert (g.toponym, g.feature_type, g.junction_id) == ("Hindmata (Dadar East)", "landmark", 19)
    assert all(g is not None for g in geo.values())


def test_the_mumbai_golden():
    result = run()
    assert [_row(r) for r in result.resolved] == GOLDEN
    withheld = sum(s.pii_redactions for s in [*hindmata_reports(), *hindi_extras()])
    assert withheld >= 5  # the Hindi texts really meet the redaction
    assert result.counts.model_dump() == {
        "signals": 14,
        "geotagged": 14,
        "incident_geotagged": 11,  # 5 WEH, 2 Hindmata, the robbery, 3 alerts; not the closure, crowd, chatter
        "fused": 8,
        "surfaced": 4,
        "correlated": 1,
        "cross_type_corroborated": 0,
        "social_held": 2,
        "outside_city_held": 1,
        "pii_redactions": 2 + withheld,  # the canonical [PERSON] and [AGE], and the Hindi [WITHHELD] runs
        "attached_to_live": 0,  # nothing corroborates the Dadar pursuit: a pursuit is never corroborated
    }
    weh = result.resolved[0]
    assert weh.correlated_classes == ["road_accident", "public_conflict"] and weh.sajag_event_kind == "road_accident"
    assert weh.label == "Road accident · Western Express Highway"
    assert weh.fused_event_id == fused_event_id(testing.weh_signals())


def test_the_hindi_waterlogging_is_one_situation_at_hindmata():
    result = run()
    a, b = hindmata_reports()
    (flood,) = [r for r in result.resolved if a.signal_id in r.member_signal_ids]
    assert sorted(flood.member_signal_ids) == sorted([a.signal_id, b.signal_id])
    assert (flood.event_class, flood.subtype, flood.sajag_event_kind) == ("urban_flooding", "waterlogging",
                                                                           "flooding")
    assert flood.label == "Urban flooding · Hindmata (Dadar East)" and flood.junction_id == 19
    assert flood.summary == a.title  # the primary report's redacted Hindi headline
    assert {s.publisher for s in flood.sources} == {"news-hi-a.example", "news-hi-b.example"}
    assert all(s.url is None for s in flood.sources)  # a news URL can name a person: withheld
    assert flood.fused_event_id == fused_event_id([a])
    # the Mumbai district thunderstorm alert is a different level and class: it never joins the street situation
    assert testing.sachet_mumbai_signal().signal_id not in flood.member_signal_ids


def test_one_outlet_or_one_syndicated_text_is_one_publisher():
    a, b = hindmata_reports()
    same_outlet = b.model_copy(update={"publisher": "news-hi-a.example", "url": None})
    (one,) = [r for r in run([a, same_outlet]).resolved]
    assert one.is_event and one.independent_publishers == 1 and one.credibility == 0.6
    copy = a.model_copy(update={"publisher": "news-hi-b.example", "url": None,
                                "signal_id": "f" * 40, "source_id": "synthetic:hi-copy"})
    (wire,) = [r for r in run([a, copy]).resolved]
    assert wire.source_count == 2 and wire.independent_publishers == 1 and wire.credibility == 0.6


def test_a_single_hindi_social_post_is_held_even_with_a_hindi_news_report_elsewhere():
    result = run()
    post = hindi_extras()[0]
    (held,) = [r for r in result.resolved if post.signal_id in r.member_signal_ids]
    assert not held.is_event and held.held_reason == HELD_SINGLE_SOCIAL and held.credibility <= 0.30
    assert held.attach.novel and held.second_order == []


def test_the_state_wide_nowcasts_are_held_as_outside_the_city():
    result = run()
    english, hindi_nowcast = testing.sachet_maharashtra_signal(), hindi_extras()[1]
    (held,) = [r for r in result.resolved if english.signal_id in r.member_signal_ids]
    assert hindi_nowcast.signal_id in held.member_signal_ids  # one aggregate per state and class
    assert held.held_reason == HELD_STATE_LEVEL and held.rep_lon is None and not held.is_event


def test_the_golden_is_the_same_in_any_input_order():
    signals = golden_signals()
    reference = run(signals).model_dump_json()
    rng = random.Random(1028)
    for _ in range(4):
        order = signals[:]
        rng.shuffle(order)
        assert run(order).model_dump_json() == reference


def test_the_golden_output_carries_no_person_and_never_crime_incident():
    result = run()
    dumped = result.model_dump(mode="json")
    ethics.assert_no_person_keys(dumped)
    blob = json.dumps(dumped, ensure_ascii=False)
    assert "crime_incident" not in blob and "vehicle_pursuit" not in blob
    for r in result.resolved:
        assert ethics.find_pii(r.label) == [] and ethics.find_pii(r.summary) == []
        # a Hindi text leaves the pipeline as ingress left it: nothing a redactor could not read
        assert ethics.find_unredactable(r.summary) == []
        assert all(ethics.find_unredactable(s.title) == [] for s in r.sources)
