"""The gated preferred models (IndicConformer ASR, Indic Parler-TTS): config
switches, clear "gated" errors, and the fallback to the open models.

Offline: no network, no weights, no GPU. The adapters get fake loaders.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest
from fakes import FakeASR, FakeTTS, tone_wav
from fastapi.testclient import TestClient

from speech_service.api import create_app, make_asr, make_tts
from speech_service.asr import (
    FallbackASR,
    IndicConformerASR,
    RoutedASR,
    WhisperASR,
    assets_revision_error,
)
from speech_service.config import Settings
from speech_service.runtime import ModelNotProvisioned, ModelUnavailable, not_provisioned
from speech_service.tts import (
    PARLER_SPEAKERS,
    FallbackTTS,
    IndicParlerTTS,
    ParlerWorkerTTS,
    SvaraTTS,
    TTSCache,
    speak,
)

CONFORMER = "ai4bharat/indic-conformer-600m-multilingual"
PARLER = "ai4bharat/indic-parler-tts"


# --- the error message --------------------------------------------------------

class GatedRepoError(OSError):  # same name as huggingface_hub's, no import needed
    pass


class LocalEntryNotFoundError(OSError):
    pass


def test_gated_error_names_the_access_page() -> None:
    err = not_provisioned(CONFORMER, GatedRepoError("401 Client Error ... gated repo"), gated=True)
    assert isinstance(err, ModelNotProvisioned) and isinstance(err, ModelUnavailable)
    assert f"gated: request access at https://huggingface.co/{CONFORMER}" in str(err)


def test_offline_cache_miss_is_not_provisioned() -> None:
    err = not_provisioned(PARLER, LocalEntryNotFoundError("offline mode is enabled"), gated=True)
    assert err is not None
    assert "not in the local Hugging Face cache" in str(err)
    assert f"https://huggingface.co/{PARLER}" in str(err)
    assert "fetch_gated_models.sh" in str(err)


def test_missing_package_is_not_provisioned() -> None:
    err = not_provisioned(CONFORMER, ImportError("No module named 'onnxruntime'"), gated=True)
    assert err is not None and "onnxruntime" in str(err) and "gated: request access" in str(err)


def test_other_failures_stay_loud() -> None:
    cuda = RuntimeError("CUDA error: device-side assert")
    assert not_provisioned(CONFORMER, cuda, gated=True) is None


# --- IndicConformer adapter ---------------------------------------------------

def test_conformer_without_onnxruntime_says_so(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "onnxruntime", None)  # import fails, nothing is fetched
    asr = IndicConformerASR(CONFORMER, min_free_gib=0)
    asr._lazy._probe = lambda: 999.0
    with pytest.raises(ModelNotProvisioned, match="request access at https://huggingface.co/"):
        asr.transcribe(np.zeros(16000, dtype=np.float32), "mr")
    assert "onnxruntime" in asr.status()["last_error"]


def test_conformer_calls_the_model_as_the_card_does() -> None:
    calls = []

    def model(wav, lang, decoder):
        calls.append((tuple(wav.shape), lang, decoder))
        return "हिंदमाता येथे गुडघाभर पाणी"

    asr = IndicConformerASR(CONFORMER, decoder="ctc", loader=lambda: model, min_free_gib=0)
    asr._lazy._probe = lambda: 999.0
    tr = asr.transcribe(np.zeros(16000 * 2, dtype=np.float32), "mr")
    assert calls == [((1, 32000), "mr", "ctc")]
    assert tr.text == "हिंदमाता येथे गुडघाभर पाणी" and tr.language == "mr"
    assert tr.confidence is None  # the published inference gives no probabilities
    assert tr.model == f"{CONFORMER} (ctc)"


def test_conformer_chunks_long_audio_and_accepts_list_output() -> None:
    model_calls = []

    def model(wav, lang, decoder):
        model_calls.append(wav.shape[1])
        return [f"part{len(model_calls)}"]

    asr = IndicConformerASR(CONFORMER, loader=lambda: model, min_free_gib=0)
    asr._lazy._probe = lambda: 999.0
    tr = asr.transcribe(np.zeros(16000 * 45, dtype=np.float32), "mr")
    assert model_calls == [16000 * 30, 16000 * 15] and tr.text == "part1 part2"


def test_conformer_rejects_english_and_bad_decoder() -> None:
    asr = IndicConformerASR(CONFORMER, loader=lambda: (lambda *a: ""), min_free_gib=0)
    with pytest.raises(ValueError):
        asr.transcribe(np.zeros(16000, dtype=np.float32), "en")
    with pytest.raises(ValueError):
        IndicConformerASR(CONFORMER, decoder="beam")


# --- ASR fallback -------------------------------------------------------------

def _gated_loader():
    raise not_provisioned(CONFORMER, GatedRepoError("403 gated"), gated=True)


def test_fallback_asr_answers_with_whisper_when_gated() -> None:
    preferred = IndicConformerASR(CONFORMER, loader=_gated_loader, min_free_gib=0)
    preferred._lazy._probe = lambda: 999.0
    fallback = FakeASR()
    asr = FallbackASR(preferred, fallback)
    assert asr.model_id == CONFORMER
    x = np.zeros(16000, dtype=np.float32)
    tr = asr.transcribe(x, "mr")
    assert tr.model == "fake-asr" and asr.model_id == "fake-asr"
    st = asr.status()
    assert st["active"] == "fallback"
    assert f"gated: request access at https://huggingface.co/{CONFORMER}" in st["preferred_error"]
    # decided once: the gated model is not retried on every request
    preferred._lazy._loader = lambda: pytest.fail("retried the gated model")
    asr.transcribe(x, "mr")
    assert len(fallback.calls) == 2


def test_memory_refusal_is_not_a_reason_to_switch() -> None:
    preferred = IndicConformerASR(CONFORMER, loader=lambda: None, min_free_gib=12)
    preferred._lazy._probe = lambda: 3.0  # refused: below the floor
    asr = FallbackASR(preferred, FakeASR())
    with pytest.raises(ModelUnavailable) as exc:
        asr.transcribe(np.zeros(16000, dtype=np.float32), "mr")
    assert not isinstance(exc.value, ModelNotProvisioned)
    assert asr.preferred_error is None and asr.status()["active"] == "preferred"


def test_config_switches_the_asr_backend() -> None:
    default = make_asr(Settings())  # Mumbai default: IndicConformer (RNNT, pinned) first for mr/hi
    assert isinstance(default, RoutedASR) and isinstance(default.mr, FallbackASR)
    assert isinstance(default.mr.preferred, IndicConformerASR) and default.mr.preferred.decoder == "rnnt"
    assert default.mr.preferred.revision == "2a77d305038dfc502fd9464e7d028b90381976cb"
    assert default.indic_langs == ("mr", "hi")
    w = make_asr(Settings(asr_backend="whisper", asr_indic_langs="mr,en"))
    assert isinstance(w.mr, WhisperASR) and w.indic_langs == ("mr", "en")
    assert make_asr(Settings(asr_indic_langs="mr,en")).indic_langs == ("mr",)  # IndicConformer has no English
    s = Settings(asr_backend="indic_conformer", asr_indic_conformer_decoder="ctc",
                 asr_indic_conformer_revision="abc123")
    r = make_asr(s)
    assert isinstance(r.mr, FallbackASR)
    assert isinstance(r.mr.preferred, IndicConformerASR) and isinstance(r.mr.fallback, WhisperASR)
    assert r.mr.preferred.decoder == "ctc" and r.mr.preferred.revision == "abc123"
    assert r.mr.fallback.model_id == s.asr_model
    assert isinstance(r.multi, WhisperASR) and r.multi.model_id == s.asr_multilingual_model
    with pytest.raises(ValueError, match="SPEECH_ASR_BACKEND"):
        make_asr(Settings(asr_backend="indic-conformer"))


def test_api_reports_through_the_fallback(gaz, tmp_path: Path) -> None:
    preferred = IndicConformerASR(CONFORMER, loader=_gated_loader, min_free_gib=0)
    preferred._lazy._probe = lambda: 999.0
    asr = RoutedASR(FallbackASR(preferred, FakeASR()), FakeASR(lang="en"))
    app = create_app(Settings(tts_cache_dir=tmp_path), asr=asr, tts=FakeTTS(), gazetteer=gaz)
    with TestClient(app) as c:
        r = c.post("/speech/report", content=tone_wav(), headers={"content-type": "audio/wav"})
        assert r.status_code == 200, r.text
        rep = r.json()
        assert rep["asr"]["model"] == "fake-asr"
        assert rep["verification_state"] == "UNVERIFIED-FIELD"
        h = c.get("/health").json()
        assert h["asr"]["mr"]["active"] == "fallback"
        assert "gated: request access at" in h["asr"]["mr"]["preferred_error"]


# --- Indic Parler-TTS adapter and TTS fallback --------------------------------

def test_parler_without_package_says_so(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "parler_tts", None)
    tts = IndicParlerTTS(PARLER, min_free_gib=0)
    tts._lazy._probe = lambda: 999.0
    with pytest.raises(ModelNotProvisioned, match=f"https://huggingface.co/{PARLER}"):
        tts.synthesize("हिंदमाता येथे पाणी.", "mr", "female")


def test_parler_voices_cover_every_language_and_voice() -> None:
    for lang in ("mr", "en", "hi"):
        for voice in ("female", "male"):
            assert PARLER_SPEAKERS[(lang, voice)]
    t = IndicParlerTTS(PARLER, loader=lambda: None)
    assert t.caption("mr", "female").startswith("Sunita speaks in a calm, clear")
    assert t.caption("mr", "male").startswith("Sanjay ")
    assert "no background noise" in t.caption("en", "female")


def test_parler_generates_one_utterance_per_sentence() -> None:
    torch = pytest.importorskip("torch")

    class Enc(dict):
        def __getattr__(self, k):
            return self[k]

        def to(self, _device):
            return self

    class Tok:
        def __init__(self):
            self.seen = []

        def __call__(self, text, return_tensors="pt"):
            self.seen.append(text)
            ids = torch.ones(1, 3, dtype=torch.long)
            return Enc(input_ids=ids, attention_mask=ids)

    class Model:
        class config:
            sampling_rate = 44100

        def __init__(self):
            self.calls = 0

        def generate(self, **kw):
            assert {"input_ids", "attention_mask", "prompt_input_ids",
                    "prompt_attention_mask"} <= set(kw)
            self.calls += 1
            return torch.full((1, 4410), 0.5)

    tok, desc_tok, model = Tok(), Tok(), Model()
    t = IndicParlerTTS(PARLER, device="cpu", loader=lambda: (tok, desc_tok, model), min_free_gib=0)
    t._lazy._probe = lambda: 999.0
    audio, sr = t.synthesize("हिंदमाता येथे पाणी. पर्यायी मार्ग वापरा.", "mr", "female")
    assert sr == 44100 and model.calls == 2
    assert tok.seen == ["हिंदमाता येथे पाणी.", "पर्यायी मार्ग वापरा."]
    assert desc_tok.seen[0].startswith("Sunita ")
    assert audio.size == 4410 * 2 + int(0.22 * 44100)
    assert float(np.max(np.abs(audio))) <= 0.95 + 1e-6


def test_config_switches_the_tts_backend(tmp_path: Path) -> None:
    s = Settings(tts_backend="indic_parler", tts_gguf=tmp_path / "absent.gguf",
                 tts_parler_description="{speaker} reads slowly.")
    t = make_tts(s)
    assert isinstance(t, FallbackTTS)
    assert isinstance(t.preferred, IndicParlerTTS) and isinstance(t.fallback, SvaraTTS)
    assert t.preferred.caption("hi", "male") == "Rohit reads slowly."
    with pytest.raises(ValueError, match="SPEECH_TTS_BACKEND"):
        make_tts(Settings(tts_backend="parler"))


def test_tts_fallback_audio_is_cached_under_the_model_that_spoke(tmp_path: Path) -> None:
    def gated():
        raise not_provisioned(PARLER, GatedRepoError("403 gated"), gated=True)

    preferred = IndicParlerTTS(PARLER, loader=gated, min_free_gib=0)
    preferred._lazy._probe = lambda: 999.0
    fake = FakeTTS()
    tts = FallbackTTS(preferred, fake)
    cache = TTSCache(tmp_path)
    first = speak(tts, cache, "हिंदमाता येथे पाणी.", "mr", "female", "<clear>")
    assert not first.cached and first.model == "fake-tts"
    assert "gated: request access at" in tts.status()["preferred_error"]
    second = speak(tts, cache, "हिंदमाता येथे पाणी.", "mr", "female", "<clear>")
    assert second.cached and len(fake.calls) == 1
    # nothing was filed under the preferred (gated) model's key
    from speech_service.tts import LEVEL_FORMAT, PROMPT_FORMAT

    k = TTSCache.key(f"{PARLER}|{PROMPT_FORMAT}|{LEVEL_FORMAT}", "mr", "female", "<clear>", "हिंदमाता येथे पाणी.")
    assert cache.get(k) is None


def test_api_speaks_through_the_tts_fallback(gaz, tmp_path: Path) -> None:
    def gated():
        raise not_provisioned(PARLER, GatedRepoError("403 gated"), gated=True)

    preferred = IndicParlerTTS(PARLER, loader=gated, min_free_gib=0)
    preferred._lazy._probe = lambda: 999.0
    app = create_app(Settings(tts_cache_dir=tmp_path), asr=FakeASR(),
                     tts=FallbackTTS(preferred, FakeTTS()), gazetteer=gaz)
    with TestClient(app) as c:
        r = c.post("/speech/speak", json={"text": "हिंदमाता येथे पाणी साचले आहे.", "lang": "mr"})
        assert r.status_code == 200 and r.headers["x-speech-model"] == "fake-tts"
        assert r.headers["x-speech-label"] == "synthetic-voice"
        assert c.get("/health").json()["tts"]["active"] == "fallback"


# --- Parler in its own venv (worker over pipes) -------------------------------

class _FakeEngine:
    def __init__(self, fail=None):
        self.fail = fail
        self.calls = []

    def synthesize(self, text, lang, voice):
        if self.fail:
            raise self.fail
        self.calls.append((text, lang, voice))
        return np.full(441, 0.25, dtype=np.float32), 44100


def test_worker_protocol_round_trip() -> None:
    import io
    import json

    from speech_service.parler_worker import serve

    loaded = []
    speak_req = {"op": "synthesize", "text": "पाणी", "lang": "mr", "voice": "female"}
    req = b'{"op": "load"}\n' + json.dumps(speak_req).encode() + b'\n{"op": "nope"}\n'
    out = io.BytesIO()
    eng = _FakeEngine()
    serve(eng, lambda: loaded.append(1), io.BytesIO(req), out)
    stream = io.BytesIO(out.getvalue())
    assert json.loads(stream.readline()) == {"ok": True} and loaded == [1]
    head = json.loads(stream.readline())
    assert head == {"ok": True, "sr": 44100, "bytes": 441 * 4}
    audio = np.frombuffer(stream.read(head["bytes"]), dtype="<f4")
    assert audio.size == 441 and float(audio[0]) == 0.25
    bad = json.loads(stream.readline())
    assert bad["ok"] is False and bad["not_provisioned"] is False
    assert eng.calls == [("पाणी", "mr", "female")]


def test_worker_reports_the_gate() -> None:
    import io
    import json

    from speech_service.parler_worker import serve

    def gated_load():
        raise not_provisioned(PARLER, GatedRepoError("403 gated"), gated=True)

    out = io.BytesIO()
    serve(_FakeEngine(), gated_load, io.BytesIO(b'{"op": "load"}\n'), out)
    head = json.loads(out.getvalue().splitlines()[0])
    assert head["ok"] is False and head["not_provisioned"] is True
    assert f"gated: request access at https://huggingface.co/{PARLER}" in head["error"]


_FAKE_WORKER = r'''
import sys, numpy as np
from speech_service.parler_worker import serve
from speech_service.runtime import ModelNotProvisioned
mode = sys.argv[1]
print("library noise on stdout must not break the protocol")
class E:
    def synthesize(self, text, lang, voice):
        return np.linspace(-0.5, 0.5, 2205, dtype=np.float32), 22050
def load():
    if mode == "gated":
        raise ModelNotProvisioned(
            "gated: request access at https://huggingface.co/ai4bharat/indic-parler-tts")
import os
proto = os.fdopen(os.dup(1), "wb"); os.dup2(2, 1); sys.stdout = sys.stderr
serve(E(), load, sys.stdin.buffer, proto)
'''


def _worker(tmp_path: Path, mode: str) -> ParlerWorkerTTS:
    script = tmp_path / "fake_worker.py"
    script.write_text(_FAKE_WORKER, encoding="utf-8")
    t = ParlerWorkerTTS(sys.executable, PARLER, cmd=[sys.executable, str(script), mode],
                        min_free_gib=0, load_timeout_s=60, synth_timeout_s=60)
    t._lazy._probe = lambda: 999.0
    return t


def test_worker_process_speaks_and_stops(tmp_path: Path) -> None:
    t = _worker(tmp_path, "ok")
    try:
        audio, sr = t.synthesize("हिंदमाता येथे पाणी.", "mr", "female")
        assert sr == 22050 and audio.size == 2205 and audio.dtype == np.float32
        assert t.running and t.status()["worker_running"] is True
        audio2, _ = t.synthesize("पर्यायी मार्ग वापरा.", "mr", "male")  # same process, second request
        assert audio2.size == 2205
    finally:
        assert t.unload() is True
    assert not t.running


def test_gated_worker_falls_back_to_svara_stand_in(tmp_path: Path) -> None:
    t = _worker(tmp_path, "gated")
    fake = FakeTTS()
    tts = FallbackTTS(t, fake)
    audio, sr = tts.synthesize("हिंदमाता येथे पाणी.", "mr", "female")
    assert sr == 24000 and fake.calls and not t.running  # the failed worker was stopped
    assert "gated: request access at" in tts.status()["preferred_error"]


def test_missing_parler_venv_is_not_provisioned(tmp_path: Path) -> None:
    t = ParlerWorkerTTS(tmp_path / "no-venv" / "bin" / "python", PARLER, min_free_gib=0)
    t._lazy._probe = lambda: 999.0
    with pytest.raises(ModelNotProvisioned, match="Parler venv"):
        t.synthesize("पाणी.", "mr", "female")


def test_config_runs_parler_in_its_own_venv(tmp_path: Path) -> None:
    s = Settings(tts_backend="indic_parler", tts_gguf=tmp_path / "absent.gguf",
                 tts_parler_python="/opt/parler/bin/python")
    t = make_tts(s)
    assert isinstance(t.preferred, ParlerWorkerTTS)
    cmd = t.preferred.cmd()
    assert cmd[:3] == ["/opt/parler/bin/python", "-m", "speech_service.parler_worker"]
    assert cmd[cmd.index("--model") + 1] == PARLER
    assert "--revision" not in cmd  # unpinned: the worker loads what the cache holds


def test_config_pins_the_parler_revision(tmp_path: Path) -> None:
    kw = dict(tts_backend="indic_parler", tts_gguf=tmp_path / "absent.gguf",
              tts_parler_revision="abc123")
    worker = make_tts(Settings(tts_parler_python="/opt/parler/bin/python", **kw)).preferred
    assert worker.revision == "abc123"
    cmd = worker.cmd()
    assert cmd[cmd.index("--revision") + 1] == "abc123"
    in_process = make_tts(Settings(**kw)).preferred
    assert isinstance(in_process, IndicParlerTTS) and in_process.revision == "abc123"


# --- IndicConformer: the pin must cover the assets, not only the code ---------

PINNED = "2a77d305038dfc502fd9464e7d028b90381976cb"


def test_assets_from_the_pinned_commit_pass() -> None:
    folder = f"/hf/models--ai4bharat--indic-conformer-600m-multilingual/snapshots/{PINNED}"
    assert assets_revision_error(CONFORMER, folder, PINNED) is None
    assert assets_revision_error(CONFORMER, folder, PINNED[:12]) is None
    assert assets_revision_error(CONFORMER, folder, None) is None  # unpinned: not checked


def test_assets_from_another_commit_are_refused() -> None:
    why = assets_revision_error(CONFORMER, "/hf/snapshots/ffff0000", PINNED)
    assert why and "ffff0000" in why and PINNED in why and "fetch_gated_models.sh" in why


def _fake_remote_model(monkeypatch, folder: str) -> None:
    """The remote code's from_pretrained, as far as the adapter sees it."""
    import types

    class Model:
        config = types.SimpleNamespace(ts_folder=folder)

    class AutoModel:
        @staticmethod
        def from_pretrained(repo, trust_remote_code=False, revision=None):
            assert trust_remote_code
            return Model()

    monkeypatch.setitem(sys.modules, "onnxruntime", types.ModuleType("onnxruntime"))
    fake_tf = types.ModuleType("transformers")
    fake_tf.AutoModel = AutoModel
    monkeypatch.setitem(sys.modules, "transformers", fake_tf)


