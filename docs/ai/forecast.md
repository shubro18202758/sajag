# Corridor forecasting (`services/forecast`)

Mumbai's peaks are long and slow. TomTom's Traffic Index 2025 puts the time lost to peak-hour traffic at about **126 hours** in 2025 (14 h less than in 2024), the rush-hour average at **about 17–21 km/h** depending on the definition (TomTom's city page: 17.6 km/h; 5.2 km in 15 minutes on average), Mumbai **18th** most congested worldwide, and the worst day **16 Sep 2025** (+129 % congestion). The peaks load the arterials: the Western and Eastern Express Highways (WEH, EEH), SV Road, LBS Marg, Dr Ambedkar Road (Parel–Dadar–King's Circle–Sion), the Bandra–Worli Sea Link, the Coastal Road, and the JVLR and SCLR links.

Sajag forecasts speed and volume-to-capacity (V/C) for every segment of the Mumbai road network, 15 to 120 minutes ahead, as p10 / p50 / p90 bands. When the median V/C is forecast to cross 0.8, the service raises a **pre-emptive diversion proposal**. A named duty officer decides; the service never acts.

| | |
|---|---|
| Model | **Chronos-2** (`amazon/chronos-2`), zero-shot and covariate-aware, about 120 M parameters, on the GPU |
| Second model (backtest) | **TimesFM 2.5** (`google/timesfm-2.5-200m-pytorch`), univariate |
| Baseline | Seasonal naive: same slot yesterday or last week, whichever fitted the last two days better |
| Covariates | Rain intensity, outfall blockage (the Arabian Sea tide at Apollo Bunder), active events |
| Port | 8195 in production (loopback); 9151 in development |
| Label | **"Forecast on simulated traffic"** until the platform has recorded traffic for Mumbai |

## Licences (checked against the model cards, 28 Oct 2026)

| Artefact | Licence | Where it was checked |
|---|---|---|
| `amazon/chronos-2` weights | Apache-2.0 | model card front matter `license: apache-2.0` (HF snapshot `29ec376…`) |
| `chronos-forecasting` 2.3.2 (package) | Apache-2.0 | wheel METADATA |
| `google/timesfm-2.5-200m-pytorch` weights | Apache-2.0 | model card front matter `license: apache-2.0` (HF snapshot `1d95242…`) |
| `timesfm` 3.0.2 (package) | Apache-2.0 | wheel METADATA |

TimesFM 2.5 installs cleanly on aarch64 (`timesfm[torch]==3.0.2`) and runs on the GB10. Its covariate path (`forecast_with_covariates`) needs the JAX `xreg` extra, which the service does not install, so it runs univariate.

## Data: where the platform keeps traffic, and what the service reads

The traffic-oracle holds traffic state in four places:

- `traffic.observations`: the raw rows (`speed_kmh`, `congestion_idx`, `data_quality`). Read through `GET /api/v1/traffic/history/{id}`, which returns the last 24 hours, at most 500 rows.
- `traffic.hourly_aggregates` and `traffic.hourly_aggregates_synthetic`. Read through `GET /api/v1/traffic/historical?segment_id=&hours=`, which returns them as `aggregates` (real) and `synthetic_aggregates` (simulated). They are never merged.
- `corridor.road_segments`. Read through `GET /api/traffic/segments?bbox`. The deck's `traffic-flow` layer draws from the same geometry.
- Active corridor events and their route spines. Read through `GET /api/v1/events/active`.

The service only ever sends GET requests to the oracle, and a test asserts it. The oracle's base URL is configurable. Development used the Sajag sandbox at `http://127.0.0.1:8170`.

### How a segment's history is built

1. Take the hourly aggregates and interpolate them to 15-minute steps. Real rows are used first. The synthetic rollup is used only when there is no real row, and then the whole series is labelled SIMULATED.
2. Lay the last day's raw rows over that, resampled to 15-minute means.
3. The oracle stores speed, not V/C. V/C is derived from speed by inverting the oracle's own twin curve, `v = v_ff / (1 + 0.55·(V/C)^4.2)` (`bpr.py`, MODELLED).

### The city guard

A store still seeded with another city has the same segment ids on different roads. To avoid reading it as Mumbai, only segments the oracle serves **inside the Mumbai bbox** (18.89–19.28 N, 72.77–72.99 E, from `cities/mumbai/city.json`) are read from it. A segment the oracle does not serve inside the bbox falls back to the synthetic history, with the reason stated: "oracle serves no segment with this id inside the city bbox (its store is not seeded with this city's network)".

### The synthetic Mumbai history (`synthetic.py`, SIMULATED)

`synthetic.py` generates a deterministic, seeded history for offline tests and backtests. None of it is a measurement of Mumbai traffic. It models these rhythms:

