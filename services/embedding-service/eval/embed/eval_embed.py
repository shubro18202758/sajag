"""Encode the SYNTHETIC eval set with one candidate model; save score matrices, latency and GPU memory.

    python -I eval_embed.py <candidate> [--device cuda] [--dtype auto|bf16|fp32]

One process per candidate (clean GPU accounting; the shared GB10 gets the memory back when it exits). Candidates
are listed in ``CANDIDATES``. Writes ``results/<candidate>.npz`` (score matrices) and ``results/<candidate>.json``
(timings, memory, shapes). ``report.py`` turns those into the tables.

How each family scores (mirrors production where production exists):

* ``dense``  (bge-m3, pplx-embed-v1-*): cosine of mean-pooled vectors (v1 vectors are unnormalised int8 values;
  the card says compare with cosine).
* ``late``   (pplx-embed-v2-late-*): MaxSim over 128-d token vectors, normalised by the query's token count (the
  brain's 0..1 scale). Saved twice: full token sets, and capped at 64 token vectors per document and query, which
  is what ``traffic.memory_docs`` stores today (``MAX_TOKEN_VECS_PER_DOC``).
* ``ctx``    (pplx-embed-context-v1-*, pplx-embed-v2-context-9b-preview): contextual chunk vectors. SOP paragraphs
  of one doc file are encoded together as the chunks of one document, the advisory strings of one language pack
  likewise; memory docs, rendered advisories and headlines are single-chunk documents. Queries: ``encode_queries``
  where the model has it (v2), else a single-chunk document (v1).

Memory task: as in ``api.embed_documents``, dense encoders see ``"<title>. <body>"`` and late encoders see the body.
OSINT task: a symmetric similarity per headline pair (late: mean of both MaxSim directions).
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
BGE_M3 = os.environ.get("BGE_M3_PATH", os.path.expanduser("~/models/bge-m3"))
CAP = 64  # traffic.memory_docs token-vector cap
DEVICE = "cuda"  # set from --device in main()

CANDIDATES: dict[str, tuple[str, str]] = {
    "bge-m3": ("dense", BGE_M3),
    "pplx-embed-v1-0.6b": ("dense", "perplexity-ai/pplx-embed-v1-0.6b"),
    "pplx-embed-v1-4b": ("dense", "perplexity-ai/pplx-embed-v1-4b"),
    "pplx-embed-v2-late-0.6b": ("late", "perplexity-ai/pplx-embed-v2-late-0.6b"),
    "pplx-embed-v2-late-9b": ("late", "perplexity-ai/pplx-embed-v2-late-9b"),
    "pplx-embed-context-v1-0.6b": ("ctx", "perplexity-ai/pplx-embed-context-v1-0.6b"),
    "pplx-embed-context-v1-4b": ("ctx", "perplexity-ai/pplx-embed-context-v1-4b"),
    "pplx-embed-v2-context-9b-preview": ("ctx", "perplexity-ai/pplx-embed-v2-context-9b-preview"),
}


def _on_cuda() -> bool:
    """CUDA accounting only for a CUDA run: a CPU run (``--device cpu``) never creates a CUDA context, which can
    fail on the shared unified-memory box (cuDevicePrimaryCtxRetain out of memory)."""
    import torch

    return DEVICE.startswith("cuda") and torch.cuda.is_available()


def _sync() -> None:
    import torch

    if _on_cuda():
        torch.cuda.synchronize()


def _unit(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=np.float32)
    return x / (np.linalg.norm(x, axis=-1, keepdims=True) + 1e-12)


def _maxsim(q: np.ndarray, d: np.ndarray) -> float:
    """Normalised MaxSim: mean over query tokens of the best cosine against the document tokens."""
    if len(q) == 0 or len(d) == 0:
        return 0.0
    return float((_unit(q) @ _unit(d).T).max(axis=1).mean())


class Runner:
    def __init__(self, name: str, device: str, dtype: str) -> None:
        import torch

        self.name, self.device = name, device
        self.family, self.repo = CANDIDATES[name]
        if dtype == "auto":  # 0.6b-late stays fp32 exactly as the live service loads it; the rest bf16
            dtype = "fp32" if name in ("bge-m3", "pplx-embed-v2-late-0.6b") else "bf16"
        self.dtype = dtype
        tdt = torch.bfloat16 if dtype == "bf16" else torch.float32
        if _on_cuda():
            torch.cuda.reset_peak_memory_stats()
        base = torch.cuda.memory_allocated() if _on_cuda() else 0
        t0 = time.perf_counter()
        if self.family == "dense":
            from sentence_transformers import SentenceTransformer

            self.model = SentenceTransformer(self.repo, device=device, trust_remote_code=True,
                                             model_kwargs={"dtype": tdt})
        elif self.family == "late":
            from sentence_transformers import MultiVectorEncoder

            # device_map streams each tensor to the GPU in the target dtype: the 9B checkpoint is stored in
            # fp32 (31 GiB) and a CPU-side load would push the shared box toward its memguard floor
            self.model = MultiVectorEncoder(self.repo, device=device,
                                            model_kwargs={"dtype": tdt, "device_map": device})
        else:
            from transformers import AutoModel

            # by repo id (HF_HUB_OFFLINE=1): a local snapshot path makes transformers load the config and the
            # model classes from two dynamic-module copies and the model's isinstance check fails
            self.model = AutoModel.from_pretrained(self.repo, trust_remote_code=True, dtype=tdt,
                                                   device_map=device).eval()
        _sync()
        self.load_s = time.perf_counter() - t0
        self.weights_gib = ((torch.cuda.memory_allocated() - base) / 2**30) if _on_cuda() else 0.0

    # ── encoders: return per-text arrays (dense: (dim,), late: (n_tok, 128)) ──
    def enc_queries(self, texts: list[str]) -> list[np.ndarray]:
        if self.family == "dense":
            return list(np.asarray(self.model.encode(texts, batch_size=16, convert_to_numpy=True), np.float32))
        if self.family == "late":
            return [t.float().cpu().numpy() for t in self.model.encode_query(texts, batch_size=16)]
        if hasattr(self.model, "encode_queries"):
            out = self.model.encode_queries([[t] for t in texts], batch_size=16)
        else:
            out = self.model.encode([[t] for t in texts], batch_size=16)
        return [np.asarray(o[0], np.float32) for o in out]

    def enc_docs(self, texts: list[str], groups: list[list[int]] | None = None) -> list[np.ndarray]:
        """``groups`` (ctx only): index lists of texts that are chunks of one document."""
        if self.family == "dense":
            return list(np.asarray(self.model.encode(texts, batch_size=16, convert_to_numpy=True), np.float32))
        if self.family == "late":
            return [t.float().cpu().numpy() for t in self.model.encode_document(texts, batch_size=16)]
        groups = groups or [[i] for i in range(len(texts))]
        out: list[np.ndarray | None] = [None] * len(texts)
        enc = self.model.encode([[texts[i] for i in g] for g in groups], batch_size=4)
        for g, arr in zip(groups, enc):
            arr = np.asarray(arr, np.float32)
            for j, i in enumerate(g):
                out[i] = arr[j]
        return out  # type: ignore[return-value]

    def score(self, qs: list[np.ndarray], ds: list[np.ndarray], cap: int | None = None) -> np.ndarray:
        if self.family == "late":
            c = (lambda a: a[:cap]) if cap else (lambda a: a)
            return np.array([[_maxsim(c(q), c(d)) for d in ds] for q in qs], np.float32)
        return _unit(np.stack(qs)) @ _unit(np.stack(ds)).T


def main() -> None:
    import torch

    ap = argparse.ArgumentParser()
    ap.add_argument("candidate", choices=sorted(CANDIDATES))
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--dtype", default="auto", choices=("auto", "bf16", "fp32"))
    ap.add_argument("--tag", default="", help="suffix for the result files (e.g. a dtype variant)")
    args = ap.parse_args()
    global DEVICE
    DEVICE = args.device
    out_name = args.candidate + (f"@{args.tag}" if args.tag else "")
    data = json.loads((HERE / "eval_set.synthetic.json").read_text(encoding="utf-8"))
    RESULTS.mkdir(exist_ok=True)

    r = Runner(args.candidate, args.device, args.dtype)
    print(f"[{r.name}] loaded in {r.load_s:.1f}s, weights {r.weights_gib:.2f} GiB ({r.dtype})", flush=True)
    mats: dict[str, np.ndarray] = {}
    timing: dict[str, float] = {}

    # warm-up (kernels, allocator) so latencies are steady-state
    r.enc_queries(["warm up the encoder"])
    r.enc_docs(["warm up the encoder with a short document"])

    # ── memory ──
    mem = data["memory"]
    late = r.family == "late"
    mdocs = [d["body"] if late else f"{d['title']}. {d['body']}" for d in mem["docs"]]
    _sync(); t0 = time.perf_counter()
    dvec = r.enc_docs(mdocs)
    _sync(); t_mdocs = time.perf_counter() - t0
    qvec = r.enc_queries([q["text"] for q in mem["queries"]])
    mats["memory"] = r.score(qvec, dvec)
    if late:
        mats["memory_cap64"] = r.score(qvec, dvec, cap=CAP)
        timing["memory_doc_tokens_mean"] = float(np.mean([len(d) for d in dvec]))

    # ── sop ──
    sop = data["sop"]
    stexts = [f"{d['title']}. {d['body']}" if d["title"] and d["id"].startswith("d:") else d["body"]
              for d in sop["docs"]]
    groups: dict[str, list[int]] = {}
    for i, d in enumerate(sop["docs"]):
        key = d["source"] if d["id"].startswith(("d:", "p:")) else d["id"]
        groups.setdefault(key, []).append(i)
    _sync(); t0 = time.perf_counter()
    sdvec = r.enc_docs(stexts, list(groups.values()) if r.family == "ctx" else None)
    _sync(); t_sdocs = time.perf_counter() - t0
    sqvec = r.enc_queries([q["text"] for q in sop["queries"]])
    mats["sop"] = r.score(sqvec, sdvec)
    if late:
        mats["sop_cap64"] = r.score(sqvec, sdvec, cap=CAP)
        timing["sop_doc_tokens_mean"] = float(np.mean([len(d) for d in sdvec]))
        timing["sop_docs_over_cap64"] = int(sum(len(d) > CAP for d in sdvec))
    if r.family == "ctx":  # the same model without context (each paragraph alone), to isolate the effect
        mats["sop_noctx"] = r.score(sqvec, r.enc_docs(stexts))
    if r.family != "late" and dvec[0].shape[-1] > 1024:
        # Matryoshka truncation to the store's vector(1024) column (first 1024 values, then renormalise)
        cut = lambda vs: [v[:1024] for v in vs]  # noqa: E731
        mats["memory_mrl1024"] = r.score(cut(qvec), cut(dvec))
        mats["sop_mrl1024"] = r.score(cut(sqvec), cut(sdvec))

    # ── osint ──
    heads = [h["text"] for h in data["osint"]["headlines"]]
    if late:
        hq, hd = r.enc_queries(heads), r.enc_docs(heads)
        n = len(heads)
        m = np.zeros((n, n), np.float32)
        for i in range(n):
            for j in range(n):
                if i != j:
                    m[i, j] = 0.5 * (_maxsim(hq[i], hd[j]) + _maxsim(hq[j], hd[i]))
        mats["osint"] = m
        # raw token vectors, for cross-model scoring (the 0.6b and 9b late models share one space)
        import pickle
        with open(RESULTS / f"{out_name}.vectors.pkl", "wb") as fh:
            pickle.dump({"memory_docs": dvec, "memory_queries": qvec, "sop_docs": sdvec, "sop_queries": sqvec,
                         "heads_q": hq, "heads_d": hd}, fh)
    else:
        hv = r.enc_docs(heads)
        mats["osint"] = _unit(np.stack(hv)) @ _unit(np.stack(hv)).T
        if hv[0].shape[-1] > 1024:
            h1 = _unit(np.stack([v[:1024] for v in hv]))
            mats["osint_mrl1024"] = h1 @ h1.T

    # ── latency: one query at a time (the brain's /search path), docs batched ──
    lat = []
    for q in [q["text"] for q in mem["queries"]] + [q["text"] for q in sop["queries"]]:
        _sync(); t0 = time.perf_counter()
        r.enc_queries([q])
        _sync(); lat.append((time.perf_counter() - t0) * 1000.0)
    lat.sort()
    timing.update({
        "query_ms_p50": statistics.median(lat),
        "query_ms_p95": lat[min(len(lat) - 1, int(0.95 * len(lat)))],
        "memory_doc_ms": t_mdocs * 1000.0 / len(mdocs),
        "sop_doc_ms": t_sdocs * 1000.0 / len(stexts),
    })
    dims = {"dense": int(dvec[0].shape[-1])}
    out = {
        "candidate": out_name, "repo": r.repo, "family": r.family, "dtype": r.dtype, "device": args.device,
        "load_s": round(r.load_s, 1), "weights_gib": round(r.weights_gib, 2),
        "peak_alloc_gib": round(torch.cuda.max_memory_allocated() / 2**30, 2) if _on_cuda() else None,
        "reserved_gib": round(torch.cuda.memory_reserved() / 2**30, 2) if _on_cuda() else None,
        "dim": dims["dense"], "timing": {k: round(v, 2) for k, v in timing.items()},
        "at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    np.savez_compressed(RESULTS / f"{out_name}.npz", **mats)
    (RESULTS / f"{out_name}.json").write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps(out), flush=True)


if __name__ == "__main__":
    sys.exit(main())
