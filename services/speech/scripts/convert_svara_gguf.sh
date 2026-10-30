#!/usr/bin/env bash
# Convert Svara-TTS v1 (kenpath/svara-tts-v1, Apache-2.0) to a Q8_0 GGUF for
# the llama.cpp TTS backend. Needs the HF snapshot in the local cache, the
# llama.cpp checkout and, in the Python used, transformers + sentencepiece +
# torch (the gguf package is taken from the checkout).
#
#   scripts/convert_svara_gguf.sh [out.gguf]
set -euo pipefail
LLAMA="${LLAMA_CPP_DIR:-$HOME/llama.cpp}"
OUT="${1:-$HOME/.cache/sajag/svara-gguf/svara-tts-v1-q8_0.gguf}"
PY="${PYTHON:-python3}"
SNAP=$("$PY" -c "from huggingface_hub import snapshot_download as s; print(s('kenpath/svara-tts-v1', allow_patterns=['*.json','*.jinja','*.safetensors']))")
mkdir -p "$(dirname "$OUT")"
PYTHONPATH="$LLAMA/gguf-py" "$PY" "$LLAMA/convert_hf_to_gguf.py" "$SNAP" --outtype q8_0 --outfile "$OUT"
echo "wrote $OUT"
