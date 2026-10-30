"""OSINT ingest — ``POST /api/v1/osint/signals`` behind the oracle's trust boundary (contract C-T).

One batch (1..200 signals, already redacted at parse by osint-ingress) is screened signal by signal,
stored, and the recent window is RE-FUSED server-side through the OSINT libraries — all in ONE
serialised transaction:

1. **Screen** every signal: no person key at any depth (``ethics.assert_no_person_keys``), the
   canonical model (``RawOsintSignal``, ``extra="forbid"``), and the surviving-PII check again
   (``ethics.find_pii`` on the title and the text).  A failing signal is ``rejected`` with its reason
   (``forbidden_key`` | ``pii_unredacted`` | ``invalid``) and is NEVER stored; its id is echoed only
   when it is a well-formed signal id, and no text of it is ever logged.
2. **Trust boundary (plan R26)**: the payload's ``source_tier``, ``provenance_label``,
   ``credibility_prior``, ``license`` and ``redistributable`` are never trusted — they are re-derived
   from ``osint_common.kinds.SOURCE_PRIORS[signal.source]`` before anything is stored or fused, so a
   caller can never mint an "Official, verified" situation by labelling a signal so.  The one
   exception only ever LOWERS trust: a signal that declares itself ``EMULATED`` or ``SIMULATED``
   keeps that label (synthetic data stays labelled synthetic).  Signals whose payload disagreed are
   counted (the ``osint.ingest.counts`` log line and ``trust_boundary`` in the reply; no text).
   A news- or social-tier signal is stored without its raw URL (orchestrator decision: URL slugs can
   name a person; the publisher and the signal id stay) — counted as ``urls_withheld``.  A poster
   handle that slipped through parse is stripped from the title and the text before anything is
   stored or fused (ethics rule 2, defence in depth: ``osint_analysis.classify.strip_handles``, the
   pipeline's own helper — the ``submitted by …`` trailer goes, any other ``/u/<name>`` becomes
   ``[PERSON]``) — counted as ``account_refs_stripped``.
2b. **Scope (events are about places and road situations)**: a signal that reports a person-crime, a clash
   between groups or a political item (``osint_common.scope``: the wording, then the classifier's class —
   ``reported_crime``, ``public_conflict`` and ``unrest`` are out of scope) is ``rejected`` with
   ``out_of_scope_crime`` | ``out_of_scope_conflict`` | ``out_of_scope_political`` and is NEVER stored; a
   procession or gathering on a road is kept with its political terms withheld (``[WITHHELD]``).  The
   re-fused window is screened the same way (a signal stored before the rule is left out of re-fusion, so
   its situation is withdrawn), and a situation the pipeline still places in an out-of-scope class (the
   zero-shot fallback) is not written.  Counted in ``scope`` in the reply and the ``osint.ingest.counts``
   log line; no text.
3. **Store** ``osint.raw_signals`` (``ON CONFLICT DO NOTHING``: a repeat is counted in
   ``duplicates``), then **re-fuse** the window — this batch, every signal stored in the last 72 h,
   every signal published within 72 h of the batch's reports (so a replay or backfill of cached
   signals corroborates across batches too), each with every member of its current situation;
   ≤ 2 000 signals in WHOLE units (``store.load_window``: a situation that does not fit is left out
   untouched, never re-fused half-seen; counted as ``window.truncated``) — with
   ``run_pipeline(..., live=live_state.snapshot(conn, valkey=...))`` — the live corridor state,
   convoys in motion, 108 routes and closures the second-order flags read — and write the
   situations, sources and geocodes (``store.persist_result``: ``osint_event_id`` stays stable per
   ``fused_event_id``; an absorbed situation gets ``superseded_by``; a situation never
   corroborates the corridor event promoted from it — that attach is stored novel and not counted
   in ``attached_to_live``).

The pipeline is ``osint_analysis.pipeline.run_pipeline`` with an
``osint_geo.resolver.GazetteerResolver``, imported lazily by :func:`get_pipeline` — a FastAPI
dependency, so tests override it
(``app.dependency_overrides[get_pipeline]``) or set :data:`PIPELINE_HOOK`.  Without the libraries the
route answers 503 "osint pipeline not deployed" and stores nothing.
"""

from __future__ import annotations

