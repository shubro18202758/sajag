"""Covariates for forecasts made on platform (oracle) history.

* rain intensity — the hydro service's Open-Meteo nowcast (``GET /hydro/rain``; LIVE), city mean, mapped
  onto the 15-min forecast grid; when the hydro service does not answer the covariate is 0 and says so;
* outfall gate closure — the Apollo Bunder (Mumbai harbour) tide model (``tide.py``, MODELLED): the sea
  outfalls' flap gates shut at high tide; computed here;
* events — active corridor events from the oracle whose route spine includes the segment.

For forecasts made on the SIMULATED history the covariates come from the same simulated world
(``synthetic.py``), so the past and the future stay consistent; their label says SIMULATED.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import httpx
import numpy as np

from forecast.tide import TideModel

__all__ = ["HydroClient", "gate_series"]

_TIDE = TideModel()  # the city's outfall tide station (tide.py default)


def gate_series(start: datetime, n: int, step_min: int = 15) -> np.ndarray:
    return np.array([1.0 if _TIDE.gate_closed(start + timedelta(minutes=step_min * i)) else 0.0
                     for i in range(n)])


class HydroClient:
    def __init__(self, base_url: str, timeout: float = 6.0, transport: httpx.AsyncBaseTransport | None = None):
        self._client = httpx.AsyncClient(base_url=base_url.rstrip("/"), timeout=timeout, transport=transport,
                                         headers={"user-agent": "sajag-forecast/0.1"})

    async def aclose(self) -> None:
        await self._client.aclose()

    async def rain(self, start: datetime, n: int, step_min: int = 15) -> tuple[np.ndarray, dict]:
        """City-mean rain (mm/h) on the grid start + i·step, i < n, and a provenance note."""
        try:
            r = await self._client.get("/hydro/rain")
            r.raise_for_status()
            body = r.json()
            series = (body.get("city") or {}).get("series") or []
            if not series:
                raise ValueError("no city series")
            ts = np.array([datetime.fromisoformat(p["t"].replace("Z", "+00:00")).timestamp() for p in series])
            mm = np.array([float(p.get("mm_h") or 0.0) for p in series])
            grid = np.array([(start + timedelta(minutes=step_min * i)).timestamp() for i in range(n)])
            vals = np.interp(grid, ts, mm, left=0.0, right=0.0)
            return vals, {"label": body.get("label", "LIVE"), "source": "hydro service /hydro/rain (Open-Meteo)"}
        except Exception as exc:  # noqa: BLE001
            return np.zeros(n), {"label": "UNAVAILABLE", "source": f"hydro service did not answer "
                                 f"({type(exc).__name__}); rain covariate set to 0"}
