"""classify(), English: the lexicon in order (first match wins), the SACHET rule, general_news, the zero-shot
fallback, and the invariant that no input ever yields crime_incident (nor vehicle_pursuit). The Marathi and Hindi
rules are tested in ``test_classify_marathi.py``."""

from __future__ import annotations

import random
import re

import numpy as np
import pytest

from analysis_fixtures import make_signal
from osint_common import kinds, testing
from osint_common.types import Classification
from osint_analysis import classify as C


def _news(title: str, text: str | None = None):
    return make_signal("google_news_rss", title=title, text=text)


def _reference_hit(keyword: str, hay: str) -> bool:
    """An independent reading of the English word rule: a stem starts a word; any other keyword is a whole word,
    itself or with one of the regular endings (a noun: a plural only). Indic keywords are never read here (the
    titles of this file are English)."""
    if C.is_indic(keyword):
        return False
    k = keyword.lower()
    if keyword in C.STEM_KEYWORDS:
        return any(
            not any(hay[m.end():].startswith(x) for x in C.STEM_KEYWORDS[keyword])
            for m in re.finditer(r"(?<!\w)" + re.escape(k), hay)
        )
    endings = ["", "s", "es"] if keyword in C.NOUN_KEYWORDS else ["", "s", "es", "ed", "d", "ing"]
    if k[-1].isalpha() and k[-1] == "y" and k[-2] not in "aeiou":
        endings += ["ies"] if keyword in C.NOUN_KEYWORDS else ["ies", "ied"]
    if keyword not in C.NOUN_KEYWORDS and re.search(r"(?:^|[^aeiou\W])[aeiou][b-df-hj-np-tv-z]$", k.split()[-1]):
        endings += [k[-1] + "ed", k[-1] + "ing"]
    for e in endings:
        stem = k[:-1] if e in ("ies", "ied") else k
        if not k[-1].isalpha() and e:
            continue
        if re.search(r"(?<!\w)" + re.escape(stem + e) + r"(?!\w)", hay):
            return True
    for derived in C.DERIVED_FORMS.get(keyword, ()):
        if re.search(r"(?<!\w)" + re.escape(derived) + r"(?:s|es)?(?!\w)", hay):
            return True
    return False


def _reference_class(text: str) -> str:
    """An independent reading of "first row wins, a keyword is a whole word (or a stem)" over the raw lexicon (the
    titles here never meet a context rule)."""
    hay = " ".join(text.lower().split())
    for row in C.CLASS_LEXICON:
        if any(_reference_hit(k, hay) for k in row.keywords):
            return row.event_class
    return "general_news"


@pytest.mark.parametrize(
    ("title", "event_class", "subtype", "kind", "incident"),
    [
        ("Jewellery shop robbed at gunpoint near Dadar TT Circle", "reported_crime", "daylight_robbery",
         "reported_crime", "robbery"),
        ("Road rage on Marine Drive leaves commuter shaken", "reported_crime", "road_rage", "reported_crime",
         "road_rage"),
        ("Stone pelting near Kurla after a dispute; police deployed", "public_conflict", "affray",
         "public_disorder", "public_disorder"),
        ("Multi-vehicle crash on the Western Express Highway near Andheri", "road_accident", "collision",
         "road_accident", "accident"),
        ("Massive fire in a godown near Kurla", "fire", "structure_fire", "hazard", "other"),
        ("Knee-deep water after a downpour at Hindmata", "urban_flooding", "waterlogging", "flooding",
         "weather"),
        ("Wall collapse on Bidhan Sarani blocks one lane", "infra_failure", "collapse", "infra_failure",
         "route_blockage"),
        ("Chemical spill reported at an industrial estate", "hazard", "spill", "hazard", "other"),
        ("Huge crowd at Prinsep Ghat for the river festival", "public_gathering", "mass_gathering",
         "mass_gathering", "crowd_surge"),
        ("Rath Yatra route announced for Juhu", "procession", "procession", "procession", "other"),
        ("Traders observe bandh in Burrabazar", "unrest", "protest", "public_disorder", "protest"),
        ("Road closed for metro work near Ghatkopar", "road_closure", "closure", "work_zone",
         "route_blockage"),
        ("Thunderstorm and lightning lash the western suburbs", "weather_hazard", "storm", "hazard", "weather"),
        # the two hazard rows the proof-of-concept had no row for, and a parade
        ("Uprooted trees block Rash Behari Avenue", "hazard", "fallen_tree", "hazard", "route_blockage"),
        ("Tree fell on a taxi near Deshapriya Park", "hazard", "fallen_tree", "hazard", "route_blockage"),
        ("Live wire snaps on Amherst Street; two electrocuted", "hazard", "live_wire", "hazard", "other"),
        ("Republic Day parade rehearsal on Red Road", "procession", "procession", "procession", "other"),
    ],
)
def test_lexicon_cases(title, event_class, subtype, kind, incident):
    got = C.classify(_news(title))
    assert (got.event_class, got.subtype, got.sajag_event_kind, got.sajag_incident_kind) == (
        event_class,
        subtype,
        kind,
        incident,
    )
    assert got.matched_terms, "the matched cue words are recorded"


