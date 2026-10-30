"""C0 coordination — the ONE shared registration site for stream routers.

Contract C0: exactly two shared files carry registrations
(``traffic_oracle/__main__.py`` and ``convoy_brain/agents/__init__.py``).
This module holds the oracle half so the __main__.py edit stays two lines.

Registration rules:
    * a stream's real router mounts when its module imports (each stream
      owns exactly its own module files);
    * when a module is absent (stream not landed), a STUB mounts in its
      place answering 503 {"detail": "not deployed"} on its documented
      paths — the tree always boots, parallel streams never collide;
    * a stub is skipped entirely when a real route with the same path
      already exists (an owning stream that registers directly never gets
      shadowed).

Routes registered here (contract C1):
    /api/v1/vehicles...          watchlist-anpr (real, this stream)
    /api/v1/enforcement...       watchlist-anpr (real, this stream)
    /api/v1/events/.../interception-plan  watchlist-anpr (real, this stream)
    /api/v1/signals/state        signalling stream (stub until landed)
    /api/v1/units                signalling/canvas stream (stub until landed)
    /api/v1/adaptive/situation_log  adaptive stream (stub until landed)

City fusion spine (contract C-C, WP-02 — real router, 503 stub only if
its package fails to import):
    /api/v1/cameras              camera layer (locations + read counters)
    /api/v1/city/entities        fused snapshot of the city
    /api/v1/city/entity/{kind}/{id}  dossier
    /api/v1/city/feed            city narrative
    /api/v1/events/{id}/audit    the narrative scoped to one event

OSINT surfaces (contract C-T) and decision support (C-U) — guarded mounts
of ``traffic_oracle.osint.router`` and ``traffic_oracle.decision_support.router``
(each module exposes ``router``); until a router lands, or when it cannot
import (the OSINT libraries are not deployed in the image), its GET paths
answer a truthful 503 "not deployed".  A router that is present but BROKEN
(any exception while importing or including it) is logged as a warning with
its type and never propagates: the oracle always boots.  The path templates
are frozen (OS-1): the real routers use the same parameter names.
    /api/v1/osint/events                      surfaced reported situations
    /api/v1/osint/events/{osint_event_id}     one situation's dossier
    /api/v1/osint/gazetteer/resolve           free text → place candidates
    /api/v1/decision-support/{dss_id}         one decision-support proposal

AI-proposal decisions (the forecast, hydro and twin services' proposals: a
named officer decides, the decision is recorded, nothing is actuated) — a
guarded mount of ``traffic_oracle.ai_proposals.router``, the same seam:
    /api/v1/ai-proposals/decisions            the recorded decisions
"""

from __future__ import annotations

import importlib
from typing import Any

import structlog
from fastapi import APIRouter, FastAPI
from fastapi.responses import JSONResponse

logger = structlog.get_logger(__name__)

__all__ = [
    "AI_PROPOSAL_PATHS",
    "CITY_PATHS",
    "DECISION_SUPPORT_PATHS",
    "OSINT_PATHS",
    "register_coordination_routers",
]

_STUB_DETAIL = "not deployed"

#: Every documented city fusion path (C-C): if the city package fails to
#: import, ALL of them answer 503 not-deployed — none silently 404s.
CITY_PATHS: tuple[str, ...] = (
    "/api/v1/cameras",
    "/api/v1/city/entities",
    "/api/v1/city/entity/{kind}/{entity_id}",
    "/api/v1/city/feed",
    "/api/v1/events/{event_id}/audit",
)

#: OSINT GET paths (C-T) stubbed until traffic_oracle.osint.router mounts.
#: Frozen templates: OS-5's router uses these parameter names.
OSINT_PATHS: tuple[str, ...] = (
    "/api/v1/osint/events",
    "/api/v1/osint/events/{osint_event_id}",
    "/api/v1/osint/gazetteer/resolve",
)

#: Decision-support GET path (C-U) stubbed until
#: traffic_oracle.decision_support.router mounts (OS-6, same parameter name).
DECISION_SUPPORT_PATHS: tuple[str, ...] = ("/api/v1/decision-support/{dss_id}",)

#: AI-proposal decision record (GET) stubbed until traffic_oracle.ai_proposals.router mounts.
AI_PROPOSAL_PATHS: tuple[str, ...] = ("/api/v1/ai-proposals/decisions",)

#: The guarded optional mounts: (stream label, module exposing ``router``).
_OPTIONAL_ROUTERS: tuple[tuple[str, str], ...] = (
    ("osint", "traffic_oracle.osint.router"),
    ("decision_support", "traffic_oracle.decision_support.router"),
    ("ai_proposals", "traffic_oracle.ai_proposals.router"),
)


def _stub_router(paths: tuple[str, ...]) -> APIRouter:
    """A router answering 503 not-deployed on every documented path."""
    r = APIRouter()

    for path in paths:

        @r.get(path, include_in_schema=False)
        async def _not_deployed() -> JSONResponse:
            return JSONResponse(status_code=503, content={"detail": _STUB_DETAIL})

    return r


