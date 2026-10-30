"""Kind and severity rules (Marathi, Hindi, English, romanised)."""

from __future__ import annotations

import pytest

from speech_service.kinds import KINDS, classify


@pytest.mark.parametrize("text,kind", [
    ("हिंदमाता येथे गुडघाभर पाणी साचले आहे, बस अडकल्या आहेत", "waterlogging"),
    ("अंधेरी सबवे में पानी भर गया है", "waterlogging"),
    ("Knee-deep water at Hindmata, buses stuck", "waterlogging"),
    ("Andheri subway band hai, paani bhar gaya", "waterlogging"),
    ("सायन सर्कलवर प्रचंड वाहतूक कोंडी", "jam"),
    ("कलानगर के पास भारी जाम है", "jam"),
    ("Massive traffic jam on the Western Express Highway", "jam"),
    ("दादर टीटीजवळ दोन गाड्यांची धडक", "accident"),
    ("बीकेसी में दो गाड़ियों की टक्कर", "accident"),
    ("Collision between a taxi and a bus at Worli Naka", "accident"),
    ("किंग्ज सर्कलजवळ झाड पडले, रस्ता बंद", "tree_fall"),
    ("पवई में पेड़ गिर गया है", "tree_fall"),
    ("Fallen tree across both lanes", "tree_fall"),
    ("घाटकोपर येथे बॅरिकेड लावून रस्ता बंद", "blockade"),
    ("लालबाग येथे विसर्जन मिरवणूक सुरू आहे", "procession"),
    ("गिरगांव चौपाटी की तरफ विसर्जन जुलूस", "procession"),
    ("Immersion procession at Girgaon Chowpatty", "procession"),
    ("चेंबूर येथे दुकानाला आग लागली", "fire"),
    ("परेल में इमारत में आग लगी है", "fire"),
    ("वरळी नाक्यावर विजेची तार तुटून पडली आहे", "live_wire"),
    ("हाजी अली पर बिजली का तार टूटकर गिरा", "live_wire"),
    ("Live wire hanging over the road at Haji Ali", "live_wire"),
    ("माहीम कॉजवेवर एक बस बंद पडली आहे", "other"),
    # typed in Latin letters, the way a phone keyboard often gets it
    ("Sion circle la khup traffic aahe", "jam"),
    ("kings circle jawal zaad padla", "tree_fall"),
    ("Milan subway madhe pani bharla", "waterlogging"),
])
def test_kind(text: str, kind: str) -> None:
    c = classify(text)
    assert c.kind == kind, c
    assert c.kind in KINDS
    if kind != "other":
        assert c.kind_cues, "the officer sees which words decided the label"


def test_jam_is_a_symptom_when_a_cause_is_reported() -> None:
    assert classify("पाणी साचल्यामुळे प्रचंड वाहतूक कोंडी").kind == "waterlogging"
    assert classify("झाड पडल्यामुळे वाहतूक कोंडी").kind == "tree_fall"
    assert classify("पेड़ गिरने से भारी जाम").kind == "tree_fall"


def test_ahead_is_not_fire() -> None:
    # "आगे" (Hindi: ahead) starts with "आग" (fire): only the whole word counts
    c = classify("आगे भारी जाम है")
    assert c.kind == "jam"
    assert "fire" not in c.scores


def test_east_is_not_a_flood() -> None:
    # "पूर्व" (East) starts with "पूर" (flood): no flood is read into a place name
    assert classify("दादर पूर्व येथे गर्दी").kind == "other"


def test_single_weak_word_is_not_a_label() -> None:
    assert classify("रस्त्यावर पाणी").kind == "other"
    assert classify("सड़क पर पानी").kind == "other"


@pytest.mark.parametrize("text,severity", [
    ("मिलन सबवेमध्ये घोट्याइतके पाणी", "low"),
    ("हिंदमाता येथे गुडघाभर पाणी साचले आहे, बस अडकल्या आहेत", "medium"),
    ("मिलन सबवेमध्ये कमरेइतके पाणी भरले आहे", "high"),
    ("मिलन सबवे में कमर तक पानी भर गया है", "high"),
    ("दादर टीटीजवळ अपघात, एक जण जखमी", "high"),
    ("लालबाग येथे मिरवणूक", "low"),
    ("लालबाग येथे मिरवणूक, रस्ता बंद", "medium"),
    ("चेंबूर येथे आग", "high"),
    ("थोडा धुआं, मामूली आग", "high"),  # fire never drops below high
    ("Minor jam near Sion", "low"),
])
def test_severity(text: str, severity: str) -> None:
    assert classify(text).severity == severity


@pytest.mark.parametrize("text,kind", [
    ("रस्त्यावर पाणी नाही, पण प्रचंड वाहतूक कोंडी", "jam"),
    ("सड़क पर पानी नहीं है, भारी जाम है", "jam"),
    ("No water on the road, heavy traffic jam", "jam"),
    ("पाणी साचले नाही", "other"),
    ("जाम नहीं है", "other"),
    ("road not blocked, slow traffic", "other"),
])
def test_negated_cues_do_not_count(text: str, kind: str) -> None:
    assert classify(text).kind == kind


@pytest.mark.parametrize("text,kind", [
    ("सायन सर्कलवर वाहतुक कोन्डी", "jam"),                # ASR spelling of वाहतूक कोंडी
    ("लालबाग येथे विसरजन सुरू", "procession"),           # halant dropped
    ("कुर्ला स्टेशन के पास दुरघटना हुई", "accident"),     # halant dropped (Hindi)
])
def test_asr_misspelt_strong_cues_still_count_and_say_so(text: str, kind: str) -> None:
    c = classify(text)
    assert c.kind == kind, c
    assert any(cue.endswith("(≈)") for cue in c.kind_cues)


def test_fuzzy_cues_do_not_invent_hazards() -> None:
    assert classify("ऑफिस सुटल्यावर गाड्या पुढे सरकत नाहीत, वाहतूक कोंडी").kind == "jam"
    assert classify("पाणी साचले नाही").kind == "other"


def test_one_cue_in_two_spellings_is_one_cue() -> None:
    # the Marathi and Hindi spellings of "barricade" are one cue, not two
    c = classify("घाटकोपर येथे बॅरिकेड लावून रस्ता बंद केला आहे")
    assert not any(cue.endswith("(≈)") for cue in c.kind_cues), c.kind_cues
