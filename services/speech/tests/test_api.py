"""API contract tests (in-process; fake ASR/TTS; no GPU, no network)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from fakes import FakeASR, FakeTTS, tone_wav
from speech_service.api import create_app
from speech_service.config import Settings
from speech_service.places import Gazetteer
from speech_service.tts import TTSCache

HAS_MULTIPART = importlib.util.find_spec("multipart") is not None or \
    importlib.util.find_spec("python_multipart") is not None


@pytest.fixture()
def env(tmp_path: Path, gaz: Gazetteer):
    asr, tts = FakeASR(), FakeTTS()
    s = Settings(tts_cache_dir=tmp_path / "tts", max_audio_bytes=2_000_000)
    app = create_app(s, asr=asr, tts=tts, gazetteer=gaz, cache=TTSCache(tmp_path / "tts"))
    with TestClient(app) as c:
        yield c, asr, tts, tmp_path


def _wav(c: TestClient, path: str, data: bytes, ctype: str = "audio/wav", **params):
    return c.post(path, content=data, headers={"Content-Type": ctype}, params=params)


def test_health(env, gaz: Gazetteer) -> None:
    c, *_ = env
    b = c.get("/health").json()
    assert b["status"] == "ok" and b["service"] == "speech"
    assert b["places"]["landmarks"] == len(gaz.places)  # every cities/mumbai/landmarks.json entry
    assert "no speaker identification" in b["privacy"]


def test_transcribe_contract(env) -> None:
    c, asr, *_ = env
    r = _wav(c, "/speech/transcribe", tone_wav(1.0))
    assert r.status_code == 200
    b = r.json()
    assert set(b) >= {"text", "language", "confidence", "model"}
    assert b["language"] == "mr" and b["model"] == "fake-asr" and b["confidence"] == 0.87
    assert asr.calls == [(16000, "mr")]


def test_transcribe_language_choice(env) -> None:
    c, asr, *_ = env
    assert _wav(c, "/speech/transcribe", tone_wav(), lang="en").json()["language"] == "en"
    assert _wav(c, "/speech/transcribe", tone_wav(), lang="auto").status_code == 200
    assert asr.calls[-1][1] is None  # auto → the model detects
    assert _wav(c, "/speech/transcribe", tone_wav(), lang="fr").status_code == 422


def test_transcribe_rejects_bad_uploads(env) -> None:
    c, asr, *_ = env
    assert _wav(c, "/speech/transcribe", b"hello", "text/plain").status_code == 415
    assert _wav(c, "/speech/transcribe", b"garbage-bytes").status_code == 422
    assert _wav(c, "/speech/transcribe", tone_wav(0.05)).status_code == 422
    assert _wav(c, "/speech/transcribe", b"\0" * 2_100_000).status_code == 413
    assert asr.calls == []


def test_audio_is_not_stored(env) -> None:
    c, _asr, _tts, tmp = env
    before = sorted(p for p in tmp.rglob("*"))
    _wav(c, "/speech/transcribe", tone_wav(1.0))
    _wav(c, "/speech/report", tone_wav(1.0))
    assert sorted(p for p in tmp.rglob("*")) == before


def test_report_from_audio(env) -> None:
    c, *_ = env
    r = _wav(c, "/speech/report", tone_wav(1.0))
    assert r.status_code == 200
    b = r.json()
    assert b["place"]["id"] == "hindmata"
    assert b["place"]["name_mr"] == "हिंदमाता (दादर पूर्व)"
    assert b["place"]["match_score"] >= 0.8
    assert {"lat", "lon"} <= set(b["place"])
    assert b["kind"] == "waterlogging" and b["severity"] == "medium"
    assert b["transcript"] == "हिंदमाता येथे गुडघाभर पाणी साचले आहे, बस अडकल्या आहेत"
    assert b["verification_state"] == "UNVERIFIED-FIELD"
    assert b["requires_confirmation"] is True
    assert b["source"] == "field-voice" and b["asr"]["model"] == "fake-asr"
    assert set(b["note"]) == {"en", "mr", "hi"}  # the not-an-action note in all three UI languages


def test_report_from_text(env) -> None:
    c, asr, *_ = env
    r = c.post("/speech/report", json={"text": "लालबाग येथे मिरवणूक, रस्ता बंद"})
    b = r.json()
    assert b["place"]["id"] == "lalbaug"
    assert b["kind"] == "procession"
    assert b["verification_state"] == "UNVERIFIED-FIELD"
    assert b["source"] == "field-text" and b["asr"] is None
    assert asr.calls == []


def test_report_without_a_place_still_reports(env) -> None:
    c, *_ = env
    b = c.post("/speech/report", json={"text": "इथे प्रचंड वाहतूक कोंडी"}).json()
    assert b["place"] is None
    assert b["kind"] == "jam"
    assert b["verification_state"] == "UNVERIFIED-FIELD"


def test_report_rejects_bad_json(env) -> None:
    c, *_ = env
    assert c.post("/speech/report", json={"txt": "x"}).status_code == 422
    assert c.post("/speech/report", json={"text": ""}).status_code == 422


def test_speak_returns_wav_and_caches_by_hash(env) -> None:
    c, _asr, tts, tmp = env
    req = {"text": "हिंदमाता येथे पाणी साचले आहे. कृपया पर्यायी मार्ग वापरा.", "lang": "mr"}
    r1 = c.post("/speech/speak", json=req)
    assert r1.status_code == 200
    assert r1.headers["content-type"] == "audio/wav"
    assert r1.content[:4] == b"RIFF"
    assert r1.headers["x-speech-cached"] == "0"
    assert r1.headers["x-speech-voice"] == "mr-female"
    r2 = c.post("/speech/speak", json=req)
    assert r2.headers["x-speech-cached"] == "1"
    assert r2.content == r1.content
    assert len(tts.calls) == 1
    assert len(list((tmp / "tts").rglob("*.wav"))) == 1
    c.post("/speech/speak", json={**req, "voice": "male"})
    c.post("/speech/speak", json={**req, "lang": "en", "text": "Waterlogging at Hindmata."})
    assert len(tts.calls) == 3


def test_speak_validation(env) -> None:
    c, *_ = env
    assert c.post("/speech/speak", json={"text": "x", "lang": "gu"}).status_code == 422
    assert c.post("/speech/speak", json={"text": "", "lang": "mr"}).status_code == 422
    assert c.post("/speech/speak", json={"text": "क" * 700, "lang": "mr"}).status_code == 413
    assert c.post("/speech/speak", json={"text": "x", "lang": "mr", "voice": "child"}).status_code == 422


def test_model_unavailable_is_503(tmp_path: Path, gaz: Gazetteer) -> None:
    app = create_app(Settings(tts_cache_dir=tmp_path), asr=FakeASR(unavailable=True), tts=FakeTTS(),
                     gazetteer=gaz, cache=TTSCache(tmp_path))
    with TestClient(app) as c:
        r = _wav(c, "/speech/transcribe", tone_wav())
    assert r.status_code == 503
    assert "GiB available" in r.json()["detail"]


def test_models_are_unloaded_on_shutdown(tmp_path: Path, gaz: Gazetteer) -> None:
    asr = FakeASR()
    app = create_app(Settings(tts_cache_dir=tmp_path), asr=asr, tts=FakeTTS(), gazetteer=gaz,
                     cache=TTSCache(tmp_path))
    with TestClient(app):
        pass
    assert asr.unloaded


@pytest.mark.skipif(not HAS_MULTIPART, reason="python-multipart not installed")
def test_multipart_upload(env) -> None:
    c, *_ = env
    r = c.post("/speech/transcribe", files={"audio": ("r.wav", tone_wav(), "audio/wav")})
    assert r.status_code == 200


def test_gpu_oom_during_inference_is_503(tmp_path: Path, gaz: Gazetteer) -> None:
    class OomASR(FakeASR):
        def transcribe(self, samples, lang):
            raise RuntimeError("CUDA error: out of memory")

    app = create_app(Settings(tts_cache_dir=tmp_path), asr=OomASR(), tts=FakeTTS(),
                     gazetteer=gaz, cache=TTSCache(tmp_path))
    with TestClient(app) as c:
        r = _wav(c, "/speech/transcribe", tone_wav())
    assert r.status_code == 503 and "GPU memory" in r.json()["detail"]


def test_the_app_gives_whisper_the_city_place_names(tmp_path: Path, gaz: Gazetteer) -> None:
    from speech_service.asr import RoutedASR

    app = create_app(Settings(tts_cache_dir=tmp_path), tts=FakeTTS(), gazetteer=gaz)  # real (lazy) ASR
    asr = app.state.asr
    assert isinstance(asr, RoutedASR)
    assert asr.multi.prompts["en"] == gaz.prompt("en")
    off = create_app(Settings(tts_cache_dir=tmp_path, asr_place_prompt=False), tts=FakeTTS(), gazetteer=gaz)
    assert off.state.asr.multi.prompts == {}
