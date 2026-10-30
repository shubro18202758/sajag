"""Parse-time redaction: synthetic names and ages are redacted, ``find_pii`` is clean on every emitted title and
text, gazetteer toponyms survive, ``raw`` holds no person value, and no real person's name is in any file of
this package (the PoC-name scan, which keeps the names in memory and prints only sha256 prefixes)."""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import pytest
from conftest import PACKAGE, POC_RAW, POC_SOURCE, URL_HANDLE_PROBES, h12, needs_poc, parse_cache

import osint_ingress.connectors._redact as redact_module
from osint_common import ethics
from osint_ingress.cache import Cache
from osint_ingress.connectors import build_connectors
from osint_ingress.connectors._redact import (
    TOKENS,
    DocumentRedactor,
    has_poster_handle,
    has_url,
    redact_persons,
)
from osint_ingress.importer import import_capture

#: The fictional names and ages planted in the synthetic capture (never real people).
SYNTHETIC_NAMES = ("Fictus Dummyvala", "Kalpit Exemplar", "Zara Placeholderi", "Vimal Fixturebhai", "Rohan Fictionwala",
                   "Testa Exampleson", "काल्पनिक नमुनेकर")
SYNTHETIC_AGES = ("34-year-old", "80-year-old", ", 52,", ", 71,", "(६०)")
#: The fictional bylines of the synthetic outlet feeds (``dc:creator``, ``content:encoded``): never read.
SYNTHETIC_BYLINES = ("Synthetic Byline Reporterwala", "Reporterwala")


def _all(capture_cache, connectors, protect):
    return [s for sigs in parse_cache(capture_cache, connectors, protect).values() for s in sigs]


def test_synthetic_names_and_ages_are_redacted(capture_cache, connectors, protect):
    sigs = _all(capture_cache, connectors, protect)
    blob = json.dumps([s.model_dump(mode="json") for s in sigs], ensure_ascii=False)
    for name in SYNTHETIC_NAMES:
        assert name not in blob
        assert name.split()[1] not in blob  # not even the surname alone
    for age in SYNTHETIC_AGES:
        assert age not in blob
    for byline in SYNTHETIC_BYLINES:
        assert byline not in blob
    assert blob.count("[PERSON]") >= 6 and blob.count("[AGE]") >= 5
    total = sum(s.pii_redactions for s in sigs)
    # pii_redactions counts every token written: [PERSON], [AGE], [CONTACT], [URL] and [WITHHELD] (Indic-script
    # words no rule can read for names)
    assert set(TOKENS) == {"[PERSON]", "[AGE]", "[CONTACT]", "[URL]", "[WITHHELD]"}
    assert total == sum(s.title.count(t) + s.text.count(t) for s in sigs for t in TOKENS)
    assert total > 0


def test_find_pii_is_clean_on_every_emitted_title_and_text(capture_cache, connectors, protect):
    sigs = _all(capture_cache, connectors, protect)
    assert sigs
    for s in sigs:
        assert ethics.find_pii(s.title) == [] and ethics.find_pii(s.text) == []
        for v in s.raw.values():
            assert not isinstance(v, str) or ethics.find_pii(v) == []


@pytest.mark.parametrize(
    "text",
    [
        "Accused named Mr R. K. Fictuswala, 45, held after the scuffle",
        "Victim Testo Exampleson (34) was taken to hospital",
        "Shri Fic\u200btus Dum\u200bmyvala inaugurates the hall",  # zero-width characters inside the name
        "Ｍｒ Ｆｉｃｔｕｓ Ｅｘａｍｐｌｅ visited",  # fullwidth letters
        "A 61 yrs old resident of Fictuspur and the deceased Fixtura Dummy",
        "Constable Placeholdra Singhvala and ASI Testa Example reached the spot",
    ],
)
def test_redaction_always_passes_find_pii(protect, text):
    for tier in ("news_regional", "official", "social_unverified"):
        out, n = redact_persons(text, tier, protect)
        assert ethics.find_pii(out) == [] and n > 0, (tier, out)


