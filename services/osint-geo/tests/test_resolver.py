"""GazetteerResolver on the canonical synthetic fixtures (osint_common.testing) and on hand-made synthetic Mumbai
signals, in English, Marathi, Hindi and mixed text.

Every signal here is synthetic: fictional publishers (``*.example``), no real person, redacted placeholders only.
The ids are the Mumbai network's (scripts/data/osm_network.json: segments 1001-1086, junctions 1-72).
"""

from __future__ import annotations

import json
import re
import threading
import time

import pytest

from osint_common import ethics, testing
from osint_common.pipeline import GeoResolver
from osint_common.types import Geocode, RawOsintSignal
from osint_geo import resolver as resolver_mod
from osint_geo import translit
from osint_geo.gazetteer import Gazetteer, norm
from osint_geo.resolver import (
    CONTEXT_FORMS,
    DISTRICT_MUMBAI,
    DISTRICT_MUMBAI_SUBURBAN,
    DISTRICT_WITHOUT_POINT,
    STATE_MAHARASHTRA,
    GazetteerResolver,
)

from _synthetic import make_signal

WEH = "Western Express Highway"
#: a city-scoped source (source locality 1.0): the fictional community on the fictional social host
LOCAL = {"source": "reddit_rss", "publisher": "social-a.example/r/example_city"}
SACHET = {"source": "sachet_cap", "publisher": "sachet.ndma.gov.in"}
#: a state-wide SACHET alert: state-level evidence only
MH = {**SACHET, "admin_codes": ["LGD:MAHARASHTRA"], "place_names": ["Maharashtra"]}
#: GDELT's events export: a Maharashtra ActionGeo with the state code
GDELT_IN16 = {"source": "gdelt_events", "publisher": None, "admin_codes": ["GDELT_ADM1:IN16"]}
#: another Maharashtra city's ActionGeo_FullName (OS-2's GDELT hint)
PUNE = ["Pune, Maharashtra, India"]


@pytest.fixture(scope="module")
def resolver() -> GazetteerResolver:
    return GazetteerResolver()


def _resolve(resolver: GazetteerResolver, title: str, text: str | None = None, **kwargs) -> Geocode | None:
    return resolver.resolve(make_signal(title, f"{title}. Details are awaited." if text is None else text, **kwargs))


# ----------------------------------------------------------------------------------------------- the protocol
def test_implements_the_geo_resolver_protocol(resolver):
    assert isinstance(resolver, GeoResolver)


# ----------------------------------------------------------------------------------------------- the WEH replica
def test_weh_replica_resolves_to_the_kalina_vakola_segment_near_andheri(resolver):
    # osint_common.testing's WEH case (its committed geocode uses synthetic ids; the real network's reading is here)
    first = testing.weh_signals()[0]
    g = resolver.resolve(first)
    assert isinstance(g, Geocode) and g.signal_id == first.signal_id
    # the WEH has seven segments: "near Andheri" (coherence) picks the one nearest the Andheri area point
    assert (g.toponym, g.feature_type, g.segment_id, g.junction_id) == (WEH, "road", 1015, None)
    assert g.snapped_to is None and g.residual_m == 0.0 and g.method == "gazetteer_exact"
    assert g.confidence == 0.68 and g.bucket == "medium"
    assert not g.area_level and g.area_scope is None
    assert g.alternatives == ["Andheri"]


def test_every_weh_report_lands_on_the_same_segment(resolver):
    for s in testing.weh_signals():
        g = resolver.resolve(s)
        assert g is not None and g.segment_id == 1015 and g.toponym == WEH, (s.title, g)


def test_a_junction_named_after_the_road_never_takes_the_roads_name(resolver):
    # junction 48 "Western Express Highway (Sahar Elevated Road)" and junctions 2/5 "Marine Drive (...)" never carry
    # the bare road name: "the WEH" is the road, never a pin on one junction of it
    for form in ("western express highway", "पश्चिम द्रुतगती महामार्ग", "marine drive"):
        hits = resolver.gazetteer.lookup(form)
        assert hits and all(resolver.gazetteer.entry(h).feature_type == "road" for h in hits), form


# ----------------------------------------------------------------------------------------------- Dadar TT
def test_dadar_robbery_replica_is_the_dadar_tt_flooding_spot_on_junction_20(resolver):
    g = resolver.resolve(testing.dadar_robbery_signal())
    assert g is not None
    assert (g.toponym, g.feature_type, g.junction_id, g.segment_id) == ("Dadar TT Circle", "landmark", 20, None)
    assert g.snapped_to is None
    assert g.confidence == pytest.approx(0.73, abs=0.001) and g.bucket == "medium"


# ----------------------------------------------------------------------------------------------- area levels (R28)
def test_sachet_district_alert_is_district_level(resolver):
    g = resolver.resolve(testing.sachet_mumbai_signal())
    assert g is not None
    assert g.area_level and g.area_scope == "district" and g.method == "area_fallback" and g.feature_type == "admin"
    assert (g.lon, g.lat) == (DISTRICT_MUMBAI.lon, DISTRICT_MUMBAI.lat)
    assert g.confidence <= 0.4 and g.bucket == "low"
    assert g.segment_id is None and g.junction_id is None and g.snapped_to is None and g.residual_m is None
    assert g.toponym == "Mumbai City (district)"


def test_sachet_state_nowcast_is_state_level_without_a_point(resolver):
    g = resolver.resolve(testing.sachet_maharashtra_signal())
    assert g is not None
    assert g.area_level and g.area_scope == "state" and g.method == "area_fallback"
    assert g.lon is None and g.lat is None
    assert g.confidence == STATE_MAHARASHTRA.confidence <= 0.25 and g.toponym == STATE_MAHARASHTRA.toponym
    assert g.toponym == "Maharashtra (state)" and g.segment_id is None and g.junction_id is None


def test_the_mumbai_suburban_district_has_its_own_point(resolver):
    g = _resolve(resolver, "Heavy rain warning for the district", admin_codes=["LGD:MUMBAI_SUBURBAN"], **SACHET)
    assert g is not None and g.toponym == "Mumbai Suburban (district)" and g.area_scope == "district"
    assert (g.lon, g.lat) == (DISTRICT_MUMBAI_SUBURBAN.lon, DISTRICT_MUMBAI_SUBURBAN.lat) and g.confidence == 0.4


@pytest.mark.parametrize("hint", ["Mumbai Suburban", "मुंबई उपनगर", "mumbai suburban"])
def test_a_hint_that_is_only_a_district_name_is_the_district(resolver, hint):
    # a CAP alert's area "Mumbai Suburban" names the district: it scopes the signal but is never read as text
    s = make_signal("Heavy rain warning for Mumbai Suburban district", admin_codes=["LGD:MUMBAI_SUBURBAN"],
                    place_names=[hint], **SACHET)
    g = resolver.resolve(s)
    assert g is not None and g.toponym == "Mumbai Suburban (district)" and g.area_scope == "district"
    assert g.confidence == 0.4
    assert resolver.city_scoped(s) and resolver.explain(s)["mentions"] == []
    # a news item whose only hint is the district's name is no place at all
    assert resolver.resolve(make_signal("Road caves in", "Road caves in.", source="news_rss",
                                        place_names=[hint])) is None
    # the text naming an area still reads it (a finer toponym)
    g = _resolve(resolver, "Waterlogging in Andheri", admin_codes=["LGD:MUMBAI_SUBURBAN"], place_names=[hint],
                 **SACHET)
    assert g is not None and g.toponym == "Andheri" and g.feature_type == "neighbourhood"


