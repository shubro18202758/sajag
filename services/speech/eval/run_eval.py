"""Synthetic round-trip evaluation of the speech service (Marathi, Hindi, English).

This is honest about what it measures: there are no recordings of officers.
Each phrase in ``phrases.json`` (Mumbai field reports, each tagged with its
language) is spoken by Indic Parler-TTS with four trained voices per
language (the two house advisory voices and two others), then transcribed.
WER/CER therefore measure ASR on *synthetic* speech, which is cleaner than a
field officer on a phone in the rain, and place/kind accuracy measure the
whole report pipeline on that audio. A separate stage (``real``) measures
WER/CER on a few real read-speech clips (FLEURS, CC BY 4.0) so the synthetic
numbers have a real-speech reference next to them.

    # 1. synthesize in-process with Indic Parler-TTS (the parler venv)
    python eval/run_eval.py synth-parler --audio /tmp/sajag-speech-eval
    #    (or through a running service: synth --base http://127.0.0.1:8505 --audio …)
    # 2. compare ASR checkpoints in-process on the same audio
    python eval/run_eval.py asr --audio /tmp/sajag-speech-eval --models openai/whisper-large-v3,...
    #    (an IndicConformer run is --models indic_conformer or indic_conformer@ctc)
    # 3. real read speech: fetch a few FLEURS clips, then score the checkpoints on them
    python eval/run_eval.py fetch-real --audio /tmp/sajag-speech-real --n 12
    python eval/run_eval.py real --audio /tmp/sajag-speech-real --models openai/whisper-large-v3,...
    # 4. end-to-end through the running service (POST /speech/report)
    python eval/run_eval.py api --base http://127.0.0.1:8505 --audio /tmp/sajag-speech-eval

Results go to ``eval/results.json`` (merged per stage), or to the file named
by ``--results``.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))

from speech_service.places import _mr_compose, fold_mr  # noqa: E402

PHRASES = json.loads((HERE / "phrases.json").read_text(encoding="utf-8"))["phrases"]
VOICES = ("female", "male", "alt1", "alt2")
LANGS = ("mr", "hi", "en")
RESULTS = HERE / "results.json"
_PUNCT = re.compile(r"[।॥,.!?;:\"'“”‘’()\-–—]")


def norm(text: str, fold: bool = False) -> str:
    t = _mr_compose(text)
    t = _PUNCT.sub(" ", t).lower()
    if fold:
        t = fold_mr(t)
    return " ".join(t.split())


def _lev(a: list, b: list) -> int:
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        cur = [i] + [0] * len(b)
        for j, y in enumerate(b, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (x != y))
        prev = cur
    return prev[-1]


def wer_cer(refs: list[str], hyps: list[str], fold: bool = False) -> tuple[float, float]:
    we = wn = ce = cn = 0
    for r, h in zip(refs, hyps):
        r, h = norm(r, fold), norm(h, fold)
        we += _lev(r.split(), h.split())
        wn += len(r.split())
        ce += _lev(list(r.replace(" ", "")), list(h.replace(" ", "")))
        cn += len(r.replace(" ", ""))
    return round(we / max(1, wn), 4), round(ce / max(1, cn), 4)


def _merge(key: str, value) -> None:
    doc = json.loads(RESULTS.read_text(encoding="utf-8")) if RESULTS.exists() else {}
    doc[key] = value
    RESULTS.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")


def _status_kib(pid: int | str, field: str) -> int | None:
    try:
        for line in Path(f"/proc/{pid}/status").read_text().splitlines():
            if line.startswith(field + ":"):
                return int(line.split()[1])
    except (OSError, ValueError, IndexError):
        pass
    return None


def _gpu_mib(pids: set[int]) -> float | None:
    """GPU memory the driver attributes to these processes (nvidia-smi), MiB.
    On the GB10 this is unified memory that does not show in the process RSS."""
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-compute-apps=pid,used_memory", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=20, check=True).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    total = None
    for line in out.splitlines():
        parts = [x.strip() for x in line.split(",")]
        if len(parts) == 2 and parts[0].isdigit() and int(parts[0]) in pids:
            try:
                total = (total or 0.0) + float(parts[1])
            except ValueError:
                pass
    return total


def proc_memory(pid: int | None = None) -> dict:
    """Resident memory of one process: RSS now and its peak (VmHWM), plus the
    GPU memory the driver attributes to it. Together they are what the model
    takes from the shared pool while it is loaded."""
    pid = pid or os.getpid()
    rss, hwm, gpu = _status_kib(pid, "VmRSS"), _status_kib(pid, "VmHWM"), _gpu_mib({pid})
    out = {"rss_gib": round(rss / 2**20, 2) if rss else None,
           "rss_peak_gib": round(hwm / 2**20, 2) if hwm else None,
           "gpu_gib": round(gpu / 1024, 2) if gpu is not None else None}
    out["resident_gib"] = round((out["rss_gib"] or 0) + (out["gpu_gib"] or 0), 2)
    return out


def _post(url: str, data: bytes, ctype: str, timeout: float = 600) -> tuple[bytes, dict]:
    req = urllib.request.Request(url, data=data, method="POST", headers={"Content-Type": ctype})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(), {k.lower(): v for k, v in r.headers.items()}


def cmd_synth(args) -> None:
    out = Path(args.audio)
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for voice in ("female", "male"):
        for p in PHRASES:
            body = json.dumps({"text": p["text"], "lang": p["lang"], "voice": voice}).encode()
            t0 = time.perf_counter()
            wav, hdr = _post(args.base.rstrip("/") + "/speech/speak", body, "application/json")
            dt = time.perf_counter() - t0
            (out / f"{p['id']}_{voice}.wav").write_bytes(wav)
            rows.append({"id": p["id"], "voice": voice, "seconds": float(hdr.get("x-speech-seconds", 0)),
                         "latency_s": round(dt, 2), "cached": hdr.get("x-speech-cached") == "1"})
            print(f"{p['id']} {voice} audio={rows[-1]['seconds']}s synth={dt:.1f}s", flush=True)
    fresh = [r for r in rows if not r["cached"]]
    rtf = [r["latency_s"] / r["seconds"] for r in fresh if r["seconds"]]
    _merge("tts", {
        "model": hdr.get("x-speech-model"), "voices": ["female", "male"],
        "n": len(rows), "audio_seconds_total": round(sum(r["seconds"] for r in rows), 1),
        "synth_seconds_median": round(statistics.median([r["latency_s"] for r in fresh]), 2) if fresh else None,
        "real_time_factor_median": round(statistics.median(rtf), 2) if rtf else None,
        "rows": rows,
    })


def cmd_synth_parler(args) -> None:
    """Every phrase in its own language, four Parler voices each, in this
    process (run with the parler venv). The house voices go through the
    service's own :class:`IndicParlerTTS`; the two others swap the speaker
    name in the same caption."""
    from speech_service.audio import encode_wav
    from speech_service.tts import PARLER_DESCRIPTION, PARLER_EVAL_SPEAKERS, PARLER_SPEAKERS, IndicParlerTTS

    out = Path(args.audio)
    out.mkdir(parents=True, exist_ok=True)
    tts = IndicParlerTTS(revision=os.environ.get("SPEECH_TTS_PARLER_REVISION") or None, min_free_gib=8)
    rows = []
    for p in PHRASES:
        for voice in VOICES:
            dest = out / f"{p['id']}_{voice}.wav"
            if voice in ("female", "male"):
                speaker = PARLER_SPEAKERS[(p["lang"], voice)]
                tts.description = PARLER_DESCRIPTION
                key = voice
            else:
                speaker = PARLER_EVAL_SPEAKERS[p["lang"]][int(voice[-1]) - 1]
                tts.description = PARLER_DESCRIPTION.replace("{speaker}", speaker)
                key = "female"  # caption() ignores the voice once the name is baked in
            if dest.exists() and not args.force:
                continue
            t0 = time.perf_counter()
            audio, sr = tts.synthesize(p["text"], p["lang"], key)
            dt = time.perf_counter() - t0
            dest.write_bytes(encode_wav(audio, sr))
            rows.append({"id": p["id"], "lang": p["lang"], "voice": voice, "speaker": speaker,
                         "seconds": round(audio.size / sr, 2), "latency_s": round(dt, 2)})
            print(f"{p['id']} {p['lang']} {voice}/{speaker} audio={rows[-1]['seconds']}s synth={dt:.1f}s",
                  flush=True)
    tts.unload()
    if rows:
        rtf = [r["latency_s"] / r["seconds"] for r in rows if r["seconds"]]
        _merge("tts", {
            "model": tts.model_id, "revision": tts.revision, "voices": {
                lang: {"female": PARLER_SPEAKERS[(lang, "female")], "male": PARLER_SPEAKERS[(lang, "male")],
                       "alt1": PARLER_EVAL_SPEAKERS[lang][0], "alt2": PARLER_EVAL_SPEAKERS[lang][1]}
                for lang in LANGS},
            "n": len(rows), "audio_seconds_total": round(sum(r["seconds"] for r in rows), 1),
            "synth_seconds_median": round(statistics.median(r["latency_s"] for r in rows), 2),
            "real_time_factor_median": round(statistics.median(rtf), 2) if rtf else None,
            "rows": rows,
        })


def _score(rows: list[dict]) -> dict:
    refs = [r["ref"] for r in rows]
    hyps = [r["hyp"] for r in rows]
    w, c = wer_cer(refs, hyps)
    wf, cf = wer_cer(refs, hyps, fold=True)
    return {
        "n": len(rows), "wer": w, "cer": c, "wer_folded": wf, "cer_folded": cf,
        "place_accuracy": round(sum(r["place_ok"] for r in rows) / len(rows), 3),
        "kind_accuracy": round(sum(r["kind_ok"] for r in rows) / len(rows), 3),
        "asr_seconds_median": round(statistics.median(r["asr_s"] for r in rows), 3),
    }


def _reset_gpu_peak() -> None:
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.reset_peak_memory_stats()
    except Exception:  # CPU-only run: no peak to report
        pass


def _gpu_peak_gib() -> dict | None:
    """Peak memory PyTorch's CUDA allocator held during the run (weights and
    activations; the CUDA context, about 0.5 GiB, is not included). A backend
    that runs outside PyTorch's allocator (ONNX Runtime) shows ~0 here."""
    try:
        import torch

        if not torch.cuda.is_available():
            return None
        return {"gpu_peak_alloc_gib": round(torch.cuda.max_memory_allocated() / 2**30, 2),
                "gpu_peak_reserved_gib": round(torch.cuda.max_memory_reserved() / 2**30, 2)}
    except Exception:
        return None


