"""Speed ↔ V/C through the traffic-oracle's own BPR-like urban curve (MODELLED).

The oracle's twin (``services/traffic-oracle/src/traffic_oracle/simulation/engine.py``) uses
``v = v_ff / (1 + a·(V/C)^b)`` with a = 0.55, b = 4.2. The oracle stores speed and a congestion index, not
V/C, so for oracle history this module inverts the same curve; for forecasts it maps the V/C quantiles to
speed quantiles. The map is monotone decreasing, so V/C p90 ↦ speed p10 exactly.
"""

from __future__ import annotations

import numpy as np

__all__ = ["BPR_A", "BPR_B", "speed_from_vc", "vc_from_speed", "VC_MAX"]

BPR_A = 0.55
BPR_B = 4.2
#: V/C is reported up to this value (queued traffic; the curve flattens beyond it)
VC_MAX = 2.0


def speed_from_vc(vc, free_flow_kmh: float):
    vc = np.clip(np.asarray(vc, dtype=float), 0.0, VC_MAX)
    return free_flow_kmh / (1.0 + BPR_A * vc ** BPR_B)


def vc_from_speed(speed, free_flow_kmh: float):
    s = np.clip(np.asarray(speed, dtype=float), 0.5, None)
    ratio = np.clip(free_flow_kmh / s, 1.0, None)
    return np.clip(((ratio - 1.0) / BPR_A) ** (1.0 / BPR_B), 0.0, VC_MAX)
