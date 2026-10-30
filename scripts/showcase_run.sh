#!/usr/bin/env bash
# showcase_run.sh — the FLAGSHIP demonstration: "GOD'S-EYE EVENING OVER MUMBAI".
#
# One Anant Chaturdashi night over Mumbai, end to end, no arguments, through
# the real HTTP APIs of the RUNNING stack (every scenario EMULATED / SIMULATED
# and labelled so; every approval a named officer's):
#
#   21:30  VISARJAN NIGHT, LALBAUG TO GIRGAON CHOWPATTY (use case
#          ganesh_visarjan_girgaon, SIMULATED). Processions move from Lalbaug
#          past Byculla, JJ, Nagpada and Opera House to Girgaon Chowpatty;
#          the crowd spills off the footpaths along the route and at the
#          beach; heavy vehicles are kept off the procession roads (modelled
#          as fewer heavy-vehicle breakdowns); the closures and the
#          procession load are injected through the event emulator's HTTP
#          API into the RUNNING fleet.
#   21:3x  MONSOON BURST AT HIGH TIDE (use case cloudburst_high_tide,
#          SIMULATED). A heavy burst (MODELLED rain rate) while the Arabian
#          Sea is at high water (MODELLED tide phase, Apollo Bunder): the
#          storm-water outfalls close, the BMC pumps (EMULATED) carry the
#          load, and the rain use case's first waterlogging spot (Hindmata on
#          Dr Ambedkar Road) floods first. The hydro service is asked for its
#          proposals: the LIVE nowcast (Open-Meteo rain; tonight may be dry,
#          and then it proposes nothing — recorded as such) and the
#          18–19 Aug 2025 Mumbai storm replay (HINDSIGHT, MODELLED: reroute,
#          ambulance window, live-wire request, advisory draft).
#   21:4x  AN AMBULANCE (108) asks for a green corridor through the
#          procession: the flagship's own emergency_vehicle windows (read
#          from the library). The escalation channel decides
#          AMBULANCE_DELAY mid-crowd and the twin's audited schedule opens
#          the green-corridor windows (emergency_vehicle) on those roads.
#   21:5x  A STOLEN VEHICLE is reported (FIR 4401/2026, Azad Maidan PS — a
#          scenario reference; plate MH01EM9001, an EMULATED mark). The chain
#          runs through the real stack — vehicles only, never a fine for the
#          theft victim (C-N):
#            plate EARMARKED (flagged, lawful basis stolen_vehicle_fir)
#            -> emulated ANPR sightings on the Mumbai camera sites (the
#               watchlist sweep's belt on the Western Express Highway;
#               matched_plate_hit 'stolen_vehicle', source 'emulated_anpr')
#            -> one EVIDENCE-ONLY R_STOLEN_SIGHTING per read: the penal
#               rules still run, but their e-challan is WITHHELD — PENDING, a
#               proposal only
#            -> APPROVAL of the newest sighting by the clearly labelled
#               "Scripted demo officer (showcase script)": 'pursuit
#               authorised on a reported-stolen vehicle (evidence, no fine)';
#               an e-challan approval on the plate is REFUSED (409)
#            -> PURSUIT EVENT (vehicle_pursuit, EMULATED, carrying vehicle_id
#               + recommendation_id)
#            -> INTERCEPTION PLAN (pgRouting choke-junction ranking off the
#               latest sighting)
#            -> LIVE TRACE on the God's-eye canvas (GET /api/v1/vehicles/{id}/trace)
#            -> the scripted pursuit CLOSED when the run ends (C-F
#               cancelled): nothing an unattended script opened stays open on
#               /ops or holds a band for the situation engine.
#   22:0x  CIVIC VOLUNTEERS (the platform's agency code jan_rakshak) are
#          dispatched to the visarjan crowd spill (the flagship's first
#          crowd cause): requested -> approved -> en_route -> on_scene, every
#          transition audited, the emulated unit projected live.
#   22:1x  The city SIGNAL-POLICY ENGINE answers the situation band: the twin
#          calibration replay is run (honest numbers recorded), the live
#          band's city plan is applied for the evening, and the C7 shadow-eval
#          guard REFUSES the commit while the twin is uncalibrated — fail-closed
#          BY DESIGN, fully audited in GET /api/v1/signals/plans.
#   22:2x  A VIP MOVEMENT, Mantralaya -> Mumbai Airport T2, is PLANNED only
#          (convoy-brain's pre-movement workflow: ranked routes, the decider's
#          pick, the corridor event registered in 'planning'); nothing is
#          launched, and the scripted plan is closed when the run ends.
#
# What this script proves, in order:
#   1. HEALTH   — the fleet's containers + host models + emulator (checked
#                 on connectivity) + deck (one operator sign-in), fail fast
#                 with the exact fix hint if not. The city signal-plan writer
#                 must already be ON (sajag_up.sh --demo); the live stack's
#                 containers are never recreated by this script unless
#                 SHOWCASE_ALLOW_RECREATE=1 (then phase 8d, or the exit trap,
#                 puts the writer back to its pre-run value).
#   2. ACTION   — every beat above through the emulator + real APIs.
#   3. ASSERT   — the real stack did the work, each verifiable from
#                 API/store state: audit-log decision rows, band
#                 transitions, green-corridor windows, the hydro proposals,
#                 the signal-policy guard decision, every pursuit-chain step,
#                 the VIP plan.
#   4. EVIDENCE — headless SwiftShader screenshots of the CANVAS (the
#                 deck's /gods-eye 3D city, signed in, and the /citizen
#                 advisory as the public sees it — the pursuit and every
#                 plate kept off it), each proven non-blank at the pixel
#                 level (scripts/showcase/canvas_shots.mjs), into the
#                 output dir (showcase/).
#   5. RESULT   — showcase_results.json in the output dir (with this
#                 run's emulator run ids and event ids) + nonzero exit on
#                 ANY failed assertion.
#
# Approvals: in a live demo a signed-in HUMAN approves on /ops (and
# scripts/demo_reset.sh stops at PENDING for exactly that); this script runs
# unattended, so the two approvals it makes (the Civic Volunteers dispatch,
# the stolen-vehicle sighting that authorises the pursuit) are recorded under
# the officer label "Scripted demo officer (showcase script)".
#
# Usage: bash scripts/showcase_run.sh     (no arguments)
# Env:   CHROME_PATH optional (defaults to the puppeteer cache).
#        Endpoints/containers are env-overridable with the live defaults of
#        scripts/sajag_env.sh (see the block below): *_URL/*_PORT for the
#        services (HYDRO_URL / TWIN_URL for the AI services), DECK_URL /
#        DECK_PORT for the deck, COMPOSE_PROJECT / COMPOSE_FILES /
#        *_CONTAINER for the fleet (DECK_CONTAINER= or EMULATOR_CONTAINER=
#        empty: that service is served outside docker — checked over HTTP
#        only).
#        FLAG_RUN_TIMEOUT_SEC / SWEEP_RUN_TIMEOUT_SEC bound the emulator
#        run polls (C-G runs are asynchronous).
#        SHOWCASE_ALLOW_RECREATE=1 (off by default): when the signal-plan
#        writer is off, recreate the oracle with it on for this run (compose,
#        or ORACLE_WRITER_CMD for a private stack's `docker run`), and with
#        its pre-run value at the end. Off: such a run is refused.
#        SHOWCASE_OUT_DIR: where the artifacts and showcase_results.json
#        land (default showcase/ — the committed evidence; point it
#        elsewhere for any run against a private stack).
#        The deck's operator gate: signed in through scripts/deck_session.sh
#        (PIN from SAJAG_OPERATOR_PIN, SAJAG_OPERATOR_PIN_FILE or sajag.env).
#
# Security: every URL below is an internal endpoint (an env-overridable
# config constant of this script, http scheme, loopback default) — none
# comes from external input, so no host validation is required before
# these requests (the convoy-brain http_guard carve-out for platform
# services).

set -uo pipefail

SAJAG_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SHOWCASE_DIR="${SHOWCASE_OUT_DIR:-$SAJAG_ROOT/showcase}"
INFRA_DIR="$SAJAG_ROOT/infra"

# ── internal endpoints (env-overridable constants, loopback-only defaults) ──
# The hooks.server.ts pattern in URL form: *_PORT tunes the port, *_URL
# overrides the whole origin. Defaults are the live argus stack's
# (scripts/sajag_env.sh — not sourced: it would export sajag.env, the
# operator PIN included, into every child of this script).
ORACLE_URL="${ORACLE_URL:-http://127.0.0.1:${ORACLE_PORT:-8191}}"
BRAIN_URL="${BRAIN_URL:-http://127.0.0.1:${BRAIN_PORT:-8192}}"
EMULATOR_URL="${EMULATOR_URL:-http://127.0.0.1:${EMULATOR_PORT:-8190}}"
DECIDER_URL="${DECIDER_URL:-http://127.0.0.1:${DECIDER_PORT:-8083}}"
LLAMA_URL="${LLAMA_URL:-http://127.0.0.1:${LLAMA_PORT:-8084}}"
# the embedding service's port is host configuration (sajag.env EMBEDDING_PORT, not a secret): read
# that one line, never the file's other values
EMBED_PORT="${EMBED_PORT:-${EMBEDDING_PORT:-$(sed -n 's/^EMBEDDING_PORT=//p' "${SAJAG_ENV_FILE:-$HOME/.config/sajag/sajag.env}" 2>/dev/null | tail -n 1 | tr -d "\"' ")}}"
EMBED_URL="${EMBED_URL:-http://127.0.0.1:${EMBED_PORT:-8085}}"
# the on-premises AI services the evening calls (compute only: they never write the city)
HYDRO_URL="${HYDRO_URL:-http://127.0.0.1:${HYDRO_PORT:-8197}}"
TWIN_URL="${TWIN_URL:-http://127.0.0.1:${TWIN_PORT:-8198}}"
DECK_CONTAINER_URL="${DECK_URL:-http://127.0.0.1:${DECK_PORT:-5373}}"
# The ONE deck: sajag-command-deck serves the SvelteKit deck on :5373 —
# same origin serves /gods-eye, /citizen and the /api/v1 reverse proxy
# (src/hooks.server.ts), the proxy behind the operator PIN gate. One
# origin, one constant: the canvas origin IS the deck.
DECK_ORIGIN="$DECK_CONTAINER_URL"

# ── fleet addressing (compose project + derived container names) ────────────
# COMPOSE_PROJECT drives the derived container names (project-service), so a
# parallel stack needs one override, not eight; any single *_CONTAINER can
# still be pinned explicitly (DECK_CONTAINER= / EMULATOR_CONTAINER= empty:
# served outside docker, checked over HTTP only).
COMPOSE_PROJECT="${COMPOSE_PROJECT:-sajag}"
COMPOSE_FILES="${COMPOSE_FILES:--f compose.yml -f compose.gb10-override.yml -f compose.argus-override.yml}"
PG_CONTAINER="${POSTGIS_CONTAINER:-${COMPOSE_PROJECT}-postgis}"
VALKEY_CONTAINER="${VALKEY_CONTAINER:-${COMPOSE_PROJECT}-valkey}"
NATS_CONTAINER="${NATS_CONTAINER:-${COMPOSE_PROJECT}-nats}"
ORACLE_CONTAINER="${ORACLE_CONTAINER:-${COMPOSE_PROJECT}-traffic-oracle}"
BRAIN_CONTAINER="${BRAIN_CONTAINER:-${COMPOSE_PROJECT}-convoy-brain}"
INGRESS_CONTAINER="${INGRESS_CONTAINER:-${COMPOSE_PROJECT}-signal-ingress}"
DECK_CONTAINER="${DECK_CONTAINER-${COMPOSE_PROJECT}-command-deck}"
EMULATOR_CONTAINER="${EMULATOR_CONTAINER-${COMPOSE_PROJECT}-event-emulator}"
PG_USER="${POSTGIS_USER:-corridor_admin}"
PG_DB="${POSTGIS_DB:-corridor_db}"
PSQL="docker exec $PG_CONTAINER psql -U $PG_USER -d $PG_DB -At"

# ── the evening's cast ──────────────────────────────────────────────────────
# Every emulator run is a fresh subject: its movement/event id is uuid5 over
# use_case|seed|run_id (event_emulator/tape.py movement_uuid), so this run's
# ids are READ from the run document (GET /api/v1/emulator/runs/{id}),
# never derived here.
FLAGSHIP_ID="ganesh_visarjan_girgaon"   # Anant Chaturdashi visarjan: procession crowds + heavy-vehicle restriction + the 108 request
RAIN_ID="cloudburst_high_tide"          # monsoon burst at high tide: the rain use case's first waterlogging spot floods first
SWEEP_ID="watchlist_anpr_sweep"         # the emulated ANPR sweep that reads the stolen plate
SWEEP_BASE_SEED=20261105
# Fresh per run by default; overridable via env so the repetition gate can
# PIN the seed (identical tapes -> identical sightings/rules/terminal state
# across rounds).
SWEEP_SEED="${SWEEP_SEED:-$((SWEEP_BASE_SEED + (EPOCHSECONDS % 899999)))}"
STOLEN_PLATE="MH01EM9001"                                    # event_emulator/city.py STOLEN_FIR_PLATE (EMULATED)
OFFICER="Scripted demo officer (showcase script)"            # every unattended approval
SHOWCASE_LABEL="God's-eye evening showcase"                  # earmarked_by / requested_by of this script
FIR_REF="FIR 4401/2026, Azad Maidan PS"                      # event_emulator/city.py STOLEN_FIR_REF (a scenario reference)

# The Mumbai network (cities/mumbai/network.json). The evening's roads are READ
# from the emulator's own library (services/event-emulator/src/event_emulator/
# use_case_library.json — the file the running emulator serves), so they follow
# the library when the network is regenerated:
#   AMBULANCE_ROUTE  the flagship's emergency_vehicle windows, in the order they open
#   WATER_SEGMENT    the rain use case's first waterlogging cause (Hindmata)
#   SPILL_SEGMENT    the flagship's first crowd cause (rally_spillover)
#   SWEEP_BELT       the watchlist sweep's route
# The defaults below (legal on the Mumbai network) are used only when the
# library cannot be read.
AMBULANCE_ROUTE="1063,1062,1081,1082,1083"
AMBULANCE_ROUTE_TEXT="Lalbaug -> Byculla -> JJ -> Nagpada -> Opera House -> Girgaon Chowpatty (1063->1062->1081->1082->1083)"
WATER_SEGMENT=1066                      # Dr Ambedkar Road (Hindmata - Dadar TT)
WATER_TEXT="Hindmata (Dr Ambedkar Road, segment 1066)"
SPILL_SEGMENT=1083                      # Jagannath Shankarsheth Marg: Opera House to Girgaon Chowpatty
SPILL_TEXT="visarjan crowd on Jagannath Shankarsheth Marg (segment 1083)"
SWEEP_BELT="1014,1015,1016,1017"        # Western Express Highway, Kalanagar -> Jogeshwari (EM-CAM-01..04)
SWEEP_BELT_TEXT="Western Express Highway sweep belt (Kalanagar – Vakola – Andheri – Jogeshwari)"
FLAG_KIND="mass_gathering"
FLAG_CLOSURE="signal_hold"
eval "$(LIB="$SAJAG_ROOT/services/event-emulator/src/event_emulator/use_case_library.json" \
        NET="$SAJAG_ROOT/cities/mumbai/network.json" \
        FLAG="$FLAGSHIP_ID" RAIN="$RAIN_ID" SWEEP="$SWEEP_ID" python3 - <<'PYEOF' 2>/dev/null
import json, os, shlex
lib = {u["id"]: u["scenarioConfig"] for u in json.load(open(os.environ["LIB"], encoding="utf-8"))}
net = json.load(open(os.environ["NET"], encoding="utf-8"))
road = {s["segment_id"]: s["road_name"] for s in net["segments"]}
out = {}
def place(fe):
    return (fe.get("label") or "").split(" — ")[0].strip() or road.get(fe["segment_id"], "")
flag, rain, sweep = lib.get(os.environ["FLAG"]), lib.get(os.environ["RAIN"]), lib.get(os.environ["SWEEP"])
if flag:
    evs = sorted((fe for fe in flag["forced_events"] if fe["type"] == "emergency_vehicle"),
                 key=lambda fe: fe["start_sec"])
    amb = list(dict.fromkeys(fe["segment_id"] for fe in evs)) or flag["route_segment_ids"]
    if amb:
        names = list(dict.fromkeys(road.get(s, str(s)) for s in amb))
        out["AMBULANCE_ROUTE"] = ",".join(map(str, amb))
        out["AMBULANCE_ROUTE_TEXT"] = " -> ".join(names) + " (" + "->".join(map(str, amb)) + ")"
    spill = next((fe for fe in flag["forced_events"] if fe["type"] == "rally_spillover"), None)
    if spill:
        out["SPILL_SEGMENT"] = str(spill["segment_id"])
        out["SPILL_TEXT"] = f"{place(spill)} (segment {spill['segment_id']})"
    if flag.get("event_kind"):
        out["FLAG_KIND"] = flag["event_kind"]
    if (flag.get("closure_policy") or {}).get("closure_type"):
        out["FLAG_CLOSURE"] = flag["closure_policy"]["closure_type"]
