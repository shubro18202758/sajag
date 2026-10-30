"""Decider runtime: loads the decision checkpoint from the verified snapshot
and serves typed (choice/noul/score) decisions with compute-only serialization.

The checkpoint family is a backend (``decider_backends``): ``autojev`` for
protocol v1 (pplx-decider-v1-27b) and ``pplx_decider`` for the protocol v3
joint checkpoints (pplx-decider-v1.2, pplx-decider-flash-v1.2). The C1 HTTP
contract — request and answer shapes, caps, error codes — is the same for
both.

Load path (C1 contract): the model MUST be loaded via the snapshot directory
path. Every file in the HF snapshot is a double symlink into ../../blobs —
a naive copy of the tree yields dangling links, so we never copy.

torch is imported lazily (only by the backends and the CUDA gauges), so the
service's HTTP layer can be tested without it. This module performs NO
outbound HTTP calls.
"""

from __future__ import annotations

import asyncio
import math
import threading
import time
from collections import deque
from pathlib import Path
from typing import Any, Callable

from .config import Settings
from .decider_backends import (
    MAX_OPTIONS,  # noqa: F401 — re-exported (historical import site)
    Backend,
    StateTooLarge,  # noqa: F401 — re-exported for app.py (HTTP 413)
    c1_answer,
    load_backend,
    normalize_questions,
)


class ModelNotReady(RuntimeError):
    """Raised when /decide is called before the weights finish loading."""


