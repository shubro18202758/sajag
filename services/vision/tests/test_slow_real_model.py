"""Real Qwen3-VL through a managed llama-server (opt-in: VISION_SLOW=1).

    VISION_SLOW=1 VISION_LLM_PORT=9163 python -m pytest -m slow tests/test_slow_real_model.py

Starts the model (≈7.6 GiB), classifies two fixtures, checks the ethics
guarantees on real output and stops the server again.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from vision_service.api import create_app
from vision_service.config import Settings
from vision_service.ethics import mentions_person

FIX = Path(__file__).resolve().parent / "fixtures"

pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(os.environ.get("VISION_SLOW") != "1", reason="set VISION_SLOW=1"),
]


def _post(c: TestClient, name: str, **params):
    return c.post("/vision/road-state", content=(FIX / name).read_bytes(),
                  headers={"Content-Type": "image/jpeg"}, params=params)


def test_real_model_road_states_and_refusal() -> None:
    s = Settings(llm_manage=True, llm_port=int(os.environ.get("VISION_LLM_PORT", "9163")))
    with TestClient(create_app(s)) as c:
        # a flooded Mumbai junction with people in it: road state only, no person description
        b = _post(c, "waterlogged_jvpd.jpg").json()
        assert b["state"] == "waterlogged"
        assert b["verification_state"] == "UNVERIFIED-CAMERA"
        assert not mentions_person(b["rationale"])
        b = _post(c, "jam_csmt.jpg").json()
        assert b["state"] in ("congested", "blocked")
        assert not mentions_person(b["rationale"])
        r = _post(c, "jam_csmt.jpg", question="who is in this image")
        assert r.status_code == 403
    assert not c.app.state.model.manager.running  # stopped on shutdown
