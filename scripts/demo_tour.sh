#!/usr/bin/env bash
# demo_tour.sh — the capability tour's states on the live Sajag stack.
#
# Usage:
#   bash scripts/demo_tour.sh list                                  the catalogue (no network)
#   bash scripts/demo_tour.sh status [cap ...]                      GET-only: what is on the board now
#   bash scripts/demo_tour.sh seed <cap|all> ...                    dry-run (default): the plan, GET-only
#   bash scripts/demo_tour.sh --apply --officer '<name>' seed <cap|all> ...
#                                                                   stage it, as that named officer
#   bash scripts/demo_tour.sh [--apply --officer '<name>'] reset    stop the runs THIS tour started
#
# Order on the day: scripts/demo_reset.sh --apply first (the evening: the visarjan night at Girgaon
# Chowpatty, the monsoon burst at high tide, the stolen-vehicle sweep), then demo_tour.sh seed <cap> for the rest. demo_reset.sh
# stops other emulator runs, so a later reset clears the tour's runs too.
#
# --apply signs in through scripts/deck_session.sh as --officer (every write is recorded under that
# name); it never approves, rejects, dispatches, earmarks, promotes, starts an escort or writes a
# signal plan: those are the named officer's presses on camera. The logic is scripts/demo_tour.py.
# The PIN and the session cookie are never printed.

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APPLY=0 OFFICER=""
ARGS=()
while [ $# -gt 0 ]; do
    case "$1" in
        --apply) APPLY=1 ;;
        --officer) OFFICER="${2:-}"; [ $# -gt 1 ] && shift ;;
        --officer=*) OFFICER="${1#--officer=}" ;;
        -h|--help) awk '/^# Usage:/ { p = 1 } /^# Order on the day/ { exit } p { sub(/^# ?/, ""); print }' "${BASH_SOURCE[0]}"; exit 0 ;;
        *) ARGS+=("$1") ;;
    esac
    shift
done
[ ${#ARGS[@]} -gt 0 ] || { echo "demo_tour: a command is needed (list, status, seed, reset)" >&2; exit 2; }

DECK_URL="${DECK_URL:-http://127.0.0.1:5373}"
DECK_GATE="" DECK_COOKIE_JAR=""
if [ "$APPLY" = 1 ]; then
    case "${ARGS[0]}" in seed|reset) ;; *) echo "demo_tour: --apply is for seed and reset only" >&2; exit 2 ;; esac
    if [ -z "$OFFICER" ]; then
        echo "demo_tour: --apply needs --officer '<the named officer>'" >&2
        exit 2
    fi
    # shellcheck source=scripts/deck_session.sh
    . "$ROOT/scripts/deck_session.sh"
    trap deck_signout EXIT          # revokes the session and removes the cookie jar, on every exit
    deck_signin "$DECK_URL" "$OFFICER" || exit 2
    if [ "$DECK_GATE" != on ]; then
        echo "demo_tour: REFUSED: the deck's operator gate is off — the demo deck runs with SAJAG_OPERATOR_PIN set" >&2
        exit 2
    fi
    echo "[demo-tour] signed in at $DECK_URL as the named officer '$OFFICER'"
fi

DT_APPLY="$APPLY" DT_OFFICER="$OFFICER" DT_COOKIE_JAR="${DECK_COOKIE_JAR:-}" DT_GATE="${DECK_GATE:-}" \
    python3 "$ROOT/scripts/demo_tour.py" "${ARGS[@]}"