@pytest.mark.parametrize("code", ["LGD:THANE", "LGD:PUNE"])
def test_another_maharashtra_district_never_borrows_a_city_point(resolver, code):
    # a district outside the city is no city location: None alone, the state level with the state code
    s = make_signal("Heavy rain warning for the district", admin_codes=[code], **SACHET)
    assert resolver.resolve(s) is None
    both = make_signal("Heavy rain warning for the district", admin_codes=[code, "LGD:MAHARASHTRA"], **SACHET)
    g = resolver.resolve(both)
    assert g is not None and g.lon is None and g.area_scope == "state"


def test_the_district_contract_probe_reads_the_point_rule_only():
    # DISTRICT_WITHOUT_POINT says whether C-T accepts a district geocode with no point; the same probe with a point
    # is a valid geocode, so a False answer can only come from that rule
    fields = {"signal_id": "0" * 40, "toponym": "probe", "feature_type": "admin", "method": "area_fallback",
              "confidence": 0.30, "bucket": "low", "area_level": True, "area_scope": "district"}
    assert Geocode(lon=72.83, lat=18.94, **fields).area_scope == "district"
    try:
        Geocode(lon=None, lat=None, **fields)
        accepted = True
    except ValueError:
        accepted = False
    assert accepted is DISTRICT_WITHOUT_POINT


def test_the_city_district_comes_first(resolver):
    s = make_signal("Heavy rain warning", admin_codes=["LGD:MUMBAI_SUBURBAN", "LGD:MUMBAI"], **SACHET)
    g = resolver.resolve(s)
    assert g is not None and g.toponym == "Mumbai City (district)"


def test_gdelt_another_state_alone_is_none(resolver):
    s = make_signal("Clashes reported, details awaited", source="gdelt_events", publisher=None,
                    admin_codes=["GDELT_ADM1:IN07"])
    assert resolver.resolve(s) is None


def test_gdelt_in16_alone_is_state_level(resolver):
    s = make_signal("Protest reported, details awaited", **GDELT_IN16)
    g = resolver.resolve(s)
    assert g is not None and g.area_scope == "state" and g.lon is None and g.confidence <= 0.25


@pytest.mark.parametrize("fullname", ["Mumbai, Maharashtra, India", "Bombay, Maharashtra, India"])
def test_a_gdelt_fullname_naming_the_city_is_the_city_district(resolver, fullname):
    s = make_signal("Protest reported, details awaited", place_names=[fullname], **GDELT_IN16)
    g = resolver.resolve(s)
    assert g is not None and g.toponym == DISTRICT_MUMBAI.toponym and g.area_scope == "district"
    assert g.confidence <= 0.4 and (g.lon, g.lat) == (DISTRICT_MUMBAI.lon, DISTRICT_MUMBAI.lat)


def test_another_district_code_is_none(resolver):
    s = make_signal("Heavy rain warning for the district", admin_codes=["LGD:NAGPUR"], **SACHET)
    assert resolver.resolve(s) is None


@pytest.mark.parametrize("source", ["sachet_cap", "imd", "wbsdma", "kmc_scrape", "mumbai_police_scrape"])
def test_every_official_source_uses_the_area_fallback(resolver, source):
    s = make_signal("Heavy rain warning", source=source, publisher=None, admin_codes=["LGD:MUMBAI"])
    g = resolver.resolve(s)
    assert g is not None and g.toponym == "Mumbai City (district)"


def test_only_official_and_gdelt_sources_use_the_area_fallback(resolver):
    # a news or social payload carrying an admin code is not an official area: no city centroid for it
    for kwargs in ({"source": "google_news_rss"}, {"source": "news_rss"}, LOCAL):
        s = make_signal("Rain all evening, roads slow", admin_codes=["LGD:MUMBAI"], **kwargs)
        assert resolver.resolve(s) is None, kwargs


def test_a_finer_toponym_beats_the_area_code(resolver):
    s = make_signal("Waterlogging warning", "Waterlogging likely near Hindmata during the next 3 hours.",
                    admin_codes=["LGD:MUMBAI"], **SACHET)
    g = resolver.resolve(s)
    assert g is not None and not g.area_level and g.toponym == "Hindmata (Dadar East)" and g.junction_id == 19


# ----------------------------------------------------------------------------------------------- honest None
@pytest.mark.parametrize(
    "title",
    [
        "Markets close higher on festive demand",
        "Weather to stay dry through the weekend, says forecaster",
        "Cricket: home side wins the series 3-1",
        "शेअर बाजारात निर्देशांक वाढला",
        "बाजार में तेजी",
        "",
    ],
)
def test_unresolvable_text_is_none(resolver, title):
    s = make_signal(title or "No place named here", "Nothing in this report names a place in the city.")
    assert resolver.resolve(s) is None


@pytest.mark.parametrize(
    "title", ["Mumbai: traffic slow in the evening", "Bombay sees slow traffic", "मुंबईत संध्याकाळी वाहतूक कोंडी",
              "मुंबई में शाम को जाम"]
)
def test_a_city_name_alone_is_never_a_point(resolver, title):
    assert resolver.resolve(make_signal(title, f"{title}.", place_names=["Mumbai"])) is None
    assert resolver.resolve(make_signal(title, f"{title}.")) is None


# ------------------------------------------------------------------------------- "airport" is not a junction alias
@pytest.mark.parametrize(
    "title",
    [
        "Flights delayed at Delhi airport after fog",
        "Kolkata airport runway closed for repairs",
        "Bomb threat email sent to an airport",
    ],
)
def test_another_citys_airport_is_none(resolver, title):
    assert resolver.resolve(make_signal(title, f"{title}. Passengers were told to check their flight status.")) is None


def test_the_airport_word_never_gives_the_airport_junctions(resolver):
    g = _resolve(resolver, "Fire at the airport in Mumbai")
    assert g is None or g.junction_id not in (48, 49)
    assert resolver.gazetteer.lookup("airport") == ()


@pytest.mark.parametrize(
    ("title", "language"),
    [("Smoke seen near Mumbai Airport T2", "en"), ("Smoke seen near the T2 terminal", "en"),
     ("मुंबई विमानतळ टी२ जवळ धूर", "mr"), ("मुंबई हवाई अड्डा टी2 पर धुआं", "hi")],
)
def test_the_airport_by_its_own_names(resolver, title, language):
    # the City Pack's terminal, pre-linked to junction 49 (the departure forecourt)
    g = _resolve(resolver, title, language=language)
    assert g is not None and g.toponym == "Mumbai Airport T2" and g.feature_type == "landmark"
    assert g.junction_id == 49 and g.segment_id is None


def test_the_airport_approach_junction_by_its_own_name(resolver):
    g = _resolve(resolver, "Jam at Western Express Highway (Sahar Elevated Road)")
    assert g is not None and g.junction_id == 48 and g.feature_type == "junction"


