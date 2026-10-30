"""HTTP surface of the speech service.

    GET  /health
    POST /speech/transcribe   audio (wav/webm/ogg) → {text, language, confidence, model}
    POST /speech/report       audio or {"text": …}  → structured field report (UNVERIFIED-FIELD)
    POST /speech/speak        {"text", "lang": mr|en|hi} → audio/wav (cached by hash)
    POST /admin/release       loopback machine callers only: unload this service's idle models
                              (unused for ?idle_s=, default 20 s, and not serving a request)

A load that would break the memory floor first makes room (``memroom.py``):
this service's own idle models, then the other on-demand services' idle ones,
are released and the floor is checked again. Released models reload on their
next use; /health shows the last attempt.

Audio is sent as the raw request body with its Content-Type (what a browser
``fetch(url, {body: blob})`` does), or as multipart form field ``audio`` when
python-multipart is installed. It is decoded in memory and dropped when the
request ends: no speaker identification, no voice storage.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from .asr import (
    SUPPORTED_LANGS,
    attach_place_prompts,
    ASRBackend,
    FallbackASR,
    IndicConformerASR,
    RoutedASR,
    WhisperASR,
    lazy_models_of,
)
from .audio import AudioError, decode_audio
from .config import Settings, get_settings
from .places import Gazetteer, load_gazetteer
from .report import build_report
from .memroom import RELOAD_NOTE, RoomMaker, loopback_refusal, summarize
from .runtime import ModelUnavailable, mem_available_gib
from .tts import (
    FallbackTTS,
    IndicParlerTTS,
    ParlerWorkerTTS,
    SvaraLlamaTTS,
    SvaraTTS,
    TTSBackend,
    TTSCache,
    speak,
)

__all__ = ["create_app", "make_asr", "make_tts", "make_room_maker", "release_idle_models", "main",
           "ASR_BACKENDS", "TTS_BACKENDS"]

ASR_BACKENDS = ("whisper", "indic_conformer")
TTS_BACKENDS = ("auto", "llama", "transformers", "indic_parler")

log = logging.getLogger("speech.api")

_AUDIO_TYPES = ("audio/", "video/webm", "application/octet-stream", "application/ogg")


class SpeakRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    lang: str = Field(default="mr", pattern="^(mr|en|hi)$")
    voice: str = Field(default="female", pattern="^(female|male)$")


class TextReport(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    lang: str = Field(default="mr", pattern="^(mr|en|hi)$")


def _origins(raw: str) -> list[str]:
    out = []
    for o in (x.strip() for x in raw.split(",")):
        if o.startswith(("http://", "https://")) and "*" not in o:
            out.append(o.rstrip("/"))
    return out


async def _read_audio(request: Request, settings: Settings) -> bytes:
    ctype = (request.headers.get("content-type") or "").lower()
    clen = request.headers.get("content-length")
    if clen and clen.isdigit() and int(clen) > settings.max_audio_bytes:
        raise HTTPException(413, f"audio larger than {settings.max_audio_bytes} bytes")
    if ctype.startswith("multipart/form-data"):
        try:
            form = await request.form()
        except AssertionError as exc:  # python-multipart missing
            raise HTTPException(415, "multipart needs python-multipart; send the raw audio body") from exc
        up = form.get("audio") or form.get("file")
        if up is None or not hasattr(up, "read"):
            raise HTTPException(422, "multipart field 'audio' is missing")
        data = await up.read()
    elif ctype.startswith(_AUDIO_TYPES) or not ctype:
        data = await request.body()
    else:
        raise HTTPException(415, f"unsupported content type {ctype!r} (send wav, webm or ogg audio)")
    if len(data) > settings.max_audio_bytes:
        raise HTTPException(413, f"audio larger than {settings.max_audio_bytes} bytes")
    return data


def _raise_if_oom(exc: BaseException) -> None:
    """A GPU out-of-memory during inference is "try later" (503), not a bug.
    On the GB10's unified memory this can happen with MemAvailable still high
    when most of it is page cache. A ModelUnavailable is already a 503 and keeps its own
    message (a load that ran out of memory says what making room found)."""
    if isinstance(exc, ModelUnavailable):
        return
    if "out of memory" in str(exc).lower() or type(exc).__name__.endswith("OutOfMemoryError"):
        raise ModelUnavailable(f"GPU memory exhausted: {str(exc)[:160]}") from exc


def make_asr(s: Settings) -> RoutedASR:
    """The Indic backend per ``Settings.asr_backend`` for ``asr_indic_langs``
    (Marathi, Hindi); English (and ``auto`` detection) go to the multilingual
    Whisper."""
    if s.asr_backend not in ASR_BACKENDS:
        raise ValueError(f"SPEECH_ASR_BACKEND must be one of {ASR_BACKENDS}, not {s.asr_backend!r}")
    whisper = WhisperASR(s.asr_model, device=s.device, beams=s.asr_beams,
                         min_free_gib=s.min_free_gib, idle_unload_s=s.idle_unload_s)
    marathi: ASRBackend = whisper
    if s.asr_backend == "indic_conformer":
        marathi = FallbackASR(
            IndicConformerASR(s.asr_indic_conformer_model, decoder=s.asr_indic_conformer_decoder,
                              revision=s.asr_indic_conformer_revision or None,
                              min_free_gib=s.min_free_gib, idle_unload_s=s.idle_unload_s),
            whisper,
        )
    allowed = IndicConformerASR.LANGS if s.asr_backend == "indic_conformer" else SUPPORTED_LANGS
    indic = tuple(x.strip() for x in s.asr_indic_langs.split(",") if x.strip() in allowed)
    return RoutedASR(
        marathi,
        WhisperASR(s.asr_multilingual_model, device=s.device, beams=s.asr_beams,
                   min_free_gib=s.min_free_gib, idle_unload_s=s.idle_unload_s),
        indic_langs=indic or ("mr",),
    )


def make_tts(s: Settings) -> TTSBackend:
    """Pick the TTS runtime (see ``Settings.tts_backend``)."""
    backend = s.tts_backend
    if backend not in TTS_BACKENDS:
        raise ValueError(f"SPEECH_TTS_BACKEND must be one of {TTS_BACKENDS}, not {backend!r}")
    if backend == "indic_parler":
        kw = dict(device=s.device, description=s.tts_parler_description, seed=s.tts_seed,
                  revision=s.tts_parler_revision or None,
                  min_free_gib=s.min_free_gib, idle_unload_s=s.idle_unload_s)
        preferred: TTSBackend = (
            ParlerWorkerTTS(s.tts_parler_python, s.tts_parler_model, **kw)
            if s.tts_parler_python else IndicParlerTTS(s.tts_parler_model, **kw))
        return FallbackTTS(preferred, make_tts(s.model_copy(update={"tts_backend": "auto"})))
    if backend == "auto":
        have = s.tts_gguf.is_file() and (s.llama_server_bin.is_file() or not s.tts_llm_manage)
        backend = "llama" if have else "transformers"
    if backend == "llama":
        return SvaraLlamaTTS(s.tts_gguf, s.tts_model, s.tts_codec, server_bin=s.llama_server_bin,
                             port=s.tts_llm_port, manage=s.tts_llm_manage,
                             url=s.tts_llm_url or None, device=s.device,
                             style_tag=s.tts_style_tag, seed=s.tts_seed,
                             min_free_gib=s.min_free_gib, idle_unload_s=s.idle_unload_s)
    return SvaraTTS(s.tts_model, s.tts_codec, device=s.device, style_tag=s.tts_style_tag,
                    seed=s.tts_seed, min_free_gib=s.min_free_gib, idle_unload_s=s.idle_unload_s)


def release_idle_models(backends: tuple[Any, ...], min_idle_s: float, exclude: str | None = None) -> dict[str, Any]:
    """Unload every model behind ``backends`` that is loaded, not serving a request and unused for
    ``min_idle_s`` seconds (``exclude``: the model a load is making room for)."""
    items = []
    for lm in lazy_models_of(*backends):
        if exclude is not None and lm.name == exclude:
            continue
        r = lm.release_if_idle(min_idle_s)
        if r is not None:
            items.append(r)
    return summarize("speech", items)


def make_room_maker(s: Settings, backends: tuple[Any, ...], **kw: Any) -> RoomMaker:
    """Own models not serving a request first (the Parler worker while the ASR loads, and the
    reverse), then forecast (≈2 GiB, quick to reload), then vision (≈8 GiB)."""
    peers = [("forecast", s.peer_forecast_port), ("vision", s.peer_vision_port)]
    return RoomMaker("speech", peers,
                     own_release=lambda model: release_idle_models(backends, s.make_room_idle_s, exclude=model),
                     timeout_s=s.make_room_timeout_s, wait_s=s.make_room_wait_s,
                     release_idle_s=s.make_room_idle_s, **kw)


def create_app(
    settings: Settings | None = None,
    *,
    asr: ASRBackend | None = None,
    tts: TTSBackend | None = None,
    gazetteer: Gazetteer | None = None,
    cache: TTSCache | None = None,
    room: RoomMaker | None = None,
) -> FastAPI:
    s = settings or get_settings()
    asr = asr or make_asr(s)
    tts = tts or make_tts(s)
    gaz = gazetteer or load_gazetteer(s.city_dir, s.gazetteer_file, s.place_threshold)
    if s.asr_place_prompt:
        attach_place_prompts(asr, {lang: gaz.prompt(lang) for lang in SUPPORTED_LANGS})
    tts_cache = cache or TTSCache(s.tts_cache_dir)
    if room is None and s.make_room:
        room = make_room_maker(s, (asr, tts))
    for lm in lazy_models_of(asr, tts):
        lm.room = room
    last_release: dict[str, Any] = {}

    @contextlib.asynccontextmanager
    async def lifespan(_app: FastAPI):
        async def reaper() -> None:
            while True:
                await asyncio.sleep(30)
                for b in (asr, tts):
                    with contextlib.suppress(Exception):
                        await run_in_threadpool(b.maybe_unload_idle)

        task = asyncio.create_task(reaper())
        try:
            yield
        finally:
            task.cancel()
            for b in (asr, tts):
                with contextlib.suppress(Exception):
                    getattr(b, "unload", lambda: None)()

    app = FastAPI(title="Sajag speech", version="0.1.0", lifespan=lifespan)
    origins = _origins(s.deck_origins)
    if origins:
        app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["GET", "POST"],
                           allow_headers=["content-type"])
    app.state.settings = s
    app.state.asr = asr
    app.state.tts = tts
    app.state.gazetteer = gaz
    app.state.room = room

    @app.exception_handler(ModelUnavailable)
    async def _unavailable(_req: Request, exc: ModelUnavailable) -> JSONResponse:
        return JSONResponse({"detail": str(exc), "retry": "later"}, status_code=503)

    @app.get("/health")
    async def health() -> dict[str, Any]:
        sources: dict[str, int] = {}
        for p in gaz.places:
            sources[p.source] = sources.get(p.source, 0) + 1
        mem = mem_available_gib()
        return {
            "status": "ok",
            "service": "speech",
            "asr": asr.status(),
            "tts": tts.status(),
            "places": {"total": len(gaz), **sources},
            "mem_available_gib": round(mem, 1) if mem is not None else None,
            "make_room": {
                **(room.config() if room is not None else {"enabled": False}),
                "release_idle_s": s.release_idle_s,
                "last_event": room.last_event if room is not None else None,
                "last_release": last_release or None,
                "note": RELOAD_NOTE,
            },
            "privacy": "audio is decoded in memory and discarded after the request; "
                       "no speaker identification; no voice storage",
        }

    async def _transcribe(request: Request, lang: str) -> tuple[Any, float]:
        data = await _read_audio(request, s)
        try:
            samples, dur, _fmt = await run_in_threadpool(decode_audio, data, s.max_audio_seconds)
        except AudioError as exc:
            raise HTTPException(422, str(exc)) from exc
        finally:
            del data
        want = None if lang == "auto" else lang
        try:
            tr = await run_in_threadpool(asr.transcribe, samples, want)
        except RuntimeError as exc:
            _raise_if_oom(exc)
            raise
        del samples
        return tr, dur

    @app.post("/speech/transcribe")
    async def transcribe(request: Request,
                         lang: str = Query("mr", pattern="^(mr|en|hi|auto)$")) -> dict[str, Any]:
        t0 = time.perf_counter()
        tr, dur = await _transcribe(request, lang)
        return {
            "text": tr.text,
            "language": tr.language,
            "confidence": tr.confidence,
            "model": tr.model,
            "audio_seconds": round(dur, 2),
            "latency_s": round(time.perf_counter() - t0, 3),
        }

    @app.post("/speech/report")
    async def report(request: Request,
                     lang: str = Query("mr", pattern="^(mr|en|hi|auto)$")) -> dict[str, Any]:
        t0 = time.perf_counter()
        ctype = (request.headers.get("content-type") or "").lower()
        if ctype.startswith("application/json"):
            try:
                body = TextReport.model_validate(await request.json())
            except Exception as exc:
                raise HTTPException(422, f"expected {{'text': …}}: {exc}") from exc
            out = await run_in_threadpool(build_report, body.text.strip(), gaz,
                                          source="field-text", language=body.lang)
        else:
            tr, dur = await _transcribe(request, lang)
            asr_meta = {"model": tr.model, "confidence": tr.confidence,
                        "audio_seconds": round(dur, 2), "asr_seconds": tr.seconds}
            out = await run_in_threadpool(build_report, tr.text, gaz, source="field-voice",
                                          language=tr.language, asr=asr_meta)
        out["latency_s"] = round(time.perf_counter() - t0, 3)
        return out

    @app.post("/admin/release")
    async def admin_release(request: Request,
                            idle_s: float | None = Query(None, ge=0, le=3600)) -> dict[str, Any]:
        why = loopback_refusal(request.client.host if request.client else None, request.headers)
        if why:
            raise HTTPException(403, why)
        min_idle = s.release_idle_s if idle_s is None else idle_s
        out = await run_in_threadpool(release_idle_models, (asr, tts), min_idle)
        last_release.clear()
        last_release.update(at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), idle_s=min_idle,
                            released=out["released"], freed_gib_estimate=out["freed_gib_estimate"],
                            kept=out["kept"])
        log.info("release asked: released %s (~%.1f GiB); kept %s", out["released"] or "nothing",
                 out["freed_gib_estimate"], out["kept"] or "nothing")
        return out

    @app.post("/speech/speak")
    async def speak_ep(req: SpeakRequest) -> Response:
        text = " ".join(req.text.split())
        if len(text) > s.tts_max_chars:
            raise HTTPException(413, f"text longer than {s.tts_max_chars} characters")
        if req.lang not in SUPPORTED_LANGS:
            raise HTTPException(422, "lang must be mr, en or hi")
        t0 = time.perf_counter()
        try:
            sp = await run_in_threadpool(speak, tts, tts_cache, text, req.lang, req.voice,
                                         s.tts_style_tag)
        except RuntimeError as exc:
            if isinstance(exc, ModelUnavailable):
                raise
            _raise_if_oom(exc)
            raise HTTPException(500, str(exc)) from exc
        headers = {
            "X-Speech-Model": sp.model,
            "X-Speech-Voice": f"{req.lang}-{sp.voice}",
            "X-Speech-Cached": "1" if sp.cached else "0",
            "X-Speech-Seconds": f"{sp.seconds:.2f}",
            "X-Speech-Latency": f"{time.perf_counter() - t0:.3f}",
            "X-Speech-Label": "synthetic-voice",
            "Cache-Control": "public, max-age=86400",
        }
        return Response(sp.wav, media_type="audio/wav", headers=headers)

    return app


def open_cuda_context(s: Settings) -> bool:
    """Create this process's CUDA context now, at start, while memory allows.

    On this unified-memory box creating it later failed (``cuDevicePrimaryCtxRetain``: out of memory)
    with 18 GiB available and 16 GiB free, after making room (29 Oct, live), and the first Marathi
    ASR load is where it would be created (the Parler worker has its own process). torch keeps the
    context for the life of the process once a model has run, so this only moves it earlier; the
    weights still load on first use. A failure here is logged and the first load tries again."""
    if not s.cuda_context_at_start or not s.device.startswith("cuda"):
        return False
    try:
        import torch

        if not torch.cuda.is_available():
            return False
        torch.zeros(1, device=s.device)
    except Exception:  # noqa: BLE001 - never stop the service for this
        log.warning("CUDA context not created at start; the first model load will try", exc_info=True)
        return False
    log.info("CUDA context ready on %s", s.device)
    return True


def main() -> None:
    import uvicorn

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    s = get_settings()
    open_cuda_context(s)
    uvicorn.run(create_app(s), host=s.host, port=s.port, log_level="info")
