"""OSINT lockstep (contract C3 + X18/X20): every mirror of the shared vocabulary agrees.

* the six new event kinds across the 021 CHECKs (both tables), ``events.EVENT_KINDS``,
  the emulator's ``profiles.EVENT_KINDS``, the deck's ``ops/types.ts`` ``EventKind``
  and ``ops/client.ts`` ``KINDS`` (parsed by regex) and
  ``osint_common.kinds.ALL_EVENT_KINDS``;
* the verification states and source kinds across 021, the oracle, osint_common and the
  deck;
* the person-key denylist in ``events/__init__.py`` equals
  ``osint_common.ethics.FORBIDDEN_KEY_RE`` (string, exemptions, the opaque-id escape and
  fail-closed matching, key by key, over 20,000 opaque ids and payload by payload);
* every entity and feed kind the brain names is one the oracle serves (a subset rule
  that holds at every wave), and the deck's mirrors EQUAL the oracle's — ``ENTITY_KINDS``
  entity for entity and ``CITY_FEED_KINDS`` (the wire kinds: the 7 lanes + ``osint``)
  against the served ``city_common.FEED_KINDS`` (OS-DECK-A tightens the deck rule to
  equality in wave D; the lane list never carries ``osint``);
* the packaging rules: ``traffic_oracle.osint`` imports nothing,
  ``traffic_oracle.osint.types`` re-exports ``osint_common.types``, and the oracle core
  (``events/``, ``city/``) never imports ``osint_*``.
"""

from __future__ import annotations

import ast
import hashlib
import re
import sys
import uuid
from pathlib import Path

import pytest

from osint_common import ethics, kinds
from traffic_oracle import events
from traffic_oracle.city import common as city_common

ORACLE = Path(__file__).resolve().parents[1]
SERVICES = ORACLE.parent
M021 = SERVICES / "corridor-store" / "migrations" / "021_osint_events.sql"
TYPES_TS = SERVICES / "command-deck" / "src" / "lib" / "ops" / "types.ts"
CLIENT_TS = SERVICES / "command-deck" / "src" / "lib" / "ops" / "client.ts"
CITY_API_TS = SERVICES / "command-deck" / "src" / "lib" / "gods-eye" / "city-api.ts"
BRAIN_SERVER = SERVICES / "convoy-brain" / "src" / "convoy_brain" / "mcp" / "server.py"
NEW_KINDS = (
    "reported_crime", "public_disorder", "road_accident", "hazard", "flooding", "infra_failure",
)


def _sql_no_comments() -> str:
    return re.sub(r"--[^\n]*", "", M021.read_text())


def _check_values(constraint: str) -> set[str]:
    """The quoted values inside ``ADD CONSTRAINT <constraint> CHECK (...)`` (balanced
    parentheses)."""
    text = _sql_no_comments()
    m = re.search(r"ADD CONSTRAINT " + constraint + r" CHECK \(", text)
    assert m, constraint
    depth, i = 0, m.end() - 1
    while True:
        depth += {"(": 1, ")": -1}.get(text[i], 0)
        if depth == 0:
            break
        i += 1
    return set(re.findall(r"'([A-Za-z_\-]+)'", text[m.end() : i]))


def _ts_union(path: Path, name: str) -> set[str]:
    text = path.read_text()
    m = re.search(r"export type " + name + r"\s*=([^;]+);", text)
    assert m, f"{name} not found in {path.name}"
    body = re.sub(r"//[^\n]*", "", m.group(1))
    return set(re.findall(r"'([A-Za-z_\-]+)'", body))


def _ts_array(path: Path, decl: str) -> set[str]:
    text = path.read_text()
    m = re.search(decl + r"[^=]*=\s*\[([^\]]*)\]", text)
    assert m, f"{decl} not found in {path.name}"
    return set(re.findall(r"'([a-z_]+)'", re.sub(r"//[^\n]*", "", m.group(1))))


