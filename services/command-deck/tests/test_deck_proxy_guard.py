"""Deck edge regression (gate-venv python): proxy guard, hardening, operator gate.

The edge itself is TypeScript (src/hooks.server.ts + the operator-session
and public-projection modules), so this module has two rungs:

* SOURCE CONTRACT (pure python, no node): the authority-pinning refusal
  exists and runs BEFORE the upstream fetch (the live-confirmed open proxy:
  /api/convoy//127.0.0.1:8091/health once fetched the traffic-oracle through
  the brain rule), the upstream targets stay pinned loopback literals, the
  WebSocket 501 answer precedes any proxying, and the R26 machine-ingest
  refusal (POST /api/v1/osint/signals, 403) precedes both the gate and the
  upstream fetch.
* BEHAVIOUR (node): bundles tests/ops-guard.entry.ts with the vendored
  esbuild and runs it — authority pinning, 501-on-upgrade, header hygiene,
  the nonce CSP, the opt-in SAJAG_OPERATOR_PIN gate (default-deny on the
  canonical, once-decoded path: %-encoded operator feeds, the interception
  plan, the raw events feed and one event row by id refused; the anonymous
  ambulance request capped per client) and its /api/session sign-in, the
  public projection's allowlist and hold provenance, the driver status
  OSINT firewall failing CLOSED (an unreadable event row 503, an absent or
  OSINT-sourced one not-found, never the dispatch body; a failed read
  cached for the poll window), the doctrine window timing, and the C-D chat
  parser. The suite stubs fetch, so nothing leaves the process.
  Equivalent manual run from services/command-deck:

      node_modules/.bin/esbuild tests/ops-guard.entry.ts --bundle \\
          --platform=node --format=esm --alias:$lib=./src/lib \\
          --outfile=tests/artifacts/ops-guard-bundle.mjs \\
          && node tests/artifacts/ops-guard-bundle.mjs

The behaviour rung skips (with the reason) only when node or the vendored
esbuild is absent; it never passes vacuously.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
DECK_ROOT = HERE.parent
HOOKS_TS = DECK_ROOT / "src" / "hooks.server.ts"
ENTRY = HERE / "ops-guard.entry.ts"
ESBUILD = DECK_ROOT / "node_modules" / ".bin" / "esbuild"


def test_guard_present_in_source() -> None:
    source = HOOKS_TS.read_text(encoding="utf-8")

    # The authority-pinning refusal, verbatim contract from the fix.
    assert "upstream.origin !== base.origin" in source, (
        "hooks.server.ts lost the upstream-origin pinning guard"
    )
    assert "refused authority-override path" in source, (
        "hooks.server.ts refusal response lost its detail marker"
    )

    # The guard must run BEFORE the upstream fetch — a check placed after
    # the fetch would refuse the response but the request would already
    # have left for the attacker-chosen host.
    guard_at = source.index("upstream.origin !== base.origin")
    fetch_at = source.index("await fetch(upstream, init)")
    assert guard_at < fetch_at, "authority pinning must precede the upstream fetch"


def test_proxy_rules_still_pinned_to_loopback() -> None:
    """The proxy targets must stay loopback literals on the live ports.

    The origin check compares against ``rule.target`` — if a target ever
    stops being a loopback constant the pin itself becomes the hole.
    """
    source = HOOKS_TS.read_text(encoding="utf-8")

    for env_name, default in (
        ("ORACLE_PORT", "8091"),
        ("BRAIN_PORT", "8092"),
        ("EMULATOR_PORT", "8090"),
    ):
        assert f"http://127.0.0.1:${{process.env.{env_name} ?? '{default}'}}" in source, (
            f"proxy target for {env_name} is no longer a pinned 127.0.0.1 constant "
            f"defaulting to the live port {default}"
        )


def test_upgrade_answered_before_proxying() -> None:
    """WebSocket upgrades get 501 at the top of handle(), before any proxy."""
    source = HOOKS_TS.read_text(encoding="utf-8")
    handle_at = source.index("export const handle")
    upgrade_at = source.index("isUpgrade(event.request)", handle_at)
    proxy_at = source.index("await proxy(event, rule", handle_at)
    assert upgrade_at < proxy_at, "the 501 upgrade answer must precede proxying"


def test_machine_ingest_refused_before_gate_and_fetch() -> None:
    """R26: the deck edge refuses the loopback machine-ingest path.

    osint-ingress posts ``POST /api/v1/osint/signals`` to the oracle directly,
    never through the deck; the deck proxies all of /api/v1, so a browser could
    otherwise post a fabricated "official" signal. The refusal must sit in
    handle() BEFORE the operator gate (so it holds gate on or off, signed in or
    not) and BEFORE any upstream fetch.
    """
    source = HOOKS_TS.read_text(encoding="utf-8")
    assert "const MACHINE_INGEST_PATH = '/api/v1/osint/signals';" in source, (
        "hooks.server.ts lost the machine-ingest path constant (R26)"
    )
    assert "'machine ingest: loopback only'" in source, (
        "hooks.server.ts lost the R26 refusal detail"
    )
    handle_at = source.index("export const handle")
    refuse_at = source.index("isMachineIngestWrite(event.request.method, event.url.pathname)", handle_at)
    gate_at = source.index("gateDecision(event.request.method", handle_at)
    proxy_at = source.index("await proxy(event, rule", handle_at)
    assert refuse_at < gate_at, "the R26 refusal must precede the operator gate"
    assert refuse_at < proxy_at, "the R26 refusal must precede the upstream fetch"
    # checked on the canonical (once-decoded) path as well as the raw one
    assert "canonicalGatePath(pathname)" in source[: source.index("export const handle")]


def test_guard_bundle_behaviour(tmp_path: Path) -> None:
    node = shutil.which("node")
    if node is None or not ESBUILD.exists():
        pytest.skip("node or the vendored esbuild (node_modules/.bin/esbuild) is not installed")

    bundle = tmp_path / "ops-guard-bundle.mjs"
    build = subprocess.run(
        [
            str(ESBUILD),
            str(ENTRY),
            "--bundle",
            "--platform=node",
            "--format=esm",
            "--alias:$lib=./src/lib",
            "--log-level=warning",
            f"--outfile={bundle}",
        ],
        cwd=DECK_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert build.returncode == 0, f"esbuild failed:\n{build.stdout}\n{build.stderr}"

    run = subprocess.run(
        [node, str(bundle)],
        cwd=DECK_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    output = run.stdout + run.stderr
    assert run.returncode == 0, f"guard suite failed:\n{output[-4000:]}"
    assert "all guard assertions passed" in run.stdout
    # The suite must actually exercise every rung, not pass vacuously.
    for marker in (
        "ok proxy-refuse",
        "ok ws-upgrade answered 501",
        "ok page: CSP present",
        "ok gate on, anonymous POST /api/v1/enforcement",
        "ok gate on, anonymous GET /api/v1/%76ehicles → 403",
        "ok gate on, anonymous GET /api/v1/events/4508d86d-566b-438f-8414-b3d67fd7e6e4/interception-plan → 403",
        "ok gate on, anonymous GET /api/v1/events/4508d86d-566b-438f-8414-b3d67fd7e6e4 → 403",
        "ok gate on: anonymous ambulance requests capped per client",
        "ok gate on: malformed session cookie → 403, never 500",
        "ok session: right PIN",
        "ok projection: vehicle_pursuit never projected",
        'ok feed: oracle "baseline" params stay labelled baseline',
        "ok driver status: polling drivers share one upstream read set per 2 s",
        "ok driver status: the event row is read by id (GET /events/{id})",
        "ok driver status: event read failing → 503 temporarily unavailable, never the dispatch body",
        "ok driver status: a failed event read is cached for the poll window too",
        "ok driver status: an oracle without GET /events/{id} → 503, never the dispatch body",
        "ok driver status: event absent (404 'event … not found') → 'no such ambulance request'",
        "ok driver status: OSINT event (source_kind 'osint') → 'no such ambulance request'",
        "ok driver status: OSINT event (metadata.source 'osint') → 'no such ambulance request'",
        "ok window: unit beyond one window",
        "ok writer: no citizen all-clear for a pursuit",
        "ok C-D: tool_call",
        "ok R26: gate off, anonymous POST /api/v1/osint/signals → 403 machine ingest",
        "ok R26: gate on, anonymous POST /api/v1/osint/signals → 403 machine ingest",
        "ok R26: gate on, signed in, POST /api/v1/osint/signals → 403 machine ingest",
        "ok R26: gate off the other /api/v1/osint/* GETs still proxy",
        "ok R26: gate on, signed in: the other /api/v1/osint/* GETs still proxy",
    ):
        assert marker in run.stdout, f"guard suite never reached: {marker}"


AI_ENTRY = HERE / "ai-gate.entry.ts"


def test_ai_routes_gated_in_source() -> None:
    """The AI services sit behind the operator gate (src/lib/ai/gate.server.ts), decided before the proxy."""
    source = HOOKS_TS.read_text(encoding="utf-8")
    handle_at = source.index("export const handle")
    ai_at = source.index("aiGateDecision(event.request.method, event.url.pathname, event.url.search)", handle_at)
    proxy_at = source.index("await proxy(event, rule", handle_at)
    assert ai_at < proxy_at, "the AI gate must precede the upstream fetch"
    for env_name, default in (
        ("SPEECH_PORT", "8194"),
        ("FORECAST_PORT", "8195"),
        ("VISION_PORT", "8196"),
        ("HYDRO_PORT", "8197"),
        ("TWIN_PORT", "8198"),
        ("CITYFEEDS_PORT", "8199"),
    ):
        assert f"AI_TARGET('{env_name}', '{default}')" in source, f"the {env_name} target is no longer a pinned loopback rule"
    gate = (DECK_ROOT / "src" / "lib" / "ai" / "gate.server.ts").read_text(encoding="utf-8")
    assert "canonicalGatePath" in gate, "the AI gate must decide on the canonical (once-decoded) path"
    assert "SPEAK_MAX_CHARS = 400" in gate


def test_ai_gate_bundle_behaviour(tmp_path: Path) -> None:
    node = shutil.which("node")
    if node is None or not ESBUILD.exists():
        pytest.skip("node or the vendored esbuild (node_modules/.bin/esbuild) is not installed")
    bundle = tmp_path / "ai-gate-bundle.mjs"
    build = subprocess.run(
        [str(ESBUILD), str(AI_ENTRY), "--bundle", "--platform=node", "--format=esm", "--alias:$lib=./src/lib",
         "--log-level=warning", f"--outfile={bundle}"],
        cwd=DECK_ROOT, capture_output=True, text=True, timeout=120, check=False,
    )
    assert build.returncode == 0, f"esbuild failed:\n{build.stdout}\n{build.stderr}"
    run = subprocess.run([node, str(bundle)], cwd=DECK_ROOT, capture_output=True, text=True, timeout=120, check=False)
    output = run.stdout + run.stderr
    assert run.returncode == 0, f"ai gate suite failed:\n{output[-4000:]}"
    assert "all ai gate assertions passed" in run.stdout
    for marker in (
        "ok ai gate off: the forecast proxies",
        "ok ai gate on, anonymous GET /api/forecast/forecast/segments?horizon_min=120 → 403",
        "ok ai gate on, anonymous POST /api/twin/twin/propose → 403",
        "ok ai gate on, anonymous GET /api/hydro/hydro/nowcast?force=true → 403",
        "ok ai gate on, anonymous POST /api/speech/speech/transcribe → 403",
        "ok ai gate on, anonymous GET /api/hydro/hydro/nowcast passes (public read)",
        "ok ai gate on, anonymous GET /api/cityfeeds/feeds/air passes (citizen air today)",
        "ok ai gate on, anonymous GET /api/cityfeeds/feeds/cyclones → 403",
        "ok ai gate on, anonymous GET /api/cityfeeds/feeds/street-image.jpg?lat=22.564600&lon=88.351000 → 403",
        "ok ai gate on: anonymous speak with a short advisory passes",
        "ok ai gate on: speak with more than 400 characters → 413, never fetched",
        "ok ai gate on: the speak cap is per client",
        "ok ai gate on, signed in: every AI route proxies",
        "ok ai gate on, signed in: the street photo proxies to the city feeds and its JPEG comes back intact",
    ):
        assert marker in run.stdout, f"ai gate suite never reached: {marker}"
