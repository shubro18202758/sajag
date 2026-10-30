"""A llama.cpp ``llama-server`` child process, started on demand.

Used by the Svara-TTS GGUF backend: the 3B speech-token model runs about
three times faster in llama.cpp than in eager transformers on the GB10
(≈60 vs ≈20 tokens/s; 82 tokens are one second of audio).

The server binds 127.0.0.1 only, starts on the first request after the
caller's memory check, and is stopped when the backend unloads.
"""

from __future__ import annotations

import json
import logging
import os
import signal
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from .runtime import ModelUnavailable

__all__ = ["LlamaServer"]

log = logging.getLogger("speech.llama")


class LlamaServer:
    def __init__(self, binary: Path, model: Path, port: int, *, ctx: int = 4096,
                 extra_args: tuple[str, ...] = (), start_timeout_s: float = 180.0,
                 manage: bool = True, url: str | None = None) -> None:
        self.binary = Path(binary)
        self.model = Path(model)
        self.port = port
        self.ctx = ctx
        self.extra_args = extra_args
        self.start_timeout_s = start_timeout_s
        self.manage = manage
        self._url = (url or f"http://127.0.0.1:{port}").rstrip("/")
        self._proc: subprocess.Popen[bytes] | None = None

    @property
    def url(self) -> str:
        return self._url

    @property
    def running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def cmd(self) -> list[str]:
        return [str(self.binary), "-m", str(self.model), "--host", "127.0.0.1",
                "--port", str(self.port), "-c", str(self.ctx), "-ngl", "99", "-np", "1",
                "--no-webui", *self.extra_args]

    def _healthy(self) -> bool:
        try:
            with urllib.request.urlopen(self._url + "/health", timeout=3) as r:
                return r.status == 200
        except (urllib.error.URLError, OSError):
            return False

    def start(self) -> None:
        if not self.manage:
            if not self._healthy():
                raise ModelUnavailable(f"TTS model server not reachable at {self._url}")
            return
        if self.running:
            return
        for p in (self.binary, self.model):
            if not p.exists():
                raise ModelUnavailable(f"missing: {p}")
        log.info("starting llama-server on :%s", self.port)
        self._proc = subprocess.Popen(  # noqa: S603 - fixed argv from config
            self.cmd(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        deadline = time.monotonic() + self.start_timeout_s
        while time.monotonic() < deadline:
            if self._proc.poll() is not None:
                code = self._proc.returncode
                self._proc = None
                raise ModelUnavailable(f"llama-server exited with {code}")
            if self._healthy():
                return
            time.sleep(0.5)
        self.stop()
        raise ModelUnavailable("llama-server did not become healthy in time")

    def stop(self) -> bool:
        proc, self._proc = self._proc, None
        if proc is None or proc.poll() is not None:
            return False
        try:
            os.killpg(proc.pid, signal.SIGTERM)
            proc.wait(timeout=10)
        except (ProcessLookupError, subprocess.TimeoutExpired):
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        log.info("stopped llama-server")
        return True

    def completion(self, body: dict[str, Any], timeout: float = 300.0) -> dict[str, Any]:
        req = urllib.request.Request(self._url + "/completion", data=json.dumps(body).encode(),
                                     method="POST", headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.load(r)
        except (urllib.error.URLError, OSError, ValueError) as exc:
            raise ModelUnavailable(f"TTS model server error: {exc}") from exc
