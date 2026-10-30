#!/usr/bin/env bash
# sajag_up.sh — one idempotent command that brings the Sajag (argus) stack up,
# proves it is actually working, and says so in a readiness table.
#
# Usage (from anywhere, as the user that owns the stack — never root/sudo):
#   scripts/sajag_up.sh                    bring-up: preflight → model units → (--build:
#                                         build images) → PostGIS alone up -d → healthy
#                                         → migrate → seed if empty (+ the
#                                         OpenStreetMap road network step when it
#                                         changes or the store is not on that network,
#                                         the post-seed repairs and the display file
#                                         when they change) → every service up -d →
#                                         after a network step, restart the services
#                                         that cached the old network → converge →
#                                         readiness table
#   scripts/sajag_up.sh --status           READ-ONLY readiness table (exit 0 iff all READY)
#   scripts/sajag_up.sh --install-units    write ~/.config/sajag/sajag.env (if absent), link
#                                         infra/systemd/* into ~/.config/systemd/user and
#                                         enable sajag.target (does not start anything)
# The model hosts run only as those systemd --user units: a bring-up that
# manages them needs --install-units done once (or --no-models).
# Flags:
#   --build           rebuild the service images (compose build, before anything is
#                     recreated; fetches the t0 artifact first). The PostGIS image is NOT
#                     rebuilt — a new one would recreate the store container.
#   --rebuild-postgis --build, and rebuild the PostGIS image too (recreates the store
#                     container; its data stays on the postgis_data volume)
#   --demo            demo mode: city signal-plan writer (VVIP_SIGNAL_POLICY_WRITER=1) and
#                     living-city emulation (EMULATOR_LIVING_CITY=1); persisted as SAJAG_DEMO=1
#                     in sajag.env so reboots keep it. --no-demo switches it off again.
#                     HELD until the citizen pages label emulated events: --demo is refused
#                     unless the running deck's GET /api/public/events carries
#                     emulated_labelling:true (or SAJAG_DEMO_ALLOW_UNLABELLED=1 overrides); a
#                     persisted SAJAG_DEMO=1 keeps the writer but holds the living city OFF
#                     while the marker is missing (the deck must already answer).
#   --retire-legacy   stop hand-launched processes holding stack ports (bash serve_models.sh
#                     restart loops, the nohup emulator) so the units and containers can bind;
#                     the model units start right after. Never done implicitly.
#   --no-models       leave the host model services alone: their ports are not inspected,
#                     retired, started or waited for (--retire-legacy then retires only
#                     the emulator)
#   --timeout SEC     convergence timeout (default 600, or SAJAG_CONVERGE_TIMEOUT)
#   --boot            mode of sajag-up.service: wait for Docker, bring up, converge
#                     (the models are started by sajag-models.target alongside)
#
# Values compose interpolates (SAJAG_PERSIST_KEYS in scripts/sajag_env.sh: the
# operator gate's SAJAG_OPERATOR_PIN / SAJAG_SESSION_SECRET, POSTGIS_PASSWORD,
# SAJAG_CESIUM_ION_TOKEN, …) reach a boot bring-up only through sajag.env:
# persist them with scripts/sajag_env.sh --set KEY - (value on stdin; a
# bring-up warns when this shell carries one sajag.env lacks).
# --status shows a 'security' row: the deck's bind scope and its operator
# gate (GET /api/session); a deck exposed beyond loopback with the gate OFF
# is DEGRADED.
# One bring-up runs at a time (lock in $SAJAG_RUN_DIR): a second one is
# refused, --boot waits for it.
#
# SAJAG_OSINT (sajag.env; 0 by default — plan R7): with SAJAG_OSINT=1 the
# compose invocation also names infra/compose.osint-ingress.yml
# (scripts/sajag_env.sh) and the table gains a 12th component, osint
# (sajag-osint-ingress, loopback :8193), gated like the others and
# checked in the preflight's port list. Its readiness never depends on the
# internet: READY = GET /health answers AND reports the oracle reachable,
# whatever the connectors say (no egress at a venue, a GDELT 429, Reddit
# refusing the box: shown in DETAIL, "READY · offline cache only · 4 of 4
# connectors failing …"); DEGRADED = /health answers but the oracle is not
# reachable from it; DOWN = /health does not answer. With the flag at 0 the
# stack is exactly its 11 components and 3 compose files, and a bring-up
# stops and removes a stale sajag-osint-ingress container an earlier
# SAJAG_OSINT=1 bring-up left (one docker rm -f; nothing when absent), so a
# flag rollback cannot leave it fetching and posting. Set it with
# scripts/sajag_env.sh --set SAJAG_OSINT 1 (or 0).
#
# The road network (seed()): services/corridor-store/seed/reanchor_osm_network.sql
# — generated, idempotent, one transaction — is applied when the store is
# empty, when the file differs from its run-dir stamp, AND whenever a
# read-only probe finds the store off that network (a segment whose
# geom_source is not 'osm', or a segment / junction count other than the
# file's network-probe line). The stamp lives in $SAJAG_RUN_DIR, not in the
# store: a pre-conversion backup restored after the deploy (the rollback) or
# a reboot onto one is converted again, never left on the schematic network.
# The postgis readiness row names the basis ('network osm 49/49 · 34
# junctions') and is DEGRADED while the store is not on the generated one.
# The services are (re)created only after the migrations and the seed (the
# store comes up alone first), but a container that was already running and
# is not recreated keeps what it cached: after a network step in THIS
# bring-up (also under --boot) each of the containers that cache the network
# — the traffic-oracle (segment names, geometry basis, unit paths), the
# event-emulator (segment anchors and paths) and the command-deck (citizen
# facts) — that started before the step is restarted once; a bring-up that
# fails between the step and that restart leaves
# $SAJAG_RUN_DIR/seed/network_readers.restart, so the next one (or the boot
# retry) restarts them. (At boot Docker's restart policy starts every
# container before this script runs: the order above applies to bring-ups.) Nothing is restarted when the network did not change;
# --status never writes. Each seed file is one transaction and runs quietly: a file
# that opens its own (BEGIN; … COMMIT;) is not wrapped in a second one, so
# psql prints no 'transaction in progress' warnings.
#
# Exit codes: 0 ready · 1 not converged / not ready · 2 preflight refusal or usage ·
#             3 a bring-up step failed (Docker unreachable, compose, migrate, seed,
#             model units)

set -euo pipefail

SAJAG_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=scripts/sajag_env.sh
. "$SAJAG_ROOT/scripts/sajag_env.sh"

MODE=up
BUILD=0
REBUILD_POSTGIS=0
DEMO_FLAG=""
RETIRE=0
NO_MODELS=0
TIMEOUT="${SAJAG_CONVERGE_TIMEOUT:-600}"

while [ $# -gt 0 ]; do
    case "$1" in
        --status)        MODE=status ;;
        --install-units) MODE=install ;;
        --boot)          MODE=boot ;;
        --build)         BUILD=1 ;;
        --rebuild-postgis) BUILD=1; REBUILD_POSTGIS=1 ;;
        --demo)          DEMO_FLAG=on ;;
        --no-demo)       DEMO_FLAG=off ;;
        --retire-legacy) RETIRE=1 ;;
        --no-models)     NO_MODELS=1 ;;
        --timeout)       TIMEOUT="${2:?--timeout needs seconds}"; shift ;;
        -h|--help)       awk 'NR > 1 { if (!/^#/) exit; sub(/^# ?/, ""); print }' "$0"; exit 0 ;;
        *) echo "unknown option: $1 (see --help)" >&2; exit 2 ;;
    esac
    shift
done
if [ "$MODE" = status ] && { [ -n "$DEMO_FLAG" ] || [ "$BUILD" = 1 ] || [ "$RETIRE" = 1 ]; }; then
    echo "--status is read-only; it takes no other flag" >&2; exit 2
fi

say()  { printf '[sajag_up] %s\n' "$*"; }
warn() { printf '[sajag_up] WARN: %s\n' "$*" >&2; }
die()  { printf '[sajag_up] ERROR: %s\n' "$1" >&2; exit "${2:-2}"; }

# Under sudo every judgement below would be about root: root's user manager
# and home, and ss reporting docker-proxy as the owner of every published
# port (a "conflict" on each one).
if [ "$(id -u)" = 0 ]; then
    die "run as the user that owns the stack, not root/sudo: the model hosts are that user's systemd --user units, sajag.env lives in its home and port owners are matched against its processes"
fi

