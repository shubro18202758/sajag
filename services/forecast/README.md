# forecast: corridor speed and congestion forecasting

This service forecasts speed and V/C for every Mumbai road segment of the curated arterial network, 15 to 120 minutes ahead in 15-minute steps, as p10 / p50 / p90 bands. A segment is flagged with a `crossing` when its median V/C is forecast to reach 0.8 within the horizon. Each crossing produces a **pre-emptive diversion proposal**, never an action: a named duty officer decides. The full design, data paths and backtest numbers are in [`docs/ai/forecast.md`](../../docs/ai/forecast.md).

## Models and licences

| Role | Model | Licence |
|---|---|---|
| Forecaster | **Chronos-2** (`amazon/chronos-2`, ~120 M parameters), via `chronos-forecasting`; on the GPU; covariate-aware | Apache-2.0 (model card and package) |
| Second model (backtest only) | **TimesFM 2.5** (`google/timesfm-2.5-200m-pytorch`), via `timesfm[torch]`; univariate here | Apache-2.0 (model card and package) |
| Baseline | Seasonal naive: day or week lag, chosen on the last two days | — |

- **Loading:** weights load lazily, are freed after `SAJAG_FORECAST_IDLE_UNLOAD_SEC` (600 s) of disuse, and are never downloaded at import.
- **GPU memory (GB10):** Chronos-2 weights take 456 MiB, peaking at 1.6 GiB for 65 segments with 14 days of context (measured on the earlier 65-segment network; the Mumbai network has 86). TimesFM takes 882 MiB and is freed right after the backtest.
- **Fallback:** if the model cannot load, the service serves the baseline and says so in `model_note`.

## API (production port 8195, loopback)

`GET /health` · `GET /forecast/segments?horizon_min=15..120` · `GET /forecast/segment/{id}` · `GET /forecast/metrics` (rolling backtest: model vs baseline vs second model, plus a no-covariate ablation) · `POST /forecast/refresh?backtest=false`

## Data and honest labels

| Data | Source | Label |
|---|---|---|
| History | The traffic-oracle, read only (GET): hourly aggregates + raw rows, and only for segments it serves inside the Mumbai bbox (`cities/mumbai/city.json`) | `LIVE` if the rows are real; `SIMULATED` if they are its simulated feed |
| History (fallback) | The deterministic synthetic Mumbai history (`synthetic.py`): office peaks towards South Mumbai, Ganeshotsav nights by Lalbaugcha Raja and King's Circle, immersion days to Girgaon / Dadar Chowpatty / Juhu (Anant Chaturdashi through the night), Wankhede egress, the marathon morning, New Year's Eve on Marine Drive, the Mount Mary fair; monsoon storm cells (June–September) and waterlogging at the chronic flooding spots (Hindmata, King's Circle, Sion, Dadar TT, Parel, Milan and Andheri subways, Kurla) made worse while the sea outfalls are shut at high tide | `SIMULATED` |
| V/C | Derived from speed through the oracle's twin curve (`bpr.py`) | MODELLED |
| Rain covariate (oracle history) | The hydro service, Open-Meteo | LIVE |
| Gate-closure covariate | Apollo Bunder (Mumbai harbour) tide model: the sea outfalls' flap gates shut at high tide (`tide.py`, a copy of the hydro service's) | MODELLED |
| Event covariate | Oracle active events | — |
| Covariates (synthetic history) | The same simulated world | SIMULATED |
| Proposals | — | Carry their data label and `MODELLED` |

Until the oracle stores Mumbai traffic, every forecast is a **forecast on simulated traffic**, and the response says so in `data_note`.

## Backtest on the Mumbai network (recorded)

`scripts/backtest_mumbai.py` (venv with chronos-forecasting / timesfm) writes `eval/backtest_mumbai.json`. Run on
30 Oct 2026 on the GB10 (commit 636bca2): 86 segments × 12 rolling origins (every 6 h over 3 days) = 1032 series,
120 min ahead from a 14-day context, on the **SIMULATED** Mumbai history (seed 1853). Future covariates are the
realised simulated values (a perfect-nowcast assumption). V/C mean absolute error, p10–p90 coverage (target 0.80)
and V/C-0.8 crossing alerts (precision / recall):

| Window | Chronos-2 | Chronos-2, no covariates | TimesFM 2.5 | Seasonal naive |
|---|---|---|---|---|
| 27–30 Oct 2026 | **0.0381** · 0.818 · 0.92 / 0.69 | 0.0381 · 0.784 · 0.90 / 0.74 | 0.0385 · 0.825 · 0.90 / 0.73 | 0.0625 · 0.814 · 0.72 / 0.76 |
| 24–26 Sep 2026 (monsoon; Anant Chaturdashi) | **0.0425** · 0.798 · 0.87 / 0.81 | 0.0439 · 0.755 · 0.87 / 0.84 | 0.0446 · 0.802 · 0.88 / 0.84 | 0.0728 · 0.798 · 0.70 / 0.88 |

Read honestly: both foundation models cut the baseline's error by about 40 %. The rain, gate-closure and event
covariates leave the point error unchanged in the dry October window and lower it by about 3 % in the monsoon /
festival window; they mainly improve calibration (coverage 0.78 → 0.82 and 0.76 → 0.80). Chronos-2 raises fewer,
more precise crossing alerts than the baseline and recalls fewer. These are numbers on simulated traffic: they
show the pipeline works on Mumbai's network, not accuracy on recorded Mumbai traffic. Peak GPU memory in this run
3.6 GiB (both models loaded in one process).

## Run and test

```bash
# dev run (venv with chronos-forecasting / timesfm; sandbox oracle read-only)
PYTHONPATH=src PORT=9151 SAJAG_FORECAST_ORACLE_URL=http://127.0.0.1:8170 python -m forecast

# offline tests (no model, no network)
python -m pytest -q -p no:cacheprovider
# the real-model tests (GPU venv, weights in the HF cache)
python -m pytest -q -p no:cacheprovider -m model
```

Settings use the `SAJAG_FORECAST_*` prefix (see `config.py`): `DATA_SOURCE` (auto | oracle | synthetic), `MODEL` (chronos2 | timesfm | naive), `CONTENDER` (timesfm | ""), `DEVICE`, `DTYPE` (float32 | bfloat16), `CONTEXT_DAYS`, `IDLE_UNLOAD_SEC`, `ORACLE_URL`, `HYDRO_URL`, `CITY_DIR`. The image is `infra/docker/Dockerfile.forecast`; the compose stanza is in `infra/compose.ai.yml`.

## Limits

- **History:** simulated until Mumbai traffic is recorded. V/C is derived, not counted.
- **Calendar:** Ganesh Chaturthi is the state's notified date; Anant Chaturdashi, the intermediate immersions and the Mount Mary fair are approximate (panchang / custom); sources in `calendar.py`.
- **Proposals:**
  - detours are on the curated 86-segment Mumbai arterial network (the network stream's v1); 37 of its 86 segments have a detour within the length bound (sea links, the Coastal Road and many highway links have none), and the others get a signal-timing review instead;
  - the diverted share is a proportional estimate that was not run through the twin.
- **TimesFM:** runs without covariates.
- **Network:** the bundled snapshot (`data/mumbai_network.json`, junctions and segments only) is taken from the network stream's v1.1 (b7d833f; ids stable). A `cities/mumbai/network.json` in the repo takes precedence.