if rain:
    wl = next((fe for fe in rain["forced_events"] if fe["type"] == "waterlogging"), None)
    if wl:
        out["WATER_SEGMENT"] = str(wl["segment_id"])
        out["WATER_TEXT"] = f"{place(wl)} ({road.get(wl['segment_id'], '')}, segment {wl['segment_id']})"
if sweep and sweep.get("route_segment_ids"):
    belt = sweep["route_segment_ids"]
    out["SWEEP_BELT"] = ",".join(map(str, belt))
    out["SWEEP_BELT_TEXT"] = "sweep belt (" + " – ".join(dict.fromkeys(road.get(s, str(s)) for s in belt)) + ")"
for k, v in out.items():
    print(f"{k}={shlex.quote(v)}")
PYEOF
)"
#   the VIP movement, planned only: Mantralaya (junction 1) -> Mumbai Airport T2,
#   departure forecourt (junction 49), (lon, lat) from network.json
VIP_ORIGIN="72.8255127,18.9275189"
VIP_DESTINATION="72.8724794,19.0999035"

CLOCK_SCALE=30        # flagship + rain: 60 sim-min in 120 s wall (mid-evening room)
SWEEP_CLOCK=60        # sweep:            45 sim-min in 45 s wall
TICK_SEC=10
# C-G runs are asynchronous (202 at once): bounds on the progress polls
FLAG_RUN_TIMEOUT_SEC="${FLAG_RUN_TIMEOUT_SEC:-600}"
SWEEP_RUN_TIMEOUT_SEC="${SWEEP_RUN_TIMEOUT_SEC:-300}"
RESULTS_JSON="$SHOWCASE_DIR/showcase_results.json"

RED=$'\033[0;31m'; GREEN=$'\033[0;32m'; CYAN=$'\033[0;36m'; BOLD=$'\033[1m'; RESET=$'\033[0m'
log()  { printf '%s[evening]%s %s\n' "$CYAN" "$RESET" "$*"; }
ok()   { printf '%s[ ok ]%s %s\n' "$GREEN" "$RESET" "$*"; }
bad()  { printf '%s[FAIL]%s %s\n' "$RED" "$RESET" "$*"; }

mkdir -p "$SHOWCASE_DIR"
FAILURES=0
declare -a FAILED_ASSERTS=()
fail() { FAILURES=$((FAILURES + 1)); FAILED_ASSERTS+=("$1"); bad "$1"; }

health() { curl -s --max-time "${2:-10}" "$1" 2>/dev/null; }
hcode()  { curl -s -o /dev/null -w '%{http_code}' --max-time "${2:-10}" "$1" 2>/dev/null; }

die_hint() { # <problem> <hint>
    bad "$1"
    printf '     FIX: %s\n' "$2" >&2
    exit 2
}

jget() { # <json-file> <dotted.key> — the value ('' when absent; objects as JSON)
    python3 -c '
import json, sys
v = json.load(open(sys.argv[1]))
for k in sys.argv[2].split("."):
    v = v.get(k) if isinstance(v, dict) else None
print("" if v is None else json.dumps(v) if isinstance(v, (dict, list)) else v)' "$1" "$2" 2>/dev/null
}

# The deck's operator gate: its /api/v1 proxy answers 403 without a session.
# One sign-in per run through the shared helper (the PIN is read at call
# time and never echoed), signed out on exit.
# shellcheck source=scripts/deck_session.sh
. "$SAJAG_ROOT/scripts/deck_session.sh"

# When phase 1b recreated the oracle to switch the signal-policy writer on,
# phase 8d recreates it again with its PRE-RUN value (the run leaves the
# writer as it found it); the exit trap does it on any other way out
# (die_hint, Ctrl-C, TERM) and signs out.  A restore that cannot be verified
# fails the run (exit 3 from the trap).
WRITER_RECREATED=""      # set by phase 1b just before it recreates the oracle
WRITER_ORIG_ENV=""       # the oracle container's VVIP_SIGNAL_POLICY_WRITER before that
WRITER_RESTORED=""       # true once the pre-run value is back (verified)
restore_writer() {
    log "restoring traffic-oracle's signal-policy writer to its pre-run value '${WRITER_ORIG_ENV}' (recreate, --no-deps)"
    if recreate_oracle_writer "$WRITER_ORIG_ENV" && wait_writer False \
       && [ "$(oracle_writer_env)" = "$WRITER_ORIG_ENV" ]; then
        WRITER_RESTORED=true
        ok "traffic-oracle restored to its pre-run state: VVIP_SIGNAL_POLICY_WRITER='${WRITER_ORIG_ENV}', writer_enabled False, /health 200"
        return 0
    fi
    WRITER_RESTORED=false
    bad "traffic-oracle NOT restored to its pre-run writer state ('${WRITER_ORIG_ENV}') — the city signal-plan writer may still be ON"
    printf '     FIX: %s\n' "${ORACLE_WRITER_CMD:+VVIP_SIGNAL_POLICY_WRITER='$WRITER_ORIG_ENV' $ORACLE_WRITER_CMD}${ORACLE_WRITER_CMD:-cd $INFRA_DIR && (. $SAJAG_ROOT/scripts/sajag_env.sh && VVIP_SIGNAL_POLICY_WRITER='$WRITER_ORIG_ENV' docker compose -p $COMPOSE_PROJECT $COMPOSE_FILES up -d --no-deps --no-build traffic-oracle) — or bash $SAJAG_ROOT/scripts/sajag_up.sh}" >&2
    return 1
}
on_exit() {
    local rc=$?
    trap - EXIT INT TERM
    deck_signout
    if [ -n "$WRITER_RECREATED" ] && [ "$WRITER_RESTORED" != true ]; then
        restore_writer || { [ "$rc" -eq 0 ] && rc=3; }
    fi
    exit "$rc"
}
trap on_exit EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

# C-G emulator runs are asynchronous: POST answers 202 at once and the run
# goes on inside the emulator; GET /runs/{id}?include_tape=false is the
# light progress poll (status, progress{frame,total,delivered,failed},
# event_id; spec.reason once a run failed or was interrupted).
emu_start() { # <request-json> <out-json> — prints the run_id (202), else the refusal
    EMULATOR="$EMULATOR_URL" python3 - "$1" "$2" <<'PYEOF'
import json, os, sys, urllib.error, urllib.request
req = urllib.request.Request(os.environ["EMULATOR"] + "/api/v1/emulator/runs",
    data=sys.argv[1].encode(), headers={"Content-Type": "application/json"})
try:
    with urllib.request.urlopen(req, timeout=60) as r:
        code, doc = r.status, json.loads(r.read())
except urllib.error.HTTPError as e:
    code = e.code
    try:
        doc = json.loads(e.read())
    except ValueError:
        doc = {}
except OSError as e:
    code, doc = 0, {"detail": f"{type(e).__name__}: {e}"}
json.dump({"http": code, **doc}, open(sys.argv[2], "w"), indent=1)
if code == 202 and doc.get("run_id") is not None:
    print(doc["run_id"])
    sys.exit(0)
# a 409 names the run holding the use case: "... is already running as run N"
print(f"HTTP {code}: {doc.get('detail') or doc}")
sys.exit(1)
PYEOF
}
emu_poll() { # <run_id> <out-json> <timeout-sec> <event|end> — polls every 2 s (bounded), prints the status
    EMULATOR="$EMULATOR_URL" python3 - "$@" <<'PYEOF'
import json, os, sys, time, urllib.request
run_id, out, timeout, until = sys.argv[1], sys.argv[2], float(sys.argv[3]), sys.argv[4]
url = f"{os.environ['EMULATOR']}/api/v1/emulator/runs/{run_id}?include_tape=false"
deadline = time.monotonic() + timeout
doc, error = {}, None
while True:
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            doc, error = json.loads(r.read()), None
    except (OSError, ValueError) as e:
        error = f"{type(e).__name__}: {e}"
    status = doc.get("status")
    if (until == "event" and doc.get("event_id")) or (until == "end" and status not in (None, "running")):
        break
    if time.monotonic() >= deadline:
        break
    time.sleep(2.0)
spec = doc.get("spec") if isinstance(doc.get("spec"), dict) else {}
json.dump({
    "run_id": doc.get("run_id"), "use_case_id": doc.get("use_case_id"), "status": status,
    "reason": spec.get("reason"), "event_id": doc.get("event_id"),
    "movement_id": doc.get("movement_id"), "event_status": doc.get("event_status"),
    "seed": doc.get("seed"), "clock_scale": doc.get("clock_scale"),
    "progress": doc.get("progress"), "delivery": spec.get("delivery"),
    "event_activation": spec.get("event_activation"),
    "scenario_precondition": spec.get("scenario_precondition"),
    "created_at": doc.get("created_at"), "ended_at": doc.get("ended_at"),
    "poll_error": error,
}, open(out, "w"), indent=1)
print(status or "unknown")
PYEOF
}

# Compose may recreate the oracle only when $ORACLE_CONTAINER IS that
# service's container: compose stamps a config hash on the containers it
# creates, while a `docker run` of the compose-built image (a private stack)
# carries only the image's project label — so an env-pointed run can never
# recreate the live oracle by accident.
compose_owns_oracle() {
    local labels
    labels="$(docker inspect "$ORACLE_CONTAINER" --format '{{index .Config.Labels "com.docker.compose.project"}} {{index .Config.Labels "com.docker.compose.config-hash"}}' 2>/dev/null)" || return 1
    [ "${labels%% *}" = "$COMPOSE_PROJECT" ] && [ -n "${labels#* }" ]
}

# The signal-policy writer flag as the oracle reports it: True | False | error
writer_flag() { health "$ORACLE_URL/api/v1/signals/plans" 15 | python3 -c 'import json,sys; print(json.load(sys.stdin).get("writer_enabled"))' 2>/dev/null || echo error; }
# The VVIP_SIGNAL_POLICY_WRITER value the oracle container runs with ('' when empty or unset)
oracle_writer_env() {
    docker inspect "$ORACLE_CONTAINER" --format '{{range .Config.Env}}{{println .}}{{end}}' 2>/dev/null \
        | sed -n 's/^VVIP_SIGNAL_POLICY_WRITER=//p' | tail -n 1
}
# Recreate the oracle with VVIP_SIGNAL_POLICY_WRITER=<value>: a compose-owned
# one through compose (sajag.env loaded for the interpolation, as
# scripts/sajag_up.sh does it; --no-deps --no-build: nothing else is touched
# or built), a private stack's one only through ORACLE_WRITER_CMD; anything
# else is refused (3).  Bounded: a hung recreate cannot wedge the run.
recreate_oracle_writer() { # <value>
    if [ "${SHOWCASE_ALLOW_RECREATE:-0}" != 1 ]; then
        return 4    # the live stack's containers are never recreated unless the operator asks (SHOWCASE_ALLOW_RECREATE=1)
    elif [ -n "${ORACLE_WRITER_CMD:-}" ]; then
        VVIP_SIGNAL_POLICY_WRITER="$1" timeout 300 bash -c "$ORACLE_WRITER_CMD"
    elif compose_owns_oracle; then
        ( cd "$INFRA_DIR" && . "$SAJAG_ROOT/scripts/sajag_env.sh" \
            && export VVIP_SIGNAL_POLICY_WRITER="$1" \
            && timeout 300 docker compose -p "$COMPOSE_PROJECT" $COMPOSE_FILES up -d --no-deps --no-build traffic-oracle )
    else
        return 3
    fi
}
wait_writer() { # <True|False> — the oracle answers /health and reports that writer flag (≤ 120 s)
    local i
    for i in $(seq 1 60); do
        [ "$(hcode "$ORACLE_URL/health" 5)" = "200" ] && [ "$(writer_flag)" = "$1" ] && return 0
        sleep 2
    done
    return 1
}

is_uuid() { [[ "$1" =~ ^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$ ]]; }

# ════════════════════════════════════════════════════════════════════════════
# 1. HEALTH — fleet + host models + emulator + deck, fail fast
# ════════════════════════════════════════════════════════════════════════════
log "phase 1: fleet + host-model health (fail fast)"

n_fleet=0
for c in "$PG_CONTAINER" "$VALKEY_CONTAINER" "$NATS_CONTAINER" "$ORACLE_CONTAINER" "$BRAIN_CONTAINER" "$INGRESS_CONTAINER" "$DECK_CONTAINER" "$EMULATOR_CONTAINER"; do
    [ -n "$c" ] || continue   # served outside docker here: checked over HTTP below
    [ "$(docker inspect "$c" --format '{{.State.Running}}' 2>/dev/null)" = "true" ] \
        || die_hint "container $c is not running" \
            "bash $SAJAG_ROOT/scripts/sajag_up.sh (the live stack) — or bring up the private stack this run is pointed at"
    n_fleet=$((n_fleet + 1))
done
pg_ok=$(docker exec "$PG_CONTAINER" pg_isready -U "$PG_USER" -d "$PG_DB" 2>&1) \
    || die_hint "postgis not answering: $pg_ok" "docker logs $PG_CONTAINER --tail 50"
[ "$(docker exec "$VALKEY_CONTAINER" valkey-cli ping 2>/dev/null)" = "PONG" ] \
    || die_hint "valkey not answering PONG" "docker logs $VALKEY_CONTAINER --tail 50"

[ "$(hcode "$ORACLE_URL/health")" = "200" ] \
    || die_hint "traffic-oracle $ORACLE_URL/health not 200" "docker logs $ORACLE_CONTAINER --tail 50"
cb=$(health "$BRAIN_URL/health" 15)
printf '%s' "$cb" | python3 -c 'import json,sys; d=json.load(sys.stdin); sys.exit(0 if d.get("status")=="ok" and d.get("strategic_tier",{}).get("model_host")=="connected" and d.get("tactical_tier",{}).get("llama_server")=="connected" else 1)' 2>/dev/null \
    || die_hint "convoy-brain $BRAIN_URL/health not ok (decider+gemma must be connected)" \
        "check the host models (systemctl --user status sajag-models.target), then docker restart $BRAIN_CONTAINER; body was: $cb"
# The ONE deck: GET /analyst IS the Convoy Command cockpit — the restored VVIP
# template home, moved off / by the V3 root flip (/ is Home; design-smoke contract:
# 200 + data-template="convoy-command"); /ops remains the situation wall on the
# SAME origin the canvas uses.
deck_root="$(health "$DECK_CONTAINER_URL/analyst" 15)"
if [ "$(hcode "$DECK_CONTAINER_URL/analyst" 15)" = "200" ] \
   && [ "$(hcode "$DECK_CONTAINER_URL/" 15)" = "200" ] \
   && printf '%s' "$deck_root" | grep -q 'data-template="convoy-command"' \
   && [ "$(hcode "$DECK_CONTAINER_URL/ops" 15)" = "200" ]; then
    ok "command-deck $DECK_CONTAINER_URL serving the cockpit (/analyst 200 + convoy-command template; / 200; /ops 200)"
else
    die_hint "command-deck $DECK_CONTAINER_URL not serving the cockpit (want /analyst = 200 + convoy-command template, / = 200, /ops = 200)" \
        "cd $INFRA_DIR && docker compose -p $COMPOSE_PROJECT $COMPOSE_FILES up -d --no-deps --build command-deck"
fi

# Emulator health is assessed on CONNECTIVITY: every seam it probes for real
# (store, Valkey, NATS, the oracle) must answer. A 'degraded' status for
# another reason (the last run failed, the living city idle) is reported,
# never fatal.
emu=$(health "$EMULATOR_URL/health" 15)
emu_state=$(printf '%s' "$emu" | python3 -c '
import json, sys
d = json.load(sys.stdin)
s = d.get("stack") or {}
down = [k for k in ("store", "valkey", "nats", "twin") if not s.get(k)]
print("down " + ",".join(down) if down else "up " + " | ".join(d.get("degraded_reasons") or []))' 2>/dev/null || echo "down unreachable")
case "$emu_state" in
    "up ") ok "event-emulator $EMULATOR_URL wired (store, valkey, nats, oracle all answer)" ;;
    up\ *) ok "event-emulator $EMULATOR_URL wired (store, valkey, nats, oracle all answer); degraded, not down: ${emu_state#up }" ;;
    *) die_hint "event-emulator $EMULATOR_URL cannot reach: ${emu_state#down } (body: $emu)" \
           "docker restart ${EMULATOR_CONTAINER:-<the emulator>} (the live stack: bash $SAJAG_ROOT/scripts/sajag_up.sh)" ;;
esac
lib=$(health "$EMULATOR_URL/api/v1/emulator/use-cases")
n_lib=$(printf '%s' "$lib" | python3 -c 'import json,sys; print(len(json.load(sys.stdin)))' 2>/dev/null || echo 0)
[ "$n_lib" -ge 3 ] || die_hint "emulator library has $n_lib use cases (needs the evening's three)" \
    "the emulator image carries use_case_library.json (the Mumbai library): rebuild/restart ${EMULATOR_CONTAINER:-<the emulator>} (bash $SAJAG_ROOT/scripts/sajag_up.sh)"
printf '%s' "$lib" | grep -q "\"$FLAGSHIP_ID\"" || die_hint "emulator library lacks $FLAGSHIP_ID" "docker restart ${EMULATOR_CONTAINER:-<the emulator>}"
printf '%s' "$lib" | grep -q "\"$RAIN_ID\""      || die_hint "emulator library lacks $RAIN_ID" "docker restart ${EMULATOR_CONTAINER:-<the emulator>}"
printf '%s' "$lib" | grep -q "\"$SWEEP_ID\""     || die_hint "emulator library lacks $SWEEP_ID" "docker restart ${EMULATOR_CONTAINER:-<the emulator>}"

