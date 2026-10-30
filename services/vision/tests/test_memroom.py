"""Making room before a memory refusal, and POST /admin/release (fake memory and peers; no model).

The only process started here is a ``sleep`` in its own session, standing in for llama-server so the
real stop path (SIGTERM to its process group) is exercised."""

from __future__ import annotations

import asyncio
import socket
import subprocess
import time
import urllib.error
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from vision_service import model as model_mod
from vision_service.api import create_app
from vision_service.config import Settings
from vision_service.memroom import RoomMaker
from vision_service.model import LlamaServerManager, LlamaVisionModel, ModelUnavailable

LOOPBACK = ("127.0.0.1", 50000)


class Mem:
    def __init__(self, free: float) -> None:
        self.free = free

    def __call__(self) -> float:
        return self.free


class Clock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t

    def sleep(self, s: float) -> None:
        self.t += s


def _settings(tmp_path: Path, **kw) -> Settings:
    for n in ("llama-server", "m.gguf", "mm.gguf"):
        (tmp_path / n).write_bytes(b"x")
    return Settings(llama_server_bin=tmp_path / "llama-server", model_path=tmp_path / "m.gguf",
                    mmproj_path=tmp_path / "mm.gguf", need_gib=8, min_free_gib=8, **kw)


def _manager(tmp_path: Path, monkeypatch, mem: Mem, call) -> tuple[LlamaServerManager, list, Clock]:
    """A manager whose start succeeds without a process; memory is ``mem``; peers answer ``call``."""
    monkeypatch.setattr(model_mod, "_mem_available_gib", mem)
    starts: list[int] = []

    async def fake_start(self) -> bool:
        starts.append(1)
        return True

    monkeypatch.setattr(LlamaServerManager, "_start_once", fake_start)
    clock = Clock()
    mgr = LlamaServerManager(_settings(tmp_path))
    mgr.room = RoomMaker("vision", [("forecast", 8195), ("speech", 8194)], call=call,
                         probe=lambda: model_mod._mem_available_gib(), sleep=clock.sleep, clock=clock)
    return mgr, starts, clock


def test_refused_then_made_room_then_started(tmp_path: Path, monkeypatch) -> None:
    mem, asked = Mem(12.0), []  # 8 GiB model + 8 GiB floor needs 16

    def call(port: int, timeout: float, idle_s: float = 0.0) -> dict:
        asked.append(port)
        if port == 8195:  # forecast frees its ~2 GiB: not enough on its own
            mem.free += 1.6
            return {"released": ["chronos-2"], "freed_gib_estimate": 2.0, "kept": []}
        mem.free += 5.0  # speech's Parler worker exits
        return {"released": ["tts:ai4bharat/indic-parler-tts (worker)"], "freed_gib_estimate": 5.0, "kept": []}

    mgr, starts, _ = _manager(tmp_path, monkeypatch, mem, call)
    assert asyncio.run(mgr.ensure()) == mgr.url and starts == [1]
    assert asked == [8195, 8194]
    ev = mgr.room.last_event
    assert ev["free_before_gib"] == 12.0 and ev["free_after_gib"] == 18.6 and ev["enough"] is True
    assert [r["service"] for r in ev["released"]] == ["forecast", "speech"]
    assert ev["freed_gib_estimate"] == 7.0 and ev["load_succeeded"] is True


def test_a_small_shortfall_stops_at_the_first_peer(tmp_path: Path, monkeypatch) -> None:
    mem, asked = Mem(15.0), []

    def call(port: int, timeout: float, idle_s: float = 0.0) -> dict:
        asked.append(port)
        mem.free += 1.6
        return {"released": ["chronos-2"], "freed_gib_estimate": 2.0, "kept": []}

    mgr, starts, _ = _manager(tmp_path, monkeypatch, mem, call)
    asyncio.run(mgr.ensure())
    assert asked == [8195] and starts == [1]  # speech's models were never touched


