"""Lazy load, memory floor and idle unload."""

from __future__ import annotations

import pytest

from speech_service.runtime import LazyModel, ModelUnavailable


def test_loads_once_and_reuses() -> None:
    loads = []
    m = LazyModel("x", lambda: loads.append(1) or object(), need_gib=1, min_free_gib=1,
                  idle_unload_s=60, mem_probe=lambda: 100.0)
    a, b = m.get(), m.get()
    assert a is b and loads == [1] and m.loaded


def test_refuses_below_the_memory_floor() -> None:
    m = LazyModel("tts", object, need_gib=8, min_free_gib=12, idle_unload_s=60,
                  mem_probe=lambda: 15.0)
    with pytest.raises(ModelUnavailable, match="15.0 GiB available"):
        m.get()
    assert not m.loaded and "refused" in m.status()["last_error"]


def test_loader_failure_becomes_unavailable() -> None:
    def boom():
        raise OSError("weights missing")

    m = LazyModel("asr", boom, need_gib=1, min_free_gib=1, idle_unload_s=60, mem_probe=lambda: 99.0)
    with pytest.raises(ModelUnavailable, match="weights missing"):
        m.get()


def test_idle_unload() -> None:
    m = LazyModel("x", object, need_gib=1, min_free_gib=1, idle_unload_s=0.01,
                  mem_probe=lambda: 99.0)
    m.get()
    import time

    time.sleep(0.03)
    assert m.maybe_unload_idle() is True
    assert not m.loaded
    assert m.maybe_unload_idle() is False


def test_default_floor_keeps_two_gib_clear_of_the_host_memory_guard() -> None:
    """29 Oct audit: 15.4 GiB available refused a 4 GiB ASR load under the old 12 GiB floor."""
    from speech_service.asr import WhisperASR
    from speech_service.config import DEFAULT_MIN_FREE_GIB, Settings

    assert DEFAULT_MIN_FREE_GIB == 8.0
    assert Settings().min_free_gib == DEFAULT_MIN_FREE_GIB
    asr = WhisperASR("openai/whisper-large-v3-turbo")
    assert asr._lazy._min_free == DEFAULT_MIN_FREE_GIB  # noqa: SLF001
    ok = LazyModel("asr", object, need_gib=4.0, min_free_gib=DEFAULT_MIN_FREE_GIB,
                   idle_unload_s=60, mem_probe=lambda: 15.4)
    assert ok.get() is not None  # 11.4 GiB left after the load
    low = LazyModel("asr", object, need_gib=4.0, min_free_gib=DEFAULT_MIN_FREE_GIB,
                    idle_unload_s=60, mem_probe=lambda: 11.5)
    with pytest.raises(ModelUnavailable, match="8 GiB floor"):
        low.get()  # would leave 7.5 GiB: too close to the 6 GiB eviction line


def test_a_refused_load_is_logged(caplog) -> None:
    m = LazyModel("tts", object, need_gib=5, min_free_gib=8, idle_unload_s=60,
                  mem_probe=lambda: 10.0)
    with caplog.at_level("WARNING", logger="speech.runtime"), pytest.raises(ModelUnavailable):
        m.get()
    assert any("refused to load tts" in r.getMessage() for r in caplog.records)