printf '%s' "$(health "$DECIDER_URL/decider/health")" | grep -q '"loaded": *true' \
    || die_hint "decider $DECIDER_URL not loaded" "systemctl --user restart sajag-decider.service (services/model-host/switch_decider.sh status shows the served checkpoint)"
[ "$(hcode "$LLAMA_URL/health" 15)" = "200" ] \
    || die_hint "llama-server $LLAMA_URL not answering" "systemctl --user restart sajag-llama.service (sajag-tactical)"
[ "$(hcode "$EMBED_URL/health" 15)" = "200" ] \
    || die_hint "embedding-service $EMBED_URL not answering" "systemctl --user restart sajag-embed.service"
# the AI services the evening asks (compute only; their proposals wait for an officer)
[ "$(hcode "$HYDRO_URL/health" 15)" = "200" ] \
    || die_hint "hydro service $HYDRO_URL not answering" "systemctl --user status sajag-ai-hydro.service (the waterlogging nowcast, :8197)"
[ "$(hcode "$TWIN_URL/health" 15)" = "200" ] \
    && TWIN_SVC_UP=true || { TWIN_SVC_UP=false; log "note: the signal-timing twin $TWIN_URL does not answer — its proposals are recorded as unavailable"; }

# 1b. the signal-policy writer flag: phase 4d needs it ON (scripts/sajag_up.sh
# --demo sets it).  When it is off the run is REFUSED — unless the operator
# asked for SHOWCASE_ALLOW_RECREATE=1: then the oracle is recreated with it ON
# for this run, and phase 8d (or the exit trap) recreates it with its PRE-RUN
# value (recreate_oracle_writer: compose for a compose-owned oracle,
# ORACLE_WRITER_CMD for a private stack's; any other is refused).
writer_on=$(writer_flag)
if [ "$writer_on" != "True" ] && [ "${SHOWCASE_ALLOW_RECREATE:-0}" != 1 ]; then
    die_hint "the city signal-plan writer is off on $ORACLE_URL (writer_enabled $writer_on) — this script never recreates a running container on its own" \
        "start the stack in demo mode (bash $SAJAG_ROOT/scripts/sajag_up.sh --demo), or re-run with SHOWCASE_ALLOW_RECREATE=1 to recreate the oracle with the writer on for this run only (put back at the end)"
fi
if [ "$writer_on" != "True" ]; then
    [ -n "${ORACLE_WRITER_CMD:-}" ] || compose_owns_oracle \
        || die_hint "signal-policy writer disabled on $ORACLE_CONTAINER, a container compose project $COMPOSE_PROJECT did not create (a private stack) — not recreating it" \
            "set ORACLE_WRITER_CMD to the command that recreates $ORACLE_CONTAINER with VVIP_SIGNAL_POLICY_WRITER from its environment (it is restored on exit), or recreate it with VVIP_SIGNAL_POLICY_WRITER=1 yourself, then re-run"
    WRITER_ORIG_ENV="$(oracle_writer_env)"
    WRITER_RECREATED=1      # armed BEFORE the recreate: even a failed one is put back on exit
    log "signal-policy writer disabled (oracle runs with VVIP_SIGNAL_POLICY_WRITER='${WRITER_ORIG_ENV}') — recreating traffic-oracle with VVIP_SIGNAL_POLICY_WRITER=1 for this run; it is put back to '${WRITER_ORIG_ENV}' at the end (phase 8d, or the exit trap)"
    recreate_oracle_writer 1 \
        || die_hint "could not recreate traffic-oracle with the writer flag" \
            "${ORACLE_WRITER_CMD:+VVIP_SIGNAL_POLICY_WRITER=1 $ORACLE_WRITER_CMD}${ORACLE_WRITER_CMD:-cd $INFRA_DIR && (. $SAJAG_ROOT/scripts/sajag_env.sh && VVIP_SIGNAL_POLICY_WRITER=1 docker compose -p $COMPOSE_PROJECT $COMPOSE_FILES up -d --no-deps --no-build traffic-oracle)}"
    wait_writer True || true
    writer_on=$(writer_flag)
fi
[ "$writer_on" = "True" ] \
    && ok "signal-policy writer ENABLED${WRITER_RECREATED:+ for this run (put back to '${WRITER_ORIG_ENV}' at the end)} (C7 flag; commits still fail closed without a calibrated twin)" \
    || die_hint "signal-policy writer still disabled after recreate" \
        "docker exec $ORACLE_CONTAINER env | grep VVIP_SIGNAL_POLICY_WRITER (must be 1); see $INFRA_DIR/compose.argus-override.yml traffic-oracle.environment"

# 1c. the canvas origin IS the deck (one origin serves /gods-eye, /citizen
# and the /api/v1 reverse proxy, src/hooks.server.ts). Its pages are public;
# the proxy sits behind the operator PIN gate, so this run signs in ONCE.
[ "$(hcode "$DECK_ORIGIN/gods-eye" 10)" = "200" ] && [ "$(hcode "$DECK_ORIGIN/citizen" 10)" = "200" ] \
    && ok "deck serving $DECK_ORIGIN (canvas origin; /gods-eye + /citizen up)" \
    || die_hint "deck canvas origin not answering on $DECK_ORIGIN" \
        "cd $INFRA_DIR && docker compose -p $COMPOSE_PROJECT $COMPOSE_FILES up -d --no-deps --build command-deck"
deck_signin "$DECK_ORIGIN" "Showcase run (automated check)" \
    || die_hint "no operator session on $DECK_ORIGIN (deck_signin said why, above)" \
        "the PIN comes from SAJAG_OPERATOR_PIN, SAJAG_OPERATOR_PIN_FILE (a private deck's PIN file) or sajag.env; one attempt per run — the deck throttles failed sign-ins"
[ "$(deck_curl -s -o /dev/null -w '%{http_code}' --max-time 10 "$DECK_ORIGIN/api/v1/movements/active" 2>/dev/null)" = "200" ] \
    && ok "deck /api/v1 proxy live (hooks.server.ts → traffic-oracle; operator gate ${DECK_GATE}${DECK_OFFICER:+, signed in as \"$DECK_OFFICER\"})" \
    || die_hint "deck /api/v1 proxy not answering 200 on $DECK_ORIGIN" \
        "the deck must reach the oracle on loopback (host networking)${DECK_CONTAINER:+; docker logs $DECK_CONTAINER}"

ok "fleet ($n_fleet containers), emulator $EMULATOR_URL, models $DECIDER_URL/$LLAMA_URL/$EMBED_URL, hydro $HYDRO_URL, deck $DECK_ORIGIN (the ONE deck), writer flag — all healthy"
log "sweep seed this run: $SWEEP_SEED; event ids come from each run's document"

# ════════════════════════════════════════════════════════════════════════════
# 2. BASELINE — none to take: every emulator run is a fresh subject (its
#    event id is run-scoped), so every audit row that names this run's
#    flagship is this run's; phase 8 counts them straight from the store.
# ════════════════════════════════════════════════════════════════════════════
log "phase 2: baseline — this run's flagship is a fresh subject (run-scoped event id): every audit row naming it is this run's"

