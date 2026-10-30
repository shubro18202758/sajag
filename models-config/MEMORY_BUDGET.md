# Sajag Model Stack — Resident Memory Budget (GB10 unified pool)

Owner: models stream. Source of truth for "what may be resident and how much
it costs". Update the **Measured** column whenever a host or quantization
changes; `/decider/health` (`resident_rss_gib`, `cuda_reserved_gib`),
`/proc/<pid>/status` (VmRSS/VmHWM), and `/proc/meminfo` are the measurement
interfaces.

## Pool

| Item | Value | Source |
|---|---|---|
| Total unified memory | **121.63 GiB** (MemTotal 127,533,976 kB; the configs plan with a conservative 121.44 GiB pool) | `/proc/meminfo` — nvidia-smi reports `memory.total` as **N/A** on GB10, so /proc/meminfo is the only source |
| Eviction policy | **none** — every host is resident forever (keep_alive semantics below) | perfPlan |
| Disk | 2,248 GiB free of 3,754 GiB | `df -BG /` (model manifest) |

## Resident processes

| # | Resident process | Weights | Process budget (planned) | Measured (this session, 2026-10-12) |
|---|---|---|---|---|
| 1 | model-host: pplx-decider-v1-27b BF16 (11 shards, 52,170,802,640 B + 2.6 MB readout) | 48.58 GiB | 55 GiB (weights + ≤8k-state activations — estimate) | **measured 2026-10-12**: `cuda_reserved_gib` **48.99**, VmRSS 1.66 / VmHWM 5.92 GiB (weights migrate to the GPU side of the pool), cold load ≈5 min, warm decide **460–477 ms @ 138-token state / 1 question** (3 probes; first-ever call pays ≈4.7 s CUDA warmup — keep warmup in smoke), 19 decides / 0 failed |
| 2 | llama-server: sajag-tactical Gemma 4 12B Q4_K_M (GGUF 7,208,382 KiB), `-c 16384 -np 2` (2 slots × 8192) | 6.87 GiB | 9.5 GiB (weights + KV/compute for 2×8192) | **VmHWM 7,602,840 kB = 7.25 GiB** peak after first completion (llama.cpp migrates weights into the GPU side of the pool; idle VmRSS reads far lower) |
| 3 | embedding-service: pplx-embed-v2-late-0.6b fp32 (multivector MaxSim) | 2.22 GiB | 3.5 GiB incl. torch CUDA ctx | **measured 2026-10-28** (eval process): peak 3.16 GiB, load 17 s, query p50 17 ms |
| 4 | embedding-service: pplx-embed-context-v1-4b bf16 (dense ANN, 2,560-d cut to 1,024, unit-norm) — fallback bge-m3 (2.4 GiB) | 7.55 GiB | 9.5 GiB | **measured 2026-10-28**: peak 8.75 GiB, load 27 s, query p50 48 ms; live service (late + dense + PII loaded) 11.0 GiB CUDA reserved + 0.5 GiB RSS (`/health` → `gpu`); PII-Tracer (1.1 GiB) loads on the first `/pii/spans`. Eval: `docs/ai/embeddings.md` |
| 5 | traffic-oracle: DSTGAT ONNX (CPU fallback kept) | — | 0.4 GiB | unchanged from v1 budget |
| | **MODEL SUBTOTAL** | | **≈78 GiB (64 %)** | |
| | PostGIS 2.0 + Valkey 0.5 + NATS 0.5 + traffic-oracle 3.5 (MEMORY_GUARD_MB=3500) + convoy-brain 1.5 + browser/dev 4 | | ≈12 GiB | |
| | **TOTAL PLANNED** | | **≈90 GiB → ≈31 GiB (26 %) headroom** (shared with the speech, vision and forecast services, which load lazily) | |

Optional 9B aux embedder (pplx-embed-v2-late-9b, 16.79 GB) stays OFF by
default (`sajag_models.yaml → embeddings.aux_9b.enabled: false`); enabling it
still fits at ≈23 GiB spare.

## Live measurement, 29 Oct 2026 (after the v1.2 switch and the llama.cpp c3df4b7 update)

