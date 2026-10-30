from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import pytest

from hydro.config import Settings
from hydro.network import load_network
from hydro.nowcast import Hydro
from hydro.rain import POINTS, RainClient

NOW = datetime(2026, 10, 28, 11, 7, tzinfo=UTC)


def forecast_body(mm_per_15: float, now: datetime = NOW, past: int = 96, future: int = 8) -> list[dict]:
    """An Open-Meteo-shaped multi-location answer: ``mm_per_15`` mm every quarter hour from 30 min before now
    to the end of the window, dry before."""
    base = now.replace(second=0, microsecond=0) - timedelta(minutes=now.minute % 15)
    times = [base + timedelta(minutes=15 * (i - past + 1)) for i in range(past + future)]
    vals = [mm_per_15 if t >= now - timedelta(minutes=30) else 0.0 for t in times]
    return [{"latitude": lat, "longitude": lon,
             "minutely_15": {"time": [t.strftime("%Y-%m-%dT%H:%M") for t in times], "precipitation": vals}}
            for _pid, lat, lon in POINTS]


def archive_body(mm_per_hour: float = 1.0, burst: float = 0.0) -> list[dict]:
    """18–19 Aug 2025 (UTC hours): ``mm_per_hour`` throughout, plus ``burst`` mm/h in the three hours ending
    03:00–05:00 UTC on the 19th (08:30–10:30 IST, the morning burst)."""
    times = [datetime(2025, 8, 18, tzinfo=UTC) + timedelta(hours=h) for h in range(48)]
    vals = [mm_per_hour + (burst if 27 <= h <= 29 else 0.0) for h in range(48)]
    return [{"latitude": lat, "longitude": lon,
             "hourly": {"time": [t.strftime("%Y-%m-%dT%H:%M") for t in times],
                        "precipitation": vals}} for _pid, lat, lon in POINTS]


def transport(mm_per_15: float = 0.0, fail: bool = False, calls: list | None = None,
              burst: float = 0.0) -> httpx.MockTransport:
    def handler(req: httpx.Request) -> httpx.Response:
        if calls is not None:
            calls.append(str(req.url))
        if fail:
            raise httpx.ConnectError("no network")
        if "archive" in req.url.host:
            return httpx.Response(200, json=archive_body(burst=burst))
        return httpx.Response(200, json=forecast_body(mm_per_15))

    return httpx.MockTransport(handler)


def make_hydro(mm_per_15: float = 0.0, **kw) -> Hydro:
    s = Settings()
    rc = RainClient(s.open_meteo_forecast_url, s.open_meteo_archive_url, min_interval_sec=0.0,
                    transport=transport(mm_per_15, **kw))
    return Hydro(load_network(None), rc)


@pytest.fixture
def hydro_dry():
    return make_hydro(0.0)


@pytest.fixture
def hydro_storm():
    # 20 mm every quarter hour = 80 mm/h from 30 min ago through the next two hours
    return make_hydro(20.0)
