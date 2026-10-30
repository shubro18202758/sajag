#!/usr/bin/env python3
"""demo_tour.py — the capability tour's states on the live Sajag stack.

Run it through ``scripts/demo_tour.sh`` (which signs in for --apply). Every
capability the console offers has a catalogue entry here: the screen it is seen
on, what must be on the board for it to show, a GET-only check for that state
and, where the state has to be staged, the seed that stages it.

    demo_tour.sh list                              the catalogue (no network)
    demo_tour.sh status [cap ...]                  GET-only: is each state on the board now?
    demo_tour.sh seed <cap|all> ...                dry-run (default): the plan, GET-only
    demo_tour.sh --apply --officer '<name>' seed <cap|all> ...
                                                   stage it, as that named officer
    demo_tour.sh [--apply --officer '<name>'] reset
                                                   stop the emulator runs THIS tour started

Rules it keeps (the same as scripts/demo_reset.sh):

* It never decides anything a human must decide: no approval, rejection,
  dismissal, dispatch, earmark, promotion, escort start or signal write. A
  seed stops at PENDING; the named officer acts on camera.
* A dry-run is GET-only by construction: any other method raises before a byte
  is sent.
* Writes go THROUGH THE DECK as the signed-in officer (the deck sets the
  verified officer header); the backend services are only read.
* Seeds are idempotent: a use case that is already running is kept, not
  started again; a decision-support case the oracle already holds for the same
  inputs is returned by the oracle, not recomputed.
* ``reset`` stops only the runs recorded in this tour's state file. The
  evening (the visarjan night at Girgaon Chowpatty, the monsoon burst at high tide,
  the stolen-vehicle sweep)
  belongs to scripts/demo_reset.sh, which this tour calls for the ``evening``
  seed and never undoes. demo_reset.sh stops every other emulator run, so the
  tour calls it only when the evening is not already running, and before its
  own starts.

Env: DECK_URL (http://127.0.0.1:5373), ORACLE_URL (:8191), BRAIN_URL (:8192),
EMULATOR_URL (:8190), OSINT_URL (:8193), SPEECH_URL (:8194), FORECAST_URL
(:8195), VISION_URL (:8196), HYDRO_URL (:8197), DEMO_TOUR_CLOCK (1: real
time), DEMO_TOUR_STATE (~/.local/state/sajag/demo_tour.json).

Exit: 0 done · 1 a write or a check failed · 2 usage.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def _env(name: str, default: str) -> str:
    return (os.environ.get(name) or default).rstrip("/")


DECK = _env("DECK_URL", "http://127.0.0.1:5373")
ORACLE = _env("ORACLE_URL", "http://127.0.0.1:8191")
BRAIN = _env("BRAIN_URL", "http://127.0.0.1:8192")
EMU = _env("EMULATOR_URL", "http://127.0.0.1:8190")
SERVICES = {
    "brain": _env("BRAIN_URL", "http://127.0.0.1:8192") + "/health",
    "osint": _env("OSINT_URL", "http://127.0.0.1:8193") + "/health",
    "speech": _env("SPEECH_URL", "http://127.0.0.1:8194") + "/health",
    "forecast": _env("FORECAST_URL", "http://127.0.0.1:8195") + "/health",
    "vision": _env("VISION_URL", "http://127.0.0.1:8196") + "/health",
    "hydro": _env("HYDRO_URL", "http://127.0.0.1:8197") + "/health",
}
STATE_FILE = Path(os.environ.get("DEMO_TOUR_STATE")
                  or Path.home() / ".local/state/sajag/demo_tour.json")
CLOCK = float(os.environ.get("DEMO_TOUR_CLOCK") or 1)
#: What scripts/demo_reset.sh stages (its DEMO_EVENING_USE_CASES default plus the sweep).
EVENING_USE_CASES = ("ganesh_visarjan_girgaon", "cloudburst_high_tide", "watchlist_anpr_sweep")


# ── the catalogue ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Cap:
    """One capability: where it is seen, what it needs, how that is staged."""

    id: str
    title: str
    route: str
    show: str                               # the clicks, in a few words
    checks: tuple[str, ...] = ()            # GET-only state checks (see CHECKS)
    seeds: tuple[str, ...] = ()             # use_case:<id> | evening | dss:<kinds> | none
    officer_acts: str = ""                  # what the named officer does on camera, never the script
    origin: str = "earlier"                 # earlier | sajag


CAPS: tuple[Cap, ...] = (
    # ── the surfaces ──
    Cap("landing", "Landing page, English first (मराठी · हिंदी one tap away)", "/welcome",
        "scroll to the audiences; Open the console / Check your road"),
    Cap("shell", "Shell: rail, Decide badge, officer pill, menu (language, exercise data, feeds, map style)",
        "/home", "sweep the rail; open the menu", ("decision_waiting",)),
    Cap("omnibar", "One search box for a place, road, event or vehicle mark", "any page",
        "Ctrl K, type 'Sea Link', Enter"),
    Cap("alerts", "Alerts bell and two-note chime", "any operator page",
        "wait for a new decision (a 108 request); open the bell", ("living_city", "decision_waiting"),
        ("use_case:weh_crash_ambulance",)),
    Cap("live-band", "Live band: something live is never hidden", "/ops",
        "the 36 px strip under the top bar", ("live_operation",), ("use_case:vvip_convoy_base",)),
    Cap("shortcuts", "Keyboard shortcuts (no key approves)", "/decide",
        "G then D; J/K through the queue; 1–4 picks an option; Enter only focuses"),
    Cap("home", "Home: featured decision, city pulse, four rails", "/home",
        "Review now on the featured decision", ("decision_waiting", "osint_situation")),
    Cap("decide", "Decide: one decision at a time, What changes if you approve", "/decide",
        "walk the queue kinds", ("decision_waiting",), ("evening",)),
    Cap("object-pages", "Object pages: vehicle, reported event, road, camera, dispatch", "/o/<urn>",
        "open a card's Details; tabs Overview · Reads · Timeline · Record", ("stolen_vehicle",), ("evening",)),
    Cap("map", "Map: chips, layers, Now panel, selection card, thermal-style, measure, follow", "/map",
        "Layers; pick an event; Follow; thermal-style; measure two points", ("event_any",)),
    Cap("movement-planning", "Plan a movement: routes, security validation, closure plans", "/plan",
        "Mantralaya → Mumbai Airport T2, Z+, Find routes; the Z+ route Needs a waiver",
        officer_acts="Find routes registers the movement (an officer action, label it REHEARSAL)"),
    Cap("escort", "Rolling holds and the escort: one proposal, officer approves, no answer → plan holds",
        "/plan → Launch → Live; /decide",
        "accept the waiver, Start escort; a proposal arrives with its countdown ring",
        ("escort_live",), ("use_case:vvip_convoy_base",),
        officer_acts="Start escort, approve or let the proposal expire, Stop escort, Clear the movement"),
    Cap("event-library", "One engine, the corridor event classes", "/map, /ops",
        "Now panel lists each class; the emulator panel on /ops names the use cases",
        ("class:protected_movement", "class:mass_gathering", "class:race", "class:ceremonial",
         "class:egress_surge", "class:emergency_evacuation", "class:work_zone", "class:procession"),
        ("use_case:vvip_convoy_base", "use_case:mumbai_marathon", "use_case:shivaji_park_parade",
         "use_case:wankhede_egress", "use_case:metro_work_zone",
         "use_case:ganeshotsav_night", "evening")),
    Cap("traffic-feed", "Traffic picture (simulated, labelled)", "/home, /map",
        "the systems line 'Traffic simulated on 86 roads'; the traffic layer", ("service:brain",)),
    Cap("forecasting", "Forecasting ladder in routes and ETAs (support gate → foundation → heuristic)",
        "/plan", "route cards carry their times, labelled Simulated traffic"),
    Cap("ama", "Active Movement Adaptation bands with floors and hysteresis", "/ops",
        "the AMA module card; the band chip on the map; the city pulse on Home", ("city_band",)),
    Cap("signal-plans", "City signal plans and their guards", "/ops",
        "City Signal Plans card: band → green split, History; Apply is refused until the twin is "
        "field-calibrated", ("city_band",),
        officer_acts="Apply plan (shows the honest refusal) or Restore"),
    Cap("twin", "The digital twin: shadow-evaluation and scenario comparison", "/ops (Lab)",
        "Twin comparison panel; AMA 'held baseline: twin not calibrated' in the audit stream",
        ("city_band",)),
    Cap("stolen-chain", "Stolen vehicle: earmark → reads → evidence → approval → pursuit → interception",
        "/decide → /ops → /map", "Authorise pursuit, Open the pursuit, the choke plan, the trace",
        ("stolen_sighting_pending",), ("evening",),
        officer_acts="Authorise pursuit, then Open the pursuit; dispatch units to the chokes"),
    Cap("echallan", "E-challan support: PENDING until an officer decides; theft victim never fined",
        "/decide", "the stolen plate's e-challan can only be rejected", ("echallan_pending",),
        ("evening",), officer_acts="Reject with a reason"),
    Cap("dispatch", "Dispatch to five agencies with the full lifecycle", "/ops",
        "Dispatch tiles: Civic Volunteers, Police Control, Traffic Police, Ambulance (108), Fire",
        ("units_live",), officer_acts="Request, approve, en route, on scene, completed"),
    Cap("green-corridor", "Ambulance (108) green corridor: request → officer → timed window",
        "/driver → /decide → /driver", "request on the phone; approve on Decide; the window counts down",
        ("ambulance_requested",), ("use_case:weh_crash_ambulance",),
        officer_acts="Approve the corridor request"),
    Cap("osint", "Reported events at places: redaction, credibility, the promote gate", "/home → /o/osint_event:<id>",
        "Reported in the city → How sure are we; Sources; Promote needs an officer",
        ("osint_situation", "service:osint"), officer_acts="Promote (only if the film wants it)"),
    Cap("dss", "Decision support: ranked courses of action", "/decide",
        "Choose a response: option cards, Why this one", ("dss_any",),
        ("dss:emergency_evacuation,egress_surge,mass_gathering",),
        officer_acts="Approve one option (it only creates dispatch requests)"),
    Cap("assistant", "Assistant: grounded, read-only, proposals as cards", "/assistant",
        "'Where was the stolen vehicle last read?'", ("service:brain", "stolen_vehicle"), ("evening",)),
    Cap("advisories", "Advisories: four audiences, three languages, drafted not delivered", "/comms",
        "pick an event; switch the audience; Generate advisory; Draft all-clear", ("event_any",)),
    Cap("gods-eye", "God's-eye 3D city, thermal-style view, share link", "/gods-eye",
        "City Vitals; sensor white-hot; share link", ("event_any",)),
    Cap("audit", "Audit trail with Ask why", "/ops, /analyst", "Audit stream; a row → Ask why",
        ("city_feed",)),
    Cap("operator-gate", "Operator gate: masking and attribution", "officer pill",
        "sign out: marks masked, buttons disabled with the reason; sign in again",
        officer_acts="sign out and in with the duty PIN (never shown on screen)"),
    Cap("privacy", "Privacy and retention", "/o/vehicle:<id> · Analyst → Policies",
        "Withheld: no lawful basis; the Policies sheet", ("retention",)),
    Cap("offline-degraded", "Offline and degraded operation", "/home",
        "a stopped feed is named, 'Decisions still work'; the OSM fallback chip", ("service:vision",)),
    Cap("analyst", "Analyst workspace: Graph, Table, masked CSV, timeline, saved views", "/analyst",
        "Graph view → search around; Table → Export CSV (masked)", ("event_any",)),
    Cap("situation-wall", "Situation wall", "/ops", "header counts, Decisions, band chart, audit",
        ("decision_waiting",)),
    Cap("emulator-replay", "Emulator runs and their replay", "/map Now panel → Replay; /ops Lab",
        "Replay a completed run (refused while a movement or pursuit is live)", ("completed_run",)),
    Cap("citizen", "Citizen page: your road, solid = live, dashed = emulated", "/citizen",
        "phone frame; English · मराठी · हिंदी", ("event_any",)),
    Cap("driver", "Ambulance (108) crew page", "/driver", "pick the stretch, unit, urgency; Request"),
    Cap("languages", "English · मराठी · हिंदी everywhere", "menu → language", "switch on one screen"),
    # ── Sajag's own ──
    Cap("waterlogging", "Waterlogging nowcast: rain × Arabian Sea tide (Apollo Bunder) × pumps × terrain", "/map",
        "Layers → Waterlogging; pick a road: depth class, lead time, four labelled drivers",
        ("service:hydro",), origin="sajag"),
    Cap("storm-replay", "Replay of the 18–19 Aug 2025 Mumbai storm", "/map?replay=2025-08-19",
        "step through the night; Decide → Exercise: 19 Aug 2025", ("service:hydro",), origin="sajag"),
    Cap("chronos-forecast", "Chronos-2 congestion forecast with p10–p90 bands", "/o/segment:1033",
        "the two-hour band against the 0.8 line", ("service:forecast",), origin="sajag"),
    Cap("signal-twin", "Signal changes tested in the traffic twin", "/decide (AI proposals)",
        "the twin's comparison: junction, cross street, network", ("ai_proposal",), origin="sajag"),
    Cap("voice-report", "Marathi voice field report", "top bar → Report",
        "hold, speak, the transcript, place, kind, severity, unverified", ("service:speech",),
        origin="sajag", officer_acts="Send to the board (unverified)"),
    Cap("camera-road-state", "Camera road state (vehicles and roads only)", "/o/camera:EM-J12",
        "Read the still; the street-photo tab on /o/camera:EM-CAM-04", ("service:vision",),
        origin="sajag"),
    Cap("air-quality", "Air quality and the city feeds", "/map → City panel",
        "Air, Heat, Cyclone, River, Quake chips", (), origin="sajag"),
    Cap("citizen-listen", "Citizen advisories read aloud in Marathi", "/citizen", "Listen",
        ("service:speech",), origin="sajag"),
)

BY_ID = {c.id: c for c in CAPS}


# ── HTTP (GET-only unless --apply) ────────────────────────────────────────────

APPLY = os.environ.get("DT_APPLY") == "1"
OFFICER = os.environ.get("DT_OFFICER") or ""


def _cookie() -> str | None:
    """The session cookie from deck_session.sh's jar, read into the request
    header only (never printed)."""
    jar = os.environ.get("DT_COOKIE_JAR") or ""
    if os.environ.get("DT_GATE") != "on" or not jar or not os.path.exists(jar):
        return None
    with open(jar, encoding="utf-8") as fh:
        for line in fh:
            parts = line.rstrip("\n").split("\t")
            if len(parts) >= 7 and parts[5] == "sajag_operator":
                return f"sajag_operator={parts[6]}"
    return None


def http(method: str, url: str, body: dict | None = None, timeout: float = 20,
         cookie: str | None = None) -> tuple[int, object]:
    """(status, json); status 0 when unreachable. A dry-run is GET-only by construction."""
    if method != "GET" and not APPLY:
        raise RuntimeError(f"dry-run refused a {method} to {url}")
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if data is not None:
        req.add_header("content-type", "application/json")
    if cookie:
        req.add_header("cookie", cookie)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - loopback config constants
            raw = resp.read()
            return resp.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            return exc.code, json.loads(raw)
        except ValueError:
            return exc.code, {"detail": raw.decode("utf-8", "replace")[:300]}
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return 0, {"detail": f"{type(exc).__name__}: {exc}"[:300]}


def get(url: str) -> tuple[int, object]:
    return http("GET", url)


def write(path: str, body: dict) -> tuple[int, object]:
    """One write THROUGH THE DECK as the signed-in officer."""
    return http("POST", DECK + path, body, timeout=90, cookie=_cookie())


def _list(doc: object, key: str) -> list:
    if isinstance(doc, list):
        return doc
    if isinstance(doc, dict) and isinstance(doc.get(key), list):
        return doc[key]
    return []


# ── the board, read once ─────────────────────────────────────────────────────


@dataclass
class Board:
    events: list = field(default_factory=list)
    recs: list = field(default_factory=list)
    dispatches: list = field(default_factory=list)
    units: list = field(default_factory=list)
    osint: list = field(default_factory=list)
    runs: list = field(default_factory=list)
    use_cases: list = field(default_factory=list)
    living: dict = field(default_factory=dict)
    escorts: dict = field(default_factory=dict)
    plans: dict = field(default_factory=dict)
    vehicles: list = field(default_factory=list)
    retention: dict = field(default_factory=dict)
    feed: dict = field(default_factory=dict)
    ai: dict = field(default_factory=dict)
    health: dict = field(default_factory=dict)
    reachable: dict = field(default_factory=dict)


def read_board(fetch=get) -> Board:
    b = Board()

    def grab(name: str, url: str) -> object:
        st, doc = fetch(url)
        b.reachable[name] = st == 200
        return doc if st == 200 else None

    b.events = _list(grab("events", ORACLE + "/api/v1/events/active"), "events")
    b.recs = _list(grab("recs", ORACLE + "/api/v1/enforcement/recommendations?limit=300"),
                   "recommendations")
    b.dispatches = _list(grab("dispatches", ORACLE + "/api/v1/dispatches?limit=200"), "dispatches")
    b.units = _list(grab("units", ORACLE + "/api/v1/units"), "units")
    b.osint = _list(grab("osint", ORACLE + "/api/v1/osint/events?limit=50"), "events")
    b.vehicles = _list(grab("vehicles", ORACLE + "/api/v1/vehicles?limit=20"), "vehicles")
    b.retention = grab("retention", ORACLE + "/api/v1/vehicles/retention") or {}
    b.plans = grab("plans", ORACLE + "/api/v1/signals/plans") or {}
    b.feed = grab("feed", ORACLE + "/api/v1/city/feed") or {}
    b.ai = grab("ai", ORACLE + "/api/v1/ai-proposals/decisions?limit=5") or {}
    b.runs = _list(grab("runs", EMU + "/api/v1/emulator/runs?limit=60"), "runs")
    b.use_cases = _list(grab("use_cases", EMU + "/api/v1/emulator/use-cases"), "use_cases")
    b.living = grab("living", EMU + "/api/v1/emulator/living-city") or {}
    b.escorts = grab("escorts", BRAIN + "/escorts") or {}
    for name, url in SERVICES.items():
        st, doc = fetch(url)
        b.health[name] = st == 200 and isinstance(doc, dict) and doc.get("status") in ("ok", "healthy")
    return b


def run_use_case(r: dict) -> str | None:
    spec = r.get("spec") if isinstance(r.get("spec"), dict) else {}
    return spec.get("use_case_id") or r.get("use_case_id")


def running_use_cases(b: Board) -> dict[str, int]:
    return {uc: r["run_id"] for r in b.runs
            if r.get("status") == "running" and (uc := run_use_case(r))}


def _pending(b: Board, rules: set[str]) -> int:
    return sum(1 for r in b.recs if str(r.get("status", "")).lower() == "pending"
               and (r.get("rule_id") or r.get("rule")) in rules)


def check(b: Board, name: str) -> tuple[bool, str]:
    """(ok, what was seen) for one GET-only state check."""
    kinds = [str(e.get("event_kind") or e.get("kind") or "") for e in b.events]
    if name.startswith("class:"):
        k = name.split(":", 1)[1]
        n = kinds.count(k)
        return n > 0, f"{n} live {k} event(s)"
    if name.startswith("service:"):
        s = name.split(":", 1)[1]
        return bool(b.health.get(s)), f"{s} {'answering' if b.health.get(s) else 'not ready'}"
    if name == "event_any":
        return bool(b.events), f"{len(b.events)} live corridor event(s)"
    if name == "decision_waiting":
        n = _pending(b, {"R_STOLEN_SIGHTING", "R_SPD_SEGMENT", "R_SIGNAL_VIOLATION",
                         "R_CLOSED_CORRIDOR_ENTRY"})
        a = sum(1 for d in b.dispatches if d.get("status") == "requested")
        return n + a > 0, f"{n} recommendation(s) and {a} dispatch request(s) waiting"
    if name == "stolen_sighting_pending":
        n = _pending(b, {"R_STOLEN_SIGHTING"})
        return n > 0, f"{n} stolen-vehicle sighting(s) PENDING"
    if name == "echallan_pending":
        n = _pending(b, {"R_SPD_SEGMENT", "R_SIGNAL_VIOLATION", "R_CLOSED_CORRIDOR_ENTRY"})
        return n > 0, f"{n} e-challan recommendation(s) PENDING"
    if name == "stolen_vehicle":
        n = sum(1 for v in b.vehicles if v.get("lawful_basis") == "stolen_vehicle_fir"
                and v.get("earmark_state") not in (None, "cleared"))
        return n > 0, f"{n} earmarked stolen vehicle(s)"
    if name == "ambulance_requested":
        n = sum(1 for d in b.dispatches if d.get("agency") == "ambulance" and d.get("status") == "requested")
        return n > 0, f"{n} ambulance (108) request(s) waiting"
    if name == "units_live":
        return bool(b.units), f"{len(b.units)} emulated unit(s) on the map"
    if name == "osint_situation":
        return bool(b.osint), f"{len(b.osint)} reported event(s)"
    if name == "living_city":
        st = b.living.get("status") if isinstance(b.living, dict) else None
        return st == "running", f"living city {st or 'unknown'}"
    if name == "live_operation":
        live = sum(1 for e in b.events if e.get("status") == "active")
        esc = int((b.escorts or {}).get("count") or 0)
        return live + esc > 0, f"{live} active event(s), {esc} escort(s)"
    if name == "escort_live":
        esc = int((b.escorts or {}).get("count") or 0)
        return esc > 0, f"{esc} escort(s) running"
    if name == "city_band":
        band = (b.plans or {}).get("city_band")
        stale = (b.plans or {}).get("city_band_stale")
        return bool(band) and not stale, f"city band {band or 'unknown'}{' (stale)' if stale else ''}"
    if name == "dss_any":
        # the oracle lists no DSS index; an event of a DSS-able kind is the precondition
        n = sum(1 for k in kinds if k in ("emergency_evacuation", "egress_surge", "mass_gathering"))
        return n > 0, f"{n} event(s) a decision-support case can be generated for"
    if name == "city_feed":
        n = len(_list(b.feed, "items"))
        return n > 0, f"{n} audit/feed row(s)"
    if name == "retention":
        return bool(b.retention), "retention policy answered" if b.retention else "retention not answered"
    if name == "ai_proposal":
        return bool(b.reachable.get("ai")), "AI proposal log answering" if b.reachable.get("ai") else "AI log down"
    if name == "completed_run":
        n = sum(1 for r in b.runs if r.get("status") == "completed")
        return n > 0, f"{n} completed run(s) to replay"
    raise KeyError(name)


CHECKS = {
    "event_any", "decision_waiting", "stolen_sighting_pending", "echallan_pending", "stolen_vehicle",
    "ambulance_requested", "units_live", "osint_situation", "living_city", "live_operation",
    "escort_live", "city_band", "dss_any", "city_feed", "retention", "ai_proposal", "completed_run",
}


def known_check(name: str) -> bool:
    if name.startswith("class:"):
        return True
    if name.startswith("service:"):
        return name.split(":", 1)[1] in SERVICES
    return name in CHECKS


# ── state file (the runs this tour started) ──────────────────────────────────


def load_state() -> dict:
    try:
        doc = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return doc if isinstance(doc, dict) else {"runs": []}
    except (OSError, ValueError):
        return {"runs": []}


def save_state(doc: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8")
    os.chmod(tmp, 0o600)
    tmp.replace(STATE_FILE)


# ── plans ────────────────────────────────────────────────────────────────────


def plan_seed(caps: list[Cap], b: Board) -> list[tuple[str, str, str]]:
    """[(action, arg, why)] — action is keep | start | evening | dss | skip; no I/O."""
    out: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    running = running_use_cases(b)
    offered = {u.get("id") for u in b.use_cases}
    for cap in caps:
        for seed in cap.seeds:
            if seed in seen:
                continue
            seen.add(seed)
            if seed == "evening":
                # demo_reset.sh stops every other emulator run, so it runs only when the evening
                # is not all running already, and always before this invocation's own starts
                _, saw = check(b, "stolen_sighting_pending")
                if all(uc in running for uc in EVENING_USE_CASES):
                    out.append(("keep", "evening", f"{cap.id}: the evening is running; {saw}"))
                else:
                    out.append(("evening", "", f"{cap.id}: {saw} now; demo_reset.sh stages the evening "
                                               "(and stops other emulator runs, so it goes first)"))
            elif seed.startswith("use_case:"):
                uc = seed.split(":", 1)[1]
                if uc in running:
                    out.append(("keep", uc, f"{cap.id}: {uc} already running (run {running[uc]})"))
                elif offered and uc not in offered:
                    out.append(("skip", uc, f"{cap.id}: the emulator does not offer {uc}"))
                else:
                    out.append(("start", uc, f"{cap.id}: start {uc} at clock {CLOCK:g}"))
            elif seed.startswith("dss:"):
                kinds = seed.split(":", 1)[1].split(",")
                live = [e for e in b.events if e.get("status") == "active"]
                ev = next((e for k in kinds for e in live
                           if (e.get("event_kind") or e.get("kind")) == k), None)
                if ev is None:
                    out.append(("skip", "", f"{cap.id}: no active {'/'.join(kinds)} event yet "
                                            "(seed the evening first)"))
                else:
                    eid = ev.get("event_id") or ev.get("id")
                    out.append(("dss", str(eid), f"{cap.id}: decision support for '{ev.get('title', eid)}'"))
            else:
                raise ValueError(f"unknown seed {seed}")
    # the evening first: demo_reset.sh would stop a use case started before it
    return [o for o in out if o[0] == "evening"] + [o for o in out if o[0] != "evening"]


def resolve(names: list[str]) -> list[Cap]:
    if not names or names == ["all"]:
        return list(CAPS)
    bad = [n for n in names if n not in BY_ID]
    if bad:
        raise SystemExit(f"demo_tour: unknown capability {', '.join(bad)} (see: demo_tour.sh list)")
    return [BY_ID[n] for n in names]


# ── commands ─────────────────────────────────────────────────────────────────


def cmd_list() -> int:
    for c in CAPS:
        tag = "earlier" if c.origin == "earlier" else "sajag"
        seeds = ", ".join(c.seeds) or "-"
        print(f"{c.id:18s} [{tag}] {c.route}")
        print(f"{'':18s}   {c.title}")
        print(f"{'':18s}   show: {c.show}")
        print(f"{'':18s}   seed: {seeds}" + (f" · officer: {c.officer_acts}" if c.officer_acts else ""))
    return 0


def cmd_status(caps: list[Cap], b: Board) -> int:
    down = [k for k, v in b.reachable.items() if not v]
    if down:
        print(f"[demo-tour] not answering: {', '.join(sorted(down))}")
    missing = 0
    for c in caps:
        res = [(n, *check(b, n)) for n in c.checks]
        ok_ = all(r[1] for r in res)
        missing += 0 if ok_ else 1
        state = "READY" if ok_ else ("NEEDS SEED" if c.seeds else "NEEDS STATE")
        print(f"{state:11s} {c.id:18s} {c.route}")
        for name, good, saw in res:
            print(f"{'':12s}{'ok ' if good else '-- '}{name}: {saw}")
    print(f"[demo-tour] {len(caps) - missing}/{len(caps)} capabilities ready to film")
    return 0


def cmd_seed(caps: list[Cap], b: Board) -> int:
    plan = plan_seed(caps, b)
    if not APPLY:
        for action, arg, why in plan:
            verb = {"start": "would POST /api/emulator/api/v1/emulator/runs",
                    "dss": "would POST /api/v1/decision-support/event:<id>/generate",
                    "evening": "would run scripts/demo_reset.sh --apply --officer <name>",
                    "keep": "keep", "skip": "skip"}[action]
            print(f"[dry-run] {verb:58s} {why}")
        print("[dry-run] nothing written (GET-only); --apply --officer '<name>' stages it")
        return 0
    failed = 0
    state = load_state()
    for action, arg, why in plan:
        if action in ("keep", "skip"):
            print(f"[demo-tour] {action}: {why}")
            continue
        if action == "evening":
            rc = subprocess.run(["bash", str(HERE / "demo_reset.sh"), "--apply", "--officer", OFFICER],
                                check=False).returncode
            print(f"[demo-tour] demo_reset.sh --apply exited {rc}: {why}")
            failed += rc != 0
            continue
        if action == "start":
            st, doc = write("/api/emulator/api/v1/emulator/runs",
                            {"use_case_id": arg, "clock_scale": CLOCK})
            rid = doc.get("run_id") if isinstance(doc, dict) else None
            print(f"[demo-tour] start {arg}: HTTP {st}" + (f", run {rid}" if rid else f" {doc}"))
            if st in (200, 201, 202) and rid is not None:
                state["runs"].append({"run_id": rid, "use_case_id": arg,
                                      "started_at": datetime.now(timezone.utc).isoformat()})
                save_state(state)
            else:
                failed += 1
            continue
        if action == "dss":
            st, doc = write(f"/api/v1/decision-support/event:{arg}/generate", {"requested_by": "deck"})
            dss = doc.get("dss_id") if isinstance(doc, dict) else None
            print(f"[demo-tour] decision support: HTTP {st}" + (f", {dss}" if dss else f" {doc}"))
            failed += st not in (200, 201)
    return 1 if failed else 0


def cmd_reset(b: Board) -> int:
    state = load_state()
    mine = state.get("runs") or []
    status = {r.get("run_id"): r.get("status") for r in b.runs}
    if not mine:
        print("[demo-tour] reset: this tour started no runs (the evening is scripts/demo_reset.sh's)")
        return 0
    failed = 0
    keep = []
    for r in mine:
        rid = r.get("run_id")
        if status.get(rid) != "running":
            print(f"[demo-tour] run {rid} ({r.get('use_case_id')}) already {status.get(rid) or 'gone'}")
            continue
        if not APPLY:
            print(f"[dry-run] would POST /api/emulator/api/v1/emulator/runs/{rid}/stop ({r.get('use_case_id')})")
            keep.append(r)
            continue
        st, _ = write(f"/api/emulator/api/v1/emulator/runs/{rid}/stop", {})
        print(f"[demo-tour] stop run {rid} ({r.get('use_case_id')}): HTTP {st}")
        if st not in (200, 202, 409):
            failed += 1
            keep.append(r)
    if APPLY:
        state["runs"] = keep
        save_state(state)
    return 1 if failed else 0


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__.split("\n\n")[1])
        return 0 if argv else 2
    cmd, rest = argv[0], argv[1:]
    if cmd == "list":
        return cmd_list()
    if cmd not in ("status", "seed", "reset"):
        print(f"demo_tour: unknown command '{cmd}'", file=sys.stderr)
        return 2
    if cmd == "seed" and not rest:
        print("demo_tour: seed needs a capability or 'all'", file=sys.stderr)
        return 2
    caps = resolve(rest) if cmd != "reset" else []
    board = read_board()
    if cmd == "status":
        return cmd_status(caps, board)
    if cmd == "seed":
        return cmd_seed(caps, board)
    return cmd_reset(board)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
