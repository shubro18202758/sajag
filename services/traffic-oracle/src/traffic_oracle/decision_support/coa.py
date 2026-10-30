"""Course-of-action generation (C-U): a small, distinct COA set from REAL Sajag actuators.

Every event gets the same five strategies (GEOSPATIAL_AND_DSS §B1-2, the PoC's ``build_coas``):

* ``coa_base`` — **baseline**: monitor only (the mandatory do-nothing option);
* ``coa_min`` — **minimal**: a driver and citizen advisory (draft only);
* ``coa_std`` — **standard**: advisory + a 108 dispatch (when the situation calls for one) + one responder
  dispatch + an emergency signal-priority hold;
* ``coa_agg`` — **aggressive**: closure + diversion + the dispatches (two responder units);
* ``coa_info`` — **information**: one patrol to verify + a situation check by the city's ICCC (outside Sajag,
  **no identification**) + a 10-minute hold.

The responder and the 108 follow the situation (a declared deviation from the WP's literal "108 dispatch + police
dispatch", which is the PoC's road-collision case and which this reproduces exactly): the responder agency is the one
the class calls for (:data:`_RESPONDER`: a fire tender for a fire, hazard or infrastructure failure; a traffic
police unit for flooding, weather, a closure, a work zone or an egress surge; police otherwise), and the 108 is
included when a report carries an injury cue or the class is one where casualties are likely
(:data:`_AMBULANCE_CLASSES`).  The verifying patrol of the information COA is always police.

Targets are real URNs (``segment:<id>``, ``junction:<id>``, ``place:<slug>``). Every actuating action
(``signal_hold``, ``diversion``, ``dispatch``, ``escort_switch``, ``closure``) has ``requires_officer: true``.
A COA that touches a person is impossible by construction: no verb acts on a person, no target names one, and
the ICCC check is a situation check only (``identification: false``). :func:`assess_ethics` and the lexical veto
check it anyway.

An **area-level** subject (no segment and no junction: a district report) cannot anchor a dispatch, closure,
diversion or signal hold: those COAs are marked infeasible up front ("no road anchor: area-level report") and the
information COA becomes an ICCC check plus a hold for an official source, so it stays feasible.

Each COA also carries its DSS-layer **effect profile** (the PoC's ``sim``): how much carriageway it takes, how
long the disturbance lasts, how fast it acts — the per-COA event injection the twin cannot express.
"""

from __future__ import annotations

import copy
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from osint_common import ethics, kinds

__all__ = [
    "ACTION_VERBS",
    "AGENCY_NOUN",
    "ANCHOR_SHORTFALL",
    "ICCC_AREA_LABEL",
    "ICCC_LABEL",
    "ICCC_ROAD_LABEL",
    "KIND_ORDER",
    "NEXT_STEP_HOMES",
    "TARGET_KINDS",
    "Anchors",
    "CoaDraft",
    "Effects",
    "assess_ethics",
    "build_coas",
    "next_steps",
    "responder_agency",
    "target_kind",
]

#: The action vocabulary (C-U ``ActionVerb``): real Sajag actuators and two non-actuating verbs.
ACTION_VERBS: frozenset[str] = frozenset(
    {"monitor", "advisory", "signal_hold", "diversion", "dispatch", "escort_switch", "closure", "request_cctv"}
)

#: URN kinds an action may target: places, roads, junctions, events — never a person.
TARGET_KINDS: frozenset[str] = frozenset({"segment", "junction", "place", "event", "osint_event", "corridor"})

#: The kinds, in generation order (the order also seeds each COA's wargame RNG, as in the PoC).
KIND_ORDER: tuple[str, ...] = ("baseline", "minimal", "standard", "aggressive", "information")

#: The shortfall an area-level subject's road-anchored COAs carry (C-U; the model checks the phrase).
ANCHOR_SHORTFALL = "no road anchor: area-level report"

#: The ICCC action's wording (C-U): the city's own channel, outside Sajag, a situation check only.
ICCC_LABEL = "Situation check at the junction (ICCC) — no identification"
#: ... when no junction is known at the scene and the check targets the road segment itself
ICCC_ROAD_LABEL = "Situation check on the road (ICCC) — no identification"
ICCC_AREA_LABEL = "Situation check of the area (ICCC) — no identification"