def _py_tuple(path: Path, name: str) -> tuple[str, ...]:
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == name for t in node.targets
        ):
            return tuple(ast.literal_eval(node.value))
    raise AssertionError(f"{name} not found in {path}")


# ── event kinds (C3) ─────────────────────────────────────────────────────────


def test_six_new_kinds_in_every_mirror():
    sixteen = set(events.EVENT_KINDS)
    assert len(events.EVENT_KINDS) == 16 and set(NEW_KINDS) <= sixteen
    assert tuple(events.EVENT_KINDS) == kinds.ALL_EVENT_KINDS  # same order too
    assert kinds.NEW_EVENT_KINDS == NEW_KINDS
    assert _check_values("corridor_events_event_kind_check") == sixteen
    assert _check_values("event_profiles_event_kind_check") == sixteen

    sys.path.insert(0, str(SERVICES / "event-emulator" / "src"))
    from event_emulator.profiles import EVENT_KINDS as EMU_KINDS
    from event_emulator.profiles import PROFILES

    assert set(EMU_KINDS) == sixteen
    assert all(p.event_kind not in NEW_KINDS for p in PROFILES.values()), (
        "no profile uses an OSINT kind"
    )

    assert _ts_union(TYPES_TS, "EventKind") == sixteen
    assert _ts_array(CLIENT_TS, r"const KINDS: EventKind\[\]") == sixteen


def test_osint_kinds_never_include_crime_incident():
    values = _check_values("resolved_events_sajag_event_kind_check")
    assert values == set(kinds.OSINT_EVENT_KINDS)
    assert "crime_incident" not in values and "vehicle_pursuit" not in values


# ── verification states and source kinds ─────────────────────────────────────


def test_verification_states_agree():
    six = set(kinds.VERIFICATION_STATES)
    assert len(six) == 6
    assert tuple(events.VERIFICATION_STATES) == kinds.VERIFICATION_STATES
    assert _check_values("corridor_events_verification_state_check") == six
    table = _sql_no_comments().split("CREATE TABLE IF NOT EXISTS osint.resolved_events", 1)[1]
    body = table.split(");", 1)[0]
    m = re.search(
        r"verification_state TEXT NOT NULL CHECK \(verification_state IN \((.*?)\)\)", body, re.S
    )
    assert m and set(re.findall(r"'([A-Z\-]+)'", m.group(1))) == six
    assert _ts_union(TYPES_TS, "VerificationState") == six


def test_source_kinds_agree():
    four = {"operator", "brain", "emulator", "osint"}
    assert set(events.SOURCE_KINDS) == set(kinds.SOURCE_KINDS) == four
    assert _check_values("corridor_events_source_kind_check") == four
    assert _ts_union(TYPES_TS, "SourceKind") == four


def test_deck_event_source_is_not_widened():
    """EventSource is a FETCH source, not provenance (plan R14): unchanged."""
    assert _ts_union(TYPES_TS, "EventSource") == {
        "live-events-api", "live-movements-api", "offline-fixture",
    }


# ── the person-key denylist ──────────────────────────────────────────────────


#: Compound keys the frozen regex matches as a substring (no token equals a term):
#: forbidden on both sides.
COMPOUND = (
    "authorname", "personid", "personname", "postauthor", "reportername", "victimname",
    "suspectname", "ownername", "userName", "faceprint",
)
#: Lookalikes holding a term: the check fails closed, so they are forbidden on both sides.
LOOKALIKES = (
    "interface", "facet", "typeface", "authority", "issuing_authority", "handler",
    "ownership", "suspected_cause",
)

