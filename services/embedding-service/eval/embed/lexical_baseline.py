"""OSINT dedup baseline: what the pipeline links today without an embedder.

osint-analysis ``fusion.link_strength`` falls back to token Jaccard (``text_tokens`` + ``jaccard``) at
``LEXICAL_THRESHOLD`` 0.20 when no embedder answers, and today's embedding service has no ``/embed`` route, so
this is the live behaviour. Writes ``results/lexical-jaccard.osint.npz`` (pair similarity matrix).

    <the gate venv>/bin/python lexical_baseline.py   (needs sklearn and the osint packages on the path)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
for sub in ("services/osint-analysis/src", "services/osint-common/src"):
    sys.path.insert(0, str(REPO / sub))

from osint_analysis.fusion import LEXICAL_THRESHOLD, jaccard, text_tokens  # noqa: E402


def main() -> None:
    data = json.loads((HERE / "eval_set.synthetic.json").read_text(encoding="utf-8"))
    toks = [text_tokens(h["text"]) for h in data["osint"]["headlines"]]
    n = len(toks)
    m = np.array([[jaccard(toks[i], toks[j]) if i != j else 0.0 for j in range(n)] for i in range(n)], np.float32)
    (HERE / "results").mkdir(exist_ok=True)
    np.savez_compressed(HERE / "results" / "lexical-jaccard.osint.npz", osint=m,
                        threshold=np.array(LEXICAL_THRESHOLD, np.float32))
    print(f"lexical Jaccard matrix {m.shape}, pipeline threshold {LEXICAL_THRESHOLD}")


if __name__ == "__main__":
    main()
