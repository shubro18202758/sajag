"""Text-to-speech for public advisories (Marathi, English, Hindi).

Backend: Svara-TTS v1 (Apache-2.0), an Orpheus-style model that writes SNAC
audio codes which the SNAC 24 kHz codec (MIT) turns into a waveform. Indic
Parler-TTS, the first choice, is gated on Hugging Face; access was granted on
29 Oct 2026 and it did better in the evaluation (docs/ai/speech.md). It drops
in by configuration (``SPEECH_TTS_BACKEND=indic_parler``); while it cannot
load, :class:`FallbackTTS` says why and Svara answers.

Svara takes a speaker id ("Marathi (Female)") plus an end-of-utterance style
tag. The house voice is the female speaker of the requested language with
the ``<clear>`` tag, which reads like a calm, steady announcement. Sampling
is seeded from the text hash, so one text always gives one waveform and the
on-disk cache is exact.
"""

from __future__ import annotations

import hashlib
import io
import json
import logging
import os
import re
import select
import subprocess
import tempfile
import threading
import time
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Protocol

import numpy as np

from .audio import encode_wav, level_speech
from .runtime import DEFAULT_MIN_FREE_GIB, LazyModel, ModelNotProvisioned, ModelUnavailable, not_provisioned

log = logging.getLogger("speech.tts")

__all__ = [
    "Speech",
    "TTSBackend",
    "SvaraTTS",
    "SvaraLlamaTTS",
    "IndicParlerTTS",
    "ParlerWorkerTTS",
    "FallbackTTS",
    "PARLER_SPEAKERS",
    "PARLER_EVAL_SPEAKERS",
    "PARLER_DESCRIPTION",
    "TTSCache",
    "split_sentences",
    "speaker_for",
    "LANG_NAMES",
    "PROMPT_FORMAT",
    "prompt_ids",
]

LANG_NAMES = {"mr": "Marathi", "en": "English (Indian)", "hi": "Hindi"}

# Svara-TTS token layout (Orpheus convention on the Llama-3.2 tokenizer).
_TOKENISER_LEN = 128256
START_OF_SPEECH = _TOKENISER_LEN + 1
END_OF_SPEECH = _TOKENISER_LEN + 2
START_OF_HUMAN = _TOKENISER_LEN + 3
END_OF_HUMAN = _TOKENISER_LEN + 4
START_OF_AI = _TOKENISER_LEN + 5
END_OF_AI = _TOKENISER_LEN + 6
AUDIO_TOKENS_START = _TOKENISER_LEN + 10
BOS = 128000
END_OF_TURN = 128009
SAMPLE_RATE = 24_000

_SENT_RE = re.compile(r"(?<=[।!?\.\n])\s+")


@dataclass(frozen=True)
class Speech:
    wav: bytes
    sample_rate: int
    seconds: float
    model: str
    voice: str
    cached: bool
    synth_seconds: float


class TTSBackend(Protocol):
    model_id: str

    def synthesize(self, text: str, lang: str, voice: str) -> tuple[np.ndarray, int]: ...

    def status(self) -> dict: ...

    def maybe_unload_idle(self) -> bool: ...


def speaker_for(lang: str, voice: str) -> str:
    gender = "Male" if voice == "male" else "Female"
    return f"{LANG_NAMES[lang]} ({gender})"


def split_sentences(text: str, max_chars: int = 220) -> list[str]:
    """Sentence-ish chunks (the model reads one chunk per generation)."""
    parts = [p.strip() for p in _SENT_RE.split(text.strip()) if p.strip()]
    out: list[str] = []
    for p in parts:
        while len(p) > max_chars:  # long run-on: break at the last comma/space
            cut = max(p.rfind(",", 0, max_chars), p.rfind("，", 0, max_chars), p.rfind(" ", 0, max_chars))
            cut = cut if cut > max_chars // 3 else max_chars
            out.append(p[:cut + 1].strip())
            p = p[cut + 1:].strip()
        if p:
            out.append(p)
    return out


# Bumped whenever the prompt layout changes, so cached audio is regenerated.
PROMPT_FORMAT = "orpheus-human-turn/2"
# Bumped whenever the output levelling changes (audio.level_speech), for the same reason.
LEVEL_FORMAT = "level/1"


