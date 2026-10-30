# Sajag — sample data and tests

This page lists the data Sajag ships with for Mumbai, the sample files in [`samples/`](samples/), every test suite
with the command that runs it and its total, and 48 representative test cases with what each one proves.

It describes the repository with the **Mumbai City Pack** (`cities/mumbai/`), the five AI services and the
platform services. The Kolkata pack the platform was first built on stays in `cities/kolkata/` as a second,
reference City Pack. Totals change as the code grows; the commands below reproduce them.

---

## Contents

- [Part 1 — Sample data](#part-1--sample-data)
  - [1.1 At a glance](#11-at-a-glance)
  - [1.2 The City Pack: `cities/mumbai/`](#12-the-city-pack-citiesmumbai)
  - [1.3 Files generated from the City Pack](#13-files-generated-from-the-city-pack)
  - [1.4 The scenario library](#14-the-scenario-library)
  - [1.5 Waterlogging data](#15-waterlogging-data)
  - [1.6 Speech and vision evaluation sets](#16-speech-and-vision-evaluation-sets)
  - [1.7 The impact model](#17-the-impact-model)
  - [1.8 The `samples/` folder](#18-the-samples-folder)
- [Part 2 — Tests](#part-2--tests)
  - [2.1 How the gates fit together](#21-how-the-gates-fit-together)
  - [2.2 Totals](#22-totals)
  - [2.3 Python suites](#23-python-suites)
  - [2.4 The Rust suite](#24-the-rust-suite)
  - [2.5 The command deck](#25-the-command-deck)
  - [2.6 The City Pack check](#26-the-city-pack-check)
  - [2.7 The offline acceptance ladder](#27-the-offline-acceptance-ladder)
  - [2.8 Running tests safely](#28-running-tests-safely)
- [Part 3 — Representative test cases](#part-3--representative-test-cases)
- [Part 4 — Known gaps](#part-4--known-gaps)

---

# Part 1 — Sample data

## 1.1 At a glance

| Data | Where | What it is | Label |
|---|---|---|---|
| City facts | `cities/mumbai/city.json` | Names in English, Marathi and Hindi; bbox; centre; plate format; emergency numbers (112, 100, 108, 101 and the BMC's 1916); 18 agencies; hydrology notes; population (Census 2011) | Sourced |
| Canonical place names | `cities/mumbai/landmarks.json` | 55 landmarks (junctions, stations, subways, pumping stations, hospitals, venues, agencies) with ids, positions and names in English, Marathi and Hindi | Sourced (OpenStreetMap and city knowledge) |
| Curated corridors | `cities/mumbai/corridors.json` | The road corridors the network is cut from, junction seeds and name aliases | Curated |
| OpenStreetMap extracts | `cities/mumbai/osm/` | Overpass extracts for the city, the airport approach and the stations | © OpenStreetMap contributors, ODbL |
| Road network | `cities/mumbai/network.json` | 72 junctions, 86 segments (202 km), signal programs, camera sites and stations | Roads real; signal programs and camera sites MODELLED |
| Store seed | `services/corridor-store/seed/*.sql` | The generated network seed and its derivations | Generated |
| Scenario library | `scripts/scenario_library.json` | The scenarios the emulator and the twin replay on the Mumbai network (§1.4) | SIMULATED |
| Waterlogging hotspots | `services/hydro/src/hydro/data/hotspots.json` | Reported waterlogging places, each with its news or official sources | Sourced |
| Susceptibility | `services/hydro/src/hydro/data/susceptibility.json` | Per-segment terrain and drainage score from Copernicus DEM, OSM drains and the hotspots | MODELLED |
| Speech evaluation | `services/speech/eval/` | 40 short Mumbai field-report phrases in Marathi, Hindi and English | Synthetic audio |
| Vision evaluation | `services/vision/tests/fixtures/`, `services/vision/eval/` | 12 credited public photos, 10 of them from Mumbai (faces and legible plates pixelated), with expected road states; results | Real model |
| Impact model | `IMPACT_REPORT.md`, `scripts/impact_results.json` | Rolling holds against a blanket freeze, central and bounding cases | MODELLED |
| API samples | [`samples/`](samples/) | 7 Mumbai captures and 12 files from the Kolkata reference pack | Each states its provenance |
| Reference City Pack | `cities/kolkata/` | The pack the platform was first built on, kept as a second pack (§1.3) | Reference |

## 1.2 The City Pack: `cities/mumbai/`

A city is a folder. Everything specific to Mumbai lives in it, and every other city-dependent file is generated from
it (§1.3).

| File | Contents |
|---|---|
| `city.json` (schema `sajag.city/1`) | `name` and `region` in `en`/`mr`/`hi`; `state` (Maharashtra, code `MH`); timezone India Standard Time; centre (Dadar / Matunga); bbox 18.89–19.28 N, 72.77–72.99 E, and a core box for the Island City and the inner suburbs; UI languages `en`, `mr`, `hi`, English the default on public and console pages; the plate format `MH NN X[X] NNNN` and its regular expression; emergency numbers 112, 100, 108 (ambulance), 101 (fire) and 1916 (BMC disaster control); 18 agencies, from Mumbai Traffic Police and the BMC to BEST, Central and Western Railway and the Mumbai Port Authority; hydrology: the Arabian Sea, the Mithi, the Apollo Bunder tide (MODELLED) and the BMC storm-water pumping stations (EMULATED); population: Greater Mumbai 1.24 crore and the urban agglomeration 1.84 crore (Census 2011) |
| `landmarks.json` | The canonical place ids every service uses: junctions and flood spots (`hindmata`, `dadar_tt`, `kings_circle`, `sion_circle`, `kalanagar`, `worli_naka`, `haji_ali`, `bkc`), subways (`milan_subway`, `andheri_subway`), stations (`csmt`, `churchgate`, `dadar`, `kurla`, `andheri`, `ltt`), the airport (`airport_t1`, `airport_t2`), bridges (`sea_link`, `atal_setu`), venues (`wankhede`, `girgaon_chowpatty`, `shivaji_park`, `juhu_beach`), pandals (`lalbaugcha_raja`), hospitals (`kem`, `sion_hospital`, `jj_hospital`, `nair_hospital`, `cooper_hospital`), the six major pumping stations (`haji_ali_ps`, `irla_ps`, `love_grove_ps`, `cleveland_bunder_ps`, `britannia_ps`, `gazdarbandh_ps`), `mithi_kurla`, `apollo_bunder` and the agencies (`mantralaya`, `bmc_hq`, `police_hq`, `traffic_hq`), each with names in English, Marathi and Hindi |
| `corridors.json` | The curated corridors: Marine Drive and the Coastal Road, the Bandra–Worli Sea Link, the Western and Eastern Express Highways, SV Road, the Milan Subway road and Gokhale Bridge, the Andheri Subway approach, Andheri–Kurla Road, JVLR, LBS Marg, SCLR and the BKC roads, the Sion–Panvel Highway, the Eastern Freeway, P D'Mello Road, Dr Ambedkar Road (Hindmata – Dadar TT – King's Circle) and Senapati Bapat Marg, among others |
| `network.json` (schema `sajag.network/1`) | The compact network generated from the corridors and the OSM extracts |
| `osm/` | The committed Overpass extracts (ODbL) |

The plate rule in `city.json` notes that MH-01, MH-02, MH-03 and MH-47 are commonly listed for Mumbai's transport
offices, and that Sajag never infers an office from a code.

## 1.3 Files generated from the City Pack

`python3 scripts/city_build.py mumbai` regenerates, deterministically and offline:

| Generated file | Reader |
|---|---|
| `services/corridor-store/seed/sample_corridor.sql` | A fresh store |
| `services/corridor-store/seed/reanchor_osm_network.sql` | The bring-up's network step (idempotent, one transaction) |
| `services/corridor-store/seed/display_geometry_osm.sql` | The display geometry |
| `scripts/data/osm_network.json`, `scripts/data/osm_network_map.json` | The evidence and the resolved table |
| `cities/mumbai/network.json` | The twin, the forecast and hydro services, the deck's city module |
| the segment table under `services/signal-ingress/src/feeds/` | The Rust ingress (compiled in) |
| `services/traffic-oracle/src/traffic_oracle/simulation/use_case_scenarios.json` | The oracle's twin |
| `scripts/scenario_library.json` | The scenario library |

`python3 scripts/city_build.py mumbai --check` rebuilds into a temporary folder and compares; it prints
`[mumbai] OK: every derived file is current` when nothing differs. The Kolkata reference pack is kept in `cities/`,
and a test builds a second city from its own folder (case T-41 below), which shows the data layer is portable: a
city is moved by writing its pack, not by editing services.

## 1.4 The scenario library

`scripts/scenario_library.json` (format `sajag/scenario-library/1`) holds the Mumbai scenarios on the Mumbai
network. Each names its route segments, departure time, protection class, closure policy, weather, forced events
and the features it is expected to show. The event emulator replays them through the real APIs, and the oracle's
twin runs them. Every one is SIMULATED: a scenario, not a recorded event. The Mumbai situations the library is
built to cover come from the city's own record:

| Situation | Kind | Why it matters in Mumbai |
|---|---|---|
| Cloudburst at high tide | emergency evacuation | A heavy burst at a high tide of about 4.5 m closes the sea outfalls; Hindmata, Milan Subway, Andheri Subway, King's Circle, Sion and Kurla flood (BMC chief engineer, Free Press Journal, 2025) |
| Anant Chaturdashi visarjan night | mass gathering | Processions from Lalbaug to Girgaon Chowpatty, with restrictions on 53 roads in 2024 (The Statesman) and an emergency corridor kept open |
| Wankhede match-night egress | egress surge | Crowds onto Marine Drive, Churchgate and Marine Lines |
| Locals stop, station surge | egress surge | When tracks flood at Sion and Kurla, riders pour onto the forecourts at CSMT, Dadar, Kurla and Andheri |
| Protected movement, Mantralaya to Mumbai Airport T2 | protected movement | Rolling holds, never a blanket freeze (§1.7) |
| Mumbai Marathon | race | January route closures from CSMT along Marine Drive and over the Sea Link |
| New Year on Marine Drive | mass gathering | A night crowd on the seafront |
| Arterial crash, ambulance window | emergency evacuation | A green corridor to KEM or Sion hospital for an ambulance (108) |

Two scenario samples from the Kolkata reference pack are in
[`samples/kolkata-reference/corridor/`](samples/kolkata-reference/corridor/); the Mumbai ones are pending
([`samples/README.md`](samples/README.md)).

## 1.5 Waterlogging data

- **Hotspots** (`hotspots.json`): reported waterlogging places, each with its news or official sources. Mumbai's
  recur in reporting: Hindmata (Dadar East), Dadar TT, King's Circle, Sion, Gandhi Market, Wadala, Kurla (Kranti
  Nagar by the Mithi), Chembur, Andheri Subway, Milan Subway, Vile Parle, Parel and Byculla. The BMC itself counts
  hundreds of known flooding spots (386–498 by year, Free Press Journal).
- **Susceptibility** (`susceptibility.json`): built by `services/hydro/scripts/build_susceptibility.py` from the
  Copernicus DEM GLO-30 tile, OSM waterways and the hotspots. MODELLED.
- **Pumping stations**: the six major BMC storm-water pumping stations (Haji Ali, Irla, Love Grove, Cleveland
  Bunder, Britannia, Gazdarbandh) are real names and places; their pump states are EMULATED.
- **The storm replay** (18–19 August 2025): the IMD totals it is anchored to are in the replay code with their
  sources; see [`ai/hydro.md`](ai/hydro.md). with the rain gauges' observed totals, the model flagged 9 of the 12 places reported flooded on its network (King's Circle, Andheri Subway, Gandhi Market, Byculla, Dadar TT, Vile Parle, Hindmata, Chembur, Kurla by the Mithi) and missed Sion, Khar and Goregaon. Its own flag came after the first news report at most places (median 51 minutes late: the bucket model fills slowly); with the observed rain as a perfect 2-hour nowcast (hindsight) it would have led the first report at 8 of the 9 (median 69 minutes). The Open-Meteo archive carried a third of the gauges' rain and flagged nothing, which is the case for a live rain-gauge feed. A second replay, 26 May 2025, flagged 5 of 15 reported places.

## 1.6 Speech and vision evaluation sets

- **Speech** (`services/speech/eval/phrases.json`): 40 short Mumbai field-report phrases (14 in Marathi, 13 in
  Hindi, 13 in English), written in the words a traffic officer or BMC field worker would use, each with its
  expected place (a `landmarks.json` id) and kind. The audio is synthesized with Indic Parler-TTS; nobody was
  recorded. `services/speech/eval/run_eval.py` writes the results to `services/speech/eval/results.json`.
- **Vision** (`services/vision/tests/fixtures/`): 12 public photos from Wikimedia Commons, 10 of them from Mumbai
  (JVPD and an arterial under monsoon water, BEST buses in the 2005 flood, an evening queue near CSMT, a fallen
  banyan on Old Prabhadevi Road after Cyclone Tauktae, the Western Express Highway, Amar Mahal), with `labels.json`
  and `NOTICE.md` (credits and licences). Results, refusal probes in English, Marathi and Hindi, and the
  output-filter demonstration are in `services/vision/eval/results.json`: 11 of 12 road states right and 11 of 11
  probes passed on 30 Oct 2026.

## 1.7 The impact model

`scripts/impact_run.py` compares a blanket junction freeze with rolling holds on the City Pack's network (run it
with `SAJAG_CITY=mumbai`). It is deterministic: `SAJAG_CITY=mumbai python3 scripts/impact_run.py --offline`
regenerates `IMPACT_REPORT.md` and `scripts/impact_results.json` from the committed network. Every figure is
**MODELLED**, and the assumptions table lists each constant with its source or the word "assumption". The central
case for the protected-movement corridor (Mantralaya to Mumbai Airport T2, 10 junctions):
192,820 commuter-minutes of delay per movement with a 25-minute freeze,
1,928 with 2.5-minute rolling holds.

## 1.8 The `samples/` folder

[`samples/README.md`](samples/README.md) lists two sets. **Mumbai** (made on 30 Oct 2026): a typed Marathi field
report matched to Hindmata, three vision policy refusals (a plate question and a person question in English and
Marathi), the vision evaluation on the Mumbai stills, a Chronos-2 forecast with a diversion proposal on Saki Vihar
Road, a twin signal proposal and the Webster / max-pressure baselines at Hindmata on the Mumbai network, and an
excerpt of that network. **Kolkata reference** (made on 28 Oct 2026 on the
reference pack, in [`samples/kolkata-reference/`](samples/kolkata-reference/)): the waterlogging nowcast, tide,
pumps and a storm replay; a Chronos-2 forecast; a twin proposal and the Webster / max-pressure baselines; a camera
road-state answer; a constructed OSINT situation row; two scenarios; and a City Pack network excerpt. Each file
states how it was made; the reference files say they are not Mumbai captures, and the Mumbai versions are listed
as pending.

To regenerate the run-locally samples on Mumbai (each service on a loopback development port of your choice; stop
each process when you are done):

```bash
# speech: a typed report needs no model (no CUDA context, no peers asked to release memory)
cd services/speech
PYTHONPATH=src SPEECH_PORT=9161 SPEECH_CITY_DIR=../../cities/mumbai SPEECH_DEVICE=cpu \
  SPEECH_CUDA_CONTEXT_AT_START=false SPEECH_MAKE_ROOM=false python -m speech_service &
curl -s -X POST -H 'Content-Type: application/json' \
  -d '{"text":"हिंदमाता येथे गुडघाभर पाणी साचले आहे, बस अडकल्या आहेत"}' '127.0.0.1:9161/speech/report?lang=mr'

# vision: the policy screen answers before any model is called
cd services/vision
PYTHONPATH=src VISION_PORT=9163 VISION_LLM_MANAGE=false VISION_LLM_URL=http://127.0.0.1:9 python -m vision_service &
curl -s -X POST -H 'Content-Type: image/jpeg' --data-binary @tests/fixtures/jam_csmt.jpg \
  '127.0.0.1:9163/vision/road-state?question=who%20is%20in%20this%20image'

# twin (CPU): a proposal for Hindmata at the evening peak
cd services/twin
SAJAG_TWIN_PORT=9171 SAJAG_TWIN_NETWORK=../../cities/mumbai/network.json \
  SAJAG_TWIN_ORACLE_URL= SAJAG_TWIN_LLM=0 PYTHONPATH=src python -m sajag_twin &
curl -s -X POST 127.0.0.1:9171/twin/propose -H 'content-type: application/json' \
  -d '{"junction_ids":["hindmata"],"horizon_min":45,"start":"18:00"}'

# hydro (CPU; calls Open-Meteo, no key; SAJAG_HYDRO_OFFLINE=1 makes no outbound call)
cd services/hydro
PYTHONPATH=src PORT=9152 SAJAG_HYDRO_CITY_DIR=../../cities/mumbai python -m hydro &
curl -s 127.0.0.1:9152/hydro/nowcast
curl -s 127.0.0.1:9152/hydro/tide?hours=24

# forecast (Chronos-2 weights in the Hugging Face cache; GPU)
cd services/forecast
HF_HUB_OFFLINE=1 PYTHONPATH=src PORT=9151 SAJAG_FORECAST_DATA_SOURCE=synthetic \
  SAJAG_FORECAST_CITY_DIR=../../cities/mumbai python -m forecast &
curl -s '127.0.0.1:9151/forecast/segments?horizon_min=120'
```

The twin's junction ids are the network's junction keys (landmark ids where the junction is a landmark); the
storm replay takes the event id the hydro service lists in its `/hydro/replay` documentation
([`ai/hydro.md`](ai/hydro.md)).

---

# Part 2 — Tests

## 2.1 How the gates fit together

| Layer | What it checks | Where |
|---|---|---|
| Python unit and API suites | Every service's logic and its HTTP contract, offline (models and outbound calls mocked) | `services/*/tests/` |
| Real-model tests | The AI services against their real weights (opt-in markers) | `-m model` (forecast), `-m slow` (speech, vision) |
| Rust suite | The ingress pipeline and its plausibility checks | `services/signal-ingress` |
| Deck type check | `svelte-check` with errors as failures | `services/command-deck` |
| Deck lints | Design tokens (contrast, spacing, colour use), English copy, Marathi script | `tests/design-tokens.mjs`, `tests/copy-lint.mjs`, `tests/mr-script.unit.mjs` |
| Deck unit suites | `tests/*.unit.mjs`: masking, the gate, Decide, Home, Map, Plan, public pages, the city module | `services/command-deck/tests/` |
| Contract replay | The deck's typed client against recorded backend answers | `tests/contract/run.mjs` |
| Proxy guard | The deck's loopback proxy rules | `tests/test_deck_proxy_guard.py` |
| Compose | The compose files render | `docker compose ... config -q` |
| City Pack | Every generated file is current | `scripts/city_build.py mumbai --check` |
| Browser smokes | Screens in a headless browser against a running stack | `tests/*-smoke.mjs` |
| Acceptance ladder | All of the above in order, offline or against a live stack | `scripts/verify_all.sh` |

## 2.2 Totals

Every suite is run once, offline, in parallel, on the merged tree.

| Suite | Notes |
|---|---|
| traffic-oracle | Some tests skip themselves: they need a database sandbox |
| convoy-brain | |
| corridor-store | Some tests skip themselves: they need a database sandbox |
| event-emulator | |
| embedding-service | |
| forecast | 2 real-model tests deselected (`-m model`) |
| hydro | Open-Meteo mocked |
| speech | real-model tests skipped |
| vision | real-model tests skipped |
| twin | |
| cityfeeds | every outside source mocked or replayed from a recording |
| osint-common, osint-ingress, osint-geo, osint-analysis | |
| deck proxy guard (pytest) | |

| Total | Result |
|---|---|
| **Python** (all suites above) | **6,443** passed |
| signal-ingress (cargo) | 121 passed |
| deck unit suites | 46 |
| deck lints | design tokens, copy (4,939 English strings), Marathi script: all pass |
| `svelte-check` | 0 errors (1,040 files) |
| OSINT offline smoke | PASS |
| contract replay | PASS, 0 failures |
| **Gates** | **69** green |

## 2.3 Python suites

Each Python service carries its own `tests/` folder and runs offline. From the repository root:

```bash
cd services/<service> && python -m pytest -q -p no:cacheprovider
```

Use a Python 3.12 environment with the service's dependencies (each service has a `pyproject.toml` or
`requirements.txt`, and a Dockerfile under `infra/docker/`). The AI services also have real-model tests:

```bash
cd services/forecast && python -m pytest -q -p no:cacheprovider -m model   # Chronos-2 and TimesFM in the HF cache
cd services/vision   && VISION_SLOW=1 python -m pytest -q -m slow           # Qwen3-VL via llama.cpp (~7.6 GiB)
cd services/speech   && SPEECH_SLOW=1 python -m pytest -q -m slow            # ASR and TTS weights in the HF cache
```

Database tests in the oracle and the store skip themselves unless a sandbox store answers (the OSINT store tests
refuse any DSN other than a loopback sandbox).

## 2.4 The Rust suite

```bash
cd services/signal-ingress && cargo test --locked
```

121 tests across the crate's test binaries: the plausibility checks (future timestamp, stale data, speed
jump, phantom reading, z-score, congestion outlier, road-class mismatch, spatial mismatch), the batcher, the Arrow
encoding and the compiled-in segment table of the City Pack.

## 2.5 The command deck

From `services/command-deck` (the deck's `node_modules` must already be installed with `bun install`):

```bash
node_modules/.bin/svelte-kit sync
node_modules/.bin/svelte-check --tsconfig ./tsconfig.json --threshold error
node tests/design-tokens.mjs
node tests/copy-lint.mjs
node tests/contract/run.mjs
for u in tests/*.unit.mjs; do node "$u" || echo "FAIL $u"; done
```

The browser smokes (`tests/*-smoke.mjs`) need a running deck and a headless Chromium; each prints the URL it
expects in its header.

## 2.6 The City Pack check

```bash
python3 scripts/city_build.py mumbai --check
```

Standard library only; no network, no database. It fails if any generated file differs from what the pack
produces.

## 2.7 The offline acceptance ladder

```bash
bash scripts/verify_all.sh            # the offline tiers, in order
bash scripts/verify_all.sh --live     # adds the tiers that need a running stack
```

The offline tiers include the script syntax check, the deck tiers, every pytest suite it discovers under
`services/`, the OSINT offline smoke, cargo, the display-geometry and ingress-segment checks, and the forecaster,
routing and repetition checks of the platform's decision AI.

## 2.8 Running tests safely

- Unit suites never call a live service: outbound HTTP is mocked, and the deck's `no-live-port` suite fails if any
  browser code targets a service port directly.
- Some scripts (`scripts/verify_all.sh --live`, `scripts/journeys.mjs`, `scripts/showcase_run.sh`) default to fixed
  loopback ports that may belong to another stack on a shared machine. Export `DECK_URL`, `ORACLE_PORT`,
  `BRAIN_PORT` and `EMULATOR_PORT` for the stack you mean to test before running them
  ([`ENVIRONMENT.md`](ENVIRONMENT.md) lists every default).
- A development copy of the speech service creates a CUDA context at start and may ask its loopback peers to release
  memory unless told not to: run it with `SPEECH_DEVICE=cpu`, `SPEECH_CUDA_CONTEXT_AT_START=false` and
  `SPEECH_MAKE_ROOM=false` beside a live stack (§1.8).
- Database tests run only against a sandbox DSN on loopback.

---

# Part 3 — Representative test cases

Commands are run from the service folder named in the "Area" column (`services/<area>`), or from
`services/command-deck` for the deck and the repository root for scripts. `pytest` stands for
`python -m pytest -q -p no:cacheprovider`.

| ID | Area | What it proves | How to run | Expected |
|---|---|---|---|---|
| T-01 | twin | The cell-transmission model conserves vehicles | `pytest tests/test_ctm_physics.py::test_vehicles_are_conserved` | pass: inflow = outflow + stored |
| T-02 | twin | A queue's back moves at the kinematic-wave speed | `pytest tests/test_ctm_physics.py::test_shockwave_speed_matches_lwr` | pass: within tolerance of the LWR speed |
| T-03 | twin | A candidate that only moves the jam is rejected | `pytest tests/test_proposals.py::test_guards_reject_moving_the_jam` | pass: network delay up → not eligible |
| T-04 | twin | When nothing helps, the answer is "hold" | `pytest tests/test_proposals.py::test_hold_when_nothing_helps` | pass: recommendation `hold`, ranking explains why |
| T-05 | twin | Live state is read with GETs only and labelled | `pytest tests/test_network.py::test_live_state_is_read_only_and_labelled` | pass: no write; LIVE / EMULATED / SIMULATED label |
| T-06 | twin | An LLM rationale with a number not in the twin metrics is replaced by the template | `pytest tests/test_rationale.py::test_llm_number_not_in_metrics_falls_back_to_template` | pass: `source: template` |
| T-07 | twin | A Marathi rationale with stray Latin words or another script is rejected | `pytest tests/test_rationale.py::test_marathi_with_stray_latin_or_another_script_is_rejected` | pass |
| T-08 | hydro | More rain, a high tide (outfall gates shut) and pumps out of service each make ponding worse: Mumbai's rain × tide × pumps problem in one test | `pytest tests/test_model_ffews.py::test_more_rain_tide_and_pump_loss_make_it_worse` | pass: each one deepens the water |
| T-09 | hydro | Dry weather and light rain below the drainage floor never pond | `pytest tests/test_model_ffews.py::test_dry_and_light_rain_stay_dry` | pass: class 0, depth 0 |
| T-10 | hydro | Bridge decks and flyovers never pond; water recedes after rain | `pytest tests/test_model_ffews.py::test_elevated_never_ponds_and_water_recedes` | pass |
| T-11 | hydro | The pumping-station stand-in labels every record EMULATED and is deterministic | `pytest tests/test_model_ffews.py::test_emulated_ffews_is_labelled_and_deterministic` | pass |
| T-12 | hydro | A storm flags segments with lead times and drafts proposals, never actions | `pytest tests/test_nowcast_replay_api.py::test_storm_flags_segments_with_lead_times_and_proposals` | pass: `requires_officer: true`, `await_officer` |
| T-13 | hydro | The storm replay runs both rain sources and checks against reported places honestly | `pytest tests/test_nowcast_replay_api.py::test_replay_two_runs_and_honest_check` | pass |
| T-14 | hydro | The rain client serves the cache when rate-limited | `pytest tests/test_rain.py::test_rate_limit_serves_stale_cache` | pass: at most one call per 30 s |
| T-15 | forecast | A store seeded with another city is not read as Mumbai history | `pytest tests/test_oracle_covariates.py::test_engine_ignores_an_oracle_seeded_with_another_city` | pass: falls back with the reason |
| T-16 | forecast | Simulated history is labelled SIMULATED, never merged with real rows | `pytest tests/test_oracle_covariates.py::test_assemble_history_synthetic_rollup_is_labelled` | pass |
| T-17 | forecast | If the model breaks, the baseline is served and the response says so | `pytest tests/test_models_engine.py::test_engine_falls_back_to_baseline_when_model_breaks` | pass: `model_note` set |
| T-18 | forecast | The synthetic history loads pandal roads on Ganeshotsav nights | `pytest tests/test_synthetic.py::test_ganeshotsav_nights_load_pandal_roads` | pass |
| T-19 | forecast | The forecast's tide model is identical to the hydro service's | `pytest tests/test_oracle_covariates.py::test_tide_copy_matches_hydro` | pass |
| T-20 | forecast | Chronos-2 beats the seasonal-naive baseline on the simulated history | `pytest -m model tests/test_model_real.py::test_chronos2_beats_baseline_on_simulated_history` | pass (needs the GPU and weights) |
| T-21 | speech | Uploaded audio is never stored | `pytest tests/test_api.py::test_audio_is_not_stored` | pass |
| T-22 | speech | A typed Marathi report ("लालबाग येथे मिरवणूक, रस्ता बंद": a procession at Lalbaug, road closed) becomes a structured, unverified field report | `pytest tests/test_api.py::test_report_from_text` | pass: place `lalbaug`, kind `procession`, `UNVERIFIED-FIELD`, no ASR call |
| T-23 | speech | Negated cues ("no water") do not count | `pytest tests/test_kinds.py::test_negated_cues_do_not_count` | pass |
| T-24 | speech | "पूर्व" (East) is not read as "पूर" (flood): "दादर पूर्व येथे गर्दी" is a crowd at Dadar East, not a flood | `pytest tests/test_kinds.py::test_east_is_not_a_flood` | pass: kind `other` |
| T-25 | speech | Mumbai places match in Marathi, Hindi, English and romanised speech: Hindmata, शीव for Sion, VT for CSMT, BKC not taken for Kurla or Bandra | `pytest tests/test_places.py::test_match` | pass: each phrase → its `landmarks.json` id |
| T-26 | speech | Marathi text is split for TTS at the danda (।) | `pytest tests/test_tts_unit.py::test_split_sentences_marathi_danda_and_long_runs` | pass |
| T-27 | speech | The model refuses to load below the memory floor | `pytest tests/test_runtime.py::test_refuses_below_the_memory_floor` | pass: 503, nothing loaded |
| T-28 | vision | "Who is in this image" is refused before the model is called | `pytest tests/test_api.py::test_who_is_in_this_image_is_refused_without_calling_the_model` | pass: 403, policy `vehicles-and-roads-only` |
| T-29 | vision | Plate questions in English, Marathi or Hindi ("या टॅक्सीचा नोंदणी क्रमांक काय आहे?") are refused and routed to the ANPR path | `pytest tests/test_ethics.py::test_plate_questions_are_refused_and_routed_to_anpr` | pass: 403, `no-plate-reading` |
| T-30 | vision | The output filter removes every person sentence from real unguarded model text | `pytest tests/test_ethics.py::test_scrub_never_returns_person_terms_for_real_unguarded_model_text` | pass |
| T-31 | vision | The JSON schema allows only the known road states and depth bands | `pytest tests/test_model.py::test_schema_only_allows_known_states_and_bands` | pass |
| T-32 | vision | Every evaluation image is credited and openly licensed | `pytest tests/test_fixtures.py::test_every_image_is_credited_and_openly_licensed` | pass |
| T-33 | vision | Road questions stay allowed: "लोकल" (the local train) is not taken for "लोक" (people), and "कोणता रस्ता" (which road) is not "who" | `pytest tests/test_ethics.py::test_road_questions_are_allowed` | pass |
| T-34 | traffic-oracle | Approving an e-challan on a stolen vehicle is refused: no fine for a theft victim | `pytest tests/test_enforcement_stolen.py::test_approving_an_e_challan_of_a_stolen_vehicle_is_409` | pass: HTTP 409 |
| T-35 | traffic-oracle | One approval authorises one pursuit | `pytest tests/test_enforcement_stolen.py::test_one_approval_authorises_one_pursuit` | pass |
| T-36 | traffic-oracle | Plates in any case or spelling (lower case, dotted, slashed, underscored) never leave the server unmasked; the rule works for any state code, MH included | `pytest tests/test_city_plate_mask.py::test_lower_case_dotted_and_slashed_marks_never_leave_raw` | pass: the digits never appear; each mark ends `•••1` |
| T-37 | traffic-oracle | A signal-plan write without a named officer is refused before any write | `pytest tests/test_signals_officer.py::test_officer_required_flag_is_enforced_before_any_write` | pass |
| T-38 | convoy-brain | An unanswered proposal expires and the current plan holds | `pytest tests/test_escort_authority.py::test_no_answer_expires_and_the_convoy_holds_its_current_plan` | pass |
| T-39 | convoy-brain | Even a confident reroute waits for an officer | `pytest tests/test_escort_authority.py::test_a_confident_reroute_waits_for_the_officer` | pass |
| T-40 | corridor-store | The live City Pack rebuilds the committed files byte for byte | `pytest tests/test_city_build.py::test_the_live_pack_rebuilds_the_committed_files` | pass |
| T-41 | corridor-store | A second city builds from its own folder | `pytest tests/test_city_build.py::test_the_first_city_builds_from_its_own_folder` | pass |
| T-42 | osint-analysis | A single social post is capped at credibility 0.30 | `pytest tests/test_credibility.py::test_a_single_social_post_is_capped_at_0_30` | pass |
| T-43 | deck | The loopback proxy refuses machine ingest from a browser, before the gate and before any fetch | `python -m pytest -q tests/test_deck_proxy_guard.py::test_machine_ingest_refused_before_gate_and_fetch` | pass: 403 |
| T-44 | deck | Plates are masked in every deck rendering path until an officer is named | `node tests/plates.unit.mjs` | `ok` lines, exit 0 |
| T-45 | deck | No browser code targets a service port directly | `node tests/no-live-port.unit.mjs` | `no-live-port: all checks passed` |
| T-46 | deck | Every Marathi string pack matches English key for key and is in Devanagari | `node tests/mr-script.unit.mjs` | `all mr-script checks passed` |
| T-47 | deck | No yellow token, V3 colour or brand file anywhere: the palette is neutral and colour carries meaning only | `node tests/v3-tokens.unit.mjs` | `v3-tokens: ALL OK` |
| T-48 | City Pack | Every generated file is current | `python3 scripts/city_build.py mumbai --check` | `[mumbai] OK: every derived file is current` |

---

# Part 4 — Known gaps

- **Real field data.** The speech evaluation uses synthetic audio, the vision evaluation uses 12 public photos, and
  the forecasts run on simulated traffic. Each service document in [`ai/`](ai/) lists what a pilot must collect.
- **Agency feeds.** BMC pumps and gauges, Mumbai Traffic Police signal controllers and detectors, ANPR, CCTV,
  ambulance (108) GPS and BEST and rail running status are EMULATED until access is granted
  ([`DATA_SOURCES.md`](DATA_SOURCES.md) §7).
- **Mumbai sample captures.** Twelve files in [`samples/`](samples/) are still the Kolkata reference pack's; the
  Mumbai captures that need the Apollo Bunder tide model, the Mumbai hydro data and the scenario library are listed
  as pending in [`samples/README.md`](samples/README.md).
- **End-to-end browser journeys** need a running stack, so they are not part of the offline totals above.
- **Database tests** run only when a sandbox store answers; their skips are listed in §2.2.
