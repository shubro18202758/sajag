"""The cycle engine shared by ``serve``, ``POST /cycle`` and ``once``.

One cycle: run the chosen connectors in order (live: ``fetch`` then ``parse``; a failed fetch falls back to the
newest cache entry, honestly labelled ``cached-sample``; offline: ``parse`` the newest entry), apply cache
retention, then queue the new signals in the outbox and flush it to the oracle when the oracle is reachable.

A source that asks us to slow down (``ConnectorThrottled``: HTTP 429, a throttle banner, an overload timeout) is
backed off (:class:`Backoff`): no request to it until the server's ``Retry-After`` or a jittered exponential delay
(the connector's cadence × 2^(n-1), ±20 %, at most 2 h), whichever is later. Meanwhile each run serves the
connector's last LIVE answer and says so with its real fetch time and age (``cache_age_sec``); it is never a
recorded sample. One answer resets the back-off.

A source that says no (``ConnectorDisabled``: "robots.txt disallows") is not a failure: that connector is
disabled for the run, its cache is NOT served in place of the fetch, and ``/health`` shows it ``enabled: false``
with the reason as its ``error``. It stays on the schedule, so it re-enables itself once the source allows it
(robots.txt is re-read every 24 h).

``/health`` (contract, OS-2 → OS-INT)::

    {status: "ok"|"degraded", mode: "live"|"offline", version,
     oracle: {host: "127.0.0.1:<port>", reachable, last_post_at|null, last_post_status|null},
     connectors: {<name>: {enabled, cadence_sec, last_run_at|null, last_ok_at|null, fetch_mode|null, signals,
                           error|null, cache_age_sec|null}},
     last_cycle: {at|null, signals, accepted, rejected, geotagged, surfaced, pii_redactions},
     egress_allowlist: [host, ...]}

``ok`` = the process is up and a cycle has completed (offline counts) with the oracle reachable; ``degraded`` =
the oracle is unreachable, no cycle has completed yet, or every enabled connector that ran in the last cycle
failed (a connector its source disabled does not count as failed). ``oracle.reachable`` comes only from the
``GET /health`` probe. ``cache_age_sec`` (an additive field) is the age of the cached sample a connector served,
so an offline box shows how stale it is.
"""

from __future__ import annotations

import asyncio
import json
import random
import secrets
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import structlog

from osint_common import ethics
from osint_common.types import RawOsintSignal
from osint_ingress import __version__
from osint_ingress.cache import Cache, stamp_of
from osint_ingress.connectors._redact import has_poster_handle, has_url
from osint_ingress.connectors.base import Connector, ConnectorDisabled, ConnectorError, ConnectorThrottled
from osint_ingress.publish import PublishResult, Publisher
from osint_ingress.safe_http import EGRESS_HOSTS, EgressRefused, FetchError, network_reason

__all__ = ["Backoff", "ConnectorStatus", "CycleReport", "Engine", "new_run_id", "signal_checks"]

log = structlog.get_logger("osint_ingress.runner")


def _iso(dt: datetime | None) -> str | None:
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z") if dt else None


def new_run_id(now: datetime | None = None) -> str:
    """``osint-<UTC stamp>-<4 hex>`` (≤ 64 characters, the C-T ``run_id`` bound)."""
    return f"osint-{stamp_of(now or datetime.now(UTC))}-{secrets.token_hex(2)}"


#: the longest back-off (a throttled source is asked again at least every six hours)
MAX_BACKOFF_SEC = 2 * 3600


@dataclass
class Backoff:
    """Jittered exponential back-off for one throttled connector (module docstring)."""

    base_sec: float
    failures: int = 0
    until: datetime | None = None
    rng: random.Random = field(default_factory=random.Random)

    def active(self, now: datetime) -> bool:
        return self.until is not None and now < self.until

    def fail(self, now: datetime, retry_after_sec: float | None = None) -> datetime:
        self.failures += 1
        delay = min(MAX_BACKOFF_SEC, max(60.0, self.base_sec) * 2 ** (self.failures - 1))
        delay *= 1.0 + self.rng.uniform(-0.2, 0.2)
        if retry_after_sec is not None and retry_after_sec > 0:
            delay = max(delay, min(float(retry_after_sec), 24 * 3600.0))
        self.until = now + timedelta(seconds=delay)
        return self.until

    def reset(self) -> None:
        self.failures, self.until = 0, None