def prompt_ids(tok, text: str, speaker: str, style_tag: str = "") -> list[int]:
    """One human turn, as the model card's own demo builds it:

        <start-of-human> <bos> "Marathi (Female): text <clear>" <eot> <end-of-human>

    The model then writes <start-of-ai><start-of-speech> and the audio codes
    itself. (An earlier layout that pre-filled <start-of-ai><start-of-speech>
    and an <|audio|> marker made the model read the speaker label aloud —
    "Marathi …" — at the start of about one utterance in three.)
    """
    body = f"{speaker}: {text}"
    if style_tag:
        body = f"{body} {style_tag}"
    ids = tok(body, add_special_tokens=False).input_ids
    return [START_OF_HUMAN, BOS, *ids, END_OF_TURN, END_OF_HUMAN]


def codes_from_tokens(tokens: list[int]) -> list[int]:
    """Generated ids → raw SNAC codes (0..4095), whole 7-code frames only.

    Everything up to the last <start-of-speech> is dropped first.
    """
    if START_OF_SPEECH in tokens:
        tokens = tokens[len(tokens) - tokens[::-1].index(START_OF_SPEECH):]
    out: list[int] = []
    for t in tokens:
        if t == END_OF_SPEECH or t == END_OF_AI:
            break
        if t < AUDIO_TOKENS_START:
            continue
        code = t - AUDIO_TOKENS_START - (len(out) % 7) * 4096
        if 0 <= code < 4096:
            out.append(code)
    return out[: (len(out) // 7) * 7]


def redistribute(codes: list[int]) -> tuple[list[int], list[int], list[int]]:
    """Interleaved frames [c0,c1,c2,c3,c4,c5,c6] → SNAC's three code layers."""
    l0, l1, l2 = [], [], []
    for i in range(len(codes) // 7):
        f = codes[7 * i: 7 * i + 7]
        l0.append(f[0])
        l1 += [f[1], f[4]]
        l2 += [f[2], f[3], f[5], f[6]]
    return l0, l1, l2


class SvaraTTS:
    def __init__(self, model_id: str, codec_id: str, *, device: str = "cuda",
                 style_tag: str = "<clear>", seed: int = 1847,
                 min_free_gib: float = DEFAULT_MIN_FREE_GIB, idle_unload_s: float = 600) -> None:
        self.model_id = model_id
        self.codec_id = codec_id
        self.device = device
        self.style_tag = style_tag
        self.seed = seed
        self._run_lock = threading.Lock()
        self._lazy = LazyModel(
            f"tts:{model_id}", self._load, need_gib=8.0,
            min_free_gib=min_free_gib, idle_unload_s=idle_unload_s,
        )

    def _load(self):
        import torch
        from snac import SNAC
        from transformers import AutoModelForCausalLM, AutoTokenizer

        dtype = torch.bfloat16 if self.device.startswith("cuda") else torch.float32
        tok = AutoTokenizer.from_pretrained(self.model_id)
        model = AutoModelForCausalLM.from_pretrained(self.model_id, dtype=dtype).to(self.device).eval()
        codec = SNAC.from_pretrained(self.codec_id).eval().to(self.device)
        return tok, model, codec

    def status(self) -> dict:
        return {"model": self.model_id, "codec": self.codec_id, **self._lazy.status()}

    def maybe_unload_idle(self) -> bool:
        return self._lazy.maybe_unload_idle()

    def unload(self) -> bool:
        return self._lazy.unload()

    def lazy_models(self) -> list[LazyModel]:
        return [self._lazy]

    def _prompt_ids(self, tok, text: str, speaker: str) -> list[int]:
        return prompt_ids(tok, text, speaker, self.style_tag)

    def synthesize(self, text: str, lang: str, voice: str) -> tuple[np.ndarray, int]:
        with self._lazy.using() as loaded:  # held: never released mid-request
            return self._synthesize(loaded, text, lang, voice)

    def _synthesize(self, loaded: Any, text: str, lang: str, voice: str) -> tuple[np.ndarray, int]:
        import torch

        tok, model, codec = loaded
        speaker = speaker_for(lang, voice)
        pieces: list[np.ndarray] = []
        gap = np.zeros(int(0.22 * SAMPLE_RATE), dtype=np.float32)
        with self._run_lock, torch.inference_mode():
            for sent in split_sentences(text):
                seed = self.seed ^ int(hashlib.sha256(f"{speaker}|{sent}".encode()).hexdigest()[:8], 16)
                torch.manual_seed(seed)
                ids = torch.tensor([self._prompt_ids(tok, sent, speaker)], device=self.device)
                # ~82 codes per second of speech; cap by text length (Marathi
                # reads at roughly 12-16 characters a second).
                budget = int(min(2400, max(280, len(sent) * 16)))
                out = model.generate(
                    ids,
                    attention_mask=torch.ones_like(ids),
                    max_new_tokens=budget,
                    do_sample=True,
                    temperature=0.6,
                    top_p=0.9,
                    repetition_penalty=1.1,
                    eos_token_id=END_OF_SPEECH,
                    pad_token_id=END_OF_AI,
                )
                gen = out[0, ids.shape[1]:].tolist()
                codes = codes_from_tokens(gen)
                if len(codes) < 7:
                    continue
                l0, l1, l2 = redistribute(codes)
                layers = [torch.tensor(l, dtype=torch.int32, device=self.device).unsqueeze(0)
                          for l in (l0, l1, l2)]
                wav = codec.decode(layers).squeeze().float().cpu().numpy()
                if pieces:
                    pieces.append(gap)
                pieces.append(wav.astype(np.float32))
        self._lazy.touch()
        if not pieces:
            raise RuntimeError("the TTS model produced no audio for this text")
        audio = np.concatenate(pieces)
        peak = float(np.max(np.abs(audio))) or 1.0
        return (audio / max(peak, 1.0) * 0.95).astype(np.float32), SAMPLE_RATE


class SvaraLlamaTTS:
    """Svara-TTS from a GGUF in llama.cpp; SNAC decoding stays in torch.

    Same prompt, same sampling, same output as :class:`SvaraTTS`, about three
    times faster on the GB10. The GGUF is a Q8_0 conversion of the
    published weights (``scripts/convert_svara_gguf.sh``).
    """

    def __init__(self, gguf: Path, tokenizer_id: str, codec_id: str, *, server_bin: Path,
                 port: int, manage: bool = True, url: str | None = None, device: str = "cuda",
                 style_tag: str = "<clear>", seed: int = 1847, min_free_gib: float = DEFAULT_MIN_FREE_GIB,
                 idle_unload_s: float = 600) -> None:
        from .llama import LlamaServer

        self.model_id = f"{tokenizer_id} (Q8_0 GGUF, llama.cpp)"
        self.tokenizer_id = tokenizer_id
        self.codec_id = codec_id
        self.device = device
        self.style_tag = style_tag
        self.seed = seed
        # stop on <end-of-speech>: the converted vocab marks <|eot_id|> as EOS
        self.server = LlamaServer(
            server_bin, gguf, port, ctx=4096, manage=manage, url=url,
            extra_args=("--override-kv", f"tokenizer.ggml.eos_token_id=int:{END_OF_SPEECH}"),
        )
        self._run_lock = threading.Lock()
        self._lazy = LazyModel(
            f"tts:{self.model_id}", self._load, need_gib=5.0,
            min_free_gib=min_free_gib, idle_unload_s=idle_unload_s,
        )
        self._lazy.on_release = self.server.stop  # released to make room: the llama-server goes too

    def _load(self):
        from snac import SNAC
        from transformers import AutoTokenizer

        tok = AutoTokenizer.from_pretrained(self.tokenizer_id)
        codec = SNAC.from_pretrained(self.codec_id).eval().to(self.device)
        self.server.start()
        return tok, codec

    def status(self) -> dict:
        return {"model": self.model_id, "codec": self.codec_id, "backend": "llama.cpp",
                "server_running": self.server.running if self.server.manage else None,
                **self._lazy.status()}

    def maybe_unload_idle(self) -> bool:
        if self._lazy.maybe_unload_idle():
            self.server.stop()
            return True
        return False

    def unload(self) -> bool:
        self.server.stop()
        return self._lazy.unload()

    def lazy_models(self) -> list[LazyModel]:
        return [self._lazy]

    def synthesize(self, text: str, lang: str, voice: str) -> tuple[np.ndarray, int]:
        with self._lazy.using() as loaded:  # held: never released mid-request
            return self._synthesize(loaded, text, lang, voice)

    def _synthesize(self, loaded: Any, text: str, lang: str, voice: str) -> tuple[np.ndarray, int]:
        import torch

        tok, codec = loaded
        if self.server.manage and not self.server.running:
            self.server.start()  # restarted after a crash or an external kill
        speaker = speaker_for(lang, voice)
        pieces: list[np.ndarray] = []
        gap = np.zeros(int(0.22 * SAMPLE_RATE), dtype=np.float32)
        with self._run_lock:
            for sent in split_sentences(text):
                seed = self.seed ^ int(hashlib.sha256(f"{speaker}|{sent}".encode()).hexdigest()[:8], 16)
                body = {
                    "prompt": prompt_ids(tok, sent, speaker, self.style_tag),
                    "n_predict": int(min(2400, max(280, len(sent) * 16))),
                    "temperature": 0.6, "top_p": 0.9, "repeat_penalty": 1.1,
                    "seed": seed, "return_tokens": True, "cache_prompt": False,
                }
                codes = codes_from_tokens(self.server.completion(body).get("tokens", []))
                if len(codes) < 7:
                    continue
                l0, l1, l2 = redistribute(codes)
                with torch.inference_mode():
                    layers = [torch.tensor(x, dtype=torch.int32, device=self.device).unsqueeze(0)
                              for x in (l0, l1, l2)]
                    wav = codec.decode(layers).squeeze().float().cpu().numpy()
                if pieces:
                    pieces.append(gap)
                pieces.append(wav.astype(np.float32))
        self._lazy.touch()
        if not pieces:
            raise RuntimeError("the TTS model produced no audio for this text")
        audio = np.concatenate(pieces)
        peak = float(np.max(np.abs(audio))) or 1.0
        return (audio / max(peak, 1.0) * 0.95).astype(np.float32), SAMPLE_RATE


# Indic Parler-TTS names its trained voices; these are the model card's
# recommended speakers for each of our languages (model card, "Speakers"
# table: Marathi — Sanjay, Sunita; Hindi — Rohit, Divya; English — Thoma, Mary).
PARLER_SPEAKERS = {
    ("mr", "female"): "Sunita", ("mr", "male"): "Sanjay",
    ("en", "female"): "Mary", ("en", "male"): "Thoma",
    ("hi", "female"): "Divya", ("hi", "male"): "Rohit",
}
# Other trained voices of the same languages (model card, "Available
# Speakers"). Never used for advisories; the evaluation speaks its phrases
# with them too, so the ASR is not only measured on the house voices.
PARLER_EVAL_SPEAKERS = {
    "mr": ("Radha", "Nikhil"), "hi": ("Rani", "Aman"), "en": ("Meera", "Jatin"),
}
# The house advisory voice as a Parler caption ({speaker} is filled in).
PARLER_DESCRIPTION = (
    "{speaker} speaks in a calm, clear and unhurried voice at a steady, moderate pace, "
    "reading a public traffic advisory. The recording is of very high quality, with the "
    "speaker's voice sounding clear and very close up, and no background noise."
)


class IndicParlerTTS:
    """AI4Bharat Indic Parler-TTS (Apache-2.0; **gated** on Hugging Face).

    Loaded as the model card documents: ``ParlerTTSForConditionalGeneration``
    from the ``parler_tts`` package, the prompt tokenizer of the repo and the
    description tokenizer of its text encoder. The voice is a named speaker
    (:data:`PARLER_SPEAKERS`) plus the house caption; sampling is seeded from
    the text, so one text gives one waveform and the cache stays exact.
    """

    DEFAULT_MODEL = "ai4bharat/indic-parler-tts"

    def __init__(self, model_id: str = DEFAULT_MODEL, *, device: str = "cuda",
                 description: str = PARLER_DESCRIPTION, seed: int = 1847,
                 revision: str | None = None,
                 min_free_gib: float = DEFAULT_MIN_FREE_GIB, idle_unload_s: float = 600,
                 loader: Callable[[], Any] | None = None) -> None:
        self.model_id = model_id
        self.device = device
        self.description = description
        self.seed = seed
        self.revision = revision or None
        self._run_lock = threading.Lock()
        self._lazy = LazyModel(
            f"tts:{model_id}", loader or self._load, need_gib=5.0,
            min_free_gib=min_free_gib, idle_unload_s=idle_unload_s,
        )

    def _load(self):
        try:
            from parler_tts import ParlerTTSForConditionalGeneration
            from transformers import AutoTokenizer
        except ImportError as exc:
            raise not_provisioned(self.model_id, exc, gated=True) from exc
        try:
            model = ParlerTTSForConditionalGeneration.from_pretrained(self.model_id,
                                                                      revision=self.revision)
            model = model.to(self.device).eval()
            tok = AutoTokenizer.from_pretrained(self.model_id, revision=self.revision)
            desc_tok = AutoTokenizer.from_pretrained(model.config.text_encoder._name_or_path)
        except Exception as exc:
            mapped = not_provisioned(self.model_id, exc, gated=True)
            if mapped is not None:
                raise mapped from exc
            raise
        return tok, desc_tok, model

    def status(self) -> dict:
        return {"model": self.model_id, **self._lazy.status()}

    def maybe_unload_idle(self) -> bool:
        return self._lazy.maybe_unload_idle()

    def unload(self) -> bool:
        return self._lazy.unload()

    def lazy_models(self) -> list[LazyModel]:
        return [self._lazy]

    def caption(self, lang: str, voice: str) -> str:
        return self.description.format(speaker=PARLER_SPEAKERS[(lang, voice)])

    def synthesize(self, text: str, lang: str, voice: str) -> tuple[np.ndarray, int]:
        # first: a gated model fails here, before torch is touched
        with self._lazy.using() as loaded:  # held: never released mid-request
            return self._synthesize(loaded, text, lang, voice)

    def _synthesize(self, loaded: Any, text: str, lang: str, voice: str) -> tuple[np.ndarray, int]:
        tok, desc_tok, model = loaded
        import torch

        sr = int(model.config.sampling_rate)
        caption = self.caption(lang, voice)
        pieces: list[np.ndarray] = []
        gap = np.zeros(int(0.22 * sr), dtype=np.float32)
        with self._run_lock, torch.inference_mode():
            desc = desc_tok(caption, return_tensors="pt").to(self.device)
            for sent in split_sentences(text):
                digest = hashlib.sha256(f"{caption}|{sent}".encode()).hexdigest()
                torch.manual_seed(self.seed ^ int(digest[:8], 16))
                prompt = tok(sent, return_tensors="pt").to(self.device)
                out = model.generate(input_ids=desc.input_ids, attention_mask=desc.attention_mask,
                                     prompt_input_ids=prompt.input_ids,
                                     prompt_attention_mask=prompt.attention_mask)
                wav = out.float().cpu().numpy().squeeze()
                if wav.size == 0:
                    continue
                if pieces:
                    pieces.append(gap)
                pieces.append(wav.astype(np.float32))
        self._lazy.touch()
        if not pieces:
            raise RuntimeError("the TTS model produced no audio for this text")
        audio = np.concatenate(pieces)
        peak = float(np.max(np.abs(audio))) or 1.0
        return (audio / max(peak, 1.0) * 0.95).astype(np.float32), sr


class ParlerWorkerTTS:
    """:class:`IndicParlerTTS` in a child interpreter with its own venv.

    ``parler-tts`` pins ``transformers==4.46.1``; the service runs on
    transformers 5.x. Set ``SPEECH_TTS_PARLER_PYTHON`` to the python of a
    venv that has parler-tts, and the model runs there
    (``python -m speech_service.parler_worker``), started after the memory
    check on the first advisory and stopped when the backend unloads. The
    child talks over its stdin/stdout only (no port).
    """

    def __init__(self, python: Path | str, model_id: str = IndicParlerTTS.DEFAULT_MODEL, *,
                 device: str = "cuda", description: str = PARLER_DESCRIPTION, seed: int = 1847,
                 revision: str | None = None,
                 min_free_gib: float = DEFAULT_MIN_FREE_GIB, idle_unload_s: float = 600,
                 load_timeout_s: float = 900.0, synth_timeout_s: float = 300.0,
                 cmd: list[str] | None = None) -> None:
        self.python = Path(python)
        self.model_id = model_id
        self.device = device
        self.description = description
        self.seed = seed
        self.revision = revision or None
        self.load_timeout_s = load_timeout_s
        self.synth_timeout_s = synth_timeout_s
        self._cmd_override = cmd
        self._proc: subprocess.Popen[bytes] | None = None
        self._run_lock = threading.Lock()
        self._lazy = LazyModel(
            f"tts:{model_id} (worker)", self._load, need_gib=5.0,
            min_free_gib=min_free_gib, idle_unload_s=idle_unload_s,
        )
        self._lazy.on_release = self._stop  # released to make room: the worker process exits

    def cmd(self) -> list[str]:
        if self._cmd_override is not None:
            return list(self._cmd_override)
        cmd = [str(self.python), "-m", "speech_service.parler_worker", "--model", self.model_id,
               "--device", self.device, "--seed", str(self.seed),
               "--description", self.description]
        if self.revision:
            cmd += ["--revision", self.revision]
        return cmd

    @property
    def running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def _load(self):
        if self._cmd_override is None and not self.python.is_file():
            raise ModelNotProvisioned(
                f"{self.model_id}: the Parler venv's python is missing ({self.python}); "
                f"see docs/ai/speech.md \"When access is granted\"")
        src = str(Path(__file__).resolve().parents[1])
        env = dict(os.environ)
        env["PYTHONPATH"] = src + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
        self._proc = subprocess.Popen(  # noqa: S603 - argv from config, no shell
            self.cmd(), stdin=subprocess.PIPE, stdout=subprocess.PIPE, env=env,
            start_new_session=True,
        )
        try:
            self._call({"op": "load"}, self.load_timeout_s)
        except BaseException:
            self._stop()
            raise
        return self._proc

    def _call(self, req: dict, timeout_s: float) -> tuple[dict, bytes]:
        proc = self._proc
        if proc is None or proc.stdin is None or proc.stdout is None or proc.poll() is not None:
            raise ModelUnavailable("the Parler worker is not running")
        try:
            proc.stdin.write(json.dumps(req, ensure_ascii=False).encode("utf-8") + b"\n")
            proc.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            raise WorkerFailed(f"the Parler worker exited (code {proc.poll()})") from exc
        ready, _, _ = select.select([proc.stdout], [], [], timeout_s)
        if not ready:
            self._stop()
            raise WorkerFailed(f"the Parler worker did not answer within {timeout_s:.0f} s")
        line = proc.stdout.readline()
        if not line:
            code = proc.wait(timeout=5)
            raise WorkerFailed(f"the Parler worker exited (code {code}); see the service log")
        head = json.loads(line)
        if not head.get("ok"):
            msg = str(head.get("error") or "the Parler worker failed")
            if head.get("not_provisioned"):
                raise ModelNotProvisioned(msg)
            raise RuntimeError(msg)
        n = int(head.get("bytes") or 0)
        payload = proc.stdout.read(n) if n else b""
        if len(payload) != n:
            raise ModelUnavailable("the Parler worker's answer was cut short")
        return head, payload

    def _stop(self) -> None:
        proc, self._proc = self._proc, None
        if proc is None:
            return
        try:
            if proc.stdin:
                proc.stdin.close()  # EOF: the worker leaves its loop and exits
            proc.wait(timeout=10)
        except Exception:
            proc.kill()
            try:
                proc.wait(timeout=5)
            except Exception:
                pass

    def status(self) -> dict:
        return {"model": self.model_id, "backend": "parler-worker", "python": str(self.python),
                "worker_running": self.running, **self._lazy.status()}

    def maybe_unload_idle(self) -> bool:
        if self._lazy.maybe_unload_idle():
            self._stop()
            return True
        return False

    def unload(self) -> bool:
        self._stop()
        return self._lazy.unload()

    def lazy_models(self) -> list[LazyModel]:
        return [self._lazy]

    def synthesize(self, text: str, lang: str, voice: str) -> tuple[np.ndarray, int]:
        if PARLER_SPEAKERS.get((lang, voice)) is None:
            raise ValueError(f"no Parler voice for {lang}/{voice}")
        with self._lazy.using(), self._run_lock:  # held: never released mid-request
            if not self.running:  # died since it loaded: start over on the next call
                self._lazy.unload()
                self._lazy.get()
            head, payload = self._call({"op": "synthesize", "text": text, "lang": lang,
                                        "voice": voice}, self.synth_timeout_s)
        return np.frombuffer(payload, dtype="<f4").copy(), int(head["sr"])


class WorkerFailed(ModelUnavailable):
    """The preferred backend's worker process died or stopped answering (not a memory refusal): the fallback
    answers that request, and the next request tries the preferred backend again."""


class FallbackTTS:
    """The preferred TTS first; the fallback when it cannot be provisioned
    (gated access not granted, weights not downloaded, package missing). The
    reason is logged once and shown in ``/health``; the fallback answers until
    the service restarts. When the preferred backend's worker dies mid-request
    (:class:`WorkerFailed`) the fallback answers that request and the next one
    tries the preferred backend again, so a citizen pressing Listen still hears
    the advisory. A memory refusal stays a 503 and does not switch."""

    def __init__(self, preferred: TTSBackend, fallback: TTSBackend) -> None:
        self.preferred = preferred
        self.fallback = fallback
        self.preferred_error: str | None = None
        #: the last request was answered by the fallback after a worker failure (its reason)
        self.last_worker_failure: str | None = None
        self._fell_back = False

    @property
    def model_id(self) -> str:
        return self.fallback.model_id if (self.preferred_error or self._fell_back) else self.preferred.model_id

    def synthesize(self, text: str, lang: str, voice: str) -> tuple[np.ndarray, int]:
        self._fell_back = False
        if self.preferred_error is None:
            try:
                return self.preferred.synthesize(text, lang, voice)
            except ModelNotProvisioned as exc:
                self.preferred_error = str(exc)
                log.warning("TTS %s unavailable, using %s: %s", self.preferred.model_id,
                            self.fallback.model_id, exc)
            except WorkerFailed as exc:
                self.last_worker_failure = str(exc)
                self._fell_back = True
                log.warning("TTS %s failed (%s); %s answers this request", self.preferred.model_id, exc,
                            self.fallback.model_id)
        return self.fallback.synthesize(text, lang, voice)

    def status(self) -> dict:
        return {"model": self.model_id,
                "active": "fallback" if self.preferred_error else "preferred",
                "preferred": self.preferred.status(), "preferred_error": self.preferred_error,
                "last_worker_failure": self.last_worker_failure,
                "fallback": self.fallback.status()}

    def maybe_unload_idle(self) -> bool:
        a = self.preferred.maybe_unload_idle()
        b = self.fallback.maybe_unload_idle()
        return a or b

    def unload(self) -> bool:
        a = getattr(self.preferred, "unload", lambda: False)()
        b = getattr(self.fallback, "unload", lambda: False)()
        return a or b

    def lazy_models(self) -> list[LazyModel]:
        out: list[LazyModel] = []
        for b in (self.preferred, self.fallback):
            out += [lm for lm in getattr(b, "lazy_models", lambda: [])() if all(lm is not x for x in out)]
        return out


class TTSCache:
    """wav files keyed by sha256(model | voice | style | lang | text)."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    @staticmethod
    def key(model: str, lang: str, voice: str, style: str, text: str) -> str:
        h = hashlib.sha256()
        for part in (model, lang, voice, style, text):
            h.update(part.encode("utf-8"))
            h.update(b"\x1f")
        return h.hexdigest()

    def _path(self, key: str) -> Path:
        return self.root / key[:2] / f"{key}.wav"

    def get(self, key: str) -> bytes | None:
        p = self._path(key)
        try:
            return p.read_bytes()
        except OSError:
            return None

    def put(self, key: str, data: bytes) -> None:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=p.parent, suffix=".part")
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        os.replace(tmp, p)


def speak(backend: TTSBackend, cache: TTSCache, text: str, lang: str, voice: str,
          style: str) -> Speech:
    model_id = backend.model_id
    key = TTSCache.key(f"{model_id}|{PROMPT_FORMAT}|{LEVEL_FORMAT}", lang, voice, style, text)
    hit = cache.get(key)
    if hit is not None:
        try:
            with wave.open(io.BytesIO(hit), "rb") as w:
                sr, n = w.getframerate(), w.getnframes()
            return Speech(hit, sr, round(n / sr, 2), backend.model_id, voice, True, 0.0)
        except (wave.Error, EOFError):
            pass  # a damaged cache file is regenerated below
    t0 = time.perf_counter()
    audio, sr = backend.synthesize(text, lang, voice)
    if backend.model_id != model_id:
        # a fallback answered for the preferred model: file the audio under
        # the model that actually spoke it, never under the preferred one
        model_id = backend.model_id
        key = TTSCache.key(f"{model_id}|{PROMPT_FORMAT}|{LEVEL_FORMAT}", lang, voice, style, text)
    audio = level_speech(audio)
    wav = encode_wav(audio, sr)
    cache.put(key, wav)
    return Speech(wav, sr, round(audio.size / sr, 2), model_id, voice, False,
                  round(time.perf_counter() - t0, 3))
