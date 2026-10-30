"""The schedule: each connector at its own cadence, with jitter, plus the independent oracle probe.

Cadences (``config.DEFAULT_CADENCE_SEC``; ``OSINT_CADENCE_<CONNECTOR>_SEC`` overrides, 0 takes a connector off):
SACHET 5 min, Google News 10 min, GDELT bulk and DOC 15 min, Reddit 15 min, the official pages hourly, Common
Crawl never (backfill only). Each next run is ``cadence × (1 ± jitter)`` after the last one, so the box never
polls on round minutes in step with anyone else.

At start-up every scheduled connector runs once (one cycle); afterwards a tick runs only the connectors that are
due, as one cycle (one publish). The oracle probe runs immediately and every ``probe_interval_sec`` (≤ 30 s)
whatever the connectors do (plan R7).
"""

from __future__ import annotations

import asyncio
import random
import time
from collections.abc import Callable

import structlog

from osint_ingress.runner import Engine

__all__ = ["Scheduler", "probe_loop"]

log = structlog.get_logger("osint_ingress.scheduler")


class Scheduler:
    def __init__(
        self,
        engine: Engine,
        cadences: dict[str, int],
        *,
        jitter: float = 0.1,
        rng: random.Random | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.engine = engine
        self.cadences = {n: c for n, c in cadences.items() if c > 0 and n in engine.scheduled_names()}
        self.jitter = jitter
        self.rng = rng or random.Random()
        self.clock = clock
        self.next_due: dict[str, float] = {}

    def _interval(self, name: str) -> float:
        base = float(self.cadences[name])
        return max(1.0, base * (1.0 + self.rng.uniform(-self.jitter, self.jitter)))

    def due(self, now: float | None = None) -> list[str]:
        now = self.clock() if now is None else now
        return [n for n in self.cadences if self.next_due.get(n, 0.0) <= now]

    def reschedule(self, names: list[str], now: float | None = None) -> None:
        now = self.clock() if now is None else now
        for n in names:
            self.next_due[n] = now + self._interval(n)

    def seconds_to_next(self, now: float | None = None) -> float:
        now = self.clock() if now is None else now
        if not self.next_due:
            return 0.0
        return max(0.0, min(self.next_due.values()) - now)

    async def run(self, stop: asyncio.Event) -> None:
        """Run until ``stop`` is set. A failing cycle is logged and the schedule goes on."""
        while not stop.is_set():
            names = self.due()
            if names:
                try:
                    await self.engine.cycle(names)
                except Exception as exc:  # noqa: BLE001 - the service must outlive any one cycle
                    log.error("cycle_failed", error=type(exc).__name__)
                self.reschedule(names)
            try:
                await asyncio.wait_for(stop.wait(), timeout=max(1.0, self.seconds_to_next()))
            except TimeoutError:
                pass


async def probe_loop(engine: Engine, stop: asyncio.Event, *, interval_sec: float = 30.0) -> None:
    """``GET {oracle}/health`` now and every ``interval_sec`` until ``stop`` (independent of posting)."""
    while not stop.is_set():
        await engine.publisher.probe()
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval_sec)
        except TimeoutError:
            pass
