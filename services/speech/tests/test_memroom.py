"""Making room before a memory refusal, and POST /admin/release (fake memory, fake peers; no model)."""

from __future__ import annotations

import http.server
import json
import socket
import threading
import time
import urllib.error
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from fakes import FakeTTS, tone_wav
from speech_service.api import create_app, make_room_maker, release_idle_models
from speech_service.asr import Transcript
from speech_service.config import Settings
from speech_service.memroom import RoomMaker, loopback_refusal, post_release
from speech_service.runtime import LazyModel, ModelUnavailable

LOOPBACK = ("127.0.0.1", 50000)


class Mem:
    """A fake MemAvailable that tests move."""

    def __init__(self, free: float) -> None:
        self.free = free

    def __call__(self) -> float:
        return self.free


class Clock:
    def __init__(self) -> None:
        self.t = 0.0
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.t

    def sleep(self, s: float) -> None:
        self.sleeps.append(s)
        self.t += s


def _room(mem: Mem, clock: Clock, call, peers=(("forecast", 8195), ("vision", 8196)), own=None) -> RoomMaker:
    return RoomMaker("speech", list(peers), own_release=own, call=call, probe=mem,
                     sleep=clock.sleep, clock=clock, timeout_s=2.0, wait_s=5.0)


def _asr(mem: Mem, loads: list | None = None) -> LazyModel:
    """A 4 GiB model under the 8 GiB floor: it needs 12 GiB available."""
    loads = loads if loads is not None else []
    return LazyModel("asr:test", lambda: loads.append(1) or "weights", need_gib=4.0, min_free_gib=8.0,
                     idle_unload_s=600, mem_probe=mem)


# --- the make-room path --------------------------------------------------------

def test_refused_then_made_room_then_loaded() -> None:
    mem, clock, loads, asked = Mem(10.0), Clock(), [], []

    def call(port: int, timeout: float, idle_s: float = 0.0) -> dict:
        asked.append((port, timeout))
        if port == 8195:  # forecast: busy a moment ago, keeps its model
            return {"released": [], "freed_gib_estimate": 0.0, "kept": [{"model": "chronos-2", "why": "used 3s ago"}]}
        mem.free += 7.6  # vision's llama-server exits
        return {"released": ["Qwen3-VL-8B"], "freed_gib_estimate": 8.0, "kept": []}

    lm = _asr(mem, loads)
    lm.room = room = _room(mem, clock, call)
    assert lm.get() == "weights" and loads == [1]
    assert asked == [(8195, 2.0), (8196, 2.0)]  # forecast first (cheap to reload), 2 s each
    ev = room.last_event
    assert ev["for"] == "asr:test" and ev["needed_gib"] == 12.0
    assert ev["free_before_gib"] == 10.0 and ev["free_after_gib"] == 17.6 and ev["enough"] is True
    assert ev["released"] == [{"service": "vision", "models": ["Qwen3-VL-8B"], "freed_gib_estimate": 8.0}]
    assert {"service": "forecast", "model": "chronos-2", "why": "used 3s ago"} in ev["kept"]
    assert ev["load_succeeded"] is True and "reloads on its next use" in ev["note"]
    assert clock.sleeps == []  # memory was back at once: no waiting


def test_memory_that_comes_back_slowly_is_polled_for_up_to_the_wait() -> None:
    mem, clock = Mem(10.0), Clock()

    def call(port: int, timeout: float, idle_s: float = 0.0) -> dict:
        return {"released": ["m"], "freed_gib_estimate": 8.0, "kept": []} if port == 8196 else {}

    def probe() -> float:  # the peer's process takes about 1.5 s to exit
        return 10.0 if clock.t < 1.5 else 18.0

    lm = LazyModel("asr:test", lambda: "w", need_gib=4.0, min_free_gib=8.0, idle_unload_s=600, mem_probe=mem)
    lm.room = RoomMaker("speech", [("forecast", 8195), ("vision", 8196)], call=call, probe=probe,
                        sleep=clock.sleep, clock=clock, wait_s=5.0, poll_s=0.25)
    assert lm.get() == "w"
    assert 1.5 <= clock.t < 5.0


