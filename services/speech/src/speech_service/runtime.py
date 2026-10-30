"""Lazy model lifecycle shared by the ASR and TTS backends.

A model loads on its first request, stays warm while it is used and is
dropped after ``idle_unload_s`` seconds without a call. Before a load the
host's MemAvailable is checked (``/proc/meminfo``): below ``min_free_gib``
the load is refused with :class:`ModelUnavailable`, which the API turns into
a 503. The box is shared with other model servers and a memory guard, so a
refused load is the correct outcome, not an error to retry in a loop.

Before refusing, a model with a ``room`` maker (``memroom.RoomMaker``, installed
by the API) first makes room: this service's other idle models, then the other
on-demand services' idle ones, are released and the same floor is checked
again. A load that passed the floor check but then ran out of GPU memory
(unified memory: MemAvailable counts page cache an allocation cannot always
get) makes room for the model's size and is tried once more. Requests hold a
model through :meth:`LazyModel.using`, so one serving a request is never released.
"""

from __future__ import annotations

import contextlib
import gc
import logging
import threading
import time
from typing import Any, Callable, Iterator

# stdlib only, like this module: the Parler worker's venv imports tts → runtime → memroom
from .memroom import idle_verdict, looks_out_of_memory

__all__ = [
    "DEFAULT_MIN_FREE_GIB",
    "ModelUnavailable",
    "ModelNotProvisioned",
    "LazyModel",
    "mem_available_gib",
    "hf_page",
    "not_provisioned",
]

#: MemAvailable that must remain AFTER a model load (here, not in config: the Parler worker runs in its own
#: venv without pydantic-settings and imports tts, which needs this). The host's memory guard
#: evicts llama servers (the tactical Gemma among them) below 6 GiB available,
#: so 8 GiB left keeps 2 GiB clear of it — the same floor the vision service
#: uses. It was 12 GiB: with the need estimate on top (ASR 4, TTS 5) a load then
#: wanted 16–17 GiB free, and on the shared box (15 GiB available on 29 Oct) a
#: field voice report was refused (503) although loading it would have left
#: 11 GiB.
DEFAULT_MIN_FREE_GIB = 8.0

log = logging.getLogger("speech.runtime")

#: One model load at a time in this service. Two loads at once (the Parler worker and an ASR, 29 Oct)
#: ran the GPU out of memory with 20 GiB available; a load that waits checks memory after the other
#: one has finished. Requests for a loaded model never wait on this.
_LOAD_LOCK = threading.RLock()
#: how long a load waits for another to finish before it is refused (503); a cold Parler load takes ~60 s
LOAD_WAIT_S = 180.0


class ModelUnavailable(RuntimeError):
    """The model cannot be loaded right now (memory, missing weights)."""


class ModelNotProvisioned(ModelUnavailable):
    """The model cannot load until an operator acts: its gated weights were
    not granted or not downloaded, or a runtime package is missing. Unlike a
    memory refusal this does not clear by waiting, so a fallback backend may
    take over (see ``asr.FallbackASR`` / ``tts.FallbackTTS``)."""


def hf_page(repo: str) -> str:
    return f"https://huggingface.co/{repo}"


# Substrings of the errors transformers / huggingface_hub raise (older
# transformers wrap them in a plain OSError) when a repo is gated and not
# granted, or absent from the local cache in offline mode.
_GATED_HINTS = ("gated", "401 client error", "403 client error", "restricted",
                "awaiting a review", "not in the authorized list")
_NOT_CACHED_HINTS = (
    "offline", "couldn't connect", "cannot find the requested files", "not a local folder",
    "does not appear to have a file", "local_files_only", "no such file",
)


def not_provisioned(repo: str, exc: BaseException, *, gated: bool) -> ModelNotProvisioned | None:
    """Turn a load error into a clear :class:`ModelNotProvisioned`, or return
    ``None`` when it is something else (a CUDA error, a bug) that should stay
    loud. Never echoes a token: only the exception's type and message."""
    name = type(exc).__name__
    msg = str(exc)
    low = msg.lower()
    gate = f"gated: request access at {hf_page(repo)}" if gated else f"see {hf_page(repo)}"
    if isinstance(exc, ImportError):
        return ModelNotProvisioned(f"{repo}: a runtime package is missing ({msg[:160]}); {gate}")
    if name in ("GatedRepoError", "RepositoryNotFoundError") or (
            name == "HfHubHTTPError" and ("401" in msg or "403" in msg)) or (
            isinstance(exc, (OSError, ValueError)) and any(h in low for h in _GATED_HINTS)):
        return ModelNotProvisioned(
            f"{gate} with the deployment's Hugging Face account; the account has not been "
            f"granted access yet ({name})")
    if name in ("LocalEntryNotFoundError", "OfflineModeIsEnabled", "EntryNotFoundError") or (
            isinstance(exc, (OSError, ValueError)) and any(h in low for h in _NOT_CACHED_HINTS)):
        return ModelNotProvisioned(
            f"{repo}: weights are not in the local Hugging Face cache ({name}); {gate}, "
            f"then download them with scripts/fetch_gated_models.sh")
    return None


