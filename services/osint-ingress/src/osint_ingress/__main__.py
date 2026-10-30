"""``python -m osint_ingress`` — the CLI.

::

    serve                                   the service (HOST/PORT, default 127.0.0.1:8193)
    once [--offline] [--cache-dir D] [--oracle URL] [--dry-run] [--report out.json] [--backfill] [--only a,b]
                                            one cycle, then exit. It probes the oracle FIRST: when unreachable it
                                            posts nothing (no retry loop), keeps the batches in the cache outbox,
                                            reports publish "skipped: oracle unreachable" and exits 0.
                                            --dry-run: no posting; runs osint_analysis.pipeline.run_pipeline with
                                            the osint_geo resolver in-process and prints MACHINE_RESULT={...}
                                            (the PoC's keys). --backfill adds the Common Crawl backfill.
    import-poc <capture_dir> <cache_dir>    copy a PoC-style raw capture directory into the cache layout

Exit codes: 0 ok, 2 usage (including a non-loopback oracle URL and an unknown ``--only`` connector), 3 pipeline
libraries missing (``--dry-run``). Usage errors are caught before anything is built or probed. Output is counts
only: no title, text or URL of any signal is printed.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import structlog
from pydantic import ValidationError

from osint_ingress import __version__

__all__ = ["main"]

EXIT_OK, EXIT_USAGE, EXIT_NO_PIPELINE = 0, 2, 3


def _configure_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(level=level, stream=sys.stderr, format="%(message)s")
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        wrapper_class=structlog.make_filtering_bound_logger(level),
        cache_logger_on_first_use=True,
    )


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="osint_ingress", description="Sajag OSINT ingress")
    p.add_argument("--version", action="version", version=f"osint-ingress {__version__}")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("serve", help="run the service")
    once = sub.add_parser("once", help="run one cycle and exit")
    once.add_argument("--offline", action="store_true", help="no source egress: parse the newest cache entries")
    once.add_argument("--cache-dir", type=Path, help="cache directory (default $OSINT_CACHE_DIR)")
    once.add_argument("--oracle", help="oracle base URL, loopback only (default $OSINT_ORACLE_URL)")
    once.add_argument("--dry-run", action="store_true", help="run the pipeline in-process instead of posting")
    once.add_argument("--report", type=Path, help="write the cycle report (JSON, counts only) here")
    once.add_argument("--backfill", action="store_true", help="also run the Common Crawl backfill")
    once.add_argument("--only", help="comma-separated connector names to run (default: the schedule)")
    imp = sub.add_parser("import-poc", help="copy a PoC raw capture directory into the cache layout")
    imp.add_argument("capture_dir", type=Path)
    imp.add_argument("cache_dir", type=Path)
    return p


def _settings(args: argparse.Namespace) -> Any:
    from osint_ingress.config import Settings

    overrides: dict[str, Any] = {}
    if getattr(args, "cache_dir", None):
        overrides["cache_dir"] = args.cache_dir
    if getattr(args, "oracle", None):
        overrides["oracle_url"] = args.oracle
    if getattr(args, "offline", False):
        overrides["mode"] = "offline"
    return Settings(**overrides)


class UsageError(Exception):
    """A command-line mistake (exit code 2); its message names no signal content."""


def _only(args: argparse.Namespace) -> list[str] | None:
    """The ``--only`` connector names (``None`` when not given); :class:`UsageError` for an unknown or empty list."""
    if getattr(args, "only", None) is None:
        return None
    from osint_ingress.config import CONNECTOR_NAMES

    names = list(dict.fromkeys(n.strip() for n in args.only.split(",") if n.strip()))
    unknown = [n for n in names if n not in CONNECTOR_NAMES]
    known = ", ".join(CONNECTOR_NAMES)
    if unknown:
        raise UsageError(f"--only: unknown connector(s): {', '.join(unknown)[:200]} (known: {known})")
    if not names:
        raise UsageError(f"--only: no connector named (known: {known})")
    return names


def _pipeline() -> tuple[Any, Any] | None:
    """``(run_pipeline, GazetteerResolver)`` when the pipeline libraries import, else ``None``."""
    try:
        from osint_analysis.pipeline import run_pipeline
        from osint_geo.resolver import GazetteerResolver
    except ImportError:
        return None
    return run_pipeline, GazetteerResolver


def _machine_result(signals: Sequence[Any], result: Any, connectors: dict[str, Any]) -> dict[str, Any]:
    """The PoC's MACHINE_RESULT keys, from a ``PipelineResult`` (counts and labels only, no text)."""
    from osint_common.kinds import INCIDENT_CLASSES

    counts = result.counts
    surfaced = [r for r in result.resolved if r.is_event]
    held = [r for r in result.resolved if not r.is_event]
    reasons = Counter((r.held_reason or "").split(" (")[0].split(":")[0] for r in held)
    per_source: dict[str, dict[str, Any]] = {}
    for s in signals:
        per_source.setdefault(s.source, {"n": 0, "mode": s.fetch_mode})
        per_source[s.source]["n"] += 1
    return {
        "real_events_geotagged": counts.surfaced,
        "surfaced_incident_events": sum(1 for r in surfaced if r.event_class in INCIDENT_CLASSES),
        "geo_tagged_signals": counts.geotagged,
        "fused_situations": counts.fused,
        "cross_type_corroborated": counts.cross_type_corroborated,
        "social_held_aggregate_only": counts.social_held,
        "pii_redactions": sum(s.pii_redactions for s in signals),
        "attached_to_live": counts.attached_to_live,
        "sources_proven": sorted(per_source),
        "per_source": per_source,
        # beyond the PoC keys: what the C-T reads expose, and the ethics checks
        "signals": len(signals),
        "correlated": counts.correlated,
        "held": {
            "social_single_source": sum(1 for r in held if (r.held_reason or "").startswith("single social")),
            "not_event_class": sum(1 for r in held if (r.held_reason or "").startswith("not an event")),
            "outside_city": counts.outside_city_held,
        },
        "held_reasons": dict(reasons),
        "crime_incident": sum(1 for r in result.resolved if r.sajag_event_kind == "crime_incident"),
        "publishers": sorted({s.publisher for s in signals if s.publisher}),
        "surfaced": [
            {
                "event_class": r.event_class,
                "correlated_classes": list(r.correlated_classes),
                "subtype": r.subtype,
                "sajag_event_kind": r.sajag_event_kind,
                "toponym": r.toponym,
                "segment_id": r.segment_id,
                "junction_id": r.junction_id,
                "area_level": r.area_level,
                "credibility": r.credibility,
                "verification_state": r.verification_state,
                "source_count": r.source_count,
                "independent_publishers": r.independent_publishers,
            }
            for r in surfaced
        ],
        "connector_errors": {n: st.error for n, st in connectors.items() if st.error},
    }


