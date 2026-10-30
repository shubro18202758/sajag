"""Test doubles for the speech service (no model, no GPU)."""

from __future__ import annotations

import numpy as np

from speech_service.asr import Transcript
from speech_service.runtime import ModelUnavailable


class FakeASR:
    model_id = "fake-asr"

    def __init__(self, text: str = "हिंदमाता येथे गुडघाभर पाणी साचले आहे, बस अडकल्या आहेत", lang: str = "mr",
                 unavailable: bool = False) -> None:
        self.text = text
        self.lang = lang
        self.unavailable = unavailable
        self.calls: list[tuple[int, str | None]] = []
        self.unloaded = False

    def transcribe(self, samples: np.ndarray, lang: str | None) -> Transcript:
        if self.unavailable:
            raise ModelUnavailable("refused to load asr: 3.0 GiB available")
        self.calls.append((int(samples.size), lang))
        return Transcript(self.text, lang or self.lang, 0.87, self.model_id, 0.01)

    def status(self) -> dict:
        return {"model": self.model_id, "loaded": True}

    def maybe_unload_idle(self) -> bool:
        return False

    def unload(self) -> bool:
        self.unloaded = True
        return True


class FakeTTS:
    model_id = "fake-tts"

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str]] = []

    def synthesize(self, text: str, lang: str, voice: str) -> tuple[np.ndarray, int]:
        self.calls.append((text, lang, voice))
        t = np.linspace(0, 0.5, 12000, endpoint=False)
        return (0.3 * np.sin(2 * np.pi * 220 * t)).astype(np.float32), 24000

    def status(self) -> dict:
        return {"model": self.model_id, "loaded": True}

    def maybe_unload_idle(self) -> bool:
        return False


def tone_wav(seconds: float = 1.0, sr: int = 16000, channels: int = 1, width: int = 2) -> bytes:
    import io
    import wave

    t = np.linspace(0, seconds, int(sr * seconds), endpoint=False)
    x = 0.4 * np.sin(2 * np.pi * 440 * t)
    if width == 2:
        frames = (x * 32767).astype("<i2")
    elif width == 1:
        frames = ((x * 127) + 128).astype(np.uint8)
    else:
        raise ValueError(width)
    if channels == 2:
        frames = np.repeat(frames, 2)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(width)
        w.setframerate(sr)
        w.writeframes(frames.tobytes())
    return buf.getvalue()
