"""Synthetic signals for the osint-geo tests: the source's own priors, fictional publishers (``*.example``), never a
real outlet or person (plan R13). Not a test module."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from osint_common.kinds import SOURCE_PRIORS
from osint_common.types import RawGeoHint, RawOsintSignal, signal_id_for


def make_signal(
    title: str,
    text: str = "",
    *,
    source: str = "google_news_rss",
    n: int = 1,
    place_names: list[str] | None = None,
    admin_codes: list[str] | None = None,
    category_hint: list[str] | None = None,
    publisher: str | None = "news-a.example",
    language: str = "en",
) -> RawOsintSignal:
    """A synthetic signal with the source's own priors (never a real outlet or person)."""
    prior = SOURCE_PRIORS[source]
    digest = hashlib.sha1(f"{title}|{text}".encode()).hexdigest()[:12]
    source_id = f"synthetic:os3-{source}-{n}-{digest}"
    return RawOsintSignal(
        signal_id=signal_id_for(source, source_id),
        source=source,  # type: ignore[arg-type]
        source_id=source_id,
        source_tier=prior.tier,  # type: ignore[arg-type]
        publisher=publisher,
        url=None,
        title=title,
        text=text or title,
        language=language,
        published_at=datetime(2026, 10, 20, 12, 0, tzinfo=UTC),
        fetched_at=datetime(2026, 10, 20, 12, 5, tzinfo=UTC),
        fetch_mode="cached-sample",
        pii_redactions=0,
        raw_geo_hint=RawGeoHint(place_names=place_names or [], admin_codes=admin_codes or []),
        category_hint=category_hint or [],
        provenance_label=prior.provenance_label,  # type: ignore[arg-type]
        credibility_prior=prior.credibility_prior,
        license=prior.license,
        redistributable=prior.redistributable,
    )
