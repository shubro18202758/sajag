"""The X19 gazetteer of Mumbai: format, places only (no field outside the list), the ODbL notice, the City Pack
(ids, order, spellings), the protect-set, the normaliser (Marathi and Devanagari), the longest-match index with
Marathi case endings, the path rules, and the generator (deterministic, --check, lint)."""

from __future__ import annotations

import copy
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from osint_common import ethics
from osint_geo import gazetteer as gz
from osint_geo import translit
from osint_geo.gazetteer import ENTRY_FIELDS, LICENCE, META_FIELDS, Gazetteer, load, norm

REPO = Path(__file__).resolve().parents[3]
GAZ_JSON = REPO / "scripts" / "data" / "osint_gazetteer.json"
NETWORK_JSON = REPO / "scripts" / "data" / "osm_network.json"
PACK_JSON = REPO / "cities" / "mumbai" / "gazetteer.json"
CITY_JSON = REPO / "cities" / "mumbai" / "city.json"
GENERATOR = REPO / "scripts" / "gen_osint_gazetteer.py"
#: the first pack place's gaz_id: 72 junctions and 86 road segments come first
FIRST_PLACE = 159


def _generator():
    spec = importlib.util.spec_from_file_location("gen_osint_gazetteer", GENERATOR)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def doc() -> dict:
    return json.loads(GAZ_JSON.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def pack() -> dict:
    return json.loads(PACK_JSON.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def gaz() -> Gazetteer:
    return load()


# ------------------------------------------------------------------------------------------------- X19 format
def test_x19_format(doc):
    assert set(doc) == {"meta", "entries"}
    assert set(doc["meta"]) == set(META_FIELDS)
    assert doc["meta"]["entries"] == len(doc["entries"]) == 392
    for e in doc["entries"]:
        assert list(e) == list(ENTRY_FIELDS), e.get("gaz_id")
        assert e["feature_type"] in gz.FEATURE_TYPES
        assert isinstance(e["surface_forms"], list) and all(isinstance(f, str) for f in e["surface_forms"])
    assert [e["gaz_id"] for e in doc["entries"]] == list(range(1, 393))
    counts = {t: sum(1 for e in doc["entries"] if e["feature_type"] == t) for t in gz.FEATURE_TYPES}
    assert counts == {"road": 86, "junction": 72, "neighbourhood": 85, "landmark": 115, "admin": 0, "poi": 34}
    assert "Mumbai" in doc["meta"]["source"]


def test_odbl_notice(doc, gaz):
    assert doc["meta"]["licence"] == LICENCE == "© OpenStreetMap contributors, ODbL 1.0"
    assert gaz.meta["licence"] == LICENCE
    assert "OpenStreetMap" in doc["meta"]["source"]


def test_ids_are_the_network_of_record_then_the_city_pack(doc, pack):
    net = json.loads(NETWORK_JSON.read_text(encoding="utf-8"))
    junctions = [e for e in doc["entries"] if e["feature_type"] == "junction"]
    roads = [e for e in doc["entries"] if e["feature_type"] == "road"]
    assert [e["gaz_id"] for e in junctions] == list(range(1, 73))
    assert [e["junction_id"] for e in junctions] == [j["junction_id"] for j in net["junctions"]]
    assert [e["canonical_name"] for e in junctions] == [j["name"] for j in net["junctions"]]
    assert [e["gaz_id"] for e in roads] == list(range(73, FIRST_PLACE))
    assert [e["segment_id"] for e in roads] == [s["segment_id"] for s in net["segments"]] == list(range(1001, 1087))
    assert [e["canonical_name"] for e in roads] == [s["road_name"] for s in net["segments"]]
    # the pack's places follow in pack order, so their gaz_ids stay stable while new places are appended
    places = [e for e in doc["entries"] if e["feature_type"] not in ("junction", "road")]
    assert [e["gaz_id"] for e in places] == list(range(FIRST_PLACE, FIRST_PLACE + len(pack["places"])))
    for e, p in zip(places, pack["places"], strict=True):
        assert e["canonical_name"] == p["en"], p["id"]
        assert e["feature_type"] == ("neighbourhood" if p["anchor"] == "area" else p["feature_type"]), p["id"]
        anchor = p["anchor"]
        want = (int(anchor[1:]) if anchor[0] == "J" else None, int(anchor[1:]) if anchor[0] == "S" else None)
        assert (e["junction_id"], e["segment_id"]) == want, p["id"]
        assert e["source"].startswith("city_pack."), p["id"]


@pytest.mark.parametrize(
    ("gaz_id", "pack_id"),
    [(159, "ward_a"), (165, "ward_fn"), (170, "ward_ke"), (197, "worli"), (204, "dadar_area"), (217, "andheri_area"),
     (226, "kurla_area"), (240, "hindmata"), (242, "kings_circle"), (254, "milan_subway"), (255, "andheri_subway"),
     (260, "csmt"), (294, "kem"), (317, "girgaon_chowpatty"), (321, "lalbaugcha_raja"), (369, "ps_dadar"),
     (392, "ps_mulund")],
)
def test_the_pack_ids_other_streams_use_are_stable(doc, pack, gaz_id, pack_id):
    # a pack place's gaz_id is its position: existing places keep their ids and order, new ones are appended
    assert pack["places"][gaz_id - FIRST_PLACE]["id"] == pack_id
    assert doc["entries"][gaz_id - 1]["canonical_name"] == pack["places"][gaz_id - FIRST_PLACE]["en"]


def test_points_are_in_the_city(doc):
    bbox = json.loads(CITY_JSON.read_text(encoding="utf-8"))["bbox"]
    for e in doc["entries"]:
        assert bbox["west"] <= e["lon"] <= bbox["east"] and bbox["south"] <= e["lat"] <= bbox["north"], (
            e["canonical_name"])


def test_the_city_pack_rows(pack):
    assert pack["schema"] == "sajag.gazetteer/1" and pack["city"] == "mumbai"
    assert "OpenStreetMap" in pack["attribution"] and "ODbL" in pack["attribution"]
    ids = [p["id"] for p in pack["places"]]
    assert len(ids) == len(set(ids))
    for p in pack["places"]:
        assert p["en"].strip() and p["mr"].strip() and p["hi"].strip(), p["id"]
        assert translit.is_indic(p["mr"]) and translit.is_indic(p["hi"]), p["id"]
        assert re.fullmatch(r"area|snap|J\d+|S\d+", p["anchor"]), p["id"]
        assert 0.0 <= p["importance"] <= 1.0 and isinstance(p.get("low_lying"), bool), p["id"]
        # a hand row's point is approximate and says so; the others come from landmarks.json or the OSM extract
        assert p["source"] == "hand" or p["source"] == "landmarks.json" or p["source"].startswith("osm:"), p["id"]


def test_the_low_lying_spots_are_flagged(pack):
    low = {p["id"] for p in pack["places"] if p["low_lying"]}
    assert {"hindmata", "kings_circle", "dadar_tt", "gandhi_market", "kranti_nagar", "parel_tt", "milan_subway",
            "andheri_subway", "chunabhatti_station_road", "yellow_gate", "mithi_kurla"} <= low
    # the 24 BMC wards are all in the pack, as areas
    wards = [p for p in pack["places"] if p["kind"] == "ward"]
    assert len(wards) == 24 and all(p["anchor"] == "area" for p in wards)


# ------------------------------------------------------------------------------------------------- places only
def test_places_only_no_person_key(doc):
    ethics.assert_no_person_keys(doc)
    for e in doc["entries"]:
        assert not any(ethics.is_forbidden_key(k) for k in e if k != "surface_forms")


@pytest.mark.parametrize("extra", ["victim", "author", "notes", "person_name", "reporter", "owner"])
def test_a_key_outside_the_x19_list_is_refused(doc, extra):
    bad = copy.deepcopy(doc)
    bad["entries"][5][extra] = "x"
    with pytest.raises(ValueError, match="outside the X19 field list"):
        Gazetteer.from_document(bad)


def test_a_meta_or_top_level_key_outside_the_list_is_refused(doc):
    bad = copy.deepcopy(doc)
    bad["meta"]["uploader"] = "x"
    with pytest.raises(ValueError, match="X19"):
        Gazetteer.from_document(bad)
    bad = copy.deepcopy(doc)
    bad["people"] = []
    with pytest.raises(ValueError, match="top-level"):
        Gazetteer.from_document(bad)


@pytest.mark.parametrize(
    "field,value",
    [
        ("gaz_id", True),
        ("gaz_id", 0),
        ("feature_type", "person"),
        ("lon", 200.0),
        ("lat", float("nan")),
        ("importance", 1.5),
        ("surface_forms", "dadar"),
        ("surface_forms", [1, 2]),
        ("canonical_name", ""),
        ("canonical_name", "Dadar\x00"),
        ("canonical_name", "Dadar‮"),  # a bidi override: display spoofing
        ("lang_primary", "Marathi"),
        ("junction_id", -3),
    ],
)
def test_bad_values_are_refused(doc, field, value):
    bad = copy.deepcopy(doc)
    bad["entries"][0][field] = value
    with pytest.raises(ValueError):
        Gazetteer.from_document(bad)


def test_missing_fields_and_wrong_counts_are_refused(doc):
    bad = copy.deepcopy(doc)
    del bad["entries"][3]["importance"]
    with pytest.raises(ValueError, match="lacks"):
        Gazetteer.from_document(bad)
    bad = copy.deepcopy(doc)
    bad["meta"]["entries"] = 391
    with pytest.raises(ValueError, match="meta.entries"):
        Gazetteer.from_document(bad)
    bad = copy.deepcopy(doc)
    bad["entries"][1]["gaz_id"] = 1
    with pytest.raises(ValueError, match="duplicate"):
        Gazetteer.from_document(bad)
    bad = copy.deepcopy(doc)
    bad["entries"][100]["segment_id"] = None  # a road without its segment
    with pytest.raises(ValueError, match="segment_id"):
        Gazetteer.from_document(bad)
    bad = copy.deepcopy(doc)
    bad["entries"][10]["junction_id"] = None  # a junction without its id
    with pytest.raises(ValueError, match="junction_id"):
        Gazetteer.from_document(bad)


# ------------------------------------------------------------------------------------------------- protect-set
def test_protect_set_holds_every_canonical_name_and_form(doc, gaz):
    assert isinstance(gaz.protect_set, frozenset)
    for e in doc["entries"]:
        assert norm(e["canonical_name"]) in gaz.protect_set
        for f in e["surface_forms"]:
            assert f in gaz.protect_set
    for part in ("western express highway", "weh", "sea link", "hindmata", "dadar tt circle", "kings circle",
                 "milan subway", "andheri subway", "lalbaugcha raja", "csmt", "दादर", "हिंदमाता", "अंधेरी सबवे",
                 "बांद्रा", "वरळी नाका"):
        assert part in gaz.protect_set, part


def test_protect_set_never_holds_a_bare_person_name(gaz):
    # a sub-phrase of a place named after a person would protect that person's name: none is added
    for name in ("senapati bapat", "ambedkar", "babasaheb ambedkar", "annie besant", "lal bahadur shastri",
                 "swami vivekanand", "dadabhai naoroji", "maulana azad", "gokhale", "tilak", "lokmanya tilak",
                 "sane guruji", "jagannath shankarsheth", "keshavrao khadye", "pandurang budhkar",
                 "khan abdul gaffar khan", "acharya atre", "veer nariman", "sant gadge maharaj", "rajiv gandhi",
                 "shivaji", "chhatrapati shivaji maharaj", "mahatma gandhi", "indira gandhi", "vallabhbhai patel",
                 "savarkar", "jijamata", "kaustubh rane", "annabhau sathe", "kokilaben", "nanavati", "hinduja",
                 "lilavati", "jaslok", "hiranandani", "gandhi", "nehru", "indira"):
        assert name not in gaz.protect_set, name


# ------------------------------------------------------------------------------------------------- forms
def test_every_form_is_normal_matchable_and_not_generic(doc):
    for e in doc["entries"]:
        assert e["surface_forms"] == sorted(set(e["surface_forms"])), e["gaz_id"]
        for f in e["surface_forms"]:
            assert norm(f) == f, (e["gaz_id"], f)
            assert len(f) >= gz.MIN_FORM_CHARS
            assert not all(t in gz.GENERIC_STOPWORDS for t in f.split(" ")), (e["gaz_id"], f)


def test_every_pack_spelling_is_carried(doc, pack):
    gen = _generator()
    for p in pack["places"]:
        e = doc["entries"][FIRST_PLACE - 1 + pack["places"].index(p)]
        forms = set(e["surface_forms"])
        for raw in (p["en"], gen._base(p["en"]), p["mr"], p["hi"], *p.get("aka", []), *p.get("aka_mr", []),
                    *p.get("aka_hi", [])):
            n = norm(raw)
            if gen._good(n):
                assert n in forms, (p["id"], raw)


def test_no_bare_first_word_of_a_junction_name_is_its_alias(doc, gaz):
    # the first word of a junction's name is often a surname or a person's name ("Jacob", "Kemps", "Acharya"), a
    # word ("Opera", "Lower") or an area ("Worli", "Sion"): the generator adds none of them
    for e in doc["entries"]:
        if e["feature_type"] != "junction":
            continue
        words = norm(re.sub(r"\s*\(.*?\)\s*", " ", e["canonical_name"])).split(" ")
        if len(words) > 1:
            assert words[0] not in e["surface_forms"], (e["gaz_id"], words[0])
    for word in ("jacob", "kemps", "opera", "haji", "amar", "acharya", "lower", "chheda", "worli", "sion", "nagpada"):
        assert all(gaz.by_id[g].feature_type != "junction" for g in gaz.lookup(word)), word
    # the junctions' own names still reach them
    for name, jid in (("jacob circle", 11), ("kemps corner", 8), ("opera house", 7), ("haji ali junction", 10),
                      ("amar mahal junction", 65), ("chheda nagar", 66), ("nagpada junction", 14)):
        assert [gaz.by_id[g].junction_id for g in gaz.lookup(name)] == [jid], name


@pytest.mark.parametrize(
    ("word", "gaz_id"),
    [
        ("dadar", 204), ("दादर", 204), ("andheri", 217), ("अंधेरी", 217), ("kurla", 226), ("कुर्ला", 226),
        ("bandra", 211), ("वांद्रे", 211), ("बांद्रा", 211), ("sion", 208), ("सायन", 208), ("worli", 197),
        ("वरळी", 197), ("parel", 200), ("परळ", 200), ("lalbaug", 201), ("lalbag", 201), ("लालबाग", 201),
        ("matunga", 205), ("mahim", 206), ("byculla", 193), ("भायखळा", 193), ("chembur", 227), ("ghatkopar", 228),
        ("ghatkoper", 228), ("powai", 230), ("santacruz", 213), ("borivali", 224), ("borivli", 224),
    ],
)
def test_an_area_word_is_never_a_junction_alias(gaz, word, gaz_id):
    # F-HONEST OSINT-1: a bare area word reaches the area (or the station) only, in every script, never the junction
    # named after it ("Worli" alone is the neighbourhood; "Worli Naka" is junction 24)
    assert gaz.lookup(word) == (gaz_id,), word


def test_the_junctions_own_names_still_reach_them(gaz):
    for name, jid in (("worli naka", 24), ("वरळी नाका", 24), ("worli naka junction", 24), ("sion circle", 23),
                      ("सायन सर्कल", 23), ("शीव सर्कल", 23), ("jacob circle", 11), ("saat rasta", 11),
                      ("जेकब सर्कल", 11), ("kemps corner", 8), ("haji ali junction", 10), ("opera house", 7),
                      ("amar mahal junction", 65), ("saki naka junction", 54), ("kalanagar junction", 37),
                      ("csmt junction", 4), ("nagpada junction", 14), ("jj junction", 13)):
        assert [gaz.by_id[g].junction_id for g in gaz.lookup(name)] == [jid], name


def test_the_lint_refuses_an_area_word_on_a_junction_and_a_person_phrase(doc):
    gen = _generator()
    assert gen.lint(doc) == []
    bad = copy.deepcopy(doc)
    junction = next(e for e in bad["entries"] if e["junction_id"] == 24 and e["feature_type"] == "junction")
    junction["surface_forms"] = sorted([*junction["surface_forms"], "worli"])
    assert any("junction form shared with a pack place: 'worli'" in p for p in gen.lint(bad))
    bad = copy.deepcopy(doc)
    for jid in (8, 11):
        j = next(e for e in bad["entries"] if e["junction_id"] == jid and e["feature_type"] == "junction")
        j["surface_forms"] = sorted([*j["surface_forms"], "jacob"])
    assert any("bare junction form shared with another junction: 'jacob'" in p for p in gen.lint(bad))
    # a multi-word phrase with no place-type word (a person's name) is never a form
    bad = copy.deepcopy(doc)
    road = next(e for e in bad["entries"] if e["segment_id"] == 1079 and e["feature_type"] == "road")
    road["surface_forms"] = sorted([*road["surface_forms"], "sane guruji"])
    assert any("phrase without a place-type word: 'sane guruji'" in p for p in gen.lint(bad))


def test_the_osm_names_along_a_segment(gaz):
    gen = _generator()
    assert {"bridge", "setu", "circle", "crossing"} <= gen.POINT_WORDS
    # a bridge or circle on the segment is point-like: an alias at any length (Warerkar bridge: 40 m of segment 1083;
    # Khodadad Circle: 43 m of 1066, and on 1067 and 1071)
    assert [gaz.by_id[g].segment_id for g in gaz.lookup("warerkar bridge")] == [1083]
    assert [gaz.by_id[g].segment_id for g in gaz.lookup("khodadad circle")] == [1066, 1067, 1071]
    # a few metres of another road where it touches the segment is not its alias: Marine Drive's 23 m on segments
    # 1083, 1084 and 1086 and 35 m on the Coastal Road (1007) leave "marine drive" to the Marine Drive segments
    marine = {gaz.by_id[g].segment_id for g in gaz.lookup("marine drive")}
    assert marine == {1001, 1002, 1003} and not marine & {1007, 1083, 1084, 1086}
    # another network road's own name along a segment is never borrowed (OSM names stretches of the Eastern Express
    # Highway at Sion "Sion Panvel Highway": the name stays the Sion-Panvel Highway's)
    assert not {gaz.by_id[g].segment_id for g in gaz.lookup("sion panvel highway")} & {1043, 1044, 1045}
    # an OSM circle named like a junction stays the junction's alone (Sion Circle, 96 m of segment 1043)
    assert gaz.lookup("sion circle") == (23,)


def test_generator_lint_is_clean_and_phrases_are_places(doc):
    gen = _generator()
    assert gen.lint(doc) == []
    multi = {gen._phrase(f) for e in doc["entries"] for f in e["surface_forms"]} - {""}
    assert len([p for p in multi if " " in p]) > 300


def test_marathi_and_hindi_aliases(gaz, pack):
    assert gaz.lookup("दादर") == gaz.lookup("dadar") == (204,)
    assert gaz.lookup("वांद्रे") == gaz.lookup("बांद्रा") == gaz.lookup("bandra") == (211,)
    assert 24 in gaz.lookup("वरळी नाका")  # junction 24, from osm_network.json's name_mr
    # every pack place carries its Marathi and its Hindi name
    for i, p in enumerate(pack["places"]):
        assert FIRST_PLACE + i in gaz.lookup(p["mr"]) and FIRST_PLACE + i in gaz.lookup(p["hi"]), p["id"]
    # common Marathi words are never a place on their own
    for word in ("शहर", "रस्ता", "चौक", "पोलीस", "पाणी", "मुंबई", "गणपती"):
        assert gaz.lookup(word) == (), word


def test_the_gated_forms_carry_their_script_spellings(gaz):
    # translit's tables give a gated Latin form its Marathi and Devanagari spellings (the resolver gates them all)
    for latin in ("coastal road", "marine drive", "atal setu", "sv road", "santacruz"):
        carried = [s for s in translit.script_aliases(latin) if gaz.lookup(s)]
        assert len(carried) >= 2 and all(gaz.lookup(s) == gaz.lookup(latin) for s in carried), latin
    assert translit.latin_variants("santacruz") == ("santa cruz",)
    assert translit.latin_variants("lalbaug") == ("lalbag",)
    assert "ghatkoper" in translit.latin_variants("ghatkopar")


# ------------------------------------------------------------------------------------------------- normaliser
@pytest.mark.parametrize(
    "raw,want",
    [
        ("Dr. A.R. Nair Road", "dr a r nair road"),
        ("  WEH   Andheri ", "weh andheri"),
        ("NH-48", "nh48"),
        ("NH 48", "nh48"),
        ("Eastern Express Highway SH-42", "eastern express highway sh42"),
        ("Dādar Chowpātty", "dadar chowpatty"),
        ("Matunga’s", "matunga s"),
        ("Sion-Panvel Highway, Chembur", "sion panvel highway chembur"),
        ("Dr Ambedkar Road (Hindmata–Dadar TT)", "dr ambedkar road hindmata dadar tt"),
        ("हिंदमाता (दादर पूर्व)", "हिंदमाता दादर पूर्व"),
        ("हिंद\u200dमाता", "हिंदमाता"),  # a zero-width joiner never splits a word
        # a precomposed nukta letter (ज़ U+095B) decomposes (NFKC): one form for both spellings
        ("सांताक्रू\u095b", "सांताक्रू\u091c\u093c"),
        ("वांद्रे स्थानक", "वांद्रे स्थानक"),
        ("ＷＥＨ\u3000Ａｎｄｈｅｒｉ", "weh andheri"),
        (None, ""),
    ],
)
def test_norm(raw, want):
    assert norm(raw) == want
    assert norm(norm(raw)) == norm(raw)


def test_translit_is_in_step_with_norm():
    for s in ("Dr. A.R. Nair Road", "हिंदमाता (दादर पूर्व)", "सांताक्रूज़", "Kings Circle"):
        assert translit._n(s) == norm(s)
    assert translit.to_latin("दादर स्थानक") == "dadar station"
    assert translit.to_latin("वरळी नाका") == "worli naka"
    assert translit.to_latin("सायन सर्कल") == "sion circle"
    assert translit.to_latin("अनोळखी जागा") is None  # a partial transliteration is never guessed
    assert len(translit.MR_LATIN_SEED) == 21


def test_marathi_case_endings_are_the_ethics_lexicon_s():
    # one list for the scanner and the redactor (osint_common.ethics.INDIC_SUFFIXES): a lockstep
    assert translit.MR_SUFFIXES == ethics.INDIC_SUFFIXES
    assert list(translit.MR_SUFFIXES) == sorted(translit.MR_SUFFIXES, key=len, reverse=True)
    assert not any("઀" <= ch <= "૿" for s in translit.MR_SUFFIXES for ch in s)  # Marathi endings only


# ------------------------------------------------------------------------------------------------- longest match
def test_longest_match_prefers_the_longer_form(gaz):
    hits = gaz.match("Flooding on Dr Ambedkar Road (Hindmata - Dadar TT)")
    assert [h.form for h in hits] == ["dr ambedkar road hindmata dadar tt"]
    hits = gaz.match("Crash on Andheri Subway near Western Express Highway")
    assert sorted((h.start, h.form) for h in hits) == [(2, "andheri subway"), (5, "western express highway")]
    # the selection order is the PoC's: longer covered text first
    assert [h.form for h in hits] == ["western express highway", "andheri subway"]


def test_every_occurrence_is_a_mention(gaz):
    hits = gaz.match("Worli Naka ... Worli Naka ... worli naka")
    assert [h.form for h in hits] == ["worli naka"] * 3


@pytest.mark.parametrize(
    ("text", "forms"),
    [
        ("दादरच्या रस्त्यावर हिंदमातामध्ये", ["दादर", "हिंदमाता"]),  # -च्या (of Dadar), -मध्ये (in Hindmata)
        ("अंधेरीतील वरळीत घाटकोपरला", ["अंधेरी", "वरळी", "घाटकोपर"]),  # -तील, -त, -ला
        ("दादरहून सायनपर्यंत", ["दादर", "सायन"]),  # -हून (from), -पर्यंत (up to)
        ("लालबागचा परिसर", ["लालबाग"]),  # a word the place "लालबागचा राजा" also carries
        ("शहराच्या रस्त्यावर", []),  # "of the city", "on the road": no place stem
        ("मुंबईत", []),  # the city's name is no place (it opens the context gate instead)
    ],
)
def test_marathi_case_endings_are_read(gaz, text, forms):
    assert [h.form for h in sorted(gaz.match(text))] == forms


def test_an_inflected_alias_word_stays_whole_only_inside_its_form(gaz):
    assert gaz.tokens("लालबागचा राजा") == ["लालबागचा", "राजा"]  # the pandal "लालबागचा राजा"
    assert gaz.tokens("लालबागचा परिसर")[0] == "लालबाग"
    # both spellings of "ज़" (one code point, or "ज" + nukta) read the same
    assert gaz.tokens("सांताक्रू\u095bमध्ये") == gaz.tokens("सांताक्रू\u091c\u093cमध्ये") == [norm("सांताक्रूज़")]


def test_tokens_never_match_inside_a_word(gaz):
    assert gaz.match("Dadarwala") == [] and gaz.match("Kurlapada") == [] and gaz.match("Andheriwadi") == []


# ------------------------------------------------------------------------------------------------- path rules
def test_path_rules_and_cache(tmp_path, monkeypatch):
    assert load() is load() and load().path is not None and load().path.name == "osint_gazetteer.json"
    custom = tmp_path / "g.json"
    custom.write_text(GAZ_JSON.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setenv(gz.GAZETTEER_ENV, str(custom))
    assert load().path == custom
    monkeypatch.setenv(gz.GAZETTEER_ENV, str(tmp_path / "missing.json"))
    with pytest.raises(FileNotFoundError):
        load()
    with pytest.raises(FileNotFoundError):
        load(tmp_path / "nope.json")
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"meta": {}, "entries": [{"gaz_id": 1}]}), encoding="utf-8")
    with pytest.raises(ValueError):
        load(bad)


