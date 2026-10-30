"""The C1 HTTP contract, end to end through FastAPI, with a fake backend.

The brain's client (convoy_brain.llm.decider_client) depends on exactly
these shapes: answers{name:{value, probability, confidence, distribution}},
state_tokens, latency_ms, the request_id echo, ≤6 questions (422), 413 for
an over-cap branch, 429 + Retry-After when the queue is full, 503 while
loading or after a failed load.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from conftest import DEFAULT_SNAPSHOT, FakeLengthError, FakePplxDecider, FakeRequestError
import model_host.app as app_module
from model_host.config import Settings
from model_host.decider_backends import PplxDeciderBackend, resolve_question_mode
from model_host.decider_runtime import Runtime

PRE_MOVEMENT = {
    "route_strategy": {
        "type": "choice",
        "instructions": "Which candidate strategy should lead?",
        "options": ["route_3f2a9c1d0b7e", "route_8e41aa0c55d2", "delay_departure"],
    },
    "urgency": {"type": "noul", "instructions": "How urgent is it to lock this plan now?"},
    "disruption_tolerance": {
        "type": "score",
        "instructions": "Acceptable disruption, 0.0 to 1.0.",
        "scale": [0.0, 1.0],
    },
}


class Harness:
    def __init__(self, settings: Settings, fake: FakePplxDecider, *, fail: str | None = None,
                 gate: threading.Event | None = None) -> None:
        self.settings = settings
        self.fake = fake
        self.fail = fail
        self.gate = gate
        self.backends: list[PplxDeciderBackend] = []

    def factory(self, settings: Settings, snap: Path) -> PplxDeciderBackend:
        if self.gate is not None:
            self.gate.wait(10)
        if self.fail:
            raise RuntimeError(self.fail)
        backend = PplxDeciderBackend(
            snap, device="cpu", max_state_tokens=settings.max_state_tokens,
            model_name=settings.model_name,
            question_mode=resolve_question_mode(settings.question_mode, snap),
            decider=self.fake, errors=(FakeLengthError, FakeRequestError),
        )
        self.backends.append(backend)
        return backend


@pytest.fixture
def harness(monkeypatch):
    def build(*, env: dict[str, str] | None = None, fail: str | None = None,
              gate: threading.Event | None = None) -> tuple[TestClient, Harness]:
        for key, value in (env or {}).items():
            monkeypatch.setenv(key, value)
        settings = Settings()
        h = Harness(settings, FakePplxDecider(), fail=fail, gate=gate)
        monkeypatch.setattr(app_module, "settings", settings)
        monkeypatch.setattr(app_module, "runtime", Runtime(settings, backend_factory=h.factory))
        return TestClient(app_module.app), h

    return build


def _wait_loaded(client: TestClient, timeout: float = 5.0) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        body = client.get("/decider/health").json()
        if not body["loading"]:
            return body
        time.sleep(0.02)
    raise AssertionError("fake backend never finished loading")


def test_decide_returns_the_c1_shape(harness):
    client, h = harness()
    with client:
        health = _wait_loaded(client)
        assert health["loaded"] is True and health["load_error"] is None
        r = client.post("/decide", json={"request_id": "rq-1", "state": "TRIGGER: pre_movement\nx",
                                         "questions": PRE_MOVEMENT})
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"answers", "state_tokens", "latency_ms", "request_id"}
    assert body["request_id"] == "rq-1"
    assert isinstance(body["state_tokens"], int) and body["state_tokens"] > 0
    assert isinstance(body["latency_ms"], float)
    answers = body["answers"]
    assert list(answers) == list(PRE_MOVEMENT)
    for answer in answers.values():
        assert set(answer) == {"value", "probability", "confidence", "distribution"}
    route = answers["route_strategy"]
    assert route["value"] == "route_3f2a9c1d0b7e"
    assert route["probability"] == pytest.approx(0.6)
    assert route["value"] == max(route["distribution"], key=route["distribution"].get)
    urgency = answers["urgency"]
    assert urgency["confidence"] is None
    assert urgency["value"] == urgency["probability"] == urgency["distribution"]["true"]
    assert set(urgency["distribution"]) == {"false", "true"}
    score = answers["disruption_tolerance"]
    assert 0.0 <= score["value"] <= 1.0
    assert score["probability"] == max(score["distribution"].values())
    assert isinstance(score["confidence"], float)


def test_no_request_id_means_no_echo(harness):
    client, _ = harness()
    with client:
        _wait_loaded(client)
        r = client.post("/decide", json={"state": "s", "questions": {"u": PRE_MOVEMENT["urgency"]}})
    assert r.status_code == 200 and "request_id" not in r.json()


def test_health_names_the_model_from_the_snapshot_and_the_backend(harness):
    client, h = harness()
    with client:
        health = _wait_loaded(client)
    assert health["model"] == "pplx-decider-flash-v1.2"
    assert health["runtime"] == "pplx_decider"
    assert health["question_mode"] == "per_question"   # flash default (card)
    for key in ("loaded", "loading", "load_error", "resident_rss_gib", "cuda_reserved_gib",
                "p95_decide_latency_ms", "queue_depth", "decides_total", "decides_failed"):
        assert key in health


def test_model_name_and_question_mode_overrides(harness):
    client, h = harness(env={"DECIDER_MODEL_NAME": "decider-under-test",
                             "DECIDER_QUESTION_MODE": "joint"})
    with client:
        health = _wait_loaded(client)
        client.post("/decide", json={"state": "s", "questions": PRE_MOVEMENT})
    assert health["model"] == "decider-under-test"
    assert health["question_mode"] == "joint"
    # warmup (1 question) + one joint request carrying all three questions
    assert [len(call) for call in h.fake.calls] == [1, 1]
    assert list(h.fake.calls[-1][0]["questions"]) == list(PRE_MOVEMENT)


def test_per_question_mode_splits_the_request(harness):
    client, h = harness(env={"DECIDER_QUESTION_MODE": "per_question"})
    with client:
        _wait_loaded(client)
        r = client.post("/decide", json={"state": "s", "questions": PRE_MOVEMENT})
    assert r.status_code == 200
    assert [list(req["questions"]) for req in h.fake.calls[-1]] == [[k] for k in PRE_MOVEMENT]


def test_more_than_six_questions_is_422(harness):
    client, h = harness()
    questions = {f"q{i}": {"type": "noul", "instructions": "?"} for i in range(7)}
    with client:
        _wait_loaded(client)
        calls_before = len(h.fake.calls)
        r = client.post("/decide", json={"state": "s", "questions": questions})
    assert r.status_code == 422
    assert "at most 6 questions" in r.json()["error"]
    assert len(h.fake.calls) == calls_before


@pytest.mark.parametrize(
    "questions",
    [
        {"q": {"type": "freeform"}},
        {"q": {"type": "choice"}},
        {"q": {"type": "score", "scale": [1]}},
        {"token_budget": {"type": "choice", "options": []}},  # a name with "token" stays 422
    ],
)
def test_malformed_questions_are_422_before_any_compute(harness, questions):
    client, h = harness()
    with client:
        _wait_loaded(client)
        calls_before = len(h.fake.calls)
        r = client.post("/decide", json={"state": "s", "questions": questions})
    assert r.status_code == 422
    assert len(h.fake.calls) == calls_before


def test_empty_state_or_questions_is_422(harness):
    client, _ = harness()
    with client:
        _wait_loaded(client)
        assert client.post("/decide", json={"state": "", "questions": PRE_MOVEMENT}).status_code == 422
        assert client.post("/decide", json={"state": "s", "questions": {}}).status_code == 422


def test_over_cap_branch_is_413(harness):
    client, h = harness()
    with client:
        _wait_loaded(client)
        h.fake.raise_on_decide = FakeLengthError("Question 'q' needs 9100 tokens")
        r = client.post("/decide", json={"state": "s", "questions": PRE_MOVEMENT})
        health = client.get("/decider/health").json()
    assert r.status_code == 413
    assert "8192-token limit" in r.json()["error"]
    assert health["decides_failed"] == 1


def test_checkpoint_request_error_is_422(harness):
    client, h = harness()
    with client:
        _wait_loaded(client)
        h.fake.raise_on_decide = FakeRequestError("Question 'q': 300 options")
        r = client.post("/decide", json={"state": "s", "questions": PRE_MOVEMENT})
    assert r.status_code == 422


def test_full_queue_is_429_with_retry_after(harness):
    client, _ = harness()
    with client:
        _wait_loaded(client)
        rt = app_module.runtime
        rt._queue_counter = rt.settings.queue_depth   # 8 already running+waiting
        try:
            r = client.post("/decide", json={"state": "s", "questions": PRE_MOVEMENT})
        finally:
            rt._queue_counter = 0
    assert r.status_code == 429
    assert r.headers["retry-after"] == "5"


def test_failed_load_is_503_and_reported_by_health(harness):
    client, _ = harness(fail="CUDA out of memory (simulated)")
    with client:
        health = _wait_loaded(client)
        r = client.post("/decide", json={"state": "s", "questions": PRE_MOVEMENT})
        w = client.post("/warmup")
    assert health["loaded"] is False
    assert "CUDA out of memory" in health["load_error"]
    assert r.status_code == 503 and w.status_code == 503


def test_health_reports_loading_until_the_backend_is_ready(harness):
    gate = threading.Event()
    client, _ = harness(gate=gate)
    with client:
        health = client.get("/decider/health").json()
        assert health["loading"] is True and health["loaded"] is False
        assert health["model"] == "pplx-decider-flash-v1.2"
        assert health["runtime"] == "auto"           # resolved once loaded
        gate.set()
        assert _wait_loaded(client)["loaded"] is True


def test_warmup_and_metrics(harness):
    client, _ = harness()
    with client:
        _wait_loaded(client)
        w = client.post("/warmup")
        m = client.get("/metrics")
    assert w.status_code == 200
    assert w.json()["status"] == "warm"
    assert set(w.json()["warm_decision"]["answers"]) == {"self_test"}
    assert "model_host_loaded 1" in m.text


def test_default_config_points_at_the_tracked_models_config():
    from model_host import config

    assert config.DEFAULT_CONFIG.parts[-3:] == ("models-config", "configs", "sajag_models.yaml")
    assert Settings().snapshot_path == DEFAULT_SNAPSHOT
