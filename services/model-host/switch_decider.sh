#!/usr/bin/env bash
# switch_decider.sh — move the strategic-tier decider (model-host, 127.0.0.1:8083)
# to a protocol v3 checkpoint, check it against the saved answers of
# pplx-decider-v1-27b, and roll back.
#
#   switch_decider.sh download  <v1.2|flash>                 fetch the pinned snapshot (HF cache)
#   switch_decider.sh verify    <v1.2|flash>                 sha256 every file against release-manifest.json
#   switch_decider.sh preflight <v1.2|flash>                 code merged, unit reads decider.env, memory, snapshot
#   switch_decider.sh switch    <v1.2|flash> [auto|joint|per_question]
#                                                            write decider.env, restart the unit, wait, verify
#   switch_decider.sh check                                  side-by-side eval vs the saved v1-27b answers
#   switch_decider.sh rollback                               remove decider.env, restart, wait, verify v1-27b
#   switch_decider.sh status                                 what is served now
#
# How the switch works: the unit (infra/systemd/sajag-decider.service)
# reads the optional ~/.config/sajag/decider.env AFTER sajag.env, so the
# DECIDER_SNAPSHOT_PATH / DECIDER_RUNTIME / DECIDER_QUESTION_MODE written
# there win; serve_models.sh passes them through. sajag.env (which holds
# secrets) is never read or edited here, except the SAJAG_ROOT and SAJAG_VENV_DIR lines (read only).
# Rollback = delete decider.env + restart.
#
# Memory: a 27B decider holds ~49 GiB of the GB10 unified pool; two cannot be
# resident together, so `switch v1.2` restarts in place (stop, then load):
# the strategic tier is down for the cold load (≈4 min; the brain degrades to
# Gemma-only and recovers by itself when /decider/health says loaded).
#
# Never run this while someone else is benchmarking the box.

set -euo pipefail

CONF_DIR="$HOME/.config/sajag"
# the tree the live unit runs: SAJAG_ROOT, else the SAJAG_ROOT line of sajag.env (what the unit reads),
# else the checkout this script is in
ROOT="${SAJAG_ROOT:-$( { sed -n 's/^SAJAG_ROOT=//p' "$CONF_DIR/sajag.env" 2>/dev/null || true; } | tail -1 | tr -d "\"'")}"
ROOT="${ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
DECIDER_ENV="$CONF_DIR/decider.env"
UNIT=sajag-decider.service
URL="${MODEL_HOST_URL:-http://127.0.0.1:8083}"
HUB="${HF_HUB_CACHE:-$HOME/.cache/huggingface/hub}"
EVAL_DIR="$ROOT/services/embedding-service/eval/decider"
REFERENCE=v1-27b-live            # results/v1-27b-live.json: answers of the live v1-27b (2026-10-28)
MIN_AVAILABLE_GIB=10

log()  { echo -e "\033[0;32m[switch_decider]\033[0m $*"; }
warn() { echo -e "\033[1;33m[switch_decider:WARN]\033[0m $*" >&2; }
die()  { echo -e "\033[0;31m[switch_decider:FAIL]\033[0m $*" >&2; exit 1; }

variant() {  # <v1.2|flash> → REPO REV NAME SIZE_GIB LOAD_S
    case "${1:-}" in
        v1.2|27b|pplx-decider-v1.2)
            REPO=perplexity-ai/pplx-decider-v1.2
            REV=cce0f3f80033e9d89d80831d5281fd72124aacce
            NAME=pplx-decider-v1.2; SIZE_GIB=48.6; LOAD_S=600 ;;
        flash|pplx-decider-flash-v1.2)
            REPO=perplexity-ai/pplx-decider-flash-v1.2
            REV=9ff7cf9838e59df461c276b7699d56b244d2af58
            NAME=pplx-decider-flash-v1.2; SIZE_GIB=8.5; LOAD_S=240 ;;
        *) die "variant must be v1.2 or flash (got '${1:-}')" ;;
    esac
    SNAP="$HUB/models--${REPO/\//--}/snapshots/$REV"
}

