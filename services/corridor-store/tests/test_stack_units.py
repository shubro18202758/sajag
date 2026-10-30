"""scripts/sajag_up.sh --install-units links EVERY unit in infra/systemd (audit, 29 Oct).

The AI tier (sajag-ai.target and its six services) was missing from the
script's UNITS list: sajag.target Wants= sajag-ai.target, so on a fresh
machine the forecast, hydro, twin, speech, vision and city-feed services never
started at boot (the live box had them only because they were linked by hand).
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
SAJAG_UP = REPO / "scripts" / "sajag_up.sh"
UNIT_DIR = REPO / "infra" / "systemd"


def _units_array() -> list[str]:
    body = SAJAG_UP.read_text(encoding="utf-8")
    m = re.search(r"^UNITS=\(([^)]*)\)", body, re.MULTILINE)
    assert m, "sajag_up.sh has no UNITS=( … ) array"
    return m.group(1).split()


def _unit_files() -> set[str]:
    return {p.name for p in UNIT_DIR.iterdir() if p.suffix in (".service", ".target")}


def test_units_array_names_every_unit_file():
    units = _units_array()
    assert len(units) == len(set(units)), "a unit is listed twice"
    assert set(units) == _unit_files()


def test_the_ai_tier_is_linked():
    units = set(_units_array())
    for name in ("sajag-ai.target", "sajag-ai-forecast.service", "sajag-ai-hydro.service",
                 "sajag-ai-twin.service", "sajag-ai-speech.service", "sajag-ai-vision.service",
                 "sajag-feeds.service"):
        assert name in units


def test_every_wanted_unit_is_one_the_script_links():
    units = set(_units_array())
    for f in UNIT_DIR.iterdir():
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.startswith(("Wants=", "Requires=", "PartOf=")):
                for wanted in line.split("=", 1)[1].split():
                    assert wanted in units, f"{f.name}: {line} names {wanted}, which is never linked"


@pytest.mark.skipif(shutil.which("bash") is None, reason="needs bash")
def test_install_units_links_all_of_them_in_a_scratch_home(tmp_path):
    """--install-units against stub systemctl / loginctl / docker in a scratch HOME."""
    home, stubs, calls = tmp_path / "home", tmp_path / "bin", tmp_path / "calls.log"
    home.mkdir()
    stubs.mkdir()
    for cmd in ("systemctl", "loginctl", "docker"):
        stub = stubs / cmd
        stub.write_text(f'#!/bin/sh\necho "{cmd} $*" >> "{calls}"\n'
                        '[ "$1" = show-user ] && echo yes\nexit 0\n', encoding="utf-8")
        stub.chmod(0o755)
    env = {"HOME": str(home), "PATH": f"{stubs}:/usr/bin:/bin", "LANG": "C.UTF-8"}
    out = subprocess.run(["bash", str(SAJAG_UP), "--install-units"], env=env,
                         capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr[-2000:]
    linked = home / ".config" / "systemd" / "user"
    names = {p.name for p in linked.iterdir()}
    assert names == _unit_files()
    for p in linked.iterdir():
        assert p.is_symlink() and Path(os.readlink(p)) == UNIT_DIR / p.name
    log = calls.read_text(encoding="utf-8")
    assert "systemctl --user daemon-reload" in log
    assert "systemctl --user enable sajag.target" in log
    assert f"linked {len(names)} units" in out.stdout
