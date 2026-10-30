"""FastAPI wiring for the C3 endpoints.

POST /embed/documents   — encode + upsert memory docs (late + dense)
POST /search            — hybrid: dense ANN recall_k=100 → MaxSim top-20
POST /incidents         — record a live incident OR a simulation scenario run
GET  /incidents/recent  — recent incident/pattern memory
GET  /health            — service heartbeat (+ models, load state, fallback)
POST /embed             — read-only dense vectors (OSINT semantic dedup)
POST /pii/spans         — read-only PII spans (PII-Tracer; OSINT defence in depth)

FastAPI/pydantic are imported lazily; the handlers themselves live in
``api.py`` and are transport-neutral.
"""

from __future__ import annotations

from typing import Any

import logging
import threading

from . import config
from .api import ApiError, EmbeddingApi
from .db import create_pool
from .encoders import build_dense_encoder, build_late_encoder
from .incidents import IncidentIngestor
from .retrieval import HybridRetriever
from .store import MemoryStore

logger = logging.getLogger("embedding_service.service")


def build_api(
    store: MemoryStore,
    late_encoder: Any,
    dense_encoder: Any,
    *,
    pii: Any = None,
    rank_mode: str | None = None,
) -> EmbeddingApi:
    """Assemble handlers over injected store + encoders (tests use fakes)."""
    retriever = HybridRetriever(store, late_encoder, dense_encoder, rank_mode=rank_mode)
    ingestor = IncidentIngestor(store, late_encoder, dense_encoder)
    return EmbeddingApi(store=store, retriever=retriever, ingestor=ingestor, pii=pii)


def build_pii_detector() -> Any:
    """PII-Tracer (lazy: weights load on the first /pii/spans call), or None when EMBED_PII=0."""
    if not config.PII_ENABLED:
        return None
    from .pii import PiiTracerDetector

    return PiiTracerDetector(device=config.EMBED_DEVICE)


def warm_up(api: EmbeddingApi) -> None:
    """Load both encoders on a background thread so the first /search is not a cold load.

    Failures are logged and surfaced by /health (``load_error``); a dense
    failure leaves /search on the recency-recall fallback.
    """

    def _run() -> None:
        for label, enc, call in (
            ("late", api.retriever._late, lambda e: e.encode_query("warm up")),
            ("dense", api.retriever._dense, lambda e: e.encode(["warm up"])),
        ):
            try:
                call(enc)
                logger.info("embedding warm-up: %s encoder ready", label)
            except Exception as exc:  # noqa: BLE001
                logger.warning("embedding warm-up: %s encoder failed: %s", label, str(exc)[:200])

    threading.Thread(target=_run, name="embed-warmup", daemon=True).start()


def create_app(api: EmbeddingApi | None = None):
    """Create the FastAPI application (lazy import keeps core testable).

    Pass ``api`` (tests inject fakes); the production factory is
    ``create_app_from_env`` below.
    """
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse

    if api is None:
        raise RuntimeError(
            "create_app() requires an EmbeddingApi; use create_app_from_env()"
        )

    app = FastAPI(title="sajag-embedding-service", version="1.0.0")

    @app.get("/health")
    async def health() -> dict:
        return await api.health()

    @app.post("/embed/documents")
    async def embed_documents(payload: dict) -> dict:
        return await _guard(api.embed_documents(payload))

    @app.post("/search")
    async def search(payload: dict) -> dict:
        return await _guard(api.search(payload))

    @app.post("/incidents")
    async def record_incident(payload: dict) -> dict:
        return await _guard(api.record_incident(payload))

    @app.post("/embed")
    async def embed(payload: dict) -> dict:
        return await _guard(api.embed(payload))

    @app.post("/pii/spans")
    async def pii_spans(payload: dict) -> dict:
        return await _guard(api.pii_spans(payload))

    @app.get("/incidents/recent")
    async def recent_incidents(limit: str = "20", kind: str | None = None) -> dict:
        # NOTE(core fix): this handler previously took ``request: Request``.
        # With ``from __future__ import annotations`` the annotation is a
        # string FastAPI resolves against module globals — and Request was
        # imported INSIDE create_app's closure, so resolution failed and
        # FastAPI fell back to treating it as a required query param
        # (live 422: "field required: query.request").  Explicit query
        # parameters keep the contract typed and the closure bug
        # structurally impossible; ``dict(request.query_params)`` semantics
        # are preserved (unknown params were ignored by the API layer).
        params: dict[str, Any] = {"limit": limit}
        if kind is not None:
            params["kind"] = kind
        return await _guard(api.recent_incidents(params))

    async def _guard(coro):
        try:
            return await coro
        except ApiError as exc:
            return JSONResponse({"detail": exc.detail}, status_code=exc.status)

    return app


class _LazyApi:
    """Delegates to the real EmbeddingApi once the startup event has built it."""

    def __init__(self) -> None:
        self._real: EmbeddingApi | None = None

    def __getattr__(self, name: str):
        if self._real is None:
            raise RuntimeError("embedding api not initialized yet")
        return getattr(self._real, name)


def build_lazy_app(*, warm: bool | None = None):
    """The production app: pool + encoders are created INSIDE the serving loop.

    (An asyncpg pool is bound to the loop that created it, so building it
    before uvicorn starts its loop fails on the first request.) Encoders come
    from the model registry (EMBED_DENSE_MODEL / EMBED_LATE_MODEL) and load
    lazily; ``warm`` (default: EMBED_WARMUP != 0) preloads them on a thread.
    """
    import os

    lazy = _LazyApi()
    app = create_app(lazy)  # type: ignore[arg-type]
    warm = (os.environ.get("EMBED_WARMUP", "1") not in ("0", "false", "no")) if warm is None else warm

    @app.on_event("startup")
    async def _init_on_serving_loop() -> None:
        pool = await create_pool()
        lazy._real = build_api(
            MemoryStore(pool),
            build_late_encoder(),
            build_dense_encoder(),
            pii=build_pii_detector(),
        )
        if warm:
            warm_up(lazy._real)

    return app


def main() -> None:
    """Run the service with uvicorn (models venv / serve_models.sh)."""
    import uvicorn

    uvicorn.run(
        build_lazy_app(),
        host=config.LISTEN_HOST,
        port=config.LISTEN_PORT,
        log_level="info",
    )


async def create_app_from_env():
    """Kept for callers that await the factory themselves (the pool binds to their loop)."""
    pool = await create_pool()
    api = build_api(
        MemoryStore(pool),
        build_late_encoder(),
        build_dense_encoder(),
        pii=build_pii_detector(),
    )
    return create_app(api)


if __name__ == "__main__":
    main()
