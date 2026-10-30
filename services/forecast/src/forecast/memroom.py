"""Making room for an on-demand model on the shared box (standard library only).

The on-demand models (speech ASR and TTS, vision, forecast) share one unified memory pool with the
resident ones (decider, Gemma, embeddings). Each refuses a load that would leave MemAvailable under
its floor. When that happens, :class:`RoomMaker` first frees this service's OWN idle models, then
asks the OTHER on-demand services to free theirs (loopback ``POST /admin/release``), waits briefly
for MemAvailable to come back, and hands the new figure back for the load to re-check. The floor
itself never moves, and nothing here touches a resident model or any other process: a service only
ever unloads its own models, and never one that is serving a request. A model waiting to load has
priority: making room releases every model not serving a request right now, however recently used
(``release_idle_s``, default 0); ``POST /admin/release`` called by hand keeps a 20 s default.

A released model is not restarted when the load is done: it reloads on its own next use, through
the service's existing lazy load. That is what "switching back" means here.

This file is identical in services/speech, services/vision and services/forecast (each suite's
test_memroom.py checks the copies match); edit all three together.
"""

from __future__ import annotations

import ipaddress
import json
import logging
import socket
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Sequence

__all__ = [
    "RELOAD_NOTE",
    "DEFAULT_RELEASE_IDLE_S",
    "RoomMaker",
    "idle_verdict",
    "looks_out_of_memory",
    "loopback_refusal",
    "mem_available_gib",
    "mem_free_gib",
    "post_release",
    "summarize",
]

RELOAD_NOTE = "released models are not restarted; each reloads on its next use"
#: a model used within this many seconds is kept (a demo segment that just used it is not robbed)
DEFAULT_RELEASE_IDLE_S = 20.0

# Headers a browser or the deck's proxy adds. /admin/release is for machine callers on this host
# (a peer service, scripts/ai_warm.sh); the deck proxies /api/<service>/* from loopback too, so a
# loopback source address alone would not keep a browser out.
_PROXY_HEADERS = ("forwarded", "x-forwarded-for", "x-forwarded-host", "x-real-ip", "origin", "referer",
                  "sec-fetch-site", "sec-fetch-mode", "x-sajag-officer")


def _meminfo_gib(key: str) -> float | None:
    try:
        with open("/proc/meminfo", encoding="ascii") as fh:
            for line in fh:
                if line.startswith(key + ":"):
                    return int(line.split()[1]) / (1024 * 1024)
    except OSError:
        return None
    return None


def mem_available_gib() -> float | None:
    return _meminfo_gib("MemAvailable")


def mem_free_gib() -> float | None:
    """MemFree: pages free right now. A GPU allocation (even creating a CUDA context) can fail on this
    unified-memory box while MemAvailable is high, because page cache and swap do not count for it."""
    return _meminfo_gib("MemFree")


def looks_out_of_memory(exc: BaseException | str) -> bool:
    """A failed allocation (torch, CUDA, llama.cpp's ggml) rather than any other load error."""
    text = str(exc).lower()
    name = type(exc).__name__ if isinstance(exc, BaseException) else ""
    return (name.endswith("OutOfMemoryError") or "out of memory" in text or "failed to allocate" in text
            or "cudamalloc failed" in text or "cuda_error_out_of_memory" in text
            or "cudaerrormemoryallocation" in text)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def idle_verdict(busy: int, last_used: float, now: float, min_idle_s: float) -> str | None:
    """None when a loaded model may be released, else why it is kept."""
    if busy > 0:
        return "in use"
    age = now - last_used
    if age < min_idle_s:
        return f"used {max(0.0, age):.0f}s ago"
    return None


