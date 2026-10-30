"""MCDA for decision support (C-U): AHP weights, the lexical veto, TOPSIS and Dirichlet sensitivity.

The method is GEOSPATIAL_AND_DSS §B4, ported from the PoC (``prototype/dss.py``: ``ahp_weights``, ``topsis``,
``sensitivity``, ``lexical_veto``) so the seeded surrogate run reproduces its numbers:

* **AHP** over the nine criteria with the default prior order (safety > protocol ≈ legality > time > cascade >
  disruption > population > cost > reversibility): a rank-gap pairwise matrix (Saaty 1..9), the principal
  eigenvector by power iteration, and the consistency ratio — reported, and flagged when it exceeds 0.10.
* **The lexical veto runs BEFORE scoring** (non-compensatory): a COA that touches a person, is illegal, breaches
  the protocol floor or is irreversible without a named-officer path is removed, never out-weighed.
* **TOPSIS** over the benefit-oriented attribute matrix (cost criteria are stored as their benefit complement).
  Zero-variance columns cannot change the ranking, so they are dropped and reported as gate-passed.
* **Ranking**: feasible COAs first, then by closeness; an infeasible COA is ranked after every feasible one and a
  vetoed COA after both — listed and labelled, never hidden.  The **public-safety floor** (FIX-C): when people are
  reported hurt or public safety is at stake and the report is credible enough to act on, the do-nothing baseline
  is also held below every feasible response COA — a documented, non-compensatory ordering rule; the TOPSIS
  closeness values are unchanged and still shown, and the rule is stated in the scoring note.  The decision
  margin is then measured against the best feasible COA the floor does NOT hold down (a held baseline is not a
  competitor the pick beat on score) — 0.0 when there is none, never negative because of the hold.
* **Sensitivity**: 2 000 Dirichlet draws around the AHP weights (concentration 60, seeded) → the share of draws
  in which the recommended (top feasible) COA stays on top, and which COA takes over otherwise.

Pure and deterministic given ``(matrix, weights, seed)``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np

from osint_common import kinds

__all__ = [
    "AHP_RANK",
    "CR_THRESHOLD",
    "CRITERIA",
    "CRITERION_IDS",
    "DIRICHLET_CONCENTRATION",
    "DIRICHLET_DRAWS",
    "FIXED_PRIORS",
    "PEOPLE_SAFETY_PRIORITY",
    "VERIFY_BELOW",
    "AhpResult",
    "Ranking",
    "TopsisResult",
    "ahp_weights",
    "lexical_veto",
    "public_safety_floor",
    "rank_coas",
    "sensitivity",
    "topsis",
]

#: The nine MCDA criteria (GEOSPATIAL_AND_DSS §B3): (id, label, direction). A cost criterion's attribute is
#: stored as its benefit complement, so every column maximises.
#:
#: Two criteria are NOT simulated outcomes, and their labels say so wherever the criteria table is shown:
#: ``safety_risk_reduction`` is a fixed prior — the event-resolution probability of a per-action table (a base
#: 0.30, +0.30 for a responder, +0.20 for a 108, +0.12 for a second unit, +0.08 for an advisory, the same for
#: every event class), lowered for a 108 delay and an unserved injury; ``time_to_effect`` is a nominal time per
#: COA kind (the PoC's effect profile), not a unit's ETA to the scene.  :data:`FIXED_PRIORS` says how.
CRITERIA: tuple[tuple[str, str, str], ...] = (
    (
        "safety_risk_reduction",
        "Public-safety risk reduction (fixed prior by COA actions, not simulated)",
        "benefit",
    ),
    ("time_to_effect", "Speed of effect (nominal time by COA kind, not a unit ETA)", "benefit"),
    ("resource_cost", "Resource cost", "cost"),
    ("public_disruption", "Public traffic disruption", "cost"),
    ("cascade_risk", "Cascade / spillover risk", "cost"),
    ("reversibility", "Reversibility", "benefit"),
    ("affected_population", "Affected population", "cost"),
    ("protocol_compliance", "Protocol compliance", "benefit"),
    ("legality", "Legality", "benefit"),
)
CRITERION_IDS: tuple[str, ...] = tuple(c[0] for c in CRITERIA)

#: The criteria whose attribute is a fixed table, not a simulated or measured outcome (HON-7, HON-8), with the
#: words the dissent and the scoring note use for them: a lead on one of these is never claimed as a simulated
#: advantage.
FIXED_PRIORS: dict[str, str] = {
    "safety_risk_reduction": "a fixed per-action prior, not a simulated outcome",
    "time_to_effect": "a nominal time per COA kind, not a unit ETA",
}

#: The default AHP prior order (§B4): an officer may re-elicit it; it is stored with every DSS.
AHP_RANK: tuple[str, ...] = (
    "safety_risk_reduction",
    "protocol_compliance",
    "legality",
    "time_to_effect",
    "cascade_risk",
    "public_disruption",
    "affected_population",
    "resource_cost",
    "reversibility",
)

#: Saaty's acceptance threshold for the consistency ratio.
CR_THRESHOLD = 0.10

#: Saaty's random indices.
_RANDOM_INDEX = {1: 0.0, 2: 0.0, 3: 0.58, 4: 0.9, 5: 1.12, 6: 1.24, 7: 1.32, 8: 1.41, 9: 1.45}

DIRICHLET_DRAWS = 2000
DIRICHLET_CONCENTRATION = 60.0
#: The sensitivity RNG is the DSS seed plus this offset (the PoC's).
SENSITIVITY_SEED_OFFSET = 101

#: A column whose variance is at most this is non-discriminating.
_ZERO_VARIANCE = 1e-12

#: The public-safety floor (FIX-C).  A situation is a people-safety situation when the reports carry an injury
#: cue or its class (or a correlated class) is urgent enough on the OSINT response-priority scale
#: (:data:`osint_common.kinds.RESPONSE_PRIORITY`) that doing nothing while it is real costs people their safety.
PEOPLE_SAFETY_PRIORITY = 6

#: The credibility at or above which a people-safety report is credible enough to act on: below it the report may
#: not be real, the floor does not hold, and the rationale says verify first (pointing at the information COA).
VERIFY_BELOW = 0.5


@dataclass(frozen=True)
class AhpResult:
    weights: tuple[float, ...]  # in CRITERION_IDS order
    consistency_ratio: float
    rank_order: tuple[str, ...]

    @property
    def acceptable(self) -> bool:
        return self.consistency_ratio < CR_THRESHOLD

    def weight_of(self, criterion: str) -> float:
        return self.weights[CRITERION_IDS.index(criterion)]


def ahp_weights(rank: Sequence[str] = AHP_RANK) -> AhpResult:
    """Principal-eigenvector AHP weights of a rank-gap pairwise matrix, and its consistency ratio."""
    rank = tuple(rank)
    if sorted(rank) != sorted(CRITERION_IDS):
        raise ValueError("the AHP rank order names each criterion exactly once")
    n = len(rank)
    pos = {k: i for i, k in enumerate(rank)}
    a = np.ones((n, n))
    for i, ki in enumerate(rank):
        for j, kj in enumerate(rank):
            if i == j:
                continue
            gap = pos[kj] - pos[ki]
            intensity = min(9, 1 + abs(gap))
            a[i, j] = intensity if gap > 0 else 1.0 / intensity
    w = np.ones(n) / n
    for _ in range(200):
        w2 = a @ w
        w2 = w2 / w2.sum()
        if np.allclose(w2, w, atol=1e-12):
            break
        w = w2
    lam_max = float((a @ w / w).mean())
    ci = (lam_max - n) / (n - 1)
    ri = _RANDOM_INDEX[n]
    cr = ci / ri if ri else 0.0
    wmap = {rank[i]: float(w[i]) for i in range(n)}
    return AhpResult(tuple(wmap[c] for c in CRITERION_IDS), float(cr), rank)


#: Veto reasons (the PoC's wording).
VETO_REASONS = {
    "touches_persons": "takes action against a person (forbidden)",
    "illegal": "illegal action",
    "protocol": "breaches protocol floor for event class",
    "irreversible": "irreversible without a named-officer path",
}


def lexical_veto(ethics: Mapping[str, bool]) -> tuple[bool, str | None]:
    """The non-compensatory veto (before scoring): ``(vetoed, reason)``."""
    if ethics.get("touches_persons"):
        return True, VETO_REASONS["touches_persons"]
    if not ethics.get("legal", False):
        return True, VETO_REASONS["illegal"]
    if not ethics.get("protocol_ok", False):
        return True, VETO_REASONS["protocol"]
    if ethics.get("irreversible_without_officer"):
        return True, VETO_REASONS["irreversible"]
    return False, None


@dataclass(frozen=True)
class TopsisResult:
    closeness: tuple[float, ...]
    keep: tuple[bool, ...]  # per criterion: discriminating (kept) or gate (dropped)
    effective_weights: tuple[float, ...]  # renormalised weights of the kept criteria


def topsis(matrix: Sequence[Sequence[float]], weights: Sequence[float]) -> TopsisResult:
    """TOPSIS closeness over benefit-normalised columns, zero-variance columns dropped (they contribute
    identically to every COA and cannot change the ranking; keeping them only dilutes the reported weight)."""
    x = np.array(matrix, dtype=float)
    w = np.array(weights, dtype=float)
    if x.ndim != 2 or x.shape[0] == 0:
        return TopsisResult((), tuple(False for _ in w), ())
    keep = x.var(axis=0) > _ZERO_VARIANCE
    if not keep.any():
        # nothing discriminates: every COA is equally close to the ideal
        return TopsisResult(tuple(1.0 for _ in range(x.shape[0])), tuple(bool(k) for k in keep), ())
    xk = x[:, keep]
    wk = w[keep]
    wk = wk / wk.sum()
    norm = np.sqrt((xk**2).sum(axis=0))
    norm[norm == 0] = 1e-9
    v = (xk / norm) * wk
    best = v.max(axis=0)
    worst = v.min(axis=0)
    d_best = np.sqrt(((v - best) ** 2).sum(axis=1))
    d_worst = np.sqrt(((v - worst) ** 2).sum(axis=1))
    denom = d_best + d_worst
    denom[denom == 0] = 1e-9
    c = d_worst / denom
    return TopsisResult(tuple(float(z) for z in c), tuple(bool(k) for k in keep), tuple(float(z) for z in wk))


def public_safety_floor(
    event_class: str, correlated_classes: Sequence[str], *, injuries: bool, credibility: float
) -> str:
    """The public-safety floor's mode for one situation: ``"hold"``, ``"verify"`` or ``"none"``.

    ``"hold"`` — people are reported hurt (an injury cue) or the class (or a correlated class) sits at or above
    :data:`PEOPLE_SAFETY_PRIORITY` on the response-priority scale, and the credibility of the report is at or above
    :data:`VERIFY_BELOW`: the do-nothing baseline is held below every feasible response COA.  ``"verify"`` — the
    same stake but below the threshold: the floor does not hold (the report may not be real) and the rationale says
    verify first.  ``"none"`` — no people-safety stake; the closeness order stands."""
    classes = [str(event_class), *(str(c) for c in correlated_classes)]
    people = bool(injuries) or any(
        kinds.RESPONSE_PRIORITY.get(c, 0) >= PEOPLE_SAFETY_PRIORITY for c in classes
    )
    if not people:
        return "none"
    return "hold" if float(credibility) >= VERIFY_BELOW else "verify"


@dataclass(frozen=True)
class Ranking:
    """The final order over the SCORED (unvetoed) COAs: feasible first, then by closeness (descending); when the
    public-safety floor holds, the do-nothing baseline also ranks after every feasible response COA.

    ``rival`` is the row the ``margin`` is measured against: the runner-up, unless it is the baseline the floor
    holds down — then ``None`` and the margin is ``0.0``: no other feasible response competes with the pick on
    score, and the held baseline's higher closeness never makes the margin negative."""

    order: tuple[int, ...]  # indices into the scored rows
    top: int
    runner_up: int | None
    margin: float
    rival: int | None = None