def test_first_matching_row_wins_and_records_every_hit_of_that_row():
    # "mob" (public_conflict) precedes "crash" (road_accident) in the lexicon
    got = C.classify(_news("Driver beaten by mob after Western Express Highway crash near Andheri"))
    assert got.event_class == "public_conflict"
    assert set(got.matched_terms) == {"mob", "beaten by mob"}
    # "gas leak" is both an infra_failure and a hazard cue: the earlier row (infra_failure) wins
    assert C.classify(_news("Gas leak at a pipeline near Chembur")).event_class == "infra_failure"


def test_keywords_match_whole_words_never_inside_a_word():
    assert C.classify(_news("Automobile showroom opens on the WEH")).event_class == "general_news"  # not "mob"
    assert C.classify(_news("Markets generally calm on Sunday")).event_class == "general_news"  # not "rally"
    assert C.classify(_news("An affair of the heart, said the film's makers")).event_class == "general_news"
    assert C.classify(_news("Mobs gather near the circle")).event_class == "public_conflict"
    assert C.classify(_news("Waterlogging reported at underpass")).event_class == "urban_flooding"  # a stem
    assert C.classify(_news("Chain-snatching cases rise in the east")).event_class == "reported_crime"


@pytest.mark.parametrize(
    "title",
    [
        "KMC launches mobile app for property tax at Kasba",  # "mob"
        "Mobility plan for the Western Express Highway",  # "mob"
        "Striker scores twice as the city club wins",  # "strike"
        "Fairly good monsoon expected this year",  # "fair"
        "Melange of colours at the art gallery",  # "mela"
        "Toxicology lab opens at the civil hospital campus",  # "toxic"
        "Concerted efforts to clean the lake",  # "concert" (a noun: never "concerted")
        "Stadium floodlights fail during the match",  # the "flood" stem's exclusion
        "Metro to open by March",  # the month, not a march
        "Admissions open from March 15 at the college",  # the month
        "Lightning strike damages a transformer",  # weather_hazard below, never a labour strike
    ],
)
def test_a_word_that_merely_starts_with_a_cue_is_not_an_event_of_that_class(title):
    got = C.classify(_news(title))
    assert got.event_class not in ("public_conflict", "unrest", "public_gathering", "hazard", "urban_flooding",
                                   "procession"), (title, got.event_class)


def test_the_false_public_conflict_at_kasba_is_never_surfaced():
    from analysis_fixtures import KASBA, FakeResolver, point
    from osint_analysis.pipeline import HELD_NOT_EVENT, run_pipeline

    sig = _news("KMC launches mobile app for property tax at Kasba")
    assert C.classify(sig).event_class == "general_news"
    geo = point(sig, KASBA, toponym="Kasba", feature_type="neighbourhood")
    (held,) = run_pipeline([sig], resolver=FakeResolver([geo])).resolved
    assert not held.is_event and held.held_reason == HELD_NOT_EVENT
    assert not held.label.startswith("Public conflict")


@pytest.mark.parametrize(
    ("title", "event_class"),
    [
        ("Driver mobbed after the crash", "public_conflict"),  # a doubled final consonant
        ("Clashes near the old market gate", "public_conflict"),
        ("Two cars crashed near the circle", "road_accident"),
        ("Accidents rise on the ring road", "road_accident"),
        ("Shop looted in Burrabazar", "reported_crime"),
        ("Spate of robberies in the east zone", "reported_crime"),  # y -> ies
        ("Supporters rallied at the ground", "public_gathering"),  # y -> ied
        ("Concerts at Prinsep Ghat this weekend", "public_gathering"),  # a noun's plural
        ("Toxic fumes from a drain", "hazard"),
        ("Waterlogged roads after the downpour", "urban_flooding"),  # stems
        ("Inundation in low-lying areas", "urban_flooding"),
        ("Underpass flooded after heavy rainfall", "urban_flooding"),
        ("Students march from Dadar to Shivaji Park", "procession"),  # a march, not the month
        ("Students marched to Azad Maidan", "procession"),
        ("Transporters strike in the city", "unrest"),
        ("Hunger strike at Azad Maidan", "unrest"),
        ("Lightning strike damages a transformer", "weather_hazard"),
        ("Lightning strikes two trees near Powai", "weather_hazard"),
    ],
)
def test_regular_inflections_stems_and_context(title, event_class):
    assert C.classify(_news(title)).event_class == event_class, title


