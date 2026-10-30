"""COA-strategy questions for the 27B decider + the answer → strategy_prior.

Generalisation of ``DeciderBrain.pre_movement_questions`` (route strategy /
urgency / disruption tolerance) onto any reported situation: which course-of-
action strategy should lead the response, how urgent acting is, and how much
public-traffic disruption the response may cause.  The ``coa_strategy``
answer maps onto the oracle DSS's ``strategy_prior`` (contract C-U) — an
opinion recorded with the decision support, never a decision, and never an
input to the MCDA ranking itself.
"""

from __future__ import annotations

from typing import Any

from convoy_brain.decider import CheckpointResult, DeciderBrain

#: The COA strategies the oracle DSS generates (contract C-U ``Coa.kind``):
#: the decider ranks THESE, it never invents one.
COA_KINDS = ("baseline", "minimal", "standard", "aggressive", "information")

#: ``CheckpointResult.tier`` → ``strategy_prior.tier`` (C-U's tier enum).
#: A tier-0 hit serves a stored decider answer, so it keeps the decider tier.
_PRIOR_TIERS = {"decider": "decider_27b", "tier0_cache_hit": "decider_27b"}

#: The situation fields the state document carries.  The WHITELIST keeps any
#: caller-supplied key — a person, an author, a handle — out of the decider's
#: context by construction: OSINT situations are about places, never persons.
_CONTEXT_KEYS = (
    "event_class",
    "subtype",
    "toponym",
    "credibility",
    "verification_state",
    "second_order",
)


def dss_questions(situation: dict) -> dict[str, dict]:
    """Typed question set for the COA-strategy checkpoint.

    Same shapes as ``DeciderBrain.pre_movement_questions`` — one ``choice``
    over :data:`COA_KINDS`, one ``noul`` urgency, one ``score`` on [0, 1] —
    with the instructions weighing public safety, the ambulance/108 impact,
    the disruption each response causes and the credibility of the reports.
    """
    state = situation.get("verification_state") if isinstance(situation, dict) else None
    cred = situation.get("credibility") if isinstance(situation, dict) else None
    trust = ""
    if state or isinstance(cred, (int, float)):
        trust = " The reports are labelled"
        if state:
            trust += f" {state}"
        if isinstance(cred, (int, float)):
            trust += f" (credibility {float(cred):.2f})"
        trust += " — weigh how far they can be trusted before acting."
    return {
        "coa_strategy": {
            "type": "choice",
            "instructions": (
                "Decision support for a reported situation on the city's "
                "roads. Choose which course-of-action strategy should lead "
                "the response: baseline (monitor only, do nothing), minimal, "
                "standard, aggressive, or information (gather more before "
                "acting). Weigh public safety first, the impact on ambulances "
                "and the 108 emergency corridor, the traffic disruption each "
                "response causes, and the credibility of the reports." + trust
            ),
            "options": list(COA_KINDS),
        },
        "urgency": {
            "type": "noul",
            "instructions": (
                "How urgent is it to act on this situation now rather than "
                "waiting for better information or conditions? (noul = "
                "none-of-the-above likelihood, i.e. probability the situation "
                "defies the listed strategy options)"
            ),
        },
        "disruption_tolerance": {
            "type": "score",
            "instructions": (
                "Acceptable level of public-traffic disruption for the "
                "response, 0.0 (minimize at all costs) to 1.0 (response speed "
                "dominates completely)."
            ),
            "scale": [0.0, 1.0],
        },
    }


def _prior_from_checkpoint(result: Any) -> dict | None:
    """One ``CheckpointResult`` as contract C-U's ``strategy_prior``, or None.

    None when the checkpoint is degraded, the answer is novelty-latched (a
    latched result still carries the answers — they are WITHHELD), the tier
    is not a served decider answer, or there is no usable ``coa_strategy``
    answer inside the COA vocabulary.
    """
    tier = _PRIOR_TIERS.get(getattr(result, "tier", ""))
    if tier is None or getattr(result, "degraded_reason", None) is not None:
        return None
    answer = (getattr(result, "answers", None) or {}).get("coa_strategy")
    if answer is None or getattr(answer, "value", None) not in COA_KINDS:
        return None
    return {
        "kind": answer.value,
        "probability": answer.probability,
        "confidence": answer.confidence,
        "tier": tier,
    }


async def strategy_prior(
    decider: DeciderBrain, situation: dict, *, event_urn: str
) -> dict | None:
    """One COA-strategy opinion from the 27B decider (contract C-U), or None.

    ``force=True`` bypasses the per-movement rate limit: one opinion per
    generated decision support, never a per-tick loop.  The state document
    carries ONLY the whitelisted situation fields — no person field by
    construction — and the situation summary is already redacted at parse
    (contract C-T); egress masking stays the caller's job (the MCP tool's).
    """
    context = {key: situation.get(key) for key in _CONTEXT_KEYS}
    state_doc = DeciderBrain.build_state_doc(
        trigger="incident_detected",
        summary=str(situation.get("summary") or ""),
        context=context,
    )
    result = await decider.checkpoint(
        movement_id=f"dss:{event_urn}",
        trigger="incident_detected",
        state_doc=state_doc,
        questions=dss_questions(situation),
        force=True,
    )
    return _prior_from_checkpoint(result)
