"""scripts/secret_scan.sh --selftest runs with the offline gates too (CI runs it on push).

Audit, 29 Oct: the scan read the literal values of only the PIN, the session
secret and the Cesium ion token. The open-data keys added since (WAQI, OpenAQ,
FIRMS, Mapillary, data.gov.in) and the ion dev/record tokens were looked for by
shape alone, and the Mapillary ``MLY|…|…`` token shape by none. The selftest
plants one of each and fails if a rule stays silent or a value is printed.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
SCAN = REPO / "scripts" / "secret_scan.sh"


@pytest.mark.skipif(shutil.which("git") is None or shutil.which("bash") is None,
                    reason="needs git and bash")
def test_every_rule_fires_on_its_planted_fake_and_no_value_is_printed(tmp_path):
    out = subprocess.run(["bash", str(SCAN), "--selftest"], capture_output=True, text=True,
                         timeout=300, env={"PATH": "/usr/bin:/bin", "HOME": str(tmp_path),
                                           "TMPDIR": str(tmp_path), "LANG": "C.UTF-8"})
    assert out.returncode == 0, (out.stdout + out.stderr)[-3000:]
    assert "secret_scan selftest: PASS" in out.stdout


def test_the_new_rules_are_in_the_selftest():
    body = SCAN.read_text(encoding="utf-8")
    assert "mapillary-token\t" in body and "env-credential-value" in body
    want = body[body.index("want=("):body.index(")", body.index("want=("))]
    assert "mapillary-token" in want and "env-credential-value" in want
