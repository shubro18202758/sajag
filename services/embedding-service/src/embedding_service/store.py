"""Parameter-bound SQL for the memory store.

Every statement is a module-level constant using $n placeholders — no
f-string/format/percent SQL construction anywhere (C12), matching the
existing parameter-bound pattern in traffic-oracle's
data/vector_store.py:21-29. Vector values are serialised by
``pgvector_codec`` and passed as bound parameters with explicit casts.

All statements execute through ``fetchrow``/``fetch`` with positional
bound parameters (writes carry ``RETURNING`` so no ``execute()`` sink is
used anywhere). The store is duck-typed over an asyncpg-like pool so tests
inject fakes; real pool creation lives in ``db.py``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Sequence

from . import config
from .encoders import TokenVecs
from .pgvector_codec import (
    parse_vector_array_text,
    parse_vector_text,
    vector_array_to_param,
    vector_to_text,
)

# ─── SQL statements (parameter-bound constants) ───────────────────────────────

UPSERT_DOC_SQL = """
    INSERT INTO traffic.memory_docs
        (kind, ref_id, title, body, metadata, dense_embedding,
         token_vectors, token_count, movement_id, occurred_at)
    VALUES ($1, $2, $3, $4, $5::jsonb, $6::vector,
            $7::vector(128)[], $8, $9, $10)
    ON CONFLICT (kind, ref_id) DO UPDATE SET
        title = EXCLUDED.title,
        body = EXCLUDED.body,
        metadata = EXCLUDED.metadata,
        dense_embedding = EXCLUDED.dense_embedding,
        token_vectors = EXCLUDED.token_vectors,
        token_count = EXCLUDED.token_count,
        movement_id = EXCLUDED.movement_id,
        occurred_at = EXCLUDED.occurred_at
    RETURNING doc_id;
"""

# $4: the dense model that wrote the query vector. Vectors of two models are
# not comparable, so recall only sees docs embedded by the same model (docs
# from before the registry carry no marker and were embedded by bge-m3).
RECALL_BY_DENSE_SQL = """
    SELECT doc_id, kind, ref_id, title, body, metadata, movement_id,
           occurred_at, token_count,
           dense_embedding::text AS dense_text,
           1 - (dense_embedding <=> $1::vector) AS dense_score
    FROM traffic.memory_docs
    WHERE dense_embedding IS NOT NULL
      AND kind = ANY($2::text[])
      AND coalesce(metadata->'embedding'->>'dense', 'bge-m3') = $4
    ORDER BY dense_embedding <=> $1::vector
    LIMIT $3;
"""

# The no-dense-encoder fallback: the most recent docs of the kinds that carry
# token vectors (MaxSim reranks them).
RECALL_RECENT_SQL = """
    SELECT doc_id, kind, ref_id, title, body, metadata, movement_id,
           occurred_at, token_count,
           NULL::text AS dense_text,
           NULL::float8 AS dense_score
    FROM traffic.memory_docs
    WHERE token_vectors IS NOT NULL
      AND kind = ANY($1::text[])
    ORDER BY coalesce(occurred_at, created_at) DESC
    LIMIT $2;
"""

# Re-embedding (scripts/reembed.py): docs whose dense or late marker differs
# from the configured models, oldest first, in pages.
STALE_DOCS_SQL = """
    SELECT doc_id, kind, title, body, metadata
    FROM traffic.memory_docs
    WHERE coalesce(metadata->'embedding'->>'dense', 'bge-m3') <> $1
       OR coalesce(metadata->'embedding'->>'late', 'pplx-embed-v2-late-0.6b') <> $2
       OR dense_embedding IS NULL
    ORDER BY created_at
    LIMIT $3;
"""

UPDATE_EMBEDDINGS_SQL = """
    UPDATE traffic.memory_docs
    SET dense_embedding = $2::vector,
        token_vectors = $3::vector(128)[],
        token_count = $4,
        metadata = $5::jsonb
    WHERE doc_id = $1::uuid
    RETURNING doc_id;
"""

COUNT_BY_MODEL_SQL = """
    SELECT coalesce(metadata->'embedding'->>'dense', 'bge-m3') AS dense_model,
           count(*) AS n
    FROM traffic.memory_docs
    GROUP BY 1;
"""

FETCH_TOKEN_VECTORS_SQL = """
    SELECT doc_id, token_vectors::text AS tokens_text
    FROM traffic.memory_docs
    WHERE doc_id = ANY($1::uuid[]);