def test_toponyms_in_the_protect_set_survive(capture_cache, connectors, protect, tmp_path):
    sigs = _all(capture_cache, connectors, protect)
    blob = " ".join(s.title + " " + s.text for s in sigs)
    for place in ("Western Express Highway", "Andheri", "Dadar TT circle", "Lalbaug flyover", "Wankhede Stadium",
                  "Matunga", "Bandra", "Dadar", "Matunga school", "CSMT", "Girgaon"):
        assert place in blob, place
    from conftest import PAGES

    from osint_ingress.connectors.official import BmcPage

    page = Cache(tmp_path).put("kmc_scrape", (PAGES / "bmc_home_synthetic.html").read_bytes(), "html")
    titles = " ".join(s.title for s in BmcPage().parse(page, protect))
    assert "Dadar TT stretch" in titles
    # after a residence cue, a gazetteer place is not a name (the contract's check reads the shared gazetteer: until
    # it holds the place, the place is redacted too rather than the whole signal refused)
    out, n = redact_persons("A resident of Shivaji Park said the lane flooded", "news_regional", protect)
    if "shivaji park" in ethics.place_phrases():
        assert "Shivaji Park" in out and n == 0
    else:
        assert out == "A resident of [PERSON] said the lane flooded" and ethics.find_pii(out) == []
    # Mumbai's places named after people survive the surname and honorific rules (the city pack's protect phrases)
    for place in ("Senapati Bapat Marg", "Bhulabhai Desai Road", "Lokmanya Tilak Terminus", "Acharya Atre Chowk",
                  "Gokhale Bridge", "P D'Mello Road", "Haji Ali", "Mahalaxmi", "Annie Besant Road"):
        out, n = redact_persons(f"Waterlogging reported on {place} after the downpour", "news_regional", protect)
        assert place in out and n == 0, out
    # a place after an honorific ("Dr. Ambedkar Road") survives once the shared gazetteer, which the contract's
    # check reads, holds it; until then it is redacted (stricter), never refused at validation
    text = "Dr. Ambedkar Road closed; Dr.Ambedkar Road diversions"
    out, _n = redact_persons(text, "news_regional", protect)
    assert ethics.find_pii(out) == []
    if "dr ambedkar road" in ethics.place_phrases():
        assert out == text
    out, n = redact_persons("Residents near Wankhede Stadium reported the crash", "social_unverified", protect)
    assert "Wankhede Stadium" in out and n == 0


def test_social_runs_keep_places_and_ordinary_words_but_not_names():
    protect = frozenset({"fictus memorial stadium", "king s circle", "matunga"})
    cases = {
        "Match tonight at Fictus Memorial Stadium, avoid the stretch": "Fictus Memorial Stadium",  # a place phrase
        "Weekend Live Chat thread for the city": "Weekend Live Chat",  # ordinary words
        "Visit Matunga with family this weekend": "Matunga",  # a lone gazetteer alias
    }
    for text, kept in cases.items():
        out, _ = redact_persons(text, "social_unverified", protect)
        assert kept in out, out
    # a place noun keeps itself, never the name before it: "<Name> Road" survives only as a gazetteer phrase
    out, n = redact_persons("Traffic jam near Fixture Road since morning", "social_unverified", protect)
    assert out == "Traffic jam near [PERSON] Road since morning" and n == 1
    # the leading words of a place phrase, without the rest of the phrase, are a name
    out, n = redact_persons("Fictus Memorial spoke at the rally", "social_unverified", protect)
    assert out.startswith("[PERSON] spoke") and n == 1
    # three capitalised name words cannot leave a third one behind
    out, n = redact_persons("Thanks to Rohana Fictus Exampleton for the help", "social_unverified", protect)
    assert "Exampleton" not in out and "Fictus" not in out and n == 1
    # news tier: no capitalised-run rule (Title Case headlines stay readable)
    out, n = redact_persons("Fixture Kiosk Opens At Riverfront", "news_regional", protect)
    assert out == "Fixture Kiosk Opens At Riverfront" and n == 0


