"""The polite fetcher: cache, minimum interval, daily cap, stale-on-failure, offline fixtures."""

import httpx
import pytest

from cityfeeds.fetch import FEEDS, Fetcher


def _transport(calls: list, fail: bool = False):
    def handler(req: httpx.Request) -> httpx.Response:
        calls.append(str(req.url))
        if fail:
            raise httpx.ConnectError("no network")
        return httpx.Response(200, json={"n": len(calls)})
    return httpx.MockTransport(handler)


async def _fetch(c: httpx.AsyncClient):
    return (await c.get("https://example.invalid/x")).json()


async def test_cache_then_rate_limit_then_stale():
    calls: list = []
    f = Fetcher(transport=_transport(calls))
    a = await f.get("air", _fetch, lambda: None)
    b = await f.get("air", _fetch, lambda: None)  # inside cache_sec: no call
    assert a.mode == b.mode == "LIVE" and len(calls) == 1 and b.data == {"n": 1}
    c = await f.get("air", _fetch, lambda: None, force=True)  # forced, but inside min_interval: refused → cache, stale
    assert len(calls) == 1 and c.stale and "rate limit" in c.error
    await f.aclose()


async def test_failure_without_cache_is_unavailable_never_zero():
    calls: list = []
    f = Fetcher(transport=_transport(calls, fail=True))
    r = await f.get("quakes", _fetch, lambda: None)
    assert r.mode == "UNAVAILABLE" and r.data is None and "ConnectError" in r.error
    await f.aclose()


async def test_daily_cap(monkeypatch):
    calls: list = []
    f = Fetcher(transport=_transport(calls), cache_scale=0.0)  # no cache, no interval: only the cap is left
    cap = FEEDS["mtp"].max_refresh_per_day
    for _ in range(cap):
        assert (await f.get("mtp", _fetch, lambda: None, force=True)).error is None
    r = await f.get("mtp", _fetch, lambda: None, force=True)
    assert r.stale and "daily cap" in r.error and len(calls) == cap
    await f.aclose()


async def test_an_expired_cache_answers_at_once_and_refreshes_behind():
    import asyncio
    calls: list = []
    f = Fetcher(transport=_transport(calls), cache_scale=0.0)
    first = await f.get("air", _fetch, lambda: None)
    assert first.data == {"n": 1}
    second = await f.get("air", _fetch, lambda: None)  # expired: the old answer now, a refresh behind
    assert second.data == {"n": 1}
    await asyncio.sleep(0.05)
    third = await f.get("air", _fetch, lambda: None)
    assert third.data["n"] >= 2 and f.status()["feeds"]["air"]["calls_today"] >= 2
    await f.aclose()


async def test_a_slow_first_answer_never_holds_the_request():
    import asyncio

    async def slow(c):
        await asyncio.sleep(0.3)
        return {"late": True}
    f = Fetcher(first_wait_sec=0.05)
    r = await f.get("cyclones", slow, lambda: None)
    assert r.mode == "UNAVAILABLE" and r.data is None
    await asyncio.sleep(0.4)
    r2 = await f.get("cyclones", slow, lambda: None)
    assert r2.mode == "LIVE" and r2.data == {"late": True}
    await f.aclose()


async def test_offline_makes_no_call_and_says_recorded():
    calls: list = []
    f = Fetcher(offline=True, transport=_transport(calls))
    r = await f.get("air", _fetch, lambda: {"fixture": True})
    assert r.mode == "RECORDED" and r.data == {"fixture": True} and calls == []
    await f.aclose()


def test_every_feed_has_a_polite_schedule():
    for p in FEEDS.values():
        assert p.cache_sec >= 600 and p.min_interval_sec >= 30 and 0 < p.max_refresh_per_day <= 2000