import asyncio
import os
import re
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import structlog
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from osint_common import ethics, kinds, scope
from osint_common.pipeline import Embedder, GeoResolver, RunPipeline
from osint_common.types import PipelineResult, RawOsintSignal, signal_rejection_reason
from traffic_oracle.osint import live_state, store

logger = structlog.get_logger(__name__)

__all__ = [
    "HANDLE_REPLACEMENT",
    "HANDLE_STRIPPER_HOOK",
    "MAX_SIGNALS",
    "PIPELINE_HOOK",
    "PIPELINE_NOT_DEPLOYED",
    "TRUST_FIELDS",
    "IngestRequest",
    "Pipeline",
    "get_pipeline",
    "ingest_signals",
    "prepare_signal",
    "reset_pipeline_cache",
    "screen_signal",
    "strip_poster_handles",
]

#: The 503 detail when ``osint_geo`` / ``osint_analysis`` cannot import (C-T).
PIPELINE_NOT_DEPLOYED = "osint pipeline not deployed"

#: Signals per batch (C-T).
MAX_SIGNALS = 200

#: The payload fields the trust boundary re-derives from SOURCE_PRIORS (plan R26).
TRUST_FIELDS: tuple[str, ...] = (
    "source_tier",
    "provenance_label",
    "credibility_prior",
    "license",
    "redistributable",
)

#: Labels a producer may declare to mark its data synthetic: kept (they only lower trust).
_SELF_DECLARED_SYNTHETIC = frozenset({"EMULATED", "SIMULATED"})

_SIGNAL_ID = re.compile(r"^[0-9a-f]{40}$")


class IngestRequest(BaseModel):
    """``POST /api/v1/osint/signals`` body (C-T): 1..200 signals, each screened on its own."""

    model_config = ConfigDict(extra="forbid")

    signals: list[dict[str, Any]] = Field(min_length=1, max_length=MAX_SIGNALS)
    run_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:\-]{0,63}$")


@dataclass(frozen=True)
class Pipeline:
    """The fusion seam: ``run`` is ``run_pipeline``, ``resolver`` the geo-resolver."""

    run: RunPipeline | Callable[..., PipelineResult]
    resolver: GeoResolver
    embedder: Embedder | None = None


#: A test / tooling hook: when set, :func:`get_pipeline` returns ``PIPELINE_HOOK()``.
PIPELINE_HOOK: Callable[[], Pipeline] | None = None

_CACHED: list[Pipeline | None] = [None]


def reset_pipeline_cache() -> None:
    """Forget the cached real pipeline (tests)."""
    _CACHED[0] = None


def _dedup_embedder() -> Embedder | None:
    """Cross-script duplicate detection uses the embedding service's dense vectors (``POST /embed``) when
    ``OSINT_EMBEDDING_URL`` (else the oracle's own ``EMBEDDING_SERVICE_URL``) names it and ``OSINT_EMBED_DEDUP``
    is not ``0``.  ``None`` keeps the token-Jaccard fallback — so does an embedder that cannot answer, per call."""
    url = os.environ.get("OSINT_EMBEDDING_URL") or os.environ.get("EMBEDDING_SERVICE_URL")
    if not url or os.environ.get("OSINT_EMBED_DEDUP", "1") == "0":
        return None
    try:
        from osint_analysis.embed import HttpEmbedder  # noqa: PLC0415 — lazy like the rest of the pipeline
        return HttpEmbedder(url)
    except Exception as exc:  # noqa: BLE001 — dedup degrades to Jaccard, never blocks ingest
        logger.warning("osint.pipeline.embedder_unavailable", error_type=type(exc).__name__)
        return None


def get_pipeline() -> Pipeline:
    """The real pipeline: ``osint_analysis.pipeline.run_pipeline`` + ``osint_geo.resolver
    .GazetteerResolver()`` (loaded once per process).  503 "osint pipeline not deployed" when either
    library is missing or the resolver cannot load — before anything is stored."""
    if PIPELINE_HOOK is not None:
        return PIPELINE_HOOK()
    if _CACHED[0] is not None:
        return _CACHED[0]
    try:
        from osint_analysis.pipeline import run_pipeline  # noqa: PLC0415 — lazy by design (X20)
        from osint_geo.resolver import GazetteerResolver  # noqa: PLC0415
    except ImportError as exc:
        raise HTTPException(status_code=503, detail=PIPELINE_NOT_DEPLOYED) from exc
    try:
        resolver = GazetteerResolver()
    except Exception as exc:  # noqa: BLE001 — a resolver that cannot load is not deployed
        logger.warning("osint.pipeline.resolver_failed", error_type=type(exc).__name__)
        raise HTTPException(status_code=503, detail=PIPELINE_NOT_DEPLOYED) from exc
    pipeline = Pipeline(run=run_pipeline, resolver=resolver, embedder=_dedup_embedder())
    _CACHED[0] = pipeline
    return pipeline