class Runtime:
    """Wraps the decider backend with serialization, queueing and metrics."""

    def __init__(
        self,
        settings: Settings,
        backend_factory: Callable[[Settings, Path], Backend] | None = None,
    ) -> None:
        self.settings = settings
        self._backend_factory = backend_factory or load_backend
        self._backend: Backend | None = None
        self._load_error: str | None = None
        self._load_done = threading.Event()
        self._load_started = False
        self._load_lock = threading.Lock()
        self._compute_lock = threading.Lock()   # compute-only serialization
        self._queue_counter = 0                 # running + waiting decides
        self._queue_lock = threading.Lock()
        self._latencies_ms: deque[float] = deque(
            maxlen=max(8, settings.latency_window)
        )
        self._decides_total = 0
        self._decides_failed = 0

    # ─── loading ────────────────────────────────────────────────────────

    def start_load(self) -> None:
        """Kick the (≈285 s cold) load on a daemon thread, once."""
        with self._load_lock:
            if self._load_started:
                return
            self._load_started = True
        threading.Thread(target=self._load_sync, name="decider-load", daemon=True).start()

    def _load_sync(self) -> None:
        try:
            snap = Path(self.settings.snapshot_path)
            if not snap.is_dir():
                raise FileNotFoundError(f"decider snapshot not found: {snap}")
            t0 = time.perf_counter()
            self._backend = self._backend_factory(self.settings, snap)
            print(
                f"[model-host] decider {self._backend.model_name} loaded from {snap} "
                f"(runtime {self._backend.runtime}, {self._backend.question_mode}) "
                f"in {time.perf_counter()-t0:.1f}s",
                flush=True,
            )
            self._warm_sync()
        except Exception as exc:  # noqa: BLE001 — surface any load failure via /health
            self._backend = None
            self._load_error = f"{type(exc).__name__}: {exc}"
            print(f"[model-host] LOAD FAILED: {self._load_error}", flush=True)
        finally:
            self._load_done.set()

    async def wait_loaded(self, timeout_s: float = 600.0) -> None:
        if not self._load_started:
            self.start_load()
        loaded = await asyncio.to_thread(self._load_done.wait, timeout_s)
        if not loaded:
            raise ModelNotReady("decider still loading")
        if self._load_error is not None:
            raise ModelNotReady(f"decider load failed: {self._load_error}")

    # ─── warmup ─────────────────────────────────────────────────────────

    def _warm_sync(self) -> dict[str, Any]:
        result = self._decide_sync(
            "Warmup: convoy platform self-test.",
            {
                "self_test": {
                    "type": "noul",
                    "instructions": "Is this a warmup self-test message?",
                }
            },
        )
        return result

    async def warmup(self) -> dict[str, Any]:
        await self.wait_loaded()
        return await asyncio.to_thread(self._warm_sync)

    # ─── queue admission ────────────────────────────────────────────────

    class _Admission:
        def __init__(self, rt: "Runtime") -> None:
            self.rt = rt

        def __enter__(self) -> None:
            with self.rt._queue_lock:
                if self.rt._queue_counter >= self.rt.settings.queue_depth:
                    raise QueueFull()
                self.rt._queue_counter += 1

        def __exit__(self, *exc: object) -> None:
            with self.rt._queue_lock:
                self.rt._queue_counter -= 1

    def admission(self) -> "Runtime._Admission":
        return self._Admission(self)

    # ─── decide ─────────────────────────────────────────────────────────

    def _decide_sync(
        self, state: str, questions: dict[str, dict[str, Any]]
    ) -> dict[str, Any]:
        """One serialized decide over all questions (C1 response body)."""
        backend = self._backend
        if backend is None:
            raise ModelNotReady("decider not loaded")
        # validate before queueing for compute (422 never waits for the GPU)
        normalize_questions(questions, list_options_described_by_name=True)
        t0 = time.perf_counter()
        with self._compute_lock:
            raw_answers, state_tokens = backend.decide(state, questions)
        latency_ms = (time.perf_counter() - t0) * 1000.0
        self._latencies_ms.append(latency_ms)
        self._decides_total += 1
        return {
            "answers": {name: c1_answer(raw_answers[name]) for name in questions},
            "state_tokens": int(state_tokens),
            "latency_ms": round(latency_ms, 3),
        }

    async def decide(
        self, state: str, questions: dict[str, dict[str, Any]]
    ) -> dict[str, Any]:
        await self.wait_loaded()
        with self.admission():
            try:
                return await asyncio.to_thread(self._decide_sync, state, questions)
            except Exception:
                self._decides_failed += 1
                raise

    # ─── health / metrics ───────────────────────────────────────────────

    @staticmethod
    def _proc_rss_gib() -> float:
        try:
            pages = int(Path("/proc/self/statm").read_text().split()[1])
            return pages * 4096 / (1024 ** 3)
        except Exception:  # noqa: BLE001
            return 0.0

    def p95_latency_ms(self) -> float | None:
        if not self._latencies_ms:
            return None
        ordered = sorted(self._latencies_ms)
        idx = min(len(ordered) - 1, max(0, math.ceil(0.95 * len(ordered)) - 1))
        return round(ordered[idx], 3)

    def cuda_reserved_gib(self) -> float:
        if self._backend is None:
            return 0.0  # nothing resident yet; never import torch just to report 0
        try:
            import torch

            return round(torch.cuda.memory_reserved() / (1024 ** 3), 3)
        except Exception:  # noqa: BLE001
            return 0.0

    @property
    def loaded(self) -> bool:
        return self._backend is not None and self._load_error is None

    def health(self) -> dict[str, Any]:
        return {
            "loaded": self.loaded,
            "loading": self._load_started and not self._load_done.is_set(),
            "load_error": self._load_error,
            "resident_rss_gib": round(self._proc_rss_gib(), 3),
            "cuda_reserved_gib": self.cuda_reserved_gib(),
            "p95_decide_latency_ms": self.p95_latency_ms(),
            "queue_depth": self._queue_counter,
            "decides_total": self._decides_total,
            "decides_failed": self._decides_failed,
            "model": self.settings.model_name,
            "runtime": self._backend.runtime if self._backend else self.settings.runtime,
            "question_mode": (
                self._backend.question_mode if self._backend else self.settings.question_mode
            ),
        }


class QueueFull(Exception):
    """Queue depth exceeded → HTTP 429 + Retry-After (C1)."""