venv_python() {  # the model-host venv (huggingface-hub 1.31, the serving pins)
    local dir
    dir="$(sed -n 's/^SAJAG_VENV_DIR=//p' "$CONF_DIR/sajag.env" 2>/dev/null | tail -1 | tr -d "\"'")"
    dir="${SAJAG_VENV_DIR:-${dir:-$ROOT/.venvs}}"
    [ -x "$dir/model-host/bin/python" ] || die "model-host venv not found under $dir"
    echo "$dir/model-host/bin/python"
}

mem_available_gib() { awk '/^MemAvailable:/ {printf "%.1f", $2/1048576}' /proc/meminfo; }

health() { curl -sf --max-time 5 "$URL/decider/health" 2>/dev/null || echo '{}'; }

hfield() {  # <json> <key>
    python3 -c 'import json,sys; v=json.loads(sys.argv[1]).get(sys.argv[2]); print("" if v is None else v)' "$1" "$2"
}

wait_loaded() {  # <timeout_s> <expected model name>
    local deadline=$(( $(date +%s) + $1 )) h
    while [ "$(date +%s)" -lt "$deadline" ]; do
        h="$(health)"
        if [ "$(hfield "$h" loaded)" = "True" ]; then
            [ "$(hfield "$h" model)" = "$2" ] || die "loaded model is '$(hfield "$h" model)', expected '$2'"
            log "loaded: $h"
            return 0
        fi
        if [ -n "$(hfield "$h" load_error)" ]; then
            die "load failed: $(hfield "$h" load_error) — run: $0 rollback"
        fi
        sleep 5
    done
    die "not loaded after $1 s (last health: $(health)) — run: $0 rollback"
}

cmd_download() {
    variant "$1"
    local py t0; py="$(venv_python)"; t0=$(date +%s)
    log "downloading $REPO@$REV (~$SIZE_GIB GiB; ≈$(python3 -c "print(round($SIZE_GIB*1.074/0.020/60))") min at 20 MB/s)"
    # from an empty directory, isolated interpreter: nothing local is imported
    ( cd "$(mktemp -d)" && "$py" -I -c '
import sys, time
from huggingface_hub import snapshot_download
t = time.time()
p = snapshot_download(sys.argv[1], revision=sys.argv[2], max_workers=8)
print(f"downloaded to {p} in {time.time()-t:.0f}s")' "$REPO" "$REV" )
    [ -d "$SNAP" ] || die "snapshot dir missing after download: $SNAP"
    log "done in $(( $(date +%s) - t0 )) s"
    cmd_verify "$1"
}

cmd_verify() {
    variant "$1"
    [ -f "$SNAP/release-manifest.json" ] || die "no snapshot at $SNAP (run: $0 download $1)"
    log "verifying $SNAP against release-manifest.json (sha256; ~1 min per 10 GiB)"
    python3 -I - "$SNAP" <<'PY'
import hashlib, json, sys
from pathlib import Path
snap = Path(sys.argv[1])
files = json.loads((snap / "release-manifest.json").read_text())["files"]
bad = []
for name, meta in files.items():
    if name == "README.md":          # the model card is edited after release; not served
        continue
    want = meta["sha256"] if isinstance(meta, dict) else meta
    path = snap / name
    if not path.exists():
        bad.append(f"missing {name}")
        continue
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 24), b""):
            h.update(chunk)
    if h.hexdigest() != want:
        bad.append(f"sha256 mismatch {name}")
if bad:
    sys.exit("VERIFY FAILED: " + "; ".join(bad))
print(f"verified {len(files) - 1} files")
PY
}

