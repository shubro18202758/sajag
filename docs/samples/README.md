# Sample data

Small, real sample files from the Sajag services, so a reader can see what each API returns without running the
stack. Every file says where it came from in a `_sample` key at the top. Lists are trimmed (for example 4 of 12
evaluation images); nothing inside a kept record was edited, except that absolute paths on the build machine were
shortened to repository paths and the removals each file's `_sample` names.

There are two sets:

- **Mumbai** (top level): made on **30 Oct 2026** on the Mumbai City Pack (`cities/mumbai/`).
- **Kolkata reference** ([`kolkata-reference/`](kolkata-reference/)): made on 28 Oct 2026 on the **Kolkata
  reference pack** (`cities/kolkata/`, the second City Pack kept in the repository) before the platform moved to
  Mumbai. They show the shape of each answer; **they are not Mumbai captures**, and each says so in
  `_sample.pack`. Fields in the reference pack's earlier second UI language were removed from them (each file lists
  what was removed in `_sample.removed`); Sajag's UI languages are now English, Marathi and Hindi.

How they were made:

- **Run locally:** the service was started on a loopback development port and called with `curl`. On 30 Oct the
  speech and vision services ran on ports 9361 and 9363 without loading a model (a typed report, and three policy
  refusals), the twin ran on the CPU on port 9371 and the forecast ran Chronos-2 on the GPU on port 9351, both on
  the Mumbai network; each was stopped afterwards. On 28 Oct (reference pack) the twin and hydro ran on the CPU and the
  forecast ran Chronos-2 on the GPU.
- **From an evaluation file:** copied from the service's own committed evaluation results, which were produced by
  the real model.
- **From a committed data file:** an excerpt of a file the City Pack build generates.
- **Constructed:** written for this documentation and validated against the service's schema. Only one file is
  constructed, and it says so.

## Mumbai

| File | What it shows | Provenance | Honest label in the data |
|---|---|---|---|
| [`speech/report-typed-mr.json`](speech/report-typed-mr.json) | `POST /speech/report?lang=mr` with a typed Marathi report, "हिंदमाता येथे गुडघाभर पाणी साचले आहे, बस अडकल्या आहेत" (knee-deep water at Hindmata, buses stuck): matched place `hindmata`, candidates, kind `waterlogging`, severity `medium`, the cue words, and the confirmation note in English, Marathi and Hindi | Run locally on 30 Oct 2026, `SPEECH_CITY_DIR=cities/mumbai` (no ASR needed for typed text) | UNVERIFIED-FIELD, `requires_confirmation: true` |
| [`vision/refusals-403.json`](vision/refusals-403.json) | A plate question ("Read the number plate of the kaali-peeli taxi"), a person question in English and the same in Marathi, all refused with HTTP 403 before any model call, on the Mumbai test still near CSMT | Run locally on 30 Oct 2026, no model attached | policy `no-plate-reading`, `vehicles-and-roads-only` |
| [`vision/eval-excerpt.json`](vision/eval-excerpt.json) | The evaluation summary (11 of 12 road states right), the confusion matrix, four image rows (a flooded arterial in 2017, an evening queue near CSMT, a banyan across Old Prabhadevi Road after Cyclone Tauktae, and the one miss) and all 11 refusal probes in English, Marathi and Hindi | From `services/vision/eval/results.json` (Qwen3-VL-8B, re-run on 30 Oct 2026 on 12 credited public photos, 10 of them from Mumbai) | UNVERIFIED-CAMERA |
| [`forecast/segments-chronos2-synthetic-2026-10-30.json`](forecast/segments-chronos2-synthetic-2026-10-30.json) | `GET /forecast/segments?horizon_min=120` on Mumbai: p10/p50/p90 V/C and speed in 15-minute steps, the seasonal-naive baseline beside each step, for 3 of 86 segments (Dr Ambedkar Road at Hindmata, the Andheri Subway approach, Saki Vihar Road), and one of the 36 forecast crossings with its proposal: Saki Vihar Road (Powai) at V/C 0.83 in 45 minutes (p10–p90 0.77–0.88), a pre-emptive diversion via Andheri–Kurla Road, the Western Express Highway and JVLR, and an advisory draft in English and Marathi, each action needing an officer | Run locally on 30 Oct 2026, Chronos-2 on the GPU, the synthetic Mumbai history on the Mumbai network v1; nothing live read | SIMULATED history ("forecast on simulated traffic") · proposal `requires_officer: true` |
| [`twin/propose-hindmata-1800.json`](twin/propose-hindmata-1800.json) | `POST /twin/propose` for Hindmata (Dadar East) at 18:00 IST over 45 minutes: 14 candidates evaluated, the recommendation and the full proposal object. The twin proposes 6 s more green for the Dr Ambedkar Road movement for 30 minutes: modelled delay at Hindmata down 14.7 %, the longest queue 13 m longer and cross-street delay up 20 %, with the English rationale and "a named officer decides" | Run locally on 30 Oct 2026 on the Mumbai network v1, CPU, the oracle and the LLM off (template rationale). The twin's simulated demand was still its original weekday profile, which the file says | result MODELLED · demand SIMULATED · status PROPOSED |
| [`twin/baselines-hindmata.json`](twin/baselines-hindmata.json) | `GET /twin/baselines/hindmata`: the junction's assumed program (`osm_assumed`), Webster and max-pressure, each simulated on its three approaches (Dr Ambedkar Road both ways, Dr E Borges Road) | Run locally on 30 Oct 2026 on the Mumbai network v1, CPU | MODELLED |
| [`city-pack/network-excerpt.json`](city-pack/network-excerpt.json) | The Mumbai road network (`sajag.network/1`): the network summary, two junctions (Hindmata, Andheri Subway), two segments, Hindmata's signal program, a camera site and a station | From `cities/mumbai/network.json` (network v1, 30 Oct 2026) | signal programs and camera sites MODELLED; roads from OpenStreetMap |

