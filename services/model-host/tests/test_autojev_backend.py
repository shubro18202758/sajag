"""Regression: the protocol v1 (pplx-decider-v1-27b) path is unchanged by the refactor.

A fake snapshot ships a stand-in ``inference.py`` and ``autojev`` package
(the same import surface as the real snapshot) and a stub ``torch`` module
provides ``inference_mode``; the test checks the exact rows the backend
hands to ``DecisionModel.prepare`` — the prompt the live 27B has always
received — and the answer mapping, the token count and the 413 path.
"""

from __future__ import annotations

import contextlib
import sys
import textwrap
import types
from pathlib import Path

import pytest

from conftest import make_snapshot
from model_host.decider_backends import AutojevBackend, StateTooLarge, c1_answer, load_backend

FAKE_INFERENCE = textwrap.dedent('''
    import math

    class _Batch:
        def __init__(self, counts, tokens):
            self.counts = counts
            self.input_tokens = tokens

    class _Rows(list):
        def cpu(self):
            return self
        def tolist(self):
            return [list(r) for r in self]

    class _Logits:
        def __init__(self, rows):
            self.rows = rows
            self.scale = 1.0
        def __truediv__(self, scale):
            self.scale = scale
            return self
        def softmax(self, dim):
            out = _Rows()
            for row in self.rows:
                ex = [math.exp(v / self.scale) if v > -1e8 else 0.0 for v in row]
                total = sum(ex)
                out.append([e / total for e in ex])
            return out

    class _DecisionModel:
        temperature = 2.2

        def __init__(self):
            self.prepared = []

        def prepare(self, rows, max_length=8192):
            self.prepared.append((rows, max_length))
            if any(len(r["state"]) > 200 for r in rows):
                raise ValueError(
                    f"Question branch exceeds the {max_length}-token limit; no input was truncated."
                )
            from autojev.model import options
            counts = tuple(len(options(r["question"])[0]) for r in rows)
            return _Batch(counts, 50 * len(rows))

        def __call__(self, batch):
            rows = []
            for count in batch.counts:
                rows.append([float(count - i) if i < count else -1e9 for i in range(255)])
            return _Logits(rows)

    class Decider:
        def __init__(self):
            self.model = _DecisionModel()

        @classmethod
        def from_pretrained(cls, path, device=None):
            inst = cls()
            inst.path, inst.device = path, device
            return inst
''')

# the real autojev.model options()/answer() semantics (pplx-decider-v1-27b snapshot)
FAKE_AUTOJEV_MODEL = textwrap.dedent('''
    def options(question):
        if question["type"] == "choice":
            c = question["criteria"]
            return list(c), [k if v is None else f"{k}: {v}" for k, v in c.items()]
        if question["type"] == "score":
            return [str(i) for i in range(len(question["criteria"]))], list(question["criteria"])
        return ["false", "true"], ["No / false", "Yes / true"]

    def answer(question, probabilities):
        keys, descriptions = options(question)
        total = sum(probabilities)
        values = [v / total for v in probabilities]
        if question["type"] == "noul":
            return {"type": "noul", "noul": values[1]}
        best = max(range(len(values)), key=values.__getitem__)
        dist = dict(zip(keys, values))
        if question["type"] == "choice":
            n = len(values)
            conf = 1.0 if n == 1 else (values[best] - 1 / n) / (1 - 1 / n)
            return {"type": "choice", "probabilities": dist, "choice": keys[best],
                    "confidence": max(0.0, min(1.0, conf))}
        distance = sum(p * abs(i - best) for i, p in enumerate(values))
        mid = (len(values) - 1) / 2
        base = sum(abs(i - mid) for i in range(len(values))) / len(values)
        return {"type": "score", "probabilities": dist, "legend": dict(zip(keys, descriptions)),
                "score": sum(i * p for i, p in enumerate(values)),
                "confidence": max(0.0, 1.0 - distance / base)}
''')

