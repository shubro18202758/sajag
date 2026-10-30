"""In-memory audio decoding."""

from __future__ import annotations

import shutil
import subprocess

import numpy as np
import pytest

from fakes import tone_wav
from speech_service.audio import (
    SPEECH_PEAK,
    SPEECH_RMS,
    TARGET_SR,
    AudioError,
    decode_audio,
    encode_wav,
    level_speech,
    sniff_format,
)


def test_sniff() -> None:
    assert sniff_format(tone_wav()) == "wav"
    assert sniff_format(b"\x1a\x45\xdf\xa3....") == "webm"
    assert sniff_format(b"OggS....") == "ogg"
    assert sniff_format(b"ID3....") == "mp3"
    assert sniff_format(b"hello") == "unknown"


@pytest.mark.parametrize("sr,ch,width", [(16000, 1, 2), (44100, 2, 2), (8000, 1, 1), (48000, 1, 2)])
def test_wav_variants_decode_to_16k_mono(sr: int, ch: int, width: int) -> None:
    x, dur, fmt = decode_audio(tone_wav(1.0, sr, ch, width))
    assert fmt == "wav"
    assert abs(dur - 1.0) < 0.01
    assert x.dtype == np.float32 and x.ndim == 1
    assert abs(x.size - TARGET_SR) <= 2
    assert 0.3 < float(np.max(np.abs(x))) <= 1.0


def test_rejects_bad_audio() -> None:
    with pytest.raises(AudioError):
        decode_audio(b"")
    with pytest.raises(AudioError):
        decode_audio(b"not audio at all")
    with pytest.raises(AudioError, match="shorter"):
        decode_audio(tone_wav(0.05))
    with pytest.raises(AudioError, match="longer"):
        decode_audio(tone_wav(3.0), max_seconds=2.0)


def test_encode_wav_round_trip() -> None:
    x = (0.5 * np.sin(np.linspace(0, 100, 24000))).astype(np.float32)
    y, dur, _ = decode_audio(encode_wav(x, 24000))
    assert abs(dur - 1.0) < 0.01


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")
@pytest.mark.parametrize("fmt,codec", [("webm", "libopus"), ("ogg", "libopus")])
def test_browser_formats_decode_through_ffmpeg_pipes(fmt: str, codec: str) -> None:
    p = subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-f", "wav", "-i", "pipe:0",
                        "-c:a", codec, "-f", fmt, "pipe:1"], input=tone_wav(1.5, 48000),
                       capture_output=True, check=False)
    if p.returncode != 0 or not p.stdout:
        pytest.skip(f"ffmpeg cannot encode {codec}")
    x, dur, got = decode_audio(p.stdout)
    assert got == fmt
    assert 1.3 < dur < 1.7


def _rms(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(x, dtype=np.float64))))


def test_level_speech_gives_quiet_and_loud_voices_one_loudness() -> None:
    t = np.arange(24_000) / 24_000
    quiet = (0.016 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)   # about -37 dBFS, as Parler speaks Marathi
    loud = (0.17 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)    # about -18 dBFS
    a, b = level_speech(quiet), level_speech(loud)
    assert abs(_rms(a) - SPEECH_RMS) < 0.005 and abs(_rms(b) - SPEECH_RMS) < 0.005
    assert np.max(np.abs(a)) <= SPEECH_PEAK + 1e-6 and np.max(np.abs(b)) <= SPEECH_PEAK + 1e-6


def test_level_speech_never_pushes_a_peak_past_the_ceiling_and_leaves_silence() -> None:
    spiky = np.zeros(16_000, dtype=np.float32)
    spiky[::400] = 0.5   # a high crest factor: the peak, not the RMS, sets the gain
    out = level_speech(spiky)
    assert abs(float(np.max(np.abs(out))) - SPEECH_PEAK) < 1e-6 and _rms(out) < SPEECH_RMS
    silence = np.zeros(800, dtype=np.float32)
    assert np.array_equal(level_speech(silence), silence) and level_speech(np.zeros(0, np.float32)).size == 0
