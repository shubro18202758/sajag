# speech — Mumbai field reports and spoken advisories (Marathi, Hindi, English)

Two jobs, both on-premises on the GB10:

1. **Field reports (speech → structured report).** A traffic officer or a
   BMC field worker speaks a short report in Marathi, Hindi or English
   ("हिंदमाता येथे गुडघाभर पाणी साचले आहे, बस अडकल्या आहेत" /
   "अंधेरी सबवे में पानी भर गया है" / "Tree fallen at King's Circle, one lane
   blocked"). The service transcribes it and turns it into a structured
   report: which Mumbai place, what kind of problem, how bad. The report
   always leaves as `UNVERIFIED-FIELD` and waits for an officer's
   confirmation. It is a claim, never an action.
2. **Advisories (text → speech).** A public advisory is read out in Marathi,
   Hindi or English in a calm, clear voice, cached by hash.

## API

| Method | Path | Body | Answer |
|---|---|---|---|
| GET | `/health` | — | model status (loaded or not), place counts, memory |
| POST | `/speech/transcribe?lang=mr` | audio (wav / webm / ogg) as the raw body with its `Content-Type`, or multipart field `audio` | `{text, language, confidence, model, audio_seconds, latency_s}` |
| POST | `/speech/report?lang=mr` | the same audio, **or** JSON `{"text": "…"}` | structured field report (below) |
| POST | `/speech/speak` | JSON `{"text", "lang": "mr"\|"en"\|"hi", "voice": "female"\|"male"}` | `audio/wav` (24 kHz mono); headers `X-Speech-Model`, `X-Speech-Cached`, `X-Speech-Seconds`, `X-Speech-Label: synthetic-voice` |

`lang` is `mr` (default), `hi`, `en` or `auto`. Marathi and Hindi go to the
Indic backend (IndicConformer, with a Whisper checkpoint behind it); English
goes to a multilingual Whisper, which also decides the language for `auto`
and then routes the clip.
Errors: `413` too large (8 MB / 60 s / 600 characters), `415` wrong type,
`422` undecodable or invalid, `503` the model cannot load right now (memory).

A report as the service builds it (`POST /speech/report` with
`{"text": …}` gives the same body with `"source": "field-text"` and
`"asr": null`; `place_candidates` shortened to one here):

```json
{
  "report_id": "9f56444e-3a84-4de0-ae8f-29f57f66849e",
  "received_at": "2026-10-30T09:35:11+00:00",
  "place": {
    "id": "hindmata",
    "name_en": "Hindmata (Dadar East)",
    "name_mr": "हिंदमाता (दादर पूर्व)",
    "lat": 19.00561,
    "lon": 72.83976,
    "match_score": 1.0,
    "matched_text": "हिंदमाता",
    "source": "landmarks"
  },
  "place_candidates": [
    {"id": "hindmata", "name_en": "Hindmata (Dadar East)", "name_mr": "हिंदमाता (दादर पूर्व)",
     "lat": 19.00561, "lon": 72.83976, "match_score": 1.0, "matched_text": "हिंदमाता", "source": "landmarks"}
  ],
  "kind": "waterlogging",
  "kind_cues": ["पाणी साच", "गुडघाभर", "साचल"],
  "severity": "medium",
  "severity_cues": ["गुडघाभर", "बस अडकल"],
  "transcript": "हिंदमाता येथे गुडघाभर पाणी साचले आहे बस अडकल्या आहेत",
  "language": "mr",
  "source": "field-voice",
  "asr": {
    "model": "ai4bharat/indic-conformer-600m-multilingual (rnnt)",
    "confidence": null,
    "audio_seconds": 4.1,
    "asr_seconds": 0.79
  },
  "verification_state": "UNVERIFIED-FIELD",
  "requires_confirmation": true,
  "note": {
    "en": "Field report awaiting an officer's confirmation. It is not an action.",
    "mr": "क्षेत्रातून आलेला अहवाल, अधिकाऱ्याच्या पुष्टीच्या प्रतीक्षेत. ही कारवाई नाही.",
    "hi": "फ़ील्ड से आई रिपोर्ट, अधिकारी की पुष्टि की प्रतीक्षा में। यह कोई कार्रवाई नहीं है।"
  }
}
```

(`confidence` is `null` for IndicConformer: its published inference returns
text only; a Whisper transcript carries one.)

- `place` is the best match over the city's places (`null` when no place
  clears the threshold; `place_candidates` then still lists the top three for
  the officer to pick from). `match_score` is in [0, 1].
