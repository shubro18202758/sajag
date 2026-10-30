"""TTS runtime selection and the llama-server child (no model is started)."""

from __future__ import annotations

from pathlib import Path

import pytest

from speech_service.api import make_tts
from speech_service.config import Settings
from speech_service.llama import LlamaServer
from speech_service.runtime import ModelUnavailable
from speech_service.tts import END_OF_SPEECH, SvaraLlamaTTS, SvaraTTS


def test_auto_uses_transformers_without_the_gguf(tmp_path: Path) -> None:
    s = Settings(tts_backend="auto", tts_gguf=tmp_path / "absent.gguf")
    assert isinstance(make_tts(s), SvaraTTS)


def test_auto_uses_llama_when_gguf_and_server_exist(tmp_path: Path) -> None:
    (tmp_path / "m.gguf").write_bytes(b"x")
    (tmp_path / "llama-server").write_bytes(b"x")
    s = Settings(tts_backend="auto", tts_gguf=tmp_path / "m.gguf",
                 llama_server_bin=tmp_path / "llama-server", tts_llm_port=9999)
    t = make_tts(s)
    assert isinstance(t, SvaraLlamaTTS)
    cmd = t.server.cmd()
    assert cmd[cmd.index("--host") + 1] == "127.0.0.1"
    assert cmd[cmd.index("--port") + 1] == "9999"
    assert f"tokenizer.ggml.eos_token_id=int:{END_OF_SPEECH}" in cmd


def test_forced_transformers(tmp_path: Path) -> None:
    (tmp_path / "m.gguf").write_bytes(b"x")
    s = Settings(tts_backend="transformers", tts_gguf=tmp_path / "m.gguf")
    assert isinstance(make_tts(s), SvaraTTS)


def test_server_refuses_missing_files(tmp_path: Path) -> None:
    srv = LlamaServer(tmp_path / "llama-server", tmp_path / "m.gguf", 9999)
    with pytest.raises(ModelUnavailable, match="missing"):
        srv.start()
    assert not srv.running and srv.stop() is False


def test_unmanaged_server_must_answer() -> None:
    srv = LlamaServer(Path("/x"), Path("/y"), 9, manage=False, url="http://127.0.0.1:9")
    with pytest.raises(ModelUnavailable, match="not reachable"):
        srv.start()


def test_llama_backend_turns_tokens_into_audio(tmp_path: Path) -> None:
    torch = pytest.importorskip("torch")
    from speech_service.tts import AUDIO_TOKENS_START, START_OF_SPEECH

    class Tok:
        def __call__(self, text, add_special_tokens=False):
            class R:
                input_ids = [1, 2, 3]
            return R()

    class Codec:
        def decode(self, layers):
            assert [x.shape[1] for x in layers] == [2, 4, 8]  # 2 frames
            return torch.zeros(1, 1, 4096)

    t = SvaraLlamaTTS(tmp_path / "m.gguf", "tok", "codec", server_bin=tmp_path / "bin",
                      port=9999, device="cpu")
    t._lazy._loader = lambda: (Tok(), Codec())
    t._lazy._probe = lambda: 999.0
    frame = [AUDIO_TOKENS_START + i * 4096 for i in range(7)]
    bodies = []

    def fake_completion(body, timeout=300.0):
        bodies.append(body)
        return {"tokens": [START_OF_SPEECH] + frame * 2 + [END_OF_SPEECH]}

    t.server.completion = fake_completion
    t.server.manage = False
    audio, sr = t.synthesize("हिंदमाता येथे पाणी. पर्यायी मार्ग वापरा.", "mr", "female")
    assert sr == 24000 and len(bodies) == 2  # one generation per sentence
    assert audio.size == 4096 * 2 + int(0.22 * 24000)
    assert bodies[0]["return_tokens"] is True and bodies[0]["temperature"] == 0.6
    assert bodies[0]["seed"] != bodies[1]["seed"]