@pytest.mark.parametrize(
    ("title", "event_class"),
    [
        # the agent nouns the PoC's substring test caught (review round 2): never general_news, never unrest
        ("Protesters block the Eastern Express Highway near Sion", "unrest"),
        ("Protestors detained near Azad Maidan", "unrest"),
        ("Looters target jewellery shop in Kurla", "reported_crime"),
        ("Looters ransack shops after clash", "reported_crime"),  # the robbery row comes before the clash row
        ("Chain snatchers strike again in Borivali", "reported_crime"),  # never unrest through "strike"
        ("Snatchers flee on a bike near the bus stand", "reported_crime"),
        ("Brawlers detained after a fight at the mall", "public_conflict"),
        ("Marchers reach Marine Drive", "procession"),
        ("Rallyists gather at Azad Maidan", "public_gathering"),
        # derived nouns: one class whichever way a leak or a spill is written
        ("Gas leakage at a factory in Chembur", "infra_failure"),  # as "gas leak": the PoC's first match
        ("Oil spillage on the ring road", "hazard"),
        ("Processional route announced for Sunday", "procession"),
    ],
)
def test_agent_nouns_and_derived_forms_the_poc_caught(title, event_class):
    got = C.classify(_news(title))
    assert got.event_class == event_class, (title, got.event_class, got.matched_terms)
    assert got.event_class == _reference_class(title)


@pytest.mark.parametrize(
    ("title", "event_class"),
    [
        # where the PoC's substring test was wrong, the whole-word rule stays right
        ("Accidental fire at a godown in Kurla", "fire"),  # not a road accident
        ("Protestant church marks its centenary", "general_news"),
        ("Strikers score twice as the city club wins", "general_news"),  # a labour strike needs "strike"
        ("Blazer-clad students at the convocation", "general_news"),
        ("Metro workers colony gets a new park", "general_news"),  # not a "metro work" zone
        ("Mobsters film shoot at the old fort", "general_news"),
    ],
)
def test_derived_forms_never_bring_back_a_substring_false_positive(title, event_class):
    assert C.classify(_news(title)).event_class == event_class, title


def test_keyword_forms_include_the_derived_forms_with_their_plurals():
    assert {"protester", "protesters", "protestor", "protestors"} <= set(C.keyword_forms("protest"))
    assert {"looter", "looters"} <= set(C.keyword_forms("loot"))
    assert {"chain snatcher", "chain snatchers"} <= set(C.keyword_forms("chain snatch"))
    assert "gas leakage" in C.keyword_forms("gas leak")
    assert "protestant" not in C.keyword_forms("protest")
    assert not any(f.startswith("striker") for f in C.keyword_forms("strike"))
    for keyword in C.DERIVED_FORMS:  # every entry belongs to a lexicon keyword
        assert any(keyword in row.keywords for row in C.CLASS_LEXICON), keyword


def test_keyword_forms_are_whole_words():
    assert set(C.keyword_forms("mob")) >= {"mob", "mobs", "mobbed", "mobbing"}
    assert "mobile" not in C.keyword_forms("mob")
    assert set(C.keyword_forms("concert")) == {"concert", "concerts", "concertes"}
    assert {"robberies"} <= set(C.keyword_forms("robbery"))
    assert C.keyword_forms("hits 3") == ("hits 3",)  # a number matches only itself
    assert C.keyword_matches("hits 3", "car hits 3 vehicles") and not C.keyword_matches("hits 3", "car hits 30 bikes")
    assert C.keyword_matches("flood", "flooded underpass") and not C.keyword_matches("flood", "floodlit ground")
    assert C.keyword_matches("march", "the march reached dadar") and not C.keyword_matches("march", "in march")


def test_text_is_normalised_before_matching():
    # fullwidth letters, a zero-width space inside the phrase, odd whitespace: still "heavy rain"
    got = C.classify(_news("Ｈｅａｖｙ​ rain\n\tin the east zone"))
    assert got.event_class == "urban_flooding"


