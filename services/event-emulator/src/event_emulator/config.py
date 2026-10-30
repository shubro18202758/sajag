"""Configuration — fixed internal endpoints are config constants.

Environment overrides follow the repo conventions (infra/compose.yml):
VVIP_DATABASE_URL, VVIP_VALKEY_URL, VVIP_NATS_URL.  Database credentials are
NEVER hardcoded — the DSN is env-only and runners fail closed without it.

The traffic-oracle URL is validated by :func:`assert_internal_endpoint` at
load time (loopback / host.docker.internal allowlist), so a stray
environment override cannot redirect the twin seam at an arbitrary host.

The HTTP surface binds loopback by default (HOST env overrides): the deck
reaches the emulator through its same-origin /api/emulator proxy, and the
service writes events, sightings and Valkey inputs, so it must not answer on
a venue LAN. CORS origins come from EMULATOR_DECK_ORIGINS (comma-separated
http(s)://host[:port]); the default covers the deployed deck (:5273) and the
vite dev server (:5173).

Living city (ambient.py): EMULATOR_LIVING_CITY=1 starts the ambient city at
boot (0/unset: off; an operator can still start it from the deck),
EMULATOR_CITY_SEED picks the deterministic day program (default 400001,
the PIN code of the GPO at Fort, Mumbai), EMULATOR_LIVING_VIOLATORS=0 stops the
city driving its deliberate violators (~4 an hour, each a PENDING e-challan
recommendation in the human review queue; default on — the program itself
is unchanged), and EMULATOR_PUJA_NIGHTS (comma-separated ISO dates of
Ganeshotsav's busiest evenings: the two before Anant Chaturdashi and the
visarjan evening) overrides the festival calendar of city.PUJA_NIGHTS when
the year's almanac differs.
"""

from __future__ import annotations

import os
from datetime import date
from urllib.parse import urlparse

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from event_emulator.safe_http import assert_internal_endpoint

__all__ = [
    "DEFAULT_DECK_ORIGINS",
    "Settings",
    "get_settings",
    "parse_deck_origins",
    "LIVING_DENSITIES",
    "parse_density",
    "parse_flag",
    "parse_puja_nights",
]

# Deck origins allowed by CORS when EMULATOR_DECK_ORIGINS is unset.
DEFAULT_DECK_ORIGINS: tuple[str, ...] = (
    # deployed command-deck (infra/compose.argus-override.yml, :5273)
    "http://127.0.0.1:5273",
    "http://localhost:5273",
    # vite dev server (services/command-deck `bun dev`, :5173)
    "http://localhost:5173",
    "http://127.0.0.1:5173",
)


def parse_deck_origins(raw: str) -> tuple[str, ...]:
    """Comma-separated origins → tuple; fail closed on anything but
    http(s)://host[:port] (no wildcard, path, query or credentials).

    The port is validated by READING ``parsed.port`` — urlparse only checks
    it then — so a non-numeric, negative or out-of-range port (and a bare
    trailing colon) refuses the whole list instead of slipping through.
    """
    origins: list[str] = []
    for item in raw.split(","):
        origin = item.strip().rstrip("/")
        if not origin:
            continue
        parsed = urlparse(origin)
        try:
            port = parsed.port
        except ValueError:
            raise ValueError(
                f"EMULATOR_DECK_ORIGINS: not an origin: {origin!r}") from None
        if (parsed.scheme not in ("http", "https") or not parsed.hostname
                or parsed.username or parsed.password or parsed.path
                or parsed.query or parsed.fragment or "*" in origin
                or parsed.netloc.endswith(":")
                or (port is not None and not 1 <= port <= 65535)):
            raise ValueError(f"EMULATOR_DECK_ORIGINS: not an origin: {origin!r}")
        origins.append(origin)
    if not origins:
        raise ValueError("EMULATOR_DECK_ORIGINS is set but lists no origin")
    return tuple(origins)


def parse_flag(raw: str | None) -> bool:
    """'1' / 'true' / 'yes' / 'on' → True; empty, '0' and anything else → False."""
    return (raw or "").strip().lower() in ("1", "true", "yes", "on")


#: The living city's density levels (ambient.DENSITY_LEVELS).
LIVING_DENSITIES = (1, 2, 3)


