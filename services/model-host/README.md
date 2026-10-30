# model-host — T5 strategic tier (the decider)

Serves a decision model as typed questions (choice / noul / score) with
probability distributions. **Not** a chat model and **not** the jinja chat
template — decisions come from the readout head. Each checkpoint applies its
own calibrated temperature from its `decision_config.json`; it is never
overridden here.

Two checkpoint families sit behind the same C1 contract
(`src/model_host/decider_backends.py`):

| Runtime | Checkpoints | Protocol | Temperature | Weights (BF16) |
|---|---|---|---:|---:|
| `autojev` | pplx-decider-v1-27b (the default) | v1: one sequence per question, last-token readout | 2.2076 | 48.58 GiB |
| `pplx_decider` | pplx-decider-v1.2 (27B) | v3: one sequence per request, one readout per question marker, noncausal full attention | 1.382 | 48.6 GiB |
| `pplx_decider` | pplx-decider-flash-v1.2 (4B) | v3 | 1.554 | 8.5 GiB |

Selection (env wins over `sajag_models.yaml` `decider:`):

- `DECIDER_SNAPSHOT_PATH` / `snapshot_path` — the HF snapshot directory.
- `DECIDER_RUNTIME` / `runtime` — `auto` (default: read the snapshot layout:
  `source/src/pplx_decider` + `joint_config.json` → `pplx_decider`;
  `inference.py` + `source/src/autojev` → `autojev`), or name one; a name that
  contradicts the layout fails the load (reported by `/decider/health`).
- `DECIDER_QUESTION_MODE` / `question_mode` (protocol v3 only) — `auto`
  (default: `joint` for the 27B, `per_question` for flash, as their model
  cards recommend), `joint` (all questions of a request in one sequence: they
  see each other) or `per_question` (one sequence per question, still one
  batched forward pass).
- `DECIDER_MODEL_NAME` / `model_name` — the `/decider/health` `model` field;
  default: the snapshot's repository name.
- `DECIDER_FAST` / `fast` (protocol v3 only, default off) — the packed,
  compiled fast path; needs `flash-linear-attention` in the venv, else the
  reference path is served (logged).

## Run

```bash
# deployed: the systemd --user unit (Restart=always, under sajag-models.target)
systemctl --user status sajag-decider.service   # runs serve_models.sh --foreground decider
# by hand: the legacy bash supervisor, or the host directly
./infra/scripts/serve_models.sh start
PYTHONPATH=services/model-host/src \
  "$SAJAG_VENV_DIR"/model-host/bin/python -m model_host.app
```

`SAJAG_VENV_DIR` comes from `~/.config/sajag/sajag.env` (`scripts/sajag_env.sh`);
on this box it is still the retired tree's `models/.venvs` (the
`VVIP/models` symlink) — `scripts/sajag_env.sh` warns and names the
rebuild under `VVIP/.venvs`. Both runtimes use the same pins (torch 2.14.0,
transformers 5.17.0, safetensors 0.8.0, pillow 12.3.0, huggingface-hub
1.31.0); the checkpoint code is imported from the snapshot itself.

Cold load: ≈4 min for a 27B (48.6 GiB into the GB10 unified pool), ≈46 s
for flash. Bind: `127.0.0.1:8083` (fixed internal endpoint; env
`MODEL_HOST_BIND` / `MODEL_HOST_PORT` for tests). Config:
`models-config/configs/sajag_models.yaml` (decider section).

**Switching the decider:** `services/model-host/switch_decider.sh`
(`download`, `preflight`, `switch`, `check`, `rollback`). It writes the
optional `~/.config/sajag/decider.env`, which the unit reads after
`sajag.env`; removing it rolls back. Two 27B deciders cannot be resident
at once on this box: a 27B switch stops the old host first (the brain runs
Gemma-only while the new one loads).

**Load-path rule (C1):** the model is loaded via the HF snapshot *directory
path*. Every file there is a symlink into the blob store; a naive `cp -r`
produces dangling stubs. Never copy the tree.

## API (contract C1, identical for both runtimes)

- `GET /decider/health` → `{loaded, loading, load_error, resident_rss_gib,
  cuda_reserved_gib, p95_decide_latency_ms, queue_depth, decides_total,
  decides_failed, model, runtime, question_mode}`
- `POST /warmup` → waits for load, runs a warm decision (idempotent).
- `POST /decide` `{request_id?, state, questions:{name:{type, instructions,
  options?|scale?}}}` — ≤6 questions per call (422 beyond), typed only.
  Responses: `{request_id?, answers:{name:{value, probability, confidence,
  distribution}}, state_tokens, latency_ms}`.
  - `choice` → options: list[str] | dict[label→description] (≤249)
  - `noul` → P(true); confidence is `null` (the model emits none for noul)
  - `score` → scale: ≥2 level descriptions; value = expected level index
  - `state_tokens`: non-padding tokens of the forward pass(es); a joint
    request counts the state once, the per-question layouts once per question.
- Errors: `429` + `Retry-After: 5` when 8 requests are already queued
  (serialized compute — one forward at a time), `503` while loading or after
  a failed load, `413` when one question with its state exceeds the
  8192-token cap (no truncation by design), `422` on malformed questions.
- `GET /metrics` → Prometheus exposition (`model_host_*`).

This service makes **no outbound HTTP calls**; every endpoint it needs is a
fixed internal platform constant.

## Tests

```bash
cd services/model-host && "$GATE_PYTHON" -m pytest -q -p no:cacheprovider
```

`$GATE_PYTHON`: the gate interpreter the other Python services' suites use
(any Python with fastapi, httpx, PyYAML and pytest). Offline: fake
snapshots and a fake decider; no torch, no weights.

## Degradation contract

convoy-brain polls `/decider/health`; when `p95_decide_latency_ms` stays
above 3000 ms it falls back to Gemma-only tactical mode and alerts the
operator (audit-logged brain-side). Checkpoints are event-driven (≥5 s
apart) — never per GPS tick. The brain's confidence floor (0.45) was
calibrated on pplx-decider-v1-27b: re-measure it after a model switch
(`switch_decider.sh check` prints the per-question confidences).
