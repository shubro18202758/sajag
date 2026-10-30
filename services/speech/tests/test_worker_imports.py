"""The Parler worker runs in its own venv (parler-tts pins transformers 4.46.1), which has no pydantic-settings.
It imports ``speech_service.tts``, so tts (and everything it imports) must not need the service's config."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"


def test_tts_imports_without_pydantic_settings():
    # a None entry in sys.modules makes any import of that name fail, as in the worker's venv
    code = ("import sys; sys.modules['pydantic_settings'] = None; sys.modules['pydantic'] = None; "
            "import speech_service.tts, speech_service.parler_worker; print('ok')")
    r = subprocess.run([sys.executable, "-c", code], cwd=SRC, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0 and r.stdout.strip() == "ok", r.stderr[-800:]
