"""The optional dense embedder (bge-m3 through the embedding service): the pipeline never depends on it.

:class:`HttpEmbedder` implements :class:`osint_common.pipeline.Embedder`. It calls ``POST {base_url}/embed`` with
``{"texts": [...]}`` and reads ``{"vectors": [[float, ...], ...]}`` (``"embeddings"`` or ``"dense"`` are read too,
as is a bare list). It returns ``None`` on ANY failure: a refused connection, a timeout, a non-200 status, a
redirect, malformed JSON, the wrong number of vectors, ragged or non-finite values, or the whole call running past
its ``deadline`` (default :data:`DEFAULT_DEADLINE_S`: a slow but answering service can hold an ingest for at most
that long, however many batches the texts need). ``run_pipeline`` then falls back to the lexical similarity, so a
missing or slow service changes no outcome except that one choice.

Safety, by construction:

* the path is fixed: ``/embed``, a read. It never calls ``/embed/documents`` or ``/incidents``, which UPSERT into
  the memory store (plan R21: nothing in this programme writes ``osint`` memory documents);
* redirects are never followed (a redirect to a write endpoint cannot be replayed), and ``trust_env=False`` keeps
  proxies and ``.netrc`` credentials out; no header, token or secret is sent;
* texts are bounded (:data:`MAX_TEXT_CHARS` each, :data:`MAX_BATCH` per request) and are the already-redacted
  titles and texts: no person field exists to send.

Deployment note: today's embedding service exposes no dense ``/embed`` route (only ``/embed/documents``, which
writes, and ``/search``), so this client answers ``None`` against it until a read-only ``/embed`` is added there.
"""

from __future__ import annotations

import logging
import math
import time
from collections.abc import Sequence
from typing import Any
from urllib.parse import urlsplit

import httpx
import numpy as np

from osint_common.pipeline import Embedder

__all__ = ["DEFAULT_DEADLINE_S", "EMBED_PATH", "MAX_BATCH", "MAX_TEXT_CHARS", "HttpEmbedder", "unit_vectors"]

logger = logging.getLogger("osint_analysis.embed")

#: The one route this client calls: a read (dense vectors), never a store.
EMBED_PATH = "/embed"
#: Texts per request (the embedding service's encoder batch ceiling).
MAX_BATCH = 64
#: Characters per text.
MAX_TEXT_CHARS = 2000
#: The whole ``embed`` call (every batch) ends by then, seconds; each request also keeps its own ``timeout``.
DEFAULT_DEADLINE_S = 10.0
_RESPONSE_KEYS = ("vectors", "embeddings", "dense")
#: The clock of the deadline (a module attribute, so a test can drive it).
_monotonic = time.monotonic


def _validated_base(base_url: str) -> str:
    parts = urlsplit(str(base_url).strip())
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ValueError("base_url is an http(s) URL with a host, e.g. http://127.0.0.1:8085")
    if parts.username or parts.password:
        raise ValueError("base_url carries no credentials")
    if parts.query or parts.fragment:
        raise ValueError("base_url carries no query or fragment")
    return f"{parts.scheme}://{parts.netloc}{parts.path.rstrip('/')}"


def _parse_vectors(payload: Any, expected: int) -> list[list[float]] | None:
    rows = payload
    if isinstance(payload, dict):
        rows = next((payload[k] for k in _RESPONSE_KEYS if k in payload), None)
    if not isinstance(rows, list) or len(rows) != expected:
        return None
    out: list[list[float]] = []
    dim = None
    for row in rows:
        if not isinstance(row, list) or not row:
            return None
        if dim is None:
            dim = len(row)
        elif len(row) != dim:
            return None
        vec: list[float] = []
        for x in row:
            if isinstance(x, bool) or not isinstance(x, int | float) or not math.isfinite(x):
                return None
            vec.append(float(x))
        out.append(vec)
    return out


class HttpEmbedder:
    """``HttpEmbedder(base_url, timeout=3.0)``: dense vectors from the embedding service, or ``None``.

    ``timeout`` bounds each request, ``deadline`` the whole call (all batches). ``transport`` is for tests (an
    :class:`httpx.MockTransport`); production leaves it unset.
    """

    def __init__(
        self,
        base_url: str,
        timeout: float = 3.0,
        *,
        deadline: float = DEFAULT_DEADLINE_S,
        transport: httpx.BaseTransport | None = None,
        max_batch: int = MAX_BATCH,
    ) -> None:
        self._base = _validated_base(base_url)
        self._url = self._base + EMBED_PATH
        if not (isinstance(timeout, int | float) and 0 < timeout <= 60):
            raise ValueError("timeout is a positive number of seconds (at most 60)")
        if not (isinstance(deadline, int | float) and 0 < deadline <= 300):
            raise ValueError("deadline is a positive number of seconds (at most 300)")
        self._timeout = float(timeout)
        self._deadline = float(deadline)
        self._transport = transport
        self._max_batch = max(1, min(int(max_batch), MAX_BATCH))

    @property
    def url(self) -> str:
        """The one URL this client posts to (``<base>/embed``)."""
        return self._url

    def embed(self, texts: list[str]) -> list[list[float]] | None:
        """Embed ``texts`` (in order); ``None`` on any failure, ``[]`` for no text."""
        if not texts:
            return []
        bounded = [str(t or "")[:MAX_TEXT_CHARS] for t in texts]
        out: list[list[float]] = []
        ends_at = _monotonic() + self._deadline
        try:
            with httpx.Client(
                timeout=self._timeout,
                transport=self._transport,
                follow_redirects=False,
                trust_env=False,
            ) as client:
                for start in range(0, len(bounded), self._max_batch):
                    left = ends_at - _monotonic()
                    if left <= 0:
                        logger.info("embedder past its %.0f s deadline; falling back to lexical similarity",
                                    self._deadline)
                        return None
                    chunk = bounded[start : start + self._max_batch]
                    response = client.post(self._url, json={"texts": chunk}, timeout=min(self._timeout, left))
                    if response.status_code != 200:
                        logger.info("embedder answered %s; falling back to lexical similarity", response.status_code)
                        return None
                    vectors = _parse_vectors(response.json(), len(chunk))
                    if vectors is None:
                        logger.info("embedder answered a malformed body; falling back to lexical similarity")
                        return None
                    out.extend(vectors)
        except Exception as exc:  # noqa: BLE001 - the pipeline never depends on the embedder
            logger.info("embedder unavailable (%s); falling back to lexical similarity", type(exc).__name__)
            return None
        if out and any(len(v) != len(out[0]) for v in out):
            return None
        return out


def unit_vectors(embedder: Embedder | None, texts: Sequence[str]) -> np.ndarray | None:
    """Call ``embedder.embed(texts)`` once and return the rows as unit vectors, or ``None`` on any failure (an
    exception, ``None``, the wrong count, a ragged, non-finite or zero row)."""
    if embedder is None or not texts:
        return None
    try:
        raw = embedder.embed(list(texts))
    except Exception as exc:  # noqa: BLE001 - optional component
        logger.info("embedder raised %s; falling back to lexical similarity", type(exc).__name__)
        return None
    if raw is None or len(raw) != len(texts):
        return None
    try:
        arr = np.asarray(raw, dtype=float)
    except (TypeError, ValueError):
        return None
    if arr.ndim != 2 or arr.shape[0] != len(texts) or arr.shape[1] == 0 or not np.all(np.isfinite(arr)):
        return None
    norms = np.linalg.norm(arr, axis=1)
    if np.any(norms <= 0.0):
        return None
    return arr / norms[:, None]