def asr_for_eval(spec: str, *, min_free_gib: float = 8):
    """``<hf-id>`` → a Whisper checkpoint; ``indic_conformer[:<hf-id>][@ctc|@rnnt]``
    → the IndicConformer adapter, with **no** fallback (a gated or missing
    model is reported as SKIPPED, never measured as something else)."""
    import os

    from speech_service.asr import IndicConformerASR, WhisperASR

    if spec.startswith("indic_conformer"):
        rest = spec[len("indic_conformer"):].lstrip(":")
        decoder = "rnnt"
        if "@" in rest:
            rest, decoder = rest.rsplit("@", 1)
        return IndicConformerASR(rest or IndicConformerASR.DEFAULT_MODEL, decoder=decoder,
                                 revision=os.environ.get("SPEECH_ASR_INDIC_CONFORMER_REVISION"),
                                 min_free_gib=min_free_gib)
    return WhisperASR(spec, min_free_gib=min_free_gib)


def cmd_asr(args) -> None:
    from speech_service.audio import decode_audio
    from speech_service.config import default_city_dir
    from speech_service.places import load_gazetteer
    from speech_service.report import build_report

    gaz = load_gazetteer(default_city_dir())
    audio = Path(args.audio)
    summary = {}
    for mid in args.models.split(","):
        asr = asr_for_eval(mid)
        if args.place_prompt and hasattr(asr, "prompts"):
            asr.prompts = {g: gaz.prompt(g) for g in LANGS}
            mid = f"{mid}+place-prompt"
        _reset_gpu_peak()
        mem_before = proc_memory()
        t0 = time.perf_counter()
        try:
            asr._lazy.get()
        except Exception as exc:  # one checkpoint that cannot load must not stop the rest
            print(mid, "SKIPPED:", exc, flush=True)
            continue
        load_s = round(time.perf_counter() - t0, 1)
        rows = []
        langs = [g for g in getattr(asr, "LANGS", LANGS) if g in args.langs.split(",")]
        for voice in VOICES:
            for p in PHRASES:
                f = audio / f"{p['id']}_{voice}.wav"
                if p["lang"] not in langs or not f.exists():
                    continue
                x, dur, _ = decode_audio(f.read_bytes())
                tr = asr.transcribe(x, p["lang"])
                rep = build_report(tr.text, gaz, source="field-voice", language=p["lang"])
                rows.append({"id": p["id"], "lang": p["lang"], "voice": voice, "ref": p["text"], "hyp": tr.text,
                             "confidence": tr.confidence, "asr_s": tr.seconds,
                             "place": (rep["place"] or {}).get("id"), "expected_place": p["place"],
                             "place_ok": (rep["place"] or {}).get("id") == p["place"],
                             "kind": rep["kind"], "expected_kind": p["kind"],
                             "kind_ok": rep["kind"] == p["kind"]})
        gpu_peak = _gpu_peak_gib()
        mem = proc_memory()  # with the model still loaded, after all the clips
        asr.unload()
        s = _score(rows)
        s["load_s"] = load_s
        s["asr_seconds_mean"] = round(statistics.mean(r["asr_s"] for r in rows), 3)
        s.update(gpu_peak or {})
        s["process_memory"] = {"before_load": mem_before, "loaded": mem}
        s["per_voice"] = {v: _score([r for r in rows if r["voice"] == v]) for v in VOICES
                          if any(r["voice"] == v for r in rows)}
        s["per_lang"] = {g: _score([r for r in rows if r["lang"] == g]) for g in LANGS
                         if any(r["lang"] == g for r in rows)}
        summary[mid] = {"summary": s, "rows": rows}
        print(mid, json.dumps(s), flush=True)
        # saved after every model, so one checkpoint failing loses nothing
        doc = json.loads(RESULTS.read_text(encoding="utf-8")) if RESULTS.exists() else {}
        doc.setdefault("asr_comparison", {})[mid] = summary[mid]
        RESULTS.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")


