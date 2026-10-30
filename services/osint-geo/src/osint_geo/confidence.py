"""The calibrated geocode confidence (OSINT SPEC §1.4 step 6; research A8), exactly::

    geocode_confidence = 0.30·match + 0.25·specificity + 0.20·disambiguation_margin
                       + 0.15·snap_quality + 0.10·source_locality

clamped to [0, 1]; bucket ``high`` ≥ 0.75, ``medium`` ≥ 0.5, ``low`` otherwise. Every component is in [0, 1]:

* **match** — 1.0 for an exact alias (also a grammar rewrite of a generic word, "Gariahat more" → "gariahat
  crossing"); the ``difflib`` ratio for a fuzzy match;
* **specificity** — landmark or POI 1.0, junction 0.95, road 0.8, neighbourhood 0.55, admin area 0.2
  (:data:`SPECIFICITY`; the PoC's table: a landmark outranks the junction named after it);
* **disambiguation margin** — ``(R_top − R_2) / R_top`` between the best and the runner-up reading of the text,
  1.0 for a single reading (:func:`margin`);
* **snap quality** — 1.0 on the network (a junction or a road toponym); for a place snapped to a segment anchor
  within :data:`SNAP_ANCHOR_MAX_M` (900 m) ``1 − residual/2500 m`` (the PoC's curve); 0.0 with no road anchor or
  beyond 900 m (F-HONEST OSINT-3: a place that far from its nearest segment is not ON it, and fusion already
  refuses such a snap; the PoC's 0.4 floor between 1.5 and 2.5 km paid confidence for a segment the report never
  named) (:func:`snap_quality`);
* **source locality** — 1.0 for a city- or state-scoped source or geo hint, else 0.3 (:data:`LOCAL`,
  :data:`NON_LOCAL`).

The sum is taken in the formula's order so equal inputs give bit-equal results (the PoC's 0.7175 rounds to 0.718).
The score is monotone: raising any component never lowers it.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from types import MappingProxyType
from typing import Literal

__all__ = [
    "HIGH",
    "LOCAL",
    "MEDIUM",
    "NON_LOCAL",
    "SNAP_ANCHOR_MAX_M",
    "SNAP_FLOOR",
    "SNAP_REACH_M",
    "SPECIFICITY",
    "WEIGHTS",
    "Bucket",
    "bucket",
    "margin",
    "score",
    "snap_quality",
    "specificity",
]

#: The formula's weights (SPEC §1.4 step 6); they sum to 1.
WEIGHTS: Mapping[str, float] = MappingProxyType(
    {"match": 0.30, "specificity": 0.25, "margin": 0.20, "snap": 0.15, "locality": 0.10}
)
HIGH = 0.75
MEDIUM = 0.5

#: Feature specificity (research A6/A8; the PoC's values, admin as "city" 0.2).
SPECIFICITY: Mapping[str, float] = MappingProxyType(
    {"landmark": 1.0, "poi": 1.0, "junction": 0.95, "road": 0.8, "neighbourhood": 0.55, "admin": 0.2}
)
LOCAL = 1.0
NON_LOCAL = 0.3
#: A snapped place earns snap quality ``max(SNAP_FLOOR, 1 − residual / SNAP_REACH_M)`` within the reach.
SNAP_REACH_M = 2500.0
SNAP_FLOOR = 0.4
#: A place lies ON its snapped segment only within this residual (``osint_analysis.fusion.SEGMENT_RESIDUAL_MAX_M``,
#: the same 900 m): beyond it the geocode keeps no road anchor and earns no snap quality (F-HONEST OSINT-3).
SNAP_ANCHOR_MAX_M = 900.0

Bucket = Literal["high", "medium", "low"]


def _unit(name: str, v: float) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not 0.0 <= v <= 1.0:
        raise ValueError(f"{name} must be a number within 0..1, got {v!r}")
    return float(v)


def score(match: float, specificity: float, margin: float, snap_quality: float, source_locality: float) -> float:
    """``0.30·match + 0.25·specificity + 0.20·margin + 0.15·snap_quality + 0.10·source_locality``, clamped to
    [0, 1] (unrounded; the resolver reports it to 3 decimals). Each component must be within 0..1."""
    total = (
        0.30 * _unit("match", match)
        + 0.25 * _unit("specificity", specificity)
        + 0.20 * _unit("margin", margin)
        + 0.15 * _unit("snap_quality", snap_quality)
        + 0.10 * _unit("source_locality", source_locality)
    )
    return max(0.0, min(1.0, total))


def bucket(confidence: float) -> Bucket:
    """``high`` at 0.75 and above, ``medium`` at 0.5 and above, ``low`` below."""
    c = _unit("confidence", confidence)
    if c >= HIGH:
        return "high"
    if c >= MEDIUM:
        return "medium"
    return "low"


def margin(r_top: float, r_second: float | None) -> float:
    """The disambiguation margin ``(R_top − R_2) / R_top`` in [0, 1]; 1.0 when there is no runner-up."""
    if r_second is None:
        return 1.0
    if r_top <= 0:
        return 0.0
    return max(0.0, min(1.0, (r_top - r_second) / r_top))


def snap_quality(residual_m: float | None, *, on_network: bool = False) -> float:
    """1.0 on the network; ``max(0.4, 1 − residual/2500)`` for a place snapped within :data:`SNAP_ANCHOR_MAX_M`
    (900 m, so the floor is never reached); 0.0 without a road anchor (``residual_m`` ``None`` or beyond 900 m).
    Non-increasing in the residual."""
    if on_network:
        return 1.0
    if residual_m is None or not math.isfinite(residual_m) or residual_m < 0 or residual_m > SNAP_ANCHOR_MAX_M:
        return 0.0
    return max(SNAP_FLOOR, 1.0 - residual_m / SNAP_REACH_M)


def specificity(feature_type: str) -> float:
    """The specificity of a feature type (:data:`SPECIFICITY`; 0.5 for an unknown type, as the PoC)."""
    return SPECIFICITY.get(feature_type, 0.5)
