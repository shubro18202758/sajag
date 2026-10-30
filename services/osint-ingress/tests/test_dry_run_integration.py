"""``once --dry-run``: the connectors' signals through ``osint_analysis.pipeline.run_pipeline`` with the
``osint_geo`` resolver, in-process. Skipped until both libraries import (they arrive with OS-3 and OS-4; this
becomes active at the wave-B gate). Without them, ``--dry-run`` exits 3 ("pipeline libraries not importable").

The capture's situations are Mumbai places (the Western Express Highway near Andheri, Dadar TT circle, Hindmata), so
the situation tests also wait for the shared gazetteer (``scripts/data/osint_gazetteer.json``, read by both
``osint_geo`` and ``osint_common.ethics``) to hold Mumbai: until it is regenerated for the Mumbai pack, nothing in the
capture can be geotagged and they are skipped with that reason."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys

import pytest
from conftest import CAPTURE, PACKAGE, parse_cache

from osint_ingress.cache import Cache
from osint_ingress.connectors import build_connectors
from osint_ingress.importer import import_capture


def _importable(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


HAVE_PIPELINE = _importable("osint_analysis.pipeline") and _importable("osint_geo.resolver")
needs_pipeline = pytest.mark.skipif(not HAVE_PIPELINE, reason="osint_analysis and osint_geo not importable yet")


def _gazetteer_holds_mumbai() -> bool:
    from osint_common import ethics

    return {"hindmata", "andheri", "dadar"} <= ethics.place_phrases()


needs_mumbai_gazetteer = pytest.mark.skipif(
    not _gazetteer_holds_mumbai(),
    reason="the shared gazetteer (scripts/data/osint_gazetteer.json) does not hold Mumbai yet: regenerate it for "
           "the Mumbai pack (scripts/gen_osint_gazetteer.py)",
)
_PATHS = ("src", "../osint-common/src", "../osint-geo/src", "../osint-analysis/src")


def _env() -> dict[str, str]:
    paths = [str(PACKAGE / p) for p in _PATHS]
    if os.environ.get("PYTHONPATH"):
        paths.append(os.environ["PYTHONPATH"])  # keep whatever made the libraries importable in this process
    return dict(os.environ, PYTHONPATH=os.pathsep.join(paths))


def _capture_signals(tmp_path, protect):
    import_capture(CAPTURE, tmp_path / "cache")
    got = parse_cache(Cache(tmp_path / "cache"), build_connectors(), protect)
    return [s for v in got.values() for s in v]


def _run(signals):
    from osint_analysis.pipeline import run_pipeline
    from osint_geo.resolver import GazetteerResolver

    now = max(s.fetched_at for s in signals)
    return run_pipeline(signals, resolver=GazetteerResolver(), live=None, embedder=None, now=now)


@needs_pipeline
@needs_mumbai_gazetteer
def test_synthetic_weh_crash_yields_one_correlated_situation(tmp_path, protect):
    weh = [s for s in _capture_signals(tmp_path, protect)
           if s.source == "google_news_rss" and "Western Express Highway" in s.title]
    assert len(weh) == 5
    surfaced = [r for r in _run(weh).resolved if r.is_event]
    assert len(surfaced) == 1
    (r,) = surfaced
    assert set(r.correlated_classes) == {"road_accident", "public_conflict"} and r.subtype == "affray+collision"
    # developer-written reports stay SIMULATED through the pipeline (F-HONEST OSINT-5), on a road segment
    assert r.segment_id is not None and r.verification_state == "SIMULATED" and r.independent_publishers == 2
    assert r.sajag_event_kind != "crime_incident"


@needs_pipeline
@needs_mumbai_gazetteer
def test_synthetic_marathi_waterlogging_yields_one_situation_at_hindmata(tmp_path, protect):
    mr = [s for s in _capture_signals(tmp_path, protect) if s.source == "news_rss" and s.language == "mr"
          and s.publisher in ("news-mr-a.example", "news-mr-b.example")]
    assert len(mr) == 4  # two Hindmata reports, two general items
    surfaced = [r for r in _run(mr).resolved if r.is_event]
    assert len(surfaced) == 1
    (r,) = surfaced
    assert r.event_class == "urban_flooding" and r.verification_state == "SIMULATED"


@needs_pipeline
@needs_mumbai_gazetteer
def test_whole_capture_yields_the_four_situations(tmp_path, protect):
    signals = _capture_signals(tmp_path, protect)
    result = _run(signals)
    surfaced = [r for r in result.resolved if r.is_event]
    assert len(surfaced) == 4, [(r.event_class, r.toponym) for r in surfaced]
    crash = [r for r in surfaced if set(r.correlated_classes) == {"road_accident", "public_conflict"}]
    crime = [r for r in surfaced if r.event_class == "reported_crime"]
    flooding = [r for r in surfaced if r.event_class == "urban_flooding" and not r.area_level]
    sachet = [r for r in surfaced if r.area_level]
    assert len(crash) == 1 and len(crime) == 1 and len(flooding) == 1
    assert len(sachet) == 1 and sachet[0].source_count == 1 and sachet[0].verification_state == "SIMULATED"
    assert {r.verification_state for r in surfaced} == {"SIMULATED"}  # every file of the seed is synthetic
    assert result.counts.outside_city_held >= 1  # the 6 state-level nowcasts
    assert result.counts.social_held >= 2  # single social posts are held (aggregate-only)
    assert not [r for r in result.resolved if r.sajag_event_kind == "crime_incident"]
    assert sum(s.pii_redactions for s in signals) > 0


def test_the_capture_signals_are_redacted_and_simulated(tmp_path, protect):
    """What holds whatever the gazetteer: 32 signals, every one SIMULATED, redactions made."""
    signals = _capture_signals(tmp_path, protect)
    assert len(signals) == 32 and {s.provenance_label for s in signals} == {"SIMULATED"}
    assert sum(s.pii_redactions for s in signals) > 0


@needs_pipeline
@needs_mumbai_gazetteer
def test_cli_dry_run_prints_machine_result(tmp_path):
    import_capture(CAPTURE, tmp_path / "cache")
    proc = subprocess.run(
        [sys.executable, "-m", "osint_ingress", "once", "--offline", "--dry-run", "--cache-dir",
         str(tmp_path / "cache"), "--oracle", "http://127.0.0.1:9"],
        cwd=PACKAGE, env=_env(), capture_output=True, text=True, timeout=120,
    )
    assert proc.returncode == 0, proc.stderr[-2000:]
    line = next(ln for ln in proc.stdout.splitlines() if ln.startswith("MACHINE_RESULT="))
    mr = json.loads(line.removeprefix("MACHINE_RESULT="))
    for key in ("real_events_geotagged", "surfaced_incident_events", "geo_tagged_signals", "fused_situations",
                "cross_type_corroborated", "social_held_aggregate_only", "pii_redactions", "attached_to_live",
                "sources_proven", "per_source"):
        assert key in mr
    assert mr["real_events_geotagged"] == 4 and mr["held"]["outside_city"] >= 1 and mr["crime_incident"] == 0
    assert not list((tmp_path / "cache" / "_outbox").glob("*.json"))  # a dry run posts and queues nothing


@pytest.mark.skipif(HAVE_PIPELINE, reason="the pipeline libraries are importable here")
def test_dry_run_without_the_libraries_exits_3(tmp_path):
    import_capture(CAPTURE, tmp_path / "cache")
    env = dict(os.environ, PYTHONPATH=os.pathsep.join(str(PACKAGE / p) for p in ("src", "../osint-common/src")))
    proc = subprocess.run(
        [sys.executable, "-m", "osint_ingress", "once", "--offline", "--dry-run", "--cache-dir",
         str(tmp_path / "cache"), "--oracle", "http://127.0.0.1:9"],
        cwd=PACKAGE, env=env, capture_output=True, text=True, timeout=60,
    )
    assert proc.returncode == 3 and "pipeline libraries not importable" in proc.stderr