#: Fictional names (never real people) right before place nouns, several words deep: the review-r1 probes. Each
#: case lists the name words that must not survive. "Nagar" is a place noun AND a Marathi surname.
PLACE_NOUN_PROBES = [
    ("Ask Fictus Dummyvala School Principal about the timings", ("Fictus", "Dummyvala")),
    ("Accident Near Kalpit Exemplar Residence Ring Road this morning", ("Kalpit", "Exemplar")),
    ("Zara Placeholderi Road blocked again near the bridge", ("Zara", "Placeholderi")),
    ("Vimal Fixturebhai Club party tonight, avoid the lane", ("Vimal", "Fixturebhai")),
    ("Please Call Rohan Fictionwala Market Side for the keys", ("Rohan", "Fictionwala")),
    ("Fictus Dummyvala Nagar Society meeting at the hall", ("Fictus", "Dummyvala")),
    ("Thanks Kalpit Exemplar Shivaji Park residents for the help", ("Kalpit", "Exemplar")),
    ("Lost dog near Zara Placeholderi Garden Lane, please share", ("Zara", "Placeholderi")),
    ("Ask Testo Nagar about the plot near the temple", ("Testo", "Nagar")),
    ("Shoutout to Vimal Rohan Fixturebhai Hospital Road staff", ("Vimal", "Rohan", "Fixturebhai")),
]


@pytest.mark.parametrize(("text", "name_words"), PLACE_NOUN_PROBES)
def test_a_place_noun_never_vouches_for_the_name_before_it(protect, text, name_words):
    out, n = redact_persons(text, "social_unverified", protect)
    assert n >= 1 and "[PERSON]" in out, out
    for word in name_words:
        assert not re.search(rf"\b{word}\b", out), (word, out)
    assert ethics.find_pii(out) == []


def test_social_tier_still_keeps_gazetteer_places_next_to_place_nouns(protect):
    text = "Jam near Shivaji Park and Wankhede Stadium, King's Circle is clear"
    out, n = redact_persons(text, "social_unverified", protect)
    assert out == text and n == 0


@pytest.mark.parametrize(
    ("text", "handle"),
    [
        ("DM @fictus_handle on insta for details", "fictus_handle"),
        ("Thanks @kalpit.exemplar. Great pics", "kalpit.exemplar"),
        ("cc @Zara_Placeholderi, she saw it", "Zara_Placeholderi"),
    ],
)
def test_social_at_handles_are_redacted(text, handle):
    out, n = redact_persons(text, "social_unverified", frozenset())
    assert handle not in out and "@" not in out and "[PERSON]" in out and n >= 1, out
    assert ethics.find_pii(out) == []


@pytest.mark.parametrize(
    "text",
    ["Ask @Fictus Dummyvala about the plot", "Ask u/Fictus Dummyvala about the plot"],
)
def test_a_handle_followed_by_a_name_leaves_no_name_word(text):
    """The handle span and the capitalised run overlap: they are joined, never one dropped for the other."""
    out, n = redact_persons(text, "social_unverified", frozenset())
    assert out == "Ask [PERSON] about the plot" and n == 1, out


def test_the_at_handle_rule_spares_emails_times_and_the_news_tier():
    out, _ = redact_persons("Mail fictus@example.com or meet @5pm near the gate, not @10:30", "social_unverified",
                            frozenset())
    assert "[CONTACT]" in out and "@5pm" in out and "@10:30" in out and "[PERSON]" not in out, out
    out, n = redact_persons("Commuters told to follow @CityTrafficDesk for diversions", "news_regional", frozenset())
    assert out.endswith("@CityTrafficDesk for diversions") and n == 0


@pytest.mark.parametrize(("text", "handle", "expected"), URL_HANDLE_PROBES)
@pytest.mark.parametrize("tier", ["social_unverified", "aggregator", "news_regional", "archive"])
def test_a_handle_inside_a_url_never_survives(text, handle, expected, tier):
    """Every non-official tier: a Reddit user page becomes [PERSON], any other URL [URL]; nothing of the path
    is left, and the parity detectors find no handle and no URL afterwards."""
    out, n = redact_persons(text, tier, frozenset())
    assert out == expected and n == 1, out
    assert handle not in out and not has_url(out) and not has_poster_handle(out, tier)
    assert ethics.find_pii(out) == []
    # ...and before redaction the same detectors see the handle (the checks are not vacuous)
    assert has_url(text) and has_poster_handle(text, tier)


