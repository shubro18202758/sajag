# Voice: field reports and advisories (AI row C)

**What it does.** A field officer speaks a short report in Marathi, Hindi or
English, and in Mumbai usually a mix of the three ("हिंदमाताला पाणी
भरलंय, traffic पूर्ण जाम"). The service returns a structured report: the
place from the city gazetteer, the kind, the severity and the transcript. It
enters the system as `UNVERIFIED-FIELD` and waits for an officer's
confirmation. The other way round, public advisories are read out in
English, Marathi or Hindi.

Service: [`services/speech`](../../services/speech/README.md) · production
port **8194** (loopback) · dev port 9161.

## Decision record

| Question | Decision | Why |
|---|---|---|
| ASR for Marathi and Hindi | AI4Bharat **IndicConformer** 600M multilingual (`ai4bharat/indic-conformer-600m-multilingual`, MIT, gated; access granted), RNNT decoder, pinned to the reviewed commit `2a77d30`; ONNX Runtime on the CPU | on the Mumbai field-report set (synthetic, four Parler voices per language) Marathi WER 7.1 % with every place right (56/56) against 73–76 % for Whisper large-v3 and turbo; Hindi WER 14.0 % against 25–27 %; on real FLEURS read speech Marathi 16.6 %, Hindi 12.8 %. RNNT over CTC because it is better on the real speech. It takes no GPU memory from the shared box |
| ASR for English | `openai/whisper-large-v3-turbo` (MIT) with the city's place names as a decoder prompt, also language detection for `lang=auto`; loaded on demand | English is not among IndicConformer's languages; the prompt halves English WER on the field reports (19.6 % → 10.2 %) and gets 47 of 52 places instead of 43 |
| Fallback ASR (Marathi, Hindi) | `openai/whisper-large-v3` answers only while IndicConformer cannot load (gate, weights or package), and `/health` says why (`"active": "fallback"`); a memory refusal stays a 503 | the better of the two Whisper checkpoints on Marathi; a report is never lost because one model is down, and the answer names the model that actually answered so the officer can weigh it |
| Gated models | IndicConformer (ASR) and Indic Parler-TTS are gated on Hugging Face; access was granted to the deployment's account on 29 Oct 2026 | both adapters load lazily; while a model cannot load, `/health` says `gated: request access at https://huggingface.co/…` or the reason, and the fallback answers; a memory refusal stays a 503 and never switches models. [Runbook](#when-access-is-granted) |
| TTS model | AI4Bharat **Indic Parler-TTS** (`ai4bharat/indic-parler-tts` rev `660bc53`, Apache-2.0) for Marathi, Hindi and English, live since 29 Oct 2026; Svara-TTS v1 (`kenpath/svara-tts-v1`, Apache-2.0) + SNAC 24 kHz codec (MIT) answers while Parler cannot load | Parler covers all three languages with named, trained voices; in the earlier round on the reference pack it was understood better by the ASR than Svara in half the synthesis time |
| Indic Parler-TTS runtime | its own venv, run as a child process over pipes (`speech_service.parler_worker`) | `parler-tts` 0.2.3 pins `transformers==4.46.1`; the service runs on transformers 5.x. No port is opened |
| Svara runtime (fallback) | llama.cpp `llama-server` on a Q8_0 GGUF conversion, started on demand; transformers bf16 as the fallback (and in the container) | ≈60 against ≈20 speech tokens/s on the GB10 |
| Svara prompt | the single human turn as the model card's demo builds it | an earlier layout made the model read its speaker label aloud |
| Voices | Parler: the model card's recommended speakers, Marathi **Sunita / Sanjay**, Hindi **Divya / Rohit**, English **Mary / Thoma**, with the house caption (`SPEECH_TTS_PARLER_DESCRIPTION`: calm, clear, unhurried); seeded sampling | calm and clear for advisories; one text gives one waveform, so the cache is exact |
| Place matching | fuzzy over `landmarks.json` + `gazetteer.json` + spoken aliases, with a cross-script consonant skeleton; a name split in two ("हिंद माता") goes to the whole name, not to a place its first half spells | ASR spells names inconsistently, and Mumbai's places have several names (below) |
| Kind / severity | keyword rules (Marathi, Hindi, English and romanised) with the deciding words returned | explainable to the officer; no extra model |
| Report state | always `UNVERIFIED-FIELD`, `requires_confirmation: true` | the AI proposes, a named officer decides |
| Privacy | audio decoded in memory and dropped; no speaker identification; no voice storage | only the transcript is needed |
| Lifecycle | lazy load, unload after 10 idle minutes, refuse below an 8 GiB floor | the GB10 is shared with live models |

### Mumbai's place names

Officers rarely use the signboard name. The matcher carries the names people
actually say, in Devanagari and in Latin letters, and maps them to the
canonical ids of `cities/mumbai/landmarks.json`:

| Said | Canonical place (id) |
|---|---|
| शीव, सायन, Sion | Sion Circle (`sion_circle`) |
| वांद्रे (Marathi), बांद्रा (Hindi), Bandra | Bandra station (`bandra`) |
| परळ (Marathi), परेल (Hindi), Parel | Parel (`parel`) |
| वरळी नाका, वर्ली नाका, Worli Naka | Worli Naka (`worli_naka`) |
| सीएसएमटी, व्हीटी, CST, VT | CSMT (`csmt`) |
| किंग्ज सर्कल, किंग्स सर्कल, King's Circle | King's Circle (Matunga) (`kings_circle`) |
| सी लिंक, सागरी सेतू, Sea Link | Bandra–Worli Sea Link (`sea_link`) |
| हिंदमाता, हिंद माता | Hindmata (Dadar East) (`hindmata`) |

Code-switching is normal in Mumbai. IndicConformer transcribes Marathi and
Hindi in Devanagari, so English words inside that speech come out in
Devanagari too ("सबवे", "ट्रॅफिक जाम", "सिग्नल"), and the kind rules and the matcher accept those spellings as well
as the English ones.

## Integration contract

- `POST /speech/report?lang=mr|hi|en|auto` with the browser recording as the
  raw body (`Content-Type: audio/webm` from `MediaRecorder`, or `audio/wav`),
  or JSON `{"text": "…", "lang": "mr"}` for a typed report. With `auto`,
  whisper-large-v3-turbo detects the language and the router sends the audio
  to the right model.
- Show the answer as **"Field report · unverified"** with the transcript, the
  matched place (and `place_candidates` when `place` is `null`), kind and
  severity, and the cue words. An officer confirms, edits or dismisses it.
- `POST /speech/speak` with `{"text", "lang": "mr"|"hi"|"en"}` returns
  `audio/wav`; the public page plays it with a "synthetic voice" note
  (`X-Speech-Label: synthetic-voice`). `X-Speech-Model` names the model that
  spoke.
- `503` = the model cannot load right now (memory); retry later.

## Making room

The voice models load on demand and share the box's memory with the resident models, so a load
that would leave MemAvailable under the 8 GiB floor is refused. Before refusing, the service makes
room (`memroom.py`): it first releases its own other model (the Parler worker while the ASR loads,
or the reverse), then asks forecast and vision on loopback (`POST /admin/release?idle_s=0`, 2 s
each) to release theirs, polls MemAvailable for up to 5 s and checks the same floor again; the
floor never moves. A waiting load has priority: any of these on-demand models that is not serving
a request right now may be released, however recently it was used (`SPEECH_MAKE_ROOM_IDLE_S`,
default 0); one serving a request never is, and nothing else on the box is touched.

A load that passed the floor check can still run out of GPU memory, even when creating the CUDA
context (`cuDevicePrimaryCtxRetain`): on this unified-memory box MemAvailable counts page cache and
swap that a GPU allocation cannot use (seen live on 29 Oct with 20.7 GiB available and about 3 GiB
free). Such a load makes room for its own size the same way and is tried once more; `/health`
records MemFree beside MemAvailable. The service creates its CUDA context at start, while memory
allows (`SPEECH_CUDA_CONTEXT_AT_START`). It loads one model at a time (an ASR load beside a loading
Parler worker ran the GPU out of memory), and a load that waits checks memory after the other has
finished.

Released models are not restarted afterwards: each reloads on its own next use. `/health` →
`make_room` shows the last attempt (why, what was asked and freed, MemAvailable and MemFree before
and after, whether the load then succeeded) and the last release this service was asked for; a 503
that follows an attempt says what it found. `POST /admin/release` called by hand keeps a 20 s
default (`SPEECH_RELEASE_IDLE_S`); `SPEECH_MAKE_ROOM=0` turns making room off. Before a demo
segment, `scripts/ai_warm.sh speech` releases the other idle models and loads the voice and the
ASR ahead of time.

## Evaluation

Method and per-clip results:
[`services/speech/README.md#evaluation`](../../services/speech/README.md#evaluation),
[`services/speech/eval/results.json`](../../services/speech/eval/results.json).

### The Mumbai set

- **Set:** short Mumbai field-report phrases in Marathi, Hindi and English
  (`eval/phrases.json`), written in the words a traffic officer or BMC field
  worker would use: waterlogging at Hindmata and the subways, a tree fall at
  King's Circle, a jam at Sion Circle and Kalanagar, a visarjan procession at
  Lalbaug, a live wire at Worli Naka, a bus broken down on the Sea Link. Place
  ids are `cities/mumbai/landmarks.json` ids.
- **Audio:** synthesized by Indic Parler-TTS in the house voices and in other
  trained voices of each language, so the ASR is not measured only on the
  voices it will hear in advisories. This is a **synthetic round trip**;
  nobody was recorded.
- **Scoring:** word error rate (WER) on the transcript; place (top-1) and kind
  by the report rules; the upper bound is the report rules on the reference
  text.

**Results (30 Oct 2026, synthetic round trip, 160 clips; the configuration the service runs):** Marathi and Hindi
on IndicConformer (RNNT decoder), English on whisper-large-v3-turbo with Mumbai's place names as a decoder prompt.
On real read speech (FLEURS, 15 clips per language, general sentences) IndicConformer has WER 16.6 % in Marathi
and 12.8 % in Hindi; Whisper turbo has 5.5 % in English. Whisper on Marathi is far behind (WER 73–76 % on the
same clips), which is why it is only the fallback.

| Language | ASR | WER | Place (top-1) | Kind |
|---|---|---|---|---|
| Marathi | IndicConformer RNNT | 7.1 % | 56 of 56 | 56 of 56 |
| Hindi | IndicConformer RNNT | 14.0 % | 50 of 52 | 52 of 52 |
| English | whisper-large-v3-turbo | 10.2 % | 47 of 52 | 46 of 52 |

### The 29 Oct gated round: IndicConformer and Indic Parler-TTS

Access to both gated models was granted on 29 Oct 2026, and both were measured
that evening. That round ran on the Kolkata reference pack (`cities/kolkata`),
where the service was first built, in another Indian language. Its word-error, place and kind
figures are **not** Marathi results and are not repeated here; they stay in
`eval/results.json` (`round_29oct`, `round_gated_29oct`) for the record. What
does not depend on the language carries over:

- **IndicConformer speed and memory (29 Oct 2026, GB10):** median 0.46 s per
  short clip with the RNNT decoder (0.38 s with CTC), on ONNX Runtime's CPU
  provider; with the model loaded the process held 3.9 GiB RSS and 0.26 GiB
  GPU (the TorchScript front end and the CUDA context).
- **IndicConformer is deterministic:** a second run on the same files gave
  identical transcripts. The Whisper-family checkpoints decoding in fp16 on
  the shared GPU did not (6 of 60 transcripts changed between runs).
- **Indic Parler-TTS cost:** median 3.5 s to synthesize 3.7 s of audio (0.97×
  real time); worker load 35 s, first clip 41 s; 11.5 GiB peak while loading
  (fp32 weights pass through the CPU), 2.0–5.6 GiB RSS + 4.6 GiB GPU once
  loaded.
- **Loudness:** one Indic voice came out about 18 dB quieter than English
  (RMS −37 against −18 dBFS), so every voice is now levelled to about
  −20 dBFS RMS with the peak held under −1 dBFS (`audio.level_speech`; the
  cache key carries `LEVEL_FORMAT`, so older audio is regenerated).

### IndicConformer's remote code (reviewed 29 Oct 2026)

`trust_remote_code` imports only `model_onnx.py` (named in `config.json`; it
has no relative imports, so `model_ts.py` and `model_onnx_1b_batched_rnnt.py`
in the same repo are never loaded). It imports transformers, torch, numpy,
json, os, onnxruntime and `huggingface_hub.snapshot_download`. There is no
subprocess, socket, eval/exec or pickle call, and it writes no files. It reads
`vocab.json`, `language_masks.json`, 28 ONNX graphs (standard ONNX operators
only, no custom-op domains; their 366 external-data files are plain names in
the same folder) and one TorchScript file, `preprocessor.ts`. That file is
NeMo's mel-spectrogram front end (pre-emphasis, STFT, mel filterbank, log,
per-feature normalisation), and its pickles reference only torch's tensor
helpers.

One thing goes beyond loading and inference: the model's own
`from_pretrained` calls `snapshot_download(repo)` and ignores `revision`,
`local_files_only` and `cache_dir`. Online, that contacts huggingface.co on
every load and fetches the assets of `main`, whatever commit the code was
pinned to. Offline (`HF_HUB_OFFLINE=1`, as the systemd unit and the container
run), it uses whichever commit the local cache's `main` points to. The adapter
therefore refuses assets from any commit other than
`SPEECH_ASR_INDIC_CONFORMER_REVISION`: the fallback answers and `/health` says
why. Two quirks were measured as published: it prints "Please check
FRAME_DURATION_MS…" on every load, and it builds its config from the class
defaults (SOS 5632) rather than from `config.json` (SOS 256). It reports no
confidence (the published inference returns text only), so the deck shows
none for those reports.

## When access is granted

Both models are gated on Hugging Face; the account owner requests access on
each page (accepting AI4Bharat's terms):
<https://huggingface.co/ai4bharat/indic-conformer-600m-multilingual> and
<https://huggingface.co/ai4bharat/indic-parler-tts>. Nothing here tries to get
around the gate. Access was granted on 29 Oct 2026. Commands run from
`services/speech`; `$SVC_PY` is the service venv's python, `$CLIPS` the
evaluation WAVs.

1. **Check and download** (the service runs offline, so the weights must be
   in the local cache first):
   ```bash
   PY=$SVC_PY scripts/fetch_gated_models.sh check   # "access granted" / "gated: request access at …"
   PY=$SVC_PY scripts/fetch_gated_models.sh all     # downloads; prints the commit to pin
   ```
2. **Runtime packages.** IndicConformer runs its own ONNX code
   (`trust_remote_code`): read `model_onnx.py` in the downloaded snapshot,
   then
   ```bash
   $SVC_PY -m pip install onnxruntime==1.31.1              # CPU (installs and imports on the GB10)
   scripts/make_parler_venv.sh ~/argus/sajag/.venvs/speech-parler $SVC_PY   # Parler's own venv (transformers 4.46.1)
   ```
   The model card's install line also has torchaudio, but `model_onnx.py`
   does not import it. The service venv needs onnxruntime only for
   IndicConformer.
3. **Evaluate** on the Mumbai set, one model per process:
   ```bash
   HF_HUB_OFFLINE=1 $SVC_PY eval/run_eval.py asr --audio $CLIPS --models indic_conformer       # RNNT
   HF_HUB_OFFLINE=1 $SVC_PY eval/run_eval.py asr --audio $CLIPS --models indic_conformer@ctc   # CTC
   ```
   It adds a row to `eval/results.json` (or prints `SKIPPED: gated: …`);
   `SPEECH_ASR_INDIC_CONFORMER_REVISION` in the environment pins the commit
   here too.
4. **Switch** in `~/.config/sajag/sajag.env` (absolute paths: the systemd
   unit does not expand variables there), then restart the speech service:
   ```bash
   SPEECH_ASR_BACKEND=indic_conformer
   SPEECH_ASR_INDIC_CONFORMER_REVISION=2a77d305038dfc502fd9464e7d028b90381976cb
   SPEECH_ASR_INDIC_CONFORMER_DECODER=rnnt
   SPEECH_TTS_BACKEND=indic_parler
   SPEECH_TTS_PARLER_PYTHON=/home/<user>/sajag/.venvs/speech-parler/bin/python
   SPEECH_TTS_PARLER_REVISION=660bc53c64ae83150613264111708a0465211237
   ```
   Pinned revisions: IndicConformer `2a77d305038dfc502fd9464e7d028b90381976cb`;
   Indic Parler-TTS `660bc53c64ae83150613264111708a0465211237` (its description
   tokenizer, `google/flan-t5-large`, `0613663d0d48ea86ba8cb3d7a44f0f65dc596a2a`).
   Synthesize the standing advisories once after the restart, so that no
   reader waits for the worker's 35 s cold start. `GET /health` shows
   `"active": "preferred"` or, if a model still cannot load,
   `"active": "fallback"` with the reason in `preferred_error`; the
   `asr.model` of a report and the `X-Speech-Model` header of an advisory
   name the model that actually answered. Back out by removing the lines
   (rollback for TTS: `SPEECH_TTS_BACKEND=auto`, and Svara answers again).

The model cards now point to successors, `bodhan-ai/indic-transcribe-core`
and `bodhan-ai/indic-speak`; both are gated and under a custom licence (Bodhan
AI Open Model License), which needs reading before they are considered.

## Limits

- The evaluation audio is **synthetic** (the service's own TTS). Real field
  audio will be harder: phones, rain on the microphone, traffic, and
  code-switching between Marathi, Hindi and English mid-sentence. Before a
  pilot: a consented recording set from officers in one traffic division, and
  a re-run of this evaluation on it.
- The Marathi and Hindi results above are on synthetic voices and are an optimistic bound; place and kind on
  real Marathi field speech are not yet measured.
- Mumbai's places have several spoken names (Sion and शीव, Bandra and वांद्रे,
  CSMT and VT). The alias list covers the common ones; the matcher returns
  candidates when it is unsure rather than asserting a place.
- Kind and severity are keyword rules with simple negation; they are
  explainable but not exhaustive.
- TTS is slower than real time on the shared GPU at a cold start: synthesize
  advisories ahead and serve them from the cache.
- Nobody has listened systematically to the Marathi and Hindi advisories in
  Mumbai voices; a native listener should check a few in each language before
  they go to the public page.
