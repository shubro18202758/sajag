"""The brain's COA-strategy seam (OSINT slice 6 / plan §5.2 C-U).

What this suite pins:
    questions   dss_questions mirrors pre_movement_questions' shapes — one
                choice over the five DSS COA kinds, one noul, one score on
                [0, 1] — and its instructions weigh public safety, the
                ambulance/108 corridor, disruption and report credibility
    checkpoint  strategy_prior calls the decider with movement_id
                "dss:<urn>", trigger "incident_detected" and force=True
    mapping     the coa_strategy answer maps to C-U's
                {kind, probability, confidence, tier}; a degraded or
                novelty-latched checkpoint (or an answer outside the COA
                vocabulary) maps to None
    ethics      the state document carries only the whitelisted situation
                fields — a person-ish key handed in by a caller can never
                reach the decider's context (events are about places)
"""

from __future__ import annotations

import json

from convoy_brain.decider import CheckpointResult
from convoy_brain.dss import COA_KINDS, dss_questions, strategy_prior
from convoy_brain.decider import DeciderBrain
from convoy_brain.llm.decider_client import DeciderAnswer

URN = "osint_event:1b94e9d2-7e11-4174-a735-7dd3be3189cf"

SITUATION = {
    "summary": "Two cars collided near Sector V; the service lane is blocked",
    "event_class": "road_accident",
    "subtype": "collision",
    "toponym": "Salt Lake Bypass",
    "credibility": 0.55,
    "verification_state": "NEWS-REPORTED",
    "second_order": [],
}


class FakeDecider:
    """Scriptable DeciderBrain stand-in: records the checkpoint kwargs."""

    def __init__(self, result: CheckpointResult) -> None:
        self.result = result
        self.calls: list[dict] = []

    async def checkpoint(self, **kwargs) -> CheckpointResult:
        self.calls.append(kwargs)
        return self.result


def decider_answer(value="standard", probability=0.61, confidence=0.83) -> DeciderAnswer:
    return DeciderAnswer(
        name="coa_strategy", type="choice", value=value,
        probability=probability, confidence=confidence,
    )


class TestDssQuestions:
    def test_types_mirror_pre_movement_questions(self):
        mirror = DeciderBrain.pre_movement_questions(["primary", "alternate"])
        questions = dss_questions(SITUATION)
        assert set(questions) == {"coa_strategy", "urgency", "disruption_tolerance"}
        assert set(mirror) == {"route_strategy", "urgency", "disruption_tolerance"}
        for name, mine in questions.items():
            twin = next(v for k, v in mirror.items() if v["type"] == mine["type"])
            assert set(mine) == set(twin), name  # same keys per type
        assert questions["coa_strategy"]["type"] == "choice"
        assert questions["urgency"]["type"] == "noul"
        assert questions["disruption_tolerance"]["type"] == "score"
        assert questions["disruption_tolerance"]["scale"] == [0.0, 1.0]

    def test_choice_is_exactly_the_five_dss_coa_kinds(self):
        options = dss_questions(SITUATION)["coa_strategy"]["options"]
        assert options == ["baseline", "minimal", "standard", "aggressive", "information"]
        assert list(COA_KINDS) == options

    def test_instructions_weigh_safety_ambulance_disruption_and_credibility(self):
        blob = json.dumps(dss_questions(SITUATION)).lower()
        for topic in ("public safety", "108", "disruption", "credibility"):
            assert topic in blob, topic

    def test_credibility_of_the_reports_reaches_the_instructions(self):
        text = dss_questions(SITUATION)["coa_strategy"]["instructions"]
        assert "NEWS-REPORTED" in text and "0.55" in text
        bare = dss_questions({})["coa_strategy"]["instructions"]
        assert "NEWS-REPORTED" not in bare