def test_nothing_idle_to_release_still_refuses_with_a_clear_reason(caplog) -> None:
    mem, clock = Mem(10.0), Clock()

    def call(port: int, timeout: float, idle_s: float = 0.0) -> dict:
        model = "chronos-2" if port == 8195 else "Qwen3-VL-8B"
        return {"released": [], "freed_gib_estimate": 0.0, "kept": [{"model": model, "why": "in use"}]}

    loads: list = []
    lm = _asr(mem, loads)
    lm.room = room = _room(mem, clock, call)
    with caplog.at_level("INFO"), pytest.raises(ModelUnavailable) as exc:
        lm.get()
    msg = str(exc.value)
    assert "refused to load asr:test: 10.0 GiB available" in msg and "8 GiB floor" in msg  # the floor is unchanged
    assert "nothing idle to release" in msg and "vision: Qwen3-VL-8B in use" in msg
    assert loads == [] and not lm.loaded
    assert clock.sleeps == []  # nothing was released, so there was nothing to wait for
    assert room.last_event["enough"] is False and room.last_event["load_succeeded"] is False
    assert any("made room for asr:test" in r.getMessage() for r in caplog.records)  # the journal says so too


def test_peers_down_is_best_effort_and_still_refuses_cleanly() -> None:
    mem, clock = Mem(10.0), Clock()

    def call(port: int, timeout: float, idle_s: float = 0.0) -> dict:
        if port == 8195:
            raise urllib.error.URLError(ConnectionRefusedError(111, "Connection refused"))
        raise urllib.error.URLError(socket.timeout("timed out"))

    lm = _asr(mem)
    lm.room = room = _room(mem, clock, call)
    with pytest.raises(ModelUnavailable) as exc:
        lm.get()
    msg = str(exc.value)
    assert "forecast: unreachable" in msg and "vision: no answer within 2 s" in msg
    ev = room.last_event
    assert ev["errors"] == {"forecast": "unreachable",
                            "vision": "no answer within 2 s (it may still be releasing)"}
    assert 5.0 <= clock.t <= 5.5  # a peer that timed out may still be releasing: memory was polled ~5 s
    assert ev["load_succeeded"] is False


def test_a_peer_error_does_not_stop_the_next_peer() -> None:
    mem, clock = Mem(10.0), Clock()

    def call(port: int, timeout: float, idle_s: float = 0.0) -> dict:
        if port == 8195:
            raise urllib.error.HTTPError("http://127.0.0.1:8195/admin/release", 404, "Not Found", None, None)
        mem.free = 20.0
        return {"released": ["Qwen3-VL-8B"], "freed_gib_estimate": 8.0, "kept": []}

    lm = _asr(mem)
    lm.room = room = _room(mem, clock, call)
    assert lm.get() == "weights"
    assert room.last_event["errors"] == {"forecast": "HTTP 404"} and room.last_event["load_succeeded"] is True


def test_room_is_not_asked_when_memory_suffices() -> None:
    mem = Mem(30.0)
    lm = _asr(mem)
    lm.room = room = _room(mem, Clock(), lambda p, t, i=0.0: pytest.fail("asked a peer with memory to spare"))
    assert lm.get() == "weights" and room.last_event is None and room.attempts == 0


def test_a_load_that_fails_after_making_room_is_recorded() -> None:
    mem, clock = Mem(10.0), Clock()

    def call(port: int, timeout: float, idle_s: float = 0.0) -> dict:
        mem.free = 30.0
        return {"released": ["m"], "freed_gib_estimate": 8.0, "kept": []}

    def boom():
        raise OSError("weights missing")

    lm = LazyModel("asr:test", boom, need_gib=4.0, min_free_gib=8.0, idle_unload_s=600, mem_probe=mem)
    lm.room = room = _room(mem, clock, call)
    with pytest.raises(ModelUnavailable, match="weights missing"):
        lm.get()
    assert room.last_event["enough"] is True and room.last_event["load_succeeded"] is False
    assert "weights missing" in room.last_event["load_error"]


class _Leaf:
    """A backend over one LazyModel, as the real ones are."""

    def __init__(self, lm: LazyModel) -> None:
        self._lazy = lm

    def lazy_models(self) -> list[LazyModel]:
        return [self._lazy]


def test_own_idle_model_is_released_first_and_the_peers_are_not_asked() -> None:
    mem, clock = Mem(8.0), Clock()
    asr = LazyModel("asr:mr", lambda: "asr-weights", need_gib=4.0, min_free_gib=8.0, idle_unload_s=600,
                    mem_probe=mem)
    tts = LazyModel("tts:parler (worker)", lambda: "worker", need_gib=5.0, min_free_gib=8.0,
                    idle_unload_s=600, mem_probe=mem)
    mem.free = 20.0
    asr.get()                     # loaded for a voice report a minute ago
    asr._last_used -= 60          # noqa: SLF001
    mem.free = 9.0                # the box got tight since
    stopped = []
    asr.on_release = lambda: (stopped.append("asr"), setattr(mem, "free", mem.free + 4.2))
    backends = (_Leaf(asr), _Leaf(tts))
    room = make_room_maker(Settings(peer_forecast_port=8195, peer_vision_port=8196), backends,
                           call=lambda p, t, i=0.0: pytest.fail("asked a peer although its own idle model sufficed"),
                           probe=mem, sleep=clock.sleep, clock=clock)
    tts.room = room
    assert tts.get() == "worker"
    assert stopped == ["asr"] and not asr.loaded
    ev = room.last_event
    assert ev["asked"] == ["speech (own)"]
    assert ev["released"] == [{"service": "speech", "models": ["asr:mr"], "freed_gib_estimate": 4.0}]
    assert ev["load_succeeded"] is True


