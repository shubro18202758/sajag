"""Audio in and out, entirely in memory.

Uploaded audio is never written to disk: WAV is parsed with the standard
library, WebM/Ogg/MP3 go through ``ffmpeg`` over stdin/stdout pipes. The
decoded samples live only for the duration of the request (see README,
"Privacy": no speaker identification, no voice storage).
"""

from __future__ import annotations

import io
import shutil
import subprocess
import wave

import numpy as np

__all__ = [
    "AudioError",
    "TARGET_SR",
    "sniff_format",
    "decode_audio",
    "encode_wav",
    "level_speech",
    "resample",
]

TARGET_SR = 16_000


class AudioError(ValueError):
    """The upload is not audio we can decode (HTTP 415/422)."""


def sniff_format(data: bytes) -> str:
    """Container format from magic bytes: wav | webm | ogg | mp3 | flac | unknown."""
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WAVE":
        return "wav"
    if data[:4] == b"\x1a\x45\xdf\xa3":  # EBML header (WebM / Matroska)
        return "webm"
    if data[:4] == b"OggS":
        return "ogg"
    if data[:4] == b"fLaC":
        return "flac"
    if data[:3] == b"ID3" or (len(data) > 1 and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0):
        return "mp3"
    return "unknown"


def resample(x: np.ndarray, sr_in: int, sr_out: int = TARGET_SR) -> np.ndarray:
    """Polyphase resampling (scipy) with a linear-interpolation fallback."""
    if sr_in == sr_out or x.size == 0:
        return x.astype(np.float32, copy=False)
    try:
        from math import gcd

        from scipy.signal import resample_poly

        g = gcd(sr_in, sr_out)
        return resample_poly(x, sr_out // g, sr_in // g).astype(np.float32)
    except ImportError:  # pragma: no cover - scipy is a declared dependency
        n_out = int(round(x.size * sr_out / sr_in))
        t_in = np.linspace(0.0, 1.0, num=x.size, endpoint=False)
        t_out = np.linspace(0.0, 1.0, num=n_out, endpoint=False)
        return np.interp(t_out, t_in, x).astype(np.float32)


def _decode_wav(data: bytes) -> tuple[np.ndarray, int]:
    try:
        with wave.open(io.BytesIO(data), "rb") as w:
            ch, width, sr, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
            raw = w.readframes(n)
    except (wave.Error, EOFError) as exc:
        # WAVE_FORMAT_IEEE_FLOAT (3) and extensible headers are not handled by
        # the stdlib reader; ffmpeg can still read them.
        raise AudioError(f"wav: {exc}") from exc
    if width == 2:
        x = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    elif width == 4:
        x = np.frombuffer(raw, dtype="<i4").astype(np.float32) / 2147483648.0
    elif width == 1:
        x = (np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
    elif width == 3:
        b = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3)
        i = (b[:, 0].astype(np.int32) | (b[:, 1].astype(np.int32) << 8) | (b[:, 2].astype(np.int32) << 16))
        i = np.where(i & 0x800000, i - 0x1000000, i)
        x = i.astype(np.float32) / 8388608.0
    else:
        raise AudioError(f"wav: unsupported sample width {width}")
    if ch > 1:
        x = x[: (x.size // ch) * ch].reshape(-1, ch).mean(axis=1)
    return x, sr


def _decode_ffmpeg(data: bytes, timeout: float = 30.0) -> tuple[np.ndarray, int]:
    exe = shutil.which("ffmpeg")
    if exe is None:
        raise AudioError("ffmpeg is not installed; only WAV can be decoded")
    cmd = [exe, "-nostdin", "-hide_banner", "-loglevel", "error", "-i", "pipe:0",
           "-f", "f32le", "-ac", "1", "-ar", str(TARGET_SR), "pipe:1"]
    try:
        proc = subprocess.run(cmd, input=data, capture_output=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired as exc:
        raise AudioError("ffmpeg timed out") from exc
    if proc.returncode != 0 or not proc.stdout:
        msg = proc.stderr.decode("utf-8", "replace").strip().splitlines()[-1:] or ["no output"]
        raise AudioError(f"could not decode audio: {msg[0][:200]}")
    return np.frombuffer(proc.stdout, dtype="<f4").astype(np.float32), TARGET_SR


def decode_audio(data: bytes, max_seconds: float = 60.0) -> tuple[np.ndarray, float, str]:
    """bytes → (mono float32 at 16 kHz, duration seconds, container format)."""
    if not data:
        raise AudioError("empty audio")
    fmt = sniff_format(data)
    if fmt == "unknown":
        raise AudioError("unrecognised audio container (send wav, webm or ogg)")
    if fmt == "wav":
        try:
            x, sr = _decode_wav(data)
        except AudioError:
            x, sr = _decode_ffmpeg(data)
    else:
        x, sr = _decode_ffmpeg(data)
    x = resample(x, sr, TARGET_SR)
    dur = x.size / TARGET_SR
    if dur < 0.2:
        raise AudioError("audio shorter than 0.2 s")
    if dur > max_seconds:
        raise AudioError(f"audio longer than {max_seconds:.0f} s")
    peak = float(np.max(np.abs(x))) if x.size else 0.0
    if peak > 1.0:
        x = x / peak
    return x, dur, fmt


#: synthetic speech is levelled to about -20 dBFS RMS, never past -1 dBFS peak
SPEECH_RMS = 0.1
SPEECH_PEAK = 0.89


def level_speech(x: np.ndarray, rms: float = SPEECH_RMS, peak: float = SPEECH_PEAK) -> np.ndarray:
    """One loudness for every voice and language (Indic Parler-TTS speaks Marathi about 18 dB quieter than
    English): scale to ``rms``, but never so far that the peak passes ``peak``. Silence is left as it is."""
    x = np.asarray(x, dtype=np.float32)
    if not x.size:
        return x
    now_rms = float(np.sqrt(np.mean(np.square(x, dtype=np.float64))))
    now_peak = float(np.max(np.abs(x)))
    if now_rms < 1e-4 or now_peak <= 0.0:
        return x
    return (x * min(rms / now_rms, peak / now_peak)).astype(np.float32)


def encode_wav(x: np.ndarray, sr: int) -> bytes:
    """float32 mono [-1, 1] → 16-bit PCM WAV bytes."""
    pcm = (np.clip(np.asarray(x, dtype=np.float32), -1.0, 1.0) * 32767.0).astype("<i2")
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())
    return buf.getvalue()