def cmd_detect(args) -> None:
    """lang=auto: which language the multilingual Whisper hears in each clip
    (Whisper's language-id head, restricted to mr/hi/en as the service does)."""
    from speech_service.audio import decode_audio

    asr = asr_for_eval(args.model)
    asr._lazy.get()
    rows = []
    for voice in VOICES:
        for p in PHRASES:
            f = Path(args.audio) / f"{p['id']}_{voice}.wav"
            if f.exists():
                x, _, _ = decode_audio(f.read_bytes())
                rows.append({"id": p["id"], "voice": voice, "lang": p["lang"], "detected": asr.detect(x)})
    asr.unload()
    per = {g: {"n": sum(r["lang"] == g for r in rows),
               "correct": sum(r["lang"] == g and r["detected"] == g for r in rows),
               "detected_as": {d: sum(r["lang"] == g and r["detected"] == d for r in rows) for d in LANGS}}
           for g in LANGS}
    print(json.dumps(per))
    _merge("language_detection", {"model": args.model, "per_lang": per, "rows": rows})


def cmd_api(args) -> None:
    audio = Path(args.audio)
    rows = []
    for voice in VOICES:
        for p in PHRASES:
            f = audio / f"{p['id']}_{voice}.wav"
            if not f.exists():
                continue
            t0 = time.perf_counter()
            body, _ = _post(args.base.rstrip("/") + f"/speech/report?lang={p['lang']}",
                            f.read_bytes(), "audio/wav")
            dt = time.perf_counter() - t0
            rep = json.loads(body)
            rows.append({"id": p["id"], "lang": p["lang"], "voice": voice, "ref": p["text"],
                         "hyp": rep["transcript"],
                         "asr_s": rep["asr"]["asr_seconds"], "latency_s": round(dt, 3),
                         "place": (rep["place"] or {}).get("id"),
                         "match_score": (rep["place"] or {}).get("match_score"),
                         "expected_place": p["place"],
                         "place_ok": (rep["place"] or {}).get("id") == p["place"],
                         "kind": rep["kind"], "expected_kind": p["kind"],
                         "kind_ok": rep["kind"] == p["kind"], "severity": rep["severity"],
                         "verification_state": rep["verification_state"]})
            r = rows[-1]
            print(f"{p['id']} {voice} place={r['place']}({'ok' if r['place_ok'] else 'MISS'}) "
                  f"kind={r['kind']}({'ok' if r['kind_ok'] else 'MISS'}) t={dt:.2f}s | {r['hyp']}",
                  flush=True)
    s = _score(rows)
    s["latency_s_median"] = round(statistics.median(r["latency_s"] for r in rows), 3)
    s["all_unverified_field"] = all(r["verification_state"] == "UNVERIFIED-FIELD" for r in rows)
    s["per_lang"] = {g: _score([r for r in rows if r["lang"] == g]) for g in LANGS
                     if any(r["lang"] == g for r in rows)}
    print(json.dumps(s, indent=1))
    _merge("api_end_to_end", {"summary": s, "rows": rows})