async def _once(
    args: argparse.Namespace, settings: Any, pipeline: tuple[Any, Any] | None, only: list[str] | None
) -> dict[str, Any]:
    from osint_ingress.service import build_runtime

    rt = build_runtime(settings)
    try:
        engine = rt.engine
        if only is not None:
            names = only  # checked against CONNECTOR_NAMES before the runtime was built (exit 2)
        else:
            names = engine.scheduled_names() + (["common_crawl"] if args.backfill else [])
        if pipeline is None:
            report = await engine.cycle(names, probe_first=True)
            return report.as_report()
        run_pipeline, resolver_cls = pipeline
        report = await engine.cycle(names, publish=False)
        signals = report.signals
        now = max((s.fetched_at for s in signals), default=None)
        result = run_pipeline(signals, resolver=resolver_cls(), live=None, embedder=None, now=now)
        out = report.as_report()
        out["publish"] = "dry-run (nothing posted)"
        out["machine_result"] = _machine_result(signals, result, report.connectors)
        return out
    finally:
        await rt.aclose()


def _print_summary(rep: dict[str, Any]) -> None:
    print(f"osint-ingress once · mode={rep['mode']} · run_id={rep['run_id']}")
    for name, c in rep["connectors"].items():
        print(f"  {name:<24} {c['signals']:>4} signals  ({c['fetch_mode'] or '-'})" + (f"  error: {c['error']}" if c["error"] else ""))
    print(f"  signals ingested            : {rep['signals']}")
    print(f"  person names/ages redacted  : {rep['pii_redactions']}")
    ch = rep["checks"]
    print(f"  validated / find_pii clean  : {ch['validated']} / {ch['find_pii_clean']} of {ch['signals']}")
    print(f"  publish                     : {rep['publish']}")


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    _configure_logging()
    if args.command == "import-poc":
        from osint_ingress.importer import import_capture

        try:
            rep = import_capture(args.capture_dir, args.cache_dir)
        except FileNotFoundError as exc:
            print(f"import-poc: {exc}", file=sys.stderr)
            return EXIT_USAGE
        print(json.dumps({k: v for k, v in rep.items() if k != "imported"} | {
            "imported": {k: {"file": v["file"], "bytes": v["bytes"]} for k, v in rep["imported"].items()}
        }, indent=1))
        return EXIT_OK
    try:
        only = _only(args)
    except UsageError as exc:
        print(f"osint_ingress: {exc}", file=sys.stderr)
        return EXIT_USAGE
    try:
        settings = _settings(args)
    except ValidationError as exc:
        fields = ", ".join(str(e.get("loc", ("?",))[0]) for e in exc.errors(include_url=False))
        print(f"osint_ingress: invalid settings ({fields}); the oracle URL must be loopback", file=sys.stderr)
        return EXIT_USAGE
    if args.command == "serve":
        import uvicorn

        from osint_ingress.service import create_app

        uvicorn.run(create_app(settings), host=settings.host, port=settings.port, access_log=False, log_level="info")
        return EXIT_OK
    pipeline = None
    if args.dry_run:
        pipeline = _pipeline()
        if pipeline is None:
            print("osint_ingress: pipeline libraries not importable (osint_analysis, osint_geo)", file=sys.stderr)
            return EXIT_NO_PIPELINE
    rep = asyncio.run(_once(args, settings, pipeline, only))
    _print_summary(rep)
    if "machine_result" in rep:
        print("MACHINE_RESULT=" + json.dumps(rep["machine_result"], sort_keys=True))
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(rep, indent=1, sort_keys=True, default=str) + "\n", encoding="utf-8")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
