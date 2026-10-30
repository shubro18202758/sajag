"""POST /admin/release: another on-demand service short of memory asks forecast to free its idle models.

No real model: a ModelSlot over fake weights, held the way the forecasters hold it."""

from __future__ import annotations

import asyncio
import threading
import time
from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient

from conftest import ORIGIN
from forecast.api import create_app
from forecast.engine import Engine
from forecast.models import ModelSlot, QuantileForecast, SeriesInput

LOOPBACK = ("127.0.0.1", 50000)


class SlotModel:
    """A forecaster with a lazily loaded slot, holding it per prediction as Chronos-2 does."""

    name = "slot-test-model"
    licence = "test"

    def __init__(self, gate: threading.Event | None = None) -> None:
        self.loads = 0
        self.gate = gate
        self.slot = ModelSlot("chronos-2", self._load, idle_sec=600, need_gib=2.0)

    def _load(self) -> str:
        self.loads += 1
        return "weights"

    def predict(self, inputs: list[SeriesInput], horizon: int) -> list[QuantileForecast]:
        with self.slot.using():
            if self.gate is not None:
                self.gate.wait(5)
            out = []
            for i in inputs:
                p50 = np.full(horizon, float(i.target[-1]))
                out.append(QuantileForecast(p50 - 0.05, p50, p50 + 0.05))
            return out


def test_slot_in_use_is_never_released() -> None:
    m = SlotModel()
    s = m.slot
    assert s.release_if_idle(0) is None  # nothing loaded
    with s.using():
        assert s.release_if_idle(0) == {"model": "chronos-2", "released": False, "why": "in use", "freed_gib": 0.0}
        assert s.maybe_unload(now=time.monotonic() + 10_000) is False  # nor by the idle reaper
    kept = s.release_if_idle(20)
    assert kept["released"] is False and kept["why"] == "used 0s ago" and s.loaded
    assert s.release_if_idle(0) == {"model": "chronos-2", "released": True, "why": None, "freed_gib": 2.0}
    assert not s.loaded and s.unloads == 1
    with s.using() as w:  # reloads on its next use
        assert w == "weights" and m.loads == 2


def test_a_prediction_running_in_a_thread_keeps_the_model(settings, net) -> None:
    gate = threading.Event()
    model = SlotModel(gate)
    eng = Engine(settings, net, model=model)
    t = threading.Thread(target=lambda: asyncio.run(eng.forecasts(now=ORIGIN)))
    t.start()
    try:
        deadline = time.monotonic() + 5
        while not model.slot._busy and time.monotonic() < deadline:  # noqa: SLF001
            time.sleep(0.01)
        model.slot.last_used -= 600
        out = eng.release_idle(0)
        assert out["released"] == [] and out["kept"] == [{"model": "chronos-2", "why": "in use"}]
    finally:
        gate.set()
        t.join(10)
    assert model.slot.loaded
    assert eng.release_idle(0)["released"] == ["chronos-2"]


def test_a_loading_slot_is_reported_in_use_without_waiting() -> None:
    started, finish = threading.Event(), threading.Event()

    def slow():
        started.set()
        finish.wait(5)
        return "weights"

    s = ModelSlot("chronos-2", slow, idle_sec=600)
    t = threading.Thread(target=lambda: s.using().__enter__())
    t.start()
    try:
        assert started.wait(5)
        t0 = time.monotonic()
        assert s.release_if_idle(0)["why"] == "in use"
        assert time.monotonic() - t0 < 1.0
    finally:
        finish.set()
        t.join(5)


def _client(settings, net, model, **kw) -> TestClient:
    eng = Engine(settings, net, model=model)
    asyncio.run(eng.forecasts(now=ORIGIN))  # loads the slot once
    eng.s.cache_ttl_sec = 1e9
    return TestClient(create_app(settings, engine=eng), **kw)


def test_admin_release_contract_and_health(settings, net) -> None:
    model = SlotModel()
    with _client(settings, net, model, client=LOOPBACK) as c:
        kept = c.post("/admin/release").json()  # just used: kept at the default 20 s
        assert kept["released"] == [] and kept["kept"][0]["why"].startswith("used ")
        model.slot.last_used -= 60
        out = c.post("/admin/release").json()
        assert out == {"service": "forecast", "released": ["chronos-2"], "freed_gib_estimate": 2.0, "kept": [],
                       "note": "released models are not restarted; each reloads on its next use"}
        h = c.get("/health").json()
        assert h["model"]["slot"]["loaded"] is False
        assert h["make_room"]["last_release"]["released"] == ["chronos-2"]
        assert h["make_room"]["enabled"] is False  # forecast has no memory floor of its own
        # the next forecast reloads it
        assert c.post("/forecast/refresh").status_code == 200 and model.slot.loaded and model.loads == 2


def test_admin_release_refuses_non_loopback_and_browser_callers(settings, net) -> None:
    model = SlotModel()
    with _client(settings, net, model, client=("10.1.2.3", 40000)) as c:
        model.slot.last_used -= 60
        assert c.post("/admin/release").status_code == 403
        assert model.slot.loaded
    with _client(settings, net, model, client=LOOPBACK) as c:
        model.slot.last_used -= 60
        r = c.post("/admin/release", headers={"X-Forwarded-For": "203.0.113.9"})
        assert r.status_code == 403 and "machine callers" in r.json()["detail"]
        assert c.post("/admin/release", params={"idle_s": -1}).status_code == 422
        assert model.slot.loaded  # (the app's own shutdown unloads it afterwards)


def test_the_memroom_copies_match() -> None:
    here = Path(__file__).resolve().parents[1] / "src" / "forecast" / "memroom.py"
    services = here.parents[3]
    for other in (services / "speech" / "src" / "speech_service" / "memroom.py",
                  services / "vision" / "src" / "vision_service" / "memroom.py"):
        if other.is_file():
            assert other.read_bytes() == here.read_bytes(), f"{other} differs: edit the copies together"
