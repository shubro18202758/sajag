"""Service configuration (environment only; the service reads no secret and needs none).

Contract (OS-2 → OS-INT)::

    OSINT_ORACLE_URL   http://127.0.0.1:9      loopback only (127.0.0.1, localhost, ::1); unset = the discard port
    HOST               127.0.0.1
    PORT               8193
    OSINT_CACHE_DIR    /var/cache/osint-ingress
    OSINT_MODE         live | offline          offline: no source egress, parse the newest cache entry
    OSINT_GAZETTEER_PATH                       the X19 place gazetteer (else repo-rooted, else the image path)
    OSINT_CADENCE_<CONNECTOR>_SEC              e.g. OSINT_CADENCE_SACHET_CAP_SEC=300; 0 takes it off the schedule

The oracle has NO usable default (F-CONN-09): unset, ``OSINT_ORACLE_URL`` is :data:`UNSET_ORACLE_URL`, the
loopback discard port, which refuses at once, so a CLI run or a test that forgets to name its oracle posts
nowhere (its batches wait in the outbox) instead of into the live oracle. The deployment names its oracle
explicitly (``infra/compose.osint-ingress.yml``), as the image already did (``Dockerfile.osint-ingress``).

Cadences below 60 s are raised to 60 s (the sources ask for polite polling; GDELT DOC is additionally spaced
≥ 5 s per request inside its connector). Common Crawl is a backfill: never scheduled, whatever its cadence says.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from osint_ingress import __version__
from osint_ingress.safe_http import check_oracle_url

__all__ = [
    "CONNECTOR_NAMES",
    "DEFAULT_CADENCE_SEC",
    "MIN_CADENCE_SEC",
    "Settings",
    "UNSET_ORACLE_URL",
    "USER_AGENT",
    "cadences_from_env",
]

#: Every connector, keyed by its ``RawOsintSignal.source`` (one connector per source).
CONNECTOR_NAMES: tuple[str, ...] = (
    "sachet_cap",
    "imd",
    "google_news_rss",
    "news_rss",
    "gdelt_events",
    "gdelt_doc",
    "reddit_rss",
    "kmc_scrape",
    "wbsdma",
    "mumbai_police_scrape",
    "common_crawl",
)

#: Schedule (seconds): SACHET 5 min, IMD and Google News 10 min, the outlets' feeds, GDELT bulk and Reddit 15 min,
#: GDELT DOC 30 min (it throttles this box; a throttle backs it off further, see ``runner.Backoff``), official pages
#: hourly, Common Crawl off (backfill only, `once --backfill`).
DEFAULT_CADENCE_SEC: Mapping[str, int] = {
    "sachet_cap": 300,
    "imd": 600,
    "google_news_rss": 600,
    "news_rss": 900,
    "gdelt_events": 900,
    "gdelt_doc": 1800,
    "reddit_rss": 900,
    "kmc_scrape": 3600,
    "wbsdma": 3600,
    "mumbai_police_scrape": 3600,
    "common_crawl": 0,
}

MIN_CADENCE_SEC = 60

#: The oracle URL when none is configured: the loopback discard port (nothing listens; a post fails at once and
#: stays in the outbox). Never a live oracle (F-CONN-09).
UNSET_ORACLE_URL = "http://127.0.0.1:9"

#: Names the project, never a person or a personal contact address.
USER_AGENT = f"sajag-osint-ingress/{__version__} (Sajag corridor operations, Mumbai; open-source civic research)"


def cadences_from_env(env: Mapping[str, str] | None = None) -> dict[str, int]:
    """The per-connector cadence: ``OSINT_CADENCE_<CONNECTOR>_SEC`` overrides the default; 0 = not scheduled.

    A value that is not a non-negative integer is ignored (the default stays); 1..59 is raised to 60.
    """
    env = os.environ if env is None else env
    out: dict[str, int] = {}
    for name, default in DEFAULT_CADENCE_SEC.items():
        raw = env.get(f"OSINT_CADENCE_{name.upper()}_SEC")
        value = default
        if raw is not None:
            try:
                parsed = int(str(raw).strip())
            except ValueError:
                parsed = -1
            if parsed >= 0:
                value = parsed
        if 0 < value < MIN_CADENCE_SEC:
            value = MIN_CADENCE_SEC
        out[name] = value
    return out


class Settings(BaseSettings):
    """Environment-driven settings; every field has a safe default.

    The contract variables are read by their exact names (``OSINT_ORACLE_URL``, ``HOST``, ``PORT``, ...); the
    tuning fields below them take the ``OSINT_`` prefix (``OSINT_BATCH_SIZE``), so no unrelated variable of the
    environment can reach a field. Tests construct ``Settings(oracle_url=..., cache_dir=...)`` by field name.
    """

    model_config = SettingsConfigDict(
        env_prefix="OSINT_", extra="ignore", case_sensitive=False, populate_by_name=True
    )

    oracle_url: str = Field(default=UNSET_ORACLE_URL, validation_alias=AliasChoices("OSINT_ORACLE_URL"))
    host: str = Field(default="127.0.0.1", validation_alias=AliasChoices("HOST"))
    port: int = Field(default=8193, ge=1, le=65535, validation_alias=AliasChoices("PORT"))
    cache_dir: Path = Field(default=Path("/var/cache/osint-ingress"), validation_alias=AliasChoices("OSINT_CACHE_DIR"))
    mode: Literal["live", "offline"] = Field(default="live", validation_alias=AliasChoices("OSINT_MODE"))
    gazetteer_path: Path | None = Field(default=None, validation_alias=AliasChoices("OSINT_GAZETTEER_PATH"))
    #: read from OSINT_CADENCE_<CONNECTOR>_SEC (see :func:`cadences_from_env`), never from one JSON variable
    cadence_sec: dict[str, int] = Field(default_factory=cadences_from_env, exclude=True)
    #: ± fraction of each cadence (spreads the polls; never synchronised with other boxes)
    jitter: float = Field(default=0.1, ge=0.0, le=0.5)
    #: the oracle reachability probe (GET {oracle}/health), independent of posting (plan R7)
    probe_interval_sec: float = Field(default=30.0, gt=0.0, le=30.0)
    probe_timeout_sec: float = Field(default=2.0, gt=0.0, le=10.0)
    #: cache retention: whichever comes first (the newest entry of each connector is always kept)
    retention_hours: float = Field(default=72.0, gt=0.0)
    retention_bytes: int = Field(default=200 * 1024 * 1024, gt=0)
    batch_size: int = Field(default=200, ge=1, le=200)
    publish_retries: int = Field(default=3, ge=1, le=10)
    publish_backoff_sec: float = Field(default=0.5, ge=0.0, le=30.0)
    http_timeout_sec: float = Field(default=25.0, gt=0.0, le=120.0)

    @field_validator("oracle_url")
    @classmethod
    def _loopback_oracle(cls, v: str) -> str:
        return check_oracle_url(v)

    @field_validator("mode", mode="before")
    @classmethod
    def _mode(cls, v: object) -> object:
        return v.strip().lower() if isinstance(v, str) else v

    @property
    def offline(self) -> bool:
        return self.mode == "offline"