#: Where each verb an approval does not write is done (C-U ``next_steps``).
NEXT_STEP_HOMES: Mapping[str, str] = {
    "advisory": "Advisories (draft only)",
    "signal_hold": "City signal plans (writer off by default)",
    "closure": "Corridor operations",
    "diversion": "Corridor operations",
    "escort_switch": "Movement tab",
    "request_cctv": "ICCC, outside Sajag",
    "monitor": "none",
}

#: How a COA label names one unit of an agency.
AGENCY_NOUN: Mapping[str, tuple[str, str]] = {
    "police": ("patrol", "police units"),
    "traffic": ("traffic police unit", "traffic police units"),
    "fire": ("fire tender", "fire tenders"),
    "jan_rakshak": ("civic volunteer unit", "civic volunteer units"),
    "ambulance": ("108 ambulance", "108 ambulances"),
}

#: The responder agency by situation class (OSINT classes and corridor event kinds); police otherwise.
_RESPONDER: Mapping[str, str] = {
    "fire": "fire",
    "hazard": "fire",
    "infra_failure": "fire",
    "urban_flooding": "traffic",
    "flooding": "traffic",
    "weather_hazard": "traffic",
    "road_closure": "traffic",
    "work_zone": "traffic",
    "egress_surge": "traffic",
}

#: Classes whose standard response includes a 108 ambulance even without an injury cue in the reports.
_AMBULANCE_CLASSES: frozenset[str] = frozenset(
    {"road_accident", "public_conflict", "fire", "hazard", "infra_failure", "unrest", "public_disorder"}
)

_URN_RE = re.compile(r"^([a-z][a-z_]{0,31}):[A-Za-z0-9][A-Za-z0-9_.:\-]{0,127}$")


def responder_agency(event_class: str) -> str:
    return _RESPONDER.get(event_class, "police")


@dataclass(frozen=True)
class Effects:
    """The DSS-layer effect profile of one COA (the PoC's ``sim``), the per-COA event injection.

    ``lanes_blocked`` is ``0``, ``1`` or ``"all"`` (resolved against the segment's lanes by the wargame);
    ``capacity_factor`` the residual capacity of the open lanes; ``active_min`` how long the disturbance lasts;
    ``advisory`` whether drivers are warned (resolution + demand relief); ``emergency_lane`` whether a lane stays
    open for the 108; ``time_to_effect_sec`` how fast the COA acts."""

    lanes_blocked: int | str
    capacity_factor: float
    active_min: float
    advisory: bool
    time_to_effect_sec: float
    emergency_lane: bool


#: The PoC's effect profiles, by kind.
EFFECTS: Mapping[str, Effects] = {
    "baseline": Effects(0, 1.0, 30, False, 0, True),
    "minimal": Effects(0, 0.95, 40, True, 120, True),
    "standard": Effects(1, 0.9, 45, True, 300, True),
    "aggressive": Effects("all", 0.4, 50, True, 420, False),
    "information": Effects(0, 0.97, 15, True, 240, True),
}


@dataclass(frozen=True)
class Anchors:
    """Where the COAs act: the road anchor (or none, for an area-level report), the junction a signal hold or
    an ICCC check targets, the place an advisory names and the roads a diversion uses."""

    segment_id: int | None
    junction_id: int | None
    route_segment_ids: tuple[int, ...] = ()
    hold_junction_id: int | None = None
    place_urn: str | None = None
    diversion_via: tuple[str, ...] = ()
    area_level: bool = False

    @property
    def anchored(self) -> bool:
        return self.segment_id is not None or self.junction_id is not None

    @property
    def road_urn(self) -> str | None:
        if self.segment_id is not None:
            return f"segment:{self.segment_id}"
        if self.junction_id is not None:
            return f"junction:{self.junction_id}"
        return None

    @property
    def junction_urn(self) -> str | None:
        jid = self.hold_junction_id or self.junction_id
        return f"junction:{jid}" if jid else None