def test_nothing_idle_to_release_still_refuses_with_a_clear_reason(tmp_path: Path, monkeypatch) -> None:
    mem = Mem(12.0)

    def call(port: int, timeout: float, idle_s: float = 0.0) -> dict:
        return {"released": [], "freed_gib_estimate": 0.0,
                "kept": [{"model": "asr:marathi-whisper", "why": "in use"}] if port == 8194 else []}

    mgr, starts, clock = _manager(tmp_path, monkeypatch, mem, call)
    with pytest.raises(ModelUnavailable) as exc:
        asyncio.run(mgr.ensure())
    msg = str(exc.value)
    assert msg.startswith("refused to start the vision model: 12.0 GiB available") and "8 GiB floor" in msg
    assert "nothing idle to release (speech: asr:marathi-whisper in use)" in msg
    assert starts == [] and clock.t == 0.0
    assert mgr.room.last_event["load_succeeded"] is False and mgr.last_error == msg


def test_peers_down_is_best_effort_and_still_refuses_cleanly(tmp_path: Path, monkeypatch) -> None:
    def call(port: int, timeout: float, idle_s: float = 0.0) -> dict:
        raise urllib.error.URLError(ConnectionRefusedError(111, "Connection refused"))

    mgr, starts, _ = _manager(tmp_path, monkeypatch, Mem(12.0), call)
    with pytest.raises(ModelUnavailable, match="forecast: unreachable; speech: unreachable"):
        asyncio.run(mgr.ensure())
    assert starts == []


def test_a_peer_that_times_out_is_waited_for(tmp_path: Path, monkeypatch) -> None:
    mem = Mem(12.0)

    def call(port: int, timeout: float, idle_s: float = 0.0) -> dict:
        raise urllib.error.URLError(socket.timeout("timed out"))

    mgr, starts, clock = _manager(tmp_path, monkeypatch, mem, call)
    with pytest.raises(ModelUnavailable, match="no answer within 2 s"):
        asyncio.run(mgr.ensure())
    assert 5.0 <= clock.t <= 5.5 and starts == []


def test_a_start_that_fails_after_making_room_is_recorded(tmp_path: Path, monkeypatch) -> None:
    mem = Mem(12.0)

    def call(port: int, timeout: float, idle_s: float = 0.0) -> dict:
        mem.free = 30.0
        return {"released": ["m"], "freed_gib_estimate": 8.0, "kept": []}

    mgr, _, _ = _manager(tmp_path, monkeypatch, mem, call)

    async def fail(self) -> bool:
        self.last_error = "llama-server exited with 1"
        return False

    async def no_wait(_s: float) -> None:
        return None

    monkeypatch.setattr(LlamaServerManager, "_start_once", fail)
    monkeypatch.setattr(model_mod.asyncio, "sleep", no_wait)
    with pytest.raises(ModelUnavailable, match="exited with 1"):
        asyncio.run(mgr.ensure())
    ev = mgr.room.last_event
    assert ev["enough"] is True and ev["load_succeeded"] is False and "exited with 1" in ev["load_error"]


def test_a_start_that_runs_out_of_gpu_memory_makes_room_before_its_retry(tmp_path: Path, monkeypatch) -> None:
    """The floor check passed (20 GiB) but llama.cpp could not allocate: room for the model's size, then the retry."""
    mem, asked, tries = Mem(20.0), [], []

    def call(port: int, timeout: float, idle_s: float = 0.0) -> dict:
        asked.append(port)
        mem.free += 8.0
        return {"released": ["chronos-2"], "freed_gib_estimate": 2.0, "kept": []}

    mgr, _, _ = _manager(tmp_path, monkeypatch, mem, call)

    async def start(self) -> bool:
        tries.append(mem.free)
        if len(tries) == 1:
            self.last_error = "llama-server exited with 134: ggml_cuda_init: failed to allocate"
            return False
        return True

    async def no_wait(_s: float) -> None:
        return None

    monkeypatch.setattr(LlamaServerManager, "_start_once", start)
    monkeypatch.setattr(model_mod.asyncio, "sleep", no_wait)
    assert asyncio.run(mgr.ensure()) == mgr.url
    assert tries == [20.0, 28.0] and asked == [8195]
    ev = mgr.room.last_event
    assert ev["reason"] == "the server ran out of GPU memory while starting" and ev["needed_gib"] == 28.0
    assert ev["load_succeeded"] is True


