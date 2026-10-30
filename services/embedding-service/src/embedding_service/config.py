"""Compile-time configuration for the embedding service.

Two classes of setting live here:

1. FIXED INTERNAL ENDPOINTS — http://127.0.0.1:{8081,8083,8084,8085} are
   platform constants (architecture contract C0/C8), overridable only via
   environment variables read at import time. They are NEVER taken from
   request payloads or other external input, which is what makes them
   eligible for the internal-host allowlist in ``security.py``.

2. MODEL / RETRIEVAL CONSTANTS — embedding dimensions, token-vector caps and
   hybrid-retrieval defaults from the architecture plan (T1 MEMORY, C3).

No credentials live here or anywhere in source: the database DSN is read
from the environment only (C12).
"""

from __future__ import annotations

import os

# ─── Fixed internal endpoints (platform compile-time constants, C0) ──────────
# Each may be overridden by env var at process start, never per-request.
EMBEDDING_SERVICE_URL = os.environ.get(
    "EMBEDDING_SERVICE_URL", "http://127.0.0.1:8085"
)
TRAFFIC_ORACLE_URL = os.environ.get(
    "TRAFFIC_ORACLE_URL", "http://127.0.0.1:8081"
)

# Hosts that fixed internal endpoints are allowed to point at. Only URLs
# constructed from the constants above may use these hosts; anything coming
# from external input is rejected outright regardless of host.
FIXED_INTERNAL_HOSTS: frozenset[str] = frozenset(
    {"127.0.0.1", "localhost", "host.docker.internal", "::1"}
)

# Default listen address for the service itself (host-mode gate, C8/C9).
LISTEN_HOST = os.environ.get("EMBEDDING_LISTEN_HOST", "127.0.0.1")
LISTEN_PORT = int(os.environ.get("EMBEDDING_LISTEN_PORT", "8085"))

# ─── Database (credentials env-only — no literals anywhere) ──────────────────
# Same DSN variable family the rest of the stack uses; see infra/compose.yml.
DATABASE_DSN_ENV_VARS = ("SAJAG_DATABASE_DSN", "VVIP_DATABASE_URL", "DATABASE_URL")


def database_dsn() -> str | None:
    """Return the Postgres DSN from the environment, or None if unset."""
    for var in DATABASE_DSN_ENV_VARS:
        value = os.environ.get(var)
        if value:
            return value
    return None


# ─── Models ───────────────────────────────────────────────────────────────────
# Primary late-interaction encoder: pplx-embed-v2-late (verified on this
# machine: MultiVectorEncoder, per-token 128-d vectors, MaxSim similarity).
LATE_MODEL_ID = os.environ.get(
    "LATE_EMBED_MODEL", "perplexity-ai/pplx-embed-v2-late-0.6b"
)
# bge-m3 local snapshot (verified: (N,1024) unit-norm): the fallback dense model.
DENSE_MODEL_PATH = os.environ.get("BGE_M3_PATH", os.path.expanduser("~/models/bge-m3"))

# The 9B aux embedder is a config slot, default OFF (architecture plan T1).
AUX_LATE_MODEL_ID = os.environ.get("AUX_LATE_EMBED_MODEL", "")

# ─── Embedding geometry (pplx-embed-v2-late contract) ────────────────────────
TOKEN_VEC_DIM = 128          # per-token vector width
DENSE_DIM = 1024             # traffic.memory_docs.dense_embedding is vector(1024)
MAX_TOKEN_VECS_PER_DOC = 64  # perf plan: 64 x 128 fp16 token-vecs/doc

# ─── Model registry (docs/ai/embeddings.md has the eval behind each entry) ───
# Every dense model writes ``store_dim`` floats into the vector(1024) column:
# a model wider than that is cut to its first ``store_dim`` values (a
# Matryoshka prefix the model was trained for) and renormalised. A model whose
# ``store_dim`` differs from DENSE_DIM cannot be configured without a store
# migration, and startup refuses it (``dense_spec``). Revisions pin the
# snapshot that was evaluated; ``trust_remote_code`` models run reviewed code
# from that pinned snapshot only (loaded offline, HF_HUB_OFFLINE=1).
DENSE_MODELS: dict[str, dict] = {
    "bge-m3": {
        "source": DENSE_MODEL_PATH, "revision": None, "family": "sentence_transformers",
        "dim": 1024, "store_dim": 1024, "dtype": "float32", "trust_remote_code": False,
        "licence": "MIT",
    },
    "pplx-embed-context-v1-4b": {
        "source": "perplexity-ai/pplx-embed-context-v1-4b",
        "revision": "679845b2236c653177fff8fa3ffc1b22f3090d30", "family": "contextual",
        "dim": 2560, "store_dim": 1024, "dtype": "bfloat16", "trust_remote_code": True,
        "licence": "MIT",
    },
    "pplx-embed-v1-4b": {
        "source": "perplexity-ai/pplx-embed-v1-4b",
        "revision": "06456497a00540a582918fe8dcd3a5eabb207772", "family": "sentence_transformers",
        "dim": 2560, "store_dim": 1024, "dtype": "bfloat16", "trust_remote_code": True,
        "licence": "MIT",
    },
    "pplx-embed-v1-0.6b": {
        "source": "perplexity-ai/pplx-embed-v1-0.6b",
        "revision": "2c4d510dd4a732063c31a0f70193e35067b51fd8", "family": "sentence_transformers",
        "dim": 1024, "store_dim": 1024, "dtype": "bfloat16", "trust_remote_code": True,
        "licence": "MIT",
    },
}
LATE_MODELS: dict[str, dict] = {
    "pplx-embed-v2-late-0.6b": {
        "source": "perplexity-ai/pplx-embed-v2-late-0.6b",
        "revision": "7bba8e7cf2075dec747fa8557f41eb90e70361ed", "dtype": "float32", "licence": "MIT",
    },
    "pplx-embed-v2-late-9b": {
        "source": "perplexity-ai/pplx-embed-v2-late-9b",
        "revision": "e6f9fd05b69356dec68b9b15443d3e963f3d2c09", "dtype": "bfloat16", "licence": "MIT",
    },
}
# The legacy memory corpus (every doc written before the registry existed)
# carries no model marker and was embedded by these two.
LEGACY_DENSE_MODEL = "bge-m3"
LEGACY_LATE_MODEL = "pplx-embed-v2-late-0.6b"

