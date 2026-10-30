"""The pipeline protocols (X18): what the geo-resolver (OS-3), the embedder (OS-4) and ``run_pipeline`` (OS-4)
provide, so the oracle (OS-5), the ingress dry run (OS-2) and the tests can be built against them in parallel.

Implemented by ``osint_analysis.pipeline``::

    run_pipeline(signals, *, resolver: GeoResolver, live: LiveStateSnapshot | None = None,
                 embedder: Embedder | None = None, now: datetime | None = None) -> PipelineResult

It is pure and deterministic: no database and no network except the optional embedder.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol, runtime_checkable

from osint_common.types import Geocode, LiveStateSnapshot, PipelineResult, RawOsintSignal

__all__ = ["Embedder", "GeoResolver", "RunPipeline"]


@runtime_checkable
class GeoResolver(Protocol):
    """Resolve one signal to a :class:`Geocode`, or an honest ``None`` (never a centroid dressed as precise)."""

    def resolve(self, signal: RawOsintSignal) -> Geocode | None: ...


@runtime_checkable
class Embedder(Protocol):
    """Dense embeddings for semantic dedup; ``None`` on any failure (the pipeline never depends on it)."""

    def embed(self, texts: list[str]) -> list[list[float]] | None: ...


class RunPipeline(Protocol):
    """The ``run_pipeline`` callable's signature, for injecting a pipeline (OS-5 tests, OS-2 ``--dry-run``)."""

    def __call__(
        self,
        signals: Sequence[RawOsintSignal],
        *,
        resolver: GeoResolver,
        live: LiveStateSnapshot | None = None,
        embedder: Embedder | None = None,
        now: datetime | None = None,
    ) -> PipelineResult: ...