cmd_preflight() {
    variant "$1"
    local ok=1 h cur avail need
    [ -d "$SNAP/source/src/pplx_decider" ] && [ -f "$SNAP/joint_config.json" ] \
        || { warn "snapshot incomplete or absent: $SNAP (run: $0 download $1)"; ok=0; }
    [ -f "$ROOT/services/model-host/src/model_host/decider_backends.py" ] \
        || { warn "$ROOT has no protocol v3 backend yet: merge the model-host change into the live tree first"; ok=0; }
    systemctl --user cat "$UNIT" 2>/dev/null | grep -q 'decider.env' \
        || { warn "$UNIT does not read decider.env yet: merge infra/systemd/sajag-decider.service, then: systemctl --user daemon-reload"; ok=0; }
    [ -f "$EVAL_DIR/results/$REFERENCE.json" ] \
        || { warn "saved reference answers missing: $EVAL_DIR/results/$REFERENCE.json (check would have nothing to compare)"; }
    h="$(health)"; cur="$(hfield "$h" cuda_reserved_gib)"; avail="$(mem_available_gib)"
    need=$(python3 -c "print(round($SIZE_GIB + 2.0, 1))")   # weights + working memory
    # the restart frees the current decider before the new one loads
    if python3 -c "import sys; sys.exit(0 if float('${avail:-0}') + float('${cur:-0}' or 0) - $need >= $MIN_AVAILABLE_GIB else 1)"; then
        log "memory: available ${avail} GiB + current decider ${cur:-0} GiB - new ~${need} GiB stays >= $MIN_AVAILABLE_GIB GiB"
    else
        warn "memory: available ${avail} GiB + current ${cur:-0} GiB - new ~${need} GiB would leave < $MIN_AVAILABLE_GIB GiB"
        ok=0
    fi
    [ "$ok" = 1 ] || die "preflight failed for $NAME"
    log "preflight OK for $NAME ($SNAP)"
}

cmd_switch() {
    variant "$1"
    local mode="${2:-auto}"
    case "$mode" in auto|joint|per_question) ;; *) die "question mode must be auto|joint|per_question" ;; esac
    cmd_preflight "$1"
    log "currently serving: $(hfield "$(health)" model)"
    ( umask 077
      cat > "$DECIDER_ENV.tmp" <<EOF
# written by services/model-host/switch_decider.sh on $(date -Is): $NAME
# remove this file and restart $UNIT to return to the sajag.env decider
DECIDER_SNAPSHOT_PATH=$SNAP
DECIDER_RUNTIME=pplx_decider
DECIDER_QUESTION_MODE=$mode
EOF
      mv "$DECIDER_ENV.tmp" "$DECIDER_ENV" )
    log "wrote $DECIDER_ENV; restarting $UNIT (strategic tier down until loaded)"
    systemctl --user restart "$UNIT"
    wait_loaded "$LOAD_S" "$NAME"
    [ "$(hfield "$(health)" runtime)" = "pplx_decider" ] || die "runtime is not pplx_decider"
    curl -sf --max-time 120 -X POST "$URL/warmup" >/dev/null || die "/warmup failed"
    log "switched to $NAME ($(hfield "$(health)" question_mode)); next: $0 check"
}