class TestStrategyPrior:
    async def test_checkpoint_called_as_a_dss_incident_and_forced(self):
        fake = FakeDecider(CheckpointResult(
            tier="decider",
            answers={"coa_strategy": decider_answer(), "urgency": DeciderAnswer(
                name="urgency", type="noul", value=0.12, probability=0.12,
                confidence=None),
                "disruption_tolerance": DeciderAnswer(
                name="disruption_tolerance", type="score", value=0.4,
                probability=0.4, confidence=0.7)},
        ))
        prior = await strategy_prior(fake, SITUATION, event_urn=URN)
        assert len(fake.calls) == 1
        call = fake.calls[0]
        assert call["movement_id"] == f"dss:{URN}"
        assert call["trigger"] == "incident_detected"
        assert call["force"] is True
        assert call["questions"] == dss_questions(SITUATION)

    async def test_answer_maps_onto_the_cu_prior(self):
        fake = FakeDecider(CheckpointResult(
            tier="decider", answers={"coa_strategy": decider_answer()}))
        prior = await strategy_prior(fake, SITUATION, event_urn=URN)
        assert prior == {"kind": "standard", "probability": 0.61,
                         "confidence": 0.83, "tier": "decider_27b"}

    async def test_tier0_hit_maps_to_the_decider_tier(self):
        fake = FakeDecider(CheckpointResult(
            tier="tier0_cache_hit",
            answers={"coa_strategy": decider_answer(value="information",
                                                    confidence=0.91)}))
        prior = await strategy_prior(fake, SITUATION, event_urn=URN)
        assert prior == {"kind": "information", "probability": 0.61,
                         "confidence": 0.91, "tier": "decider_27b"}

    async def test_noul_confidence_stays_none(self):
        fake = FakeDecider(CheckpointResult(
            tier="decider",
            answers={"coa_strategy": decider_answer(confidence=None)}))
        prior = await strategy_prior(fake, SITUATION, event_urn=URN)
        assert prior["confidence"] is None

    async def test_degraded_gemma_fallback_is_none(self):
        fake = FakeDecider(CheckpointResult(
            tier="gemma", degraded_reason="decider degraded: p95"))
        assert await strategy_prior(fake, SITUATION, event_urn=URN) is None

    async def test_novelty_latched_answer_is_withheld(self):
        fake = FakeDecider(CheckpointResult(
            tier="novelty_latched",
            answers={"coa_strategy": decider_answer()},  # answered, but withheld
            degraded_reason="novel situation: confident answer withheld",
        ))
        assert await strategy_prior(fake, SITUATION, event_urn=URN) is None

    async def test_an_answer_off_the_coa_vocabulary_is_none(self):
        fake = FakeDecider(CheckpointResult(
            tier="decider", answers={"coa_strategy": decider_answer(value="nuke_it")}))
        assert await strategy_prior(fake, SITUATION, event_urn=URN) is None

    async def test_no_coa_strategy_answer_is_none(self):
        fake = FakeDecider(CheckpointResult(tier="decider", answers={}))
        assert await strategy_prior(fake, SITUATION, event_urn=URN) is None


class TestStateDocEthics:
    async def test_no_person_key_reaches_the_state_document(self):
        """The context whitelist keeps caller-supplied keys out of the
        decider's context by construction — a poisoned person field in the
        situation dict can never travel."""
        poisoned = {
            **SITUATION,
            "suspect_name": "Dolores A. Ivens",
            "driver_age": 34,
        }
        fake = FakeDecider(CheckpointResult(
            tier="decider", answers={"coa_strategy": decider_answer()}))
        await strategy_prior(fake, poisoned, event_urn=URN)
        state_doc = fake.calls[0]["state_doc"]
        assert "Dolores" not in state_doc and "Ivens" not in state_doc
        assert "suspect" not in state_doc and "driver_age" not in state_doc
        # exactly the whitelisted situation fields, honestly labelled
        for line in ("class: road_accident", "subtype: collision",
                     "toponym: Salt Lake Bypass", "verification_state: NEWS-REPORTED"):
            assert line in state_doc
        assert state_doc.startswith("TRIGGER: incident_detected")

    async def test_state_doc_is_capped_and_redacted_text_only(self):
        fake = FakeDecider(CheckpointResult(
            tier="decider", answers={"coa_strategy": decider_answer()}))
        long = {**SITUATION, "summary": "x" * 20_000}
        await strategy_prior(fake, long, event_urn=URN)
        assert len(fake.calls[0]["state_doc"]) <= 400 * 4  # the per-event token cap