# ----------------------------------------------------------------------- the context gate (common words, namesakes)
ELSEWHERE = [
    ("Jam on Marine Drive in Kochi", "en"),
    ("Jam on Coastal Road in Chennai", "en"),
    ("Breakdown on Atal Setu in Goa", "en"),
    ("Jam on LBS Marg in Delhi", "en"),
    ("Jam on LBS Road in Pune", "en"),
    ("Jam on SV Road in Bengaluru", "en"),
    ("Fire at Kasturba Hospital in Manipal", "en"),
    ("Fire at Holy Family Hospital in Delhi", "en"),
    ("Fire at Seven Hills Hospital in Visakhapatnam", "en"),
    ("Fire at St George Hospital in Sydney", "en"),
    ("Tata Memorial Hospital opens a centre in Varanasi", "en"),
    ("Fire at Gandhi Market in Tiruchirappalli", "en"),
    ("Crowd at Mahalaxmi Temple in Kolhapur", "en"),
    ("Mahalaxmi fair draws crowds in Kolhapur", "en"),
    ("Shivaji Park walkers protest in Pune", "en"),
    ("Tigers sighted in a national park in Madhya Pradesh", "en"),
    ("Tourists throng the fort in Jaipur", "en"),
    ("Floods in Santa Cruz, California", "en"),
    ("Lalbag garden reopens in Lucknow", "en"),
    ("Jam on Marine Drvie in Kochi", "en"),  # fuzzy matching never reaches a gated form either
]


@pytest.mark.parametrize(("title", "language"), ELSEWHERE)
def test_context_forms_from_elsewhere_are_none(resolver, title, language):
    # a national outlet that names no Mumbai word: these words mean something else there; one mention and two, and
    # with a next sentence
    for text in (f"{title}. More details are awaited.", title):
        assert resolver.resolve(make_signal(title, text, language=language)) is None, (title, text)


@pytest.mark.parametrize(
    ("title", "kwargs", "toponym"),
    [
        ("Waterlogging on Marine Drive, Mumbai", {}, "Marine Drive"),  # the text names the city
        ("Water main burst on SV Road, 400050", {}, "Swami Vivekanand Road"),  # a Mumbai PIN
        ("Jam on the Coastal Road", {"place_names": ["Mumbai"]}, "Mumbai Coastal Road (northbound)"),  # a city hint
        ("Crowd at Shivaji Park", LOCAL, "Shivaji Park"),  # a city-scoped source
        ("Diversion near Kasturba Hospital", {"source": "kmc_scrape", "publisher": None},
         "Kasturba Hospital (Chinchpokli)"),
        ("Diversion on the Coastal Road tonight", {"source": "mumbai_police_scrape", "publisher": None},
         "Mumbai Coastal Road (northbound)"),
        ("Jam on Marine Drive", {"source": "news_rss", "category_hint": ["area:mumbai"]}, "Marine Drive"),
        ("Waterlogging in Santacruz, Mumbai", {}, "Santacruz"),
        ("मुंबईत मरीन ड्राइव्हवर गर्दी", {"language": "mr"}, "Marine Drive"),  # a Marathi ending on both words
        ("मुंबई में मरीन ड्राइव पर भीड़", {"language": "hi"}, "Marine Drive"),
        ("सांताक्रूझमध्ये पाणी साचले", {**LOCAL, "language": "mr"}, "Santacruz"),
    ],
)
def test_context_forms_count_in_a_signal_about_the_city(resolver, title, kwargs, toponym):
    g = _resolve(resolver, title, **kwargs)
    assert g is not None and g.toponym == toponym and g.method == "gazetteer_exact", (title, g)


@pytest.mark.parametrize(
    ("title", "toponym"),
    [
        ("Waterlogging outside Marine Lines station", "Marine Lines station"),
        ("Jam on Netaji Subhash Chandra Bose Road", "Marine Drive"),
        ("Theft reported at Khar Police Station", "Khar Police Station"),
        ("Khar subway flooded after heavy rain", "Khar subway"),
        ("Fire near Kasturba Hospital (Chinchpokli)", "Kasturba Hospital (Chinchpokli)"),
        ("Crowd at Santacruz station", "Santacruz station"),
        ("Jam on the Bandra-Worli Sea Link", "Bandra-Worli Sea Link (northbound)"),
        ("Jam on the Mumbai Trans Harbour Link", "Atal Setu (Mumbai Trans Harbour Link)"),
    ],
)
def test_the_longer_forms_that_carry_the_place_are_never_gated(resolver, title, toponym):
    g = _resolve(resolver, title)  # a national outlet
    assert g is not None and g.toponym == toponym, (title, g)


def test_the_gate_covers_the_marathi_and_hindi_spellings(resolver):
    assert {"मरीन ड्राइव्ह", "मरीन ड्राइव", "कोस्टल रोड", "अटल सेतू", "अटल सेतु", "खार", "फोर्ट", "एलबीएस मार्ग",
            "शिवाजी पार्क", "सांताक्रूझ", "सांताक्रूज़", "राष्ट्रीय उद्यान"} <= resolver.context_forms
    elsewhere = make_signal("कोचीच्या मरीन ड्राइव्हवर गर्दी", "कोचीच्या मरीन ड्राइव्हवर गर्दी।", language="mr")
    assert resolver.resolve(elsewhere) is None
    here = make_signal("मुंबईच्या मरीन ड्राइव्हवर गर्दी", "मुंबईच्या मरीन ड्राइव्हवर गर्दी।", language="mr")
    g = resolver.resolve(here)
    assert g is not None and g.toponym == "Marine Drive" and g.feature_type == "road"
    # the longer names that carry the place are never gated, in any script
    for form in ("खार पोलीस ठाणे", "खार सबवे", "मरीन लाइन्स स्थानक", "सांताक्रूझ स्थानक", "वांद्रे वरळी सागरी सेतू"):
        assert resolver.gazetteer.lookup(form) and norm(form) not in resolver.context_forms, form


@pytest.mark.parametrize(("latin", "variants"), [("santacruz", ["santa cruz"]), ("mahalaxmi", ["mahalakshmi"])])
def test_the_gate_covers_the_latin_variants(resolver, latin, variants):
    assert latin in resolver.context_forms
    for v in variants:
        assert resolver.gazetteer.lookup(v) == resolver.gazetteer.lookup(latin) and v in resolver.context_forms, v


def test_every_context_form_is_a_gazetteer_form_and_gated(resolver):
    for form in CONTEXT_FORMS:
        assert resolver.gazetteer.lookup(form), form
        assert norm(form) in resolver.context_forms, form
    # the state's name in the free text never opens the gate: Pune has a Shivaji Park too
    s = make_signal("Shivaji Park crowd in Pune, Maharashtra", "Shivaji Park crowd in Pune, Maharashtra.")
    assert resolver.resolve(s) is None
    assert resolver.explain(s)["context_open"] is False


def test_every_bare_route_code_is_gated(resolver):
    # a highway runs on through other towns and states: a bare route code is gated (the Mumbai network carries none)
    codes = {f for f in resolver.gazetteer.forms if re.fullmatch(r"(?:nh|ne|sh)\d+", f)}
    assert codes <= resolver.context_forms


