"""Read-only adapter for the traffic-oracle (GET only — this service never writes to the oracle).

Where the platform keeps traffic state:

* ``traffic.observations`` — raw per-segment rows (speed_kmh, congestion_idx, source, data_quality);
  served for the last 24 h by ``GET /api/v1/traffic/history/{segment_id}`` (≤ 500 rows, newest first);
* ``traffic.hourly_aggregates`` (real) and ``traffic.hourly_aggregates_synthetic`` (the simulated feed's
  rollup) — served by ``GET /api/v1/traffic/historical?segment_id=&hours=`` as ``aggregates`` and
  ``synthetic_aggregates`` (never merged by the oracle, never merged here without a label);
* ``corridor.road_segments`` — ``GET /api/traffic/segments?min_lon=…`` (the deck's traffic-flow layer
  geometry);
* active corridor events with their route spines — ``GET /api/v1/events/active``.

A 15-min history is assembled per segment: hourly aggregates (real first; the synthetic rollup only when
there is no real row, and then the whole series is labelled SIMULATED) interpolated to 15 min, with the
raw rows of the last day resampled to 15-min means laid over them. V/C is not stored by the oracle; it
is derived from speed with the oracle's own BPR curve (``bpr.py``, MODELLED).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import numpy as np
import structlog

from forecast.bpr import vc_from_speed
from forecast.synthetic import History, align

logger = structlog.get_logger(__name__)

__all__ = ["OracleClient", "OracleHistory", "assemble_history", "events_covariate"]


@dataclass
class OracleHistory:
    history: History | None
    steps: int
    provenance: str  # real | synthetic | mixed | none
    reason: str | None = None


class OracleClient:
    def __init__(self, base_url: str, timeout: float = 8.0, transport: httpx.AsyncBaseTransport | None = None):
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=timeout, transport=transport,
                                         headers={"user-agent": "sajag-forecast/0.1"})

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _get(self, path: str, **params: Any) -> Any:
        r = await self._client.get(path, params=params or None)
        r.raise_for_status()
        return r.json()

    async def health(self) -> dict:
        try:
            body = await self._get("/health")
            return {"reachable": True, "status": body.get("status") if isinstance(body, dict) else None}
        except Exception as exc:  # noqa: BLE001
            return {"reachable": False, "error": type(exc).__name__}

    async def segments(self, bbox: tuple[float, float, float, float]) -> list[dict]:
        min_lon, min_lat, max_lon, max_lat = bbox
        body = await self._get("/api/traffic/segments", min_lon=min_lon, min_lat=min_lat,
                               max_lon=max_lon, max_lat=max_lat)
        return body if isinstance(body, list) else []

    async def hourly(self, sid: int, hours: int) -> dict:
        return await self._get("/api/v1/traffic/historical", segment_id=sid, hours=min(hours, 720))

    async def raw(self, sid: int) -> list[dict]:
        body = await self._get(f"/api/v1/traffic/history/{sid}")
        return body.get("observations", []) if isinstance(body, dict) else []

    async def active_events(self) -> list[dict]:
        body = await self._get("/api/v1/events/active")
        return body.get("events", []) if isinstance(body, dict) else []


def _parse_ts(s: str) -> datetime:
    t = datetime.fromisoformat(s.replace("Z", "+00:00"))
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def assemble_history(sid: int, hourly: dict, raw: list[dict], *, end: datetime, days: int,
                     free_flow_kmh: float, step_min: int = 15, min_steps: int = 192) -> OracleHistory:
    """Turn the oracle's answers into a 15-min ``History`` (or say why not)."""
    end = align(end, step_min)
    start = end - timedelta(days=days)
    n = int((end - start).total_seconds() // (60 * step_min)) + 1
    grid = np.array([(start + timedelta(minutes=step_min * i)).timestamp() for i in range(n)])
    speed = np.full(n, np.nan)

    real = hourly.get("aggregates") or []
    synth = hourly.get("synthetic_aggregates") or []
    rows, provenance = (real, "real") if real else (synth, "synthetic") if synth else ([], "none")
    if rows:
        ts = np.array([_parse_ts(r["hour_utc"]).timestamp() + 1800 for r in rows])  # bucket centre
        sp = np.array([float(r.get("avg_speed_kmh") or r.get("p50_speed_kmh") or np.nan) for r in rows])
        ok = np.isfinite(sp)
        if ok.sum() >= 2:
            inside = (grid >= ts[ok].min()) & (grid <= ts[ok].max())
            speed[inside] = np.interp(grid[inside], ts[ok], sp[ok])

    raw_quality = set()
    if raw:
        rt = np.array([_parse_ts(o["timestamp_utc"]).timestamp() for o in raw])
        rs = np.array([float(o["speed_kmh"]) for o in raw])
        raw_quality = {str(o.get("data_quality") or "unknown") for o in raw}
        bins = np.floor((rt - grid[0]) / (60 * step_min)).astype(int)
        for b in np.unique(bins):
            if 0 <= b < n:
                speed[b] = float(np.mean(rs[bins == b]))
        if provenance == "none":
            provenance = "synthetic" if raw_quality <= {"synthetic"} else "real"
        elif raw_quality - {"real"} and provenance == "real":
            provenance = "mixed"

    valid = np.isfinite(speed)
    if valid.sum() == 0:
        return OracleHistory(None, 0, provenance, "oracle has no history for this segment")
    first = int(np.argmax(valid))
    speed = speed[first:]
    valid = valid[first:]
    if (~valid).any():  # interior gaps: linear interpolation
        idx = np.arange(speed.size)
        speed[~valid] = np.interp(idx[~valid], idx[valid], speed[valid])
    steps = int(speed.size)
    if steps < min_steps:
        return OracleHistory(None, steps, provenance,
                             f"oracle history too short ({steps} × {step_min} min < {min_steps})")
    vc = vc_from_speed(speed, free_flow_kmh)
    label = "LIVE" if provenance == "real" else "SIMULATED"
    zeros = np.zeros(steps)
    h = History(sid, start + timedelta(minutes=step_min * first), step_min, vc, speed, zeros.copy(),
                zeros.copy(), zeros.copy(), free_flow_kmh, label,
                f"traffic-oracle ({provenance}; hourly aggregates + raw rows)",
                ["V/C derived from speed via the oracle's BPR curve (MODELLED)"])
    return OracleHistory(h, steps, provenance)


def events_covariate(events: list[dict], sid: int, start: datetime, n: int, step_min: int = 15) -> np.ndarray:
    """1.0 on steps where an active corridor event's spine includes the segment."""
    out = np.zeros(n)
    for ev in events:
        segs = {s for r in ev.get("routes") or [] for s in r.get("segment_ids") or []}
        if sid not in segs:
            continue
        try:
            t0 = _parse_ts(ev.get("actual_start") or ev.get("planned_start"))
            t1 = _parse_ts(ev.get("actual_end") or ev.get("planned_end")) if (
                ev.get("actual_end") or ev.get("planned_end")) else t0 + timedelta(hours=3)
        except Exception:  # noqa: BLE001
            continue
        for i in range(n):
            t = start + timedelta(minutes=step_min * i)
            if t0 <= t <= t1:
                out[i] = 1.0
    return out
