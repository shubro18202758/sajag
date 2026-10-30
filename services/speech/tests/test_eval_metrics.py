"""WER/CER as computed by eval/run_eval.py."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "speech_eval", Path(__file__).resolve().parents[1] / "eval" / "run_eval.py")
run_eval = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(run_eval)


def test_wer_cer_basic() -> None:
    w, c = run_eval.wer_cer(["हिंदमाता येथे गुडघाभर पाणी."], ["हिंदमाता येथे गुडघाभर पाणी"])
    assert (w, c) == (0.0, 0.0)  # punctuation is not scored
    w, _ = run_eval.wer_cer(["a b c d"], ["a x c d"])
    assert w == 0.25


def test_folded_cer_forgives_spelling_variants() -> None:
    ref, hyp = ["माहीम कॉजवेवर पाणी साचले"], ["माहिम कोजवेवर पानी साचले"]
    _, cer = run_eval.wer_cer(ref, hyp)
    _, cer_f = run_eval.wer_cer(ref, hyp, fold=True)
    assert cer > 0 and cer_f == 0.0


def test_eval_model_specs() -> None:
    from speech_service.asr import IndicConformerASR, WhisperASR

    w = run_eval.asr_for_eval("openai/whisper-large-v3")
    assert isinstance(w, WhisperASR)
    c = run_eval.asr_for_eval("indic_conformer")
    assert isinstance(c, IndicConformerASR) and c.decoder == "rnnt"
    assert c.model_id == "ai4bharat/indic-conformer-600m-multilingual"
    c2 = run_eval.asr_for_eval("indic_conformer:someone/other-conformer@ctc")
    assert c2.model_id == "someone/other-conformer" and c2.decoder == "ctc"
