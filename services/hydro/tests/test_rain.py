import asyncio
from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from conftest import transport
from hydro.rain import POINTS, RainClient, RainPoint, idw, quarter_series


def _client(**kw):
    calls = kw.pop("calls", None)
    return RainClient("https://api.open-meteo.com/v1/forecast", "https://archive-api.open-meteo.com/v1/archive",
                      transport=transport(kw.pop("mm", 1.0), fail=kw.pop("fail", False), calls=calls), **kw)


def test_parse_cache_and_label():
    calls: list = []
    rc = _client(mm=2.0, calls=calls, min_interval_sec=0.0)
    nc = asyncio.run(rc.nowcast())
    assert nc.label == "LIVE" and len(nc.points) == len(POINTS)
    assert nc.points[0].mm_h.max() == pytest.approx(8.0)  # 2 mm per quarter hour → 8 mm/h
    assert "minutely_15=precipitation" in calls[0] and "past_minutely_15=96" in calls[0]
    asyncio.run(rc.nowcast())
    assert len(calls) == 1  # served from cache
    assert rc.status()["calls_today"] == 1


def test_rate_limit_serves_stale_cache():
    rc = _client(mm=1.0, min_interval_sec=3600.0)
    first = asyncio.run(rc.nowcast())
    second = asyncio.run(rc.nowcast(force=True))
    assert second.stale and "rate limit" in second.error and second.points == first.points


def test_offline_and_failure_are_unavailable():
    nc = asyncio.run(_client(offline=True).nowcast())
    assert nc.label == "UNAVAILABLE" and not nc.points and "offline" in nc.error
    nc = asyncio.run(_client(fail=True, min_interval_sec=0.0).nowcast())
    assert nc.label == "UNAVAILABLE" and "ConnectError" in nc.error


def test_daily_cap():
    rc = _client(min_interval_sec=0.0, max_calls_per_day=1, cache_sec=0.0)
    asyncio.run(rc.nowcast())
    nc = asyncio.run(rc.nowcast(force=True))
    assert nc.stale and "cap" in nc.error


def test_archive_and_quarter_series():
    rc = _client(min_interval_sec=0.0)
    arc = asyncio.run(rc.archive_hourly(POINTS[:2], datetime(2025, 8, 18).date(), datetime(2025, 8, 19).date()))
    assert len(arc["points"]) == 2 and arc["points"][0]["mm"].sum() == 48.0
    t0 = datetime(2025, 8, 18, 0, 0, tzinfo=UTC)
    times = [t0 + timedelta(hours=h) for h in range(1, 4)]  # sums stamped at the hour's end
    q = quarter_series(times, np.array([4.0, 8.0, 0.0]), t0 + timedelta(minutes=15), 8)
    assert q.tolist() == [4.0, 4.0, 4.0, 4.0, 8.0, 8.0, 8.0, 8.0]  # grid times are interval ends


def test_idw_prefers_the_nearest_point():
    t = [datetime(2026, 1, 1, tzinfo=UTC)]
    pts = [RainPoint("a", 19.00, 72.84, t, np.array([10.0])), RainPoint("b", 19.10, 72.88, t, np.array([0.0])),
           RainPoint("c", 19.20, 72.86, t, np.array([0.0]))]
    assert idw(pts, 19.00, 72.84)[0] > 9.9
    assert 0 < idw(pts, 19.05, 72.86)[0] < 10


def test_points_are_canonical_mumbai_landmarks():
    import json
    from pathlib import Path

    lms = json.loads((Path(__file__).resolve().parents[1] / "src" / "hydro" / "data" / "mumbai_landmarks.json")
                     .read_text(encoding="utf-8"))["landmarks"]
    by = {lm["id"]: lm for lm in lms}
    assert len(POINTS) == 18
    for pid, lat, lon in POINTS:
        assert pid in by and (by[pid]["lat"], by[pid]["lon"]) == (lat, lon)
        assert 18.89 <= lat <= 19.28 and 72.77 <= lon <= 72.99