# --- a load that passed the floor check but ran out of GPU memory --------------------

def _oom_once(mem: Mem, attempts: list, times: int = 1):
    def loader():
        attempts.append(round(mem.free, 1))
        if len(attempts) <= times:
            raise RuntimeError("CUDA error: out of memory")
        return "weights"
    return loader


def test_a_load_that_runs_out_of_gpu_memory_makes_room_and_is_tried_once_more() -> None:
    """29 Oct, live: 12.4 GiB available passed the 12 GiB check, then CUDA could not allocate (page cache)."""
    mem, clock, attempts, asked = Mem(12.4), Clock(), [], []

    def call(port: int, timeout: float, idle_s: float = 0.0) -> dict:
        asked.append(port)
        if port == 8195:
            mem.free += 1.5
            return {"released": ["chronos-2"], "freed_gib_estimate": 2.0, "kept": []}
        mem.free += 7.5
        return {"released": ["Qwen3-VL-8B"], "freed_gib_estimate": 8.0, "kept": []}

    lm = LazyModel("asr:mr", _oom_once(mem, attempts), need_gib=4.0, min_free_gib=8.0, idle_unload_s=600,
                   mem_probe=mem)
    lm.room = room = _room(mem, clock, call)
    assert lm.get() == "weights"
    assert attempts == [12.4, 21.4]  # the retry ran after both peers released
    ev = room.last_event
    assert ev["reason"] == "the load ran out of GPU memory"
    assert ev["needed_gib"] == 16.4  # the model's size on top of what was available: the floor is not involved
    assert asked == [8195, 8196] and ev["load_succeeded"] is True


def test_out_of_memory_with_nothing_to_release_fails_once_and_says_so() -> None:
    mem, clock, attempts = Mem(12.4), Clock(), []
    lm = LazyModel("asr:mr", _oom_once(mem, attempts), need_gib=4.0, min_free_gib=8.0, idle_unload_s=600,
                   mem_probe=mem)
    lm.room = room = _room(mem, clock, lambda p, t, i=0.0: {"released": [], "kept": [{"model": "m", "why": "in use"}]})
    with pytest.raises(ModelUnavailable) as exc:
        lm.get()
    assert attempts == [12.4]  # not retried: nothing was freed
    assert "out of memory while loading (made room first: nothing idle to release" in str(exc.value)
    assert room.last_event["load_succeeded"] is False


def test_out_of_memory_twice_is_tried_only_once_more() -> None:
    mem, clock, attempts = Mem(12.4), Clock(), []

    def call(port: int, timeout: float, idle_s: float = 0.0) -> dict:
        mem.free += 8.0
        return {"released": ["m"], "freed_gib_estimate": 8.0, "kept": []}

    lm = LazyModel("asr:mr", _oom_once(mem, attempts, times=5), need_gib=4.0, min_free_gib=8.0,
                   idle_unload_s=600, mem_probe=mem)
    lm.room = room = _room(mem, clock, call)
    with pytest.raises(ModelUnavailable, match="out of memory"):
        lm.get()
    assert len(attempts) == 2 and room.last_event["load_succeeded"] is False


def test_other_load_errors_and_a_missing_room_are_not_retried() -> None:
    mem, attempts = Mem(30.0), []

    def missing():
        attempts.append(1)
        raise OSError("weights missing")

    lm = LazyModel("asr:mr", missing, need_gib=4.0, min_free_gib=8.0, idle_unload_s=600, mem_probe=mem)
    lm.room = _room(mem, Clock(), lambda p, t, i=0.0: pytest.fail("made room for a non-memory error"))
    with pytest.raises(ModelUnavailable, match="weights missing"):
        lm.get()
    assert attempts == [1]
    oom: list = []
    plain = LazyModel("asr:mr", _oom_once(mem, oom), need_gib=4.0, min_free_gib=8.0, idle_unload_s=600,
                      mem_probe=mem)
    with pytest.raises(ModelUnavailable, match="out of memory"):
        plain.get()  # no room maker: the old behaviour, one attempt
    assert oom == [30.0]


