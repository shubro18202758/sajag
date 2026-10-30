"""The regex place grammar: relational, feature and PIN spans, clause boundaries, and the rewrite hits (Mumbai's
place words: "chowk"/"naka" for a junction, "setu" for a bridge, "rd", "under pass", "स्थानक" for a station)."""

from __future__ import annotations

from osint_geo.gazetteer import load
from osint_geo.grammar import PIN_RE, SYNONYMS, feature_hits, find_spans, lookup_keys, pin_codes
from osint_geo.resolver import SENTENCE_BREAK


def _spans(text: str, kind: str):
    return [s for s in find_spans(text) if s.kind == kind]


def test_relational_spans():
    rel = _spans("Accident near Hinduja Hospital on Tuesday; jam opp. Gandhi Market", "relational")
    assert [s.head for s in rel] == ["hinduja hospital", "gandhi market"]
    assert rel[0].surface == "Hinduja Hospital" and rel[0].keys == ("hinduja hospital",)


def test_a_relational_span_never_crosses_a_clause():
    rel = _spans("Seen near Hindmata - The Daily Example", "relational")
    assert [s.head for s in rel] == ["hindmata"]
    rel = _spans("He was near. Parel was quiet", "relational")
    assert rel == []


def test_abbreviations_keep_the_clause():
    # the initials' full stops keep the clause (a relational name is four words at most)
    rel = _spans("Crash near S.V. Road flyover", "relational")
    assert rel and rel[0].head == "s v road"
    rel = _spans("Jam near Dr. Ambedkar Road", "relational")
    assert rel and rel[0].head == "dr ambedkar road"


def test_feature_spans_carry_every_rewrite():
    feat = _spans("Car fire near Hindmata chowk", "feature")
    assert len(feat) == 1
    span = feat[0]
    assert span.head == "hindmata" and span.feature == "chowk"
    assert "hindmata junction" in span.keys and "hindmata chowk" in span.keys
    feat = _spans("Shops shut at Gokhale setu and on LBS Rd.", "feature")
    keys = [k for s in feat for k in s.keys]
    assert "gokhale bridge" in keys and "lbs road" in keys
    feat = _spans("Complaint lodged at Dadar ps", "feature")
    assert feat and "dadar police station" in feat[0].keys


def test_mumbai_place_words_are_synonyms():
    for word, generic in (("chowk", "junction"), ("naka", "junction"), ("setu", "bridge"), ("rd", "road"),
                          ("marg", "road"), ("under pass", "underpass"), ("underpass", "subway"), ("st", "street"),
                          ("thana", "police station"), ("ps", "police station"), ("चौक", "chowk"), ("पूल", "bridge"),
                          ("स्थानक", "station"), ("पोलीस ठाणे", "police station"), ("थाना", "police station"),
                          ("सबवे", "subway")):
        assert generic in SYNONYMS[tuple(word.split(" "))], word


def test_feature_heads_stop_at_cue_words():
    feat = _spans("traffic near worli naka", "feature")
    assert feat and all("near" not in k for k in feat[0].keys)


def test_marathi_and_hindi_feature_spans_are_transliterated():
    feat = _spans("सायन सर्कल पर जाम", "feature")
    assert feat and "sion circle" in feat[0].keys and "सायन सर्कल" in feat[0].keys
    feat = _spans("दादर स्थानक परिसरात गर्दी", "feature")
    assert feat and "dadar station" in feat[0].keys


def test_lookup_keys():
    assert lookup_keys("Hindmata", "chowk") == ("hindmata chowk", "hindmata junction")
    assert lookup_keys("Andheri", "under pass") == ("andheri under pass", "andheri underpass")
    assert lookup_keys("Gokhale", "setu") == ("gokhale setu", "gokhale bridge")
    assert lookup_keys("दादर", "स्थानक") == ("दादर स्थानक", "दादर station", "dadar स्थानक", "dadar station")
    assert lookup_keys("", "crossing") == ()


def test_pin_codes():
    assert pin_codes("Water main burst, Parel 400012. Call 1800-400012-99") == ["400012"]
    assert pin_codes("Mumbai-400014, or Mumbai 400 053") == ["400014", "400053"]
    assert pin_codes("ref 4000199 or 14000 19 or 400209") == []
    assert PIN_RE.fullmatch("400104") is not None and PIN_RE.fullmatch("400001") is not None
    # a Navi Mumbai / Thane PIN (4006xx, 4007xx), past the range (400105) or another city's PIN is not a Mumbai PIN
    assert PIN_RE.fullmatch("400703") is None and PIN_RE.fullmatch("400601") is None
    assert PIN_RE.fullmatch("400105") is None and PIN_RE.fullmatch("700019") is None
    pins = _spans("near the school, 400007.", "pin")
    assert [p.head for p in pins] == ["400007"]


def test_feature_hits_rewrite_against_the_index():
    gaz = load()
    toks = gaz.tokens("jam at senapati bapat rd and gokhale setu")
    hits = feature_hits(toks, gaz)
    assert {h.form for h in hits} == {"senapati bapat road", "gokhale bridge"}
    assert all(h.via == "grammar" for h in hits)
    gokhale = next(h for h in hits if h.form == "gokhale bridge")
    assert toks[gokhale.start : gokhale.end] == ["gokhale", "setu"]


def test_feature_hits_read_marathi_case_endings():
    gaz = load()
    # "दादर स्थानकाजवळ" (near Dadar station): the scanner reads the stem "स्थानक", the rewrite the station's Latin form
    toks = gaz.tokens("दादर स्थानकाजवळ गर्दी")
    assert toks[:2] == ["दादर", "स्थानक"]
    assert [h.form for h in feature_hits(toks, gaz)] == ["dadar station"]


def test_feature_hits_never_cross_a_sentence_break():
    # the resolver puts SENTENCE_BREAK between sentences; a head transliterated across it ("दादर ." → "dadar") would
    # make "आग लागली दादरला। स्थानकाजवळ ..." the station
    gaz = load()
    toks = [*gaz.tokens("आग लागली दादर"), SENTENCE_BREAK, *gaz.tokens("स्थानकाजवळ गर्दी")]
    assert feature_hits(toks, gaz) == []
    toks = [*gaz.tokens("fire at gokhale"), SENTENCE_BREAK, *gaz.tokens("setu traffic slow")]
    assert feature_hits(toks, gaz) == []


def test_feature_hits_need_a_real_form():
    gaz = load()
    assert feature_hits(gaz.tokens("the old gate"), gaz) == []
    assert feature_hits(gaz.tokens("unknown place more"), gaz) == []


def test_no_spans_in_plain_text():
    assert find_spans("") == [] and find_spans("nothing here at all") == []
