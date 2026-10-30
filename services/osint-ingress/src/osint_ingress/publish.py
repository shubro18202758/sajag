"""Publishing to the oracle (contract C-T): ``POST {oracle}/api/v1/osint/signals`` over loopback.

* **Outbox first.** New signals are written to the cache outbox in batches of at most 200 (with a ``run_id``)
  before anything is posted, then the outbox is flushed oldest first. A batch leaves the outbox only when the
  oracle answers 200; on a 503 "osint pipeline not deployed", a connection failure or a 5xx it stays cached for
  the next cycle.
* **A 422** (the request envelope failed validation) can never succeed when re-sent. When its validation detail
  names the offending signals (FastAPI's ``loc: ["body", "signals", <i>, ...]``), only those are dropped and the
  rest of the batch is re-queued and posted at once, so one bad signal never sinks its 199 batch-mates; otherwise
  (``run_id``, the envelope itself) the whole batch is dropped. Either way the dropped signal ids are remembered
  with the answered ones, so the next cycle does not queue, post and drop them again.
* **Retries** with exponential backoff on connection errors and 5xx (the definitive 503 "osint pipeline not
  deployed" is recorded, not retried).
* **Rejected signals** are logged by ``signal_id`` and ``reason`` only (``forbidden_key``, ``pii_unredacted``,
  ``invalid``), never with their text.
* **Reachability is its own probe** (plan R7): ``GET {oracle}/health`` with a 2 s timeout, at start-up and at
  least every 30 s, independent of posting. It alone fills ``/health``'s ``oracle.reachable``.
* Signals the oracle has already answered for (accepted, duplicate, rejected, or dropped on a 422) are not queued
  again by this process, so an unchanged feed does not make the oracle re-fuse its window every cycle. NATS
  publishing is out of scope (plan R16).
"""

from __future__ import annotations

import asyncio
import json
import random
import re
from collections import Counter, OrderedDict
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import httpx
import structlog

from osint_common.types import RawOsintSignal
from osint_ingress.cache import Cache

__all__ = ["INGEST_PATH", "OracleStatus", "PublishResult", "Publisher"]

INGEST_PATH = "/api/v1/osint/signals"
NOT_DEPLOYED = "osint pipeline not deployed"
_SENT_MEMORY = 50_000

log = structlog.get_logger("osint_ingress.publish")


@dataclass
class OracleStatus:
    host: str
    reachable: bool = False
    last_probe_at: datetime | None = None
    last_post_at: datetime | None = None
    last_post_status: str | None = None


@dataclass
class PublishResult:
    status: str = "nothing new"
    batches_queued: int = 0
    batches_sent: int = 0
    batches_pending: int = 0
    #: batches the oracle refused as malformed (422) and that were dropped whole or in part
    batches_dropped: int = 0
    #: signals dropped on a 422 (only the ones its detail names, when it names any)
    signals_dropped: int = 0
    accepted: int = 0
    duplicates: int = 0
    rejected: int = 0
    rejected_reasons: Counter[str] = field(default_factory=Counter)
    geotagged: int = 0
    surfaced: int | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "batches": {
                "queued": self.batches_queued,
                "sent": self.batches_sent,
                "pending": self.batches_pending,
                "dropped": self.batches_dropped,
            },
            "signals_dropped": self.signals_dropped,
            "accepted": self.accepted,
            "duplicates": self.duplicates,
            "rejected": self.rejected,
            "rejected_reasons": dict(self.rejected_reasons),
            "geotagged": self.geotagged,
            "surfaced": self.surfaced,
        }


def _iso(dt: datetime | None) -> str | None:
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z") if dt else None


