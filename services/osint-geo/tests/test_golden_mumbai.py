"""The Mumbai golden set: synthetic headlines in English, Marathi, Hindi and mixed text, each with the geocode the
resolver must give (toponym, feature type, segment or junction, area scope), and the time budget.

It replaces the proof-of-concept parity check, which compared the resolver with another city's real geocodes
(README, "Tests"). Every headline is written for this test: fictional publishers, no real person's name, no real
event. The places are the City Pack's (``cities/mumbai``) and the network's (``scripts/data/osm_network.json``); a
place's name may honour a person (a road, a hospital, a square), which is a place, never that person. The set covers
the recurring flooding spots and subways (Hindmata, King's Circle, Dadar TT, Gandhi Market, Kranti Nagar by the
Mithi, Parel TT, Chunabhatti, Milan and Andheri subways, Malad subway), bridges and links, stations, Ganeshotsav
(pandals and visarjan points), police stations, hospitals, junctions, roads, the two Mumbai districts, state-level
alerts and honest ``None``s. Every expectation was checked by hand against the map, not copied from the resolver.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import pytest

from osint_common import ethics
from osint_geo.resolver import GazetteerResolver

from _synthetic import make_signal

LOCAL = {"source": "reddit_rss", "publisher": "social-a.example/r/example_city"}
SACHET = {"source": "sachet_cap", "publisher": "sachet.ndma.gov.in"}
#: the whole set, title to geocode, cold (a fresh resolver) and warm: the PoC's budget for its 107 signals
TIME_BUDGET_S = 2.0


@dataclass(frozen=True)
class Golden:
    """One synthetic headline and the geocode it must give (``want`` ``None``: the honest ``None``)."""

    gid: str
    category: str
    language: str  # en, mr, hi or mixed
    title: str
    want: dict[str, Any] | None
    signal: dict[str, Any] = field(default_factory=dict)


def _place(toponym: str, feature_type: str, segment_id: int | None = None, junction_id: int | None = None) -> dict:
    return {"toponym": toponym, "feature_type": feature_type, "segment_id": segment_id, "junction_id": junction_id,
            "area_scope": None}


def _area(toponym: str, scope: str) -> dict:
    return {"toponym": toponym, "feature_type": "admin", "segment_id": None, "junction_id": None, "area_scope": scope}


GOLDEN: tuple[Golden, ...] = (
    # ---------------------------------------------- flooding spots and subways (pre-linked to their junction)
    Golden("M01", "low_lying", "en", "Knee-deep water at Hindmata after overnight rain",
           _place("Hindmata (Dadar East)", "landmark", junction_id=19)),
    Golden("M02", "low_lying", "mr", "हिंदमाता परिसरात गुडघाभर पाणी, वाहतूक वळवली",
           _place("Hindmata (Dadar East)", "landmark", junction_id=19)),
    Golden("M03", "low_lying", "en", "King's Circle waterlogged at high tide; BEST buses diverted",
           _place("King's Circle (Matunga)", "landmark", junction_id=21)),
    Golden("M04", "low_lying", "hi", "किंग्स सर्कल में जलभराव, बसें मोड़ी गईं",
           _place("King's Circle (Matunga)", "landmark", junction_id=21)),
    Golden("M05", "low_lying", "mr", "दादर टीटी येथे पाणी साचले", _place("Dadar TT Circle", "landmark", junction_id=20)),
    # a gated form ("Gandhi Market" names markets in many cities): read in a city-scoped source
    Golden("M06", "low_lying", "en", "Gandhi Market flooded again after heavy rain",
           _place("Gandhi Market (Sion)", "landmark", segment_id=1068), LOCAL),  # Dr Ambedkar Road, 310 m
    Golden("M07", "low_lying", "en", "Water enters homes in Kranti Nagar as the Mithi rises",
           _place("Kranti Nagar (Kurla, Mithi river)", "landmark", segment_id=1051)),  # SCLR Kurla ramp
    Golden("M08", "low_lying", "en", "Parel TT junction under water; traffic crawls",
           _place("Parel TT (Parel East)", "landmark", segment_id=1070)),  # Dr E Borges Road
    Golden("M09", "low_lying", "en", "Chunabhatti station road waterlogged after heavy showers",
           _place("Chunabhatti station road", "landmark", segment_id=1043)),  # Eastern Express Highway (Sion)
    Golden("M10", "low_lying", "en", "Milan Subway shut after heavy rain",
           _place("Milan Subway (Santacruz)", "landmark", junction_id=42)),
    Golden("M11", "low_lying", "mr", "अंधेरी सबवे पाण्याखाली, वाहतूक बंद", _place("Andheri Subway", "landmark", junction_id=47)),
    Golden("M12", "low_lying", "hi", "मिलन सबवे में पानी भरा, यातायात रोका गया",
           _place("Milan Subway (Santacruz)", "landmark", junction_id=42)),
    Golden("M13", "low_lying", "en", "Malad subway closed to traffic as water rises",
           _place("Malad subway (Malad West)", "landmark")),  # more than 900 m from every segment: no road anchor
    # ---------------------------------------------- bridges and links
    Golden("M14", "bridge", "en", "Bandra-Worli Sea Link closed to two-wheelers in strong winds",
           _place("Bandra-Worli Sea Link (northbound)", "road", segment_id=1008)),
    Golden("M15", "bridge", "en", "Mumbai: breakdown on Atal Setu slows traffic",
           _place("Atal Setu (Mumbai Trans Harbour Link)", "neighbourhood")),  # off the network: an area
    Golden("M16", "bridge", "en", "Gokhale Bridge reopened for light vehicles",
           _place("G K Gokhale Bridge", "road", segment_id=1028)),
    Golden("M17", "bridge", "mr", "टिळक पूल येथे वाहतूक कोंडी", _place("Tilak Bridge", "road", segment_id=1071)),
    Golden("M18", "bridge", "en", "Delisle Road bridge work: diversions in place",
           _place("Delisle Road bridge (Lower Parel)", "landmark", segment_id=1064)),  # Dr Ambedkar Road
    # ---------------------------------------------- stations
    Golden("M19", "station", "en", "Overcrowding at Dadar station after local trains halted",
           _place("Dadar station", "landmark", segment_id=1071)),  # Tilak Bridge
    Golden("M20", "station", "hi", "सीएसएमटी स्टेशन पर भारी भीड़",
           _place("CSMT (Chhatrapati Shivaji Maharaj Terminus)", "landmark", junction_id=4)),
    Golden("M21", "station", "en", "Crowds build at Kurla station as Harbour line services stop",
           _place("Kurla station", "landmark", segment_id=1038)),  # LBS Marg
    Golden("M22", "station", "mr", "अंधेरी स्थानकात प्रवाशांची गर्दी",
           _place("Andheri station", "landmark", segment_id=1028)),  # Gokhale Bridge
    # ---------------------------------------------- Ganeshotsav: pandals and visarjan points
    Golden("M23", "ganeshotsav", "en", "Lalbaugcha Raja queue stretches past midnight",
           _place("Lalbaugcha Raja", "landmark", segment_id=1064)),  # Dr Ambedkar Road, 106 m
    Golden("M24", "ganeshotsav", "mr", "लालबागचा राजा मंडपाजवळ भाविकांची गर्दी",
           _place("Lalbaugcha Raja", "landmark", segment_id=1064)),
    Golden("M25", "ganeshotsav", "en", "Long queue at GSB Seva Mandal pandal on the fifth day",
           _place("GSB Seva Mandal (King's Circle)", "landmark", segment_id=1068)),
    Golden("M26", "ganeshotsav", "en", "Visarjan crowds swell at Girgaon Chowpatty",
           _place("Girgaon Chowpatty", "landmark", junction_id=6)),
    Golden("M27", "ganeshotsav", "mr", "गिरगाव चौपाटीवर विसर्जनासाठी गर्दी",
           _place("Girgaon Chowpatty", "landmark", junction_id=6)),
    # ---------------------------------------------- police stations
    Golden("M28", "police_station", "en", "Complaint filed at Dadar police station",
           _place("Dadar Police Station", "poi", segment_id=1072)),  # Senapati Bapat Marg
    Golden("M29", "police_station", "mr", "माटुंगा पोलीस ठाणे येथे तक्रार",
           _place("Matunga Police Station", "poi", segment_id=1068)),  # Dr Ambedkar Road, 88 m
    Golden("M30", "police_station", "hi", "बांद्रा पुलिस थाना के पास जाम",
           _place("Bandra Police Station", "poi", segment_id=1022)),  # SV Road
    # ---------------------------------------------- hospitals (KEM and Sion pre-linked to their junctions)
    Golden("M31", "hospital", "en", "Ambulances queue outside KEM Hospital", _place("KEM Hospital", "landmark", junction_id=18)),
    Golden("M32", "hospital", "en", "Sion hospital emergency ward shifted",
           _place("Sion Hospital (LTMGH)", "landmark", junction_id=22)),
    Golden("M33", "hospital", "mr", "केईएम रुग्णालयात रुग्णवाहिकांची रांग", _place("KEM Hospital", "landmark", junction_id=18)),
    Golden("M34", "hospital", "hi", "कूपर अस्पताल के बाहर एम्बुलेंस की कतार",
           _place("Cooper Hospital", "landmark", segment_id=1026)),  # SV Road
    # ---------------------------------------------- junctions and roads
    Golden("M35", "junction", "en", "Signal failure at Worli Naka, long tailbacks",
           _place("Worli Naka", "junction", junction_id=24)),
    Golden("M36", "junction", "mr", "सायन सर्कल येथे अपघात", _place("Sion Circle", "junction", junction_id=23)),
    # "on WEH near Vakola": the WEH stretch that starts at Vakola junction 39 (segment 1015, 39 -> 48, the Kalina-Vakola
    # flyover); the junction is the alternative, the road is what the report is about
    Golden("M37", "road", "en", "Truck breakdown on WEH near Vakola",
           _place("Western Express Highway", "road", segment_id=1015)),
    Golden("M38", "road", "en", "Traffic slow on Peddar Road after tree fall",
           _place("Peddar Road (Dr G Deshmukh Marg)", "road", segment_id=1085)),
    Golden("M39", "road", "en", "Mumbai: tree falls on SV Road near Santacruz",
           _place("Swami Vivekanand Road", "road", segment_id=1022)),
    Golden("M40", "low_lying", "mixed", "Hindmata-la paani bharla, BEST bus वळवल्या",
           _place("Hindmata (Dadar East)", "landmark", junction_id=19)),
    Golden("M41", "junction", "mixed", "Sion Circle-javal अपघात, traffic jam", _place("Sion Circle", "junction", junction_id=23)),
    Golden("M42", "ganeshotsav", "mixed", "Lalbaugcha Raja-chya darshanasathi गर्दी",
           _place("Lalbaugcha Raja", "landmark", segment_id=1064)),
    # ---------------------------------------------- the two Mumbai districts (R28: the district point, 0.40)
    Golden("M43", "district", "en", "Thunderstorm warning for Mumbai City district",
           _area("Mumbai City (district)", "district"),
           {**SACHET, "admin_codes": ["LGD:MUMBAI"], "place_names": ["Mumbai"]}),
    Golden("M44", "district", "en", "Heavy rain warning for Mumbai Suburban district",
           _area("Mumbai Suburban (district)", "district"),
           {**SACHET, "admin_codes": ["LGD:MUMBAI_SUBURBAN"], "place_names": ["Mumbai Suburban"]}),
    Golden("M45", "district", "en", "Flooding reported", _area("Mumbai City (district)", "district"),
           {"source": "gdelt_events", "publisher": None, "admin_codes": ["GDELT_ADM1:IN16"],
            "place_names": ["Mumbai, Maharashtra, India"]}),
    # ---------------------------------------------- state-level alerts (no point, 0.25)
    Golden("M46", "state", "en", "Heavy rain likely over Thane, Palghar and Raigad",
           _area("Maharashtra (state)", "state"),
           {**SACHET, "admin_codes": ["LGD:MAHARASHTRA"], "place_names": ["Maharashtra"]}),
    # a state alert listing talukas names Andheri, Borivali and Kurla, never their area pins (STATE_GATED_FORMS)
    Golden("M47", "state", "en", "Heavy rain likely over Andheri, Borivali and Kurla talukas",
           _area("Maharashtra (state)", "state"),
           {**SACHET, "admin_codes": ["LGD:MAHARASHTRA"], "place_names": ["Maharashtra"]}),
    Golden("M48", "state", "mr", "किनारपट्टीच्या जिल्ह्यांत मुसळधार पावसाचा इशारा",
           _area("Maharashtra (state)", "state"),
           {"source": "wbsdma", "publisher": None, "admin_codes": ["LGD:MAHARASHTRA"]}),
    Golden("M49", "state", "hi", "महाराष्ट्र के तटीय जिलों में भारी बारिश", _area("Maharashtra (state)", "state"),
           {"source": "imd", "publisher": None, "admin_codes": ["LGD:MAHARASHTRA"]}),
    # ---------------------------------------------- honest None: the same words elsewhere
    Golden("M50", "none", "en", "Waterlogging on Marine Drive in Kochi", None),
    Golden("M51", "none", "en", "Waterlogging on SV Road in Bengaluru", None),
    Golden("M52", "none", "en", "Fire near Santa Cruz boardwalk in California", None),
    Golden("M53", "none", "hi", "रामलीला मैदान में भीड़", None),
)


def _signal(g: Golden):
    return make_signal(g.title, f"{g.title}. Details are awaited.", language="mr" if g.language == "mixed" else
                       g.language, **g.signal)


def _shape(geo) -> dict[str, Any] | None:
    if geo is None:
        return None
    return {"toponym": geo.toponym, "feature_type": geo.feature_type, "segment_id": geo.segment_id,
            "junction_id": geo.junction_id, "area_scope": geo.area_scope}


@pytest.fixture(scope="module")
def resolver() -> GazetteerResolver:
    return GazetteerResolver()


@pytest.mark.parametrize("g", GOLDEN, ids=[g.gid for g in GOLDEN])
def test_golden_geocode(resolver, g):
    geo = resolver.resolve(_signal(g))
    assert _shape(geo) == g.want, (g.gid, g.title, geo)
    if geo is None:
        return
    # the honest shape of each kind of answer
    if geo.feature_type == "neighbourhood":  # an area (F-HONEST OSINT-3): its point, never a road anchor
        assert geo.lon is not None and geo.snapped_to is None and geo.residual_m is None
    if geo.feature_type == "admin":  # R28: a district carries its representative point, a state none
        assert geo.area_level and geo.method == "area_fallback"
        assert (geo.lon is None) == (geo.area_scope == "state")
        assert geo.confidence == (0.4 if geo.area_scope == "district" else 0.25) and geo.bucket == "low"
    if geo.junction_id is not None or (geo.feature_type == "road" and geo.segment_id is not None):
        assert geo.residual_m == 0.0 and geo.snapped_to is None
    if geo.feature_type in ("landmark", "poi") and geo.snapped_to is not None:
        assert 0.0 < geo.residual_m <= 900.0


def test_the_golden_set_covers_the_city():
    assert len(GOLDEN) >= 30 and len({g.gid for g in GOLDEN}) == len(GOLDEN)
    assert {g.category for g in GOLDEN} == {"low_lying", "bridge", "station", "ganeshotsav", "police_station",
                                           "hospital", "junction", "road", "district", "state", "none"}
    assert {g.language for g in GOLDEN} == {"en", "mr", "hi", "mixed"}
    low = {g.want["toponym"] for g in GOLDEN if g.category == "low_lying" and g.want}
    assert low == {"Hindmata (Dadar East)", "King's Circle (Matunga)", "Dadar TT Circle", "Gandhi Market (Sion)",
                   "Kranti Nagar (Kurla, Mithi river)", "Parel TT (Parel East)", "Chunabhatti station road",
                   "Milan Subway (Santacruz)", "Andheri Subway", "Malad subway (Malad West)"}
    assert {g.want["area_scope"] for g in GOLDEN if g.want and g.want["area_scope"]} == {"district", "state"}


def test_the_golden_headlines_name_no_person():
    # synthetic text only: the redactor finds nothing to redact in any headline (places are protected, no names)
    for g in GOLDEN:
        assert ethics.find_pii(g.title) == [], g.gid


def test_golden_geocodes_are_places_only(resolver):
    for g in GOLDEN:
        geo = resolver.resolve(_signal(g))
        if geo is not None:
            ethics.assert_no_person_keys(geo.model_dump(mode="json"))


def test_golden_is_deterministic(resolver):
    other = GazetteerResolver()
    for g in GOLDEN:
        s = _signal(g)
        a, b = resolver.resolve(s), other.resolve(s)
        assert (a and a.model_dump()) == (b and b.model_dump()), g.gid


def test_the_golden_set_resolves_well_within_the_time_budget():
    signals = [_signal(g) for g in GOLDEN]
    t0 = time.perf_counter()
    fresh = GazetteerResolver()  # a new resolver over the loaded gazetteer and network: the gates are rebuilt
    cold = [fresh.resolve(s) for s in signals]
    cold_s = time.perf_counter() - t0
    t0 = time.perf_counter()
    for _ in range(5):
        warm = [fresh.resolve(s) for s in signals]
    warm_s = (time.perf_counter() - t0) / 5
    assert [_shape(x) for x in cold] == [_shape(x) for x in warm] == [g.want for g in GOLDEN]
    assert cold_s < TIME_BUDGET_S and warm_s < TIME_BUDGET_S / 4, (cold_s, warm_s)