def summarize(service: str, items: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Per-model release results → the /admin/release answer.

    Each item is ``{"model", "released": bool, "why": str | None, "freed_gib": float}``."""
    released = [str(i["model"]) for i in items if i.get("released")]
    freed = sum((float(i.get("freed_gib") or 0.0) for i in items if i.get("released")), 0.0)
    kept = [{"model": str(i["model"]), "why": str(i.get("why") or "kept")} for i in items if not i.get("released")]
    return {"service": service, "released": released, "freed_gib_estimate": round(freed, 1), "kept": kept,
            "note": RELOAD_NOTE}


def loopback_refusal(client_host: str | None, headers: Mapping[str, str]) -> str | None:
    """Why a caller may not use /admin/release (None = allowed): loopback, no browser/proxy headers."""
    host = (client_host or "").strip().strip("[]")
    if host.lower().startswith("::ffff:"):
        host = host[7:]
    try:
        local = ipaddress.ip_address(host).is_loopback
    except ValueError:
        local = host == "localhost"
    if not local:
        return "loopback callers only"
    for name in _PROXY_HEADERS:
        if headers.get(name):
            return f"machine callers on this host only (the request carries a {name} header)"
    return None


def post_release(port: int, timeout_s: float, idle_s: float | None = None) -> dict[str, Any]:
    """POST http://127.0.0.1:<port>/admin/release[?idle_s=]; the peer's JSON answer. Never via a proxy."""
    query = f"?idle_s={float(idle_s):g}" if idle_s is not None else ""
    req = urllib.request.Request(
        f"http://127.0.0.1:{int(port)}/admin/release{query}", data=b"", method="POST",
        headers={"Content-Type": "application/json", "User-Agent": "sajag-memroom"})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(req, timeout=timeout_s) as resp:  # noqa: S310 - fixed loopback URL
        body = resp.read(65536)
    out = json.loads(body or b"{}")
    return out if isinstance(out, dict) else {}


def _is_timeout(exc: BaseException) -> bool:
    if isinstance(exc, (TimeoutError, socket.timeout)):
        return True
    return isinstance(exc, urllib.error.URLError) and isinstance(exc.reason, (TimeoutError, socket.timeout))


class RoomMaker:
    """Tries to bring MemAvailable up to ``need + floor`` before a load is refused.

    Called as ``room(model, need_gib, floor_gib, free_gib)`` by the service's own load path; returns
    the MemAvailable the load should re-check (``None`` when it cannot be read). After a load that
    passed the floor check but then ran out of GPU memory (on unified memory MemAvailable counts page
    cache an allocation cannot always get), the load path calls it with ``floor_gib`` = what is
    available now, so that the model's own size is freed on top before its one retry. Order: this
    service's own idle models (``own_release``), then each peer in ``peers`` (name, port) until
    enough is free. List the cheapest-to-reload peer first: forecast (≈2 GiB, reloads in seconds)
    often covers a small shortfall without unloading a bigger model. When something was released
    (or a peer did not answer in time and may still be releasing), MemAvailable is polled for up to
    ``wait_s`` seconds. Peers are asked to release every model not serving a request that has been
    unused for ``release_idle_s`` (default 0: a waiting load has priority over a model merely kept
    warm). The last attempt is kept in ``last_event`` for ``/health``, with MemFree beside
    MemAvailable (an allocation can fail with MemAvailable high and MemFree low).
    """

    def __init__(self, service: str, peers: Sequence[tuple[str, int]], *,
                 own_release: Callable[[str], Mapping[str, Any]] | None = None,
                 timeout_s: float = 2.0, wait_s: float = 5.0, poll_s: float = 0.25,
                 release_idle_s: float = 0.0,
                 probe: Callable[[], float | None] = mem_available_gib,
                 free_probe: Callable[[], float | None] = mem_free_gib,
                 call: Callable[[int, float, float], Mapping[str, Any]] = post_release,
                 sleep: Callable[[float], None] = time.sleep,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self.service = service
        self.peers = [(str(n), int(p)) for n, p in peers if int(p) > 0]
        self._own = own_release
        self.timeout_s = timeout_s
        self.wait_s = wait_s
        self.poll_s = poll_s
        self.release_idle_s = release_idle_s
        self._probe = probe
        self._free_probe = free_probe
        self._call = call
        self._sleep = sleep
        self._clock = clock
        self.last_event: dict[str, Any] | None = None
        self.attempts = 0
        self.log = logging.getLogger(f"{service}.memroom")

    def config(self) -> dict[str, Any]:
        return {"enabled": True, "asks": ([f"{self.service} (own idle models)"] if self._own else [])
                + [f"{n} :{p}" for n, p in self.peers],
                "releases_models_unused_for_s": self.release_idle_s, "timeout_s": self.timeout_s,
                "wait_s": self.wait_s}

    # -- the attempt -----------------------------------------------------------
    def __call__(self, model: str, need_gib: float, floor_gib: float, free_gib: float,
                 reason: str = "a load would leave less than the memory floor") -> float | None:
        t0 = self._clock()
        target = need_gib + floor_gib
        self.attempts += 1
        ev: dict[str, Any] = {
            "at": _now_iso(), "for": model, "reason": reason, "needed_gib": round(target, 1),
            "free_before_gib": round(free_gib, 1), "memfree_before_gib": self._memfree(),
            "asked": [], "released": [], "kept": [],
            "errors": {}, "freed_gib_estimate": 0.0, "free_after_gib": None, "enough": False,
            "seconds": None, "load_succeeded": None, "note": RELOAD_NOTE,
        }
        self.last_event = ev
        self.log.info("making room for %s (%s): %.1f GiB available, wants %.1f", model, reason, free_gib, target)
        free: float | None = free_gib
        pending = False  # something was released, or a peer may still be releasing

        if self._own is not None:
            name = f"{self.service} (own)"
            ev["asked"].append(name)
            try:
                res = self._own(model)
            except Exception as exc:  # noqa: BLE001 - best effort: a failed own release must not break the load path
                ev["errors"][name] = f"failed ({type(exc).__name__})"
                self.log.warning("own release failed while making room for %s", model, exc_info=True)
            else:
                if self._absorb(ev, self.service, res):
                    pending = True
                    free = self._probe()

        for name, port in self.peers:
            if free is None or free >= target:
                break
            ev["asked"].append(name)
            try:
                res = self._call(port, self.timeout_s, self.release_idle_s)
            except Exception as exc:  # noqa: BLE001 - peers are best effort
                if _is_timeout(exc):
                    ev["errors"][name] = f"no answer within {self.timeout_s:.0f} s (it may still be releasing)"
                    pending = True
                elif isinstance(exc, urllib.error.HTTPError):
                    ev["errors"][name] = f"HTTP {exc.code}"
                elif isinstance(exc, urllib.error.URLError):
                    ev["errors"][name] = "unreachable"
                else:
                    ev["errors"][name] = f"failed ({type(exc).__name__})"
                continue
            if self._absorb(ev, name, res):
                pending = True
                free = self._probe()

        if pending and free is not None and free < target:
            deadline = self._clock() + self.wait_s
            while free is not None and free < target and self._clock() < deadline:
                self._sleep(self.poll_s)
                free = self._probe()

        ev["free_after_gib"] = round(free, 1) if free is not None else None
        ev["memfree_after_gib"] = self._memfree()
        ev["enough"] = free is None or free >= target
        ev["seconds"] = round(self._clock() - t0, 2)
        self.log.warning("made room for %s: %s; %s", model, self._describe(),
                         "enough to load" if ev["enough"] else "still short: the load is refused")
        return free

    def _memfree(self) -> float | None:
        try:
            v = self._free_probe()
        except Exception:  # noqa: BLE001 - diagnostics only
            return None
        return round(v, 1) if v is not None else None

    def outcome(self, succeeded: bool, detail: str | None = None) -> None:
        """Called by the load path once it has (or has not) loaded after this attempt."""
        ev = self.last_event
        if ev is None:
            return
        ev["load_succeeded"] = bool(succeeded)
        if detail:
            ev["load_error"] = str(detail)[:300]
        self.log.info("after making room, %s %s", ev["for"],
                      "loaded" if succeeded else f"did not load ({detail or 'refused'})")

    def summary(self) -> str | None:
        """One line for a 503 (and /health) that follows an attempt."""
        return None if self.last_event is None else "made room first: " + self._describe()

    def _describe(self) -> str:
        ev = self.last_event or {}
        rel = ", ".join(f"{m} ({r['service']})" for r in ev["released"] for m in r["models"])
        why = [f"{k['service']}: {k['model']} {k['why']}" for k in ev["kept"]]
        why += [f"{n}: {e}" for n, e in ev["errors"].items()]
        head = f"released {rel} (~{ev['freed_gib_estimate']:.1f} GiB)" if rel else "nothing idle to release"
        out = head + (f" ({'; '.join(why)})" if why else "")
        if ev["free_after_gib"] is not None:
            out += f"; {ev['free_after_gib']:.1f} GiB available after"
        return out

    @staticmethod
    def _absorb(ev: dict[str, Any], service: str, res: Mapping[str, Any]) -> bool:
        models = [str(m) for m in (res.get("released") or [])]
        for k in res.get("kept") or []:
            if isinstance(k, Mapping):
                ev["kept"].append({"service": service, "model": str(k.get("model")), "why": str(k.get("why"))})
        if not models:
            return False
        freed = float(res.get("freed_gib_estimate") or 0.0)
        ev["released"].append({"service": service, "models": models, "freed_gib_estimate": round(freed, 1)})
        ev["freed_gib_estimate"] = round(ev["freed_gib_estimate"] + freed, 1)
        return True
