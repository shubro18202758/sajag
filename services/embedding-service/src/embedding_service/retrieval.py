"""Hybrid retrieval: dense ANN recall → late-interaction MaxSim rerank.

This is the T1 MEMORY retrieval path the brain calls for "similar past
situations" (contract C3): bge-m3 dense ANN recall_k=100 over
traffic.memory_docs, then pplx-embed-v2-late MaxSim rerank to top-20.

Documents without token vectors fall back to their dense cosine score,
flagged via ``strategy='dense_fallback'`` — never silently mixed with
MaxSim scores.

Models: recall only compares vectors of the configured dense model (docs
carry a ``metadata.embedding`` marker; unmarked legacy docs are bge-m3).
When the dense encoder is unavailable (failed load, out of memory), recall
falls back to the most recent docs and MaxSim ranks them
(``recall: "recent"``), so the brain's novelty check keeps working.
``config.RANK_MODE='fused'`` ranks by a per-query z-score fusion of dense
cosine and MaxSim instead of MaxSim alone; ``score`` and ``maxsim_score``
keep their meaning (the brain's calibrated MaxSim scale) in both modes.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Sequence

from . import config
from .encoders import (
    DenseEncoderProtocol,
    LateInteractionEncoder,
    TokenVecs,
    encoder_model,
    truncate_for_embedding,
    validate_dense_vector,
)
from .maxsim import cosine, maxsim_score
from .store import MemoryDocRow, MemoryStore

DEFAULT_SEARCH_KINDS: tuple[str, ...] = ("incident", "scenario_run", "aar")
"""Kinds included in the brain's 'similar past situations' contract."""


@dataclass(frozen=True)
class SearchHit:
    doc_id: str
    kind: str
    ref_id: str
    title: str
    snippet: str
    score: float
    maxsim_score: float | None
    dense_score: float | None
    strategy: str
    token_count: int | None
    occurred_at: object | None
    metadata: dict = field(default_factory=dict)
    fused_score: float | None = None

    def to_dict(self) -> dict:
        out = {
            "doc_id": self.doc_id,
            "kind": self.kind,
            "ref_id": self.ref_id,
            "title": self.title,
            "snippet": self.snippet,
            "score": self.score,
            "maxsim_score": self.maxsim_score,
            "dense_score": self.dense_score,
            "strategy": self.strategy,
            "token_count": self.token_count,
            "occurred_at": (
                self.occurred_at.isoformat() if self.occurred_at else None
            ),
            "metadata": self.metadata,
        }
        if self.fused_score is not None:
            out["fused_score"] = self.fused_score
        return out


@dataclass(frozen=True)
class SearchResponse:
    query: str
    results: list[SearchHit]
    query_token_count: int
    recalled: int
    latency_ms: float
    recall: str = "dense"
    rank_mode: str = "maxsim"
    models: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "query_token_count": self.query_token_count,
            "recalled": self.recalled,
            "latency_ms": round(self.latency_ms, 2),
            "recall": self.recall,
            "rank_mode": self.rank_mode,
            "models": self.models,
            "results": [hit.to_dict() for hit in self.results],
        }


def embedding_marker(late_encoder: object, dense_encoder: object | None, *, dense_ok: bool = True) -> dict:
    """The ``metadata.embedding`` marker a stored doc carries: which models wrote its vectors."""
    return {
        "dense": (encoder_model(dense_encoder, "dense") or config.LEGACY_DENSE_MODEL) if dense_ok else None,
        "late": encoder_model(late_encoder, "late") or config.LEGACY_LATE_MODEL,
    }


def _zscores(values: list[float]) -> list[float]:
    if not values:
        return []
    mean = sum(values) / len(values)
    sd = (sum((v - mean) ** 2 for v in values) / len(values)) ** 0.5
    return [0.0 if sd == 0 else (v - mean) / sd for v in values]


def _snippet(body: str, width: int = 240) -> str:
    body = body.strip()
    return body if len(body) <= width else body[: width - 1] + "…"