@pytest.mark.parametrize("text,oom", [
    ("CUDA error: out of memory", True), ("CUDA out of memory. Tried to allocate 20.00 MiB", True),
    ("ggml_cuda_init: failed to allocate", True), ("cudaMalloc failed: out of memory", True),
    ("weights missing", False), ("401 Client Error", False)])
def test_what_counts_as_out_of_memory(text: str, oom: bool) -> None:
    from speech_service.memroom import looks_out_of_memory

    assert looks_out_of_memory(RuntimeError(text)) is oom


# --- a waiting load has priority over a model merely kept warm (coordinator, 29 Oct) ---

def test_peers_are_asked_to_release_whatever_is_not_serving_right_now() -> None:
    mem, clock, seen = Mem(10.0), Clock(), []

    def call(port: int, timeout: float, idle_s: float = -1.0) -> dict:
        seen.append(idle_s)
        mem.free = 20.0
        return {"released": ["Qwen3-VL-8B"], "freed_gib_estimate": 8.0, "kept": []}

    lm = _asr(mem)
    room = make_room_maker(Settings(peer_forecast_port=8195, peer_vision_port=0), (), call=call, probe=mem,
                           sleep=clock.sleep, clock=clock)
    lm.room = room
    assert lm.get() == "weights" and seen == [0.0]
    assert room.config()["releases_models_unused_for_s"] == 0.0


def test_live_regression_the_tts_used_seconds_ago_makes_room_for_the_asr() -> None:
    """14:57:10, live: the ASR ran out of GPU memory (cuDevicePrimaryCtxRetain); the Parler worker, used 12 s
    earlier and not speaking, was kept by the 20 s rule and the retry failed. Now it is released."""
    mem, clock, attempts = Mem(14.3), Clock(), []
    tts = LazyModel("tts:parler (worker)", lambda: "worker", need_gib=5.0, min_free_gib=8.0, idle_unload_s=600,
                    mem_probe=mem)
    tts.get()
    tts._last_used -= 12  # noqa: SLF001
    tts.on_release = lambda: setattr(mem, "free", mem.free + 8.8)  # the worker process exits

    def asr_load():
        attempts.append(mem.free)
        if len(attempts) == 1:
            raise RuntimeError("CUDA error: out of memory\nReturning 2 (CUDA_ERROR_OUT_OF_MEMORY) from "
                               "cuDevicePrimaryCtxRetain")
        return "asr"

    asr = LazyModel("asr:mr", asr_load, need_gib=4.0, min_free_gib=8.0, idle_unload_s=600, mem_probe=mem)
    room = make_room_maker(Settings(peer_forecast_port=8195, peer_vision_port=8196), (_Leaf(tts), _Leaf(asr)),
                           call=lambda p, t, i=0.0: pytest.fail("asked a peer although the own TTS sufficed"),
                           probe=mem, free_probe=lambda: 3.1, sleep=clock.sleep, clock=clock)
    asr.room = room
    assert asr.get() == "asr" and not tts.loaded
    ev = room.last_event
    assert ev["released"] == [{"service": "speech", "models": ["tts:parler (worker)"], "freed_gib_estimate": 5.0}]
    assert ev["memfree_before_gib"] == 3.1 and ev["load_succeeded"] is True


def test_a_model_serving_a_request_is_still_never_released_for_room() -> None:
    mem, clock = Mem(14.3), Clock()
    tts = LazyModel("tts:parler (worker)", lambda: "worker", need_gib=5.0, min_free_gib=8.0, idle_unload_s=600,
                    mem_probe=mem)
    asr = LazyModel("asr:mr", _oom_once(mem, [], times=9), need_gib=4.0, min_free_gib=8.0, idle_unload_s=600,
                    mem_probe=mem)
    room = make_room_maker(Settings(peer_forecast_port=0, peer_vision_port=0), (_Leaf(tts), _Leaf(asr)),
                           probe=mem, sleep=clock.sleep, clock=clock)
    asr.room = room
    with tts.using():  # speaking an advisory right now
        with pytest.raises(ModelUnavailable, match="tts:parler \\(worker\\) in use"):
            asr.get()
        assert tts.loaded


def test_post_release_asks_for_idle_seconds_on_the_wire() -> None:
    paths: list[str] = []
    handler = type("H", (_Peer,), {"status": 200})
    orig = handler.do_POST

    def do_post(self) -> None:
        paths.append(self.path)
        orig(self)

    handler.do_POST = do_post
    srv = http.server.HTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        post_release(srv.server_address[1], 2.0, 0.0)
        post_release(srv.server_address[1], 2.0)
    finally:
        srv.shutdown()
    assert paths == ["/admin/release?idle_s=0", "/admin/release"]


