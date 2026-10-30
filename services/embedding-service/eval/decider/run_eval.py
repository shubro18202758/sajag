"""Run the decider request set against a model-host or a checkpoint in-process.

Two targets, one output format (results/<name>.json):

  HTTP (the live reference, or a post-switch check):
      python3 run_eval.py --http http://127.0.0.1:8083 --name v1-27b-live
    Sequential POST /decide, one at a time, waiting while the host reports a
    queue; never more than one request in flight. Records each C1 answer,
    the host's latency_ms and the wall time, plus /decider/health before
    and after.

  In-process (a candidate checkpoint through model-host's own backend):
      python3 -I run_eval.py --snapshot <snapshot dir> --modes per_question,joint \\
          --name flash-v1.2
    Loads the checkpoint once with model_host.decider_backends (the exact
    code the service runs), then answers the set in each question mode.
    Records cold load time, per-request latency, torch peak GPU memory and
    process RSS. A watchdog aborts the run if MemAvailable drops below
    --min-available-gib (shared unified-memory box).

Inputs: requests.json (build_requests.py). SIMULATED scenarios only.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
MODEL_HOST_SRC = HERE.parents[2] / "model-host" / "src"


def mem_available_gib() -> float:
    for line in Path("/proc/meminfo").read_text().splitlines():
        if line.startswith("MemAvailable:"):
            return int(line.split()[1]) / (1024 ** 2)
    return float("nan")


def proc_status_gib(field: str) -> float:
    for line in Path("/proc/self/status").read_text().splitlines():
        if line.startswith(field + ":"):
            return int(line.split()[1]) / (1024 ** 2)
    return float("nan")


def load_requests(path: Path, only: set[str] | None) -> list[dict[str, Any]]:
    reqs = json.loads(path.read_text())["requests"]
    return [r for r in reqs if not only or r["kind"] in only or r["id"] in only]


def pct(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, round(q * (len(ordered) - 1))))
    return round(ordered[idx], 1)


# ── HTTP target ──────────────────────────────────────────────────────────────


def _get(url: str, timeout: float = 5.0) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310 — fixed loopback URL
        return json.loads(resp.read())


def _post(url: str, body: dict[str, Any], timeout: float = 120.0) -> tuple[int, dict[str, Any]]:
    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 — fixed loopback URL
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, {"error": exc.read().decode(errors="replace")[:300]}


def run_http(base: str, requests: list[dict[str, Any]], pause_s: float) -> dict[str, Any]:
    if not base.startswith(("http://127.0.0.1:", "http://localhost:")):
        raise SystemExit("only a loopback model-host is allowed")
    health_before = _get(f"{base}/decider/health")
    if not health_before.get("loaded"):
        raise SystemExit(f"model-host not loaded: {health_before}")
    rows = []
    for r in requests:
        # be a polite guest on a shared, serialised host: never queue behind others
        for _ in range(60):
            if int(_get(f"{base}/decider/health").get("queue_depth", 0)) == 0:
                break
            time.sleep(1.0)
        t0 = time.perf_counter()
        status, body = _post(f"{base}/decide", {"request_id": f"eval-{r['id']}",
                                               "state": r["state"], "questions": r["questions"]})
        wall_ms = (time.perf_counter() - t0) * 1000
        rows.append({
            "id": r["id"], "kind": r["kind"], "status": status,
            "answers": body.get("answers"), "state_tokens": body.get("state_tokens"),
            "latency_ms": body.get("latency_ms"), "wall_ms": round(wall_ms, 1),
            "error": body.get("error"),
        })
        print(f"{r['id']:<40} {status} {wall_ms:8.1f} ms", flush=True)
        time.sleep(pause_s)
    health_after = _get(f"{base}/decider/health")
    wall = [x["wall_ms"] for x in rows if x["status"] == 200]
    server = [x["latency_ms"] for x in rows if x["status"] == 200 and x["latency_ms"] is not None]
    return {
        "target": base,
        "model": health_after.get("model"),
        "runtime": health_after.get("runtime", "autojev (pre-backend host)"),
        "question_mode": health_after.get("question_mode", "per_question"),
        "health_before": health_before,
        "health_after": health_after,
        "modes": {
            "served": {
                "results": rows,
                "wall_ms_p50": pct(wall, 0.5), "wall_ms_p95": pct(wall, 0.95),
                "server_ms_p50": pct(server, 0.5), "server_ms_p95": pct(server, 0.95),
                "errors": sum(1 for x in rows if x["status"] != 200),
            }
        },
    }


# ── in-process target ────────────────────────────────────────────────────────


class _Settings:
    """The subset of model_host.config.Settings that load_backend reads."""

    def __init__(self, snapshot: Path, mode: str, fast: bool) -> None:
        from model_host.decider_backends import model_name_from_snapshot

        self.snapshot_path = snapshot
        self.runtime = "auto"
        self.question_mode = mode
        self.fast = fast
        self.device = "cuda"
        self.offline = True
        self.max_state_tokens = 8192
        self.model_name = model_name_from_snapshot(snapshot)


def _watchdog(min_gib: float, stop: threading.Event) -> None:
    while not stop.is_set():
        avail = mem_available_gib()
        if avail < min_gib:
            print(f"[watchdog] MemAvailable {avail:.1f} GiB < {min_gib} GiB: aborting", flush=True)
            os._exit(3)
        stop.wait(0.5)


def run_inprocess(snapshot: Path, modes: list[str], requests: list[dict[str, Any]],
                  min_available_gib: float, fast: bool) -> dict[str, Any]:
    sys.path.insert(0, str(MODEL_HOST_SRC))
    avail = mem_available_gib()
    print(f"MemAvailable before load: {avail:.1f} GiB", flush=True)
    stop = threading.Event()
    threading.Thread(target=_watchdog, args=(min_available_gib, stop), daemon=True).start()

    import torch

    from model_host.decider_backends import c1_answer, load_backend

    settings = _Settings(snapshot, modes[0], fast)
    torch.cuda.reset_peak_memory_stats()
    t0 = time.perf_counter()
    backend = load_backend(settings, snapshot)
    torch.cuda.synchronize()
    load_s = time.perf_counter() - t0
    after_load = {
        "allocated_gib": round(torch.cuda.memory_allocated() / 2 ** 30, 3),
        "reserved_gib": round(torch.cuda.memory_reserved() / 2 ** 30, 3),
        "rss_gib": round(proc_status_gib("VmRSS"), 3),
        "mem_available_gib": round(mem_available_gib(), 1),
    }
    print(f"loaded {settings.model_name} in {load_s:.1f}s: {after_load}", flush=True)

    warm_q = {"self_test": {"type": "noul", "instructions": "Is this a warmup self-test message?"}}
    t1 = time.perf_counter()
    backend.decide("Warmup: convoy platform self-test.", warm_q)
    torch.cuda.synchronize()
    first_call_ms = (time.perf_counter() - t1) * 1000

    out_modes: dict[str, Any] = {}
    for mode in modes:
        backend.question_mode = mode
        rows = []
        for r in requests:
            t = time.perf_counter()
            raw, tokens = backend.decide(r["state"], r["questions"])
            torch.cuda.synchronize()
            wall_ms = (time.perf_counter() - t) * 1000
            rows.append({
                "id": r["id"], "kind": r["kind"], "status": 200,
                "answers": {k: c1_answer(raw[k]) for k in r["questions"]},
                "state_tokens": tokens, "latency_ms": round(wall_ms, 3), "wall_ms": round(wall_ms, 1),
            })
        wall = [x["wall_ms"] for x in rows]
        out_modes[mode] = {
            "results": rows,
            "wall_ms_p50": pct(wall, 0.5), "wall_ms_p95": pct(wall, 0.95),
            "wall_ms_mean": round(statistics.fmean(wall), 1),
            "errors": 0,
        }
        print(f"[{mode}] p50 {pct(wall, 0.5)} ms p95 {pct(wall, 0.95)} ms", flush=True)
    stop.set()
    return {
        "target": f"in-process {snapshot}",
        "model": settings.model_name,
        "runtime": backend.runtime,
        "temperature": getattr(backend, "temperature", None),
        "fast_path": bool(getattr(backend, "fast", False)),
        "cold_load_s": round(load_s, 1),
        "first_call_ms": round(first_call_ms, 1),
        "after_load": after_load,
        "peak_allocated_gib": round(torch.cuda.max_memory_allocated() / 2 ** 30, 3),
        "peak_reserved_gib": round(torch.cuda.max_memory_reserved() / 2 ** 30, 3),
        "rss_gib": round(proc_status_gib("VmRSS"), 3),
        "rss_peak_gib": round(proc_status_gib("VmHWM"), 3),
        "torch": torch.__version__,
        "device": torch.cuda.get_device_name(0),
        "modes": out_modes,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--requests", type=Path, default=HERE / "requests.json")
    ap.add_argument("--name", required=True)
    ap.add_argument("--http")
    ap.add_argument("--snapshot", type=Path)
    ap.add_argument("--modes", default="per_question,joint")
    ap.add_argument("--only", default="", help="comma-separated kinds or ids")
    ap.add_argument("--pause", type=float, default=0.3, help="seconds between HTTP requests")
    ap.add_argument("--min-available-gib", type=float, default=10.0)
    ap.add_argument("--fast", action="store_true", help="protocol v3 packed fast path")
    args = ap.parse_args()
    only = {x for x in args.only.split(",") if x} or None
    requests = load_requests(args.requests, only)
    if args.http:
        result = run_http(args.http.rstrip("/"), requests, args.pause)
    elif args.snapshot:
        result = run_inprocess(args.snapshot, [m for m in args.modes.split(",") if m], requests,
                               args.min_available_gib, args.fast)
    else:
        raise SystemExit("--http or --snapshot is required")
    result.update({"name": args.name, "label": "SIMULATED", "requests": len(requests),
                   "finished": time.strftime("%Y-%m-%dT%H:%M:%S%z")})
    out = HERE / "results" / f"{args.name}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(result, indent=1))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
