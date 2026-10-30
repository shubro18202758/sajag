"""Cross-model late interaction: documents encoded by pplx-embed-v2-late-9b, queries by -0.6b.

The two late models share one embedding space (their card: "the 0.6B model can query an index built with the 9B
model"). This scores that set-up from the token vectors ``eval_embed.py`` saved for both models, so it needs no
GPU: ``python cross_late.py`` → ``results/late-9b-docs+0.6b-queries.npz`` (+ ``.json`` for report.py).
"""

from __future__ import annotations

import json
import pickle
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
RES = HERE / "results"
CAP = 64


def _unit(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, np.float32)
    return x / (np.linalg.norm(x, axis=-1, keepdims=True) + 1e-12)


def maxsim(q: np.ndarray, d: np.ndarray) -> float:
    return float((_unit(q) @ _unit(d).T).max(axis=1).mean()) if len(q) and len(d) else 0.0


def main() -> None:
    small = pickle.loads((RES / "pplx-embed-v2-late-0.6b.vectors.pkl").read_bytes())
    big = pickle.loads((RES / "pplx-embed-v2-late-9b.vectors.pkl").read_bytes())
    mats = {}
    for task in ("memory", "sop"):
        qs, ds = small[f"{task}_queries"], big[f"{task}_docs"]
        mats[task] = np.array([[maxsim(q, d) for d in ds] for q in qs], np.float32)
        mats[f"{task}_cap64"] = np.array([[maxsim(q[:CAP], d[:CAP]) for d in ds] for q in qs], np.float32)
    hq, hd = small["heads_q"], big["heads_d"]
    n = len(hq)
    m = np.zeros((n, n), np.float32)
    for i in range(n):
        for j in range(n):
            if i != j:
                m[i, j] = 0.5 * (maxsim(hq[i], hd[j]) + maxsim(hq[j], hd[i]))
    mats["osint"] = m
    name = "late-9b-docs+0.6b-queries"
    np.savez_compressed(RES / f"{name}.npz", **mats)
    meta_q = json.loads((RES / "pplx-embed-v2-late-0.6b.json").read_text())
    meta_d = json.loads((RES / "pplx-embed-v2-late-9b.json").read_text())
    meta = {"candidate": name, "repo": "0.6b queries x 9b documents", "family": "late", "dtype": "fp32/bf16",
            "dim": 128, "load_s": meta_q["load_s"], "weights_gib": meta_q["weights_gib"],
            "peak_alloc_gib": meta_q["peak_alloc_gib"], "reserved_gib": meta_q["reserved_gib"],
            "timing": {"query_ms_p50": meta_q["timing"]["query_ms_p50"],
                       "query_ms_p95": meta_q["timing"]["query_ms_p95"],
                       "memory_doc_ms": meta_d["timing"]["memory_doc_ms"],
                       "sop_doc_ms": meta_d["timing"]["sop_doc_ms"]},
            "note": "query-side cost of the 0.6b, document-side cost of the 9b"}
    (RES / f"{name}.json").write_text(json.dumps(meta, indent=1) + "\n")
    print(f"wrote {name}")


if __name__ == "__main__":
    main()