def test_the_cuda_context_failure_counts_as_out_of_memory() -> None:
    from speech_service.memroom import looks_out_of_memory

    assert looks_out_of_memory("Returning 2 (CUDA_ERROR_OUT_OF_MEMORY) from cuDevicePrimaryCtxRetain")
    assert looks_out_of_memory("Search for `cudaErrorMemoryAllocation'")


def test_the_cuda_context_is_opened_at_start_and_a_failure_is_not_fatal(monkeypatch, caplog) -> None:
    import sys
    import types

    from speech_service.api import open_cuda_context

    made: list[str] = []
    fake = types.SimpleNamespace(cuda=types.SimpleNamespace(is_available=lambda: True),
                                 zeros=lambda n, device: made.append(device))
    monkeypatch.setitem(sys.modules, "torch", fake)
    assert open_cuda_context(Settings()) is True and made == ["cuda"]
    assert open_cuda_context(Settings(device="cpu")) is False
    assert open_cuda_context(Settings(cuda_context_at_start=False)) is False and made == ["cuda"]

    def boom(n, device):
        raise RuntimeError("CUDA_ERROR_OUT_OF_MEMORY from cuDevicePrimaryCtxRetain")

    fake.zeros = boom
    with caplog.at_level("WARNING", logger="speech.api"):
        assert open_cuda_context(Settings()) is False
    assert any("first model load will try" in r.getMessage() for r in caplog.records)


# --- one load at a time --------------------------------------------------------------

def test_two_models_never_load_at_once_and_the_second_checks_memory_after_the_first() -> None:
    """29 Oct, live: an ASR load beside a loading Parler worker ran out of GPU memory at 20.7 GiB."""
    mem = Mem(30.0)
    events: list[str] = []
    first_in, release_first = threading.Event(), threading.Event()

    def tts_load():
        events.append("tts start")
        first_in.set()
        release_first.wait(5)
        mem.free -= 5.0
        events.append("tts done")
        return "tts"

    def asr_load():
        events.append(f"asr start at {mem.free:.0f} GiB")
        return "asr"

    tts = LazyModel("tts:worker", tts_load, need_gib=5.0, min_free_gib=8.0, idle_unload_s=600, mem_probe=mem)
    asr = LazyModel("asr:mr", asr_load, need_gib=4.0, min_free_gib=8.0, idle_unload_s=600, mem_probe=mem)
    t = threading.Thread(target=tts.get)
    t.start()
    assert first_in.wait(5)
    u = threading.Thread(target=asr.get)
    u.start()
    time.sleep(0.2)
    assert events == ["tts start"]  # the ASR load waits
    release_first.set()
    t.join(5)
    u.join(5)
    assert events == ["tts start", "tts done", "asr start at 25 GiB"]
    assert tts.loaded and asr.loaded


def test_a_loaded_model_never_waits_behind_another_load() -> None:
    mem = Mem(30.0)
    started, finish = threading.Event(), threading.Event()
    asr = _asr(mem)
    asr.get()
    slow = LazyModel("tts:worker", lambda: (started.set(), finish.wait(5), "tts")[-1], need_gib=5.0,
                     min_free_gib=8.0, idle_unload_s=600, mem_probe=mem)
    t = threading.Thread(target=slow.get)
    t.start()
    try:
        assert started.wait(5)
        t0 = time.monotonic()
        with asr.using() as w:
            assert w == "weights"
        assert time.monotonic() - t0 < 0.5
    finally:
        finish.set()
        t.join(5)


def test_a_load_that_waits_too_long_is_refused(monkeypatch) -> None:
    from speech_service import runtime

    monkeypatch.setattr(runtime, "LOAD_WAIT_S", 0.1)
    mem = Mem(30.0)
    started, finish = threading.Event(), threading.Event()
    slow = LazyModel("tts:worker", lambda: (started.set(), finish.wait(5), "tts")[-1], need_gib=5.0,
                     min_free_gib=8.0, idle_unload_s=600, mem_probe=mem)
    t = threading.Thread(target=slow.get)
    t.start()
    try:
        assert started.wait(5)
        with pytest.raises(ModelUnavailable, match="another voice model is still loading"):
            _asr(mem).get()
    finally:
        finish.set()
        t.join(5)


# --- release: never a model that is serving a request --------------------------

