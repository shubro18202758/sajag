#!/usr/bin/env bash
# The gated preferred speech models: check access, then download them into
# the local Hugging Face cache (the service itself runs offline).
#
#   scripts/fetch_gated_models.sh check          # access status only; downloads nothing
#   scripts/fetch_gated_models.sh asr|tts|all    # download what access allows
#
#   ASR  ai4bharat/indic-conformer-600m-multilingual  (MIT)
#   TTS  ai4bharat/indic-parler-tts                   (Apache-2.0)
#        + the tokenizer of its text encoder (named in its config.json)
#
# Access is requested by the Hugging Face account owner on each model page
# (accepting AI4Bharat's terms); this script never tries to get around the
# gate. It uses the token the HF libraries already find (HF_TOKEN or
# ~/.cache/huggingface/token) and never prints it.
# Run it with a python that has huggingface_hub, e.g. PY=<service venv>/bin/python.
set -euo pipefail
PY="${PY:-python3}"
WHAT="${1:-check}"
case "$WHAT" in check|asr|tts|all) ;; *) echo "usage: $0 check|asr|tts|all" >&2; exit 2;; esac

exec "$PY" -I - "$WHAT" <<'EOF'
import json
import sys

from huggingface_hub import auth_check, snapshot_download
from huggingface_hub.errors import GatedRepoError, RepositoryNotFoundError

MODELS = {
    "asr": "ai4bharat/indic-conformer-600m-multilingual",
    "tts": "ai4bharat/indic-parler-tts",
}
what = sys.argv[1]
wanted = list(MODELS) if what in ("check", "all") else [what]
missing = 0
for job in wanted:
    repo = MODELS[job]
    try:
        auth_check(repo)
    except GatedRepoError:
        print(f"{job}: {repo}: gated: request access at https://huggingface.co/{repo}")
        missing += 1
        continue
    except RepositoryNotFoundError:
        print(f"{job}: {repo}: not found (or no access) on this account")
        missing += 1
        continue
    if what == "check":
        print(f"{job}: {repo}: access granted")
        continue
    path = snapshot_download(repo)
    rev = path.rstrip("/").rsplit("/", 1)[-1]
    print(f"{job}: {repo}: downloaded, commit {rev}")
    if job == "asr":
        print(f"     review {path}/model_onnx.py (trust_remote_code runs it), then pin it:")
        print(f"     SPEECH_ASR_INDIC_CONFORMER_REVISION={rev}")
    if job == "tts":
        cfg = json.load(open(f"{path}/config.json", encoding="utf-8"))
        enc = (cfg.get("text_encoder") or {}).get("_name_or_path")
        if enc:
            snapshot_download(enc, allow_patterns=["*.json", "*.model", "*.txt"])
            print(f"     description tokenizer {enc}: downloaded")
sys.exit(1 if missing else 0)
EOF