def test_general_news_when_nothing_matches():
    got = C.classify(_news("City library extends its evening hours"))
    assert got == Classification(event_class="general_news")
    assert got.sajag_event_kind is None and got.sajag_incident_kind is None and got.subtype is None


def test_sachet_rule_flood_words_make_a_flood_situation():
    for words in ("Heavy rain", "Very heavy rainfall", "Flood warning", "Waterlogging likely", "Inundation risk"):
        sig = make_signal("sachet_cap", title=f"{words} for Mumbai district", publisher="sachet.ndma.gov.in")
        got = C.classify(sig)
        assert (got.event_class, got.subtype, got.sajag_event_kind, got.sajag_incident_kind) == (
            "urban_flooding",
            "waterlogging",
            "flooding",
            "weather",
        ), words
        assert got.matched_terms == ["CAP:flood"]


def test_sachet_rule_otherwise_an_honest_weather_hazard():
    got = C.classify(testing.sachet_district_signal())  # cap_event "Thunderstorm"
    assert (got.event_class, got.subtype, got.sajag_event_kind) == ("weather_hazard", "thunderstorm", "hazard")
    assert got.matched_terms == ["CAP:weather"]
    # the CAP rule decides even when the lexicon would say something else: an alert is not a report of a fire
    alert = make_signal(
        "sachet_cap", title="Light rain likely; fire danger low in the forest belt", publisher="sachet.ndma.gov.in"
    )
    assert C.classify(alert).event_class == "weather_hazard"
    assert C.classify(testing.sachet_state_signal()).event_class == "weather_hazard"


def test_rows_stay_inside_the_vocabularies():
    for row in C.CLASS_LEXICON:
        assert row.event_class in kinds.EVENT_CLASS_NAMES
        assert row.sajag_event_kind in kinds.OSINT_EVENT_KINDS
        assert row.sajag_incident_kind in kinds.INCIDENT_KINDS  # traffic.incidents as relaxed by 021
        assert row.sajag_event_kind not in C.FORBIDDEN_OSINT_KINDS
    assert set(C.ZERO_SHOT_EXEMPLARS) == kinds.EVENT_CLASSES  # one exemplar per event class, none for news
    for cls in C.ZERO_SHOT_EXEMPLARS:
        assert C.default_row(cls) is not None


@pytest.mark.parametrize("row_index", range(len(C.CLASS_LEXICON)))
def test_every_lexicon_keyword_classifies_as_the_first_row_it_matches_and_never_crime_incident(row_index):
    row = C.CLASS_LEXICON[row_index]
    for keyword in (k for k in row.keywords if not C.is_indic(k)):
        title = f"Report: {keyword} near the market this evening"
        got = C.classify(_news(title))
        assert got.event_class == _reference_class(title), keyword
        assert got.sajag_event_kind not in C.FORBIDDEN_OSINT_KINDS
        assert got.sajag_event_kind != "crime_incident"


def test_fuzz_200_random_titles_never_yield_crime_incident():
    rng = random.Random(20261024)
    vocab = [k for row in C.CLASS_LEXICON for k in row.keywords] + [
        "crime", "incident", "crime incident", "stolen", "vehicle", "pursuit", "chase", "suspect vehicle",
        "watchlist", "anpr", "camera", "theft", "murder", "assault", "police", "near", "hindmata", "kurla",
        "highway", "junction", "market", "reported", "on", "the", "at", "evening", "after", "two", "injured",
    ]
    for _ in range(200):
        title = " ".join(rng.choice(vocab) for _ in range(rng.randint(3, 12)))
        source = rng.choice(["google_news_rss", "gdelt_doc", "reddit_rss", "sachet_cap"])
        publisher = {
            "google_news_rss": "news-a.example",
            "gdelt_doc": "news-b.example",
            "reddit_rss": "social-a.example/r/example_city",
            "sachet_cap": "sachet.ndma.gov.in",
        }[source]
        got = C.classify(make_signal(source, title=title, publisher=publisher))
        assert got.sajag_event_kind != "crime_incident", title
        assert got.sajag_event_kind != "vehicle_pursuit", title
        assert got.event_class in kinds.EVENT_CLASS_NAMES


