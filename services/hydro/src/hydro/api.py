"""Hydro HTTP surface (production :8197, loopback).

    GET  /health                       service, rain feed state, data files
    GET  /hydro/nowcast                per segment: risk class 0–3, expected depth band, lead time and the
                                       drivers (rain LIVE · tide MODELLED · susceptibility MODELLED · pumps
                                       EMULATED), plus PROPOSALS (reroute + BEST diversion, ambulance window,
                                       pump request to BMC 1916, English/Marathi/Hindi advisory draft,
                                       live-wire hazard) — never actions
    GET  /hydro/tide?hours=1..72       Apollo Bunder tide model (MODELLED, approximate): series, extremes,
                                       outfall restriction, gates
    GET  /hydro/rain                   the Open-Meteo nowcast at the fixed point set (cached, rate-limited)
    GET  /hydro/pumps                  BMC pumping-station state (EMULATED adapter)
    POST /hydro/replay?event=2025-08-19   replay of the 18–19 Aug 2025 Mumbai storm (Open-Meteo archive run
                                       and an IMD/BMC gauge-anchored run) against the places the news reported
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any, AsyncIterator

import structlog
import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from hydro import __version__
from hydro import ffews as ffews_mod
from hydro.config import Settings, get_settings
from hydro.network import load_network
from hydro.nowcast import Hydro, rain_view
from hydro.rain import RainClient
from hydro.replay import DEFAULT_EVENT, EVENTS, replay

logger = structlog.get_logger(__name__)

__all__ = ["create_app", "main"]


def build(s: Settings, transport=None) -> Hydro:
    rain = RainClient(s.open_meteo_forecast_url, s.open_meteo_archive_url, timeout=s.http_timeout_sec,
                      cache_sec=s.rain_cache_sec, min_interval_sec=s.min_call_interval_sec,
                      max_calls_per_day=s.max_calls_per_day, offline=s.offline, transport=transport)
    return Hydro(load_network(s.resolved_city_dir()), rain, step_min=s.step_min, horizon_min=s.horizon_min)


def create_app(settings: Settings | None = None, hydro: Hydro | None = None) -> FastAPI:
    s = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.hydro = hydro or build(s)
        app.state.replays = {}
        try:
            yield
        finally:
            await app.state.hydro.rain.aclose()

    app = FastAPI(title="Sajag hydro", version=__version__, lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=list(s.deck_origins), allow_methods=["GET", "POST"],
                       allow_headers=["*"])

    def h() -> Hydro:
        return app.state.hydro

    @app.get("/health")
    async def health() -> dict[str, Any]:
        hy = h()
        return {
            "status": "ok", "service": "hydro", "version": __version__,
            "labels": {"rain": "LIVE (Open-Meteo)", "tide": "MODELLED (approximate)",
                       "susceptibility": "MODELLED", "pumps": "EMULATED (BMC pumping-station stand-in)"},
            "rain_feed": hy.rain.status(),
            "network": {"source": hy.net.source, "segments": len(hy.net.segments)},
            "susceptibility": {"built_at": hy.sus_meta["built_at"], "segments": len(hy.sus)},
            "tide_now": hy.tide_view(hours=1)["now"],
        }

    @app.get("/hydro/nowcast")
    async def nowcast(force: bool = Query(default=False)) -> dict:
        return await h().nowcast(force=force)

    @app.get("/hydro/tide")
    async def tide(hours: float = Query(default=24.0, ge=1.0, le=72.0)) -> dict:
        return h().tide_view(hours=hours)

    @app.get("/hydro/rain")
    async def rain(force: bool = Query(default=False)) -> dict:
        hy = h()
        nc = await hy.rain.nowcast(force=force)
        return rain_view(nc, hy.rain.status())

    @app.get("/hydro/pumps")
    async def pumps() -> dict:
        hy = h()
        states = hy.ffews.states(datetime.now(UTC))
        return {"label": "EMULATED", "note": "BMC pumping-station stand-in: station names are real, their pump "
                "counts and state are invented until the BMC's telemetry (IFLOWS-Mumbai) is connected",
                "published": {"major_stations": 6, "major_pumps_total": ffews_mod.MAJOR_PUMPS_TOTAL,
                              "major_capacity_lps": ffews_mod.MAJOR_CAPACITY_LPS,
                              "source": ffews_mod.SOURCE_MAJOR},
                "stations": [x.as_dict() for x in states]}

    @app.post("/hydro/replay")
    async def do_replay(event: str = Query(default=DEFAULT_EVENT)) -> dict:
        if event not in EVENTS:
            raise HTTPException(status_code=404, detail=f"unknown event; known: {sorted(EVENTS)}")
        cache = app.state.replays
        if event not in cache:
            cache[event] = await replay(h(), event)
        return cache[event]

    return app


def main() -> None:
    s = get_settings()
    structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(20))
    logger.info("hydro.starting", host=s.host, port=s.port, offline=s.offline)
    uvicorn.run(create_app(s), host=s.host, port=s.port, log_level="info")
