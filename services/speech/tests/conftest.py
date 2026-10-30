from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from speech_service.config import default_city_dir
from speech_service.places import Gazetteer, load_gazetteer

EVAL = Path(__file__).resolve().parents[1] / "eval"

# A test never asks the live services on this box to release their models: no make-room peers unless a
# test names its own (fake) ones.
os.environ["SPEECH_PEER_FORECAST_PORT"] = "0"
os.environ["SPEECH_PEER_VISION_PORT"] = "0"


@pytest.fixture(scope="session")
def city_dir() -> Path:
    d = default_city_dir()
    assert (d / "landmarks.json").is_file(), d
    return d


@pytest.fixture(scope="session")
def gaz(city_dir: Path, tmp_path_factory) -> Gazetteer:
    """Landmarks only, so the tests do not move when the events stream's
    gazetteer.json lands next to landmarks.json."""
    d = tmp_path_factory.mktemp("city")
    (d / "landmarks.json").write_bytes((city_dir / "landmarks.json").read_bytes())
    return load_gazetteer(d)


@pytest.fixture(scope="session")
def phrases() -> list[dict]:
    return json.loads((EVAL / "phrases.json").read_text(encoding="utf-8"))["phrases"]