#: Opaque ids whose hex digits spell "face": a real sha1 signal id (the review's
#: reproduction) and a canonical uuid. Whole, they are ids on both sides; any other shape
#: of them is still checked.
FACE_SIGNAL_ID = hashlib.sha1(b"google_news_rss:synthetic:559").hexdigest()
FACE_UUID = "0b7e3c2a-face-4d1e-9a8b-5c6d7e8f9a0b"
OPAQUE_LOOKALIKES = (
    FACE_SIGNAL_ID.upper(), FACE_UUID.upper(), FACE_SIGNAL_ID + "\n", FACE_SIGNAL_ID[1:],
    FACE_SIGNAL_ID + "0", f"event:{FACE_UUID}", f"osint_event:{FACE_UUID}",
    f"signal_{FACE_SIGNAL_ID}", FACE_UUID.replace("-", ""),
)

CORPUS = (
    "author", "Author", "authors", "authorName", "author_name", "post_author", "URLAuthor",
    "person", "persons", "person_id", "handle", "user_handle", "username", "byline",
    "reporter", "poster", "uploader", "suspect", "accused", "victim", "victim_count", "owner",
    "vehicle_owner", "driver_name", "driverName", "driver-name", "face", "faces", "faceId",
    "biometric", "biometrics", "individual_id", "individualId", "IndividualAge",
    "ａｕｔｈｏｒ", "authoŕ", "driveŕ_name", "Touches_Persons",
    "surfaced_count", "surface_form",
    *COMPOUND, *LOOKALIKES, *OPAQUE_LOOKALIKES,
    # allowed: the exempt contract keys, whole opaque ids, and keys holding no term
    "surface_forms", "surfaced", "touches_persons", "reported_at", "publisher", "publishers",
    "posted_at", "individuals", "driver", "source_feeds", "geocoder", "geocode_confidence",
    "osint_event_id", "dss_id", FACE_SIGNAL_ID, FACE_UUID,
)

#: Keys that must read forbidden on both sides.
FORBIDDEN = (
    *COMPOUND, *LOOKALIKES, *OPAQUE_LOOKALIKES, "authorName", "driverName", "individualId",
    "faceprint", "face_id", "victims",
)
#: Keys that must read allowed on both sides.
ALLOWED = (
    "surface_forms", "surfaced", "touches_persons", "publishers", "source_feeds", "geocoder",
    "driver", FACE_SIGNAL_ID, FACE_UUID,
)


def test_person_key_regex_is_the_ethics_denylist():
    assert events.PERSON_KEY_RE == ethics.FORBIDDEN_KEY_RE


def test_person_key_exemptions_are_the_ethics_exemptions():
    assert events._PERSON_KEY_EXEMPT == ethics.EXEMPT_KEYS
    assert events._PERSON_KEY_EXEMPT_TYPES == dict(ethics._EXEMPT_VALUE_TYPES)


def test_person_key_opaque_ids_are_the_ethics_opaque_ids():
    assert events._PERSON_KEY_OPAQUE_ID_RE.pattern == ethics.OPAQUE_ID_RE
    assert "face" in FACE_SIGNAL_ID and "face" in FACE_UUID


def _opaque_ids(n: int) -> list[str]:
    """Deterministic sha1 signal ids and uuids: about 1 sha1 in 2,000 spells "face"."""
    namespace = uuid.uuid5(uuid.NAMESPACE_URL, "https://sajag.example/osint/lockstep")
    sha1s = [
        hashlib.sha1(f"google_news_rss:synthetic:{i}".encode()).hexdigest() for i in range(n)
    ]
    return sha1s + [str(uuid.uuid5(namespace, f"id-{i}")) for i in range(n)]


def _generated_corpus() -> list[str]:
    """Every term in many spellings, every osint_common model field, every raw key and
    20,000 opaque ids."""
    from pydantic import BaseModel

    from osint_common import types as ot

    out: list[str] = []
    for term in ethics.FORBIDDEN_KEY_RE.split("|"):
        bare = term.rstrip("_")
        camel = "".join(p.capitalize() for p in bare.split("_"))
        out += [
            term, term.upper(), bare, bare + "s", "x" + bare, bare + "name", "post_" + bare,
            "my" + camel, camel + "Id", bare.replace("_", "-"), bare.replace("_", "") + "_x",
            "a." + bare,
        ]
    for name in ot.__all__:
        obj = getattr(ot, name)
        if isinstance(obj, type) and issubclass(obj, BaseModel):
            out += list(obj.model_fields)
    out += sorted(ethics.RAW_ALLOWED_KEYS)
    ids = _opaque_ids(10000)
    face = [i for i in ids if "face" in i]
    out += ids + [i.upper() for i in face] + [f"event:{i}" for i in face]
    return out


