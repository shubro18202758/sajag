"""Every modelling assumption of the twin, in one place (MODELLED values).

None of these numbers is a measurement of Mumbai traffic. They are
textbook-range values for a macroscopic model, chosen so the model is
self-consistent, and they are reported back with every result (the
``assumptions`` list) so an officer can see what a proposal stands on.

Units: flows in PCU per hour (passenger-car units), densities in PCU per
km per lane, speeds in km/h unless a name says otherwise.
"""

from __future__ import annotations

from dataclasses import dataclass

#: Saturation flow per lane by OSM road class (PCU/h/lane). Textbook range
#: 1,400-2,000; urban Indian arterials with mixed traffic sit at the lower
#: end, so the values are conservative.
SAT_FLOW_PCU_H_LANE: dict[str, float] = {
    "motorway": 1900.0,
    "trunk": 1800.0,
    "primary": 1800.0,
    "secondary": 1600.0,
    "tertiary": 1400.0,
    "unclassified": 1200.0,
    "residential": 1200.0,
    "service": 1000.0,
}

#: Jam density (PCU/km/lane): about 7 m of road per stopped PCU.
JAM_DENSITY_PCU_KM_LANE = 140.0

#: Free-flow speed = the segment's speed limit times this factor.
FREE_FLOW_FACTOR = 1.0

#: Fallback free-flow speed when a segment has no limit (km/h).
DEFAULT_SPEED_KMH = 40.0

#: Simulation step (s) and the shortest cell (m). A cell is never shorter
#: than one free-flow step (the CFL condition), so dx >= vf * dt.
DT_S = 2.0
MIN_CELL_M = 40.0

#: Share of the flow arriving at a junction that leaves the modelled
#: network for side streets the network does not carry.
SIDE_STREET_EXIT_SHARE = 0.15

#: Turning weights (multiplied by the exit link's target flow): straight on
#: (deflection < 45 deg) versus a turn. U-turns are excluded unless they are
#: the only way out (a dead end on the network boundary).
STRAIGHT_WEIGHT = 1.0
TURN_WEIGHT = 0.6
STRAIGHT_MAX_DEG = 45.0

#: The through-leg rule, matching the platform's own (traffic-oracle
#: enforcement/rules.py ``through_legs``): pairs within 75 deg of straight,
#: scored by class rank minus one rank per 45 deg of bend.
THROUGH_MAX_DEFLECTION_DEG = 75.0
CLASS_RANK: dict[str, int] = {
    "motorway": 6,
    "trunk": 5,
    "primary": 4,
    "secondary": 3,
    "tertiary": 2,
    "unclassified": 1,
    "residential": 1,
    "service": 0,
}

#: Fixed-time template for a crossing the network gives no program
#: (``assumed`` control). Cycle by the dominant class of the through road;
#: lost time and through share follow the network's own osm_assumed seed
#: (cycle 110 = 50 + 42 greens + 18 s lost).
ASSUMED_CYCLE_S: dict[str, int] = {
    "motorway": 110,
    "trunk": 110,
    "primary": 110,
    "secondary": 120,
    "tertiary": 120,
    "unclassified": 120,
    "residential": 120,
    "service": 90,
}
ASSUMED_LOST_S = 18
ASSUMED_THROUGH_SHARE = 0.54

#: A virtual cross street (the network does not carry the cross road of a
#: signalised crossing): 2 lanes of secondary road.
VIRTUAL_CROSS_LANES = 2
VIRTUAL_CROSS_CLASS = "secondary"
#: v/c the cross street runs at under the base program at the profile peak.
VIRTUAL_CROSS_VC = 0.80
#: storage used to normalise its queue for max-pressure (m of road).
VIRTUAL_CROSS_STORAGE_M = 200.0

#: Target volume/capacity at the profile peak (time-of-day factor 1.0), by
#: class. Capacity of a signalised approach is its saturation flow times
#: its green share.
PEAK_VC: dict[str, float] = {
    "motorway": 0.75,
    "trunk": 0.78,
    "primary": 0.80,
    "secondary": 0.75,
    "tertiary": 0.65,
    "unclassified": 0.60,
    "residential": 0.55,
    "service": 0.40,
}

#: Directional peaking: in the evening peak, links heading away from the
#: city centre carry this much more (and links heading in this much less);
#: the morning is the mirror image.
DIRECTIONAL_SPLIT = 0.12
#: The centre used for the directional split (CSMT, cities/mumbai/landmarks.json):
#: the island city's south end, where the morning peak heads.
CBD_LAT = 18.9398
CBD_LON = 72.8355

#: A proposal must cut delay at the focus by at least this much (%), or the
#: twin says "hold": a change an officer has to approve should be worth it.
MIN_GAIN_PCT = 3.0

#: Signal safety bounds used by every generated program.
MIN_GREEN_S = 15
MIN_CYCLE_S = 60
MAX_CYCLE_S = 180

#: Max-pressure runs in its cyclic form: the base program's cycle, phase
#: order, offset and lost time are kept and only the split moves, each
#: cycle, towards the split proportional to the cycle-average phase pressure
#: (sampled every MP_SAMPLE_S; minimum green MIN_GREEN_S).
MP_SAMPLE_S = 10
#: largest change of a phase's green from one cycle to the next (s)
MP_MAX_STEP_S = 4
#: no change while the pressure split is within this of the current one (s)
MP_DEADBAND_S = 2
#: How far from the stop line (and into each exit) the queue is measured (m).
MP_SENSOR_M = 250.0

#: Live demand: the oracle's congestion index (0..1) is read as a
#: volume/capacity proxy, times this factor, clipped to [VC_MIN, VC_MAX].
LIVE_CI_TO_VC = 1.1
LIVE_VC_MIN = 0.15
LIVE_VC_MAX = 1.15
#: Live demand is used only when it covers at least this share of segments.
LIVE_MIN_COVERAGE = 0.5

#: Warm-up before a scenario is measured, so queues at signals reach a
#: cyclic steady state (min).
WARMUP_MIN = 15


@dataclass(frozen=True)
class ClassParams:
    sat_pcu_h_lane: float
    jam_pcu_km_lane: float


def class_params(road_class: str) -> ClassParams:
    return ClassParams(
        sat_pcu_h_lane=SAT_FLOW_PCU_H_LANE.get(road_class, 1400.0),
        jam_pcu_km_lane=JAM_DENSITY_PCU_KM_LANE,
    )


def assumptions_doc() -> list[str]:
    """The assumptions every result carries, in plain words."""
    return [
        "Macroscopic cell-transmission model (Daganzo): flows and queues, not vehicles.",
        "Saturation flow by road class 1,000-1,900 PCU/h/lane; jam density "
        f"{JAM_DENSITY_PCU_KM_LANE:.0f} PCU/km/lane; free-flow speed = the speed limit.",
        "Lanes per direction = half the segment's lanes on a two-way road.",
        f"{int(SIDE_STREET_EXIT_SHARE * 100)}% of arriving traffic leaves to side streets at each "
        "junction; turning ratios assumed (straight 1.0, turn 0.6, weighted by exit flow).",
        "Signal programs are MODELLED templates (osm_assumed), not controller timings; a "
        "crossing with no program gets the same fixed-time template (labelled assumed).",
        "A crossing whose cross road is not in the network gets a virtual 2-lane cross "
        "street so cross-traffic delay is counted.",
        "Green time is effective green; the rest of the cycle is lost time (amber/all-red).",
    ]
