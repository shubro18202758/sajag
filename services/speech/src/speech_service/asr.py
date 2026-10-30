"""Speech-to-text for field reports (Marathi, Hindi, English).

Marathi and Hindi go to AI4Bharat's IndicConformer (gated on Hugging Face;
``SPEECH_ASR_BACKEND=indic_conformer``, the default) with a Whisper
checkpoint behind it (:class:`FallbackASR` says why the preferred model
cannot load and the Whisper checkpoint answers); English goes to a
multilingual Whisper run with ``transformers`` on the GPU. See README
"Models" for the measured choice and the licences. The backend interface
is deliberately small so tests can swap in a fake.

The audio array passed in is the only copy of the speech; nothing here keeps
it, logs it or writes it anywhere.
"""

from __future__ import annotations

import logging
import math
import re
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Protocol

import numpy as np

from .audio import TARGET_SR
from .runtime import DEFAULT_MIN_FREE_GIB, LazyModel, ModelNotProvisioned, not_provisioned

__all__ = [
    "Transcript",
    "ASRBackend",
    "WhisperASR",
    "IndicConformerASR",
    "assets_revision_error",
    "FallbackASR",
    "RoutedASR",
    "SUPPORTED_LANGS",
    "lazy_models_of",
    "attach_place_prompts",
    "after_start_of_transcript",
]

log = logging.getLogger("speech.asr")

SUPPORTED_LANGS = ("mr", "en", "hi")
_CHUNK_S = 30.0
# Some fine-tuned checkpoints ship a tokenizer that does not mark Whisper's
# control tokens as special, so they survive skip_special_tokens.
_CONTROL_RE = re.compile(r"<\|[^|>]{1,20}\|>")


@dataclass(frozen=True)
class Transcript:
    text: str
    language: str
    # None when the model reports no token probabilities (IndicConformer's
    # published inference returns text only); the deck then shows none.
    confidence: float | None
    model: str
    seconds: float


class ASRBackend(Protocol):
    model_id: str

    def transcribe(self, samples: np.ndarray, lang: str | None) -> Transcript: ...

    def status(self) -> dict: ...

    def maybe_unload_idle(self) -> bool: ...


def _complete_generation_config(model, tok) -> None:
    """Some fine-tuned checkpoints ship a pre-2023 generation config without
    the language/task tables, and then ``generate(language=…)`` refuses to
    run. Rebuild the tables from the checkpoint's own tokenizer."""
    gc = model.generation_config
    if getattr(gc, "lang_to_id", None) and getattr(gc, "task_to_id", None):
        return
    unk = tok.unk_token_id
    langs = {}
    specials = list(getattr(tok, "added_tokens_encoder", {}) or {})
    for t in specials:
        if len(t) <= 9 and t.startswith("<|") and t.endswith("|>") and t[2:-2].isalpha() \
                and t[2:-2].islower() and t[2:-2] not in ("transcribe", "translate", "nocaptions"):
            langs[t] = tok.convert_tokens_to_ids(t)
    for code in SUPPORTED_LANGS:  # make sure ours are there even if the list above is short
        tid = tok.convert_tokens_to_ids(f"<|{code}|>")
        if tid is not None and tid != unk:
            langs[f"<|{code}|>"] = tid
    gc.lang_to_id = langs
    gc.task_to_id = {k: tok.convert_tokens_to_ids(f"<|{k}|>") for k in ("transcribe", "translate")}
    gc.is_multilingual = True
    nts = tok.convert_tokens_to_ids("<|notimestamps|>")
    if nts is not None and nts != unk:
        gc.no_timestamps_token_id = nts


