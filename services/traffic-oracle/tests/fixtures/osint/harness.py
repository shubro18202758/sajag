"""Run one OS-5 test against either backend: the in-memory fake (always) or the sandbox database
(``OSINT_TEST_DSN``, int3c / int3cl only).  Same app, same routes, same assertions.

The app is the real ``create_app()`` (so the real OSINT router is mounted by coordination.py) over
the backend's pool; the client connects as loopback (``http://127.0.0.1``), so the deck-verified
``x-sajag-officer`` header is honoured exactly as in production.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from fixtures.osint.db import DSN_ENV, Cleanup, osint_db
from fixtures.osint.fakedb import FakeOsintConn, FakeOsintDB, FakePool
from fixtures.osint.signals import FakePipeline
from traffic_oracle.city import common
from traffic_oracle.osint import ingest, live_state, store

__all__ = ["BACKENDS", "Backend", "backend", "client", "make_app", "reset_osint_state"]

#: The parametrisation every dual-mode test uses.
BACKENDS = [
    "fake",
    pytest.param("db", marks=pytest.mark.skipif(not os.environ.get(DSN_ENV), reason=f"{DSN_ENV} not set")),
]


@dataclass
class Backend:
    kind: str
    pool: Any
    db: FakeOsintDB | None = None
    conn: FakeOsintConn | None = None
    cleanup: Cleanup | None = None

    def track(self, *signals: Any) -> None:
        if self.cleanup is not None:
            self.cleanup.signal_ids.update(s.signal_id for s in signals)

    def track_event(self, event_id: str | None) -> None:
        if self.cleanup is not None and event_id:
            self.cleanup.event_ids.add(str(event_id))


@asynccontextmanager
async def backend(kind: str, tag: str, *, migrated: bool = True) -> AsyncIterator[Backend]:
    if kind == "fake":
        db = FakeOsintDB(migrated=migrated)
        conn = FakeOsintConn(db)
        yield Backend(kind, FakePool(conn), db=db, conn=conn)
        return
    # on a shared sandbox the re-fusion window holds only this test's rows: the "fetched in the
    # last 72 h" span is closed (seeded captures were fetched recently) and every test signal is
    # published decades ago (signals.RUN_SHIFT), so the "published within 72 h" span is ours alone
    saved = store.FETCHED_WINDOW_HOURS
    store.FETCHED_WINDOW_HOURS = 0
    try:
        async with osint_db(tag) as (pool, cleanup):
            yield Backend(kind, pool, cleanup=cleanup)
    finally:
        store.FETCHED_WINDOW_HOURS = saved


def reset_osint_state() -> None:
    """Forget every process-level cache the OSINT surfaces keep (probes, gazetteer sync, hooks)."""
    common.reset_relation_cache()
    store.reset_gazetteer_sync()
    store.GAZETTEER_LOADER = None
    store.CLASSIFIER_HOOK = None
    ingest.PIPELINE_HOOK = None
    ingest.reset_pipeline_cache()
    # (getattr: the harness also loads against older modules, for before/after runs)
    for reset in (getattr(store, "reset_role_probe", None), getattr(live_state, "reset_route_cache", None)):
        if reset is not None:
            reset()
    if hasattr(ingest, "HANDLE_STRIPPER_HOOK"):
        ingest.HANDLE_STRIPPER_HOOK = None


def make_app(pool: Any, pipeline: FakePipeline | None = None) -> Any:
    from traffic_oracle.__main__ import create_app

    reset_osint_state()
    store.GAZETTEER_LOADER = lambda: []  # tests never sync the real gazetteer into a sandbox
    app = create_app()
    app.state.pool = pool
    app.state.adaptive_valkey = None
    app.state.graph_db = None
    if pipeline is not None:
        app.dependency_overrides[ingest.get_pipeline] = pipeline.pipeline
    return app


def client(app: Any) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://127.0.0.1")