def rank_coas(
    closeness: Sequence[float], feasible: Sequence[bool], *, baseline: int | None = None
) -> Ranking:
    """Feasible first, then by closeness (ties: generation order). Infeasible COAs rank last, never hidden.

    ``baseline`` names the do-nothing baseline's row while the public-safety floor holds: it then also ranks
    after every feasible response COA.  Its closeness is unchanged and still shown — only the order is the
    floor's — and the margin is measured against the best feasible response COA after the pick, never against
    the held baseline (whose higher closeness would otherwise make the margin negative)."""
    idx = list(range(len(closeness)))
    held = (
        baseline is not None
        and 0 <= baseline < len(idx)
        and feasible[baseline]
        and any(feasible[i] and i != baseline for i in idx)
    )

    def key(i: int) -> tuple[bool, bool, float, int]:
        return (not feasible[i], held and i == baseline, -float(closeness[i]), i)

    order = sorted(idx, key=key)
    top = order[0]
    runner = order[1] if len(order) > 1 else None
    # every feasible response ranks above a held baseline, so the baseline is the runner-up only when no other
    # feasible response exists: nothing then competes with the pick on score (margin 0.0, never negative)
    rival = None if held and runner == baseline else runner
    margin = float(closeness[top] - closeness[rival]) if rival is not None else 0.0
    return Ranking(tuple(order), top, runner, margin, rival)