@dataclass
class CoaDraft:
    """One generated COA before the wargame and the scoring."""

    coa_id: str
    kind: str
    label: str
    actions: list[dict[str, Any]]
    effects: Effects
    index: int
    #: the up-front shortfall of an area-level subject's road-anchored COA ("no road anchor: ...")
    anchor_shortfall: str | None = None
    ethics: dict[str, bool] = field(default_factory=dict)

    # -- derived from the actions ---------------------------------------------------------------------------
    def verbs(self) -> list[str]:
        return [a["verb"] for a in self.actions]

    def dispatches(self) -> list[dict[str, Any]]:
        return [a for a in self.actions if a["verb"] == "dispatch"]

    @property
    def dispatch_108(self) -> bool:
        return any((a.get("params") or {}).get("agency") == "ambulance" for a in self.dispatches())

    @property
    def responder_units(self) -> int:
        """Units dispatched besides the 108 (the PoC's ``police_units``)."""
        return sum(
            int((a.get("params") or {}).get("count", 1))
            for a in self.dispatches()
            if (a.get("params") or {}).get("agency") != "ambulance"
        )

    @property
    def signal_priority(self) -> bool:
        return any(a["verb"] == "signal_hold" for a in self.actions)

    @property
    def closure(self) -> bool:
        return any(a["verb"] == "closure" for a in self.actions)

    @property
    def diversion(self) -> bool:
        return any(a["verb"] == "diversion" for a in self.actions)

    @property
    def needs_anchor(self) -> bool:
        return any(v in kinds.ANCHOR_VERBS for v in self.verbs())

    def required_resources(self) -> dict[str, int]:
        need: dict[str, int] = {}
        for a in self.dispatches():
            p = a.get("params") or {}
            agency = str(p.get("agency") or "police")
            need[agency] = need.get(agency, 0) + int(p.get("count", 1))
        return need


def _action(
    verb: str, target: str | None, *, officer: bool, reversible: bool = True, **params: Any
) -> dict[str, Any]:
    return {
        "verb": verb,
        "target_urn": target,
        "params": {k: v for k, v in params.items() if v is not None},
        "requires_officer": officer,
        "reversible": reversible,
    }


def _units(agency: str, n: int) -> str:
    one, many = AGENCY_NOUN.get(agency, (agency, agency))
    return f"{n} {one if n == 1 else many}"


def build_coas(
    *,
    event_class: str,
    anchors: Anchors,
    injuries: bool = False,
) -> list[CoaDraft]:
    """The five COAs for one situation (see the module docstring)."""
    responder = responder_agency(event_class)
    ambulance = injuries or event_class in _AMBULANCE_CLASSES
    road = anchors.road_urn
    place = anchors.place_urn or road
    junction = anchors.junction_urn
    hold_target = junction or road
    area = anchors.area_level or not anchors.anchored

    advisory = _action("advisory", place, officer=False, channel="vms_and_app", draft=True)
    disp_108 = _action("dispatch", road or place, officer=True, agency="ambulance", count=1)

    def responders(count: int) -> list[dict[str, Any]]:
        return [_action("dispatch", road or place, officer=True, agency=responder, count=count)]

    std_actions = [advisory]
    if ambulance:
        std_actions.append(disp_108)
    std_actions += responders(1)
    std_actions.append(
        _action("signal_hold", hold_target, officer=True, mode="emergency_priority", hold_sec=60)
    )
    std_label = "Advisory + " + ("108 ambulance + " if ambulance else "")
    std_label += f"{_units(responder, 1)} + signal priority"

    agg_actions = [
        _action("closure", road or place, officer=True, scope="carriageway"),
        _action("diversion", road or place, officer=True, via=list(anchors.diversion_via)[:8]),
    ]
    if ambulance:
        agg_actions.append(dict(disp_108))
    agg_actions += responders(2)
    agg_label = "Close carriageway + full diversion + " + ("108 + " if ambulance else "")
    agg_label += _units(responder, 2)

    hold = _action("monitor", place, officer=False, hold_min=10, then="regenerate with any new source")
    if area:
        info_actions = [
            _action(
                "request_cctv",
                place,
                officer=False,
                channel="ICCC",
                outside_sajag=True,
                identification=False,
                label=ICCC_AREA_LABEL,
            ),
            _action("monitor", place, officer=False, hold_min=10, then="await an official source"),
        ]
        info_label = "Verify first: ICCC situation check of the area (no identification) + 10-min hold"
    else:
        info_actions = [
            _action("dispatch", road, officer=True, agency="police", count=1, role="verify"),
            _action(
                "request_cctv",
                junction or road,
                officer=False,
                channel="ICCC",
                outside_sajag=True,
                identification=False,
                # the wording says where the check really is: a junction when one is known, else the road
                label=ICCC_LABEL if junction else ICCC_ROAD_LABEL,
            ),
            hold,
        ]
        info_label = "Verify first: 1 patrol to confirm + ICCC situation check (no identification) + 10-min hold"

    specs: list[tuple[str, str, str, list[dict[str, Any]]]] = [
        ("coa_base", "baseline", "Monitor only (do nothing)", [_action("monitor", place, officer=False)]),
        ("coa_min", "minimal", "Driver and citizen advisory only (VMS + app push)", [dict(advisory)]),
        ("coa_std", "standard", std_label, std_actions),
        ("coa_agg", "aggressive", agg_label, agg_actions),
        ("coa_info", "information", info_label, info_actions),
    ]
    drafts: list[CoaDraft] = []
    for index, (coa_id, kind, label, actions) in enumerate(specs):
        draft = CoaDraft(coa_id, kind, label, copy.deepcopy(actions), EFFECTS[kind], index)
        if area and draft.needs_anchor:
            draft.anchor_shortfall = ANCHOR_SHORTFALL
        draft.ethics = assess_ethics(draft.actions)
        drafts.append(draft)
    return drafts


