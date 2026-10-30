"""Shared fixtures. Tests never open a socket to a real host: every HTTP exchange goes through an
``httpx.MockTransport`` (wrapped by the real allow-list transport), and the only "oracle" ever dialled for real is
``127.0.0.1:9`` (the discard port: nothing listens, so the connection is refused at once)."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from pathlib import Path

import httpx
import pytest

from osint_ingress.cache import Cache
from osint_ingress.connectors import build_connectors
from osint_ingress.connectors._protect import default_protect
from osint_ingress.importer import import_capture

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
CAPTURE = FIXTURES / "capture"
HOSTILE = FIXTURES / "hostile"
PAGES = FIXTURES / "pages"
PACKAGE = HERE.parent

#: The real PoC, read in place only (never copied into the repo); absent in CI.
POC_DIR = Path("/home/sandy050405/argus/sajag/.orchestration/osint/prototype")
#: the PoC script (its file name carries the previous product's name, so it is found by pattern)
POC_SOURCE = next(iter(sorted(POC_DIR.glob("*_osint_poc.py"))), POC_DIR / "osint_poc.py")
POC_RAW = POC_DIR / "out" / "raw"
needs_poc = pytest.mark.skipif(not POC_RAW.is_dir(), reason="PoC captures not present (read in place only; CI)")

#: An oracle URL nothing listens on (the discard port): connection refused immediately.
DEAD_ORACLE = "http://127.0.0.1:9"

#: Fictional handles inside URLs in a post body (the review-r2 probes): ``(text, handle, redacted text)``. A
#: profile link, and a Reddit user page with and without a scheme. Reddit shows a bare URL as a link whose visible
#: text is the URL, so it reaches a signal's ``text``.
URL_HANDLE_PROBES = [
    ("my insta: https://instagram.com/fictus_dummyvala", "fictus_dummyvala", "my insta: [URL]"),
    ("follow reddit.com/u/kalpit_exemplar for the pics", "kalpit_exemplar", "follow [PERSON] for the pics"),
    ("details at https://www.reddit.com/user/zara_placeholderi/ thanks", "zara_placeholderi",
     "details at [PERSON] thanks"),
    ("x.com/vimal_fixturebhai posted the video of the jam", "vimal_fixturebhai", "[URL] posted the video of the jam"),
    ("see www.facebook.com/rohan.fictionwala for the photos.", "rohan.fictionwala", "see [URL] for the photos."),
]


def h12(s: str) -> str:
    """What a test may print about a real name: a 12-character SHA-256 prefix, never the name."""
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:12]


@pytest.fixture(scope="session")
def protect() -> frozenset[str]:
    return default_protect()


@pytest.fixture
def capture_cache(tmp_path: Path) -> Cache:
    """The committed synthetic capture, imported into a fresh cache."""
    import_capture(CAPTURE, tmp_path / "cache")
    return Cache(tmp_path / "cache")


@pytest.fixture
def connectors():
    return build_connectors()


def parse_cache(cache: Cache, connectors: dict, protect: frozenset[str]) -> dict[str, list]:
    out: dict[str, list] = {}
    for name, conn in connectors.items():
        entry = cache.latest(name)
        if entry is not None:
            out[name] = conn.parse(entry, protect)
    return out


class Recorder:
    """A MockTransport handler that records every request and answers from ``routes``."""

    def __init__(self, routes: dict[str, Callable[[httpx.Request], httpx.Response]] | None = None) -> None:
        self.routes = routes or {}
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        key = f"{request.url.host}{request.url.path}"
        for prefix, fn in self.routes.items():
            if key.startswith(prefix):
                return fn(request)
        return httpx.Response(404, json={"detail": "no route in the test double"})

    @property
    def hosts(self) -> list[str]:
        return [r.url.host for r in self.requests]


@pytest.fixture
def recorder() -> Recorder:
    return Recorder()