PRE_MOVEMENT = {
    "route_strategy": {
        "type": "choice",
        "instructions": "Which candidate strategy should lead?",
        "options": ["route_aaaa", "route_bbbb", "delay_departure"],
    },
    "urgency": {"type": "noul", "instructions": "How urgent is it to lock this plan now?"},
    "disruption_tolerance": {
        "type": "score",
        "instructions": "Acceptable disruption, 0.0 to 1.0.",
        "scale": [0.0, 1.0],
    },
}


@pytest.fixture
def v1_snapshot(tmp_path, monkeypatch):
    snap = make_snapshot(tmp_path, "pplx-decider-v1-27b", "autojev", base_model="Qwen/Qwen3.8-27B")
    (snap / "inference.py").write_text(FAKE_INFERENCE)
    pkg = snap / "source" / "src" / "autojev"
    (pkg / "__init__.py").write_text("")
    (pkg / "model.py").write_text(FAKE_AUTOJEV_MODEL)
    stub = types.ModuleType("torch")
    stub.inference_mode = contextlib.nullcontext  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "torch", stub)
    monkeypatch.setattr(sys, "path", list(sys.path))
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")  # load_backend sets it; restored after
    before = set(sys.modules)
    yield snap
    for name in set(sys.modules) - before:
        if name == "inference" or name.startswith("autojev"):
            del sys.modules[name]


def _backend(snap: Path) -> AutojevBackend:
    return AutojevBackend(snap, device="cuda", max_state_tokens=8192, model_name="pplx-decider-v1-27b")


def test_rows_are_the_historical_v1_prompt_rows(v1_snapshot):
    backend = _backend(v1_snapshot)
    assert backend.runtime == "autojev" and backend.question_mode == "per_question"
    assert backend.temperature == 2.2
    answers, tokens = backend.decide("TRIGGER: pre_movement\nstate", PRE_MOVEMENT)
    rows, max_length = backend._decider.model.prepared[-1]
    assert max_length == 8192
    assert rows == [
        {"state": "TRIGGER: pre_movement\nstate",
         "question": {"type": "choice",
                      "criteria": {"route_aaaa": "route_aaaa", "route_bbbb": "route_bbbb",
                                   "delay_departure": "delay_departure"},
                      "instructions": "Which candidate strategy should lead?"}},
        {"state": "TRIGGER: pre_movement\nstate",
         "question": {"type": "noul", "instructions": "How urgent is it to lock this plan now?"}},
        {"state": "TRIGGER: pre_movement\nstate",
         "question": {"type": "score", "criteria": ["0.0", "1.0"],
                      "instructions": "Acceptable disruption, 0.0 to 1.0."}},
    ]
    assert tokens == 150
    assert list(answers) == list(PRE_MOVEMENT)
    route = c1_answer(answers["route_strategy"])
    assert route["value"] == "route_aaaa"
    assert set(route["distribution"]) == {"route_aaaa", "route_bbbb", "delay_departure"}
    assert sum(route["distribution"].values()) == pytest.approx(1.0)
    urgency = c1_answer(answers["urgency"])
    assert urgency["confidence"] is None and 0.0 < urgency["value"] < 1.0
    score = c1_answer(answers["disruption_tolerance"])
    assert 0.0 <= score["value"] <= 1.0 and isinstance(score["confidence"], float)


def test_over_cap_branch_is_state_too_large(v1_snapshot):
    backend = _backend(v1_snapshot)
    with pytest.raises(StateTooLarge, match="8192-token limit"):
        backend.decide("x" * 500, PRE_MOVEMENT)


def test_auto_runtime_loads_the_autojev_backend(v1_snapshot):
    class S:
        runtime = "auto"
        question_mode = "auto"
        fast = False
        device = "cuda"
        offline = True
        max_state_tokens = 8192
        model_name = "pplx-decider-v1-27b"

    backend = load_backend(S(), v1_snapshot)
    assert isinstance(backend, AutojevBackend)
    assert backend._decider.path == str(v1_snapshot)