DEFAULT_DENSE_MODEL = "pplx-embed-context-v1-4b"  # eval: docs/ai/embeddings.md; fallback: bge-m3
DENSE_MODEL = os.environ.get("EMBED_DENSE_MODEL", DEFAULT_DENSE_MODEL)
# Late model: a registry key, or (backward compatible) the HF repo id that
# LATE_EMBED_MODEL used to carry.
LATE_MODEL = os.environ.get("EMBED_LATE_MODEL") or next(
    (k for k, v in LATE_MODELS.items() if v["source"] == LATE_MODEL_ID), LATE_MODEL_ID
)
EMBED_DEVICE = os.environ.get("EMBED_DEVICE", "cuda")

# /search ranking: "maxsim" (late-interaction score, the brain's calibrated
# scale; the default) or "fused" (per-query z-score fusion of the dense and
# MaxSim scores). ``score``/``maxsim_score`` keep their meaning either way.
RANK_MODE = os.environ.get("EMBED_RANK_MODE", "maxsim")
RANK_MODES: tuple[str, ...] = ("maxsim", "fused")

# Without a dense encoder (failed to load, out of memory) /search still
# answers: recall = the most recent docs of the requested kinds, reranked by
# MaxSim (``recall: "recent"`` in the response).
RECENT_RECALL_K = 100

# Read-only routes. /embed returns dense vectors (OSINT semantic dedup);
# /pii/spans runs PII-Tracer (OSINT defence-in-depth redaction).
MAX_EMBED_TEXTS = 64
MAX_EMBED_TEXT_CHARS = 2000
PII_ENABLED = os.environ.get("EMBED_PII", "1") not in ("0", "false", "no", "")


def dense_spec(name: str | None = None) -> dict:
    """The registry entry for a dense model; refuses names and widths the store cannot hold."""
    name = name or DENSE_MODEL
    if name not in DENSE_MODELS:
        raise ValueError(f"unknown dense model {name!r}; registry: {sorted(DENSE_MODELS)}")
    spec = dict(DENSE_MODELS[name], name=name)
    if spec["store_dim"] != DENSE_DIM:
        raise ValueError(
            f"dense model {name!r} stores {spec['store_dim']} dims but traffic.memory_docs."
            f"dense_embedding is vector({DENSE_DIM}); a store migration is needed first"
        )
    if spec["store_dim"] > spec["dim"]:
        raise ValueError(f"dense model {name!r}: store_dim exceeds the model's width")
    return spec


def late_spec(name: str | None = None) -> dict:
    name = name or LATE_MODEL
    if name not in LATE_MODELS:
        raise ValueError(f"unknown late model {name!r}; registry: {sorted(LATE_MODELS)}")
    return dict(LATE_MODELS[name], name=name)

# ─── Hybrid retrieval defaults (C3: dense ANN recall_k=100 -> MaxSim top-20) ─
DEFAULT_RECALL_K = 100
DEFAULT_TOP_K = 20
MAX_TOP_K = 50
MAX_BATCH_DOCS = 64          # encoder batch ceiling per /embed/documents call
MAX_BODY_CHARS = 8000        # truncate pathological documents before encoding

# ─── Kinds (the memory-side half of the leak guard; see README contract) ─────
MEMORY_DOC_KINDS: tuple[str, ...] = (
    "incident",
    "aar",
    "decision",
    "scenario_run",
    "pattern",
)
INCIDENT_KINDS: tuple[str, ...] = (
    "congestion_spike",
    "route_blockage",
    "signal_failure",
    "protest",
    "accident",
    "weather",
    "vvip_hold",
    "other",
)
INCIDENT_SEVERITIES: tuple[str, ...] = ("low", "medium", "high", "critical")
INCIDENT_SOURCES: tuple[str, ...] = ("live", "scenario_run", "import")