class WhisperASR:
    """Whisper (transformers) with the language forced when it is known.

    Confidence is the geometric-mean token probability of the decoded
    sequence (exp of the mean log-probability), a calibrated-enough signal
    for "ask the officer to check this one" — not an accuracy estimate.
    """

    def __init__(self, model_id: str, *, device: str = "cuda", beams: int = 1,
                 min_free_gib: float = DEFAULT_MIN_FREE_GIB, idle_unload_s: float = 600) -> None:
        self.model_id = model_id
        self.device = device
        self.beams = beams
        # language → vocabulary prompt (the city's place names; see
        # ``attach_place_prompts``). Whisper spells the names it was shown.
        self.prompts: dict[str, str] = {}
        self._prompt_cache: dict[str, Any] = {}
        self._run_lock = threading.Lock()
        self._lazy = LazyModel(
            f"asr:{model_id}", self._load, need_gib=4.0,
            min_free_gib=min_free_gib, idle_unload_s=idle_unload_s,
        )

    # -- lifecycle -------------------------------------------------------------
    def _load(self):
        import torch
        from transformers import WhisperForConditionalGeneration, WhisperProcessor

        dtype = torch.float16 if self.device.startswith("cuda") else torch.float32
        proc = WhisperProcessor.from_pretrained(self.model_id)
        model = WhisperForConditionalGeneration.from_pretrained(self.model_id, dtype=dtype)
        model = model.to(self.device).eval()
        _complete_generation_config(model, proc.tokenizer)
        return proc, model, dtype

    def status(self) -> dict:
        return {"model": self.model_id, **self._lazy.status()}

    def maybe_unload_idle(self) -> bool:
        return self._lazy.maybe_unload_idle()

    def unload(self) -> bool:
        return self._lazy.unload()

    def lazy_models(self) -> list[LazyModel]:
        return [self._lazy]

    # -- inference -------------------------------------------------------------
    def transcribe(self, samples: np.ndarray, lang: str | None) -> Transcript:
        with self._lazy.using() as (proc, model, dtype):  # held: never released mid-request
            return self._transcribe(proc, model, dtype, samples, lang)

    def _transcribe(self, proc, model, dtype, samples: np.ndarray, lang: str | None) -> Transcript:
        import torch

        t0 = time.perf_counter()
        texts: list[str] = []
        logps: list[float] = []
        detected = lang
        step = int(_CHUNK_S * TARGET_SR)
        with self._run_lock, torch.inference_mode():
            for start in range(0, max(1, samples.size), step):
                chunk = samples[start:start + step]
                if chunk.size < int(0.2 * TARGET_SR):
                    continue
                feats = proc(chunk, sampling_rate=TARGET_SR, return_tensors="pt").input_features
                feats = feats.to(self.device, dtype=dtype)
                if detected is None:
                    detected = self._detect(model, proc, feats)
                kw = {}
                pids = self._prompt_ids(proc, detected)
                if pids is not None:
                    kw["prompt_ids"] = pids
                gen = model.generate(
                    feats,
                    language=detected,
                    task="transcribe",
                    num_beams=self.beams,
                    max_new_tokens=180 if pids is not None else 220,
                    return_dict_in_generate=True,
                    output_scores=True,
                    **kw,
                )
                seq = gen.sequences
                if pids is not None:  # the returned sequence starts with the prompt: keep what follows it
                    seq = after_start_of_transcript(seq, proc.tokenizer.convert_tokens_to_ids("<|startoftranscript|>"))
                text = proc.batch_decode(seq, skip_special_tokens=True)[0]
                texts.append(_CONTROL_RE.sub("", text).strip())
                try:
                    trans = model.compute_transition_scores(
                        seq, gen.scores, beam_indices=getattr(gen, "beam_indices", None),
                        normalize_logits=True,
                    )
                    vals = trans[0].float().cpu().numpy()
                    vals = vals[np.isfinite(vals)]
                    logps.extend(vals.tolist())
                except Exception:  # scores are a nicety; never fail the transcript
                    pass
        self._lazy.touch()
        conf = float(math.exp(sum(logps) / len(logps))) if logps else 0.0
        return Transcript(
            text=" ".join(t for t in texts if t).strip(),
            language=detected or "mr",
            confidence=round(conf, 3),
            model=self.model_id,
            seconds=round(time.perf_counter() - t0, 3),
        )

    def _prompt_ids(self, proc, lang: str | None):
        """The prompt of this language as decoder ids (≤ 200 tokens: Whisper
        takes at most half its 448-token context as prompt; names are dropped
        from the end until it fits), or None without a prompt."""
        text = self.prompts.get(lang or "")
        if not text:
            return None
        if lang not in self._prompt_cache:
            parts = text.split(", ")
            while True:
                ids = proc.get_prompt_ids(", ".join(parts), return_tensors="pt")
                if ids.shape[-1] <= 200 or len(parts) <= 2:
                    break
                parts = parts[:-1]
            self._prompt_cache[lang] = ids.to(self.device)
        return self._prompt_cache[lang]

    def detect(self, samples: np.ndarray) -> str:
        """Spoken language of the first 30 s: mr, en or hi (anything else → mr)."""
        import torch

        with self._lazy.using() as (proc, model, dtype):
            chunk = samples[: int(_CHUNK_S * TARGET_SR)]
            with self._run_lock, torch.inference_mode():
                feats = proc(chunk, sampling_rate=TARGET_SR, return_tensors="pt").input_features
                code = self._detect(model, proc, feats.to(self.device, dtype=dtype))
        return code

    @staticmethod
    def _detect(model, proc, feats) -> str:
        """Pick mr/en/hi by Whisper's language-id head; anything else → mr."""
        try:
            tok = proc.tokenizer
            ids = model.detect_language(feats)
            code = tok.decode(ids[0]).strip("<|>") if hasattr(ids, "__len__") else "mr"
        except Exception:
            return "mr"
        return code if code in SUPPORTED_LANGS else "mr"