def _route_exists(app: FastAPI, path: str) -> bool:
    """True when ``path`` is already registered.

    FastAPI >= 0.143 wraps included routers in a lazy ``_IncludedRouter``
    carrying the original router — walk both layers so a stream's real
    route is found no matter which representation it sits in.  The
    include-time prefix (``include_router(..., prefix="/api/v1")``) lives
    on the wrapper's ``include_context``, not on the inner routes.
    """
    for route in app.router.routes:
        inner = getattr(route, "original_router", None)
        if inner is not None:
            context = getattr(route, "include_context", None)
            prefix = getattr(context, "prefix", "") or ""
            for sub in inner.routes:
                sub_path = getattr(sub, "path", None)
                if sub_path is not None and path in (sub_path, prefix + sub_path):
                    return True
        if getattr(route, "path", None) == path:
            return True
    return False


def _mount(app: FastAPI, label: str, router: Any) -> None:
    if router is not None:
        app.include_router(router)
        logger.info("coordination.router_mounted", stream=label)


def _mount_guarded(app: FastAPI, label: str, module_name: str) -> None:
    """Mount ``module_name.router`` if it imports; NEVER let it stop the boot.

    * ImportError for the router module, its package or an ``osint_*``
      library: the stream is simply not deployed (info) — its stubs answer.
    * Any other ImportError (a present module importing something missing)
      or ANY other exception while importing or including the router (the
      ``spatial`` pattern in ``__main__``): a fault, logged as a warning with
      its type; the stubs answer and the oracle keeps booting.
    """
    try:
        module = importlib.import_module(module_name)
        _mount(app, label, module.router)
    except ImportError as exc:
        package = module_name.rsplit(".", 1)[0]
        missing = exc.name or ""
        absent = missing in (module_name, package) or missing.startswith("osint_")
        (logger.info if absent else logger.warning)(
            "coordination.not_deployed" if absent else "coordination.import_failed",
            stream=label,
            missing=missing,
            error=str(exc)[:200],
        )
    except Exception as exc:  # noqa: BLE001 — a broken stream router never takes the oracle down
        logger.warning(
            "coordination.router_failed",
            stream=label,
            error_type=type(exc).__name__,
            error=str(exc)[:200],
        )


def register_coordination_routers(app: FastAPI) -> None:
    """Mount every stream router with ImportError tolerance (C0)."""

    # ── watchlist-anpr (this stream) — real routers ─────────────────────
    try:
        from traffic_oracle.vehicles import router as vehicles_router

        _mount(app, "vehicles", vehicles_router)
    except ImportError as exc:  # pragma: no cover - tree-safety stub
        logger.warning("coordination.import_failed", stream="vehicles", error=str(exc))
        app.include_router(_stub_router(("/api/v1/vehicles",)))

    try:
        from traffic_oracle.enforcement import router as enforcement_router

        _mount(app, "enforcement", enforcement_router)
    except ImportError as exc:  # pragma: no cover
        logger.warning(
            "coordination.import_failed", stream="enforcement", error=str(exc)
        )
        app.include_router(
            _stub_router(("/api/v1/enforcement/recommendations",))
        )

    try:
        from traffic_oracle.vehicles.pursuit import router as pursuit_router

        _mount(app, "pursuit", pursuit_router)
    except ImportError as exc:  # pragma: no cover
        logger.warning("coordination.import_failed", stream="pursuit", error=str(exc))

    # ── city fusion spine (C-C) — cameras, entities, dossier, feed, audit ──
    try:
        from traffic_oracle.city.router import router as city_router

        _mount(app, "city", city_router)
    except ImportError as exc:  # pragma: no cover - tree-safety stub
        logger.warning("coordination.import_failed", stream="city", error=str(exc))
        app.include_router(_stub_router(CITY_PATHS))

    # ── OSINT surfaces (C-T) + decision support (C-U) — guarded mounts ──
    for label, module_name in _OPTIONAL_ROUTERS:
        _mount_guarded(app, label, module_name)

    # ── signalling / canvas / adaptive / OSINT streams — 503 stubs until landed
    stubbed: tuple[tuple[str, tuple[str, ...]], ...] = (
        ("signals", ("/api/v1/signals/state",)),
        ("units", ("/api/v1/units",)),
        ("situation_log", ("/api/v1/adaptive/situation_log",)),
        ("osint", OSINT_PATHS),
        ("decision_support", DECISION_SUPPORT_PATHS),
        ("ai_proposals", AI_PROPOSAL_PATHS),
    )
    for label, paths in stubbed:
        if any(_route_exists(app, p) for p in paths):
            logger.info("coordination.stub_skipped", stream=label)
            continue
        app.include_router(_stub_router(paths))
        logger.info("coordination.stub_mounted", stream=label)