# The ports this script probes, preflights and builds the DSN from are the
# ones compose actually binds: read from the rendered compose files (no
# interpolation, so no value from sajag.env is ever rendered), never from a
# shell that exported ORACLE_PORT & co. for a sandbox or a dev deck. A
# shell value that differs is reported and ignored. The model hosts' ports
# (systemd units) are not in compose and keep sajag_env.sh's values.
compose_ports() {  # → KEY=VALUE lines for the compose-bound host ports
    sajag_compose config --no-interpolate --format json 2>/dev/null | python3 -c '
import json, sys
try:
    services = json.load(sys.stdin)["services"]
except Exception:
    sys.exit(0)
def env(name):
    e = (services.get(name) or {}).get("environment") or {}
    if isinstance(e, list):
        e = dict(item.split("=", 1) if "=" in item else (item, None) for item in e)
    return e
def published(name, target):
    for p in (services.get(name) or {}).get("ports") or []:
        if isinstance(p, dict) and int(p.get("target", 0)) == target and p.get("published"):
            return str(p["published"])
    return None
want = {
    "POSTGIS_HOST_PORT": published("postgis", 5432),
    "VALKEY_HOST_PORT": published("valkey", 6379),
    "NATS_HOST_PORT": published("nats", 4222),
    "NATS_MON_PORT": published("nats", 8222),
    "ORACLE_PORT": env("traffic-oracle").get("PORT"),
    "BRAIN_PORT": env("convoy-brain").get("PORT"),
    "DECK_PORT": env("command-deck").get("PORT"),
    "EMULATOR_PORT": env("event-emulator").get("PORT"),
    "OSINT_PORT": env("osint-ingress").get("PORT"),
}
for key, value in want.items():
    if value and str(value).isdigit():
        print(f"{key}={value}")
' 2>/dev/null || true
}

sync_compose_ports() {
    local line key value seen=0
    while IFS= read -r line; do
        [ -n "$line" ] || continue
        key="${line%%=*}"; value="${line#*=}"; seen=$((seen + 1))
        if [ "${!key:-}" != "$value" ]; then
            warn "$key=${!key:-<unset>} in this environment, but compose binds $value — probing $value"
            printf -v "$key" '%s' "$value"
            export "${key?}"
        fi
    done < <(compose_ports)
    [ "$seen" -gt 0 ] || warn "could not read the host ports from the compose files (docker compose config) — probing sajag_env.sh's values"
}
sync_compose_ports

PG_DSN="postgresql://corridor_admin:${POSTGIS_PASSWORD:-dev_changeme}@127.0.0.1:${POSTGIS_HOST_PORT}/corridor_db"
# Every unit file in infra/systemd (a unit left out here is never linked, and
# sajag.target's Wants= on it does nothing on a fresh machine): the model
# hosts, the AI tier (forecast, hydro, twin, speech, vision, city feeds) and
# the targets that pull them in.
UNITS=(sajag-llama.service sajag-decider.service sajag-embed.service sajag-models.target
       sajag-ai-forecast.service sajag-ai-hydro.service sajag-ai-twin.service
       sajag-ai-speech.service sajag-ai-vision.service sajag-feeds.service sajag-ai.target
       sajag-up.service sajag.target)
# The user manager's default unit directory and the EnvironmentFile= the
# units load (%h/.config/sajag/sajag.env): both under $HOME/.config, whatever
# this shell's XDG_CONFIG_HOME says.
SYSTEMD_USER_DIR="$HOME/.config/systemd/user"
UNIT_ENV_FILE="$HOME/.config/sajag/sajag.env"

# ─── read-only probes ───────────────────────────────────────────────────────

http_code() {  # <url> → status code (000 when unreachable)
    curl -s -o /dev/null -m 4 -w '%{http_code}' "$1" 2>/dev/null || true
}

http_body() {  # <url> → body ('' when unreachable or non-2xx)
    curl -sf -m 4 "$1" 2>/dev/null || true
}

jget() {  # <dotted.path> — JSON on stdin → value at that path ('' when absent)
    python3 -c '
import json, sys
try:
    v = json.load(sys.stdin)
    for key in sys.argv[1].split("."):
        v = v[int(key)] if isinstance(v, list) else v[key]
except Exception:
    sys.exit(0)
if isinstance(v, bool):
    print("true" if v else "false")
elif isinstance(v, (dict, list)):
    print(json.dumps(v))
elif v is not None:
    print(v)
' "$1" 2>/dev/null || true
}

false_keys() {  # <dotted.path to an object> — JSON on stdin → keys whose value is falsy
    python3 -c '
import json, sys
try:
    v = json.load(sys.stdin)
    for key in sys.argv[1].split("."):
        v = v[key]
    print(",".join(k for k, ok in v.items() if not ok))
except Exception:
    print("?")
' "$1" 2>/dev/null || true
}

connz_in_msgs() {  # <client name> — NATS /connz JSON on stdin → in_msgs of that client
    python3 -c '
import json, sys
try:
    conns = json.load(sys.stdin).get("connections", [])
    print(sum(c.get("in_msgs", 0) for c in conns if c.get("name") == sys.argv[1]))
except Exception:
    print("")
' "$1" 2>/dev/null || true
}

container_status() {  # <name> → running|exited|…|absent
    docker inspect -f '{{.State.Status}}' "$1" 2>/dev/null || echo absent
}

container_health() {  # <name> → healthy|unhealthy|starting|none|absent
    docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$1" 2>/dev/null || echo absent
}

psql_q() {  # <SELECT …> — read-only query in the PostGIS container
    docker exec "$POSTGIS_CONTAINER" psql -X -A -t -q -U corridor_admin -d corridor_db \
        -c "SET default_transaction_read_only = on" -c "$1" 2>/dev/null | tail -n 1
}

NETWORK_SQL="$SAJAG_ROOT/services/corridor-store/seed/reanchor_osm_network.sql"

network_expected() {  # → "<segments> <junctions>" of the generated network ('' when unknown)
    [ -f "$NETWORK_SQL" ] || return 0
    sed -n 's/^-- network-probe: geom_source=osm segments=\([0-9][0-9]*\) junctions=\([0-9][0-9]*\)$/\1 \2/p' \
        "$NETWORK_SQL"
}

network_probe() {  # → "<osm segments> <segments> <junctions>" of the store ('' when unreadable)
    # before migration 020 (no geom_source column) no segment is on OpenStreetMap
    local osm="count(*) filter (where geom_source = 'osm')"
    [ "$(psql_q "select count(*) from information_schema.columns where table_schema = 'corridor' and table_name = 'road_segments' and column_name = 'geom_source'" || true)" = 1 ] || osm=0
    psql_q "select $osm || ' ' || count(*) || ' ' || (select count(*) from corridor.junctions) from corridor.road_segments" || true
}

on_network() {  # <probe> <expected> — is the store on the generated road network?
    [ -n "$2" ] || return 0   # a network step without a probe line: nothing to compare
    local segs juncs; read -r segs juncs <<<"$2"
    [ "$1" = "$segs $segs $juncs" ]
}

network_basis() {  # <probe> → 'network osm 49/49 · 34 junctions'
    local osm segs juncs; read -r osm segs juncs <<<"$1"
    if [ -n "$juncs" ]; then echo "network osm $osm/$segs · $juncs junctions"; else echo "network ?"; fi
}

listeners() {  # <port> → "addr pid" lines (pid empty when not visible to this user)
    ss -H -ltnp "sport = :$1" 2>/dev/null | awk '{
        pid = ""; if (match($0, /pid=[0-9]+/)) pid = substr($0, RSTART + 4, RLENGTH - 4)
        print $4, pid }'
}

bind_scope() {  # <port> → loopback | exposed:<addrs> | none
    local addrs; addrs="$(listeners "$1" | awk '{print $1}' | sort -u | tr '\n' ' ')"
    [ -z "$addrs" ] && { echo none; return; }
    local a exposed=""
    for a in $addrs; do
        case "$a" in 127.*|\[::1\]:*) ;; *) exposed="$exposed${exposed:+,}$a" ;; esac
    done
    if [ -n "$exposed" ]; then echo "exposed:$exposed"; else echo loopback; fi
}

pid_owner() {  # <pid> → unit:<sajag unit> | legacy-models | legacy-emulator | other:<cmd>
    local pid="$1" cg cmd
    cg="$(cat "/proc/$pid/cgroup" 2>/dev/null || true)"
    if grep -qE 'sajag-[a-z]+\.service' <<<"$cg"; then
        echo "unit:$(grep -oE 'sajag-[a-z]+\.service' <<<"$cg" | head -n 1)"; return
    fi
    cmd="$(tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null || true)"
    case "$cmd" in
        *event_emulator*) echo legacy-emulator ;;
        *llama-server*|*model_host.app*|*embedding_launcher*) echo legacy-models ;;
        *) echo "other:${cmd:0:90}" ;;
    esac
}

