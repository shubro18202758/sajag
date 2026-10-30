"""osint_common.scope: the deterministic scope gate (roads, crowds, weather, hazards, closures and services only).

Synthetic Mumbai headlines in English, Marathi and Hindi (and a few Bengali ones: the Kolkata pack stays as the
second pack). No real person, party, organisation or election symbol is named here: the party-name and symbol
checks are exercised with fictional names added to the hash sets for the test.
"""

from __future__ import annotations

import hashlib
import unicodedata

import pytest

from osint_common import scope


def _h(name: str) -> str:
    return hashlib.sha256(unicodedata.normalize("NFKC", name).lower().encode()).hexdigest()[:16]


@pytest.mark.parametrize(
    ("title", "reason"),
    [
        ("Daylight robbery at a jewellery shop near Dadar TT Circle", "crime"),
        ("Two arrested for chain snatching on SV Road in Andheri", "crime"),
        ("दादरमध्ये सोनसाखळी चोरी, दोघांना अटक", "crime"),
        ("कुर्ल्यात दरोडा, गुन्हा दाखल", "crime"),
        ("चालकाला अटक केली", "crime"),
        ("दुकान में चोरी", "crime"),
        ("Clash between two groups at Kurla, stones pelted", "conflict"),
        ("दोन गटांत हाणामारी, दगडफेक", "conflict"),
        ("वस्तीत दोन गटांत संघर्ष", "conflict"),  # संघर्ष with no vehicle: a clash
        ("घाटकोपर में झड़प", "conflict"),
        ("Election results: counting at the strong rooms", "political"),
        ("Voters queue at polling booths in Worli", "political"),
        ("Civic polls: corporators file nominations", "political"),
        ("महापालिका निवडणुकीत मतदान", "political"),
        ("आमदार आणि नगरसेवक बैठकीला उपस्थित", "political"),
        ("चुनावी सभा के लिए प्रत्याशी पहुंचे", "political"),
        # the Kolkata pack's Bengali cues still gate a Bengali item
        ("ছিনতাইয়ের অভিযোগে গ্রেফতার", "crime"),
        ("পাড়ায় দুই গোষ্ঠীর সংঘর্ষ", "conflict"),
        ("উপনির্বাচনে ভোট", "political"),
    ],
)
def test_out_of_scope(title, reason):
    v = scope.screen(title)
    assert v.reason == reason and v.masked == 0


@pytest.mark.parametrize(
    "title",
    [
        "Two killed as a BEST bus hits a truck on the Western Express Highway near Andheri",  # a road accident stays
        "Heavy rain at high tide: Hindmata waterlogged, Dr Ambedkar Road slow",
        "Fire in a Kurla godown, fire tenders on LBS Marg",
        "Ganeshotsav visarjan procession from Lalbaug to Girgaon Chowpatty, roads closed till 22:00",
        "Heart attack patient taken by ambulance through a green corridor to KEM",  # 'attack' is not a cue
        "Pollution level rises in Mumbai",  # 'poll' is a whole word only
        "मुसळधार पावसामुळे हिंदमाता येथे पाणी साचले, वाहतूक कोंडी",
        "अंधेरी सबवे बंद, वाहतूक वळवली",
        "रेल्वे इंजिनात बिघाड, लोकल सेवा ठप्प",
        "अटकाव करण्यासाठी नवे पंप",  # "अटकाव" (prevention) is not an arrest
        "सायन में भारी जलभराव, सड़क पर जाम",
        "गणेशोत्सव मंडळाच्या कार्यकर्त्यांनी वाहतूक नियंत्रणात मदत केली",  # a festival mandal's volunteers
        "Thunderstorm warning for Mumbai",
        "लोकल आणि बसचा संघर्ष, अपघातात अनेक जखमी",  # संघर्ष with vehicles: a collision, not a clash
        "दो ट्रेनों में संघर्ष, हादसे में कई घायल",
        "বাস ও লরির সংঘর্ষে যানজট",  # the Kolkata pack's collision context
    ],
)
def test_in_scope_passes_unchanged(title):
    v = scope.screen(title, "")
    assert v.reason is None and v.masked == 0 and v.title == title


@pytest.mark.parametrize(
    ("title", "keeps"),
    [
        ("Political rally of party workers blocks Annie Besant Road, traffic diverted", "blocks Annie Besant Road"),
        ("राजकीय मोर्चामुळे दादर टीटी सर्कल येथे वाहतूक कोंडी", "दादर टीटी सर्कल येथे वाहतूक कोंडी"),
        ("राजनीतिक रैली से सड़क जाम", "सड़क जाम"),
        ("রাজনৈতিক মিছিলে যানজট", "যানজট"),
    ],
)
def test_a_gathering_on_a_road_keeps_place_and_impact_only(title, keeps):
    v = scope.screen(title)
    assert v.reason is None and v.masked >= 1
    assert keys_absent(v.title) and scope.WITHHELD in v.title and keeps in v.title


def keys_absent(text: str) -> bool:
    return all(w not in text for w in ("Political", "party workers", "राजकीय", "राजनीतिक", "রাজনৈতিক"))


