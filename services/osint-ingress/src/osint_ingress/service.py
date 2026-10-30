"""The HTTP service (FastAPI) on ``HOST``/``PORT`` (default ``127.0.0.1:8193``).

Routes:

* ``GET /health`` — the contract shape (:mod:`.runner`); OS-INT's readiness keys on ``oracle.reachable``.
* ``POST /cycle`` — loopback callers only (403 otherwise): runs one cycle of every scheduled connector now and
  returns its ``last_cycle`` object.

Nothing else is served: no docs, no OpenAPI, and never the cache. The service reads no secret and writes nothing
but its cache. Background tasks: the scheduler (:mod:`.scheduler`) and the oracle probe (start-up, then every
≤ 30 s).
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator
from dataclasses import dataclass

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from osint_ingress import __version__
from osint_ingress.cache import Cache
from osint_ingress.config import USER_AGENT, Settings
from osint_ingress.connectors import build_connectors
from osint_ingress.connectors._protect import default_protect
from osint_ingress.publish import Publisher
from osint_ingress.runner import Engine
from osint_ingress.safe_http import check_oracle_url, make_oracle_client, make_source_client
from osint_ingress.scheduler import Scheduler, probe_loop

__all__ = ["Runtime", "build_runtime", "create_app", "oracle_host"]

_LOOPBACK_CLIENTS = frozenset({"127.0.0.1", "::1", "localhost", "::ffff:127.0.0.1"})


def oracle_host(oracle_url: str) -> str:
    """``http://127.0.0.1:8091`` → ``127.0.0.1:8091`` (the ``/health`` ``oracle.host``)."""
    return check_oracle_url(oracle_url).split("://", 1)[1]


@dataclass
class Runtime:
    settings: Settings
    source_client: httpx.AsyncClient
    oracle_client: httpx.AsyncClient
    engine: Engine

    async def aclose(self) -> None:
        await self.source_client.aclose()
        await self.oracle_client.aclose()


def build_runtime(
    settings: Settings,
    *,
    source_transport: httpx.AsyncBaseTransport | None = None,
    oracle_transport: httpx.AsyncBaseTransport | None = None,
) -> Runtime:
    """Clients, cache, connectors, publisher and engine for ``settings`` (the CLI and the app share it)."""
    source_client = make_source_client(
        user_agent=USER_AGENT, timeout=settings.http_timeout_sec, transport=source_transport
    )
    oracle_client = make_oracle_client(settings.oracle_url, user_agent=USER_AGENT, transport=oracle_transport)
    cache = Cache(settings.cache_dir, retention_hours=settings.retention_hours, max_bytes=settings.retention_bytes)
    publisher = Publisher(
        oracle_client,
        cache,
        oracle_host=oracle_host(settings.oracle_url),
        batch_size=settings.batch_size,
        retries=settings.publish_retries,
        backoff_sec=settings.publish_backoff_sec,
        probe_timeout_sec=settings.probe_timeout_sec,
    )
    engine = Engine(
        mode=settings.mode,
        source_client=source_client,
        publisher=publisher,
        cache=cache,
        connectors=build_connectors(),
        protect=default_protect(str(settings.gazetteer_path) if settings.gazetteer_path else None),
        cadences=settings.cadence_sec,
    )
    return Runtime(settings=settings, source_client=source_client, oracle_client=oracle_client, engine=engine)


def create_app(
    settings: Settings | None = None,
    *,
    source_transport: httpx.AsyncBaseTransport | None = None,
    oracle_transport: httpx.AsyncBaseTransport | None = None,
    background: bool = True,
) -> FastAPI:
    """The FastAPI app. ``background=False`` (tests) starts neither the scheduler nor the probe loop."""
    settings = settings or Settings()

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        rt = build_runtime(settings, source_transport=source_transport, oracle_transport=oracle_transport)
        app.state.runtime = rt
        stop = asyncio.Event()
        tasks: list[asyncio.Task[None]] = []
        if background:
            tasks.append(asyncio.create_task(probe_loop(rt.engine, stop, interval_sec=settings.probe_interval_sec)))
            tasks.append(asyncio.create_task(Scheduler(rt.engine, settings.cadence_sec, jitter=settings.jitter).run(stop)))
        try:
            yield
        finally:
            stop.set()
            for t in tasks:
                t.cancel()
            for t in tasks:
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await t
            await rt.aclose()

    app = FastAPI(
        title="osint-ingress",
        version=__version__,
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    @app.get("/health")
    async def health(request: Request) -> JSONResponse:
        return JSONResponse(request.app.state.runtime.engine.health())

    @app.post("/cycle")
    async def cycle(request: Request) -> JSONResponse:
        client = request.client.host if request.client else ""
        if client not in _LOOPBACK_CLIENTS:
            return JSONResponse({"detail": "loopback callers only"}, status_code=403)
        report = await request.app.state.runtime.engine.cycle()
        return JSONResponse(report.last_cycle())

    return app
