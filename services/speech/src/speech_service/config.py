"""Configuration for the speech service (environment prefix ``SPEECH_``).

Everything binds loopback by default. The production port is 8194; a dev run
picks its own port through ``SPEECH_PORT``.

Model ids are config, not code: the ASR and TTS backends load whatever the
environment names, lazily on the first request, and drop the weights again
after ``SPEECH_IDLE_UNLOAD_S`` seconds without a call (the box is shared).
Before a load the service checks MemAvailable and refuses (503) below
``SPEECH_MIN_FREE_GIB``, so it never pushes the host into the memory guard.
Before refusing it makes room (``memroom.py``): its own idle models, then the
other on-demand services' idle ones (``POST /admin/release`` on loopback), are
released and the same floor is checked again. Released models reload on their
next use.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

__all__ = ["Settings", "get_settings", "default_city_dir", "DEFAULT_MIN_FREE_GIB"]

#: defined in runtime (no pydantic there), so the Parler worker's own venv can import tts
from .runtime import DEFAULT_MIN_FREE_GIB  # noqa: E402


def default_city_dir() -> Path:
    """``cities/<city>`` of the repo checkout, or ``/app/cities/<city>`` in the
    container (compose mounts the city pack read-only there). The city is
    ``SAJAG_CITY`` (default ``mumbai``); ``SPEECH_CITY_DIR`` overrides the
    whole path."""
    city = (os.environ.get("SAJAG_CITY") or "mumbai").strip().lower() or "mumbai"
    here = Path(__file__).resolve()
    for parent in here.parents:
        cand = parent / "cities" / city
        if (cand / "landmarks.json").is_file():
            return cand
    return Path("/app/cities") / city


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SPEECH_", extra="ignore")

    host: str = "127.0.0.1"
    port: int = 8194

    # CORS: the deck reaches the service through its own proxy, so no browser
    # origin is allowed by default. Comma-separated http(s)://host[:port].
    deck_origins: str = ""

    # --- ASR -----------------------------------------------------------------
    # Marathi and Hindi (``asr_indic_langs``) go to the Indic backend:
    # "indic_conformer" (default): AI4Bharat IndicConformer-600M-multilingual
    # (MIT, gated on Hugging Face; access granted to the deployment's account),
    # with the Whisper checkpoint ``asr_model`` taking over automatically while
    # it cannot load; "whisper": ``asr_model`` answers them directly. English
    # (and language detection for lang=auto) go to ``asr_multilingual_model``.
    # Chosen by the evaluation in eval/; see README "Models".
    asr_backend: str = "indic_conformer"
    asr_indic_langs: str = "mr,hi"
    # Whisper fallback for Marathi/Hindi (MIT): the best Whisper on the Marathi set.
    asr_model: str = "openai/whisper-large-v3"
    asr_indic_conformer_model: str = "ai4bharat/indic-conformer-600m-multilingual"
    asr_indic_conformer_decoder: str = "rnnt"  # or "ctc"
    # The model runs its own code (trust_remote_code): pin the commit whose
    # model_onnx.py was reviewed (2a77d30, 29 Oct). The remote code fetches its
    # ONNX assets from main regardless, so the adapter refuses assets from any
    # commit other than this one. Empty = the repo's main branch.
    asr_indic_conformer_revision: str = "2a77d305038dfc502fd9464e7d028b90381976cb"
    # English and language detection: a general multilingual Whisper. MIT; fast.
    asr_multilingual_model: str = "openai/whisper-large-v3-turbo"
    asr_default_lang: str = "mr"
    asr_beams: int = 1
    # Whisper decoders get the city's place names as a prompt (places.Gazetteer.prompt):
    # it spells "Worli Naka", "KEM", "Ghatkopar" instead of "Walinaka", "Chem", "Ghat Kho Par".
    asr_place_prompt: bool = True

    # --- TTS -----------------------------------------------------------------
    # "auto": the llama.cpp GGUF backend when the GGUF and llama-server exist
    # (about 3x faster on the GB10), else transformers. Or force one of
    # "llama" / "transformers". "indic_parler": AI4Bharat Indic Parler-TTS
    # (gated), with Svara ("auto") taking over while it cannot load.
    tts_backend: str = "auto"
    tts_parler_model: str = "ai4bharat/indic-parler-tts"
    # Pin the commit that was evaluated (the fetch script prints it). Empty =
    # the repo's main branch (offline: whatever commit the cache holds).
    tts_parler_revision: str = ""
    # parler-tts pins transformers 4.46.1, so it runs in its own venv: the
    # python of that venv (empty = load it in this process instead).
    tts_parler_python: str = ""
    # Parler caption; {speaker} becomes the language's recommended voice.
    tts_parler_description: str = (
        "{speaker} speaks in a calm, clear and unhurried voice at a steady, moderate pace, "
        "reading a public traffic advisory. The recording is of very high quality, with the "
        "speaker's voice sounding clear and very close up, and no background noise."
    )
    tts_gguf: Path = Path.home() / ".cache" / "sajag" / "svara-gguf" / "svara-tts-v1-q8_0.gguf"
    llama_server_bin: Path = Path.home() / "llama.cpp" / "build" / "bin" / "llama-server"
    tts_llm_port: int = 8202
    tts_llm_manage: bool = True
    tts_llm_url: str = ""
    tts_model: str = "kenpath/svara-tts-v1"
    tts_codec: str = "hubertsiuzdak/snac_24khz"
    # Calm, clear, unhurried public-advisory voice. Svara-TTS takes a speaker
    # id ("Marathi (Female)") and an end-of-utterance style tag; this is the
    # house description of what the service asks it for.
    tts_voice_description: str = (
        "A calm, clear, unhurried female voice reading a public traffic "
        "advisory at a steady pace, close to the microphone, no background noise."
    )
    tts_default_voice: str = "female"
    tts_style_tag: str = "<clear>"
    tts_cache_dir: Path = Path.home() / ".cache" / "sajag" / "speech-tts"
    tts_max_chars: int = 600
    tts_seed: int = 1847

    # --- shared --------------------------------------------------------------
    device: str = "cuda"
    idle_unload_s: int = 600
    min_free_gib: float = DEFAULT_MIN_FREE_GIB
    max_audio_bytes: int = 8 * 1024 * 1024
    max_audio_seconds: float = 60.0
    # --- making room (memroom.py; docs/ai/speech.md "Making room") --------------
    # A load that would break the floor first releases this service's own idle
    # models, then asks the other on-demand services on loopback to release
    # theirs (forecast first: small and quick to reload). Port 0 skips a peer.
    make_room: bool = True
    peer_forecast_port: int = 8195
    peer_vision_port: int = 8196
    # POST /admin/release called by hand (or by scripts/ai_warm.sh) keeps a model used within this
    # many seconds; one serving a request is never released
    release_idle_s: float = 20.0
    # making room for a waiting load has priority: every model not serving a request right now (own
    # and the peers') may be released, however recently used; it reloads on its next use
    make_room_idle_s: float = 0.0
    # create the process's CUDA context at start (see api.open_cuda_context): creating it at the
    # first ASR load failed on the shared box with plenty of memory available
    cuda_context_at_start: bool = True
    make_room_timeout_s: float = 2.0   # per peer call
    make_room_wait_s: float = 5.0      # MemAvailable is polled this long after a release
    city_dir: Path = default_city_dir()
    # Gazetteer from the events stream; optional (landmarks.json always loads).
    gazetteer_file: str = "gazetteer.json"
    place_threshold: float = 0.80


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
