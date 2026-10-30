from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

FIXTURES = Path(__file__).resolve().parent / "fixtures"

# A test never asks the live services on this box to release their models: no make-room peers unless a
# test names its own (fake) ones.
os.environ["VISION_PEER_FORECAST_PORT"] = "0"
os.environ["VISION_PEER_SPEECH_PORT"] = "0"


@pytest.fixture(scope="session")
def labels() -> list[dict]:
    return json.loads((FIXTURES / "labels.json").read_text(encoding="utf-8"))["images"]


@pytest.fixture(scope="session")
def jpeg_bytes() -> bytes:
    return (FIXTURES / "jam_csmt.jpg").read_bytes()