- `kind` is one of `waterlogging | jam | accident | tree_fall | blockade |
  procession | fire | live_wire | other`; `kind_cues` and `severity_cues`
  are the exact words that decided them, so the officer can see why.
- `severity` is `low | medium | high`.

## How a report is built

1. **Audio** is decoded in memory: WAV with the standard library, WebM/Ogg
   (what browsers record) through `ffmpeg` over pipes. Nothing is written to
   disk.
2. **ASR** (below) with the language forced to the requested one (Marathi
   unless asked otherwise). A Whisper transcript carries `confidence`, the
   geometric-mean token probability of the decoded text — a "check this
   one" signal, not an accuracy estimate.
3. **Place** (`places.py`): fuzzy matching over
   `cities/mumbai/landmarks.json` (the canonical ids and en/mr/hi spellings)
   plus the events stream's `cities/mumbai/gazetteer.json` when it exists
   (read tolerantly; a landmark id always wins), plus everyday names officers
   actually say (दादर टीटी, सीएसटी / VT for CSMT, बीकेसी, शीव for Sion, WEH /
   पश्चिम द्रुतगती महामार्ग, सी लिंक, अटल सेतू / MTHL, केईएम …). Matching works
   across scripts: Marathi and Hindi (Devanagari), romanised ("Andheri subway
   band hai") and English all reduce to a consonant skeleton (हिंदमाता →
   `hndmt` ← "Hindmata"; वरळी → `brl` ← "Worli": व/v/w and b are one letter,
   as speakers and ASR use them). Devanagari spelling variants that ASR mixes
   up (ी/ि, ू/ु, ळ/ल, ण/न, श/ष/स, nukta, anusvara, ॅ/े, ॉ/ो, doubled
   consonants) are folded. Marathi postpositions written onto the name
   (-मध्ये, -जवळ, -वर, -ला, -बाहेर …) are tried with and without; Hindi ones
   are separate words (में, पर, के पास) and never start a name. A name with a
   qualifier wins over its qualifier when both are said ("WEH … near Andheri"
   is the highway at Andheri, not the station). Skeletons of two consonants
   never assert a place on their own ("सुबह", morning, and "शीव", Sion, are
   both `sb`).
4. **Kind and severity** (`kinds.py`): keyword rules in Marathi, Hindi,
   English and romanised Hindi/Marathi, explainable by design. A strong
   Devanagari cue that the ASR misspelt ("वाहतुक कोन्डी" for वाहतूक कोंडी,
   "विसरजन" for विसर्जन) still counts when its consonant skeleton matches
   exactly (or very closely, for long cues); it is then shown with "(≈)" and
   weighs one point less, and the Marathi and Hindi spellings of one cue
   count once. Negation ("पाणी साचले नाही", "जाम नहीं है", "no water")
   cancels a cue. Short cues that begin other words are whole-word only
   ("आग", fire, never fires inside "आगे", ahead; "पूर", flood, is never read
   into "पूर्व", East). A jam reported together with a cause (water, a fallen
   tree …) is labelled by the cause. Severity reads cues such as
   घोट्याइतके / गुडघाभर / कमरेइतके पाणी and टखने / घुटनों / कमर तक पानी
   (ankle / knee / waist-deep), जखमी / घायल (injured), रस्ता बंद / सड़क बंद
   (road closed); fire and live wires are never below high.

## Models