def test_a_script_spelling_known_only_word_by_word_is_gated_too(resolver):
    # the gate reads a script form through to_latin when translit lists no whole-name spelling of it ("कोस्टल रस्ता"
    # → "coastal road"); inject one into the Coastal Road entry
    form = norm("कोस्टल रस्ता")
    assert form not in translit.script_aliases("coastal road")
    assert translit.to_latin(form) == "coastal road"
    doc = json.loads(resolver.gazetteer.path.read_text(encoding="utf-8"))
    entry = next(e for e in doc["entries"] if e["canonical_name"] == "Mumbai Coastal Road (northbound)")
    entry["surface_forms"] = sorted({*entry["surface_forms"], form})
    other = GazetteerResolver(gazetteer=Gazetteer.from_document(doc), network=resolver.network)
    assert form in other.context_forms
    elsewhere = make_signal("चेन्नई कोस्टल रस्ता येथे कोंडी", "चेन्नई कोस्टल रस्ता येथे कोंडी।", language="mr")
    assert other.resolve(elsewhere) is None
    here = make_signal("मुंबई कोस्टल रस्ता येथे कोंडी", "मुंबई कोस्टल रस्ता येथे कोंडी।", language="mr")
    g = other.resolve(here)
    assert g is not None and g.toponym == "Mumbai Coastal Road (northbound)"


# ------------------------------------------------- the gate opens on CITY-level evidence only (review r2, R28)
@pytest.mark.parametrize(
    ("title", "kwargs"),
    [
        ("Jam on LBS Marg in Pune", {"source": "gdelt_doc", "publisher": None, "place_names": PUNE}),
        ("Fire near Kasturba Hospital in Nagpur", {"source": "gdelt_doc", "publisher": None, "place_names": PUNE}),
        # a GDELT DOC article whose URL names only the state (OS-2's _url_place_hints)
        ("Shivaji Park crowd", {"source": "gdelt_doc", "publisher": None, "place_names": ["maharashtra"]}),
        ("Jam on Marine Drive", {"source": "news_rss", "category_hint": ["area:maharashtra"]}),
        # SACHET for another district: R28 says None
        ("Heavy rain likely; Kasturba Hospital on alert in Nagpur",
         {**SACHET, "admin_codes": ["LGD:NAGPUR"], "place_names": ["Nagpur"]}),
    ],
)
def test_state_or_other_city_evidence_never_opens_the_gate(resolver, title, kwargs):
    s = make_signal(title, f"{title}. Details are awaited.", **kwargs)
    assert resolver.resolve(s) is None, title
    ex = resolver.explain(s)
    assert ex["city_scoped"] is False and ex["context_open"] is False and ex["mentions"] == []


@pytest.mark.parametrize(
    ("title", "kwargs"),
    [
        ("Jam on LBS Marg in Pune", {**GDELT_IN16, "place_names": PUNE}),
        ("Fire near Kasturba Hospital in Nagpur", {**GDELT_IN16, "place_names": PUNE}),
        ("Shivaji Park crowd in Pune", {"source": "gdelt_doc", "publisher": None, "admin_codes": ["GDELT_ADM1:IN16"]}),
        ("Heavy rain alert: waterlogging near Shivaji Park in Pune", MH),
        ("Thunderstorm warning for Satara; Kasturba Hospital on alert", MH),
        ("Crowd advisory near the national park in Nashik", {"source": "wbsdma", "publisher": None,
                                                             "admin_codes": ["LGD:MAHARASHTRA"]}),
        ("Fog advisory for the Coastal Road in Ratnagiri", {"source": "imd", "publisher": None,
                                                           "admin_codes": ["LGD:MAHARASHTRA"]}),
    ],
)
def test_a_state_level_signal_naming_another_citys_place_stays_state_level(resolver, title, kwargs):
    s = make_signal(title, f"{title}. Stay indoors.", **kwargs)
    g = resolver.resolve(s)
    assert g is not None and g.area_scope == "state" and g.toponym == "Maharashtra (state)", (title, g)
    assert g.lon is None and g.lat is None and g.confidence <= 0.25
    ex = resolver.explain(s)
    assert ex["city_scoped"] is False and ex["context_open"] is False
    assert resolver.source_locality(s) == 1.0  # the confidence term keeps the source's scope (the PoC's)


@pytest.mark.parametrize(
    ("title", "kwargs", "toponym"),
    [
        ("Heavy rain likely; Kasturba Hospital on alert",
         {**SACHET, "admin_codes": ["LGD:MUMBAI"], "place_names": ["Mumbai"]}, "Kasturba Hospital (Chinchpokli)"),
        ("Protest outside Kasturba Hospital", {**GDELT_IN16, "place_names": ["Mumbai, Maharashtra, India"]},
         "Kasturba Hospital (Chinchpokli)"),
        ("Protest outside Kasturba Hospital", {**GDELT_IN16, "place_names": ["Bombay, Maharashtra, India"]},
         "Kasturba Hospital (Chinchpokli)"),
        ("Fire at Kasturba Hospital", {"source": "gdelt_doc", "publisher": None,
                                       "place_names": ["mumbai", "maharashtra"]}, "Kasturba Hospital (Chinchpokli)"),
        ("Water supply cut near Shivaji Park", {"source": "kmc_scrape", "publisher": None,
                                                "admin_codes": ["LGD:MUMBAI"]}, "Shivaji Park"),
        ("Diversion on Marine Drive tonight", {"source": "mumbai_police_scrape", "publisher": None}, "Marine Drive"),
        ("Jam on LBS Marg", {"admin_codes": ["LGD:MUMBAI_SUBURBAN"], **SACHET}, "Lal Bahadur Shastri Marg"),
        ("Jam on Marine Drive", LOCAL, "Marine Drive"),
    ],
)
def test_city_level_evidence_opens_the_gate(resolver, title, kwargs, toponym):
    s = make_signal(title, f"{title}. Details are awaited.", **kwargs)
    g = resolver.resolve(s)
    assert g is not None and g.toponym == toponym and not g.area_level, (title, g)
    ex = resolver.explain(s)
    assert ex["city_scoped"] is True and ex["context_open"] is True