def after_start_of_transcript(seq, sot_id: int):
    """Drop a decoder prompt from generated ids: keep each row from its first
    ``<|startoftranscript|>`` on (rows without one are kept whole)."""
    rows = []
    for row in seq:
        ids = row.tolist() if hasattr(row, "tolist") else list(row)
        rows.append(ids[ids.index(sot_id):] if sot_id in ids else ids)
    return rows


def attach_place_prompts(asr: Any, prompts: dict[str, str]) -> int:
    """Give every Whisper decoder behind ``asr`` (routed, fallback or plain)
    the city's place-name prompts; returns how many decoders got them."""
    n = 0
    stack, seen = [asr], set()
    while stack:
        b = stack.pop()
        if id(b) in seen or b is None:
            continue
        seen.add(id(b))
        if isinstance(b, WhisperASR):
            b.prompts = dict(prompts)
            b._prompt_cache.clear()
            n += 1
        stack += [getattr(b, k, None) for k in ("mr", "multi", "preferred", "fallback")]
    return n


def _inference_mode():
    try:
        import torch
    except ImportError:  # the offline test venv has no torch
        import contextlib

        return contextlib.nullcontext()
    return torch.inference_mode()


def _batch_of_one(chunk: np.ndarray):
    """16 kHz mono float32 as the (1, N) tensor the model card passes."""
    x = np.ascontiguousarray(chunk, dtype=np.float32)[None, :]
    try:
        import torch
    except ImportError:  # offline tests only: production always has torch
        return x
    return torch.from_numpy(x)


def _as_text(out: Any) -> str:
    """The remote code returns a string; tolerate a list/tuple of them."""
    while isinstance(out, (list, tuple)) and out:
        out = out[0]
    return out if isinstance(out, str) else ("" if out is None else str(out))