def test_every_url_form_is_redacted_outside_the_official_tier():
    cases = {
        "Read more at https://news-a.example/2026/10/fictus-dummyvala-arrested-near-sealdah": "Read more at [URL]",
        "Pics (preview.redd.it/abc123.jpg?width=640) of the jam": "Pics ([URL]) of the jam",
        "Old thread: old.reddit.com/r/u_fictus_dummyvala/comments/x1": "Old thread: [PERSON]",
        "Petition at www.news-b.example, sign it": "Petition at [URL], sign it",
        "Channel: youtube.com/@FictusDummyvalaVlogs!": "Channel: [URL]!",
    }
    for text, expected in cases.items():
        assert redact_persons(text, "social_unverified", frozenset()) == (expected, 1), text
    # what is not a URL stays: fractions, units, "and/or", times, e-mail-free text
    for text in ("Open 24/7 near the BRTS lane", "Speed checks at 60 km/h, fines and/or towing",
                 "Meet at 5.30 p.m. near the gate"):
        assert redact_persons(text, "social_unverified", frozenset()) == (text, 0), text


def test_official_sources_keep_their_identifier_urls():
    text = "Details: https://sachet.ndma.gov.in/cap_public_website/FetchXMLFile?identifier=1.2.3"
    assert redact_persons(text, "official", frozenset()) == (text, 0)
    # an office's own account in an official alert is no poster handle; in a post the same link would be one
    office = "Updates on https://x.com/SyntheticDistrictEOC"
    assert redact_persons(office, "official", frozenset()) == (office, 0)
    assert not has_poster_handle(office, "official") and has_poster_handle(office, "social_unverified")


#: Reddit user mentions and pages written into a news, GDELT or official text (the review-r3 must-fix probes;
#: fictional handles only): ``(text, handle, redacted text)``. Every form ``has_poster_handle`` reads in any tier:
#: ``u/``, ``/u/``, ``/user/``, ``r/u_`` and a user page on a reddit.com host, with and without a scheme.
REDDIT_USER_PROBES = [
    ("Reddit user u/fictus_dummyvala films waterlogging near Dadar", "fictus_dummyvala",
     "Reddit user [PERSON] films waterlogging near Dadar"),
    ("Viral clip by /u/kalpit_exemplar shows a crash at King's Circle", "kalpit_exemplar",
     "Viral clip by [PERSON] shows a crash at King's Circle"),
    ("Video posted by /user/zara_placeholderi shows the flooded underpass", "zara_placeholderi",
     "Video posted by [PERSON] shows the flooded underpass"),
    ("Photos shared on r/u_vimal_fixturebhai show the jam near Dadar", "vimal_fixturebhai",
     "Photos shared on [PERSON] show the jam near Dadar"),
    ("Footage at reddit.com/u/rohan_fictionwala shows the jam", "rohan_fictionwala",
     "Footage at [PERSON] shows the jam"),
    ("Thread: https://old.reddit.com/user/fictus_dummyvala/comments/x1/jam_near_sealdah/ has the photos",
     "fictus_dummyvala", "Thread: [PERSON] has the photos"),
    ("Clip (www.reddit.com/r/u_kalpit_exemplar) shows the crash", "kalpit_exemplar",
     "Clip ([PERSON]) shows the crash"),
]
#: Every source tier: GDELT events (news_wire), GDELT DOC (news_regional), Google News (aggregator), Common Crawl
#: (archive), SACHET/IMD/the traffic police notices (official) and Reddit (social_unverified).
ALL_TIERS = ["news_wire", "news_regional", "aggregator", "archive", "official", "social_unverified"]


@pytest.mark.parametrize(("text", "handle", "expected"), REDDIT_USER_PROBES)
@pytest.mark.parametrize("tier", ALL_TIERS)
def test_a_reddit_user_mention_is_redacted_in_every_tier(protect, text, handle, expected, tier):
    """Review-r3 must-fix: a Reddit user mention or page is a poster handle in ANY tier (``has_poster_handle``
    says so), so every tier redacts it to [PERSON], the mention form exactly as the URL form."""
    assert has_poster_handle(text, tier)  # the detector sees it before redaction (the check is not vacuous)
    out, n = redact_persons(text, tier, protect)
    assert out == expected and n == 1, out
    assert handle not in out and not has_poster_handle(out, tier)
    assert ethics.find_pii(out) == []


