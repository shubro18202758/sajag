"""Read-only access to the traffic-oracle's live state (GET only).

The twin never writes to the oracle: this module has no POST, PUT or
DELETE, and every call has a short timeout. Anything that fails returns
``None`` and the twin falls back to its SIMULATED profile.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

log = logging.getLogger("sajag_twin.oracle")

__all__ = ["LiveSnapshot", "OracleClient"]


@dataclass
class LiveSnapshot:
    congestion: dict[int, float]  # segment id -> congestion index (0..1)
    label: str  # LIVE | EMULATED
    rows: int


class OracleClient:
    def __init__(self, base_url: str | None, timeout_s: float = 3.0, transport: httpx.BaseTransport | None = None):
        self.base_url = (base_url or "").rstrip("/")
        self.timeout_s = timeout_s
        self._transport = transport

    @property
    def enabled(self) -> bool:
        return bool(self.base_url)

    def _get(self, path: str, params: dict | None = None):
        if not self.enabled:
            return None
        try:
            with httpx.Client(base_url=self.base_url, timeout=self.timeout_s, transport=self._transport) as c:
                r = c.get(path, params=params)
                if r.status_code != 200:
                    return None
                return r.json()
        except (httpx.HTTPError, ValueError) as exc:
            log.info("oracle GET %s failed: %s", path, type(exc).__name__)
            return None

    def snapshot(self, bbox: tuple[float, float, float, float]) -> LiveSnapshot | None:
        """Latest per-segment congestion inside the network's bounding box."""
        min_lon, min_lat, max_lon, max_lat = bbox
        rows = self._get(
            "/api/traffic/snapshot",
            {"min_lon": min_lon, "min_lat": min_lat, "max_lon": max_lon, "max_lat": max_lat},
        )
        if not isinstance(rows, list) or not rows:
            return None
        cong: dict[int, float] = {}
        synthetic = 0
        for r in rows:
            if not isinstance(r, dict):
                continue
            try:
                sid = int(r["segmentId"])
                ci = float(r["congestionIdx"])
            except (KeyError, TypeError, ValueError):
                continue
            if not 0.0 <= ci <= 1.0:
                continue
            cong[sid] = ci
            if str(r.get("dataQuality", "")).lower() not in ("real", "live", "0"):
                synthetic += 1
        if not cong:
            return None
        label = "EMULATED" if synthetic else "LIVE"
        return LiveSnapshot(cong, label, len(cong))

    def health(self) -> bool:
        return self._get("/health") is not None
