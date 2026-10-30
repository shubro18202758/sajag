"""``import-poc``: copy a PoC-style raw capture directory into the cache layout (offline seeding and parity).

A capture directory looks like the PoC's ``out/raw/``::

    gnews_live.xml               → google_news_rss
    news_rss_live.json           → news_rss (a bundle of outlet feeds, inlined)
    reddit_live.rss              → reddit_rss
    sachet_<state>_<kind>.xml    → sachet_cap (``sachet_maharashtra_synthetic.xml``, the sandbox seed's replica; the
                                   PoC's real capture of another state, whose alerts are all filtered out)
    gdelt_doc_live.json          → gdelt_doc
    gdelt_lastupdate_live.txt    → gdelt_events (its entry references the ONE export zip it names)
    <stamp>.export.CSV.zip       → gdelt_events blobs

Exactly two inputs are meant for it (plan R13): the committed synthetic ``tests/fixtures/capture/`` (sandbox
seeding; int3cl takes nothing else) and the real PoC ``out/raw/`` read in place (parity runs on int3c, never
committed). Each file becomes the newest cache entry of its connector, marked ``origin: import-poc`` and with
``captured_at`` = the capture file's mtime, so the signals parsed from it say ``cached-sample`` with an honest
age. Any other file in the directory is ignored. Nothing here prints or logs a byte of the capture.

**Synthetic files are SIMULATED** (F-HONEST OSINT-5). A capture directory's ``README.md`` marks each file in its
table (``| `<file>` | **synthetic** | ...`` or ``**real**``); every file it marks synthetic is imported as a
``synthetic`` cache entry, so its signals carry ``provenance_label: SIMULATED`` instead of the source's prior
(``NEWS-REPORTED`` for a news feed): developer-written reports are never served as an outlet's news. A capture
without a README (the PoC's real ``out/raw/``) has no synthetic file. The report lists the synthetic files.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

from osint_ingress.cache import Cache
from osint_ingress.connectors.gdelt import export_named_by

__all__ = ["CAPTURE_FILES", "SACHET_CAPTURE_RE", "capture_target", "import_capture", "synthetic_files"]

#: capture file name → (connector, cache extension)
CAPTURE_FILES: dict[str, tuple[str, str]] = {
    "gnews_live.xml": ("google_news_rss", "xml"),
    "news_rss_live.json": ("news_rss", "json"),
    "reddit_live.rss": ("reddit_rss", "xml"),
    "gdelt_doc_live.json": ("gdelt_doc", "json"),
    "gdelt_lastupdate_live.txt": ("gdelt_events", "txt"),
}
#: A SACHET CAP RSS capture, by state: ``sachet_<state>_<kind>.xml`` (one per directory).
SACHET_CAPTURE_RE = re.compile(r"^sachet_[a-z]{2,40}_[a-z]{2,20}\.xml$")
_EXPORT = re.compile(r"^\d{14}\.export\.CSV\.zip$")
#: A README table row marking a capture file: ``| `<file>` | **synthetic** |`` (or ``**real**``).
_README_ROW = re.compile(r"^\|\s*`([^`]+)`\s*\|\s*\*\*(real|synthetic)\*\*", re.MULTILINE)
_MAX_README = 256 * 1024
_MAX_FILE = 64 * 1024 * 1024


def capture_target(fname: str) -> tuple[str, str] | None:
    """``(connector, cache extension)`` a capture file is imported as, else ``None`` (the file is ignored)."""
    if fname in CAPTURE_FILES:
        return CAPTURE_FILES[fname]
    return ("sachet_cap", "xml") if SACHET_CAPTURE_RE.match(fname) else None


def _mtime(p: Path) -> datetime:
    return datetime.fromtimestamp(p.stat().st_mtime, UTC)


def synthetic_files(capture_dir: str | Path) -> frozenset[str]:
    """The capture files the directory's ``README.md`` marks ``**synthetic**`` (none without a README)."""
    readme = Path(capture_dir) / "README.md"
    if not readme.is_file() or readme.stat().st_size > _MAX_README:
        return frozenset()
    text = readme.read_text(encoding="utf-8", errors="replace")
    return frozenset(name for name, kind in _README_ROW.findall(text) if kind == "synthetic")


def import_capture(capture_dir: str | Path, cache_dir: str | Path) -> dict[str, object]:
    """Import ``capture_dir`` into the cache at ``cache_dir``. Returns a content-free report.

    Raises ``FileNotFoundError`` when ``capture_dir`` is not a directory or holds none of the capture files.
    """
    src = Path(capture_dir)
    if not src.is_dir():
        raise FileNotFoundError(f"not a directory: {src}")
    cache = Cache(cache_dir)
    synthetic = synthetic_files(src)
    imported: dict[str, dict[str, object]] = {}
    blobs: list[str] = []
    for p in sorted(src.iterdir()):
        if p.is_file() and _EXPORT.match(p.name) and p.stat().st_size <= _MAX_FILE:
            cache.put_blob("gdelt_events", p.name, p.read_bytes())
            blobs.append(p.name)
    names = list(CAPTURE_FILES) + sorted(p.name for p in src.iterdir() if SACHET_CAPTURE_RE.match(p.name))
    for fname in names:
        connector, ext = capture_target(fname) or ("", "")
        p = src / fname
        if not connector or not p.is_file() or p.stat().st_size > _MAX_FILE:
            continue
        data = p.read_bytes()
        refs: list[str] = []
        if connector == "gdelt_events":
            item = export_named_by(data.decode("ascii", "replace"))
            if item is not None and item[0] in blobs:
                refs = [item[0]]
        entry = cache.put(connector, data, ext, captured_at=_mtime(p), origin="import-poc", blobs=refs,
                          synthetic=fname in synthetic)
        imported[connector] = {
            "file": fname,
            "bytes": entry.size,
            "sha256": entry.sha256,
            "captured_at": entry.meta()["captured_at"],
            "blobs": list(refs),
            "synthetic": fname in synthetic,
        }
    if not imported:
        raise FileNotFoundError(f"no capture files in {src}")
    known = {n for n in names if capture_target(n)} | set(blobs)
    ignored = sorted(p.name for p in src.iterdir() if p.is_file() and p.name not in known)
    return {
        "capture_dir": str(src),
        "cache_dir": str(Path(cache_dir)),
        "imported": imported,
        "gdelt_export_blobs": blobs,
        "ignored": ignored,
    }
