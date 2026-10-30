"""Measure PII-Tracer against the OSINT rule redactor on the SYNTHETIC Mumbai set (``pii_eval_set.synthetic.json``).

Three phases, because the rule redactor and the model live in different environments:

    # 1. the rules (needs osint-common + osint-ingress importable: the service gate venv has their deps)
    python eval_pii.py rules --work <dir>
    # 2. the model (needs torch + transformers and the cached snapshot; GPU if present)
    python -I eval_pii.py model --work <dir>
    # 3. the scores (standard library only) → results.json and results.md next to this file
    python -I eval_pii.py score --work <dir>

Rules are measured as the parse-time redactor would run with the Mumbai pack: the OSINT gazetteer may still hold
the previous city's places, so phase 1 writes a stand-in gazetteer from ``cities/mumbai/landmarks.json`` (en, mr,
hi names) and points ``OSINT_GAZETTEER_PATH`` at it. Variants: ``rules_shared`` (``osint_common.ethics.pii_spans``,
the shared check), ``rules_news`` and ``rules_social`` (``osint_ingress.connectors._redact.redaction_spans`` in the
``news_regional`` and ``social_unverified`` tiers; the Indic ``[WITHHELD]`` rule included).

Model variants (``embedding_service.pii.postprocess``): ``model_raw`` (the decoder's spans as they are),
``model_snap`` (word-snapped, labels and score floor, no place guard), ``model_g1`` (guard with the landmark names
and the place-word rule only) and ``model_g2`` (the shipped default: landmarks, the place-word rule and the built-in
eponymous list, which was written alongside this set, so its place numbers flatter it; ``model_g1`` is the honest
generalisation figure). ``combo_*`` = a rules variant ∪ a guarded model variant.

Metrics, per language and overall: person P/R/F1 (overlap and exact), person character recall, all-PII P/R/F1
(person, phone, e-mail), and the false-positive counts on must-not-redact spans (places, office titles, public
emergency numbers): a protected mention counts once if any predicted span overlaps any part of it.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
SERVICE = HERE.parents[1]  # services/embedding-service
REPO = HERE.parents[3]
SET_PATH = HERE / "pii_eval_set.synthetic.json"
LANDMARKS = REPO / "cities" / "mumbai" / "landmarks.json"

sys.path.insert(0, str(SERVICE / "src"))

PERSON_RULE_KINDS = {"name", "script"}  # a withheld Indic run stands in for a name
PII_RULE_KINDS = {"name", "script", "contact"}
PERSON_MODEL_LABELS = {"private_person"}
PII_MODEL_LABELS = {"private_person", "private_email", "private_phone"}
GOLD_PII = {"person", "phone", "email"}
PROTECTED = ("place", "office", "public_number")
LANGS = ("en", "mr", "hi", "mr-Latn")


def load_set() -> list[dict]:
    return json.loads(SET_PATH.read_text(encoding="utf-8"))["items"]


# ── phase 1: rules ───────────────────────────────────────────────────────────────────────────────────────────────


def phase_rules(work: Path) -> None:
    work.mkdir(parents=True, exist_ok=True)
    lm = json.loads(LANDMARKS.read_text(encoding="utf-8"))["landmarks"]
    gaz = {
        "meta": {"note": "stand-in Mumbai gazetteer built from cities/mumbai/landmarks.json for this evaluation"},
        "entries": [
            {"gaz_id": i, "canonical_name": x["en"], "surface_forms": [x["en"], x["mr"], x.get("hi", "")]}
            for i, x in enumerate(lm, 1)
        ],
    }
    gpath = work / "mumbai_gazetteer.json"
    gpath.write_text(json.dumps(gaz, ensure_ascii=False), encoding="utf-8")
    os.environ["OSINT_GAZETTEER_PATH"] = str(gpath)
    for sub in ("osint-common", "osint-ingress"):
        sys.path.insert(0, str(REPO / "services" / sub / "src"))
    from osint_common import ethics  # noqa: PLC0415
    from osint_ingress.connectors import _redact  # noqa: PLC0415
    from osint_ingress.connectors._protect import load_protect  # noqa: PLC0415

    ethics.reset_place_phrases()
    protect = load_protect(gpath)
    out: dict[str, dict[str, list]] = {}
    t0 = time.perf_counter()
    for it in load_set():
        text = it["text"]
        out[it["id"]] = {
            "rules_shared": [[s.start, s.end, s.kind, s.label] for s in ethics.pii_spans(text, protect=protect)],
            "rules_news": [
                [s.start, s.end, s.kind, s.rule] for s in _redact.redaction_spans(text, "news_regional", protect)
            ],
            "rules_social": [
                [s.start, s.end, s.kind, s.rule] for s in _redact.redaction_spans(text, "social_unverified", protect)
            ],
        }
    dt = time.perf_counter() - t0
    (work / "rules_spans.json").write_text(
        json.dumps({"spans": out, "seconds": dt, "protect_phrases": len(protect)}, ensure_ascii=False), "utf-8"
    )
    print(f"rules: {len(out)} items in {dt:.2f}s; protect-set {len(protect)} phrases")


# ── phase 2: the model ───────────────────────────────────────────────────────────────────────────────────────────


def phase_model(work: Path, batch_size: int) -> None:
    import torch  # noqa: PLC0415

    from embedding_service.pii import PiiTracerDetector, ToponymGuard  # noqa: PLC0415

    work.mkdir(parents=True, exist_ok=True)
    items = load_set()
    texts = [it["text"] for it in items]
    det = PiiTracerDetector(batch_size=batch_size, guard=ToponymGuard(()))
    if torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()
    det.load()
    load_s = det.load_seconds
    mem_after_load = torch.cuda.max_memory_allocated() if det.device.startswith("cuda") else 0
    det.raw_spans(texts[:8])  # warm-up
    # latency, one sentence per call
    lat = []
    raw_single = []
    for t in texts:
        if det.device.startswith("cuda"):
            torch.cuda.synchronize()
        t0 = time.perf_counter()
        raw_single.append(det.raw_spans([t])[0])
        if det.device.startswith("cuda"):
            torch.cuda.synchronize()
        lat.append(time.perf_counter() - t0)
    # throughput, batched
    t0 = time.perf_counter()
    raw_batched = det.raw_spans(texts)
    if det.device.startswith("cuda"):
        torch.cuda.synchronize()
    batched_s = time.perf_counter() - t0
    peak = torch.cuda.max_memory_allocated() if det.device.startswith("cuda") else 0
    same = sum(
        1
        for a, b in zip(raw_single, raw_batched, strict=True)
        if [(s.start, s.end, s.label) for s in a] == [(s.start, s.end, s.label) for s in b]
    )
    lat_sorted = sorted(lat)
    stats = {
        "model": det.model_name,
        "device": det.device,
        "torch": torch.__version__,
        "load_seconds": round(load_s or 0.0, 2),
        "gpu_mem_after_load_gib": round(mem_after_load / 2**30, 3),
        "gpu_mem_peak_gib": round(peak / 2**30, 3),
        "latency_ms_bs1": {
            "mean": round(1000 * sum(lat) / len(lat), 1),
            "p50": round(1000 * lat_sorted[len(lat) // 2], 1),
            "p95": round(1000 * lat_sorted[int(len(lat) * 0.95) - 1], 1),
            "max": round(1000 * lat_sorted[-1], 1),
        },
        "batched": {
            "batch_size": batch_size,
            "seconds": round(batched_s, 3),
            "ms_per_sentence": round(1000 * batched_s / len(texts), 1),
        },
        "batched_equals_single": f"{same}/{len(texts)}",
    }
    out = {
        it["id"]: [[s.start, s.end, s.label, round(s.score, 4)] for s in spans]
        for it, spans in zip(items, raw_single, strict=True)
    }
    out_b = {
        it["id"]: [[s.start, s.end, s.label, round(s.score, 4)] for s in spans]
        for it, spans in zip(items, raw_batched, strict=True)
    }
    (work / "model_spans.json").write_text(
        json.dumps({"spans": out, "spans_batched": out_b, "stats": stats}, ensure_ascii=False), "utf-8"
    )
    det.unload()
    print(json.dumps(stats, indent=1))


# ── phase 3: scores ──────────────────────────────────────────────────────────────────────────────────────────────


def _overlap(a: tuple[int, int], b: tuple[int, int]) -> bool:
    return a[0] < b[1] and b[0] < a[1]


def _trim(text: str, s: int, e: int) -> tuple[int, int]:
    def word(c: str) -> bool:
        return c.isalnum() or unicodedata.category(c)[0] == "M"

    while s < e and not word(text[s]):
        s += 1
    while e > s and not word(text[e - 1]):
        e -= 1
    return s, e


def _prf(tp_p: int, n_p: int, tp_r: int, n_g: int) -> dict:
    p = tp_p / n_p if n_p else None
    r = tp_r / n_g if n_g else None
    f = 2 * p * r / (p + r) if p and r else (0.0 if p is not None and r is not None else None)
    return {
        "p": None if p is None else round(p, 3),
        "r": None if r is None else round(r, 3),
        "f1": None if f is None else round(f, 3),
        "pred": n_p,
        "gold": n_g,
    }


def score_config(items: list[dict], preds: dict[str, list[tuple[int, int, str]]]) -> dict:
    """``preds[id]`` = ``[(start, end, cls)]`` with ``cls`` in {"person", "contact", "other"}."""
    by_lang: dict[str, list[dict]] = defaultdict(list)
    for it in items:
        by_lang[it["lang"]].append(it)
    res: dict[str, dict] = {}
    for lang in (*LANGS, "all"):
        group = items if lang == "all" else by_lang.get(lang, [])
        c = Counter()
        for it in group:
            text = it["text"]
            gold_person = [(s["start"], s["end"]) for s in it["spans"] if s["type"] == "person"]
            gold_pii = [(s["start"], s["end"]) for s in it["spans"] if s["type"] in GOLD_PII]
            pr = preds.get(it["id"], [])
            pred_person = [(s, e) for s, e, k in pr if k == "person"]
            pred_pii = [(s, e) for s, e, k in pr if k in ("person", "contact")]
            all_pred = [(s, e) for s, e, _k in pr]
            # person, overlap
            c["pp"] += len(pred_person)
            c["pp_tp"] += sum(1 for p in pred_person if any(_overlap(p, g) for g in gold_person))
            c["gp"] += len(gold_person)
            c["gp_tp"] += sum(1 for g in gold_person if any(_overlap(p, g) for p in pred_person))
            # person, exact (boundaries trimmed of spaces and punctuation)
            gset = {_trim(text, *g) for g in gold_person}
            pset = {_trim(text, *p) for p in pred_person}
            c["ex_tp"] += len(gset & pset)
            c["ex_p"] += len(pset)
            # person characters covered (letters and marks only)
            for g in gold_person:
                for i in range(*g):
                    if text[i].isalnum() or unicodedata.category(text[i])[0] == "M":
                        c["ch_g"] += 1
                        c["ch_tp"] += any(p[0] <= i < p[1] for p in pred_person)
            # all PII
            c["ap"] += len(pred_pii)
            c["ap_tp"] += sum(1 for p in pred_pii if any(_overlap(p, g) for g in gold_pii))
            c["ag"] += len(gold_pii)
            c["ag_tp"] += sum(1 for g in gold_pii if any(_overlap(p, g) for p in pred_pii))
            # must-not-redact spans: any predicted span of any kind
            for s in it["spans"]:
                if s["type"] in PROTECTED:
                    c[f"n_{s['type']}"] += 1
                    c[f"fp_{s['type']}"] += any(_overlap(p, (s["start"], s["end"])) for p in all_pred)
        res[lang] = {
            "person_overlap": _prf(c["pp_tp"], c["pp"], c["gp_tp"], c["gp"]),
            "person_exact": _prf(c["ex_tp"], c["ex_p"], c["ex_tp"], c["gp"]),
            "person_char_recall": round(c["ch_tp"] / c["ch_g"], 3) if c["ch_g"] else None,
            "pii_overlap": _prf(c["ap_tp"], c["ap"], c["ag_tp"], c["ag"]),
            **{f"fp_{t}": f"{c[f'fp_{t}']}/{c[f'n_{t}']}" for t in PROTECTED},
        }
    return res


def _rules_preds(spans: list) -> list[tuple[int, int, str]]:
    out = []
    for s, e, kind, _rule in spans:
        cls = "person" if kind in PERSON_RULE_KINDS else "contact" if kind == "contact" else "other"
        out.append((s, e, cls))
    return out


def _model_preds(dicts: list[dict]) -> list[tuple[int, int, str]]:
    out = []
    for d in dicts:
        lab = d["label"]
        cls = "person" if lab in PERSON_MODEL_LABELS else "contact" if lab in PII_MODEL_LABELS else "other"
        out.append((d["start"], d["end"], cls))
    return out


def phase_score(work: Path) -> None:
    from embedding_service.pii import (  # noqa: PLC0415
        DEFAULT_LABELS,
        MUMBAI_EPONYMOUS_PLACES,
        RawSpan,
        ToponymGuard,
        load_landmark_names,
        postprocess,
    )

    items = load_set()
    rules = json.loads((work / "rules_spans.json").read_text("utf-8"))
    model = json.loads((work / "model_spans.json").read_text("utf-8"))
    raw = {k: [RawSpan(s, e, lab, sc) for s, e, lab, sc in v] for k, v in model["spans"].items()}
    raw_b = {k: [RawSpan(s, e, lab, sc) for s, e, lab, sc in v] for k, v in model["spans_batched"].items()}
    texts = {it["id"]: it["text"] for it in items}
    landmarks = load_landmark_names(LANDMARKS)
    guards = {
        "g1": ToponymGuard(landmarks),
        "g2": ToponymGuard(landmarks | frozenset(MUMBAI_EPONYMOUS_PLACES)),
    }

    def model_cfg(guard: str | None, min_score: float, labels=DEFAULT_LABELS, spans=None) -> dict[str, list]:
        g = guards[guard] if guard else None
        src = raw if spans is None else spans
        return {
            k: _model_preds(postprocess(texts[k], src[k], guard=g, labels=labels, min_score=min_score))
            for k in texts
        }

    configs: dict[str, dict[str, list]] = {}
    for v in ("rules_shared", "rules_news", "rules_social"):
        configs[v] = {k: _rules_preds(rules["spans"][k][v]) for k in texts}
    configs["model_raw"] = {
        k: [
            (s.start, s.end, "person" if s.label in PERSON_MODEL_LABELS else "contact" if s.label in PII_MODEL_LABELS
             else "other")
            for s in raw[k]
        ]
        for k in texts
    }
    configs["model_snap"] = model_cfg(None, 0.5)
    configs["model_g1"] = model_cfg("g1", 0.5)
    configs["model_g2"] = model_cfg("g2", 0.5)
    configs["model_g2_batched"] = model_cfg("g2", 0.5, spans=raw_b)
    for rv in ("rules_news", "rules_social"):
        for g in ("g1", "g2"):
            configs[f"combo_{rv.split('_')[1]}_{g}"] = {
                k: configs[rv][k] + configs[f"model_{g}"][k] for k in texts
            }
    results = {name: score_config(items, preds) for name, preds in configs.items()}

    # the model's additions on top of the rules: protected spans that only the model part hits
    added: dict[str, dict[str, int]] = {}
    for combo, rv, mv in (("combo_news_g1", "rules_news", "model_g1"), ("combo_news_g2", "rules_news", "model_g2")):
        c = Counter()
        for it in items:
            for s in it["spans"]:
                if s["type"] not in PROTECTED:
                    continue
                g = (s["start"], s["end"])
                by_rules = any(_overlap((a, b), g) for a, b, _ in configs[rv][it["id"]])
                by_model = any(_overlap((a, b), g) for a, b, _ in configs[mv][it["id"]])
                c[s["type"]] += by_model and not by_rules
            for s in it["spans"]:
                if s["type"] == "person":
                    g = (s["start"], s["end"])
                    by_rules = any(_overlap((a, b), g) and k == "person" for a, b, k in configs[rv][it["id"]])
                    by_model = any(_overlap((a, b), g) and k == "person" for a, b, k in configs[mv][it["id"]])
                    c["person_only_model"] += by_model and not by_rules
                    c["person_only_rules"] += by_rules and not by_model
                    c["person_missed_both"] += not by_model and not by_rules
        added[combo] = dict(c)

    # thresholds (guard g2 and g1)
    sweep = {}
    for g in ("g1", "g2"):
        for t in (0.3, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95):
            r = score_config(items, model_cfg(g, t))["all"]
            sweep[f"{g}@{t}"] = {
                "person_overlap": r["person_overlap"],
                "fp_place": r["fp_place"],
                "fp_office": r["fp_office"],
            }

    # what the model does with plates and ages
    plates = []
    for it in items:
        for s in it["spans"]:
            if s["type"] in ("plate", "age", "public_number"):
                hits = [
                    (r.label, r.score) for r in raw[it["id"]] if _overlap((r.start, r.end), (s["start"], s["end"]))
                ]
                plates.append({"id": it["id"], "type": s["type"], "model": hits})
    label_counts = Counter(r.label for v in raw.values() for r in v)

    # model place errors before the guard, for the write-up (which protected mentions the raw model hits)
    raw_place_hits = []
    for it in items:
        for s in it["spans"]:
            if s["type"] == "place":
                hits = [r for r in raw[it["id"]] if _overlap((r.start, r.end), (s["start"], s["end"]))]
                if hits:
                    raw_place_hits.append(
                        {"id": it["id"], "place": s["text"], "labels": sorted({h.label for h in hits})}
                    )

    doc = {
        "set": SET_PATH.name,
        "synthetic": True,
        "n_items": len(items),
        "langs": dict(Counter(it["lang"] for it in items)),
        "gold": dict(Counter(s["type"] for it in items for s in it["spans"])),
        "model_stats": model["stats"],
        "rules_seconds": round(rules["seconds"], 3),
        "configs": results,
        "model_additions_vs_rules": added,
        "threshold_sweep": sweep,
        "model_label_counts_raw": dict(label_counts),
        "plates_ages_public_numbers": plates,
        "raw_model_place_hits": raw_place_hits,
        "guard_sizes": {k: v.size for k, v in guards.items()},
    }
    (HERE / "results.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", "utf-8")
    (HERE / "results.md").write_text(render_md(doc), "utf-8")
    print(render_md(doc))


def _f(x: object) -> str:
    return "–" if x is None else f"{x:.2f}" if isinstance(x, float) else str(x)


def render_md(doc: dict) -> str:
    st = doc["model_stats"]
    lines = [
        "# PII-Tracer vs the OSINT rules: SYNTHETIC Mumbai set",
        "",
        f"{doc['n_items']} SYNTHETIC sentences ({', '.join(f'{k} {v}' for k, v in doc['langs'].items())}); gold "
        f"{doc['gold'].get('person', 0)} person, {doc['gold'].get('phone', 0)} phone, {doc['gold'].get('email', 0)}"
        f" e-mail; must-not-redact {doc['gold'].get('place', 0)} place, {doc['gold'].get('office', 0)} office, "
        f"{doc['gold'].get('public_number', 0)} public number. Generated by `eval_pii.py`; see its docstring for the "
        "variants.",
        "",
        f"Model {st['model']} on {st['device']} (torch {st['torch']}): load {st['load_seconds']} s, GPU memory "
        f"{st['gpu_mem_after_load_gib']} GiB after load, {st['gpu_mem_peak_gib']} GiB peak; latency per sentence "
        f"(batch 1) mean {st['latency_ms_bs1']['mean']} ms, p50 {st['latency_ms_bs1']['p50']} ms, p95 "
        f"{st['latency_ms_bs1']['p95']} ms; batched ({st['batched']['batch_size']}) "
        f"{st['batched']['ms_per_sentence']} ms per sentence. Batched spans equal single-call spans: "
        f"{st['batched_equals_single']}.",
        "",
        "## Person names (overlap match) and protected-span false positives",
        "",
        "| config | lang | P | R | F1 | exact F1 | char R | all-PII F1 | FP place | FP office | FP public no. |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    order = [
        "rules_shared", "rules_news", "rules_social", "model_raw", "model_snap", "model_g1", "model_g2",
        "model_g2_batched", "combo_news_g1", "combo_news_g2", "combo_social_g2",
    ]
    for name in order:
        for lang in (*LANGS, "all"):
            r = doc["configs"][name][lang]
            po, pe, pa = r["person_overlap"], r["person_exact"], r["pii_overlap"]
            lines.append(
                f"| {name} | {lang} | {_f(po['p'])} | {_f(po['r'])} | {_f(po['f1'])} | {_f(pe['f1'])} | "
                f"{_f(r['person_char_recall'])} | {_f(pa['f1'])} | {r['fp_place']} | {r['fp_office']} | "
                f"{r['fp_public_number']} |"
            )
    lines += ["", "## What the model adds on top of `rules_news`", "", "| combo | counts |", "|---|---|"]
    for k, v in doc["model_additions_vs_rules"].items():
        lines.append(f"| {k} | {', '.join(f'{a}={b}' for a, b in sorted(v.items()))} |")
    lines += ["", "## Score floor (all languages)", "", "| guard@floor | person P | R | F1 | FP place | FP office |",
              "|---|---|---|---|---|---|"]
    for k, v in doc["threshold_sweep"].items():
        po = v["person_overlap"]
        lines.append(f"| {k} | {_f(po['p'])} | {_f(po['r'])} | {_f(po['f1'])} | {v['fp_place']} | {v['fp_office']} |")
    lines += ["", "## Plates, ages and public numbers (raw model labels)", ""]
    for p in doc["plates_ages_public_numbers"]:
        lines.append(f"- {p['id']} {p['type']}: {p['model'] or 'not tagged'}")
    lines += ["", f"Raw model label counts: {doc['model_label_counts_raw']}", ""]
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("phase", choices=("rules", "model", "score"))
    ap.add_argument("--work", type=Path, required=True)
    ap.add_argument("--batch-size", type=int, default=16)
    a = ap.parse_args()
    if a.phase == "rules":
        phase_rules(a.work)
    elif a.phase == "model":
        phase_model(a.work, a.batch_size)
    else:
        phase_score(a.work)


if __name__ == "__main__":
    main()
