"""Configuration — every value overridable by environment (prefix ``SAJAG_HYDRO_``), none secret.

Production port 8197 (``infra/compose.ai.yml``, loopback only); ``PORT`` / ``HOST`` override.

Open-Meteo needs no key. Calls are cached (``rain_cache_sec``) and rate-limited (at least
``min_call_interval_sec`` between calls, at most ``max_calls_per_day``) — far inside the free tier's
non-commercial limits. ``offline=1`` never calls out (tests, air-gapped boxes): rain is then UNAVAILABLE
and says so.
"""

from __future__ import annotations

import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

__all__ = ["Settings", "get_settings"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SAJAG_HYDRO_", extra="ignore")

    host: str = "127.0.0.1"
    port: int = 8197
    deck_origins: tuple[str, ...] = ("http://127.0.0.1:5373", "http://localhost:5373")

    open_meteo_forecast_url: str = "https://api.open-meteo.com/v1/forecast"
    open_meteo_archive_url: str = "https://archive-api.open-meteo.com/v1/archive"
    http_timeout_sec: float = 15.0
    rain_cache_sec: float = 600.0
    min_call_interval_sec: float = 30.0
    max_calls_per_day: int = 2000
    offline: bool = False

    #: a city-pack folder holding network.json (``SAJAG_HYDRO_CITY_DIR``); empty → ``cities/mumbai`` of the
    #: checkout, else the bundled snapshot
    city_dir: str = ""
    step_min: int = 15
    #: nowcast horizon (the lead time window)
    horizon_min: int = 120

    def resolved_city_dir(self) -> Path | None:
        if self.city_dir:
            p = Path(self.city_dir)
            return p if (p / "network.json").is_file() else None
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
    return s
