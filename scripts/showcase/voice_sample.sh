#!/usr/bin/env bash
# showcase/voice_sample.sh — the voice-report shot's microphone input: one Marathi field report, spoken by the
# speech service's own TTS (a synthetic voice) and saved as a WAV that console_shots.mjs plays into Chrome's fake
# microphone (--fake-audio). Compute only: POST /speech/speak writes nothing.
#
#   bash scripts/showcase/voice_sample.sh [out.wav]
#   node scripts/showcase/console_shots.mjs --only voice-report --fake-audio out.wav
set -euo pipefail
OUT="${1:-${TMPDIR:-/tmp}/sajag-voice-report.wav}"
SPEECH_URL="${SPEECH_URL:-http://127.0.0.1:${SPEECH_PORT:-8194}}"
# "Knee-deep water on Bidhan Sarani at Thanthania, a bus is stuck."
TEXT='ঠনঠনিয়ায় বিধান সরণিতে হাঁটু জল, একটা বাস আটকে আছে।'
python3 - "$SPEECH_URL" "$TEXT" "$OUT" <<'PYEOF'
import json, sys, urllib.request
url, text, out = sys.argv[1:4]
req = urllib.request.Request(url + "/speech/speak", data=json.dumps({"text": text, "lang": "mr", "voice": "male"}).encode(),
                             headers={"Content-Type": "application/json"})
with urllib.request.urlopen(req, timeout=240) as r:
    body = r.read()
if body[:4] != b"RIFF":
    sys.exit(f"speech service answered no WAV ({len(body)} bytes)")
open(out, "wb").write(body)
print(out)
PYEOF
