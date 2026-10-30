"""Backend selection and the C1 ↔ checkpoint mapping (no torch, no weights)."""

from __future__ import annotations

import sys

import pytest

from conftest import FakeLengthError, FakePplxDecider, FakeRequestError, protocol_answer
from model_host.decider_backends import (
    MAX_OPTIONS,
    BackendConfigError,
    PplxDeciderBackend,
    StateTooLarge,
    c1_answer,
    default_question_mode,
    detect_runtime,
    model_name_from_snapshot,
    normalize_questions,
    resolve_question_mode,
    resolve_runtime,
)

BRAIN_PRE_MOVEMENT = {
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


def make_backend(mode: str, decider: FakePplxDecider | None = None) -> PplxDeciderBackend:
    return PplxDeciderBackend(
        "/nonexistent",
        device="cpu",
        max_state_tokens=8192,
        model_name="pplx-decider-flash-v1.2",
        question_mode=mode,
        decider=decider or FakePplxDecider(),
        errors=(FakeLengthError, FakeRequestError),
    )


# ── snapshot inspection ──────────────────────────────────────────────────────


def test_detect_runtime_from_layout(snapshots):
    assert detect_runtime(snapshots["flash"]) == "pplx_decider"
    assert detect_runtime(snapshots["v12"]) == "pplx_decider"
    assert detect_runtime(snapshots["v1"]) == "autojev"
    assert detect_runtime(snapshots["empty"]) is None


def test_resolve_runtime_auto_and_explicit(snapshots):
    assert resolve_runtime("auto", snapshots["flash"]) == "pplx_decider"
    assert resolve_runtime("", snapshots["v1"]) == "autojev"
    assert resolve_runtime("AUTOJEV", snapshots["v1"]) == "autojev"
    assert resolve_runtime("pplx_decider", snapshots["v12"]) == "pplx_decider"


def test_resolve_runtime_refuses_mismatch_and_unknown(snapshots):
    with pytest.raises(BackendConfigError, match="is a pplx_decider checkpoint"):
        resolve_runtime("autojev", snapshots["flash"])
    with pytest.raises(BackendConfigError, match="is a autojev checkpoint"):
        resolve_runtime("pplx_decider", snapshots["v1"])
    with pytest.raises(BackendConfigError, match="cannot detect"):
        resolve_runtime("auto", snapshots["empty"])
    with pytest.raises(BackendConfigError, match="DECIDER_RUNTIME must be"):
        resolve_runtime("vllm", snapshots["flash"])


def test_model_name_comes_from_the_snapshot(snapshots, tmp_path):
    assert model_name_from_snapshot(snapshots["flash"]) == "pplx-decider-flash-v1.2"
    assert model_name_from_snapshot(snapshots["v12"]) == "pplx-decider-v1.2"
    assert model_name_from_snapshot(snapshots["v1"]) == "pplx-decider-v1-27b"
    plain = tmp_path / "my-local-decider"
    plain.mkdir()
    assert model_name_from_snapshot(plain) == "my-local-decider"


def test_question_mode_defaults_follow_the_cards(snapshots):
    # 27B: grouping related facets helps; flash: one question per request
    assert default_question_mode(snapshots["v12"]) == "joint"
    assert default_question_mode(snapshots["flash"]) == "per_question"
    assert resolve_question_mode("auto", snapshots["flash"]) == "per_question"
    assert resolve_question_mode("joint", snapshots["flash"]) == "joint"
    assert resolve_question_mode("per-question", snapshots["v12"]) == "per_question"
    with pytest.raises(BackendConfigError):
        resolve_question_mode("both", snapshots["v12"])


# ── C1 request mapping ───────────────────────────────────────────────────────


def test_normalize_matches_the_historical_autojev_rows():
    out = normalize_questions(BRAIN_PRE_MOVEMENT, list_options_described_by_name=True)
    assert list(out) == ["route_strategy", "urgency", "disruption_tolerance"]
    assert out["route_strategy"] == {
        "type": "choice",
        "criteria": {"route_aaaa": "route_aaaa", "route_bbbb": "route_bbbb",
                     "delay_departure": "delay_departure"},
        "instructions": "Which candidate strategy should lead?",
    }
    assert out["urgency"] == {"type": "noul", "instructions": "How urgent is it to lock this plan now?"}
    assert out["disruption_tolerance"]["criteria"] == ["0.0", "1.0"]


def test_normalize_protocol_v3_shows_list_options_by_name():
    out = normalize_questions(BRAIN_PRE_MOVEMENT, list_options_described_by_name=False)
    assert out["route_strategy"]["criteria"] == {
        "route_aaaa": None, "route_bbbb": None, "delay_departure": None}
    described = normalize_questions(
        {"q": {"type": "choice", "options": {"hold_route": "Keep the planned route"}}},
        list_options_described_by_name=False,
    )
    assert described["q"]["criteria"] == {"hold_route": "Keep the planned route"}
    assert "instructions" not in described["q"]


@pytest.mark.parametrize(
    ("question", "message"),
    [
        ({"type": "choice"}, "choice requires options"),
        ({"type": "choice", "options": "a,b"}, "options must be list or dict"),
        ({"type": "choice", "options": []}, "1..249 options required"),
        ({"type": "choice", "options": [f"o{i}" for i in range(MAX_OPTIONS + 1)]}, "1..249"),
        ({"type": "score", "scale": [0.0]}, "score requires scale"),
        ({"type": "score"}, "score requires scale"),
        ({"type": "freeform"}, "type must be choice|noul|score"),
    ],
)
def test_normalize_rejects_malformed_questions(question, message):
    with pytest.raises(ValueError, match=message):
        normalize_questions({"q": question}, list_options_described_by_name=False)


def test_options_cap_is_the_c1_249():
    ok = {"q": {"type": "choice", "options": [f"o{i}" for i in range(MAX_OPTIONS)]}}
    assert len(normalize_questions(ok, list_options_described_by_name=False)["q"]["criteria"]) == 249


# ── C1 answer mapping ────────────────────────────────────────────────────────


def test_c1_answer_shapes():
    noul = c1_answer({"type": "noul", "noul": 0.8})
    assert noul == {"value": 0.8, "probability": 0.8, "confidence": None,
                    "distribution": {"false": pytest.approx(0.2), "true": 0.8}}
    q = {"type": "choice", "criteria": {"a": None, "b": None, "c": None}}
    choice = c1_answer(protocol_answer(q, [0.1, 0.7, 0.2]))
    assert choice["value"] == "b"
    assert choice["probability"] == pytest.approx(0.7)
    assert choice["confidence"] == pytest.approx((0.7 - 1 / 3) / (1 - 1 / 3))
    assert set(choice["distribution"]) == {"a", "b", "c"}
    s = {"type": "score", "criteria": ["0.0", "1.0"]}
    score = c1_answer(protocol_answer(s, [0.3, 0.7]))
    assert score["value"] == pytest.approx(0.7)       # expected level index
    assert score["probability"] == pytest.approx(0.7)  # distribution max
    assert set(score["distribution"]) == {"0", "1"}


# ── protocol v3 backend ──────────────────────────────────────────────────────


def test_joint_mode_sends_one_sequence_with_every_question_in_order():
    fake = FakePplxDecider()
    backend = make_backend("joint", fake)
    answers, tokens = backend.decide("TRIGGER: pre_movement\nstate", BRAIN_PRE_MOVEMENT)
    assert len(fake.calls) == 1 and len(fake.calls[0]) == 1
    request = fake.calls[0][0]
    assert request["state"] == "TRIGGER: pre_movement\nstate"
    assert list(request["questions"]) == list(BRAIN_PRE_MOVEMENT)
    assert request["questions"]["route_strategy"]["criteria"]["route_aaaa"] is None
    assert list(answers) == list(BRAIN_PRE_MOVEMENT)
    assert tokens == fake.decide(fake.calls[0])[0]["usage"]["input_tokens"]


def test_per_question_mode_sends_one_sequence_per_question_and_sums_tokens():
    fake = FakePplxDecider()
    backend = make_backend("per_question", fake)
    answers, tokens = backend.decide("state", BRAIN_PRE_MOVEMENT)
    assert len(fake.calls) == 1  # one decide() call: the library batches them
    sent = fake.calls[0]
    assert [list(r["questions"]) for r in sent] == [[k] for k in BRAIN_PRE_MOVEMENT]
    assert all(r["state"] == "state" for r in sent)
    assert list(answers) == list(BRAIN_PRE_MOVEMENT)
    assert tokens == sum(r["usage"]["input_tokens"] for r in fake.decide(sent))


def test_length_error_is_state_too_large_and_request_error_is_value_error():
    fake = FakePplxDecider()
    backend = make_backend("joint", fake)
    fake.raise_on_decide = FakeLengthError("Question 'q' needs 9000 tokens")
    with pytest.raises(StateTooLarge, match="8192-token limit"):
        backend.decide("s", BRAIN_PRE_MOVEMENT)
    fake.raise_on_decide = FakeRequestError("bad request")
    with pytest.raises(ValueError, match="bad request") as info:
        backend.decide("s", BRAIN_PRE_MOVEMENT)
    assert not isinstance(info.value, StateTooLarge)


def test_unknown_question_mode_is_a_config_error():
    with pytest.raises(BackendConfigError):
        make_backend("grouped")


def test_backends_module_does_not_import_torch():
    # the HTTP layer and these tests run without torch; only a real load imports it
    assert "torch" not in sys.modules
