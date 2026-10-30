"""osint-geo tests: the helper modules beside the tests (``_synthetic``) import under any pytest import mode."""

from __future__ import annotations

import sys
from pathlib import Path

_HERE = str(Path(__file__).resolve().parent)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
