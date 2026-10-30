"""The schedule: every scheduled connector at start-up, then each at its cadence ± jitter; the probe loop."""

from __future__ import annotations

import asyncio
import random

from osint_ingress.scheduler import Scheduler, probe_loop


class FakeEngine:
    def __init__(self, names: list[str]) -> None:
        self._names = names
        self.cycles: list[list[str]] = []
        self.probes = 0

        class _Pub:
            async def probe(inner) -> bool:  # noqa: N805 - a tiny stand-in
                self.probes += 1
                return True

        self.publisher = _Pub()

    def scheduled_names(self) -> list[str]:
        return list(self._names)

    async def cycle(self, names: list[str]) -> None:
        self.cycles.append(list(names))


def test_first_tick_runs_every_scheduled_connector_then_cadences_apply():
    eng = FakeEngine(["sachet_cap", "google_news_rss", "gdelt_events"])
    clock = [0.0]
    s = Scheduler(eng, {"sachet_cap": 300, "google_news_rss": 600, "gdelt_events": 900, "common_crawl": 0},
                  jitter=0.1, rng=random.Random(7), clock=lambda: clock[0])
    assert sorted(s.due()) == ["gdelt_events", "google_news_rss", "sachet_cap"]
    assert "common_crawl" not in s.cadences  # cadence 0: never scheduled
    s.reschedule(s.due())
    assert s.due() == []
    for name, base in (("sachet_cap", 300), ("google_news_rss", 600), ("gdelt_events", 900)):
        assert base * 0.9 <= s.next_due[name] <= base * 1.1  # ± 10 % jitter
    clock[0] = 330.0
    assert s.due() == ["sachet_cap"]


def test_connectors_outside_the_engine_schedule_are_ignored():
    eng = FakeEngine(["sachet_cap"])
    s = Scheduler(eng, {"sachet_cap": 300, "mumbai_police_scrape": 3600})
    assert list(s.cadences) == ["sachet_cap"]


async def test_run_executes_due_cycles_until_stopped():
    eng = FakeEngine(["sachet_cap", "reddit_rss"])
    s = Scheduler(eng, {"sachet_cap": 300, "reddit_rss": 900}, jitter=0.0)
    stop = asyncio.Event()
    task = asyncio.create_task(s.run(stop))
    await asyncio.sleep(0.05)
    stop.set()
    await asyncio.wait_for(task, timeout=5)
    assert eng.cycles == [["sachet_cap", "reddit_rss"]]


async def test_a_failing_cycle_does_not_stop_the_schedule():
    eng = FakeEngine(["sachet_cap"])

    async def boom(names):  # noqa: ANN001
        eng.cycles.append(names)
        raise RuntimeError("synthetic failure")

    eng.cycle = boom  # type: ignore[method-assign]
    s = Scheduler(eng, {"sachet_cap": 300})
    stop = asyncio.Event()
    task = asyncio.create_task(s.run(stop))
    await asyncio.sleep(0.05)
    stop.set()
    await asyncio.wait_for(task, timeout=5)
    assert eng.cycles == [["sachet_cap"]] and s.next_due["sachet_cap"] > 0


async def test_probe_loop_probes_at_start_and_periodically():
    """Event-driven, not a fixed sleep (a loaded box may run the loop late): the first probe comes before the first
    wait, and three probes arrive well inside a generous bound at a 10 ms interval."""
    eng = FakeEngine([])
    stop = asyncio.Event()
    third = asyncio.Event()
    probe = eng.publisher.probe

    async def counting_probe() -> bool:
        ok = await probe()
        if eng.probes >= 3:
            third.set()
        return ok

    eng.publisher.probe = counting_probe  # type: ignore[method-assign]
    task = asyncio.create_task(probe_loop(eng, stop, interval_sec=0.01))
    await asyncio.sleep(0)  # one turn of the loop: the start-up probe runs before any wait
    assert eng.probes == 1
    await asyncio.wait_for(third.wait(), timeout=10)
    stop.set()
    await asyncio.wait_for(task, timeout=5)
    assert eng.probes >= 3


async def test_probe_loop_stops_promptly_while_waiting():
    eng = FakeEngine([])
    stop = asyncio.Event()
    task = asyncio.create_task(probe_loop(eng, stop, interval_sec=3600))
    await asyncio.sleep(0)
    stop.set()
    await asyncio.wait_for(task, timeout=5)  # an hour-long interval does not hold the shutdown
    assert eng.probes == 1
