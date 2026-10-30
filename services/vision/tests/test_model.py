"""Prompt, schema and llama-server lifecycle (no model is started here)."""

from __future__ import annotations

import asyncio
import base64
import json
from pathlib import Path

import pytest

from vision_service import model as model_mod
from vision_service.config import Settings
from vision_service.model import (
    DEPTH_BANDS,
    OUTPUT_SCHEMA,
    STATES,
    SYSTEM_PROMPT,
    LlamaServerManager,
    LlamaVisionModel,
    ModelUnavailable,
)


def test_system_prompt_restricts_to_roads_and_vehicles() -> None:
    p = SYSTEM_PROMPT.lower()
    assert "road" in p and "vehicles" in p
    for word in ("people", "faces", "clothing", "gender", "age", "ethnicity", "identity"):
        assert word in p, word
    assert "number plates" in p


def test_schema_only_allows_known_states_and_bands() -> None:
    props = OUTPUT_SCHEMA["properties"]
    assert props["state"]["enum"] == list(STATES)
    assert props["water_depth_band"]["enum"] == list(DEPTH_BANDS)
    assert OUTPUT_SCHEMA["additionalProperties"] is False
    assert set(props["vehicles_estimate"]["required"]) == {"cars", "buses", "two_wheelers", "autos"}
    # depth is judged against vehicles, never against a human body
    assert not any(w in " ".join(DEPTH_BANDS) for w in ("knee", "waist", "ankle", "chest"))


def test_payload_carries_image_prompt_and_schema() -> None:
    m = LlamaVisionModel(Settings(llm_manage=False))
    p = m._payload(b"\xff\xd8\xffJPEG", "Is the road open?")
    assert p["messages"][0] == {"role": "system", "content": SYSTEM_PROMPT}
    parts = p["messages"][1]["content"]
    url = parts[0]["image_url"]["url"]
    assert url.startswith("data:image/jpeg;base64,")
    assert base64.b64decode(url.split(",", 1)[1]) == b"\xff\xd8\xffJPEG"
    assert "Is the road open?" in parts[1]["text"]
    assert p["temperature"] == 0.0
    assert p["response_format"]["json_schema"]["schema"] == OUTPUT_SCHEMA


def test_manager_binds_loopback_and_loads_projector(tmp_path: Path) -> None:
    s = Settings(llm_port=9999)
    cmd = LlamaServerManager(s)._cmd()
    assert cmd[cmd.index("--host") + 1] == "127.0.0.1"
    assert cmd[cmd.index("--port") + 1] == "9999"
    assert "--mmproj" in cmd


def _files(tmp_path: Path) -> Settings:
    for n in ("llama-server", "m.gguf", "mm.gguf"):
        (tmp_path / n).write_bytes(b"x")
    return Settings(llama_server_bin=tmp_path / "llama-server", model_path=tmp_path / "m.gguf",
                    mmproj_path=tmp_path / "mm.gguf", need_gib=8, min_free_gib=12)


def test_manager_refuses_to_start_when_memory_is_low(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(model_mod, "_mem_available_gib", lambda: 15.0)
    started = []
    monkeypatch.setattr(model_mod.subprocess, "Popen", lambda *a, **k: started.append(a))
    mgr = LlamaServerManager(_files(tmp_path))
    with pytest.raises(ModelUnavailable, match="15.0 GiB available"):
        asyncio.run(mgr.ensure())
    assert started == []


def test_manager_reports_missing_weights(tmp_path: Path) -> None:
    s = Settings(model_path=tmp_path / "absent.gguf")
    with pytest.raises(ModelUnavailable, match="missing"):
        asyncio.run(LlamaServerManager(s).ensure())


def test_classify_parses_llama_server_json(monkeypatch) -> None:
    content = json.dumps({"state": "clear", "confidence": 0.9, "vehicles_estimate":
                          {"cars": 1, "buses": 0, "two_wheelers": 0, "autos": 0},
                          "water_depth_band": "none", "rationale": "Open road."})

    class Resp:
        status_code = 200
        text = ""

        def json(self):
            return {"choices": [{"message": {"content": content}}],
                    "timings": {"prompt_ms": 700.0, "predicted_ms": 2000.0}}

    class Client:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, json):
            assert url.endswith("/v1/chat/completions")
            return Resp()

    monkeypatch.setattr(model_mod.httpx, "AsyncClient", Client)
    m = LlamaVisionModel(Settings(llm_manage=False, llm_url="http://127.0.0.1:1"))
    out = asyncio.run(m.classify(b"\xff\xd8\xff"))
    assert out["state"] == "clear"
    assert out["_timings"]["predicted_ms"] == 2000.0