def test_entries_read_as_objects_and_mappings(gaz):
    e = gaz.by_id[240]
    assert e.canonical_name == e["canonical_name"] == "Hindmata (Dadar East)"
    assert dict(e)["gaz_id"] == 240 and e.get("nope", 1) == 1 and e.junction_id == 19 and e.segment_id is None
    assert json.loads(json.dumps(e.as_dict()))["surface_forms"] == list(e.surface_forms)
    with pytest.raises(KeyError):
        e["victim"]


# ------------------------------------------------------------------------------------------------- generator
def test_generator_is_deterministic_and_matches_the_committed_file():
    gen = _generator()
    a, b = gen.render(gen.build()), gen.render(gen.build())
    assert a == b == GAZ_JSON.read_text(encoding="utf-8")


def test_generator_check_exit_codes(tmp_path):
    ok = subprocess.run([sys.executable, str(GENERATOR), "--check"], capture_output=True, text=True, cwd=REPO)
    assert ok.returncode == 0, ok.stderr
    stale = tmp_path / "stale.json"
    stale.write_text(GAZ_JSON.read_text(encoding="utf-8").replace('"hindmata"', '"hindmaata"', 1), encoding="utf-8")
    bad = subprocess.run([sys.executable, str(GENERATOR), "--check", "--out", str(stale)], capture_output=True,
                         text=True, cwd=REPO)
    assert bad.returncode == 1 and "DIFFERS" in bad.stderr