# ---------------------------------------------------------------------------
# Screening and the trust boundary (pure)
# ---------------------------------------------------------------------------


def _echo_id(item: Any) -> str | None:
    """A rejected signal's id, echoed only when it is a well-formed signal id (never free text)."""
    sid = item.get("signal_id") if isinstance(item, dict) else None
    return sid if isinstance(sid, str) and _SIGNAL_ID.fullmatch(sid) else None


def screen_signal(item: Any) -> tuple[RawOsintSignal | None, str | None]:
    """``(signal, None)`` when the signal passes every rail, else ``(None, reason)``."""
    try:
        ethics.assert_no_person_keys(item)
    except ValueError as exc:
        return None, ("forbidden_key" if "forbidden_key" in str(exc) else "invalid")
    try:
        signal = RawOsintSignal.model_validate(item)
    except ValidationError as exc:
        return None, signal_rejection_reason(exc)
    # find_pii proves only its own patterns are absent; find_unredactable also refuses Indic-script words the redactor
    # must withhold ([WITHHELD]) — a signal that still carries one was not redacted (FIX-G-OSINT, OSINT-2)
    if (
        ethics.find_pii(signal.title)
        or ethics.find_pii(signal.text)
        or ethics.find_unredactable(signal.title)
        or ethics.find_unredactable(signal.text)
    ):
        return None, "pii_unredacted"
    return signal, None


@dataclass(frozen=True)
class Prepared:
    """A screened signal after the trust boundary."""

    signal: RawOsintSignal
    disagreed: bool
    url_withheld: bool
    #: a poster handle was stripped from its title or text
    account_refs_stripped: bool = False


#: The replacement of a poster handle in a text that leaves the oracle (the parse redaction token).
HANDLE_REPLACEMENT = "[PERSON]"

#: ``RawOsintSignal.title`` / ``.text`` limits.
_TITLE_MAX = 1000
_TEXT_MAX = 4000

#: A test / tooling hook replacing the handle stripper (default: the pipeline's own helper).
HANDLE_STRIPPER_HOOK: Callable[[str, str], str] | None = None

#: The fallback when ``osint_analysis`` is not importable (a hooked pipeline): the same patterns as
#: ``osint_analysis.classify`` (a profile link, ``/u/<name>`` or a bare ``u/<name>`` never inside a
#: word or a path — "u/s 302" is legal shorthand; the RSS trailer; the ``[link]``/``[comments]``
#: boilerplate).
_FALLBACK_HANDLE = (
    r"(?:(?:https?://)?(?:[\w-]+\.)*reddit\.com/(?:u|user)/[A-Za-z0-9_-]{3,}/?"
    r"|(?<![\w/])/?u/[A-Za-z0-9_-]{3,})"
)
_FALLBACK_BOILERPLATE = r"\[(?:link|comments)\]"
_FALLBACK_HANDLE_RE = re.compile(_FALLBACK_HANDLE, re.IGNORECASE)
_FALLBACK_BOILERPLATE_RE = re.compile(_FALLBACK_BOILERPLATE, re.IGNORECASE)
_FALLBACK_TRAILER_RE = re.compile(
    r"(?:\s*[,;:|–—-])?\s*\bsubmitted\s+by\s*(?:(?:" + _FALLBACK_HANDLE + r"|\[person\])(?:\s*"
    + _FALLBACK_BOILERPLATE + r")*|(?:" + _FALLBACK_BOILERPLATE + r"\s*)+|$)",
    re.IGNORECASE,
)