units_installed() {  # all six linked where the user manager looks (a dangling link is not)
    local u
    for u in "${UNITS[@]}"; do [ -e "$SYSTEMD_USER_DIR/$u" ] || return 1; done
}

model_supervision() {  # <unit> <port> → how the host on <port> is supervised
    if systemctl --user is-active --quiet "$1" 2>/dev/null; then echo "systemd $1"; return; fi
    local pid; pid="$(listeners "$2" | awk '$2 != "" {print $2; exit}')"
    if [ -n "$pid" ]; then
        case "$(pid_owner "$pid")" in
            unit:*) echo "systemd $(pid_owner "$pid" | cut -d: -f2)" ;;
            legacy-models) echo "LEGACY hand-launched loop (pid $pid) — not reboot-proof" ;;
            *) echo "unknown owner pid $pid" ;;
        esac
    else
        echo "not running"
    fi
}

# ─── readiness checks ───────────────────────────────────────────────────────

ORDER=(postgis valkey nats signal-ingress oracle brain deck emulator)
# SAJAG_OSINT=1 (plan R7): the 12th component, after the emulator (its cousin
# for real open signals); with the flag at 0 the 11 components are unchanged
if [ "$SAJAG_OSINT" = 1 ]; then ORDER+=(osint); fi
ORDER+=(decider gemma embeddings)
declare -A STATE DETAIL ENDPOINT
INFO=()

mark() { STATE[$1]="$2"; DETAIL[$1]="$3"; }

check_postgis() {
    ENDPOINT[postgis]="127.0.0.1:$POSTGIS_HOST_PORT"
    local health; health="$(container_health "$POSTGIS_CONTAINER")"
    if [ "$health" != healthy ]; then mark postgis DOWN "container $POSTGIS_CONTAINER: $health"; return; fi
    local net want migs
    net="$(network_probe)"; want="$(network_expected)"
    migs="$(psql_q "select count(*) from corridor.schema_migrations")"
    if ! on_network "$net" "$want"; then
        mark postgis DEGRADED "healthy · $(network_basis "$net") — NOT the generated OpenStreetMap network (${want% *} segments, ${want#* } junctions): scripts/sajag_up.sh applies the network step · ${migs:-?} migrations ledgered"
        return
    fi
    mark postgis READY "healthy · $(network_basis "$net") · ${migs:-?} migrations ledgered"
}

check_valkey() {
    ENDPOINT[valkey]="127.0.0.1:$VALKEY_HOST_PORT"
    local pong; pong="$(docker exec "$VALKEY_CONTAINER" valkey-cli ping 2>/dev/null || true)"
    if [ "$pong" != PONG ]; then mark valkey DOWN "container $VALKEY_CONTAINER: $(container_status "$VALKEY_CONTAINER")"; return; fi
    local keys live
    keys="$(docker exec "$VALKEY_CONTAINER" valkey-cli dbsize 2>/dev/null || echo '?')"
    live="$(docker exec "$VALKEY_CONTAINER" valkey-cli --scan --pattern 'traffic:latest:*' 2>/dev/null | wc -l)"
    mark valkey READY "PONG · $keys keys · $live traffic:latest:*"
}

VARZ=""
check_nats() {
    ENDPOINT[nats]="127.0.0.1:$NATS_HOST_PORT (mon :$NATS_MON_PORT)"
    VARZ="$(http_body "http://127.0.0.1:$NATS_MON_PORT/varz")"
    local sid; sid="$(jget server_id <<<"$VARZ")"
    if [ -n "$sid" ]; then
        mark nats READY "v$(jget version <<<"$VARZ") · $(jget connections <<<"$VARZ") conns · $(jget in_msgs <<<"$VARZ") msgs in · server ${sid:0:8}"
    elif (exec 3<>"/dev/tcp/127.0.0.1/$NATS_HOST_PORT") 2>/dev/null; then
        mark nats DEGRADED "client port up; monitoring :$NATS_MON_PORT off (server not started with -m 8222)"
    else
        mark nats DOWN "container $NATS_CONTAINER: $(container_status "$NATS_CONTAINER")"
    fi
}

check_ingress() {
    ENDPOINT[signal-ingress]="nats corridor.traffic.live"
    local st image
    st="$(container_status "$INGRESS_CONTAINER")"
    image="$(docker inspect -f '{{.Config.Image}}' "$INGRESS_CONTAINER" 2>/dev/null || echo '?')"
    if [ "$st" != running ]; then mark signal-ingress DOWN "container $INGRESS_CONTAINER: $st"; return; fi
    if [ -z "$VARZ" ]; then
        mark signal-ingress DEGRADED "running ($image); publishing unverified — NATS monitoring off"
        return
    fi
    local a b
    a="$(http_body "http://127.0.0.1:$NATS_MON_PORT/connz?limit=1024" | connz_in_msgs signal-ingress)"
    sleep 3
    b="$(http_body "http://127.0.0.1:$NATS_MON_PORT/connz?limit=1024" | connz_in_msgs signal-ingress)"
    if [ -n "$a" ] && [ -n "$b" ] && [ "$b" -gt "$a" ]; then
        mark signal-ingress READY "publishing $(( (b - a) / 3 )) msg/s ($image)"
    elif [ "${b:-0}" = 0 ]; then
        mark signal-ingress DEGRADED "running ($image) but no NATS client named signal-ingress (pre-WP-08 image?)"
    else
        mark signal-ingress DEGRADED "connected but no messages in 3 s ($image)"
    fi
}

check_oracle() {
    ENDPOINT[oracle]="127.0.0.1:$ORACLE_PORT"
    local body; body="$(http_body "http://127.0.0.1:$ORACLE_PORT/health")"
    if [ "$(jget status <<<"$body")" != ok ]; then mark oracle DOWN "/health unreachable"; return; fi
    local ingest; ingest="$(jget ingest <<<"$body")"
    if [ -z "$ingest" ]; then
        mark oracle DEGRADED "up, but /health reports no ingest block (live NATS consumer not deployed)"
        return
    fi
    local connected age
    connected="$(jget ingest.connected <<<"$body")"
    age="$(jget ingest.last_msg_age_sec <<<"$body")"
    if [ "$connected" = true ] && awk -v a="${age:-x}" 'BEGIN { exit !(a ~ /^[0-9.]+$/ && a + 0 < 10) }'; then
        mark oracle READY "ingest connected · last msg ${age}s ago · $(jget ingest.msgs_per_min <<<"$body") msg/min"
    else
        mark oracle DEGRADED "ingest connected=${connected:-?} · last msg ${age:-?}s ago"
    fi
}

check_brain() {
    ENDPOINT[brain]="127.0.0.1:$BRAIN_PORT"
    local body st tiers
    body="$(http_body "http://127.0.0.1:$BRAIN_PORT/health")"
    st="$(jget status <<<"$body")"
    tiers="strategic $(jget strategic_tier.model_host <<<"$body") · tactical $(jget tactical_tier.llama_server <<<"$body")"
    case "$st" in
        ok) mark brain READY "$tiers" ;;
        # the brain answers but a model tier is loading / unreachable (or the
        # decider is degraded): up, not DOWN — the reason is shown
        degraded)
            local why; why="$(jget strategic_tier.degraded_reason <<<"$body")"
            mark brain DEGRADED "/health degraded · $tiers${why:+ · $why}" ;;
        "") mark brain DOWN "/health unreachable" ;;
        *)  mark brain DOWN "/health status '$st'" ;;
    esac
}

DECK_SCOPE="" DECK_GATE="" DECK_GATE_OPEN_ON_LAN=0
check_deck() {
    ENDPOINT[deck]="0.0.0.0:$DECK_PORT"
    local root emu
    root="$(http_code "http://127.0.0.1:$DECK_PORT/")"
    emu="$(http_code "http://127.0.0.1:$DECK_PORT/api/emulator/health")"
    # the operator gate (SAJAG_OPERATOR_PIN): read-only GET of the sign-in
    # status; on when /api/session says gate:true
    DECK_SCOPE="$(bind_scope "$DECK_PORT")"
    case "$(http_body "http://127.0.0.1:$DECK_PORT/api/session" | jget gate)" in
        true)  DECK_GATE=on ;;
        false) DECK_GATE=OFF ;;
        *)     DECK_GATE=unknown ;;
    esac
    DECK_GATE_OPEN_ON_LAN=0
    if [ "$root" = 200 ] && [[ "$DECK_SCOPE" == exposed:* ]] && [ "$DECK_GATE" = OFF ]; then
        DECK_GATE_OPEN_ON_LAN=1
        mark deck DEGRADED "reachable beyond loopback (${DECK_SCOPE#exposed:}) with the operator gate OFF — every operator write is open to the LAN"
        return
    fi
    if [ "$root" = 200 ] && [ "$emu" = 200 ]; then mark deck READY "/ 200 · /api/emulator/health 200 · gate $DECK_GATE"
    elif [ "$root" = 200 ]; then mark deck DEGRADED "/ 200 · /api/emulator/health $emu"
    else mark deck DOWN "/ $root"
    fi
}

