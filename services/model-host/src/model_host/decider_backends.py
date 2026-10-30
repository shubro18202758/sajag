"""Decider backends behind the C1 HTTP contract.

Two checkpoint families are served through one contract:

  autojev       — protocol v1 checkpoints (pplx-decider-v1-27b): the snapshot
                  ships ``inference.py`` + ``source/src/autojev``; one sequence
                  per question, readout at the last token.
  pplx_decider  — protocol v3 joint checkpoints (pplx-decider-v1.2,
                  pplx-decider-flash-v1.2): the snapshot ships
                  ``source/src/pplx_decider`` + ``joint_config.json``; one
                  sequence per request holds the state and every question,
                  one readout per question at its ``<|fim_suffix|>`` marker,
                  full attention noncausal.

The backend is chosen by ``DECIDER_RUNTIME`` / ``decider.runtime``
(``auto`` | ``autojev`` | ``pplx_decider``); ``auto`` reads the snapshot
layout. For protocol v3 the question mode (``joint`` | ``per_question``) is
chosen by ``DECIDER_QUESTION_MODE`` / ``decider.question_mode``; ``auto``
groups the questions of a request for the 27B (its card: grouping related
facets helps) and sends one question per sequence for the 4B flash model
(its card: one question per request is the safer default).

The C1 request/answer shapes are identical for both backends (see
``normalize_questions`` and ``c1_answer``). Each checkpoint applies its own
calibrated temperature from ``decision_config.json``; it is never overridden
here.

Nothing in this module imports torch (or the checkpoint code) at import
time, and nothing here makes an outbound network call: checkpoints load
from the local snapshot directory only.
"""

from __future__ import annotations

import json
import os
import sys
import threading
from pathlib import Path
from typing import Any, Protocol

#: C1 cap on options per choice question (the brain's client enforces the
#: same 249). Both checkpoint families have 255 readout rows; the contract
#: keeps the historical 249.
MAX_OPTIONS = 249

RUNTIMES = ("autojev", "pplx_decider")
QUESTION_MODES = ("joint", "per_question")


class StateTooLarge(ValueError):
    """One question with its state exceeds the per-sequence token cap (HTTP 413).

    Nothing is ever truncated: the request is refused instead.
    """


class BackendConfigError(RuntimeError):
    """The snapshot does not match the requested runtime (surfaced via /health)."""


# ─── snapshot inspection (no torch) ──────────────────────────────────────────


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def detect_runtime(snapshot: Path) -> str | None:
    """The runtime a snapshot's layout calls for, or None when unknown."""
    snap = Path(snapshot)
    if (snap / "source" / "src" / "pplx_decider").is_dir() and (snap / "joint_config.json").is_file():
        return "pplx_decider"
    if (snap / "inference.py").is_file() and (snap / "source" / "src" / "autojev").is_dir():
        return "autojev"
    return None


def resolve_runtime(requested: str, snapshot: Path) -> str:
    """``auto`` → the detected runtime; an explicit choice must match the layout."""
    choice = (requested or "auto").strip().lower()
    detected = detect_runtime(snapshot)
    if choice == "auto":
        if detected is None:
            raise BackendConfigError(
                f"cannot detect the decider runtime of {snapshot}: expected "
                "source/src/pplx_decider + joint_config.json (protocol v3) or "
                "inference.py + source/src/autojev (protocol v1)"
            )
        return detected
    if choice not in RUNTIMES:
        raise BackendConfigError(
            f"DECIDER_RUNTIME must be auto|{'|'.join(RUNTIMES)} (got {requested!r})"
        )
    if detected is not None and detected != choice:
        raise BackendConfigError(
            f"DECIDER_RUNTIME={choice} but {snapshot} is a {detected} checkpoint"
        )
    return choice


def model_name_from_snapshot(snapshot: Path) -> str:
    """``…/models--org--name/snapshots/<sha>`` → ``name``; otherwise the dir name."""
    snap = Path(snapshot)
    parent = snap.parent
    if parent.name == "snapshots" and parent.parent.name.startswith("models--"):
        return parent.parent.name.split("--")[-1]
    return snap.name or str(snap)


def default_question_mode(snapshot: Path) -> str:
    """Card defaults: group related questions for the 27B, one per sequence for flash."""
    cfg = _read_json(Path(snapshot) / "decision_config.json")
    base = str(cfg.get("base_model", ""))
    name = model_name_from_snapshot(snapshot).lower()
    if "flash" in name:
        return "per_question"
    if "27b" in base.lower() or "27b" in name:
        return "joint"
    # unknown size: the per-question layout is the conservative choice
    # (it is never more than ~0.4 points worse than grouping on either card)
    return "per_question"


def resolve_question_mode(requested: str, snapshot: Path) -> str:
    choice = (requested or "auto").strip().lower().replace("-", "_")
    if choice == "auto":
        return default_question_mode(snapshot)
    if choice not in QUESTION_MODES:
        raise BackendConfigError(
            f"DECIDER_QUESTION_MODE must be auto|{'|'.join(QUESTION_MODES)} (got {requested!r})"
        )
    return choice