# ════════════════════════════════════════════════════════════════════════════
# 3. THE REPORT — plate earmarked (the stolen-vehicle chain opens)
# ════════════════════════════════════════════════════════════════════════════
log "phase 3: STOLEN VEHICLE reported — earmarking $STOLEN_PLATE ($FIR_REF; an EMULATED mark, a scenario FIR)"
EARMARK_JSON="$SHOWCASE_DIR/chain_earmark.json"
ORACLE="$ORACLE_URL" PLATE="$STOLEN_PLATE" FIR="$FIR_REF" LABEL="$SHOWCASE_LABEL" python3 - > "$EARMARK_JSON" <<'PYEOF'
import json, os, urllib.request
body = {
    "state": "flagged",
    "reason": f"STOLEN VEHICLE reported — {os.environ['FIR']} (scenario reference); God's-eye evening flagship",
    "lawful_basis": "stolen_vehicle_fir",
    "retention_days": 30,
    "earmarked_by": os.environ["LABEL"],
}
req = urllib.request.Request(
    f"{os.environ['ORACLE']}/api/v1/vehicles/{os.environ['PLATE']}/earmark",
    data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
with urllib.request.urlopen(req, timeout=30) as r:
    print(json.dumps(json.loads(r.read()), indent=1))
PYEOF
EARMARK_OK=$(python3 -c '
import json,sys
d=json.load(open(sys.argv[1]))
print("yes" if d.get("state")=="flagged" and d.get("lawful_basis")=="stolen_vehicle_fir" and d.get("vehicle_id") else "no")' "$EARMARK_JSON" 2>/dev/null || echo no)
VEHICLE_ID=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("vehicle_id",""))' "$EARMARK_JSON" 2>/dev/null || echo "")
[ "$EARMARK_OK" = "yes" ] && [ -n "$VEHICLE_ID" ] \
    && ok "chain[1/6] plate earmarked: $STOLEN_PLATE flagged (lawful_basis stolen_vehicle_fir, vehicle $VEHICLE_ID)" \
    || fail "chain[1/6] earmark failed (see $EARMARK_JSON)"

# ════════════════════════════════════════════════════════════════════════════
# 4. THE EVENING — visarjan crowds + monsoon burst at high tide + the 108 (live)
# ════════════════════════════════════════════════════════════════════════════
log "phase 4: injecting $FLAGSHIP_ID (visarjan night, Lalbaug to Girgaon Chowpatty) and $RAIN_ID (monsoon burst at high tide) clock_scale=$CLOCK_SCALE"
FLAG_JSON="$SHOWCASE_DIR/injection_flagship.json"
FLAG_RUN_ID=$(emu_start "{\"use_case_id\":\"$FLAGSHIP_ID\",\"clock_scale\":$CLOCK_SCALE,\"tick_sec\":$TICK_SEC}" "$FLAG_JSON") \
    || die_hint "the emulator refused the flagship run — $FLAG_RUN_ID" \
        "a 409 names the run already holding $FLAGSHIP_ID: let it finish, or stop it (curl -X POST $EMULATOR_URL/api/v1/emulator/runs/N/stop)"
RAIN_JSON="$SHOWCASE_DIR/injection_rain.json"
RAIN_RUN_ID=$(emu_start "{\"use_case_id\":\"$RAIN_ID\",\"clock_scale\":$CLOCK_SCALE,\"tick_sec\":$TICK_SEC}" "$RAIN_JSON") \
    || die_hint "the emulator refused the cloudburst run — $RAIN_RUN_ID" \
        "a 409 names the run already holding $RAIN_ID: let it finish, or stop it (curl -X POST $EMULATOR_URL/api/v1/emulator/runs/N/stop)"
emu_poll "$FLAG_RUN_ID" "$FLAG_JSON" 60 event >/dev/null
emu_poll "$RAIN_RUN_ID" "$RAIN_JSON" 60 event >/dev/null
FLAG_EVENT_ID=$(jget "$FLAG_JSON" event_id)
RAIN_EVENT_ID=$(jget "$RAIN_JSON" event_id)
is_uuid "$FLAG_EVENT_ID" \
    || die_hint "flagship run $FLAG_RUN_ID named no event id ($(jget "$FLAG_JSON" status): $(jget "$FLAG_JSON" reason))" \
        "GET $EMULATOR_URL/api/v1/emulator/runs/$FLAG_RUN_ID?include_tape=false"
is_uuid "$RAIN_EVENT_ID" || RAIN_EVENT_ID=""
log "flagship run $FLAG_RUN_ID → event $FLAG_EVENT_ID; cloudburst run $RAIN_RUN_ID → event ${RAIN_EVENT_ID:-?} (run-scoped: uuid5 over use_case|seed|run)"

# both events must go LIVE in the movements feed (the advisory source)
seen_live() { # <event_id> — seconds until the event shows in /movements/active (-1: never in 60 s)
    local i n
    for i in $(seq 1 60); do
        n=$(curl -s --max-time 5 "$ORACLE_URL/api/v1/movements/active" \
            | python3 -c 'import json,sys; j=json.load(sys.stdin); print(sum(1 for m in j.get("movements",[]) if m.get("movement_id")==sys.argv[1]))' "$1" 2>/dev/null || echo 0)
        if [ "$n" -ge 1 ] 2>/dev/null; then echo "$i"; return 0; fi
        sleep 1
    done
    echo -1
}
visible_after=$(seen_live "$FLAG_EVENT_ID")
if [ "$visible_after" -ge 0 ] 2>/dev/null; then
    ok "visarjan night LIVE in GET /api/v1/movements/active after ${visible_after}s (the citizen advisory reflects it; SIMULATED)"
    ACTIVE_FEED_SEEN=true
else
    fail "flagship event never appeared in GET /api/v1/movements/active"
    ACTIVE_FEED_SEEN=false
fi
RAIN_FEED_SEEN=false
if [ -n "$RAIN_EVENT_ID" ]; then
    rain_after=$(seen_live "$RAIN_EVENT_ID")
    if [ "$rain_after" -ge 0 ] 2>/dev/null; then
        ok "cloudburst at high tide LIVE in GET /api/v1/movements/active after ${rain_after}s (SIMULATED; $WATER_TEXT first)"
        RAIN_FEED_SEEN=true
    else
        fail "cloudburst event never appeared in GET /api/v1/movements/active"
    fi
else
    fail "cloudburst run $RAIN_RUN_ID named no event id ($(jget "$RAIN_JSON" status): $(jget "$RAIN_JSON" reason))"
fi

# the situation engine must start deciding (audit rows appear) — an uncapped
# SQL count (the /adaptive/situation_log API caps `count` at its limit)
rows_after=-1
for i in $(seq 1 60); do
    n=$($PSQL -c "SELECT count(*) FROM adaptive.situation_log WHERE movement_id='$FLAG_EVENT_ID'" 2>/dev/null || echo 0)
    if [ "${n:-0}" -gt 0 ] 2>/dev/null; then rows_after=$i; break; fi
    sleep 2
done
if [ "$rows_after" -ge 0 ] 2>/dev/null; then
    ok "situation engine deciding on the visarjan night after ~$((rows_after*2))s (audit rows growing)"
else
    log "note: no engine rows yet for the flagship — the explicit observe calls below still drive the audit path"
fi

# 4a. THE WATER — the first waterlogging spot (Hindmata) and the hydro proposals.
#     Three honest sources, never blended:
#       * the SIMULATED monsoon burst's own twin run (its waterlogging events
#         at the first spot, MODELLED);
#       * the hydro service's LIVE nowcast (Open-Meteo rain: a dry night
#         gives class 0 and no proposal — recorded as such);
#       * the hydro service's replay of the 18–19 Aug 2025 Mumbai storm (HINDSIGHT,
#         MODELLED: the observed rain used as if it had been a perfect
#         nowcast) — the proposals an officer would have been shown.
log "phase 4a: waterlogging at $WATER_TEXT — the monsoon burst's twin, the live nowcast, the 18–19 Aug 2025 hindsight replay"
HYDRO_JSON="$SHOWCASE_DIR/hydro_waterlogging.json"
ORACLE="$ORACLE_URL" HYDRO="$HYDRO_URL" SEG="$WATER_SEGMENT" SCENARIO="$RAIN_ID" python3 - > "$HYDRO_JSON" <<'PYEOF'
import json, os, urllib.error, urllib.request

seg = int(os.environ["SEG"])

def call(url, body=None, timeout=180):
    req = urllib.request.Request(url, data=None if body is None else json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"},
                                 method="GET" if body is None else "POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, {"detail": e.read().decode("utf-8", "replace")[:300]}
    except (OSError, ValueError) as e:
        return 0, {"detail": f"{type(e).__name__}: {e}"[:300]}

# 1. the SIMULATED cloudburst through the twin (its audited schedule)
code, twin = call(os.environ["ORACLE"] + "/api/v1/simulate/twin", {"scenario_id": os.environ["SCENARIO"]})
runs = twin.get("runs", []) if code == 200 else []
ev0 = runs[0].get("events", []) if runs else []
wl = [e for e in ev0 if e.get("type") == "waterlogging"]
twin_out = {"http": code, "replications": len(runs), "calibrated": twin.get("calibrated"),
            "waterlogging_events": len(wl),
            "on_segment": [e.get("label") for e in wl if e.get("segment_id") == seg],
            "labels_sample": [e.get("label") for e in wl][:4],
            "emergency_windows": sum(1 for e in ev0 if e.get("type") == "emergency_vehicle"),
            "label": "SIMULATED scenario; rain, tide, pumps and spread MODELLED"}

# 2. the LIVE nowcast (compute only; GET)
code, nc = call(os.environ["HYDRO"] + "/hydro/nowcast")
segs = nc.get("segments", []) if code == 200 else []
mine = next((s for s in segs if s.get("segment_id") == seg), {})
props = nc.get("proposals", []) if code == 200 else []
live_out = {"http": code, "labels": nc.get("labels"),
            "rain_now_mm_h": (nc.get("rain_feed") or {}).get("city_now_mm_h"),
            "rain_source": (nc.get("rain_feed") or {}).get("source"),
            "counts_by_class": nc.get("counts_by_class"),
            "segment": {"risk_class": mine.get("risk_class"), "risk_name": mine.get("risk_name"),
                        "expected_depth_band": mine.get("expected_depth_band"),
                        "lead_time_min": mine.get("lead_time_min"),
                        "drivers": sorted((mine.get("drivers") or {}).keys())},
            "proposals": len(props),
            "proposals_on_segment": [p.get("kind") for p in props if p.get("subject_urn") == f"segment:{seg}"]}

# 3. the 18–19 Aug 2025 Mumbai storm replay (HINDSIGHT; compute only)
code, rp = call(os.environ["HYDRO"] + "/hydro/replay?event=2025-08-19", {})
gauge = ((rp.get("runs") or {}).get("imd_gauge_anchored") or {}) if code == 200 else {}
snap = gauge.get("snapshot") or {}
rseg = next((s for s in (gauge.get("segments") or []) if s.get("segment_id") == seg), {})
rprops = snap.get("proposals") or []
replay_out = {"http": code, "event": rp.get("event"), "title": rp.get("title"),
              "label": snap.get("label"), "at_ist": snap.get("at_ist"),
              "station_window_totals_mm": gauge.get("station_window_totals_mm"),
              "flagged_segments": gauge.get("flagged_segments"),
              "segment": {k: rseg.get(k) for k in ("road_name", "peak_class", "peak_band", "peak_depth_cm",
                                                    "first_class1_ist", "first_class2_ist", "peak_at_ist")},
              "proposal_counts": snap.get("proposal_counts"),
              "proposal_kinds": sorted({p.get("kind") for p in rprops}),
              "proposal_examples": [p.get("summary") for p in rprops if p.get("kind") != "public_advisory_draft"][:3],
              "every_proposal_proposed": all(p.get("state") == "proposed" for p in rprops),
              "labels": sorted({l for p in rprops for l in (p.get("labels") or [])})}
print(json.dumps({"segment_id": seg, "twin_simulated": twin_out, "live_nowcast": live_out,
                  "hindsight_replay_2025_08_19": replay_out}, indent=1, ensure_ascii=False))
PYEOF
read -r WL_TWIN WL_ON_SEG LIVE_CLASS LIVE_PROPS RAIN_NOW RP_CLASS RP_BAND RP_KINDS RP_OK < <(python3 -c '
import json, sys
d = json.load(open(sys.argv[1]))
t, l, r = d["twin_simulated"], d["live_nowcast"], d["hindsight_replay_2025_08_19"]
kinds = r.get("proposal_kinds") or []
need = {"waterlogging_reroute", "ambulance_window", "live_wire_hazard", "public_advisory_draft"}
print(t.get("waterlogging_events", 0), len(t.get("on_segment") or []),
      l["segment"].get("risk_class") if l["segment"].get("risk_class") is not None else "-",
      l.get("proposals", 0), l.get("rain_now_mm_h") if l.get("rain_now_mm_h") is not None else "-",
      r["segment"].get("peak_class") if r["segment"].get("peak_class") is not None else "-",
      (r["segment"].get("peak_band") or "-").replace(" ", "_"),
      ",".join(kinds) or "-",
      "yes" if need <= set(kinds) and r.get("every_proposal_proposed") and "HINDSIGHT" in (r.get("labels") or []) else "no")' "$HYDRO_JSON" 2>/dev/null || echo "0 0 - 0 - - - - no")
[ "$WL_TWIN" -ge 1 ] && [ "$WL_ON_SEG" -ge 1 ] \
    && ok "monsoon burst (SIMULATED) in the twin: $WL_TWIN waterlogging events, $WL_ON_SEG at $WATER_TEXT (MODELLED rain, tide, pumps)" \
    || fail "the monsoon burst's twin run shows no waterlogging at $WATER_TEXT (see $HYDRO_JSON)"
if [ "$LIVE_CLASS" != "-" ]; then
    ok "hydro LIVE nowcast answered: segment $WATER_SEGMENT class $LIVE_CLASS, city rain now ${RAIN_NOW} mm/h (Open-Meteo, LIVE), $LIVE_PROPS proposal(s) city-wide — a dry night proposes nothing, and says so"
else
    fail "hydro live nowcast did not answer for segment $WATER_SEGMENT (see $HYDRO_JSON)"
fi
[ "$RP_OK" = "yes" ] \
    && ok "hindsight replay of 18–19 Aug 2025 (HINDSIGHT, MODELLED): segment $WATER_SEGMENT peaked at class $RP_CLASS (${RP_BAND//_/ }); the replay proposes $RP_KINDS — each 'proposed', for an officer to decide" \
    || fail "the 19 Aug 2025 replay's proposals are not the four kinds, labelled HINDSIGHT and all 'proposed' (see $HYDRO_JSON)"

# 4b. THE SIREN — the 108 green-corridor request, decided mid-crowd.
#     Observe calls with the flagship's documented cause values (EXTREME
#     crowd, rain, ambulance projection 120 s) drive the escalation channel;
#     the band itself only escalates after hysteresis up_confirm=2, so the
#     peak is re-polled until the effective band carries it.
log "phase 4b: ambulance (108) green-corridor request — $AMBULANCE_ROUTE_TEXT"
OBSERVE_JSON="$SHOWCASE_DIR/ambulance_observe.json"
ORACLE="$ORACLE_URL" MID="$FLAG_EVENT_ID" ROUTE="$AMBULANCE_ROUTE" python3 - > "$OBSERVE_JSON" <<'PYEOF'
import json, os, time, urllib.request

ROUTE = [int(s) for s in os.environ["ROUTE"].split(",")]

def post(doc):
    body = {"movement_id": os.environ["MID"], "vvip_class": "none", **doc}
    req = urllib.request.Request(
        os.environ["ORACLE"] + "/api/v1/adaptive/observe",
        data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())

def summarize(label, resp):
    return {
        "label": label,
        "effective_class": resp.get("effective_class"),
        "transitioned": resp.get("transitioned"),
        "previous_class": resp.get("previous_class"),
        "escalation": ((resp.get("params_response") or {}).get("evidence") or {}).get("escalation"),
        "param_source": (resp.get("params_response") or {}).get("source"),
    }

out = [summarize("window_opening", post({
    "predicted_congestion_idx": 0.55, "weather_severity": 0.35, "weather": "RAIN",
    "crowd_score": 0.55, "crowd_class": "EXTREME", "duration_class": "hours",
    "event_active": True, "ambulance_delay_projection_sec": 45,
    "route_segment_ids": ROUTE,
}))]

# The peak: the monsoon cell sits over the same island-city roads (the
# procession route runs through the low-lying belt), so the weather is the storm the
# SIMULATED scenario models (100 mm/h) — STORM, not RAIN.
# Band escalation is confirmation-gated (hysteresis up_confirm=2) and the
# engine loop interleaves its own ticks on the same movement every ~5 s, so
# the 108 dispatcher RE-POLLS (bounded train, early exit once the band
# carries the escalation past the crowd's own AMBER).
peak_doc = {
    "predicted_congestion_idx": 0.92, "weather_severity": 0.9, "weather": "STORM",
    "crowd_score": 0.92, "crowd_class": "EXTREME", "duration_class": "hours",
    "event_active": True, "ambulance_delay_projection_sec": 120,
    "route_segment_ids": ROUTE,
}
trail, peak = [], None
for i in range(9):
    peak = summarize("escalation_peak", post(peak_doc))
    trail.append({"attempt": i + 1, "effective_class": peak["effective_class"],
                  "transitioned": peak["transitioned"]})
    if peak["effective_class"] in ("RED", "BLACK"):
        break
    time.sleep(2.0)
peak["confirm_attempts"] = len(trail)
peak["confirm_trail"] = trail
out.append(peak)
print(json.dumps(out, indent=1))
PYEOF
OBSERVE_OK=$(python3 -c '
import json,sys
d=json.load(open(sys.argv[1]))
peak=d[-1]
esc=json.dumps(peak.get("escalation") or "")
print("yes" if len(d)==2 and peak.get("effective_class") in ("AMBER","RED","BLACK") and "AMBULANCE_DELAY" in esc else "no")' "$OBSERVE_JSON" 2>/dev/null || echo no)
[ "$OBSERVE_OK" = "yes" ] \
    && ok "ambulance (108) escalation decided mid-crowd ($(python3 -c 'import json,sys;d=json.load(open(sys.argv[1]));p=d[-1];print(p["effective_class"], json.dumps(p["escalation"]))' "$OBSERVE_JSON" 2>/dev/null))" \
    || fail "ambulance escalation decision missing (see $OBSERVE_JSON)"

# 4c. CIVIC VOLUNTEERS — dispatch to the visarjan crowd spill (the flagship's first crowd cause)
# a crossing at the end of that road, checked against the store's adjacency
SPILL_JUNCTION=$($PSQL -c "SELECT via_junction_id FROM corridor.segment_adjacency WHERE $SPILL_SEGMENT IN (from_segment_id, to_segment_id) ORDER BY via_junction_id LIMIT 1")
[ -n "$SPILL_JUNCTION" ] || SPILL_JUNCTION=6
log "phase 4c: Civic Volunteers dispatch to the $SPILL_TEXT (junction $SPILL_JUNCTION)"
JR_JSON="$SHOWCASE_DIR/civic_volunteers.json"
ORACLE="$ORACLE_URL" EVENT="$FLAG_EVENT_ID" JUNCTION="$SPILL_JUNCTION" OFFICER="$OFFICER" LABEL="$SHOWCASE_LABEL" SPILL_TEXT="$SPILL_TEXT" python3 - > "$JR_JSON" <<'PYEOF'
import json, os, urllib.request

def post(path, body):
    req = urllib.request.Request(os.environ["ORACLE"] + path,
        data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())

ev, junction = os.environ["EVENT"], int(os.environ["JUNCTION"])
# the platform's agency code for the Civic Volunteers is 'jan_rakshak'
# (migration 011 CHECK; ingest/units_consumer.py maps civic_volunteers to it)
d = post(f"/api/v1/events/{ev}/dispatch", {
    "agency": "jan_rakshak", "unit_id": "CV-EM-01", "waypoint_junction": junction,
    "requested_by": os.environ["LABEL"],
    "note": os.environ["SPILL_TEXT"] + " — crowd-management support for the traffic police",
})
did = d["dispatch_id"]
decision = post(f"/api/v1/dispatches/{did}/decision",
                {"action": "approve", "officer": os.environ["OFFICER"],
                 "note": "Civic Volunteers approved for the visarjan crowd spill"})
en_route = post(f"/api/v1/dispatches/{did}/status",
                {"status": "en_route", "officer": os.environ["OFFICER"]})
on_scene = post(f"/api/v1/dispatches/{did}/status",
                {"status": "on_scene", "officer": os.environ["OFFICER"],
                 "note": "volunteers holding the queue line along the procession route"})
with urllib.request.urlopen(os.environ["ORACLE"] + "/api/v1/units", timeout=30) as r:
    units = json.loads(r.read()).get("units", [])
mine = [x for x in units if x.get("dispatch_id") == did]
print(json.dumps({
    "dispatch_id": did, "event_id": ev, "agency": d.get("agency"),
    "agency_label": d.get("agency_label"), "unit_id": d.get("unit_id"),
    "statuses": [d.get("status"), decision.get("status"), en_route.get("status"), on_scene.get("status")],
    "audit": [(a.get("from_status"), a.get("to_status"), a.get("actor")) for a in reversed(on_scene.get("audit", []))],
    "projected_unit": mine[0] if mine else None,
}, indent=1))
PYEOF
JR_OK=$(python3 -c '
import json,sys
d=json.load(open(sys.argv[1]))
print("yes" if d.get("statuses")==["requested","approved","en_route","on_scene"] and d.get("projected_unit") else "no")' "$JR_JSON" 2>/dev/null || echo no)
JR_UNIT=$(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); u=d.get("projected_unit") or {}; print(u.get("label") or u.get("unit_id") or "")' "$JR_JSON" 2>/dev/null || echo "")
JR_LABEL=$(jget "$JR_JSON" agency_label)
JR_DISPATCH_ID=$(jget "$JR_JSON" dispatch_id)
[ "$JR_OK" = "yes" ] \
    && ok "Civic Volunteers (agency code jan_rakshak, label '${JR_LABEL:-?}') dispatched: requested->approved->en_route->on_scene (audited, approved by \"$OFFICER\"); live unit projected (EMULATED): $JR_UNIT" \
    || fail "Civic Volunteers dispatch lifecycle incomplete (see $JR_JSON)"
CIVIC_DISPATCHED=$([ "$JR_OK" = "yes" ] && echo true || echo false)

# 4d. CITY SIGNAL PLANS vs THE BAND — calibration replay + live-band apply;
#     the C7 guard's decision must be fully auditable (ruling on record).
log "phase 4d: city signal-policy engine vs the situation band"
SIGNALS_JSON="$SHOWCASE_DIR/signal_policy.json"
ORACLE="$ORACLE_URL" EVENT="$FLAG_EVENT_ID" OFFICER="$OFFICER" ROUTE="$AMBULANCE_ROUTE" python3 - > "$SIGNALS_JSON" <<'PYEOF'
import json, os, urllib.request, urllib.error
from datetime import datetime, timedelta, timezone

def post(path, body, timeout=180):
    req = urllib.request.Request(os.environ["ORACLE"] + path,
        data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())

def get(path):
    with urllib.request.urlopen(os.environ["ORACLE"] + path, timeout=30) as r:
        return json.loads(r.read())

# 1. the twin calibration replay over the last 72 h of FIELD data (honest
#    numbers): traffic.hourly_aggregates holds real observations only — with
#    a simulated / emulated feed the replay answers no_data and the twin
#    stays uncalibrated, which is the truth
now = datetime.now(timezone.utc).replace(microsecond=0)
code, replay = post("/api/v1/simulate/replay",
    {"window_start": (now - timedelta(hours=72)).isoformat().replace("+00:00", "Z"),
     "window_end": now.isoformat().replace("+00:00", "Z")})
# 2. the LIVE city band as the situation engine sees it
band_live = get("/api/v1/signals/plans").get("city_band")
# 3. the operator action: apply the live band's city plan for the evening
band = band_live if band_live in ("AMBER", "RED", "BLACK") else "RED"
code_apply, apply_resp = post("/api/v1/signals/plans/apply",
    {"band": band, "event_id": os.environ["EVENT"],
     "route_segment_ids": [int(s) for s in os.environ["ROUTE"].split(",")],
     "officer": os.environ["OFFICER"]})
detail = apply_resp.get("detail", apply_resp) if code_apply != 200 else apply_resp
# 4. the auditable decision surface
plans = get("/api/v1/signals/plans")
last = plans.get("last_plan") or {}
committed = bool(code_apply == 200 and apply_resp.get("applied"))
refused = (not committed) and bool(last) and last.get("band") == band
history = get("/api/v1/signals/history?limit=20").get("history", [])
print(json.dumps({
    "replay": {"status": replay.get("status"), "reason": replay.get("reason"),
               "window_start": replay.get("window_start"), "window_end": replay.get("window_end"),
               "n_observations": replay.get("n_observations"),
               "speed_mae_kmh": replay.get("speed_mae_kmh"),
               "mae_tolerance_kmh": replay.get("mae_tolerance_kmh"),
               "calibrated": replay.get("calibrated")},
    "city_band_live": band_live,
    "city_band_simulated_feed": plans.get("city_band_simulated_feed"),
    "apply": {"http": code_apply, "band": band, "applied": committed,
              "reason": detail.get("reason"),
              "planned_junctions": detail.get("planned_junctions"),
              "shadow_eval": detail.get("shadow_eval")},
    "last_plan_auditable": {
        "band": last.get("band"),
        "planned_junctions": last.get("planned_junctions"),
        "shadow_eval": last.get("shadow_eval"),
        "event_id": last.get("event_id"),
    },
    "committed_writes": 0 if not committed else len(apply_resp.get("planned_junctions", [])),
    "policy_refusals": 1 if refused else 0,
    "history_rows": len(history),
}, indent=1))
PYEOF
SIGNAL_GUARD_OK=$(python3 -c '
import json,sys
d=json.load(open(sys.argv[1]))
rep=d.get("replay") or {}; ap=d.get("apply") or {}; lp=d.get("last_plan_auditable") or {}
se=(ap.get("shadow_eval") or {}); lse=(lp.get("shadow_eval") or {})
ok = rep.get("status") is not None \
     and rep.get("calibrated") is False \
     and ap.get("applied") is False \
     and (len(ap.get("planned_junctions") or []) >= 1) \
     and se.get("detail") == "twin_not_calibrated" \
     and lse.get("detail") == "twin_not_calibrated" \
     and (len(lp.get("planned_junctions") or []) >= 1)
print("yes" if ok else "no")' "$SIGNALS_JSON" 2>/dev/null || echo no)
SIGNAL_MAE=$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["replay"]["speed_mae_kmh"])' "$SIGNALS_JSON" 2>/dev/null || echo unknown)
REPLAY_SUMMARY=$(python3 -c '
import json, sys
r = json.load(open(sys.argv[1]))["replay"]
head = "replay %s: %s field hourly aggregates in the last 72 h" % (r.get("status"), r.get("n_observations") or 0)
mae = r.get("speed_mae_kmh")
print(head + (", MAE %s km/h vs the %s km/h gate" % (mae, r.get("mae_tolerance_kmh")) if mae is not None
              else " (%s)" % (r.get("reason") or "no MAE")))' "$SIGNALS_JSON" 2>/dev/null || echo "replay summary unavailable")
if [ "$SIGNAL_GUARD_OK" = "yes" ]; then
    NJ=$(python3 -c 'import json,sys;print(len(json.load(open(sys.argv[1]))["last_plan_auditable"]["planned_junctions"]))' "$SIGNALS_JSON" 2>/dev/null)
    ok "signal-policy engine end-to-end: band $(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["city_band_live"])' "$SIGNALS_JSON" 2>/dev/null) -> plan for $NJ junctions proposed -> C7 guard REFUSED the commit (twin_not_calibrated; $REPLAY_SUMMARY) -> decision auditable in GET /signals/plans"
else
    fail "signal-policy guard sequence not auditable as expected (see $SIGNALS_JSON — a COMMIT would also fail this check; committed writes are counted, not asserted absent)"
fi
SIGNAL_PLAN_SHIFTS=$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1])).get("committed_writes",0))' "$SIGNALS_JSON" 2>/dev/null || echo 0)
SIGNAL_REFUSALS=$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1])).get("policy_refusals",0))' "$SIGNALS_JSON" 2>/dev/null || echo 0)