def test_a_model_in_use_is_never_released() -> None:
    mem = Mem(50.0)
    lm = _asr(mem)
    hooks: list[str] = []
    lm.on_release = lambda: hooks.append("stop")
    assert lm.release_if_idle(0) is None  # nothing loaded: nothing to report
    with lm.using() as w:
        assert w == "weights"
        assert lm.release_if_idle(0) == {"model": "asr:test", "released": False, "why": "in use", "freed_gib": 0.0}
        assert lm.loaded and hooks == []
    kept = lm.release_if_idle(20)
    assert kept["released"] is False and kept["why"] == "used 0s ago" and lm.loaded
    done = lm.release_if_idle(0)
    assert done == {"model": "asr:test", "released": True, "why": None, "freed_gib": 4.0}
    assert not lm.loaded and hooks == ["stop"]
    # released, not gone: the next request loads it again
    with lm.using() as w:
        assert w == "weights" and lm.loaded


def test_a_request_running_in_another_thread_keeps_its_model() -> None:
    mem = Mem(50.0)
    lm = _asr(mem)
    inside, finish = threading.Event(), threading.Event()

    def request() -> None:
        with lm.using():
            inside.set()
            finish.wait(5)

    t = threading.Thread(target=request)
    t.start()
    try:
        assert inside.wait(5)
        lm._last_used -= 600  # noqa: SLF001 - even "long unused", a held model is kept
        out = release_idle_models((_Leaf(lm),), 0)
        assert out["released"] == [] and out["kept"] == [{"model": "asr:test", "why": "in use"}]
        assert lm.maybe_unload_idle() is False  # nor does the idle reaper take it
    finally:
        finish.set()
        t.join(5)
    assert lm.loaded


def test_a_loading_model_is_reported_in_use_and_release_does_not_wait() -> None:
    mem = Mem(50.0)
    started, finish = threading.Event(), threading.Event()

    def slow_load():
        started.set()
        finish.wait(5)
        return "weights"

    lm = LazyModel("tts:worker", slow_load, need_gib=5.0, min_free_gib=8.0, idle_unload_s=600, mem_probe=mem)
    t = threading.Thread(target=lambda: lm.using().__enter__())
    t.start()
    try:
        assert started.wait(5)
        t0 = time.monotonic()
        out = release_idle_models((_Leaf(lm),), 0)
        assert time.monotonic() - t0 < 1.0
        assert out["kept"] == [{"model": "tts:worker", "why": "in use"}]
    finally:
        finish.set()
        t.join(5)


def test_release_stops_the_parler_worker_process(tmp_path: Path) -> None:
    from test_gated_backends import _worker

    t = _worker(tmp_path, "ok")
    try:
        t.synthesize("हिंदमाता येथे पाणी.", "mr", "female")
        assert t.running
        assert release_idle_models((t,), 20)["kept"][0]["why"].startswith("used ")
        out = release_idle_models((t,), 0)
        assert out["released"] == ["tts:ai4bharat/indic-parler-tts (worker)"] and out["freed_gib_estimate"] == 5.0
        assert not t.running and not t.status()["loaded"]
        audio, _ = t.synthesize("पर्यायी मार्ग वापरा.", "mr", "female")  # reloads on its next use
        assert audio.size and t.running
    finally:
        t.unload()


# --- who may call /admin/release -------------------------------------------------

@pytest.mark.parametrize("host", ["127.0.0.1", "::1", "::ffff:127.0.0.1", "localhost", "127.0.0.2"])
def test_loopback_machine_callers_may_release(host: str) -> None:
    assert loopback_refusal(host, {}) is None


@pytest.mark.parametrize("host", ["10.0.0.5", "192.168.1.20", "testclient", "", None])
def test_other_callers_may_not(host) -> None:
    assert loopback_refusal(host, {}) == "loopback callers only"


@pytest.mark.parametrize("header", ["origin", "referer", "x-forwarded-for", "forwarded", "sec-fetch-site",
                                    "x-sajag-officer"])
def test_a_browser_or_proxied_request_is_refused_even_from_loopback(header: str) -> None:
    assert "machine callers" in loopback_refusal("127.0.0.1", {header: "x"})


# --- the HTTP call to a peer (a real local socket, an ephemeral port) -------------

class _Peer(http.server.BaseHTTPRequestHandler):
    status = 200

    def do_POST(self) -> None:  # noqa: N802
        body = json.dumps({"released": ["m"], "freed_gib_estimate": 2.0, "kept": []}).encode()
        self.send_response(self.status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a) -> None:
        pass


def _serve(status: int):
    handler = type("H", (_Peer,), {"status": status})
    srv = http.server.HTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def test_post_release_reads_the_peer_answer() -> None:
    srv = _serve(200)
    try:
        assert post_release(srv.server_address[1], 2.0)["released"] == ["m"]
    finally:
        srv.shutdown()


