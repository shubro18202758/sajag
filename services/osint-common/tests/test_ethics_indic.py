"""F-HONEST OSINT-2: Indic-script words no redactor can read for names are found (``ethics.unredactable_spans``).

``find_pii`` reads Latin-script cue patterns only, so a Marathi or Devanagari name passed it as clean (the audit
stored "<Hindi name> के खिलाफ ..." beside its own redacted Latin copy). The names below are fictional. The places
come from the synthetic Mumbai test gazetteer (tests/conftest.py).
"""

from __future__ import annotations

import unicodedata

import pytest

from osint_common import ethics


def _apply(text: str) -> str:
    out = text
    for s in reversed(ethics.unredactable_spans(text)):
        out = out[: s.start] + "[W]" + out[s.end :]
    return out


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # a place with a case ending, a fictional name with an honorific pronoun, a common word
        ("दादरमध्ये फिक्टस डमीवाले यांचा मृत्यू", "दादरमध्ये [W] मृत्यू"),
        ("घाटकोपर में फिक्टस डमीवाला की हत्या", "घाटकोपर में [W] की हत्या"),
        ("अंधेरीत आग", "अंधेरीत आग"),  # a gazetteer place with a case ending, and a common word
        ("हिंदमाता येथे पाणी साचल्याने वाहतूक विस्कळीत", "हिंदमाता येथे पाणी साचल्याने वाहतूक विस्कळीत"),  # the low spot
        ("किंग्ज सर्कल येथे पाणी साचले", "किंग्ज सर्कल येथे पाणी साचले"),  # a multi-word place phrase
        ("पश्चिम द्रुतगती महामार्गावर अपघात, तीन जण जखमी", "पश्चिम द्रुतगती महामार्गावर अपघात, तीन जण जखमी"),
        ("चक्रीवादळामुळे मुंबईत मुसळधार पाऊस", "चक्रीवादळामुळे मुंबईत मुसळधार पाऊस"),
        ("अंधेरी सबवे बंद, वाहतूक वळवली", "अंधेरी सबवे बंद, वाहतूक वळवली"),
        ("गणेशोत्सवात लालबागमध्ये मोठी गर्दी", "गणेशोत्सवात लालबागमध्ये मोठी गर्दी"),
        # "भाविक" (devotee) is also a given name: withheld, never guessed harmless
        ("लालबागमध्ये भाविकांची गर्दी", "लालबागमध्ये [W] गर्दी"),
        ("पोलीस के. डी. फिक्टसकर म्हणाले", "पोलीस [W]. [W]. [W] म्हणाले"),  # initials are a name part
        ("Plain ASCII text with no script", "Plain ASCII text with no script"),
    ],
)
def test_unknown_indic_words_are_found_and_places_kept(text, expected):
    assert _apply(text) == expected


def test_the_two_spellings_of_a_nukta_letter_read_alike():
    """"ड़" is written as one code point (U+095C) or as "ड" + nukta; NFKC makes them one form, so a common word
    in either spelling is kept."""
    composed = "स\u095cक पर जाम"
    decomposed = "स\u0921\u093cक पर जाम"
    assert composed != decomposed
    assert unicodedata.normalize("NFKC", composed) == unicodedata.normalize("NFKC", decomposed)
    assert _apply(composed) == composed and _apply(decomposed) == decomposed


def test_find_pii_does_not_see_indic_names_and_find_unredactable_does():
    text = "मुंबईत फिक्टस डमीवाले यांचा मृत्यू"
    assert ethics.find_pii(text) == []  # the documented limit of find_pii: Latin cue patterns only
    assert ethics.find_unredactable(text) == ["script:indic"]
    assert ethics.find_unredactable("मुंबईत अपघात") == []
    assert ethics.find_unredactable("मुंबई में हादसा") == []
    assert ethics.find_unredactable(None) == [] and ethics.find_unredactable("") == []


def test_a_multi_word_place_keeps_its_words_only_where_the_whole_phrase_occurs():
    # "किंग्ज" is a word of the gazetteer phrase "किंग्ज सर्कल": alone, beside a name, it is withheld
    assert _apply("फिक्टस किंग्ज") == "[W]"


def test_without_the_gazetteer_places_are_withheld_never_kept(monkeypatch, tmp_path):
    monkeypatch.setenv(ethics.GAZETTEER_ENV, str(tmp_path / "missing.json"))
    ethics.reset_place_phrases()
    assert _apply("अंधेरीत आग") == "[W] आग"  # stricter, never laxer


def test_common_words_hold_no_name():
    for word in (
        "किरण", "आशा", "विजय", "दीपक", "प्रकाश", "संध्या", "वर्षा", "सागर", "पूजा", "गणेश", "गणपती", "अनंत", "राजा",
        "आनंद", "उषा", "रमेश", "सुरेश", "पाटील", "जोशी", "कुलकर्णी", "शाह", "खान", "नवीन", "उत्सव", "दर्शन", "भाविक",
        "सराफ", "अधिकारी", "गंभीर", "गुल", "अग्नि", "मिलन",
    ):
        assert ethics._indic_key(word) not in ethics.INDIC_COMMON_WORDS, word


def test_suffixes_are_marathi_case_endings_and_the_kolkata_packs():
    """The case endings are Marathi's (locative, dative, instrumental, genitive in three genders and the oblique,
    ablative, the plural oblique, emphatic) and the Kolkata pack's Bengali ones, longest first; no Gujarati letter.
    The common words are Hindi and Marathi only (Bengali words are withheld: stricter, never laxer)."""
    suffixes = ethics.INDIC_SUFFIXES
    assert [len(s) for s in suffixes] == sorted((len(s) for s in suffixes), reverse=True)
    assert set(suffixes) == {unicodedata.normalize("NFKC", s) for s in (*ethics.MARATHI_SUFFIXES,
                                                                         *ethics.BENGALI_SUFFIXES)}
    for s in ("त", "ात", "ला", "ने", "नी", "चा", "ची", "चे", "च्या", "मध्ये", "वर", "हून", "तील", "मुळे", "ांच्या",
              "ांना"):
        assert unicodedata.normalize("NFKC", s) in suffixes
    assert all(all("\u0900" <= ch <= "\u097f" for ch in s) for s in ethics.MARATHI_SUFFIXES)
    assert not any("઀" <= ch <= "૿" for s in suffixes for ch in s)
    assert not any("ঀ" <= ch <= "৿" or "઀" <= ch <= "૿" for w in ethics.INDIC_COMMON_WORDS for ch in w)


def test_a_case_ending_reads_the_stem_of_a_common_word_and_of_a_place():
    for word in ("मुंबईत", "पावसामुळे", "रस्त्यावर", "शहराच्या", "पोलिसांना", "दादरहून", "अंधेरीतील"):
        assert _apply(word) == word, word