def test_a_start_that_fails_for_another_reason_makes_no_room(tmp_path: Path, monkeypatch) -> None:
    mgr, _, _ = _manager(tmp_path, monkeypatch, Mem(20.0), lambda p, t, i=0.0: pytest.fail("made room for a crash"))

    async def start(self) -> bool:
        self.last_error = "llama-server exited with 1: unknown model architecture"
        return False

    async def no_wait(_s: float) -> None:
        return None

    monkeypatch.setattr(LlamaServerManager, "_start_once", start)
    monkeypatch.setattr(model_mod.asyncio, "sleep", no_wait)
    with pytest.raises(ModelUnavailable, match="unknown model architecture"):
        asyncio.run(mgr.ensure())
    assert mgr.room.last_event is None


def test_the_model_builds_its_room_from_settings_forecast_first(tmp_path: Path) -> None:
    m = LlamaVisionModel(_settings(tmp_path, peer_forecast_port=8195, peer_speech_port=8194))
    assert m.manager.room.peers == [("forecast", 8195), ("speech", 8194)]
    assert LlamaVisionModel(_settings(tmp_path, make_room=False)).manager.room is None
    assert LlamaVisionModel(Settings(llm_manage=False)).manager is None  # an external server: nothing to stop


def test_peers_are_asked_to_release_whatever_is_not_serving_right_now(tmp_path: Path, monkeypatch) -> None:
    mem, seen = Mem(12.0), []

    def call(port: int, timeout: float, idle_s: float = -1.0) -> dict:
        seen.append((port, idle_s))
        mem.free = 20.0
        return {"released": ["tts:parler (worker)"], "freed_gib_estimate": 5.0, "kept": []}

    mgr, starts, _ = _manager(tmp_path, monkeypatch, mem, call)
    asyncio.run(mgr.ensure())
    assert seen == [(8195, 0.0)] and starts == [1]
    m = LlamaVisionModel(_settings(tmp_path, peer_forecast_port=8195, peer_speech_port=8194))
    assert m.manager.room.release_idle_s == 0.0  # VISION_MAKE_ROOM_IDLE_S: a waiting start has priority


def test_readiness_says_a_request_would_make_room_first(tmp_path: Path, monkeypatch) -> None:
    mgr, _, _ = _manager(tmp_path, monkeypatch, Mem(12.0), lambda p, t, i=0.0: {})
    r = mgr.readiness()
    assert r["ready"] is False and "release idle models" in r["reason"]


def test_tests_never_point_at_the_live_peers() -> None:
    s = Settings()
    assert s.peer_forecast_port == 0 and s.peer_speech_port == 0  # conftest: no live service is ever asked


# --- release ------------------------------------------------------------------

def _running_model(tmp_path: Path) -> LlamaVisionModel:
    """A managed model whose "llama-server" is a harmless sleep in its own process group."""
    m = LlamaVisionModel(_settings(tmp_path, make_room=False))
    m.manager._proc = subprocess.Popen(["sleep", "60"], start_new_session=True)  # noqa: SLF001, S603, S607
    return m


def test_release_never_stops_a_model_that_is_serving(tmp_path: Path) -> None:
    m = _running_model(tmp_path)
    try:
        m._busy = 1  # noqa: SLF001 - a road-state request is running
        out = asyncio.run(m.release_idle(0))
        assert out["released"] == [] and out["kept"] == [{"model": m.name, "why": "in use"}]
        assert m.manager.running
        m._busy = 0  # noqa: SLF001
        m._last_used = time.monotonic() - 5  # noqa: SLF001
        out = asyncio.run(m.release_idle(20))
        assert out["kept"] == [{"model": m.name, "why": "used 5s ago"}] and m.manager.running
        assert asyncio.run(m.maybe_stop_idle()) is False  # nor does the idle reaper
    finally:
        asyncio.run(m.aclose())


