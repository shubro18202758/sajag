"""Use-case emulation profiles — one per Mumbai scenario (emulatorContract).

A profile is pure cause-side interpretation of a UseCaseLibrary config: the
event_kind archetype, the crowd script, the weather onset ramp, any
profile-added scheduled causes (EMERGENCY_VEHICLE green-corridor requests,
the base case's planted breakdown), and the ambulance-delay projection the
escalation engine reads.  Profiles NEVER select code paths in the real stack
and never carry outcomes — only exogenous cause shape.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from event_emulator.city import STOLEN_FIR_REF
from event_emulator.mumbai_network import PROFILE_SEGMENTS

__all__ = ["UseCaseProfile", "PROFILES", "EVENT_KINDS"]

# The archetypes (domain-model axis 3); they select closure-policy and
# dossier TEMPLATES downstream, never emulator code paths.  crime_incident
# and vehicle_pursuit are the watchlist-anpr additions; the last six are the
# OSINT reported-situation kinds (contract C3 lockstep: migrations 010 and
# 021's CHECK relaxations + traffic_oracle events.EVENT_KINDS mirror this
# tuple exactly).  No profile uses the OSINT kinds: a reported situation
# enters only through a named officer's promotion, never the emulator.
EVENT_KINDS = (
    "protected_movement",
    "procession",
    "mass_gathering",
    "race",
    "ceremonial",
    "egress_surge",
    "emergency_evacuation",
    "work_zone",
    # watchlist-anpr additions (010, C3):
    "crime_incident",
    "vehicle_pursuit",
    # OSINT reported-situation additions (021, C3; lockstep only):
    "reported_crime",
    "public_disorder",
    "road_accident",
    "hazard",
    "flooding",
    "infra_failure",
)


@dataclass(frozen=True)
class UseCaseProfile:
    """Cause-side interpretation of one use case."""

    event_kind: str
    crowd_class: str                       # LOW | MEDIUM | HIGH | EXTREME
    crowd_waypoints: tuple[tuple[float, float], ...]   # (t_sec, score 0..1)
    weather_onset_sec: float = 0.0         # ramp-up time to steady severity
    weather_steady_severity: float = 0.0
    weather_code: str | None = None        # explicit code key (C3), or None
    # profile-added scheduled causes beyond the config's forced_events
    extra_events: tuple[dict, ...] = field(default_factory=tuple)
    # ambulance delay projection (escalation side-input) while an
    # EMERGENCY_VEHICLE window is active: decays base → cleared
    ambulance_base_sec: float = 0.0
    ambulance_cleared_sec: float = 0.0
    # ── watchlist knobs (watchlist-anpr stream, contract C2) ────────────
    # Drive the tape's anpr_read / agency_unit generators: how many
    # registered mid-block ANPR sweep cameras watch the route, how many
    # stop-line approach cameras the fleeing vehicle runs a red at, how
    # much background traffic they read, and whether the scenario drives
    # the FIR-named stolen plate and/or the earmark-exercise plate through
    # them.  Causes only — the oracle's ANPR seam computes every hit (from
    # its own earmarks) and every rule outcome; the tape never asserts one.
    anpr_cameras: int = 0
    anpr_stopline_cameras: int = 0
    anpr_background_vehicles: int = 0
    anpr_stolen_plate_hit: bool = False
    anpr_earmarked_plate_hit: bool = False
    agency_units: int = 0
    # The FIR the scenario's premise names (C-N): a use case that drives
    # its FIR-named stolen plate states, at t0, that the plate IS reported
    # stolen — an EMULATED scenario precondition earmark (lawful basis
    # stolen_vehicle_fir) through the oracle's own earmark API, so its reads
    # are evidence-only sightings and never a fine to the theft victim.
    # The use-case config's ``stolen_fir_ref`` wins when it carries one.
    anpr_stolen_fir_ref: str | None = None


_BASE_EV = {
    "type": "emergency_vehicle",
    "severity": 0.9,
}

#: The Mumbai network segments the profile-added causes sit on (ids of the
#: city network, mumbai_network.PROFILE_SEGMENTS; the tests check each one
#: is the named road and, where it says so, on its use case's route).
_WEH_VAKOLA = PROFILE_SEGMENTS["weh_vakola"]                          # WEH, Vakola–Sahar
_MARINE_DRIVE_WANKHEDE = PROFILE_SEGMENTS["marine_drive_wankhede"]    # Wankhede gates
_DN_ROAD_CSMT = PROFILE_SEGMENTS["dn_road_csmt"]                      # D N Road to CSMT
_AMBEDKAR_HINDMATA = PROFILE_SEGMENTS["dr_ambedkar_hindmata"]         # Hindmata
_AMBEDKAR_SION = PROFILE_SEGMENTS["dr_ambedkar_sion"]                 # Sion
_SWEEP_ROADSIDE = PROFILE_SEGMENTS["sweep_market_road"]               # WEH, sweep stretch

PROFILES: dict[str, UseCaseProfile] = {
    # BASE CASE — Z+ run Mantralaya -> Mumbai Airport T2, LOW crowd, one
    # planted breakdown (contract) on the Western Express Highway.
    "vvip_convoy_base": UseCaseProfile(
        event_kind="protected_movement",
        crowd_class="LOW",
        crowd_waypoints=((0, 0.08), (900, 0.15), (1800, 0.12), (2700, 0.10)),
        extra_events=(
            {
                "type": "vehicle_breakdown",
                "segment_id": _WEH_VAKOLA,
                "start_sec": 600,
                "duration_sec": 900,
                "severity": 0.6,
                "label": "planted breakdown — goods vehicle stalled on the Western Express Highway "
                         "(base-case cause)",
            },
        ),
    ),
    # FLAGSHIP multi-event composition — Anant Chaturdashi visarjan night:
    # processions from Lalbaug to Girgaon Chowpatty and the Lalbaugcha Raja
    # crowd (EXTREME crowd building through the window, festival stalls via
    # event_overrides.market, heavy vehicles off the roads via
    # event_overrides.breakdown) + one siren: the ambulance (108)
    # green-corridor windows to JJ Hospital ride the config's forced_events;
    # the ambulance-delay projection decays base -> cleared while a window
    # runs (the escalation channel the engine reads).  No weather.
    "ganesh_visarjan_girgaon": UseCaseProfile(
        event_kind="mass_gathering",
        crowd_class="EXTREME",
        crowd_waypoints=((0, 0.62), (1200, 0.9), (2400, 0.93), (3600, 0.88)),
        ambulance_base_sec=150.0,
        ambulance_cleared_sec=20.0,
    ),
    # Heavy burst at high tide — weather ramp (100 mm/h -> severity 1.0 after
    # a short 300 s onset: a burst arrives fast, RAIN code), waterlogging at
    # Hindmata, King's Circle, Sion and the subways in the config's
    # forced_events, and ambulance (108) windows to KEM and Sion Hospital
    # through the water + the delay projection (relief
    # per C4: scheduled EMERGENCY_VEHICLE + projection inputs).
    "cloudburst_high_tide": UseCaseProfile(
        event_kind="emergency_evacuation",
        crowd_class="MEDIUM",
        crowd_waypoints=((0, 0.35), (1200, 0.45), (3600, 0.40)),
        weather_onset_sec=300.0,
        weather_steady_severity=1.0,      # 100 mm/h -> min(1, 100/30)
        weather_code="RAIN",
        extra_events=(
            {
                **_BASE_EV,
                "segment_id": _AMBEDKAR_HINDMATA,
                "start_sec": 900,
                "duration_sec": 1200,
                "label": "ambulance (108) window through the water at Hindmata, towards KEM Hospital",
            },
            {
                **_BASE_EV,
                "segment_id": _AMBEDKAR_SION,
                "start_sec": 1800,
                "duration_sec": 1200,
                "severity": 0.85,
                "label": "ambulance (108) window along Dr Ambedkar Road to Sion Hospital",
            },
        ),
        ambulance_base_sec=180.0,
        ambulance_cleared_sec=30.0,
    ),
    # Cyclone recovery — residual squalls (STORM, steady from t0), tree-fall
    # lane losses with staggered clearance (staged reopening) in forced_events.
    "cyclone_landfall_recovery": UseCaseProfile(
        event_kind="work_zone",
        crowd_class="LOW",
        crowd_waypoints=((0, 0.10), (1800, 0.16), (3600, 0.22)),
        weather_onset_sec=1.0,
        weather_steady_severity=0.55,
        weather_code="STORM",
        ambulance_base_sec=150.0,
        ambulance_cleared_sec=25.0,
    ),
    # Wankhede — night egress surge + two ambulance (108) green-corridor
    # requests fighting the dispersal wave (the showcase's emergency channel).
    "wankhede_egress": UseCaseProfile(
        event_kind="egress_surge",
        crowd_class="EXTREME",
        crowd_waypoints=((0, 0.75), (600, 0.95), (2400, 0.62), (3600, 0.35)),
        extra_events=(
            {
                **_BASE_EV,
                "segment_id": _MARINE_DRIVE_WANKHEDE,
                "start_sec": 300,
                "duration_sec": 1200,
                "label": "green-corridor request — ambulance (108) through the dispersal wave",
            },
            {
                **_BASE_EV,
                "segment_id": _DN_ROAD_CSMT,
                "start_sec": 1500,
                "duration_sec": 900,
                "severity": 0.8,
                "label": "second green-corridor request — ambulance (108) along D N Road "
                         "towards CSMT against the wave",
            },
        ),
        ambulance_base_sec=120.0,
        ambulance_cleared_sec=15.0,
    ),
    # Bandra — the station's evening surge + a bus broken down on the Sea
    # Link (both in forced_events); HIGH crowd on the approach.
    "sea_link_breakdown_surge": UseCaseProfile(
        event_kind="egress_surge",
        crowd_class="HIGH",
        crowd_waypoints=((0, 0.55), (900, 0.72), (2400, 0.68), (3600, 0.50)),
    ),
    # Shivaji Park — Z tier ceremonial ground, spectator load on the approaches.
    "shivaji_park_parade": UseCaseProfile(
        event_kind="ceremonial",
        crowd_class="HIGH",
        crowd_waypoints=((0, 0.50), (900, 0.65), (1800, 0.55), (3600, 0.40)),
    ),
    # Gateway and the ferry wharf — holiday crowds and ferry queues; HIGH crowd.
    "gateway_ferry_transit": UseCaseProfile(
        event_kind="mass_gathering",
        crowd_class="HIGH",
        crowd_waypoints=((0, 0.70), (1800, 0.78), (3600, 0.72)),
    ),
    # Marathon — staged crossings, rolling reopen behind the sweep.
    "mumbai_marathon": UseCaseProfile(
        event_kind="race",
        crowd_class="HIGH",
        crowd_waypoints=((0, 0.60), (600, 0.72), (2400, 0.50), (3600, 0.30)),
    ),
    # New Year's Eve on Marine Drive — EXTREME crowd peaking at midnight.
    "marine_drive_new_year": UseCaseProfile(
        event_kind="mass_gathering",
        crowd_class="EXTREME",
        crowd_waypoints=((0, 0.70), (2700, 0.95), (3600, 0.80)),
        ambulance_base_sec=120.0,
        ambulance_cleared_sec=20.0,
    ),
    # Metro works on LBS Marg — a published multi-week lane loss; the run
    # window sees the standing pinch plus the Kurla market's squeezed
    # traffic (both in forced_events).
    "metro_work_zone": UseCaseProfile(
        event_kind="work_zone",
        crowd_class="LOW",
        crowd_waypoints=((0, 0.18), (1800, 0.22), (3600, 0.20)),
    ),
    # WEH crash — a lane-loss crash and the ambulance (108) windows to Cooper
    # Hospital (forced_events, one per route segment, timed on the roads).
    "weh_crash_ambulance": UseCaseProfile(
        event_kind="emergency_evacuation",
        crowd_class="LOW",
        crowd_waypoints=((0, 0.12), (1200, 0.15), (2700, 0.12)),
        ambulance_base_sec=150.0,
        ambulance_cleared_sec=20.0,
    ),
    # WATCHLIST (watchlist-anpr stream) — a stolen-vehicle FIR drives an
    # emulated ANPR camera sweep of the western suburbs (WEH).  The corridor event
    # this animates is the CRIME INCIDENT itself (public/civic operation,
    # protection_class 'none'); the camera reads and agency-unit patrols
    # ride the tape's anpr_read / agency_unit frames (contracts C2 / C-E)
    # with the FIR-named plate and the earmark-exercise plate among them —
    # the oracle turns a read into a hit only through an ACTIVE earmark.
    # The scenario's premise (the FIR) is made explicit at t0: the runner
    # ensures the FIR-named plate's stolen_vehicle_fir earmark (a labelled
    # EMULATED precondition), so the sweep files R_STOLEN_SIGHTING evidence
    # — never a penal e-challan against its own stolen plate.
    "watchlist_anpr_sweep": UseCaseProfile(
        event_kind="crime_incident",
        crowd_class="LOW",
        crowd_waypoints=((0, 0.15), (1200, 0.28), (2700, 0.35), (3600, 0.25)),
        extra_events=(
            {
                "type": "market_spillover",
                "segment_id": _SWEEP_ROADSIDE,
                "start_sec": 900,
                "duration_sec": 1200,
                "severity": 0.5,
                "label": "parked tempos and kerbside vendors squeeze the WEH service lane during the sweep",
            },
        ),
        # watchlist knobs (consumed by the tape's anpr_read generator):
        # the four EM-CAM sweep sites + two stop-line approach sites
        # (corridor.cameras) on the sweep route
        anpr_cameras=4,
        anpr_stopline_cameras=2,
        anpr_background_vehicles=6,
        anpr_stolen_plate_hit=True,
        anpr_earmarked_plate_hit=True,
        agency_units=2,
        anpr_stolen_fir_ref=STOLEN_FIR_REF,
    ),
    # Crawford Market fire — fire-tender green-corridor windows (Mumbai Fire
    # Brigade from Byculla, then the Fort line) and an ambulance (108)
    # window to JJ Hospital ride the config's forced_events; the
    # crowd is the wholesale market's afternoon load, pushed out of the
    # cordoned lanes.  The emergency-delay projection runs while a window is
    # open (tender or ambulance alike).  No weather.
    "crawford_market_fire": UseCaseProfile(
        event_kind="emergency_evacuation",
        crowd_class="HIGH",
        crowd_waypoints=((0, 0.55), (600, 0.72), (1800, 0.70), (3600, 0.55)),
        ambulance_base_sec=150.0,
        ambulance_cleared_sec=20.0,
    ),
    # Mithi at the danger mark (Kurla) — heavy rain (60 mm/h -> severity 1.0,
    # RAIN code) after a 300 s onset; the water on LBS Marg and the BKC
    # road by the river, the stalled bus, the commuters off the stopped
    # locals and the closed subways are in forced_events.  The river level is
    # a SIMULATED premise; nothing here models the river.
    "mithi_overflow_kurla": UseCaseProfile(
        event_kind="emergency_evacuation",
        crowd_class="MEDIUM",
        crowd_waypoints=((0, 0.40), (1800, 0.50), (3600, 0.45)),
        weather_onset_sec=300.0,
        weather_steady_severity=1.0,
        weather_code="RAIN",
    ),
    # Diwali night — the Dadar market crowd, stalls on Dr Ambedkar Road and
    # Senapati Bapat Marg, and the ambulance (108) windows to Sion Hospital
    # on a breathing-difficulty call (forced events).  The air-quality readings are SIMULATED and live only in the
    # description: the cause model has no smoke input (and haze is NOT the
    # winter-fog model).
    "diwali_air_quality": UseCaseProfile(
        event_kind="mass_gathering",
        crowd_class="HIGH",
        crowd_waypoints=((0, 0.70), (1200, 0.80), (3000, 0.90), (3600, 0.88)),
        ambulance_base_sec=150.0,
        ambulance_cleared_sec=20.0,
    ),
    # Hot afternoon — no weather code (the adaptive engine knows
    # CLEAR, RAIN, FOG and STORM; heat is not one): the heat shows only
    # through its modelled causes, the overheated breakdowns in forced_events
    # and the thin street crowd (LOW).  Temperatures are SIMULATED, in the
    # description only.
    "october_heat_breakdowns": UseCaseProfile(
        event_kind="work_zone",
        crowd_class="LOW",
        crowd_waypoints=((0, 0.10), (1800, 0.08), (3600, 0.12)),
    ),
    # Monsoon squall — STORM steady from t0 (the squall is already over the
    # city), tree-fall lane losses on SV Road cleared in stages and the
    # overhead wire at Santacruz (forced_events), and an ambulance (108)
    # window to Cooper Hospital + the delay projection.
    "weh_treefall_squall": UseCaseProfile(
        event_kind="work_zone",
        crowd_class="LOW",
        crowd_waypoints=((0, 0.08), (1800, 0.14), (3600, 0.22)),
        weather_onset_sec=1.0,
        weather_steady_severity=0.8,
        weather_code="STORM",
        ambulance_base_sec=150.0,
        ambulance_cleared_sec=25.0,
    ),
    # Ganeshotsav night — the procession class: EXTREME crowd building as the
    # King's Circle and Matunga processions converge on Dadar Chowpatty, a
    # rolling full closure ahead of each one and the ambulance (108) windows
    # along the same route (forced_events).
    "ganeshotsav_night": UseCaseProfile(
        event_kind="procession",
        crowd_class="EXTREME",
        crowd_waypoints=((0, 0.65), (1800, 0.85), (3000, 0.95), (3600, 0.80)),
        ambulance_base_sec=150.0,
        ambulance_cleared_sec=20.0,
    ),
    # Locals stop — the station surge class: stranded commuters out of the
    # Dadar, CSMT, Kurla and Andheri stations (forced_events), EXTREME at
    # first and easing as BEST shuttles and restored services take them;
    # light rain (30 mm/h -> 1.0 capped, RAIN) is already falling at t0.
    "dadar_surge": UseCaseProfile(
        event_kind="egress_surge",
        crowd_class="EXTREME",
        crowd_waypoints=((0, 0.80), (900, 0.95), (2400, 0.75), (3600, 0.55)),
        weather_onset_sec=1.0,
        weather_steady_severity=1.0,
        weather_code="RAIN",
    ),
}


def profile_for(use_case_id: str) -> UseCaseProfile:
    try:
        return PROFILES[use_case_id]
    except KeyError as exc:
        raise KeyError(
            f"no emulation profile for use case {use_case_id!r} — "
            f"known: {sorted(PROFILES)}"
        ) from exc


# Event kinds that are PUBLIC operations (no protectee) → protection_class
# 'none' in events.corridor_events (007 semantics: 'none' = public event);
# protected_movement / ceremonial keep the config's vvip_class (Z+ / Z).
# The watchlist kinds (010) are government/civic operations with no
# protectee — 'none' as well.
_PUBLIC_EVENT_KINDS = frozenset(
    {"procession", "mass_gathering", "race", "egress_surge",
     "emergency_evacuation", "work_zone",
     "crime_incident", "vehicle_pursuit"}
)


def protection_class_for(profile: UseCaseProfile, vvip_class: str) -> str:
    if profile.event_kind in _PUBLIC_EVENT_KINDS:
        return "none"
    return vvip_class