def test_an_official_alert_keeps_its_url_but_never_a_reddit_user():
    text = ("Advisory https://sachet.ndma.gov.in/cap_public_website/FetchXMLFile?identifier=1.2.3 cites photos by "
            "u/fictus_dummyvala and reddit.com/user/kalpit_exemplar")
    out, n = redact_persons(text, "official", frozenset())
    assert out == ("Advisory https://sachet.ndma.gov.in/cap_public_website/FetchXMLFile?identifier=1.2.3 cites photos "
                   "by [PERSON] and [PERSON]") and n == 2, out
    assert not has_poster_handle(out, "official")
    # what only looks like a mention stays: a legal "u/s" reference, units, an official URL path
    for keep in ("Order u/s 144 in force near Dadar", "Winds 40 km/h near Dadar",
                 "See https://www.kmcgov.in/user/manual for the drill"):
        assert redact_persons(keep, "official", frozenset()) == (keep, 0), keep


#: A minimal RSS 2.0 document around ``items``.
_RSS = ('<?xml version="1.0" encoding="UTF-8"?>'
        '<rss version="2.0"><channel><title>synthetic</title>{items}</channel></rss>')


def _strings(obj) -> list[str]:
    """Every string value in a dumped signal, at any depth."""
    if isinstance(obj, str):
        return [obj]
    if isinstance(obj, dict):
        return [s for v in obj.values() for s in _strings(v)]
    if isinstance(obj, list | tuple):
        return [s for v in obj for s in _strings(v)]
    return []


def test_reddit_user_mentions_never_reach_a_news_gdelt_or_official_signal(tmp_path, protect):
    """Review-r3 must-fix, end to end: a Reddit user mention or page in a Google News headline (aggregator), a
    GDELT DOC title (news_regional) or a SACHET alert (official) is emitted as [PERSON]. No field of any emitted
    signal keeps the handle, ``find_pii`` is clean, and the parity checks count no poster handle."""
    from html import escape

    from osint_ingress.connectors.gdelt import GdeltDoc
    from osint_ingress.connectors.google_news import GoogleNews
    from osint_ingress.connectors.official import Sachet
    from osint_ingress.runner import signal_checks

    texts = [escape(t, quote=False) for t, _h, _e in REDDIT_USER_PROBES]
    gnews = "".join(
        f"<item><title>{t} - Outlet A</title>"
        f"<link>https://news.google.com/rss/articles/SYNTHETIC-GNEWS-77{i:02d}?oc=5</link>"
        f'<guid isPermaLink="false">SYNTHETIC-GNEWS-77{i:02d}</guid><pubDate>Tue, 20 Oct 2026 13:40:00 GMT</pubDate>'
        f'<description>{t}</description><source url="https://news-a.example">Outlet A</source></item>'
        for i, t in enumerate(texts)
    )
    gnews = _RSS.format(items=gnews)
    doc = {"articles": [
        {"url": f"https://news-b.example/city/mumbai/viral-clip-{i}", "title": t, "seendate": "20261020T100000Z",
         "domain": "news-b.example", "language": "English", "sourcecountry": "India"}
        for i, (t, _h, _e) in enumerate(REDDIT_USER_PROBES)
    ]}
    sachet = "".join(
        f"<item><title>Heavy rain likely at isolated places over Mumbai in next 3 hours.</title>"
        f"<description>{t}</description><category>Met</category>"
        f"<link>https://sachet.ndma.gov.in/cap_public_website/FetchXMLFile?identifier=19990000000077{i:02d}</link>"
        f'<guid isPermaLink="false">19990000000077{i:02d}</guid><pubDate>Tue, 20 Oct 2026 12:00:00 GMT</pubDate></item>'
        for i, t in enumerate(texts)
    )
    sachet = _RSS.format(items=sachet)
    cache = Cache(tmp_path)
    cases = [
        (GoogleNews(), cache.put("google_news_rss", gnews.encode("utf-8"), "xml"), "aggregator"),
        (GdeltDoc(), cache.put("gdelt_doc", json.dumps(doc).encode("utf-8"), "json"), "news_regional"),
        (Sachet(), cache.put("sachet_cap", sachet.encode("utf-8"), "xml"), "official"),
    ]
    handles = [h for _t, h, _e in REDDIT_USER_PROBES]
    for conn, entry, tier in cases:
        sigs = conn.parse(entry, protect)
        assert len(sigs) == len(REDDIT_USER_PROBES) and {s.source_tier for s in sigs} == {tier}, conn.name
        blob = json.dumps([s.model_dump(mode="json") for s in sigs], ensure_ascii=False)
        for h in handles:
            assert h not in blob, (conn.name, h)
        for s in sigs:
            assert "[PERSON]" in s.text and s.pii_redactions >= 1, (conn.name, s.text)
            assert ethics.find_pii(s.title) == [] and ethics.find_pii(s.text) == []
            for v in _strings(s.model_dump(mode="json")):
                assert not has_poster_handle(v, tier), (conn.name, v)
            if tier == "official":
                assert s.url and s.url.startswith("https://sachet.ndma.gov.in/")  # identifier URLs are kept
            else:
                assert "[PERSON]" in s.title and s.url is None
        checks = signal_checks(sigs)
        assert checks["with_poster_handle"] == 0 and checks["find_pii_clean"] == len(sigs), (conn.name, checks)
        # ...and the same check counts a mention left in the title (the check is not vacuous in this tier)
        leaked = [sigs[0].model_copy(update={"title": REDDIT_USER_PROBES[0][0]})]
        assert signal_checks(leaked)["with_poster_handle"] == 1, conn.name