@pytest.mark.parametrize("key", CORPUS)
def test_person_key_matching_is_identical(key):
    assert events.is_person_key(key) == ethics.is_forbidden_key(key), key


def test_person_key_matching_is_identical_over_a_generated_corpus():
    corpus = _generated_corpus()
    assert len(corpus) > 20000
    diff = [k for k in corpus if events.is_person_key(k) != ethics.is_forbidden_key(k)]
    assert diff == []


def test_opaque_ids_never_read_as_person_keys_on_either_side():
    # 15,000 of each kind: the namespace's ids spell "face" often enough
    # (11 times) that the check below is a real test of the exemption
    ids = _opaque_ids(15000)
    assert sum("face" in i for i in ids) >= 5
    assert not [i for i in ids if events.is_person_key(i) or ethics.is_forbidden_key(i)]


@pytest.mark.parametrize("key", FORBIDDEN)
def test_both_sides_fail_closed(key):
    assert events.is_person_key(key) and ethics.is_forbidden_key(key)


@pytest.mark.parametrize("key", ALLOWED)
def test_both_sides_allow_the_exempt_and_the_harmless(key):
    assert not events.is_person_key(key) and not ethics.is_forbidden_key(key)


PAYLOADS = (
    {"source_feeds": ["google_news_rss"], "publishers": ["news-a.example"]},
    {"touches_persons": False, "surfaced": 2, "surface_forms": ["taratala", "তারাতলা"]},
    {"touches_persons": "someone"},
    {"surfaced": ["x"]},
    {"surface_forms": ["taratala", 3]},
    {"deep": [{"x": {"victimname": "y"}}]},
    {"deep": [{"x": {"Authority": "y"}}]},
    {"deep": [{"x": {"geocoder": "gazetteer_exact"}}]},
    # maps keyed by opaque ids (a geocode per signal id): allowed even when an id spells
    # "face" ...
    {"geocodes": {FACE_SIGNAL_ID: {"geocoder": "gazetteer_exact"}}, "by_uuid": {FACE_UUID: 1}},
    # ... but only whole and canonical
    {"by_uuid": {FACE_UUID.upper(): 1}},
    {"geocodes": {FACE_SIGNAL_ID: {"faceprint": "x"}}},
)


@pytest.mark.parametrize("payload", PAYLOADS)
def test_person_key_walkers_agree(payload):
    try:
        ethics.assert_no_person_keys(payload)
        refused = False
    except ValueError:
        refused = True
    assert (events._person_key_in(payload) is not None) == refused


# ── entity and feed kinds: the brain names a subset, the deck mirrors exactly ──


def _deck_wire_kinds() -> set[str]:
    """The deck's WIRE kinds (``CITY_FEED_KINDS`` — the 7 lanes + ``osint``):
    the array literal spreads ``FEED_KINDS`` and appends the wire-only kind,
    so the parse resolves the spread instead of reading it as one token."""
    text = CITY_API_TS.read_text()
    m = re.search(r"export const CITY_FEED_KINDS[^=]*=\s*\[([^\]]*)\]", text)
    assert m, "CITY_FEED_KINDS not found in city-api.ts"
    body = re.sub(r"//[^\n]*", "", m.group(1))
    lanes = _ts_array(CITY_API_TS, r"export const FEED_KINDS: readonly FeedKind\[\]")
    out: set[str] = set()
    for token in body.split(","):
        token = token.strip()
        if not token:
            continue
        if token.startswith("..."):
            name = token[3:]
            assert name == "FEED_KINDS", f"unexpected spread {name}"
            out |= lanes
        else:
            found = re.fullmatch(r"'([a-z_]+)'", token)
            assert found, f"unexpected token {token!r}"
            out.add(found.group(1))
    return out


