"""Launcher for the embedding-service app (what serve_models.sh / sajag-embed.service run).

It puts ``services/embedding-service/src`` on the path and serves
``embedding_service.service.build_lazy_app()``: the asyncpg pool and the
encoders are created inside the serving loop by a FastAPI startup event (a
pool built before uvicorn's loop starts is bound to the wrong loop), the
encoders come from the model registry (``EMBED_DENSE_MODEL`` /
``EMBED_LATE_MODEL``, see ``embedding_service/config.py``) and are warmed on a
background thread. It performs no outbound HTTP calls; weights load from the
local Hugging Face cache (``HF_HUB_OFFLINE=1`` is set by serve_models.sh).

Kept as a file (rather than ``python -m embedding_service``) so the unit's
command line stays the same across releases.
"""

from __future__ import annotations

import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SRC = os.path.join(_REPO, "services", "embedding-service", "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from embedding_service.service import build_lazy_app  # noqa: E402


def main() -> None:
    import uvicorn

    uvicorn.run(
        build_lazy_app(),
        host=os.environ.get("EMBEDDING_LISTEN_HOST", "127.0.0.1"),
        port=int(os.environ.get("EMBEDDING_LISTEN_PORT", "8085")),
        log_level="info",
    )


if __name__ == "__main__":
    main()