#: News-tier forms past where the shared cue spans stop (review-r2 should-fix and the OS-1 cases); fictional names.
NEWS_NAME_PROBES = [
    ("Mr Fictus Kalpitbhai Dummyvala Exampleton was arrested near Dadar", "Mr [PERSON] was arrested near Dadar"),
    ("Inspector Fictus D. Dummyvala said the road is clear", "Inspector [PERSON] said the road is clear"),
    ("PSI Fictus Dummyvala-Exampleton registered the FIR", "PSI [PERSON] registered the FIR"),
    ("Fictus Dummyvala, 45, was injured near Dadar", "[PERSON], [AGE], was injured near Dadar"),
    ("Fictus Dummyvala (45) was injured near Dadar", "[PERSON] ([AGE]) was injured near Dadar"),
    ("Fictus Dummyvala, aged 45, was injured", "[PERSON], [AGE], was injured"),
    ("Fictus Dummyvala, a 45-year-old resident of Dadar, was hurt", "[PERSON], a [AGE] resident of Dadar, was hurt"),
    ("Fictus Engineer, 45, was injured", "[PERSON], [AGE], was injured"),  # an occupational surname stays in
    ("Senior Citizen Fictus Dummyvala, 80, Robbed Near Dadar", "Senior Citizen [PERSON], [AGE], Robbed Near Dadar"),
    ("The victim, Fictus Dummyvala, was taken to hospital", "The victim, [PERSON], was taken to hospital"),
    ("Police identified the deceased as Fictus Dummyvala", "Police identified the deceased as [PERSON]"),
    ("Mr.Fictus Dummyvala visited the site", "Mr.[PERSON] visited the site"),
    ("Accused Fictus Rameshbhai Dummyvala Exampleton held", "Accused [PERSON] held"),
    ("Accused Fictus Dummyvala Arrested Near Dadar", "Accused [PERSON] Arrested Near Dadar"),
    ("A man aged about 60 was found near Dadar", "A man [AGE] was found near Dadar"),
    ("Fictus Dummyvala, 45 years of age, was hurt", "[PERSON], [AGE], was hurt"),
]


@pytest.mark.parametrize(("text", "expected"), NEWS_NAME_PROBES)
@pytest.mark.parametrize("tier", ["news_regional", "aggregator"])
def test_news_tier_names_past_the_shared_cue_spans(protect, tier, text, expected):
    out, _n = redact_persons(text, tier, protect)
    if "resident of Dadar" in expected and "dadar" not in ethics.place_phrases():
        # the contract's own check reads the shared gazetteer only: until it holds Dadar, the place after the
        # residence cue is redacted too (stricter), never left for validation to refuse
        expected = expected.replace("resident of Dadar", "resident of [PERSON]")
    assert out == expected, out
    assert ethics.find_pii(out) == []


