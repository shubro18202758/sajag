#!/usr/bin/env bash
# osint_smoke.sh — the OSINT pipeline smoke (events are about PLACES and
# SITUATIONS, never persons).
#
#   bash scripts/osint_smoke.sh --offline
#       No egress, no oracle, no database. Imports the committed SYNTHETIC
#       capture (services/osint-ingress/tests/fixtures/capture/: synthetic
#       Google News / outlet RSS (English and Marathi) / Reddit / GDELT / NDMA
#       SACHET replicas with fictional *.example publishers) into a temp
#       cache, parses it through osint-ingress's own connectors (the service's
#       offline cycle, nothing posted) and runs osint_analysis.run_pipeline
#       in-process with the osint_geo gazetteer resolver. It asserts:
#         · exactly 4 surfaced situations — the correlated affray+collision on
#           the Western Express Highway near Andheri (a road segment; SIMULATED: the capture is
#           developer-written, two independent publishers), the Dadar TT robbery at a junction
#           (reported_crime), the Marathi waterlogging reports at Hindmata (urban_flooding, two
#           Marathi publishers) and the SACHET Mumbai district alert (area-level, 1 source;
#           SIMULATED, because the SACHET replica is synthetic: no real Maharashtra capture is
#           committed). Situations are found by class and toponym, not by segment id, so the
#           check holds for any generated Mumbai network;
#         · every single social post held (aggregate-only), and the state-wide
#           nowcasts held as outside the city (outside_city_held >= 1);
#         · pii_redactions > 0, and find_pii / the person-key denylist clean on
#           every signal and every situation;
#         · 0 crime_incident anywhere (OSINT never emits it);
#         · every publisher ends in .example, is reddit.com/r/example_city or is
#           sachet.ndma.gov.in (plan R13);
#       and reports "signals" and "surfaced events" separately, then prints
#       MACHINE_RESULT={...} (counts and labels only: no headline text).
#
#   bash scripts/osint_smoke.sh --oracle URL [--cache-dir D]
#       Posts the capture (the synthetic one unless --cache-dir names a cache
#       already filled with `python -m osint_ingress import-poc`) to a SANDBOX
#       oracle through `python -m osint_ingress once --offline`, then prints
#       the counts of the oracle's C-T answer (accepted, duplicates, rejected,
#       geotagged, surfaced) and of GET /api/v1/osint/events. The URL must be
#       loopback with an explicit port; the live oracle (8191; 8091 and 8081 of the
#       original stack) and every other live-stack port are refused, and so is
#       a missing URL — osint-ingress defaults to the discard port :9, never the live oracle. The
#       port must be written plainly (1..65535, no leading zero: httpx reads
#       "08091" as 8091). The URL is then rebuilt as scheme://host:port and
#       checked a second time through osint-ingress's own check_oracle_url, so
#       the port this script vets is the port the service would post to.
#
# Python: $OSINT_SMOKE_PY, else this checkout's .venvs/gate, else the gate
# venv of the main checkout of this git worktree, else python3 — the first
# that imports the services' dependencies (bash scripts/verify_all.sh
# bootstraps the gate venv). PYTHONPATH names the four services/osint-*/src.
#
# Exit codes: 0 pass · 1 fail (an assertion, a refusal, a missing dependency).
set -uo pipefail

VVIP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CAPTURE="$VVIP_DIR/services/osint-ingress/tests/fixtures/capture"
SRC_PATHS="$VVIP_DIR/services/osint-ingress/src:$VVIP_DIR/services/osint-common/src:$VVIP_DIR/services/osint-geo/src:$VVIP_DIR/services/osint-analysis/src"
# the discard port: nothing listens, so a connection is refused at once
DEAD_ORACLE=http://127.0.0.1:9
# live-stack ports (Sajag's oracle 8191, and the oracles 8091 and 8081 of the other stacks on this box) — never
# a target of this smoke
LIVE_ORACLE_PORTS=" 8191 8091 8081 "
LIVE_STACK_PORTS=" 5373 8190 8192 8193 8194 8195 8196 8197 56534 6390 4233 8233 5273 5173 8090 8092 8080 8093 8083 8084 8085 56434 55434 6380 6379 4223 4222 8223 8222 "