def cmd_rescore(_args) -> None:
    """Re-run place/kind on the saved transcripts with the current rules
    (ASR output is unchanged; only the report pipeline is re-applied)."""
    from speech_service.config import default_city_dir
    from speech_service.places import load_gazetteer
    from speech_service.report import build_report

    gaz = load_gazetteer(default_city_dir())
    doc = json.loads(RESULTS.read_text(encoding="utf-8"))
    for mid, v in doc.get("asr_comparison", {}).items():
        for r in v["rows"]:
            rep = build_report(r["hyp"], gaz, source="field-voice", language=r.get("lang", "mr"))
            r["place"] = (rep["place"] or {}).get("id")
            r["place_ok"] = r["place"] == r["expected_place"]
            r["kind"] = rep["kind"]
            r["kind_ok"] = rep["kind"] == r["expected_kind"]
        kept = {k: v["summary"][k]
                for k in ("load_s", "asr_seconds_mean", "gpu_peak_alloc_gib",
                          "gpu_peak_reserved_gib", "process_memory")
                if k in v["summary"]}
        v["summary"] = _score(v["rows"])
        v["summary"].update(kept)
        v["summary"]["per_voice"] = {x: _score([r for r in v["rows"] if r["voice"] == x])
                                     for x in VOICES if any(r["voice"] == x for r in v["rows"])}
        v["summary"]["per_lang"] = {g: _score([r for r in v["rows"] if r.get("lang") == g])
                                    for g in LANGS if any(r.get("lang") == g for r in v["rows"])}
        print(mid, json.dumps({k: v["summary"][k] for k in ("wer", "cer", "place_accuracy",
                                                             "kind_accuracy")}))
    RESULTS.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")


