"""Configuration for the vision service (environment prefix ``VISION_``).

The service binds loopback (production port 8196). The vision-language model
runs in a llama.cpp ``llama-server`` with the Qwen3-VL projector loaded:

* ``VISION_LLM_MANAGE=1`` (default): the service starts its own
  llama-server on ``VISION_LLM_PORT`` at the first request, after checking
  MemAvailable, and stops it after ``VISION_IDLE_UNLOAD_S`` idle seconds.
* ``VISION_LLM_MANAGE=0``: it talks to an already-running server at
  ``VISION_LLM_URL`` (the compose layout, where the host runs the model).

Weights live in ``~/models/qwen3-vl-8b/`` on the GB10 host.

A start that would break the memory floor first makes room (``memroom.py``):
the other on-demand services (forecast, then speech) are asked on loopback to
release their idle models, and the same floor is checked again. Released
models reload on their next use.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

__all__ = ["Settings", "get_settings"]

_MODELS = Path.home() / "models" / "qwen3-vl-8b"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="VISION_", extra="ignore")

    host: str = "127.0.0.1"
    port: int = 8196
    deck_origins: str = ""

    # llama-server (Qwen3-VL-8B-Instruct GGUF + mmproj)
    llm_manage: bool = True
    llm_url: str = "http://127.0.0.1:8201"
    llm_port: int = 8201
    llama_server_bin: Path = Path.home() / "llama.cpp" / "build" / "bin" / "llama-server"
    model_path: Path = _MODELS / "Qwen3VL-8B-Instruct-Q4_K_M.gguf"
    mmproj_path: Path = _MODELS / "mmproj-Qwen3VL-8B-Instruct-F16.gguf"
    model_name: str = "Qwen3-VL-8B-Instruct (Q4_K_M GGUF, llama.cpp)"
    ctx_size: int = 8192
    gpu_layers: int = 99
    llm_start_timeout_s: float = 240.0
    # llama-server's own output (truncated at every start); its last lines go into last_error on a failed start
    llm_log_path: Path = Path.home() / ".cache" / "sajag" / "vision-llama-server.log"
    # a start that dies early (a transient allocation failure while another model loads) is tried once more
    llm_start_attempts: int = 2
    llm_request_timeout_s: float = 180.0

    idle_unload_s: int = 600
    # Q4_K_M weights + F16 projector + KV cache ≈ 7.5 GiB; keep a floor on top. The box's memory
    # guard evicts llama servers under 6 GiB available, so 8 GiB left after the load keeps 2 GiB clear.
    need_gib: float = 8.0
    min_free_gib: float = 8.0

    # making room (memroom.py; docs/ai/vision.md "Making room"): before refusing a start, ask the
    # other on-demand services on loopback to release their idle models. Port 0 skips a peer.
    make_room: bool = True
    peer_forecast_port: int = 8195
    peer_speech_port: int = 8194
    # POST /admin/release called by hand keeps a model used within this many seconds (and one serving
    # a request)
    release_idle_s: float = 20.0
    # making room for a waiting start has priority: the peers release every model not serving a
    # request right now, however recently used; it reloads on its next use
    make_room_idle_s: float = 0.0
    make_room_timeout_s: float = 2.0   # per peer call
    make_room_wait_s: float = 5.0      # MemAvailable is polled this long after a release

    max_image_bytes: int = 12 * 1024 * 1024
    max_side: int = 1024


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