class Publisher:
    """Outbox + poster for one oracle (``client`` is the loopback oracle client)."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        cache: Cache,
        *,
        oracle_host: str,
        batch_size: int = 200,
        retries: int = 3,
        backoff_sec: float = 0.5,
        probe_timeout_sec: float = 2.0,
    ) -> None:
        self.client = client
        self.cache = cache
        self.batch_size = max(1, min(200, batch_size))
        self.retries = max(1, retries)
        self.backoff_sec = max(0.0, backoff_sec)
        self.probe_timeout_sec = probe_timeout_sec
        self.status = OracleStatus(host=oracle_host)
        self._sent: OrderedDict[str, None] = OrderedDict()
        self._queued: set[str] | None = None

    # ── reachability ──────────────────────────────────────────────────────────────────────────────────────────

    async def probe(self) -> bool:
        """``GET {oracle}/health`` (2 s): reachable when it answers below 500. Never raises."""
        try:
            resp = await self.client.get("/health", timeout=self.probe_timeout_sec)
            reachable = resp.status_code < 500
        except (httpx.HTTPError, OSError):
            reachable = False
        self.status.reachable = reachable
        self.status.last_probe_at = datetime.now(UTC)
        return reachable

    # ── outbox ────────────────────────────────────────────────────────────────────────────────────────────────

    def _load_queued(self) -> set[str]:
        if self._queued is None:
            ids: set[str] = set()
            for path in self.cache.outbox_pending():
                try:
                    doc = json.loads(path.read_bytes())
                    ids.update(str(s.get("signal_id")) for s in doc.get("signals", []) if isinstance(s, dict))
                except (OSError, ValueError, AttributeError):
                    continue
            self._queued = ids
        return self._queued

    def _remember_sent(self, ids: Sequence[str]) -> None:
        for sid in ids:
            self._sent[sid] = None
            self._sent.move_to_end(sid)
        while len(self._sent) > _SENT_MEMORY:
            self._sent.popitem(last=False)

    def enqueue(self, signals: Sequence[RawOsintSignal], run_id: str) -> int:
        """Write the signals not yet sent or queued to the outbox, ≤ ``batch_size`` per batch. Returns batches."""
        queued = self._load_queued()
        fresh: list[RawOsintSignal] = []
        seen: set[str] = set()
        for s in signals:
            if s.signal_id in self._sent or s.signal_id in queued or s.signal_id in seen:
                continue
            seen.add(s.signal_id)
            fresh.append(s)
        n = 0
        for start in range(0, len(fresh), self.batch_size):
            chunk = fresh[start : start + self.batch_size]
            payload = {"signals": [s.model_dump(mode="json") for s in chunk], "run_id": run_id}
            self.cache.outbox_put(f"{run_id}-{n:03d}", json.dumps(payload, ensure_ascii=False).encode("utf-8"))
            queued.update(s.signal_id for s in chunk)
            n += 1
        return n

    def pending(self) -> int:
        return len(self.cache.outbox_pending())

    # ── posting ───────────────────────────────────────────────────────────────────────────────────────────────

    async def _post(self, payload: bytes) -> httpx.Response:
        last_exc: Exception | None = None
        for attempt in range(self.retries):
            if attempt:
                await asyncio.sleep(self.backoff_sec * (2 ** (attempt - 1)) * (1 + random.random() * 0.25))
            try:
                resp = await self.client.post(
                    INGEST_PATH, content=payload, headers={"content-type": "application/json"}
                )
            except httpx.TransportError as exc:
                last_exc = exc
                continue
            if resp.status_code >= 500 and not (resp.status_code == 503 and _detail(resp) == NOT_DEPLOYED):
                last_exc = None
                if attempt + 1 < self.retries:
                    continue
            return resp
        assert last_exc is not None
        raise last_exc

    async def flush(self, *, max_batches: int = 50) -> PublishResult:
        """Send pending outbox batches, oldest first, until one cannot be delivered (at most ``max_batches``
        posts; the remainder of a 422-refused batch is re-queued first in line and counts as one more)."""
        result = PublishResult(status="nothing new")
        queued = self._load_queued()
        for _ in range(max_batches):
            pending = self.cache.outbox_pending()
            if not pending:
                break
            path = pending[0]
            try:
                payload = path.read_bytes()
                doc = json.loads(payload)
                signals = doc.get("signals", [])
                ids = [str(s.get("signal_id")) for s in signals]
            except (OSError, ValueError, AttributeError):
                path.unlink(missing_ok=True)
                continue
            try:
                resp = await self._post(payload)
            except httpx.TransportError as exc:
                self.status.last_post_status = f"connection failed ({type(exc).__name__})"
                result.status = "pending: oracle connection failed"
                break
            self.status.last_post_at = datetime.now(UTC)
            code = resp.status_code
            if code == 200:
                body = _json(resp)
                rejected = body.get("rejected") or []
                for r in rejected if isinstance(rejected, list) else []:
                    if isinstance(r, dict):
                        reason = str(r.get("reason", "invalid"))[:32]
                        result.rejected_reasons[reason] += 1
                        log.warning("signal_rejected", signal_id=str(r.get("signal_id", ""))[:40], reason=reason)
                result.accepted += _int(body.get("accepted"))
                result.duplicates += _int(body.get("duplicates"))
                result.rejected += len(rejected) if isinstance(rejected, list) else 0
                result.geotagged += _int(body.get("geotagged"))
                counts = body.get("counts") if isinstance(body.get("counts"), dict) else {}
                if "surfaced" in counts:
                    result.surfaced = _int(counts.get("surfaced"))
                else:
                    resolved = body.get("resolved") if isinstance(body.get("resolved"), list) else []
                    result.surfaced = sum(1 for r in resolved if isinstance(r, dict) and r.get("is_event"))
                result.batches_sent += 1
                self.status.last_post_status = "200 ok"
                path.unlink(missing_ok=True)
                queued.difference_update(ids)
                self._remember_sent(ids)
                result.status = "ok"
                continue
            if code == 422:
                bad = _refused_positions(resp, len(ids))
                keep = [s for i, s in enumerate(signals) if i not in bad] if bad else []
                dropped = [ids[i] for i in sorted(bad)] if bad else ids
                if keep:  # the rest of the batch goes straight back into the outbox, first in line
                    rest = {"signals": keep, "run_id": doc.get("run_id")}
                    try:
                        self.cache.outbox_put(_requeue_name(path.stem), json.dumps(rest, ensure_ascii=False).encode())
                    except OSError as exc:  # an unwritable outbox: keep the whole batch rather than lose good signals
                        log.error("outbox_unwritable", error=type(exc).__name__)
                        result.status = "pending: cache outbox not writable"
                        break
                path.unlink(missing_ok=True)
                queued.difference_update(dropped)
                self._remember_sent(dropped)  # answered for: never queued, posted and dropped again
                result.batches_dropped += 1
                result.signals_dropped += len(dropped)
                self.status.last_post_status = (
                    f"422 malformed signals ({len(dropped)} dropped, {len(keep)} re-queued)"
                    if keep
                    else "422 malformed batch (dropped)"
                )
                log.error("batch_dropped", reason="422 malformed", signals=len(dropped), requeued=len(keep))
                continue
            detail = _detail(resp)
            self.status.last_post_status = f"{code} {detail}".strip()[:120]
            result.status = f"pending: {detail or f'HTTP {code}'}"[:120]
            log.warning("batch_kept", status=code, detail=detail[:80], signals=len(ids))
            break
        result.batches_pending = self.pending()
        if result.batches_dropped and result.status == "nothing new":
            result.status = "dropped: malformed batch (422)"
        return result

    def oracle_health(self) -> dict[str, Any]:
        return {
            "host": self.status.host,
            "reachable": self.status.reachable,
            "last_post_at": _iso(self.status.last_post_at),
            "last_post_status": self.status.last_post_status,
        }


def _json(resp: httpx.Response) -> dict[str, Any]:
    try:
        body = resp.json()
    except ValueError:
        return {}
    return body if isinstance(body, dict) else {}


def _detail(resp: httpx.Response) -> str:
    d = _json(resp).get("detail")
    return d[:120] if isinstance(d, str) else ""


def _refused_positions(resp: httpx.Response, n: int) -> set[int]:
    """The batch positions a 422's validation detail names (FastAPI: ``loc = ["body", "signals", <i>, ...]``).
    Empty when any error is not about one signal (``run_id``, the envelope), so the whole batch is refused."""
    detail = _json(resp).get("detail")
    if not isinstance(detail, list) or not detail:
        return set()
    out: set[int] = set()
    for err in detail:
        loc = err.get("loc") if isinstance(err, dict) else None
        if not (isinstance(loc, list) and len(loc) >= 3 and loc[0] == "body" and loc[1] == "signals"):
            return set()
        i = loc[2]
        if isinstance(i, bool) or not isinstance(i, int) or not 0 <= i < n:
            return set()
        out.add(i)
    return out


_REQUEUED = re.compile(r"^(?P<base>.*?)(?:-r(?P<n>\d{1,4}))?$")


def _requeue_name(stem: str) -> str:
    """``<batch>-r<k>``: the k-th remainder of a batch, which sorts right before the batch after it."""
    m = _REQUEUED.match(stem)
    assert m is not None
    return f"{m.group('base')[:100]}-r{int(m.group('n') or 0) + 1}"


def _int(v: object) -> int:
    try:
        return int(v)  # type: ignore[call-overload]
    except (TypeError, ValueError):
        return 0