def test_a_refusing_or_absent_peer_is_named_in_the_event() -> None:
    srv = _serve(403)
    with socket.socket() as sk:
        sk.bind(("127.0.0.1", 0))
        closed = sk.getsockname()[1]
    try:
        room = RoomMaker("speech", [("forecast", srv.server_address[1]), ("vision", closed)],
                         probe=lambda: 10.0, timeout_s=2.0, wait_s=0.0)
        assert room("asr:test", 4.0, 8.0, 10.0) == 10.0
    finally:
        srv.shutdown()
    assert room.last_event["errors"] == {"forecast": "HTTP 403", "vision": "unreachable"}


# --- the API ----------------------------------------------------------------------

class LazyASR:
    """A backend with a real LazyModel (fake weights) so the API's make-room wiring is exercised."""

    model_id = "lazy-asr"

    def __init__(self, mem: Mem, loader=lambda: "weights") -> None:
        self._lazy = LazyModel("asr:lazy", loader, need_gib=4.0, min_free_gib=8.0,
                               idle_unload_s=600, mem_probe=mem)

    def transcribe(self, samples: np.ndarray, lang: str | None) -> Transcript:
        with self._lazy.using():
            return Transcript("हिंदमाता येथे पाणी", lang or "mr", 0.9, self.model_id, 0.01)

    def status(self) -> dict:
        return {"model": self.model_id, **self._lazy.status()}

    def maybe_unload_idle(self) -> bool:
        return self._lazy.maybe_unload_idle()

    def unload(self) -> bool:
        return self._lazy.unload()

    def lazy_models(self) -> list[LazyModel]:
        return [self._lazy]


def _app(gaz, tmp_path: Path, asr, room=None, **kw):
    s = Settings(tts_cache_dir=tmp_path, **kw)
    return create_app(s, asr=asr, tts=FakeTTS(), gazetteer=gaz, room=room)


def test_api_makes_room_and_health_shows_the_event(gaz, tmp_path: Path) -> None:
    mem, clock = Mem(10.0), Clock()
    asr = LazyASR(mem)

    def call(port: int, timeout: float, idle_s: float = 0.0) -> dict:
        mem.free = 19.0
        return {"released": ["Qwen3-VL-8B"], "freed_gib_estimate": 8.0, "kept": []}

    s = Settings(tts_cache_dir=tmp_path, peer_forecast_port=0, peer_vision_port=8196)
    room = make_room_maker(s, (asr,), call=call, probe=mem, sleep=clock.sleep, clock=clock)
    app = create_app(s, asr=asr, tts=FakeTTS(), gazetteer=gaz, room=room)
    with TestClient(app) as c:
        r = c.post("/speech/transcribe", content=tone_wav(), headers={"content-type": "audio/wav"})
        assert r.status_code == 200, r.text
        mr = c.get("/health").json()["make_room"]
    assert mr["enabled"] is True and mr["asks"] == ["speech (own idle models)", "vision :8196"]
    ev = mr["last_event"]
    assert ev["for"] == "asr:lazy" and ev["load_succeeded"] is True and ev["enough"] is True
    assert ev["released"][0]["service"] == "vision"
    assert "reloads on its next use" in mr["note"]


def test_api_503_after_making_room_carries_the_reason(gaz, tmp_path: Path) -> None:
    mem, clock = Mem(10.0), Clock()
    asr = LazyASR(mem)
    s = Settings(tts_cache_dir=tmp_path, peer_forecast_port=8195, peer_vision_port=0)
    room = make_room_maker(s, (asr,), call=lambda p, t, i=0.0: {"released": [], "kept": [{"model": "chronos-2",
                                                                                   "why": "in use"}]},
                           probe=mem, sleep=clock.sleep, clock=clock)
    with TestClient(create_app(s, asr=asr, tts=FakeTTS(), gazetteer=gaz, room=room)) as c:
        r = c.post("/speech/transcribe", content=tone_wav(), headers={"content-type": "audio/wav"})
    assert r.status_code == 503
    assert "nothing idle to release (forecast: chronos-2 in use)" in r.json()["detail"]


