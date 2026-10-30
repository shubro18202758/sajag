"""The stoplist guard (the PoC's "India" ↔ "indira" fix, which Mumbai needs as much: "Gateway of India" and the
"Times of India flyover" on the Western Express Highway): India never matches another place, short tokens never
fuzzy-match, fuzzy matching runs on multi-word names only, and a gated form is never read fuzzily."""

from __future__ import annotations

import difflib

import pytest

from osint_geo.gazetteer import GENERIC_STOPWORDS
from osint_geo.resolver import FUZZY_STOP, GazetteerResolver

from _synthetic import make_signal


@pytest.fixture(scope="module")
def resolver() -> GazetteerResolver:
    return GazetteerResolver()


def test_the_trap_is_real():
    # why the guard exists: difflib alone would take "india" for "indira"
    assert difflib.SequenceMatcher(None, "india", "indira").ratio() > 0.9


@pytest.mark.parametrize(
    "title",
    [
        "India records its wettest October",
        "INDIA: monsoon withdraws late",
        "India's cities brace for heavy rain",
        "Indian Express: markets steady",
        "Times of India reports a quiet weekend",
        "India Today: traffic advisory for the festival",
        "Team India arrives for the series",
        "India Gandhi statue unveiled abroad",
    ],
)
def test_india_never_matches_indira(resolver, title):
    g = resolver.resolve(make_signal(title, f"{title}. Nothing else happened."))
    assert g is None or "indira" not in (g.toponym or "").lower()
    assert g is None


def test_india_never_matches_indira_in_any_window(resolver):
    # "india" is a fuzzy stop word: a window holding it is never read fuzzily, so "Times of India flyovr" (a
    # newspaper name and a typo) is no mention, although "times of india flyover" is a form of the Western Express
    # Highway at ratio 0.98
    text = "India gandhi road India times of india flyovr India indira gandhi road"
    mentions = resolver.mentions(text)
    assert all("indira" not in m.form and "times of india" not in m.form for m in mentions)
    assert resolver._fuzzy_mentions(resolver.tokens("Times of India flyovr jam")) == []
    assert resolver.gazetteer.fuzzy("times of india flyovr") == ("times of india flyover",
                                                                 pytest.approx(0.977, abs=0.001))


def test_the_real_india_place_still_resolves(resolver):
    g = resolver.resolve(make_signal("Gateway of India closed for the visit",
                                     "Gateway of India closed for the visit this evening."))
    assert g is not None and g.toponym == "Gateway of India" and g.method == "gazetteer_exact"
    assert g.feature_type == "landmark"


def test_no_bare_given_name_or_common_word_alias(resolver):
    gaz = resolver.gazetteer
    for word in ("india", "gandhi", "nehru", "shivaji", "ambedkar", "tilak", "gokhale", "vivekanand", "patel",
                 "netaji", "subhash", "jijamata", "mahatma", "hinduja", "lilavati", "jaslok", "nanavati",
                 "kokilaben", "wadia", "tata", "atre", "acharya", "senapati", "bapat", "annie", "besant", "rajiv",
                 "science", "airport", "medical", "college", "central", "mumbai", "bombay", "maharashtra", "street",
                 "naka", "chowk", "setu", "marg", "subway", "chowpatty", "times"):
        assert gaz.lookup(word) == (), word


@pytest.mark.parametrize("typo", ["Andheir", "Matnga", "Byclla", "Chembr", "Borvali", "Malaad", "Dadarr", "Mahm"])
def test_short_or_single_tokens_never_fuzzy_match(resolver, typo):
    g = resolver.resolve(make_signal(f"Traffic jam in {typo}", f"Traffic jam in {typo} this evening."))
    assert g is None, (typo, g)


def test_multi_word_names_fuzzy_match(resolver):
    s = make_signal("Accident near Wankhede Stadum", "An accident near Wankhede Stadum this evening.")
    g = resolver.resolve(s)
    assert g is not None and g.toponym == "Wankhede Stadium" and g.method == "gazetteer_fuzzy"
    assert g.segment_id == 1002  # Marine Drive, 176 m (test_snap)
    ex = resolver.explain(s)
    assert ex["mentions"] and all(0.9 <= m["score"] < 1.0 for m in ex["mentions"])
    # a fuzzy match is never as sure as the exact alias
    exact = resolver.resolve(make_signal("Accident near Wankhede Stadium", "An accident near Wankhede Stadium."))
    assert exact is not None and exact.confidence > g.confidence


def test_fuzzy_reads_a_misspelt_junction_with_a_rewritten_place_word(resolver):
    # "kalanagr chowk" → "kalanagr junction" (the place word rewritten) → "kalanagar junction" (fuzzy)
    g = resolver.resolve(make_signal("Signal down at Kalanagr chowk", "Signal down at Kalanagr chowk."))
    assert g is not None and g.junction_id == 37 and g.method == "gazetteer_fuzzy"


