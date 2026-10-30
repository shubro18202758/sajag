"""Encoder abstractions: late-interaction primary + dense auxiliary.

Real encoders wrap the models verified on this machine (manifest):

* pplx-embed-v2-late-0.6b — ``sentence_transformers.MultiVectorEncoder``;
  ``encode_query``/``encode_document`` return per-input tensors of shape
  ``(n_tokens, 128)``; similarity is MaxSim (see maxsim.py). Text-only and
  image-only batches must be encoded separately (model-card constraint); this
  service embeds text only.
* bge-m3 — local SentenceTransformer snapshot at
  ``BGE_M3_PATH`` (default ``~/models/bge-m3``); encode → ``(N, 1024)`` float32
  unit-norm.

Heavy imports (sentence_transformers / torch) happen lazily inside
``_load_model`` so this module — and every test of it — runs without them.
Shape validation is shared by real and fake encoders, which is what the
encode-shape tests exercise.
"""

from __future__ import annotations

import hashlib
from typing import Protocol, Sequence

from . import config


class EncodingError(ValueError):
    """Raised when encoder output violates the embedding geometry contract."""


TokenVecs = list[list[float]]
"""One document's late-interaction representation: n_tokens × 128 floats."""


def validate_token_vectors(
    tokens: Sequence[Sequence[float]],
    *,
    dim: int = config.TOKEN_VEC_DIM,
    max_tokens: int = config.MAX_TOKEN_VECS_PER_DOC,
    allow_empty: bool = False,
) -> TokenVecs:
    """Validate one document's token-vector set; return it as plain lists.

    Enforces the storage contract mirrored by traffic.memory_docs:
    1..max_tokens vectors, each exactly ``dim`` wide, finite floats.
    """
    n = len(tokens)
    if n == 0:
        if allow_empty:
            return []
        raise EncodingError("token vector set must not be empty")
    if n > max_tokens:
        raise EncodingError(
            f"{n} token vectors exceeds cap {max_tokens}"
        )
    out: TokenVecs = []
    for i, vec in enumerate(tokens):
        if len(vec) != dim:
            raise EncodingError(
                f"token {i} has {len(vec)} dims, expected {dim}"
            )
        row = [float(v) for v in vec]
        for j, v in enumerate(row):
            if v != v or v in (float("inf"), float("-inf")):  # NaN/inf guard
                raise EncodingError(f"token {i} dim {j} is not finite")
        out.append(row)
    return out


def validate_dense_vector(
    vec: Sequence[float],
    *,
    dim: int = config.DENSE_DIM,
) -> list[float]:
    """Validate one document's dense (bge-m3) vector: exactly ``dim`` wide."""
    if len(vec) != dim:
        raise EncodingError(f"dense vector has {len(vec)} dims, expected {dim}")
    out = [float(v) for v in vec]
    for i, v in enumerate(out):
        if v != v or v in (float("inf"), float("-inf")):
            raise EncodingError(f"dense dim {i} is not finite")
    return out


