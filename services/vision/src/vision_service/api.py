"""HTTP surface of the vision service.

    GET  /health
    POST /vision/road-state   image (jpeg/png) [+ ?question=…] → road state, UNVERIFIED-CAMERA
    POST /admin/release       loopback machine callers only: stop the idle model (unused for
                              ?idle_s=, default 20 s, and not serving a request)

A start that would break the memory floor first makes room: the other
on-demand services release their idle models (``memroom.py``). Released
models reload on their next use; /health shows the last attempt.

The image is the raw request body with its Content-Type (``image/jpeg`` or
``image/png``), or multipart field ``image`` when python-multipart is
installed. It is processed in memory and dropped when the request ends.

A camera road state is a *claim awaiting an officer's confirmation*, never an
action, and it never describes people (see ``ethics.py``).
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from .config import Settings, get_settings
from .ethics import screen_query, scrub
from .images import ImageError, prepare
from .memroom import RELOAD_NOTE, loopback_refusal, summarize
from .model import DEPTH_BANDS, STATES, LlamaVisionModel, ModelUnavailable, RoadStateModel

__all__ = ["create_app", "normalize", "main", "VERIFICATION_STATE"]

log = logging.getLogger("vision.api")

VERIFICATION_STATE = "UNVERIFIED-CAMERA"
_IMAGE_TYPES = ("image/jpeg", "image/jpg", "image/png", "application/octet-stream")
_VEHICLE_KEYS = ("cars", "buses", "two_wheelers", "autos")


def _int(v: Any, hi: int = 500) -> int:
    try:
        return max(0, min(hi, int(round(float(v)))))
    except (TypeError, ValueError):
        return 0


def normalize(raw: dict[str, Any], model_name: str) -> dict[str, Any]:
    """Model JSON → the public contract; every free-text field is scrubbed."""
    state = raw.get("state") if raw.get("state") in STATES else "unknown"
    try:
        conf = float(raw.get("confidence", 0.0))
    except (TypeError, ValueError):
        conf = 0.0
    conf = max(0.0, min(1.0, conf if conf <= 1.0 else conf / 100.0))
    if state == "unknown":
        conf = min(conf, 0.5)
    ve_raw = raw.get("vehicles_estimate") if isinstance(raw.get("vehicles_estimate"), dict) else {}
    vehicles = {k: _int(ve_raw.get(k)) for k in _VEHICLE_KEYS}
    band = raw.get("water_depth_band") if raw.get("water_depth_band") in DEPTH_BANDS else "unknown"
    if state == "waterlogged" and band == "none":
        band = "unknown"
    rationale, removed = scrub(str(raw.get("rationale", "")), state)
    out: dict[str, Any] = {
        "state": state,
        "confidence": round(conf, 2),
        "vehicles_estimate": vehicles,
        "rationale": rationale,
        "model": model_name,
        "verification_state": VERIFICATION_STATE,
        "requires_confirmation": True,
        "label": "Camera still · AI reading · awaiting an officer's confirmation",
        "filtered": removed > 0,
    }
    if state == "waterlogged" or band not in ("none", "unknown"):
        out["water_depth_band"] = band
    if removed:
        out["filter"] = {"clauses_removed": removed, "policy": "vehicles-and-roads-only"}
    return out


async def _read_image(request: Request, s: Settings) -> tuple[bytes, str | None]:
    ctype = (request.headers.get("content-type") or "").lower()
    clen = request.headers.get("content-length")
    if clen and clen.isdigit() and int(clen) > s.max_image_bytes:
        raise HTTPException(413, f"image larger than {s.max_image_bytes} bytes")
    question = None
    if ctype.startswith("multipart/form-data"):
        try:
            form = await request.form()
        except AssertionError as exc:
            raise HTTPException(415, "multipart needs python-multipart; send the raw image body") from exc
        up = form.get("image") or form.get("file")
        if up is None or not hasattr(up, "read"):
            raise HTTPException(422, "multipart field 'image' is missing")
        data = await up.read()
        q = form.get("question")
        question = q if isinstance(q, str) else None
    elif ctype.startswith(_IMAGE_TYPES) or not ctype:
        data = await request.body()
    else:
        raise HTTPException(415, f"unsupported content type {ctype!r} (send image/jpeg or image/png)")
    if len(data) > s.max_image_bytes:
        raise HTTPException(413, f"image larger than {s.max_image_bytes} bytes")
    return data, question


def create_app(settings: Settings | None = None, *, model: RoadStateModel | None = None) -> FastAPI:
    s = settings or get_settings()
    mdl: RoadStateModel = model or LlamaVisionModel(s)

    @contextlib.asynccontextmanager
    async def lifespan(_app: FastAPI):
        async def reaper() -> None:
            while True:
                await asyncio.sleep(30)
                with contextlib.suppress(Exception):
                    await mdl.maybe_stop_idle()

        task = asyncio.create_task(reaper())
        try:
            yield
        finally:
            task.cancel()
            with contextlib.suppress(Exception):
                await mdl.aclose()

    app = FastAPI(title="Sajag vision", version="0.1.0", lifespan=lifespan)
    origins = [o.strip().rstrip("/") for o in s.deck_origins.split(",")
               if o.strip().startswith(("http://", "https://")) and "*" not in o]
    if origins:
        app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["GET", "POST"],
                           allow_headers=["content-type"])
    app.state.model = mdl
    last_release: dict[str, Any] = {}

    @app.exception_handler(ModelUnavailable)
    async def _unavailable(_req: Request, exc: ModelUnavailable) -> JSONResponse:
        return JSONResponse({"detail": str(exc), "retry": "later"}, status_code=503)

    @app.get("/health")
    async def health() -> dict[str, Any]:
        model_status = mdl.status()
        readiness = model_status.get("readiness") if isinstance(model_status, dict) else None
        ready = readiness.get("ready") if isinstance(readiness, dict) else None
        return {
            # the process answers either way; "degraded" when a road-state request would
            # get a 503 right now (it said "ok" while the model could not start)
            "status": "degraded" if ready is False else "ok",
            "ready": ready is not False,
            "degraded_reason": readiness.get("reason") if ready is False else None,
            "service": "vision",
            "model": model_status,
            "states": list(STATES),
            "policy": "roads and vehicles only; no person description; no plate reading",
            "make_room": {
                **(mdl.make_room_status() if hasattr(mdl, "make_room_status")
                   else {"enabled": False, "note": RELOAD_NOTE}),
                "last_release": last_release or None,
            },
        }

    @app.post("/admin/release")
    async def admin_release(request: Request,
                            idle_s: float | None = Query(None, ge=0, le=3600)) -> dict[str, Any]:
        why = loopback_refusal(request.client.host if request.client else None, request.headers)
        if why:
            raise HTTPException(403, why)
        min_idle = s.release_idle_s if idle_s is None else idle_s
        release = getattr(mdl, "release_idle", None)
        out = await release(min_idle) if release is not None else summarize("vision", [])
        last_release.clear()
        last_release.update(at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), idle_s=min_idle,
                            released=out["released"], freed_gib_estimate=out["freed_gib_estimate"],
                            kept=out["kept"])
        log.info("release asked: released %s (~%.1f GiB); kept %s", out["released"] or "nothing",
                 out["freed_gib_estimate"], out["kept"] or "nothing")
        return out

    @app.post("/vision/road-state")
    async def road_state(request: Request,
                         question: str | None = Query(None, max_length=300)) -> JSONResponse:
        t0 = time.perf_counter()
        data, form_q = await _read_image(request, s)
        q = question or form_q
        screen = screen_query(q)
        if not screen.allowed:
            del data
            return JSONResponse(
                {"refused": True, "reason": screen.reason, "policy": screen.policy,
                 "verification_state": VERIFICATION_STATE},
                status_code=403,
            )
        try:
            prep = await run_in_threadpool(prepare, data, s.max_side)
        except ImageError as exc:
            raise HTTPException(422, str(exc)) from exc
        finally:
            del data
        raw = await mdl.classify(prep.jpeg, q)
        out = normalize(raw, mdl.name)
        out["image"] = {"width": prep.width, "height": prep.height, "format": prep.source_format,
                        "resized": prep.resized, "metadata": "stripped" if prep.width else "unchanged"}
        timings = raw.get("_timings") or {}
        out["latency_s"] = round(time.perf_counter() - t0, 3)
        if timings:
            out["model_timings_ms"] = {k: round(float(timings[k]), 1)
                                       for k in ("prompt_ms", "predicted_ms") if k in timings}
        return JSONResponse(out)

    return app


def main() -> None:
    import uvicorn

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    s = get_settings()
    uvicorn.run(create_app(s), host=s.host, port=s.port, log_level="info")
