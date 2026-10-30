# Embeddings, memory retrieval and PII detection (`services/embedding-service`)

Sajag uses one local embedding service (`127.0.0.1:8205`, `sajag-embed.service`) for three jobs:

- **Decision memory.** The brain asks "have we seen this situation before?" before it trusts a confident
  decider answer (the novelty latch and the tier-0 cache). It also records every served checkpoint.
- **SOP and advisory retrieval.** A Marathi, Hindi or English question should find the paragraph that answers it.
- **OSINT dedup.** Marathi, Hindi and English headlines about the same Mumbai event should cluster: "Andheri Subway shut after heavy rain", "मुसळधार पावसामुळे अंधेरी सबवे बंद" and "भारी बारिश के बाद अंधेरी सबवे बंद" are one event; "Milan Subway shut" the same hour is another.

On 28 Oct 2026 every open Perplexity model that could serve these jobs was evaluated on the GB10, against the
live set-up (bge-m3 dense recall followed by a pplx-embed-v2-late-0.6b MaxSim rerank). **What is deployed now:**

| Role | Model | Why |
|---|---|---|
| Late interaction (MaxSim rerank) | `perplexity-ai/pplx-embed-v2-late-0.6b`, fp32, unchanged | Best single model for memory; second-best for SOP. The brain's novelty (0.35) and tier-0 (0.75) floors are calibrated on its score scale. |
| Dense (ANN recall, `POST /embed`) | `perplexity-ai/pplx-embed-context-v1-4b`, bf16, cut to its first 1,024 values (Matryoshka) | Best SOP retriever by far. Ties on memory. Its dedup AUC equals bge-m3's, and its F1 at the OSINT pipeline's existing threshold is 0.86 against bge-m3's 0.26. It fits the existing `vector(1024)` column, so no migration. |
| PII spans (`POST /pii/spans`) | `perplexity-ai/PII-Tracer` | Defence in depth for the OSINT ethics layer (see the PII-Tracer section). |
| Fallback dense | bge-m3 (`EMBED_DENSE_MODEL=bge-m3`, then `scripts/reembed.py`) | The previous model, still registered |

## Candidates and licences

All the Perplexity models below are **MIT**; bge-m3 is MIT. **None of the cards list Marathi or Hindi explicitly**
(they say "multilingual"), so Indian-language quality has to be measured, not assumed.

| Model | Type | Width | Card says | Evaluated |
|---|---|---|---|---|
| `pplx-embed-v2-late-0.6b` (rev `7bba8e7`) | late interaction (ColBERT-style), text + images | 128 per token | multilingual | yes (live) |
| `pplx-embed-v2-late-9b` (rev `e6f9fd0`) | late interaction, same space as the 0.6b | 128 per token | multilingual | see below |
| `pplx-embed-v2-context-9b-preview` (rev `e2c06a7`) | contextual chunk embeddings, preview | 2048 (MRL 1024) | multilingual, "preview: may change" | see below |
| `pplx-embed-v1-0.6b` / `-4b` | dense | 1024 / 2560 (MRL) | multilingual | yes |
| `pplx-embed-context-v1-0.6b` / `-4b` | contextual dense (late chunking) | 1024 / 2560 (MRL) | multilingual | yes |
| bge-m3 (local snapshot) | dense | 1024 | 100+ languages | yes (live baseline) |

## The eval set (SYNTHETIC)

`services/embedding-service/eval/embed/build_eval_set.py` builds it from the repo's own material. It is
labelled SYNTHETIC: the situations and headlines are invented, no person is named and no real statistic is claimed.

**The results below were measured on 28 Oct 2026 on the set built from the Kolkata reference pack**
(`cities/kolkata/landmarks.json`), where the platform was first built. That set's Indian-language queries are in
Hindi and in the reference pack's own regional language, not Marathi. In the tables, **"ref. Indic"** marks that
regional language; the Hindi columns are Hindi. Hindi shares Devanagari with Marathi, so it is the closest
evidence for Marathi that exists today, but it is not a Marathi result.