check_emulator() {
    ENDPOINT[emulator]="127.0.0.1:$EMULATOR_PORT"
    local body; body="$(http_body "http://127.0.0.1:$EMULATOR_PORT/health")"
    local sup="container $EMULATOR_CONTAINER"
    [ "$(container_status "$EMULATOR_CONTAINER")" = running ] || sup="NOT the compose container"
    local pid; pid="$(listeners "$EMULATOR_PORT" | awk '$2 != "" {print $2; exit}')"
    [ -n "$pid" ] && [ "$(pid_owner "$pid")" = legacy-emulator ] && sup="LEGACY nohup pid $pid"
    if [ -z "$body" ]; then mark emulator DOWN "/health unreachable · $sup"; return; fi
    local down; down="$(false_keys stack <<<"$body")"
    if [ -z "$down" ]; then
        # 'degraded' with full connectivity is historical (e.g. a failed last
        # run): the emulator works, so it is READY and the reason is shown.
        local note=""
        [ "$(jget status <<<"$body")" = degraded ] && note=" · degraded: $(jget degraded_reasons <<<"$body")"
        mark emulator READY "stack all true · library $(jget library <<<"$body") · $sup$note"
    else
        mark emulator DEGRADED "stack false: $down · $sup"
    fi
}

osint_summary() {  # osint-ingress /health JSON on stdin → the DETAIL text after the state
    # counts, names and short connector errors only (never a signal's text)
    python3 -c '
import json, sys
from datetime import datetime, timezone
try:
    h = json.load(sys.stdin)
except Exception:
    print("?"); sys.exit(0)
def ago(ts):
    try:
        t = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        s = max(0, int((datetime.now(timezone.utc) - t).total_seconds()))
    except Exception:
        return None
    return f"{s} s ago" if s < 120 else (f"{s // 60} min ago" if s < 7200 else f"{s // 3600} h ago")
out = ["live" if h.get("mode") == "live" else "offline cache only"]
lc = h.get("last_cycle") if isinstance(h.get("last_cycle"), dict) else {}
when = ago(lc.get("at")) if lc.get("at") else None
if when:
    n_sig, n_acc = lc.get("signals", 0), lc.get("accepted", 0)
    out.append(f"last cycle {when} · {n_sig} signals · {n_acc} accepted")
else:
    out.append("no cycle yet")
conns = h.get("connectors") if isinstance(h.get("connectors"), dict) else {}
on = {n: c for n, c in conns.items() if isinstance(c, dict) and c.get("enabled")}
bad = {n: c for n, c in on.items() if c.get("error")}
if not on:
    out.append("no connector enabled")
elif bad:
    # the reason before "; serving the cached entry" (the cached sample is noted once, below)
    why = ", ".join("%s (%s)" % (n, str(c.get("error")).split(";")[0][:44]) for n, c in list(bad.items())[:3])
    more = f" +{len(bad) - 3} more" if len(bad) > 3 else ""
    cached = sum(1 for c in bad.values() if c.get("fetch_mode") == "cached-sample")
    note = f" — {cached} serving their cached sample" if cached else ""
    out.append(f"{len(bad)} of {len(on)} connectors failing: {why}{more}{note}")
else:
    out.append(f"{len(on)} connectors ok")
o = h.get("oracle") if isinstance(h.get("oracle"), dict) else {}
post = o.get("last_post_status")
out.append(f"last post {post}" if post else "no post yet")
print(" · ".join(out))
' 2>/dev/null || echo "?"
}

check_osint() {  # SAJAG_OSINT=1 only; READY never depends on the internet (plan R7)
    ENDPOINT[osint]="127.0.0.1:$OSINT_PORT"
    local body st sup="container $OSINT_CONTAINER"
    body="$(http_body "http://127.0.0.1:$OSINT_PORT/health")"
    st="$(container_status "$OSINT_CONTAINER")"
    [ "$st" = running ] || sup="container $OSINT_CONTAINER $st"
    if [ -z "$body" ] || [ -z "$(jget status <<<"$body")" ]; then
        mark osint DOWN "/health unreachable · $sup"
        return
    fi
    local summary; summary="$(osint_summary <<<"$body")"
    if [ "$(jget oracle.reachable <<<"$body")" = true ]; then
        # connector failures (no egress, a 429, a source refusing the box) are
        # shown, never gating: the emulator's "READY · reason shown" pattern
        mark osint READY "$summary · $sup"
    else
        mark osint DEGRADED "oracle $(jget oracle.host <<<"$body") NOT reachable from osint-ingress (signals stay in its cache outbox) · $summary · $sup"
    fi
}

check_decider() {
    ENDPOINT[decider]="127.0.0.1:$MODEL_HOST_PORT"
    local body; body="$(http_body "http://127.0.0.1:$MODEL_HOST_PORT/decider/health")"
    local sup; sup="$(model_supervision sajag-decider.service "$MODEL_HOST_PORT")"
    if [ -z "$body" ]; then mark decider DOWN "unreachable · $sup"; return; fi
    if [ "$(jget loaded <<<"$body")" = true ]; then
        mark decider READY "loaded · p95 $(jget p95_decide_latency_ms <<<"$body") ms · $sup"
    elif [ -n "$(jget load_error <<<"$body")" ]; then
        mark decider FAILED "load_error: $(jget load_error <<<"$body") · $sup"
    else
        mark decider LOADING "weights loading (cold load ≈5 min) · $sup"
    fi
}

check_gemma() {
    ENDPOINT[gemma]="127.0.0.1:$LLAMA_PORT"
    local code; code="$(http_code "http://127.0.0.1:$LLAMA_PORT/health")"
    local sup; sup="$(model_supervision sajag-llama.service "$LLAMA_PORT")"
    case "$code" in
        200) mark gemma READY "llama-server ok · $sup" ;;
        503) mark gemma LOADING "model loading · $sup" ;;
        *)   mark gemma DOWN "/health $code · $sup" ;;
    esac
}

check_embeddings() {
    ENDPOINT[embeddings]="127.0.0.1:$EMBEDDING_PORT"
    local body; body="$(http_body "http://127.0.0.1:$EMBEDDING_PORT/health")"
    local sup; sup="$(model_supervision sajag-embed.service "$EMBEDDING_PORT")"
    if [ "$(jget status <<<"$body")" = ok ]; then
        mark embeddings READY "$(jget late_encoder <<<"$body") + $(jget dense_encoder <<<"$body") · $sup"
    else
        mark embeddings DOWN "/health not ok · $sup"
    fi
}

