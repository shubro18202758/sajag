"""Place matching across Devanagari (Marathi, Hindi), romanised text and English."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from speech_service.places import ALIASES, Gazetteer, fold_mr, load_gazetteer, skeleton


@pytest.mark.parametrize("deva,en", [
    ("हिंदमाता", "Hindmata"), ("वरळी", "Worli"), ("अंधेरी सबवे", "Andheri Subway"),
    ("मिलन सबवे", "Milan Subway"), ("कुर्ला", "Kurla"), ("घाटकोपर", "Ghatkopar"),
    ("चेंबूर", "Chembur"), ("परळ", "Parel"), ("लालबाग", "Lalbaug"), ("सायन", "Sion"),
    ("किंग्स सर्कल", "King's Circle"), ("कलानगर", "Kalanagar"), ("वानखेडे", "Wankhede"),
    ("व्हीटी", "VT"), ("बोरीवली", "Borivali"),
    ("वांद्रे", "Bandra"),  # व and b are one letter
])
def test_skeleton_is_the_same_in_both_scripts(deva: str, en: str) -> None:
    assert skeleton(deva) == skeleton(en)


def test_fold_mr_merges_asr_spelling_variants() -> None:
    assert fold_mr("हिंदमाता") == fold_mr("हिन्दमाता".replace("न्", ""))  # anusvara dropped either way
    assert fold_mr("माहीम") == fold_mr("माहिम")          # ी/ि
    assert fold_mr("परळ") == fold_mr("परल")              # Marathi ळ, Hindi ल
    assert fold_mr("पाणी") == fold_mr("पानी")            # ण/न
    assert fold_mr("कॉजवे") == fold_mr("कोजवे")          # ॉ/ो
    assert fold_mr("पेड़") == fold_mr("पेड")              # nukta
    assert fold_mr("टर्मिनल २") == "टर्मिनल 2"
    assert fold_mr("टक्कर") == fold_mr("टकर")            # gemination


def test_aliases_point_at_real_landmark_ids(gaz: Gazetteer) -> None:
    ids = {p.id for p in gaz.places}
    assert set(ALIASES) <= ids


def test_the_city_pack_is_mumbai(gaz: Gazetteer) -> None:
    assert gaz.by_id("hindmata") is not None and gaz.by_id("andheri_subway") is not None
    assert all(18.8 < p.lat < 19.4 and 72.7 < p.lon < 73.1 for p in gaz.places)


@pytest.mark.parametrize("text,pid", [
    ("हिंदमाता येथे गुडघाभर पाणी साचले आहे, बस अडकल्या आहेत", "hindmata"),
    ("हिंदमाताजवळ पाणी तुंबले", "hindmata"),                         # postposition on the name
    ("हिंद माता चौकात पाणी", "hindmata"),                            # ASR split
    ("Hindmata la gudghabhar pani", "hindmata"),                      # romanised Marathi
    ("Knee-deep water at Hindmata", "hindmata"),                      # English
    ("मिलन सबवेमध्ये कमरेइतके पाणी", "milan_subway"),
    ("अंधेरी सबवे में पानी भर गया है", "andheri_subway"),            # Hindi
    ("Andheri subway band hai, paani bhar gaya", "andheri_subway"),   # romanised Hindi
    ("अंधेरी स्टेशनबाहेर गर्दी", "andheri"),
    ("किंग्ज सर्कलजवळ झाड पडले आहे", "kings_circle"),
    ("Tree fallen at King's Circle, one lane blocked", "kings_circle"),
    ("शीव सर्कलवर वाहतूक कोंडी", "sion_circle"),                     # Marathi name of Sion
    ("सायन में भारी जाम", "sion_circle"),
    ("दादर टीटीला अपघात", "dadar_tt"),
    ("वरळी नाक्यावर विजेची तार तुटली", "worli_naka"),
    ("सीएसटी स्टेशनबाहेर गर्दी", "csmt"),                            # everyday name
    ("VT station ke bahar bheed", "csmt"),
    ("बीकेसीमध्ये दोन गाड्यांची धडक", "bkc"),
    ("बांद्रा कुर्ला कॉम्प्लेक्स में टक्कर", "bkc"),                 # not Kurla, not Bandra
    ("सी लिंकवर एक बस बंद पडली", "sea_link"),
    ("WEH पर अंधेरी के पास जाम", "weh_andheri"),
    ("पश्चिम द्रुतगती महामार्गावर अंधेरीजवळ कोंडी", "weh_andheri"),
    ("पवईत जेव्हीएलआरवर झाड पडले", "powai"),
    ("केईएम रुग्णालयाकडे जाणारा रस्ता पाण्याखाली", "kem"),
    ("लालबागचा राजा परिसरात गर्दी", "lalbaugcha_raja"),               # not Lalbaug
    ("गिरगाव चौपाटीकडे विसर्जन मिरवणूक", "girgaon_chowpatty"),
    ("Mithi river near Kurla is rising", "mithi_kurla"),
    ("के ई एम रुग्णालयाकडे जाणारा रस्ता पाण्याखाली", "kem"),        # initials spelt out (ASR)
    ("अंधेरी सभ्भे पाणी साचल्यामुळे बंद", "andheri_subway"),          # ASR: भ for ब, व for व
    ("मिलनसव्य में कमर तक पानी", "milan_subway"),                    # ASR: merged and misspelt
    ("बांद्रा कुला कॉम्प्लेक्स में टक्कर", "bkc"),                    # one word misheard, not Bandra
])
def test_match(gaz: Gazetteer, text: str, pid: str) -> None:
    m, cands = gaz.match(text)
    assert m is not None, (text, [(c.place.id, c.score) for c in cands])
    assert m.place.id == pid, (text, m.place.id, m.matched_text)
    d = m.as_dict()
    assert set(d) >= {"id", "name_en", "name_mr", "lat", "lon", "match_score"}
    assert 0.8 <= d["match_score"] <= 1.0


@pytest.mark.parametrize("text", [
    "पाऊस पडत आहे, रस्त्यावर पाणी",        # no place named
    "सुबह से भारी बारिश हो रही है",        # "सुबह" (morning) and "शीव" (Sion) share a skeleton
    "Heavy rain everywhere since morning",
    "Fire reported near the market",     # "reported" must not spell "एअरपोर्ट"
])
def test_no_place_is_asserted_when_none_is_named(gaz: Gazetteer, text: str) -> None:
    m, _ = gaz.match(text)
    assert m is None


def test_a_qualified_name_wins_over_its_qualifier(gaz: Gazetteer) -> None:
    """"WEH … near Andheri" names the highway at Andheri, not the station:
    when two places match equally and one's full name carries the other as
    its qualifier ("Western Express Highway (Andheri)"), the qualified one wins."""
    m, cands = gaz.match("WEH पर अंधेरी के पास जाम")
    assert m is not None and m.place.id == "weh_andheri"
    assert "andheri" in [c.place.id for c in cands]
    m2, _ = gaz.match("अंधेरी स्टेशनबाहेर गर्दी")
    assert m2 is not None and m2.place.id == "andheri"


def test_candidates_are_offered_below_threshold(gaz: Gazetteer) -> None:
    m, cands = gaz.match("गिंदमाता येथे पाणी")  # one consonant off
    assert cands, "the officer gets candidates to pick from"
    assert cands[0].place.id == "hindmata" or m is None


def _write_city(tmp: Path, gazetteer: object) -> Path:
    tmp.mkdir(parents=True, exist_ok=True)
    (tmp / "landmarks.json").write_text(json.dumps({"landmarks": [
        {"id": "hindmata", "kind": "junction", "lat": 19.0049, "lon": 72.8424, "en": "Hindmata (Dadar East)",
         "mr": "हिंदमाता (दादर पूर्व)", "hi": "हिंदमाता (दादर पूर्व)"}]}, ensure_ascii=False), encoding="utf-8")
    (tmp / "gazetteer.json").write_text(json.dumps(gazetteer, ensure_ascii=False), encoding="utf-8")
    return tmp


@pytest.mark.parametrize("doc", [
    {"entries": [{"id": "ps_matunga", "name_en": "Matunga Police Station", "name_mr": "माटुंगा पोलीस ठाणे",
                  "lat": 19.0275, "lon": 72.8535}]},
    [{"id": "ps_matunga", "en": "Matunga Police Station", "mr": "माटुंगा पोलीस ठाणे",
      "lat": 19.0275, "lon": 72.8535}],
    {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {
        "id": "ps_matunga", "name_en": "Matunga Police Station", "name_mr": "माटुंगा पोलीस ठाणे"},
        "geometry": {"type": "Point", "coordinates": [72.8535, 19.0275]}}]},
    {"police_stations": [{"id": "ps_matunga", "names": {"en": "Matunga Police Station",
                                                       "mr": "माटुंगा पोलीस ठाणे"},
                          "lat": 19.0275, "lng": 72.8535}]},
])
def test_gazetteer_json_shapes_are_read(tmp_path: Path, doc: object) -> None:
    g = load_gazetteer(_write_city(tmp_path / "c", doc))
    assert len(g) == 2
    m, _ = g.match("माटुंगा पोलीस ठाण्यासमोर पाणी साचले आहे")
    assert m is not None and m.place.id == "ps_matunga"
    assert m.place.source == "gazetteer"
    assert abs(m.place.lat - 19.0275) < 1e-6 and abs(m.place.lon - 72.8535) < 1e-6


def test_landmark_wins_over_gazetteer_with_the_same_id(tmp_path: Path) -> None:
    g = load_gazetteer(_write_city(tmp_path / "c", [
        {"id": "hindmata", "en": "Somewhere else", "mr": "दुसरीकडे", "lat": 1, "lon": 1},
        {"id": "no_coords", "en": "Nowhere"}]))
    assert len(g) == 1
    assert g.by_id("hindmata").lat == pytest.approx(19.0049)


def test_broken_gazetteer_is_ignored(tmp_path: Path) -> None:
    d = _write_city(tmp_path / "c", [])
    (d / "gazetteer.json").write_text("{not json", encoding="utf-8")
    assert len(load_gazetteer(d)) == 1


def test_a_split_name_is_not_taken_for_its_first_half(gaz: Gazetteer) -> None:
    """The ASR wrote "हाजीअली" as "हाजी अली"; with a place called Haji in the
    gazetteer the first half alone would match it exactly. The longer name
    wins, and Haji said on its own is still Haji."""
    from speech_service.places import Place

    haji = Place("haji_lane", "Haji Lane", "हाजी", 18.98, 72.83, source="gazetteer")
    g = Gazetteer([*gaz.places, haji])
    m, cands = g.match("हाजी अली जंक्शनवर विजेची तार तुटली")
    assert m is not None and m.place.id == "haji_ali"
    m2, _ = g.match("हाजी येथे पाणी साचले")
    assert m2 is not None and m2.place.id == "haji_lane"


def test_a_stray_word_does_not_promote_a_longer_name(gaz: Gazetteer) -> None:
    from speech_service.places import Place

    ps = Place("ps_kurla", "Kurla Police Station", "कुर्ला पोलीस ठाणे", 19.07, 72.88,
               kind="police_station", source="gazetteer")
    g = Gazetteer([*gaz.places, ps])
    m, _ = g.match("कुर्ला पश्चिमेला प्रचंड वाहतूक कोंडी")
    assert m is not None and m.place.id == "kurla"


def test_default_city_is_mumbai_and_can_be_named(monkeypatch) -> None:
    from speech_service.config import default_city_dir

    monkeypatch.delenv("SAJAG_CITY", raising=False)
    assert default_city_dir().name == "mumbai"
    monkeypatch.setenv("SAJAG_CITY", "kolkata")  # the second pack stays loadable by name
    assert default_city_dir().name == "kolkata"


def test_the_whisper_prompt_lists_mumbai_places(gaz: Gazetteer) -> None:
    en = gaz.prompt("en")
    assert en.startswith("Mumbai traffic report.") and len(en) <= 900
    for name in ("Hindmata", "King's Circle", "Milan Subway", "Andheri Subway", "Worli Naka"):
        assert name in en
    assert "(" not in en  # qualifiers are left out
    assert "हिंदमाता" in gaz.prompt("hi") and "वरळी नाका" in gaz.prompt("mr")
