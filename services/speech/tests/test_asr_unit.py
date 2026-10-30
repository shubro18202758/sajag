"""ASR helpers that need no model."""

from __future__ import annotations

from types import SimpleNamespace

from speech_service.asr import _CONTROL_RE, _complete_generation_config


class _Tok:
    unk_token_id = 0
    ids = {"<|en|>": 50259, "<|hi|>": 50276, "<|mr|>": 50302, "<|transcribe|>": 50359,
           "<|translate|>": 50358, "<|notimestamps|>": 50363}
    added_tokens_encoder = dict(ids)

    def convert_tokens_to_ids(self, t):
        return self.ids.get(t, 0)


def test_old_generation_configs_get_language_tables() -> None:
    model = SimpleNamespace(generation_config=SimpleNamespace())
    _complete_generation_config(model, _Tok())
    gc = model.generation_config
    assert gc.lang_to_id == {"<|en|>": 50259, "<|hi|>": 50276, "<|mr|>": 50302}
    assert gc.task_to_id == {"transcribe": 50359, "translate": 50358}
    assert gc.no_timestamps_token_id == 50363 and gc.is_multilingual


def test_complete_configs_are_left_alone() -> None:
    gc = SimpleNamespace(lang_to_id={"<|mr|>": 1}, task_to_id={"transcribe": 2})
    _complete_generation_config(SimpleNamespace(generation_config=gc), _Tok())
    assert gc.lang_to_id == {"<|mr|>": 1}


def test_leaked_control_tokens_are_stripped() -> None:
    raw = "<|startoftranscript|><|mr|><|transcribe|><|notimestamps|>बस अडकल्या आहेत."
    assert _CONTROL_RE.sub("", raw) == "बस अडकल्या आहेत."


def test_routing_by_language() -> None:
    import numpy as np

    from speech_service.asr import RoutedASR, Transcript

    class B:
        def __init__(self, name, detected="mr"):
            self.model_id, self.detected, self.calls = name, detected, []

        def transcribe(self, x, lang):
            self.calls.append(lang)
            return Transcript("t", lang, 0.9, self.model_id, 0.0)

        def detect(self, x):
            return self.detected

    mr, multi = B("indic-model"), B("multi-model", detected="hi")
    r = RoutedASR(mr, multi)  # default: Marathi and Hindi to the Indic backend
    x = np.zeros(16000, dtype=np.float32)
    assert r.transcribe(x, "mr").model == "indic-model"
    assert r.transcribe(x, "hi").model == "indic-model"
    assert r.transcribe(x, "en").model == "multi-model"
    t = r.transcribe(x, None)  # auto: detected by the multilingual model, then routed
    assert t.language == "hi" and t.model == "indic-model"
    multi.detected = "en"
    assert r.transcribe(x, None).model == "multi-model"
    assert mr.calls == ["mr", "hi", "hi"] and multi.calls == ["en", "en"]
    only_mr = RoutedASR(B("indic-model"), B("multi-model"), indic_langs=("mr",))
    assert only_mr.transcribe(x, "hi").model == "multi-model"
    assert only_mr.indic_langs == ("mr",)


def test_a_decoder_prompt_is_cut_from_the_output() -> None:
    from speech_service.asr import after_start_of_transcript

    SOT = 50258
    rows = after_start_of_transcript([[50361, 11, 12, 13, SOT, 50259, 50360, 7, 8, 50257], [SOT, 5, 6]], SOT)
    assert rows == [[SOT, 50259, 50360, 7, 8, 50257], [SOT, 5, 6]]
    assert after_start_of_transcript([[1, 2, 3]], SOT) == [[1, 2, 3]]  # no prompt: kept whole


def test_every_whisper_decoder_gets_the_place_prompts() -> None:
    from speech_service.api import make_asr
    from speech_service.asr import attach_place_prompts
    from speech_service.config import Settings

    r = make_asr(Settings())  # IndicConformer → Whisper fallback, plus the multilingual Whisper
    n = attach_place_prompts(r, {"en": "Mumbai traffic report. Hindmata, Worli Naka."})
    assert n == 2
    assert r.multi.prompts["en"].startswith("Mumbai traffic report.")
    assert r.mr.fallback.prompts == r.multi.prompts
    assert not hasattr(r.mr.preferred, "prompts")  # IndicConformer takes no prompt