def test_brain_kinds_are_served_by_the_oracle():
    # the snapshot's kinds (GET /city/entities?kinds=), and every URN kind the oracle
    # resolves: the snapshot kinds plus 'segment', which only the dossier serves
    # (city/common.DOSSIER_KINDS)
    served_entities = set(city_common.ENTITY_KINDS)
    served_urn_kinds = set(city_common.DOSSIER_KINDS)
    served_feeds = set(city_common.FEED_KINDS)
    brain_entities = set(_py_tuple(BRAIN_SERVER, "_CITY_ENTITY_KINDS_DEF"))
    brain_feeds = set(_py_tuple(BRAIN_SERVER, "_CITY_FEED_KINDS_DEF"))
    assert brain_entities and brain_feeds
    assert brain_entities <= served_entities, brain_entities - served_entities
    assert brain_feeds <= served_feeds, brain_feeds - served_feeds


def test_deck_kinds_equal_the_oracles():
    """OS-DECK-A tightens the deck mirror to EQUALITY (the plan's subset rule
    held at every earlier wave): city-api.ts ENTITY_KINDS — the deck's URN
    vocabulary — equals every kind the oracle resolves (the snapshot kinds
    plus ``segment``, which only the dossier serves; the snapshot remainder
    equals ``ENTITY_KINDS`` exactly), and the deck's WIRE kinds
    (``CITY_FEED_KINDS``) equal the oracle's served ``FEED_KINDS``. The
    deck's LANES (``FEED_KINDS``) stay the 7 lanes — an osint row rides the
    Events lane through ``feedLane``; ``osint`` is a wire kind, never a
    lane."""
    served_entities = set(city_common.ENTITY_KINDS)
    served_urn_kinds = set(city_common.DOSSIER_KINDS)
    served_feeds = set(city_common.FEED_KINDS)
    deck_entities = _ts_array(CITY_API_TS, r"export const ENTITY_KINDS")
    deck_lanes = _ts_array(CITY_API_TS, r"export const FEED_KINDS: readonly FeedKind\[\]")
    deck_wire = _deck_wire_kinds()
    assert deck_entities and deck_lanes and deck_wire
    assert deck_entities == served_urn_kinds, deck_entities ^ served_urn_kinds
    assert deck_entities - {"segment"} == served_entities, deck_entities - {"segment"} ^ served_entities
    assert deck_wire == served_feeds, deck_wire ^ served_feeds
    assert "osint" not in deck_lanes and "osint" in deck_wire


# ── packaging (X18/X20) ──────────────────────────────────────────────────────


def _imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text())
    out: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out.extend(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            out.append(node.module or "")
    return out


def test_osint_package_init_imports_nothing():
    init = ORACLE / "src" / "traffic_oracle" / "osint" / "__init__.py"
    assert _imports(init) == []
    tree = ast.parse(init.read_text())
    assert len(tree.body) == 1 and isinstance(tree.body[0], ast.Expr)  # a docstring only


def test_osint_types_reexports_osint_common():
    import osint_common.types as canonical

    import traffic_oracle.osint.types as shim

    for name in canonical.__all__:
        assert getattr(shim, name) is getattr(canonical, name), name
    assert shim.__all__ == canonical.__all__


def test_oracle_core_never_imports_osint_packages():
    src = ORACLE / "src" / "traffic_oracle"
    core = [src / "events", src / "city"]
    for root in core:
        for path in root.rglob("*.py"):
            bad = [m for m in _imports(path) if m.split(".")[0].startswith("osint_")]
            assert not bad, f"{path.relative_to(ORACLE)} imports {bad}"