def test_conformer_with_unpinned_assets_falls_back(monkeypatch) -> None:
    _fake_remote_model(monkeypatch, "/hf/snapshots/0123newer")
    preferred = IndicConformerASR(CONFORMER, revision=PINNED, min_free_gib=0)
    preferred._lazy._probe = lambda: 999.0
    asr = FallbackASR(preferred, FakeASR())
    tr = asr.transcribe(np.zeros(16000, dtype=np.float32), "mr")
    assert tr.model == "fake-asr"
    assert "not the pinned revision" in asr.status()["preferred_error"]


def test_conformer_with_pinned_assets_loads(monkeypatch) -> None:
    _fake_remote_model(monkeypatch, f"/hf/snapshots/{PINNED}")
    c = IndicConformerASR(CONFORMER, revision=PINNED, min_free_gib=0)
    c._lazy._probe = lambda: 999.0
    assert c._lazy.get().config.ts_folder.endswith(PINNED)


def test_a_dead_parler_worker_hands_that_request_to_the_fallback(tmp_path: Path) -> None:
    from speech_service.tts import WorkerFailed

    class Flaky:
        model_id = PARLER

        def __init__(self) -> None:
            self.fail = True

        def synthesize(self, text, lang, voice):
            if self.fail:
                raise WorkerFailed("the Parler worker exited (code 1); see the service log")
            t = np.linspace(0, 0.5, 12000, endpoint=False)
            return (0.2 * np.sin(2 * np.pi * 330 * t)).astype(np.float32), 24000

        def status(self):
            return {"model": PARLER}

        def maybe_unload_idle(self):
            return False

    flaky, fake = Flaky(), FakeTTS()
    tts = FallbackTTS(flaky, fake)
    cache = TTSCache(tmp_path)
    first = speak(tts, cache, "हिंदमाता येथे पाणी.", "mr", "female", "<clear>")
    assert first.model == "fake-tts" and len(fake.calls) == 1  # the citizen still hears it, labelled honestly
    assert "exited" in tts.status()["last_worker_failure"] and tts.status()["preferred_error"] is None
    flaky.fail = False  # the worker comes back: the next request is the preferred voice again
    second = speak(tts, cache, "सायन येथे वाहतूक कोंडी.", "mr", "female", "<clear>")
    assert second.model == PARLER and len(fake.calls) == 1