def test_overpass_review_is_offline_and_writes_nothing(doc):
    gen = _generator()
    response = {"elements": [
        {"type": "node", "lat": 19.118, "lon": 72.855, "tags": {"place": "neighbourhood", "name": "Gundavali"}},
        {"type": "node", "lat": 19.02, "lon": 72.84, "tags": {"place": "suburb", "name": "Dadar"}},
        {"type": "node", "lat": 19.1, "lon": 72.9, "tags": {"place": "neighbourhood"}},
    ]}
    lines = gen.overpass_review(response, doc)
    assert len(lines) == 1 and "Gundavali" in lines[0]
    query = gen.overpass_query()
    assert "suburb|neighbourhood|quarter" in query and "18.89,72.77,19.28,72.99" in query


def test_every_junction_keeps_its_marathi_name_unless_a_pack_place_carries_it(doc):
    # F-HONEST OSINT-1: "हिंदमाता" and "मिलन सबवे" alone are the flooding spot and the subway (pre-linked to their
    # junctions), never a second junction pin
    net = json.loads(NETWORK_JSON.read_text(encoding="utf-8"))
    forms = {e["junction_id"]: set(e["surface_forms"]) for e in doc["entries"] if e["feature_type"] == "junction"}
    place_forms = {f for e in doc["entries"] if e["feature_type"] not in ("junction", "road")
                   for f in e["surface_forms"]}
    dropped = []
    for j in net["junctions"]:
        mr = norm(j["name_mr"])
        if mr in forms[j["junction_id"]]:
            continue
        assert mr in place_forms, j["junction_id"]
        dropped.append(j["junction_id"])
    assert dropped == [19, 20, 21, 42]


