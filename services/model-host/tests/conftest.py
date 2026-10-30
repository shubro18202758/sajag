"""Offline fixtures for model-host: fake snapshots, a fake config, no weights.

Nothing here imports torch or a checkpoint's code. The HTTP tests swap the
module-level runtime of ``model_host.app`` for one whose backend factory
returns an in-memory fake, so the C1 contract is exercised end to end
without a GPU.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# ── a process-wide fake config + snapshot, set BEFORE model_host.app imports ──
_ROOT = Path(tempfile.mkdtemp(prefix="model-host-tests-"))


def make_snapshot(root: Path, repo: str, layout: str, base_model: str = "") -> Path:
    """An HF-cache-shaped snapshot dir with the files the runtime inspects."""
    snap = root / f"models--perplexity-ai--{repo}" / "snapshots" / "0123abcd"
    if layout == "pplx_decider":
        (snap / "source" / "src" / "pplx_decider").mkdir(parents=True, exist_ok=True)
        (snap / "joint_config.json").write_text(json.dumps({"version": 3}))
        cfg = {"format_version": 2, "temperature": 1.5, "base_model": base_model}
    elif layout == "autojev":
        (snap / "source" / "src" / "autojev").mkdir(parents=True, exist_ok=True)
        (snap / "inference.py").write_text("# placeholder\n")
        cfg = {"format_version": 1, "temperature": 2.2, "base_model": base_model}
    else:
        snap.mkdir(parents=True, exist_ok=True)
        cfg = {}
    (snap / "decision_config.json").write_text(json.dumps(cfg))
    return snap


DEFAULT_SNAPSHOT = make_snapshot(
    _ROOT, "pplx-decider-flash-v1.2", "pplx_decider", base_model="Qwen/Qwen3.5-4B"
)
CONFIG_PATH = _ROOT / "sajag_models.yaml"
CONFIG_PATH.write_text(
    "decider:\n"
    f"  snapshot_path: {DEFAULT_SNAPSHOT}\n"
    "  device: cpu\n"
    "  offline: true\n"
    "  max_questions_per_request: 6\n"
    "  max_state_tokens: 8192\n"
    "  queue_depth: 8\n"
)
os.environ["SAJAG_MODELS_CONFIG"] = str(CONFIG_PATH)
for _var in ("DECIDER_SNAPSHOT_PATH", "DECIDER_RUNTIME", "DECIDER_QUESTION_MODE",
             "DECIDER_MODEL_NAME", "DECIDER_FAST"):
    os.environ.pop(_var, None)


# ── fakes ────────────────────────────────────────────────────────────────────


def protocol_answer(question: dict[str, Any], probabilities: list[float]) -> dict[str, Any]:
    """The answer shape both checkpoint families return (pplx_decider.answer)."""
    if question["type"] == "noul":
        return {"type": "noul", "noul": probabilities[1]}
    if question["type"] == "choice":
        keys = list(question["criteria"])
    else:
        keys = [str(i) for i in range(len(question["criteria"]))]
    best = max(range(len(probabilities)), key=probabilities.__getitem__)
    dist = dict(zip(keys, probabilities))
    n = len(probabilities)
    if question["type"] == "choice":
        conf = 1.0 if n == 1 else (probabilities[best] - 1 / n) / (1 - 1 / n)
        return {"type": "choice", "probabilities": dist, "choice": keys[best],
                "confidence": max(0.0, min(1.0, conf))}
    return {"type": "score", "probabilities": dist,
            "legend": dict(zip(keys, question["criteria"])),
            "score": sum(i * p for i, p in enumerate(probabilities)), "confidence": 0.5}


def fixed_probabilities(question: dict[str, Any]) -> list[float]:
    """Deterministic, question-shaped probabilities (first option favoured)."""
    if question["type"] == "noul":
        return [0.25, 0.75]
    n = len(question["criteria"])
    if n == 1:
        return [1.0]
    head = 0.6
    return [head] + [(1 - head) / (n - 1)] * (n - 1)


class FakePplxDecider:
    """Stands in for ``pplx_decider.Decider``: records every request it gets."""

    temperature = 1.5

    def __init__(self) -> None:
        self.calls: list[list[dict[str, Any]]] = []
        self.raise_on_decide: BaseException | None = None

    def decide(self, requests: list[dict[str, Any]]) -> list[dict[str, Any]]:
        self.calls.append(requests)
        if self.raise_on_decide is not None:
            raise self.raise_on_decide
        out = []
        for request in requests:
            answers = {
                key: protocol_answer(q, fixed_probabilities(q))
                for key, q in request["questions"].items()
            }
            tokens = 100 + 40 * len(request["questions"]) + len(str(request["state"])) // 4
            out.append({"answers": answers,
                        "usage": {"input_tokens": tokens, "output_tokens": 0, "sequences": 1}})
        return out


class FakeLengthError(ValueError):
    pass


class FakeRequestError(ValueError):
    pass


@pytest.fixture
def snapshots(tmp_path: Path) -> dict[str, Path]:
    return {
        "flash": make_snapshot(tmp_path, "pplx-decider-flash-v1.2", "pplx_decider",
                               base_model="Qwen/Qwen3.5-4B"),
        "v12": make_snapshot(tmp_path, "pplx-decider-v1.2", "pplx_decider",
                             base_model="Qwen/Qwen3.8-27B"),
        "v1": make_snapshot(tmp_path, "pplx-decider-v1-27b", "autojev",
                            base_model="Qwen/Qwen3.8-27B"),
        "empty": make_snapshot(tmp_path, "something-else", "none"),
    }
