"""Real foundation-model tests — run with ``-m model`` in a venv that has chronos-forecasting / timesfm and
the weights in the Hugging Face cache. Skipped otherwise."""

import asyncio

import numpy as np
import pytest

from conftest import ORIGIN

pytestmark = pytest.mark.model


def test_chronos2_beats_baseline_on_simulated_history(net):
    pytest.importorskip("chronos")
    from forecast.config import Settings
    from forecast.engine import Engine

    s = Settings(data_source="synthetic", contender="", backtest_days=1, backtest_stride_hours=6, context_days=7)
    eng = Engine(s, net)
    body = asyncio.run(eng.forecasts(now=ORIGIN))
    assert body["model"] == "chronos-2" and body["model_note"] is None
    st = eng.model.slot.status()
    assert st["loaded"] and st["weights_gpu_mib"] is None or st["weights_gpu_mib"] < 1200
    bt = asyncio.run(eng.backtest(end=ORIGIN))
    assert bt["models"]["chronos-2"]["mae_vc"] < bt["models"]["seasonal-naive"]["mae_vc"]
    assert eng.model.slot.unload()


def test_timesfm_contender_runs(net):
    pytest.importorskip("timesfm")
    from forecast.models import SeriesInput, TimesFMForecaster

    m = TimesFMForecaster()
    x = np.arange(96 * 4)
    q = m.predict([SeriesInput(target=0.5 + 0.3 * np.sin(2 * np.pi * x / 96))], 8)[0]
    assert q.p50.shape == (8,) and np.all(q.p10 <= q.p90)
    assert m.slot.unload()