collect_info() {  # non-gating facts shown under the table
    INFO=()
    local port scope exposed=""
    local internal=("$POSTGIS_HOST_PORT" "$VALKEY_HOST_PORT" "$NATS_HOST_PORT" "$NATS_MON_PORT"
                    "$EMULATOR_PORT" "$ORACLE_PORT" "$BRAIN_PORT" "$MODEL_HOST_PORT" "$LLAMA_PORT" "$EMBEDDING_PORT")
    if [ "$SAJAG_OSINT" = 1 ]; then internal+=("$OSINT_PORT"); fi
    for port in "${internal[@]}"; do
        scope="$(bind_scope "$port")"
        case "$scope" in exposed:*) exposed="$exposed :$port(${scope#exposed:})" ;; esac
    done
    if [ -n "$exposed" ]; then INFO+=("network   EXPOSED beyond loopback:$exposed")
    else INFO+=("network   internal ports loopback-only; deck :$DECK_PORT is $(bind_scope "$DECK_PORT")"); fi
    local sec="security  deck :$DECK_PORT ${DECK_SCOPE:-$(bind_scope "$DECK_PORT")} · operator gate ${DECK_GATE:-unknown}"
    [ "${DECK_GATE_OPEN_ON_LAN:-0}" = 1 ] && sec="$sec — WARN: reachable beyond loopback with the gate OFF (persist SAJAG_OPERATOR_PIN + SAJAG_SESSION_SECRET: scripts/sajag_env.sh --set KEY -, then recreate the deck)"
    INFO+=("$sec")
    local writer
    writer="$(http_body "http://127.0.0.1:$ORACLE_PORT/api/v1/signals/plans" | jget writer_enabled)"
    INFO+=("modes     signal-plan writer ${writer:-unknown} · SAJAG_DEMO=$SAJAG_DEMO (sajag.env: $([ -f "$SAJAG_ENV_FILE" ] && echo present || echo absent))")
    if units_installed; then
        # is-active prints 'inactive' AND exits 3: `|| echo` would add a
        # second line ('?') to the row — take the output, ignore the status
        local en act
        en="$(systemctl --user is-enabled sajag.target 2>/dev/null)" || true
        act="$(systemctl --user is-active sajag.target 2>/dev/null)" || true
        INFO+=("boot      units linked; sajag.target ${en:-?} / ${act:-?}")
    else
        INFO+=("boot      systemd units NOT installed — not reboot-proof (scripts/sajag_up.sh --install-units)")
    fi
    if [ "$SAJAG_OSINT" != 1 ]; then
        local osint_st; osint_st="$(container_status "$OSINT_CONTAINER")"
        [ "$osint_st" = absent ] || INFO+=("osint     SAJAG_OSINT=$SAJAG_OSINT but $OSINT_CONTAINER exists ($osint_st) — the next bring-up removes it (docker rm -f $OSINT_CONTAINER)")
    fi
}

run_checks() {
    check_postgis; check_valkey; check_nats; check_ingress; check_oracle; check_brain
    check_deck; check_emulator
    if [ "$SAJAG_OSINT" = 1 ]; then check_osint; fi
    check_decider; check_gemma; check_embeddings
}

gating() {  # components that must be READY (model hosts excluded by --no-models)
    local c
    for c in "${ORDER[@]}"; do
        if [ "$NO_MODELS" = 1 ]; then
            case "$c" in decider|gemma|embeddings) continue ;; esac
        fi
        echo "$c"
    done
}

all_ready() {
    local c
    for c in $(gating); do [ "${STATE[$c]:-}" = READY ] || return 1; done
}

print_table() {
    collect_info
    printf '\n%-15s %-9s %-34s %s\n' COMPONENT STATE ENDPOINT DETAIL
    local c n=0
    for c in "${ORDER[@]}"; do
        printf '%-15s %-9s %-34s %s\n' "$c" "${STATE[$c]:-?}" "${ENDPOINT[$c]:-}" "${DETAIL[$c]:-}"
        [ "${STATE[$c]:-}" = READY ] && n=$((n + 1))
    done
    printf '\n'
    local line; for line in "${INFO[@]}"; do printf '%s\n' "$line"; done
    printf '\nREADY %d/%d' "$n" "${#ORDER[@]}"
    if [ "$n" -ne "${#ORDER[@]}" ]; then
        printf ' — not ready:'
        for c in "${ORDER[@]}"; do [ "${STATE[$c]:-}" = READY ] || printf ' %s(%s)' "$c" "${STATE[$c]:-?}"; done
    fi
    [ "$NO_MODELS" = 1 ] && printf ' (model hosts not gated: --no-models)'
    printf '\n'
}

# ─── bring-up steps ─────────────────────────────────────────────────────────

lock_bring_up() {  # one bring-up at a time: sajag-up.service at boot vs. a manual run
    mkdir -p "$SAJAG_RUN_DIR"
    exec 9>"$SAJAG_RUN_DIR/sajag_up.lock"
    if [ "$MODE" = boot ]; then
        # the manual run is doing the same work: wait, then report
        flock -w 900 9 || die "another bring-up held $SAJAG_RUN_DIR/sajag_up.lock for 15 min" 3
    else
        flock -n 9 || die "another bring-up is running (sajag-up.service after a boot, or a second sajag_up.sh) — let it finish (journalctl --user -u sajag-up -f), then re-run"
    fi
}

wait_docker() {  # <timeout_s>
    local deadline=$(( $(date +%s) + $1 ))
    until docker info >/dev/null 2>&1; do
        [ "$(date +%s)" -lt "$deadline" ] || die "docker daemon not reachable after $1 s" 3
        sleep 3
    done
}

preflight() {
    command -v docker >/dev/null || die "docker CLI not found"
    docker info >/dev/null 2>&1 || die "docker daemon not reachable (is docker.service running?)"
    docker compose version >/dev/null 2>&1 || die "docker compose v2 plugin not found"
    command -v ss >/dev/null || die "ss (iproute2) not found"

    # The retired `vvip` project must not run beside the argus stack.
    local retired
    retired="$(docker ps -a --format '{{.Names}}' | grep -E '^vvip-(postgis|valkey|nats|signal-ingress|traffic-oracle|convoy-brain|command-deck|event-emulator)$' || true)"
    if [ -n "$retired" ]; then
        retired="$(tr '\n' ' ' <<<"$retired")"
        die "retired original-stack containers exist: ${retired% } — remove them first: docker rm -f ${retired% }"
    fi

    # Port owners: free, the argus container, a sajag systemd unit, or a
    # legacy hand-launched process (retired only with --retire-legacy).
    # --no-models leaves the host model services alone: their ports are not
    # inspected, so whatever serves them is neither refused nor retired.
    local specs=(
        "$POSTGIS_HOST_PORT:$POSTGIS_CONTAINER" "$VALKEY_HOST_PORT:$VALKEY_CONTAINER"
        "$NATS_HOST_PORT:$NATS_CONTAINER" "$NATS_MON_PORT:$NATS_CONTAINER"
        "$ORACLE_PORT:$ORACLE_CONTAINER" "$BRAIN_PORT:$BRAIN_CONTAINER"
        "$DECK_PORT:$DECK_CONTAINER" "$EMULATOR_PORT:$EMULATOR_CONTAINER"
    )
    if [ "$SAJAG_OSINT" = 1 ]; then specs+=("$OSINT_PORT:$OSINT_CONTAINER"); fi
    [ "$NO_MODELS" = 1 ] || specs+=("$MODEL_HOST_PORT:unit" "$LLAMA_PORT:unit" "$EMBEDDING_PORT:unit")
    local spec port expect legacy_models="" legacy_emulator="" conflicts=""
    for spec in "${specs[@]}"; do
        port="${spec%%:*}"; expect="${spec#*:}"
        local addr pid owner
        while read -r addr pid; do
            [ -z "$addr" ] && continue
            if [ -z "$pid" ]; then
                # not visible to this user: Docker (port proxy or a container
                # user). Any state counts — at boot the proxy can be bound while
                # its container is still restarting.
                if [ "$expect" != unit ] && [ "$(container_status "$expect")" != absent ]; then continue; fi
                conflicts="$conflicts :$port($addr held by a process this user cannot see; expected $expect)"
                continue
            fi
            owner="$(pid_owner "$pid")"
            case "$owner" in
                unit:*) ;;
                legacy-models)   legacy_models="$legacy_models $pid" ;;
                legacy-emulator) legacy_emulator="$legacy_emulator $pid" ;;
                *) conflicts="$conflicts :$port(pid $pid ${owner#other:})" ;;
            esac
        done < <(listeners "$port")
    done
    [ -z "$conflicts" ] || die "ports held by unexpected processes:$conflicts"

    # This run starts the model units (with --boot, sajag.target does).
    # Everything they need — the installed units, a reachable user manager,
    # weights, binaries and venvs — must exist BEFORE any legacy host is
    # retired: never leave the host without model servers.
    if [ "$NO_MODELS" != 1 ] && [ "$MODE" != boot ]; then
        units_installed || die "the sajag systemd --user units are not installed; the model hosts run only as those (reboot-proof) units.
    Run scripts/sajag_up.sh --install-units once, or pass --no-models to leave the model hosts alone."
        systemctl --user show -p Version --value >/dev/null 2>&1 \
            || die "the systemd --user manager is not reachable from this shell (no user session bus) — run from a login session of $(id -un)"
        local var path missing=""
        for spec in "DECIDER_SNAPSHOT_PATH:-d" "LLAMA_SERVER_BIN:-x" "GEMMA_GGUF:-f" "BGE_M3_PATH:-d"; do
            var="${spec%%:*}"; path="${!var:-}"
            [ -n "$path" ] && test "${spec#*:}" "$path" || missing="$missing $var=${path:-<unset>}"
        done
        for path in "$SAJAG_VENV_DIR/model-host/bin/python" "$SAJAG_VENV_DIR/embedding/bin/python"; do
            [ -x "$path" ] || missing="$missing SAJAG_VENV_DIR:$path"
        done
        [ -z "$missing" ] || die "model host paths missing:$missing
    Set them in $SAJAG_ENV_FILE (scripts/sajag_env.sh --write / --set), build venvs with
    infra/scripts/serve_models.sh build, or pass --no-models."
    fi

    if [ -n "$legacy_models$legacy_emulator" ]; then
        if [ "$RETIRE" != 1 ]; then
            die "hand-launched legacy processes hold stack ports (models:${legacy_models:- none}; emulator:${legacy_emulator:- none}).
    They are not reboot-proof and would block the systemd units / compose emulator.
    Re-run with --retire-legacy to stop them${legacy_models:+ (the decider then reloads under systemd, ≈5 min; add --no-models to keep the model hosts as they are)}."
        fi
        retire_legacy "$legacy_models" "$legacy_emulator"
    fi
}