def _fallback_strip_handles(text: str, replacement: str = " ") -> str:
    out = _FALLBACK_TRAILER_RE.sub(" ", text)
    out = _FALLBACK_HANDLE_RE.sub(replacement, out)
    out = _FALLBACK_BOILERPLATE_RE.sub(" ", out)
    return text if out == text else out.strip()


def _handle_stripper() -> Callable[[str, str], str]:
    if HANDLE_STRIPPER_HOOK is not None:
        return HANDLE_STRIPPER_HOOK
    try:
        from osint_analysis.classify import strip_handles  # noqa: PLC0415 — lazy by design (X20)
    except ImportError:
        return _fallback_strip_handles
    return strip_handles


def strip_poster_handles(text: str) -> str:
    """``text`` without poster handles (``[PERSON]`` in their place; the RSS trailer and boilerplate
    dropped); an unchanged text is returned as it was."""
    if not text:
        return text
    return _handle_stripper()(text, HANDLE_REPLACEMENT)


def prepare_signal(signal: RawOsintSignal) -> Prepared:
    """Re-derive the trust fields from SOURCE_PRIORS (plan R26), withhold a news/social URL and
    strip any poster handle from the title and the text (ethics rule 2)."""
    prior = kinds.SOURCE_PRIORS[signal.source]
    derived: dict[str, Any] = {
        "source_tier": prior.tier,
        "provenance_label": prior.provenance_label,
        "credibility_prior": prior.credibility_prior,
        "license": prior.license,
        "redistributable": prior.redistributable,
    }
    trusted = dict(derived)
    if signal.provenance_label in _SELF_DECLARED_SYNTHETIC:
        trusted["provenance_label"] = signal.provenance_label  # only ever lowers trust
    disagreed = any(getattr(signal, f) != derived[f] for f in TRUST_FIELDS)
    data = signal.model_dump()
    data.update(trusted)
    withheld = prior.tier in store.URL_WITHHELD_TIERS and (
        signal.url is not None or signal.raw_geo_hint.polygon_url is not None
    )
    if prior.tier in store.URL_WITHHELD_TIERS:
        data["url"] = None
        data["raw_geo_hint"] = dict(data["raw_geo_hint"], polygon_url=None)
    title, text = strip_poster_handles(signal.title), strip_poster_handles(signal.text)
    stripped = title != signal.title or text != signal.text
    # the token is longer than a short handle: keep each text inside its model limit
    data["title"], data["text"] = title[:_TITLE_MAX], text[:_TEXT_MAX]
    return Prepared(RawOsintSignal.model_validate(data), disagreed, withheld, stripped)


# ---------------------------------------------------------------------------
# The scope gate (osint_common.scope)
# ---------------------------------------------------------------------------

#: A test / tooling hook replacing the classifier the scope gate reads (default: ``osint_analysis``'s).
SCOPE_CLASSIFIER_HOOK: Callable[[RawOsintSignal], Any] | None = None

#: The scope gate is always on in the service: nothing (no environment variable, no setting) reads or sets this.
#: It exists for the test modules whose synthetic fixtures were written before the rule — they exercise fusion,
#: decision support and promotion mechanics on a reported clash beside a collision — and turn it off for their
#: own tests only (``SCOPE_GATE_OFF = True`` in the module, read by tests/conftest.py).
SCOPE_GATE: bool = True


def _scope_class(signal: RawOsintSignal) -> str | None:
    """The deterministic (lexicon) class of a signal, or None when the classifier is not importable."""
    classify = SCOPE_CLASSIFIER_HOOK
    if classify is None:
        try:
            from osint_analysis.classify import classify  # noqa: PLC0415 — lazy by design (X20)
        except ImportError:
            return None
    try:
        return str(classify(signal).event_class)
    except Exception:  # noqa: BLE001 — a classifier failure never lets a text through unscreened by wording
        return None


def scope_screen(signal: RawOsintSignal) -> tuple[RawOsintSignal | None, str | None, int]:
    """``(signal, None, masked)`` when in scope (its political terms withheld when ``masked``), else
    ``(None, reason, 0)`` with reason ``crime`` | ``conflict`` | ``political``."""
    if not SCOPE_GATE:
        return signal, None, 0
    verdict = scope.screen(signal.title, signal.text)
    if verdict.reason is not None:
        return None, verdict.reason, 0
    if verdict.masked:
        signal = RawOsintSignal.model_validate(
            dict(signal.model_dump(), title=verdict.title[:_TITLE_MAX], text=verdict.text[:_TEXT_MAX])
        )
    out = scope.screen_class(_scope_class(signal))
    if out is not None:
        return None, out, 0
    return signal, None, verdict.masked