# 4d'. the signal-timing twin's own proposal for Rashbehari crossing (junction
#      20, programmed): the South belt's Deshapriya Park crowd fills Rash Behari
#      Avenue from there. The twin computes only; its proposal waits for a named
#      officer on Decide and is never applied by this script.
TWIN_JSON2="$SHOWCASE_DIR/twin_proposal.json"
TWIN_JUNCTION=20
if [ "${TWIN_SVC_UP:-false}" = true ]; then
    TWIN="$TWIN_URL" JUNCTION="$TWIN_JUNCTION" python3 - > "$TWIN_JSON2" <<'PYEOF'
import json, os, urllib.error, urllib.request

body = {"junction_ids": [int(os.environ["JUNCTION"])]}
req = urllib.request.Request(os.environ["TWIN"] + "/twin/propose", data=json.dumps(body).encode(),
                             headers={"Content-Type": "application/json"})
try:
    with urllib.request.urlopen(req, timeout=120) as r:
        code, doc = r.status, json.loads(r.read())
except urllib.error.HTTPError as e:
    code, doc = e.code, {"detail": e.read().decode("utf-8", "replace")[:300]}
except (OSError, ValueError) as e:
    code, doc = 0, {"detail": f"{type(e).__name__}: {e}"[:300]}
p = doc.get("proposal") if isinstance(doc.get("proposal"), dict) else {}
change = p.get("change") if isinstance(p.get("change"), dict) else {}
print(json.dumps({"http": code, "junction_ids": body["junction_ids"],
                  "recommendation": doc.get("recommendation"),
                  "candidates_evaluated": doc.get("candidates_evaluated"),
                  "labels": doc.get("labels"),
                  "proposal_id": p.get("proposal_id"), "kind": p.get("kind"), "state": p.get("state"),
                  "summary": change.get("summary"), "summary_mr": change.get("summary_mr"),
                  "duration_min": p.get("duration_min"),
                  "detail": None if code == 200 else doc.get("detail")}, indent=1, ensure_ascii=False))
PYEOF
    TWIN_PROPS_HTTP=$(jget "$TWIN_JSON2" http)
    TWIN_REC=$(jget "$TWIN_JSON2" recommendation)
    if [ "$TWIN_PROPS_HTTP" = "200" ] && [ -n "$TWIN_REC" ]; then
        TWIN_PROPS=$([ -n "$(jget "$TWIN_JSON2" proposal_id)" ] && echo 1 || echo 0)
        ok "signal-timing twin for Rashbehari crossing: $(jget "$TWIN_JSON2" candidates_evaluated) timings evaluated against doing nothing -> '$TWIN_REC'$([ "$TWIN_PROPS" = 1 ] && echo ": $(jget "$TWIN_JSON2" summary | cut -c1-140)") (MODELLED; waits for an officer, nothing applied)"
    else
        TWIN_PROPS=0
        log "note: the signal-timing twin answered HTTP ${TWIN_PROPS_HTTP:-?} ($(jget "$TWIN_JSON2" detail | cut -c1-120)) — recorded, not asserted"
    fi
else
    TWIN_PROPS=0
    echo '{"unavailable": true}' > "$TWIN_JSON2"
fi

# 4e. THE CITY, MID-EVENING — the 3D canvas while the flagship event is active
log "phase 4e: 3D city canvas shot (mid-evening, live layers, the visarjan route to Girgaon Chowpatty)"
CHROME_BIN="${CHROME_PATH:-$HOME/.cache/puppeteer/chrome/linux_arm-153.0.8010.36/chrome-linux-arm64/chrome}"
if [ ! -x "$CHROME_BIN" ]; then
    CHROME_BIN="$(find "$HOME/.cache/puppeteer/chrome" -name chrome -type f -perm -u+x 2>/dev/null | sort | tail -1)"
fi
CANVAS_SHOTS="$SAJAG_ROOT/scripts/showcase/canvas_shots.mjs"
if [ -n "$CHROME_BIN" ] && [ -x "$CHROME_BIN" ]; then
    export CHROME_PATH="$CHROME_BIN"
    if ( cd "$SAJAG_ROOT/frontend" && NODE_PATH="$SAJAG_ROOT/frontend/node_modules" \
         node "$CANVAS_SHOTS" --city-only "$DECK_ORIGIN" "$SHOWCASE_DIR" "pending" ) \
         > "$SHOWCASE_DIR/shots_city.log" 2>&1; then
        ok "canvas shot: showcase_gods_eye_city.png proven non-blank (see shots_city.log)"
        CITY_SHOT_OK=true
    else
        bad "city canvas capture failed (details: $SHOWCASE_DIR/shots_city.log)"
        fail "3D city canvas shot failed"
        CITY_SHOT_OK=false
    fi
else
    fail "chrome binary missing (CHROME_PATH) — canvas shots impossible"
    CITY_SHOT_OK=false
fi

# 4f. the flagship and rain runs' end — C-G runs are asynchronous, so each run
#     document is polled (GET /runs/{id}?include_tape=false every 2 s,
#     bounded) — then the green-corridor windows in the twin's schedule
log "phase 4f: flagship run $FLAG_RUN_ID + cloudburst run $RAIN_RUN_ID — waiting for their end (poll every 2 s, ≤ ${FLAG_RUN_TIMEOUT_SEC}s)"
FLAG_STATUS=$(emu_poll "$FLAG_RUN_ID" "$FLAG_JSON" "$FLAG_RUN_TIMEOUT_SEC" end)
RAIN_STATUS=$(emu_poll "$RAIN_RUN_ID" "$RAIN_JSON" "$FLAG_RUN_TIMEOUT_SEC" end)
FLAG_DELIVERED=$(jget "$FLAG_JSON" progress.delivered)
FLAG_DELIVERED=${FLAG_DELIVERED:-0}
FLAG_DELIVERY=$(jget "$FLAG_JSON" progress)
[ -n "$FLAG_DELIVERY" ] || FLAG_DELIVERY="{}"
RAIN_DELIVERED=$(jget "$RAIN_JSON" progress.delivered)
RAIN_DELIVERED=${RAIN_DELIVERED:-0}
log "flagship run $FLAG_RUN_ID $FLAG_STATUS; progress $FLAG_DELIVERY; cloudburst run $RAIN_RUN_ID $RAIN_STATUS ($RAIN_DELIVERED frames)"
case "$FLAG_STATUS" in
    completed)
        [ "$FLAG_DELIVERED" -gt 0 ] \
            && ok "flagship run $FLAG_RUN_ID completed: $FLAG_DELIVERED of $(jget "$FLAG_JSON" progress.total) frames delivered (progress.delivered)" \
            || fail "flagship run $FLAG_RUN_ID completed with 0 frames delivered" ;;
    running) fail "flagship run $FLAG_RUN_ID still running after ${FLAG_RUN_TIMEOUT_SEC}s (see $FLAG_JSON)" ;;
    *) fail "flagship run $FLAG_RUN_ID ended $FLAG_STATUS: $(jget "$FLAG_JSON" reason)" ;;
esac
case "$RAIN_STATUS" in
    completed)
        [ "$RAIN_DELIVERED" -gt 0 ] \
            && ok "cloudburst run $RAIN_RUN_ID completed: $RAIN_DELIVERED of $(jget "$RAIN_JSON" progress.total) frames delivered" \
            || fail "cloudburst run $RAIN_RUN_ID completed with 0 frames delivered" ;;
    running) fail "cloudburst run $RAIN_RUN_ID still running after ${FLAG_RUN_TIMEOUT_SEC}s (see $RAIN_JSON)" ;;
    *) fail "cloudburst run $RAIN_RUN_ID ended $RAIN_STATUS: $(jget "$RAIN_JSON" reason)" ;;
esac

log "phase 4f: twin audit — green-corridor windows in the audited schedule"
TWIN_JSON="$SHOWCASE_DIR/twin_audit.json"
ORACLE="$ORACLE_URL" SCENARIO="$FLAGSHIP_ID" python3 - > "$TWIN_JSON" <<'PYEOF'
import json, os, urllib.request
req = urllib.request.Request(os.environ["ORACLE"] + "/api/v1/simulate/twin",
    data=json.dumps({"scenario_id": os.environ["SCENARIO"]}).encode(),
    headers={"Content-Type": "application/json"})
with urllib.request.urlopen(req, timeout=300) as r:
    d = json.loads(r.read())
runs = d.get("runs", [])
ev0 = runs[0].get("events", []) if runs else []
windows = [e for e in ev0 if e.get("type") == "emergency_vehicle"]
print(json.dumps({
    "replications": len(runs),
    "seed": d.get("seed"),
    "route_segment_ids": d.get("route_segment_ids"),
    "green_corridor_windows": len(windows),
    "window_labels": [w.get("label") for w in windows][:6],
    "window_segments": [w.get("segment_id") for w in windows][:6],
    "ambulance_delay_sec_mean": (sum(r.get("ambulance_delay_sec", 0) for r in runs) / len(runs)) if runs else None,
}, indent=1))
PYEOF
GC_WINDOWS=$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1])).get("green_corridor_windows",0))' "$TWIN_JSON" 2>/dev/null || echo 0)
[ "$GC_WINDOWS" -ge 1 ] \
    && ok "green corridor windows: the twin's audited schedule holds $GC_WINDOWS emergency_vehicle windows for the 108's crossings ($(python3 -c 'import json,sys;print("; ".join(json.load(open(sys.argv[1])).get("window_labels",[])[:3]))' "$TWIN_JSON" 2>/dev/null))" \
    || fail "no green-corridor window in the twin audited schedule (see $TWIN_JSON)"

# ════════════════════════════════════════════════════════════════════════════
# 5. THE SWEEP — emulated ANPR cameras read the stolen plate (live)
# ════════════════════════════════════════════════════════════════════════════
log "phase 5: ANPR sweep $SWEEP_ID (seed $SWEEP_SEED, clock $SWEEP_CLOCK) — the stolen plate crosses the emulated Mumbai camera sites"
SWEEP_JSON="$SHOWCASE_DIR/injection_sweep.json"
SWEEP_RUN_ID=$(emu_start "{\"use_case_id\":\"$SWEEP_ID\",\"seed\":$SWEEP_SEED,\"clock_scale\":$SWEEP_CLOCK,\"tick_sec\":$TICK_SEC}" "$SWEEP_JSON") \
    || die_hint "the emulator refused the ANPR sweep — $SWEEP_RUN_ID" \
        "a 409 names the run already holding $SWEEP_ID: let it finish, or stop it (curl -X POST $EMULATOR_URL/api/v1/emulator/runs/N/stop)"
SWEEP_STATUS=$(emu_poll "$SWEEP_RUN_ID" "$SWEEP_JSON" "$SWEEP_RUN_TIMEOUT_SEC" end)
SWEEP_DELIVERED=$(jget "$SWEEP_JSON" progress.delivered)
SWEEP_DELIVERED=${SWEEP_DELIVERED:-0}
SWEEP_EVENT_ID=$(jget "$SWEEP_JSON" event_id)
is_uuid "$SWEEP_EVENT_ID" || SWEEP_EVENT_ID=""
log "sweep run $SWEEP_RUN_ID $SWEEP_STATUS: event ${SWEEP_EVENT_ID:-?}, delivered $SWEEP_DELIVERED frames; scenario precondition: $(jget "$SWEEP_JSON" scenario_precondition)"
if [ "$SWEEP_STATUS" = "completed" ] && [ "$SWEEP_DELIVERED" -gt 0 ]; then
    ok "ANPR sweep delivered $SWEEP_DELIVERED frames into the live stack (run $SWEEP_RUN_ID completed)"
elif [ "$SWEEP_STATUS" = "running" ]; then
    fail "ANPR sweep run $SWEEP_RUN_ID still running after ${SWEEP_RUN_TIMEOUT_SEC}s (see $SWEEP_JSON)"
else
    fail "ANPR sweep run $SWEEP_RUN_ID ended $SWEEP_STATUS with $SWEEP_DELIVERED frames delivered: $(jget "$SWEEP_JSON" reason)"
fi

# ════════════════════════════════════════════════════════════════════════════
# 6. THE CHAIN — evidence -> officer authorisation -> pursuit -> interception
#                -> live trace (every step a real API call, asserted)
# ════════════════════════════════════════════════════════════════════════════
log "phase 6: the stolen-vehicle chain (sightings -> evidence, no fine -> officer authorisation -> pursuit -> trace)"
CHAIN_JSON="$SHOWCASE_DIR/pursuit_chain.json"
ORACLE="$ORACLE_URL" VID="$VEHICLE_ID" RUN="$SWEEP_RUN_ID" PLATE="$STOLEN_PLATE" \
OFFICER="$OFFICER" FIR="$FIR_REF" BELT="$SWEEP_BELT" BELT_TEXT="$SWEEP_BELT_TEXT" python3 - > "$CHAIN_JSON" <<'PYEOF'
import json, os, urllib.request, urllib.error

PENAL = ("R_SPD_SEGMENT", "R_SIGNAL_VIOLATION", "R_CLOSED_CORRIDOR_ENTRY")   # enforcement/rules.py RULE_IDS
NOTE = "pursuit authorised on a reported-stolen vehicle (evidence, no fine)"