def cmd_text(_args) -> None:
    """Upper bound: the report pipeline on the reference text itself (no audio)."""
    from speech_service.config import default_city_dir
    from speech_service.places import load_gazetteer
    from speech_service.report import build_report

    gaz = load_gazetteer(default_city_dir())
    rows = []
    for p in PHRASES:
        rep = build_report(p["text"], gaz, source="field-text", language=p["lang"])
        rows.append({"id": p["id"], "lang": p["lang"], "place_ok": (rep["place"] or {}).get("id") == p["place"],
                     "kind_ok": rep["kind"] == p["kind"]})
    s = {"n": len(rows), "place_accuracy": round(sum(r["place_ok"] for r in rows) / len(rows), 3),
         "kind_accuracy": round(sum(r["kind_ok"] for r in rows) / len(rows), 3),
         "per_lang": {g: {"n": sum(r["lang"] == g for r in rows),
                          "place_ok": sum(r["place_ok"] for r in rows if r["lang"] == g),
                          "kind_ok": sum(r["kind_ok"] for r in rows if r["lang"] == g)} for g in LANGS}}
    print(s)
    _merge("reference_text", s)


FLEURS_CONFIG = {"mr": "mr_in", "hi": "hi_in", "en": "en_us"}
_FLEURS = "https://huggingface.co/datasets/google/fleurs/resolve/main/data/{cfg}/"


def cmd_fetch_real(args) -> None:
    """A few real read-speech clips per language from FLEURS (google/fleurs,
    CC BY 4.0): the split's transcript table, then the first ``--n`` clips of
    its audio archive, read as a stream and closed early (a few MB per
    language, never the whole archive)."""
    import csv
    import io
    import tarfile

    out = Path(args.audio)
    out.mkdir(parents=True, exist_ok=True)
    mf = out / "manifest.json"
    manifest = json.loads(mf.read_text(encoding="utf-8"))["clips"] if mf.exists() else []
    hdr = {"User-Agent": "sajag-speech-eval"}
    for lang in args.langs.split(","):
        if any(c["lang"] == lang for c in manifest):
            continue  # fetched before (the manifest is saved after each language)
        base = _FLEURS.format(cfg=FLEURS_CONFIG[lang])
        with urllib.request.urlopen(urllib.request.Request(base + f"{args.split}.tsv", headers=hdr),
                                    timeout=60) as r:
            table = r.read().decode("utf-8")
        refs = {}
        for row in csv.reader(io.StringIO(table), delimiter="\t", quoting=csv.QUOTE_NONE):
            if len(row) >= 4:
                refs[row[1]] = (row[2], row[3])  # file name → (raw, normalised) transcription
        got = 0
        with urllib.request.urlopen(urllib.request.Request(base + f"audio/{args.split}.tar.gz", headers=hdr),
                                    timeout=120) as r, tarfile.open(fileobj=r, mode="r|gz") as tar:
            for m in tar:
                name = Path(m.name).name
                if not m.isfile() or name not in refs:
                    continue
                f = tar.extractfile(m)
                dest = f"fleurs_{lang}_{name}"
                (out / dest).write_bytes(f.read())
                manifest.append({"file": dest, "lang": lang, "raw": refs[name][0], "ref": refs[name][1]})
                got += 1
                if got >= args.n:
                    break
        print(lang, got, "clips", flush=True)
        mf.write_text(json.dumps({
            "source": f"google/fleurs {args.split} split (CC BY 4.0), first clips of each language's archive",
            "clips": manifest}, ensure_ascii=False, indent=1), encoding="utf-8")