legacy_holders() {  # → ":port" list of in-scope stack ports still held by legacy processes
    local ports=("$EMULATOR_PORT") port addr pid out=""
    [ "$NO_MODELS" = 1 ] || ports+=("$MODEL_HOST_PORT" "$LLAMA_PORT" "$EMBEDDING_PORT")
    for port in "${ports[@]}"; do
        while read -r addr pid; do
            [ -n "$pid" ] || continue
            case "$(pid_owner "$pid")" in legacy-*) out="$out :$port"; break ;; esac
        done < <(listeners "$port")
    done
    echo "$out"
}

retire_legacy() {  # <model pids> <emulator pids>
    # Stop the supervising shell first (a bash restart loop would otherwise
    # respawn the server 5 s later), then the server itself.
    local pid parent pcmd
    for pid in $1 $2; do
        parent="$(ps -o ppid= -p "$pid" 2>/dev/null | tr -d ' ' || true)"
        pcmd="$(tr '\0' ' ' < "/proc/${parent:-0}/cmdline" 2>/dev/null || true)"
        say "retiring hand-launched pid $pid ($(pid_owner "$pid"))"
        case "$pcmd" in
            *serve_models*|*event_emulator*)
                [ "$parent" != 1 ] && kill -TERM "$parent" 2>/dev/null || true ;;
        esac
        kill -TERM "$pid" 2>/dev/null || true
    done
    # pidfiles of what was retired (never of hosts left alone by --no-models)
    [ -z "$1" ] || rm -f "$SAJAG_RUN_DIR/model-host.pid" "$SAJAG_RUN_DIR/llama-server.pid" \
                         "$SAJAG_RUN_DIR/embedding.pid"
    [ -z "$2" ] || rm -f "$SAJAG_RUN_DIR/emulator.pid"
    # wait for the ports to free up (the decider releases ~49 GiB)
    local deadline=$(( $(date +%s) + 90 )) busy
    while busy="$(legacy_holders)"; [ -n "$busy" ]; do
        if [ "$(date +%s)" -ge "$deadline" ]; then
            # replace whatever did stop; the units keep retrying
            # (Restart=always) until the stuck holder lets go
            [ -z "$1" ] || start_models
            die "legacy processes still hold$busy after 90 s"
        fi
        sleep 2
    done
}

ensure_postgis_image() {
    if ! docker image inspect sajag-postgis:arm64 >/dev/null 2>&1 \
       && docker image inspect sajag-vvip-postgis:arm64 >/dev/null 2>&1; then
        say "tagging the existing sajag-vvip-postgis:arm64 build as sajag-postgis:arm64 (no rebuild)"
        docker tag sajag-vvip-postgis:arm64 sajag-postgis:arm64
    fi
}

demo_labelling_ok() {  # do the citizen pages label emulated events? (contract C-M)
    # The living city puts emulated public events on /citizen and /driver:
    # only a deck whose public projection labels them EMULATED (WP-18 marks
    # GET /api/public/events with emulated_labelling:true) may carry it.
    [ "${SAJAG_DEMO_ALLOW_UNLABELLED:-0}" = 1 ] && return 0
    [ "$(http_body "http://127.0.0.1:$DECK_PORT/api/public/events" | jget emulated_labelling)" = true ]
}

apply_demo_mode() {
    case "$DEMO_FLAG" in
        on)
            demo_labelling_ok || die "--demo refused: the deck on :$DECK_PORT does not mark GET /api/public/events
    with emulated_labelling:true, so the living city's emulated events would show on /citizen and
    /driver as LIVE. Bring the stack up with a deck that labels them (then re-run --demo), or set
    SAJAG_DEMO_ALLOW_UNLABELLED=1 to override deliberately."
            SAJAG_DEMO=1; bash "$SAJAG_ROOT/scripts/sajag_env.sh" --set SAJAG_DEMO 1 >/dev/null ;;
        off) SAJAG_DEMO=0; bash "$SAJAG_ROOT/scripts/sajag_env.sh" --set SAJAG_DEMO 0 >/dev/null ;;
    esac
    # compose interpolates these into traffic-oracle / event-emulator
    if [ "$SAJAG_DEMO" = 1 ]; then
        export VVIP_SIGNAL_POLICY_WRITER=1
        if demo_labelling_ok; then
            export EMULATOR_LIVING_CITY=1
            say "demo mode: city signal-plan writer ON, living city ON"
        else
            # a persisted SAJAG_DEMO=1 (a reboot, a plain bring-up): hold the
            # living city rather than show emulated events as live
            export EMULATOR_LIVING_CITY=0
            warn "SAJAG_DEMO=1 but GET :$DECK_PORT/api/public/events has no emulated_labelling:true — living city held OFF (signal-plan writer ON); SAJAG_DEMO_ALLOW_UNLABELLED=1 overrides"
        fi
    else
        export VVIP_SIGNAL_POLICY_WRITER="" EMULATOR_LIVING_CITY=0
    fi
}

remove_stale_osint() {  # SAJAG_OSINT=0: nothing of the OSINT service may keep running
    # An earlier SAJAG_OSINT=1 bring-up left sajag-osint-ingress; compose
    # run with the three files no longer knows it (an orphan it only warns
    # about), so it would keep fetching the sources and posting to the oracle.
    # A no-op when absent (the case before the flag is ever set).
    [ "$SAJAG_OSINT" = 1 ] && return 0
    [ "$(container_status "$OSINT_CONTAINER")" = absent ] && return 0
    say "SAJAG_OSINT=$SAJAG_OSINT — removing the stale $OSINT_CONTAINER container an earlier SAJAG_OSINT=1 bring-up left"
    docker rm -f "$OSINT_CONTAINER" >/dev/null \
        || warn "could not remove $OSINT_CONTAINER — remove it by hand: docker rm -f $OSINT_CONTAINER"
}

built_services() {  # → the compose services with a build section (postgis only with --rebuild-postgis)
    local skip=postgis
    [ "$REBUILD_POSTGIS" = 1 ] && skip=""
    sajag_compose config --no-interpolate --format json 2>/dev/null | python3 -c '
import json, sys
services = json.load(sys.stdin)["services"]
skip = set(sys.argv[1].split())
print(" ".join(sorted(n for n, s in services.items() if "build" in s and n not in skip)))
' "$skip"
}

build_images() {  # --build: rebuild the service images BEFORE anything is recreated
    [ "$BUILD" = 1 ] || return 0
    bash "$SAJAG_ROOT/scripts/fetch_t0.sh" || die "t0 artifact unavailable (oracle image bakes models-local/t0)" 3
    local svcs; svcs="$(built_services)" || die "could not list the compose services (docker compose config)" 3
    [ -n "$svcs" ] || die "no buildable compose service found (docker compose config)" 3
    # PostGIS is never rebuilt by --build alone: a new image would recreate
    # the store container (the corridor data lives on its volume, but the
    # store would restart under every service). --rebuild-postgis asks.
    [ "$REBUILD_POSTGIS" = 1 ] || say "PostGIS image kept (--rebuild-postgis rebuilds it)"
    say "docker compose -p $SAJAG_COMPOSE_PROJECT build $svcs"
    # shellcheck disable=SC2086  # one word per service name
    sajag_compose build $svcs || die "compose build failed" 3
}

store_up() {  # the store only, so the schema is migrated before any service (re)starts
    say "docker compose -p $SAJAG_COMPOSE_PROJECT up -d postgis"
    sajag_compose up -d postgis || die "compose up (postgis) failed" 3
}