def call(path, body=None):
    """(HTTP status, body) — a refusal is RECORDED, never fatal: the
    artifact must always land so the assertions check real state."""
    req = urllib.request.Request(os.environ["ORACLE"] + path,
        data=None if body is None else json.dumps(body).encode(),
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            doc = json.loads(e.read())
        except ValueError:
            doc = {}
        return e.code, doc if isinstance(doc, dict) else {"detail": doc}

def refused(code, doc):
    return {"_http_error": code, "_detail": str(doc.get("detail", doc))[:300]}

vid, run, plate = os.environ["VID"], int(os.environ["RUN"]), os.environ["PLATE"]
officer, fir = os.environ["OFFICER"], os.environ["FIR"]

# 2. the emulated ANPR camera sightings of the stolen plate (this run)
code, sight = call(f"/api/v1/vehicles/{vid}/sightings?limit=200")
sightings = sight.get("sightings", []) if code == 200 else []
stolen = [s for s in sightings if s.get("matched_plate_hit") == "stolen_vehicle"]
this_run = [s for s in stolen if s.get("run_id") == run]
this_ids = {s["sighting_id"] for s in this_run}

# 3. the deterministic rules over this run's reads.  The ANPR ingest ran
#    them as each read landed; re-running is idempotent and says what fired:
#    under the FIR earmark ONE evidence-only R_STOLEN_SIGHTING per read, the
#    penal rules' outcomes WITHHELD — no e-challan for the victim's car (C-N)
fired, withheld, eval_errors = [], [], []
for s in this_run:
    code, resp = call("/api/v1/enforcement/evaluate", {"sighting_id": s["sighting_id"]})
    if code != 200:
        eval_errors.append(refused(code, resp))
        continue
    fired += resp.get("fired", [])
    withheld += resp.get("withheld_rules", [])

code, listing = call("/api/v1/enforcement/recommendations?status=pending&limit=500")
pending = listing.get("recommendations", []) if code == 200 else []
on_plate = [r for r in pending if r.get("plate") == plate]
evidence = [r for r in on_plate
            if r.get("rule_id") == "R_STOLEN_SIGHTING" and r.get("sighting_id") in this_ids]
penal_this_run = [r for r in on_plate
                  if r.get("rule_id") in PENAL and r.get("sighting_id") in this_ids]

# 4. a named officer decides the NEWEST sighting: approve = the authorised
#    basis of a pursuit (evidence, never a fine).  Newest by the read's own
#    time, ties by camera — content, never listing order, so seed-pinned
#    repetition rounds decide the same read.
def read_key(r):
    ev = r.get("evidence") or {}
    return (str(ev.get("t") or ""), str(ev.get("camera_id") or ""))

rec = max(evidence, key=read_key) if evidence else None
approval = None
if rec:
    code, doc = call(f"/api/v1/enforcement/recommendations/{rec['recommendation_id']}/decision",
                     {"decision": "approve", "officer": officer, "note": NOTE})
    approval = doc if code == 200 else refused(code, doc)

# C-N: approving an e-challan on this plate must be REFUSED — 409, nothing
# written, the row stays pending.  Probed on the oldest pending penal row of
# THIS vehicle (a read from before the FIR); a store holding none (a fresh
# install: every read since the FIR is evidence-only) has nothing to probe.
# The approval is SENT only while the vehicle is verifiably reported stolen
# right now — its newest active earmark (GET /api/v1/vehicles) carries the
# lawful basis stolen_vehicle_fir, so the decision endpoint's C-N predicate
# (an active FIR earmark exists) holds: the refusal is the server's, but the
# probe must never be able to land a real e-challan on the victim's car
# should the FIR earmark have lapsed or been cleared.
penal_pending = sorted((r for r in on_plate
                        if r.get("rule_id") in PENAL and str(r.get("vehicle_id")) == vid),
                       key=lambda r: (str(r.get("created_at") or ""), r["recommendation_id"]))
code_v, vlist = call("/api/v1/vehicles")
active = next((v for v in (vlist.get("vehicles") or []) if str(v.get("vehicle_id")) == vid),
              None) if code_v == 200 else None
stolen_now = bool(active) and active.get("lawful_basis") == "stolen_vehicle_fir"
if penal_pending and stolen_now:
    target = penal_pending[0]
    code, doc = call(f"/api/v1/enforcement/recommendations/{target['recommendation_id']}/decision",
                     {"decision": "approve", "officer": officer,
                      "note": "C-N check: an e-challan on a reported-stolen vehicle must be refused"})
    c2, after = call("/api/v1/enforcement/recommendations?status=pending&limit=500")
    probe = {"exercised": True, "recommendation_id": target["recommendation_id"],
             "rule_id": target.get("rule_id"), "http": code,
             "detail": doc.get("detail"), "reason": doc.get("reason"),
             "precondition": {"earmark_state": active.get("earmark_state"),
                              "lawful_basis": active.get("lawful_basis")},
             "still_pending": c2 == 200 and any(
                 r.get("recommendation_id") == target["recommendation_id"]
                 for r in after.get("recommendations", []))}
elif penal_pending:
    probe = {"exercised": False, "unsafe": True,
             "why": "NOT SENT: the vehicle is not verifiably reported stolen right now "
                    f"(GET /api/v1/vehicles HTTP {code_v}, newest active earmark "
                    f"{(active or {}).get('lawful_basis')!r}) — an approval could land as a "
                    "real e-challan on the victim's car"}
else:
    probe = {"exercised": False,
             "why": "no pending e-challan recommendation on the plate in this store "
                    "(every read since the FIR is evidence-only)"}

# 5. the pursuit event (human-initiated; carries vehicle + the approved sighting)
pursuit = pursuit_title = None
if approval and approval.get("status") == "approved":
    pursuit_title = f"PURSUIT — stolen {plate} ({fir})"
    code, doc = call("/api/v1/events", {
        "event_kind": "vehicle_pursuit", "protection_class": "none", "crowd_class": "LOW",
        "title": pursuit_title,
        "description": ("God's-eye evening over Mumbai: a pursuit of a FIR-named stolen "
                        "vehicle (an EMULATED plate and a scenario FIR), authorised by the "
                        "scripted demo officer's approval of a sighting of emulated ANPR reads "
                        "(evidence only — no e-challan for a reported-stolen vehicle). "
                        "Vehicles only (C6); the interception plan assists the operator."),
        # the watchlist sweep's belt: a drivable chain of the Mumbai network
        "route_spines": [{"label": os.environ.get("BELT_TEXT") or "Mumbai sweep belt",
                          "segment_ids": [int(s) for s in os.environ["BELT"].split(",")]}],
        # HON-4: the pursued vehicle exists only in the emulator's ANPR sweep
        # and this script opens the pursuit unattended — the event is
        # EMULATED (the oracle badges metadata.source 'emulated'), never live
        "metadata": {"vehicle_id": vid, "recommendation_id": rec["recommendation_id"],
                     "fir": fir, "opened_by": officer,
                     "source": "emulated", "scripted_by": "scripts/showcase_run.sh",
                     "fir_is_demo": True},
    })
    pursuit = doc if code < 300 else refused(code, doc)

# 6. the interception plan + the live trace (supporting evidence; the plan
#    keys on the LATEST emulated read, which may sit outside the 300 m
#    attribution band — a 422 there is recorded, not fatal)
plan = trace = None
if pursuit and pursuit.get("event_id"):
    code, plan = call(f"/api/v1/events/{pursuit['event_id']}/interception-plan")
    plan = plan if code == 200 else refused(code, plan)
    code, trace = call(f"/api/v1/vehicles/{vid}/trace?window_sec=86400")
    trace = trace if code == 200 else refused(code, trace)

def withheld_of(r):
    """What the penal rules would have proposed for this read — never filed."""
    return [{"rule_id": w.get("rule_id"),
             "speed_kmh": (w.get("evidence") or {}).get("speed_kmh"),
             "speed_limit_kmh": (w.get("evidence") or {}).get("speed_limit_kmh")}
            for w in ((r.get("evidence") or {}).get("withheld_rules") or [])]

print(json.dumps({
    "vehicle_id": vid, "plate": plate,
    "sightings": {"stolen_total": len(stolen), "stolen_this_run": len(this_run),
                  "cameras": sorted({s["camera_id"] for s in this_run}),
                  "speeds_kmh": [s["speed_kmh"] for s in this_run],
                  "source": (this_run[0]["source"] if this_run else None)},
    "recommendation": {"fired_rules": fired,
                       "withheld_rules": withheld,
                       "evidence_recs_this_run": len(evidence),
                       "penal_recs_this_run": len(penal_this_run),
                       "eval_errors": eval_errors,
                       "chosen": {"id": rec["recommendation_id"], "rule_id": rec["rule_id"],
                                  "text": rec["recommendation"],
                                  "camera_id": (rec.get("evidence") or {}).get("camera_id"),
                                  "read_t": (rec.get("evidence") or {}).get("t"),
                                  "withheld": withheld_of(rec)} if rec else None},
    "approval": ({"status": approval.get("status"), "officer": approval.get("decided_by"),
                  "note": NOTE,
                  "audit_tail_last": (approval.get("audit_tail") or [{}])[-1]}
                 if approval and "_http_error" not in approval else approval),
    "penal_approval_probe": probe,
    "pursuit_event": ({"event_id": pursuit.get("event_id"), "kind": "vehicle_pursuit",
                       "status": pursuit.get("status"), "metadata": pursuit.get("metadata") or {},
                       "title": pursuit_title}
                      if pursuit and "_http_error" not in pursuit else pursuit),
    "interception": ({"n_junctions": len(plan.get("interception_junctions", [])),
                      "top": (plan.get("interception_junctions") or [{}])[0],
                      "latest_sighting": plan.get("latest_sighting")}
                     if plan and "_http_error" not in plan
                     else {"unavailable": True,
                           "http": (plan or {}).get("_http_error"),
                           "detail": (plan or {}).get("_detail")}),
    "trace": {"points": len(trace.get("positions", [])),
              "source": trace.get("source"),
              "first": (trace.get("positions") or [{}])[0].get("t"),
              "last": (trace.get("positions") or [{}])[-1].get("t")}
             if trace and "_http_error" not in trace else None,
}, indent=1))
PYEOF

read -r N_STOLEN_THIS N_STOLEN_ALL N_EVIDENCE N_PENAL_RUN FIRED_OK APPROVED PROBE PURSUIT_ID N_INTERCEPT N_TRACE TRACE_SRC < <(python3 -c '
import json, sys
d = json.load(open(sys.argv[1]))
s = d.get("sightings") or {}
rec = d.get("recommendation") or {}
app = d.get("approval") or {}
pr = d.get("penal_approval_probe") or {}
pur = d.get("pursuit_event") or {}
inter = d.get("interception") or {}
tr = d.get("trace") or {}
fired = rec.get("fired_rules") or []
probe = ("unsafe" if pr.get("unsafe") else
         "n/a" if not pr.get("exercised") else
         "refused" if (pr.get("http") == 409
                       and pr.get("detail") == "e-challan withheld — vehicle reported stolen"
                       and pr.get("reason") == "stolen_vehicle_fir"
                       and pr.get("still_pending")) else "NOT-refused")
print(s.get("stolen_this_run", 0), s.get("stolen_total", 0),
      rec.get("evidence_recs_this_run", 0), rec.get("penal_recs_this_run", 0),
      "yes" if fired and set(fired) == {"R_STOLEN_SIGHTING"} else "no",
      1 if app.get("status") == "approved" and app.get("officer") == sys.argv[2] else 0,
      probe, pur.get("event_id") or "-", inter.get("n_junctions", 0),
      tr.get("points", 0), tr.get("source") or "-")' "$CHAIN_JSON" "$OFFICER" 2>/dev/null || echo "0 0 0 0 no 0 NOT-refused - 0 0 -")
[ "$PURSUIT_ID" = "-" ] && PURSUIT_ID=""

[ "$N_STOLEN_THIS" -ge 2 ] \
    && ok "chain[2/6] emulated ANPR cameras sighted the stolen plate: $N_STOLEN_THIS reads this run ($([ "$N_STOLEN_ALL" -gt "$N_STOLEN_THIS" ] && echo "$N_STOLEN_ALL incl. earlier runs" || echo this vehicle only), source $TRACE_SRC)" \
    || fail "chain[2/6] fewer than 2 stolen-plate sightings this run (got $N_STOLEN_THIS)"
WITHHELD_SUMMARY=$(python3 -c '
import collections, json, sys
r = json.load(open(sys.argv[1])).get("recommendation") or {}
c = collections.Counter(r.get("withheld_rules") or [])
print(", ".join(f"{k} x{v}" for k, v in sorted(c.items())) or "none")' "$CHAIN_JSON" 2>/dev/null || echo "?")
if [ "$N_EVIDENCE" -ge 1 ] && [ "$N_PENAL_RUN" = "0" ] && [ "$FIRED_OK" = "yes" ]; then
    ok "chain[3/6] EVIDENCE, NO FINE: $N_EVIDENCE R_STOLEN_SIGHTING recommendation(s) PENDING for this run's reads; the penal rules' e-challans WITHHELD (would have fired: $WITHHELD_SUMMARY); 0 penal recommendations"
else
    fail "chain[3/6] stolen-vehicle reads not evidence-only: $N_EVIDENCE R_STOLEN_SIGHTING + $N_PENAL_RUN penal recommendation(s) this run, rules fired $(python3 -c 'import json,sys;print(sorted(set((json.load(open(sys.argv[1])).get("recommendation") or {}).get("fired_rules") or [])))' "$CHAIN_JSON" 2>/dev/null) (C-N: never a fine for a reported-stolen vehicle)"
fi
[ "$APPROVED" = "1" ] \
    && ok "chain[4/6] OFFICER APPROVAL of the newest sighting: pursuit authorised on a reported-stolen vehicle (evidence, no fine) — approved by \"$OFFICER\"" \
    || fail "chain[4/6] the pursuit authorisation did not land (see approval in $CHAIN_JSON)"
case "$PROBE" in
    refused) ok "C-N: an e-challan approval on $STOLEN_PLATE is REFUSED — 409 'e-challan withheld — vehicle reported stolen' (the pending $(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["penal_approval_probe"]["rule_id"])' "$CHAIN_JSON" 2>/dev/null) row stays pending; nothing written)" ;;
    n/a) log "C-N: no pending e-challan on $STOLEN_PLATE in this store to probe (every read since the FIR is evidence-only) — the 409 refusal is not exercised here" ;;
    unsafe) fail "C-N: the e-challan approval probe was NOT sent — $STOLEN_PLATE is not verifiably reported stolen right now (see penal_approval_probe.why in $CHAIN_JSON); a probe must never be able to land a fine" ;;
    *) fail "C-N: approving an e-challan on $STOLEN_PLATE was NOT refused as withheld (see penal_approval_probe in $CHAIN_JSON)" ;;
esac
[ -n "$PURSUIT_ID" ] \
    && ok "chain[5/6] PURSUIT EVENT opened by the operator: $PURSUIT_ID (vehicle_pursuit, carries vehicle_id + the approved sighting's recommendation_id)" \
    || fail "chain[5/6] pursuit event not created (see pursuit_event in $CHAIN_JSON)"

# enrich the artifact with the PERSISTED pursuit metadata: the POST
# response echoes metadata as {} — the authoritative copy lives in
# events.corridor_events. Merge it so a cold auditor reads vehicle_id +
# recommendation_id + FIR in-band in pursuit_chain.json.
if is_uuid "$PURSUIT_ID"; then
    PURSUIT_META=$($PSQL -c "SELECT metadata::text FROM events.corridor_events WHERE event_id='$PURSUIT_ID'" 2>/dev/null || true)
    if [ -n "$PURSUIT_META" ]; then
        PURSUIT_META="$PURSUIT_META" CHAIN_JSON="$CHAIN_JSON" python3 - <<'PYEOF'
import json, os
p = os.environ["CHAIN_JSON"]
d = json.load(open(p))
pe = d.get("pursuit_event")
if pe:
    pe["metadata"] = json.loads(os.environ["PURSUIT_META"])
    pe["metadata_source"] = ("events.corridor_events (persisted row merged; "
                             "the POST response echoes metadata as {})")
    json.dump(d, open(p, "w"), indent=1)
PYEOF
        ok "pursuit metadata persisted and merged into the artifact: $(python3 -c 'import json,sys;m=(json.load(open(sys.argv[1]))["pursuit_event"] or {}).get("metadata") or {};print(sorted(m))' "$CHAIN_JSON" 2>/dev/null || echo '?')"
    else
        log "pursuit metadata query returned nothing — artifact keeps the POST echo"
    fi
fi
N_INTERCEPT_AVAIL=$(python3 -c 'import json,sys;d=json.load(open(sys.argv[1]));i=d.get("interception") or {};print("no" if i.get("unavailable") else "yes")' "$CHAIN_JSON" 2>/dev/null || echo no)
if [ "$N_INTERCEPT_AVAIL" = "yes" ] && [ "$N_INTERCEPT" -ge 1 ]; then
    ok "support: interception plan ranks $N_INTERCEPT choke junctions (top: junction $(python3 -c 'import json,sys;d=json.load(open(sys.argv[1]));t=d["interception"]["top"];print(t.get("junction_id"),t.get("junction_type"),"score",t.get("score"))' "$CHAIN_JSON" 2>/dev/null))"
else
    log "support: interception plan unavailable this seed — $(python3 -c 'import json,sys;d=json.load(open(sys.argv[1]));print(str((d.get("interception") or {}).get("detail") or "")[:120])' "$CHAIN_JSON" 2>/dev/null) (the emulated camera's latest read sits outside the 300 m attribution band; recorded, not asserted)"
fi
[ "$N_TRACE" -ge 2 ] && [ "$TRACE_SRC" = "emulated_anpr" ] \
    && ok "chain[6b] LIVE TRACE on the canvas layer: $N_TRACE timed positions (source $TRACE_SRC) — GET /api/v1/vehicles/{id}/trace feeds the vehicle-traces layer" \
    || fail "chain[6b] trace not usable by the canvas (points=$N_TRACE source=$TRACE_SRC)"

PURSUIT_TITLE=$(python3 -c 'import json,sys;d=json.load(open(sys.argv[1]));print((d.get("pursuit_event") or {}).get("title") or "PURSUIT")' "$CHAIN_JSON" 2>/dev/null || echo "PURSUIT")
APPROVED_REC_ID=$(python3 -c 'import json,sys;d=json.load(open(sys.argv[1]));print(((d.get("recommendation") or {}).get("chosen") or {}).get("id") or "")' "$CHAIN_JSON" 2>/dev/null || echo "")

# ════════════════════════════════════════════════════════════════════════════
# 6b. THE VIP MOVEMENT — Mantralaya -> Mumbai Airport T2, PLANNED ONLY
#     convoy-brain's pre-movement workflow (POST /movements/{id}/plan): ranked
#     routes on the Mumbai network, the decider's pick, and the plan
#     registered as a corridor event in 'planning'. Nothing is launched: no
#     escort, no approval. The scripted plan is closed when the run ends
#     (phase 8c), so it never holds a band for the situation engine.
# ════════════════════════════════════════════════════════════════════════════
log "phase 6b: VIP movement Mantralaya -> Mumbai Airport T2 — planned only (no escort, no approval)"
VIP_JSON="$SHOWCASE_DIR/vip_plan.json"
VIP_MOVEMENT_ID=$(python3 -c 'import uuid; print(uuid.uuid4())')
BRAIN="$BRAIN_URL" MID="$VIP_MOVEMENT_ID" ORIGIN="$VIP_ORIGIN" DEST="$VIP_DESTINATION" python3 - > "$VIP_JSON" <<'PYEOF'
import json, os, urllib.error, urllib.request
from datetime import datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))
origin = [float(x) for x in os.environ["ORIGIN"].split(",")]
dest = [float(x) for x in os.environ["DEST"].split(",")]
departure = (datetime.now(IST) + timedelta(hours=2)).replace(second=0, microsecond=0)
body = {"origin": origin, "destination": dest, "vvip_class": "Z",
        "planned_departure": departure.isoformat()}
