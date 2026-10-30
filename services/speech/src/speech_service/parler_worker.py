"""Indic Parler-TTS in its own interpreter, spoken to over pipes.

``parler-tts`` (0.2.3, the current release) pins ``transformers==4.46.1``,
while the service's ASR and Svara-TTS run on the model host's transformers
5.x. So Parler gets its own venv and runs here as a child process of the
service (:class:`speech_service.tts.ParlerWorkerTTS` starts and stops it).
No port is opened: requests and audio travel over stdin/stdout.

Protocol, one request at a time:

    parent → worker   one JSON line: {"op": "load"} or
                      {"op": "synthesize", "text": …, "lang": "mr", "voice": "female"}
    worker → parent   one JSON line: {"ok": true, "sr": 44100, "bytes": N}
                      followed by N bytes of little-endian float32 mono audio, or
                      {"ok": false, "error": "…", "not_provisioned": true|false}

``not_provisioned`` (gated access not granted, weights not downloaded,
package missing) lets the parent fall back to Svara instead of failing.
Whatever the libraries print goes to stderr (the service log), never into
the protocol stream.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, BinaryIO, Protocol

import numpy as np

from .runtime import ModelNotProvisioned

__all__ = ["serve", "main"]


class _Engine(Protocol):
    def synthesize(self, text: str, lang: str, voice: str) -> tuple[np.ndarray, int]: ...


def _send(out: BinaryIO, header: dict[str, Any], payload: bytes = b"") -> None:
    out.write(json.dumps(header, ensure_ascii=False).encode("utf-8") + b"\n")
    if payload:
        out.write(payload)
    out.flush()


def serve(engine: _Engine, load, rfile: BinaryIO, wfile: BinaryIO) -> None:
    """Answer requests until the parent closes stdin."""
    for line in rfile:
        if not line.strip():
            continue
        try:
            req = json.loads(line)
            op = req.get("op")
            if op == "load":
                load()
                _send(wfile, {"ok": True})
            elif op == "synthesize":
                audio, sr = engine.synthesize(str(req["text"]), str(req["lang"]), str(req["voice"]))
                data = np.ascontiguousarray(audio, dtype="<f4").tobytes()
                _send(wfile, {"ok": True, "sr": int(sr), "bytes": len(data)}, data)
            else:
                _send(wfile, {"ok": False, "error": f"unknown op {op!r}", "not_provisioned": False})
        except ModelNotProvisioned as exc:
            _send(wfile, {"ok": False, "error": str(exc)[:600], "not_provisioned": True})
        except Exception as exc:  # report and keep serving; the parent decides
            _send(wfile, {"ok": False, "error": f"{type(exc).__name__}: {exc}"[:600],
                          "not_provisioned": False})


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--model", required=True)
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--seed", type=int, default=1847)
    ap.add_argument("--description", required=True)
    ap.add_argument("--revision", default="", help="pinned commit of the model repo")
    args = ap.parse_args(argv)

    # keep the protocol stream clean: stdout now points at stderr
    proto = os.fdopen(os.dup(1), "wb")
    os.dup2(2, 1)
    sys.stdout = sys.stderr

    from .tts import IndicParlerTTS

    # the parent already checked memory before starting this process
    tts = IndicParlerTTS(args.model, device=args.device, description=args.description,
                         seed=args.seed, revision=args.revision or None,
                         min_free_gib=0, idle_unload_s=0)
    serve(tts, tts._lazy.get, sys.stdin.buffer, proto)


if __name__ == "__main__":
    main()