| Job | Model | Licence | Runtime |
|---|---|---|---|
| ASR, Marathi and Hindi | **`ai4bharat/indic-conformer-600m-multilingual`** (AI4Bharat IndicConformer, 22 Indian languages), RNNT decoder, pinned to the reviewed commit `2a77d30` | MIT (gated on Hugging Face; access granted to the deployment's account, 29 Oct) | ONNX Runtime (its remote code), CPU on the aarch64 wheel |
| ASR fallback for Marathi/Hindi (while IndicConformer cannot load) | `openai/whisper-large-v3` | MIT (release) · Apache-2.0 (card) | transformers, fp16, GPU; loaded only if needed |
| ASR, English, and language detection for `lang=auto` | `openai/whisper-large-v3-turbo`, with the city's place names as a decoder prompt | MIT | transformers, fp16, GPU; loaded only when en/auto is used |
| TTS (advisories) | **Indic Parler-TTS** (`ai4bharat/indic-parler-tts`), the model card's recommended voices: Marathi **Sunita** (female, the house voice) / Sanjay, Hindi Divya / Rohit, English Mary / Thoma | Apache-2.0 (gated; access granted) | its own venv (`parler-tts` pins transformers 4.46.1), a child process over pipes; `SPEECH_TTS_BACKEND=indic_parler` |
| TTS fallback | **Svara-TTS v1** (`kenpath/svara-tts-v1`, Kenpath), 19 Indian languages incl. Marathi ("Marathi (Female)"), Hindi, Indian English | Apache-2.0 (see lineage note) | llama.cpp `llama-server` with a Q8_0 GGUF, or transformers bf16 |
| Codec (Svara) | SNAC 24 kHz (`hubertsiuzdak/snac_24khz`) | MIT | torch, GPU |

**Why these (measured 30 Oct 2026 on the Mumbai set, see [Evaluation](#evaluation)).**
- *Marathi ASR is IndicConformer.* On the Marathi field reports it has
  WER 7.1 % and the place right in 56 of 56 clips (RNNT; CTC: WER 6.2 %, 55/56) — far ahead of every Whisper checkpoint
  available here: `whisper-large-v3` has WER 73.1 % (50/56 places), `whisper-large-v3-turbo`
  76.3 % (48/56). Whisper's Marathi is poor (it is a low-resource language in
  its training data); IndicConformer is trained on Indian speech. On real
  read Marathi (FLEURS) it has WER 16.6 %, CER 4.3 % (RNNT). It runs on the CPU (no CUDA
  provider in the aarch64 ONNX Runtime wheel), so its weights take no GPU
  memory (the process holds 3.9 GiB of RAM), and it is fast (median 0.7 s
  per clip).
- *Hindi goes the same way* (`SPEECH_ASR_INDIC_LANGS=mr,hi`): WER 14.0 %, place 50/52
  against `whisper-large-v3-turbo`'s 27.3 % (19.4 % with the place prompt, place 51/52).
- *RNNT, not CTC:* CTC is slightly better on the synthetic set (WER 6.2 % against 7.1 % in Marathi), RNNT on the real FLEURS speech (16.6 % against 18.4 % in Marathi, 12.8 % against 13.9 % in Hindi) and on Marathi places (56/56 against 55/56), and it is a little faster; real speech decides.
- *English* stays on `whisper-large-v3-turbo` (IndicConformer has no
  English): WER 10.2 % and 47/52 places with the place prompt, against
  19.6 % and 43/52 without it. `whisper-large-v3` with the same prompt is a
  little better (WER 8.4 %, 48/52) but 5× slower (3.3 s against 0.66 s per
  clip) and needs twice the GPU memory; on real English (FLEURS) both are
  good (4.4 % and 5.5 %). `SPEECH_ASR_MULTILINGUAL_MODEL` switches it.
- *The Whisper fallback for Marathi/Hindi* is `whisper-large-v3`, the better
  of the two Whisper checkpoints on Marathi; it only loads if IndicConformer
  cannot (access revoked, weights missing, `onnxruntime` absent), and
  `/health` then says why (`preferred_error`, `"active": "fallback"`). A
  memory refusal is not a reason to switch: it stays a 503.
- *Not measured:* Marathi fine-tunes of Whisper on Hugging Face are old
  (2022) `.bin` checkpoints trained on Common Voice 11; the one with a clear
  licence (`DrishtiSharma/whisper-large-v2-marathi`, Apache-2.0) is a 6 GB
  pickle download and was not pursued once IndicConformer measured as it did.
  `facebook/omniASR-CTC-1B` (cached) needs `fairseq2n`, which has no Linux
  aarch64 build.
- *TTS: Indic Parler-TTS* has trained Marathi voices; the model card
  recommends Sanjay and Sunita for Marathi. Sunita is the house advisory
  voice (calm, clear, unhurried caption). Synthesis on the shared GPU:
  median 3.7 s for a 3.8 s clip (0.94× real time).
- *The gated models are pinned and fall back by config.* IndicConformer
  runs its own code (`trust_remote_code`), so the service pins the commit
  whose `model_onnx.py` was reviewed (`SPEECH_ASR_INDIC_CONFORMER_REVISION`)
  and refuses ONNX assets from any other commit. Parler is pinned the same
  way (`SPEECH_TTS_PARLER_REVISION`). Runbook:
  [docs/ai/speech.md, "When access is granted"](../../docs/ai/speech.md#when-access-is-granted).
- *Lineage note:* Svara-TTS is fine-tuned from Canopy Labs' Orpheus 3B, which
  is itself built on Meta's Llama-3.2-3B (Llama 3.2 Community License), and
  is trained on SYSPIN, RASA, IndicTTS and SPICOR speech. The model is
  published as Apache-2.0; check the base-model and data terms before a
  commercial deployment.

**The advisory voice.** Indic Parler-TTS takes a free-text caption with a
trained speaker's name: the house caption is "{speaker} speaks in a calm,
clear and unhurried voice at a steady, moderate pace, reading a public
traffic advisory …" (`SPEECH_TTS_PARLER_DESCRIPTION`), with Sunita for
Marathi, Divya for Hindi and Mary for English (`voice: "male"`: Sanjay,
Rohit, Thoma). Sampling is seeded from the text, so one text always gives
the same audio and the cache is exact. Long text is read sentence by
sentence (। . ! ?).

**Svara fallback.** With `SPEECH_TTS_BACKEND=auto` (the code default; the
deployment sets `indic_parler`) Svara answers, through llama.cpp when the
GGUF and `llama-server` exist (the service starts its own server on
127.0.0.1:`SPEECH_TTS_LLM_PORT`), else transformers. Svara takes a speaker id
("Marathi (Female)") and the `<clear>` style tag; the prompt is the single
human turn the model card's demo builds (an earlier layout made the model
read its speaker label aloud; `PROMPT_FORMAT` is part of the cache key, so
old audio is never served).

**Memory and latency** (GB10, shared with the live system's models; measured 30 Oct 2026):

| Part | Memory while loaded | Latency |
|---|---|---|
| ASR, IndicConformer RNNT (mr, hi) | 3.9 GiB RAM (ONNX Runtime on the CPU; 0.26 GiB GPU for the process's CUDA context) | median 0.66 s per clip (≈3.8 s of speech); first load 11 s |
| ASR, whisper-large-v3-turbo (en, `auto`) | 2.0 GiB GPU + 1.8 GiB RAM, only once en/auto is used | median 0.51 s per English clip, 0.66 s with the place prompt; first load 22 s |
| ASR, whisper-large-v3 (fallback only) | 3.9 GiB GPU + 2.0 GiB RAM, only if IndicConformer cannot load | median 2.6–3.9 s per clip; first load 33 s |
| TTS, Indic Parler-TTS (its own process) | 4.7 GiB GPU + 2.6 GiB RAM in the worker process (7.5 GiB RAM peak while loading) | median 3.7 s for a 3.8 s clip (0.94× real time) |

Models load on first use and unload after `SPEECH_IDLE_UNLOAD_S` (600 s)
idle. Before a load the service checks MemAvailable and refuses (503) when
the load would leave less than `SPEECH_MIN_FREE_GIB` (the host memory guard
evicts llama servers under 6 GiB available).

## Privacy

- **No speaker identification**, no voice prints, no speaker embeddings.
- **No voice storage.** Uploaded audio is decoded in memory and discarded
  when the request ends; it is never written to disk or logged. Only the
  transcript leaves the service, inside the response.
- The only files the service writes are the advisory audio it synthesizes
  itself (TTS cache, keyed by a hash of model, voice, language and text).
- Advisory audio is synthetic and labelled so (`X-Speech-Label:
  synthetic-voice`); it imitates no real person.

## Evaluation

**What it is.** 40 short Mumbai field-report phrases — 14 Marathi, 13 Hindi,
13 English ([`eval/phrases.json`](eval/phrases.json); Hindmata, Milan and
Andheri subways, King's Circle, Sion, Dadar TT, Kurla, Worli Naka, BKC,
Girgaon Chowpatty, the WEH …; all eight kinds plus "other") — spoken by
**Indic Parler-TTS with four trained voices per language** (the two house
voices and two others: Marathi Sunita, Sanjay, Radha, Nikhil; Hindi Divya,
Rohit, Rani, Aman; English Mary, Thoma, Meera, Jatin), then transcribed: a
**synthetic round trip**, 160 clips, 10.3 minutes of audio. No person was
recorded. Synthetic speech is clean and evenly paced, so these numbers are
an optimistic bound for a phone at a waterlogged junction. As a real-speech
reference, every checkpoint was also scored on **45 real read-speech clips**
(15 per language, the first clips of the FLEURS dev split, CC BY 4.0;
general sentences, not field reports, so WER/CER only). Raw transcripts and
per-clip results: [`eval/results.json`](eval/results.json); method:
[`eval/run_eval.py`](eval/run_eval.py) (`synth-parler`, `asr`, `fetch-real`,
`real`, `rescore`). WER/CER ignore punctuation. Place is the top-1 match at
the 0.80 threshold; place and kind use the final rules on every model's
transcripts (`rescore`).

Upper bound (the report rules on the reference text, no audio): place
**40/40**, kind **40/40**.

**Field reports, synthetic round trip** (30 Oct 2026; bold = what the
service runs: Marathi and Hindi on IndicConformer RNNT, English on Whisper
turbo with the place prompt):

| ASR checkpoint | Language | Clips | WER | CER | Place (top-1) | Kind | s / clip (median) | In service |
|---|---|---|---|---|---|---|---|---|
| **IndicConformer-600M, RNNT** | mr | 56 | **7.1 %** | 1.2 % | **56/56** | 56/56 | 0.69 | **yes** |
| **IndicConformer-600M, RNNT** | hi | 52 | **14.0 %** | 3.6 % | **50/52** | 52/52 | 0.61 | **yes** |
| IndicConformer-600M, CTC | mr | 56 | 6.2 % | 1.4 % | 55/56 | 56/56 | 0.83 |  |
| IndicConformer-600M, CTC | hi | 52 | 12.1 % | 3.8 % | 50/52 | 52/52 | 0.71 |  |
| whisper-large-v3-turbo + place prompt | hi | 52 | 19.4 % | 6.5 % | 51/52 | 52/52 | 1.05 |  |
| **whisper-large-v3-turbo + place prompt** | en | 52 | **10.2 %** | 3.1 % | **47/52** | 46/52 | 0.66 | **yes** |
| whisper-large-v3-turbo | mr | 56 | 76.3 % | 18.7 % | 48/56 | 52/56 | 1.18 |  |
| whisper-large-v3-turbo | hi | 52 | 27.3 % | 10.7 % | 50/52 | 52/52 | 0.87 |  |
| whisper-large-v3-turbo | en | 52 | 19.6 % | 6.2 % | 43/52 | 48/52 | 0.51 |  |
| whisper-large-v3 + place prompt | en | 52 | 8.4 % | 2.9 % | 48/52 | 46/52 | 3.31 |  |
| whisper-large-v3 | mr | 56 | 73.1 % | 18.8 % | 50/56 | 52/56 | 3.91 |  |
| whisper-large-v3 | hi | 52 | 24.8 % | 7.9 % | 49/52 | 51/52 | 3.78 |  |
| whisper-large-v3 | en | 52 | 14.8 % | 5.0 % | 44/52 | 47/52 | 2.56 |  |

**Real read speech, FLEURS** (15 clips per language; WER/CER only):

| ASR checkpoint | FLEURS mr (15) WER / CER | FLEURS hi (15) WER / CER | FLEURS en (15) WER / CER |
|---|---|---|---|
| IndicConformer-600M, RNNT | 16.6 % / 4.3 % | 12.8 % / 5.1 % | — (no English) |
| IndicConformer-600M, CTC | 18.4 % / 4.8 % | 13.9 % / 5.4 % | — (no English) |
| whisper-large-v3-turbo + place prompt | 79.1 % / 24.9 % | 27.7 % / 11.2 % | 5.5 % / 1.8 % |
| whisper-large-v3-turbo | 77.7 % / 22.9 % | 27.2 % / 10.1 % | 5.5 % / 1.8 % |
| whisper-large-v3 | 80.2 % / 23.5 % | 27.2 % / 9.0 % | 4.4 % / 1.3 % |

"s / clip" is ASR time per clip on the shared GPU/CPU (median; it varies by
about 2× between runs). IndicConformer has no English, so its English cells
are empty.

**What the numbers say.**
- *Marathi:* IndicConformer is in a different class from Whisper: WER 7.1 %
  (RNNT) / 6.2 % (CTC) against 73–76 % for both Whisper checkpoints, and the
  place is right in 56 of 56 clips. On real read Marathi it holds up
  (WER 16.6 %, CER 4.3 %). Whisper writes Marathi as a Hindi-flavoured
  approximation (wrong verb endings, Hindi spellings), so most words count as
  errors, yet the place matcher still recovers 48–50 of 56 places from it.
- *RNNT over CTC:* CTC has a slightly lower WER on the synthetic set, RNNT
  is better on the real FLEURS speech (mr 16.6 % against 18.4 %, hi 12.8 %
  against 13.9 %), places one more Marathi clip and is a little faster, so
  the service uses RNNT (the model card's default).
- *Hindi:* IndicConformer RNNT WER 14.0 %, place 50/52; Whisper turbo with
  the place prompt has a higher WER (19.4 %) and one more place (51/52).
  Hindi stays on IndicConformer (lower WER on both sets, CPU, no GPU memory);
  `SPEECH_ASR_INDIC_LANGS=mr` sends Hindi to Whisper instead.
- *English and the place prompt:* Whisper hears Mumbai names as English
  words ("Walinaka", "Ghat Kho Par", "Chem Hospital", "Xi'an Circle"). Given
  the city's place names as a decoder prompt (`SPEECH_ASR_PLACE_PROMPT`,
  on by default, built from `landmarks.json`), turbo's English WER halves
  (19.6 % → 10.2 %) and places go 43 → 47 of 52; Hindi improves the same way.
  The prompt can bias a decoder towards names that were not said; on the
  45 FLEURS sentences (no Mumbai place in them) it left turbo's English WER
  unchanged (5.5 %; one word changed case), moved its Hindi and Marathi WER
  by under 2 points, and made the matcher assert no place it did not assert
  without the prompt.
- *Misses that remain* are mostly names the TTS voice itself mispronounced
  ("तला नगर" for Kalanagar, "पैल" for Parel, "Kullla" for Kurla) and English
  cue words misheard ("Kedip water" for knee-deep, "Leaf wire" for live wire).
  One English clip asserted a wrong place ("Xion Circle" → King's Circle).
- *Rules were tuned on this set.* The place matcher's ASR tolerances (b/v,
  doubled consonants, spelt-out initials such as "के ई एम", a long name with
  one misheard word) and two English cues ("deep water", "wire") were added
  after reading these transcripts, and every row is re-scored with the final
  rules. Place and kind accuracy here are therefore optimistic; WER/CER are
  not affected (the ASR output is unchanged).

**End to end through the service** (a dev instance with the default
configuration, `POST /speech/report?lang=…` with each of the 160 WAVs):
WER 10.5 %, place **153/160** (Marathi 56/56, Hindi 50/52, English 47/52),
kind 154/160, median **1.0 s per report**; every report `UNVERIFIED-FIELD`.
Advisories through the service the other way round (`/speech/speak` with
Parler, then `/speech/report` on that audio; six advisories in three
languages): every transcript readable, kind right in five of six, and the
place right in the four that name one place; the other two (Marathi and
English) name two places ("Hindmata … via Dadar TT Circle") and the matcher
took the longer name, Dadar TT, with Hindmata among the three candidates. The first `/speech/speak`
took 140 s (the Parler worker starting and loading); later ones 3.5–12 s.

**TTS.** Indic Parler-TTS spoke all 160 clips: median **3.7 s to synthesize
a 3.8 s clip** (0.94× real time on the shared GPU; Marathi 3.8 s for 4.0 s,
Hindi 3.5 s for 3.5 s, English 3.5 s for 3.7 s). Every Marathi clip it
produced was transcribed by IndicConformer with the place right (56/56).


## Run

```bash
# once: the Q8_0 GGUF for the fast TTS backend (else TTS runs in transformers)
scripts/convert_svara_gguf.sh
# dev: port 9161, TTS llama-server on 9164; the HF cache must hold the models
PYTHONPATH=src SPEECH_PORT=9161 SPEECH_TTS_LLM_PORT=9164 python -m speech_service
curl -s -X POST -H 'Content-Type: audio/wav' --data-binary @report.wav 127.0.0.1:9161/speech/report
curl -s -X POST -H 'Content-Type: application/json' \
     -d '{"text":"हिंदमाता येथे पाणी साचले आहे. कृपया पर्यायी मार्ग वापरा.","lang":"mr"}' \
     127.0.0.1:9161/speech/speak -o advisory.wav
```

Production: port **8194**, loopback only (`infra/compose.ai-media.yml`,
`infra/docker/Dockerfile.speech`; the container mounts the host's Hugging
Face cache read-only and runs offline).

## Configuration

Environment variables (prefix `SPEECH_`, see `config.py`):

| Variable | Default | Meaning |
|---|---|---|
| `SPEECH_HOST` / `SPEECH_PORT` | `127.0.0.1` / `8194` | bind address |
| `SPEECH_ASR_BACKEND` | `indic_conformer` | `indic_conformer` (gated; `SPEECH_ASR_MODEL` answers until it loads) or `whisper` |
| `SPEECH_ASR_INDIC_LANGS` | `mr,hi` | languages sent to the Indic backend (the rest go to the multilingual Whisper) |
| `SPEECH_ASR_MODEL` | `openai/whisper-large-v3` | Whisper for the Indic languages when `whisper` is chosen, and the IndicConformer fallback |
| `SPEECH_ASR_INDIC_CONFORMER_MODEL` / `_DECODER` / `_REVISION` | `ai4bharat/indic-conformer-600m-multilingual` / `ctc` / `2a77d30…` | IndicConformer repo, `ctc` or `rnnt`, and the reviewed commit it is pinned to (it runs remote code; assets from another commit are refused) |
| `SPEECH_ASR_MULTILINGUAL_MODEL` | `openai/whisper-large-v3-turbo` | English ASR and `auto` detection |
| `SPEECH_TTS_BACKEND` | `auto` | `llama` (GGUF in llama.cpp), `transformers`, `auto` (llama when available), or `indic_parler` (gated; Svara answers until it loads) |
| `SPEECH_TTS_PARLER_MODEL` / `SPEECH_TTS_PARLER_PYTHON` | `ai4bharat/indic-parler-tts` / empty | Parler repo; the python of its own venv (`scripts/make_parler_venv.sh`; empty = load in-process) |
| `SPEECH_TTS_PARLER_REVISION` | main | the evaluated Parler commit to pin |
| `SPEECH_TTS_PARLER_DESCRIPTION` | calm, clear, unhurried advisory | Parler caption; `{speaker}` becomes the language's recommended voice |
| `SPEECH_TTS_GGUF` / `SPEECH_LLAMA_SERVER_BIN` | `~/.cache/sajag/svara-gguf/svara-tts-v1-q8_0.gguf` / `~/llama.cpp/build/bin/llama-server` | llama.cpp backend files |
| `SPEECH_TTS_LLM_PORT` | `8202` | loopback port of the TTS llama-server the service starts |
| `SPEECH_TTS_MODEL` / `SPEECH_TTS_CODEC` | `kenpath/svara-tts-v1` / SNAC 24 kHz | TTS model (tokenizer) and codec |
| `SPEECH_TTS_STYLE_TAG` | `<clear>` | Svara end-of-utterance style |
| `SPEECH_TTS_CACHE_DIR` | `~/.cache/sajag/speech-tts` | advisory audio cache |
| `SPEECH_CITY_DIR` | `cities/$SAJAG_CITY` of the checkout (`SAJAG_CITY` defaults to `mumbai`) | landmarks.json (+ gazetteer.json) |
| `SPEECH_PLACE_THRESHOLD` | `0.80` | minimum `match_score` to assert a place |
| `SPEECH_IDLE_UNLOAD_S` | `600` | unload models after this many idle seconds |
| `SPEECH_MIN_FREE_GIB` | `8` | refuse a load that would leave less memory |
| `SPEECH_MAX_AUDIO_BYTES` / `SPEECH_MAX_AUDIO_SECONDS` | 8 MB / 60 s | upload limits |
| `SPEECH_DECK_ORIGINS` | empty | CORS origins (none: the deck proxies) |

## Tests

```bash
python -m pytest -q -p no:cacheprovider          # offline, models mocked
SPEECH_SLOW=1 python -m pytest -q -m slow         # real TTS → ASR round trip on the GPU
python eval/run_eval.py --help                     # the round-trip evaluation (synthetic + FLEURS real speech)
scripts/fetch_gated_models.sh check                # access to the gated models (downloads nothing)
```

## Limits

- **The field-report audio is synthetic.** No officer was recorded; the
  WER/CER above measure ASR on clean TTS speech, which is easier than a
  phone at a waterlogged junction in the rain (wind, traffic, engine noise,
  code-switching between Marathi, Hindi and English inside one sentence).
  The FLEURS clips are real people, but read general sentences in quiet
  rooms. A pilot needs a consented, recorded test set of real field reports.
- The evaluation is spoken by the advisory TTS itself. The two other voices
  per language and the FLEURS clips are there so the numbers do not rest on
  the house voices alone.
- Code-switched speech (a Marathi sentence with English road names, the way
  Mumbai speaks) is forced into one language; IndicConformer writes the
  English words in Devanagari, which the cross-script matcher handles for
  place names, not for every cue word.
- `lang=auto` asks Whisper turbo which language was spoken, and it mostly
  takes Marathi for Hindi: on the synthetic clips it named Marathi correctly
  in only 8 of 56 (48 as Hindi), Hindi in 52 of 52 and English in 51 of 52
  (`run_eval.py detect`). A Marathi clip heard as Hindi still goes to
  IndicConformer, but is decoded with its Hindi head. The deck sends the
  officer's chosen language (`?lang=`), so `auto` should stay the exception.
- IndicConformer reports no confidence (`null`); Whisper transcripts do.
- Places outside `landmarks.json` and the events stream's gazetteer are not
  found; `place_candidates` is there for the officer.