def scope_window(signals: Sequence[RawOsintSignal]) -> tuple[list[RawOsintSignal], Counter[str]]:
    """The re-fusion window without out-of-scope signals (stored before the rule), and the count by reason."""
    kept: list[RawOsintSignal] = []
    left_out: Counter[str] = Counter()
    for s in signals:
        screened, reason, _ = scope_screen(s)
        if screened is None:
            left_out[str(reason)] += 1
        else:
            kept.append(screened)
    return kept, left_out


def scope_result(result: PipelineResult) -> tuple[PipelineResult, int]:
    """The pipeline's answer without a situation in an out-of-scope class (primary or correlated)."""
    if not SCOPE_GATE:
        return result, 0
    keep = [
        r
        for r in result.resolved
        if scope.screen_class(r.event_class) is None
        and not any(scope.screen_class(c) for c in (r.correlated_classes or ()))
    ]
    dropped = len(result.resolved) - len(keep)
    if not dropped:
        return result, 0
    counts = result.counts.model_copy(
        update={"fused": len(keep), "surfaced": sum(1 for r in keep if r.is_event)}
    )
    return result.model_copy(update={"resolved": keep, "counts": counts}), dropped


# ---------------------------------------------------------------------------
# The transaction
# ---------------------------------------------------------------------------


def _resolved_item(ev: Any, oid: str, roads: tuple[int | None, int | None]) -> dict:
    """One C-T ``resolved[]`` item, with the road ids as STORED (an unknown one is NULL)."""
    return {
        "osint_event_id": oid,
        "fused_event_id": ev.fused_event_id,
        "event_class": ev.event_class,
        "subtype": ev.subtype,
        "sajag_event_kind": ev.sajag_event_kind,
        "is_event": ev.is_event,
        "verification_state": ev.verification_state,
        "credibility": ev.credibility,
        "segment_id": roads[0],
        "junction_id": roads[1],
        "source_count": ev.source_count,
    }


async def _run(pipeline: Pipeline, signals: Sequence[RawOsintSignal], live: Any, now: datetime) -> PipelineResult:
    result = await asyncio.to_thread(
        pipeline.run,
        list(signals),
        resolver=pipeline.resolver,
        live=live,
        embedder=pipeline.embedder,
        now=now,
    )
    return result if isinstance(result, PipelineResult) else PipelineResult.model_validate(result)


