"""classify() on Marathi and Hindi text, as it reaches the classifier: AFTER the ingress redaction.

Every headline here is synthetic (written for this file; no real person's name, no party, leader or symbol). Each is
classified twice: as written, and as ingress leaves it, where every Marathi or Devanagari word that is neither a
gazetteer place nor an ordinary word of ``osint_common.ethics.INDIC_COMMON_WORDS`` is ``[WITHHELD]`` (no Indic NER
runs at parse, so an unknown word may be a name). :func:`redact` applies exactly the spans ingress applies. The class
must be the same both ways: every cue word the lexicon relies on survives the redaction (a test below pins that too).
The places are read from osint-common's synthetic Mumbai test gazetteer, so the redaction is the same whatever the
generated repo gazetteer holds.
"""

from __future__ import annotations

import random
import unicodedata
from pathlib import Path

import pytest

from analysis_fixtures import make_signal
from osint_common import ethics, kinds
from osint_analysis import classify as C
from osint_analysis.fusion import content_tokens

#: The token ingress writes for a withheld Indic word or run of words (``osint_ingress.connectors._redact``).
WITHHELD = "[WITHHELD]"
_TEST_GAZETTEER = (
    Path(__file__).resolve().parents[2] / "osint-common" / "tests" / "fixtures" / "mumbai_gazetteer.synthetic.json"
)


@pytest.fixture(autouse=True)
def _mumbai_places(monkeypatch):
    monkeypatch.setenv(ethics.GAZETTEER_ENV, str(_TEST_GAZETTEER))
    ethics.reset_place_phrases()
    yield
    ethics.reset_place_phrases()


def redact(text: str) -> str:
    """The text as ingress leaves it: each run of unreadable Indic words becomes ``[WITHHELD]``."""
    out = text
    for span in reversed(ethics.unredactable_spans(text)):
        out = out[: span.start] + WITHHELD + out[span.end :]
    return out


def mr(title: str, **kw):
    """A Marathi report from a fictional outlet's own feed (``news_rss``)."""
    sig = make_signal("news_rss", title=title, publisher=kw.pop("publisher", "news-mr-a.example"), **kw)
    return sig.model_copy(update={"language": "mr"})


def both(title: str):
    """The classification of a headline as written and as redacted."""
    return C.classify(mr(title)), C.classify(mr(redact(title)))


