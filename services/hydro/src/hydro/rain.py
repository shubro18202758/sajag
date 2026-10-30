"""Rain for Mumbai from Open-Meteo (no key): the live nowcast and the historical archive.

* **Nowcast** — ``/v1/forecast`` with ``minutely_15=precipitation`` at a
  FIXED point set (``POINTS``, canonical landmark ids spread over the city), past 24 h and next 2 h. The
  15-minute values are the preceding 15 minutes' sum in mm (×4 → mm/h). Open-Meteo is a model product
  (blended NWP), not a rain gauge; over India its 15-minute field may be interpolated from hourly
  models. Label: LIVE (the feed is live; the values are a model's).
* **Archive** — ``archive-api.open-meteo.com/v1/archive`` hourly precipitation (reanalysis-based) for
  the replay.

Calls are cached and rate-limited (config): a refresh inside ``rain_cache_sec`` is served from cache,
calls closer than ``min_call_interval_sec`` are refused (the cache answers, marked stale), and a daily cap
stops runaway use.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx
import numpy as np

from hydro.network import haversine_m

__all__ = ["POINTS", "RainPoint", "RainNowcast", "RainClient", "RateLimited", "idw"]

#: (landmark id, lat, lon) — cities/mumbai/landmarks.json; a fixed set over the island city, the western
#: and the eastern suburbs, so the call is stable and cheap
POINTS: list[tuple[str, float, float]] = [
    ("gateway", 18.922, 72.8347), ("csmt", 18.9398, 72.8355), ("jj_hospital", 18.96386, 72.83479),
    ("haji_ali", 18.97811, 72.81137), ("hindmata", 19.00561, 72.83976), ("worli_naka", 19.00629, 72.81826),
    ("kings_circle", 19.0278, 72.85649), ("sion_circle", 19.04231, 72.86345),
    ("mahim_causeway", 19.04871, 72.83824), ("bkc", 19.06521, 72.86226), ("bandra", 19.0544, 72.8406),
    ("milan_subway", 19.09048, 72.84261), ("andheri_subway", 19.1148, 72.84742), ("kurla", 19.065, 72.879),
    ("chembur", 19.062, 72.9), ("ghatkopar", 19.086, 72.9081), ("powai", 19.12624, 72.89368),
    ("borivali", 19.229, 72.857),
]


class RateLimited(RuntimeError):
    pass


@dataclass
class RainPoint:
    id: str
    lat: float
    lon: float
    times: list[datetime]          # UTC, 15-min, end of each interval
    mm_h: np.ndarray               # intensity over the 15 min ending at times[i]


@dataclass
class RainNowcast:
    fetched_at: datetime
    points: list[RainPoint]
    label: str
    source: str
    stale: bool = False
    error: str | None = None
    notes: list[str] = field(default_factory=list)

    def at(self, lat: float, lon: float) -> tuple[list[datetime], np.ndarray]:
        """IDW (power 2, nearest 3 points) series at a location."""
        if not self.points:
            return [], np.zeros(0)
        return self.points[0].times, idw(self.points, lat, lon)

    def city_mean(self) -> tuple[list[datetime], np.ndarray]:
        if not self.points:
            return [], np.zeros(0)
        return self.points[0].times, np.mean(np.stack([p.mm_h for p in self.points]), axis=0)


def idw(points: list[RainPoint], lat: float, lon: float, k: int = 3) -> np.ndarray:
    d = np.array([haversine_m(lat, lon, p.lat, p.lon) for p in points])
    idx = np.argsort(d)[:k]
    w = 1.0 / np.maximum(d[idx], 50.0) ** 2
    return np.sum(np.stack([points[i].mm_h for i in idx]) * w[:, None], axis=0) / w.sum()


class RainClient:
    def __init__(self, forecast_url: str, archive_url: str, *, timeout: float = 15.0, cache_sec: float = 600.0,
                 min_interval_sec: float = 30.0, max_calls_per_day: int = 2000, offline: bool = False,
                 transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.forecast_url = forecast_url
        self.archive_url = archive_url
        self.cache_sec = cache_sec
        self.min_interval = min_interval_sec
        self.max_calls = max_calls_per_day
        self.offline = offline
        self._client = httpx.AsyncClient(timeout=timeout, transport=transport,
                                         headers={"user-agent": "sajag-hydro/0.1 (Mumbai waterlogging nowcast)"})
        self._cache: RainNowcast | None = None
        self._cache_at = 0.0
        self._last_call: dict[str, float] = {}
        self._day = date.today()
        self.calls_today = 0
        self._lock = asyncio.Lock()
        self._archive: dict[tuple, dict] = {}

    async def aclose(self) -> None:
        await self._client.aclose()

    def _admit(self, kind: str = "forecast") -> None:
        if self.offline:
            raise RateLimited("offline mode: no outbound calls")
        today = date.today()
        if today != self._day:
            self._day, self.calls_today = today, 0
        now = time.monotonic()
        if now - self._last_call.get(kind, -1e9) < self.min_interval:
            raise RateLimited(f"rate limit: one {kind} call per {self.min_interval:.0f} s")
        if self.calls_today >= self.max_calls:
            raise RateLimited("daily call cap reached")
        self._last_call[kind] = now
        self.calls_today += 1

    def status(self) -> dict[str, Any]:
        return {"calls_today": self.calls_today, "max_calls_per_day": self.max_calls,
                "cache_age_sec": round(time.monotonic() - self._cache_at, 1) if self._cache else None,
                "offline": self.offline}

    async def nowcast(self, force: bool = False) -> RainNowcast:
        async with self._lock:
            if self._cache is not None and not force and time.monotonic() - self._cache_at < self.cache_sec:
                return self._cache
            try:
                self._admit()
                nc = await self._fetch_nowcast()
                self._cache, self._cache_at = nc, time.monotonic()
                return nc
            except Exception as exc:  # noqa: BLE001
                err = f"{type(exc).__name__}: {exc}"[:200]
                if self._cache is not None:
                    c = self._cache
                    return RainNowcast(c.fetched_at, c.points, c.label, c.source, stale=True, error=err,
                                       notes=c.notes)
                return RainNowcast(datetime.now(UTC), [], "UNAVAILABLE", "Open-Meteo (no answer)", error=err)

    async def _fetch_nowcast(self) -> RainNowcast:
        params = {
            "latitude": ",".join(f"{p[1]:.4f}" for p in POINTS),
            "longitude": ",".join(f"{p[2]:.4f}" for p in POINTS),
            "minutely_15": "precipitation",
            "past_minutely_15": 96,  # 24 h of spin-up for the ponding model
            "forecast_minutely_15": 8,
            "timezone": "GMT",
        }
        r = await self._client.get(self.forecast_url, params=params)
        r.raise_for_status()
        body = r.json()
        locs = body if isinstance(body, list) else [body]
        if len(locs) != len(POINTS):
            raise ValueError(f"expected {len(POINTS)} locations, got {len(locs)}")
        points = []
        for (pid, lat, lon), loc in zip(POINTS, locs):
            m = loc.get("minutely_15") or {}
            times = [datetime.fromisoformat(t).replace(tzinfo=UTC) for t in m.get("time", [])]
            mm = np.array([float(v or 0.0) for v in m.get("precipitation", [])]) * 4.0
            # Open-Meteo stamps each "preceding 15 minutes" sum at the END of its interval
            points.append(RainPoint(pid, lat, lon, times, mm))
        n = min(len(p.times) for p in points)
        for p in points:
            p.times, p.mm_h = p.times[:n], p.mm_h[:n]
        return RainNowcast(datetime.now(UTC), points, "LIVE",
                           "Open-Meteo forecast API, minutely_15 precipitation (model nowcast, not a gauge)",
                           notes=["15-min values are the preceding quarter-hour's sum ×4 (mm/h)",
                                  "over India the 15-min field may be interpolated from hourly models"])

    async def archive_hourly(self, points: list[tuple[str, float, float]], start: date, end: date,
                             model: str | None = None) -> dict[str, Any]:
        key = (tuple(points), start, end, model)
        if key in self._archive:
            return self._archive[key]
        self._admit("archive")
        params: dict[str, Any] = {
            "latitude": ",".join(f"{p[1]:.4f}" for p in points),
            "longitude": ",".join(f"{p[2]:.4f}" for p in points),
            "start_date": start.isoformat(), "end_date": end.isoformat(),
            "hourly": "precipitation", "timezone": "GMT",
        }
        if model:
            params["models"] = model
        r = await self._client.get(self.archive_url, params=params)
        r.raise_for_status()
        body = r.json()
        locs = body if isinstance(body, list) else [body]
        out = {"points": [], "model": model or "best_match", "grid": []}
        for (pid, lat, lon), loc in zip(points, locs):
            h = loc.get("hourly") or {}
            times = [datetime.fromisoformat(t).replace(tzinfo=UTC) for t in h.get("time", [])]
            mm = np.array([float(v or 0.0) for v in h.get("precipitation", [])])
            out["points"].append({"id": pid, "lat": lat, "lon": lon, "times": times, "mm": mm})
            out["grid"].append((loc.get("latitude"), loc.get("longitude")))
        self._archive[key] = out
        return out


def quarter_series(times: list[datetime], hourly_mm: np.ndarray, start: datetime, n: int,
                   step_min: int = 15) -> np.ndarray:
    """Hourly sums (stamped at the hour's END, Open-Meteo convention for 'preceding hour') → mm/h on a
    15-min grid (flat within the hour)."""
    out = np.zeros(n)
    for i in range(n):
        t = start + timedelta(minutes=step_min * i)
        # the hour whose (end − 1 h, end] window contains t
        for tt, v in zip(times, hourly_mm):
            if tt - timedelta(hours=1) < t <= tt:
                out[i] = float(v)
                break
    return out