async def ingest_signals(
    conn: Any,
    pipeline: Pipeline,
    items: Sequence[Any],
    *,
    run_id: str | None = None,
    now: datetime | None = None,
    valkey: Any = None,
) -> dict:
    """Screen, store and re-fuse one batch in ONE transaction; the C-T 200 body.  ``valkey`` (the
    app's client) lets the live state read the convoy position frames."""
    when = now or datetime.now(UTC)
    rejected: list[dict] = []
    reasons: Counter[str] = Counter()
    prepared: list[Prepared] = []
    scope_rejected: Counter[str] = Counter()
    masked_terms = 0
    for item in items:
        signal, reason = screen_signal(item)
        if signal is None:
            rejected.append({"signal_id": _echo_id(item), "reason": reason})
            reasons[str(reason)] += 1
            continue
        in_scope, out, masked = scope_screen(signal)
        if in_scope is None:
            rejected.append({"signal_id": _echo_id(item), "reason": f"out_of_scope_{out}"})
            reasons[f"out_of_scope_{out}"] += 1
            scope_rejected[str(out)] += 1
            continue
        signal, masked_terms = in_scope, masked_terms + masked
        try:
            prepared.append(prepare_signal(signal))
        except ValidationError:  # a text the handle strip left invalid is never stored
            rejected.append({"signal_id": _echo_id(item), "reason": "invalid"})
            reasons["invalid"] += 1

    accepted = duplicates = 0
    batch_ids: list[str] = []
    result = PipelineResult()
    outcome = store.PersistOutcome()
    window = store.Window()
    window_left_out: Counter[str] = Counter()
    situations_left_out = 0
    async with conn.transaction():
        await store.lock_ingest(conn)
        for p in prepared:
            if await store.insert_signal(conn, p.signal, run_id=run_id):
                accepted += 1
            else:
                duplicates += 1
            batch_ids.append(p.signal.signal_id)
        batch_ids = list(dict.fromkeys(batch_ids))
        if batch_ids:
            window = await store.load_window(conn, batch_ids)
        if window.signals:
            live = await live_state.snapshot(conn, now=when, valkey=valkey)
            fused_in, window_left_out = scope_window(window.signals)
            try:
                result = await _run(pipeline, fused_in, live, when)
                result, situations_left_out = scope_result(result)
            except HTTPException:
                raise
            except Exception as exc:
                logger.warning("osint.ingest.pipeline_failed", error_type=type(exc).__name__)
                raise HTTPException(
                    status_code=500, detail=f"osint pipeline failed ({type(exc).__name__})"
                ) from exc
            outcome = await store.persist_result(conn, result, window.signal_ids)

    batch = set(batch_ids)
    resolved = [
        _resolved_item(
            ev,
            outcome.ids_by_fused[ev.fused_event_id],
            outcome.roads_by_fused.get(ev.fused_event_id, (ev.segment_id, ev.junction_id)),
        )
        for ev in result.resolved
        if ev.fused_event_id in outcome.ids_by_fused and batch & set(ev.member_signal_ids)
    ]
    geotagged = sum(1 for sid in batch if result.geocodes.get(sid) is not None)
    trust = {
        "payload_disagreed": sum(1 for p in prepared if p.disagreed),
        "urls_withheld": sum(1 for p in prepared if p.url_withheld),
        "account_refs_stripped": sum(1 for p in prepared if p.account_refs_stripped),
    }
    counts = result.counts
    if outcome.self_attach_cleared:  # stored novel: the counts say what was stored
        counts = counts.model_copy(
            update={
                "attached_to_live": max(
                    0, counts.attached_to_live - len(outcome.self_attach_cleared)
                )
            }
        )
    logger.info(
        "osint.ingest.counts",
        received=len(items),
        accepted=accepted,
        duplicates=duplicates,
        rejected=len(rejected),
        rejected_reasons=dict(reasons),
        trust_overrides=trust["payload_disagreed"],
        urls_withheld=trust["urls_withheld"],
        account_refs_stripped=trust["account_refs_stripped"],
        scope_rejected=dict(scope_rejected),
        scope_masked_terms=masked_terms,
        scope_window_left_out=dict(window_left_out),
        scope_situations_left_out=situations_left_out,
        window=len(window.signals),
        window_seeds=window.seeds,
        window_units=window.units,
        window_truncated=window.truncated_signals,
        window_truncated_units=window.truncated_units,
        window_unreadable=window.unreadable_signals,
        situations=len(result.resolved),
        surfaced=counts.surfaced,
        inserted=outcome.inserted,
        updated=outcome.updated,
        superseded=len(outcome.superseded),
        inherited=len(outcome.inherited),
        withdrawn=len(outcome.withdrawn),
        self_attach_cleared=len(outcome.self_attach_cleared),
        unknown_road_ids=outcome.unknown_road_ids,
        run_id=run_id,
    )
    return {
        "accepted": accepted,
        "duplicates": duplicates,
        "rejected": rejected,
        "geotagged": geotagged,
        "resolved": resolved,
        "counts": counts.model_dump(mode="json"),
        # additive: what the trust boundary did to this batch (counts only, no text)
        "trust_boundary": trust,
        # additive: the scope gate (counts only, no text): rejected by reason, political terms withheld from
        # kept signals, stored signals left out of re-fusion by reason, situations not written
        "scope": {
            "rejected": dict(scope_rejected),
            "masked_terms": masked_terms,
            "window_left_out": dict(window_left_out),
            "situations_left_out": situations_left_out,
        },
        "superseded": [{"osint_event_id": k, "superseded_by": v} for k, v in outcome.superseded.items()],
        # additive: the re-fused window — signals read, and those left out WHOLE (a unit that did
        # not fit the cap, or one with a member that could not be rebuilt), stored and untouched
        "window": {
            "signals": len(window.signals),
            "truncated": window.truncated_signals,
            "unreadable": window.unreadable_signals,
        },
    }
