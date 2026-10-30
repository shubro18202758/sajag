"""Forecasters: the seasonal-naive baseline (always), Chronos-2 (the model) and TimesFM 2.5 (contender).

All three answer the same question — given a V/C context (15-min steps) and its covariates, what are the
p10 / p50 / p90 of the next ``horizon`` steps — so the backtest compares like with like.

* **Seasonal naive** — tomorrow looks like today (or like the same slot last week): the lag (1 day or
  1 week) with the lower error over the context's last two days is used; the p10/p90 band comes from the
  empirical quantiles of that lag's errors over the last week of context.
* **Chronos-2** (``amazon/chronos-2``, Apache-2.0, ~120 M parameters) — zero-shot, covariate-aware: rain
  intensity, gate (outfall) closure and the event flag are passed as past covariates and, for the
  horizon, as known future covariates.
* **TimesFM 2.5** (``google/timesfm-2.5-200m-pytorch``, Apache-2.0) — the contender, univariate here
  (its covariate path needs the JAX ``xreg`` extra, which this service does not install).

Model weights load lazily on first use, on the GPU when there is one, and are freed after
``idle_unload_sec`` of disuse (``ModelSlot.maybe_unload``). Nothing is downloaded at import time.
Another on-demand service that is short of memory may ask for them sooner (``POST /admin/release``):
a slot is released only when no forecast holds it (``ModelSlot.using``) and it has been idle for
``release_idle_sec``; it reloads on its next use.
"""

from __future__ import annotations

import gc
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Callable, Iterator, Protocol

import numpy as np

from forecast.memroom import idle_verdict

__all__ = [
    "SeriesInput",
    "QuantileForecast",
    "Forecaster",
    "SeasonalNaive",
    "Chronos2Forecaster",
    "TimesFMForecaster",
    "ModelSlot",
    "gpu_stats",
]

QUANTILES = (0.1, 0.5, 0.9)


@dataclass
class SeriesInput:
    target: np.ndarray
    past_cov: dict[str, np.ndarray] = field(default_factory=dict)
    future_cov: dict[str, np.ndarray] = field(default_factory=dict)


@dataclass
class QuantileForecast:
    p10: np.ndarray
    p50: np.ndarray
    p90: np.ndarray
    meta: dict[str, Any] = field(default_factory=dict)

    def sorted(self) -> "QuantileForecast":
        q = np.sort(np.stack([self.p10, self.p50, self.p90]), axis=0)
        return QuantileForecast(q[0], q[1], q[2], self.meta)


class Forecaster(Protocol):
    name: str
    licence: str

    def predict(self, inputs: list[SeriesInput], horizon: int) -> list[QuantileForecast]: ...


# ── seasonal naive ─────────────────────────────────────────────────────────


class SeasonalNaive:
    name = "seasonal-naive"
    licence = "n/a (baseline)"

    def __init__(self, steps_per_day: int = 96) -> None:
        self.day = steps_per_day

    def _season(self, y: np.ndarray) -> int:
        week = 7 * self.day
        if y.size < week + 2 * self.day:
            return self.day
        tail = 2 * self.day
        e_day = np.mean(np.abs(y[-tail:] - y[-tail - self.day:-self.day]))
        e_week = np.mean(np.abs(y[-tail:] - y[-tail - week:-week]))
        return week if e_week < e_day else self.day

    def predict(self, inputs: list[SeriesInput], horizon: int) -> list[QuantileForecast]:
        out = []
        for inp in inputs:
            y = np.asarray(inp.target, dtype=float)
            if y.size <= self.day:
                last = float(y[-1]) if y.size else 0.0
                spread = float(np.std(np.diff(y))) * 2 if y.size > 2 else 0.1
                p50 = np.full(horizon, last)
                out.append(QuantileForecast(p50 - 1.28 * spread, p50, p50 + 1.28 * spread,
                                            {"season_steps": 0, "note": "context shorter than a day: persistence"}))
                continue
            s = self._season(y)
            n = y.size
            p50 = y[n - s + (np.arange(horizon) % s)]
            window = min(n - s, 7 * self.day)
            resid = y[n - window:] - y[n - window - s:n - s]
            q10, q90 = np.quantile(resid, [0.1, 0.9])
            out.append(QuantileForecast(p50 + q10, p50.copy(), p50 + q90, {"season_steps": int(s)}))
        return out


# ── GPU helpers ────────────────────────────────────────────────────────────


def _torch():
    import torch  # noqa: PLC0415 — optional dependency, imported only when a model is used

    return torch