def test_manager_retries_an_early_exit_once_and_reports_the_server_output(tmp_path: Path, monkeypatch) -> None:
    s = _files(tmp_path)
    count = tmp_path / "starts"
    s.llama_server_bin.write_text(f"#!/bin/sh\necho x >> {count}\necho 'ggml_cuda_init: failed to allocate'\nexit 134\n")
    s.llama_server_bin.chmod(0o755)
    s.llm_log_path = tmp_path / "llama.log"
    monkeypatch.setattr(model_mod, "_mem_available_gib", lambda: 100.0)

    async def no_wait(_s: float) -> None:
        return None

    monkeypatch.setattr(model_mod.asyncio, "sleep", no_wait)
    mgr = LlamaServerManager(s)
    with pytest.raises(ModelUnavailable, match="exited with 134: ggml_cuda_init: failed to allocate"):
        asyncio.run(mgr.ensure())
    assert count.read_text().count("x") == 2
    assert not mgr.running


def test_manager_does_not_retry_when_memory_has_gone(tmp_path: Path, monkeypatch) -> None:
    s = _files(tmp_path)
    count = tmp_path / "starts"
    s.llama_server_bin.write_text(f"#!/bin/sh\necho x >> {count}\nexit 1\n")
    s.llama_server_bin.chmod(0o755)
    s.llm_log_path = tmp_path / "llama.log"
    free = iter([100.0, 5.0])
    monkeypatch.setattr(model_mod, "_mem_available_gib", lambda: next(free))

    async def no_wait(_s: float) -> None:
        return None

    monkeypatch.setattr(model_mod.asyncio, "sleep", no_wait)
    with pytest.raises(ModelUnavailable, match="exited with 1"):
        asyncio.run(LlamaServerManager(s).ensure())
    assert count.read_text().count("x") == 1


def test_refusal_is_logged_with_its_reason(tmp_path: Path, monkeypatch, caplog) -> None:
    """Audit 29 Oct: the 503s of 28 Oct left nothing in the journal."""
    monkeypatch.setattr(model_mod, "_mem_available_gib", lambda: 15.0)
    monkeypatch.setattr(model_mod.subprocess, "Popen", lambda *a, **k: None)
    mgr = LlamaServerManager(_files(tmp_path))
    with caplog.at_level("WARNING", logger="vision.model"), pytest.raises(ModelUnavailable):
        asyncio.run(mgr.ensure())
    assert any("15.0 GiB available" in r.getMessage() for r in caplog.records)


def test_missing_weights_are_logged(tmp_path: Path, caplog) -> None:
    # the server binary and projector exist (as on a provisioned box, or a CI runner without llama.cpp): only the
    # weights are missing
    s = _files(tmp_path).model_copy(update={"model_path": tmp_path / "absent.gguf"})
    with caplog.at_level("WARNING", logger="vision.model"), pytest.raises(ModelUnavailable):
        asyncio.run(LlamaServerManager(s).ensure())
    assert any("absent.gguf" in r.getMessage() for r in caplog.records)


def test_readiness_says_when_a_start_would_be_refused(tmp_path: Path, monkeypatch) -> None:
    started = []
    monkeypatch.setattr(model_mod.subprocess, "Popen", lambda *a, **k: started.append(a))
    mgr = LlamaServerManager(_files(tmp_path))  # need 8 + floor 12 = 20 GiB
    monkeypatch.setattr(model_mod, "_mem_available_gib", lambda: 15.0)
    r = mgr.readiness()
    assert r["ready"] is False and "15.0 GiB available" in r["reason"]
    assert r["start_needs_gib"] == 20.0 and r["mem_available_gib"] == 15.0
    monkeypatch.setattr(model_mod, "_mem_available_gib", lambda: 40.0)
    assert mgr.readiness() == {"ready": True, "reason": None, "start_needs_gib": 20.0,
                               "mem_available_gib": 40.0}
    assert started == []  # readiness never starts anything


def test_readiness_reports_missing_files(tmp_path: Path) -> None:
    r = LlamaServerManager(_files(tmp_path).model_copy(update={"model_path": tmp_path / "absent.gguf"})).readiness()
    assert r["ready"] is False and "absent.gguf" in r["reason"]


def test_unmanaged_model_has_no_readiness_probe() -> None:
    assert LlamaVisionModel(Settings(llm_manage=False)).status()["readiness"] is None
