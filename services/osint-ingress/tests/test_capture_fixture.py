"""The committed synthetic capture (``tests/fixtures/capture/``): import-poc reads it unchanged; per-source counts;
every publisher is fictional (``*.example``, the community ``reddit.com/r/example_city``) or ``sachet.ndma.gov.in``
(the replica's own schema); redaction is counted; its README marks every file, and every file is synthetic (no real
capture is committed, plan R13)."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from collections import Counter

from conftest import CAPTURE, FIXTURES, PACKAGE, POC_RAW, parse_cache

from osint_ingress.cache import Cache
from osint_ingress.connectors import build_connectors
from osint_ingress.importer import CAPTURE_FILES, SACHET_CAPTURE_RE, import_capture

EXPECTED = {"sachet_cap": 7, "google_news_rss": 8, "news_rss": 6, "gdelt_events": 2, "gdelt_doc": 5, "reddit_rss": 4}


def test_import_poc_cli_reads_the_capture(tmp_path):
    env = dict(os.environ, PYTHONPATH=os.pathsep.join(str(PACKAGE / p) for p in ("src", "../osint-common/src")))
    proc = subprocess.run(
        [sys.executable, "-m", "osint_ingress", "import-poc", str(CAPTURE), str(tmp_path / "cache")],
        cwd=PACKAGE, env=env, capture_output=True, text=True, timeout=60,
    )
    assert proc.returncode == 0, proc.stderr[-1000:]
    out = json.loads(proc.stdout)
    assert set(out["imported"]) == set(EXPECTED) and out["gdelt_export_blobs"] == ["20261020120000.export.CSV.zip"]
    assert out["ignored"] == ["README.md"]
    cache = Cache(tmp_path / "cache")
    assert all(cache.latest(n) is not None and cache.latest(n).origin == "import-poc" for n in EXPECTED)


def test_per_source_counts_publishers_and_redaction(tmp_path, protect):
    import_capture(CAPTURE, tmp_path / "cache")
    got = parse_cache(Cache(tmp_path / "cache"), build_connectors(), protect)
    assert {k: len(v) for k, v in got.items()} == EXPECTED
    sigs = [s for v in got.values() for s in v]
    for s in sigs:
        assert (
            s.publisher.endswith(".example")
            or s.publisher == "reddit.com/r/example_city"
            or s.publisher == "sachet.ndma.gov.in"
        ), s.publisher
        assert s.fetch_mode == "cached-sample"
    by_source = Counter()
    for s in sigs:
        by_source[s.source] += s.pii_redactions
    assert sum(by_source.values()) > 0
    assert by_source["google_news_rss"] > 0 and by_source["gdelt_doc"] > 0 and by_source["reddit_rss"] > 0
    assert by_source["news_rss"] > 0


def test_readme_marks_every_file_and_every_file_is_synthetic():
    readme = (CAPTURE / "README.md").read_text(encoding="utf-8")
    rows = dict(re.findall(r"^\|\s*`([^`]+)`\s*\|\s*\*\*(real|synthetic)\*\*", readme, re.MULTILINE))
    files = {p.name for p in CAPTURE.iterdir() if p.is_file() and p.name != "README.md"}
    assert set(rows) == files, (set(rows) ^ files)
    assert [f for f, kind in rows.items() if kind == "real"] == []
    assert (FIXTURES / "README.md").is_file()


def test_no_real_capture_is_committed():
    """The old public-domain SACHET sample of another state is gone; the Maharashtra file is a labelled replica."""
    assert [p.name for p in CAPTURE.glob("sachet_*.xml")] == ["sachet_maharashtra_synthetic.xml"]
    data = (CAPTURE / "sachet_maharashtra_synthetic.xml").read_bytes()
    assert b"SYNTHETIC REPLICA" in data and b"public domain" not in data
    assert all(re.fullmatch(rb"1999\d{12}", g) for g in re.findall(rb"<guid[^>]*>([^<]+)</guid>", data))


def test_capture_layout_matches_a_poc_raw_directory():
    names = {p.name for p in CAPTURE.iterdir() if p.is_file()}
    shared = {"gnews_live.xml", "reddit_live.rss", "gdelt_doc_live.json", "gdelt_lastupdate_live.txt"}
    assert shared <= names and shared <= set(CAPTURE_FILES)
    if POC_RAW.is_dir():
        poc = {p.name for p in POC_RAW.iterdir() if p.is_file()}
        assert shared <= poc and any(SACHET_CAPTURE_RE.match(n) for n in poc)  # the PoC's out/raw, read in place


def test_synthetic_gdelt_files_match_their_generator():
    proc = subprocess.run([sys.executable, str(FIXTURES / "build_synthetic_gdelt.py"), "--check"],
                          capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stdout + proc.stderr


# ── F-HONEST OSINT-5: the synthetic capture is SIMULATED and names no real community ──────────────────────────


def test_import_marks_the_readme_synthetic_files_and_their_signals_are_simulated(tmp_path, protect):
    from osint_ingress.importer import synthetic_files

    marked = synthetic_files(CAPTURE)
    assert marked == {p.name for p in CAPTURE.iterdir() if p.is_file() and p.name != "README.md"}
    report = import_capture(CAPTURE, tmp_path / "cache")
    assert {k: v["synthetic"] for k, v in report["imported"].items()} == {k: True for k in EXPECTED}
    cache = Cache(tmp_path / "cache")
    assert cache.latest("google_news_rss").synthetic and cache.latest("sachet_cap").synthetic  # survives a reload
    got = parse_cache(cache, build_connectors(), protect)
    for source, sigs in got.items():
        labels = {s.provenance_label for s in sigs}
        # every written file is SIMULATED, the SACHET replica included: never OFFICIAL-VERIFIED or NEWS-REPORTED
        assert labels == {"SIMULATED"}, (source, labels)


def test_a_capture_without_a_readme_is_not_synthetic(tmp_path, protect):
    import shutil

    from osint_ingress.importer import synthetic_files

    raw = tmp_path / "raw"
    raw.mkdir()
    shutil.copy(CAPTURE / "gnews_live.xml", raw / "gnews_live.xml")
    assert synthetic_files(raw) == frozenset()
    import_capture(raw, tmp_path / "cache")
    entry = Cache(tmp_path / "cache").latest("google_news_rss")
    assert not entry.synthetic
    assert {s.provenance_label for s in build_connectors()["google_news_rss"].parse(entry, protect)} == {
        "NEWS-REPORTED"}


def test_the_synthetic_posts_name_a_fictional_community_never_r_mumbai(tmp_path, protect):
    feed = (CAPTURE / "reddit_live.rss").read_text(encoding="utf-8")
    assert "r/mumbai" not in feed.lower() and 'term="example_city"' in feed
    import_capture(CAPTURE, tmp_path / "cache")
    sigs = build_connectors()["reddit_rss"].parse(Cache(tmp_path / "cache").latest("reddit_rss"), protect)
    assert len(sigs) == 4
    assert {(s.publisher, s.raw["subreddit"], s.provenance_label) for s in sigs} == {
        ("reddit.com/r/example_city", "example_city", "SIMULATED")}