def test_city_scoped_reads_city_level_metadata_only(resolver):
    city = [
        make_signal("Rain all evening", **LOCAL),
        make_signal("Rain all evening", source="kmc_scrape", publisher=None),
        make_signal("Rain all evening", source="mumbai_police_scrape", publisher=None),
        make_signal("Rain all evening", place_names=["Mumbai, Maharashtra, India"]),
        make_signal("Rain all evening", place_names=["Bombay"]),
        make_signal("Rain all evening", place_names=["Brihanmumbai"]),
        make_signal("Rain all evening", admin_codes=["LGD:MUMBAI"]),
        make_signal("Rain all evening", admin_codes=["LGD:MUMBAI_SUBURBAN"]),
        make_signal("Rain all evening", category_hint=["area:mumbai"]),
        make_signal("Rain all evening", category_hint=["area:mumbai_suburban"]),
        make_signal("Water main burst near the school, 400007"),
    ]
    state = [
        make_signal("Rain all evening", **SACHET),
        make_signal("Rain all evening", source="wbsdma", publisher=None),
        make_signal("Rain all evening", source="imd", publisher=None),
        make_signal("Rain all evening", place_names=["Maharashtra"]),
        make_signal("Rain all evening", place_names=PUNE),
        make_signal("Rain all evening", admin_codes=["LGD:MAHARASHTRA"]),
        make_signal("Rain all evening", admin_codes=["GDELT_ADM1:IN16"]),
        make_signal("Rain all evening", category_hint=["area:maharashtra"]),
    ]
    for s in city:
        assert resolver.city_scoped(s) and resolver.source_locality(s) == 1.0, (s.raw_geo_hint, s.category_hint)
    for s in state:  # full source locality (the confidence term), but not in the city
        assert not resolver.city_scoped(s) and resolver.state_scoped(s), (s.raw_geo_hint, s.category_hint)
        assert resolver.source_locality(s) == 1.0
    plain = make_signal("Mumbai: rain all evening")  # a national outlet naming the city in its text
    assert not resolver.city_scoped(plain) and resolver.source_locality(plain) == 0.3
    thane_pin = make_signal("Water main burst near the school, 400601")  # a Thane PIN is not a Mumbai PIN
    assert not resolver.city_scoped(thane_pin)
    navi_pin = make_signal("Water main burst near the school, 400703")  # nor is a Navi Mumbai PIN
    assert not resolver.city_scoped(navi_pin)


# ---------------------------------------------------------- namesakes of other cities and states (review r2)
@pytest.mark.parametrize(
    "title",
    [
        "Marine Drive walkway repaired in Kochi",
        "Coastal Road project delayed in Goa",
        "Atal Setu lit up for the festival in Goa",
        "Gandhi Market traders protest in Tiruchirappalli",
        "Lalbag flower show opens in Lucknow",
        "Santa Cruz beach cleaned in Goa",
        "Fort walls restored in Jodhpur",
        "Holy Family Hospital expands in Delhi",
    ],
)
def test_namesakes_from_elsewhere_are_none(resolver, title):
    # a national outlet whose text names no Mumbai word, one mention and two
    for text in (f"{title}. More details are awaited.", title):
        assert resolver.resolve(make_signal(title, text)) is None, (title, text)


@pytest.mark.parametrize(
    ("title", "kwargs", "want"),
    [
        ("Rally on Marine Drive, Mumbai", {}, {"segment_id": 1001}),
        ("Jam on the Coastal Road, Mumbai", {}, {"feature_type": "road"}),
        ("Breakdown on Atal Setu, Mumbai", {}, {"toponym": "Atal Setu (Mumbai Trans Harbour Link)",
                                                "segment_id": None}),
        ("Jam on SV Road, 400050", {}, {"toponym": "Swami Vivekanand Road", "segment_id": 1022}),
        ("Waterlogging in Khar", LOCAL, {"toponym": "Khar", "segment_id": None}),
        ("Crowd at Fort", LOCAL, {"toponym": "Fort (Mumbai)", "segment_id": None}),
        ("Crowd at Mahalaxmi Temple, Mumbai", {}, {"toponym": "Mahalaxmi Temple"}),
        ("Waterlogging in Mahalaxmi", LOCAL, {"toponym": "Mahalaxmi"}),
    ],
)
def test_namesakes_count_in_a_signal_placed_in_the_city(resolver, title, kwargs, want):
    g = _resolve(resolver, title, **kwargs)
    assert g is not None, title
    for key, value in want.items():
        assert getattr(g, key) == value, (title, key, getattr(g, key))


# ------------------------------------------------------- station names: the trains, the talukas (review r2)
@pytest.mark.parametrize(
    ("title", "language"),
    [
        ("Dadar Express delayed by four hours", "en"),
        ("Bandra Express derailed near Surat", "en"),
        ("LTT Duronto cancelled", "en"),
        ("Kurla Express runs late", "en"),
        ("दादर एक्सप्रेस देरी से चल रही है", "hi"),
        ("दादर एक्सप्रेस उशिराने धावत आहे", "mr"),
        ("Heavy rain in Kurla taluka", "en"),
        ("Heavy rain in Andheri taluka", "en"),
    ],
)
def test_the_trains_and_talukas_named_after_a_place_are_not_the_place(resolver, title, language):
    assert _resolve(resolver, title, language=language) is None, title
    assert _resolve(resolver, title, language=language, **LOCAL) is None, title


@pytest.mark.parametrize(
    ("title", "want"),
    [
        ("Water logging in Kurla after rain", {"toponym": "Kurla", "segment_id": None}),
        ("Crowd at Dadar station", {"toponym": "Dadar station"}),
        ("Crowd at CSMT", {"junction_id": 4}),
        ("सीएसएमटी स्थानकात गर्दी", {"junction_id": 4}),
        ("हिंदमाता में जलभराव", {"junction_id": 19}),
    ],
)
def test_the_station_places_still_resolve(resolver, title, want):
    g = _resolve(resolver, title)
    assert g is not None, title
    for key, value in want.items():
        assert getattr(g, key) == value, (title, key, getattr(g, key))


# --------------------------------- the state gate: a state-level alert names districts and talukas (review r3)
#: an alert listing the suburban talukas (Andheri, Borivali, Kurla) among other districts, in each script
STATE_ALERTS = [
    ("Heavy rain likely in Andheri, Borivali and Kurla", "en"),
    ("अंधेरी, बोरिवली आणि कुर्ला येथे मुसळधार पावसाची शक्यता", "mr"),
    ("अंधेरी, बोरीवली और कुर्ला में भारी बारिश", "hi"),
    ("Thunderstorm likely over Kurla and Thane", "en"),
    ("Heavy rain in Borivli and Palghar", "en"),
]


@pytest.mark.parametrize(
    "kwargs",
    [
        MH,
        {"source": "wbsdma", "publisher": None, "admin_codes": ["LGD:MAHARASHTRA"], "place_names": ["Maharashtra"]},
        {"source": "imd", "publisher": None, "admin_codes": ["LGD:MAHARASHTRA"]},
        {**GDELT_IN16, "place_names": ["Thane, Maharashtra, India"]},
        {**GDELT_IN16, "place_names": ["Maharashtra, India"]},
    ],
    ids=["sachet-lgd-mh", "sdma-lgd-mh", "imd-lgd-mh", "gdelt-in16-thane", "gdelt-in16-mh"],
)
@pytest.mark.parametrize(("title", "language"), STATE_ALERTS)
def test_a_state_level_alert_naming_a_taluka_stays_state_level(resolver, title, language, kwargs):
    # "Andheri", "Borivali" and "Kurla" in a state-wide alert are the talukas: never the city's area pin
    s = make_signal(title, f"{title}.", language=language, **kwargs)
    g = resolver.resolve(s)
    assert g is not None and g.toponym == "Maharashtra (state)", (title, g)
    assert g.area_level and g.area_scope == "state" and g.method == "area_fallback" and g.feature_type == "admin"
    assert g.lon is None and g.lat is None and g.confidence == 0.25
    assert g.segment_id is None and g.junction_id is None
    ex = resolver.explain(s)
    assert ex["state_scoped"] is True and ex["city_scoped"] is False and ex["context_open"] is False
    assert ex["mentions"] == []