#: Title-Case headlines and place phrases the extra rules must leave alone (role and headline words, gazetteer
#: places after an honorific, an age with only context words before it).
NEWS_CONTROLS = [
    ("Elderly Woman, 80, Dies After Fall Near Dadar", "Elderly Woman, [AGE], Dies After Fall Near Dadar"),
    ("Mumbai Man, 45, Killed In Crash On Western Express Highway",
     "Mumbai Man, [AGE], Killed In Crash On Western Express Highway"),
    ("Kurla Resident, 45, Booked For Rash Driving", "Kurla Resident, [AGE], Booked For Rash Driving"),
    ("Accused Held For Robbery In Kurla", "Accused Held For Robbery In Kurla"),
    ("Victim Dies In Hospital After Crash Near Sion Circle",) * 2,
    ("The accused, Police said, fled towards Kurla", "The accused, Police said, fled towards Kurla"),
]


@pytest.mark.parametrize(("text", "expected"), NEWS_CONTROLS)
def test_news_tier_extra_rules_leave_headlines_and_places_alone(protect, text, expected):
    # a road named after a doctor is a place when the gazetteer knows the phrase (here added to the set)
    places = protect | {"dr suresh sarkar road", "suresh sarkar road"}
    assert redact_persons(text, "aggregator", places)[0] == expected


@pytest.mark.parametrize(
    "text",
    [
        "Fictus K. Dummyvala hit my car near the gate",
        "R. K. Dummyvala hit my car near the gate",
        "Shoutout to Fictus R.K. Dummyvala for the help",
    ],
)
def test_initials_inside_a_social_run_leave_no_name_word(text):
    out, n = redact_persons(text, "social_unverified", frozenset())
    assert "Fictus" not in out and "Dummyvala" not in out and n == 1, out
    assert re.search(r"\b[A-Z]\.", out) is None, out  # the initials went with the name


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Fictus-Dummyvala runs the shop near the gate", "[PERSON] runs the shop near the gate"),
        ("Fictus de Dummyvala lost his bike near the gate", "[PERSON] lost his bike near the gate"),
        ("Thanks Kalpit bin Exemplar for the lift", "Thanks [PERSON] for the lift"),
        # a spaced " - " is a separator, and a particle needs a name on both sides
        ("Dadar - Fictus said the road is closed", "Dadar - Fictus said the road is closed"),
        ("Jam from Dadar to Kurla de tour", "Jam from Dadar to Kurla de tour"),
    ],
)
def test_hyphenated_and_particle_names_are_one_social_run(protect, text, expected):
    assert redact_persons(text, "social_unverified", protect)[0] == expected


def test_initials_next_to_place_words_stay_in_a_social_post(protect):
    text = "S. V. Road is jammed again, avoid Shivaji Park and Matunga"
    assert redact_persons(text, "social_unverified", protect) == (text, 0)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("my insta: fictus.dummyvala , dm for pics", "my insta: [PERSON] , dm for pics"),
        ("IG id - kalpit_exemplar", "IG id - [PERSON]"),
        ("snapchat: @zara.placeholderi", "snapchat: [PERSON]"),
        ("ig: link in bio", "ig: link in bio"),  # what follows the cue is no handle
        ("fb page: Mumbai Traffic updates", "fb page: Mumbai Traffic updates"),
    ],
)
def test_platform_cue_handles_in_a_social_post(text, expected):
    out, _n = redact_persons(text, "social_unverified", frozenset())
    assert out == expected, out
    assert not has_poster_handle(out, "social_unverified")


def test_title_case_cue_names_are_learned_for_the_whole_document(protect):
    doc = DocumentRedactor("aggregator", protect)
    items = ["Accused Fictus Dummyvala held for robbery in Kurla", "Fictus Dummyvala Sent To Jail"]
    doc.learn(*items)
    assert [doc.redact(t)[0] for t in items] == ["Accused [PERSON] held for robbery in Kurla", "[PERSON] Sent To Jail"]


