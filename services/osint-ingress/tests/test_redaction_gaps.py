"""F-HONEST OSINT-2 and OSINT-6: the redaction gaps the audit proved (``probes/osint_redaction_probe.txt``).

Names with no cue word, Indic-script names, and a poster's age and sex shorthand all survived parse-time redaction
while ``ethics.find_pii`` still answered ``[]``. The probes below keep the audit's shapes, written for Mumbai
(English, Marathi and Hindi); every name is invented, none is a real person's.
"""

from __future__ import annotations

import pytest

from osint_common import ethics
from osint_ingress.connectors._redact import TOKEN_WITHHELD, redact_persons

#: (text, name words that must be gone): the audit probe's leak shapes, written for Mumbai (fictional names).
AUDIT_LEAKS = [
    ("Biker Sandeep Mhaske dies after truck hits him on Western Express Highway", ["Sandeep", "Mhaske"]),
    ("Sandeep Mhaske dies after truck hits him on Eastern Express Highway", ["Sandeep", "Mhaske"]),
    ("Hit-and-run: Paresh Kamble, a resident of Kurla, succumbs", ["Paresh", "Kamble"]),
    ("Police arrest Mehul Doshi for chain snatching in Dadar", ["Mehul", "Doshi"]),
    ("Accused Bapu alias Bhurya held for robbery", ["Bapu", "Bhurya"]),
    ("Septuagenarian Haripant Kulkarni robbed at Matunga", ["Haripant", "Kulkarni"]),
    ("Doctor couple Nirav and Priya Sathe robbed at gunpoint near Bandra", ["Nirav", "Priya", "Sathe"]),
    ("PSI Rohan Gawde said the subway was shut", ["Rohan", "Gawde"]),  # a Mumbai Police rank
    ("Ganpatrao and Patil saheb inspected the pumps", ["Ganpatrao", "Patil"]),  # "-rao" and "<Name> saheb"
    ("Sau. Rupali Shelar was injured near the station", ["Rupali", "Shelar"]),
    ("रमेश पाटील (४५) यांचा अपघातात मृत्यू", ["रमेश", "पाटील", "४५"]),
    ("श्री विजय जाधव दादरमध्ये जखमी", ["विजय", "जाधव"]),  # an honorific: the given name may be an ordinary word
    ("आरोपी रमेश पवारला पोलिसांनी अटक केली", ["रमेश", "पवार"]),
    ("३५ वर्षीय सुनील साळवी कुर्ल्यात अपघातात जखमी", ["सुनील", "साळवी", "३५"]),
    ("४२ वर्षांचा प्रकाश मोरे जखमी", ["प्रकाश", "मोरे", "४२"]),
    ("मुंबईत शंकररावांच्या दुकानात चोरी", ["शंकर"]),
    ("मुंबई में रमेश यादव की हत्या", ["रमेश", "यादव"]),
    ("Where is Kalpita's body? 11 days on, nullah search continues", ["Kalpita"]),  # the stored-victim shape
]


def _kept(word: str, text: str) -> bool:
    import re

    if word.isascii():
        return re.search(rf"(?<![A-Za-z0-9]){re.escape(word)}(?![A-Za-z0-9])", text) is not None
    return word in text


@pytest.mark.parametrize("tier", ["news_regional", "aggregator", "news_wire", "social_unverified", "official"])
@pytest.mark.parametrize(("text", "names"), AUDIT_LEAKS)
def test_the_audit_leaks_are_redacted_in_every_tier(protect, tier, text, names):
    out, n = redact_persons(text, tier, protect)
    assert n > 0 and not [w for w in names if _kept(w, out)], out
    assert ethics.find_pii(out) == [] and ethics.find_unredactable(out) == []


