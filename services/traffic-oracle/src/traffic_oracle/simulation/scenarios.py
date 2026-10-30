"""Named scenario library for the VVIP corridor twin.

Fourteen seedable, reproducible scenarios on the city's own Mumbai seed
network, plus the city's use-case scenarios (same segment IDs the DB and the frozen impact harness
``scripts/impact_run.py`` parse from ``sample_corridor.sql``). Each scenario
fixes: route, departure clock, VVIP class, closure policy, horizon, weather,
event-rate overrides, and any schedule-forced events (rallies, planted
breakdowns). Every run of a scenario with the same seed reproduces
bit-identical metrics.

The three mandated anchors are present:
    - ``monsoon_evening_peak``          (monsoon evening)
    - ``multi_event_collision_sealdah`` (multi-event collision; the id is kept
      for compatibility — the scenario is Hindmata and Dadar TT)
    - ``zplus_airport_morning_peak``    (Z+ at peak)

Consumption contract for the impact harness: ``export_library()`` /
``python -m traffic_oracle.simulation export`` emits
``VVIP/scripts/scenario_library.json`` whose ``network`` block carries the
same segment/lane/speed facts the harness parses from the seed and whose
``scenarios[].closure_policy`` / demand parameters map onto
``impact_run.commuter_delay_min(hold_min, lambda_per_min, n_junctions)``.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from traffic_oracle.simulation.events import EventConfig, EventType, ScheduledEvent
from traffic_oracle.simulation.network import default_network
from traffic_oracle.simulation.tod import WeatherState


@dataclass(frozen=True)
class ScenarioSpec:
    """One named, reproducible scenario of the corridor twin."""

    scenario_id: str
    name: str
    description: str
    category: str                     # baseline | weather | event | multi_event | ops
    route_segment_ids: tuple[int, ...]
    departure_time: str               # ISO-8601 (local, IST offset in the stamp)
    vvip_class: str                   # 'Z+' | 'Z' | 'Y' | 'X' | 'none'
    closure_policy: dict
    horizon_min: int
    n_replications: int
    seed: int
    convoy_speed_kmh: float = 60.0
    weather: dict = field(default_factory=dict)
    event_overrides: dict = field(default_factory=dict)
    forced_events: tuple[dict, ...] = ()
    expected_features: tuple[str, ...] = ()
    # Event-agnostic extension (additive; defaults keep every pre-existing
    # scenario byte-identical in behavior):
    event_kind: str = "protected_movement"   # one of the 8 archetypes
    crowd_class: str = "LOW"                 # LOW | MEDIUM | HIGH | EXTREME
    duration_class: str = "minutes"          # minutes | hours | multi_day | multi_week

    # ── derived views ─────────────────────────────────────────────────
    def departure_dt(self) -> datetime:
        return datetime.fromisoformat(self.departure_time)

    def weather_state(self) -> WeatherState:
        return WeatherState(
            monsoon=bool(self.weather.get("monsoon", False)),
            rain_intensity_mm_h=float(self.weather.get("rain_intensity_mm_h", 0.0)),
            fog=bool(self.weather.get("fog", False)),
        )

    def event_config(self) -> EventConfig:
        return EventConfig(
            breakdown_rate_multiplier=float(self.event_overrides.get("breakdown", 1.0)),
            waterlogging_rate_multiplier=float(self.event_overrides.get("waterlogging", 1.0)),
            signal_fault_rate_multiplier=float(self.event_overrides.get("signal_fault", 1.0)),
            market_rate_multiplier=float(self.event_overrides.get("market", 1.0)),
            rally_rate_multiplier=float(self.event_overrides.get("rally", 0.0)),
            # Sixth override (007 / contract C4): ambulance Poisson knob.
            ambulance_rate_multiplier=float(self.event_overrides.get("ambulance", 1.0)),
        )

    def scheduled_events(self) -> list[ScheduledEvent]:
        out: list[ScheduledEvent] = []
        for fe in self.forced_events:
            out.append(
                ScheduledEvent(
                    event_type=EventType(fe["type"]),
                    segment_id=int(fe["segment_id"]),
                    start_sec=float(fe["start_sec"]),
                    duration_sec=float(fe["duration_sec"]),
                    severity=float(fe.get("severity", 0.7)),
                    label=str(fe.get("label", "")),
                    extra_demand_veh_h=float(fe.get("extra_demand_veh_h", 0.0)) or 0.0,
                )
            )
        return out

    def to_dict(self) -> dict:
        return {
            "scenario_id": self.scenario_id,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "route_segment_ids": list(self.route_segment_ids),
            "departure_time": self.departure_time,
            "vvip_class": self.vvip_class,
            "closure_policy": dict(self.closure_policy),
            "horizon_min": self.horizon_min,
            "n_replications": self.n_replications,
            "seed": self.seed,
            "convoy_speed_kmh": self.convoy_speed_kmh,
            "weather": dict(self.weather),
            "event_overrides": dict(self.event_overrides),
            "forced_events": [dict(e) for e in self.forced_events],
            "expected_features": list(self.expected_features),
            "event_kind": self.event_kind,
            "crowd_class": self.crowd_class,
            "duration_class": self.duration_class,
        }


# ── The library ────────────────────────────────────────────────────────────

SCENARIO_LIBRARY: dict[str, ScenarioSpec] = {}


def _register(s: ScenarioSpec) -> ScenarioSpec:
    if s.scenario_id in SCENARIO_LIBRARY:
        raise ValueError(f"duplicate scenario_id {s.scenario_id!r}")
    SCENARIO_LIBRARY[s.scenario_id] = s
    return s


# Dr Ambedkar Road spine used by several scenarios
# (Hindmata J19 -> Dadar TT Circle J20 -> Kings Circle J21 -> Sion Hospital J22).
_AMBEDKAR_SPINE = (1066, 1067, 1068)

_register(ScenarioSpec(
    scenario_id="baseline_weekday_midday",
    name="Baseline Weekday Midday",
    description=(
        "Z-class movement along the Dr Ambedkar Road spine (Hindmata by "
        "Dadar TT and Kings Circle to Sion Hospital) on a quiet Tuesday early "
        "afternoon — the reference case: default event rates, no weather, "
        "standard 120 s rolling closure."
    ),
    category="baseline",
    route_segment_ids=_AMBEDKAR_SPINE,
    departure_time="2026-10-13T13:40:00+05:30",
    vvip_class="Z",
    closure_policy={"advance_closure_sec": 120, "closure_type": "full_closure"},
    horizon_min=45,
    n_replications=8,
    seed=20261013,
    expected_features=("moderate_demand", "rolling_closure", "reference_case"),
))

_register(ScenarioSpec(
    scenario_id="monsoon_evening_peak",
    name="Monsoon Evening Peak",
    description=(
        "MANDATED ANCHOR — monsoon evening. Z+ airport arrival into the city "
        "at 18:30 in active monsoon (18 mm/h rain): from Airport T2 down the "
        "Western Express Highway to Kalanagar, BKC Road to Kurla, LBS Marg to "
        "Sion and Dr Ambedkar Road to Kings Circle — the Kings Circle stretch "
        "(1068) waterlogs on schedule and evening-peak demand plus "
        "weather-damped free-flow make this the worst single-weather case."
    ),
    category="weather",
    route_segment_ids=(1020, 1015, 1014, 1052, 1053, 1038, 1043, 1069, 1068),
    departure_time="2026-07-21T18:30:00+05:30",
    vvip_class="Z+",
    closure_policy={"advance_closure_sec": 180, "closure_type": "full_closure"},
    horizon_min=60,
    n_replications=10,
    seed=20260721,
    convoy_speed_kmh=50.0,
    weather={"monsoon": True, "rain_intensity_mm_h": 18.0},
    event_overrides={"waterlogging": 2.5, "breakdown": 1.4},
    forced_events=(
        {"type": "waterlogging", "segment_id": 1068, "start_sec": 300.0,
         "duration_sec": 2700.0, "severity": 0.7,
         "label": "Kings Circle (Gandhi Market) waterlogged — 45 min pump-out"},
    ),
    expected_features=("monsoon", "evening_peak", "waterlogging_prone", "low_visibility_speed"),
))

_register(ScenarioSpec(
    scenario_id="multi_event_collision_sealdah",
    name="Multi-Event Collision at Hindmata and Dadar TT",
    description=(
        "MANDATED ANCHOR — multi-event collision. A Z movement up Dr Ambedkar "
        "Road from Parel by Hindmata and Dadar TT to Kings Circle at 17:50 "
        "Friday while a double-lane breakdown blocks the Hindmata - Dadar TT "
        "stretch, a signal fault collapses the Hindmata greens, and a monsoon "
        "shower waterlogs Hindmata — three simultaneous capacity hits on one "
        "junction complex, all on the convoy's path."
    ),
    category="multi_event",
    route_segment_ids=(1065, 1066, 1067),
    departure_time="2026-08-14T17:50:00+05:30",
    vvip_class="Z",
    closure_policy={"advance_closure_sec": 150, "closure_type": "full_closure"},
    horizon_min=60,
    n_replications=12,
    seed=20260814,
    weather={"monsoon": True, "rain_intensity_mm_h": 9.0},
    event_overrides={"waterlogging": 1.5, "signal_fault": 1.2},
    forced_events=(
        {"type": "vehicle_breakdown", "segment_id": 1066, "start_sec": 240.0,
         "duration_sec": 2100.0, "severity": 0.85,
         "label": "truck breakdown blocking 2 lanes on Dr Ambedkar Road at Hindmata"},
        {"type": "signal_fault", "segment_id": 1065, "start_sec": 480.0,
         "duration_sec": 1500.0, "severity": 0.8,
         "label": "Hindmata signal controller fault — flashing amber"},
        {"type": "waterlogging", "segment_id": 1066, "start_sec": 900.0,
         "duration_sec": 2400.0, "severity": 0.65,
         "label": "waterlogged Dr Ambedkar Road approach to Dadar TT"},
    ),
    expected_features=("multi_event", "simultaneous_capacity_loss", "friday_peak",
                       "long_recovery"),
))

_register(ScenarioSpec(
    scenario_id="zplus_airport_morning_peak",
    name="Z+ Airport Run at Morning Peak",
    description=(
        "MANDATED ANCHOR — Z+ at peak. A run from Mantralaya to Airport T2 at "
        "08:45 Monday: maximum protocol closure (180 s advance), full closure "
        "type, morning-peak demand on Marine Drive, the Coastal Road, the "
        "Sea Link and the Western Express Highway, plus the Monday commute "
        "peak in full swing."
    ),
    category="baseline",
    route_segment_ids=(1001, 1002, 1006, 1008, 1011, 1013, 1014, 1015, 1020),
    departure_time="2026-10-12T08:45:00+05:30",
    vvip_class="Z+",
    closure_policy={"advance_closure_sec": 180, "closure_type": "full_closure"},
    horizon_min=45,
    n_replications=10,
    seed=20261012,
    expected_features=("zplus_protocol", "morning_peak", "full_closure"),
))

_register(ScenarioSpec(
    scenario_id="sunday_market_spillover",
    name="Sunday Market Spillover (Dadar)",
    description=(
        "Y-class run along Senapati Bapat Marg into Dadar West and up Ranade "
        "Road and Lady Jamshetji Road to Mahim at 11:00 Sunday: market "
        "spillover demand saturates the Dadar market stretch while Sunday "
        "shoppers queue at the crossings."
    ),
    category="event",
    route_segment_ids=(1072, 1073, 1021),
    departure_time="2026-10-18T11:00:00+05:30",
    vvip_class="Y",
    closure_policy={"advance_closure_sec": 90, "closure_type": "partial_closure"},
    horizon_min=45,
    n_replications=8,
    seed=20261018,
    event_overrides={"market": 2.2},
    expected_features=("market_spillover", "sunday_demand", "narrow_roads"),
))

_register(ScenarioSpec(
    scenario_id="rally_saturday_evening",
    name="Scheduled Exhibition Spillover at BKC, Saturday Evening",
    description=(
        "A scheduled exhibition at the BKC grounds at 17:00 Saturday pours "
        "900 veh/h of extra arrivals onto the BKC Road while a Z-class "
        "movement runs from Kalanagar to Kurla in the opposite shoulder of "
        "the evening peak."
    ),
    category="event",
    route_segment_ids=(1052, 1053, 1039),
    departure_time="2026-10-17T17:00:00+05:30",
    vvip_class="Z",
    closure_policy={"advance_closure_sec": 120, "closure_type": "full_closure"},
    horizon_min=60,
    n_replications=10,
    seed=20261017,
    forced_events=(
        {"type": "rally_spillover", "segment_id": 1052, "start_sec": 0.0,
         "duration_sec": 5400.0, "severity": 0.8,
         "extra_demand_veh_h": 900.0,
         "label": "exhibition at the BKC grounds — visitor parking spillover"},
        {"type": "rally_spillover", "segment_id": 1053, "start_sec": 600.0,
         "duration_sec": 4800.0, "severity": 0.6,
         "extra_demand_veh_h": 500.0,
         "label": "exhibition dispersal onto the BKC Road eastbound"},
    ),
    expected_features=("scheduled_rally", "saturday_evening", "demand_surge"),
))

_register(ScenarioSpec(
    scenario_id="signal_fault_friday_peak",
    name="Signal Faults at Friday Peak",
    description=(
        "Signal-controller faults at Santacruz and the Linking Road crossing "
        "during the Friday 18:00 peak while an X-class medical convoy runs SV "
        "Road from Bandra to Andheri (Cooper Hospital at Irla) — tests "
        "green-ratio collapse under saturated demand without any physical "
        "blockage."
    ),
    category="ops",
    route_segment_ids=(1023, 1024, 1025, 1026),
    departure_time="2026-10-16T18:00:00+05:30",
    vvip_class="X",
    closure_policy={"advance_closure_sec": 60, "closure_type": "signal_hold"},
    horizon_min=45,
    n_replications=8,
    seed=20261016,
    event_overrides={"signal_fault": 3.0},
    forced_events=(
        {"type": "signal_fault", "segment_id": 1024, "start_sec": 300.0,
         "duration_sec": 1800.0, "severity": 0.75,
         "label": "Santacruz (SV Road, Juhu Tara Road) controller fault — flashing red"},
        {"type": "signal_fault", "segment_id": 1025, "start_sec": 900.0,
         "duration_sec": 1500.0, "severity": 0.6,
         "label": "Linking Road crossing detector fault — stuck green one side"},
    ),
    expected_features=("signal_fault", "friday_peak", "capacity_loss_without_blockage"),
))

_register(ScenarioSpec(
    scenario_id="night_owl_low_demand",
    name="Night Owl — Low Demand",
    description=(
        "X-class run at 02:30 Wednesday night: near-empty roads, minimal "
        "disruption, quick recovery — the floor case that calibrates how much "
        "of peak-hour delay is demand-driven rather than closure-driven."
    ),
    category="baseline",
    route_segment_ids=_AMBEDKAR_SPINE,
    departure_time="2026-10-14T02:30:00+05:30",
    vvip_class="X",
    closure_policy={"advance_closure_sec": 60, "closure_type": "full_closure"},
    horizon_min=30,
    n_replications=6,
    seed=20261014,
    expected_features=("low_demand", "fast_recovery", "floor_case"),
))

_register(ScenarioSpec(
    scenario_id="monsoon_morning_commute",
    name="Monsoon Morning Commute (Eastern Express Highway)",
    description=(
        "Y-class run south on the Eastern Express Highway from Ghatkopar by "
        "Chheda Nagar and Amar Mahal to Sion at 09:00 in moderate monsoon "
        "rain (8 mm/h) — morning-peak demand on the arterial with "
        "weather-damped free-flow and elevated breakdown rates."
    ),
    category="weather",
    route_segment_ids=(1047, 1046, 1045, 1044),
    departure_time="2026-08-11T09:00:00+05:30",
    vvip_class="Y",
    closure_policy={"advance_closure_sec": 90, "closure_type": "partial_closure"},
    horizon_min=45,
    n_replications=8,
    seed=20260811,
    weather={"monsoon": True, "rain_intensity_mm_h": 8.0},
    event_overrides={"breakdown": 1.6, "waterlogging": 1.2},
    expected_features=("monsoon", "morning_peak", "arterial_demand"),
))

_register(ScenarioSpec(
    scenario_id="breakdown_vip_road",
    name="Multi-Lane Breakdown on the Western Express Highway",
    description=(
        "Z-class run on the Western Express Highway from Vakola towards "
        "Jogeshwari when a truck loses two lanes for 35 minutes mid-route "
        "near Vile Parle — tests partial-capacity closures interacting with "
        "a rolling convoy window."
    ),
    category="event",
    route_segment_ids=(1015, 1016, 1017),
    departure_time="2026-10-15T16:30:00+05:30",
    vvip_class="Z",
    closure_policy={"advance_closure_sec": 120, "closure_type": "full_closure"},
    horizon_min=45,
    n_replications=8,
    seed=20261015,
    forced_events=(
        {"type": "vehicle_breakdown", "segment_id": 1016, "start_sec": 420.0,
         "duration_sec": 2100.0, "severity": 0.9,
         "label": "truck breakdown on the WEH near Vile Parle — 2 lanes blocked"},
    ),
    expected_features=("forced_breakdown", "partial_capacity", "arterial_speed"),
))

_register(ScenarioSpec(
    scenario_id="stadium_match_evening",
    name="Match Night at Wankhede Stadium",
    description=(
        "Cricket match dispersal at Wankhede Stadium: a scheduled spillover "
        "of 1100 veh/h onto Marine Drive beside the stadium at 20:15 while a "
        "Z-class movement brings a dignitary out from Churchgate along the "
        "same corridor towards Marine Lines."
    ),
    category="event",
    route_segment_ids=(1004, 1002),
    departure_time="2026-10-19T20:15:00+05:30",
    vvip_class="Z",
    closure_policy={"advance_closure_sec": 120, "closure_type": "full_closure"},
    horizon_min=60,
    n_replications=10,
    seed=20261019,
    forced_events=(
        {"type": "rally_spillover", "segment_id": 1002, "start_sec": 0.0,
         "duration_sec": 3600.0, "severity": 0.85,
         "extra_demand_veh_h": 1100.0,
         "label": "post-match dispersal surge"},
    ),
    expected_features=("scheduled_surge", "stadium_adjacency", "night_peak"),
))

_register(ScenarioSpec(
    scenario_id="fog_winter_morning",
    name="Winter Haze Morning",
    description=(
        "X-class run north over the Bandra-Worli Sea Link and its Bandra "
        "approach at 07:30 in late-December haze (the twin's low-visibility "
        "mode): visibility caps urban free-flow at ~55% and shifts the "
        "morning peak later; tests weather speed caps without rain or events."
    ),
    category="weather",
    route_segment_ids=(1008, 1011),
    departure_time="2026-12-22T07:30:00+05:30",
    vvip_class="X",
    closure_policy={"advance_closure_sec": 60, "closure_type": "partial_closure"},
    horizon_min=45,
    n_replications=8,
    seed=20261222,
    weather={"monsoon": False, "fog": True},
    expected_features=("fog_speed_cap", "winter_morning", "weather_only"),
))

_register(ScenarioSpec(
    scenario_id="friday_market_evening",
    name="Friday Market Evening (Crawford Market, Mohammed Ali Road)",
    description=(
        "Friday 19:00 run from CSMT over the JJ Flyover past Crawford Market "
        "and Mohammed Ali Road and down Sir JJ Road to Byculla: late-shopping "
        "market spillover combines with the extended Friday evening peak; "
        "the signal_hold policy variant shows the lighter-touch closure "
        "option under sustained demand."
    ),
    category="event",
    route_segment_ids=(1061, 1062),
    departure_time="2026-10-16T19:00:00+05:30",
    vvip_class="Y",
    closure_policy={"advance_closure_sec": 90, "closure_type": "signal_hold"},
    horizon_min=45,
    n_replications=8,
    seed=20261016,
    event_overrides={"market": 1.8},
    forced_events=(
        {"type": "market_spillover", "segment_id": 1061, "start_sec": 0.0,
         "duration_sec": 3000.0, "severity": 0.6,
         "label": "Friday shopping spillover around Crawford Market and Mohammed Ali Road"},
    ),
    expected_features=("friday_late_peak", "market_spillover", "signal_hold_policy"),
))

_register(ScenarioSpec(
    scenario_id="republic_day_parade_morning",
    name="Republic Day Parade Morning",
    description=(
        "Jan 26 morning: the scheduled state parade at Shivaji Park, Dadar "
        "(staged, 09:00–10:30) plus holiday-morning demand shape; a Z-class "
        "movement reaches the parade ground from Worli by Lower Parel and "
        "Dadar West through the tail of the parade window."
    ),
    category="event",
    route_segment_ids=(1074, 1072, 1073),
    departure_time="2027-01-26T09:15:00+05:30",
    vvip_class="Z",
    closure_policy={"advance_closure_sec": 150, "closure_type": "full_closure"},
    horizon_min=60,
    n_replications=10,
    seed=20270126,
    forced_events=(
        {"type": "rally_spillover", "segment_id": 1073, "start_sec": 0.0,
         "duration_sec": 4500.0, "severity": 0.75,
         "extra_demand_veh_h": 700.0,
         "label": "Republic Day parade at Shivaji Park — spectators and parking"},
    ),
    expected_features=("holiday_demand", "scheduled_parade", "morning_peak_tail"),
))


# ── The city's use-case scenarios: the twin's copy of the event emulator's
# use-case library configs (use_case_scenarios.json, re-synced by
# scripts/city_build.py).  The VIP movement base case is the reference every
# other use case generalizes; the others exercise the public-event archetypes
# on the same corridor network.
# ────────────────────────────────────────────────────────────────────────────

USE_CASE_FILE = Path(os.environ.get("SAJAG_TWIN_USE_CASES")
                     or Path(__file__).with_name("use_case_scenarios.json"))


def _load_use_cases(path: Path = USE_CASE_FILE) -> tuple[str, ...]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    ids = []
    for row in doc["scenarios"]:
        _register(ScenarioSpec(
            scenario_id=str(row["scenario_id"]),
            name=str(row["name"]),
            description=str(row["description"]),
            category=str(row["category"]),
            route_segment_ids=tuple(int(s) for s in row["route_segment_ids"]),
            departure_time=str(row["departure_time"]),
            vvip_class=str(row["vvip_class"]),
            closure_policy=dict(row["closure_policy"]),
            horizon_min=int(row["horizon_min"]),
            n_replications=int(row["n_replications"]),
            seed=int(row["seed"]),
            convoy_speed_kmh=float(row.get("convoy_speed_kmh", 60.0)),
            weather=dict(row.get("weather") or {}),
            event_overrides=dict(row.get("event_overrides") or {}),
            forced_events=tuple(dict(e) for e in row.get("forced_events") or ()),
            expected_features=tuple(row.get("expected_features") or ()),
            event_kind=str(row.get("event_kind", "protected_movement")),
            crowd_class=str(row.get("crowd_class", "LOW")),
            duration_class=str(row.get("duration_class", "minutes")),
        ))
        ids.append(str(row["scenario_id"]))
    return tuple(ids)


#: the use-case scenario ids, in the library's order
USE_CASE_IDS: tuple[str, ...] = _load_use_cases()


# ── Library access API ─────────────────────────────────────────────────────

def list_scenarios() -> list[str]:
    """Scenario IDs in registration order."""
    return list(SCENARIO_LIBRARY.keys())


def get_scenario(scenario_id: str) -> ScenarioSpec:
    try:
        return SCENARIO_LIBRARY[scenario_id]
    except KeyError:
        raise KeyError(
            f"unknown scenario {scenario_id!r}; available: {list_scenarios()}"
        ) from None


def library_summary() -> list[dict]:
    return [
        {
            "scenario_id": s.scenario_id,
            "name": s.name,
            "category": s.category,
            "vvip_class": s.vvip_class,
            "departure_time": s.departure_time,
            "route_segment_ids": list(s.route_segment_ids),
            "seed": s.seed,
            "expected_features": list(s.expected_features),
        }
        for s in SCENARIO_LIBRARY.values()
    ]


def export_library(*, include_network: bool = True) -> dict:
    """Serializable form of the whole library (+ network facts for consumers).

    The JSON emitted from this dict is the artifact ``scripts/impact_run.py``
    consumes: segment facts match its own seed parse, and closure/demand
    parameters map onto ``commuter_delay_min(hold_min, lam, n_junctions)``.
    """
    network = default_network()
    return {
        "format": "sajag/scenario-library/1",
        "generator": "traffic_oracle.simulation.scenarios.export_library",
        "attribution": "network facts from the seed's roads on OpenStreetMap — "
                       "(c) OpenStreetMap contributors, ODbL 1.0",
        "n_scenarios": len(SCENARIO_LIBRARY),
        "scenarios": [s.to_dict() for s in SCENARIO_LIBRARY.values()],
        **({"network": network.to_dict()} if include_network else {}),
    }