def test_the_state_gate_covers_every_spelling(resolver):
    assert set(resolver_mod.STATE_GATED_FORMS) == {"andheri", "borivali", "kurla"}
    assert resolver.state_forms == {
        "andheri", "अंधेरी", "borivali", "borivli", "बोरिवली", "बोरीवली", "kurla", "कुर्ला",
    }
    # the longer names that carry the place are never state-gated
    for form in ("andheri subway", "andheri station", "kurla station", "borivali station", "अंधेरी सबवे",
                 "कुर्ला स्थानक"):
        assert resolver.gazetteer.lookup(form) and form not in resolver.state_forms, form


@pytest.mark.parametrize(
    ("title", "kwargs", "language"),
    [
        # the district code is city-level evidence: the neighbourhood
        ("Waterlogging in Kurla", {**SACHET, "admin_codes": ["LGD:MUMBAI_SUBURBAN"],
                                   "place_names": ["Mumbai Suburban"]}, "en"),
        ("Waterlogging in Kurla", {**SACHET, "admin_codes": ["LGD:MUMBAI_SUBURBAN"]}, "en"),
        # a state alert whose text names the city: the city word is city-level evidence
        ("Waterlogging in Kurla, Mumbai", MH, "en"),
        ("मुंबईतील कुर्ल्यात पाणी साचले", MH, "mr"),
        # GDELT's FullName naming the city
        ("Waterlogging in Kurla", {**GDELT_IN16, "place_names": ["Mumbai, Maharashtra, India"]}, "en"),
        # a national outlet with no state evidence keeps the form, and so does a city-scoped source
        ("Waterlogging in Kurla", {}, "en"),
        ("Waterlogging in Kurla", LOCAL, "en"),
    ],
)
def test_city_level_evidence_or_none_keeps_the_kurla_neighbourhood(resolver, title, kwargs, language):
    s = make_signal(title, f"{title}.", language=language, **kwargs)
    g = resolver.resolve(s)
    assert g is not None and g.toponym == "Kurla" and g.feature_type == "neighbourhood", (title, kwargs, g)
    # an area (F-HONEST OSINT-3): its point, never a segment
    assert g.segment_id is None and g.junction_id is None and g.snapped_to is None and g.residual_m is None
    assert g.lon is not None and g.lat is not None


# ---------------------------------------------------------------------------- the geo hints read (review r2)
def test_only_the_first_hints_are_read(resolver):
    assert (resolver_mod.MAX_HINTS, resolver_mod.MAX_HINT_CHARS) == (8, 200)
    filler = [f"filler {i}" for i in range(8)]
    s = make_signal("Road blocked after a fall of trees", "Traffic diverted.", place_names=[*filler, "Hindmata"])
    assert resolver.resolve(s) is None  # the ninth hint is not read
    s = make_signal("Road blocked after a fall of trees", "Traffic diverted.", place_names=[*filler, "Mumbai"])
    assert resolver.source_locality(s) == 0.3 and not resolver.city_scoped(s)
    cut = make_signal("Road blocked after a fall of trees", "Traffic diverted.",
                      place_names=["x" * 200 + " Hindmata"])
    assert resolver.resolve(cut) is None  # past the hint's 200th character
    within = make_signal("Road blocked after a fall of trees", "Traffic diverted.",
                         place_names=[*filler[:-1], "Hindmata"])
    g = resolver.resolve(within)
    assert g is not None and g.toponym == "Hindmata (Dadar East)"


def test_a_maximal_hostile_signal_stays_cheap(resolver):
    # 64 hints of 1000 characters of near-miss names: no exact form, so the fuzzy stage scans what is read
    words = ["hindmataa", "andherii", "subwayy", "kurlaa", "chowpaty", "girgaun", "wankhedee", "stadiumm", "circel",
             "nakaa"]
    blob = " ".join(words[i % len(words)] for i in range(400))
    s = make_signal(blob[:1000], blob[:4000], place_names=[blob[:1000]] * 64, **LOCAL)
    t0 = time.perf_counter()
    resolver.resolve(s)
    assert time.perf_counter() - t0 < 1.0


def test_the_operator_lookup_is_about_the_city(resolver):
    # GET /osint/gazetteer/resolve: an operator's query is local, so the gate is open
    top = resolver.resolve_text("marine drive")
    assert top and top[0]["canonical_name"] == "Marine Drive"


# ----------------------------------------------------------------------------------- generator aliases (review r1)
@pytest.mark.parametrize(
    ("title", "segment_id"),
    [("Jam on the Kalina Vakola flyover", 1015), ("Accident on the Andheri flyover", 1016),
     ("Jam on the Dindoshi flyover", 1019)],
)
def test_a_flyover_the_road_runs_over_names_the_road(resolver, title, segment_id):
    g = _resolve(resolver, title)
    assert g is not None and g.feature_type == "road" and g.segment_id == segment_id, (title, g)


# ------------------------------------------------------------------------------------ social, grammar, scripts
def test_social_post_resolves_to_the_road_it_names(resolver):
    s = testing.social_ghatkopar_signal()  # "Road closed for metro work near Ghatkopar on LBS Marg"
    g = resolver.resolve(s)
    assert g is not None and g.feature_type == "road" and g.toponym == "Lal Bahadur Shastri Marg"
    assert "Ghatkopar" in g.alternatives
    # r/<community> is a city-scoped source: full locality, and the gate is open for "LBS Marg"
    assert resolver.source_locality(s) == 1.0 and resolver.city_scoped(s)


@pytest.mark.parametrize(
    ("title", "want"),
    [("Crowd at Matunga stn", {"toponym": "Matunga station"}), ("Crowd at Girgaon chaupati", {"junction_id": 6}),
     ("Theft reported at Worli thana", {"toponym": "Worli Police Station"}), ("Fire near KEM hosp", {"junction_id": 18})],
)
def test_short_place_words_are_rewritten_to_the_place(resolver, title, want):
    g = _resolve(resolver, title)
    assert g is not None and g.method == "grammar", (title, g)
    for key, value in want.items():
        assert getattr(g, key) == value, (title, key, getattr(g, key))
    # the bare area word would also read as the neighbourhood: the rewrite is unambiguous
    assert "Matunga" not in g.alternatives and "Worli" not in g.alternatives


