import asyncio
from datetime import timedelta

import numpy as np
import pytest

from conftest import ORIGIN, BrokenModel, RampModel
from forecast.engine import Engine, crossing_of, score
from forecast.models import ModelSlot, QuantileForecast, SeasonalNaive, SeriesInput


def test_seasonal_naive_daily_and_band():
    day = 96
    x = np.arange(10 * day)
    y = 0.5 + 0.3 * np.sin(2 * np.pi * x / day)
    f = SeasonalNaive().predict([SeriesInput(target=y)], 8)[0]
    assert np.allclose(f.p50, y[len(y) - day:len(y) - day + 8])
    assert np.all(f.p10 <= f.p50) and np.all(f.p50 <= f.p90)


def test_seasonal_naive_picks_weekly_when_better():
    day, week = 96, 672
    rng = np.random.default_rng(0)
    pattern = rng.uniform(0.2, 0.9, week)
    y = np.tile(pattern, 3)
    f = SeasonalNaive().predict([SeriesInput(target=y)], 8)[0]
    assert f.meta["season_steps"] == week
    assert np.allclose(f.p50, y[len(y) - week:len(y) - week + 8])


def test_seasonal_naive_short_context_is_persistence():
    f = SeasonalNaive().predict([SeriesInput(target=np.array([0.4, 0.5, 0.6]))], 4)[0]
    assert np.allclose(f.p50, 0.6) and f.meta["season_steps"] == 0


def test_quantile_sorting():
    q = QuantileForecast(np.array([0.9]), np.array([0.5]), np.array([0.1])).sorted()
    assert q.p10[0] == 0.1 and q.p90[0] == 0.9


def test_crossing_of():
    q = QuantileForecast(np.array([0.6, 0.7, 0.75]), np.array([0.7, 0.79, 0.81]), np.array([0.8, 0.9, 0.95]))
    assert crossing_of(0.65, q, 0.8) == 2
    assert crossing_of(0.85, q, 0.8) is None  # already over: not a crossing
    assert crossing_of(0.5, QuantileForecast(q.p10, q.p10, q.p90), 0.8) is None


def test_score_perfect_and_coverage():
    actual = np.array([[0.5, 0.85], [0.6, 0.7]])
    fcs = [QuantileForecast(a - 0.1, a.copy(), a + 0.1) for a in actual]
    r = score(actual, fcs, np.array([40.0, 40.0]), 15, 0.8, np.array([0.4, 0.6]))
    assert r["mae_vc"] == 0.0 and r["coverage_p10_p90"] == 1.0
    assert r["crossing_alerts"]["hits"] == 1 and r["crossing_alerts"]["false_alarms"] == 0
    assert set(r["by_horizon_min"]) == {"15", "30"}


def test_model_slot_lazy_and_idle_unload():
    loads = []
    slot = ModelSlot("x", lambda: loads.append(1) or object(), idle_sec=10)
    assert not slot.loaded
    slot.get()
    slot.get()
    assert slot.loaded and loads == [1]
    assert not slot.maybe_unload(now=slot.last_used + 5)
    assert slot.maybe_unload(now=slot.last_used + 11)
    assert not slot.loaded and slot.unloads == 1
    slot.get()
    assert slot.loads == 2


def test_engine_forecasts_crossings_and_proposals(settings, net):
    model = RampModel()
    eng = Engine(settings, net, model=model)
    body = asyncio.run(eng.forecasts(now=ORIGIN))
    assert body["model"] == "ramp-test-model" and body["data_labels"] == ["SIMULATED"]
    assert "simulated" in body["data_note"].lower()
    segs = body["segments"]
    assert len(segs) == len(net.segments)
    s0 = segs[0]
    assert [st["lead_min"] for st in s0["steps"]] == [15, 30, 45, 60, 75, 90, 105, 120]
    for st in s0["steps"]:
        assert st["vc"]["p10"] <= st["vc"]["p50"] <= st["vc"]["p90"]
        assert st["speed_kmh"]["p10"] <= st["speed_kmh"]["p50"] <= st["speed_kmh"]["p90"]
    crossing = [s for s in segs if s["crossing"]]
    assert crossing, "the ramp must cross 0.8 somewhere"
    for s in crossing:
        assert s["now"]["vc"] < 0.8 and s["crossing"]["vc_p50"] >= 0.8
        assert s["proposal_id"].startswith(f"fc-{s['segment_id']}-")
    assert len(body["proposals"]) == len(crossing)
    for p in body["proposals"]:
        assert p["state"] == "proposed" and p["recommendation"]["decision"] == "await_officer"
        assert p["human_gate"] == {"state": "proposed", "required_role": "duty_officer", "officer": None,
                                   "decided_at": None}
        assert all(a["requires_officer"] for a in p["actions"])
        assert "SIMULATED" in p["labels"] and "V/C forecast" in p["summary"]
        assert p["actions"][0]["verb"] in ("diversion", "monitor")
    # sorted most pressing first
    v = [p["situation"]["vc_p50"] for p in body["proposals"]]
    assert v == sorted(v, reverse=True)
    # cached: a second call does not re-run the model
    calls = model.calls
    asyncio.run(eng.forecasts())
    asyncio.run(eng.forecasts())
    assert model.calls == calls
    asyncio.run(eng.forecasts(force=True))
    assert model.calls == calls + 1


def test_engine_falls_back_to_baseline_when_model_breaks(settings, net):
    eng = Engine(settings, net, model=BrokenModel())
    body = asyncio.run(eng.forecasts(now=ORIGIN))
    assert body["model"] == "seasonal-naive" and "model unavailable" in body["model_note"]
    assert eng.last_error and "weights not available" in eng.last_error


def test_backtest_shape_and_label(settings, net):
    eng = Engine(settings, net, model=RampModel())
    bt = asyncio.run(eng.backtest(end=ORIGIN))
    assert bt["data_label"] == "SIMULATED" and "not on recorded traffic" in bt["data_note"]
    assert set(bt["models"]) == {"ramp-test-model", "seasonal-naive"}
    for m in bt["models"].values():
        assert 0 <= m["coverage_p10_p90"] <= 1 and m["mae_vc"] >= 0
        assert set(m["by_horizon_min"]) == {"15", "30", "45", "60", "75", "90", "105", "120"}
    assert "mae_skill_vs_baseline" in bt["models"]["ramp-test-model"]
    assert bt["window"]["origins"] == 2 and bt["window"]["series"] == 2 * len(net.segments)