def test_api_out_of_memory_at_load_makes_room_and_answers(gaz, tmp_path: Path) -> None:
    mem, clock, attempts = Mem(12.4), Clock(), []
    asr = LazyASR(mem, _oom_once(mem, attempts))

    def call(port: int, timeout: float, idle_s: float = 0.0) -> dict:
        mem.free = 20.0
        return {"released": ["Qwen3-VL-8B"], "freed_gib_estimate": 8.0, "kept": []}

    s = Settings(tts_cache_dir=tmp_path, peer_forecast_port=0, peer_vision_port=8196)
    room = make_room_maker(s, (asr,), call=call, probe=mem, sleep=clock.sleep, clock=clock)
    with TestClient(create_app(s, asr=asr, tts=FakeTTS(), gazetteer=gaz, room=room)) as c:
        r = c.post("/speech/transcribe", content=tone_wav(), headers={"content-type": "audio/wav"})
        assert r.status_code == 200, r.text
        ev = c.get("/health").json()["make_room"]["last_event"]
    assert ev["reason"] == "the load ran out of GPU memory" and ev["load_succeeded"] is True
    assert len(attempts) == 2


def test_api_out_of_memory_503_keeps_the_make_room_reason(gaz, tmp_path: Path) -> None:
    mem, clock = Mem(12.4), Clock()
    asr = LazyASR(mem, _oom_once(mem, []))
    s = Settings(tts_cache_dir=tmp_path, peer_forecast_port=8195, peer_vision_port=0)
    room = make_room_maker(s, (asr,), call=lambda p, t, i=0.0: {"released": [], "kept": []}, probe=mem,
                           sleep=clock.sleep, clock=clock)
    with TestClient(create_app(s, asr=asr, tts=FakeTTS(), gazetteer=gaz, room=room)) as c:
        r = c.post("/speech/transcribe", content=tone_wav(), headers={"content-type": "audio/wav"})
    assert r.status_code == 503
    assert "out of memory while loading (made room first: nothing idle to release" in r.json()["detail"]


def test_admin_release_contract(gaz, tmp_path: Path) -> None:
    mem = Mem(50.0)
    asr = LazyASR(mem)
    app = _app(gaz, tmp_path, asr)
    with TestClient(app, client=LOOPBACK) as c:
        c.post("/speech/transcribe", content=tone_wav(), headers={"content-type": "audio/wav"})
        kept = c.post("/admin/release").json()  # used a moment ago: kept (default 20 s)
        assert kept["released"] == [] and kept["kept"][0]["model"] == "asr:lazy"
        assert kept["kept"][0]["why"].startswith("used ")
        out = c.post("/admin/release", params={"idle_s": 0}).json()
        assert out["released"] == ["asr:lazy"] and out["freed_gib_estimate"] == 4.0 and out["kept"] == []
        assert "reloads on its next use" in out["note"]
        assert not asr._lazy.loaded  # noqa: SLF001
        h = c.get("/health").json()["make_room"]
        assert h["last_release"]["released"] == ["asr:lazy"]
        # and it comes back on its own next use
        r = c.post("/speech/transcribe", content=tone_wav(), headers={"content-type": "audio/wav"})
        assert r.status_code == 200 and asr._lazy.loaded  # noqa: SLF001


def test_admin_release_refuses_non_loopback_and_browser_callers(gaz, tmp_path: Path) -> None:
    app = _app(gaz, tmp_path, LazyASR(Mem(50.0)))
    with TestClient(app, client=("10.1.2.3", 40000)) as c:
        assert c.post("/admin/release").status_code == 403
    with TestClient(app, client=LOOPBACK) as c:
        r = c.post("/admin/release", headers={"Origin": "http://127.0.0.1:5373"})
        assert r.status_code == 403 and "machine callers" in r.json()["detail"]
        assert c.post("/admin/release", params={"idle_s": -1}).status_code == 422


def test_make_room_can_be_switched_off(gaz, tmp_path: Path) -> None:
    mem = Mem(10.0)
    asr = LazyASR(mem)
    app = _app(gaz, tmp_path, asr, make_room=False)
    assert asr._lazy.room is None  # noqa: SLF001
    with TestClient(app) as c:
        r = c.post("/speech/transcribe", content=tone_wav(), headers={"content-type": "audio/wav"})
        assert r.status_code == 503 and "made room" not in r.json()["detail"]
        assert c.get("/health").json()["make_room"]["enabled"] is False


def test_tests_never_point_at_the_live_peers() -> None:
    s = Settings()
    assert s.peer_forecast_port == 0 and s.peer_vision_port == 0  # conftest: no live service is ever asked


# --- one implementation in three services ------------------------------------------

def test_the_memroom_copies_match() -> None:
    here = Path(__file__).resolve().parents[1] / "src" / "speech_service" / "memroom.py"
    services = here.parents[3]
    for other in (services / "vision" / "src" / "vision_service" / "memroom.py",
                  services / "forecast" / "src" / "forecast" / "memroom.py"):
        if other.is_file():
            assert other.read_bytes() == here.read_bytes(), f"{other} differs: edit the copies together"