def gpu_stats() -> dict[str, Any]:
    try:
        torch = _torch()
    except Exception:  # noqa: BLE001
        return {"cuda": False, "torch": False}
    if not torch.cuda.is_available():
        return {"cuda": False, "torch": True}
    return {
        "cuda": True,
        "device": torch.cuda.get_device_name(0),
        "allocated_mib": round(torch.cuda.memory_allocated() / 2**20, 1),
        "reserved_mib": round(torch.cuda.memory_reserved() / 2**20, 1),
        "peak_allocated_mib": round(torch.cuda.max_memory_allocated() / 2**20, 1),
    }


def _device(pref: str) -> str:
    if pref != "auto":
        return pref
    try:
        return "cuda" if _torch().cuda.is_available() else "cpu"
    except Exception:  # noqa: BLE001
        return "cpu"


class ModelSlot:
    """A lazily loaded model that frees itself after ``idle_sec`` of disuse."""

    def __init__(self, name: str, loader: Callable[[], Any], idle_sec: float, need_gib: float = 2.0) -> None:
        self.name = name
        self._loader = loader
        self.idle_sec = idle_sec
        #: what a release frees, roughly (the measured peak, rounded up): the /admin/release estimate
        self.need_gib = need_gib
        self._obj: Any = None
        self._lock = threading.RLock()
        self.last_used = 0.0
        # forecasts holding the model (``using``); its own lock, so one waiting behind a load already counts
        self._busy = 0
        self._busy_lock = threading.Lock()
        self.loaded_at: float | None = None
        self.load_sec: float | None = None
        self.loads = 0
        self.unloads = 0
        self.weights_mib: float | None = None
        self.peak_mib: float | None = None
        self.error: str | None = None

    @property
    def loaded(self) -> bool:
        return self._obj is not None

    def get(self) -> Any:
        with self._lock:
            if self._obj is None:
                t0 = time.monotonic()
                before = self._allocated()
                try:
                    self._obj = self._loader()
                except Exception as exc:  # noqa: BLE001
                    self.error = f"{type(exc).__name__}: {exc}"[:300]
                    raise
                self.error = None
                self.load_sec = round(time.monotonic() - t0, 2)
                after = self._allocated()
                if after is not None and before is not None:
                    self.weights_mib = round((after - before) / 2**20, 1)
                self.loaded_at = time.time()
                self.loads += 1
            self.last_used = time.monotonic()
            return self._obj

    @contextmanager
    def using(self) -> Iterator[Any]:
        """The loaded model, held for one prediction: never released while held."""
        with self._busy_lock:
            self._busy += 1
        try:
            yield self.get()
        finally:
            with self._busy_lock:
                self._busy -= 1
            self.last_used = time.monotonic()

    def release_if_idle(self, min_idle_s: float) -> dict[str, Any] | None:
        """Unload when loaded, not held by a prediction and unused for ``min_idle_s`` seconds.

        ``None`` when nothing is loaded (or loading); otherwise ``{"model", "released", "why",
        "freed_gib"}``. Never waits: a slot whose lock is taken (loading) is reported as in use."""
        if self._obj is None and not self._busy:
            return None
        why = idle_verdict(self._busy, self.last_used, time.monotonic(), min_idle_s)
        if why is None and not self._lock.acquire(blocking=False):
            why = "in use"
        elif why is None:
            try:  # re-check under the lock: a prediction may have started meanwhile
                if self._obj is None:
                    return None
                why = idle_verdict(self._busy, self.last_used, time.monotonic(), min_idle_s)
                if why is None:
                    self.unload()
                    return {"model": self.name, "released": True, "why": None, "freed_gib": self.need_gib}
            finally:
                self._lock.release()
        return {"model": self.name, "released": False, "why": why, "freed_gib": 0.0}

    def touch_peak(self) -> None:
        try:
            torch = _torch()
            if torch.cuda.is_available():
                self.peak_mib = round(torch.cuda.max_memory_allocated() / 2**20, 1)
        except Exception:  # noqa: BLE001
            pass

    @staticmethod
    def _allocated() -> int | None:
        try:
            torch = _torch()
            return torch.cuda.memory_allocated() if torch.cuda.is_available() else None
        except Exception:  # noqa: BLE001
            return None

    def unload(self) -> bool:
        with self._lock:
            if self._obj is None:
                return False
            self._obj = None
            gc.collect()
            try:
                torch = _torch()
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except Exception:  # noqa: BLE001
                pass
            self.unloads += 1
            return True

    def maybe_unload(self, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        if self._obj is not None and not self._busy and now - self.last_used > self.idle_sec:
            with self._lock:  # re-check: a prediction may be loading or holding it
                if self._busy or self._obj is None:
                    return False
                return self.unload()
        return False

    def status(self) -> dict[str, Any]:
        return {
            "name": self.name, "loaded": self.loaded, "loads": self.loads, "unloads": self.unloads,
            "load_sec": self.load_sec, "weights_gpu_mib": self.weights_mib, "peak_gpu_mib": self.peak_mib,
            "idle_unload_sec": self.idle_sec,
            "idle_for_sec": round(time.monotonic() - self.last_used, 1) if self.loaded else None,
            "error": self.error,
        }


# ── Chronos-2 ──────────────────────────────────────────────────────────────


class Chronos2Forecaster:
    name = "chronos-2"
    licence = "Apache-2.0 (model card amazon/chronos-2; package chronos-forecasting Apache-2.0)"

    def __init__(self, model_id: str = "amazon/chronos-2", device: str = "auto", dtype: str = "float32",
                 idle_sec: float = 600.0, batch_size: int = 256) -> None:
        self.model_id = model_id
        self.device = _device(device)
        self.dtype = dtype
        self.batch_size = batch_size
        self.slot = ModelSlot(self.name, self._load, idle_sec, need_gib=2.0)  # peak 1.6 GiB, 1.8 reserved

    def _load(self):
        torch = _torch()
        from chronos import Chronos2Pipeline  # noqa: PLC0415

        dt = torch.bfloat16 if self.dtype == "bfloat16" else torch.float32
        return Chronos2Pipeline.from_pretrained(self.model_id, device_map=self.device, dtype=dt)

    def predict(self, inputs: list[SeriesInput], horizon: int) -> list[QuantileForecast]:
        with self.slot.using() as pipe:  # held: never released mid-prediction
            return self._predict(pipe, inputs, horizon)

    def _predict(self, pipe: Any, inputs: list[SeriesInput], horizon: int) -> list[QuantileForecast]:
        batch = []
        for inp in inputs:
            item: dict[str, Any] = {"target": np.asarray(inp.target, dtype=np.float32)}
            if inp.past_cov:
                item["past_covariates"] = {k: np.asarray(v, dtype=np.float32) for k, v in inp.past_cov.items()}
                item["future_covariates"] = {k: np.asarray(v, dtype=np.float32)
                                             for k, v in inp.future_cov.items()}
            batch.append(item)
        quantiles, _mean = pipe.predict_quantiles(batch, prediction_length=horizon,
                                                  quantile_levels=list(QUANTILES), batch_size=self.batch_size)
        self.slot.touch_peak()
        self.slot.last_used = time.monotonic()
        out = []
        for q in quantiles:
            arr = q.detach().float().cpu().numpy()[0]  # (horizon, 3)
            out.append(QuantileForecast(arr[:, 0], arr[:, 1], arr[:, 2]).sorted())
        return out


# ── TimesFM 2.5 (contender) ───────────────────────────────────────────────


class TimesFMForecaster:
    name = "timesfm-2.5"
    licence = "Apache-2.0 (model card google/timesfm-2.5-200m-pytorch; package timesfm Apache-2.0)"

    def __init__(self, model_id: str = "google/timesfm-2.5-200m-pytorch", idle_sec: float = 600.0,
                 max_context: int = 1536, max_horizon: int = 128) -> None:
        self.model_id = model_id
        self.max_context = max_context
        self.max_horizon = max_horizon
        self.slot = ModelSlot(self.name, self._load, idle_sec, need_gib=3.5)  # peak 3.6 GiB process-wide

    def _load(self):
        import timesfm  # noqa: PLC0415

        m = timesfm.TimesFM_2p5_200M_torch.from_pretrained(self.model_id, torch_compile=False)
        m.compile(timesfm.ForecastConfig(
            max_context=self.max_context, max_horizon=self.max_horizon, normalize_inputs=True,
            per_core_batch_size=128,
            use_continuous_quantile_head=True, force_flip_invariance=True, infer_is_positive=True,
            fix_quantile_crossing=True))
        return m

    def predict(self, inputs: list[SeriesInput], horizon: int) -> list[QuantileForecast]:
        with self.slot.using() as m:  # held: never released mid-prediction
            return self._predict(m, inputs, horizon)

    def _predict(self, m: Any, inputs: list[SeriesInput], horizon: int) -> list[QuantileForecast]:
        _point, q = m.forecast(horizon=horizon,
                               inputs=[np.asarray(i.target[-self.max_context:], dtype=float) for i in inputs])
        self.slot.touch_peak()
        self.slot.last_used = time.monotonic()
        q = np.asarray(q)
        # quantile head: index 0 = mean, 1..9 = q10..q90
        return [QuantileForecast(q[i, :, 1], q[i, :, 5], q[i, :, 9]).sorted() for i in range(q.shape[0])]
