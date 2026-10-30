"""No real person's name in this package (ethics rule 9; plan R13).

The PoC's ``_NAME_DENYLIST`` names a real person, so it is never ported or copied: this test reads its patterns
from the PoC source AT RUN TIME (``ast``, read in place), keeps them in memory, scans every file of this package
(and the committed gazetteer seed) and reports only sha256 prefixes. Skipped where the PoC is absent (CI).
"""

from __future__ import annotations

import ast
import hashlib
import os
import re
from pathlib import Path

import pytest

def _poc_root() -> Path:
    """The OSINT prototype, read in place: OSINT_POC_ROOT, else ``.orchestration/osint/prototype`` in this checkout
    or in the checkout whose ``.worktrees/<name>`` this is (absent in a clone, where the PoC tests skip)."""
    if os.environ.get("OSINT_POC_ROOT"):
        return Path(os.environ["OSINT_POC_ROOT"])
    for parent in Path(__file__).resolve().parents:
        candidate = parent / ".orchestration" / "osint" / "prototype"
        if candidate.is_dir():
            return candidate
    return Path(".orchestration/osint/prototype")


POC = _poc_root() / "sajag_osint_poc.py"
PACKAGE = Path(__file__).resolve().parents[1]
GAZETTEER = PACKAGE.parents[1] / "scripts" / "data" / "osint_gazetteer.json"

pytestmark = pytest.mark.skipif(not POC.is_file(), reason="PoC source not present (read in place only)")


def _denylist() -> list[re.Pattern[str]]:
    tree = ast.parse(POC.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "_NAME_DENYLIST" for t in node.targets
        ):
            out = []
            for call in node.value.elts:  # type: ignore[attr-defined]
                pattern = call.args[0].value
                flags = re.I if len(call.args) > 1 else 0
                out.append(re.compile(pattern, flags))
            return out
    raise AssertionError("_NAME_DENYLIST not found in the PoC source")


def _files() -> list[Path]:
    files = [p for p in PACKAGE.rglob("*") if p.is_file() and "__pycache__" not in p.parts]
    if GAZETTEER.is_file():
        files.append(GAZETTEER)
    return files


def test_no_denylisted_real_name_anywhere_in_the_package():
    patterns = _denylist()
    assert patterns, "the PoC denylist is empty"
    hits = []
    for path in _files():
        text = path.read_text(encoding="utf-8", errors="replace")
        for rx in patterns:
            if rx.search(text):
                hits.append((path.name, hashlib.sha256(rx.pattern.encode()).hexdigest()[:12]))
    assert not hits, hits