say()  { printf 'osint_smoke: %s\n' "$*"; }
fail() { printf 'osint_smoke: FAIL: %s\n' "$*" >&2; exit 1; }

usage() {
    awk 'NR > 1 { if (!/^#/) exit; sub(/^# ?/, ""); print }' "${BASH_SOURCE[0]}" >&2
    exit 1
}

MODE="" ORACLE="" CACHE_DIR=""
while [ $# -gt 0 ]; do
    case "$1" in
        --offline)   MODE=offline ;;
        --oracle)    MODE=oracle; ORACLE="${2:-}"; [ $# -ge 2 ] && shift ;;
        --cache-dir) CACHE_DIR="${2:-}"; [ $# -ge 2 ] && shift ;;
        -h|--help)   usage ;;
        *) printf 'osint_smoke: unknown argument %s\n' "$1" >&2; usage ;;
    esac
    shift
done
[ -n "$MODE" ] || usage

# --oracle: refused before anything runs when the URL is missing, not loopback or a live port
if [ "$MODE" = oracle ]; then
    [ -n "$ORACLE" ] || fail "--oracle needs a sandbox oracle URL (a missing URL is refused; osint-ingress defaults to the discard port :9, never the live oracle)"
    if [[ ! "$ORACLE" =~ ^(https?)://(127\.0\.0\.1|localhost|\[::1\]):([0-9]{1,5})/?$ ]]; then
        fail "--oracle $ORACLE: a loopback base URL with an explicit port is required (http://127.0.0.1:<port>)"
    fi
    SCHEME="${BASH_REMATCH[1]}" HOST="${BASH_REMATCH[2]}" PORT_RAW="${BASH_REMATCH[3]}"
    # ONE spelling of the port: httpx, urlsplit and osint-ingress's check_oracle_url all read "08091" as 8091, so a
    # leading zero (or any non-ASCII digit a locale's [0-9] might admit) would slip past the string checks below
    # and post to the LIVE oracle. Plain ASCII decimal, 1..65535, no leading zero — and compared as that number.
    case "$PORT_RAW" in
        ""|0*|*[!0123456789]*)
            fail "--oracle $ORACLE: the port must be a plain decimal 1..65535 without a leading zero (got '$PORT_RAW')" ;;
    esac
    PORT=$((10#$PORT_RAW))
    { [ "$PORT" -ge 1 ] && [ "$PORT" -le 65535 ]; } || fail "--oracle $ORACLE: port $PORT is outside 1..65535"
    case "$LIVE_ORACLE_PORTS" in *" $PORT "*) fail "--oracle $ORACLE is the LIVE oracle port ($PORT): this smoke posts to sandbox oracles only" ;; esac
    case "$LIVE_STACK_PORTS" in *" $PORT "*) fail "--oracle $ORACLE is a live-stack port ($PORT), not a sandbox oracle" ;; esac
    # :8162 is the int3cl sandbox oracle, which backs every dev deck (screenshots, recorded fixtures, docs
    # images): it takes the synthetic capture only (plan R13), never another cache
    if [ "$PORT" = 8162 ] && [ -n "$CACHE_DIR" ]; then
        fail "--oracle $ORACLE is int3cl, which backs dev decks: synthetic capture only (plan R13) — drop --cache-dir"
    fi
    # from here on only the canonical URL built from the vetted parts is used (the child's env, --oracle, the GET)
    ORACLE="$SCHEME://$HOST:$PORT"
fi

# ─── the python that runs the services' code ────────────────────────────────
NEEDED='import pydantic, pydantic_settings, structlog, httpx, defusedxml, fastapi, shapely, pyproj, numpy, sklearn'
pick_python() {
    local main="" c
    # a git worktree's gate venv lives in its main checkout
    main="$(git -C "$VVIP_DIR" rev-parse --path-format=absolute --git-common-dir 2>/dev/null || true)"
    [ -n "$main" ] && main="$(dirname "$main")"
    for c in "${OSINT_SMOKE_PY:-}" "$VVIP_DIR/.venvs/gate/bin/python" \
             "${main:+$main/.venvs/gate/bin/python}" "$(command -v python3 2>/dev/null || true)"; do
        [ -n "$c" ] && [ -x "$c" ] || continue
        "$c" -c "$NEEDED" >/dev/null 2>&1 && { printf '%s\n' "$c"; return 0; }
    done
    return 1
}
PY="$(pick_python)" || fail "no python imports the OSINT services' dependencies ($NEEDED) — bootstrap the gate venv with bash scripts/verify_all.sh (or set OSINT_SMOKE_PY)"
for d in osint-ingress osint-common osint-geo osint-analysis; do
    [ -d "$VVIP_DIR/services/$d/src" ] || fail "services/$d/src is missing"
done

# --oracle, second check, before anything is imported or posted: the canonical URL through osint-ingress's own
# normaliser (and httpx's / urlsplit's port parsing) must name exactly the vetted port, so no spelling the bash
# check accepts can reach a different port inside the service
if [ "$MODE" = oracle ]; then
    NORM="$(env PYTHONPATH="$SRC_PATHS" PYTHONDONTWRITEBYTECODE=1 PROJ_NETWORK=OFF "$PY" -P -c '
import sys
from urllib.parse import urlsplit
import httpx
from osint_ingress.safe_http import check_oracle_url
url, port = sys.argv[1], int(sys.argv[2])
norm = check_oracle_url(url)
seen = {urlsplit(url).port, httpx.URL(url).port, urlsplit(norm).port, httpx.URL(norm).port}
if seen != {port}:
    sys.exit(f"read as port(s) {sorted(map(str, seen))}, not {port}")
print(norm)' "$ORACLE" "$PORT" 2>&1)" \
        || fail "--oracle $ORACLE: refused by osint-ingress's check_oracle_url (${NORM##*$'\n'})"
    [ "$NORM" = "$ORACLE" ] \
        || fail "--oracle $ORACLE: osint-ingress normalises it to ${NORM##*$'\n'}, not the vetted URL — refused"
fi

TMP="$(mktemp -d "${TMPDIR:-/tmp}/osint-smoke.XXXXXX")" || fail "mktemp failed"
trap 'rm -rf "$TMP"' EXIT

# Every child below names its oracle explicitly (osint-ingress defaults to the
# live one): the discard port offline, the checked sandbox URL with --oracle.
run_py() {  # <oracle url> <python args...>
    local oracle="$1"; shift
    (cd "$TMP" && env PYTHONPATH="$SRC_PATHS" OSINT_ORACLE_URL="$oracle" OSINT_CACHE_DIR="$TMP/cache" \
        PROJ_NETWORK=OFF PYTHONDONTWRITEBYTECODE=1 "$PY" -P "$@")
}

# ─── --offline ──────────────────────────────────────────────────────────────
if [ "$MODE" = offline ]; then
    [ -d "$CAPTURE" ] || fail "the synthetic capture is missing: ${CAPTURE#"$VVIP_DIR"/}"
    say "--offline · capture ${CAPTURE#"$VVIP_DIR"/} (synthetic) · python $PY"
    OSINT_SMOKE_CAPTURE="$CAPTURE" OSINT_SMOKE_DEAD="$DEAD_ORACLE" run_py "$DEAD_ORACLE" - <<'PY'
import asyncio
import json
import logging
import os
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

import structlog

# the services log through structlog: keep stdout for the report alone
structlog.configure(
    logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
    wrapper_class=structlog.make_filtering_bound_logger(logging.WARNING),
)

from osint_common import ethics  # noqa: E402
from osint_common.kinds import INCIDENT_CLASSES  # noqa: E402
from osint_ingress.config import Settings  # noqa: E402
from osint_ingress.importer import import_capture  # noqa: E402
from osint_ingress.runner import signal_checks  # noqa: E402
from osint_ingress.service import build_runtime  # noqa: E402

capture = Path(os.environ["OSINT_SMOKE_CAPTURE"])
cache_dir = Path(os.environ["OSINT_CACHE_DIR"])
failures: list[str] = []


def check(ok: bool, what: str) -> bool:
    if not ok:
        failures.append(what)
    return ok


SYNTHETIC_PUBLISHERS = ("reddit.com/r/example_city", "sachet.ndma.gov.in")


def synthetic_publisher(p: str | None) -> bool:
    return p is None or p.endswith(".example") or p in SYNTHETIC_PUBLISHERS


def synthetic_url(u: str | None) -> bool:
    if not u:
        return True
    host = (urlsplit(u).hostname or "").lower()
    return host.endswith(".example") or host == "sachet.ndma.gov.in"


def strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from strings(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from strings(v)


# 1. the capture → a temp cache → the service's own offline cycle (nothing posted)
import_capture(capture, cache_dir)
settings = Settings(oracle_url=os.environ["OSINT_SMOKE_DEAD"], cache_dir=cache_dir, mode="offline")


async def offline_cycle():
    rt = build_runtime(settings)
    try:
        return await rt.engine.cycle(publish=False)
    finally:
        await rt.aclose()


report = asyncio.run(offline_cycle())
signals = report.signals
checks = signal_checks(signals)
check(len(signals) > 0, "the capture parsed to 0 signals")

# 2. the pipeline in-process with the gazetteer resolver (no live state, no embedder)
from osint_analysis.pipeline import run_pipeline  # noqa: E402
from osint_geo.resolver import GazetteerResolver  # noqa: E402

now = max((s.fetched_at for s in signals), default=None)
result = run_pipeline(signals, resolver=GazetteerResolver(), live=None, embedder=None, now=now)
counts = result.counts
surfaced = [r for r in result.resolved if r.is_event]
held = [r for r in result.resolved if not r.is_event]
by_id = {s.signal_id: s for s in signals}

# 3. the four designed situations (the capture is synthetic, so every one is SIMULATED)
check(len(surfaced) == 4, f"surfaced situations: {len(surfaced)}, expected exactly 4")
def _top(r):
    return (r.toponym or "").lower()


weh = [r for r in surfaced if not r.area_level and {"road_accident", "public_conflict"} <= set(r.correlated_classes)]
dadar = [r for r in surfaced if r.event_class == "reported_crime"]
hindmata = [r for r in surfaced if r.event_class == "urban_flooding" and not r.area_level]
sachet = [r for r in surfaced if r.sources and all(s.source == "sachet_cap" for s in r.sources)]
if check(len(weh) == 1, f"correlated crash situations: {len(weh)}, expected 1 (the WEH crash near Andheri)"):
    r = weh[0]
    check(r.segment_id is not None, "the WEH crash is not on a road segment")
    check(any(t in _top(r) for t in ("western express", "weh", "andheri")), f"the crash toponym {r.toponym!r} is not WEH/Andheri")
    check(r.subtype == "affray+collision", f"the crash subtype {r.subtype!r}, expected 'affray+collision'")
    check(r.verification_state == "SIMULATED", f"the crash is {r.verification_state}, expected SIMULATED (the capture is synthetic)")
    check(r.independent_publishers >= 2, f"the crash has {r.independent_publishers} independent publisher(s), expected 2")
if check(len(dadar) == 1, f"reported_crime situations: {len(dadar)}, expected 1 (the Dadar TT robbery)"):
    r = dadar[0]
    check(r.junction_id is not None and "dadar" in _top(r), f"the robbery toponym {r.toponym!r} is not Dadar TT")
if check(len(hindmata) == 1, f"urban_flooding situations: {len(hindmata)}, expected 1 (Marathi waterlogging at Hindmata)"):
    r = hindmata[0]
    check("hindmata" in _top(r) or "ambedkar" in _top(r), f"the flooding toponym {r.toponym!r} is not Hindmata")
    langs = {by_id[i].language for i in r.member_signal_ids if i in by_id}
    check(langs == {"mr"}, f"the Hindmata reports' languages {sorted(langs)}, expected Marathi only")
    check(r.independent_publishers >= 2, f"Hindmata has {r.independent_publishers} independent publisher(s), expected 2")
if check(len(sachet) == 1, f"SACHET situations surfaced: {len(sachet)}, expected 1 (the Mumbai district alert)"):
    r = sachet[0]
    check(r.area_level, "the SACHET situation is not area-level")
    check(r.source_count == 1, f"the SACHET situation has {r.source_count} sources, expected 1")
    check("mumbai" in _top(r), "the SACHET situation is not a Mumbai district")
    check(r.verification_state == "SIMULATED", f"the SACHET situation is {r.verification_state}, expected SIMULATED (a synthetic replica)")
    scopes = {getattr(result.geocodes.get(i), "area_scope", None) for i in r.member_signal_ids}
    check(scopes == {"district"}, f"the SACHET situation's geocode scope {sorted(map(str, scopes))}, expected district")
check(counts.correlated >= 1, "no correlated (cross-class) situation")

# 4. held: every single social post (aggregate-only), the state-wide nowcasts (outside the city)
social_only = [r for r in result.resolved if r.sources and all(s.source == "reddit_rss" for s in r.sources)]
check(not [r for r in social_only if r.is_event], "a social-only situation was surfaced (aggregate-only rule)")
check(counts.social_held >= 1, f"social_held {counts.social_held}, expected the single social posts held")
check(counts.outside_city_held >= 1, f"outside_city_held {counts.outside_city_held}, expected >= 1 (state-wide nowcasts)")
check(not [r for r in surfaced if r.area_level and all(
    getattr(result.geocodes.get(i), "area_scope", None) == "state" for i in r.member_signal_ids)],
    "a state-level situation was surfaced inside the city")

# 5. ethics: redaction, find_pii, the person-key denylist, no crime_incident
pii_redactions = sum(s.pii_redactions for s in signals)
check(pii_redactions > 0, "pii_redactions is 0: the synthetic names and ages were not redacted")
for key, want in (("validated", len(signals)), ("find_pii_clean", len(signals)), ("with_person_key", 0),
                  ("with_poster_handle", 0), ("raw_outside_whitelist", 0), ("raw_with_person_value", 0),
                  ("news_social_with_url", 0), ("mentions_crime_incident", 0)):
    check(checks.get(key) == want, f"signal check {key} = {checks.get(key)}, expected {want}")
leaky = 0
for r in result.resolved:
    dump = r.model_dump(mode="json")
    try:
        ethics.assert_no_person_keys(dump)
    except ValueError as exc:
        failures.append(f"a situation carries a person key ({str(exc)[:60]})")
    if any(ethics.find_pii(s) for s in strings({k: dump.get(k) for k in ("label", "summary", "toponym")})):
        leaky += 1
    for src in dump.get("sources", []):
        if ethics.find_pii(src.get("title") or ""):
            leaky += 1
check(leaky == 0, f"{leaky} situation text(s) with a surviving name or age (find_pii)")
crime = [r for r in result.resolved if r.sajag_event_kind == "crime_incident"]
crime += [c for c in result.classifications.values() if c.sajag_event_kind == "crime_incident"]
check(not crime and "crime_incident" not in json.dumps([r.model_dump(mode="json") for r in result.resolved]),
      "crime_incident appears in the pipeline output (OSINT never emits it)")

# 6. synthetic publishers only (plan R13)
publishers = sorted({s.publisher for s in signals if s.publisher}
                    | {ref.publisher for r in result.resolved for ref in r.sources if ref.publisher})
bad_pub = [p for p in publishers if not synthetic_publisher(p)]
check(not bad_pub, f"{len(bad_pub)} publisher(s) are not synthetic (*.example, reddit.com/r/example_city, sachet.ndma.gov.in)")
bad_url = [s.signal_id for s in signals if not synthetic_url(s.url)]
bad_url += [ref.signal_id for r in result.resolved for ref in r.sources if not synthetic_url(ref.url)]
check(not bad_url, f"{len(bad_url)} source URL(s) outside *.example and sachet.ndma.gov.in")

# 7. the report: signals and surfaced events, separately
per_source = Counter(s.source for s in signals)
reasons = Counter((r.held_reason or "").split(" (")[0].split(":")[0] for r in held)
machine = {
    "capture": "synthetic",
    "signals": len(signals),
    "per_source": dict(sorted(per_source.items())),
    "geo_tagged_signals": counts.geotagged,
    "incident_geotagged_signals": counts.incident_geotagged,
    "fused_situations": counts.fused,
    "surfaced_events": counts.surfaced,
    "real_events_geotagged": counts.surfaced,
    "surfaced_incident_events": sum(1 for r in surfaced if r.event_class in INCIDENT_CLASSES),
    "correlated": counts.correlated,
    "cross_type_corroborated": counts.cross_type_corroborated,
    "social_held_aggregate_only": counts.social_held,
    "outside_city_held": counts.outside_city_held,
    "held_reasons": dict(sorted(reasons.items())),
    "attached_to_live": counts.attached_to_live,
    "pii_redactions": pii_redactions,
    "find_pii_clean_signals": checks.get("find_pii_clean"),
    "crime_incident": len(crime),
    "publishers": publishers,
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
    "failures": failures,
}

print(f"  signals                    : {len(signals)} ({', '.join(f'{k} {v}' for k, v in sorted(per_source.items()))})")
print(f"  geo-tagged signals         : {counts.geotagged} (incident {counts.incident_geotagged})")
print(f"  fused situations           : {counts.fused}")
print(f"  surfaced events            : {counts.surfaced}")
for i, r in enumerate(surfaced, 1):
    where = (f"segment {r.segment_id}" if r.segment_id is not None
             else f"junction {r.junction_id}" if r.junction_id is not None else "area-level")
    print(f"    {i}. {'+'.join(r.correlated_classes) or r.event_class} ({r.subtype}) · {r.toponym} · {where} · "
          f"{r.verification_state} · credibility {r.credibility} · {r.source_count} source(s), "
          f"{r.independent_publishers} independent publisher(s)")
print(f"  held                       : social single-source {counts.social_held} · outside the city "
      f"{counts.outside_city_held} · {dict(sorted(reasons.items()))}")
print(f"  names/ages redacted        : {pii_redactions} (find_pii clean on {checks.get('find_pii_clean')} of "
      f"{len(signals)} signals)")
print(f"  publishers                 : {', '.join(publishers)}")
print(f"  crime_incident             : {len(crime)}")
print("MACHINE_RESULT=" + json.dumps(machine, sort_keys=True))
if failures:
    for f in failures:
        print(f"osint_smoke: FAIL: {f}", file=sys.stderr)
    print(f"osint_smoke: FAIL · {len(failures)} assertion(s) failed")
    sys.exit(1)
print(f"osint_smoke: PASS · {len(signals)} signals · {counts.geotagged} geo-tagged · {counts.surfaced} surfaced "
      f"events (1 correlated on the WEH near Andheri, 1 Marathi at Hindmata) · {counts.social_held} social held · {counts.outside_city_held} "
      f"outside the city · {pii_redactions} redactions · synthetic publishers only · 0 crime_incident")
PY
    exit $?
fi

# ─── --oracle URL [--cache-dir D] ───────────────────────────────────────────

if [ -n "$CACHE_DIR" ]; then
    [ -d "$CACHE_DIR" ] || fail "--cache-dir $CACHE_DIR is not a directory"
    CACHE_DIR="$(cd "$CACHE_DIR" && pwd)"
    say "--oracle $ORACLE · cache $CACHE_DIR"
else
    [ -d "$CAPTURE" ] || fail "the synthetic capture is missing: ${CAPTURE#"$VVIP_DIR"/}"
    CACHE_DIR="$TMP/cache"
    run_py "$DEAD_ORACLE" -m osint_ingress import-poc "$CAPTURE" "$CACHE_DIR" >"$TMP/import.json" 2>"$TMP/import.err" \
        || { tail -5 "$TMP/import.err" >&2; fail "import-poc of the synthetic capture failed"; }
    say "--oracle $ORACLE · the synthetic capture (${CAPTURE#"$VVIP_DIR"/}) in a temp cache"
fi

run_py "$ORACLE" -m osint_ingress once --offline --cache-dir "$CACHE_DIR" --oracle "$ORACLE" \
    --report "$TMP/report.json" >"$TMP/once.out" 2>"$TMP/once.err"
rc=$?
[ "$rc" = 0 ] || { tail -5 "$TMP/once.err" >&2; fail "osint_ingress once exited $rc"; }

OSINT_SMOKE_REPORT="$TMP/report.json" OSINT_SMOKE_ORACLE="$ORACLE" "$PY" -I - <<'PY'
import json
import os
import sys
import urllib.request

rep = json.load(open(os.environ["OSINT_SMOKE_REPORT"], encoding="utf-8"))
pub = rep.get("publish_detail") or {}
ch = rep.get("checks") or {}
batches = pub.get("batches") or {}
print(f"  signals ingested           : {rep.get('signals')} ({', '.join(f'{k} {v}' for k, v in sorted((rep.get('per_source') or {}).items()))})")
print(f"  names/ages redacted        : {rep.get('pii_redactions')} (find_pii clean on {ch.get('find_pii_clean')} of {ch.get('signals')})")
print(f"  publish                    : {pub.get('status')} · batches sent {batches.get('sent')} pending {batches.get('pending')}")
why = f" {pub.get('rejected_reasons')}" if pub.get("rejected_reasons") else ""
print(f"  oracle answer (C-T)        : accepted {pub.get('accepted')} · duplicates {pub.get('duplicates')} · rejected "
      f"{pub.get('rejected')}{why} · geotagged {pub.get('geotagged')} · surfaced {pub.get('surfaced')}")
events = held = None
try:
    with urllib.request.urlopen(os.environ["OSINT_SMOKE_ORACLE"] + "/api/v1/osint/events?limit=200", timeout=10) as r:
        doc = json.load(r)
    events, held = len(doc.get("events") or []), doc.get("held")
    print(f"  GET /osint/events          : {events} surfaced · held {held}")
except Exception as exc:  # informational: the post's own answer is the verdict
    print(f"  GET /osint/events          : unreadable ({type(exc).__name__})")
ok = (pub.get("status") == "ok" and not batches.get("pending") and not pub.get("rejected")
      and ch.get("find_pii_clean") == ch.get("signals"))
print("MACHINE_RESULT=" + json.dumps({
    "signals": rep.get("signals"), "pii_redactions": rep.get("pii_redactions"), "publish": pub.get("status"),
    "accepted": pub.get("accepted"), "duplicates": pub.get("duplicates"), "rejected": pub.get("rejected"),
    "rejected_reasons": pub.get("rejected_reasons"), "geotagged": pub.get("geotagged"),
    "surfaced": pub.get("surfaced"), "osint_events": events, "held": held}, sort_keys=True))
if not ok:
    print(f"osint_smoke: FAIL · publish {pub.get('status')!r}, pending {batches.get('pending')}, rejected {pub.get('rejected')}",
          file=sys.stderr)
    sys.exit(1)
print(f"osint_smoke: PASS · posted {rep.get('signals')} signals · accepted {pub.get('accepted')} · duplicates "
      f"{pub.get('duplicates')} · 0 rejected · surfaced {pub.get('surfaced')}")
PY