@pytest.mark.parametrize(
    ("title", "language", "want"),
    [
        ("कुर्ल्यात एका दुकानाला आग", "mr", {"toponym": "Kurla"}),
        ("दादरमध्ये हिंदमाता येथे पाणी साचले", "mr", {"junction_id": 19}),
        ("हिंदमाता येथे पाणी साचले", "mr", {"toponym": "Hindmata (Dadar East)"}),
        ("अंधेरी सबवे पाण्याखाली", "mr", {"junction_id": 47}),
        ("मिलन सबवेमध्ये पाणी साचले", "mr", {"junction_id": 42}),
        ("किंग्ज सर्कल येथे वाहतूक कोंडी", "mr", {"junction_id": 21}),
        ("सायन सर्कलजवळ अपघात", "mr", {"junction_id": 23}),
        ("घाटकोपरमध्ये झाड कोसळले", "mr", {"toponym": "Ghatkopar"}),
        ("गिरगाव चौपाटीवर गर्दी", "mr", {"junction_id": 6}),
        ("अंधेरी में दुकान में आग", "hi", {"toponym": "Andheri"}),
        ("सायन सर्कल पर जाम", "hi", {"junction_id": 23}),
        ("हिंदमाता में जलभराव", "hi", {"toponym": "Hindmata (Dadar East)"}),
        ("मुंबई में मरीन ड्राइव पर भीड़", "hi", {"toponym": "Marine Drive"}),
    ],
)
def test_marathi_and_hindi_text(resolver, title, language, want):
    g = _resolve(resolver, title, f"{title}।", language=language)
    assert g is not None, title
    for key, value in want.items():
        assert getattr(g, key) == value, (title, key, getattr(g, key))
    if g.feature_type == "neighbourhood":  # an area, never a segment
        assert g.segment_id is None and g.junction_id is None


@pytest.mark.parametrize(
    ("title", "want"),
    [
        ("Mumbai madhe Marine Drive var gardi", {"toponym": "Marine Drive"}),
        ("जाम near Sion Circle", {"junction_id": 23}),
        ("पश्चिम द्रुतगती महामार्गावर अंधेरीजवळ अपघात", {"toponym": WEH}),
        ("WEH वर अंधेरीजवळ अपघात", {"toponym": WEH}),
        ("Waterlogging at हिंदमाता junction", {"toponym": "Hindmata (Dadar East)"}),
    ],
)
def test_mixed_marathi_and_english_text(resolver, title, want):
    g = _resolve(resolver, title)
    assert g is not None, title
    for key, value in want.items():
        assert getattr(g, key) == value, (title, key, getattr(g, key))


@pytest.mark.parametrize(
    ("title", "toponym"),
    [
        ("Jam at Ghatkoper", "Ghatkopar"),
        ("Waterlogging in Girgaum", "Girgaon"),
        ("Jam at Vileparle", "Vile Parle"),
        ("Waterlogging in Borivli", "Borivali"),
        ("Jam at Kandivli", "Kandivali"),
        ("Waterlogging in Mazagaon", "Mazgaon"),
        ("Jam at Varli", "Worli"),
        ("Rain at Mahalakshmi", "Mahalaxmi"),  # gated: the hint names the city
        ("Waterlogging in Santa Cruz", "Santacruz"),  # gated: the hint names the city
    ],
)
def test_romanised_variants_and_misspellings(resolver, title, toponym):
    g = _resolve(resolver, title, place_names=["Mumbai"])
    assert g is not None and g.toponym == toponym, (title, g)
    assert g.method == "gazetteer_exact" and g.junction_id is None  # an area word, never the junction


@pytest.mark.parametrize(
    "text",
    [
        "सांताक्रूज़ में बारिश",  # "ज़" as one code point (U+095B)
        "सांताक्रूज़ में बारिश",  # "ज" + nukta
    ],
)
def test_both_spellings_of_a_nukta_letter(resolver, text):
    assert [m.form for m in resolver.mentions(text, city=True)] == [norm("सांताक्रूज़")]


def test_the_marathi_case_endings_of_city_and_road_words(resolver):
    # "मुंबईत" (in Mumbai) names the city and opens the gate; "शहरातील" (in the city) and "रस्त्यावर" (on the road)
    # name no place
    assert resolver.names_city(resolver.tokens("मुंबईत पाणी साचले"))
    assert resolver.mentions("शहरातील रस्त्यावर पाणी साचले") == []
    assert [m.form for m in resolver.mentions("मुंबईत मरीन ड्राइव्हवर गर्दी")] == ["मरीन ड्राइव्ह"]
    assert resolver.mentions("मरीन ड्राइव्हवर गर्दी") == []  # no city word: the gated form is no mention


def test_a_landmark_near_the_road_snaps_to_a_segment(resolver):
    # Wankhede Stadium keeps its own name and snaps to Marine Drive (within 900 m)
    g = _resolve(resolver, "Crowd outside Wankhede Stadium", **LOCAL)
    assert g is not None and g.feature_type == "landmark" and g.toponym == "Wankhede Stadium"
    assert g.segment_id == 1002 and g.junction_id is None and g.snapped_to == "Marine Drive"


def test_place_name_hints_are_read(resolver):
    s = make_signal("Road blocked after a fall of trees", "Traffic diverted after trees fell.",
                    place_names=["Hindmata"])
    g = resolver.resolve(s)
    assert g is not None and g.toponym == "Hindmata (Dadar East)"


# ------------------------------------------------------------------------ sentence ends never join two words
@pytest.mark.parametrize(
    ("title", "text", "toponym", "language"),
    [
        ("Fire at Worli", "Fire at Worli. Naka traders shut their shops.", "Worli", "en"),
        ("Rain at Sion", "Rain at Sion. Circle traffic slow.", "Sion", "en"),
        ("Crowd at Lalbaug", "Crowd at Lalbaug! Chowk closed to traffic.", "Lalbaug", "en"),
        ("वरळीत आग", "वरळीत आग। नाका परिसरात गर्दी।", "Worli", "mr"),
    ],
)
def test_a_junction_is_never_read_across_a_sentence_end(resolver, title, text, toponym, language):
    # "Worli. Naka ..." names the area, never "Worli Naka" (junction 24)
    g = resolver.resolve(make_signal(title, text, language=language))
    assert g is not None and g.toponym == toponym and g.junction_id is None, (text, g)


def test_a_junction_named_naka_still_resolves(resolver):
    for text in ("Jam at Worli Naka since morning.", "Jam at Worli Naka. Details awaited."):
        g = resolver.resolve(make_signal("Jam", text))
        assert g is not None and g.junction_id == 24, text


def test_abbreviations_and_initials_never_end_a_sentence(resolver):
    g = _resolve(resolver, "Waterlogging on Dr. Ambedkar Road")
    assert g is not None and g.feature_type == "road" and g.toponym.startswith("Dr Ambedkar Road")
    g = _resolve(resolver, "Crash near S.V. Road, 400054")
    assert g is not None and g.feature_type == "road" and g.toponym == "Swami Vivekanand Road"
    assert resolver.tokens("Sion. Circle") == ["sion", resolver_mod.SENTENCE_BREAK, "circle"]
    assert resolver_mod.SENTENCE_BREAK not in resolver.tokens("Jam near S.V. Rd. flyover")


# ----------------------------------------------------------------------------------------------- confidence inputs
def test_source_locality(resolver):
    assert resolver.source_locality(testing.weh_signals()[0]) == 0.3  # a national outlet, no hint
    assert resolver.source_locality(testing.sachet_mumbai_signal()) == 1.0
    hinted = make_signal("Rain at Kurla", place_names=["Mumbai"])
    assert resolver.source_locality(hinted) == 1.0
    pinned = make_signal("Water main burst", "A water main burst near the school, 400007.")
    assert resolver.source_locality(pinned) == 1.0
    # the city's name in the free text is not locality (national outlets name it in passing)
    assert resolver.source_locality(make_signal("Mumbai: rain at Kurla")) == 0.3