def assets_revision_error(model_id: str, folder: str, revision: str | None) -> str | None:
    """Why the loaded IndicConformer assets are not the pinned commit, or None.

    The model's own ``from_pretrained`` (remote code, ``model_onnx.py``)
    fetches its ONNX graphs and TorchScript preprocessor with
    ``snapshot_download(repo)`` and ignores ``revision``: the pin selects the
    code transformers imports, not the assets it then loads. Offline, the
    assets come from whatever commit the cache's ``main`` points to; this
    check refuses to run them unless that is the pinned commit."""
    if not revision:
        return None
    got = Path(str(folder or "")).name
    if got and got.startswith(revision):
        return None
    return (f"{model_id}: the assets loaded are from commit {got or '?'}, not the pinned "
            f"revision {revision}; download the pinned commit (scripts/fetch_gated_models.sh) "
            f"or review the new one and pin it")


class IndicConformerASR:
    """AI4Bharat IndicConformer-600M-multilingual (MIT; **gated** on Hugging Face).

    Loaded exactly as the model card documents: ``AutoModel.from_pretrained(
    repo, trust_remote_code=True)`` and ``model(wav, "mr", "rnnt" | "ctc")`` on
    16 kHz mono audio. The remote code runs ONNX graphs, so ``onnxruntime``
    must be in the service venv. Pin ``revision`` to the commit whose
    ``model_onnx.py`` you reviewed: ``trust_remote_code`` executes it.

    Marathi and Hindi only (English is not among its 22 languages); the
    router keeps English on the multilingual Whisper. No confidence is
    reported (the published inference returns text only).
    """

    DEFAULT_MODEL = "ai4bharat/indic-conformer-600m-multilingual"
    LANGS = ("mr", "hi")

    def __init__(self, model_id: str = DEFAULT_MODEL, *, decoder: str = "rnnt",
                 revision: str | None = None, min_free_gib: float = DEFAULT_MIN_FREE_GIB,
                 idle_unload_s: float = 600, loader: Callable[[], Any] | None = None) -> None:
        if decoder not in ("rnnt", "ctc"):
            raise ValueError(f"IndicConformer decoder must be 'rnnt' or 'ctc', not {decoder!r}")
        self.model_id = model_id
        self.decoder = decoder
        self.revision = revision or None
        self._run_lock = threading.Lock()
        self._lazy = LazyModel(
            f"asr:{model_id}", loader or self._load, need_gib=4.0,
            min_free_gib=min_free_gib, idle_unload_s=idle_unload_s,
        )

    def _load(self):
        try:
            import onnxruntime  # noqa: F401  (the model's remote code runs ONNX graphs)
            from transformers import AutoModel
        except ImportError as exc:
            raise not_provisioned(self.model_id, exc, gated=True) from exc
        try:
            model = AutoModel.from_pretrained(self.model_id, trust_remote_code=True,
                                              revision=self.revision)
        except Exception as exc:
            mapped = not_provisioned(self.model_id, exc, gated=True)
            if mapped is not None:
                raise mapped from exc
            raise
        folder = getattr(getattr(model, "config", None), "ts_folder", "")
        why = assets_revision_error(self.model_id, folder, self.revision)
        if why:
            raise ModelNotProvisioned(why)
        return model

    def status(self) -> dict:
        return {"model": self.model_id, "decoder": self.decoder, **self._lazy.status()}

    def maybe_unload_idle(self) -> bool:
        return self._lazy.maybe_unload_idle()

    def unload(self) -> bool:
        return self._lazy.unload()

    def lazy_models(self) -> list[LazyModel]:
        return [self._lazy]

    def transcribe(self, samples: np.ndarray, lang: str | None) -> Transcript:
        lang = lang or "mr"
        if lang not in self.LANGS:
            raise ValueError(f"IndicConformer here serves {self.LANGS}, not {lang!r}")
        with self._lazy.using() as model:
            t0 = time.perf_counter()
            texts: list[str] = []
            step = int(_CHUNK_S * TARGET_SR)
            with self._run_lock, _inference_mode():
                for start in range(0, max(1, samples.size), step):
                    chunk = samples[start:start + step]
                    if chunk.size < int(0.2 * TARGET_SR):
                        continue
                    texts.append(_as_text(model(_batch_of_one(chunk), lang, self.decoder)).strip())
        return Transcript(
            text=" ".join(t for t in texts if t).strip(),
            language=lang,
            confidence=None,
            model=f"{self.model_id} ({self.decoder})",
            seconds=round(time.perf_counter() - t0, 3),
        )


