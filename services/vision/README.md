# vision — road state from a camera still

A camera still goes in; a **road state** comes out, as a claim that waits for
an officer's confirmation:

```
waterlogged | blocked | tree_fall | stalled_vehicle | crash_debris | congested | clear | unknown
```

with a confidence, a rough vehicle count, a water-depth band when there is
water, and a rationale of at most 25 words. Every answer carries
`verification_state: "UNVERIFIED-CAMERA"` and `requires_confirmation: true`.
Nothing here raises an event, diverts traffic or publishes anything.

**Roads and vehicles only.** The service never describes people, never reads
number plates, and both rules are enforced in code (see [Ethics](#ethics)).

## API

| Method | Path | Body | Answer |
|---|---|---|---|
| GET | `/health` | — | service, model status (loaded or not), states, policy |
| POST | `/vision/road-state` | JPEG or PNG as the raw body (`Content-Type: image/jpeg`), or multipart field `image`; optional `?question=` | road state (below), `403` for a refused question, `415/422/413` for bad input, `503` when the model cannot run now |

```json
{
  "state": "waterlogged",
  "confidence": 0.98,
  "vehicles_estimate": {"cars": 0, "buses": 0, "two_wheelers": 0, "autos": 0},
  "water_depth_band": "up_to_wheel_hub",
  "rationale": "Road is flooded with water up to wheel hubs, no vehicles visible.",
  "model": "Qwen3-VL-8B-Instruct (Q4_K_M GGUF, llama.cpp)",
  "verification_state": "UNVERIFIED-CAMERA",
  "requires_confirmation": true,
  "label": "Camera still · AI reading · awaiting an officer's confirmation",
  "filtered": false,
  "image": {"width": 1024, "height": 682, "format": "jpeg", "resized": false, "metadata": "stripped"},
  "latency_s": 3.01
}
```

(An illustrative answer of the real model for a flooded street.)

- `water_depth_band` is judged against **wheels and kerbs**, never against a
  human body: `none | below_kerb | up_to_wheel_hub | above_wheel_hub | unknown`.
  It is present when the state is `waterlogged` or water is seen.
- `vehicles_estimate` is rough (cars include taxis; buses include trucks and
  vans; autos include e-rickshaws).
- `confidence` is the model's own number. It is **not calibrated**: the one
  miss in the evaluation came with 0.95.
- `question` (optional) lets an operator ask about the road ("is it passable
  for buses?"); the answer lands in the rationale. Person and plate questions
  are refused before the model is called.

## Model

| | |
|---|---|
| Model | **Qwen3-VL-8B-Instruct** (Alibaba Qwen), Apache-2.0 |
| Weights | `Qwen/Qwen3-VL-8B-Instruct-GGUF`: `Qwen3VL-8B-Instruct-Q4_K_M.gguf` (5.0 GB) + `mmproj-Qwen3VL-8B-Instruct-F16.gguf` (1.2 GB), in `~/models/qwen3-vl-8b/` |
| Runtime | llama.cpp `llama-server` (MIT), build 69bf643 with libmtmd (Qwen3-VL supported), all layers on the GB10 GPU, 8k context, one slot |
| Decoding | temperature 0, JSON-schema-constrained output (the state and band are enums; the only free text is the rationale) |
| Memory | 7.6 GiB GPU (measured with `nvidia-smi`) |
| Latency | ~3.0 s per image warm (0.5–0.7 s prompt incl. image, ~2.3 s generation); ~6 s for the first call including the server start |

The service starts its own llama-server on the first request
(`VISION_LLM_MANAGE=1`, the default) after checking MemAvailable, and stops it
after `VISION_IDLE_UNLOAD_S` (600 s) without a request, so the model costs no
memory while nobody looks at a camera. Below `need_gib + min_free_gib`
(8 + 8 GiB) it refuses to start, answers 503 and logs the reason; `GET /health`
then says `"status": "degraded"`, `"ready": false` with that reason
(`model.readiness`), so a check sees the outage before a camera call does.
With `VISION_LLM_MANAGE=0`
it uses an external server at `VISION_LLM_URL` instead (the compose layout;
start it with `scripts/serve_llm.sh start`).

## Ethics

Enforced in code and tested (`tests/test_ethics.py`, `tests/test_api.py`):

1. **System prompt** (`model.py`): road surface and vehicles only; never
   describe, count or mention people (faces, bodies, clothing, gender, age,
   ethnicity, religion, identity); never read number plates; judge water
   against wheels and kerbs.
2. **Query screen** (`ethics.screen_query`): a person-centric question
   ("who is in this image", "how old is the man", "ছবিতে কে আছে?", "इस फोटो में
   कौन है?") is refused with `403 {"refused": true, "policy":
   "vehicles-and-roads-only"}` and the image never reaches the model. A plate
   question is refused with `policy: "no-plate-reading"`: plates go only
   through the existing ANPR path, masked until a named officer is on duty.
3. **Output filter** (`ethics.scrub`): every sentence of the model's text
   that mentions a person at all (about 180 English terms: people, gender, age,
   clothing, faces, ethnicity, religion, roles such as driver or vendor) is
   dropped; if nothing is left, a neutral sentence for the road state takes
   its place. `filtered: true` says when this happened.
4. **No storage.** Images are processed in memory, re-encoded (which strips
   EXIF, including GPS) and dropped when the request ends. No logs of image
   content.

What the filter is for, measured on the real model: asked *without* the
house prompt to "describe this street scene, including any people", Qwen3-VL
described the people in all 4 test images it was asked about ("one person
near the center is wearing a dark green raincoat…"); after `scrub` none of the 4 texts mentions a
person. With the house prompt the model never mentioned a person in the 12
evaluation answers (the filter did not have to act).

## Evaluation

12 public road photos (10 Mumbai: flooded junctions at JVPD and on an arterial
in 2017 and 2005, rain-hour and evening jams near CSMT, fallen trees in
Borivali and on Old Prabhadevi Road after Cyclone Tauktae, an open
Western Express Highway and Amar Mahal, a bus stuck at the WEH flyover in
Borivali; 2 generic: a flooded UK underpass standing in for Mumbai's subways
and a broken-down London bus), faces and legible plates pixelated by us;
credits in [`tests/fixtures/NOTICE.md`](tests/fixtures/NOTICE.md). Run against
the real model on 30 Oct 2026 (`eval/run_eval.py`, raw answers in
[`eval/results.json`](eval/results.json)):

| expected ↓ / model → | waterlogged | tree_fall | stalled_vehicle | congested | clear |
|---|---|---|---|---|---|
| waterlogged (4) | **4** | | | | |
| tree_fall (2) | | **2** | | | |
| stalled_vehicle (2) | | | **1** | | 1 |
| congested (2) | | | | **2** | |
| clear (2) | | | | | **2** |

**11 / 12 correct** (warm median 5.1 s per image, first call 36 s with the
model load). The miss: a London bus stopped across a junction with marshals
around it was read as `clear` (the model saw a bus on a dry road and no
obstruction); the Mumbai bus stuck at Borivali with its warning triangle out
was read correctly. Refusal probes: **11 / 11** (8 person or plate questions
in English, Marathi and Hindi refused; 3 road questions, one in Marathi,
answered). With the house prompt the model never mentioned a person in the
12 answers (the filter did not have to act); asked without it to describe the
people too, it did so in all 4 images that have them, and after `scrub` none
of the 4 texts mentions a person. Twelve images is a smoke test, not an
accuracy claim; `blocked` and `crash_debris` have no test image yet, and no
photo of a flooded Mumbai subway on Commons was found to replace the UK one.

## Run

```bash
# dev (port 9162, managed llama-server on 9163)
PYTHONPATH=src VISION_PORT=9162 VISION_LLM_PORT=9163 python -m vision_service
curl -s -X POST -H 'Content-Type: image/jpeg' --data-binary @tests/fixtures/jam_csmt.jpg \
     127.0.0.1:9162/vision/road-state
```

Production: port **8196**, loopback only (`infra/compose.ai-media.yml`,
`infra/docker/Dockerfile.vision`). The image holds only the HTTP service; the
model server runs on the host (`scripts/serve_llm.sh start`, 127.0.0.1:8201).

## Configuration

Environment variables (prefix `VISION_`, see `config.py`): `VISION_HOST` /
`VISION_PORT` (127.0.0.1 / 8196), `VISION_LLM_MANAGE` (1: start our own
llama-server; 0: use `VISION_LLM_URL`), `VISION_LLM_PORT` (8201),
`VISION_MODEL_PATH` / `VISION_MMPROJ_PATH` / `VISION_LLAMA_SERVER_BIN`,
`VISION_IDLE_UNLOAD_S` (600), `VISION_NEED_GIB` (8) and `VISION_MIN_FREE_GIB`
(12), `VISION_MAX_IMAGE_BYTES` (12 MB), `VISION_MAX_SIDE` (1024 px),
`VISION_DECK_ORIGINS` (empty: the deck proxies).

## Tests

```bash
python -m pytest -q -p no:cacheprovider                 # offline, model mocked
VISION_SLOW=1 python -m pytest -q -m slow                # real model (≈7.6 GiB, ~30 s)
```

## Limits

- Twelve test images; no `blocked` or `crash_debris` example; three images
  are from the UK. Real junction CCTV (night, rain on the lens, low angle,
  compression) will be harder.
- Self-reported confidence is not calibrated.
- One frame, no time: a bus stopped at a signal and a broken-down bus look
  alike in a single still.
- The person filter is English word lists (the model is told to answer in
  English); it is deliberately over-eager (it also drops sentences that say
  "uniform" or "worn").
