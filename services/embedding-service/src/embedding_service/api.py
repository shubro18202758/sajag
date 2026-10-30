"""Transport-neutral API handlers (C3 endpoints).

Plain async functions over dataclass-ish dicts — no FastAPI import here, so
the whole request/response contract is unit-testable without the web layer.
``service.py`` wraps these in FastAPI routes; ``client.py`` shows the exact
wire shapes callers should use.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

from . import config
from .encoders import encoder_model, truncate_for_embedding
from .incidents import IncidentIngestor
from .retrieval import HybridRetriever
from .store import MemoryStore
from .writer import embed_and_upsert


class ApiError(Exception):
    def __init__(self, status: int, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.detail = detail


@dataclass
class EmbeddingApi:
    """Handlers backing the C3 endpoints plus the read-only /embed and /pii/spans."""

    store: MemoryStore
    retriever: HybridRetriever
    ingestor: IncidentIngestor
    started_at: float = field(default_factory=time.time)
    pii: Any = None  # embedding_service.pii.PiiTracerDetector (or a fake); None = route answers 503

    # GET /health
    async def health(self) -> dict:
        late, dense = self.retriever._late, self.retriever._dense
        models: dict[str, Any] = {
            "late": {"model": encoder_model(late, "late") or getattr(late, "name", "unknown"),
                     **_status(late)},
            "dense": {"model": encoder_model(dense, "dense") or getattr(dense, "name", "unknown"),
                      "dim": getattr(dense, "dim", None), **_status(dense)},
            "rank_mode": self.retriever.rank_mode,
            "recall_fallback_active": self.retriever.dense_error is not None,
        }
        if self.pii is not None:
            models["pii"] = {"model": getattr(self.pii, "model_name", "unknown"),
                             "loaded": bool(getattr(self.pii, "loaded", False))}
        return {
            "status": "ok",
            "service": "embedding-service",
            "late_encoder": getattr(late, "name", "unknown"),
            "dense_encoder": getattr(dense, "name", "unknown"),
            "models": models,
            "gpu": _gpu_memory(),
            "uptime_sec": round(time.time() - self.started_at, 1),
        }

    # POST /embed — read-only dense vectors (OSINT semantic dedup); stores nothing
    async def embed(self, payload: dict) -> dict:
        texts = _texts(payload)
        dense = self.retriever._dense
        try:
            vectors = await asyncio.to_thread(dense.encode, texts)
        except Exception as exc:  # noqa: BLE001 - the caller falls back (OSINT: lexical similarity)
            raise ApiError(503, f"dense encoder unavailable: {str(exc)[:200]}") from exc
        return {
            "vectors": vectors,
            "model": encoder_model(dense, "dense") or getattr(dense, "name", "unknown"),
            "dim": getattr(dense, "dim", len(vectors[0]) if vectors else 0),
            "normalized": True,
        }

    # POST /pii/spans — read-only PII spans (PII-Tracer, defence in depth); stores nothing
    async def pii_spans(self, payload: dict) -> dict:
        texts = _texts(payload)
        if self.pii is None:
            raise ApiError(503, "PII model disabled (EMBED_PII=0)")
        try:
            spans = await asyncio.to_thread(self.pii.detect, texts)
        except Exception as exc:  # noqa: BLE001 - the caller fails open to its rules
            raise ApiError(503, f"PII model unavailable: {str(exc)[:200]}") from exc
        return {
            "spans": spans,
            "model": getattr(self.pii, "model_name", "unknown"),
            "labels": list(getattr(self.pii, "labels", ())),
        }

    # POST /embed/documents
    async def embed_documents(self, payload: dict) -> dict:
        documents = payload.get("documents")
        if not isinstance(documents, list) or not documents:
            raise ApiError(400, "documents must be a non-empty list")
        if len(documents) > config.MAX_BATCH_DOCS:
            raise ApiError(
                400, f"batch of {len(documents)} exceeds cap {config.MAX_BATCH_DOCS}"
            )
        kind = payload.get("kind", "pattern")
        if kind not in config.MEMORY_DOC_KINDS:
            raise ApiError(
                400,
                f"kind {kind!r} not allowed; whitelist: {config.MEMORY_DOC_KINDS}",
            )
        doc_ids: list[str] = []
        late = self.retriever._late
        dense = self.retriever._dense
        for i, doc in enumerate(documents):
            if not isinstance(doc, dict) or not str(doc.get("body", "")).strip():
                raise ApiError(400, f"documents[{i}].body must be non-empty text")
            if doc.get("metadata") is not None and not isinstance(doc.get("metadata"), dict):
                raise ApiError(400, f"documents[{i}].metadata must be an object")
            title = str(doc.get("title") or f"doc-{i}")
            body = truncate_for_embedding(str(doc["body"]))
            ref_id = str(doc.get("ref_id") or f"batch:{int(time.time()*1000)}:{i}")
            doc_id = await embed_and_upsert(
                self.store, late, dense,
                kind=kind, ref_id=ref_id, title=title, body=body,
                metadata=doc.get("metadata") or {},
                movement_id=doc.get("movement_id"),
                occurred_at=doc.get("occurred_at"),
            )
            doc_ids.append(doc_id)
        return {"embedded": len(doc_ids), "doc_ids": doc_ids}

    # POST /search  (hybrid: dense ANN recall_k=100 → MaxSim rerank top-20)
    async def search(self, payload: dict) -> dict:
        query = payload.get("query")
        if not isinstance(query, str) or not query.strip():
            raise ApiError(400, "query must be non-empty text")
        kinds = payload.get("kinds")
        if kinds is not None and (
            not isinstance(kinds, list)
            or any(k not in config.MEMORY_DOC_KINDS for k in kinds)
        ):
            raise ApiError(400, f"kinds must be a subset of {list(config.MEMORY_DOC_KINDS)}")
        try:
            response = await self.retriever.search(
                query,
                kinds=kinds,
                top_k=int(payload.get("top_k", config.DEFAULT_TOP_K)),
                recall_k=int(payload.get("recall_k", config.DEFAULT_RECALL_K)),
                movement_id=payload.get("movement_id"),
                rank_mode=payload.get("rank"),
            )
        except ValueError as exc:
            raise ApiError(400, str(exc)) from exc
        return response.to_dict()

    # POST /incidents
    async def record_incident(self, payload: dict) -> dict:
        if not isinstance(payload, dict):
            raise ApiError(400, "body must be a JSON object")
        if payload.get("scenario_run") or "scenario_id" in payload:
            result = await self.ingestor.ingest_scenario_run(
                payload.get("scenario_run") or payload,
                movement_id=payload.get("movement_id"),
                scenario_run_id=payload.get("scenario_run_id"),
                segment_ids=payload.get("segment_ids"),
            )
            if result is None:
                raise ApiError(
                    400,
                    "scenario_run must be a ScenarioResult-shaped object "
                    "with scenario_id and numeric total_disruption_vehicle_hours",
                )
            return {
                "incident_id": result.incident_id,
                "memory_doc_id": result.doc_id,
                "source": "scenario_run",
            }

        summary = payload.get("summary")
        if not isinstance(summary, str) or not summary.strip():
            raise ApiError(400, "summary must be non-empty text")
        result = await self.ingestor.ingest_live_incident(
            incident_kind=str(payload.get("incident_kind", "other")),
            severity=str(payload.get("severity", "medium")),
            summary=summary,
            segment_ids=payload.get("segment_ids"),
            movement_id=payload.get("movement_id"),
            details=payload.get("details"),
            embed=bool(payload.get("embed", True)),
        )
        if result is None:
            raise ApiError(
                400,
                f"incident_kind/severity must be within whitelists "
                f"{list(config.INCIDENT_KINDS)} / {list(config.INCIDENT_SEVERITIES)}",
            )
        return {
            "incident_id": result.incident_id,
            "memory_doc_id": result.doc_id,
            "source": "live",
        }

    # GET /incidents/recent
    async def recent_incidents(self, params: dict[str, Any] | None = None) -> dict:
        params = params or {}
        limit_raw = params.get("limit", "20")
        try:
            limit = max(1, min(int(limit_raw), 100))
        except (TypeError, ValueError) as exc:
            raise ApiError(400, "limit must be an integer") from exc
        kinds = params.get("kind")
        kind_list = None
        if kinds:
            kind_list = [k for k in str(kinds).split(",") if k]
            bad = [k for k in kind_list if k not in config.INCIDENT_KINDS]
            if bad:
                raise ApiError(
                    400,
                    f"unknown incident kinds {bad}; whitelist: "
                    f"{list(config.INCIDENT_KINDS)}",
                )
        incidents = await self.store.recent_incidents(limit=limit, kinds=kind_list)
        return {"incidents": incidents}


def _gpu_memory() -> dict | None:
    """CUDA memory of this process (GiB) when torch is already loaded; never imports torch itself."""
    import sys

    torch = sys.modules.get("torch")
    if torch is None:
        return None
    try:
        if not torch.cuda.is_available():
            return None
        return {"reserved_gib": round(torch.cuda.memory_reserved() / 2**30, 2),
                "allocated_gib": round(torch.cuda.memory_allocated() / 2**30, 2),
                "peak_allocated_gib": round(torch.cuda.max_memory_allocated() / 2**30, 2)}
    except Exception:  # noqa: BLE001 - health must never fail on a probe
        return None


def _status(encoder: Any) -> dict:
    status = getattr(encoder, "status", None)
    return status() if callable(status) else {"loaded": None, "load_error": None, "load_seconds": None}


def _texts(payload: Any) -> list[str]:
    """Validate the read-only routes' ``{"texts": [...]}`` body (bounded count and length)."""
    texts = payload.get("texts") if isinstance(payload, dict) else None
    if not isinstance(texts, list) or not texts:
        raise ApiError(400, "texts must be a non-empty list")
    if len(texts) > config.MAX_EMBED_TEXTS:
        raise ApiError(400, f"at most {config.MAX_EMBED_TEXTS} texts per request")
    out = []
    for i, t in enumerate(texts):
        if not isinstance(t, str):
            raise ApiError(400, f"texts[{i}] must be a string")
        if len(t) > config.MAX_EMBED_TEXT_CHARS:
            raise ApiError(400, f"texts[{i}] exceeds {config.MAX_EMBED_TEXT_CHARS} characters")
        out.append(t)
    return out


__all__ = ["ApiError", "EmbeddingApi"]
