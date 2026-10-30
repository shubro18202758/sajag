#!/usr/bin/env bash
# ai_warm.sh — warm an on-demand AI model just before a demo segment.
#
#   scripts/ai_warm.sh vision|speech|all
#
# 1. Asks the OTHER on-demand services to release their idle models (POST /admin/release on
#    loopback). Each releases only models unused for 20 s and not serving a request; a released
#    model reloads on its own next use.
# 2. Loads the asked one with real calls: a road-state reading of a bundled test still (vision), or
#    one spoken Marathi sentence (speech; it carries the time, so the audio cache cannot answer it
#    and the voice model really loads), then that sentence transcribed, which loads the Marathi ASR
#    a voice field report needs.
# 3. Reports how long that took and MemAvailable before and after.
#
# It never touches the resident models (decider, Gemma, embeddings) or any other process, drops no
# caches and needs no sudo. Exit status 0 when every asked model answered, 1 otherwise.
# Ports: SPEECH_PORT (8194), FORECAST_PORT (8195), VISION_PORT (8196); the still: AI_WARM_STILL.

set -uo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
SPEECH_PORT=${SPEECH_PORT:-8194}
FORECAST_PORT=${FORECAST_PORT:-8195}
VISION_PORT=${VISION_PORT:-8196}
STILL=${AI_WARM_STILL:-$ROOT/services/vision/tests/fixtures/jam_csmt.jpg}
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
FAILED=0

# JSON in and out (python3 -I: isolated, reads only the files named here)
cat > "$TMP/fmt.py" <<'PY'
import json
import sys

mode, rest = sys.argv[1], sys.argv[2:]
if mode == "body":  # the speak request
    print(json.dumps({"text": rest[0], "lang": "mr"}, ensure_ascii=False))
    sys.exit(0)
try:
    with open(rest[-1], encoding="utf-8") as fh:
        r = json.load(fh)
except Exception:
    print("no JSON answer")
    sys.exit(0)
if mode == "release":
    freed = ", ".join(r.get("released") or []) or "nothing"
    kept = "; ".join("%s (%s)" % (k.get("model"), k.get("why")) for k in r.get("kept") or [])
    print("  release %s: freed %s (~%s GiB)%s" % (rest[0], freed, r.get("freed_gib_estimate", 0),
                                                 "; kept " + kept if kept else ""))
elif mode == "state":
    print(r.get("state"))
elif mode == "text":
    print(str(r.get("text", ""))[:120])
else:  # detail of an error answer
    print(str(r.get("detail", ""))[:300])
PY
fmt() { python3 -I "$TMP/fmt.py" "$@"; }
mem() { awk '/^MemAvailable:/ {printf "%.1f", $2 / 1048576}' /proc/meminfo; }
now() { date +%s.%N; }
since() { awk -v a="$1" -v b="$(now)" 'BEGIN {printf "%.1f", b - a}'; }

release() {  # release <name> <port>
    local code
    code=$(curl -s -m 15 -o "$TMP/release.json" -w '%{http_code}' -X POST \
        "http://127.0.0.1:$2/admin/release") || code=000
    if [ "$code" != 200 ]; then
        echo "  release $1: no answer (HTTP $code)"
        return
    fi
    fmt release "$1" "$TMP/release.json"
}

warm_vision() {
    local before t0 code dt state
    if [ ! -f "$STILL" ]; then
        echo "vision: no test still at $STILL"
        FAILED=1
        return
    fi
    before=$(mem)
    t0=$(now)
    code=$(curl -s -m 300 -o "$TMP/vision.json" -w '%{http_code}' -X POST -H 'Content-Type: image/jpeg' \
        --data-binary @"$STILL" "http://127.0.0.1:$VISION_PORT/vision/road-state") || code=000
    dt=$(since "$t0")
    if [ "$code" = 200 ]; then
        state=$(fmt state "$TMP/vision.json")
        echo "vision: warm in ${dt} s (road state of $(basename "$STILL"): $state) · MemAvailable ${before} → $(mem) GiB"
    else
        echo "vision: NOT warm (HTTP $code after ${dt} s: $(fmt detail "$TMP/vision.json")) · MemAvailable $(mem) GiB"
        FAILED=1
    fi
}

warm_speech() {
    local before t0 code dt text body model
    text="सजग आवाज तयार आहे. वेळ $(date +%H:%M:%S)."
    body=$(fmt body "$text")
    before=$(mem)
    t0=$(now)
    code=$(curl -s -m 300 -o "$TMP/speech.out" -D "$TMP/speech.headers" -w '%{http_code}' -X POST \
        -H 'Content-Type: application/json' --data "$body" "http://127.0.0.1:$SPEECH_PORT/speech/speak") || code=000
    dt=$(since "$t0")
    if [ "$code" = 200 ]; then
        model=$(awk -F': ' 'tolower($1) == "x-speech-model" {sub(/\r$/, "", $2); print $2}' "$TMP/speech.headers")
        echo "speech: voice warm in ${dt} s (one Marathi sentence, $model) · MemAvailable ${before} → $(mem) GiB"
    else
        echo "speech: voice NOT warm (HTTP $code after ${dt} s: $(fmt detail "$TMP/speech.out")) · MemAvailable $(mem) GiB"
        FAILED=1
        return
    fi
    before=$(mem)
    t0=$(now)
    code=$(curl -s -m 300 -o "$TMP/asr.json" -w '%{http_code}' -X POST -H 'Content-Type: audio/wav' \
        --data-binary @"$TMP/speech.out" "http://127.0.0.1:$SPEECH_PORT/speech/transcribe?lang=mr") || code=000
    dt=$(since "$t0")
    if [ "$code" = 200 ]; then
        echo "speech: Marathi ASR warm in ${dt} s (heard: $(fmt text "$TMP/asr.json")) · MemAvailable ${before} → $(mem) GiB"
    else
        echo "speech: Marathi ASR NOT warm (HTTP $code after ${dt} s: $(fmt detail "$TMP/asr.json")) · MemAvailable $(mem) GiB"
        FAILED=1
    fi
}

target=${1:-}
case "$target" in
    vision|speech|all) ;;
    *) echo "usage: $0 vision|speech|all" >&2; exit 2 ;;
esac

echo "MemAvailable $(mem) GiB; releasing the other on-demand models that are idle (they reload on next use):"
case "$target" in
    vision) release forecast "$FORECAST_PORT"; release speech "$SPEECH_PORT" ;;
    speech) release forecast "$FORECAST_PORT"; release vision "$VISION_PORT" ;;
    all)    release forecast "$FORECAST_PORT"; release vision "$VISION_PORT"; release speech "$SPEECH_PORT" ;;
esac
case "$target" in
    vision) warm_vision ;;
    speech) warm_speech ;;
    all)    warm_vision; warm_speech ;;
esac
exit $FAILED
