"""Compare candidate decider runs with the reference run (results/*.json).

    python3 compare.py --ref v1-27b-live --cand flash-v1.2:per_question \\
        --cand flash-v1.2:joint [--out summary]

Per question type (choice / noul / score) and per brain question set:
  argmax agreement     choice: same option; noul: same side of 0.5;
                       score: same most-likely level
  mean |Δp|            choice: |p_cand(ref's choice) − p_ref(ref's choice)|;
                       noul: |ΔP(true)|; score: |Δ most-likely-level mass|
  score |Δvalue|       expected level, normalised to [0, 1] by (levels − 1)
Plus: accuracy on the requests that carry a synthetic ``expected`` answer,
the share of requests the brain would gate as low-confidence
(any answer's confidence < CONFIDENCE_FLOOR = 0.45, noul excluded, exactly as
convoy_brain.decider does), mean confidences, and latency percentiles.
SIMULATED scenarios only (see build_requests.py).
"""

from __future__ import annotations

import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
CONFIDENCE_FLOOR = 0.45


def load_run(spec: str) -> tuple[str, dict[str, Any], dict[str, Any]]:
    name, _, mode = spec.partition(":")
    run = json.loads((RESULTS / f"{name}.json").read_text())
    mode = mode or next(iter(run["modes"]))
    return f"{name}:{mode}", run, run["modes"][mode]


def qtype_of(answer: dict[str, Any]) -> str:
    dist = answer["distribution"]
    if answer["confidence"] is None and set(dist) == {"false", "true"}:
        return "noul"
    if all(k.isdigit() for k in dist) and isinstance(answer["value"], (int, float)):
        return "score"
    return "choice"


def argmax(dist: dict[str, float]) -> str:
    return max(dist, key=dist.get)


def mean(xs: list[float]) -> float | None:
    return round(statistics.fmean(xs), 4) if xs else None


def compare(ref_mode: dict[str, Any], cand_mode: dict[str, Any], requests: dict[str, Any]) -> dict[str, Any]:
    ref_rows = {r["id"]: r for r in ref_mode["results"] if r.get("answers")}
    cand_rows = {r["id"]: r for r in cand_mode["results"] if r.get("answers")}
    by_type: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    by_set: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    disagreements = []
    for rid, ref in ref_rows.items():
        cand = cand_rows.get(rid)
        if cand is None:
            continue
        kind = ref["kind"]
        for qname, ra in ref["answers"].items():
            ca = cand["answers"][qname]
            qt = qtype_of(ra)
            key = f"{kind}/{qname}"
            if qt == "choice":
                agree = float(ra["value"] == ca["value"])
                dp = abs(ca["distribution"].get(ra["value"], 0.0) - ra["probability"])
                by_type[qt]["agree"].append(agree)
                by_type[qt]["dp"].append(dp)
                by_set[key]["agree"].append(agree)
                by_set[key]["dp"].append(dp)
            elif qt == "noul":
                agree = float((ra["value"] >= 0.5) == (ca["value"] >= 0.5))
                dp = abs(ca["value"] - ra["value"])
                by_type[qt]["agree"].append(agree)
                by_type[qt]["dp"].append(dp)
                by_set[key]["agree"].append(agree)
                by_set[key]["dp"].append(dp)
                by_set[key]["ref_p"].append(ra["value"])
                by_set[key]["cand_p"].append(ca["value"])
            else:
                levels = len(ra["distribution"])
                ra_top, ca_top = argmax(ra["distribution"]), argmax(ca["distribution"])
                agree = float(ra_top == ca_top)
                dv = abs(float(ca["value"]) - float(ra["value"])) / max(1, levels - 1)
                dp = abs(ca["distribution"][ra_top] - ra["distribution"][ra_top])
                by_type[qt]["agree"].append(agree)
                by_type[qt]["dp"].append(dp)
                by_type[qt]["dvalue"].append(dv)
                by_set[key]["agree"].append(agree)
                by_set[key]["dvalue"].append(dv)
                by_set[key]["ref_v"].append(float(ra["value"]) / max(1, levels - 1))
                by_set[key]["cand_v"].append(float(ca["value"]) / max(1, levels - 1))
            if qt != "noul" and not by_set[key]["agree"][-1]:
                disagreements.append({"id": rid, "question": qname, "ref": ra["value"],
                                      "ref_p": round(ra["probability"], 3), "cand": ca["value"],
                                      "cand_p": round(ca["probability"], 3)})
    summarize = lambda d: {k: mean(v) for k, v in d.items()} | {"n": len(d.get("agree", []))}  # noqa: E731
    return {
        "by_type": {k: summarize(v) for k, v in sorted(by_type.items())},
        "by_question_set": {k: summarize(v) for k, v in sorted(by_set.items())},
        "disagreements": disagreements,
    }