| Host | Model | GPU memory | Residency |
|---|---|---|---|
| model-host :8083 | pplx-decider-v1.2 BF16 (protocol v3 joint) | `cuda_reserved_gib` **48.71** (was 50.43 for v1-27b) | always |
| llama-server :8084 | Gemma 4 12B Q4_K_M, llama.cpp c3df4b7 | 8.6 GiB | always |
| embedding-service :8205 | context-v1-4b + v2-late-0.6b + PII-Tracer | 12.0 GiB reserved, 11.0 allocated | always |
| vision llama-server :8201 | Qwen3-VL-8B Q4_K_M + F16 projector | ≈ 7.6 GiB | lazy; starts only with ≥ 8 GiB left after it (the box's memory guard acts at 6 GiB), stops after 10 idle minutes |
| speech :8194 (+ TTS llama-server :8202) | Whisper-medium (Marathi) fp16; Svara-TTS Q8_0 GGUF | ≈ 2 GiB; ≈ 5 GiB | lazy |
| forecast :8195 | Chronos-2 | 0.5 GiB, 1.6 GiB peak | lazy |

MemAvailable with the three always-resident hosts loaded and everything lazy unloaded: 33–36 GiB. The vision model
had been refused at a 12 GiB floor (18.3 GiB available when the decider was v1-27b and other work was running);
at the 8 GiB floor it starts and leaves ≥ 8 GiB.

## Not counted in the planned set

- **ollama :11434** runs externally (not ours, never restarted by us) and
  currently hosts `qwen3.5:9b-q4_K_M` (6.6 GB) plus our debug side-load
  `gemma-sajag:12b` (7.4 GB, `models-config/Modelfile.gemma_sajag`). If the ollama
  daemon loads either on this machine, subtract its runner RSS from headroom.
- The `sajag-*` throwaway migration-test containers other streams create are
  transient.

## keep_alive / residency semantics (per host)

| Host | Mechanism |
|---|---|
| model-host :8083 | Loads once at boot (≈285 s cold; ~5 min observed this session) into a supervised process; no eviction path exists; restart-on-exit via `serve_models.sh` |
| llama-server :8084 | llama.cpp has **no model eviction** — residency == process lifetime; supervised restart-on-exit. 2 parallel slots (`-np 2`), 8192 ctx per slot (`-c 16384` total) |
| embedding-service :8205 | Encoders resident in the service process (embeddings stream); supervised restart-on-exit |
| ollama :11434 (debug side-load only) | `OLLAMA_KEEP_ALIVE=-1` required so `gemma-sajag:12b` is never evicted (recorded in `sajag_models.yaml → ollama`) |

The v1 asyncio.Lock VRAM-serialization regime is retired: compute-only
serialization replaces it (decider compute lock + queue 8 in model-host,
llama-server slot scheduling, embedder batch lock in the embeddings service).

## Context budgets

- Decider state docs: ≤400 tokens/event, ≤1500 pre-movement, **hard cap 8192**
  (model-host rejects larger with HTTP 413; the autojev `prepare()` raises —
  no truncation by design). Bidirectional attention → no KV/prefix reuse;
  prefix caching is useless and not attempted.
- Gemma: 8192/slot × 2 slots = 16,384 tokens total KV. Tool results truncated
  4 KB; 200-segment agent caps unchanged.
- Decider checkpoints are event-driven with ≥5 s spacing (never per-GPS-tick);
  ≤6 typed questions batched into a single POST /decide.

## Known gaps / measurement obligations

- Decider activation overhead is an ESTIMATE until `/decider/health` RSS is
  read under production-size (1500-token) states — re-budget row 1 from
  measurement (risk register item #1).
- Gemma tok/s on GB10 and json_schema support in llama build 69bf643 are
  smoke-measured by `scripts/smoke_models.sh` + `/metrics`; not yet recorded
  as steady-state numbers.
- Unified-memory bandwidth contention (27B forward concurrent with Gemma
  generation and embedder batches) is unmeasured; event-driven decider
  cadence and embedder batch windows are the designed mitigations.