def _hhmm(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%Y-%m-%d %H:%MZ")


def _age(sec: float) -> str:
    m = int(sec // 60)
    return f"{m} min old" if m < 120 else f"{m // 60} h {m % 60} min old"


def _serving(entry: Any, now: datetime) -> str:
    """How a fallback entry is described: the last LIVE answer with its fetch time and age, or an imported capture."""
    if getattr(entry, "origin", "live") == "live" and not getattr(entry, "synthetic", False):
        return f"serving the last live answer, fetched {_hhmm(entry.captured_at)} ({_age(entry.age_sec(now))})"
    return f"serving the cached entry (an imported capture from {_hhmm(entry.captured_at)}, not a live answer)"


@dataclass
class ConnectorStatus:
    name: str
    #: on the schedule (configured, not disabled in code); a source's own "no" is :attr:`disabled_by`
    enabled: bool
    cadence_sec: int
    last_run_at: datetime | None = None
    last_ok_at: datetime | None = None
    fetch_mode: str | None = None
    signals: int = 0
    error: str | None = None
    cache_age_sec: int | None = None
    pii_redactions: int = 0
    dropped: dict[str, int] = field(default_factory=dict)
    #: set while the source disables the connector ("robots.txt disallows"); cleared by the next allowed fetch
    disabled_by: str | None = None
    #: the throttle that started the current back-off ("HTTP 429 (throttled)"); cleared by the next answer
    throttle_reason: str | None = None

    @property
    def active(self) -> bool:
        """Scheduled and not disabled by its source (what ``/health`` reports as ``enabled``)."""
        return self.enabled and self.disabled_by is None

    def as_health(self) -> dict[str, Any]:
        return {
            "enabled": self.active,
            "cadence_sec": self.cadence_sec,
            "last_run_at": _iso(self.last_run_at),
            "last_ok_at": _iso(self.last_ok_at),
            "fetch_mode": self.fetch_mode,
            "signals": self.signals,
            "error": self.error,
            "cache_age_sec": self.cache_age_sec,
        }


@dataclass
class CycleReport:
    run_id: str
    started_at: datetime
    finished_at: datetime
    mode: str
    connectors: dict[str, ConnectorStatus]
    signals: list[RawOsintSignal]
    publish: PublishResult
    oracle_reachable: bool

    @property
    def pii_redactions(self) -> int:
        return sum(s.pii_redactions for s in self.signals)

    @property
    def all_failed(self) -> bool:
        ran = [c for c in self.connectors.values() if c.active]
        return bool(ran) and all(c.error is not None for c in ran)

    def last_cycle(self) -> dict[str, Any]:
        return {
            "at": _iso(self.finished_at),
            "signals": len(self.signals),
            "accepted": self.publish.accepted,
            "rejected": self.publish.rejected,
            "geotagged": self.publish.geotagged,
            "surfaced": self.publish.surfaced if self.publish.surfaced is not None else 0,
            "pii_redactions": self.pii_redactions,
        }

    def as_report(self) -> dict[str, Any]:
        # every connector that ran is listed, with 0 when it produced nothing (e.g. gdelt_events on a quiet slice)
        per_source: Counter[str] = Counter({name: 0 for name in self.connectors})
        per_source.update(s.source for s in self.signals)
        pii: Counter[str] = Counter({name: 0 for name in self.connectors})
        for s in self.signals:
            pii[s.source] += s.pii_redactions
        return {
            "run_id": self.run_id,
            "version": __version__,
            "mode": self.mode,
            "started_at": _iso(self.started_at),
            "finished_at": _iso(self.finished_at),
            "elapsed_sec": round((self.finished_at - self.started_at).total_seconds(), 3),
            "oracle_reachable": self.oracle_reachable,
            "publish": self.publish.status,
            "publish_detail": self.publish.as_dict(),
            "signals": len(self.signals),
            "per_source": dict(sorted(per_source.items())),
            "pii_redactions": self.pii_redactions,
            "pii_by_source": dict(sorted(pii.items())),
            "connectors": {
                name: {
                    "enabled": st.active,
                    "fetch_mode": st.fetch_mode,
                    "signals": st.signals,
                    "pii_redactions": st.pii_redactions,
                    "error": st.error,
                    "cache_age_sec": st.cache_age_sec,
                    "dropped": st.dropped,
                }
                for name, st in self.connectors.items()
            },
            "checks": signal_checks(self.signals),
        }


def signal_checks(signals: Sequence[RawOsintSignal]) -> dict[str, int]:
    """Re-check every emitted signal (parity evidence): validation, surviving PII in the text and in ``raw``,
    person keys, poster handles (``u/<name>``, ``/user/<name>``, a Reddit user page or a social-platform profile
    link anywhere; ``@<name>`` or "insta: <handle>" in social posts: the redactor's own detectors), the URL rule
    (no news or social ``url``/``polygon_url``, and no URL left in a news or social title or text) and the ``raw``
    whitelist. Counts only."""
    validated = pii_clean = person_keys = handles = urls = raw_bad = raw_pii = crime = 0
    social_text_url = news_text_url = 0
    for s in signals:
        dump = s.model_dump(mode="json")
        try:
            RawOsintSignal.model_validate(dump)
            validated += 1
        except ValueError:
            pass
        if not ethics.find_pii(s.title) and not ethics.find_pii(s.text):
            pii_clean += 1
        try:
            ethics.assert_no_person_keys(dump)
        except ValueError:
            person_keys += 1
        if has_poster_handle(s.title, s.source_tier) or has_poster_handle(s.text, s.source_tier):
            handles += 1
        if s.source_tier != "official" and (s.url or s.raw_geo_hint.polygon_url):
            urls += 1
        if s.source_tier != "official" and (has_url(s.title) or has_url(s.text)):
            if s.source_tier == "social_unverified":
                social_text_url += 1
            else:
                news_text_url += 1
        if not set(s.raw) <= ethics.RAW_ALLOWED_KEYS:
            raw_bad += 1
        # raw values are checked as strictly as a social post (an @-handle there counts too)
        if any(
            isinstance(v, str) and (ethics.find_pii(v) or has_poster_handle(v, "social_unverified"))
            for v in s.raw.values()
        ):
            raw_pii += 1
        if "crime_incident" in json.dumps(dump):
            crime += 1
    return {
        "signals": len(signals),
        "validated": validated,
        "find_pii_clean": pii_clean,
        "with_person_key": person_keys,
        "with_poster_handle": handles,
        "news_social_with_url": urls,
        "social_text_with_url": social_text_url,
        "news_text_with_url": news_text_url,
        "raw_outside_whitelist": raw_bad,
        "raw_with_person_value": raw_pii,
        "mentions_crime_incident": crime,
    }


def _short(exc: BaseException) -> str:
    if isinstance(exc, (ConnectorError, EgressRefused, FetchError)):
        return str(exc)[:200]
    if isinstance(exc, httpx.HTTPError):
        return network_reason(exc)
    return f"failed ({type(exc).__name__})"


class Engine:
    """Connectors + cache + publisher, and the state ``/health`` reports."""

    def __init__(
        self,
        *,
        mode: str,
        source_client: httpx.AsyncClient,
        publisher: Publisher,
        cache: Cache,
        connectors: dict[str, Connector],
        protect: frozenset[str],
        cadences: dict[str, int],
    ) -> None:
        self.mode = mode
        self.client = source_client
        self.publisher = publisher
        self.cache = cache
        self.connectors = connectors
        self.protect = protect
        self.statuses: dict[str, ConnectorStatus] = {
            name: ConnectorStatus(
                name=name,
                enabled=conn.enabled and conn.scheduled and cadences.get(name, 0) > 0,
                cadence_sec=cadences.get(name, 0) if (conn.enabled and conn.scheduled) else 0,
                error=conn.disabled_reason,
            )
            for name, conn in connectors.items()
        }
        self.last: CycleReport | None = None
        self._lock = asyncio.Lock()
        #: per-connector back-off after a throttle (module docstring); based on the connector's cadence
        self.backoff: dict[str, Backoff] = {
            name: Backoff(base_sec=float(cadences.get(name) or conn.default_cadence_sec or 900))
            for name, conn in connectors.items()
        }

    @property
    def offline(self) -> bool:
        return self.mode == "offline"

    def scheduled_names(self) -> list[str]:
        return [n for n, st in self.statuses.items() if st.enabled]

    async def run_connector(self, name: str) -> tuple[list[RawOsintSignal], ConnectorStatus]:
        conn = self.connectors[name]
        st = self.statuses[name]
        now = datetime.now(UTC)
        st.last_run_at = now
        st.dropped = {}
        if not conn.enabled:
            st.error, st.signals, st.fetch_mode, st.pii_redactions = conn.disabled_reason, 0, None, 0
            return [], st
        entry = None
        error: str | None = None
        if self.offline:
            entry = self.cache.latest(name)
            if entry is None:
                error = "no cached entry (offline mode)"
        else:
            disabled: str | None = None
            backoff = self.backoff[name]
            if backoff.active(now):  # throttled earlier: no request until the back-off ends
                assert backoff.until is not None
                error = (f"{st.throttle_reason or 'throttled'}; backing off until {_hhmm(backoff.until)} "
                         f"(attempt {backoff.failures}, no request sent)")
            else:
                try:
                    entry = await conn.fetch(self.client, self.cache)
                    backoff.reset()
                    st.throttle_reason = None
                except ConnectorThrottled as exc:  # slow down: back off, serve the last live answer meanwhile
                    until = backoff.fail(now, exc.retry_after_sec)
                    st.throttle_reason = str(exc)[:120]
                    error = f"{st.throttle_reason}; backing off until {_hhmm(until)} (attempt {backoff.failures})"
                except ConnectorDisabled as exc:  # the source says no: disabled, and the cache is NOT served instead
                    disabled = error = str(exc)[:200]
                except Exception as exc:  # noqa: BLE001 - any connector failure degrades to the cache, never crashes
                    error = _short(exc)
                    if not isinstance(exc, (ConnectorError, EgressRefused, FetchError, httpx.HTTPError)):
                        log.error("fetch_crashed", connector=name, error=type(exc).__name__)
            st.disabled_by = disabled
            if entry is None and disabled is None:
                cached = self.cache.latest(name)
                if cached is not None:
                    entry = cached
                    error = f"{error or 'fetch skipped'}; {_serving(cached, now)}"
                elif error is None:
                    error = "fetch skipped and nothing cached"
        signals: list[RawOsintSignal] = []
        if entry is not None:
            try:
                signals = conn.parse(entry, self.protect)
            except Exception as exc:  # noqa: BLE001 - a refused document is that connector's failure only
                error = f"parse: {_short(exc)}"
                signals = []
            st.dropped = dict(conn.last_dropped)  # only this run's parse counts (never a previous one's)
        st.fetch_mode = entry.fetch_mode if entry is not None else None
        st.cache_age_sec = int(entry.age_sec(now)) if entry is not None and entry.fetch_mode == "cached-sample" else None
        st.signals = len(signals)
        st.pii_redactions = sum(s.pii_redactions for s in signals)
        st.error = error
        if error is None:
            st.last_ok_at = now
        log.info(
            "connector_ran",
            connector=name,
            fetch_mode=st.fetch_mode,
            signals=st.signals,
            pii_redactions=st.pii_redactions,
            # counts by reason only (out_of_scope_* included); never a text
            dropped=st.dropped,
            error=error,
        )
        return signals, st

    async def collect(self, names: Iterable[str]) -> tuple[list[RawOsintSignal], dict[str, ConnectorStatus]]:
        signals: list[RawOsintSignal] = []
        ran: dict[str, ConnectorStatus] = {}
        for name in names:
            got, st = await self.run_connector(name)
            signals.extend(got)
            ran[name] = st
        return signals, ran

    async def cycle(
        self, names: Iterable[str] | None = None, *, probe_first: bool = False, publish: bool = True
    ) -> CycleReport:
        """One cycle over ``names`` (default: every scheduled, enabled connector)."""
        async with self._lock:
            started = datetime.now(UTC)
            run_id = new_run_id(started)
            reachable = await self.publisher.probe() if probe_first else self.publisher.status.reachable
            signals, ran = await self.collect(list(names) if names is not None else self.scheduled_names())
            try:
                self.cache.prune()
            except OSError as exc:
                log.warning("prune_failed", error=type(exc).__name__)
            result = PublishResult(status="dry-run" if not publish else "nothing new")
            if publish:
                outbox_error = False
                try:
                    queued = self.publisher.enqueue(signals, run_id)
                except OSError as exc:  # an unwritable cache volume: report it, never crash the cycle
                    log.error("outbox_unwritable", error=type(exc).__name__)
                    queued, outbox_error = 0, True
                if not probe_first:
                    reachable = await self.publisher.probe()
                if reachable:
                    result = await self.publisher.flush()
                else:
                    # fail fast: nothing is posted, no retry loop; the batches stay in the outbox
                    result.status = "skipped: oracle unreachable"
                    result.batches_pending = self.publisher.pending()
                if outbox_error and result.status in ("nothing new", "skipped: oracle unreachable"):
                    result.status = "pending: cache outbox not writable"
                result.batches_queued = queued
            report = CycleReport(
                run_id=run_id,
                started_at=started,
                finished_at=datetime.now(UTC),
                mode=self.mode,
                connectors={n: ConnectorStatus(**vars(st)) for n, st in ran.items()},
                signals=signals,
                publish=result,
                oracle_reachable=reachable,
            )
            self.last = report
            log.info(
                "cycle_done",
                run_id=run_id,
                signals=len(signals),
                publish=result.status,
                accepted=result.accepted,
                rejected=result.rejected,
                pending=result.batches_pending,
            )
            return report

    def health(self) -> dict[str, Any]:
        last = self.last
        degraded = (not self.publisher.status.reachable) or last is None or last.all_failed
        return {
            "status": "degraded" if degraded else "ok",
            "mode": self.mode,
            "version": __version__,
            "oracle": self.publisher.oracle_health(),
            "connectors": {name: st.as_health() for name, st in self.statuses.items()},
            "last_cycle": last.last_cycle()
            if last is not None
            else {"at": None, "signals": 0, "accepted": 0, "rejected": 0, "geotagged": 0, "surfaced": 0,
                  "pii_redactions": 0},
            "egress_allowlist": sorted(EGRESS_HOSTS),
        }