def truncate_for_embedding(text: str, max_chars: int = config.MAX_BODY_CHARS) -> str:
    """Bound document length before it reaches an encoder or the store."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars]


class LateInteractionEncoder(Protocol):
    """Primary encoder: pplx-embed-v2-late multi-vector + MaxSim."""

    name: str

    def encode_query(self, text: str) -> TokenVecs: ...

    def encode_documents(self, texts: Sequence[str]) -> list[TokenVecs]: ...


class DenseEncoderProtocol(Protocol):
    """Auxiliary encoder: bge-m3 dense vectors for ANN recall."""

    name: str
    dim: int

    def encode(self, texts: Sequence[str]) -> list[list[float]]: ...


# ─── Real encoders (lazy heavy imports) ───────────────────────────────────────


class ModelUnavailable(RuntimeError):
    """The model could not be loaded (missing weights, out of memory); retried after a back-off."""


class _LazyModel:
    """Thread-safe lazy load with a failure back-off, shared by the real encoders.

    A failed load is remembered for ``retry_after_sec``, so a dead model costs
    one exception per request instead of one load attempt per request.
    """

    retry_after_sec = 300.0

    def __init__(self) -> None:
        import threading

        self._model = None
        self._lock = threading.Lock()
        self.load_error: str | None = None
        self._failed_at: float | None = None
        self.load_seconds: float | None = None

    @property
    def loaded(self) -> bool:
        return self._model is not None

    def _build(self):  # pragma: no cover - real weights only
        raise NotImplementedError

    def _load_model(self):
        if self._model is not None:
            return self._model
        import time

        with self._lock:
            if self._model is not None:
                return self._model
            if self._failed_at is not None and time.monotonic() - self._failed_at < self.retry_after_sec:
                raise ModelUnavailable(self.load_error or "model failed to load")
            t0 = time.perf_counter()
            try:
                self._model = self._build()
            except Exception as exc:  # noqa: BLE001 - surfaced through /health and ModelUnavailable
                self._failed_at = time.monotonic()
                self.load_error = f"{type(exc).__name__}: {str(exc)[:300]}"
                raise ModelUnavailable(self.load_error) from exc
            self.load_error, self._failed_at = None, None
            self.load_seconds = round(time.perf_counter() - t0, 1)
        return self._model

    def status(self) -> dict:
        return {"loaded": self.loaded, "load_error": self.load_error, "load_seconds": self.load_seconds}


def _torch_dtype(name: str):  # pragma: no cover - real weights only
    import torch  # lazy

    return {"float32": torch.float32, "bfloat16": torch.bfloat16, "float16": torch.float16}[name]


class PplxLateInteractionEncoder(_LazyModel):
    """pplx-embed-v2-late wrapper producing validated token-vector sets.

    Loads ``sentence_transformers.MultiVectorEncoder`` on first use inside
    the model venv (torch==2.14.0 / sentence-transformers>=6.1.0 — see the
    model manifest). Device defaults to cuda, CPU fallback supported.
    ``model_id`` is a LATE_MODELS registry key or, backward compatible, the HF
    repo id; the pinned revision and dtype come from the registry. The 0.6b
    and 9b models share one embedding space.
    """

    def __init__(self, model_id: str | None = None, device: str = config.EMBED_DEVICE):
        super().__init__()
        key = model_id or config.LATE_MODEL
        if key not in config.LATE_MODELS:
            key = next((k for k, v in config.LATE_MODELS.items() if v["source"] == key), key)
        spec = config.LATE_MODELS.get(key, {"source": key, "revision": None, "dtype": "float32"})
        self.name = "pplx-embed-v2-late"  # the label the health contract has always shown
        self.model = key                  # the exact registry model (marker on stored docs)
        self._model_id = spec["source"]
        self._revision = spec.get("revision")
        self._dtype = spec.get("dtype", "float32")
        self._device = device

    def _build(self):  # pragma: no cover - real weights only
        # Lazy import: keeps this module importable without torch.
        from sentence_transformers import MultiVectorEncoder  # type: ignore

        return MultiVectorEncoder(
            self._model_id, device=self._device, revision=self._revision,
            model_kwargs={"dtype": _torch_dtype(self._dtype)},
        )

    def encode_query(self, text: str) -> TokenVecs:
        model = self._load_model()
        tensors = model.encode_query([truncate_for_embedding(text)])
        tokens = [t.float().tolist() for t in tensors[0]]
        # A query may exceed the cap in principle; storage caps docs, and
        # MaxSim only needs the query's own vectors — but bound it anyway to
        # keep worst-case rerank work fixed.
        if len(tokens) > config.MAX_TOKEN_VECS_PER_DOC:
            tokens = tokens[: config.MAX_TOKEN_VECS_PER_DOC]
        return validate_token_vectors(tokens)

    def encode_documents(self, texts: Sequence[str]) -> list[TokenVecs]:
        model = self._load_model()
        bounded = [truncate_for_embedding(t) for t in texts]
        per_doc_tensors = model.encode_document(bounded)
        out: list[TokenVecs] = []
        for doc_tensors in per_doc_tensors:
            tokens = [t.float().tolist() for t in doc_tensors]
            if len(tokens) > config.MAX_TOKEN_VECS_PER_DOC:
                tokens = tokens[: config.MAX_TOKEN_VECS_PER_DOC]
            out.append(validate_token_vectors(tokens))
        return out


def fit_dense(row: Sequence[float], store_dim: int = config.DENSE_DIM) -> list[float]:
    """A model vector in store geometry: its first ``store_dim`` values (Matryoshka prefix), unit-normalised.

    pplx-embed models emit unnormalised int8-valued vectors (compare by cosine,
    per their card); bge-m3 emits unit vectors. Normalising here makes the
    store's cosine distance and the /embed dot product agree for every model.
    """
    vals = [float(v) for v in row[:store_dim]]
    norm = sum(v * v for v in vals) ** 0.5
    if norm == 0.0:
        raise EncodingError("dense vector is all zeros")
    return validate_dense_vector([v / norm for v in vals], dim=store_dim)


BLANK_TEXT = "(empty)"


def _float_row(row) -> list[float]:
    """A model output row (torch tensor in any dtype, or array) as Python floats."""
    if hasattr(row, "float"):  # torch tensor: bf16 has no numpy dtype
        row = row.float().cpu().tolist()
    elif hasattr(row, "tolist"):
        row = row.tolist()
    return [float(v) for v in row]


class DenseEncoder(_LazyModel):
    """A DENSE_MODELS registry model producing validated unit vectors of the store's width.

    ``family='sentence_transformers'`` (bge-m3, pplx-embed-v1-*) encodes with
    SentenceTransformer; ``family='contextual'`` (pplx-embed-context-v1-*)
    encodes each text as a one-chunk document through the model's own
    ``encode``. Both are cut to ``store_dim`` (Matryoshka) and normalised.
    """

    def __init__(self, name: str | None = None, device: str = config.EMBED_DEVICE,
                 source: str | None = None):
        super().__init__()
        spec = config.dense_spec(name)
        self.name = spec["name"]
        self.dim = spec["store_dim"]
        self.native_dim = spec["dim"]
        self.family = spec["family"]
        self._source = source or spec["source"]
        self._revision = spec.get("revision")
        self._dtype = spec.get("dtype", "float32")
        self._trust = bool(spec.get("trust_remote_code"))
        self._device = device

    def _build(self):  # pragma: no cover - real weights only
        if self.family == "contextual":
            from transformers import AutoModel  # type: ignore

            # by repo id + pinned revision (offline): a local snapshot path makes
            # transformers load the config and model classes from two
            # dynamic-module copies and the model's own isinstance check fails
            model = AutoModel.from_pretrained(
                self._source, revision=self._revision, trust_remote_code=self._trust,
                dtype=_torch_dtype(self._dtype),
            )
            return model.to(self._device).eval()
        from sentence_transformers import SentenceTransformer  # type: ignore

        kwargs = {"model_kwargs": {"dtype": _torch_dtype(self._dtype)}}
        if self._revision:
            kwargs["revision"] = self._revision
        return SentenceTransformer(self._source, device=self._device,
                                   trust_remote_code=self._trust, **kwargs)

    def encode(self, texts: Sequence[str]) -> list[list[float]]:
        model = self._load_model()
        # a blank text has no content to embed; the contextual model's own code
        # returns an unquantised bf16 zero vector for it (which cannot become
        # numpy), so blanks are embedded as one neutral placeholder token
        bounded = [truncate_for_embedding(t) if t.strip() else BLANK_TEXT for t in texts]
        if self.family == "contextual":
            docs = model.encode([[t] for t in bounded], batch_size=8, convert_to_numpy=False)
            rows = [_float_row(doc[0]) for doc in docs]
        else:
            rows = [_float_row(r) for r in model.encode(bounded, batch_size=16, convert_to_tensor=True)]
        return [fit_dense(row, self.dim) for row in rows]


class BgeM3DenseEncoder(DenseEncoder):
    """bge-m3 wrapper producing validated unit-norm dense vectors (the fallback dense model)."""

    def __init__(self, model_path: str = config.DENSE_MODEL_PATH, device: str = config.EMBED_DEVICE):
        super().__init__("bge-m3", device=device, source=model_path)


def build_dense_encoder(name: str | None = None, device: str = config.EMBED_DEVICE) -> DenseEncoder:
    """The configured dense encoder (EMBED_DENSE_MODEL; default in config.DEFAULT_DENSE_MODEL)."""
    name = name or config.DENSE_MODEL
    return BgeM3DenseEncoder(device=device) if name == "bge-m3" else DenseEncoder(name, device=device)


def build_late_encoder(name: str | None = None, device: str = config.EMBED_DEVICE) -> PplxLateInteractionEncoder:
    return PplxLateInteractionEncoder(name, device=device)


def encoder_model(encoder: object, kind: str) -> str | None:
    """The registry model an encoder writes (``model`` for late, ``name`` for dense); None for test fakes."""
    value = getattr(encoder, "model" if kind == "late" else "name", None)
    registry = config.LATE_MODELS if kind == "late" else config.DENSE_MODELS
    return value if value in registry else None


# ─── Deterministic fakes (tests + offline development) ────────────────────────


def _stable_pseudovector(seed_text: str, dim: int, salt: str) -> list[float]:
    """Deterministic bounded pseudo-vector keyed by (seed_text, salt).

    Same input text → same vector; disjoint texts → uncorrelated-ish
    vectors. Never used in production paths.
    """
    values: list[float] = []
    counter = 0
    while len(values) < dim:
        block = hashlib.sha256(
            f"{salt}:{seed_text}:{counter}".encode("utf-8")
        ).digest()
        for byte in block:
            values.append((byte / 127.5) - 1.0)  # [-1, 1)
            if len(values) == dim:
                break
        counter += 1
    return values


class FakeLateInteractionEncoder:
    """Deterministic late-interaction fake for tests.

    Each token of the text contributes one 128-d pseudo-vector built from
    ``salt:token``; a ``extra_vectors`` hook lets tests inject crafted
    vectors for exact ranking control. Output always satisfies the geometry
    contract enforced by validate_token_vectors.
    """

    def __init__(self, salt: str = "fake-late"):
        self.name = "fake-late"
        self._salt = salt

    def _tokens_for(self, text: str) -> list[str]:
        return text.split()[: config.MAX_TOKEN_VECS_PER_DOC]

    def encode_query(self, text: str) -> TokenVecs:
        toks = self._tokens_for(text)
        return validate_token_vectors(
            [_stable_pseudovector(t, config.TOKEN_VEC_DIM, self._salt) for t in toks]
        )

    def encode_documents(self, texts: Sequence[str]) -> list[TokenVecs]:
        return [self.encode_query(t) for t in texts]


class ScriptedEncoder:
    """Returns exactly the vectors a test supplies, after validation.

    ``vectors_by_prefix`` maps a text prefix (or full text) to its token
    vector set; unknown texts fall back to the fake late encoder behaviour.
    Lets retrieval tests assert exact MaxSim orderings without a model.
    """

    def __init__(
        self,
        vectors_by_prefix: dict[str, TokenVecs],
        fallback: LateInteractionEncoder | None = None,
    ):
        self.name = "scripted"
        self._map = vectors_by_prefix
        self._fallback = fallback or FakeLateInteractionEncoder()

    def _lookup(self, text: str) -> TokenVecs:
        for prefix, vecs in self._map.items():
            if text.startswith(prefix):
                return vecs
        return self._fallback.encode_query(text)

    def encode_query(self, text: str) -> TokenVecs:
        return validate_token_vectors(self._lookup(text))

    def encode_documents(self, texts: Sequence[str]) -> list[TokenVecs]:
        return [self.encode_query(t) for t in texts]


class FakeDenseEncoder:
    """Deterministic dense fake: one 1024-d pseudo-vector per text word-mean."""

    def __init__(self, salt: str = "fake-dense"):
        self.name = "fake-dense"
        self.dim = config.DENSE_DIM
        self._salt = salt

    def encode(self, texts: Sequence[str]) -> list[list[float]]:
        out = []
        for text in texts:
            words = text.split() or ["empty"]
            rows = [
                _stable_pseudovector(w, config.DENSE_DIM, self._salt) for w in words
            ]
            mean = [sum(col) / len(rows) for col in zip(*rows)]
            # Unit-normalise like bge-m3 output.
            norm = sum(v * v for v in mean) ** 0.5 or 1.0
            out.append(validate_dense_vector([v / norm for v in mean]))
        return out


__all__ = [
    "BgeM3DenseEncoder",
    "DenseEncoder",
    "ModelUnavailable",
    "build_dense_encoder",
    "build_late_encoder",
    "encoder_model",
    "fit_dense",
    "DenseEncoderProtocol",
    "EncodingError",
    "FakeDenseEncoder",
    "FakeLateInteractionEncoder",
    "LateInteractionEncoder",
    "PplxLateInteractionEncoder",
    "ScriptedEncoder",
    "TokenVecs",
    "truncate_for_embedding",
    "validate_dense_vector",
    "validate_token_vectors",
]
