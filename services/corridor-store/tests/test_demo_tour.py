"""scripts/demo_tour.{sh,py}: the capability tour's seeding is GET-only unless
--apply, never decides for an officer, is idempotent, and resets only its own runs.

No network: the board is built from fixtures; the shell wrapper is exercised on its
usage refusals and on a dead port.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "scripts" / "demo_tour.py"
WRAPPER = REPO / "scripts" / "demo_tour.sh"
LIBRARY = REPO / "services" / "event-emulator" / "src" / "event_emulator" / "use_case_library.json"


def _load(monkeypatch, tmp_path, apply: bool = False):
    monkeypatch.setenv("DEMO_TOUR_STATE", str(tmp_path / "tour.json"))
    monkeypatch.setenv("DT_APPLY", "1" if apply else "0")
    monkeypatch.setenv("DT_OFFICER", "Test duty officer")
    spec = importlib.util.spec_from_file_location("demo_tour_under_test", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["demo_tour_under_test"] = mod
    spec.loader.exec_module(mod)
    return mod


def _board(mod, **kw):
    b = mod.Board()
    b.events = kw.get("events", [])
    b.recs = kw.get("recs", [])
    b.runs = kw.get("runs", [])
    b.use_cases = kw.get("use_cases", [])
    b.dispatches = kw.get("dispatches", [])
    return b


def test_catalogue_is_complete_and_well_formed(monkeypatch, tmp_path):
    mod = _load(monkeypatch, tmp_path)
    ids = [c.id for c in mod.CAPS]
    assert len(ids) == len(set(ids))
    # the earlier city build's capabilities and Sajag's own are both in the tour
    for need in ("movement-planning", "escort", "event-library", "ama", "signal-plans", "twin",
                 "stolen-chain", "echallan", "dispatch", "green-corridor", "osint", "dss", "assistant",
                 "advisories", "gods-eye", "audit", "operator-gate", "privacy", "offline-degraded",
                 "alerts", "live-band", "omnibar", "shortcuts", "object-pages", "analyst",
                 "situation-wall", "citizen", "driver", "waterlogging", "storm-replay",
                 "chronos-forecast", "signal-twin", "voice-report", "camera-road-state",
                 "air-quality", "citizen-listen"):
        assert need in ids, need
    library = {u["id"] for u in json.loads(LIBRARY.read_text(encoding="utf-8"))}
    for c in mod.CAPS:
        assert c.route and c.title and c.show
        for name in c.checks:
            assert mod.known_check(name), (c.id, name)
        for seed in c.seeds:
            assert seed == "evening" or seed.startswith(("use_case:", "dss:")), (c.id, seed)
            if seed.startswith("use_case:"):
                uc = seed.split(":", 1)[1]
                # the procession use case ships with the emulator patch; the plan skips it until then
                assert uc in library or uc == "ganeshotsav_night", (c.id, uc)


def test_officer_actions_are_never_seeds(monkeypatch, tmp_path):
    """A seed only starts emulator causes, the evening or a compute call; never a decision."""
    mod = _load(monkeypatch, tmp_path)
    text = SCRIPT.read_text(encoding="utf-8")
    writes = re.findall(r'write\(f?"([^"]+)"', text)
    assert writes, "the write paths moved: update this test"
    allowed = ("/api/emulator/api/v1/emulator/runs", "/api/v1/decision-support/event:")
    for path in writes:
        assert path.startswith(allowed), path
        assert path.endswith(("/runs", "/stop", "/generate")), path
    for verb in ("/approve", "/reject", "/promote", "/earmark", "/transition", "/signals/apply",
                 "/restore", "/dismiss", "POST\", BRAIN"):
        assert verb not in text, verb



def test_dry_run_is_get_only(monkeypatch, tmp_path, capsys):
    mod = _load(monkeypatch, tmp_path, apply=False)
    with pytest.raises(RuntimeError):
        mod.http("POST", "http://127.0.0.1:9/x", {})
    board = _board(mod, use_cases=[{"id": "vvip_convoy_base"}])
    assert mod.cmd_seed([mod.BY_ID["escort"]], board) == 0
    out = capsys.readouterr().out
    assert "would POST /api/emulator/api/v1/emulator/runs" in out and "nothing written" in out
    assert not (tmp_path / "tour.json").exists()


def test_seed_is_idempotent_and_skips_what_the_emulator_lacks(monkeypatch, tmp_path):
    mod = _load(monkeypatch, tmp_path)
    running = {"run_id": 7, "status": "running", "spec": {"use_case_id": "mumbai_marathon"}}
    board = _board(mod, runs=[running], use_cases=[{"id": "mumbai_marathon"}, {"id": "shivaji_park_parade"}])
    plan = mod.plan_seed([mod.BY_ID["event-library"]], board)
    acts = {(a, arg) for a, arg, _ in plan}
    assert ("keep", "mumbai_marathon") in acts
    assert ("start", "shivaji_park_parade") in acts
    assert ("skip", "ganeshotsav_night") in acts
    assert ("evening", "") in acts           # delegated to demo_reset.sh ...
    assert plan[0][0] == "evening"           # ... before any start, since it stops other runs
    # the same seed named twice by two capabilities is planned once
    plan2 = mod.plan_seed([mod.BY_ID["escort"], mod.BY_ID["live-band"]], board)
    assert sum(1 for a, arg, _ in plan2 if arg == "vvip_convoy_base") == 1


def test_dss_targets_an_active_event_in_kind_order(monkeypatch, tmp_path):
    mod = _load(monkeypatch, tmp_path)
    events = [
        {"event_id": "a", "event_kind": "mass_gathering", "status": "active", "title": "Puja"},
        {"event_id": "b", "event_kind": "emergency_evacuation", "status": "active", "title": "Cloudburst"},
        {"event_id": "c", "event_kind": "emergency_evacuation", "status": "planning", "title": "Planned"},
    ]
    plan = mod.plan_seed([mod.BY_ID["dss"]], _board(mod, events=events))
    assert plan == [("dss", "b", "dss: decision support for 'Cloudburst'")]
    none = mod.plan_seed([mod.BY_ID["dss"]], _board(mod, events=[]))
    assert none[0][0] == "skip"


def test_checks_read_the_board(monkeypatch, tmp_path):
    mod = _load(monkeypatch, tmp_path)
    board = _board(mod,
                   events=[{"event_kind": "race", "status": "active"}],
                   recs=[{"rule_id": "R_STOLEN_SIGHTING", "status": "PENDING"},
                         {"rule_id": "R_SPD_SEGMENT", "status": "approved"}],
                   dispatches=[{"agency": "ambulance", "status": "requested"}])
    assert mod.check(board, "class:race")[0] and not mod.check(board, "class:procession")[0]
    assert mod.check(board, "stolen_sighting_pending")[0]
    assert not mod.check(board, "echallan_pending")[0]
    assert mod.check(board, "ambulance_requested")[0]
    assert mod.check(board, "decision_waiting")[0]


def test_reset_stops_only_this_tours_runs(monkeypatch, tmp_path, capsys):
    mod = _load(monkeypatch, tmp_path, apply=True)
    mod.save_state({"runs": [{"run_id": 11, "use_case_id": "shivaji_park_parade"},
                             {"run_id": 12, "use_case_id": "mumbai_marathon"}]})
    sent = []

    def fake_write(path, body):
        sent.append(path)
        return 202, {}

    monkeypatch.setattr(mod, "write", fake_write)
    board = _board(mod, runs=[{"run_id": 11, "status": "running"}, {"run_id": 12, "status": "completed"},
                              {"run_id": 30, "status": "running"}])   # 30: the living city, not ours
    assert mod.cmd_reset(board) == 0
    assert sent == ["/api/emulator/api/v1/emulator/runs/11/stop"]
    assert mod.load_state()["runs"] == []
    assert oct(os.stat(tmp_path / "tour.json").st_mode & 0o777) == "0o600"


def test_wrapper_refusals_and_offline_status(tmp_path):
    env = dict(os.environ, DEMO_TOUR_STATE=str(tmp_path / "t.json"))
    r = subprocess.run(["bash", str(WRAPPER), "--apply", "seed", "escort"], capture_output=True,
                       text=True, env=env, timeout=30)
    assert r.returncode == 2 and "--officer" in r.stderr
    r = subprocess.run(["bash", str(WRAPPER), "--apply", "--officer", "X", "status"], capture_output=True,
                       text=True, env=env, timeout=30)
    assert r.returncode == 2
    r = subprocess.run(["bash", str(WRAPPER), "list"], capture_output=True, text=True, env=env, timeout=30)
    assert r.returncode == 0 and "stolen-chain" in r.stdout and "storm-replay" in r.stdout
    dead = "http://127.0.0.1:9"
    env.update(DECK_URL=dead, ORACLE_URL=dead, BRAIN_URL=dead, EMULATOR_URL=dead, OSINT_URL=dead,
               SPEECH_URL=dead, FORECAST_URL=dead, VISION_URL=dead, HYDRO_URL=dead)
    r = subprocess.run(["bash", str(WRAPPER), "status", "escort"], capture_output=True, text=True,
                       env=env, timeout=60)
    assert r.returncode == 0 and "not answering" in r.stdout and "NEEDS SEED" in r.stdout


def test_a_running_evening_is_kept(monkeypatch, tmp_path):
    mod = _load(monkeypatch, tmp_path)
    runs = [{"run_id": i, "status": "running", "spec": {"use_case_id": uc}}
            for i, uc in enumerate(mod.EVENING_USE_CASES, start=1)]
    plan = mod.plan_seed([mod.BY_ID["stolen-chain"]], _board(mod, runs=runs))
    assert [a for a, _, _ in plan] == ["keep"]