def checkpoint_temperature(snapshot: Path) -> float | None:
    value = _read_json(Path(snapshot) / "decision_config.json").get("temperature")
    return float(value) if isinstance(value, (int, float)) else None


# ─── C1 request / answer mapping (shared by both backends) ───────────────────


def normalize_questions(
    questions: dict[str, dict[str, Any]], *, list_options_described_by_name: bool
) -> dict[str, dict[str, Any]]:
    """C1 question set → the checkpoints' question schema, insertion order kept.

    C1: ``choice`` takes ``options`` (list of names, or dict name→description),
    ``score`` takes ``scale`` (≥2 level descriptions, lowest first), ``noul``
    takes neither. Both checkpoint families read ``criteria``.

    ``list_options_described_by_name``: a plain option list becomes
    ``{name: name}`` (the autojev path's historical prompt, kept byte-exact)
    or ``{name: None}`` (protocol v3's documented form: the option is shown
    by its name alone).
    """
    out: dict[str, dict[str, Any]] = {}
    for name in questions:
        q = questions[name]
        qtype = q.get("type")
        instructions = q.get("instructions")
        if qtype == "choice":
            raw = q.get("options")
            if raw is None:
                raise ValueError(f"question '{name}': choice requires options")
            if isinstance(raw, dict):
                criteria: dict[str, Any] = {str(k): v for k, v in raw.items()}
            elif isinstance(raw, list):
                criteria = {
                    str(opt): (str(opt) if list_options_described_by_name else None)
                    for opt in raw
                }
            else:
                raise ValueError(f"question '{name}': options must be list or dict")
            if not 1 <= len(criteria) <= MAX_OPTIONS:
                raise ValueError(
                    f"question '{name}': 1..{MAX_OPTIONS} options required "
                    f"(got {len(criteria)})"
                )
            question: dict[str, Any] = {"type": "choice", "criteria": criteria}
        elif qtype == "noul":
            question = {"type": "noul"}
        elif qtype == "score":
            scale = q.get("scale")
            if not isinstance(scale, list) or len(scale) < 2:
                raise ValueError(
                    f"question '{name}': score requires scale as >=2 level descriptions"
                )
            # no C1 cap on levels beyond the checkpoint's own 255 (its
            # validation error is a 422, as it always was)
            question = {"type": "score", "criteria": [str(s) for s in scale]}
        else:
            raise ValueError(
                f"question '{name}': type must be choice|noul|score (got {qtype!r})"
            )
        if instructions is not None:
            question["instructions"] = instructions
        out[str(name)] = question
    return out


def c1_answer(ans: dict[str, Any]) -> dict[str, Any]:
    """One checkpoint answer (autojev or pplx_decider shape) → the C1 answer."""
    if ans["type"] == "noul":
        p_true = float(ans["noul"])
        return {
            "value": p_true,
            "probability": p_true,
            "confidence": None,  # noul answers carry no confidence
            "distribution": {"false": 1.0 - p_true, "true": p_true},
        }
    distribution = {k: float(v) for k, v in ans["probabilities"].items()}
    if ans["type"] == "choice":
        value: Any = ans["choice"]
        probability = distribution[value]
    else:  # score
        value = float(ans["score"])
        probability = max(distribution.values())
    return {
        "value": value,
        "probability": probability,
        "confidence": float(ans["confidence"]),
        "distribution": distribution,
    }


# ─── backends ────────────────────────────────────────────────────────────────


class Backend(Protocol):
    runtime: str
    question_mode: str
    model_name: str

    def decide(
        self, state: str, questions: dict[str, dict[str, Any]]
    ) -> tuple[dict[str, dict[str, Any]], int]:
        """C1 questions → (raw checkpoint answers by name, state_tokens)."""
        ...


def _prepend_sys_path(*paths: Path) -> None:
    for p in reversed(paths):
        s = str(p)
        if s not in sys.path:
            sys.path.insert(0, s)