services_up() {  # every service, after migrate + seed (images already built by build_images)
    say "docker compose -p $SAJAG_COMPOSE_PROJECT up -d"
    sajag_compose up -d || die "compose up failed" 3
}

wait_postgis() {  # <timeout_s>
    local deadline=$(( $(date +%s) + $1 ))
    until [ "$(container_health "$POSTGIS_CONTAINER")" = healthy ]; do
        [ "$(date +%s)" -lt "$deadline" ] || die "PostGIS not healthy after $1 s" 3
        sleep 2
    done
}

migrate_python() {
    local p
    for p in "${SAJAG_MIGRATE_PY:-}" "$SAJAG_VENV_DIR/migrate/bin/python" "$SAJAG_ROOT/.venvs/migrate/bin/python"; do
        if [ -n "$p" ] && [ -x "$p" ] && "$p" -c 'import psycopg' 2>/dev/null; then echo "$p"; return; fi
    done
    say "building the migrate venv (psycopg only) at $SAJAG_ROOT/.venvs/migrate" >&2
    python3 -m venv "$SAJAG_ROOT/.venvs/migrate" >&2 \
        && "$SAJAG_ROOT/.venvs/migrate/bin/pip" install -q --disable-pip-version-check "psycopg[binary]>=3.2" >&2 \
        && echo "$SAJAG_ROOT/.venvs/migrate/bin/python"
}

run_migrations() {
    local py out rc
    py="$(migrate_python)" || die "no python with psycopg for scripts/migrate.py" 3
    say "migrations (ledgered, idempotent)"
    out="$(POSTGIS_CONTAINER="$POSTGIS_CONTAINER" VVIP_DATABASE_URL="$PG_DSN" \
        "$py" "$SAJAG_ROOT/scripts/migrate.py" 2>&1)" && rc=0 || rc=$?
    printf '%s\n' "$out" | sed 's/^/    /'
    [ "$rc" = 0 ] || die "migrate.py failed (exit $rc)" 3
}

apply_sql() {  # <file> — ONE transaction; the first error rolls it back (psql exit 3)
    # A file that opens its own transaction (a 'BEGIN;' line … 'COMMIT;') is
    # atomic by itself: wrapped in --single-transaction too, psql would warn
    # 'there is already a transaction in progress' and 'there is no
    # transaction in progress' on every apply. Any other file is wrapped.
    local one=--single-transaction
    grep -qix 'BEGIN;' "$1" && one=""
    docker exec -i "$POSTGIS_CONTAINER" psql -X -q -U corridor_admin -d corridor_db \
        ${one:+"$one"} -v ON_ERROR_STOP=1 < "$1" >/dev/null
}

NETWORK_CHANGED=0   # seed() applied the road network step in this bring-up
# …or an earlier bring-up did, and stopped (a later seed step failed) before
# the services that cache the network were restarted
NETWORK_RESTART_MARK="$SAJAG_RUN_DIR/seed/network_readers.restart"

seed() {
    local seed_sql="$SAJAG_ROOT/services/corridor-store/seed/sample_corridor.sql"
    local network_sql="$NETWORK_SQL"
    local post_sql="$SAJAG_ROOT/services/corridor-store/seed/post_seed_derivations.sql"
    local display_sql="$SAJAG_ROOT/services/corridor-store/seed/display_geometry_osm.sql"
    local network_stamp="$SAJAG_RUN_DIR/seed/reanchor_osm_network.sha256"
    local stamp="$SAJAG_RUN_DIR/seed/post_seed_derivations.sha256"
    local display_stamp="$SAJAG_RUN_DIR/seed/display_geometry_osm.sha256"
    local n fresh=0 network_applied=0 post_applied=0
    n="$(psql_q "select count(*) from corridor.road_segments")"
    [[ "$n" =~ ^[0-9]+$ ]] || die "cannot read corridor.road_segments" 3
    if [ "$n" = 0 ]; then
        say "empty corridor store — applying seed/sample_corridor.sql"
        apply_sql "$seed_sql" || die "seed failed" 3
        fresh=1
    else
        say "corridor store already seeded ($n segments)"
    fi
    # The road network ON OpenStreetMap (WP-20; ODbL): one idempotent,
    # single-transaction step that makes the store's network exactly the
    # generated one — completes a fresh seed (junctions 16+, names,
    # cameras, programs, stations) and converts an existing store in place
    # with every id preserved.  After the migrations (it needs 020) and
    # BEFORE the post-seed file, whose geometry rules then see the real
    # network.  A failure rolls back whole and stops the bring-up: the
    # services are built against this network.  Applied when the store is
    # fresh or the file changed (stamp) — and whenever the store is not on
    # the generated network (a read-only probe against the file's
    # network-probe line): the stamp is the run dir's, so a restored
    # pre-conversion backup would otherwise keep the schematic network.
    if [ -f "$network_sql" ]; then
        local nsha; nsha="$(sha256sum "$network_sql" | cut -d' ' -f1)"
        local net want stale=0
        net="$(network_probe)"; want="$(network_expected)"
        if [ "$fresh" != 1 ] && [ "$(cat "$network_stamp" 2>/dev/null || true)" = "$nsha" ] \
           && ! on_network "$net" "$want"; then
            say "the store is not on the generated road network ($(network_basis "$net"); the network has ${want% *} segments, ${want#* } junctions) — applying the network step whatever the stamp says"
            stale=1
        fi
        if [ "$fresh" = 1 ] || [ "$stale" = 1 ] \
           || [ "$(cat "$network_stamp" 2>/dev/null || true)" != "$nsha" ]; then
            say "applying seed/reanchor_osm_network.sql (${nsha:0:12})"
            apply_sql "$network_sql" || die "reanchor_osm_network.sql failed (rolled back — the store keeps its previous network)" 3
            mkdir -p "$(dirname "$network_stamp")" && echo "$nsha" > "$network_stamp"
            # until restart_network_readers has run (a later step may fail first)
            : > "$NETWORK_RESTART_MARK"
            network_applied=1
            NETWORK_CHANGED=1
            warn_open_event_routes
        fi
    fi
    # Idempotent post-seed data repairs (when present): after a fresh seed
    # or a network step, and again whenever the file changes.
    if [ -f "$post_sql" ]; then
        local sha; sha="$(sha256sum "$post_sql" | cut -d' ' -f1)"
        if [ "$fresh" = 1 ] || [ "$network_applied" = 1 ] \
           || [ "$(cat "$stamp" 2>/dev/null || true)" != "$sha" ]; then
            say "applying seed/post_seed_derivations.sql (${sha:0:12})"
            apply_sql "$post_sql" || die "post_seed_derivations.sql failed" 3
            mkdir -p "$(dirname "$stamp")" && echo "$sha" > "$stamp"
            post_applied=1
        fi
    fi
    # DISPLAY geometry (migration 015, contract C-K): superseded since the
    # routing geom IS the OpenStreetMap road — the file only clears a
    # display line a store still carries.  After the post-seed file, only
    # when the column exists, and again whenever the file or the network
    # changes.  Display only, so a failure here WARNS and the bring-up goes
    # on: the file is one transaction (nothing half-applied) and the
    # missing stamp makes the next bring-up try again.
    if [ -f "$display_sql" ]; then
        local has_col; has_col="$(psql_q "select count(*) from information_schema.columns where table_schema = 'corridor' and table_name = 'road_segments' and column_name = 'display_geom'")"
        if [ "$has_col" = 1 ]; then
            local dsha; dsha="$(sha256sum "$display_sql" | cut -d' ' -f1)"
            if [ "$fresh" = 1 ] || [ "$post_applied" = 1 ] \
               || [ "$(cat "$display_stamp" 2>/dev/null || true)" != "$dsha" ]; then
                say "applying seed/display_geometry_osm.sql (${dsha:0:12})"
                if apply_sql "$display_sql"; then
                    mkdir -p "$(dirname "$display_stamp")" && echo "$dsha" > "$display_stamp"
                else
                    rm -f "$display_stamp"
                    warn "seed/display_geometry_osm.sql failed and was rolled back — a stale display line may still be drawn (routing is unaffected); regenerate the seed files (scripts/gen_osm_network.py), and the next bring-up retries"
                fi
            fi
        else
            warn "corridor.road_segments has no display_geom column (migration 015 not ledgered) — road display geometry skipped; maps draw the schematic network"
        fi
    fi
}