def test_the_final_check_raises_if_a_row_ever_maps_to_crime_incident(monkeypatch):
    tampered = C.LexiconRow("reported_crime", "theft", "crime_incident", "other", ("stolen",))
    monkeypatch.setattr(C, "_COMPILED", ((tampered, (("stolen", re.compile("stolen")),)),))
    with pytest.raises(ValueError, match="never emit crime_incident"):
        C.classify(_news("Car stolen from a parking lot"))
    with pytest.raises(ValueError, match="never emit vehicle_pursuit"):
        C._final_check("vehicle_pursuit")


class _VecEmbedder:
    """A deterministic fake embedder: one axis per class; a text near a class's exemplar gets that axis."""

    def __init__(self, picks: dict[str, int], noise: float = 0.0) -> None:
        self.picks = picks
        self.noise = noise
        self.calls = 0

    def embed(self, texts):
        self.calls += 1
        dim = len(C.ZERO_SHOT_EXEMPLARS) + 1
        out = []
        exemplars = list(C.ZERO_SHOT_EXEMPLARS.values())
        for t in texts:
            v = np.full(dim, self.noise)
            if t in exemplars:
                v[exemplars.index(t)] = 1.0
            else:
                axis = next((a for key, a in self.picks.items() if key in t), dim - 1)
                v[axis] = 1.0
            out.append(v.tolist())
        return out


def test_zero_shot_fallback_classifies_a_lexicon_miss_from_a_news_tier():
    flood_axis = list(C.ZERO_SHOT_EXEMPLARS).index("urban_flooding")
    emb = _VecEmbedder({"underpass": flood_axis})
    got = C.classify(_news("Underpass under water near the station"), embedder=emb)
    assert got.event_class == "urban_flooding" and got.matched_terms == [C.ZERO_SHOT_TERM]
    assert got.sajag_event_kind == "flooding"


def test_zero_shot_never_classifies_a_social_post_and_never_overrides_the_lexicon():
    flood_axis = list(C.ZERO_SHOT_EXEMPLARS).index("urban_flooding")
    emb = _VecEmbedder({"underpass": flood_axis})
    post = make_signal("reddit_rss", title="Underpass under water near the station",
                       publisher="social-a.example/r/example_city")
    assert C.classify(post, embedder=emb).event_class == "general_news"
    hit = C.classify(_news("Multi-vehicle crash at the underpass"), embedder=emb)
    assert hit.event_class == "road_accident" and hit.matched_terms != [C.ZERO_SHOT_TERM]


def test_zero_shot_needs_a_close_and_clear_nearest_class():
    # every class equally near: no clear winner, stays general_news
    flat = _VecEmbedder({}, noise=1.0)
    assert C.classify(_news("Underpass under water near the station"), embedder=flat).event_class == "general_news"


@pytest.mark.parametrize("bad", [None, "raise", "short", "nan"])
def test_zero_shot_falls_back_to_the_lexicon_when_the_embedder_fails(bad):
    class Bad:
        def embed(self, texts):
            if bad == "raise":
                raise RuntimeError("down")
            if bad == "short":
                return [[1.0, 0.0]]
            if bad == "nan":
                return [[float("nan"), 1.0] for _ in texts]
            return None

    got = C.classify(_news("Underpass under water near the station"), embedder=Bad())
    assert got == Classification(event_class="general_news")


# ── F-HONEST OSINT-7: a CAP alert's subtype is its own event, never "storm" for all ─────────────────────────────


@pytest.mark.parametrize(
    ("title", "cap_event", "subtype"),
    [
        # the audit's surfaced OFFICIAL-VERIFIED alert, a light-rain nowcast labelled "storm"
        ("Light Rain is very likely to occur at isolated places over Mumbai, Thane in next 3 hours.", None,
         "rain"),
        ("Light Rain with light thunderstorms and lightning is very likely over Mumbai", None, "thunderstorm"),
        ("Heat wave conditions very likely over Mumbai", None, "heat"),
        ("Dense fog very likely over Mumbai in the early morning", None, "fog"),
        ("Alert for Mumbai district", "Thunderstorm & Lightning, Squall etc", "thunderstorm"),
        ("Alert for Mumbai district", "Heat Wave", "heat"),
        ("Alert for Mumbai district", None, "weather_advisory"),
    ],
)
def test_cap_subtype_names_the_alerts_own_event(title, cap_event, subtype):
    raw = {"cap_identifier": "synthetic.cap.1", **({"cap_event": cap_event} if cap_event else {})}
    alert = make_signal("sachet_cap", title=title, publisher="sachet.ndma.gov.in")
    alert = alert.model_copy(update={"raw": raw})
    got = C.classify(alert)
    assert (got.event_class, got.subtype) == ("weather_hazard", subtype)