#: (headline, class, subtype): one or more Mumbai-style headlines per class.
HEADLINES = [
    # waterlogging: पाणी साचले / तुंबले, जलमय, गुडघाभर पाणी, मुसळधार पाऊस, high-tide water
    ("हिंदमाता येथे पाणी साचले, वाहतूक कोंडी", "urban_flooding", "waterlogging"),
    ("मुसळधार पावसामुळे अंधेरी सबवे जलमय", "urban_flooding", "waterlogging"),
    ("किंग्ज सर्कल परिसरात गुडघाभर पाणी", "urban_flooding", "waterlogging"),
    ("भरतीच्या वेळी सखल भागात पाणी तुंबले", "urban_flooding", "waterlogging"),
    ("मिलन सबवेत पाणी तुंबल्याने वाहतूक बंद", "urban_flooding", "waterlogging"),  # the cause wins over the closure
    # road accidents: अपघात, and with a vehicle in the clause धडक / उलटली / संघर्ष
    ("पश्चिम द्रुतगती महामार्गावर ट्रकची कारला धडक, दोन जखमी", "road_accident", "collision"),
    ("घाटकोपरमध्ये बस उलटली, प्रवासी जखमी", "road_accident", "collision"),
    ("सायन येथे भीषण अपघात, तीन जण ठार", "road_accident", "collision"),
    ("दोन बसचा संघर्ष, अनेक प्रवासी जखमी", "road_accident", "collision"),
    # a clash between groups (no vehicle), a mob beating after a crash (the conflict row comes first, as in English)
    ("कुर्ल्यात दोन गटांत हाणामारी, दगडफेक", "public_conflict", "affray"),
    ("वस्तीत दोन गटांमध्ये संघर्ष", "public_conflict", "affray"),
    ("अपघातानंतर संतप्त जमावाकडून चालकाला मारहाण", "public_conflict", "affray"),
    # fire
    ("कुर्ला येथील गोदामाला भीषण आग, अग्निशमन दलाच्या आठ गाड्या", "fire", "structure_fire"),
    ("अंधेरीत इमारतीला आग लागली", "fire", "structure_fire"),
    # collapse: a landslide, a chawl balcony, a burst main and a road cave-in
    ("भांडुपमध्ये दरड कोसळली, घरांचे नुकसान", "infra_failure", "collapse"),
    ("चाळीचा सज्जा कोसळून दोन जखमी", "infra_failure", "collapse"),
    ("जलवाहिनी फुटल्याने रस्ता खचला", "infra_failure", "collapse"),
    # a local-train stoppage
    ("ओव्हरहेड वायर तुटल्याने लोकल सेवा ठप्प", "infra_failure", "rail_disruption"),
    ("सिग्नल यंत्रणेत बिघाड, मध्य रेल्वेची लोकल वाहतूक विस्कळीत", "infra_failure", "rail_disruption"),
    # a chemical spill, a fallen tree, a live wire
    ("रासायनिक द्रव्याची गळती, परिसरात धोका", "hazard", "spill"),
    ("वादळी वाऱ्यामुळे झाड रस्त्यावर कोसळले", "hazard", "fallen_tree"),
    ("दादरमध्ये झाड उन्मळून पडले, वाहतूक खोळंबली", "hazard", "fallen_tree"),
    ("विजेचा धक्का लागून मृत्यू", "hazard", "live_wire"),
    # a crowd of devotees, a stadium crowd
    ("लालबागमध्ये भाविकांची मोठी गर्दी", "public_gathering", "mass_gathering"),
    ("वानखेडे स्टेडियमबाहेर प्रेक्षकांची गर्दी", "public_gathering", "mass_gathering"),
    # a procession (the situation on the road, whoever walks), the Ganeshotsav immersion, a palanquin procession
    ("गिरगाव चौपाटीवर गणेशोत्सवाचे विसर्जन, मिरवणुका रात्रभर", "procession", "procession"),
    ("अनंत चतुर्दशीला लालबागहून विसर्जन मिरवणूक", "procession", "procession"),
    ("पालखी सोहळ्यामुळे वाहतूक कोंडी", "procession", "procession"),
    # a sit-in, a road blockade, a strike, a bandh call
    ("मैदानात आंदोलकांचे धरणे", "unrest", "protest"),
    ("रास्ता रोको आंदोलनामुळे वाहतूक ठप्प", "unrest", "protest"),
    ("रिक्षाचालकांचा संप, प्रवाशांचे हाल", "unrest", "protest"),
    ("कामगार संघटनांकडून बंदची हाक", "unrest", "protest"),
    # a closure, metro work, an alternative route, traffic changes
    ("मेट्रोच्या कामामुळे अंधेरी-कुर्ला रस्ता बंद, वाहतूक वळवली", "road_closure", "closure"),
    ("सबवे बंद, पर्यायी मार्गाने वाहतूक", "road_closure", "closure"),
    ("वाहतुकीत बदल: शिवाजी पार्क परिसरात रस्ते बंद", "road_closure", "closure"),
    # cyclone, lightning, a heat wave
    ("मुंबईत चक्रीवादळाचा इशारा, किनारपट्टीवर सतर्कता", "weather_hazard", "storm"),
    ("विजांचा कडकडाट, सोसाट्याचा वारा", "weather_hazard", "storm"),
    ("ठाण्यात वीज कोसळून नुकसान", "weather_hazard", "storm"),
    ("राज्यात उष्णतेची लाट", "weather_hazard", "storm"),
    # reported crime: a chain snatching, a robbery at gunpoint, an ATM break-in (a situation for response, never
    # crime_incident)
    ("दादरमध्ये सोनसाखळी चोरी", "reported_crime", "daylight_robbery"),
    ("सराफ दुकानात बंदुकीचा धाक दाखवून दरोडा", "reported_crime", "daylight_robbery"),
    ("एटीएम फोडून चोरी", "reported_crime", "daylight_robbery"),
]

