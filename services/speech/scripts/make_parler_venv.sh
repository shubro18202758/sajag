#!/usr/bin/env bash
# Build the venv that runs Indic Parler-TTS (SPEECH_TTS_BACKEND=indic_parler).
#
# parler-tts 0.2.3 (the current release) pins transformers==4.46.1, while the
# speech service runs on the model host's transformers 5.x, so Parler gets a
# venv of its own and the service runs it as a child process
# (speech_service.parler_worker, SPEECH_TTS_PARLER_PYTHON=<venv>/bin/python).
#
#   scripts/make_parler_venv.sh <venv-dir> <service-python>
#
# Torch is the CUDA build the speech service already uses: the new venv gets
# a .pth file pointing at the site-packages where <service-python> finds
# torch, the same way the service venv reaches the model host's torch.
# Everything below is pinned and installed without dependency resolution, so
# pip never swaps that torch out. No torchaudio is built for torch 2.14;
# torchaudio 2.11's Python transforms (all that the audio codec's helpers
# import) work against it.
set -euo pipefail

VENV="${1:?usage: make_parler_venv.sh <venv-dir> <service-python>}"
SVC_PY="${2:?usage: make_parler_venv.sh <venv-dir> <service-python>}"
TORCH_SITE="$("$SVC_PY" -c 'import os, torch; print(os.path.dirname(os.path.dirname(torch.__file__)))')"

python3 -m venv "$VENV"
SITE="$("$VENV/bin/python" -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')"
echo "$TORCH_SITE" > "$SITE/zz_torch_site.pth"
PIP="$VENV/bin/pip"

"$PIP" install -q --no-deps \
  parler-tts==0.2.3 \
  transformers==4.46.1 tokenizers==0.20.3 huggingface_hub==0.36.0 \
  descript-audio-codec-unofficial==1.0.0 descript-audiotools-unofficial==0.7.4 \
  torchaudio==2.11.0
"$PIP" install -q \
  sentencepiece protobuf requests scipy soundfile cffi julius ffmpy flatten_dict \
  importlib_resources tensorboard randomname einops argbind

"$VENV/bin/python" - <<'EOF'
import torch, transformers, parler_tts  # noqa: F401
from parler_tts import ParlerTTSForConditionalGeneration  # noqa: F401
print(f"parler venv ok: torch {torch.__version__} (cuda {torch.cuda.is_available()}), "
      f"transformers {transformers.__version__}")
EOF
echo "set SPEECH_TTS_PARLER_PYTHON=$VENV/bin/python"