class FallbackASR:
    """The preferred backend first; the fallback when it cannot be provisioned.

    "Cannot be provisioned" is :class:`ModelNotProvisioned`: gated access not
    granted, weights not downloaded, a runtime package missing. That is
    logged once with the reason (``gated: request access at …``), shown in
    ``/health`` and the fallback answers until the service restarts. A
    memory refusal is *not* a reason to switch: it stays a 503, as before.
    """

    def __init__(self, preferred: ASRBackend, fallback: ASRBackend) -> None:
        self.preferred = preferred
        self.fallback = fallback
        self.preferred_error: str | None = None

    @property
    def model_id(self) -> str:
        return self.fallback.model_id if self.preferred_error else self.preferred.model_id

    def transcribe(self, samples: np.ndarray, lang: str | None) -> Transcript:
        if self.preferred_error is None:
            try:
                return self.preferred.transcribe(samples, lang)
            except ModelNotProvisioned as exc:
                self.preferred_error = str(exc)
                log.warning("ASR %s unavailable, using %s: %s", self.preferred.model_id,
                            self.fallback.model_id, exc)
        return self.fallback.transcribe(samples, lang)

    def status(self) -> dict:
        return {"model": self.model_id,
                "active": "fallback" if self.preferred_error else "preferred",
                "preferred": self.preferred.status(), "preferred_error": self.preferred_error,
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
        return lazy_models_of(self.preferred, self.fallback)


class RoutedASR:
    """The Indic languages to the Indic backend; the rest to a multilingual Whisper.

    ``indic_langs`` (default Marathi and Hindi) go to the first backend —
    IndicConformer when it is configured, which is trained on Indian speech
    and was measured far ahead of Whisper on Marathi (see the evaluation) —
    and English goes to the multilingual Whisper. ``lang="auto"`` asks the
    multilingual model which language it is and routes accordingly. Each
    model loads only when its language is used. (The attribute is still
    called ``mr``: Marathi is always among the Indic languages.)
    """

    def __init__(self, marathi: ASRBackend, multilingual: WhisperASR,
                 indic_langs: tuple[str, ...] = ("mr", "hi")) -> None:
        self.mr = marathi
        self.multi = multilingual
        self.indic_langs = tuple(dict.fromkeys(("mr", *indic_langs)))

    @property
    def model_id(self) -> str:
        return self.mr.model_id

    def transcribe(self, samples: np.ndarray, lang: str | None) -> Transcript:
        if lang is None:
            lang = self.multi.detect(samples)
        backend = self.mr if lang in self.indic_langs else self.multi
        return backend.transcribe(samples, lang)

    def status(self) -> dict:
        others = [x for x in SUPPORTED_LANGS if x not in self.indic_langs]
        return {"model": self.model_id, "routes": {"indic": list(self.indic_langs), "multilingual": others},
                "mr": self.mr.status(), "en_hi": self.multi.status()}

    def maybe_unload_idle(self) -> bool:
        a = self.mr.maybe_unload_idle()
        b = self.multi.maybe_unload_idle()
        return a or b

    def unload(self) -> bool:
        a = self.mr.unload()
        b = self.multi.unload()
        return a or b

    def lazy_models(self) -> list[LazyModel]:
        return lazy_models_of(self.mr, self.multi)


def lazy_models_of(*backends: Any) -> list[LazyModel]:
    """Every lazily loaded model behind these backends, once each (fakes have none)."""
    out: list[LazyModel] = []
    for b in backends:
        for lm in getattr(b, "lazy_models", lambda: [])():
            if all(lm is not x for x in out):
                out.append(lm)
    return out