def test_release_waits_for_no_start_in_progress(tmp_path: Path) -> None:
    m = _running_model(tmp_path)

    async def scenario() -> dict:
        async with m.manager.lock:  # a start (or stop) is under way
            return await asyncio.wait_for(m.release_idle(0), 1.0)

    try:
        assert asyncio.run(scenario())["kept"] == [{"model": m.name, "why": "in use"}]
    finally:
        asyncio.run(m.aclose())


def test_release_stops_an_idle_server(tmp_path: Path) -> None:
    m = _running_model(tmp_path)
    proc = m.manager._proc  # noqa: SLF001
    out = asyncio.run(m.release_idle(0))
    assert out["released"] == [m.name] and out["freed_gib_estimate"] == 8.0 and out["kept"] == []
    assert "reloads on its next use" in out["note"]
    assert not m.manager.running and proc.poll() is not None
    assert asyncio.run(m.release_idle(0))["released"] == []  # nothing left to release


# --- the API ------------------------------------------------------------------

def test_admin_release_contract_and_health(tmp_path: Path) -> None:
    m = _running_model(tmp_path)
    m._last_used = time.monotonic() - 60  # noqa: SLF001
    app = create_app(_settings(tmp_path, make_room=False), model=m)
    with TestClient(app, client=LOOPBACK) as c:
        out = c.post("/admin/release").json()
        assert out["released"] == [m.name] and out["freed_gib_estimate"] == 8.0
        h = c.get("/health").json()
        assert h["make_room"]["last_release"]["released"] == [m.name]
        assert h["make_room"]["enabled"] is False and "reloads on its next use" in h["make_room"]["note"]
    assert not m.manager.running


def test_admin_release_refuses_non_loopback_and_browser_callers(tmp_path: Path) -> None:
    m = _running_model(tmp_path)
    m._last_used = time.monotonic() - 60  # noqa: SLF001
    app = create_app(_settings(tmp_path, make_room=False), model=m)
    with TestClient(app, client=("10.1.2.3", 40000)) as c:
        assert c.post("/admin/release").status_code == 403
        assert m.manager.running
    m.manager._proc = subprocess.Popen(["sleep", "60"], start_new_session=True)  # noqa: SLF001, S603, S607
    with TestClient(app, client=LOOPBACK) as c:
        r = c.post("/admin/release", headers={"Referer": "http://127.0.0.1:5373/field"})
        assert r.status_code == 403 and "machine callers" in r.json()["detail"]
        assert m.manager.running


def test_health_shows_the_last_make_room_event(tmp_path: Path, monkeypatch) -> None:
    mem = Mem(12.0)

    def call(port: int, timeout: float, idle_s: float = 0.0) -> dict:
        mem.free = 20.0
        return {"released": ["chronos-2"], "freed_gib_estimate": 2.0, "kept": []}

    mgr, _, clock = _manager(tmp_path, monkeypatch, mem, call)
    m = LlamaVisionModel(_settings(tmp_path))
    m.manager = mgr
    asyncio.run(mgr.ensure())
    with TestClient(create_app(_settings(tmp_path), model=m)) as c:
        mr = c.get("/health").json()["make_room"]
    assert mr["enabled"] is True and mr["asks"] == ["forecast :8195", "speech :8194"]
    assert mr["last_event"]["load_succeeded"] is True and mr["last_event"]["released"][0]["service"] == "forecast"
    mgr._proc = None  # noqa: SLF001 - the fake start left no process


def test_a_fake_model_without_release_answers_empty(tmp_path: Path) -> None:
    from fakes import FakeModel

    with TestClient(create_app(Settings(llm_manage=False), model=FakeModel()), client=LOOPBACK) as c:
        out = c.post("/admin/release").json()
    assert out["released"] == [] and out["kept"] == [] and out["freed_gib_estimate"] == 0.0


def test_the_memroom_copies_match() -> None:
    here = Path(__file__).resolve().parents[1] / "src" / "vision_service" / "memroom.py"
    services = here.parents[3]
    for other in (services / "speech" / "src" / "speech_service" / "memroom.py",
                  services / "forecast" / "src" / "forecast" / "memroom.py"):
        if other.is_file():
            assert other.read_bytes() == here.read_bytes(), f"{other} differs: edit the copies together"