**The Mumbai set** is built the same way from `cities/mumbai/landmarks.json`: Mumbai situations (waterlogging at
Hindmata and the subways, tree falls, visarjan crowds at Girgaon Chowpatty, station surges at CSMT and Dadar),
Marathi queries alongside Hindi, English and romanised ones, and the same hard negatives (same place, different
situation). Its results: not yet run (the reference set's results follow).

The reference set:

- **Memory.** 53 docs in the exact shapes the brain's decision-memory feeder and the incident ingestor write:
  `TRIGGER: …` state docs, incident summaries, scenario-run bodies and after-action notes. They cover 16
  situation families. There are 12 hard negatives (the same place, a different situation) and 6 distractors.
  52 queries: 23 English, 16 in the regional language, 7 Hindi and 6 romanised/code-mixed. A query hits when
  it ranks a doc of its own family. Some queries use a place's alternate or old name or no exact place string
  (in Mumbai the same test is VT for CSMT, शीव for Sion, वांद्रे for Bandra).
- **SOP and advisories.** 120 docs: every paragraph of 25 or more words in `docs/ai/*.md`; 18 citizen advisory
  pack strings in English, the regional language and Hindi (`strings.citizen*.ts`); and six advisory or
  proposal texts rendered from the hydro and forecast templates. 47 questions: 21 English, 14 in the regional
  language, 7 Hindi and 5 code-mixed, each with its gold paragraph(s).
- **OSINT.** 55 headlines in 32 events:
  - regional-language/English/Hindi/romanised versions of the same event;
  - 15 hard negatives: the same place with a different event, or the same kind of event at a different place;
  - one English cluster taken from the OSINT test fixtures (`dss_sg_highway.synthetic.json`).

  All 1,485 headline pairs are labelled same event or not.

Metrics: recall@1, recall@5 and MRR; for OSINT, ROC-AUC over pairs, the best-F1 threshold, F1 at the pipeline's
threshold and nearest-neighbour recall@1. Latency and memory come from one process per model on the shared GB10
(`torch.cuda.max_memory_allocated`), with batch-1 queries and batch-16 documents. Harness:
`eval_embed.py <model>`, then `report.py`. All tables are in `eval/embed/results/summary.md`.

## Results

### Single models (recall@1 / MRR), reference set

| Model | Memory | Memory, ref. Indic | SOP | SOP, ref. Indic | SOP, hi | SOP, mixed | OSINT AUC | OSINT best F1 (threshold) | F1 at 0.70 |
|---|---|---|---|---|---|---|---|---|---|
| bge-m3 (live dense) | 1.00 / 1.00 | 1.00 / 1.00 | 0.70 / 0.78 | 0.71 / 0.77 | 0.71 / 0.78 | 0.80 / 0.87 | **0.999** | **0.92** (0.82) | 0.26 |
| pplx-embed-v1-0.6b | 0.98 / 0.99 | 0.94 / 0.97 | 0.74 / 0.84 | 0.71 / 0.81 | 0.86 / 0.88 | 0.80 / 0.90 | 0.997 | 0.81 (0.46) | 0.50 |
| pplx-embed-v1-4b | 1.00 / 1.00 | 1.00 / 1.00 | 0.81 / 0.88 | 0.79 / 0.86 | 0.86 / 0.89 | 0.60 / 0.80 | 0.998 | 0.86 (0.64) | 0.80 |
| pplx-embed-v1-4b, MRL 1024 | 0.98 / 0.99 | 0.94 / 0.97 | 0.85 / 0.90 | 0.86 / 0.90 | 0.86 / 0.88 | 0.80 / 0.90 | 0.998 | 0.86 (0.66) | 0.83 |
| pplx-embed-context-v1-0.6b | 0.98 / 0.99 | 0.94 / 0.96 | 0.83 / 0.88 | 0.71 / 0.77 | 1.00 / 1.00 | 1.00 / 1.00 | 0.992 | 0.80 (0.62) | 0.72 |
| pplx-embed-context-v1-4b | 1.00 / 1.00 | 1.00 / 1.00 | **0.94 / 0.96** | **0.93 / 0.96** | 0.86 / 0.91 | 1.00 / 1.00 | 0.998 | 0.86 (0.64) | 0.82 |
| **pplx-embed-context-v1-4b, MRL 1024 (deployed)** | 0.96 / 0.98 | 0.94 / 0.96 | **0.94 / 0.96** | **0.93 / 0.96** | 0.86 / 0.91 | 1.00 / 1.00 | 0.997 | 0.88 (0.69) | **0.86** |
| pplx-embed-context-v1-4b, each paragraph alone | 1.00 / 1.00 | 1.00 / 1.00 | 0.87 / 0.92 | 0.93 / 0.94 | 0.86 / 0.89 | 0.60 / 0.80 | 0.998 | 0.86 (0.64) | 0.82 |
| pplx-embed-v2-late-0.6b (live, MaxSim) | 0.98 / 0.98 | 0.94 / 0.95 | 0.87 / 0.91 | 0.86 / 0.87 | 0.86 / 0.89 | 1.00 / 1.00 | 0.836 | 0.17 (0.89) | – |
| the same, 64-token cap as stored | 0.98 / 0.98 | 0.94 / 0.95 | 0.85 / 0.90 | 0.86 / 0.86 | 0.86 / 0.89 | 1.00 / 1.00 | 0.836 | – | – |

**The 9B models** were evaluated after the deploy, one at a time. Both weigh 31 GiB on disk and were deleted after
the eval.
- Their bf16 weights were streamed straight to the GPU, because the late-9B checkpoint is stored in fp32
  (31 GiB) and a CPU-side load would push the shared box toward its memguard floor.
- A watchdog would have killed the run below 10 GiB available; the lowest seen was 18 GiB.

| Model | Memory | Memory, ref. Indic | SOP | SOP, ref. Indic | SOP, hi | SOP, mixed | OSINT AUC |
|---|---|---|---|---|---|---|---|
| pplx-embed-v2-late-9b | 0.98 / 0.99 | 0.94 / 0.97 | 0.89 / 0.92 | 0.93 / 0.93 | 0.86 / 0.89 | 1.00 / 1.00 | 0.899 |
| the same, 64-token cap | 0.98 / 0.99 | 0.94 / 0.97 | 0.87 / 0.91 | 0.86 / 0.87 | 0.86 / 0.89 | 1.00 / 1.00 | 0.899 |
| 9B documents + 0.6B queries (same space) | 0.96 / 0.98 | 0.88 / 0.94 | 0.89 / 0.92 | 0.86 / 0.86 | 0.86 / 0.89 | 1.00 / 1.00 | 0.845 |

| Model | Memory | Memory, ref. Indic | SOP | SOP, ref. Indic | SOP, hi | SOP, mixed | OSINT AUC | OSINT best F1 (threshold) |
|---|---|---|---|---|---|---|---|---|
| pplx-embed-v2-context-9b-preview | 0.98 / 0.99 | 0.94 / 0.97 | **0.96 / 0.97** | 0.86 / 0.91 | 1.00 / 1.00 | 1.00 / 1.00 | 0.968 | 0.63 (0.79) |
| the same, MRL 1024 | 0.96 / 0.98 | 0.94 / 0.97 | 0.96 / 0.97 | 0.86 / 0.91 | 1.00 / 1.00 | 1.00 / 1.00 | 0.970 | 0.64 (0.84) |
| the same, each paragraph alone | 0.98 / 0.99 | 0.94 / 0.97 | 0.83 / 0.90 | 0.86 / 0.91 | 0.71 / 0.82 | 1.00 / 1.00 | 0.968 | 0.63 (0.79) |

### What `/search` returns (dense top-100 recall, then rerank on 64-token-capped late vectors), reference set

| Pipeline | Memory | Memory, ref. Indic | SOP | SOP, ref. Indic | SOP, hi | SOP, mixed |
|---|---|---|---|---|---|---|
| before: bge-m3 → MaxSim | 0.98 / 0.98 | 0.94 / 0.95 | 0.85 / 0.90 | 0.86 / 0.86 | 0.86 / 0.89 | 1.00 / 1.00 |
| **now, default (`rank: maxsim`): context-v1-4b → MaxSim** | same as before on corpora this small (recall@100 holds nearly every doc) | | | | | |
| **now, `rank: fused`: context-v1-4b + MaxSim, z-score fusion** | 0.98 / 0.99 | 0.94 / 0.96 | **0.94 / 0.95** | 0.86 / 0.87 | 0.86 / 0.89 | 1.00 / 1.00 |
| bge-m3 + MaxSim, fused | 1.00 / 1.00 | 1.00 / 1.00 | 0.83 / 0.88 | 0.86 / 0.86 | 0.86 / 0.88 | 0.80 / 0.90 |

### OSINT dedup: today versus now

The OSINT pipeline (`osint-analysis`, `HttpEmbedder`) calls `POST /embed`. The service had no such route, so
every OSINT run fell back to token Jaccard. The route exists now.

| | AUC (all pairs) | AUC, cross-script pairs | Nearest-neighbour recall@1 | F1 / precision / recall at the pipeline threshold |
|---|---|---|---|---|
| Token Jaccard (what ran until now) | 0.562 | 0.523 | 0.15 | 0.21 / 0.28 / 0.17 at 0.20 |
| bge-m3 via `/embed` | 0.999 | 1.000 | 0.97 | 0.26 / **0.15** / 1.00 at 0.70: it would over-merge (its best threshold is 0.82) |
| **context-v1-4b, MRL 1024, via `/embed` (deployed)** | 0.997 | 0.999 | 0.97 | **0.86 / 0.92 / 0.80** at 0.70 (its best threshold is 0.69) |

### Cost on the GB10 (shared; one process per model)

| Model | dtype | Load (s) | Weights (GiB) | Peak (GiB) | Query p50 / p95 (ms) | Per doc, batched (ms): memory / SOP |
|---|---|---|---|---|---|---|
| bge-m3 | fp32 | 4 | 2.1 | 2.4 | 13 / 17 | 5.5 / 6.7 |
| pplx-embed-v1-0.6b | bf16 | 3 | 1.1 | 1.3 | 18 / 19 | 3.6 / 8.9 |
| pplx-embed-v1-4b | bf16 | 6 | 7.6 | 8.0 | 53 / 58 | 13 / 35 |
| pplx-embed-context-v1-0.6b | bf16 | 18 | 1.1 | 1.7 | 13 / 14 | 6.8 / 16 |
| **pplx-embed-context-v1-4b** | bf16 | 27 | 7.6 | 8.8 | 48 / 59 | 20 / 56 |
| **pplx-embed-v2-late-0.6b** | fp32 | 17 | 2.2 | 3.2 | 17 / 19 | 6.8 / 11 |
| pplx-embed-v2-late-9b | bf16 | 22 | 15.6 | 17.9 | 113 / 297 | 61 / 88 |
| pplx-embed-v2-context-9b-preview | bf16 | 28 | 15.7 | 19.3 | 96 / 232 | 51 / 97 |
| PII-Tracer | bf16 | 7–12 | 1.1 | 1.2 | 28–45 per sentence | 15–27 per sentence |

Live, after the deploy:
- `POST /embed` takes 52 ms for one headline and 0.88 s for 64 (the OSINT client allows 3 s per request).
- `POST /search` takes about 0.14 s.
- `POST /pii/spans` takes 32 ms warm; the first call loads the model in 5.5 s.
- The service, with all three models loaded, reports 11.0 GiB of CUDA memory reserved (`/health` → `gpu`) plus
  0.5 GiB of process RSS. Before, its two models came to about 5.5 GiB.

## The choice, and why

1. **Keep `pplx-embed-v2-late-0.6b` for MaxSim.**
   - It ties for best on memory, is the best non-contextual model on SOP and handles the reference set's
     Indian-language queries well.
   - The brain's novelty and tier-0 floors are calibrated on its score scale (normalised MaxSim), so keeping it
     keeps those floors valid.
   - It is useless for headline dedup (AUC 0.84), so OSINT gets the dense model.
2. **Dense: switch to `pplx-embed-context-v1-4b`, cut to 1,024.**
   - **SOP:** it is the clear SOP winner (MRR 0.96 against 0.78 for bge-m3), and the context matters (0.92 when
     each paragraph is encoded alone).
   - **Memory:** it ties. At 1,024 dims two hard queries miss rank 1:
     - a romanised one ranks second, behind the same-place hard negative (knee-deep water at a crossing → a
       festival crowd at the same crossing; in Mumbai terms, "Hindmata la paani" against a Ganeshotsav crowd
       at Hindmata);
     - a regional-language query with no place name (knee-deep water on "the book-market street") ranks third.
       The live late model ranks it seventh.
   - **OSINT AUC:** it ties.
   - **OSINT threshold:** it works at the OSINT pipeline's existing 0.70 threshold (F1 0.86). bge-m3 would need
     that threshold re-tuned to about 0.82 to avoid over-merging.
   - **Storage:** the Matryoshka cut keeps the `vector(1024)` column and its HNSW index; no store migration.
   - **Cost:** about 7 GiB more than bge-m3, and 35 ms more per query. Both are well within the brain's 2 s
     search timeout and the box's budget: about 35–38 GiB stayed available after the deploy.
3. **Ranking stays MaxSim by default.**
   - The brain reads the best MaxSim among its top 5; a fused order could change which docs reach those 5, and
     with them its tier-0 keys.
   - Fusion is therefore opt-in per request (`{"rank": "fused"}`) for SOP/advisory callers, where it lifts SOP
     recall@1 from 0.85 to 0.94.
4. **Not the 9B late model.**
   - It gains 1–2 queries: SOP MRR 0.92 against 0.91; memory 0.99 against 0.98; regional-language SOP recall@1
     0.93 against 0.86 without the cap, but the same once the store's 64-token cap applies.
   - It costs 5.6 times the memory (17.9 against 3.2 GiB) and 6.6 times the query latency (113 against 17 ms).
   - Indexing with the 9B and querying with the 0.6B, which the shared space allows, gains nothing here.
   - Its weights were deleted after the eval; the registry still lists it.
5. **Not `pplx-embed-v2-context-9b-preview`.**
   - It has the best overall SOP MRR (0.97 against 0.96), but it is worse on regional-language SOP (0.91
     against 0.96).
   - It is much worse at headline dedup (AUC 0.968, best F1 0.63).
   - It needs 19.3 GiB.
   - It is a preview whose card warns that embeddings may change without compatibility.
   - Its weights were deleted after the eval.
6. **Add the read-only routes.**
   - `/embed`: OSINT dedup goes from token Jaccard (AUC 0.56, cross-script 0.52) to AUC 0.997.
   - `/pii/spans`: PII-Tracer, below.

## How it is built

- **Registry.** `config.py` lists `DENSE_MODELS` and `LATE_MODELS`, each with a pinned revision, dtype, width,
  store width and licence.
  - A model wider than the column is cut to its Matryoshka prefix and renormalised (`encoders.fit_dense`).
  - A width the store cannot hold is refused at startup with "a store migration is needed first".
- **Loading.** Models load lazily on a thread at startup (`EMBED_WARMUP`). A failed load is reported in
  `/health` and retried after 5 minutes, not on every request.
- **Markers.** Every stored doc carries `metadata.embedding = {"dense", "late"}`. Recall only compares vectors of
  the configured dense model, and unmarked legacy docs count as bge-m3.
  - `scripts/reembed.py` rewrites the vectors and markers of stale docs in place; ids and text are untouched.
  - The live corpus was empty at the switch, so nothing needed re-embedding.
- **Fallbacks.**
  - **Dense model down:** writes keep their MaxSim vectors (dense filled later by `reembed.py`); `/search`
    recalls the newest docs and MaxSim ranks them (`"recall": "recent"`); `/embed` answers 503, so OSINT falls
    back to its lexical rule.
  - **Configured fallback:** `EMBED_DENSE_MODEL=bge-m3`, then a re-embed.
- **Bug fixed on the way.** asyncpg returns `jsonb` as text, so `/search` used to return `metadata: {}` for
  every hit. It now parses it.
- **Entrypoint.** `python -m embedding_service` now works: the pool and encoders are created on the serving loop
  (`service.build_lazy_app`). `models-config/embedding_launcher.py` calls the same function.

## PII-Tracer (parse-time PII check, defence in depth)

`POST /pii/spans` runs `perplexity-ai/PII-Tracer` (MIT; a ~600M bidirectional Qwen3 encoder with BIOES tags and
Viterbi decoding). It returns `{"spans": [[{start, end, label, score}]], "model", "labels"}`.

- **Labels.** The default labels are `private_person`, `private_email` and `private_phone`.
- **Only adds.** The model only ADDS redactions. The OSINT rules stay primary, and the ingress uses the model only
  with `OSINT_PII_MODEL=1`, which is off by default and fails open to the rules.
- **The integration** lives in the OSINT ingress
  (`services/osint-ingress/src/osint_ingress/connectors/_model_pii.py`), off by default.
- **Pinning.**
  - The revision is pinned (`d25c16f`), and the SHA-256 of its reviewed `modeling_pii_masking.py` is pinned
    because it runs as `trust_remote_code`.
  - It loads offline (`local_files_only`).
- **Post-processing** (`embedding_service/pii.py`):
  - spans are widened to whole words, because byte-level BPE cuts Devanagari and other Indic names mid-word;
  - plates are relabelled `vehicle_plate` (they are masked by their own rule);
  - short public numbers (112, 108) are dropped;
  - a toponym guard clips every span off protected places: `landmarks.json`, a short list of eponymous places,
    and name runs ending in a road word (Road/Marg/Chowk/Path/Setu/Park/… and रोड/मार्ग/चौक/पथ/सेतू/…).
    Mumbai needs this badly: many of its roads and stations carry a person's name (Dr Ambedkar Road, Senapati
    Bapat Marg, Annie Besant Road, Lokmanya Tilak Terminus, Chhatrapati Shivaji Maharaj Terminus, Acharya Atre
    Chowk), and none of them may be redacted as a person.