def cmd_real(args) -> None:
    """WER/CER of each checkpoint on the real FLEURS clips (no place/kind:
    these are general read sentences, not field reports)."""
    from speech_service.audio import decode_audio

    audio = Path(args.audio)
    man = json.loads((audio / "manifest.json").read_text(encoding="utf-8"))
    doc = json.loads(RESULTS.read_text(encoding="utf-8")) if RESULTS.exists() else {}
    real = doc.setdefault("real_speech", {"source": man["source"], "models": {}})
    for mid in args.models.split(","):
        asr = asr_for_eval(mid)
        if args.place_prompt and hasattr(asr, "prompts"):
            from speech_service.config import default_city_dir
            from speech_service.places import load_gazetteer

            gaz = load_gazetteer(default_city_dir())
            asr.prompts = {g: gaz.prompt(g) for g in LANGS}
            mid = f"{mid}+place-prompt"
        try:
            asr._lazy.get()
        except Exception as exc:
            print(mid, "SKIPPED:", exc, flush=True)
            continue
        langs = getattr(asr, "LANGS", LANGS)
        rows = []
        for c in man["clips"]:
            if c["lang"] not in langs:
                continue
            x, dur, _ = decode_audio((audio / c["file"]).read_bytes(), max_seconds=60)
            tr = asr.transcribe(x, c["lang"])
            ref = c["raw"] if c["lang"] != "en" else c["ref"]
            rows.append({"file": c["file"], "lang": c["lang"], "ref": ref, "hyp": tr.text,
                         "seconds": round(dur, 2), "asr_s": tr.seconds})
        asr.unload()
        per = {}
        for g in LANGS:
            sub = [r for r in rows if r["lang"] == g]
            if sub:
                w, ce = wer_cer([r["ref"] for r in sub], [r["hyp"] for r in sub])
                per[g] = {"n": len(sub), "wer": w, "cer": ce}
        real["models"][mid] = {"per_lang": per, "rows": rows}
        print(mid, json.dumps(per), flush=True)
        RESULTS.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")


def main() -> None:
    global RESULTS
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default=str(RESULTS),
                    help="the JSON file to merge results into (default: eval/results.json)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("synth"); a.add_argument("--base", required=True); a.add_argument("--audio", required=True)
    sp = sub.add_parser("synth-parler"); sp.add_argument("--audio", required=True)
    sp.add_argument("--force", action="store_true")
    fr = sub.add_parser("fetch-real"); fr.add_argument("--audio", required=True)
    fr.add_argument("--n", type=int, default=10); fr.add_argument("--split", default="dev")
    fr.add_argument("--langs", default="mr,hi,en")
    rl = sub.add_parser("real"); rl.add_argument("--audio", required=True); rl.add_argument("--models", required=True)
    rl.add_argument("--place-prompt", action="store_true")
    b = sub.add_parser("asr"); b.add_argument("--audio", required=True); b.add_argument("--models", required=True)
    b.add_argument("--place-prompt", action="store_true", help="give Whisper the city's place names as a prompt")
    b.add_argument("--langs", default="mr,hi,en", help="only the phrases of these languages")
    c = sub.add_parser("api"); c.add_argument("--base", required=True); c.add_argument("--audio", required=True)
    dt = sub.add_parser("detect"); dt.add_argument("--audio", required=True)
    dt.add_argument("--model", default="openai/whisper-large-v3-turbo")
    sub.add_parser("text")
    sub.add_parser("rescore")
    args = ap.parse_args()
    RESULTS = Path(args.results)
    {"synth": cmd_synth, "synth-parler": cmd_synth_parler, "detect": cmd_detect, "fetch-real": cmd_fetch_real,
     "real": cmd_real, "asr": cmd_asr, "api": cmd_api, "text": cmd_text,
     "rescore": cmd_rescore}[args.cmd](args)


if __name__ == "__main__":
    main()