- **Weekday office peaks.** Inbound roads (towards the Island City and BKC) load in the morning and outbound roads in the evening; the evening peak is the longer one.
- **Weekends.** Lighter Saturdays and Sundays.
- **Festival nights.** Ganeshotsav, and above all the Anant Chaturdashi visarjan, load the roads around Lalbaug, Girgaon Chowpatty, Dadar Chowpatty and Juhu heavily into the night (2025: Ganesh Chaturthi on 27 Aug, Anant Chaturdashi on 6 Sep).
- **Monsoon-shaped storm cells.** Rain cuts capacity.
- **Waterlogging at high tide.** Accumulated rain cuts capacity further while the Apollo Bunder tide model says the outfalls are blocked.
- **Stadium egress.** A few simulated Wankhede Stadium egress windows onto Marine Drive, Churchgate and Marine Lines.
- **Breakdowns.** Unannounced incidents, such as a stalled BEST bus.
- **Noise.** AR(1) noise.

A value at a given instant does not depend on the window requested.

The `data_source` setting controls which history is used:

| `data_source` | Behaviour |
|---|---|
| `auto` (default) | Oracle history where it has at least 2 days; otherwise the synthetic history, per segment |
| `oracle` | Oracle history only. A segment without it is reported in `skipped`, not forecast. |
| `synthetic` | Synthetic history only |

Covariates follow the history's world:

| History | Rain | Tide (outfall blockage) | Events |
|---|---|---|---|
| Oracle | Hydro service, `GET /hydro/rain` (Open-Meteo, LIVE) | Apollo Bunder tide model (MODELLED) | Oracle active events |
| Synthetic | Simulated world (SIMULATED) | Simulated world (SIMULATED) | Simulated world (SIMULATED) |

## API

| Route | What it returns |
|---|---|
| `GET /health` | Model slot (loaded or not, weights in GPU MiB, peak MiB, idle timer), second model, oracle probe, GPU |
| `GET /forecast/segments?horizon_min=15..120` | For each segment: 15-minute steps with `vc` and `speed_kmh` p10/p50/p90 and the baseline p50. Also `crossing` (when p50 V/C reaches 0.8 within the horizon and is below it now), the `proposals`, `data_labels` and `data_note`. |
| `GET /forecast/segment/{id}?horizon_min=` | One segment and its proposal. Unknown id: 404. Not forecast: 409. |
| `GET /forecast/metrics` | Rolling backtest, with the honest data label |
| `POST /forecast/refresh?backtest=false` | Recompute now; include the backtest when `backtest=true` |
| `POST /admin/release?idle_s=` | Loopback machine callers only: free the models no forecast holds and unused for `idle_s` (default 20 s). See "Making room". |

### Proposal shape

Proposals use the decision-support vocabulary of `osint_common` (C-U):

- `state: proposed`;
- `actions` as `CoaAction`: verb `diversion`, `monitor` or `advisory`, with `requires_officer: true` and `reversible: true`;
- `recommendation.decision: await_officer`;
- `human_gate: {state: proposed, required_role: duty_officer, officer: null, decided_at: null}`;
- `labels`.

The detour is the shortest path on the city network between the segment's end junctions. It avoids the segment and, where it can, every other segment forecast at or over 0.8.

The summary reads like this (the shape, with illustrative places; not a run output):

> Kalanagar (Bandra East): V/C forecast ‹p50› in ‹n› min (p10–p90 ‹low›–‹high›) on the Western Express Highway southbound; propose diversion via the BKC connector → SCLR.

Junctions are named by their canonical ids in `cities/mumbai/landmarks.json` (`kalanagar`, `sion_circle`, `kings_circle`, `dadar_tt`, `worli_naka`, `haji_ali`, `mahim_causeway`, `weh_andheri`, `bkc` …).

## Backtest

The backtest is run with `GET /forecast/metrics` on the GB10, or offline with `services/forecast/scripts/backtest_mumbai.py`, which records `services/forecast/eval/backtest_mumbai.json`.

**On the Mumbai network** (30 Oct 2026; 86 segments × 12 rolling origins every 6 h over 3 days = 1032 series; 120 min ahead from a 14-day context; the SIMULATED Mumbai history, seed 1853; future covariates are the realised simulated values, a perfect-nowcast assumption). Each cell: V/C MAE · p10–p90 coverage (target 0.80) · crossing-alert precision / recall.

| Window | Chronos-2 | Chronos-2, no covariates | TimesFM 2.5 | Seasonal naive |
|---|---|---|---|---|
| 27–30 Oct 2026 | **0.0381** · 0.818 · 0.92 / 0.69 | 0.0381 · 0.784 · 0.90 / 0.74 | 0.0385 · 0.825 · 0.90 / 0.73 | 0.0625 · 0.814 · 0.72 / 0.76 |
| 24–26 Sep 2026 (monsoon; Anant Chaturdashi) | **0.0425** · 0.798 · 0.87 / 0.81 | 0.0439 · 0.755 · 0.87 / 0.84 | 0.0446 · 0.802 · 0.88 / 0.84 | 0.0728 · 0.798 · 0.70 / 0.88 |