def test_a_political_item_without_a_road_or_a_gathering_is_dropped():
    assert scope.screen("Political meeting in a hall").reason == "political"  # a gathering, no road
    assert scope.screen("Political row over the road budget").reason == "political"  # a road, no gathering
    assert scope.screen("राजकीय सभा सभागृहात").reason == "political"  # a gathering, no road


def test_party_names_are_matched_by_hash_never_written(monkeypatch):
    fictional = "examplefront"
    digest = _h(fictional)
    assert digest not in scope.PARTY_HASHES
    monkeypatch.setattr(scope, "PARTY_HASHES", scope.PARTY_HASHES | {digest})
    assert scope.screen("Examplefront leader visits a pandal").reason == "political"
    v = scope.screen("Examplefront rally blocks Marine Drive, traffic diverted")
    assert v.reason is None and v.title.startswith(scope.WITHHELD) and "Marine Drive" in v.title


@pytest.mark.parametrize("ending", ["च्या", "चा", "ने", "ला", "ांनी", "मध्ये", "तील"])
def test_a_marathi_case_ending_is_removed_before_hashing(monkeypatch, ending):
    mr = "उदाहरणपक्ष"  # a fictional party name in Devanagari
    monkeypatch.setattr(scope, "PARTY_HASHES", scope.PARTY_HASHES | {_h(mr)})
    assert scope.screen(f"{mr}{ending} कार्यालयात बैठक").reason == "political"
    v = scope.screen(f"{mr}{ending} मोर्चामुळे रस्ता बंद")
    assert v.reason is None and v.masked == 1 and mr not in v.title and "रस्ता बंद" in v.title


def test_a_two_token_party_phrase_is_one_span(monkeypatch):
    monkeypatch.setattr(scope, "PARTY_HASHES", scope.PARTY_HASHES | {_h("उदाहरण आघाडी"), _h("example alliance")})
    assert scope.screen("उदाहरण आघाडीच्या नेत्यांची भेट").reason == "political"
    v = scope.screen("Example Alliance march on LBS Marg, traffic diverted")
    assert v.reason is None and v.masked == 1 and v.title.startswith(scope.WITHHELD)


def test_a_bengali_case_ending_is_still_removed_for_the_kolkata_pack(monkeypatch):
    bn = "উদাহরণদল"
    monkeypatch.setattr(scope, "PARTY_HASHES", scope.PARTY_HASHES | {_h(bn)})
    assert scope.screen(f"{bn}ের মিছিলে রাস্তা বন্ধ").masked == 1


def test_an_election_symbol_counts_only_beside_a_symbol_word_or_in_a_political_item(monkeypatch):
    sym_mr, sym_en = "झोरबेल", "zorbel"  # fictional symbol nouns
    monkeypatch.setattr(scope, "SYMBOL_HASHES", scope.SYMBOL_HASHES | {_h(sym_mr), _h(sym_en)})
    # the everyday noun alone: in scope, unchanged
    for t in (f"{sym_mr} बाजारात विक्रीला", f"A {sym_en} fell on the Sea Link"):
        v = scope.screen(t)
        assert v.reason is None and v.masked == 0 and v.title == t
    # beside a word for "symbol" (within three words): political
    assert scope.screen(f"{sym_mr} चिन्हावर लढत").reason == "political"
    assert scope.screen(f"Contest on the {sym_en} symbol").reason == "political"
    assert scope.screen(f"{sym_mr} या निवडणूक चिन्हाचा वाद").reason == "political"
    # far from it: not read as a symbol
    far = f"{sym_en} seen near the Worli sea face, then a faded road sign symbol was repainted on the bridge"
    assert scope.screen(far).reason is None
    # in a kept political item the symbol is withheld with the political words
    v = scope.screen(f"राजकीय मोर्चात {sym_mr} झेंडे, रस्ता बंद")
    assert v.reason is None and sym_mr not in v.title and v.masked >= 2 and "रस्ता बंद" in v.title


def test_the_hash_sets_are_hex_prefixes_only():
    assert len(scope.PARTY_HASHES) == 94 and len(scope.SYMBOL_HASHES) == 32
    assert not scope.PARTY_HASHES & scope.SYMBOL_HASHES
    for h in scope.PARTY_HASHES | scope.SYMBOL_HASHES:
        assert len(h) == 16 and int(h, 16) >= 0


def test_no_everyday_word_is_a_party_hash():
    """A cue word or an everyday road/situation word is never a party hash (it would drop every item)."""
    words = ("road", "traffic", "rain", "mumbai", "रस्ता", "वाहतूक", "पाऊस", "पाणी", "लोकल", "मुंबई", "बस",
             "सड़क", "बारिश", "गर्दी", "मोर्चा", "सभा", "आपला", "company", "limited")
    for w in words:
        assert _h(w) not in scope.PARTY_HASHES, w


def test_out_of_scope_classes():
    assert scope.screen_class("reported_crime") == "crime"
    assert scope.screen_class("public_conflict") == "conflict"
    assert scope.screen_class("unrest") == "political"
    for kept in ("road_accident", "fire", "urban_flooding", "infra_failure", "hazard", "public_gathering",
                 "procession", "road_closure", "weather_hazard", "general_news", None):
        assert scope.screen_class(kept) is None


def test_deterministic():
    title = "राजकीय मोर्चामुळे दादर टीटी सर्कल येथे वाहतूक कोंडी"
    assert scope.screen(title) == scope.screen(title)