- **SYNTHETIC eval on the Kolkata reference pack** (120 sentences, `services/embedding-service/eval/pii/`):
  - With the guard, person P/R/F1 is 0.85/0.82/0.83 (English 0.93, Hindi 1.00, the regional language romanised
    0.76 and in its own script 0.73), and 0 of 122 place mentions are redacted.
  - Without the eponymous list, 4 of 122 are redacted; with no guard at all, 61 of 122 (eponymous road names).
  - A Mumbai sentence set (eponymous Mumbai roads and stations, Marathi script): not yet run.
  - Added to the news-tier rules, person recall rises from 0.84 to 0.94, with no protected place, office title
    or emergency number newly redacted.
- **Live check (reference pack).** A sentence with a private person's name beside two eponymous road names →
  only the name is flagged; the same sentence in the regional script → only the name is flagged.
- **Limits.**
  - Regional-script recall on the reference set is about 0.75, and Marathi script is not yet measured, so the
    `[WITHHELD]` rule for unknown Indic words stays.
  - The model sometimes tags ages as persons.
  - Single given names in posts are still missed.
- **Side finding** for the owner of the ethics rules: on the reference set, today's rules redact 10 of 44
  English eponymous place mentions, because a surname or title inside a road name looks like a person. The same
  risk applies to Mumbai's eponymous roads and stations ("Dr Ambedkar Road", "Lokmanya Tilak Terminus"); it is
  to be checked on the Mumbai set.

## Limits

- **Small and synthetic.** The set is small (52 + 47 queries, 1,485 headline pairs) and written for this eval.
  - Differences of one or two queries (0.02–0.04) are within noise.
  - The memory task sits near the ceiling for every model, so it shows that none of them regresses on memory,
    not which is best.
  - It was built from the Kolkata reference pack. Real Mumbai situations and real Mumbai news, in Marathi,
    will be harder.
- **Recall at scale was not measured.** The corpora are small enough that dense recall@100 holds almost every
  doc. How much the dense model matters when the decision memory grows to thousands of near-duplicate
  checkpoints is not measured.
- **The 64-token cap** on stored late vectors (a `traffic.memory_docs` CHECK) costs about 0.01 MRR on long SOP
  paragraphs. Lifting it needs a store migration.
- **Marathi** is not listed on any Perplexity model card, and no Marathi query has been measured yet. Hindi
  (same script) is the nearest evidence; the Mumbai set's Marathi queries are the real test, and a native reader
  should still review real queries.
- **Slow kernels.** The Qwen3.5-based late and decider models log a slow PyTorch fallback for their
  linear-attention kernels (`flash-linear-attention` / `causal_conv1d` are not installed in the shared models
  venv). The latencies above include it.
