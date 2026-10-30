"""PII-Tracer span detection (embedding_service.pii): post-processing, the protected-toponym guard and the lazy
detector, all offline. The model is mocked; the one real-model test is ``slow`` and skips unless torch imports
and the reviewed snapshot is in the local Hugging Face cache.

Every sentence here is SYNTHETIC; the person names are fictional. Places are Mumbai's (``cities/mumbai``), the
default city pack.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from embedding_service import pii
from embedding_service.pii import (
    DEFAULT_LABELS,
    PLATE_LABEL,
    MUMBAI_EPONYMOUS_PLACES,
    FakePiiDetector,
    PiiTracerDetector,
    RawSpan,
    ToponymGuard,
    city_pack_file,
    default_protected_names,
    load_gazetteer_names,
    load_landmark_names,
    postprocess,
    snap_to_words,
)

_SRC = Path(__file__).resolve().parents[1] / "src"
_CITIES = Path(__file__).resolve().parents[3] / "cities"
_LANDMARKS = _CITIES / "mumbai" / "landmarks.json"
_GAZETTEER = _LANDMARKS.with_name("gazetteer.json")
_KOLKATA_LANDMARKS = _CITIES / "kolkata" / "landmarks.json"  # the second pack, legacy ``bn`` keys


def _span(text: str, needle: str, label: str = "private_person", score: float = 0.9) -> RawSpan:
    i = text.index(needle)
    return RawSpan(i, i + len(needle), label, score)


def _texts(text: str, spans: list[dict]) -> list[str]:
    return [text[s["start"] : s["end"]] for s in spans]


@pytest.fixture(scope="module")
def guard() -> ToponymGuard:
    return ToponymGuard()


# ── import hygiene ───────────────────────────────────────────────────────────────────────────────────────────────


def test_module_imports_without_heavy_dependencies():
    code = (
        "import sys; sys.path.insert(0, sys.argv[1]); import embedding_service.pii as p; "
        "p.FakePiiDetector({'x': 'private_person'}).detect(['x']); "
        "bad = [m for m in ('torch', 'transformers', 'huggingface_hub') if m in sys.modules]; "
        "print(','.join(bad)); sys.exit(1 if bad else 0)"
    )
    res = subprocess.run([sys.executable, "-I", "-c", code, str(_SRC)], capture_output=True, text=True, timeout=60)
    assert res.returncode == 0, res.stdout + res.stderr


def test_constructing_the_real_detector_loads_nothing():
    det = PiiTracerDetector(guard=ToponymGuard(()))
    assert not det.loaded
    assert det.model_name == f"{pii.DEFAULT_MODEL_ID}@{pii.DEFAULT_REVISION[:7]}"
    assert det.labels == DEFAULT_LABELS


# ── word snapping ────────────────────────────────────────────────────────────────────────────────────────────────


def test_snap_widens_a_half_marathi_word():
    text = "स्थानिक रहिवासी सुनील जाधव यांनी सांगितले."
    i = text.index("सुनील") + 1  # the byte-level tokenizer started the span after the first letter
    s, e = snap_to_words(text, i, i + len("ुनील"))
    assert text[s:e] == "सुनील"


def test_snap_widens_a_half_devanagari_word_and_trims_punctuation():
    text = "ड्राइवर राकेश यादव घायल।"
    i = text.index("राकेश")
    s, e = snap_to_words(text, i, i + len("राकेश य"))
    assert text[s:e] == "राकेश यादव"
    s, e = snap_to_words(text, text.index("घायल"), len(text))
    assert text[s:e] == "घायल"


def test_snap_on_latin_text():
    text = "Traffic slow on Senapati Bapat Marg."
    i = text.index("Senapati")
    assert snap_to_words(text, i, i + 3) == (i, i + 8)
    assert snap_to_words(text, 0, 0) == (0, 0)


# ── the protected-toponym guard ──────────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("text", "needle"),
    [
        ("A bus broke down on Senapati Bapat Marg near the junction.", "Senapati"),
        ("A bus broke down on Senapati Bapat Marg near the junction.", "Senapati Bapat"),
        ("Signals failed on Dr Babasaheb Ambedkar Road.", "Babasaheb Ambedkar"),
        ("Flights at Chhatrapati Shivaji Maharaj International Airport were late.", "Chhatrapati Shivaji Maharaj"),
        ("Walkers at Jijamata Udyan saw a fallen branch.", "Jijamata"),
        ("A show at Bhau Daji Lad Museum ends at 6 pm.", "Bhau Daji Lad"),
        ("Annie Besant Road is one-way until Friday.", "Annie Besant"),
        ("Passengers at Acharya Atre Chowk metro station were held back.", "Acharya Atre"),
        ("Water stood on Lady Jamshedji Road at high tide.", "Jamshedji"),  # not in any list: the place-word rule
        ("A fire was reported at Dadasaheb Phalke Chitranagari late on Tuesday.", "Phalke"),  # no place word
        ("A fire was reported at Dadasaheb Phalke Chitranagari late on Tuesday.", "Dadasaheb Phalke"),
        ("Queues at Haji Ali grew after the high tide.", "Haji Ali"),
        ("सेनापती बापट मार्गावर बस बंद पडली.", "सेनापती बापट"),
        ("डॉ. आंबेडकर मार्गावर वाहतूक कोंडी.", "आंबेडकर"),
        ("जिजामाता उद्यानाजवळ फांदी कोसळली.", "जिजामाता"),
        ("वादळानंतर छत्रपती शिवाजी महाराज आंतरराष्ट्रीय विमानतळावर विमाने उशिरा सुटली.", "छत्रपती"),
        ("हुतात्मा चौकात गर्दी वाढली.", "हुतात्मा"),
        ("दादरला आग लागली.", "दादरला"),
        ("सेनापति बापट मार्ग पर बस खराब।", "सेनापति बापट"),
        ("तूफ़ान के बाद छत्रपति शिवाजी महाराज अंतरराष्ट्रीय हवाई अड्डे पर उड़ानें देर से चलीं।", "छत्रपति शिवाजी"),
    ],
)
def test_eponymous_places_are_never_redacted(guard, text, needle):
    assert postprocess(text, [_span(text, needle)], guard=guard) == []


def test_person_next_to_an_eponymous_road_is_kept(guard):
    text = "Driver Sunil Jadhav was unhurt after the bus broke down on Senapati Bapat Marg."
    raw = [_span(text, "Sunil Jadhav"), _span(text, "Senapati Bapat")]
    assert _texts(text, postprocess(text, raw, guard=guard)) == ["Sunil Jadhav"]


def test_a_known_place_ends_a_capitalised_run(guard):
    # "<Given> <Surname> Dr Babasaheb Ambedkar Road": the run before "Road" is five capitalised words, but the
    # known place name is only the last four, so the person stays redacted
    text = "Amcha shejari Rohan Kulkarni Dr Babasaheb Ambedkar Road var adkun aahe."
    raw = [_span(text, "Rohan Kulkarni Dr Babasaheb Ambedkar")]
    assert _texts(text, postprocess(text, raw, guard=guard)) == ["Rohan Kulkarni"]


def test_lower_case_institution_word_does_not_swallow_a_name(guard):
    text = "Truck ulatla, cleaner Raju Shinde hospital madhe."
    assert _texts(text, postprocess(text, [_span(text, "Raju Shinde")], guard=guard)) == ["Raju Shinde"]
    text = "सेनापती बापट मार्गावर ट्रक उलटला, क्लीनर राकेश यादव रुग्णालयात."
    assert _texts(text, postprocess(text, [_span(text, "राकेश यादव")], guard=guard)) == ["राकेश यादव"]


@pytest.mark.parametrize(
    ("text", "name"),
    [
        # a word that only begins with a place word is not a place: मार्गदर्शन (guidance), बागुल (a surname),
        # पार्किंग, सदनिका (a flat), पुलिस (Hindi: police); the name before it stays redacted
        ("पोलीस निरीक्षक राजेश पवार यांच्या मार्गदर्शनाखाली कारवाई झाली.", "राजेश पवार"),
        ("अपघातात राजेश बागुल जखमी झाले.", "राजेश बागुल"),
        ("सुनील जाधव पार्किंगमध्ये होते.", "सुनील जाधव"),
        ("रहिवासी सुनीता पाटील सदनिकेत अडकल्या.", "सुनीता पाटील"),
        ("घायल राकेश यादव पुलिस को मिले।", "राकेश यादव"),
        # nor is a "-kar" surname a place with a case ending: दादरकर is a person, दादरला a place
        ("श्री दादरकर म्हणाले की पाणी ओसरले.", "दादरकर"),
        ("दादा म्हणाले की पाणी ओसरले.", "दादा"),  # a final consonant is no oblique stem: दादा is not दादर
    ],
)
def test_marathi_words_that_begin_with_a_place_word_do_not_protect_a_name(guard, text, name):
    assert _texts(text, postprocess(text, [_span(text, name)], guard=guard)) == [name]


@pytest.mark.parametrize(
    ("text", "needle"),
    [
        ("गोखले पुलावर वाहतूक बंद.", "गोखले"),  # पूल → पुलावर (oblique stem + ending)
        ("शिवाजी पार्कजवळ गर्दी.", "शिवाजी"),
        ("मिलन सबवेमध्ये पाणी साचले.", "मिलन"),
        ("हिंदमाता परिसरात पाणी साचले, लालबागहून वाहतूक वळवली.", "लालबागहून"),
        ("डॉ. ई. मोझेस मार्गावर ट्रक उलटला.", "डॉ. ई"),  # abbreviations inside the run (not in any list)
        ("डॉ. आंबेडकर रोड पर जलभराव।", "डॉ"),
    ],
)
def test_marathi_case_endings_still_protect_the_place(guard, text, needle):
    assert postprocess(text, [_span(text, needle)], guard=guard) == []


def test_single_word_place_only_drops_an_exact_fragment():
    g = ToponymGuard(["Mahalaxmi station"])  # variant "Mahalaxmi" is a single-word place and also a given name
    text = "Mahalaxmi Jadhav was stuck at Mahalaxmi station for an hour."
    i = text.rindex("Mahalaxmi")
    raw = [_span(text, "Mahalaxmi Jadhav"), RawSpan(i, i + len("Mahalaxmi"), "private_person", 0.8)]
    assert _texts(text, postprocess(text, raw, guard=g)) == ["Mahalaxmi Jadhav"]


def test_injected_protected_names_replace_the_default():
    text = "Crowds gathered at Jijamata Udyan."
    raw = [_span(text, "Jijamata")]
    assert postprocess(text, raw, guard=ToponymGuard(["Jijamata Udyan"], place_words=False)) == []
    assert _texts(text, postprocess(text, raw, guard=ToponymGuard((), place_words=False))) == ["Jijamata"]
    # the place-word rule alone (capitalised "Udyan") also protects it
    assert postprocess(text, raw, guard=ToponymGuard(())) == []


def test_landmarks_file_is_read_with_variants(tmp_path):
    names = load_landmark_names(_LANDMARKS)
    assert _LANDMARKS.is_file(), "the Mumbai pack is the default city"
    # "Dadar station" → "Dadar", "King's Circle (Matunga)" → "King's Circle" and "Matunga", "Haji Ali junction" →
    # "Haji Ali"; Marathi and Hindi names too
    assert {"Dadar", "दादर", "Lalbaug", "लालबाग", "King's Circle", "किंग्ज सर्कल", "Matunga", "Hindmata",
            "हिंदमाता", "Haji Ali", "हाजी अली", "CSMT", "Andheri Subway", "अंधेरी सबवे"} <= names
    assert names == load_landmark_names()  # the default is the Mumbai pack
    assert "Dadasaheb Phalke Chitranagari" in default_protected_names(_LANDMARKS)
    assert {"lalbaug", "dadar", "दादर"} <= ToponymGuard()._single  # single-word places of the default guard
    p = tmp_path / "lm.json"
    p.write_text('{"landmarks": [{"en": "Dadar station", "mr": "दादर स्थानक", "hi": "दादर स्टेशन"}, 7, {"en": ""}]}',
                 encoding="utf-8")
    assert load_landmark_names(p) == {"Dadar station", "Dadar", "दादर स्थानक", "दादर", "दादर स्टेशन"}
    # a pack that still uses the legacy Bengali key loads too (the Kolkata pack)
    p.write_text('{"landmarks": [{"en": "Esplanade", "bn": "legacy name"}]}', encoding="utf-8")
    assert load_landmark_names(p) == {"Esplanade", "legacy name"}
    if _KOLKATA_LANDMARKS.is_file():
        kol = load_landmark_names(_KOLKATA_LANDMARKS)
        assert "Esplanade" in kol and any("\u0980" <= ch <= "\u09ff" for n in kol for ch in n)
    p.write_text("not json")
    assert load_landmark_names(p) == frozenset()
    assert load_landmark_names(tmp_path / "missing.json") == frozenset()


def test_city_pack_follows_sajag_city(monkeypatch):
    monkeypatch.delenv("SAJAG_CITY", raising=False)
    assert city_pack_file("landmarks.json") == _LANDMARKS
    monkeypatch.setenv("SAJAG_CITY", "kolkata")
    if _KOLKATA_LANDMARKS.is_file():
        assert city_pack_file("landmarks.json") == _KOLKATA_LANDMARKS
        assert "Esplanade" in load_landmark_names()
    for bad in ("../kolkata", "mumbai/../../etc", ""):
        monkeypatch.setenv("SAJAG_CITY", bad)
        assert city_pack_file("landmarks.json") == _LANDMARKS
    monkeypatch.setenv("SAJAG_CITY", "atlantis")
    assert city_pack_file("landmarks.json") is None and load_landmark_names() == frozenset()
    # the built-in eponymous list still guards when no pack is found
    assert set(MUMBAI_EPONYMOUS_PLACES) <= default_protected_names()


def test_gazetteer_places_and_aliases_are_protected(tmp_path):
    names = load_gazetteer_names(_GAZETTEER)
    if _GAZETTEER.is_file():
        # every ward, neighbourhood, subway and road the pack knows is protected, in every language it is written in
        places = json.loads(_GAZETTEER.read_text(encoding="utf-8"))["places"]
        for pl in places:
            for key in ("en", "mr", "hi"):
                if isinstance(pl.get(key), str) and pl[key].strip():
                    assert pl[key].strip()[:200] in names, (pl.get("id"), key)
        assert {"Dadar", "दादर"} <= names
        assert {"Dadar", "दादर", "Lalbaug", "King's Circle"} <= default_protected_names(_LANDMARKS, _GAZETTEER)
        assert names == load_gazetteer_names()  # the default is the Mumbai pack
        # the model has called a single-word neighbourhood a person: the gazetteer alone keeps it
        text = "Sneha Gawde of Dadar reported waterlogging."
        raw = [_span(text, "Sneha Gawde"), _span(text, "Dadar")]
        assert _texts(text, postprocess(text, raw, guard=ToponymGuard(names))) == ["Sneha Gawde"]
    p = tmp_path / "gz.json"
    p.write_text('{"places": [{"en": "Lalbaug", "mr": "लालबाग", "aka": ["Lalbagh"], "aka_mr": [5]}, "x", {}]}',
                 encoding="utf-8")
    assert load_gazetteer_names(p) == {"Lalbaug", "लालबाग", "Lalbagh"}
    # legacy Bengali keys (the Kolkata pack's gazetteer) are read too
    p.write_text('{"places": [{"en": "Behala", "bn": "legacy", "aka": ["Behela"], "aka_bn": ["legacy alias"]}]}',
                 encoding="utf-8")
    assert load_gazetteer_names(p) == {"Behala", "legacy", "Behela", "legacy alias"}
    p.write_text("[]")
    assert load_gazetteer_names(p) == frozenset()
    assert load_gazetteer_names(tmp_path / "missing.json") == frozenset()


# ── post-processing ──────────────────────────────────────────────────────────────────────────────────────────────


def test_plates_are_relabelled_and_left_out_by_default(guard):
    text = "A car, MH 01 AB 1234, hit the divider."
    raw = [_span(text, "MH 01 AB 1234", "account_number", 0.97)]
    assert postprocess(text, raw, guard=guard) == []
    out = postprocess(text, raw, guard=guard, labels=None)
    assert [(d["label"], text[d["start"] : d["end"]]) for d in out] == [(PLATE_LABEL, "MH 01 AB 1234")]


def test_contacts_survive_the_guard_and_mobiles_are_relabelled(guard):
    text = "Call 98200 41526 or 9820015577, or write to gnward.help@example.in near Dadar Station."
    raw = [
        _span(text, "98200 41526", "private_phone", 0.99),
        _span(text, "9820015577", "account_number", 0.99),
        _span(text, "gnward.help@example.in", "private_email", 0.99),
    ]
    out = postprocess(text, raw, guard=guard)
    assert [(d["label"], text[d["start"] : d["end"]]) for d in out] == [
        ("private_phone", "98200 41526"),
        ("private_phone", "9820015577"),
        ("private_email", "gnward.help@example.in"),
    ]


def test_short_public_numbers_and_letterless_names_are_dropped(guard):
    text = "Dial 112, BMC disaster control 1916 or ambulance (108); flights were 40 minutes late."
    raw = [
        _span(text, "112", "private_phone"),
        _span(text, "1916", "private_phone"),
        _span(text, "108", "private_phone"),
        _span(text, "40", "private_person"),
    ]
    assert postprocess(text, raw, guard=guard) == []


def test_score_floor_label_filter_and_merge(guard):
    text = "Mrs Sunita Patil said the drains were choked."
    raw = [
        _span(text, "Mrs Sunita", score=0.6),
        _span(text, "Sunita Patil", score=0.9),
        _span(text, "drains", "private_address", 0.9),
        _span(text, "choked", score=0.2),
    ]
    out = postprocess(text, raw, guard=guard)
    assert out == [{"start": 0, "end": len("Mrs Sunita Patil"), "label": "private_person", "score": 0.9}]
    assert postprocess(text, raw, guard=guard, min_score=0.95) == []
    assert len(postprocess(text, raw, guard=guard, labels=None, min_score=0.0)) == 3


def test_out_of_range_spans_are_ignored(guard):
    assert postprocess("abc", [RawSpan(5, 9, "private_person", 0.9), RawSpan(2, 1, "private_person", 0.9)],
                       guard=guard) == []


# ── detectors ────────────────────────────────────────────────────────────────────────────────────────────────────


def test_fake_detector_runs_the_real_post_processing():
    det = FakePiiDetector({"Sunil Jadhav": "private_person", "Senapati Bapat": "private_person"})
    texts = ["Driver Sunil Jadhav was hurt on Senapati Bapat Marg.", "", None]  # type: ignore[list-item]
    out = det.detect(texts)
    assert [_texts(t or "", o) for t, o in zip(texts, out, strict=True)] == [["Sunil Jadhav"], [], []]
    assert out[0][0]["score"] == 1.0 and det.calls == 1
    assert det.detect([]) == []


def test_detector_rejects_bad_configuration():
    with pytest.raises(ValueError, match="unknown labels"):
        FakePiiDetector(labels=("private_person", "face"))
    with pytest.raises(ValueError, match="min_score"):
        FakePiiDetector(min_score=1.5)


def test_unreviewed_model_code_is_refused_before_any_import(tmp_path):
    (tmp_path / "modeling_pii_masking.py").write_text("import os  # not the reviewed file\n")
    det = PiiTracerDetector(str(tmp_path), revision=None, guard=ToponymGuard(()))
    with pytest.raises(RuntimeError, match="reviewed"):
        det.load()
    assert not det.loaded


def test_raw_spans_chunks_long_texts_and_maps_offsets_back(monkeypatch):
    det = PiiTracerDetector(guard=ToponymGuard(()), batch_size=2)
    det._model = object()  # mocked: no load
    seen: list[str] = []

    def fake_infer(chunks):
        seen.extend(chunks)
        out = []
        for c in chunks:
            i = c.find("Sunil Jadhav")
            out.append([RawSpan(i, i + len("Sunil Jadhav"), "private_person", 0.9)] if i >= 0 else [])
        return out

    monkeypatch.setattr(det, "_infer", fake_infer)
    long_text = ("rain " * 400) + "driver Sunil Jadhav hurt " + ("rain " * 400)
    texts = ["Sunil Jadhav was hurt.", "", "   ", long_text]
    raw = det.raw_spans(texts)
    assert len(seen) >= 3 and all(len(c) <= pii.MAX_CHUNK_CHARS for c in seen)
    assert raw[1] == [] and raw[2] == []
    for t, spans in ((texts[0], raw[0]), (long_text, raw[3])):
        assert [t[s.start : s.end] for s in spans] == ["Sunil Jadhav"]
    out = det.detect(texts)
    assert [len(o) for o in out] == [1, 0, 0, 1]


# ── the real model (slow) ────────────────────────────────────────────────────────────────────────────────────────


def _real_model_available() -> bool:
    if importlib.util.find_spec("torch") is None or importlib.util.find_spec("transformers") is None:
        return False
    try:
        from huggingface_hub import try_to_load_from_cache
    except ImportError:
        return False
    hit = try_to_load_from_cache(pii.DEFAULT_MODEL_ID, "model.safetensors", revision=pii.DEFAULT_REVISION)
    return isinstance(hit, str) and os.path.isfile(hit)


@pytest.mark.slow
@pytest.mark.skipif(not _real_model_available(), reason="needs torch and the cached PII-Tracer snapshot")
def test_real_model_end_to_end():
    det = PiiTracerDetector(batch_size=4)
    try:
        texts = [
            "A bus broke down on Senapati Bapat Marg near Shivaji Park; driver Sunil Jadhav was unhurt.",
            "Contact the ward office at 98200 41526 to report a blocked drain on Annie Besant Road.",
        ]
        out = det.detect(texts)
        assert "Sunil Jadhav" in _texts(texts[0], out[0])
        assert not any("Senapati" in x or "Shivaji" in x for x in _texts(texts[0], out[0]))
        assert _texts(texts[1], out[1]) == ["98200 41526"]
    finally:
        det.unload()