def target_kind(target: Any) -> str | None:
    """The URN kind of an action target (``segment`` for ``segment:1045``); ``""`` for a malformed one."""
    if target is None:
        return None
    m = _URN_RE.match(str(target))
    return m.group(1) if m else ""


def assess_ethics(actions: Sequence[Mapping[str, Any]]) -> dict[str, bool]:
    """The four lexical-veto inputs of a COA, from its actions (defence in depth: generation never produces a
    failing COA, and this check does not trust that).

    * ``touches_persons``: a target or a parameter names a person (the denylist), or an ICCC check that does
      not explicitly exclude identification;
    * ``legal``: every verb is a Sajag actuator and every target a place, road, junction or event URN;
    * ``protocol_ok``: a closure always carries a diversion (traffic is never stranded);
    * ``irreversible_without_officer``: an action that cannot be undone and has no named-officer gate."""
    touches = False
    legal = True
    protocol = True
    irreversible = False
    verbs = [str(a.get("verb")) for a in actions]
    for a in actions:
        verb = str(a.get("verb"))
        kind = target_kind(a.get("target_urn"))
        params = a.get("params") or {}
        if kind and ethics.is_forbidden_key(kind):
            touches = True
        try:
            ethics.assert_no_person_keys(params)
        except ValueError:
            touches = True
        if verb == "request_cctv" and params.get("identification") is not False:
            touches = True
        if verb not in ACTION_VERBS:
            legal = False
        if kind is not None and kind not in TARGET_KINDS:
            legal = False
        if verb in kinds.ACTUATING_VERBS and not a.get("requires_officer"):
            legal = False
        if not a.get("reversible", True) and not a.get("requires_officer"):
            irreversible = True
    if "closure" in verbs and "diversion" not in verbs:
        protocol = False
    return {
        "touches_persons": touches,
        "legal": legal,
        "protocol_ok": protocol,
        "irreversible_without_officer": irreversible,
    }


def _describe(action: Mapping[str, Any], names: Mapping[str, str] | None = None) -> str:
    verb = action["verb"]
    urn = action.get("target_urn")
    target = (names or {}).get(urn or "", urn) or "the area"
    params = action.get("params") or {}
    if verb == "advisory":
        return f"Draft the driver and citizen advisory for {target}"
    if verb == "signal_hold":
        return f"Request emergency signal priority at {target}"
    if verb == "closure":
        return f"Close the carriageway at {target}"
    if verb == "diversion":
        via = ", ".join(str(v) for v in (params.get("via") or [])[:4])
        return f"Divert traffic from {target}" + (f" via {via}" if via else "")
    if verb == "escort_switch":
        return f"Review the escort switch for {target}"
    if verb == "request_cctv":
        return str(params.get("label") or ICCC_LABEL)
    if verb == "monitor":
        hold = params.get("hold_min")
        return f"Keep monitoring for {hold} min, then regenerate" if hold else "Keep monitoring"
    return verb


def next_steps(
    actions: Sequence[Mapping[str, Any]], names: Mapping[str, str] | None = None
) -> list[dict[str, str]]:
    """Every verb an approval does not write (all but ``dispatch``), with its home (C-U); ``names`` maps a
    target URN to the place name the label uses."""
    out: list[dict[str, str]] = []
    for a in actions:
        verb = a["verb"]
        if verb == "dispatch":
            continue
        out.append({"verb": verb, "home": NEXT_STEP_HOMES[verb], "label": _describe(a, names)[:200]})
    return out[:16]