cmd_check() {
    local name stamp
    stamp="$(date +%Y%m%d-%H%M)"
    name="$(hfield "$(health)" model)-live-$stamp"
    [ "$(hfield "$(health)" loaded)" = "True" ] || die "decider not loaded"
    ( cd "$(mktemp -d)" && python3 -I "$EVAL_DIR/run_eval.py" --http "$URL" --name "$name" )
    ( cd "$(mktemp -d)" && python3 -I "$EVAL_DIR/compare.py" --ref "$REFERENCE" --cand "$name:served" \
        --out "post-switch-$stamp" )
    python3 -I - "$EVAL_DIR/results/post-switch-$stamp.json" "$name:served" <<'PY'
import json, sys
s = json.load(open(sys.argv[1]))
ref, cand = s["reference"], s["candidates"][sys.argv[2]]
vs = cand["vs_reference"]
hard, review = [], []
if cand.get("model") == s["reference"].get("model"):
    # the same checkpoint (e.g. right after merging a model-host change):
    # pplx-decider-v1-27b is bit-stable across runs, so any drift is a regression
    drift = {t: v.get("dp") for t, v in vs["by_type"].items() if v.get("dp")}
    if drift:
        hard.append(f"same model as the reference but answers moved: mean |dp| {drift}")
    else:
        print("same model as the reference: answers bit-identical to the saved run")
if cand["errors"]:
    hard.append(f"{cand['errors']} /decide errors")
if (cand["wall_ms_p95"] or 0) >= 3000:
    hard.append(f"wall p95 {cand['wall_ms_p95']} ms >= the brain's 3000 ms degrade line")
rc, rt = map(int, ref["accuracy_on_labelled"].split("/"))
cc, ct = map(int, cand["accuracy_on_labelled"].split("/"))
if ct and rt and cc / ct < (rc - 1) / rt:
    review.append(f"labelled accuracy {cc}/{ct} below reference {rc}/{rt} minus one: {cand['wrong_on_labelled']}")
tool = vs["by_question_set"].get("tool_selection/next_tool", {}).get("agree")
if tool is not None and tool < 0.9:
    review.append(f"tool selection agreement {tool} < 0.9")
choice = vs["by_type"].get("choice", {}).get("agree")
if choice is not None and choice < 0.8:
    review.append(f"choice agreement with v1-27b {choice} < 0.8 (a new model differs; read the disagreements)")
print(f"\nlow-confidence share at floor 0.45: reference {ref['low_confidence_gated_share']} -> "
      f"{cand['low_confidence_gated_share']} (re-measure VVIP_CONFIDENCE_FLOOR; see summary per question)")
for line in hard:
    print("FAIL  ", line)
for line in review:
    print("REVIEW", line)
if not hard and not review:
    print("PASS   no hard failure, no review flag")
sys.exit(1 if hard else 0)
PY
}

cmd_rollback() {
    if [ -f "$DECIDER_ENV" ]; then
        mv "$DECIDER_ENV" "$DECIDER_ENV.rolled-back-$(date +%Y%m%d-%H%M%S)"
        log "moved $DECIDER_ENV aside"
    else
        warn "no $DECIDER_ENV: the unit already serves the sajag.env decider"
    fi
    systemctl --user restart "$UNIT"
    wait_loaded 600 pplx-decider-v1-27b
    log "rolled back to pplx-decider-v1-27b; checking the probes against the saved answers"
    local stamp; stamp="$(date +%Y%m%d-%H%M)"
    ( cd "$(mktemp -d)" && python3 -I "$EVAL_DIR/run_eval.py" --http "$URL" --only probe \
        --name "rollback-$stamp" >/dev/null \
      && python3 -I "$EVAL_DIR/compare.py" --ref "$REFERENCE" --cand "rollback-$stamp:served" \
        --out "rollback-$stamp" | grep -E '^  (choice|noul|score)' ) \
        || warn "probe comparison did not run (the rollback itself succeeded)"
}

cmd_status() {
    local h; h="$(health)"
    echo "$h"
    if [ -f "$DECIDER_ENV" ]; then
        log "decider.env present:"; grep -v '^#' "$DECIDER_ENV"
    else
        log "no decider.env (the sajag.env decider)"
    fi
    log "MemAvailable $(mem_available_gib) GiB"
}

case "${1:-}" in
    download)  cmd_download "${2:-}" ;;
    verify)    cmd_verify "${2:-}" ;;
    preflight) cmd_preflight "${2:-}" ;;
    switch)    cmd_switch "${2:-}" "${3:-auto}" ;;
    check)     cmd_check ;;
    rollback)  cmd_rollback ;;
    status)    cmd_status ;;
    *) sed -n '2,13p' "$0"; exit 2 ;;
esac