def run_stats(mode: dict[str, Any], requests: dict[str, Any]) -> dict[str, Any]:
    rows = [r for r in mode["results"] if r.get("answers")]
    gated = 0
    conf: dict[str, list[float]] = defaultdict(list)
    correct = total = 0
    wrong = []
    for r in rows:
        confs = [a["confidence"] for a in r["answers"].values() if a["confidence"] is not None]
        if any(c < CONFIDENCE_FLOOR for c in confs):
            gated += 1
        for q, a in r["answers"].items():
            if a["confidence"] is not None:
                conf[f"{r['kind']}/{q}"].append(a["confidence"])
        for q, want in (requests[r["id"]].get("expected") or {}).items():
            if want is None:
                continue
            total += 1
            got = r["answers"][q]["value"]
            correct += int(got == want)
            if got != want:
                wrong.append({"id": r["id"], "question": q, "expected": want, "got": got})
    wall = [r["wall_ms"] for r in rows]
    tokens = [r["state_tokens"] for r in rows if r.get("state_tokens")]
    return {
        "requests": len(rows),
        "errors": mode.get("errors", 0),
        "accuracy_on_labelled": f"{correct}/{total}",
        "wrong_on_labelled": wrong,
        "low_confidence_gated_share": round(gated / len(rows), 3) if rows else None,
        "mean_confidence": {k: mean(v) for k, v in sorted(conf.items())},
        "wall_ms_p50": mode.get("wall_ms_p50"),
        "wall_ms_p95": mode.get("wall_ms_p95"),
        "server_ms_p50": mode.get("server_ms_p50"),
        "server_ms_p95": mode.get("server_ms_p95"),
        "state_tokens_mean": round(statistics.fmean(tokens), 1) if tokens else None,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", required=True)
    ap.add_argument("--cand", action="append", default=[])
    ap.add_argument("--requests", type=Path, default=HERE / "requests.json")
    ap.add_argument("--out", default="summary")
    args = ap.parse_args()
    requests = {r["id"]: r for r in json.loads(args.requests.read_text())["requests"]}
    ref_name, ref_run, ref_mode = load_run(args.ref)
    report: dict[str, Any] = {
        "label": "SIMULATED",
        "reference": {"name": ref_name, "model": ref_run.get("model"), **run_stats(ref_mode, requests)},
        "candidates": {},
    }
    for spec in args.cand:
        name, run, mode = load_run(spec)
        meta = {k: run.get(k) for k in ("model", "runtime", "temperature", "cold_load_s", "first_call_ms",
                                         "peak_allocated_gib", "peak_reserved_gib", "rss_gib", "rss_peak_gib",
                                         "after_load", "fast_path")}
        report["candidates"][name] = {**meta, **run_stats(mode, requests),
                                      "vs_reference": compare(ref_mode, mode, requests)}
    (RESULTS / f"{args.out}.json").write_text(json.dumps(report, indent=1))

    # compact text table
    lines = [f"reference {ref_name} ({report['reference']['model']}): "
             f"wall p50/p95 {report['reference']['wall_ms_p50']}/{report['reference']['wall_ms_p95']} ms, "
             f"labelled {report['reference']['accuracy_on_labelled']}, "
             f"gated {report['reference']['low_confidence_gated_share']}"]
    for name, c in report["candidates"].items():
        lines.append(f"\n{name}: wall p50/p95 {c['wall_ms_p50']}/{c['wall_ms_p95']} ms, labelled "
                     f"{c['accuracy_on_labelled']}, gated {c['low_confidence_gated_share']}, "
                     f"peak alloc {c['peak_allocated_gib']} GiB, load {c['cold_load_s']} s")
        for t, s in c["vs_reference"]["by_type"].items():
            lines.append(f"  {t:<8} n={s['n']:<3} agree={s.get('agree')} mean|dp|={s.get('dp')}"
                         + (f" mean|dvalue|={s.get('dvalue')}" if "dvalue" in s else ""))
        for k, s in c["vs_reference"]["by_question_set"].items():
            extra = ""
            if "ref_p" in s:
                extra = f" ref_P(true)={s['ref_p']} cand_P(true)={s['cand_p']}"
            if "ref_v" in s:
                extra = f" ref_v={s['ref_v']} cand_v={s['cand_v']}"
            lines.append(f"    {k:<42} n={s['n']:<3} agree={s.get('agree')}"
                         + (f" |dp|={s['dp']}" if s.get("dp") is not None else "")
                         + (f" |dv|={s['dvalue']}" if s.get("dvalue") is not None else "") + extra)
    text = "\n".join(lines)
    (RESULTS / f"{args.out}.txt").write_text(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
