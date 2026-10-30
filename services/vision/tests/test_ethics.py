"""Roads and vehicles only: the person filter and the query screen, in code."""

from __future__ import annotations

import pytest

from vision_service.ethics import mentions_person, neutral_rationale, scrub, screen_query

# --- the output filter --------------------------------------------------------


@pytest.mark.parametrize("text", [
    "Two women in sarees wade through the water.",
    "A man wearing a yellow vest stands near the kerb.",
    "Pedestrians cross between the buses.",
    "An elderly person waits at the signal.",
    "A boy on a bicycle rides past.",
    "The rider has a red helmet.",
    "She is holding an umbrella.",
    "A crowd gathers near the pandal.",
    "Faces of the commuters are visible.",
    "A Muslim vendor sells fruit.",
    "The driver of the taxi is looking at his phone.",
])
def test_person_sentences_are_detected(text: str) -> None:
    assert mentions_person(text)


@pytest.mark.parametrize("text", [
    "Standing water covers the carriageway up to the wheel hubs.",
    "Dense traffic, cars and buses queued under the flyover.",
    "A fallen tree blocks two lanes.",
    "Headlights and damaged bodywork visible on the stalled bus.",  # not "head"/"body"
    "The road is clear; light traffic.",
])
def test_road_sentences_are_not_flagged(text: str) -> None:
    assert not mentions_person(text)


def test_scrub_drops_person_sentences_and_keeps_road_ones() -> None:
    raw = ("Water reaches the wheel hubs of the parked cars. Two men in yellow vests wade "
           "through it. A bus is stalled in the left lane.")
    out, removed = scrub(raw, "waterlogged")
    assert removed == 1
    assert out == "Water reaches the wheel hubs of the parked cars. A bus is stalled in the left lane."
    assert not mentions_person(out)


def test_scrub_falls_back_to_neutral_text_when_everything_is_about_people() -> None:
    out, removed = scrub("A woman in a red saree and her child cross the road.", "congested")
    assert removed == 1
    assert out == neutral_rationale("congested")
    assert not mentions_person(out)


def test_scrub_caps_at_25_words_keeping_whole_sentences() -> None:
    raw = ("Dense traffic queues across all four lanes under the flyover near the signal. "
           "Buses and taxis are stopped bumper to bumper with no movement visible at all for now.")
    out, _ = scrub(raw, "congested")
    assert len(out.split()) <= 25
    assert out.endswith(".")
    assert out.startswith("Dense traffic queues")


def test_scrub_never_returns_person_terms_for_real_unguarded_model_text() -> None:
    # verbatim from Qwen3-VL-8B asked, without the house prompt, to describe a fixture
    raw = ("In a flooded urban street, two men wearing bright yellow safety vests are wading "
           "through murky water, likely performing cleanup or inspection duties. One man holds "
           "a long pole, suggesting he's clearing debris or assessing the water level, while "
           "both appear focused on navigating the submerged roadway.")
    out, removed = scrub(raw, "waterlogged")
    assert removed == 2
    assert not mentions_person(out)
    assert out == neutral_rationale("waterlogged")


# --- the query screen ---------------------------------------------------------


@pytest.mark.parametrize("q", [
    "who is in this image",
    "Who is standing near the bus?",
    "Describe the people in this picture",
    "How old is the man on the left?",
    "What is the woman wearing?",
    "Is that a girl or a boy?",
    "Count the pedestrians",
    "identify the driver",
    "ছবিতে কে আছে?",
    "এই মহিলা কী পরেছেন?",
    "इस फोटो में कौन है?",
    "आदमी की उम्र क्या है?",
    "या फोटोमध्ये कोण आहे?",
    "या माणसाचे वय किती आहे?",
    "ती बाई कोणते कपडे घातले आहे?",
    "पादचाऱ्यांची संख्या सांगा",
    "या फोटोत किती लोक आहेत?",
    "प्रवाशांचे चेहरे दिसतात का?",
])
def test_person_questions_are_refused(q: str) -> None:
    r = screen_query(q)
    assert not r.allowed
    assert r.policy == "vehicles-and-roads-only"


@pytest.mark.parametrize("q", [
    "Read the number plate of the yellow taxi",
    "what is the licence plate?",
    "গাড়ির নম্বর কত?",
    "नंबर प्लेट पढ़ो",
    "गाडीचा नंबर वाचा",
    "या टॅक्सीचा नोंदणी क्रमांक काय आहे?",
])
def test_plate_questions_are_refused_and_routed_to_anpr(q: str) -> None:
    r = screen_query(q)
    assert not r.allowed
    assert r.policy == "no-plate-reading"
    assert "ANPR" in (r.reason or "")


@pytest.mark.parametrize("q", [
    None,
    "",
    "Is the road passable for buses?",
    "How deep is the water on the carriageway?",
    "রাস্তাকে কি জল জমেছে?",  # "-কে" is a case ending here, not "who"
    "क्या सड़क पर पानी भरा है?",
    "रस्त्यावर पाणी साचले आहे का?",
    "लोकल बंद झाल्यावर रस्ता मोकळा आहे का?",  # "लोकल" (the local train) is not "लोक"
    "कोणता रस्ता बंद आहे?",  # "which road", not "who"
    "बेस्ट बस या सबवेतून जाऊ शकते का?",
])
def test_road_questions_are_allowed(q: str | None) -> None:
    assert screen_query(q).allowed