#: Headlines whose cue word is used another way: never the class that word would suggest.
NEGATIVES = [
    ("दहा वर्षांत पहिल्यांदाच पाणी साचले नाही", "general_news"),  # negated
    ("धडक मोर्चा काढला, आयुक्तांना निवेदन", "unrest"),  # "धडक मोर्चा" is a march, not a collision
    ("धडक कारवाई: अनधिकृत फेरीवाल्यांवर कारवाई", "general_news"),  # a swift action
    ("भाज्यांच्या दरांना आग", "general_news"),  # prices on fire
    ("आग ओकणारी गोलंदाजी", "general_news"),  # a fire-spitting spell
    ("राजकीय वादळ उठले", "general_news"),  # a figurative storm
    ("साचलेल्या पाण्यात डासांच्या अळ्या, डेंग्यूचा धोका", "general_news"),  # a dengue notice
    ("गर्दी कमी, दुकाने रिकामी", "general_news"),  # a thin crowd
    ("तुरळक गर्दी", "general_news"),
    ("पश्चिम द्रुतगती महामार्गावर वाहनांची गर्दी", "general_news"),  # a crowding of vehicles is congestion
    ("वाहतुकीची गर्दी, प्रवासी त्रस्त", "general_news"),
    ("पावसाने मोर्चा वळवला", "general_news"),  # the rain moved on
    ("पाऊस संपला, रस्ते कोरडे", "general_news"),  # "संपला" (it ended) is not a strike
    ("रसायनांचे विसर्जन नियमानुसार करा", "general_news"),  # immersion with no festival
    ("चालक आणि प्रवाशांमध्ये संघर्ष", "public_conflict"),  # a driver is not a vehicle: a clash
    ("मुंबईच्या पूर्व उपनगरात नवे उद्यान", "general_news"),  # "पूर्व" (east) is not "पूर" (flood)
    ("रस्ता बंद", "road_closure"),  # a bare "बंद" is a closure ...
    ("मुंबई बंदची हाक", "unrest"),  # ... and a bandh only from its call
]

HINDI = [
    ("अंधेरी सबवे में भारी जलभराव, यातायात ठप", "urban_flooding"),
    ("सायन में ट्रक की टक्कर से दो घायल", "road_accident"),
    ("घाटकोपर में इमारत गिरी", "infra_failure"),
    ("तेज आंधी से पेड़ गिरा", "hazard"),
    ("लोकल सेवा ठप, यात्री परेशान", "infra_failure"),
    ("वोट लूट का आरोप", "general_news"),  # an electoral claim, never a robbery
    ("सब्जियों की कीमतों में आग", "general_news"),  # prices on fire
    ("दुकानों पर आज भीड़ कम", "general_news"),  # a thin crowd
]


@pytest.mark.parametrize(("title", "event_class", "subtype"), HEADLINES)
def test_marathi_headlines_classify_as_written_and_after_redaction(title, event_class, subtype):
    raw, redacted = both(title)
    for got in (raw, redacted):
        assert (got.event_class, got.subtype) == (event_class, subtype), (title, redact(title), got.matched_terms)
        assert got.matched_terms and all(len(t) <= 64 for t in got.matched_terms)
        assert got.sajag_event_kind not in C.FORBIDDEN_OSINT_KINDS


def test_the_table_really_meets_the_redaction():
    # many headlines lose some words at ingress, and still classify (the test above)
    withheld = [t for t, _, _ in HEADLINES if WITHHELD in redact(t)]
    assert len(withheld) >= len(HEADLINES) // 3
    assert {cls for _, cls, _ in HEADLINES} == kinds.EVENT_CLASSES  # every event class has Marathi cues


@pytest.mark.parametrize(("title", "event_class"), NEGATIVES)
def test_marathi_precision_guards(title, event_class):
    raw, redacted = both(title)
    assert raw.event_class == event_class, (title, raw.matched_terms)
    assert redacted.event_class == event_class, (redact(title), redacted.matched_terms)


@pytest.mark.parametrize(("title", "event_class"), HINDI)
def test_hindi_headlines(title, event_class):
    raw, redacted = both(title)
    assert raw.event_class == event_class, (title, raw.matched_terms)
    assert redacted.event_class == event_class, (redact(title), redacted.matched_terms)


