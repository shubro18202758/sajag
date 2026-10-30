"""The ethics rails: the person-key denylist and the surviving-PII detector (OSINT SPEC §0, §4).

The person names used below are invented for these tests (no real person); they exist only to prove detection.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid

import pytest

from osint_common import ethics, testing, types

FICTIONAL = ("Varnel Ostrik", "Kemlo Daravin", "Pelko Tarnish", "Zorvan Quillet")


@pytest.fixture(autouse=True)
def _fresh_phrases():
    ethics.reset_place_phrases()
    yield
    ethics.reset_place_phrases()


# ── person keys ──────────────────────────────────────────────────────────────


def test_forbidden_key_re_is_the_frozen_spec_denylist():
    assert ethics.FORBIDDEN_KEY_RE == (
        r"author|person|handle|username|byline|reporter|poster|uploader|suspect|accused|victim|owner|driver_name"
        r"|face|biometric|individual_"
    )


def test_forbidden_keys_cover_the_spec_list():
    spec_1_2 = {
        "persons", "author", "username", "handle", "byline", "reporter", "poster", "uploader", "suspect",
        "accused", "victim", "owner", "driver_name", "faces", "biometrics",
    }
    assert spec_1_2 <= ethics.FORBIDDEN_KEYS
    assert all(ethics.is_forbidden_key(k) for k in ethics.FORBIDDEN_KEYS)


#: Compound keys the frozen denylist matches as a substring: refused although no token equals a term.
COMPOUND_PERSON_KEYS = (
    "authorname", "personid", "personname", "postauthor", "reportername", "victimname", "suspectname",
    "ownername", "userName", "faceprint",
)

#: Lookalikes that contain a term (interFACE, AUTHORity, HANDLEr, OWNERship, SUSPECTed): the check fails closed,
#: so they are refused too; none of them is a contract key (test_exempt_keys_are_exactly_the_contract_collisions).
LOOKALIKE_KEYS = (
    "interface", "facet", "typeface", "authority", "issuing_authority", "handler", "ownership", "suspected_cause",
)


@pytest.mark.parametrize(
    "key",
    [
        "author", "Author", "AUTHOR", "authors", "authorName", "author_name", "post_author", "reddit-author",
        "URLAuthor", "person", "persons", "person_id", "handle", "user_handle", "username", "byline", "reporter",
        "poster", "uploader", "suspect", "suspects", "accused", "victim", "victim_count", "owner", "vehicle_owner",
        "driver_name", "driverName", "driver-name", "DriverName", "face", "faces", "face_embedding", "faceId",
        "biometric", "biometrics", "individual_id", "individual_age", "individualId", "IndividualAge",
        "ａｕｔｈｏｒ",  # fullwidth "author" (NFKC folds it to ASCII)
        "authoŕ", "driveŕ_name",  # a combining mark NFKC would compose: the raw form is checked too
        "Touches_Persons", "surfaced_count", "surface_form",  # near the exemptions, but not them
        *COMPOUND_PERSON_KEYS,
        *LOOKALIKE_KEYS,
    ],
)
def test_person_keys_are_forbidden(key):
    assert ethics.is_forbidden_key(key)
    with pytest.raises(ValueError, match=r"^forbidden_key:"):
        ethics.assert_no_person_keys({"meta": {key: "x"}})


@pytest.mark.parametrize(
    "key",
    [
        "reported_at", "publisher", "publishers", "posted_at", "individuals", "driver", "source_tiers",
        "pii_redactions", "source_feeds", "geocoder", "geocode_confidence", "osint_event_id", "dss_id",
        "required_role", "officer", "decided_at", "canonical_name", "feature_type",
    ],
)
def test_keys_without_a_denylist_term_are_allowed(key):
    assert not ethics.is_forbidden_key(key)


def test_exempt_keys_are_exactly_the_three_contract_keys():
    assert ethics.EXEMPT_KEYS == frozenset({"touches_persons", "surface_forms", "surfaced"})
    for key in ethics.EXEMPT_KEYS:
        assert not ethics.is_forbidden_key(key)


def test_exempt_keys_carry_only_their_contract_value_type():
    ethics.assert_no_person_keys(
        {"touches_persons": False, "surfaced": 3, "counts": {"surfaced": 0}, "surface_forms": ["andheri", "andheri subway"]}
    )
    ethics.assert_no_person_keys({"surface_forms": ("marine drive",), "surfaced": True})
    for payload in (
        {"touches_persons": f"{FICTIONAL[0]}"},
        {"touches_persons": None},
        {"surfaced": [f"{FICTIONAL[1]}"]},
        {"surfaced": "3"},
        {"surface_forms": f"{FICTIONAL[2]}"},
        {"surface_forms": [{"name": f"{FICTIONAL[3]}"}]},
        {"surface_forms": ["andheri", 7]},
        {"nested": [{"touches_persons": {"who": "x"}}]},
    ):
        with pytest.raises(ValueError, match=r"^forbidden_key:"):
            ethics.assert_no_person_keys(payload)


def _model_field_names() -> set[str]:
    from pydantic import BaseModel

    from osint_common import kinds, types

    names: set[str] = set()
    for name in types.__all__:
        obj = getattr(types, name)
        if isinstance(obj, type) and issubclass(obj, BaseModel):
            names |= set(obj.model_fields)
    names |= set(kinds.SourcePrior.model_fields)
    return names


def _dict_keys(value) -> set[str]:
    out: set[str] = set()
    if isinstance(value, dict):
        for k, v in value.items():
            out.add(str(k))
            out |= _dict_keys(v)
    elif isinstance(value, list):
        for v in value:
            out |= _dict_keys(v)
    return out


def test_exempt_keys_are_exactly_the_contract_collisions():
    """EXEMPT_KEYS is exactly the set of contract keys the frozen regex matches as a substring: every osint_common
    model field, RAW_ALLOWED_KEYS, every key of the X19 gazetteer and of every fixture, and (when present, read in
    place) every key of the PoC outputs. No collision is left unexempted, and no exemption is superfluous."""
    import poc_parity

    keys = _model_field_names() | set(ethics.RAW_ALLOWED_KEYS)
    gaz = ethics.gazetteer_path()
    assert gaz is not None
    keys |= _dict_keys(json.loads(gaz.read_text(encoding="utf-8")))
    for name in testing.__all__:
        fn = getattr(testing, name)
        if callable(fn):
            value = fn()
            for item in value if isinstance(value, list) else [value]:
                keys |= _dict_keys(item.model_dump(mode="json"))
    out = poc_parity.poc_out_dir()
    for f in ("signals.raw.json", "events.fused.json", "dss_output.json"):
        if (out / f).is_file():
            keys |= _dict_keys(json.loads((out / f).read_text(encoding="utf-8")))
    collisions = {k for k in keys if re.search(ethics.FORBIDDEN_KEY_RE, k, re.IGNORECASE)}
    assert collisions == ethics.EXEMPT_KEYS
    assert not [k for k in keys if ethics.is_forbidden_key(k)]


#: A real sha1 signal id whose hex digits spell "face" (the review's reproduction), and a canonical uuid that does.
FACE_SIGNAL_ID = hashlib.sha1(b"google_news_rss:synthetic:559").hexdigest()
FACE_UUID = "0b7e3c2a-face-4d1e-9a8b-5c6d7e8f9a0b"


def test_opaque_ids_are_never_person_keys():
    assert "face" in FACE_SIGNAL_ID and FACE_SIGNAL_ID == types.signal_id_for("google_news_rss", "synthetic:559")
    assert "face" in FACE_UUID and str(uuid.UUID(FACE_UUID)) == FACE_UUID
    for key in (FACE_SIGNAL_ID, FACE_UUID):
        assert not ethics.is_forbidden_key(key)
        ethics.assert_no_person_keys({"geocodes": {key: {"signal_id": key}}})
    # the X18 object the review reproduced: a PipelineResult keyed by such a signal id
    geo = testing.weh_geocode().model_copy(update={"signal_id": FACE_SIGNAL_ID})
    ethics.assert_no_person_keys(types.PipelineResult(geocodes={FACE_SIGNAL_ID: geo}))
    ethics.assert_no_person_keys(types.PipelineResult(geocodes={FACE_SIGNAL_ID: geo}).model_dump(mode="json"))


@pytest.mark.parametrize(
    "key",
    [
        "face", "faceprint", "face_id", "faceId",  # the terms themselves stay forbidden
        FACE_SIGNAL_ID.upper(),  # only the canonical lower-case forms are opaque ids
        FACE_UUID.upper(),
        FACE_SIGNAL_ID + "\n",  # matched in full: no trailing newline, no padding, no truncation
        FACE_SIGNAL_ID + "0",
        FACE_SIGNAL_ID[1:],
        "x" + FACE_UUID,
        FACE_UUID.replace("-", ""),  # 32 hex digits: not a sha1 and not a canonical uuid
        f"event:{FACE_UUID}",  # a URN is not an opaque id
        f"signal_{FACE_SIGNAL_ID}",
        "face" + "0" * 36 + "_name",
    ],
)
def test_only_whole_opaque_ids_escape(key):
    assert ethics.is_forbidden_key(key)


def test_random_opaque_ids_never_read_as_person_keys():
    """About 1 sha1 in 2,000 (and some uuids) spell "face"; none of them may fail a key walk."""
    sha1s = [types.signal_id_for("google_news_rss", f"synthetic:{i}") for i in range(20000)]
    uuids = [str(uuid.uuid5(testing.SYNTHETIC_NAMESPACE, f"id-{i}")) for i in range(20000)]
    assert sum("face" in s for s in sha1s) >= 5 and sum("face" in u for u in uuids) >= 1
    assert not [k for k in sha1s + uuids if ethics.is_forbidden_key(k)]


def test_assert_no_person_keys_walks_every_depth():
    ethics.assert_no_person_keys({"a": 1, "b": [{"c": {"d": [1, 2, {"e": None}]}}], "touches_persons": False})
    for payload in (
        {"author": "x"},
        {"raw_geo_hint": {"place_names": [], "persons": ["x"]}},
        {"items": [{"ok": 1}, {"nested": {"faces": []}}]},
        [{"deep": [[{"individual_id": 1}]]}],
        ({"x": {"y": {"z": {"uploader": None}}}},),
    ):
        with pytest.raises(ValueError, match=r"^forbidden_key:"):
            ethics.assert_no_person_keys(payload)


def test_forbidden_key_error_names_the_key():
    with pytest.raises(ValueError) as exc:
        ethics.assert_no_person_keys({"meta": {"post_author": "x"}})
    assert str(exc.value) == "forbidden_key:post_author"


def test_hostile_nesting_is_refused_not_recursed_forever():
    deep: dict = {}
    cur = deep
    for _ in range(200):
        cur["k"] = {}
        cur = cur["k"]
    with pytest.raises(ValueError, match=r"^invalid:"):
        ethics.assert_no_person_keys(deep)


def test_raw_allowed_keys_are_scalar_codes_never_person_keys():
    for k in ethics.RAW_ALLOWED_KEYS:
        assert k == k.lower() and k.replace("_", "").isalnum(), k
        assert not ethics.is_forbidden_key(k), k


# ── surviving PII ────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "text",
    [
        "",
        None,
        "Car crashes into three vehicles on the Western Express Highway near Andheri",
        "Traffic diverted via Marine Drive and Kalanagar junction",
        "[PERSON], [AGE], was taken to hospital",
        "Mr [PERSON] and Smt [PERSON] were questioned",
        "the driver, identified as [PERSON], was beaten",
        "a resident of Marine Drive said the road was closed",
        "a resident of Powai reported waterlogging",
        "Dr. Ambedkar Road reopened after repairs",
        "Traffic moved to Dr. Ambedkar Road Police chowki",
        "West zone Police issued a diversion",
        "the API Gateway timed out",
        "one Police van reached the spot",
        "3 injured, including two brothers on a scooter",
        # gazetteer places longer than the 1-3 captured words, or hyphenated (the capture stops at the hyphen)
        "a resident of Netaji Subhash Chandra Bose Road said",
        "a resident of Mumbai Airport Terminal 2 said",
        "a resident of Sion-Koliwada said",
        "the 2-km stretch named Senapati Bapat Marg was resurfaced",
        # what a complete redaction leaves behind
        "[PERSON], [AGE],",
        "Driver [PERSON], [AGE], beaten by mob near Andheri",
        "[PERSON] ([AGE]) was taken to hospital",
        # numbers in parentheses that are no age
        "(45) vehicles were towed from the Western Express Highway",
        "BEST (12) buses diverted near Andheri",
        # a rank cue before a unit is a unit, not a person
        "DCP Zone 7 issued a diversion near Andheri",
        "the visarjan procession passed Dr. Ambedkar Road",
        # non-ASCII text: the detection view protects places and leaves Indic joiners alone
        "a resident of Ｍａｒｉｎｅ Ｄｒｉｖｅ said",  # fullwidth "Marine Drive"
        "क्‍ष traffic diverted near Marine Drive — one lane closed",
    ],
)
def test_clean_text_has_no_pii(text):
    assert ethics.find_pii(text) == []


@pytest.mark.parametrize(
    "text",
    [
        f"a resident of Marine Drive {FICTIONAL[0]} said",
        f"Mr {FICTIONAL[0]} of Netaji Subhash Chandra Bose Road said",
        f"a resident of Andheri {FICTIONAL[1]} said",
        f"Shri {FICTIONAL[2]} Marg",
        "Mr Bapat said the road was closed",
        "Mr Prince said nothing",
    ],
)
def test_place_lookahead_never_protects_a_name(text):
    """A phrase must be a contiguous run of the source words: a name next to (or inside) a place is still found."""
    assert ethics.find_pii(text) != []


def test_place_lookahead_is_bounded():
    long_tail = " filler" * 400
    assert ethics.find_pii("a resident of Netaji Subhash Chandra Bose Road said" + long_tail) == []
    assert ethics.find_pii(f"Mr {FICTIONAL[0]} said" + long_tail) == ["name:Mr"]


@pytest.mark.parametrize(
    ("text", "label"),
    [
        (f"Mr {FICTIONAL[0]} was detained", "name:Mr"),
        (f"Shri {FICTIONAL[1]} addressed the crowd", "name:Shri"),
        (f"Constable {FICTIONAL[2]} was injured", "name:Constable"),
        (f"the accused {FICTIONAL[3]} fled", "name:the accused"),
        (f"a man identified as {FICTIONAL[0]} was held", "name:identified as"),
        ("a 41-year-old man was injured", "age:years_old"),
        ("a 41 yrs old woman", "age:years_old"),
        ("the victim, aged 41, was taken to hospital", "age:aged"),
        ("Ostrik, 41, a trader", "age:comma"),
        ("Mr Khar arrived at the junction", "name:Mr"),
        # names written with initials
        ("Mr R. K. Ostrik was detained", "name:Mr"),
        ("Shri A.B. Daravin addressed the crowd", "name:Shri"),
        ("PSI V.K.Tarnish reached the spot", "name:PSI"),
        ("Dr. S. Quillet attended", "name:Dr"),
        # an age right after a redacted name: exactly what a name-first redaction pass leaves behind
        ("[PERSON], 45,", "age:comma"),
        ("Driver [PERSON], 45, beaten by mob near Andheri", "age:comma"),
        ("[PERSON] , 45 , was taken to hospital", "age:comma"),
        # parenthesised ages
        ("Ostrik (45) was taken to hospital", "age:paren"),
        ("Varnel Ostrik ( 45 ) was taken to hospital", "age:paren"),
        ("[PERSON] (45) was taken to hospital", "age:paren"),
        # after an honorific, generic place words alone are not a place: a surname that is also one is a name
        ("Police said Mr Rath was detained.", "name:Mr"),
        ("Dr Ward attended the injured", "name:Dr"),
        ("Mr Cross said the lane was closed", "name:Mr"),
        # a name hidden from a raw scan by a format character or fullwidth letters (the detection view)
        ("the accused Va​rnel Ostrik fled", "name:the accused"),
        ("the accused Va­rnel Ostrik fled", "name:the accused"),
        ("the accused Ｖａｒｎｅｌ Ostrik fled", "name:the accused"),
        ("the acc​used Varnel Ostrik fled", "name:the accused"),
        ("Mr​ Varnel Ostrik was detained", "name:Mr"),
        ("the victim, ag​ed 41, was taken to hospital", "age:aged"),
    ],
)
def test_surviving_names_and_ages_are_found(text, label):
    assert label in ethics.find_pii(text)


def test_detection_view_spans_are_offsets_into_the_raw_text():
    text = "the accused Va​rnel Ostrik fled near Andheri"
    (span,) = ethics.pii_spans(text)
    assert text[span.start : span.end] == "Va​rnel Ostrik" and span.kind == "name"
    text = "Mr Ｖａｒｎｅｌ Ostrik, 45, was held"
    spans = ethics.pii_spans(text)
    assert [text[s.start : s.end] for s in spans] == ["Ｖａｒｎｅｌ Ostrik", "45"]


def test_detection_view_is_only_built_for_non_ascii_text():
    assert ethics._detection_view("Mr Varnel Ostrik was detained") is None
    assert ethics._detection_view("plain — dash") is None  # NFKC-stable, no format character
    view, origin = ethics._detection_view("a​bｃ")
    assert view == "abc" and origin == [0, 2, 3]


@pytest.mark.parametrize(
    "text",
    [
        "a resident of P. D'Mello Road said",
        "a resident of S.V. Road said the lane was closed",
        "traffic on L.B.S. Marg and S.V. Road",
        "Mr. A.C. repair shop near Andheri",
        "one S.T. bus stalled near Andheri",
    ],
)
def test_initials_in_toponyms_are_not_names(text):
    assert ethics.find_pii(text) == []


def test_descriptors_never_repeat_the_name_or_the_age():
    text = f"Mr {FICTIONAL[0]}, 41, and Dr {FICTIONAL[1]} (a 52-year-old) were questioned"
    hits = ethics.find_pii(text)
    assert len(hits) >= 3
    blob = " ".join(hits)
    for word in (*FICTIONAL[0].split(), *FICTIONAL[1].split(), "41", "52"):
        assert word not in blob


def test_redacting_every_span_leaves_nothing_to_find():
    texts = [
        f"Mr {FICTIONAL[0]}, 41, of Andheri was held after the crash near Kalanagar junction",
        f"the accused {FICTIONAL[3]} and Constable {FICTIONAL[2]}, a 35-year-old, were named near Andheri",
        f"a resident of Marine Drive, aged 60, said Shri {FICTIONAL[1]} called the police",
        f"Mr R. K. {FICTIONAL[2].split()[1]} of Andheri met Constable A.B. {FICTIONAL[0].split()[1]} near Andheri",
    ]
    for text in texts:
        spans = ethics.pii_spans(text)
        assert spans, text
        out, last = [], 0
        for s in spans:
            out.append(text[last : s.start])
            out.append("[PERSON]" if s.kind == "name" else "[AGE]")
            last = s.end
        out.append(text[last:])
        redacted = "".join(out)
        assert ethics.find_pii(redacted) == [], redacted
        for name in FICTIONAL:
            for word in name.split():
                assert word not in redacted
        assert "Marine Drive" in redacted or "Kalanagar junction" in redacted or "Andheri" in redacted


def _redact(text: str) -> str:
    out, last = [], 0
    for s in ethics.pii_spans(text):
        out.append(text[last : s.start])
        out.append("[PERSON]" if s.kind == "name" else "[AGE]")
        last = s.end
    out.append(text[last:])
    return "".join(out)


@pytest.mark.parametrize(
    "text",
    [
        "the accused Va​rnel Ostrik, 41, fled near Andheri",
        "the accused Va­rnel Ostrik (41) fled near Andheri",
        "Mr Ｖａｒｎｅｌ Ostrik, a ４１-year-old, was held near Andheri",
        "the acc​used Varnel Ostrik fled near Andheri",
        "Driver [PERSON], 45, beaten by mob near Andheri",
        "Police said Mr Patil was detained near Andheri",
    ],
)
def test_redacting_every_span_also_removes_hidden_names(text):
    """The redaction recipe holds through the detection view: its spans are raw offsets, so replacing them
    removes a name that a zero-width or fullwidth character hid from a raw scan, and nothing is left to find."""
    redacted = _redact(text)
    assert ethics.find_pii(redacted) == [], redacted
    for fragment in ("rnel", "Ostrik", "ｌ", "41", "45", "Patil"):
        assert fragment not in redacted, (fragment, redacted)
    assert "Andheri" in redacted


#: Words that make a multi-word gazetteer phrase a PLACE: a place type, or a generic place word that is not also
#: a newsroom word.
_PLACE_TYPE_WORDS = frozenset({
    "road", "roads", "rd", "highway", "circle", "circus", "junction", "bridge", "setu", "flyover", "underpass",
    "overbridge", "ramp", "link", "connector", "approach", "crossing", "more", "phari", "chowrasta", "street",
    "st", "lane", "sarani", "avenue", "bypass", "station", "stn", "railway", "metro", "terminus", "bus",
    "airport", "terminal", "gate", "forecourt", "end", "market", "bazar", "square", "park", "gardens", "garden",
    "lake", "sarobar", "ghat", "temple", "mandir", "math", "masjid", "cathedral", "hospital", "college",
    "medical", "university", "school", "club", "sangha", "sammilani", "sarbojanin", "durgotsav", "puja",
    "pally", "stadium", "indoor", "krirangan", "ground", "grounds", "maidan", "mela", "prangan", "centre",
    "memorial", "hall", "building", "buildings", "bhavan", "bhawan", "sadan", "court", "headquarters", "police",
    "thana", "ps", "kalibari", "town", "city", "sector", "nagar", "para", "bag", "kolkata", "calcutta",
    "howrah", "bengal", "india", "salt", "new", "point", "phanri", "chourasta", "ave", "pass", "area", "lakes",
    # Mumbai's place types (the Mumbai gazetteer: wards, low-lying spots, subways, chowpatties, koliwadas …)
    "marg", "chowk", "naka", "subway", "drive", "complex", "chowpatty", "koliwada", "river", "east", "west",
    "mumbai", "maharashtra", "sea", "creek", "bunder", "wadi", "pada", "gaon", "expressway", "colony", "estate",
    "hills", "beach", "pumping", "sthanak", "pul", "setu", "mandal", "ward",
    # the generator's Mumbai place words (scripts/gen_osint_gazetteer.py PLACE_TYPE_WORDS)
    "pandal", "promenade", "bandstand", "center", "hq", "freeway", "hwy", "dargah", "racecourse", "causeway",
    "lines", "nadi", "basilica", "church", "dome", "village", "galli", "line", "rob", "weh", "eeh", "sclr", "gmlr",
    "hill",
})
_ROAD_CODE = re.compile(r"(?:nh|ne|sh)\d+")
#: Reviewed multi-word phrases with no place-type word: two-word place names of Kolkata (the generator's list for
#: the Kolkata pack).
_REVIEWED_PHRASES = frozenset({
    "dum dum", "behala notun dal", "badamtala ashar sangha", "prakriti tirtha", "ipgmer sskm", "amri dhakuria",
    "thanthania kali bari", "sixty six pally", "boipara", "ekdalia evergreen", "rajarhat new town", "chetla agrani",
    # the Mumbai pack's reviewed two-word place names (the generator's REVIEWED_PHRASES)
    "vile parle", "lower parel", "antop hill", "haji ali", "lalbaugcha raja", "kemps corner", "opera house",
    "queens necklace", "saat rasta", "andhericha raja", "chinchpoklicha chintamani", "khetwadi ganraj",
    "cuffe parade", "dadar tt", "parel tt", "hind mata", "hindmata dadar", "hindmata dadar tt", "lal baug",
    "santa cruz", "teli gali", "ganesh galli",
})


@pytest.mark.parametrize("which", ["repo", "test"])
def test_gazetteer_phrases_are_places_never_bare_person_names(monkeypatch, which):
    """Forward-looking lint (OS-3 regenerates the gazetteer). A multi-word phrase protects a cue-introduced name
    after ANY cue, so each one must carry a place-type word or a road code: a phrase that is only a person's name
    (a POI's namesake, "<given> <surname>") would protect that person after "Mr". A new exception needs a review
    and an entry in _REVIEWED_PHRASES. Phrases named after a person but carrying the type ("... Overbridge",
    "... Marg") are fine: the name alone is not a phrase, so "Mr <namesake>" is still flagged. Run on the repo
    gazetteer and on the synthetic Mumbai test gazetteer."""
    if which == "repo":
        monkeypatch.delenv(ethics.GAZETTEER_ENV)
        ethics.reset_place_phrases()
    multi = [p for p in ethics.place_phrases() if " " in p]
    assert len(multi) >= 20
    bare = sorted(
        p for p in multi
        if p not in _REVIEWED_PHRASES
        and not any(w in _PLACE_TYPE_WORDS or _ROAD_CODE.fullmatch(w) for w in p.split())
    )
    assert bare == []


def test_single_word_aliases_protect_only_after_a_residence_cue():
    # "kurla" is a single-word place alias; after an honorific it reads as a person's name
    assert ethics.find_pii("Mr Kurla") != []
    assert ethics.find_pii("a resident of Kurla") == []


def test_protect_argument_adds_places():
    assert ethics.find_pii("a resident of Zorvanpur") != []
    assert ethics.find_pii("a resident of Zorvanpur", protect=["Zorvanpur"]) == []


def test_gazetteer_drives_place_protection(monkeypatch, tmp_path):
    gaz = tmp_path / "gaz.json"
    gaz.write_text(
        json.dumps(
            {
                "meta": {"licence": "test"},
                "entries": [{"canonical_name": "Kemlo Nagar (East)", "surface_forms": ["kemlo nagar"]}],
            }
        )
    )
    monkeypatch.setenv(ethics.GAZETTEER_ENV, str(gaz))
    ethics.reset_place_phrases()
    assert "kemlo nagar" in ethics.place_phrases()
    assert ethics.find_pii("a resident of Kemlo Nagar") == []
    # without the gazetteer the detector is stricter, never laxer
    monkeypatch.setenv(ethics.GAZETTEER_ENV, str(tmp_path / "missing.json"))
    ethics.reset_place_phrases()
    assert ethics.place_phrases() == frozenset()
    assert ethics.find_pii("a resident of Marine Drive") != []


def test_repo_gazetteer_is_found_and_read(monkeypatch):
    monkeypatch.delenv(ethics.GAZETTEER_ENV)
    ethics.reset_place_phrases()
    path = ethics.gazetteer_path()
    assert path is not None and path.name == "osint_gazetteer.json"
    assert len(ethics.place_phrases()) > 50


def test_the_test_gazetteer_carries_the_mumbai_toponyms():
    phrases = ethics.place_phrases()
    for p in ("marine drive", "kalanagar junction", "dr ambedkar road", "dadar tt circle", "andheri",
              "western express highway", "hindmata", "netaji subhash chandra bose road"):
        assert p in phrases


def test_every_fixture_is_clean():
    for name in testing.__all__:
        fn = getattr(testing, name)
        if not callable(fn):
            continue
        value = fn()
        for item in value if isinstance(value, list) else [value]:
            dumped = item.model_dump(mode="json")
            ethics.assert_no_person_keys(dumped)
            for text in _strings(dumped):
                assert ethics.find_pii(text) == [], (name, text[:80])


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from _strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from _strings(v)
