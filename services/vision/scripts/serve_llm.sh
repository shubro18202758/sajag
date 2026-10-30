#!/usr/bin/env bash
# Start/stop the Qwen3-VL-8B llama-server for the vision service (host side).
#
#   serve_llm.sh start [port]   # default 127.0.0.1:8201
#   serve_llm.sh stop  [port]
#   serve_llm.sh status [port]
#
# Loopback only. Refuses to start below the memory floor (the box is shared
# and a memory guard kills llama servers under 6 GiB available).
set -euo pipefail
PORT="${2:-${VISION_LLM_PORT:-8201}}"
BIN="${LLAMA_SERVER_BIN:-$HOME/llama.cpp/build/bin/llama-server}"
DIR="${VISION_MODEL_DIR:-$HOME/models/qwen3-vl-8b}"
MODEL="$DIR/Qwen3VL-8B-Instruct-Q4_K_M.gguf"
MMPROJ="$DIR/mmproj-Qwen3VL-8B-Instruct-F16.gguf"
PIDF="${XDG_RUNTIME_DIR:-/tmp}/sajag-vision-llm-$PORT.pid"
NEED_GIB=20   # ~7.6 GiB for the model + a 12 GiB floor

avail_gib() { awk '/MemAvailable/ {printf "%d", $2/1048576}' /proc/meminfo; }

case "${1:-}" in
  start)
    if [ -f "$PIDF" ] && kill -0 "$(cat "$PIDF")" 2>/dev/null; then echo "running (pid $(cat "$PIDF"))"; exit 0; fi
    for f in "$BIN" "$MODEL" "$MMPROJ"; do [ -e "$f" ] || { echo "missing: $f" >&2; exit 1; }; done
    [ "$(avail_gib)" -ge "$NEED_GIB" ] || { echo "refused: $(avail_gib) GiB available, need $NEED_GIB" >&2; exit 1; }
    nohup "$BIN" -m "$MODEL" --mmproj "$MMPROJ" --host 127.0.0.1 --port "$PORT" \
      -c 8192 -ngl 99 -np 1 --jinja --no-webui >/dev/null 2>&1 &
    echo $! > "$PIDF"
    for _ in $(seq 1 120); do
      curl -sf "http://127.0.0.1:$PORT/health" >/dev/null && { echo "ready on 127.0.0.1:$PORT"; exit 0; }
      sleep 1
    done
    echo "not healthy after 120 s" >&2; exit 1 ;;
  stop)
    [ -f "$PIDF" ] && kill "$(cat "$PIDF")" 2>/dev/null && rm -f "$PIDF" && echo stopped || echo "not running" ;;
  status)
    curl -sf "http://127.0.0.1:$PORT/health" && echo || echo "down" ;;
  *) echo "usage: $0 start|stop|status [port]" >&2; exit 2 ;;
esac