def test_every_indic_cue_word_survives_the_ingress_redaction():
    """Each word of each Marathi or Hindi keyword (and of the CAP terms and the guards' vocabularies) is kept at
    ingress, so the classifier sees it. The only exceptions are words that are also given names (never added to the
    common words): their keywords match unredacted text only."""
    name_like = {C.normalize_text(w) for w in ("अग्नि", "गुल")}
    words: set[str] = set()
    for kw in [k for row in C.CLASS_LEXICON for k in row.keywords] + list(C.CAP_FLOOD_TERMS) + [
        t for _, terms in C.CAP_SUBTYPES for t in terms
    ]:
        if C.is_indic(kw):
            for slot in C.indic_slots(kw):
                words.update(slot)
    for vocabulary in (C.VEHICLE_WORDS, C._PRICE_WORDS, C._SPITTING_FIRE, C._FIGURATIVE_STORM_OF, C._SOCIAL_MEDIA,
                       C._DENGUE, C._PREVENT, C._VOTE, C._THIN, C._TRAFFIC, C._FESTIVAL, C._NEGATORS):
        words.update(w for w in vocabulary if C.is_indic(w))
    assert len(words) > 250
    withheld = sorted(w for w in words if ethics.unredactable_spans(w))
    assert set(withheld) == name_like, withheld
    for w in name_like:  # and those stay withheld: they double as names
        assert ethics._indic_key(w) not in ethics.INDIC_COMMON_WORDS


def test_no_bengali_is_read_any_more():
    """The Indic tables are Marathi and Hindi (Devanagari) only."""
    for kw in [k for row in C.CLASS_LEXICON for k in row.keywords] + list(C.CAP_FLOOD_TERMS):
        assert not any("ঀ" <= ch <= "৿" for ch in kw), kw
    assert C.classify(mr("হিন্দমাতায় জল জমেছে")).event_class == "general_news"


@pytest.mark.parametrize(
    ("text", "keyword", "expected"),
    [
        ("ट्रकची धडक", "धडक/धडकली/धडकले/धडकून/धडकल्याने/धडकेत", True),  # a case ending on the vehicle
        ("अपघातात जखमी", "अपघात", True),  # a case ending
        ("मिरवणुकीत गर्दी", "मिरवणूक/मिरवणुका/मिरवणुकी", True),
        ("वादळाचा तडाखा", "वादळ/वादळी", True),
        ("दुर्घटनाओं में", "दुर्घटना", True),  # a Hindi plural
        ("झाड रस्त्यावर कोसळले",
         "झाड/झाडे/झाडाची/झाडांची/फांदी/फांद्या/वृक्ष … "
         "कोसळले/कोसळली/कोसळला/कोसळून/कोसळल्याने/पडले/पडली/पडला/पडून/उन्मळून/तुटली/तुटून", True),  # one between
        ("तेल-गळती", "तेलगळती", False),  # a hyphenated spelling is two words
        ("संप", "संप=", True),
        ("संपला", "संप=", False),  # "=": no case ending ("it ended")
    ],
)
def test_indic_words_match_with_their_case_endings_and_slots(text, keyword, expected):
    assert C.keyword_matches(keyword, text) is expected


def test_an_indic_keyword_is_a_whole_word():
    assert not C.keyword_matches("आग/आगी", "आगमन")  # "arrival" starts with the cue
    assert not C.keyword_matches("पूर", "पूर्व")  # "east" is not a flood
    tree = ("झाड/झाडे/झाडाची/झाडांची/फांदी/फांद्या/वृक्ष … "
            "कोसळले/कोसळली/कोसळला/कोसळून/कोसळल्याने/पडले/पडली/पडला/पडून/उन्मळून/तुटली/तुटून")
    assert not C.keyword_matches(tree, "झाड लावले आणि पुस्तक पडले")  # two words between
    assert C.keyword_matches(tree, "झाड पडले")
    assert C.keyword_forms("मिरवणूक/मिरवणुका/मिरवणुकी") == ("मिरवणूक/मिरवणुका/मिरवणुकी",)  # no English forms


def test_a_shared_word_reads_its_context_per_row():
    clash, collision = "दोन गटांत संघर्ष", "दोन बसचा संघर्ष"
    assert C.keyword_matches("संघर्ष", clash, "public_conflict")
    assert not C.keyword_matches("संघर्ष", clash, "road_accident")
    assert C.keyword_matches("संघर्ष", collision, "road_accident")
    assert not C.keyword_matches("संघर्ष", collision, "public_conflict")


def test_matched_terms_name_the_cue_never_another_word_of_the_text():
    got = C.classify(mr("झाड [WITHHELD] कोसळले दादरमध्ये"))
    assert got.matched_terms == ["झाड … कोसळले"]  # the gap word is shown as "…"
    got = C.classify(mr("हिंदमाता येथे पाणी साचले, वाहतूक कोंडी"))
    assert got.matched_terms == ["पाणी साचले"]


