"""Tables from the saved score matrices: per task, per language, single models and combinations.

    python report.py            → results/summary.json + results/summary.md

Metrics: recall@1, recall@5 and MRR (a query is a hit when a gold document is ranked there; MRR uses the first
gold document). OSINT: every headline pair is labelled same-event or not; ROC-AUC over all pairs, the best-F1
threshold and its F1, F1 at the pipeline's current ``EMBED_THRESHOLD`` 0.70 (osint-analysis ``fusion.py``), and
nearest-neighbour recall@1 / MRR for headlines that have a same-event partner.

Combinations (computed, no extra encoding):
* ``live hybrid``: bge-m3 dense recall top-100 → pplx-embed-v2-late-0.6b MaxSim rerank on 64-token-capped
  vectors: what ``/search`` does today.
* ``<dense> → <late>``: the same pipeline with another dense recall model and/or uncapped late vectors.
* ``fuse(<a>+<b>)``: per-query z-score fusion of two models' scores (equal weights).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
LANGS = ("en", "mr", "hi", "mixed")
EMBED_THRESHOLD = 0.70


def load() -> tuple[dict, dict[str, dict], dict[str, dict]]:
    data = json.loads((HERE / "eval_set.synthetic.json").read_text(encoding="utf-8"))
    mats, meta = {}, {}
    for p in sorted(RESULTS.glob("*.npz")):
        if p.name.endswith(".osint.npz"):
            continue
        mats[p.stem] = dict(np.load(p))
        meta[p.stem] = json.loads(p.with_suffix(".json").read_text())
    return data, mats, meta


def retrieval(scores: np.ndarray, queries: list[dict], doc_ids: list[str]) -> dict:
    per: dict[str, list[tuple[int, int, float]]] = {k: [] for k in ("all",) + LANGS}
    for qi, q in enumerate(queries):
        order = np.argsort(-scores[qi], kind="stable")
        gold = set(q["gold"])
        rank = next((r for r, di in enumerate(order, 1) if doc_ids[di] in gold), None)
        row = (int(rank == 1), int(rank is not None and rank <= 5), 1.0 / rank if rank else 0.0)
        per["all"].append(row)
        per[q["lang"]].append(row)
    out = {}
    for k, rows in per.items():
        if rows:
            a = np.array(rows, dtype=float)
            out[k] = {"n": len(rows), "r1": round(a[:, 0].mean(), 3), "r5": round(a[:, 1].mean(), 3),
                      "mrr": round(a[:, 2].mean(), 3)}
    return out


def osint_metrics(sim: np.ndarray, heads: list[dict], threshold: float | None = EMBED_THRESHOLD) -> dict:
    n = len(heads)
    ev = [h["event"] for h in heads]
    iu = np.triu_indices(n, 1)
    s = sim[iu]
    y = np.array([ev[i] == ev[j] for i, j in zip(*iu)], dtype=bool)
    # ROC-AUC (Mann-Whitney)
    order = np.argsort(s, kind="stable")
    ranks = np.empty(len(s))
    ranks[order] = np.arange(1, len(s) + 1)
    npos, nneg = y.sum(), (~y).sum()
    auc = (ranks[y].sum() - npos * (npos + 1) / 2) / (npos * nneg)

    def f1_at(t: float) -> tuple[float, float, float]:
        pred = s >= t
        tp = (pred & y).sum()
        p = tp / pred.sum() if pred.sum() else 0.0
        r = tp / npos
        return (2 * p * r / (p + r) if p + r else 0.0), p, r

    best = max(((f1_at(t), t) for t in np.unique(s)), key=lambda x: x[0][0])
    out = {"pairs": int(len(s)), "positives": int(npos), "auc": round(float(auc), 3),
           "best_f1": round(float(best[0][0]), 3), "best_threshold": round(float(best[1]), 3),
           "best_p": round(float(best[0][1]), 3), "best_r": round(float(best[0][2]), 3)}
    if threshold is not None:
        f, p, r = f1_at(threshold)
        out.update({"f1_at_0.70": round(float(f), 3), "p_at_0.70": round(float(p), 3),
                    "r_at_0.70": round(float(r), 3)})
    # nearest neighbour
    nn1, mrr = [], []
    for i in range(n):
        if sum(e == ev[i] for e in ev) < 2:
            continue
        row = sim[i].copy()
        row[i] = -np.inf
        order = np.argsort(-row, kind="stable")
        rank = next(r for r, j in enumerate(order, 1) if ev[j] == ev[i])
        nn1.append(rank == 1)
        mrr.append(1.0 / rank)
    out["nn_r1"] = round(float(np.mean(nn1)), 3)
    out["nn_mrr"] = round(float(np.mean(mrr)), 3)
    # cross-script pairs only (Marathi/Hindi/romanised vs English): the hard half of dedup
    xs = np.array([(heads[i]["lang"] == "en") != (heads[j]["lang"] == "en") for i, j in zip(*iu)])
    if (y & xs).any():
        o2 = np.argsort(s[xs], kind="stable")
        r2 = np.empty(xs.sum())
        r2[o2] = np.arange(1, xs.sum() + 1)
        yy = y[xs]
        out["auc_cross_script"] = round(float((r2[yy].sum() - yy.sum() * (yy.sum() + 1) / 2)
                                              / (yy.sum() * (~yy).sum())), 3)
    return out


def zfuse(*ms: np.ndarray) -> np.ndarray:
    out = 0
    for m in ms:
        mu = m.mean(axis=1, keepdims=True)
        sd = m.std(axis=1, keepdims=True) + 1e-9
        out = out + (m - mu) / sd
    return out / len(ms)


def recall_rerank(dense: np.ndarray, late: np.ndarray, k: int = 100) -> np.ndarray:
    """Dense top-k recall then late rerank (non-recalled docs sink below every recalled one)."""
    out = np.full_like(late, -1e9)
    for qi in range(dense.shape[0]):
        top = np.argsort(-dense[qi], kind="stable")[:k]
        out[qi, top] = late[qi, top]
    return out


def main() -> None:
    data, mats, meta = load()
    mem_q, mem_ids = data["memory"]["queries"], [d["id"] for d in data["memory"]["docs"]]
    sop_q, sop_ids = data["sop"]["queries"], [d["id"] for d in data["sop"]["docs"]]
    heads = data["osint"]["headlines"]

    systems: dict[str, dict[str, np.ndarray]] = {}
    for name, m in mats.items():
        systems[name] = {"memory": m["memory"], "sop": m["sop"], "osint": m["osint"]}
        if "memory_cap64" in m:
            systems[f"{name} (cap64)"] = {"memory": m["memory_cap64"], "sop": m["sop_cap64"], "osint": m["osint"]}
        if "sop_mrl1024" in m:
            systems[f"{name} (MRL 1024)"] = {"memory": m["memory_mrl1024"], "sop": m["sop_mrl1024"],
                                              "osint": m["osint_mrl1024"]}
        if "sop_noctx" in m:
            systems[f"{name} (no context)"] = {"memory": m["memory"], "sop": m["sop_noctx"], "osint": m["osint"]}

    late_names = [n for n in mats if meta[n]["family"] == "late"]
    dense_names = [n for n in mats if meta[n]["family"] in ("dense", "ctx")]
    if "bge-m3" in mats and "pplx-embed-v2-late-0.6b" in mats:
        b, l6 = mats["bge-m3"], mats["pplx-embed-v2-late-0.6b"]
        systems["LIVE hybrid: bge-m3 → late-0.6b (cap64)"] = {
            "memory": recall_rerank(b["memory"], l6["memory_cap64"]),
            "sop": recall_rerank(b["sop"], l6["sop_cap64"]), "osint": l6["osint"]}
    # what /search returns: dense top-100 recall → MaxSim (cap64) or fused (dense + MaxSim cap64) ranking
    if "pplx-embed-v2-late-0.6b" in mats:
        l6 = mats["pplx-embed-v2-late-0.6b"]
        for d in dense_names:
            for variant, mk in (("", ""), (" MRL 1024", "_mrl1024")):
                if f"memory{mk}" not in mats[d]:
                    continue
                dm, ds = mats[d][f"memory{mk}"], mats[d][f"sop{mk}"]
                systems[f"/search fused: {d}{variant} → late-0.6b (cap64)"] = {
                    "memory": recall_rerank(dm, zfuse(dm, l6["memory_cap64"])),
                    "sop": recall_rerank(ds, zfuse(ds, l6["sop_cap64"])),
                    "osint": mats[d][f"osint{mk}"] if f"osint{mk}" in mats[d] else mats[d]["osint"]}
    for d in dense_names:
        for l in late_names:
            systems[f"fuse({d} + {l})"] = {
                "memory": zfuse(mats[d]["memory"], mats[l]["memory"]),
                "sop": zfuse(mats[d]["sop"], mats[l]["sop"]),
                "osint": zfuse(mats[d]["osint"], mats[l]["osint"])}

    summary: dict[str, dict] = {}
    for name, m in systems.items():
        o = osint_metrics(m["osint"], heads, EMBED_THRESHOLD if not name.startswith("fuse") else None)
        summary[name] = {"memory": retrieval(m["memory"], mem_q, mem_ids),
                         "sop": retrieval(m["sop"], sop_q, sop_ids), "osint": o}
    out = {"label": "SYNTHETIC eval set", "systems": summary,
           "models": {k: {kk: v for kk, v in meta[k].items()} for k in meta}}
    lines = ["# Embedding eval (SYNTHETIC Mumbai set; GB10, shared)", "",
             "Each model's dtype and device are in the cost table below. Candidates missing here were measured "
             "only on the earlier Kolkata-era set: `kolkata-era/summary.md`.", ""]
    lines += ["## Retrieval (recall@1 / recall@5 / MRR)", "",
              "| system | memory all | memory mr | memory hi | memory mixed | SOP all | SOP mr | SOP hi | SOP mixed |",
              "|---|---|---|---|---|---|---|---|---|"]

    def cell(r: dict, k: str) -> str:
        x = r.get(k)
        return f"{x['r1']:.2f} / {x['r5']:.2f} / {x['mrr']:.2f}" if x else "–"

    ranked = sorted((n for n in summary if "memory" in summary[n]),
                    key=lambda n: -(summary[n]["memory"]["all"]["mrr"] + summary[n]["sop"]["all"]["mrr"]))
    for n in ranked:
        s = summary[n]
        lines.append(f"| {n} | " + " | ".join([cell(s["memory"], k) for k in ("all", "mr", "hi", "mixed")]
                                               + [cell(s["sop"], k) for k in ("all", "mr", "hi", "mixed")]) + " |")
    lex = RESULTS / "lexical-jaccard.osint.npz"
    if lex.exists():
        z = np.load(lex)
        o = osint_metrics(z["osint"], heads, float(z["threshold"]))
        o["note"] = f"pipeline fallback: token Jaccard, links at {float(z['threshold']):.2f}"
        summary["lexical Jaccard (OSINT today)"] = {"osint": o}
    lines += ["", "## OSINT dedup (headline pairs)", "",
              "| system | AUC | AUC cross-script | best F1 (threshold) | F1 / P / R at the pipeline threshold (0.70 embedder; 0.20 lexical) | NN recall@1 | NN MRR |",
              "|---|---|---|---|---|---|---|"]
    for n in sorted(summary, key=lambda n: -summary[n]["osint"]["auc"]):
        o = summary[n]["osint"]
        at = (f"{o['f1_at_0.70']:.2f} / {o['p_at_0.70']:.2f} / {o['r_at_0.70']:.2f}" if "f1_at_0.70" in o else "–")
        lines.append(f"| {n} | {o['auc']:.3f} | {o.get('auc_cross_script', float('nan')):.3f} | "
                     f"{o['best_f1']:.2f} ({o['best_threshold']:.2f}) | {at} | {o['nn_r1']:.2f} | {o['nn_mrr']:.2f} |")
    lines += ["", "## Cost (one model per process)", "",
              "| model | dtype (device) | dim | load s | weights GiB | peak GiB | query ms p50 / p95 | doc ms (batched) |",
              "|---|---|---|---|---|---|---|---|"]
    for n, m in sorted(meta.items()):
        t = m["timing"]
        lines.append(f"| {n} | {m['dtype']} ({m.get('device', 'cuda')}) | {m['dim']} | {m['load_s']} | "
                     f"{m['weights_gib']} | "
                     f"{m['peak_alloc_gib']} | {t['query_ms_p50']:.0f} / {t['query_ms_p95']:.0f} | "
                     f"{t['sop_doc_ms']:.1f} |")
    (RESULTS / "summary.json").write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    (RESULTS / "summary.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