def test_fuzzy_needs_two_words_and_eight_characters(resolver):
    gaz = resolver.gazetteer
    assert gaz.fuzzy("andheir") is None  # single word: the pool holds multi-word forms only
    assert gaz.fuzzy("dh rd") is None  # too short to be a fuzzy candidate pool form at ratio 0.9
    assert gaz.fuzzy("wankhede stadum") == ("wankhede stadium", pytest.approx(0.968, abs=0.001))


def test_a_function_word_at_the_window_edge_is_never_read_as_part_of_a_name(resolver):
    # "gandhi markt in" is at ratio 0.91 of "gandhi market sion" ("in" read as "sion"): the edge word must be a word
    # of the form
    gaz = resolver.gazetteer
    assert gaz.fuzzy("gandhi markt in") is None
    assert gaz.fuzzy("gandhi markt") == ("gandhi market", pytest.approx(0.96, abs=0.001))
    assert gaz.fuzzy("gateway of indai") == ("gateway of india", pytest.approx(0.9375, abs=0.001))


def test_windows_with_a_stop_word_or_only_generic_words_are_skipped(resolver):
    for text in (
        "Maharashtra univrsity campus news",  # "maharashtra" and "news" are fuzzy stop words
        "Mumbai Airprt T2",  # "mumbai" is a stop word, although "mumbai airport t2" (a form) is at ratio 0.97
        "the road near the crossing and the bridge",
        "cross road near the station junction naka",
    ):
        assert resolver._fuzzy_mentions(resolver.tokens(text)) == [], text
    assert resolver.gazetteer.fuzzy("mumbai airprt t2") == ("mumbai airport t2", pytest.approx(0.970, abs=0.001))
    assert {"india", "indian", "maharashtra", "mumbai", "bombay", "news"} <= FUZZY_STOP
    assert {"road", "crossing", "chowk", "naka", "setu", "marg", "bridge", "near"} <= GENERIC_STOPWORDS


def test_exact_matches_win_over_fuzzy(resolver):
    # with an exact place present the fuzzy stage never runs, so a near-miss elsewhere in the text adds nothing
    mentions = resolver.mentions("Fire at Lalbaug; smoke seen from Wankhede Stadum")
    assert [m.form for m in mentions] == ["lalbaug"] and mentions[0].method == "gazetteer_exact"


def test_a_misspelt_place_is_never_surer_than_the_same_place_spelt_right(resolver):
    for typo, right in (
        ("Wankhede Stadum crash. Seen near Wankhede Stadum.", "Wankhede Stadium crash. Seen near Wankhede Stadium."),
        ("Accident near Wankhede Stadum", "Accident near Wankhede Stadium"),
        ("Signal down at Kalanagr chowk", "Signal down at Kalanagar chowk"),
        ("Crowd at Siddhivinayak Templ", "Crowd at Siddhivinayak Temple"),
    ):
        g_typo, g_right = resolver.resolve(make_signal(typo, typo)), resolver.resolve(make_signal(right, right))
        assert g_typo is not None and g_right is not None and g_typo.toponym == g_right.toponym
        assert g_typo.method == "gazetteer_fuzzy" and g_typo.confidence <= g_right.confidence, (typo, g_typo, g_right)


def test_cue_bound_names_are_the_first_fuzzy_candidates(resolver):
    text = "Jam near Wankhede Stadum; diversion opp. Siddhivinayak Templ and near Wankhede Stadum"
    names = resolver._grammar_names(text)
    assert [n for n, _ in names] == [("wankhede", "stadum"), ("siddhivinayak", "templ")]
    mentions = resolver.mentions(text)
    assert [m.form for m in mentions] == ["wankhede stadium", "siddhivinayak temple", "wankhede stadium"]
    assert all(m.method == "gazetteer_fuzzy" for m in mentions)


@pytest.mark.parametrize(
    ("elsewhere", "here", "toponym"),
    [
        # "gandhi markt in" was "Gandhi Market (Sion)" at ratio 0.91 before the edge-word rule
        ("Fire at Gandhi Markt in Bhopal", "Fire at Gandhi Markt, Mumbai", "Gandhi Market (Sion)"),
        ("Fire at Kasturba Hospitl in Delhi", "Fire at Kasturba Hospitl, Mumbai", "Kasturba Hospital (Chinchpokli)"),
    ],
)
def test_a_gated_form_is_never_read_fuzzily(resolver, elsewhere, here, toponym):
    # with the context gate closed a gated form ("medical college hospital") is no mention, and a window that IS
    # that form never fuzzy-matches a longer form that carries a place the text does not name
    s = make_signal(elsewhere, f"{elsewhere}. Details are awaited.")
    assert resolver.resolve(s) is None
    assert resolver.explain(s)["mentions"] == []
    # in a text about the city the same words are the Mumbai place
    g = resolver.resolve(make_signal(here, f"{here}. Details are awaited."))
    assert g is not None and g.toponym == toponym, (here, g)