def parse_density(raw: str) -> int:
    """'1' / '2' / '3' → that density; fail closed on anything else (a typo
    must not silently run the baseline city)."""
    item = raw.strip()
    try:
        level = int(item)
    except ValueError:
        raise ValueError(f"EMULATOR_LIVING_DENSITY: not an integer: {item!r}") from None
    if level not in LIVING_DENSITIES:
        raise ValueError(f"EMULATOR_LIVING_DENSITY must be one of {LIVING_DENSITIES}, not {level}")
    return level


def parse_puja_nights(raw: str) -> tuple[date, ...]:
    """'2026-10-17, 2026-10-18,2026-10-19' → sorted dates; fail closed on
    anything that is not an ISO date (and on an empty list)."""
    nights: list[date] = []
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        try:
            nights.append(date.fromisoformat(item))
        except ValueError:
            raise ValueError(f"EMULATOR_PUJA_NIGHTS: not an ISO date: {item!r}") from None
    if not nights:
        raise ValueError("EMULATOR_PUJA_NIGHTS is set but lists no date")
    return tuple(sorted(set(nights)))


class Settings(BaseSettings):
    """Emulator settings; every value overridable by env, none secret."""

    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    # ── fixed internal endpoints (config constants — contract C5/C6) ──────
    traffic_oracle_url: str = "http://localhost:8081"
    valkey_url: str = Field(default="redis://localhost:6379",
                            validation_alias="VVIP_VALKEY_URL")
    nats_url: str = Field(default="nats://localhost:4222",
                          validation_alias="VVIP_NATS_URL")
    # env-only; no default with credentials (repo convention, scripts/migrate.py)
    database_url: str | None = Field(default=None,
                                     validation_alias="VVIP_DATABASE_URL")

    # ── emulator HTTP surface ─────────────────────────────────────────────
    host: str = "127.0.0.1"                       # env HOST
    port: int = 8090                              # env PORT
    deck_origins: tuple[str, ...] = DEFAULT_DECK_ORIGINS  # env EMULATOR_DECK_ORIGINS

    # ── seam defaults ─────────────────────────────────────────────────────
    inputs_doc_ttl_sec: int = 30       # 3× the 5 s engine poll interval
    nats_emulated_subject: str = "corridor.traffic.emulated"

    # ── living city (ambient.py) ──────────────────────────────────────────
    living_city: bool = False          # env EMULATOR_LIVING_CITY (1 = start at boot)
    city_seed: int = 400001            # env EMULATOR_CITY_SEED
    living_violators: bool = True      # env EMULATOR_LIVING_VIOLATORS (0 = none)
    puja_nights: tuple[date, ...] | None = None   # env EMULATOR_PUJA_NIGHTS
    # env EMULATOR_LIVING_DENSITY: 1 = the baseline city (two beats, two to
    # three causes), 2 = denser (every beat and standby circuit rides, two
    # more intermittent cause lanes, 108 and violators more often), 3 =
    # densest (four more lanes).  ambient.DENSITY_LEVELS holds the numbers.
    living_density: int = 1

    def validate_internal_endpoints(self) -> None:
        """Fail closed on an illegal endpoint override."""
        assert_internal_endpoint(self.traffic_oracle_url)


def get_settings() -> Settings:
    s = Settings()

    if os.environ.get("EMULATOR_TRAFFIC_ORACLE_URL"):
        s.traffic_oracle_url = os.environ["EMULATOR_TRAFFIC_ORACLE_URL"]
    if os.environ.get("EMULATOR_DECK_ORIGINS"):
        s.deck_origins = parse_deck_origins(os.environ["EMULATOR_DECK_ORIGINS"])
    s.living_city = parse_flag(os.environ.get("EMULATOR_LIVING_CITY"))
    if os.environ.get("EMULATOR_CITY_SEED", "").strip():
        s.city_seed = int(os.environ["EMULATOR_CITY_SEED"].strip())
    if os.environ.get("EMULATOR_LIVING_VIOLATORS", "").strip():
        s.living_violators = parse_flag(os.environ["EMULATOR_LIVING_VIOLATORS"])
    if os.environ.get("EMULATOR_PUJA_NIGHTS", "").strip():
        s.puja_nights = parse_puja_nights(os.environ["EMULATOR_PUJA_NIGHTS"])
    if os.environ.get("EMULATOR_LIVING_DENSITY", "").strip():
        s.living_density = parse_density(os.environ["EMULATOR_LIVING_DENSITY"])
    s.validate_internal_endpoints()
    return s