def test_repeated_mentions_never_inflate_confidence(resolver):
    once = make_signal("Fire near Wankhede Stadium", "Fire brigade called.")
    twice = make_signal("Fire near Wankhede Stadium", "Fire near Wankhede Stadium, fire brigade called.", n=2)
    g1, g2 = resolver.resolve(once), resolver.resolve(twice)
    assert g1 is not None and g2 is not None and g1.toponym == g2.toponym == "Wankhede Stadium"
    assert g2.confidence <= g1.confidence


def test_confidence_and_bucket_agree(resolver):
    for s in [*testing.weh_signals(), testing.dadar_robbery_signal(), testing.social_ghatkopar_signal()]:
        g = resolver.resolve(s)
        assert g is not None
        assert g.bucket == ("high" if g.confidence >= 0.75 else "medium" if g.confidence >= 0.5 else "low")


# ----------------------------------------------------------------------------------------------- determinism, threads
def _all_fixture_signals() -> list[RawOsintSignal]:
    return [
        *testing.weh_signals(),
        testing.dadar_robbery_signal(),
        testing.sachet_mumbai_signal(),
        testing.sachet_maharashtra_signal(),
        testing.social_ghatkopar_signal(),
    ]


def test_deterministic_across_resolvers(resolver):
    other = GazetteerResolver()
    for s in _all_fixture_signals():
        a, b, c = resolver.resolve(s), resolver.resolve(s), other.resolve(s)
        assert (a and a.model_dump()) == (b and b.model_dump()) == (c and c.model_dump())


def test_thread_safe_after_load(resolver):
    signals = _all_fixture_signals()
    want = [g and g.model_dump() for g in (resolver.resolve(s) for s in signals)]
    errors: list[BaseException] = []
    results: list[list] = []

    def work() -> None:
        try:
            for _ in range(20):
                results.append([g and g.model_dump() for g in (resolver.resolve(s) for s in signals)])
        except BaseException as exc:  # pragma: no cover - reported below
            errors.append(exc)

    threads = [threading.Thread(target=work) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    assert all(r == want for r in results) and len(results) == 160


def test_a_mapping_is_validated_as_a_raw_signal(resolver):
    s = testing.dadar_robbery_signal()
    g = resolver.resolve(s.model_dump(mode="json"))
    assert g is not None and g.junction_id == 20
    bad = s.model_dump(mode="json")
    bad["author"] = "someone"  # a person key never gets through
    with pytest.raises(ValueError, match="forbidden_key"):
        resolver.resolve(bad)


def test_geocodes_name_places_never_persons(resolver):
    for s in _all_fixture_signals():
        g = resolver.resolve(s)
        if g is not None:
            dumped = g.model_dump(mode="json")
            ethics.assert_no_person_keys(dumped)
            assert set(dumped) == set(Geocode.model_fields)


def test_explain_reports_forms_never_the_text(resolver):
    s = testing.weh_signals()[0]
    ex = resolver.explain(s)
    assert ex["geocode"]["toponym"] == WEH and ex["locality"] == 0.3
    assert {m["form"] for m in ex["mentions"]} >= {"western express highway", "andheri"}
    assert s.title not in repr(ex) and "speeding" not in repr(ex)


def test_default_resolver_is_shared():
    assert resolver_mod.default_resolver() is resolver_mod.default_resolver()


def test_a_hostile_text_stays_cheap(resolver):
    # a 4000-character text that repeats a two-segment name: coherence runs over the distinct points, not pairs
    body = ("marine drive " * 400)[:3990]
    s = make_signal("Marine Drive, Mumbai", body)  # the city named: the context gate is open
    t0 = time.perf_counter()
    g = resolver.resolve(s)
    assert time.perf_counter() - t0 < 1.0
    assert g is not None and g.feature_type == "road" and g.toponym == "Marine Drive"
    # the same text from elsewhere is no mention at all, just as fast
    t0 = time.perf_counter()
    assert resolver.resolve(make_signal("Marine Drive", body)) is None
    assert time.perf_counter() - t0 < 1.0


# ---------------------------------------------------------------------------- F-HONEST OSINT-1 / OSINT-3
def test_an_area_mention_is_never_pinned_on_the_junction_named_after_it(resolver):
    # "Parel" alone is the area; the junction is "Parel (Dr Ambedkar Road)" (OSINT-1)
    g = _resolve(resolver, "Gold looted from a shop in Parel; traders protest")
    assert g is not None and g.toponym == "Parel" and g.feature_type == "neighbourhood"
    assert g.junction_id is None and g.segment_id is None and g.residual_m is None
    # a junction's own name still pins the junction
    g = _resolve(resolver, "Robbery at Sion Circle")
    assert g is not None and g.junction_id == 23


@pytest.mark.parametrize(
    ("word", "toponym"),
    [("Worli", "Worli"), ("Parel", "Parel"), ("Lalbaug", "Lalbaug"), ("Byculla", "Byculla"), ("Mahim", "Mahim"),
     ("Powai", "Powai"), ("Chembur", "Chembur"), ("Kurla", "Kurla"), ("Andheri", "Andheri"),
     ("Ghatkopar", "Ghatkopar"), ("Dadar", "Dadar"), ("Vakola", None)],
)
def test_a_bare_area_word_is_the_area_never_the_junction_named_after_it(resolver, word, toponym):
    g = _resolve(resolver, f"Water supply cut in {word} today")
    if toponym is None:  # Vakola has no area entry: the junction is named "Vakola" itself
        assert g is not None and g.junction_id == 39
        return
    assert g is not None and g.toponym == toponym and g.junction_id is None, (word, g)


def test_a_landmark_beyond_900_m_keeps_no_segment_and_no_snap_credit(resolver):
    for title, toponym in (("Crowd at Gateway of India", "Gateway of India"),
                           ("Crowd at Juhu Beach", "Juhu Beach"),
                           ("Fire near Rajawadi Hospital", "Rajawadi Hospital (Ghatkopar)")):
        g = _resolve(resolver, title)
        assert g is not None and g.toponym == toponym
        assert g.segment_id is None and g.snapped_to is None and g.residual_m is None


def test_a_state_alerts_issuer_sign_off_is_no_place_and_no_city_word(resolver):
    """Maharashtra SDMA signs every Marathi nowcast "मंत्रालय, मुंबई" (its office): in a state source that is never
    a Mantralaya pin and never opens the city gate; the same words in a news item are a place."""
    geo = _resolve(resolver, "पुढील ३ तासांत ठाणे आणि पालघर जिल्ह्यात मध्यम पावसाची शक्यता. मंत्रालय, मुंबई",
                   "नागरिकांनी काळजी घ्यावी. मंत्रालय, मुंबई", **MH)
    assert geo is not None and geo.area_level and geo.area_scope == "state" and geo.junction_id is None
    hit = _resolve(resolver, "Waterlogging near Mantralaya, Mumbai after heavy rain", "", **LOCAL)
    assert hit is not None and hit.junction_id == 1