## Kolkata reference pack (`kolkata-reference/`)

| File | What it shows | Provenance | Honest label in the data |
|---|---|---|---|
| [`kolkata-reference/hydro/nowcast-live-2026-10-28.json`](kolkata-reference/hydro/nowcast-live-2026-10-28.json) | `GET /hydro/nowcast`: depth-risk class 0–3, depth band, lead time and the four labelled drivers per road segment | Run locally, live Open-Meteo rain. A dry evening: every segment class 0, no proposals | rain LIVE · tide MODELLED · susceptibility MODELLED · pumps EMULATED |
| [`kolkata-reference/hydro/tide-24h-2026-10-28.json`](kolkata-reference/hydro/tide-24h-2026-10-28.json) | `GET /hydro/tide?hours=24`: the reference pack's river tide, high and low waters, outfall-gate state, sources | Run locally (series thinned to hourly) | MODELLED (approximate) |
| [`kolkata-reference/hydro/pumps-emulated.json`](kolkata-reference/hydro/pumps-emulated.json) | `GET /hydro/pumps`: the reference pack's drainage pumping stations through the pump adapter | Run locally | EMULATED (names and capacities real, pump states invented) |
| [`kolkata-reference/hydro/replay-2025-09-23.json`](kolkata-reference/hydro/replay-2025-09-23.json) | `POST /hydro/replay?event=2025-09-23`: a 2025 storm on the reference pack, two runs (Open-Meteo archive and IMD gauge-anchored), the check against places the news reported, the hindsight snapshot with its proposals and the English advisory draft | Run locally (segment lists trimmed to 3) | OBSERVED rain (IMD), MODELLED shape and model, HINDSIGHT snapshot |
| [`kolkata-reference/forecast/segments-chronos2-synthetic-2026-10-28.json`](kolkata-reference/forecast/segments-chronos2-synthetic-2026-10-28.json) | `GET /forecast/segments?horizon_min=120`: p10/p50/p90 V/C and speed in 15-minute steps, the seasonal-naive baseline beside each step | Run locally, Chronos-2 on the GPU, synthetic history (3 of 65 segments; no crossing at this origin) | SIMULATED history ("forecast on simulated traffic") |
| [`kolkata-reference/twin/propose-ultadanga-1800.json`](kolkata-reference/twin/propose-ultadanga-1800.json) | `POST /twin/propose` for one junction at 18:00 IST: the ranked candidates' count, the recommendation and the full proposal object (change, twin metrics, confidence, assumptions, English rationale) | Run locally, CPU, the LLM off (template rationale) | result MODELLED · demand SIMULATED · status PROPOSED |
| [`kolkata-reference/twin/baselines-park-circus.json`](kolkata-reference/twin/baselines-park-circus.json) | `GET /twin/baselines/<junction>`: the current program, Webster and max-pressure, each simulated | Run locally, CPU | MODELLED |
| [`kolkata-reference/vision/road-state-tree-fall.json`](kolkata-reference/vision/road-state-tree-fall.json) | `POST /vision/road-state`: a camera still of a fallen tree after a cyclone, read as `tree_fall`, with the full answer shape (model, label, image dimensions) | The real answer recorded in `docs/ai/vision.md` on 28 Oct | UNVERIFIED-CAMERA, `requires_confirmation: true` |
| [`kolkata-reference/osint/osint-event-row.json`](kolkata-reference/osint/osint-event-row.json) | One row of `GET /api/v1/osint/events`: a waterlogging situation, with its credibility, tiers, verification state and second-order flag | **Constructed** by hand from PTI and IANS reports and validated with `osint_common.types.OsintEventRow`; not a pipeline output | NEWS-REPORTED |
| [`kolkata-reference/corridor/scenario-durga-puja-north.json`](kolkata-reference/corridor/scenario-durga-puja-north.json) | A corridor scenario of the reference pack: a festival night (crowds and ambulance access) | From `scripts/scenario_library.json` as it was on 28 Oct | SIMULATED |
| [`kolkata-reference/corridor/scenario-cloudburst-high-tide.json`](kolkata-reference/corridor/scenario-cloudburst-high-tide.json) | A corridor scenario of the reference pack: a cloudburst at high tide (waterlogging, pumps, live-wire hazard) | From `scripts/scenario_library.json` as it was on 28 Oct | SIMULATED |
| [`kolkata-reference/city-pack/network-excerpt.json`](kolkata-reference/city-pack/network-excerpt.json) | A City Pack's road network (`sajag.network/1`): summary, two junctions, two segments, a signal program, a camera site, a station | From `cities/kolkata/network.json` | signal programs and camera sites MODELLED; roads from OpenStreetMap |