@pytest.mark.parametrize(
    ("text", "kept"),
    [
        ("Biker Sandeep Mhaske dies after truck hits him on Western Express Highway",
         ["Biker", "Western Express Highway"]),
        ("Hit-and-run near Kurla: Paresh Kamble succumbs", ["Kurla"]),
        ("Truck overturns on Senapati Bapat Marg near Dadar TT", ["Senapati Bapat Marg", "Dadar TT"]),
        ("Fixture Kiosk Opens At Riverfront", ["Fixture Kiosk Opens At Riverfront"]),  # a Title-Case headline
        ("Youth Association rally near CSMT", ["Youth Association"]),  # an organisation after a role noun
        ("Patil family meeting at Shivaji Park", ["Patil family", "Shivaji Park"]),  # a surname alone is no person
        ("Five More Trains Cancelled At Kurla", ["Five More Trains Cancelled At Kurla"]),  # More, a surname too
        ("Traffic diverted from Bhulabhai Desai Road to Gokhale Bridge", ["Bhulabhai Desai Road", "Gokhale Bridge"]),
    ],
)
def test_places_organisations_and_headlines_survive(protect, text, kept):
    out, _ = redact_persons(text, "news_regional", protect)
    assert all(k in out for k in kept), out


def test_indic_words_are_withheld_but_places_and_common_words_stay(protect):
    out, n = redact_persons("मुंबईत आग: रमेश साळवी सह तीन जण जखमी", "news_regional", protect)
    assert "रमेश" not in out and "साळवी" not in out and n >= 1
    assert out.startswith("मुंबईत आग: ") and out.endswith(" सह तीन जण जखमी")
    out, _ = redact_persons("मुंबई में ट्रैफिक जाम, ठाणे में जलभराव", "aggregator", protect)
    assert TOKEN_WITHHELD not in out  # places (with a case ending) and common words only
    # "डॉ. आंबेडकर मार्ग" is a road: the honorific does not make its name word a person (it may still be withheld
    # until the shared gazetteer holds the road's Marathi spelling)
    out, _ = redact_persons("डॉ. आंबेडकर मार्गावर पाणी साचले", "news_regional", protect)
    assert "[PERSON]" not in out and "पाणी साचले" in out
    # the Devanagari name in a half-Latin title (the shape of a stored case) goes with the Latin one
    out, _ = redact_persons("फिक्टस डमीवाला के खिलाफ केस; case on Accused Fictus Dummyvala", "aggregator", protect)
    assert "फिक्टस" not in out and "डमीवाला" not in out and "Dummyvala" not in out


def test_indic_suffixes_are_the_geo_scanners(protect):
    from osint_geo import translit

    geo = set(translit.MR_SUFFIXES)
    if any("\u0980" <= ch <= "\u09ff" for suf in geo for ch in suf):
        pytest.skip("osint_geo.translit.MR_SUFFIXES still holds Bengali endings: osint-geo moves to Marathi in its own "
                    "stream, and its lockstep test pins the two")
    assert set(ethics.INDIC_SUFFIXES) == geo


@pytest.mark.parametrize(
    ("text", "marker"),
    [
        ("IT'S SO BORINGGGG IN WEEEKEND HERE F(28)", "F(28)"),
        ("Any other 22M second-gen imitation jewelry wholesalers here?", "22M"),
        ("27/F, is the Hindmata stretch flooded?", "27/F"),
        ("(24F) looking for a flatmate in Bandra", "24F"),
        ("M/30 here, moved to Powai last month", "M/30"),
        ("26 M, looking for a cycling group", "26 M"),
    ],
)
def test_a_posters_age_and_sex_shorthand_is_redacted(protect, text, marker):
    out, n = redact_persons(text, "social_unverified", protect)
    assert marker not in out and "[AGE]" in out and n >= 1, out


@pytest.mark.parametrize("text", ["Flat for Rs 22M in Ballygunge", "Flat for Rs. 22M in Ballygunge", "Budget ₹22M"])
def test_amounts_are_not_age_markers(protect, text):
    # known over-redaction, accepted: a bare "15M" or "M25" in a post reads as an age marker (the poster's own
    # "22M" cannot be told apart from it without context)
    out, _ = redact_persons(text, "social_unverified", protect)
    assert "[AGE]" not in out, out
