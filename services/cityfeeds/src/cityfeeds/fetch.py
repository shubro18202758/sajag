"""The polite fetcher: one schedule per feed, a cache, a minimum interval, a daily cap and an offline mode.

Every outbound call goes through ``Fetcher.get``:

* inside the feed's ``cache_sec`` the cache answers;
* past it the cache STILL answers at once and one background refresh starts (stale-while-revalidate), so a slow
  upstream (GDACS's list API can take 40 s) never holds a deck request;
* a refresh closer than ``min_interval_sec`` to the last one, or past the feed's daily cap, is refused; a failed
  refresh keeps the last answer, marked ``stale`` with the error; with no answer ever the feed is ``UNAVAILABLE``
  and says so (never a zero);
* ``offline`` makes no call at all: the recorded fixture answers, labelled ``RECORDED``;
* an error is stored only after :func:`cityfeeds.keys.redact` (no key, no URL query string ever reaches /health);
* the default transport verifies every certificate (httpx's defaults: certifi CA bundle, host name checked); no host
  has an exception.

The schedules (``FEEDS``) are far inside every provider's published fair-use terms: Open-Meteo's free tier
(non-commercial, 10 000 calls a day), GDACS, USGS, NDMA Sachet and the news feeds at one refresh per 10–60 minutes.
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Awaitable, Callable

import httpx

from cityfeeds.keys import redact

__all__ = ["FeedPolicy", "FEEDS", "Fetched", "Fetcher", "load_fixture", "FIXTURES"]

FIXTURES = Path(__file__).resolve().parent / "fixtures"

USER_AGENT = "sajag-cityfeeds/0.1 (Mumbai situational feeds; polite schedule; on-premises)"


@dataclass(frozen=True)
class FeedPolicy:
    id: str
    #: who publishes it (the honest source line)
    source: str
    cache_sec: float
    min_interval_sec: float
    max_refresh_per_day: int
    home: str


FEEDS: dict[str, FeedPolicy] = {p.id: p for p in (
    FeedPolicy("air", "Open-Meteo air-quality API (CAMS global atmospheric-composition model)", 900, 60, 200,
               "https://open-meteo.com/en/docs/air-quality-api"),
    FeedPolicy("heat", "Open-Meteo forecast API (temperature, humidity, apparent temperature)", 900, 60, 200,
               "https://open-meteo.com/en/docs"),
    FeedPolicy("cyclones", "GDACS (Global Disaster Alert and Coordination System, EC JRC and UN OCHA)", 1800, 120, 96,
               "https://www.gdacs.org/"),
    FeedPolicy("news", "Mumbai news RSS (Mid-day, TOI Mumbai, HT Mumbai, Free Press Journal, Loksatta), mentions "
               "counted only", 1800, 600, 48, "https://www.mid-day.com/mumbai"),
    FeedPolicy("alerts", "NDMA Sachet: Common Alerting Protocol feed (IMD Mumbai, Maharashtra SDMA and others)", 900,
               120, 120, "https://sachet.ndma.gov.in/"),
    FeedPolicy("quakes", "USGS earthquake catalogue (FDSN event web service)", 3600, 300, 48,
               "https://earthquake.usgs.gov/fdsnws/event/1/"),
    FeedPolicy("mtp", "Mumbai Traffic Police public home page: current traffic notifications", 21600, 3600, 8,
               "https://trafficpolicemumbai.maharashtra.gov.in/"),
    FeedPolicy("fires", "NASA FIRMS active fires (VIIRS S-NPP, NOAA-20, NOAA-21 and MODIS; NRT)", 10800, 1800, 16,
               "https://firms.modaps.eosdis.nasa.gov/active_fire/"),
    FeedPolicy("air_waqi", "World Air Quality Index project (aqicn.org): observed station AQI", 1800, 300, 96,
               "https://aqicn.org/api/"),
    FeedPolicy("air_openaq", "OpenAQ v3: observed station measurements", 1800, 300, 96, "https://docs.openaq.org/"),
    FeedPolicy("air_cpcb", "CPCB real-time air quality index (data.gov.in)", 1800, 300, 96,
               "https://www.data.gov.in/resource/real-time-air-quality-index-various-locations"),
)}


def load_fixture(name: str) -> Any:
    p = FIXTURES / name
    if p.suffix == ".json":
        return json.loads(p.read_text(encoding="utf-8"))
    return p.read_text(encoding="utf-8")


@dataclass
class Fetched:
    feed: str
    data: Any
    fetched_at: datetime | None
    #: LIVE (answered now or from a fresh cache) · RECORDED (offline fixture) · UNAVAILABLE
    mode: str
    stale: bool = False
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.data is not None

    def meta(self) -> dict[str, Any]:
        return {"feed": self.feed, "mode": self.mode, "stale": self.stale, "error": self.error,
                "fetched_at": self.fetched_at.isoformat() if self.fetched_at else None,
                "source": FEEDS[self.feed].source, "home": FEEDS[self.feed].home}


class RateLimited(RuntimeError):
    pass


@dataclass
class _State:
    data: Any = None
    at: float = 0.0
    fetched_at: datetime | None = None
    last_call: float = -1e18
    day: date = field(default_factory=date.today)
    calls_today: int = 0
    last_error: str | None = None
    task: asyncio.Task | None = None


class Fetcher:
    """Stale-while-revalidate: a request never waits on a slow upstream once a feed has answered once — an expired
    cache answers at once and a background refresh is started (one per feed at a time, inside the feed's limits).
    The first request for a feed waits at most ``first_wait_sec`` for the first answer."""

    def __init__(self, *, offline: bool = False, timeout: float = 20.0, cache_scale: float = 1.0,
                 first_wait_sec: float = 25.0, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.offline = offline
        self.cache_scale = cache_scale
        self.first_wait = first_wait_sec
        self.client = httpx.AsyncClient(timeout=timeout, transport=transport or httpx.AsyncHTTPTransport(),
                                        follow_redirects=True, headers={"user-agent": USER_AGENT})
        self._state: dict[str, _State] = {k: _State() for k in FEEDS}
        self._locks: dict[str, asyncio.Lock] = {k: asyncio.Lock() for k in FEEDS}

    async def aclose(self) -> None:
        for st in self._state.values():
            if st.task and not st.task.done():
                st.task.cancel()
        await self.client.aclose()

    def _admit(self, st: _State, pol: FeedPolicy) -> None:
        today = date.today()
        if today != st.day:
            st.day, st.calls_today = today, 0
        now = time.monotonic()
        if now - st.last_call < pol.min_interval_sec * self.cache_scale:
            raise RateLimited(f"rate limit: one {pol.id} refresh per {pol.min_interval_sec:.0f} s")
        if st.calls_today >= pol.max_refresh_per_day:
            raise RateLimited(f"daily cap reached ({pol.max_refresh_per_day} {pol.id} refreshes)")
        st.last_call = now
        st.calls_today += 1

    async def _refresh(self, feed: str, fetch: Callable[[httpx.AsyncClient], Awaitable[Any]]) -> None:
        pol, st = FEEDS[feed], self._state[feed]
        async with self._locks[feed]:
            try:
                self._admit(st, pol)
                data = await fetch(self.client)
                st.data, st.at, st.fetched_at, st.last_error = data, time.monotonic(), datetime.now(UTC), None
            except Exception as exc:  # noqa: BLE001 — kept as the feed's error; the cache (if any) still answers
                st.last_error = redact(f"{type(exc).__name__}: {exc}")[:200]

    def _kick(self, feed: str, fetch: Callable[[httpx.AsyncClient], Awaitable[Any]]) -> asyncio.Task:
        st = self._state[feed]
        if st.task is None or st.task.done():
            st.task = asyncio.get_running_loop().create_task(self._refresh(feed, fetch))
        return st.task

    def _answer(self, feed: str) -> Fetched:
        pol, st = FEEDS[feed], self._state[feed]
        if st.data is None:
            return Fetched(feed, None, None, "UNAVAILABLE", error=st.last_error or "no answer yet")
        age = time.monotonic() - st.at
        stale = age > 3 * pol.cache_sec or st.last_error is not None
        return Fetched(feed, st.data, st.fetched_at, "LIVE", stale=stale, error=st.last_error)

    async def get(self, feed: str, fetch: Callable[[httpx.AsyncClient], Awaitable[Any]],
                  fixture: Callable[[], Any], force: bool = False) -> Fetched:
        pol = FEEDS[feed]
        st = self._state[feed]
        if self.offline:
            try:
                return Fetched(feed, fixture(), None, "RECORDED")
            except Exception as exc:  # noqa: BLE001
                return Fetched(feed, None, None, "UNAVAILABLE", error=f"no fixture: {exc}"[:200])
        if force:
            await self._refresh(feed, fetch)
            return self._answer(feed)
        if st.data is not None:
            if time.monotonic() - st.at >= pol.cache_sec * self.cache_scale:
                self._kick(feed, fetch)  # answer now from the cache; refresh behind
            return self._answer(feed)
        task = self._kick(feed, fetch)
        try:
            await asyncio.wait_for(asyncio.shield(task), timeout=self.first_wait)
        except (asyncio.TimeoutError, Exception):  # noqa: BLE001 — the task keeps running; its error is kept
            pass
        return self._answer(feed)

    def status(self) -> dict[str, Any]:
        out = {}
        for k, st in self._state.items():
            pol = FEEDS[k]
            out[k] = {"calls_today": st.calls_today, "max_refresh_per_day": pol.max_refresh_per_day,
                      "cache_sec": pol.cache_sec, "min_interval_sec": pol.min_interval_sec,
                      "cache_age_sec": round(time.monotonic() - st.at, 1) if st.data is not None else None,
                      "last_error": st.last_error, "refreshing": bool(st.task and not st.task.done())}
        return {"offline": self.offline, "feeds": out}
