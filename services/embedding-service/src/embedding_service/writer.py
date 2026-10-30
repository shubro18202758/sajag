"""One write path for every memory doc: encode with both encoders, mark the models, upsert.

Shared by ``POST /embed/documents`` (api.py), the incident / scenario-run
ingestor (incidents.py) and the re-embedding script (scripts/reembed.py), so
the geometry rules live in one place:

* the late encoder sees the body (MaxSim rerank vectors);
* the dense encoder sees ``"<title>. <body>"`` (ANN recall vector);
* ``metadata.embedding = {"dense": <model>|None, "late": <model>}`` records
  which models wrote the vectors, so recall never compares two models'
  vectors and ``scripts/reembed.py`` knows what to refresh;
* a dense encoder that is down does not lose the write: the doc is stored
  with token vectors only (``dense: None``) and the re-embed script fills
  its dense vector later. A late encoder failure still fails the write
  (MaxSim is the contract's primary score).
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from .encoders import truncate_for_embedding, validate_dense_vector
from .retrieval import embedding_marker
from .store import MemoryStore

logger = logging.getLogger("embedding_service.writer")


def encode_doc(late: Any, dense: Any, *, title: str, body: str) -> tuple[list | None, list | None, dict]:
    """Token vectors, dense vector (None when the dense encoder is down) and the model marker."""
    token_sets = late.encode_documents([body])
    vector = None
    try:
        vector = validate_dense_vector(dense.encode([f"{title}. {body}"])[0], dim=dense.dim)
    except Exception as exc:  # noqa: BLE001 - keep the doc; reembed fills the dense vector later
        logger.warning("dense encoder unavailable, storing token vectors only: %s", str(exc)[:200])
    marker = embedding_marker(late, dense, dense_ok=vector is not None)
    return (token_sets[0] if token_sets else None), vector, marker


async def embed_and_upsert(
    store: MemoryStore,
    late: Any,
    dense: Any,
    *,
    kind: str,
    ref_id: str,
    title: str,
    body: str,
    metadata: dict | None,
    movement_id: str | None = None,
    occurred_at: datetime | None = None,
) -> str:
    tokens, vector, marker = encode_doc(late, dense, title=title, body=body)
    meta = dict(metadata or {})
    meta["embedding"] = marker
    return await store.upsert_document(
        kind=kind,
        ref_id=ref_id,
        title=truncate_for_embedding(title, 300),
        body=body,
        metadata=meta,
        dense=vector,
        token_vecs=tokens,
        movement_id=movement_id,
        occurred_at=occurred_at,
    )


__all__ = ["embed_and_upsert", "encode_doc"]
