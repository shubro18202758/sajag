"""The waterlogging nowcast model: rain × tide × pumps × susceptibility → depth-risk class 0–3 per segment.

A conceptual ponding (bucket) model on 15-minute steps, per road segment — MODELLED, with every parameter
here and in docs/ai/hydro.md:

    drainage capacity   C_open = C_MAX − (C_MAX − C_MIN)·S          mm/h, S = susceptibility 0..1
                        C(t)   = C_open · (1 − GATE_CUT·gate(t)) · (PUMP_FLOOR + (1 − PUMP_FLOOR)·a)
    ponded water        W(t+Δ) = max(0, W(t) + (RUNOFF·r(t) − C(t))·Δ)   mm over the catchment
    depth at the road   d = W/10 · (1 + CONCENTRATION·S)               cm

Capacities are runoff a drain carries (mm/h of water over its catchment), from the BMC's own design figures
(BMC Storm Water Drains department, RTI manual, chapter 1):

* ``C_MIN`` 12.5 mm/h — the legacy network: "designed for the rainfall intensity of 25 mm per hour at low
  tide with run-off coefficient of 0.5" → 25 × 0.5;
* ``C_MAX`` 50 mm/h — the BRIMSTOWAD criteria: "50 mm/hour with run-off coefficient as 1" → 50 × 1.0.
  Only part of the network meets it (CAG: 25 of 53 nullahs upgraded to 50 mm/h, Scroll 2019), hence the
  range by susceptibility;
* ``GATE_CUT`` 0.5 — while the sea outfalls are submerged (Apollo Bunder tide model; ``gate(t)`` is the
  graded ``outfall_restriction`` 0..1, 1 at ≥ 4.5 m) they cannot discharge by gravity and the pumps work
  against the sea: up to half the capacity lost (assumption);
* ``PUMP_FLOOR`` 0.6 — with every pump down a catchment keeps 60 % (gravity paths); availability ``a``
  comes from the pumping-station adapter (EMULATED);
* ``RUNOFF`` 0.85 — dense urban runoff coefficient (assumption; BRIMSTOWAD designs for 1.0 because the
  city is now paved);
* ``CONCENTRATION`` 2 — a low spot collects up to 3× the catchment-average ponding (assumption).

Elevated segments (bridge decks, flyovers) are reported with depth 0 and say why.

Classes: 0 dry (< 2 cm) · 1 shallow (2–10 cm) · 2 deep (10–30 cm: small cars and two-wheelers stall,
ambulances slow, live-wire danger) · 3 impassable (> 30 cm).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

__all__ = [
    "C_MIN", "C_MAX", "GATE_CUT", "PUMP_FLOOR", "RUNOFF", "CONCENTRATION",
    "CLASS_EDGES_CM", "CLASS_BANDS", "CLASS_NAMES", "simulate", "classify", "SegmentRun",
]

C_MIN = 12.5
C_MAX = 50.0
GATE_CUT = 0.5
PUMP_FLOOR = 0.6
RUNOFF = 0.85
CONCENTRATION = 2.0
CLASS_EDGES_CM = (2.0, 10.0, 30.0)
CLASS_BANDS = ("0–2 cm", "2–10 cm", "10–30 cm", "> 30 cm")
CLASS_NAMES = ("dry", "shallow", "deep", "impassable")

#: where C_MIN / C_MAX come from (cited in answers)
CAPACITY_SOURCES = [
    {"what": "legacy design 25 mm/h at low tide, run-off 0.5; BRIMSTOWAD 50 mm/h, run-off 1",
     "ref": "BMC (MCGM) Chief Engineer, Storm Water Drains — RTI manual, chapter 1",
     "url": "https://portal.mcgm.gov.in/irj/go/km/docs/documents/MCGM%20Department%20List/Chief%20Engineer%20"
            "(Storm%20Water%20Drains)/RTI%20Manuals/Ch%20Engineer_SWD_RTI_E01.pdf"},
    {"what": "CAG: drains handle 25 mm/h; 25 of 53 nullahs upgraded to 50 mm/h",
     "ref": "Scroll.in, 2019", "url": "https://scroll.in/latest/929249/scroll_in"},
]

PARAMS = {"C_MIN_mm_h": C_MIN, "C_MAX_mm_h": C_MAX, "GATE_CUT": GATE_CUT, "PUMP_FLOOR": PUMP_FLOOR,
          "RUNOFF": RUNOFF, "CONCENTRATION": CONCENTRATION, "class_edges_cm": list(CLASS_EDGES_CM),
          "capacity_sources": CAPACITY_SOURCES}


@dataclass
class SegmentRun:
    depth_cm: np.ndarray
    water_mm: np.ndarray
    capacity_mm_h: np.ndarray
    classes: np.ndarray


def classify(depth_cm: np.ndarray | float) -> np.ndarray:
    return np.searchsorted(np.array(CLASS_EDGES_CM), np.asarray(depth_cm), side="right")


def simulate(rain_mm_h: np.ndarray, gate_closed: np.ndarray, availability: float, susceptibility: float,
             elevated: bool = False, step_min: int = 15, w0_mm: float = 0.0) -> SegmentRun:
    rain = np.asarray(rain_mm_h, dtype=float)
    gate = np.asarray(gate_closed, dtype=float)
    s = float(np.clip(susceptibility, 0.0, 1.0))
    c_open = C_MAX - (C_MAX - C_MIN) * s
    cap = c_open * (1.0 - GATE_CUT * gate) * (PUMP_FLOOR + (1.0 - PUMP_FLOOR) * float(np.clip(availability, 0, 1)))
    dt = step_min / 60.0
    w = np.empty_like(rain)
    cur = w0_mm
    for i in range(rain.size):
        cur = max(0.0, cur + (RUNOFF * rain[i] - cap[i]) * dt)
        w[i] = cur
    depth = w / 10.0 * (1.0 + CONCENTRATION * s)
    if elevated:
        depth = np.zeros_like(depth)
    return SegmentRun(depth, w, cap, classify(depth))
