# models-config — tracked, non-weight model-host files

Everything the host model stack needs that is *not* a model weight or a
virtualenv lives here, under version control. It replaces an untracked
symlink into a retired tree, which used to be load-bearing.

| File | Used by |
|---|---|
| `configs/sajag_models.yaml` | model-host (`SAJAG_MODELS_CONFIG`, exported by `infra/scripts/serve_models.sh`), smoke/drift scripts; single source of model-stack truth (C0) |
| `configs/flow_forecaster.yaml` | GAT forecaster hyper-parameters (documentation of the dormant DSTGAT rung) |
| `embedding_launcher.py` | `serve_models.sh` boots the embedding-service (:8205, `EMBEDDING_PORT`) through it: `embedding_service.service.build_lazy_app()`, models from the registry (`EMBED_DENSE_MODEL`, `EMBED_LATE_MODEL`; see `docs/ai/embeddings.md`) |
| `model-host-requirements.txt` | `serve_models.sh build` → `$SAJAG_VENV_DIR/model-host` |
| `MEMORY_BUDGET.md` | GB10 unified-memory budget (planned + measured) |
| `Modelfile.gemma_sajag` | optional ollama debug side-load of the Gemma GGUF |

The Tier-1 anomaly thresholds that used to sit in `models/configs/
anomaly_detector.yaml` now ship with the service that applies them:
`services/signal-ingress/config/anomaly_detector.yaml` (compiled into the
binary and installed in its image).

## What stays outside the repo (explicit host paths)

Weights and venvs are large and host-specific. `serve_models.sh` takes them
from environment variables, normally written once by
`scripts/sajag_env.sh --write` into `~/.config/sajag/sajag.env` (also the
`EnvironmentFile=` of the systemd units in `infra/systemd/`):

| Variable | What |
|---|---|
| `DECIDER_SNAPSHOT_PATH` | the decider's HF snapshot dir (48.6 GiB, never copied); `decider.env` (from `services/model-host/switch_decider.sh`) overrides it — the live box serves pplx-decider-v1.2 |
| `LLAMA_SERVER_BIN` | llama.cpp `llama-server` binary |
| `GEMMA_GGUF` | sajag-tactical Gemma 4 12B Q4_K_M GGUF |
| `BGE_M3_PATH` | bge-m3 snapshot (the fallback dense model; the deployed dense and late models load from the HF cache at pinned revisions) |
| `SAJAG_VENV_DIR` | root of the `model-host`, `embedding`, `migrate` venvs (default `<repo>/.venvs`; build with `serve_models.sh build`) |

`scripts/sajag_up.sh` refuses to start the model units when any of these
paths is missing, naming the variable to fix.
