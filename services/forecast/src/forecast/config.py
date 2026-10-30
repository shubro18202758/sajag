"""Configuration — every value overridable by environment (prefix ``SAJAG_FORECAST_``), none secret.

Ports: production 8195 (``infra/compose.ai.yml``, loopback only). Developers run it on another port
with ``PORT``. The HTTP surface binds loopback by default: the deck reaches it through its own
same-origin proxy.

Data source (``SAJAG_FORECAST_DATA_SOURCE``):

* ``auto`` (default) — the traffic-oracle's history when it has enough of it for a segment, otherwise
  the deterministic synthetic Mumbai history (labelled SIMULATED), per segment;
* ``oracle`` — the oracle only; a segment without enough history is reported, not forecast;
* ``synthetic`` — the synthetic history only (offline demos, tests, backtests).

The oracle is only ever read (GET). Its base URL defaults to the production oracle on loopback; the
development sandbox oracle is ``http://127.0.0.1:8170``.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

__all__ = ["Settings", "get_settings", "DEFAULT_DECK_ORIGINS"]

DEFAULT_DECK_ORIGINS: tuple[str, ...] = (
    "http://127.0.0.1:5373",
    "http://localhost:5373",
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SAJAG_FORECAST_", extra="ignore")

    # ── HTTP surface ──────────────────────────────────────────────────────
    host: str = "127.0.0.1"
    port: int = 8195
    deck_origins: tuple[str, ...] = DEFAULT_DECK_ORIGINS

    # ── upstreams (read-only) ─────────────────────────────────────────────
    oracle_url: str = "http://127.0.0.1:8191"
    hydro_url: str = "http://127.0.0.1:8197"
    http_timeout_sec: float = 8.0
    data_source: Literal["auto", "oracle", "synthetic"] = "auto"
    #: a segment needs at least this many 15-min steps of oracle history (2 days) to be forecast from it
    min_oracle_steps: int = 192

    # ── city / network ────────────────────────────────────────────────────
    #: a city-pack folder holding ``network.json``; empty → the snapshot bundled with the package
    city_dir: str = ""
    #: (min_lon, min_lat, max_lon, max_lat) — cities/mumbai/city.json "bbox" (18.89–19.28 N, 72.77–72.99 E).
    #: Only segments the oracle serves INSIDE it are read from the oracle, so a store still seeded with
    #: another city's network (same ids, other roads) is never mistaken for Mumbai history.
    city_bbox: tuple[float, float, float, float] = (72.77, 18.89, 72.99, 19.28)

    # ── forecasting ───────────────────────────────────────────────────────
    model: Literal["chronos2", "timesfm", "naive"] = "chronos2"
    chronos_model_id: str = "amazon/chronos-2"
    timesfm_model_id: str = "google/timesfm-2.5-200m-pytorch"
    #: contender in the backtest ("" to skip it)
    contender: Literal["timesfm", ""] = "timesfm"
    device: Literal["auto", "cuda", "cpu"] = "auto"
    #: bf16 halves the weights' GPU memory; fp32 is the reference
    dtype: Literal["float32", "bfloat16"] = "float32"
    #: free the model after this many idle seconds
    idle_unload_sec: float = 600.0
    #: POST /admin/release (another on-demand service making room, or scripts/ai_warm.sh) frees a model
    #: unused for this long and not serving a forecast; it reloads on its next use
    release_idle_sec: float = 20.0
    context_days: int = 14
    step_min: int = 15
    default_horizon_min: int = 120
    vc_threshold: float = 0.8
    #: forecasts are recomputed on request when older than this
    cache_ttl_sec: float = 300.0

    # ── synthetic history ─────────────────────────────────────────────────
    #: a fixed, documented seed: 1853, the year the first passenger train in India ran from Bori Bunder
    #: (today's CSMT) to Thane
    synthetic_seed: int = 1853

    # ── backtest ──────────────────────────────────────────────────────────
    backtest_days: int = 3
    backtest_stride_hours: int = 6

    def resolved_city_dir(self) -> Path | None:
        if self.city_dir:
            p = Path(self.city_dir)
            return p if (p / "network.json").is_file() else None
        # the repo layout: services/forecast/src/forecast/config.py → repo/cities/mumbai
        here = Path(__file__).resolve()
        for parent in here.parents:
            cand = parent / "cities" / "mumbai"
            if (cand / "network.json").is_file():
                return cand
        return None


def get_settings() -> Settings:
    s = Settings()
    if os.environ.get("PORT"):
        s.port = int(os.environ["PORT"])
    if os.environ.get("HOST"):
        s.host = os.environ["HOST"]
    raw = os.environ.get("SAJAG_FORECAST_DECK_ORIGINS_CSV", "").strip()
    if raw:
        s.deck_origins = tuple(o.strip().rstrip("/") for o in raw.split(",") if o.strip())
    return s
