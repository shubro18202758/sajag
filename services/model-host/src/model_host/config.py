"""Configuration loader for model-host.

Reads models-config/configs/sajag_models.yaml (models-stream-owned, C0) and
applies environment overrides. All outbound endpoints used anywhere in this
service are fixed config constants (see sajag_models.yaml `services:`); this
service itself makes NO outbound HTTP calls at all — it only serves.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

# Repo root = four levels above this file (services/model-host/src/model_host/config.py)
REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_CONFIG = REPO_ROOT / "models-config" / "configs" / "sajag_models.yaml"


def _env_or(name: str, fallback: Any) -> Any:
    value = os.environ.get(name)
    return fallback if value is None or value.strip() == "" else value


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"config not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


class Settings:
    """Typed view over sajag_models.yaml + env overrides for model-host."""

    def __init__(self, config_path: str | Path | None = None) -> None:
        cfg_path = Path(config_path or os.environ.get("SAJAG_MODELS_CONFIG", DEFAULT_CONFIG))
        cfg = _load_yaml(cfg_path)
        dec = cfg.get("decider", {})
        svc = cfg.get("services", {})

        self.host = os.environ.get("MODEL_HOST_BIND", "127.0.0.1")
        self.port = int(os.environ.get("MODEL_HOST_PORT", "8083"))
        # snapshot path: env wins, then yaml, then hard fail (the weights
        # must come from the verified on-disk snapshot, never a copy)
        snapshot = os.environ.get("DECIDER_SNAPSHOT_PATH", dec.get("snapshot_path", ""))
        if not str(snapshot or "").strip():
            raise ValueError("decider.snapshot_path missing in sajag_models.yaml")
        self.snapshot_path = Path(snapshot).expanduser()  # the yaml may write the HF cache as ~/.cache/…
        # Backend: auto (from the snapshot layout) | autojev (protocol v1,
        # pplx-decider-v1-27b) | pplx_decider (protocol v3 joint checkpoints).
        self.runtime = str(_env_or("DECIDER_RUNTIME", dec.get("runtime") or "auto")).strip().lower()
        # Protocol v3 only: auto (joint for the 27B, per_question for flash,
        # per the model cards) | joint | per_question.
        self.question_mode = str(
            _env_or("DECIDER_QUESTION_MODE", dec.get("question_mode") or "auto")
        ).strip().lower()
        # Protocol v3 packed fast path (needs flash-linear-attention); the
        # reference path is the default and the evaluated computation (the
        # fast path measured slower for single small requests on the GB10).
        self.fast = _truthy(_env_or("DECIDER_FAST", dec.get("fast") or False))
        # /decider/health "model": explicit name, else the snapshot's repo name
        from .decider_backends import model_name_from_snapshot

        self.model_name = str(
            _env_or("DECIDER_MODEL_NAME", dec.get("model_name") or "")
            or model_name_from_snapshot(self.snapshot_path)
        )
        self.device = dec.get("device", "cuda")
        self.offline = bool(dec.get("offline", True))
        self.max_questions = int(dec.get("max_questions_per_request", 6))
        self.max_state_tokens = int(dec.get("max_state_tokens", 8192))
        self.queue_depth = int(dec.get("queue_depth", 8))
        # p95 window for /decider/health (latency samples retained)
        self.latency_window = int(dec.get("latency_window_samples", 128))

        # Fixed internal endpoints of the platform (not user-supplied URLs).
        # Kept here for readiness reporting only; model-host never calls out.
        self.llama_url = os.environ.get("LLAMA_BASE_URL", svc.get("llama", "http://127.0.0.1:8084"))
        self.embedding_url = os.environ.get(
            "EMBEDDING_SERVICE_URL", svc.get("embedding", "http://127.0.0.1:8085")
        )


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
