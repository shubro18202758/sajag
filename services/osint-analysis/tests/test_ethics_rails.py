"""Ethics rails across the package (OSINT SPEC §0, §4): no word of the previous city or product in any file, no
person field in any structure the package builds, crime_incident never emitted, and no camera, image or frame path to
classify from."""

from __future__ import annotations

import dataclasses
import hashlib
import re
from pathlib import Path

import pytest

from osint_common import ethics
from osint_analysis import attach, correlate, credibility, fusion

PACKAGE = Path(__file__).resolve().parents[1]

#: sha256 prefixes of the words this package must never carry: the city it was forked from, its state, language,
#: places, agencies and source names, the previous product's name, and other products and events the project's rules
#: name. Kept as hashes so that this file never writes them either; a hit reports the hash, never the word.
_DENIED_WORD_HASHES: frozenset[str] = frozenset(
    {
        "1fff55ae51b6ec52", "0f31e6ebe465b032", "866e67fdbbb6917d", "9734621f6f5b96a1", "f5dd232ee6b02958",
        "6e5dc0f68493628f", "16284b1122023378", "ac6cc1420a461c75", "dfbc3f147f55cdff", "457f83b15cb1bef1",
        "14dfd71aa0aa2eaf", "55104d2b6257c8ca", "bb3e899d9112c8df", "4c52b533310310b1", "2571649f86fb7594",
        "844b626737fc4574", "a260eac85e1ea834", "13d7c3e63b967652", "2cfc5335969c9228", "74c860f63661b29c",
        "13ed070478ef62c3", "a56f3dbc3053cc78",
    }
)
_WORDS = re.compile(r"[a-z_]+")
#: The previous city's script block (U+0A80-U+0AFF): the package reads Marathi and Hindi, never that one.
_OLD_SCRIPT = re.compile("[\u0a80-\u0aff]")


def _files() -> list[Path]:
    return sorted(p for p in PACKAGE.rglob("*") if p.is_file() and "__pycache__" not in p.parts)


def test_no_word_of_the_previous_city_or_product_anywhere_in_the_package():
    hits = []
    for path in _files():
        text = path.read_text(encoding="utf-8", errors="replace")
        for word in set(_WORDS.findall(text.lower())):
            digest = hashlib.sha256(word.encode()).hexdigest()[:16]
            if digest in _DENIED_WORD_HASHES:
                hits.append((path.name, digest))
        if _OLD_SCRIPT.search(text):
            hits.append((path.name, "script:U+0A80"))
    assert not hits, hits


@pytest.mark.parametrize(
    "cls",
    [fusion.Member, fusion.BaseCluster, correlate.Situation, credibility.Credibility, attach.LiveSubject],
)
def test_no_internal_structure_has_a_person_field(cls):
    for f in dataclasses.fields(cls):
        assert not ethics.is_forbidden_key(f.name), f"{cls.__name__}.{f.name}"


def test_no_camera_image_or_frame_input_path():
    """Crime enters only from reported text: no module reads an image, a frame or a camera stream."""
    banned = re.compile(r"\b(?:cv2|PIL|imageio|torchvision|VideoCapture|frame_bytes|image_bytes|rtsp://)\b")
    for path in (PACKAGE / "src").rglob("*.py"):
        assert not banned.search(path.read_text(encoding="utf-8")), path.name


def test_crime_incident_appears_only_in_the_guards():
    """The string crime_incident appears in the source only to refuse it."""
    for path in (PACKAGE / "src").rglob("*.py"):
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if "crime_incident" in line:
                assert re.search(r"never|FORBIDDEN|refus|ANPR|guard|frozenset", line, re.I), f"{path.name}:{n}"