## Mumbai captures still pending

These need the Apollo Bunder tide model, the Mumbai hydro data and scenario library, and a full run of the
services on the Mumbai network, which are being finished now. Until they are captured, the reference files above show each answer's
shape, and nothing here stands in for a Mumbai measurement.

| Pending Mumbai file | What it will show |
|---|---|
| `hydro/nowcast-live-<date>.json` | The live waterlogging nowcast on Mumbai's roads (Hindmata, Milan Subway, Andheri Subway, King's Circle, Sion, Kurla) |
| `hydro/tide-24h-<date>.json` | The Arabian Sea tide at Apollo Bunder (MODELLED), high and low waters, outfall state |
| `hydro/pumps-emulated.json` | The BMC storm-water pumping stations (Haji Ali, Irla, Love Grove, Cleveland Bunder, Britannia, Gazdarbandh), EMULATED |
| `hydro/replay-<date>.json` | The replay of a real Mumbai storm (18–19 August 2025) |
| `corridor/scenario-<id>.json` | Two Mumbai scenarios (for example a visarjan night and a cloudburst at high tide) |
| `osint/osint-event-row.json` | A Mumbai OSINT situation row |
| `speech/report-audio-eval-excerpt.json` | The audio evaluation on the Marathi, Hindi and English Mumbai phrase set. The 28 Oct excerpt was dropped: its clips were in the reference pack's earlier language |
| `vision/road-state-<still>.json` | A full `POST /vision/road-state` answer on a Mumbai still (the evaluation rows above already carry the model's readings) |

The Mumbai City Pack is in [`cities/mumbai/`](../../cities/mumbai/); the reference pack in
[`cities/kolkata/`](../../cities/kolkata/). The impact model's output is [`IMPACT_REPORT.md`](../../IMPACT_REPORT.md)
and [`scripts/impact_results.json`](../../scripts/impact_results.json). How to regenerate each file, and the test
cases, are in [`../SAMPLE_DATA_AND_TESTS.md`](../SAMPLE_DATA_AND_TESTS.md).

Road network: © OpenStreetMap contributors, ODbL 1.0. Terrain: Copernicus DEM GLO-30 (© DLR e.V. 2010–2014 and
© Airbus Defence and Space GmbH 2014–2018, provided under COPERNICUS by the European Union and ESA). Rain:
Open-Meteo (CC BY 4.0). Evaluation photos: Wikimedia Commons, credited with their licences in
`services/vision/tests/fixtures/NOTICE.md`; faces and legible plates pixelated.