def mem_available_gib() -> float | None:
    try:
        with open("/proc/meminfo", encoding="ascii") as fh:
            for line in fh:
                if line.startswith("MemAvailable:"):
                    return int(line.split()[1]) / (1024 * 1024)
    except OSError:
        return None
    return None


class LazyModel:
    """Holds one loaded object (or nothing) behind a lock."""

    def __init__(
        self,
        name: str,
        loader: Callable[[], Any],
        *,
        need_gib: float,
        min_free_gib: float,
        idle_unload_s: float,
        mem_probe: Callable[[], float | None] = mem_available_gib,
    ) -> None:
        self.name = name
        self._loader = loader
        self._need = need_gib
        self._min_free = min_free_gib
        self._idle = idle_unload_s
        self._probe = mem_probe
        self._obj: Any = None
        self._lock = threading.RLock()
        self._last_used = 0.0
        # requests holding the model (``using``); counted under its own lock so that
        # a request waiting behind a load is already "in use"
        self._busy = 0
        self._busy_lock = threading.Lock()
        self.load_seconds: float | None = None
        self.last_error: str | None = None
        #: ``memroom.RoomMaker`` (or any callable ``(name, need, floor, free) -> free``), set by the API
        self.room: Callable[..., float | None] | None = None
        #: extra cleanup when the model is released (stop its worker process or llama-server)
        self.on_release: Callable[[], Any] | None = None

    @property
    def loaded(self) -> bool:
        return self._obj is not None

    @property
    def need_gib(self) -> float:
        return self._need

    @property
    def busy(self) -> bool:
        return self._busy > 0

    @contextlib.contextmanager
    def using(self) -> Iterator[Any]:
        """The loaded object, held for one request: never released while held."""
        with self._busy_lock:
            self._busy += 1
        try:
            yield self.get()
        finally:
            with self._busy_lock:
                self._busy -= 1
            self._last_used = time.monotonic()

    def _short_of_memory(self, free: float | None) -> bool:
        return free is not None and free - self._need < self._min_free

    def get(self) -> Any:
        with self._lock:
            if self._obj is None:
                if not _LOAD_LOCK.acquire(timeout=LOAD_WAIT_S):
                    self.last_error = (f"refused to load {self.name}: another voice model is still loading "
                                       f"(waited {LOAD_WAIT_S:.0f} s)")
                    log.warning("%s", self.last_error)
                    raise ModelUnavailable(self.last_error)
                try:
                    self._load_within_the_floor()
                finally:
                    _LOAD_LOCK.release()
            self._last_used = time.monotonic()
            return self._obj

    def _load_within_the_floor(self) -> None:
        """Floor check (making room first when short), then the load; under the lock of this model
        and the service's one-load-at-a-time lock."""
        free = self._probe()
        room = self.room if self._short_of_memory(free) else None
        made: str | None = None
        if room is not None:
            try:
                free = room(self.name, self._need, self._min_free, free)
            except Exception:  # noqa: BLE001 - making room is best effort; the floor still decides
                log.warning("making room for %s failed", self.name, exc_info=True)
            made = getattr(room, "summary", lambda: None)()
        if self._short_of_memory(free):
            self.last_error = (
                f"refused to load {self.name}: {free:.1f} GiB available, "
                f"needs ~{self._need:.1f} GiB plus a {self._min_free:.0f} GiB floor"
                + (f"; {made}" if made else "")
            )
            # the 503 carries the reason; the journal must too, so a refused
            # voice report during a demo is explained without a repro
            log.warning("%s", self.last_error)
            self._room_outcome(room, False, "still short of memory")
            raise ModelUnavailable(self.last_error)
        t0 = time.perf_counter()
        oom_room: list[Any] = []
        try:
            self._obj = self._load_making_room_on_oom(oom_room)
        except ModelUnavailable as exc:
            self.last_error = str(exc)[:400]
            self._room_outcome(room or (oom_room[0] if oom_room else None), False, self.last_error)
            raise
        except Exception as exc:  # weights missing, CUDA error, …
            self.last_error = f"{type(exc).__name__}: {exc}"[:400]
            log.exception("load failed: %s", self.name)
            self._room_outcome(room or (oom_room[0] if oom_room else None), False, self.last_error)
            raise ModelUnavailable(self.last_error) from exc
        self.load_seconds = round(time.perf_counter() - t0, 2)
        self.last_error = None
        log.info("loaded %s in %.1fs", self.name, self.load_seconds)
        self._room_outcome(room or (oom_room[0] if oom_room else None), True)

    def _load_making_room_on_oom(self, used: list[Any]) -> Any:
        """The loader; if it runs out of GPU memory and a room maker is set, the failed attempt's
        allocations are dropped, room is made for the model's size on top of what is available now,
        and it is tried once more (``used`` gets the room maker when that happens)."""
        try:
            return self._loader()
        except ModelUnavailable:
            raise
        except Exception as exc:
            room = self.room
            if room is None or not looks_out_of_memory(exc):
                raise
            first = exc
        used.append(room)
        log.warning("loading %s ran out of GPU memory; making room and trying once more", self.name)
        _drop_gpu_cache()
        free = self._probe()
        now = free if free is not None else 0.0
        try:
            room(self.name, self._need, now, now, reason="the load ran out of GPU memory")
        except Exception:  # noqa: BLE001 - best effort
            log.warning("making room for %s failed", self.name, exc_info=True)
        if not (getattr(room, "last_event", None) or {}).get("released"):
            made = getattr(room, "summary", lambda: None)() or "made room first: nothing released"
            raise RuntimeError(f"out of memory while loading ({made}): {type(first).__name__}: {first}") from first
        return self._loader()

    @staticmethod
    def _room_outcome(room: Any, ok: bool, detail: str | None = None) -> None:
        if room is not None and hasattr(room, "outcome"):
            with contextlib.suppress(Exception):
                room.outcome(ok, detail)

    def touch(self) -> None:
        self._last_used = time.monotonic()

    def release_if_idle(self, min_idle_s: float) -> dict[str, Any] | None:
        """Unload when loaded, not held by a request and unused for ``min_idle_s`` seconds.

        ``None`` when there is nothing to report (not loaded, not loading); otherwise
        ``{"model", "released", "why", "freed_gib"}``. Never waits: a model whose lock is
        taken (loading or unloading) is reported as in use.
        """
        if self._obj is None and not self._busy:
            return None
        why = idle_verdict(self._busy, self._last_used, time.monotonic(), min_idle_s)
        if why is None and not self._lock.acquire(blocking=False):
            why = "in use"
        elif why is None:
            try:  # re-check under the lock: a request may have started meanwhile
                if self._obj is None:
                    return None
                why = idle_verdict(self._busy, self._last_used, time.monotonic(), min_idle_s)
                if why is None:
                    if self.on_release is not None:
                        try:
                            self.on_release()
                        except Exception:  # noqa: BLE001 - the in-process weights are dropped regardless
                            log.warning("release hook failed: %s", self.name, exc_info=True)
                    self.unload()
                    log.info("released %s (idle; reloads on its next use)", self.name)
                    return {"model": self.name, "released": True, "why": None, "freed_gib": self._need}
            finally:
                self._lock.release()
        return {"model": self.name, "released": False, "why": why, "freed_gib": 0.0}

    def unload(self) -> bool:
        with self._lock:
            if self._obj is None:
                return False
            self._obj = None
        _drop_gpu_cache()
        log.info("unloaded %s", self.name)
        return True

    def maybe_unload_idle(self) -> bool:
        if self._obj is None or self._idle <= 0 or self._busy:
            return False
        if time.monotonic() - self._last_used < self._idle:
            return False
        with self._lock:  # re-check under the lock: a request may be running
            if self._busy or time.monotonic() - self._last_used < self._idle:
                return False
            return self.unload()

    def status(self) -> dict[str, Any]:
        return {
            "loaded": self.loaded,
            "load_seconds": self.load_seconds,
            "last_error": self.last_error,
        }


def _drop_gpu_cache() -> None:
    """Free unreferenced tensors and hand torch's cached GPU blocks back (this process only)."""
    gc.collect()
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:  # torch absent in the offline test venv
        pass