warn_open_event_routes() {  # after a network step: open events whose current spine broke
    # Recorded routes are history and are never rewritten; an event still
    # open (planning / approved / active) whose current spine is no longer a
    # legal path (corridor.road_graph, one-ways included) must be re-planned
    # or closed by an officer. Read-only.
    local rows
    rows="$(psql_q "select count(*) || ' ' || coalesce(string_agg(distinct left(e.event_id::text, 8), ',' order by left(e.event_id::text, 8)), '') from events.event_routes r join events.corridor_events e on e.event_id = r.event_id where e.status in ('planning', 'approved', 'active') and r.superseded_at is null and exists (select 1 from generate_subscripts(r.segment_ids, 1) i where i < array_length(r.segment_ids, 1) and not exists (select 1 from corridor.road_graph g where g.source = r.segment_ids[i] and g.target = r.segment_ids[i + 1]))")" || rows=""
    [ -n "$rows" ] && [ "${rows%% *}" != 0 ] || return 0
    warn "${rows%% *} current route(s) of open events (${rows#* }) are no longer legal paths on the road network — re-plan those events or close them (recorded routes are history and are not rewritten)"
}

started_epoch() {  # <container> → its last start as epoch seconds ('' when unknown)
    local t; t="$(docker inspect -f '{{.State.StartedAt}}' "$1" 2>/dev/null)" || return 0
    date -u -d "$t" +%s 2>/dev/null || true
}

restart_network_readers() {  # after a network step in this bring-up (seed() sets NETWORK_CHANGED)
    # The services start after the migrations and the seed, but one that was
    # already running (and not recreated by services_up) may hold the previous
    # network in a cache — the traffic-oracle (segment names, geometry basis,
    # unit paths), the event-emulator (segment anchors and paths), the
    # command-deck (citizen facts). Each one started BEFORE the network step
    # (the mark's mtime) is restarted once; one started after it already read
    # the new network. Convergence below waits for them. A bring-up that
    # applied the step and then failed leaves the mark: the next one restarts
    # them.
    [ "$NETWORK_CHANGED" = 1 ] || [ -f "$NETWORK_RESTART_MARK" ] || return 0
    local c names=() step started
    step="$(stat -c %Y "$NETWORK_RESTART_MARK" 2>/dev/null || true)"
    for c in "$ORACLE_CONTAINER" "$EMULATOR_CONTAINER" "$DECK_CONTAINER"; do
        [ "$(container_status "$c")" != absent ] || continue
        started="$(started_epoch "$c")"
        if [ -n "$step" ] && [ -n "$started" ] && [ "$started" -gt "$step" ]; then continue; fi
        names+=("$c")
    done
    [ "${#names[@]}" -gt 0 ] || { rm -f "$NETWORK_RESTART_MARK"; return 0; }
    say "road network step applied — restarting ${names[*]} once (they may have cached the network as it was before it)"
    if docker restart "${names[@]}" >/dev/null; then
        rm -f "$NETWORK_RESTART_MARK"
    else
        warn "could not restart ${names[*]}: they may serve the previous network until restarted (docker restart ${names[*]}); the next bring-up retries"
    fi
}

start_models() {  # the units only: preflight refused already if they are not installed
    say "systemctl --user start sajag-models.target (decider cold load ≈5 min)"
    systemctl --user start --no-block sajag-models.target || die "could not start sajag-models.target" 3
}

warn_unpersisted() {  # compose-interpolated values that only this shell carries
    local key
    for key in "${SAJAG_PERSIST_KEYS[@]}"; do
        [ -n "${!key:-}" ] || continue
        grep -q "^$key=" "$SAJAG_ENV_FILE" 2>/dev/null && continue
        warn "$key is set in this shell but not in $SAJAG_ENV_FILE: a boot bring-up (sajag-up.service) would recreate the containers without it — persist it with scripts/sajag_env.sh --set $key - (value on stdin)"
    done
}

remediate() {  # one-shot fixes for states that do not heal by themselves
    # The emulator connects Valkey once at start-up; if it raced the
    # containers at boot it stays degraded until restarted.
    if [ "${STATE[emulator]:-}" = DEGRADED ] && [ -z "${REMEDIATED_EMULATOR:-}" ] \
       && [ "${STATE[valkey]:-}" = READY ] && [ "${STATE[postgis]:-}" = READY ] \
       && grep -Eq 'valkey|store' <<<"${DETAIL[emulator]}" \
       && [ "$(container_status "$EMULATOR_CONTAINER")" = running ]; then
        say "emulator started before its dependencies (${DETAIL[emulator]%% ·*}) — restarting it once"
        docker restart "$EMULATOR_CONTAINER" >/dev/null || true
        REMEDIATED_EMULATOR=1
    fi
}

converge() {  # <timeout_s>
    local deadline=$(( $(date +%s) + $1 )) last="" now c
    say "converging (timeout ${1}s)"
    while :; do
        run_checks
        all_ready && return 0
        if [ "$DECK_GATE_OPEN_ON_LAN" = 1 ]; then
            # a configuration fault, not a warm-up: waiting cannot fix it
            warn "the deck is reachable beyond loopback with the operator gate OFF — not converging (see the security row)"
            return 1
        fi
        now=""
        for c in $(gating); do [ "${STATE[$c]}" = READY ] || now="$now $c=${STATE[$c]}"; done
        [ "$now" != "$last" ] && say "waiting on:$now"
        last="$now"
        [ "$(date +%s)" -lt "$deadline" ] || return 1
        remediate
        sleep 5
    done
}

install_units() {
    if [ "$SAJAG_ENV_FILE" != "$UNIT_ENV_FILE" ] && [ ! "$SAJAG_ENV_FILE" -ef "$UNIT_ENV_FILE" ]; then
        die "SAJAG_ENV_FILE is $SAJAG_ENV_FILE, but the units read $UNIT_ENV_FILE — unset SAJAG_ENV_FILE (or point it at that file)"
    fi
    bash "$SAJAG_ROOT/scripts/sajag_env.sh" --write
    mkdir -p "$SYSTEMD_USER_DIR"
    local u f
    for f in "$SAJAG_ROOT"/infra/systemd/*.service "$SAJAG_ROOT"/infra/systemd/*.target; do
        [ -e "$f" ] || continue
        [[ " ${UNITS[*]} " == *" $(basename "$f") "* ]] \
            || die "infra/systemd/$(basename "$f") is not in UNITS (scripts/sajag_up.sh): it would never be linked"
    done
    for u in "${UNITS[@]}"; do
        [ -f "$SAJAG_ROOT/infra/systemd/$u" ] || die "missing unit file infra/systemd/$u"
        ln -sfn "$SAJAG_ROOT/infra/systemd/$u" "$SYSTEMD_USER_DIR/$u"
    done
    systemctl --user daemon-reload
    systemctl --user enable sajag.target
    say "linked ${#UNITS[@]} units from $SAJAG_ROOT/infra/systemd into $SYSTEMD_USER_DIR; sajag.target enabled"
    if [ "$(loginctl show-user "$(id -un)" -p Linger --value 2>/dev/null || echo no)" != yes ]; then
        warn "linger is off — units start only at login. Enable boot start: loginctl enable-linger $(id -un)"
    fi
    say "next: scripts/sajag_up.sh --retire-legacy   (first cutover from hand-launched processes)"
}

# ─── main ───────────────────────────────────────────────────────────────────

case "$MODE" in
    status)
        command -v docker >/dev/null || die "docker CLI not found"
        run_checks
        print_table
        if all_ready; then exit 0; else exit 1; fi
        ;;
    install)
        install_units
        exit 0
        ;;
    boot)
        say "boot bring-up (sajag-up.service): waiting for Docker"
        wait_docker 600
        ;;
esac

lock_bring_up
preflight
# The model units start first: once --retire-legacy has stopped the
# hand-launched hosts, a later build, compose or migrate failure must not
# leave the host without model servers; and the decider's cold load overlaps
# the compose bring-up. (--boot: sajag.target starts sajag-models.target.)
if [ "$NO_MODELS" != 1 ] && [ "$MODE" != boot ]; then start_models; fi
warn_unpersisted
apply_demo_mode
ensure_postgis_image
remove_stale_osint
# Order: images first (nothing recreated yet), then the store alone, the
# migrations and the seed, and only then the services — none of them ever
# (re)starts against a schema older than its code.
build_images
store_up
wait_postgis 180
run_migrations
seed
services_up
restart_network_readers

if converge "$TIMEOUT"; then
    print_table
    say "stack converged"
    exit 0
fi
print_table
warn "not converged after ${TIMEOUT}s — see DETAIL above; logs: docker logs <container>, journalctl --user -u sajag-<unit>"
exit 1
