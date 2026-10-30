"""Re-embed the memory corpus after a model change (or fill dense vectors a dense outage left empty).

Every doc carries ``metadata.embedding = {"dense": <model>, "late": <model>}``
(unmarked legacy docs are bge-m3 + pplx-embed-v2-late-0.6b). This script
re-encodes, oldest first, every doc whose marker differs from the configured
models (``EMBED_DENSE_MODEL`` / ``EMBED_LATE_MODEL``) or that has no dense
vector, and rewrites its vectors and marker in place: the text, kind, ref_id
and doc_id are untouched, so the brain's tier-0 keys (which carry doc ids)
stay valid. Until a doc is re-embedded it is invisible to dense recall under
the new model (recall never compares two models' vectors), so run this right
after switching models.

    SAJAG_DATABASE_DSN=postgresql://... HF_HUB_OFFLINE=1 \\
      <models venv>/bin/python services/embedding-service/scripts/reembed.py [--dry-run] [--batch 32]

It loads its own copy of the encoders: on the shared GB10 check ``free -g``
first (the configured dense + late models need their own GPU memory while the
service runs). No outbound network calls; weights come from the local cache.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from embedding_service import config  # noqa: E402
from embedding_service.db import create_pool  # noqa: E402
from embedding_service.encoders import build_dense_encoder, build_late_encoder, encoder_model  # noqa: E402
from embedding_service.store import MemoryStore  # noqa: E402
from embedding_service.writer import encode_doc  # noqa: E402


async def reembed(store: MemoryStore, late, dense, *, batch: int = 32, dry_run: bool = False,
                  limit: int | None = None) -> dict:
    """Re-embed stale docs; returns counts. Shared with the tests (fakes)."""
    dense_model = encoder_model(dense, "dense") or config.LEGACY_DENSE_MODEL
    late_model = encoder_model(late, "late") or config.LEGACY_LATE_MODEL
    done, skipped, seen = 0, 0, set()
    t0 = time.perf_counter()
    while limit is None or done + skipped < limit:
        page = [d for d in await store.stale_documents(dense_model, late_model, batch) if d["doc_id"] not in seen]
        if not page:
            break
        if dry_run:
            return {"stale_first_page": len(page), "dense_model": dense_model, "late_model": late_model,
                    "dry_run": True}
        for doc in page:
            seen.add(doc["doc_id"])
            tokens, vector, marker = encode_doc(late, dense, title=doc["title"], body=doc["body"])
            meta = dict(doc["metadata"])
            meta["embedding"] = marker
            await store.update_embeddings(doc["doc_id"], dense=vector, token_vecs=tokens, metadata=meta)
            if vector is None:
                skipped += 1  # dense encoder down: token vectors refreshed, dense left for a later run
            else:
                done += 1
    return {"reembedded": done, "dense_missing": skipped, "dense_model": dense_model, "late_model": late_model,
            "seconds": round(time.perf_counter() - t0, 1), "dry_run": dry_run}


async def _main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dry-run", action="store_true", help="count the stale docs, change nothing")
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()
    pool = await create_pool()
    store = MemoryStore(pool)
    before = await store.count_by_dense_model()
    late, dense = build_late_encoder(), build_dense_encoder()
    result = await reembed(store, late, dense, batch=args.batch, dry_run=args.dry_run, limit=args.limit)
    result["docs_by_dense_model_before"] = before
    result["docs_by_dense_model_after"] = await store.count_by_dense_model()
    await pool.close()
    print(json.dumps(result, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