class HybridRetriever:
    """Dense recall + MaxSim rerank over the memory store."""

    def __init__(
        self,
        store: MemoryStore,
        late_encoder: LateInteractionEncoder,
        dense_encoder: DenseEncoderProtocol,
        *,
        rank_mode: str | None = None,
    ) -> None:
        self._store = store
        self._late = late_encoder
        self._dense = dense_encoder
        self.rank_mode = rank_mode or config.RANK_MODE
        if self.rank_mode not in config.RANK_MODES:
            raise ValueError(f"rank_mode must be one of {config.RANK_MODES}")
        self.dense_error: str | None = None

    @property
    def dense_model(self) -> str:
        return encoder_model(self._dense, "dense") or config.LEGACY_DENSE_MODEL

    @property
    def late_model(self) -> str:
        return encoder_model(self._late, "late") or config.LEGACY_LATE_MODEL

    async def search(
        self,
        query: str,
        *,
        kinds: Sequence[str] | None = None,
        top_k: int = config.DEFAULT_TOP_K,
        recall_k: int = config.DEFAULT_RECALL_K,
        movement_id: str | None = None,
        rank_mode: str | None = None,
    ) -> SearchResponse:
        """Run the hybrid pipeline for one query.

        Args:
            query: free-text situation description from the caller.
            kinds: doc kinds to include (default: the past-situations set).
            top_k: final results after MaxSim rerank (capped at MAX_TOP_K).
            recall_k: dense ANN candidate pool (capped at 100 per C3).
            movement_id: optional filter hint — when the store supports it,
                results are ranked but not filtered (movement is metadata).
        """
        started = time.perf_counter()
        rank = rank_mode or self.rank_mode
        if rank not in config.RANK_MODES:
            raise ValueError(f"rank must be one of {config.RANK_MODES}")
        query = truncate_for_embedding(query)
        top_k = max(1, min(int(top_k), config.MAX_TOP_K))
        recall_k = max(top_k, min(int(recall_k), config.DEFAULT_RECALL_K))
        selected_kinds = tuple(kinds) if kinds else DEFAULT_SEARCH_KINDS

        for kind in selected_kinds:
            if kind not in config.MEMORY_DOC_KINDS:
                raise ValueError(
                    f"kind {kind!r} not allowed; whitelist: "
                    f"{config.MEMORY_DOC_KINDS}"
                )

        query_tokens = self._late.encode_query(query)
        dense: list[float] | None = None
        try:
            dense = validate_dense_vector(
                self._dense.encode([query])[0], dim=self._dense.dim
            )
            self.dense_error = None
        except Exception as exc:  # noqa: BLE001 - degrade to recency recall, never fail the search
            self.dense_error = f"{type(exc).__name__}: {str(exc)[:200]}"

        if dense is not None:
            recall_mode = "dense"
            recalled: list[MemoryDocRow] = await self._store.recall_by_dense(
                dense, kinds=selected_kinds, recall_k=recall_k,
                dense_model=self.dense_model,
            )
        else:
            recall_mode = "recent"
            recalled = await self._store.recall_recent(
                kinds=selected_kinds, recall_k=max(recall_k, config.RECENT_RECALL_K)
            )
        if movement_id:
            # Prefer same-movement history at equal rank without hiding the
            # rest of the memory (soft preference, applied post-rerank).
            recalled.sort(
                key=lambda r: (r.movement_id != movement_id)
            )
        token_map = await self._store.fetch_token_vectors(
            [r.doc_id for r in recalled]
        )

        hits: list[SearchHit] = []
        for row in recalled:
            tokens: TokenVecs | None = token_map.get(row.doc_id)
            dense_score = cosine(dense, row.dense) if (dense is not None and row.dense) else 0.0
            if tokens:
                score = maxsim_score(query_tokens, tokens)
                hits.append(
                    SearchHit(
                        doc_id=row.doc_id,
                        kind=row.kind,
                        ref_id=row.ref_id,
                        title=row.title,
                        snippet=_snippet(row.body),
                        score=score,
                        maxsim_score=score,
                        dense_score=dense_score,
                        strategy="maxsim",
                        token_count=row.token_count,
                        occurred_at=row.occurred_at,
                        metadata=row.metadata,
                    )
                )
            else:
                hits.append(
                    SearchHit(
                        doc_id=row.doc_id,
                        kind=row.kind,
                        ref_id=row.ref_id,
                        title=row.title,
                        snippet=_snippet(row.body),
                        score=dense_score,
                        maxsim_score=None,
                        dense_score=dense_score,
                        strategy="dense_fallback",
                        token_count=None,
                        occurred_at=row.occurred_at,
                        metadata=row.metadata,
                    )
                )

        if rank == "fused" and dense is not None and hits:
            # per-query z-scores of dense cosine and MaxSim, equal weights; a
            # doc without token vectors contributes its dense z-score only
            zd = _zscores([h.dense_score or 0.0 for h in hits])
            ms = [h for h in hits if h.maxsim_score is not None]
            zm = dict(zip((h.doc_id for h in ms), _zscores([h.maxsim_score for h in ms])))
            hits = [
                SearchHit(**{**h.__dict__, "fused_score": round(
                    (zd[i] + zm[h.doc_id]) / 2 if h.doc_id in zm else zd[i], 4)})
                for i, h in enumerate(hits)
            ]
            hits.sort(key=lambda h: (-(h.fused_score or 0.0), h.doc_id))
        else:
            hits.sort(key=lambda h: (-h.score, h.doc_id))
        latency_ms = (time.perf_counter() - started) * 1000.0
        return SearchResponse(
            query=query,
            results=hits[:top_k],
            query_token_count=len(query_tokens),
            recalled=len(recalled),
            latency_ms=latency_ms,
            recall=recall_mode,
            rank_mode=rank if dense is not None else "maxsim",
            models={"dense": self.dense_model if dense is not None else None, "late": self.late_model},
        )

    async def similar_past_situations(
        self, query: str, *, top_k: int = config.DEFAULT_TOP_K
    ) -> SearchResponse:
        """The brain-facing contract: search over past situations by name."""
        return await self.search(query, kinds=DEFAULT_SEARCH_KINDS, top_k=top_k)


__all__ = [
    "DEFAULT_SEARCH_KINDS",
    "embedding_marker",
    "HybridRetriever",
    "SearchHit",
    "SearchResponse",
]