req = urllib.request.Request(f"{os.environ['BRAIN']}/movements/{os.environ['MID']}/plan",
                             data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
try:
    with urllib.request.urlopen(req, timeout=240) as r:
        code, doc = r.status, json.loads(r.read())
except urllib.error.HTTPError as e:
    code, doc = e.code, {"detail": e.read().decode("utf-8", "replace")[:400]}
except (OSError, ValueError) as e:
    code, doc = 0, {"detail": f"{type(e).__name__}: {e}"[:400]}

def route(r):
    if not isinstance(r, dict):
        return None
    return {k: r.get(k) for k in ("route_id", "segment_ids", "eta_seconds", "eta_sec", "distance_m",
                                  "length_m", "score", "road_names") if r.get(k) is not None}

prim = doc.get("primary_route") if isinstance(doc, dict) else None
print(json.dumps({
    "http": code, "movement_id": os.environ["MID"],
    "from": "Mantralaya (junction 1)", "to": "Mumbai Airport T2, departure forecourt (junction 49)",
    "request": body,
    "status": doc.get("status"), "event_id": doc.get("event_id"),
    "routing_tier": doc.get("routing_tier"), "confidence": doc.get("confidence"),
    "primary_route": route(prim),
    "alternates": len(doc.get("alternate_routes") or []),
    "decider_pick": doc.get("decider_pick"),
    "overall_reasoning": (doc.get("overall_reasoning") or "")[:400] or None,
    "detail": None if code == 200 else doc.get("detail"),
    "note": "planned only: no escort launched, no approval made; traffic in the plan is SIMULATED",
}, indent=1, ensure_ascii=False))
PYEOF
VIP_STATUS=$(jget "$VIP_JSON" status)
VIP_EVENT_ID=$(jget "$VIP_JSON" event_id)
is_uuid "$VIP_EVENT_ID" || VIP_EVENT_ID=""
VIP_SEGS=$(python3 -c 'import json,sys; r=(json.load(open(sys.argv[1])).get("primary_route") or {}); print(len(r.get("segment_ids") or []))' "$VIP_JSON" 2>/dev/null || echo 0)
VIP_ALTS=$(jget "$VIP_JSON" alternates)
if [ "$(jget "$VIP_JSON" http)" = "200" ] && [ -n "$VIP_STATUS" ] && [ "$VIP_STATUS" != "no_route" ] && [ "${VIP_SEGS:-0}" -ge 1 ]; then
    ok "VIP movement planned (not launched): Mantralaya -> Mumbai Airport T2, plan '$VIP_STATUS', primary route $VIP_SEGS segments + ${VIP_ALTS:-0} alternate(s), corridor event ${VIP_EVENT_ID:-not registered} in planning"
else
    fail "VIP movement plan Mantralaya -> Mumbai Airport T2 failed: HTTP $(jget "$VIP_JSON" http) status '${VIP_STATUS:-?}' ($(jget "$VIP_JSON" detail | cut -c1-160))"
fi

# ════════════════════════════════════════════════════════════════════════════
# 7. THE EVIDENCE — pursuit-trace + citizen-advisory canvas shots
# ════════════════════════════════════════════════════════════════════════════
log "phase 7: pursuit-trace + citizen-advisory canvas shots"
if [ -n "$CHROME_BIN" ] && [ -x "$CHROME_BIN" ]; then
    if ( cd "$SAJAG_ROOT/frontend" && NODE_PATH="$SAJAG_ROOT/frontend/node_modules" \
         node "$CANVAS_SHOTS" --rest-only \
              "$DECK_ORIGIN" "$SHOWCASE_DIR" "$PURSUIT_TITLE" ) \
         > "$SHOWCASE_DIR/shots_rest.log" 2>&1; then
        ok "canvas shots: showcase_pursuit_trace.png + showcase_citizen_advisory.png proven non-blank (the public /citizen page shows no pursuit, no plate)"
        REST_SHOTS_OK=true
    else
        bad "pursuit/citizen canvas capture failed (details: $SHOWCASE_DIR/shots_rest.log)"
        fail "pursuit/citizen canvas shots failed"
        REST_SHOTS_OK=false
    fi
else
    REST_SHOTS_OK=false
    fail "chrome binary missing — pursuit/citizen shots impossible"
fi

# ════════════════════════════════════════════════════════════════════════════
# 8. THE LEDGER — audit-log assertions (the real stack did the work)
# ════════════════════════════════════════════════════════════════════════════
log "phase 8: audit-log assertions"

# 8b. the evening eases — read from the audit log, no sleep, no observe
#     train: the flagship's event closed with its run (phase 4f) and the
#     situation engine drops a closed event at its next tick (retain_only:
#     a completed event never holds the city band), so every band change of
#     the evening is already a transitioned row of adaptive.situation_log.
log "phase 8b: the evening eases — the band's transitions from adaptive.situation_log; the closed event released"
CALM_JSON="$SHOWCASE_DIR/band_easing.json"
$PSQL -c "SELECT COALESCE(json_agg(json_build_object('n', n, 'previous_class', previous_class, 'effective_class', situation_class, 'observed_class', observed_class, 'situation_code', situation_code, 'transitioned', transitioned, 'observed_at', observed_at) ORDER BY n), '[]'::json) FROM (SELECT row_number() OVER w AS n, lag(situation_class) OVER w AS previous_class, situation_class, observed_class, situation_code, transitioned, observed_at FROM adaptive.situation_log WHERE movement_id='$FLAG_EVENT_ID' WINDOW w AS (ORDER BY observed_at, log_id)) t WHERE transitioned" \
    > "$CALM_JSON" 2>/dev/null || echo '[]' > "$CALM_JSON"
python3 -c 'import json,sys; json.load(open(sys.argv[1]))' "$CALM_JSON" 2>/dev/null || echo '[]' > "$CALM_JSON"
TRANSITIONS=$(python3 -c '
import json, sys
print(", ".join("%s->%s" % (t.get("previous_class"), t.get("effective_class")) for t in json.load(open(sys.argv[1]))) or "none")' "$CALM_JSON" 2>/dev/null || echo "?")
read -r RELEASED CITY_BAND_AFTER < <(health "$ORACLE_URL/api/v1/adaptive/status" 15 | python3 -c '
import json, sys
d = json.load(sys.stdin)
band = d.get("city_band")
band = band.get("band") if isinstance(band, dict) else band
print("no" if sys.argv[1] in (d.get("movements") or {}) else "yes", band or "-")' "$FLAG_EVENT_ID" 2>/dev/null || echo "unknown -")
log "band transitions of the evening: $TRANSITIONS; flagship released by the engine after its event closed: $RELEASED (city band now $CITY_BAND_AFTER)"

# the flagship is a fresh subject (run-scoped id): every row naming it is
# this run's — uncapped SQL counts
n_situation=$($PSQL -c "SELECT count(*) FROM adaptive.situation_log WHERE movement_id='$FLAG_EVENT_ID'")
n_transitions=$($PSQL -c "SELECT count(*) FROM adaptive.situation_log WHERE movement_id='$FLAG_EVENT_ID' AND transitioned")
n_params=$($PSQL -c "SELECT count(*) FROM adaptive.param_overrides WHERE movement_id='$FLAG_EVENT_ID'")
n_amb=$($PSQL -c "SELECT count(*) FROM adaptive.param_overrides WHERE movement_id='$FLAG_EVENT_ID' AND evidence::text LIKE '%AMBULANCE_DELAY%'")
bands_csv=$($PSQL -c "SELECT situation_class||':'||count(*) FROM adaptive.situation_log WHERE movement_id='$FLAG_EVENT_ID' GROUP BY situation_class ORDER BY situation_class" | paste -sd,)
d_situation=${n_situation:-0}
d_params=${n_params:-0}
d_trans=${n_transitions:-0}
d_amb=${n_amb:-0}
log "audit: situation_log rows $d_situation bands[$bands_csv] transitions $d_trans"
log "audit: param_overrides rows $d_params; AMBULANCE_DELAY escalations $d_amb"

[ "$d_situation" -ge 1 ] && [ "$d_params" -ge 1 ] \
    && ok "audit log carries THIS run's decisions: $d_situation situation rows + $d_params parameter rows for the flagship event" \
    || fail "audit log missing this run's decisions (situation rows=$d_situation params rows=$d_params)"
[ "$d_trans" -ge 1 ] \
    && ok "situation band TRANSITIONED mid-evening: $d_trans transitioned rows ($TRANSITIONS; bands this run: $bands_csv)" \
    || fail "no band transition recorded for the flagship (transitioned rows=$d_trans)"
[ "$d_amb" -ge 1 ] \
    && ok "ambulance escalation in the audit log: $d_amb AMBULANCE_DELAY parameter decisions" \
    || fail "no AMBULANCE_DELAY escalation row this run (rows=$d_amb)"

# events table: the flagship is a tier-'none' public gathering (the visarjan crowds), regulated
ev_kind=$($PSQL -c "SELECT event_kind FROM events.corridor_events WHERE event_id='$FLAG_EVENT_ID'")
ev_prot=$($PSQL -c "SELECT protection_class FROM events.corridor_events WHERE event_id='$FLAG_EVENT_ID'")
n_phases=$($PSQL -c "SELECT count(*) FROM events.event_phases WHERE event_id='$FLAG_EVENT_ID'")
phase_policy=$($PSQL -c "SELECT closure_policy::text FROM events.event_phases WHERE event_id='$FLAG_EVENT_ID' LIMIT 1")
[ "$ev_kind" = "$FLAG_KIND" ] && [ "$ev_prot" = "none" ] \
    && ok "events table: the visarjan night is a PUBLIC gathering (kind=$ev_kind, protection_class=none, $n_phases phases)" \
    || fail "events table row wrong (kind=$ev_kind protection=$ev_prot)"
printf '%s' "$phase_policy" | grep -q "$FLAG_CLOSURE" \
    && ok "the engine's answer on the phase row: $phase_policy (the library's $FLAG_CLOSURE)" \
    || fail "phase closure_policy is not $FLAG_CLOSURE (got: $phase_policy)"

# the crime-incident event from the sweep must exist (the sweep's corridor
# op; its id is the one the sweep's run document names)
sweep_kind=""
[ -n "$SWEEP_EVENT_ID" ] && sweep_kind=$($PSQL -c "SELECT event_kind FROM events.corridor_events WHERE event_id='$SWEEP_EVENT_ID'")
[ "$sweep_kind" = "crime_incident" ] \
    && ok "sweep corridor event present: crime_incident $SWEEP_EVENT_ID (the FIR-driven sweep's own operation)" \
    || fail "sweep crime_incident event not found (event ${SWEEP_EVENT_ID:-?}, kind=${sweep_kind:-none})"

# the cloudburst's own corridor event (its run closed it with the run)
rain_row=""
[ -n "$RAIN_EVENT_ID" ] && rain_row=$($PSQL -c "SELECT event_kind||' '||status FROM events.corridor_events WHERE event_id='$RAIN_EVENT_ID'")
RAIN_KIND="${rain_row%% *}"
[ -n "$rain_row" ] \
    && ok "cloudburst corridor event present: $RAIN_EVENT_ID ($rain_row — the SIMULATED storm's own operation, closed with its run)" \
    || fail "cloudburst corridor event not found (event ${RAIN_EVENT_ID:-?})"

# 8c. the scripted pursuit is CLOSED: a pursuit an unattended script opened
#     must not stay open on /ops, nor hold a band for the situation engine
#     (it tracks every planning/approved/active event) — C-F planning ->
#     cancelled under the scripted officer label; the phase-7 shots and
#     the artifacts already carry it
PURSUIT_CLOSED=false
if is_uuid "$PURSUIT_ID"; then
    close_resp=$(curl -s --max-time 30 -X POST "$ORACLE_URL/api/v1/events/$PURSUIT_ID/status" \
        -H 'Content-Type: application/json' \
        -d "{\"to_status\":\"cancelled\",\"officer\":\"$OFFICER\",\"note\":\"showcase run complete: the scripted pursuit is closed (no unit was tasked)\"}" 2>/dev/null)
    if [ "$(printf '%s' "$close_resp" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("to_status"))' 2>/dev/null)" = "cancelled" ]; then
        PURSUIT_CLOSED=true
        ok "the scripted pursuit $PURSUIT_ID is closed: planning -> cancelled by \"$OFFICER\" (C-F) — nothing scripted stays open"
    else
        fail "the scripted pursuit $PURSUIT_ID could not be closed (C-F answer: ${close_resp:0:200})"
    fi
fi

# ... and the scripted VIP plan: planned only, so it is closed the same way
#     (C-F planning -> cancelled) — the plan document stays on record
VIP_CLOSED=false
if is_uuid "$VIP_EVENT_ID"; then
    close_resp=$(curl -s --max-time 30 -X POST "$ORACLE_URL/api/v1/events/$VIP_EVENT_ID/status" \
        -H 'Content-Type: application/json' \
        -d "{\"to_status\":\"cancelled\",\"officer\":\"$OFFICER\",\"note\":\"showcase run complete: the VIP movement was planned only (Mantralaya to Mumbai Airport T2); nothing was launched\"}" 2>/dev/null)
    if [ "$(printf '%s' "$close_resp" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("to_status"))' 2>/dev/null)" = "cancelled" ]; then
        VIP_CLOSED=true
        ok "the scripted VIP plan $VIP_EVENT_ID is closed: planning -> cancelled by \"$OFFICER\" (C-F) — planned only, never launched"
    else
        fail "the scripted VIP plan $VIP_EVENT_ID could not be closed (C-F answer: ${close_resp:0:200})"
    fi
fi

# reversible state: nothing was committed, but restore is still exercised
curl -s -X POST "$ORACLE_URL/api/v1/signals/restore" -H 'Content-Type: application/json' \
    -d "{\"event_id\":\"$FLAG_EVENT_ID\",\"officer\":\"$OFFICER\"}" > "$SHOWCASE_DIR/signals_restore.json" 2>/dev/null || true

# 8d. leave the oracle as found: when phase 1b switched the signal-policy
#     writer on for this run, the oracle goes back to its pre-run value now
#     (the exit trap retries on any other way out)
if [ -n "$WRITER_RECREATED" ]; then
    restore_writer \
        || fail "traffic-oracle's signal-policy writer not restored to its pre-run value '${WRITER_ORIG_ENV}' (it may still be ON)"
fi

# ════════════════════════════════════════════════════════════════════════════
# 9. THE RECORD — showcase_results.json + exit code
# ════════════════════════════════════════════════════════════════════════════
NOW_UTC=$(date -u +%Y-%m-%dT%H:%M:%SZ)
FLAG_EVENT_ID="$FLAG_EVENT_ID" SWEEP_EVENT_ID="$SWEEP_EVENT_ID" SWEEP_SEED="$SWEEP_SEED" \
FLAG_RUN_ID="$FLAG_RUN_ID" FLAG_STATUS="$FLAG_STATUS" FLAG_DELIVERY="$FLAG_DELIVERY" \
SWEEP_RUN_ID="$SWEEP_RUN_ID" SWEEP_STATUS="$SWEEP_STATUS" SWEEP_DELIVERED="$SWEEP_DELIVERED" \
PURSUIT_ID="$PURSUIT_ID" APPROVED_REC_ID="$APPROVED_REC_ID" JR_DISPATCH_ID="$JR_DISPATCH_ID" \
VEHICLE_ID="$VEHICLE_ID" STOLEN_PLATE="$STOLEN_PLATE" FIR_REF="$FIR_REF" OFFICER="$OFFICER" \
D_SITUATION="$d_situation" D_PARAMS="$d_params" D_TRANSITIONS="$d_trans" D_AMB="$d_amb" \
BANDS_CSV="$bands_csv" GC_WINDOWS="$GC_WINDOWS" EV_KIND="$ev_kind" EV_PROT="$ev_prot" \
N_PHASES="$n_phases" PHASE_POLICY="${phase_policy:-{\}}" SWEEP_KIND="$sweep_kind" \
RELEASED="$RELEASED" CITY_BAND_AFTER="$CITY_BAND_AFTER" \
SIGNAL_PLAN_SHIFTS="$SIGNAL_PLAN_SHIFTS" SIGNAL_REFUSALS="$SIGNAL_REFUSALS" SIGNAL_MAE="$SIGNAL_MAE" \
REPLAY_SUMMARY="$REPLAY_SUMMARY" ACTIVE_FEED_SEEN="$ACTIVE_FEED_SEEN" CIVIC="$CIVIC_DISPATCHED" SPILL_JUNCTION="$SPILL_JUNCTION" \
RAIN_RUN_ID="$RAIN_RUN_ID" RAIN_STATUS="$RAIN_STATUS" RAIN_DELIVERED="$RAIN_DELIVERED" RAIN_EVENT_ID="$RAIN_EVENT_ID" \
RAIN_FEED_SEEN="$RAIN_FEED_SEEN" RAIN_ROW="$rain_row" TWIN_PROPS="$TWIN_PROPS" \
VIP_EVENT_ID="$VIP_EVENT_ID" VIP_MOVEMENT_ID="$VIP_MOVEMENT_ID" VIP_CLOSED="$VIP_CLOSED" \
AMBULANCE_ROUTE_TEXT="$AMBULANCE_ROUTE_TEXT" WATER_TEXT="$WATER_TEXT" SPILL_TEXT="$SPILL_TEXT" \
CITY_SHOT_OK="$CITY_SHOT_OK" REST_SHOTS_OK="$REST_SHOTS_OK" SHOWCASE_DIR="$SHOWCASE_DIR" \
STACK_ORACLE="$ORACLE_URL" STACK_EMULATOR="$EMULATOR_URL" STACK_DECK="$DECK_ORIGIN" \
STACK_PROJECT="$COMPOSE_PROJECT" STACK_PG="$PG_CONTAINER" \
PURSUIT_TITLE="$PURSUIT_TITLE" PURSUIT_CLOSED="$PURSUIT_CLOSED" NOW_UTC="$NOW_UTC" \
WRITER_RECREATED="$WRITER_RECREATED" WRITER_ORIG_ENV="$WRITER_ORIG_ENV" WRITER_RESTORED="$WRITER_RESTORED" \
FAILED_ASSERTS="$(printf '%s\n' ${FAILED_ASSERTS[@]+"${FAILED_ASSERTS[@]}"} | paste -sd$'\x1f' -)" \
python3 - "$RESULTS_JSON" <<'PYEOF'
import json, os, sys

def load_env_json(name, default):
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return json.loads(raw)
    except Exception:
        return default

def load_file_json(relpath, default):
    p = os.path.join(os.environ["SHOWCASE_DIR"], relpath)
    try:
        return json.load(open(p))
    except Exception:
        return default

def as_int(name):
    try:
        return int(os.environ.get(name) or 0)
    except ValueError:
        return 0

S = os.environ["SHOWCASE_DIR"]
earmark = load_file_json("chain_earmark.json", {})
chain = load_file_json("pursuit_chain.json", {})
jr = load_file_json("civic_volunteers.json", {})
hydro = load_file_json("hydro_waterlogging.json", {})
twinp = load_file_json("twin_proposal.json", {})
vip = load_file_json("vip_plan.json", {})
sig = load_file_json("signal_policy.json", {})
twin = load_file_json("twin_audit.json", {})
observe = load_file_json("ambulance_observe.json", [])
transitions = load_file_json("band_easing.json", [])
failed = [a for a in os.environ.get("FAILED_ASSERTS", "").split("\x1f") if a]

sight = chain.get("sightings") or {}
rec = chain.get("recommendation") or {}
app = chain.get("approval") or {}
probe = chain.get("penal_approval_probe") or {}
pur = chain.get("pursuit_event") or {}
inter = chain.get("interception") or {}
tr = chain.get("trace") or {}

pursuit_chain = [
    {"step": 1, "name": "plate_earmarked",
     "detail": f"{os.environ['STOLEN_PLATE']} flagged ({earmark.get('lawful_basis')}, "
               f"{os.environ['FIR_REF']}); earmark_id {earmark.get('earmark_id')}",
     "evidence": f"POST /api/v1/vehicles/{os.environ['STOLEN_PLATE']}/earmark"},
    {"step": 2, "name": "anpr_camera_sightings",
     "detail": f"{sight.get('stolen_this_run')} emulated reads this run on cameras "
               f"{sight.get('cameras')} at {sight.get('speeds_kmh')} km/h "
               f"(matched_plate_hit=stolen_vehicle, source={sight.get('source')})",
     "evidence": f"GET /api/v1/vehicles/{os.environ['VEHICLE_ID']}/sightings"},
    {"step": 3, "name": "stolen_sighting_evidence",
     "detail": f"{rec.get('evidence_recs_this_run')} R_STOLEN_SIGHTING (evidence only) for this "
               f"run's reads; e-challan withheld (penal rules that would have fired: "
               f"{sorted(set(rec.get('withheld_rules') or []))}); "
               f"{rec.get('penal_recs_this_run')} penal recommendations; "
               f"chosen: {(rec.get('chosen') or {}).get('text')}",
     "evidence": f"POST /api/v1/enforcement/evaluate x{sight.get('stolen_this_run')} -> "
                 f"recommendation {(rec.get('chosen') or {}).get('id')} PENDING"},
    {"step": 4, "name": "officer_pursuit_authorisation",
     "detail": f"{app.get('status')} by {app.get('officer')} — '{app.get('note')}'; "
               + (f"an e-challan approval on the plate is refused: HTTP {probe.get('http')} "
                  f"'{probe.get('detail')}'" if probe.get("exercised")
                  else f"e-challan approval probe {probe.get('why')}" if probe.get("unsafe")
                  else "no pending e-challan on the plate to probe in this store"),
     "evidence": "POST /api/v1/enforcement/recommendations/{id}/decision (audit tail append-only; "
                 "a penal approval on a reported-stolen vehicle → 409)"},
    {"step": 5, "name": "pursuit_event",
     "detail": f"{pur.get('title')} [{pur.get('status')}; "
               + ("closed when the run ended: cancelled by the scripted officer]"
                  if os.environ["PURSUIT_CLOSED"] == "true" else "NOT closed]"),
     "evidence": f"POST /api/v1/events vehicle_pursuit {pur.get('event_id')} "
                 f"(metadata vehicle_id+recommendation_id)"},
    {"step": 6, "name": "interception_and_live_trace",
     "detail": (f"{inter.get('n_junctions')} choke junctions ranked (top "
                f"{((inter.get('top') or {}).get('junction_id'))}); trace {tr.get('points')} "
                f"positions source={tr.get('source')}"
                if not inter.get("unavailable") else
                f"interception plan unavailable ({str(inter.get('detail') or '')[:90]}); "
                f"trace {tr.get('points')} positions source={tr.get('source')}"),
     "evidence": f"GET /api/v1/events/{pur.get('event_id')}/interception-plan + "
                 f"GET /api/v1/vehicles/{os.environ['VEHICLE_ID']}/trace (canvas vehicle-traces layer)"},
]

decisions_logged = as_int("D_SITUATION") + as_int("D_PARAMS")

summary = {
  "flagship": {
    "name": "God's-eye evening over Mumbai",
    "story": "Anant Chaturdashi visarjan night (Lalbaug to Girgaon Chowpatty) + a monsoon burst at "
             "high tide + a stolen vehicle reported, one evening, one live stack — waterlogging at "
             "Hindmata with the hydro proposals, the ambulance (108) green corridor through the procession, the "
             "pursuit chain (evidence, never a fine), the Civic Volunteers dispatch, the city "
             "signal-policy guard and a VIP movement Mantralaya -> Mumbai Airport T2 planned only, "
             "end to end. Every scenario SIMULATED, every feed stand-in EMULATED.",
    "composition_use_cases": [
        {"use_case_id": "ganesh_visarjan_girgaon", "run_id": as_int("FLAG_RUN_ID"),
         "status": os.environ["FLAG_STATUS"],
         "delivery": load_env_json("FLAG_DELIVERY", {}),
         "event_id": os.environ["FLAG_EVENT_ID"]},
        {"use_case_id": "cloudburst_high_tide", "run_id": as_int("RAIN_RUN_ID"),
         "status": os.environ["RAIN_STATUS"],
         "delivery": {"delivered": as_int("RAIN_DELIVERED")},
         "event_id": os.environ["RAIN_EVENT_ID"] or None},
        {"use_case_id": "watchlist_anpr_sweep", "seed": as_int("SWEEP_SEED"),
         "run_id": as_int("SWEEP_RUN_ID"), "status": os.environ["SWEEP_STATUS"],
         "delivery": {"delivered": as_int("SWEEP_DELIVERED")},
         "event_id": os.environ["SWEEP_EVENT_ID"] or None},
    ],
    "ambulance_route": os.environ["AMBULANCE_ROUTE_TEXT"],
    "closure_policy": load_env_json("PHASE_POLICY", None),
  },
  "run_scoped_ids": {
    "flagship_run_id": as_int("FLAG_RUN_ID"),
    "flagship_event_id": os.environ["FLAG_EVENT_ID"],
    "cloudburst_run_id": as_int("RAIN_RUN_ID"),
    "cloudburst_event_id": os.environ["RAIN_EVENT_ID"] or None,
    "sweep_run_id": as_int("SWEEP_RUN_ID"),
    "sweep_event_id": os.environ["SWEEP_EVENT_ID"] or None,
    "pursuit_event_id": os.environ["PURSUIT_ID"] or None,
    "pursuit_authorising_recommendation_id": os.environ["APPROVED_REC_ID"] or None,
    "civic_volunteers_dispatch_id": os.environ["JR_DISPATCH_ID"] or None,
    "vip_movement_id": os.environ["VIP_MOVEMENT_ID"] or None,
    "vip_plan_event_id": os.environ["VIP_EVENT_ID"] or None,
    "vehicle_id": os.environ["VEHICLE_ID"] or None,
  },
  "scripted_pursuit_closed": os.environ["PURSUIT_CLOSED"] == "true",
  "scripted_vip_plan_closed": os.environ["VIP_CLOSED"] == "true",
  "approvals": {
    "officer": os.environ["OFFICER"],
    "note": "this script runs unattended: the two approvals it makes (the Civic Volunteers "
            "dispatch, the sighting that authorises the pursuit) are recorded under this "
            "officer label; in a live demo a signed-in human approves on /ops "
            "(scripts/demo_reset.sh stops at PENDING)",
  },
  "signal_policy_writer": {
    "recreated_for_this_run": os.environ["WRITER_RECREATED"] == "1",
    "pre_run_value": os.environ["WRITER_ORIG_ENV"] if os.environ["WRITER_RECREATED"] == "1" else None,
    "restored_to_pre_run_value": (os.environ["WRITER_RESTORED"] == "true"
                                  if os.environ["WRITER_RECREATED"] == "1" else None),
    "note": ("already on before the run (left as found)"
             if os.environ["WRITER_RECREATED"] != "1" else
             "the C7 writer was switched on for this run only; phase 8d recreated the oracle "
             "with its pre-run value (verified: writer_enabled False, /health 200)"
             if os.environ["WRITER_RESTORED"] == "true" else
             "the C7 writer was switched on for this run only and could NOT be put back to its "
             "pre-run value (see the run log's FIX) — the exit trap retries once"),
  },
  "stack": {"oracle": os.environ["STACK_ORACLE"], "emulator": os.environ["STACK_EMULATOR"],
            "deck": os.environ["STACK_DECK"], "compose_project": os.environ["STACK_PROJECT"],
            "postgis_container": os.environ["STACK_PG"]},
  "event_types": [
      "mass_gathering", "visarjan_crowd_spill", "heavy_vehicle_restriction", "cloudburst_high_tide",
      "waterlogging", "hydro_proposals", "ambulance_green_corridor", "stolen_vehicle_report",
      "anpr_sweep", "crime_incident", "stolen_sighting_evidence", "officer_approval",
      "vehicle_pursuit", "interception_plan", "civic_volunteers_dispatch",
      "signal_band_plan_guard", "signal_timing_twin_proposal", "vip_movement_plan",
  ],
  "pursuit_chain": pursuit_chain,
  "stolen_vehicle_rule": {
    "rule": "C-N: a reported-stolen vehicle's reads are evidence only — no e-challan for the "
            "registered owner; approving a penal recommendation on it is refused (409)",
    "evidence_recs_this_run": rec.get("evidence_recs_this_run"),
    "penal_recs_this_run": rec.get("penal_recs_this_run"),
    "withheld_rules": rec.get("withheld_rules"),
    "penal_approval_probe": probe,
  },
  "counts": {
    "decisions_logged_audit_rows_this_run": decisions_logged,
    "situation_log_rows_this_run": as_int("D_SITUATION"),
    "param_override_rows_this_run": as_int("D_PARAMS"),
    "band_transitions_total": as_int("D_TRANSITIONS"),
    "band_transitions_this_run": as_int("D_TRANSITIONS"),
    "bands": os.environ["BANDS_CSV"],
    "green_corridor_windows": as_int("GC_WINDOWS"),
    "ambulance_delay_escalations_this_run": as_int("D_AMB"),
    "signal_plan_shifts_committed": as_int("SIGNAL_PLAN_SHIFTS"),
    "signal_policy_refusals": as_int("SIGNAL_REFUSALS"),
    "twin_timing_proposals": as_int("TWIN_PROPS"),
    "hydro_live_proposals": ((hydro.get("live_nowcast") or {}).get("proposals")),
    "hydro_hindsight_proposals": ((hydro.get("hindsight_replay_2025_08_19") or {}).get("proposal_counts")),
  },
  "waterlogging": {
    "segment": os.environ.get("WATER_TEXT"),
    "cloudburst_twin": hydro.get("twin_simulated"),
    "live_nowcast": hydro.get("live_nowcast"),
    "hindsight_replay_2025_08_19": hydro.get("hindsight_replay_2025_08_19"),
    "note": "three sources, never blended: the SIMULATED monsoon burst through the twin (MODELLED), "
            "the LIVE Open-Meteo nowcast (a dry night proposes nothing), and the 18–19 Aug 2025 "
            "storm replay (HINDSIGHT, MODELLED). Every proposal waits for a named officer.",
  },
  "signal_timing_twin": twinp,
  "vip_movement": {
    "plan": vip,
    "closed_after_run": os.environ["VIP_CLOSED"] == "true",
    "note": "planned only: no escort launched, no approval made",
  },
  "signal_policy_guard": {
    "ruling": "guard-fired + fully-auditable decision = PASS for the band->plan element; "
              "signal_plan_shifts counts COMMITTED writes only",
    "twin_calibration_replay": sig.get("replay"),
    "city_band_live": sig.get("city_band_live"),
    "operator_apply": sig.get("apply"),
    "last_plan_auditable": sig.get("last_plan_auditable"),
    "refusal_reason": (sig.get("apply") or {}).get("reason")
        and f"{(sig.get('apply') or {}).get('reason')}: {(sig.get('apply') or {}).get('shadow_eval', {}).get('detail')} "
            f"({os.environ['REPLAY_SUMMARY']}; the twin calibrates on REAL field observations only)",
  },
  "civic_volunteers": {
    "dispatched": os.environ["CIVIC"] == "true",
    "agency_code": jr.get("agency"), "agency_label": jr.get("agency_label"),
    "unit": jr.get("unit_id"), "waypoint_junction": as_int("SPILL_JUNCTION"),
    "spillover": os.environ.get("SPILL_TEXT"),
    "statuses": jr.get("statuses"), "audit": jr.get("audit"),
    "projected_unit": jr.get("projected_unit"),
  },
  "ambulance_green_corridor": {
    "escalation_decisions": observe if isinstance(observe, list) else [],
    "audit_rows_this_run": as_int("D_AMB"),
    "twin_windows": twin.get("green_corridor_windows"),
    "window_labels": twin.get("window_labels"),
  },
  "band_transitions": {
    "transitions": transitions if isinstance(transitions, list) else [],
    "released_after_completion": os.environ["RELEASED"] == "yes",
    "city_band_after": os.environ["CITY_BAND_AFTER"],
    "note": "read from adaptive.situation_log (transitioned rows of the flagship event); the "
            "situation engine releases a completed event at its next tick, so it no longer "
            "holds the city band",
  },
  "injection": {
    "active_movements_feed_reflected_event": os.environ["ACTIVE_FEED_SEEN"] == "true",
    "active_movements_feed_reflected_cloudburst": os.environ["RAIN_FEED_SEEN"] == "true",
    "cloudburst_event_row": os.environ["RAIN_ROW"],
    "event_row": {"event_kind": os.environ["EV_KIND"],
                  "protection_class": os.environ["EV_PROT"],
                  "phases": as_int("N_PHASES")},
    "sweep_event_kind": os.environ["SWEEP_KIND"],
  },
  "screenshots": sorted(f for f in os.listdir(S) if f.startswith("showcase_") and f.endswith(".png")),
  "screenshot_proofs": {
      "city3d_nonblank": os.environ["CITY_SHOT_OK"] == "true",
      "pursuit_citizen_nonblank": os.environ["REST_SHOTS_OK"] == "true",
      "method": "SwiftShader software WebGL; live-canvas distinct-colour readback + "
                "saved-PNG reload decode (Chrome as decoder), >=8 distinct colours",
  },
  "failed_assertions": failed,
  "passed": not failed,
  "generated_at_utc": os.environ["NOW_UTC"],
}
with open(sys.argv[1], "w") as fh:
    json.dump(summary, fh, indent=2)
PYEOF

log "summary written to $RESULTS_JSON"
echo "────"
if [ "$FAILURES" -eq 0 ]; then
    echo "${BOLD}SHOWCASE PASS${RESET} — God's-eye evening over Mumbai: visarjan night + monsoon burst at high tide (hydro proposals) + 108 green corridor + stolen-vehicle chain (evidence, no fine) + Civic Volunteers + signal-policy guard + VIP plan — all real APIs, all audited, every scenario labelled"
    echo "      runs: visarjan $FLAG_RUN_ID (event $FLAG_EVENT_ID), monsoon burst $RAIN_RUN_ID (event ${RAIN_EVENT_ID:-?}), sweep $SWEEP_RUN_ID (event ${SWEEP_EVENT_ID:-?}) | pursuit ${PURSUIT_ID:-?} | VIP plan ${VIP_EVENT_ID:-?}"
    echo "      decisions(this run): $d_situation situation + $d_params param rows | transitions: $d_trans | green windows: $GC_WINDOWS | signal shifts committed: $SIGNAL_PLAN_SHIFTS (refusals: $SIGNAL_REFUSALS; $REPLAY_SUMMARY) | shots: $(ls "$SHOWCASE_DIR"/showcase_*.png 2>/dev/null | xargs -n1 basename 2>/dev/null | paste -sd, -)"
    exit 0
fi
echo "${BOLD}SHOWCASE FAIL${RESET} — $FAILURES assertion(s):"
for a in "${FAILED_ASSERTS[@]}"; do echo "      - $a"; done
exit 1