class AutojevBackend:
    """Protocol v1 (pplx-decider-v1-27b): the snapshot's ``inference.Decider``.

    One row per question, all rows in one padded forward pass — exactly the
    computation model-host served before protocol v3 existed.
    """

    runtime = "autojev"
    question_mode = "per_question"

    def __init__(self, snapshot: Path, *, device: str, max_state_tokens: int, model_name: str) -> None:
        self.snapshot = Path(snapshot)
        self.max_state_tokens = int(max_state_tokens)
        self.model_name = model_name
        _prepend_sys_path(self.snapshot, self.snapshot / "source" / "src")
        from inference import Decider  # the snapshot's own loader
        from autojev.model import answer as autojev_answer

        self._decider = Decider.from_pretrained(str(self.snapshot), device=device)
        self._answer = autojev_answer
        self.temperature = float(self._decider.model.temperature)

    def decide(
        self, state: str, questions: dict[str, dict[str, Any]]
    ) -> tuple[dict[str, dict[str, Any]], int]:
        import torch

        normalized = normalize_questions(questions, list_options_described_by_name=True)
        rows = [{"state": state, "question": q} for q in normalized.values()]
        dm = self._decider.model  # autojev.model.DecisionModel
        with torch.inference_mode():
            try:
                batch = dm.prepare(rows, max_length=self.max_state_tokens)
            except ValueError as exc:
                if "token limit" in str(exc):
                    raise StateTooLarge(str(exc)) from exc
                raise
            logits = dm(batch)
            probs = (logits / dm.temperature).softmax(-1).cpu().tolist()
        answers: dict[str, dict[str, Any]] = {}
        for name, row, p_full, count in zip(normalized, rows, probs, batch.counts):
            answers[name] = self._answer(row["question"], [float(v) for v in p_full[:count]])
        return answers, int(batch.input_tokens)


class PplxDeciderBackend:
    """Protocol v3 joint checkpoints (pplx-decider-v1.2, pplx-decider-flash-v1.2).

    ``joint``: one sequence holds the state and every question (a request
    over the token cap is split into question chunks by the library, each
    with the full state). ``per_question``: one sequence per question; the
    reference path still runs them as one left-padded batch.
    """

    runtime = "pplx_decider"

    def __init__(
        self,
        snapshot: Path,
        *,
        device: str,
        max_state_tokens: int,
        model_name: str,
        question_mode: str,
        fast: bool = False,
        decider: Any = None,
        errors: tuple[type[BaseException], type[BaseException]] | None = None,
    ) -> None:
        self.snapshot = Path(snapshot)
        self.max_state_tokens = int(max_state_tokens)
        self.model_name = model_name
        if question_mode not in QUESTION_MODES:
            raise BackendConfigError(f"unknown question mode {question_mode!r}")
        self.question_mode = question_mode
        self.fast = False
        if decider is None:
            _prepend_sys_path(self.snapshot / "source" / "src")
            import pplx_decider

            fast_opt: Any = False
            if fast:
                try:
                    import fla  # noqa: F401 — flash-linear-attention (requirements-fast.txt)

                    fast_opt = True
                except ImportError:
                    print(
                        "[model-host] DECIDER_FAST requested but flash-linear-attention "
                        "is not installed; serving the reference path",
                        flush=True,
                    )
            decider = pplx_decider.Decider.from_pretrained(
                self.snapshot, device=device, fast=fast_opt, max_length=self.max_state_tokens
            )
            if fast_opt:
                decider.warmup()
            self.fast = bool(fast_opt)
            errors = (pplx_decider.LengthError, pplx_decider.RequestError)
        self._decider = decider
        self._length_error, self._request_error = errors or (_NeverRaised, _NeverRaised)
        self.temperature = float(getattr(decider, "temperature", 0.0) or 0.0) or None

    def decide(
        self, state: str, questions: dict[str, dict[str, Any]]
    ) -> tuple[dict[str, dict[str, Any]], int]:
        normalized = normalize_questions(questions, list_options_described_by_name=False)
        if self.question_mode == "joint":
            requests = [{"state": state, "questions": normalized}]
        else:
            requests = [{"state": state, "questions": {k: q}} for k, q in normalized.items()]
        try:
            responses = self._decider.decide(requests)
        except self._length_error as exc:
            raise StateTooLarge(
                f"Question branch exceeds the {self.max_state_tokens}-token limit; "
                f"no input was truncated. ({exc})"
            ) from exc
        except self._request_error as exc:
            raise ValueError(str(exc)) from exc
        answers: dict[str, dict[str, Any]] = {}
        tokens = 0
        for response in responses:
            answers.update(response["answers"])
            tokens += int(response["usage"]["input_tokens"])
        # keep the caller's question order
        return {name: answers[name] for name in normalized}, tokens


class _NeverRaised(Exception):
    """Placeholder exception type for injected deciders without error classes."""


_IMPORT_LOCK = threading.Lock()


def load_backend(settings: Any, snapshot: Path) -> Backend:
    """Build the configured backend for ``snapshot`` (loads the weights)."""
    with _IMPORT_LOCK:
        runtime = resolve_runtime(settings.runtime, snapshot)
        if getattr(settings, "offline", True):
            os.environ["HF_HUB_OFFLINE"] = "1"
        if runtime == "autojev":
            return AutojevBackend(
                snapshot,
                device=settings.device,
                max_state_tokens=settings.max_state_tokens,
                model_name=settings.model_name,
            )
        return PplxDeciderBackend(
            snapshot,
            device=settings.device,
            max_state_tokens=settings.max_state_tokens,
            model_name=settings.model_name,
            question_mode=resolve_question_mode(settings.question_mode, snapshot),
            fast=settings.fast,
        )