- Both foundation models cut the baseline's error by about 40 % on Mumbai's network.
- The rain, gate-closure (Apollo Bunder tide) and event covariates leave the point error unchanged in the dry October window and lower it by about 3 % in the monsoon and festival window. Mainly they improve calibration (coverage 0.78 → 0.82 and 0.76 → 0.80).
- Chronos-2 raises fewer, more precise crossing alerts than the baseline and recalls fewer.
- These are numbers on simulated traffic. They show the pipeline works on Mumbai's network; they do not measure accuracy on recorded Mumbai traffic.

The model comparison below was measured on **28 Oct 2026 on the Kolkata reference pack** (`cities/kolkata`), not on Mumbai roads. It shows that the pipeline works and how the models compare on simulated traffic. Its scope:

- **Origins:** 12 rolling origins, every 6 hours over 25–28 Oct 2026.
- **Series:** 65 segments × 12 origins = 780 series.
- **Horizon and context:** 120 minutes ahead, from a 14-day context.
- **Data:** the SIMULATED history of that pack (seed 1690).
- **Future covariates:** the realised simulated values, which is a perfect-nowcast assumption.

| Model (Kolkata reference pack, simulated) | MAE (V/C) | MAPE | MAE speed | p10–p90 coverage (target 0.80) | Mean band width | Skill vs baseline | Crossing alerts precision / recall |
|---|---|---|---|---|---|---|---|
| **Chronos-2** (with covariates) | **0.0429** | 15.2 % | 0.74 km/h | 0.797 | 0.135 | **+54.9 %** | 0.79 / 0.44 |
| Chronos-2 without covariates (ablation) | 0.0439 | 15.3 % | 0.76 km/h | 0.758 | 0.126 | +53.9 % | 0.83 / 0.54 |
| TimesFM 2.5 (univariate) | 0.0443 | 15.4 % | 0.77 km/h | 0.813 | 0.145 | +53.5 % | 0.78 / 0.51 |
| Seasonal naive (baseline) | 0.0952 | 32.0 % | 1.53 km/h | 0.754 | 0.276 | — | 0.63 / 0.41 |

How to read this, honestly:

- Both foundation models halve the baseline's error.
- Chronos-2 with covariates is the most accurate and the best calibrated. It improves coverage by about 4 points over its own univariate run.
- Its gain in point error from the covariates is small (2 %).
- Its alert recall is lower than without covariates. It raises fewer, more precise crossing alerts.
- A second run a few minutes later, with origins shifted by 15 minutes, kept the same order (Chronos-2 MAE 0.0415, coverage 0.813).
- These are numbers on simulated traffic of another city. They do not measure accuracy on Mumbai roads.

### GPU memory (measured with `torch.cuda` on the GB10, reference pack network)

| | Chronos-2 (fp32) | TimesFM 2.5 |
|---|---|---|
| Weights | 456 MiB | 882 MiB |
| Peak | 1,614 MiB (65 segments × 14-day context) | 3,655 MiB, process-wide (batch of 128) |
| Load time | 6–12 s | 2–4 s |
| Inference | ~1–2 s for 65 segments once loaded | — |

- The Mumbai network has 86 segments; the peak grows with the number of series.
- `SAJAG_FORECAST_DTYPE=bfloat16` halves the Chronos-2 weights.
- Chronos-2 is loaded on first use and **freed after `idle_unload_sec` of disuse**. In the development run (idle 60 s), `/health` then showed `loaded: false`, `unloads: 1` and 32 MiB still allocated.
- TimesFM is freed as soon as the backtest finishes.

### Making room

Speech and vision refuse a load that would leave MemAvailable under their 8 GiB floor (or that ran
out of GPU memory), and before refusing they ask the other on-demand services to free models;
forecast is asked first, since Chronos-2 is small (≈2 GiB) and reloads in seconds. `POST
/admin/release` (loopback only; a request carrying browser or proxy headers is refused) frees a
slot only when no forecast holds it and it has been unused for `idle_s` seconds: a service making
room sends `idle_s=0` (a waiting load has priority over a model merely kept warm), a call by hand
defaults to 20 s (`SAJAG_FORECAST_RELEASE_IDLE_SEC`). The next forecast reloads it, and until then
nothing else changes. Forecast loads without a floor of its own, so it never makes room itself.
`/health` → `make_room.last_release` shows the last release.

## Limits

- **Forecasts are on simulated traffic** until the oracle stores real Mumbai traffic (Mumbai Traffic Police detector counts are an agency feed and are EMULATED). The labels say so on every segment and every proposal.
- **V/C is derived, not measured.** It comes from speed through the twin's curve.
- **The detours use the curated arterial network** (86 segments), so they can be long. Each proposal states the detour length, and the officer judges it.
- **The diverted share is a proportional estimate.** `expected_effect.suggested_share` was not simulated in the twin.
- **At evening peaks, many segments cross 0.8 at once.** Proposals are sorted by forecast severity, then by how soon.
- **The tide model here is a copy of `services/hydro/src/hydro/tide.py`.** A test keeps the two identical.