def test_generator_check_needs_the_standard_library_only():
    # osint_geo.gazetteer, translit and geom import nothing outside the stdlib: --check runs on any Python 3.12
    code = (
        "import runpy, sys\n"
        "for m in ('numpy', 'pyproj', 'shapely', 'pydantic'): sys.modules[m] = None\n"
        f"sys.argv = [{str(GENERATOR)!r}, '--check']\n"
        f"runpy.run_path({str(GENERATOR)!r}, run_name='__main__')\n"
    )
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=REPO)
    assert r.returncode == 0, r.stderr
    assert "gazetteer OK" in r.stdout


def test_no_form_reads_as_a_person(doc):
    for e in doc["entries"]:
        for text in (e["canonical_name"], *e["surface_forms"]):
            assert ethics.find_pii(text) == [], (e["gaz_id"], text)


def test_the_seed_notice_credits_the_gazetteer():
    # F-DEPLOY D-16: the gazetteer carries OSM-derived names and points, so it sits in the seed NOTICE's ODbL table
    notice = (REPO / "services" / "corridor-store" / "seed" / "NOTICE.md").read_text(encoding="utf-8")
    rows = [line for line in notice.splitlines() if line.startswith("| `scripts/data/osint_gazetteer.json`")]
    assert len(rows) == 1 and "ODbL" in rows[0]
