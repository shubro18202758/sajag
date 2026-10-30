# Sajag — environment variable reference

All host configuration of a Sajag deployment lives in one file, **`~/.config/sajag/sajag.env`**: plain
`KEY=VALUE` lines, mode 600, never committed. This page lists every environment variable the platform's code reads,
which component reads it, its default and what it changes.

The facts are read from the code: [`scripts/sajag_env.sh`](../scripts/sajag_env.sh),
[`scripts/sajag_up.sh`](../scripts/sajag_up.sh), the compose files in [`infra/`](../infra/), the systemd units in
[`infra/systemd/`](../infra/systemd/), [`infra/scripts/serve_models.sh`](../infra/scripts/serve_models.sh) and each
service's settings module under [`services/`](../services/). Many variables keep the platform's historic `VVIP_`
prefix; they are listed exactly as the code spells them. The AI services are described in depth in [`ai/`](ai/).

This page never contains a secret value. Placeholders such as `<six-digit PIN>` stand for values you supply.

---

## Contents

1. [How configuration reaches each process](#1-how-configuration-reaches-each-process)
2. [Setting a variable](#2-setting-a-variable)
3. [Reading the tables](#3-reading-the-tables)
4. [Host environment file and bring-up](#4-host-environment-file-and-bring-up)
5. [Operator gate and sessions](#5-operator-gate-and-sessions)
6. [Maps and imagery](#6-maps-and-imagery)
7. [Database and stores](#7-database-and-stores)
8. [AI and model hosts](#8-ai-and-model-hosts)
9. [AI services: speech, forecast, vision, hydro, twin](#9-ai-services-speech-forecast-vision-hydro-twin)
10. [OSINT](#10-osint)
11. [Emulator and demo](#11-emulator-and-demo)
12. [Ports and binds](#12-ports-and-binds)
13. [Safety switches](#13-safety-switches)
14. [Gate and tool scripts (selected)](#14-gate-and-tool-scripts-selected)
15. [Set but not read, legacy and image-internal](#15-set-but-not-read-legacy-and-image-internal)
16. [A minimal working environment file](#16-a-minimal-working-environment-file)
17. [Checking the configuration](#17-checking-the-configuration)

---

## 1. How configuration reaches each process

```mermaid
flowchart LR
    SH["shell export<br/>explicit values win"] --> LD
    EF["~/.config/sajag/sajag.env<br/>mode 600, KEY=VALUE lines"] --> LD["scripts/sajag_env.sh loader<br/>exports each line not already set"]
    LD --> CI["docker compose interpolation<br/>KEY:-default and pass-through keys"]
    CI --> SV["core containers<br/>an unset pass-through key is absent,<br/>so the service's own default applies"]
    LD --> AI["AI services<br/>compose.ai.yml, compose.ai-media.yml,<br/>compose.twin.yml (layered by hand)"]
    EF --> UN["systemd --user units<br/>EnvironmentFile="]
    UN --> MH["model hosts<br/>serve_models.sh --foreground"]
    UN --> UP["sajag-up.service<br/>sajag_up.sh --boot"]
    UP --> LD
```

Four layers, in order of precedence for a container:

1. **Compose files** set most service variables directly: each service's deployed `HOST` and `PORT`, the database,
   Valkey and NATS URLs, the loopback URLs between services. Some entries interpolate with a default
   (`${VVIP_REQUIRE_OFFICER:-1}`).
2. **Pass-through keys** are compose entries with no value (`VVIP_CONFIDENCE_FLOOR:` in
   `infra/compose.argus-override.yml`). They reach the container only when set in the bring-up's environment;
   otherwise the service keeps its built-in default. An empty string never reaches a parser.
3. **The host environment file**, loaded by `scripts/sajag_env.sh`; a variable already exported in the calling
   shell wins.
4. **Service defaults** in code apply to anything not set above.

Consequences that matter in practice:

- **A boot has no login shell.** At boot, `sajag-up.service` and the model units see only `sajag.env`; a value
  only exported in a shell is gone after a reboot. `sajag_up.sh` warns when your shell carries a persisted key
  (§4.2) that `sajag.env` lacks. A deck recreated without the PIN serves the LAN with the operator gate off.
- **The units read a fixed path**, `%h/.config/sajag/sajag.env`, never `$XDG_CONFIG_HOME`. `SAJAG_ENV_FILE`
  changes only what the scripts read.
- **Two variables belong to the bring-up.** `sajag_up.sh` exports `VVIP_SIGNAL_POLICY_WRITER` and
  `EMULATOR_LIVING_CITY` from `SAJAG_DEMO` on every bring-up, so a value written for either in `sajag.env` is
  overwritten. Use `--demo` / `--no-demo`.
- **Ports are compose constants** (§12): exporting `ORACLE_PORT` does not move the stack. The AI services are
  layered by hand, outside `sajag_up.sh` (§9).

---

## 2. Setting a variable

Run these from the repository root, as the user that owns the stack (never root).

```bash
# Create ~/.config/sajag/sajag.env (mode 600) from this host's detected paths.
# scripts/sajag_up.sh --install-units does this too, then links and enables the systemd units.
bash scripts/sajag_env.sh --write            # keeps an existing file
bash scripts/sajag_env.sh --write --force    # regenerates it, keeping every other line

# A non-secret value:
bash scripts/sajag_env.sh --set SAJAG_OSINT 1

# A secret: the value is read from standard input (typed without echo at a terminal),
# so it never appears in argv, the process list or shell history.
bash scripts/sajag_env.sh --set SAJAG_OPERATOR_PIN -
bash scripts/sajag_env.sh --set SAJAG_SESSION_SECRET -
bash scripts/sajag_env.sh --set SAJAG_CESIUM_ION_TOKEN -
bash scripts/sajag_env.sh --set POSTGIS_PASSWORD -

# A generated secret can be piped in, still never on a command line:
openssl rand -hex 32 | bash scripts/sajag_env.sh --set SAJAG_SESSION_SECRET -

# Show the effective non-secret environment and the compose invocation:
bash scripts/sajag_env.sh --print
```

Rules the helper enforces:

- A value must be **one unquoted token** (no whitespace, quotes, `$`, backtick or backslash), so the loader and
  systemd's `EnvironmentFile=` parser read it identically. `--set` refuses anything else.
- `--set` replaces the first `KEY=` line (dropping repeats) or appends one, keeping mode 600. For a key whose name
  contains `PASSWORD`, `TOKEN`, `SECRET` or `PIN` it prints only "KEY set"; a value from standard input is never
  printed.
- `--write --force` regenerates the recorded paths and carries over every other line, plus any persisted key (§4.2)
  only the calling shell carries.

**Applying a change.** Re-run `bash scripts/sajag_up.sh`: compose recreates every core container whose
configuration changed. A model-host variable needs that unit restarted (`systemctl --user restart
sajag-models.target`, or the single unit). An AI service picks up a change when its compose file is brought up
again (§9.1). A new PIN or session secret takes effect when the deck is recreated; rotating `SAJAG_SESSION_SECRET`
ends every open session.

**Never** paste a secret into a command line, a commit, an issue or a chat. Before a release,
`bash scripts/secret_scan.sh` checks the tree, the uncommitted diff and the commits a push would send for the literal
values of `SAJAG_OPERATOR_PIN`, `SAJAG_SESSION_SECRET` and `SAJAG_CESIUM_ION_TOKEN` (read from `sajag.env` at
run time) and for credential patterns. It prints locations and rule names, never a value.

---

## 3. Reading the tables

| Column | Meaning |
|---|---|
| **Variable** | The exact name. `<CONNECTOR>` marks a family of names. |
| **Secret** | **yes**: keep it in the mode-600 file only, set it with `--set KEY -`, never print it. |
| **Default** | The value used when you set nothing. **Deployed** is what the Sajag compose files or the bring-up set; **code** is the service's own fallback. Where they differ, both are given. |
| **What it does** | From the code and its comments. **Required** marks a value the stack does not work without; the reader is named when a table mixes components. |

"Truthy" flags accept `1`, `true`, `yes` or `on` (any case); "exactly `1`" flags accept nothing else.
"Pass-through" means a valueless compose entry (§1, layer 2).

---

## 4. Host environment file and bring-up

Read by `scripts/sajag_env.sh` (which the operator scripts source), `scripts/sajag_up.sh`,
`infra/scripts/serve_models.sh` and the systemd units.

### 4.1 Variables

| Variable | Secret | Default | What it does |
|---|---|---|---|
| `SAJAG_ROOT` | | the repository root holding `scripts/` (detected) | **Required** in `sajag.env` for boot (`--write` records it): the units start `${SAJAG_ROOT}/infra/scripts/serve_models.sh` and `${SAJAG_ROOT}/scripts/sajag_up.sh`. Those two scripts locate the tree from their own path |
| `SAJAG_ENV_FILE` | | `$HOME/.config/sajag/sajag.env` | The host file the scripts load and `--set` / `--write` edit (`sajag_env.sh`, `deck_session.sh`, `lib/deck_session.mjs`, `secret_scan.sh`, `demo_reset.sh`, `repetition_gate.sh`, `journeys.mjs`). The units and `--install-units` always use the fixed path |
| `SAJAG_RUN_DIR` | | `$SAJAG_ROOT/.run-models` | Runtime state: the bring-up lock, the road-network stamp and restart marker, model-host pid files |
| `SAJAG_LOG_DIR` | | `$SAJAG_RUN_DIR/logs` | Model-host and script logs |
| `SAJAG_VENV_DIR` | | `$SAJAG_ROOT/.venvs` | Persistent virtual environments `model-host`, `embedding`, `migrate` (`serve_models.sh build`) |
| `SAJAG_MODELS_CONFIG_DIR` | | `$SAJAG_ROOT/models-config` | Model-stack configuration directory and the embedding launcher |
| `SAJAG_MODELS_CONFIG` | | `$SAJAG_MODELS_CONFIG_DIR/configs/sajag_models.yaml` | The one model-stack configuration (endpoints, decider limits, memory budget), read by `serve_models.sh`, model-host, convoy-brain and the oracle's memory arbiter. No credentials |
| `SAJAG_COMPOSE_PROJECT` | | `sajag` | Compose project name |
| `SAJAG_DEMO` | | `0` | `1` = demo mode on every bring-up and reboot: signal-plan writer on, living city on (only while the deck's public feed labels emulated events). Set by `sajag_up.sh --demo` / `--no-demo` |
| `SAJAG_OSINT` | | `0` | Exactly `1` adds `infra/compose.osint-ingress.yml` and a 12th readiness component. Any other value is off, and a bring-up removes a stale `sajag-osint-ingress` container |
| `SAJAG_CONVERGE_TIMEOUT` | | `600` (seconds) | How long the bring-up waits for every component (`--timeout` overrides) |
| `SAJAG_MIGRATE_PY` | | the first Python with `psycopg` among this, `$SAJAG_VENV_DIR/migrate/bin/python`, `$SAJAG_ROOT/.venvs/migrate/bin/python`; else one is built | Interpreter for `scripts/migrate.py`; also read by `scripts/gen_ingress_segments.py` |
| `POSTGIS_CONTAINER`, `VALKEY_CONTAINER`, `NATS_CONTAINER`, `INGRESS_CONTAINER`, `ORACLE_CONTAINER`, `BRAIN_CONTAINER`, `DECK_CONTAINER`, `EMULATOR_CONTAINER`, `OSINT_CONTAINER` | | `sajag-postgis`, `sajag-valkey`, `sajag-nats`, `sajag-signal-ingress`, `sajag-traffic-oracle`, `sajag-convoy-brain`, `sajag-command-deck`, `sajag-event-emulator`, `sajag-osint-ingress` | Container names the scripts inspect (deployed names: `compose.argus-override.yml`). `scripts/migrate.py` alone defaults `POSTGIS_CONTAINER` to `vvip-postgis`; the bring-up passes the Sajag name |

The units set their own `PATH`. For them to start at boot without a login, enable lingering once:
`loginctl enable-linger <user>` (`--install-units` warns when it is off).

### 4.2 The two key lists in `sajag_env.sh`

**`SAJAG_ENV_KEYS`**, recorded by `--write` and shown by `--print`: `SAJAG_ROOT`, `SAJAG_RUN_DIR`,
`SAJAG_LOG_DIR`, `SAJAG_VENV_DIR`, `SAJAG_MODELS_CONFIG`, `POSTGIS_HOST_PORT`, `DECIDER_SNAPSHOT_PATH`,
`LLAMA_SERVER_BIN`, `GEMMA_GGUF`, `BGE_M3_PATH`, `SAJAG_DEMO`, `SAJAG_OSINT`, `SAJAG_CONVERGE_TIMEOUT`.

**`SAJAG_PERSIST_KEYS`**, values compose interpolates that must survive a reboot. `--write` keeps them (from
`sajag.env`, or from the shell when only it has them) and a bring-up warns when the shell carries one `sajag.env`
lacks.

| Group | Keys |
|---|---|
| Interpolated values | `SAJAG_OPERATOR_PIN`, `SAJAG_SESSION_SECRET`, `SAJAG_SESSION_SECURE`, `SAJAG_CESIUM_ION_TOKEN`, `POSTGIS_PASSWORD`, `VVIP_ESCORT_SIM_GPS`, `VVIP_REQUIRE_OFFICER`, `EMULATOR_LIVING_VIOLATORS`, `EMULATOR_CITY_SEED`, `OSINT_MODE` |
| Pass-through flags | `VVIP_ACCEPT_LIVE_ANPR`, `VVIP_ADAPTIVE_ROBUST_INPUTS`, `VVIP_ESCORT_SIM_SPEED_KMH`, `VVIP_ESCORT_GPS_TIMEOUT_SEC`, `VVIP_ESCORT_APPROVAL_TIMEOUT_SEC`, `VVIP_CONFIDENCE_FLOOR`, `DECIDER_TIER0_DISABLE`, `INGRESS_CITY_SEED` |

The AI services' interpolations (`SAJAG_FORECAST_MODEL`, `SAJAG_FORECAST_DATA_SOURCE`, `SAJAG_ORACLE_PORT`,
`SAJAG_TWIN_LLM`) are not on this list: write them to `sajag.env` yourself and bring those services up from a
shell that has loaded it (§9.1).

---

## 5. Operator gate and sessions

Read by the command-deck (`src/lib/shell/operator-session.server.ts`, `src/routes/api/session/+server.ts`), passed
in by `infra/compose.argus-override.yml`.

| Variable | Secret | Default | What it does |
|---|---|---|---|
| `SAJAG_OPERATOR_PIN` | yes | empty: **gate off** | **Required** for any deck reachable from a network. Officers sign in with their name and this duty PIN (a `<six-digit PIN>` or longer); without a session every gated proxied call is refused (403). With the gate off, `sajag_up.sh --status` marks a deck reachable beyond loopback DEGRADED. Also read by `deck_session.sh`, `lib/deck_session.mjs`, `secret_scan.sh` |
| `SAJAG_SESSION_SECRET` | yes | empty: 32 random bytes per deck process | **Recommended** with the gate on. HMAC-SHA256 key of the 12-hour `sajag_operator` session cookie; unset, every deck restart signs everyone out. Sign-out revocations live in the deck process only, so rotating this secret is how to end every session at once |
| `SAJAG_SESSION_SECURE` | | empty (off) | Exactly `1` sets the cookie's `Secure` flag. Only behind TLS: on plain HTTP a secure cookie never comes back and nobody can sign in |

Fixed in code, not configurable:

- Failed PINs are throttled at 8 per 5 minutes per client; the PIN comparison is constant-time. Officer names are 2
  to 64 printable characters without bidirectional controls.
- The gate covers the proxied prefixes `/api/v1`, `/api/traffic`, `/api/convoy` and `/api/emulator`. On them an
  anonymous caller may reach only the road geometry (`GET /api/v1/spatial/segments`), two liveness probes
  (`/api/convoy/health`, `/api/emulator/health`) and the ambulance (108) dispatch request, capped at 6 per client per
  10 minutes and only ever a request a named officer must approve.
- The oracle's machine-ingest path is refused through the deck for every caller, signed in or not.

- The AI prefixes `/api/speech`, `/api/forecast`, `/api/vision`, `/api/hydro` and `/api/twin` are gated the same way
  (`src/lib/ai/gate.server.ts`), with a short public allow-list for the citizen page: `GET` of the hydro nowcast,
  tide and rain (no forced refresh), and `POST /api/speech/speech/speak` with a JSON `text` of at most 400
  characters, at most 10 requests per client per minute. Transcription, field reports, vision, the twin, forecasts,
  the replay and every proposal need a signed-in officer.

---

## 6. Maps and imagery

| Variable | Secret | Default | What it does |
|---|---|---|---|
| `SAJAG_CESIUM_ION_TOKEN` | yes | empty: keyless everywhere | Cesium ion access token, served by the deck's `GET /gods-eye/mode`. With the gate on, only a signed-in session receives it (Google Photorealistic 3D Tiles, Cesium World Terrain and Bing aerial imagery through ion); an anonymous caller gets the keyless OpenStreetMap mode. **With the gate off, any caller of `/gods-eye/mode` receives the token**: keep the gate on whenever it is set. It spends your ion quota. Also read by `secret_scan.sh` |
| `DATA_GOV_IN_API_KEY` | yes | empty: off, health says `needs DATA_GOV_IN_API_KEY` | City feeds (`services/cityfeeds`, read from the environment by this exact name): CPCB real-time AQI from data.gov.in, the stations' OBSERVED pollutant averages beside the MODELLED air values. Free: <https://data.gov.in/> (sign in; the key is under My Account). See `docs/DATA_SOURCES.md` |
| `WAQI_TOKEN` | yes | empty: off, `needs WAQI_TOKEN` | City feeds: World Air Quality Index station AQI (OBSERVED, US EPA scale). Free: <https://aqicn.org/data-platform/token/> |
| `OPENAQ_API_KEY` | yes | empty: off, `needs OPENAQ_API_KEY` | City feeds: OpenAQ v3 latest station PM2.5 and PM10 (OBSERVED; sent as a header). Free: <https://explore.openaq.org/register> |
| `FIRMS_MAP_KEY` | yes | empty: the public FIRMS South Asia 24-h files are read instead (live, no key) | City feeds: NASA FIRMS area API for the city's box (a constant in `services/cityfeeds/src/cityfeeds/fires.py`; Mumbai's is 18.89–19.28 N, 72.77–72.99 E), last 2 days. Free: <https://firms.modaps.eosdis.nasa.gov/api/map_key/> |
| `MAPILLARY_TOKEN` | yes | empty: off, `needs MAPILLARY_TOKEN` | City feeds `GET /feeds/street-image`: the nearest public Mapillary photo to a junction (CC BY-SA 4.0, "Reference photo · not live"; sent as a header; never passed to the vision model). Free client token: <https://www.mapillary.com/dashboard/developers> |

With no token the canvas draws Sajag's own roads and entities over OpenStreetMap raster tiles; there is no other
map key.

---

## 7. Database and stores

| Variable | Secret | Default | What it does |
|---|---|---|---|
| `POSTGIS_PASSWORD` | yes | a development placeholder written in the compose files | **Recommended**: set your own before the first bring-up. Password of role `corridor_admin` on `corridor_db`: interpolated into PostGIS's `POSTGRES_PASSWORD` and the oracle's and emulator's database URLs, used by `sajag_up.sh` (migrations, seed) and `serve_models.sh` (embedding service). PostgreSQL applies it only when it initialises an empty volume; later, change the role's password in the database too |
| `VVIP_DATABASE_URL` | yes (holds the password) | Deployed: `postgresql://corridor_admin:${POSTGIS_PASSWORD}@127.0.0.1:15434/corridor_db` (oracle, emulator). Code: the oracle falls back to a local development URL on port 5432; the emulator has none and fails closed | Read by traffic-oracle, event-emulator, embedding-service and `scripts/migrate.py`. convoy-brain does not read it and reports it as ignored |
| `DATABASE_URL` | yes | unset | Fallback for `scripts/migrate.py` and the embedding service |
| `SAJAG_DATABASE_DSN` | yes | unset | Embedding service's first choice (then `VVIP_DATABASE_URL`, then `DATABASE_URL`) |
| `EMBEDDING_DATABASE_URL` | yes | built from `POSTGIS_PASSWORD` and `POSTGIS_HOST_PORT` | `serve_models.sh`: overrides the URL it passes to the embedding service as `VVIP_DATABASE_URL` |
| `VVIP_VALKEY_URL` | | Deployed: `redis://127.0.0.1:6390`. Code: `redis://localhost:6379` | Valkey URL of traffic-oracle, convoy-brain and event-emulator |
| `VALKEY_URL` | | unset | convoy-brain's fallback Valkey URL |
| `VVIP_NATS_URL` | | Deployed: `nats://127.0.0.1:4233`. Code: `nats://localhost:4222` | NATS URL (live data plane) of the oracle and the emulator |
| `NATS_URL` | | Deployed: `nats://nats:4222` (the Sajag NATS by service name on the project network). Code: `nats://localhost:4222` | NATS URL signal-ingress publishes to |
| `VVIP_INGEST_ENABLED` | | `true` | traffic-oracle: `false` keeps the NATS ingest off (`/health` says so) |
| `VVIP_INGEST_EMULATED` | | `true` | traffic-oracle: `false` drops only the emulator's subjects (`corridor.traffic.emulated`, `corridor.units.emulated`) |
| `VVIP_INGEST_FLUSH_INTERVAL_SEC`, `VVIP_INGEST_FLUSH_ROWS` | | `5.0`, `2000` | traffic-oracle: observation buffer flush interval and size (into `traffic.observations`) |
| `VVIP_OBSERVATION_RETENTION_DAYS` | | `14` | traffic-oracle: older daily `traffic.observations` partitions are dropped (at start-up and hourly) |

Fixed, not configurable: role `corridor_admin` and database `corridor_db`; Valkey `maxmemory 512mb` with
`allkeys-lfu`.

---

## 8. AI and model hosts

### 8.1 Model files and model-host processes

Read by `infra/scripts/serve_models.sh` (run in the foreground by the `sajag-decider`, `sajag-llama` and
`sajag-embed` units under `sajag-models.target`) and by the model services. Weights are supplied by the operator
and never committed. A host whose files are missing exits with status 78, which the units do not restart, so a
configuration error is reported once.

| Variable | Secret | Default | What it does |
|---|---|---|---|
| `DECIDER_SNAPSHOT_PATH` | | `serve_models.sh` and `--write`: the decider's snapshot directory in the local Hugging Face cache. model-host: `decider.snapshot_path` in `sajag_models.yaml` | **Required**: the 27B decider's weights (:8083). Load it by path; the snapshot's files link into the cache's blob store, so never copy the tree. An optional `~/.config/sajag/decider.env` (written by `services/model-host/switch_decider.sh`, read after `sajag.env`) overrides it with `DECIDER_SNAPSHOT_PATH`, `DECIDER_RUNTIME` and `DECIDER_QUESTION_MODE`; the live box serves `pplx-decider-v1.2` that way ([`docs/ai/decider.md`](ai/decider.md)) |
| `LLAMA_SERVER_BIN` | | `$HOME/llama.cpp/build/bin/llama-server` | **Required**: llama.cpp server binary of the tactical tier (:8084). `services/vision/scripts/serve_llm.sh` reads the same name. The live box points this, `VISION_LLAMA_SERVER_BIN` and `SPEECH_LLAMA_SERVER_BIN` at one llama.cpp build (c3df4b7, 28 Oct 2026; about 15 % faster Gemma generation than 69bf643 in an A/B on 29 Oct) |
| `GEMMA_GGUF` | | `$HOME/models/q4-stack/v7h-merged-Q4_K_M.gguf` | **Required**: the Gemma 4 12B Q4_K_M model the tactical tier serves |
| `GEMMA_CTX_PER_SLOT`, `GEMMA_PARALLEL_SLOTS` | | `8192`, `2` | Context tokens per llama slot and number of slots (total context = their product) |
| `BGE_M3_PATH` | | `--write` records `$HOME/models/bge-m3` when it exists; the service's own fallback is a fixed host path | **Required**: local `bge-m3` dense encoder of the embedding service (:8085) |
| `LATE_EMBED_MODEL` | | `perplexity-ai/pplx-embed-v2-late-0.6b` | Late-interaction (multi-vector) encoder |
| `AUX_LATE_EMBED_MODEL` | | empty (off) | Optional 9B auxiliary embedder slot |
| `MODEL_HOST_BIND`, `MODEL_HOST_LOG_LEVEL` | | `127.0.0.1`, `info` | Decider host bind address (keep loopback) and log level |
| `EMBEDDING_LISTEN_HOST`, `EMBEDDING_LISTEN_PORT` | | `127.0.0.1`, `8085` (`serve_models.sh` passes `EMBEDDING_PORT`) | Embedding service bind, read by the service and `models-config/embedding_launcher.py`; keep loopback |
| `HF_HUB_OFFLINE` | | forced to `1` by `serve_models.sh` for the decider, and by model-host when its configuration says offline (the default) | Keeps the model host off the Hugging Face hub |

### 8.2 Model endpoints and AI behaviour

| Variable | Secret | Default | What it does |
|---|---|---|---|
| `MODEL_HOST_URL` | | `http://127.0.0.1:8083` (deployed and code) | Decider endpoint (convoy-brain, `smoke_models.sh`, `bench_stack.sh`, `model_drift_panel.sh`). The brain resolves: this variable, then `services.model_host` in `sajag_models.yaml`, then the default. Plain http(s) on loopback or `host.docker.internal` only |
| `LLAMA_BASE_URL` | | `http://127.0.0.1:8084` | Tactical LLM endpoint; same resolution and rules. model-host reads it for readiness only |
| `EMBEDDING_SERVICE_URL` | | `http://127.0.0.1:8085` | Embedding endpoint for the brain, model-host (readiness), the embedding client and the smoke scripts. Compose also passes it to the oracle, which does not read it |
| `TRAFFIC_ORACLE_URL` | | Deployed: `http://127.0.0.1:8191`. Code: `http://127.0.0.1:8081` | The oracle the brain calls. Resolution: this variable, then `http://127.0.0.1:$ORACLE_PORT`, then `services.traffic_oracle` in `sajag_models.yaml`, then the code default (logged). Loopback only |
| `VVIP_CONFIDENCE_FLOOR` | | `0.45` | Pass-through, convoy-brain: below it a decider answer becomes a tactical draft plus an operator alert, never an action. Calibrated 2026-10-19; do not lower it without new measurements |
| `DECIDER_TIER0_DISABLE` | | unset (cache on) | Pass-through, convoy-brain: `1` or `true` turns off the tier-0 cache for routine checkpoints; `/health` reports it |
| `VVIP_MEMORY_RECORD` | | on | convoy-brain: `0`, `false`, `no` or `off` stops filing checkpoints into the decision-memory corpus (searches still run). Sandbox and test brains must set it off |
| `VVIP_FOUNDATION_MODEL_PATH` | | Deployed: the oracle image's baked t0-alpha ONNX artifact. Code: unset (rung dormant) | traffic-oracle: zero-shot foundation rung of the forecast ladder |
| `VVIP_ONNX_MODEL_PATH` | | `models/onnx/flow_forecaster.onnx` | traffic-oracle: an exported DSTGAT forecaster; absent, that rung stays dormant |
| `VVIP_FORECAST_SUPPORT_BOUNDS_PATH` | | the package's committed `support_bounds.json` | traffic-oracle: bounds that keep out-of-range inputs away from every model rung |
| `SAJAG_UNIFIED_BUDGET_MB` | | unset: the budget in `sajag_models.yaml`, else `MemTotal`, else 121440 MiB | traffic-oracle (`runtime/gpu_arbiter.py`): unified-memory budget override |
| `SAJAG_TWIN_USE_CASES` | | the oracle's bundled `use_case_scenarios.json` | traffic-oracle (`simulation/scenarios.py`): use-case file of the oracle's corridor twin (not the twin service, §9.6) |
| `OMP_NUM_THREADS`, `MKL_NUM_THREADS`, `OPENBLAS_NUM_THREADS`, `NUMEXPR_NUM_THREADS` | | `4` each, when unset | traffic-oracle: math-library thread pools |

---

## 9. AI services: speech, forecast, vision, hydro, twin

### 9.1 Running them

The five on-premises AI services compute and propose; none writes city state and none reads a secret. `sajag_up.sh`
neither starts nor checks them: bring them up with their own compose files, from a shell that has loaded
`sajag.env`.

| Service | Compose file | Deployed bind | Upstreams | Memory |
|---|---|---|---|---|
| speech | `infra/compose.ai-media.yml` | 127.0.0.1:8194 (published; binds 0.0.0.0 inside its container) | GPU; host Hugging Face cache, read-only | 20G |
| forecast | `infra/compose.ai.yml` | 127.0.0.1:8195 (host network) | oracle :8191 (GET only), hydro :8197; GPU; host Hugging Face cache | 6G |
| vision | `infra/compose.ai-media.yml` | 127.0.0.1:8196 (host network) | the host's Qwen3-VL llama-server, 127.0.0.1:8201 | 1G |
| hydro | `infra/compose.ai.yml` | 127.0.0.1:8197 (host network) | Open-Meteo (no key; cached, rate-limited) | 512M |
| twin | `infra/compose.twin.yml` | 127.0.0.1:8198 (host network) | oracle :8191 (GET only); tactical LLM :8084, for wording only | 768M |

```bash
. scripts/sajag_env.sh     # load sajag.env into this shell first

docker compose -p sajag -f infra/compose.yml -f infra/compose.gb10-override.yml \
  -f infra/compose.argus-override.yml -f infra/compose.ai.yml up -d forecast hydro

bash services/vision/scripts/serve_llm.sh start      # vision's model server, 127.0.0.1:8201
docker compose -p sajag -f infra/compose.yml -f infra/compose.ai-media.yml up -d speech vision

docker compose -p sajag -f infra/compose.yml -f infra/compose.gb10-override.yml \
  -f infra/compose.argus-override.yml -f infra/compose.twin.yml up -d twin
```

These are the invocations the compose files' headers give. The same services can also run as systemd user units
from the checkout (`infra/systemd/sajag-ai-*.service` under `sajag-ai.target`, plus `sajag-feeds.service` for the
city feeds on 127.0.0.1:8199); those read `sajag.env` and set only their ports and upstreams, so the City Pack
variables whose code default still names the Kolkata reference pack (`SAJAG_CITY` for the twin,
`SAJAG_HYDRO_CITY_DIR`) must be in `sajag.env` for them to serve Mumbai (§16). Check `free -g` first: speech and vision refuse a model
load below their `*_MIN_FREE_GIB` floor and answer 503. The deck reaches each service through `/api/speech`,
`/api/forecast`, `/api/vision`, `/api/hydro` and `/api/twin` (prefix stripped; port variables in §12.2); a service
that is not running answers 502 through the proxy. The service READMEs run development copies on other loopback ports
by setting the same variables (for example `PORT=9151` for forecast); nothing in the code defaults to those ports.

### 9.2 Speech (`services/speech`, prefix `SPEECH_`)

Models load on first use and unload when idle. The container sets `HF_HOME=/hf` and `HF_HUB_OFFLINE=1`: nothing is
downloaded at run time.

| Variable | Secret | Default | What it does |
|---|---|---|---|
| `SPEECH_HOST`, `SPEECH_PORT` | | Code: `127.0.0.1`, `8194`. Deployed: `0.0.0.0` inside the container, published on 127.0.0.1:8194 | Bind address and port |
| `SPEECH_DECK_ORIGINS` | | empty | CORS origins, comma-separated; none needed, the deck proxies |
| `SPEECH_ASR_BACKEND` | | `indic_conformer` | Which recogniser answers the Indic languages (`SPEECH_ASR_INDIC_LANGS`): `indic_conformer` (AI4Bharat IndicConformer 600M multilingual, gated on Hugging Face), with `SPEECH_ASR_MODEL` taking over automatically while it cannot load; or `whisper` (`SPEECH_ASR_MODEL` answers them directly) |
| `SPEECH_ASR_INDIC_LANGS` | | `mr,hi` | Languages sent to the Indic backend: Marathi and Hindi |
| `SPEECH_ASR_MODEL` | | `openai/whisper-large-v3` | The Whisper fallback (or, with `whisper`, the recogniser) for Marathi and Hindi. See [`ai/speech.md`](ai/speech.md) for the checkpoints compared |
| `SPEECH_ASR_INDIC_CONFORMER_MODEL`, `SPEECH_ASR_INDIC_CONFORMER_DECODER`, `SPEECH_ASR_INDIC_CONFORMER_REVISION` | | `ai4bharat/indic-conformer-600m-multilingual`, `ctc` (or `rnnt`), `2a77d305038dfc502fd9464e7d028b90381976cb` (the commit reviewed on 29 Oct 2026) | The `indic_conformer` backend. The model runs its own code, so the revision pins the reviewed commit; the adapter refuses assets from any other commit. Empty means the repository's main branch |
| `SPEECH_ASR_MULTILINGUAL_MODEL` | | `openai/whisper-large-v3-turbo` | English recognition and `lang=auto` language detection |
| `SPEECH_ASR_BEAMS` | | `1` | Recognition beam width |
| `SPEECH_TTS_BACKEND` | | Code: `auto`. Deployed (container): `transformers` | `indic_parler` (AI4Bharat Indic Parler-TTS: Marathi, Hindi and English voices; gated, with the Svara backends taking over while it cannot load), `llama` (Svara GGUF in llama.cpp), `transformers` (Svara in transformers), or `auto` (llama when the GGUF and `llama-server` exist). The container ships no llama.cpp |
| `SPEECH_TTS_PARLER_MODEL`, `SPEECH_TTS_PARLER_REVISION` | | `ai4bharat/indic-parler-tts`, empty (main branch; offline, whatever commit the cache holds) | The Parler checkpoint; pin the evaluated commit |
| `SPEECH_TTS_PARLER_PYTHON` | | empty: Parler loads in the service's own process | Python of a separate venv for Parler (parler-tts pins its own transformers version) |
| `SPEECH_TTS_PARLER_DESCRIPTION` | | a calm, clear public-advisory caption with a `{speaker}` slot | Parler's voice caption; `{speaker}` becomes the language's recommended voice |
| `SPEECH_TTS_GGUF`, `SPEECH_LLAMA_SERVER_BIN` | | `~/.cache/sajag/svara-gguf/svara-tts-v1-q8_0.gguf`, `~/llama.cpp/build/bin/llama-server` | Files of the llama.cpp backend (`services/speech/scripts/convert_svara_gguf.sh` writes the GGUF) |
| `SPEECH_TTS_LLM_PORT` | | `8202` | Loopback port of the TTS llama-server the service starts at the first `/speech/speak` and stops when it unloads |
| `SPEECH_TTS_LLM_MANAGE`, `SPEECH_TTS_LLM_URL` | | `true`, empty | `false` starts no server and uses the one at the URL instead |
| `SPEECH_TTS_MODEL`, `SPEECH_TTS_CODEC` | | `kenpath/svara-tts-v1`, the SNAC 24 kHz codec checkpoint (`snac_24khz`) | Speech-synthesis model and audio codec |
| `SPEECH_TTS_STYLE_TAG`, `SPEECH_TTS_SEED` | | `<clear>`, `1847` | Style tag asked of the voice; sampling seed |
| `SPEECH_TTS_CACHE_DIR` | | Code: `~/.cache/sajag/speech-tts`. Deployed: `/cache/tts` (a volume) | Advisory audio cache |
| `SPEECH_TTS_MAX_CHARS` | | `600` | Longest text one request may synthesise; longer is refused (413) |
| `SPEECH_DEVICE`, `SPEECH_IDLE_UNLOAD_S` | | `cuda`, `600` | Inference device; unload the models after this many idle seconds |
| `SPEECH_MIN_FREE_GIB` | | `12.0` | Refuse (503) a load that would leave less available memory |
| `SPEECH_MAX_AUDIO_BYTES`, `SPEECH_MAX_AUDIO_SECONDS` | | `8388608` (8 MB), `60.0` | Upload limits |
| `SPEECH_CITY_DIR`, `SPEECH_GAZETTEER_FILE` | | Code: `cities/<SAJAG_CITY>` of the checkout, `SAJAG_CITY` defaulting to `mumbai` here, else `/app/cities/<city>`. Deployed: `/app/cities/mumbai` (mounted read-only); `gazetteer.json` | Where `landmarks.json` (Mumbai place ids and their English, Marathi and Hindi names) and the optional gazetteer are read |
| `SPEECH_PLACE_THRESHOLD` | | `0.80` | Minimum match score to assert a place from a report |

### 9.3 Forecast (`services/forecast`, prefix `SAJAG_FORECAST_`)

Unprefixed `HOST` and `PORT` override the prefixed ones. The image sets `HF_HUB_OFFLINE=1`; weights come from the
host's Hugging Face cache, mounted read-only.

| Variable | Secret | Default | What it does |
|---|---|---|---|
| `HOST`, `PORT` | | `127.0.0.1`, `8195` | Bind address and port (also `SAJAG_FORECAST_HOST` / `_PORT`) |
| `SAJAG_FORECAST_DECK_ORIGINS_CSV` | | `http://127.0.0.1:5373,http://localhost:5373` (deployed and code) | CORS origins; overrides `SAJAG_FORECAST_DECK_ORIGINS` (a JSON list) |
| `SAJAG_FORECAST_ORACLE_URL` | | Deployed: `http://127.0.0.1:${SAJAG_ORACLE_PORT:-8191}`. Code: `http://127.0.0.1:8191` | The oracle, read with GETs only |
| `SAJAG_ORACLE_PORT` | | `8191` | Compose interpolation in `compose.ai.yml` only; not the scripts' `ORACLE_PORT` |
| `SAJAG_FORECAST_HYDRO_URL`, `SAJAG_FORECAST_HTTP_TIMEOUT_SEC` | | `http://127.0.0.1:8197`, `8.0` | The hydro service; upstream timeout |
| `SAJAG_FORECAST_DATA_SOURCE` | | `auto` (compose interpolates the same) | `auto`: the oracle's history where a segment has enough, else the deterministic synthetic Mumbai history (festival nights, the visarjan procession, stadium egress, monsoon storms at the flood spots) labelled SIMULATED; `oracle`; `synthetic` |
| `SAJAG_FORECAST_MIN_ORACLE_STEPS` | | `192` (two days of 15-minute steps) | History a segment needs before it is forecast from the oracle |
| `SAJAG_FORECAST_CITY_DIR` | | empty: `cities/mumbai` of the checkout, else the snapshot bundled with the package (`data/mumbai_network.json`) | City Pack folder holding `network.json` |
| `SAJAG_FORECAST_CITY_BBOX` | | `[72.77, 18.89, 72.99, 19.28]` (the `bbox` of `cities/mumbai/city.json`) | `(min_lon, min_lat, max_lon, max_lat)` as a JSON list. Only oracle segments inside it are read, so a store seeded with another city's network is never taken for Mumbai history |
| `SAJAG_FORECAST_MODEL` | | `chronos2` (compose interpolates the same) | `chronos2`, `timesfm` or `naive` |
| `SAJAG_FORECAST_CHRONOS_MODEL_ID`, `SAJAG_FORECAST_TIMESFM_MODEL_ID` | | `amazon/chronos-2`, `google/timesfm-2.5-200m-pytorch` | Checkpoints |
| `SAJAG_FORECAST_CONTENDER` | | `timesfm` | Second model of the backtest; empty skips it |
| `SAJAG_FORECAST_DEVICE`, `SAJAG_FORECAST_DTYPE` | | `auto`, `float32` | `auto`, `cuda` or `cpu`; `float32` or `bfloat16` (half the weights' GPU memory) |
| `SAJAG_FORECAST_IDLE_UNLOAD_SEC` | | `600.0` (compose sets `600`) | Free the model after this many idle seconds |
| `SAJAG_FORECAST_CONTEXT_DAYS`, `SAJAG_FORECAST_STEP_MIN` | | `14`, `15` | History window; time step in minutes |
| `SAJAG_FORECAST_VC_THRESHOLD` | | `0.8` | Median volume-to-capacity ratio at which a forecast becomes a crossing and a proposal |
| `SAJAG_FORECAST_CACHE_TTL_SEC` | | `300.0` | Older forecasts are recomputed on request |
| `SAJAG_FORECAST_SYNTHETIC_SEED` | | `1853` (the year India's first passenger train ran, Bori Bunder to Thane) | Seed of the synthetic history |
| `SAJAG_FORECAST_BACKTEST_DAYS`, `SAJAG_FORECAST_BACKTEST_STRIDE_HOURS` | | `3`, `6` | Backtest length and stride |

### 9.4 Vision (`services/vision`, prefix `VISION_`)

Road state (vehicles and roads only) from an uploaded image; the image is downscaled and re-encoded, which drops its
metadata, and is never written to disk.

| Variable | Secret | Default | What it does |
|---|---|---|---|
| `VISION_HOST`, `VISION_PORT` | | `127.0.0.1`, `8196` | Bind address and port |
| `VISION_DECK_ORIGINS` | | empty | CORS origins; none needed, the deck proxies |
| `VISION_LLM_MANAGE` | | Code: `true`. Deployed: `0` | `true`: the service starts its own llama-server on `VISION_LLM_PORT` at the first request (after a memory check) and stops it when idle. `0`: it uses `VISION_LLM_URL`, the compose layout where the host runs the model |
| `VISION_LLM_URL`, `VISION_LLM_PORT` | | `http://127.0.0.1:8201`, `8201` | External model server; port of a managed one |
| `VISION_LLAMA_SERVER_BIN`, `VISION_MODEL_PATH`, `VISION_MMPROJ_PATH` | | `~/llama.cpp/build/bin/llama-server`; `Qwen3VL-8B-Instruct-Q4_K_M.gguf` and `mmproj-Qwen3VL-8B-Instruct-F16.gguf` in `~/models/qwen3-vl-8b/` | Files of a managed server |
| `VISION_MODEL_NAME` | | `Qwen3-VL-8B-Instruct (Q4_K_M GGUF, llama.cpp)` | Model label the service reports |
| `VISION_CTX_SIZE`, `VISION_GPU_LAYERS` | | `8192`, `99` | Context and GPU-offloaded layers of a managed server |
| `VISION_LLM_START_TIMEOUT_S`, `VISION_LLM_REQUEST_TIMEOUT_S` | | `240.0`, `180.0` | Wait for a managed server to be healthy; per-request timeout |
| `VISION_IDLE_UNLOAD_S` | | `600` | Stop a managed server after this many idle seconds |
| `VISION_NEED_GIB`, `VISION_MIN_FREE_GIB` | | `8.0`, `12.0` | The model's memory, and the floor kept free on top of it; below that a load is refused (503) |
| `VISION_MAX_IMAGE_BYTES`, `VISION_MAX_SIDE` | | `12582912` (12 MB), `1024` | Upload limit; longest side (pixels) after downscaling |

`services/vision/scripts/serve_llm.sh`, the host-side server of the compose layout, reads its own names: the port from
its second argument, else `VISION_LLM_PORT` (`8201`); `LLAMA_SERVER_BIN`; `VISION_MODEL_DIR` (`$HOME/models/qwen3-vl-8b`,
holding both GGUF files); `XDG_RUNTIME_DIR` for its pid file (`/tmp` when unset). It binds 127.0.0.1 only and refuses
to start below 20 GiB of available memory.

### 9.5 Hydro (`services/hydro`, prefix `SAJAG_HYDRO_`)

The waterlogging nowcast. Unprefixed `HOST` and `PORT` override the prefixed ones. Open-Meteo needs no key.

| Variable | Secret | Default | What it does |
|---|---|---|---|
| `HOST`, `PORT` | | `127.0.0.1`, `8197` | Bind address and port (also `SAJAG_HYDRO_HOST` / `_PORT`) |
| `SAJAG_HYDRO_DECK_ORIGINS` | | `["http://127.0.0.1:5373", "http://localhost:5373"]` | CORS origins (JSON list) |
| `SAJAG_HYDRO_OPEN_METEO_FORECAST_URL`, `SAJAG_HYDRO_OPEN_METEO_ARCHIVE_URL` | | `https://api.open-meteo.com/v1/forecast`, `https://archive-api.open-meteo.com/v1/archive` | Rain nowcast and history sources |
| `SAJAG_HYDRO_HTTP_TIMEOUT_SEC` | | `15.0` | Outbound timeout |
| `SAJAG_HYDRO_RAIN_CACHE_SEC`, `SAJAG_HYDRO_MIN_CALL_INTERVAL_SEC`, `SAJAG_HYDRO_MAX_CALLS_PER_DAY` | | `600.0`, `30.0`, `2000` (compose sets the same) | Rain cache lifetime; at most one call per interval; daily cap |
| `SAJAG_HYDRO_OFFLINE` | | `false` | `true` makes no outbound call; rain is then reported UNAVAILABLE, and says so |
| `SAJAG_HYDRO_CITY_DIR` | | empty: `cities/kolkata` of the checkout (the code still defaults to the Kolkata reference pack), else the bundled snapshot | City Pack folder holding `network.json`. **For Mumbai set it** to the absolute path of `cities/mumbai` |
| `SAJAG_HYDRO_STEP_MIN`, `SAJAG_HYDRO_HORIZON_MIN` | | `15`, `120` | Time step; nowcast lead-time window (minutes) |

### 9.6 Twin (`services/twin`)

A cell-transmission model of the City Pack's road network: every AI signal proposal is simulated against "do
nothing" before an officer sees it. It never writes a signal.

| Variable | Secret | Default | What it does |
|---|---|---|---|
| `SAJAG_TWIN_HOST`, `SAJAG_TWIN_PORT` | | `127.0.0.1`, `8198` | Bind address and port |
| `SAJAG_TWIN_NETWORK` | | Code: the repository's `cities/<city>/network.json`, else `scripts/data/osm_network.json`, else the image copy. Deployed (compose) and image: `/app/cities/mumbai/network.json` | Road network JSON |
| `SAJAG_CITY` | | twin, `impact_run.py`, `poi_route_matrix.py`: `kolkata` (the code default still names the reference pack); speech and `gen_osm_network.py`: `mumbai` | City Pack used when `SAJAG_TWIN_NETWORK` is unset (also read by the city scripts, §14, and by speech when `SPEECH_CITY_DIR` is unset). **Set `SAJAG_CITY=mumbai` in `sajag.env`** so the twin's systemd unit, which passes no network path, reads `cities/mumbai/network.json` |
| `SAJAG_TWIN_ORACLE_URL` | | `http://127.0.0.1:8191` | Live traffic state, GETs only; empty turns it off. Any failure falls back to the SIMULATED profile, labelled |
| `SAJAG_TWIN_LLM_URL`, `SAJAG_TWIN_LLM_MODEL` | | `http://127.0.0.1:8084`, unset | Local OpenAI-compatible LLM that words a rationale (one call at a time, 20 s timeout); optional model name |
| `SAJAG_TWIN_LLM` | | `1` (compose interpolates `${SAJAG_TWIN_LLM:-1}`) | Truthy: LLM-worded rationales; `0` keeps them to templates |

---

## 10. OSINT

The OSINT event-intelligence service runs only with `SAJAG_OSINT=1` (§4) and reads no secret. Events are about
places and situations, never persons: names and ages are redacted at parse. Tuning settings take the `OSINT_` prefix;
the contract variables are read by their exact names (`osint_ingress/config.py`).

| Variable | Secret | Default | What it does |
|---|---|---|---|
| `OSINT_MODE` | | `live` | Compose interpolation. `live` fetches on schedule from the allow-listed hosts; `offline` (no internet) parses only the newest cached capture of each source, labelled `cached-sample`. Persist it in `sajag.env` |
| `OSINT_ORACLE_URL` | | Deployed: `http://127.0.0.1:8191`. Code and image: `http://127.0.0.1:9` (the discard port) | Where redacted signals are posted; loopback only (`127.0.0.1`, `localhost`, `::1`). At the discard port a run posts nowhere and its batches wait in the outbox |
| `OSINT_CACHE_DIR` | | `/var/cache/osint-ingress` (the `osint_cache` volume) | Capture cache |
| `OSINT_GAZETTEER_PATH` | | the repository's `scripts/data/osint_gazetteer.json`, else the image path | Place gazetteer (osint-ingress, osint-common, osint-geo, also inside the oracle). A set but missing path is an error, never silently replaced |
| `OSINT_NETWORK_PATH` | | the repository's `scripts/data/osm_network.json`, else the image path | osint-geo (ingress and oracle): the road network places snap to; same rule |
| `OSINT_CADENCE_<CONNECTOR>_SEC` | | `SACHET_CAP` 300, `GOOGLE_NEWS_RSS` 600, `GDELT_EVENTS` 900, `GDELT_DOC` 1800 (a throttle backs it off further, up to 2 h), `REDDIT_RSS` 900, the three official-page scrapers 3600, `COMMON_CRAWL` 0 | Per-connector schedule (`<CONNECTOR>` = upper-cased name in `CONNECTOR_NAMES`). `0` unschedules; 1 to 59 is raised to 60; a non-integer is ignored. Common Crawl is backfill only |
| `OSINT_JITTER` | | `0.1` (0 to 0.5) | Plus-or-minus fraction applied to each cadence |
| `OSINT_PROBE_INTERVAL_SEC`, `OSINT_PROBE_TIMEOUT_SEC` | | `30` (at most 30), `2` (at most 10) | Oracle reachability probe |
| `OSINT_RETENTION_HOURS`, `OSINT_RETENTION_BYTES` | | `72`, `209715200` (200 MB) | Cache limits (the newest capture of each connector is always kept) |
| `OSINT_BATCH_SIZE`, `OSINT_PUBLISH_RETRIES`, `OSINT_PUBLISH_BACKOFF_SEC` | | `200` (1 to 200), `3` (1 to 10), `0.5` (0 to 30) | Posting to the oracle |
| `OSINT_HTTP_TIMEOUT_SEC` | | `25` (at most 120) | Source fetch timeout |
| `PROJ_NETWORK` | | `OFF` (compose and image) | Keeps pyproj from downloading grids, so the source allow-list stays the only egress |

The egress allow-list itself is code (`osint_ingress/safe_http.py` `ALLOWED_HOSTS`, shown on `GET /health`). Three
official-page scrapers belong to the Kolkata reference pack and carry its names; read their exact names, and so
their cadence variables, in `CONNECTOR_NAMES`. Which sources Sajag reads for Mumbai, and which official pages were
checked and not read, is in [`DATA_SOURCES.md`](DATA_SOURCES.md) §2.

---

## 11. Emulator and demo

Emulated data is labelled on every surface (`EMULATED`, `SIMULATED`).

| Variable | Secret | Default | What it does |
|---|---|---|---|
| `EMULATOR_LIVING_CITY` | | `0` | event-emulator, truthy: start the ambient living city (a deterministic day program of emulated causes) at boot. Set by `sajag_up.sh` from `SAJAG_DEMO` on every bring-up, and held off unless the deck's public feed labels emulated events |
| `EMULATOR_LIVING_VIOLATORS` | | `1` | event-emulator: `0` stops the living city's rare deliberate violators (each only a PENDING e-challan recommendation for a named officer, never a fine) |
| `EMULATOR_CITY_SEED` | | `1411` | event-emulator: seed of the day program |
| `EMULATOR_TRAFFIC_ORACLE_URL` | | Deployed: `http://localhost:8191`. Code: `http://localhost:8081` | The oracle the emulator drives; loopback or `host.docker.internal` only |
| `EMULATOR_DECK_ORIGINS` | | Deployed: `http://127.0.0.1:5373,http://localhost:5373`. Code: `127.0.0.1` and `localhost` on ports 5273 and 5173 | CORS origins, comma-separated `http(s)://host[:port]`; one malformed entry refuses the list |
| `VVIP_ESCORT_SIM_GPS` | | Deployed: `1`. Code: off | convoy-brain, truthy: no GPS hardware feeds the deployment, so an escort walks its approved route on emulated GPS (`emulated_gps`) and stops the moment real fixes arrive. `0` waits for real fixes and fails after the GPS timeout |
| `VVIP_ESCORT_SIM_SPEED_KMH` | | `80` (clamped 5 to 120) | Pass-through, convoy-brain: emulated cruise speed (each segment's limit also caps it) |
| `VVIP_ESCORT_GPS_TIMEOUT_SEC` | | `300` (clamped 10 to 3600) | Pass-through, convoy-brain: wait for a fix before the escort fails; a missing fix never completes one |
| `INGRESS_CITY_SEED` | | `0xA4D02026` (built in) | Pass-through, signal-ingress: seed of the synthetic traffic field (rows labelled `data_quality=synthetic`) |
| `ANOMALY_CONFIG_PATH` | | unset: the image copy `/etc/signal-ingress/anomaly_detector.yaml`, else the embedded file | signal-ingress: Tier-1 anomaly threshold file; an unusable file falls back with a warning |

The emulator's settings class has no prefix, so pydantic also accepts its bare field names (`HOST`, `PORT`,
`INPUTS_DOC_TTL_SEC` …). Only `HOST` and `PORT` are meant to be set that way.

---

## 12. Ports and binds

### 12.1 Deployed port map

The deployed ports are **constants in the compose files** (and `serve_models.sh` for the model hosts).
`sajag_up.sh` reads them from the rendered compose configuration and probes exactly those; a disagreeing shell
export only gets a warning.

| Component | Bind | Port |
|---|---|---|
| command-deck | **0.0.0.0**, the only LAN-facing bind | 5373 |
| event-emulator, traffic-oracle, convoy-brain, osint-ingress | 127.0.0.1 | 8190, 8191, 8192, 8193 |
| speech, forecast, vision, hydro, twin | 127.0.0.1 | 8194, 8195, 8196, 8197, 8198 |
| vision's Qwen3-VL llama-server; speech's TTS llama-server | 127.0.0.1 | 8201; 8202 |
| decider (model-host), tactical LLM (llama-server), embedding-service | 127.0.0.1 | 8083, 8084, 8085 |
| PostGIS, Valkey, NATS (monitoring) | 127.0.0.1 | 15434, 6390, 4233 (8233) |

### 12.2 Port and bind variables

| Variable | Secret | Default | What it does |
|---|---|---|---|
| `HOST` / `PORT` | | deployed values as in §12.1; code defaults in §12.3; the deck image's own default is `0.0.0.0` / `5173` | Bind address and port of the deck (adapter-node), oracle, brain, emulator, osint-ingress, forecast and hydro. Keep everything but the deck on loopback; the brain trusts the officer header only on a loopback connection |
| `SPEECH_HOST` / `SPEECH_PORT`, `VISION_HOST` / `VISION_PORT`, `SAJAG_TWIN_HOST` / `SAJAG_TWIN_PORT` | | §9 | The other AI services' bind names |
| `ORACLE_PORT` | | Deck code: `8091`. Deployed and `sajag_env.sh`: `8191`. `vite dev`: **none** | Deck proxy target on 127.0.0.1 for `/api/v1` and `/api/traffic`, and the `/gods-eye/feeds` probe; the host is fixed to loopback, only the port is configurable. convoy-brain builds its oracle URL from it when `TRAFFIC_ORACLE_URL` is unset |
| `BRAIN_PORT`, `EMULATOR_PORT` | | Deck code: `8092`, `8090`. Deployed and `sajag_env.sh`: `8192`, `8190`. `vite dev`: none | Deck proxy targets of `/api/convoy` and `/api/emulator` |
| `SPEECH_PORT`, `FORECAST_PORT`, `VISION_PORT`, `HYDRO_PORT`, `TWIN_PORT` | | Deck code: `8194` to `8198` (compose sets none). `vite dev`: proxied only when named | Deck proxy targets of the five AI prefixes. `SPEECH_PORT` is also the speech service's own listen port name |
| `DECK_PORT`, `OSINT_PORT` | | `5373`, `8193` (`sajag_env.sh`) | Ports the bring-up and scripts probe (see §12.3) |
| `MODEL_HOST_PORT`, `LLAMA_PORT`, `EMBEDDING_PORT` | | `8083`, `8084`, `8085` | Model-host ports (`serve_models.sh`, model-host, `sajag_up.sh`) |
| `POSTGIS_HOST_PORT` | | `15434` | PostGIS on loopback for host processes (migrations, seed, embedding service) |
| `VALKEY_HOST_PORT`, `NATS_HOST_PORT`, `NATS_MON_PORT` | | `6390`, `4233`, `8233` | Loopback ports the scripts probe |

For deck development outside Docker, `vite dev` refuses to start unless `ORACLE_PORT`, `BRAIN_PORT` and
`EMULATOR_PORT` name the backends: there is deliberately no default, so a development deck never reaches a running
stack by accident. It proxies an AI prefix only when its `*_PORT` is set, binds 127.0.0.1 only, and the gate,
authority pinning and CSP apply in production builds only.

### 12.3 Code defaults that differ from the deployment

Several code defaults are still the platform's earlier port set. The Sajag compose files and `sajag_env.sh`
override all of them, so the deployed stack is consistent; they matter when a process or script runs by hand without
the variables. Pass `HOST`, `PORT` and the URLs explicitly then.

| Where | Code default | Sajag value (set by) |
|---|---|---|
| Deck proxy `ORACLE_PORT` / `BRAIN_PORT` / `EMULATOR_PORT` (`src/hooks.server.ts`; `ORACLE_PORT` also `gods-eye/feeds`) | `8091` / `8092` / `8090` | `8191` / `8192` / `8190` (`compose.argus-override.yml`) |
| traffic-oracle `PORT` | `8081` | `8191` (compose) |
| convoy-brain `PORT`; its oracle URL | `8080`; port `8081` | `8192`; port `8191` (compose) |
| event-emulator `PORT`; `EMULATOR_TRAFFIC_ORACLE_URL`; `EMULATOR_DECK_ORIGINS` | `8090`; port `8081`; ports `5273`, `5173` | `8190`; port `8191`; port `5373` (compose) |
| osint-ingress `PORT` (and the image's `EXPOSE`) | `8093` | `8193` (`compose.osint-ingress.yml`) |
| embedding-service `TRAFFIC_ORACLE_URL` | port `8081` | not set; no code calls it (§15) |
| `serve_models.sh` `POSTGIS_HOST_PORT` fallback | `56434` | `15434`, from `sajag_env.sh`, which it sources first |
| `scripts/migrate.py` `POSTGIS_CONTAINER` | `vvip-postgis` | `sajag-postgis` (passed by the bring-up) |
| `verify_all.sh`, `journeys.mjs` (they do not source `sajag_env.sh`, so the PIN never reaches their children) | deck `5273`, oracle `8091`, brain `8092`, emulator `8090` | export `DECK_PORT=5373 ORACLE_PORT=8191 BRAIN_PORT=8192 EMULATOR_PORT=8190` (or the `*_URL` names) first |
| `impact_run.py` (`ORACLE_URL` / `ORACLE_PORT`), `poi_route_matrix.py` (`ORACLE`) | oracle `8091` | pass the Sajag oracle explicitly |
| speech `SPEECH_HOST`; `SPEECH_TTS_BACKEND` | `127.0.0.1`; `auto` | `0.0.0.0` in the container, published on loopback; `transformers` (`compose.ai-media.yml`) |
| vision `VISION_LLM_MANAGE` | `true` (starts its own model server) | `0`: the host server on 8201 (`compose.ai-media.yml`) |

---

## 13. Safety switches

These change what the platform is allowed to do. Each has a safe default.

| Variable | Secret | Default | What it does |
|---|---|---|---|
| `VVIP_REQUIRE_OFFICER` | | Deployed: `1` for oracle and brain. Code: off when unset | `1`: earmark create and clear, signal-plan apply and restore (oracle), and escort start, stop and clear (brain) are refused with 422 unless a named officer is given. The oracle's vehicle routes accept exactly `1`; its signal routes and the brain accept any truthy value. `0` relaxes both (an unnamed write is attributed to a system actor). E-challan recommendations, dispatch decisions, decision support and OSINT promotions need a named officer whatever this says |
| `VVIP_ESCORT_APPROVAL_TIMEOUT_SEC` | | `90` (clamped 15 to 600) | Pass-through, convoy-brain: how long a live-escort proposal (route switch, Plan B, hold, new closures) waits for a named officer. Then it expires and **the current plan holds**; it never auto-applies |
| `VVIP_SIGNAL_POLICY_WRITER` | | empty: **off** | traffic-oracle, truthy: the city signal-plan writer, set by `sajag_up.sh` from `SAJAG_DEMO`. Even when on, every apply needs a named officer (with `VVIP_REQUIRE_OFFICER=1`), a known or passed city band, a passing twin shadow evaluation and a field-calibrated twin (at least 24 field hours, replay error at most 5 km/h). A fresh install has no field data, so writes are refused |
| `VVIP_ACCEPT_LIVE_ANPR` | | unset: refused | Pass-through, traffic-oracle, exactly `1`: accept sightings labelled `live_anpr`. Reserved for a real vendor adapter; leave unset until one exists |
| `VVIP_ADAPTIVE_ROBUST_INPUTS` | | unset: the robust-routing knob in `shared/schemas/protocol_params.json` (on) | Pass-through, traffic-oracle: truthy or falsy forces the robust (length-weighted p90) congestion aggregation on or off |
| `SAJAG_DESIGN_HARNESS` | | unset: 404 | command-deck, exactly `1`: serves the `/design/*` harness pages (fixture data) from a production build. Private previews and smokes only |
| `SAJAG_DEMO_ALLOW_UNLABELLED` | | unset | `sajag_up.sh`, exactly `1`: lets demo mode start the living city although the public feed does not declare `emulated_labelling: true`. Leave unset: emulated events could reach the citizen pages looking live |
| `NODE_ENV` | | unset in the deck image (CSP sent) | command-deck: only `development` matters; it drops the content-security-policy header. Never set it on a deployed deck |

The brain's AI gates (`VVIP_CONFIDENCE_FLOOR`, `DECIDER_TIER0_DISABLE`, `VVIP_MEMORY_RECORD`) are in
[§8.2](#82-model-endpoints-and-ai-behaviour); `SAJAG_HYDRO_OFFLINE` and `SAJAG_TWIN_LLM` in §9.

---

## 14. Gate and tool scripts (selected)

Variables the acceptance, demo and city-build scripts under `scripts/` read, beyond the ones above. Each script's
header documents the rest.

| Variable | Secret | Default | What it does |
|---|---|---|---|
| `SAJAG_OPERATOR_PIN_FILE` | yes (names a PIN file) | unset | `deck_session.sh`, `lib/deck_session.mjs`, `secret_scan.sh`: a sandbox deck's throwaway PIN. A named but unreadable file is an error, never a fall-back to the PIN in `sajag.env` |
| `DECK_COOKIE_JAR` | yes (holds a session) | a temporary mode-600 jar | `deck_session.sh`: where the sign-in helper keeps the cookie; deleted at sign-out |
| `DECK_URL` | | `http://127.0.0.1:${DECK_PORT}`; `DECK_PORT` falls back to `5373` in `showcase_run.sh`, `demo_reset.sh`, `repetition_gate.sh`, `argus_full_smoke.sh`, `check_tier0_live.sh`, and to `5273` in `verify_all.sh`, `journeys.mjs` | The deck the script talks to |
| `ORACLE_URL`, `BRAIN_URL`, `EMULATOR_URL` | | `http://127.0.0.1:${ORACLE_PORT}` and so on | Whole-origin overrides in the gate scripts |
| `VERIFY_LIVE_MODELS`, `VERIFY_EXPECT_GATE` | | `1`, `on` | `verify_all.sh`: `0` skips the live model tiers; whether the live tier expects the gate on |
| `VERIFY_PREVIEW_PORT` | | `5199` | `verify_all.sh`: the private, keyless, gate-off preview; refused when it equals a stack port |
| `SAJAG_BUILD_HEAP_MB`; `SAJAG_RUST_IMAGE`, `SAJAG_CARGO_REGISTRY_VOLUME`, `SAJAG_CARGO_TARGET_VOLUME` | | `4096`; `rust:alpine`, `sajag-cargo-registry`, `sajag-cargo-target-<hash>` | `verify_all.sh`: Node heap of the deck build; the Docker build of signal-ingress when no local cargo exists |
| `ORACLE_WRITER_CMD` | | unset (recreates the deployed oracle) | `showcase_run.sh`, `repetition_gate.sh`: recreates a private stack's oracle when a run switches the signal writer on for its duration |
| `SAJAG_PURGE_ACCEPTANCE_OK` | | unset | `demo_reset.sh`: `yes` allows purging acceptance-test audit history; otherwise nothing is deleted |
| `SHOWCASE_ALLOW_RECREATE` | | unset | `showcase_run.sh`: `1` lets a run recreate the oracle with the signal writer on (and put it back at the end) when the writer is off; unset, such a run is refused and no container is touched |
| `HYDRO_URL`, `TWIN_URL` (`HYDRO_PORT`, `TWIN_PORT`) | | `8197`, `8198` | `showcase_run.sh`: the hydro nowcast / storm replay and the signal-timing twin it asks (compute only) |
| `DEMO_EVENING_USE_CASES`, `DEMO_EVENING_CLOCK` | | `ganesh_visarjan_girgaon,cloudburst_high_tide` (the visarjan night at Girgaon Chowpatty and the monsoon burst at high tide), `1` | `demo_reset.sh --apply`: the SIMULATED evening it stages on the board (empty: none) and its clock; any comma-separated ids of the emulator's use-case library (`scripts/scenario_library.json`) |
| `DEMO_STOLEN_PLATE`, `DEMO_PLATE_STATE`, `DEMO_LEGACY_PURSUIT` | | `MH01EM9001`, `MH`, unset | `demo_reset.sh`: the stolen demo plate (an EMULATED MH mark, the emulator's stolen-FIR plate); the city's mark prefix (pending reads on other emulated marks are stale debris); a fine-based pursuit to supersede, if any |
| `T0_REVISION`, `T0_SHA256` | | a pinned revision and its hash | `fetch_t0.sh`: the third-party t0-alpha artifact to fetch, verified before the oracle image is built |
| `SAJAG_CITY` | | `gen_osm_network.py` (and so `city_build.py`): `mumbai`; `impact_run.py`, `poi_route_matrix.py` and the twin: still `kolkata` in code | Which City Pack under `cities/` the city scripts (and the twin) use. Set `SAJAG_CITY=mumbai` for the scripts whose default still names the reference pack (`gen_osm_network.py` and `city_build.py` also take the city as an argument: `--city mumbai`, `city_build.py mumbai`) |
| `SAJAG_OSM_CACHE` | | `~/.cache/sajag/osm-network` | `gen_osm_network.py`: OpenStreetMap extract cache |
| `CHROME_PATH`, `PUPPETEER_FROM` | | the puppeteer cache; the repository's `frontend/` packages | Browser smokes and `journeys.mjs` |

---

## 15. Set but not read, legacy and image-internal

Listed so that nobody spends time tuning them.

| Variable | Where it appears | Status |
|---|---|---|
| `OLLAMA_BASE_URL` | convoy-brain `UNUSED_ENV` | Not read by any serving path; reported as ignored if set |
| `VVIP_DATABASE_URL`, `VVIP_NATS_URL` for convoy-brain | passed by `compose.gb10-override.yml` (with that file's older ports) | Not read by the brain; reported as ignored at start-up |
| `EMBEDDING_SERVICE_URL` for traffic-oracle | `compose.yml`, `compose.gb10-override.yml`, `compose.argus-override.yml` | Passed, but no oracle code reads it |
| `TRAFFIC_ORACLE_URL` in the embedding service | `embedding_service/config.py` | Declared (port 8081) and allow-listed; no call uses it |
| `VVIP_BATCH_SIZE`, `VVIP_BATCH_TIMEOUT_MS`, `VVIP_ML_THREADS`, `VVIP_ML_INTEROP_THREADS`, `VVIP_MEMORY_GUARD_MB`, `VVIP_ETA_MODEL_PATH`, `VVIP_RL_MAX_EPISODES`, `VVIP_RL_MAX_SIGNALS` | traffic-oracle `data/config.py`; some set by `compose.prod.yml` | Declared (100, 100, 4, 2, 3500, `models/onnx/eta_predictor.onnx`, 1000, 20), not read elsewhere |
| `SAJAG_FORECAST_DEFAULT_HORIZON_MIN` | forecast settings (`120`) | Not read; each request passes `horizon_min` |
| `SPEECH_ASR_DEFAULT_LANG`, `SPEECH_TTS_VOICE_DESCRIPTION`, `SPEECH_TTS_DEFAULT_VOICE` | speech settings (`mr`, a house voice description, `female`) | Declared, not read by the service code |
| `GRAFANA_PASSWORD` (secret) | `infra/compose.prod.yml` only | Older production profile with Prometheus and Grafana, not deployed. If you use it, set this (its fallback is a placeholder) |
| `ORT_GLOBAL_THREAD_POOL_SIZE`, `NVIDIA_VISIBLE_DEVICES`, `NVIDIA_DRIVER_CAPABILITIES`, `GF_*` | `infra/compose.prod.yml` only | Not deployed |
| everything in `infra/compose.event-emulator.yml`, `services/corridor-store/docker-compose.yml`, `infra/scripts/deploy.sh` | older single-purpose layouts | Not deployed; their ports (8081, 5432, 6379 …) do not apply to Sajag |
| `PYTHONPATH`, `PYTHONUNBUFFERED`, `NODE_OPTIONS`, `RUST_LOG`, `HF_HOME` | Dockerfiles | Image-internal. `RUST_LOG=info` sets signal-ingress logging; `HF_HOME` points the speech and forecast images at the mounted cache |

---

## 16. A minimal working environment file

A single-server deployment with the operator gate on, imagery keyless and OSINT off. Replace every `<…>`; each real
value must be one token with no spaces or quotes. Paths are examples. Create the file with
`bash scripts/sajag_up.sh --install-units` (or `bash scripts/sajag_env.sh --write`), then add the secrets with
`bash scripts/sajag_env.sh --set KEY -` rather than typing them into an editor.

```ini
# ~/.config/sajag/sajag.env   (mode 600; plain KEY=VALUE lines; never committed)

# repository and runtime state
SAJAG_ROOT=/home/<user>/sajag
SAJAG_RUN_DIR=/home/<user>/sajag/.run-models
SAJAG_LOG_DIR=/home/<user>/sajag/.run-models/logs
SAJAG_VENV_DIR=/home/<user>/sajag/.venvs
SAJAG_MODELS_CONFIG=/home/<user>/sajag/models-config/configs/sajag_models.yaml

# corridor-store on loopback (migrations and the embedding service)
POSTGIS_HOST_PORT=15434

# model weights and binaries: host paths supplied by the operator
DECIDER_SNAPSHOT_PATH=<path-to-the-decider-snapshot-directory>
LLAMA_SERVER_BIN=<path-to-llama-server>
GEMMA_GGUF=<path-to-the-gemma-4-12b-Q4_K_M.gguf>
BGE_M3_PATH=<path-to-the-bge-m3-directory>

# switches
SAJAG_DEMO=0
SAJAG_OSINT=0

# the City Pack: Mumbai (the twin's, two city scripts' and hydro's code defaults still name the
# Kolkata reference pack, §9 and §14; speech, forecast and the network build default to Mumbai)
SAJAG_CITY=mumbai
SAJAG_HYDRO_CITY_DIR=/home/<user>/sajag/cities/mumbai

# secrets: set each with   bash scripts/sajag_env.sh --set KEY -
SAJAG_OPERATOR_PIN=<six-digit PIN>
SAJAG_SESSION_SECRET=<64 hex characters>
POSTGIS_PASSWORD=<database password, set before the first bring-up>

# optional
# SAJAG_CESIUM_ION_TOKEN=<Cesium ion access token>
# free keys for the city feeds (docs/DATA_SOURCES.md §6); each source stays off until its key is set
# DATA_GOV_IN_API_KEY=<data.gov.in API key>
# WAQI_TOKEN=<aqicn.org data-platform token>
# OPENAQ_API_KEY=<OpenAQ API key>
# FIRMS_MAP_KEY=<NASA FIRMS map key>
# MAPILLARY_TOKEN=<Mapillary client token>
# OSINT_MODE=offline
# SAJAG_FORECAST_MODEL=chronos2
# SAJAG_TWIN_LLM=0
```

Everything else takes the deployed default from the compose files: loopback binds for everything but the deck,
`VVIP_REQUIRE_OFFICER=1`, `VVIP_ESCORT_SIM_GPS=1`, the signal writer off, the living city off. Then:

```bash
bash scripts/sajag_up.sh            # bring-up; READY 11/11 (12/12 with SAJAG_OSINT=1)
bash scripts/sajag_up.sh --status   # read-only readiness, including the security row
```

To enable OSINT later: `bash scripts/sajag_env.sh --set SAJAG_OSINT 1`, then `bash scripts/sajag_up.sh`. To add
the AI services, follow §9.1.

---

## 17. Checking the configuration

All of these are read-only.

| Check | Command | What to look for |
|---|---|---|
| Effective non-secret settings and the compose invocation | `bash scripts/sajag_env.sh --print` | Paths exist; the `# osint:` line says `on` or `off` as intended; the `# compose:` line names three files (four with OSINT). Secrets are not printed |
| Readiness and exposure | `bash scripts/sajag_up.sh --status` | Every row READY (exit 0). Below the table: `network` says the internal ports are loopback-only; `security` shows the deck's bind scope and the gate on; `modes` shows the signal-plan writer and `SAJAG_DEMO`; `boot` shows the units linked |
| The gate, as the deck sees it | `curl -s http://127.0.0.1:5373/api/session` | `"gate": true` |
| Imagery mode for an anonymous caller | `curl -s http://127.0.0.1:5373/gods-eye/mode \| python3 -c 'import json,sys; print(json.load(sys.stdin)["mode"])'` | `keyless-osm` (the filter prints only the mode, never a token) |
| AI services, when started | `for p in 8194 8195 8196 8197 8198; do curl -s -o /dev/null -w "$p %{http_code}\n" http://127.0.0.1:$p/health; done` | `200` for each service you brought up |
| Model hosts | `bash scripts/smoke_models.sh` | One PASS line per model (it sends one real request to each host) |
| No secret in the tree or the next push | `bash scripts/secret_scan.sh` | No findings |

If a value you set seems to be ignored, check in this order:

1. Is it in `sajag.env`, not only in your shell? (A bring-up warns about persisted keys that are shell-only.)
2. Is it one of the two variables the bring-up overwrites from `SAJAG_DEMO` (`VVIP_SIGNAL_POLICY_WRITER`,
   `EMULATOR_LIVING_CITY`)?
3. Does the compose file pass it to that service, interpolated or as a pass-through key? A variable compose does not
   list never reaches the container.
4. Was the container recreated? `sajag_up.sh` does this for the core services when their configuration changed; the
   AI services need their own `up -d` (§9.1); the model hosts need a unit restart.
5. Is it one of the variables in [§15](#15-set-but-not-read-legacy-and-image-internal)?