def test_names_learned_in_a_document_are_redacted_everywhere_in_it(protect):
    doc = DocumentRedactor("news_regional", protect)
    first = "Content creator Testa Placeholderwala sent to jail".replace("Content", "content")
    second = "Court hears the case of testa placeholderwala today"  # no cue, lower case
    doc.learn(first, second)
    a, na = doc.redact(first)
    b, nb = doc.redact(second)
    assert "Placeholderwala" not in a and "placeholderwala" not in b and na == nb == 1
    # without the document context the second text has no cue and stays unredacted (the NER limit)
    plain, n = redact_persons(second, "news_regional", protect)
    assert n == 0 and plain == second


def test_raw_holds_no_person_value(capture_cache, connectors, protect):
    for s in _all(capture_cache, connectors, protect):
        assert set(s.raw) <= ethics.RAW_ALLOWED_KEYS
        ethics.assert_no_person_keys(s.model_dump(mode="json"))
        raw = json.dumps(s.raw)
        assert not any(n in raw or n.split()[1] in raw for n in SYNTHETIC_NAMES)
        assert "synthetic_user" not in raw and "@" not in raw


def test_cap_of_text_length_is_applied_before_redaction(protect):
    long = "Mr Fictus Exampleton " + "x" * 3000
    from osint_ingress.connectors.base import MAX_TEXT_CHARS

    out, n = redact_persons(long[:MAX_TEXT_CHARS], "news_regional", protect)
    assert n == 1 and len(out) <= MAX_TEXT_CHARS + 8


# ── the PoC-name scan (ethics rule 9; plan R13) ───────────────────────────────────────────────────────────────


def _poc_denylist() -> list[re.Pattern[str]]:
    tree = ast.parse(POC_SOURCE.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "_NAME_DENYLIST" for t in node.targets
        ):
            patterns = []
            for call in node.value.elts:  # type: ignore[attr-defined]
                flags = re.IGNORECASE if len(call.args) > 1 else 0
                patterns.append(re.compile(call.args[0].value, flags))
            return patterns
    raise AssertionError("_NAME_DENYLIST not found in the PoC source")


def _replaced_name_spans(tmp_path: Path, monkeypatch) -> set[str]:
    """The name spans this package's redactor replaces over the real PoC captures (kept in memory only)."""
    seen: set[str] = set()
    real_apply = redact_module._apply

    def recording_apply(text: str, spans):  # noqa: ANN001
        for s in spans:
            if s.kind == "name":
                seen.add(" ".join(text[s.start : s.end].split()))
        return real_apply(text, spans)

    monkeypatch.setattr(redact_module, "_apply", recording_apply)
    import_capture(POC_RAW, tmp_path / "poc-cache")
    from osint_ingress.connectors._protect import default_protect

    parse_cache(Cache(tmp_path / "poc-cache"), build_connectors(), default_protect())
    return {n for n in seen if len(n) >= 4}


def _package_files() -> list[Path]:
    skip = {"__pycache__", ".pytest_cache"}
    return [p for p in PACKAGE.rglob("*") if p.is_file() and not (set(p.parts) & skip)]


@needs_poc
@pytest.mark.skipif(not POC_SOURCE.is_file(), reason="PoC source not present (read in place only)")
def test_no_real_name_in_any_file_of_this_package(tmp_path, monkeypatch):
    """Never writes a name down: the names live in memory; a failure prints sha256(name)[:12] and the path."""
    denylist = _poc_denylist()
    assert denylist
    spans = _replaced_name_spans(tmp_path, monkeypatch)
    assert spans, "the redactor replaced no name in the real captures"
    span_res = [(h12(n), re.compile(r"(?<![A-Za-z])" + re.escape(n) + r"(?![A-Za-z])")) for n in spans]
    deny_res = [(h12(rx.pattern), rx) for rx in denylist]
    hits: list[tuple[str, str]] = []
    for path in _package_files():
        text = path.read_bytes().decode("utf-8", "replace")
        for digest, rx in deny_res + span_res:
            if rx.search(text):
                hits.append((digest, str(path.relative_to(PACKAGE))))
    assert not hits, f"real names found (sha256 prefixes, file): {sorted(set(hits))}"