def _top_feasible(
    closeness: Sequence[float], feasible: Sequence[bool], baseline: int | None = None
) -> int | None:
    """The recommended row: the best FEASIBLE response COA while the floor holds the baseline (else the best
    feasible row)."""
    best: int | None = None
    best_response: int | None = None
    for i, c in enumerate(closeness):
        if not feasible[i]:
            continue
        if best is None or c > closeness[best]:
            best = i
        if baseline is not None and i != baseline and (best_response is None or c > closeness[best_response]):
            best_response = i
    if baseline is not None and best_response is not None and feasible[baseline]:
        return best_response
    return best


def sensitivity(
    matrix: Sequence[Sequence[float]],
    weights: Sequence[float],
    feasible: Sequence[bool],
    *,
    seed: int,
    draws: int = DIRICHLET_DRAWS,
    concentration: float = DIRICHLET_CONCENTRATION,
    baseline: int | None = None,
) -> tuple[float, dict[int, float]]:
    """``(rank_stability, flips_to)`` of the recommended COA under Dirichlet weight perturbation.

    The recommended COA is the top FEASIBLE one (an infeasible COA is never recommended, so a draw in which an
    infeasible COA scores highest is not a flip); while the public-safety floor holds (``baseline``), it is the
    best feasible response COA — the floor is non-compensatory, so weight draws cannot move it.  ``flips_to``
    maps a scored-row index to the share of draws in which it takes the top over."""
    base = topsis(matrix, weights)
    base_top = _top_feasible(base.closeness, feasible, baseline)
    if base_top is None:
        return 1.0, {}
    alpha = np.clip(np.array(weights, dtype=float) * concentration, 1e-3, None)
    rng = np.random.default_rng(int(seed) + SENSITIVITY_SEED_OFFSET)
    stay = 0
    flips: dict[int, int] = {}
    for _ in range(draws):
        w = rng.dirichlet(alpha)
        top = _top_feasible(topsis(matrix, w).closeness, feasible, baseline)
        if top == base_top:
            stay += 1
        elif top is not None:
            flips[top] = flips.get(top, 0) + 1
    return stay / draws, {i: n / draws for i, n in sorted(flips.items())}