@pytest.mark.parametrize(
    ("title", "cap_event", "event_class", "subtype"),
    [
        ("मुंबई जिल्ह्यात मुसळधार पावसाचा इशारा", None, "urban_flooding", "waterlogging"),
        ("सखल भागात पाणी साचण्याची शक्यता, सतर्क राहा", None, "urban_flooding", "waterlogging"),
        ("मुंबई में भारी बारिश की चेतावनी", None, "urban_flooding", "waterlogging"),
        ("विजांचा कडकडाट आणि हलका पाऊस", None, "weather_hazard", "thunderstorm"),
        ("अरबी समुद्रात चक्रीवादळ, किनारपट्टीला इशारा", None, "weather_hazard", "cyclone"),
        ("उष्णतेची लाट, काळजी घ्या", None, "weather_hazard", "heat"),
        ("पहाटे दाट धुके", None, "weather_hazard", "fog"),
        ("हलक्या ते मध्यम पावसाची शक्यता", None, "weather_hazard", "rain"),
        ("मुंबई जिल्ह्यासाठी सतर्कतेचा इशारा", None, "weather_hazard", "weather_advisory"),
    ],
)
def test_the_sachet_rule_reads_marathi_and_hindi_alerts(title, cap_event, event_class, subtype):
    alert = make_signal("sachet_cap", title=title, publisher="sachet.ndma.gov.in", admin_codes=["LGD:MUMBAI"])
    alert = alert.model_copy(update={"language": "mr", "raw": {"cap_identifier": "synthetic.cap.mr"}})
    got = C.classify(alert)
    assert (got.event_class, got.subtype) == (event_class, subtype), title


def test_fusion_tokens_read_marathi_words_whole_and_drop_the_withheld_token():
    a = mr("हिंदमाता येथे पाणी साचले, [WITHHELD] हाल")
    b = mr("हिंदमातामध्ये पाणी तुंबले", publisher="news-mr-b.example")
    ta, tb = content_tokens(a), content_tokens(b)
    assert "withheld" not in ta
    assert content_tokens(mr("हिंदमाता")) <= ta & tb and C.normalize_text("पाणी") in ta & tb  # case endings stripped
    assert all(unicodedata.category(t[-1])[0] in "LMN" for t in ta)  # never a fragment cut at a vowel sign
    assert "3" in content_tokens(mr("जखमी ३")) and "3" in content_tokens(mr("तीन गाड्या"))  # digits, number words
    assert "2" in content_tokens(mr("दोघांना दुखापत"))


def test_fuzz_marathi_and_hindi_titles_never_yield_crime_incident():
    rng = random.Random(20261030)
    vocab = [w for row in C.CLASS_LEXICON for k in row.keywords if C.is_indic(k) for slot in C.indic_slots(k)
             for w in slot] + ["दरोडा", "चोरी", "पोलीस", "गाडी", "पाठलाग", "नजर", WITHHELD, "मुंबई"]
    for _ in range(300):
        title = " ".join(rng.choice(vocab) for _ in range(rng.randint(2, 10)))
        source = rng.choice(["news_rss", "google_news_rss", "reddit_rss", "sachet_cap"])
        publisher = {"news_rss": "news-mr-a.example", "google_news_rss": "news-a.example",
                     "reddit_rss": "social-a.example/r/example_city", "sachet_cap": "sachet.ndma.gov.in"}[source]
        got = C.classify(make_signal(source, title=title, publisher=publisher))
        assert got.sajag_event_kind not in ("crime_incident", "vehicle_pursuit"), title
        assert got.event_class in kinds.EVENT_CLASS_NAMES


def test_every_guard_belongs_to_a_keyword_it_guards():
    keywords = {k for row in C.CLASS_LEXICON for k in row.keywords} | set(C.CAP_FLOOD_TERMS)
    assert set(C.CONTEXT_RULES) <= keywords  # a renamed keyword never silently loses its guard
    for event_class, keyword in C.CLASS_CONTEXT_RULES:
        assert keyword in C.default_row(event_class).keywords or any(
            row.event_class == event_class and keyword in row.keywords for row in C.CLASS_LEXICON
        )