"""

INSERT_INCIDENT_SQL = """
    INSERT INTO traffic.incidents
        (incident_kind, severity, movement_id, segment_ids, summary,
         details, outcome, scenario_run_id, source, occurred_at)
    VALUES ($1, $2, $3, $4::bigint[], $5, $6::jsonb, $7::jsonb,
            $8, $9, $10)
    RETURNING incident_id;
"""

LINK_MEMORY_DOC_SQL = """
    UPDATE traffic.incidents
    SET memory_doc_id = $1
    WHERE incident_id = $2
    RETURNING incident_id;
"""

RECENT_INCIDENTS_SQL = """
    SELECT incident_id, incident_kind, severity, movement_id, segment_ids,
           summary, details, outcome, scenario_run_id, source,
           memory_doc_id, occurred_at
    FROM traffic.incidents
    WHERE cardinality($1::text[]) = 0 OR incident_kind = ANY($1::text[])
    ORDER BY occurred_at DESC
    LIMIT $2;
"""

COUNT_DOCS_SQL = """
    SELECT count(*) AS n FROM traffic.memory_docs;
"""

# ─── Row shapes ────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class MemoryDocRow:
    doc_id: str
    kind: str
    ref_id: str
    title: str
    body: str
    metadata: dict
    movement_id: str | None
    occurred_at: datetime | None
    token_count: int | None
    dense: list[float] | None
    dense_score: float | None


_INCIDENT_COLUMNS = (
    "incident_id",
    "incident_kind",
    "severity",
    "movement_id",
    "segment_ids",
    "summary",
    "details",
    "outcome",
    "scenario_run_id",
    "source",
    "memory_doc_id",
    "occurred_at",
)


def _metadata(value: Any) -> dict:
    """asyncpg returns jsonb as text unless a codec is set; accept both."""
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except ValueError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _row_to_dict(row: Any) -> dict:
    getter = row.get if hasattr(row, "get") else row.__getitem__
    return {key: getter(key) for key in _INCIDENT_COLUMNS}


# ─── Store ────────────────────────────────────────────────────────────────────


class MemoryStore:
    """CRUD + hybrid-retrieval queries over traffic.memory_docs/incidents."""

    def __init__(self, pool: Any) -> None:
        self._pool = pool

    async def upsert_document(
        self,
        *,
        kind: str,
        ref_id: str,
        title: str,
        body: str,
        metadata: dict | None,
        dense: Sequence[float] | None,
        token_vecs: TokenVecs | None,
        movement_id: str | None = None,
        occurred_at: datetime | None = None,
    ) -> str:
        """Insert or update a memory document; returns its doc_id.

        ``kind`` must be on the memory kind whitelist (leak guard).
        """
        if kind not in config.MEMORY_DOC_KINDS:
            raise ValueError(
                f"kind {kind!r} not allowed; whitelist: {config.MEMORY_DOC_KINDS}"
            )
        token_param = vector_array_to_param(token_vecs)
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                UPSERT_DOC_SQL,
                kind,
                ref_id,
                title,
                body,
                json.dumps(metadata or {}),
                vector_to_text(dense) if dense is not None else None,
                token_param,
                len(token_vecs) if token_vecs else None,
                movement_id,
                occurred_at,
            )
        return str(row["doc_id"])

    async def recall_by_dense(
        self,
        dense: Sequence[float],
        *,
        kinds: Sequence[str] | None = None,
        recall_k: int = config.DEFAULT_RECALL_K,
        dense_model: str = config.LEGACY_DENSE_MODEL,
    ) -> list[MemoryDocRow]:
        """Dense ANN recall (cosine) over the docs embedded by ``dense_model``."""
        kind_array = list(kinds) if kinds else list(config.MEMORY_DOC_KINDS)
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                RECALL_BY_DENSE_SQL,
                vector_to_text(dense),
                kind_array,
                recall_k,
                dense_model,
            )
        return [self._row(r) for r in rows]

    async def recall_recent(
        self,
        *,
        kinds: Sequence[str] | None = None,
        recall_k: int = config.RECENT_RECALL_K,
    ) -> list[MemoryDocRow]:
        """Fallback recall without a dense encoder: the newest docs that carry token vectors."""
        kind_array = list(kinds) if kinds else list(config.MEMORY_DOC_KINDS)
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(RECALL_RECENT_SQL, kind_array, recall_k)
        return [self._row(r) for r in rows]

    async def stale_documents(self, dense_model: str, late_model: str, limit: int = 64) -> list[dict]:
        """Docs not embedded by the configured models (or with no dense vector), oldest first."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(STALE_DOCS_SQL, dense_model, late_model, limit)
        return [
            {"doc_id": str(r["doc_id"]), "kind": r["kind"], "title": r["title"], "body": r["body"],
             "metadata": _metadata(r["metadata"])}
            for r in rows
        ]

    async def update_embeddings(
        self,
        doc_id: str,
        *,
        dense: Sequence[float] | None,
        token_vecs: TokenVecs | None,
        metadata: dict,
    ) -> None:
        """Replace one doc's vectors and model marker (re-embedding); the text is untouched."""
        async with self._pool.acquire() as conn:
            await conn.fetchrow(
                UPDATE_EMBEDDINGS_SQL,
                doc_id,
                vector_to_text(dense) if dense is not None else None,
                vector_array_to_param(token_vecs),
                len(token_vecs) if token_vecs else None,
                json.dumps(metadata),
            )

    async def count_by_dense_model(self) -> dict[str, int]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(COUNT_BY_MODEL_SQL)
        return {r["dense_model"]: int(r["n"]) for r in rows}

    @staticmethod
    def _row(r: Any) -> MemoryDocRow:
        return MemoryDocRow(
            doc_id=str(r["doc_id"]),
            kind=r["kind"],
            ref_id=r["ref_id"],
            title=r["title"],
            body=r["body"],
            metadata=_metadata(r["metadata"]),
            movement_id=str(r["movement_id"]) if r["movement_id"] else None,
            occurred_at=r["occurred_at"],
            token_count=r["token_count"],
            dense=parse_vector_text(r["dense_text"]) if r["dense_text"] else None,
            dense_score=(
                float(r["dense_score"]) if r["dense_score"] is not None else None
            ),
        )

    async def fetch_token_vectors(
        self, doc_ids: Sequence[str]
    ) -> dict[str, TokenVecs | None]:
        """Fetch token-vector sets for the recalled candidates (rerank input)."""
        if not doc_ids:
            return {}
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(FETCH_TOKEN_VECTORS_SQL, list(doc_ids))
        return {
            str(r["doc_id"]): parse_vector_array_text(r["tokens_text"])
            for r in rows
        }

    async def insert_incident(
        self,
        *,
        incident_kind: str,
        severity: str,
        summary: str,
        segment_ids: Sequence[int] | None = None,
        movement_id: str | None = None,
        details: dict | None = None,
        outcome: dict | None = None,
        scenario_run_id: int | None = None,
        source: str = "live",
        occurred_at: datetime | None = None,
    ) -> int:
        """Insert an incident/pattern row; returns incident_id.

        ``incident_kind``, ``severity`` and ``source`` are whitelist-checked
        in Python before the parameter-bound INSERT runs.
        """
        if incident_kind not in config.INCIDENT_KINDS:
            raise ValueError(
                f"incident_kind {incident_kind!r} not allowed; "
                f"whitelist: {config.INCIDENT_KINDS}"
            )
        if severity not in config.INCIDENT_SEVERITIES:
            raise ValueError(f"severity {severity!r} not allowed")
        if source not in config.INCIDENT_SOURCES:
            raise ValueError(f"source {source!r} not allowed")
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                INSERT_INCIDENT_SQL,
                incident_kind,
                severity,
                movement_id,
                [int(s) for s in (segment_ids or [])],
                summary,
                json.dumps(details or {}),
                json.dumps(outcome) if outcome is not None else None,
                scenario_run_id,
                source,
                occurred_at,
            )
        return int(row["incident_id"])

    async def link_memory_doc(self, incident_id: int, doc_id: str) -> None:
        """Point an incident row at its embedded memory document."""
        async with self._pool.acquire() as conn:
            await conn.fetchrow(LINK_MEMORY_DOC_SQL, doc_id, incident_id)

    async def recent_incidents(
        self,
        *,
        limit: int = 20,
        kinds: Sequence[str] | None = None,
    ) -> list[dict]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                RECENT_INCIDENTS_SQL,
                list(kinds) if kinds else [],
                limit,
            )
        return [_row_to_dict(r) for r in rows]

    async def count_documents(self) -> int:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(COUNT_DOCS_SQL)
        return int(row["n"])


__all__ = ["MemoryDocRow", "MemoryStore"]
