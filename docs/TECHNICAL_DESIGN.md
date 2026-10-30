# Sajag — Technical Design Document

**Sajag (सजग, Hindi and Marathi for "alert, watchful")** is a city-scale traffic, rain and crowd operations platform
for Mumbai. *Not by stopping. By steering.* This document describes how it is built: the system context, the containers and ports, each service, the data model, the key
flows, the AI services, security and privacy, observability, deployment, testing, and the design decisions behind
them (ADRs).

Facts in this document are taken from the code in this repository. Where a figure was measured, the date is given.
Where a figure is an estimate, it is labelled MODELLED.

| | |
|---|---|
| Product description | [`../PRODUCT.md`](../PRODUCT.md) |
| Environment variables | [`ENVIRONMENT.md`](ENVIRONMENT.md) |
| Sample data and tests | [`SAMPLE_DATA_AND_TESTS.md`](SAMPLE_DATA_AND_TESTS.md), [`samples/`](samples/) |
| Design notes and wireframes | [`DESIGN_NOTES.md`](DESIGN_NOTES.md), [`wireframes/`](wireframes/) |
| AI capability notes | [`ai/forecast.md`](ai/forecast.md), [`ai/hydro.md`](ai/hydro.md), [`ai/speech.md`](ai/speech.md), [`ai/vision.md`](ai/vision.md), [`ai/twin.md`](ai/twin.md) |

---

## Contents

1. [Purpose, scope and goals](#1-purpose-scope-and-goals)
2. [System context](#2-system-context)
3. [Containers, ports and deployment](#3-containers-ports-and-deployment)
4. [Service design](#4-service-design)
5. [The AI services](#5-the-ai-services)
6. [The City Pack](#6-the-city-pack)
7. [Data model](#7-data-model)
8. [APIs](#8-apis)
9. [Key flows](#9-key-flows)
10. [State machines](#10-state-machines)
11. [Security](#11-security)
12. [Privacy](#12-privacy)
13. [Reliability and degradation](#13-reliability-and-degradation)
14. [Observability](#14-observability)
15. [Deployment and capacity](#15-deployment-and-capacity)
16. [Testing strategy](#16-testing-strategy)
17. [Architecture decision records](#17-architecture-decision-records)
18. [Known limitations](#18-known-limitations)

---

## 1. Purpose, scope and goals

### 1.1 Purpose

Mumbai is a narrow island city and its suburbs, wedged between the Arabian Sea, Thane Creek and the Mithi river.
Each monsoon, a heavy burst that coincides with a high tide of about 4.5 m closes the sea outfalls, and the water has
nowhere to go (BMC chief engineer, Free Press Journal, 2025). The same low spots flood year after year (the BMC counts
386–498 chronic or waterlogging spots, depending on the year; Free Press Journal): Hindmata, King's Circle, Sion,
Milan Subway, Andheri Subway, Kurla by the Mithi, Parel. Subways close and suburban locals stop; their riders (about
68 lakh a day on average in 2025-26; Free Press Journal, from railway data) pour onto roads and station forecourts at
CSMT, Dadar, Kurla and Andheri, and one stranded corridor spills onto the next. On an ordinary day the roads are
already slow: Mumbai drivers lost about 126 hours to peak-hour traffic in 2025 (TomTom Traffic Index 2025).

Each agency sees one piece. Mumbai Traffic Police sees the roads; the BMC sees drains and pumps and runs the 1916
disaster control; Central and Western Railway see the tracks; ambulance (108) crews see their own trips; IMD sees the
rain. Nobody has one live picture that joins rain, tide, pumps, traffic and crowds and says what to do in the next
30 to 90 minutes. The same gap shows on Ganeshotsav visarjan night, at Wankhede egress, during protected movements and
when a bridge or a highway breaks down. Sajag gives these agencies one live picture of roads, rain and crowds, and a
loop in which the AI **proposes** and a **named officer decides**. Citizens get the decided advisories in English,
Marathi and Hindi, with voice.

### 1.2 Scope

- One web console (the command deck) for officers, with public pages for citizens and ambulance crews.
- A platform of services: the system of record and numeric engine (traffic-oracle), the AI orchestrator
  (convoy-brain), the emulated city (event-emulator), the traffic ingress (signal-ingress), the store
  (corridor-store), event intelligence from open sources (OSINT) and a memory service (embedding-service).
- Five AI services built around the monsoon and the crowds: corridor forecasting, waterlogging nowcast, voice
  reports in Marathi, Hindi and English, road-state vision and a signal-timing twin.
- Open city feeds (cityfeeds): air quality, heat, cyclones, satellite fire hotspots and street photos from public
  sources, each labelled.
- A City Pack (`cities/<id>/`) from which every city-specific file is generated.

### 1.3 Goals

| Goal | How |
|---|---|
| A human decides every action | Every AI output is a proposal object with `requires_officer: true`; the server refuses an unnamed decision; no answer means the current plan holds |
| Honest about what is real | Every record carries its provenance: LIVE, EMULATED, SIMULATED, MODELLED, UNVERIFIED-FIELD, UNVERIFIED-CAMERA, NEWS-REPORTED, OFFICIAL-VERIFIED |
| Vehicles and places, never people | No person, face or biometric field exists on any path; vision refuses person and plate questions; OSINT is aggregate |
| Runs on premises | Every model runs on one edge server beside the control room; no cloud inference |
| English first, Marathi and Hindi throughout | Every page opens in English, with मराठी and हिंदी one tap away (the choice is remembered); voice in and out in Marathi, Hindi and English; Marathi rationales checked by code |
| A new city is a new folder | The City Pack and `scripts/city_build.py` |

### 1.4 Non-goals

- Sajag does not control signals, barricades or dispatch on its own. Signal changes go through an adapter that is
  emulated today, and only after an officer approves.
- It does not identify or track people.
- It does not replace agency radio or computer-aided dispatch. Advisories are drafts that an officer sends.

### 1.5 Real, emulated, simulated and modelled

| What | Status today | Label |
|---|---|---|
| Road network, junctions, stations | Real roads from OpenStreetMap | — |
| Rain nowcast | Live (Open-Meteo, a model nowcast, not a gauge) | LIVE |
| Arabian Sea tide at Apollo Bunder | Harmonic model from cited constants | MODELLED (approximate) |
| Waterlogging risk | Conceptual ponding model | MODELLED |
| BMC storm-water pumping stations (Haji Ali, Irla, Love Grove, Cleveland Bunder, Britannia, Gazdarbandh) | Adapter stand-in until access is granted | EMULATED |
| Mithi river level | No open live feed; the Kurla stretch is a named hotspot in the susceptibility layer, no level is shown | — |
| Traffic feed | Synthetic field through the real ingress pipeline | SIMULATED / EMULATED |
| Corridor forecasts | Chronos-2 on simulated history | "Forecast on simulated traffic" |
| Signal programs, camera sites | Standard templates at OSM signal positions; camera positions at signalised junctions | MODELLED |
| Signal-timing proposals | Cell-transmission twin | MODELLED |
| Field voice reports | Real ASR on the officer's speech | UNVERIFIED-FIELD until confirmed |
| Camera road state | Real VLM on a still | UNVERIFIED-CAMERA until confirmed |
| News and alerts | Real open sources, aggregate only | UNVERIFIED-OSINT / NEWS-REPORTED / OFFICIAL-VERIFIED |
| Scenarios (monsoon burst at high tide, visarjan night, Wankhede egress, station surge, cyclone …) | Emulator scenarios | SIMULATED |
| Impact figures | Deterministic model with an assumptions ledger | MODELLED |

### 1.6 Capability map

Every capability, the code that implements it and the screen it is seen on. The platform capabilities come first,
then the five AI services (§5).

| Capability | Service · module | Screen | Label |
|---|---|---|---|
| Movement planning: k-shortest routes, weighted scoring, lane-floor validation per protection class (Z+ 6 lanes / 180 s, Z 4 / 120 s, Y 2 / 60 s, X any), closure plans with detour status (`found`, `no_path`, `dead_end`, `impractical`) | convoy-brain `workflows/pre_movement.py`, `agents/security_liaison.py`; traffic-oracle `optimize/*` | `/plan` | traffic SIMULATED |
| Rolling holds and escort: closures 60–180 s ahead; one open proposal per escort (hold, alternate, re-route); officer approves; expiry after 90 s (15–600) keeps the plan; after-action report | convoy-brain `workflows/live_escort.py`, `post_clearance.py`, `gps_sim.py` | `/plan` Live, `/decide`, `/ops` | convoy GPS EMULATED |
| Corridor events: one data model, kinds `protected_movement`, `procession`, `mass_gathering`, `race`, `ceremonial`, `egress_surge`, `emergency_evacuation`, `work_zone`, `crime_incident`, `vehicle_pursuit`; closure templates per kind | corridor-store `events.corridor_events`; event-emulator use-case library | `/map`, `/ops`, `/o/event:<id>` | scenarios SIMULATED |
| Traffic ingest with eight plausibility checks | signal-ingress | Home systems line, `/map` | SIMULATED |
| Forecast ladder for routing and ETAs (support gate → foundation model → heuristic) | traffic-oracle `predict/flow_forecaster.py` | `/plan` route times | "Simulated traffic" |
| Situation bands (Active Movement Adaptation): score → GREEN/AMBER/RED/BLACK, monotone, hysteresis, protocol floors, twin shadow-evaluation fail-closed, stale after a hung tick | traffic-oracle `adaptive/*` | `/ops` module card, map band chip, Home pulse | — |
| City signal plans: band → green split with cross-street floors; writer off by default; named officer; twin check before any write; snapshot, Restore, Restore all; refusal until the twin is field-calibrated | traffic-oracle `signals/*`, `simulation/calibration.py` | `/ops` City Signal Plans | no field controller |
| Monte-Carlo scenario twin (shadow-evaluation, wargames, calibration replay) | traffic-oracle `simulation/*`, `scripts/scenario_library.json` | `/ops` Lab | MODELLED |
| Stolen-vehicle chain: lawful-basis earmark (90-day cap) → emulated ANPR reads → evidence-only sighting (an e-challan on a stolen vehicle is refused, 409) → officer approval → one pursuit per approval (422 otherwise) → interception choke plan → trace | traffic-oracle `enforcement/*`, `vehicles/*`, `events/*` | `/decide`, `/ops`, `/map`, `/o/vehicle:<id>` | ANPR EMULATED |
| E-challan support (segment speed, signal violation, closed-corridor entry), PENDING until an officer decides | traffic-oracle `enforcement/rules.py` | `/decide`, `/ops` | reads EMULATED |
| Dispatch to five agencies (Civic Volunteers, Police Control, Traffic Police, Ambulance (108), Fire & Emergency) with an append-only lifecycle | traffic-oracle `units/*` | `/ops` dispatch tiles, `/o/dispatch:<id>` | units EMULATED |
| Ambulance (108) green corridor (§9.4) | command-deck public projection; traffic-oracle `units/*` | `/driver`, `/decide` | — |
| Event intelligence: connectors for official alerts, news and aggregate social signals; redaction at parse; offline gazetteer; credibility; officer promote gate | osint-ingress, osint-common, osint-geo, osint-analysis; traffic-oracle `osint/*` | Home "Reported in the city", `/o/osint_event:<id>` | OFFICIAL-VERIFIED / NEWS-REPORTED / UNVERIFIED-OSINT |
| Decision support: five courses of action, AHP + lexical veto + TOPSIS, twin or surrogate wargame; approval creates dispatch requests only | traffic-oracle `decision_support/*` | `/decide` "Choose a response" | MODELLED |
| Assistant: two tiers, grounding validator, confidence floor 0.45, read-only tools | convoy-brain `decider.py`, `grounding.py`, `mcp/server.py` | `/assistant`, `/chat` | per answer |
| Advisories for four audiences in three languages, drafts only | command-deck `lib/comms/*` | `/comms` | exercise marker on emulated events |
| 3D city with overlays, thermal-style view, share links, replay | command-deck `lib/gods-eye/*` | `/map`, `/gods-eye` | imagery not live |
| Audit trail, operator gate, masking, retention | all services; command-deck `hooks.server.ts`, `operator-session.server.ts` | `/ops` audit, object Record tab | — |
| Waterlogging nowcast | hydro (§5.2) | `/map` Waterlogging, Home, `/decide` | rain LIVE, tide MODELLED, pumps EMULATED |
| Corridor forecasting | forecast (§5.1) | `/map` Forecast, `/o/segment:<id>` | on simulated traffic |
| Voice reports and advisories (mr, hi, en) | speech (§5.3) | top bar → Report, `/citizen` Listen | UNVERIFIED-FIELD, synthetic voice |
| Open city feeds (air, heat, cyclone, fires, street photos) | cityfeeds (§4.10) | Home and `/map` chips, object pages | LIVE feed, values MODELLED or OBSERVED; "Reference photo · not live" |
| Road-state vision | vision (§5.4) | `/o/camera:<id>` | UNVERIFIED-CAMERA |
| Signal-timing twin | twin (§5.5) | `/decide` AI proposals | MODELLED |

| The live map, closer | Situation wall |
|---|---|
| ![A closer view of the live map over the Island City](screenshots/map-live-3d-close.jpg) | ![The situation wall](screenshots/situation-wall.jpg) |
| *Closer in: each road's speed and V/C (simulated), events where they happen, units with their state (emulated).* | *Counts, decisions, the city band, signal plans (writer off) and the audit stream on one screen.* |

### 1.7 The scenarios Sajag is built for

Each scenario is a corridor event or a waterlogging situation on the Mumbai network. Place ids are the canonical
ones in `cities/mumbai/landmarks.json`. In the emulator every one of them is SIMULATED and labelled so.

| Scenario | Places (ids) | What Sajag shows and proposes | Labels |
|---|---|---|---|
| Monsoon burst at high tide | `hindmata`, `kings_circle`, `sion_circle`, `dadar_tt`, `parel`, `andheri_subway`, `milan_subway`, `mithi_kurla`; tide at `apollo_bunder`; pumps `haji_ali_ps`, `irla_ps`, `love_grove_ps`, `cleveland_bunder_ps`, `britannia_ps`, `gazdarbandh_ps` | Risk class per road 30–90 min ahead; a reroute (for example Western Express Highway traffic off the Andheri Subway approach before it closes); an ambulance window to KEM or Sion Hospital; a live-wire inspection request to the area's power utility; one advisory draft in English and Marathi, worded for every audience on the advisories page | rain LIVE, tide MODELLED, pumps EMULATED, risk MODELLED |
| Anant Chaturdashi visarjan night | `lalbaug`, `lalbaugcha_raja` → `girgaon_chowpatty`; also `juhu_beach`, Dadar Chowpatty | A `procession` event with rolling closures along the route, crowd load at Girgaon Chowpatty, a kept-open emergency corridor, diversions for the closed roads (2024 reporting: restrictions on 53 roads; The Statesman) | SIMULATED |
| Wankhede egress | `wankhede`, `churchgate`, `marine_drive` | An `egress_surge` event: the kind's closure template on Marine Drive and the Churchgate and Marine Lines approaches, with holds at the nearest junctions | SIMULATED |
| Station surge when locals stop | `csmt`, `dadar`, `kurla`, `andheri` (and `ghatkopar`) | When tracks flood at Sion and Kurla, riders pour onto forecourts and roads: a `mass_gathering` event at each station forecourt with its closure template; the forecast and the twin show the spill onto nearby roads | SIMULATED |
| Protected movement | `mantralaya` → `airport_t2` | A `protected_movement` with rolling holds 60–180 s ahead of the convoy, never a blanket freeze; routes over the Coastal Road, the Bandra–Worli Sea Link (`sea_link`) or the Western Express Highway compared in the twin | traffic SIMULATED, convoy GPS EMULATED |
| Stolen-vehicle chain | junction cameras on the network | A lawful-basis earmark on an MH plate (`MH 01 AB 1234` form), emulated ANPR sightings, officer approval, one pursuit per approval, a choke plan; no fine for a theft victim (409) | ANPR EMULATED, plates masked |
| Cyclone on the west coast | `marine_drive`, Worli seaface, hill slopes in the eastern suburbs | High winds and sea surge (as in Tauktae, May 2021): tree falls, shore closures, advisories | SIMULATED |

---

## 2. System context

```mermaid
flowchart LR
    officer(["Duty officer<br/>Mumbai Traffic Police"])
    control(["Control room<br/>BMC 1916 · Maharashtra SDMA"])
    crew(["Ambulance (108) crew"])
    citizen(["Citizen"])

    subgraph S["Sajag · one edge server"]
        deck["Command deck<br/>web console and public pages"]
        platform["Platform services<br/>oracle · brain · emulator · ingress · store · OSINT"]
        ai["AI services<br/>forecast · hydro · speech · vision · twin"]
        models["Local models<br/>decider · tactical LLM · embeddings"]
    end

    officer -->|"reviews, approves, rejects"| deck
    control -->|"watches, drafts advisories"| deck
    crew -->|"requests a corridor"| deck
    citizen -->|"checks a road, listens"| deck
    deck --> platform
    deck --> ai
    platform --> models
    ai --> models

    osm[("OpenStreetMap<br/>extracts, at build")]
    meteo[("Open-Meteo<br/>rain nowcast")]
    sachet[("NDMA Sachet CAP alerts (Maharashtra)<br/>Mumbai news RSS, GDELT")]
    feeds[("WAQI · OpenAQ · NASA FIRMS<br/>Mapillary · GDACS")]
    ion[("Cesium ion<br/>3D tiles, optional")]
    hf[("Hugging Face<br/>weights, at install")]
    pumpsrc[("BMC pumping stations<br/>and rain gauges, future")]
    cctv[("Junction CCTV stills<br/>future")]
    sig[("Signal controllers<br/>future")]

    osm -.-> platform
    meteo --> ai
    sachet --> platform
    feeds --> platform
    ion -.-> deck
    hf -.-> models
    pumpsrc -.->|"adapter, emulated today"| ai
    cctv -.->|"stills"| ai
    sig -.->|"adapter, emulated today"| platform
```

### 2.1 Actors

| Actor | Uses | Can do |
|---|---|---|
| Duty officer (Mumbai Traffic Police, Mumbai Police) | The console | Name themselves, review and decide proposals, plan movements, record voice reports, confirm field and camera readings |
| Control room (BMC disaster control 1916, Maharashtra SDMA) | The console | Watch rain, tide, pumps and waterlogging risk; draft advisories |
| Ambulance (108) crew | `/driver` | Request a corridor; see its status |
| Citizen | `/citizen`, `/welcome` | Check a road in English, Marathi or Hindi; listen to an advisory |

### 2.2 External systems

| System | Direction | Use | Status |
|---|---|---|---|
| OpenStreetMap (Overpass) | In, at build time | Road network, drains, stations | Committed extracts, ODbL |
| Copernicus DEM GLO-30 | In, at build time | Terrain for waterlogging susceptibility | Committed result |
| Open-Meteo | In, live | 15-minute rain at a fixed grid of points over the city | No key; cached 10 min; at most one call per 30 s; daily cap |
| NDMA Sachet (CAP, Maharashtra), Mumbai news RSS (Marathi, English, Hindi), GDELT, Reddit RSS | In, live | OSINT signals, aggregate only | Off by default (`SAJAG_OSINT=0`); allow-listed hosts |
| WAQI, OpenAQ, Open-Meteo air quality, NASA FIRMS, GDACS, USGS | In, live | City feeds: air quality at the CPCB/MPCB sites, heat, cyclones, satellite fire hotspots, earthquakes | Keys in `~/.config/sajag/sajag.env` where needed; polite schedule |
| Mapillary | In, live, officers only | A nearby public street photo for a camera page | Fetched server-side; "Reference photo · not live" with its date |
| Cesium ion | In, optional | Photoreal 3D tiles for signed-in officers | Needs a token; otherwise keyless OpenStreetMap |
| Hugging Face Hub | In, at install | Model weights | Never at run time (`HF_HUB_OFFLINE=1`) |
| BMC storm-water pumping stations, BMC and IMD rain gauges | In, future | Pump and sump state, gauges | Emulated adapter |
| Junction CCTV | In, future | Stills for road-state vision | Upload path ready; no feed connected |
| Mumbai Traffic Police signal controllers | Out, future | Approved timing changes | Emulated adapter; the twin never writes |

---

## 3. Containers, ports and deployment

### 3.1 Containers and ports

```mermaid
flowchart TB
    subgraph LAN["LAN"]
        browser["Browser"]
    end
    subgraph HOST["Edge server, one host"]
        deck["command-deck<br/>SvelteKit on Bun<br/>0.0.0.0:5373"]
        subgraph PLAT["Platform, loopback only"]
            emu["event-emulator :8190"]
            ora["traffic-oracle :8191"]
            brain["convoy-brain :8192"]
            osint["osint-ingress :8193<br/>(SAJAG_OSINT=1)"]
            feedsvc["cityfeeds :8199"]
            ingress["signal-ingress<br/>Rust, no port"]
        end
        subgraph AI["AI services, loopback only"]
            speech["speech :8194"]
            fc["forecast :8195"]
            vis["vision :8196"]
            hydro["hydro :8197"]
            twin["twin :8198"]
            vllm["Qwen3-VL llama-server :8201"]
            tts["TTS llama-server :8202"]
        end
        subgraph MOD["Models, loopback only"]
            mh["model-host :8083<br/>decider"]
            llama["llama-server :8084<br/>tactical LLM"]
            emb["embedding-service :8085"]
        end
        subgraph DATA["Stores, loopback only"]
            pg[("PostGIS :15434")]
            vk[("Valkey :6390")]
            nats[("NATS :4233<br/>monitor :8233")]
        end
    end
    browser -->|"HTTP"| deck
    deck -->|"/api/v1, /api/traffic"| ora
    deck -->|"/api/convoy"| brain
    deck -->|"/api/emulator"| emu
    deck -->|"/api/cityfeeds"| feedsvc
    deck -->|"/api/speech /api/forecast /api/vision /api/hydro /api/twin"| AI
    ingress -->|"Arrow batches"| nats
    nats --> ora
    ora --> pg
    ora --> vk
    brain --> ora
    brain --> mh
    brain --> llama
    brain --> emb
    emu --> ora
    emu --> vk
    emu --> nats
    osint -->|"POST /api/v1/osint/signals"| ora
    fc -->|"GET"| ora
    fc --> hydro
    twin -->|"GET"| ora
    twin -->|"rationale only"| llama
    vis --> vllm
    speech --> tts
    emb --> pg
```

| Component | Port | Bind | Started by |
|---|---|---|---|
| command-deck | 5373 | 0.0.0.0 (the only LAN surface) | compose (`sajag_up.sh`) |
| event-emulator | 8190 | 127.0.0.1 | compose |
| traffic-oracle | 8191 | 127.0.0.1 | compose |
| convoy-brain | 8192 | 127.0.0.1 | compose |
| osint-ingress | 8193 | 127.0.0.1 | compose, with `SAJAG_OSINT=1` |
| cityfeeds | 8199 | 127.0.0.1 | systemd user unit `sajag-feeds.service` |
| speech | 8194 | 127.0.0.1 | `infra/compose.ai-media.yml` |
| forecast | 8195 | 127.0.0.1 | `infra/compose.ai.yml` |
| vision | 8196 | 127.0.0.1 | `infra/compose.ai-media.yml` |
| hydro | 8197 | 127.0.0.1 | `infra/compose.ai.yml` |
| twin | 8198 | 127.0.0.1 | `infra/compose.twin.yml` |
| Qwen3-VL llama-server | 8201 | 127.0.0.1 | `services/vision/scripts/serve_llm.sh start` (the container deployment); on bare metal vision starts it on demand (`VISION_LLM_MANAGE=1`) |
| TTS llama-server | 8202 | 127.0.0.1 | started on demand by speech on bare metal (`SPEECH_TTS_BACKEND=auto`); the container runs TTS in transformers instead |
| model-host (decider) | 8083 | 127.0.0.1 | systemd user unit `sajag-decider.service` |
| llama-server (tactical LLM) | 8084 | 127.0.0.1 | `sajag-llama.service` |
| embedding-service | 8085 | 127.0.0.1 | `sajag-embed.service` |
| PostGIS | 15434 | 127.0.0.1 | compose |
| Valkey | 6390 | 127.0.0.1 | compose |
| NATS | 4233, monitoring 8233 | 127.0.0.1 | compose |

### 3.2 Compose files

| File | What it adds |
|---|---|
| `infra/compose.yml` | The base services |
| `infra/compose.gb10-override.yml` | The arm64 edge server: host networking for the services that must reach loopback model hosts |
| `infra/compose.argus-override.yml` | The deployed project `sajag`: container names, the port map, loopback binds, pass-through flags, healthchecks |
| `infra/compose.osint-ingress.yml` | The OSINT service (only with `SAJAG_OSINT=1`) |
| `infra/compose.ai.yml` | forecast and hydro |
| `infra/compose.ai-media.yml` | speech and vision |
| `infra/compose.twin.yml` | the twin |

The base invocation is `docker compose -p sajag -f infra/compose.yml -f infra/compose.gb10-override.yml -f
infra/compose.argus-override.yml`; `scripts/sajag_env.sh` exposes it as the shell function `sajag_compose`.
The AI stanzas are layered over it by hand (each file's header gives the command).

### 3.3 Systemd units and boot

`infra/systemd/` holds `sajag.target`, `sajag-models.target`, `sajag-decider.service`,
`sajag-llama.service`, `sajag-embed.service` and `sajag-up.service`. `scripts/sajag_up.sh
--install-units` links them into `~/.config/systemd/user` and enables `sajag.target`; at boot the model hosts
start and `sajag-up.service` runs `sajag_up.sh --boot`. Every unit reads `~/.config/sajag/sajag.env`.

### 3.4 Bring-up order (`scripts/sajag_up.sh`)

```mermaid
flowchart LR
    pre["preflight<br/>ports, Docker, lock"] --> mu["model units<br/>8083 · 8084 · 8085"]
    mu --> b{"--build?"}
    b -->|yes| build["compose build"]
    b -->|no| pg
    build --> pg["PostGIS alone<br/>up -d, healthy"]
    pg --> mig["migrate<br/>001–026"]
    mig --> seed["seed if empty<br/>+ network step when changed"]
    seed --> up["every service up -d"]
    up --> rs["restart network readers<br/>after a network step"]
    rs --> conv["converge<br/>readiness table"]
```

The readiness table has 11 components (12 with OSINT): postgis, valkey, nats, signal-ingress, oracle, brain, deck,
emulator, (osint), decider, gemma, embeddings, plus a security row (the deck's bind scope and gate state; a deck on
the LAN with the gate off is DEGRADED). `--status` is read-only and exits 0 only when every component is READY.
The five AI services are brought up with their own compose files and report on their own `/health`.

---

## 4. Service design

### 4.1 command-deck

**Stack:** SvelteKit (Svelte 5), TypeScript, adapter-node on Bun, MapLibre and CesiumJS. **Source:**
`services/command-deck/`.

#### Route groups

| Group | Routes | Theme and policy |
|---|---|---|
| `(v3)` operator pages | `/` (Home), `/map`, `/decide`, `/decide/[unit]`, `/plan`, `/assistant`, `/o/[urn]` (object pages) | Night theme; operator CSP |
| `(deck)` analyst pages | `/analyst` (workspace), `/ops` (situation wall), `/gods-eye` (3D city), `/chat`, `/comms` (advisories) | Night theme; operator CSP |
| `(public)` | `/citizen`, `/driver` | Day theme; strict public CSP; English first, मराठी and हिंदी one tap away |
| `(landing)` | `/welcome` | Public; no API calls |
| `api/session` | `POST /api/session` (sign in), `GET` (gate state) | — |

`src/hooks.ts` reroutes `/` to Home and `/analyst` to the workspace; every per-page decision (CSP, theme, default
language) reads the resolved route id, not the URL.

| Home | Analyst workspace |
|---|---|
| ![Home: the featured decision, the city pulse and the next two hours](screenshots/home.jpg) | ![The Analyst workspace](screenshots/analyst-workspace.jpg) |
| *What needs an officer now, the city's band and four counts, and the next two hours (modelled).* | *The map, the active events and the selected movement's figures, with the timeline below.* |

#### Request pipeline (`src/hooks.server.ts`)

1. **WebSocket upgrades** are answered 501 at once (adapter-node cannot upgrade; clients fall back to polling).
2. **Machine ingest refusal:** any write to `/api/v1/osint/signals`, under every decoding of the path, is 403 before
   the gate and before any fetch. Only osint-ingress posts there, directly on loopback.
3. **Operator gate** (when `SAJAG_OPERATOR_PIN` is set): every proxied request without the signed session cookie
   is default-denied (403), except public road geometry, liveness probes, the ambulance request (rate-capped) and
   the public AI allow-list (§11.2).
4. **Proxy:** fixed loopback targets; only ports are configurable.

   | Prefix | Target |
   |---|---|
   | `/api/v1`, `/api/traffic` | traffic-oracle |
   | `/api/convoy` | convoy-brain (prefix stripped) |
   | `/api/emulator` | event-emulator (stripped) |
   | `/api/speech`, `/api/forecast`, `/api/vision`, `/api/hydro`, `/api/twin` | the AI services (stripped) |
   | `/api/cityfeeds` | cityfeeds (stripped) |

   After building the upstream URL the hook asserts its origin is still the rule's loopback target (a
   protocol-relative path cannot turn the proxy into an open relay).
5. **Headers** on every response: `nosniff`, a referrer policy, `X-Frame-Options: DENY`, a permissions policy (no
   geolocation) and a nonce-based CSP per document (§11.4).

#### Public projection

The citizen and driver pages read a server-side projection (`/api/public/*`), never the raw APIs. It carries only
public facts, labels every emulated row (`emulated_labelling: true`) and never carries a plate.

#### Languages

`en`, `mr` and `hi` packs per feature (`src/lib/i18n/packs.*.ts`); English is the default everywhere. The reader's
choice is a cookie (`sajag_lang`); `<html lang>` follows it. Noto Sans Devanagari, which sets both Marathi and Hindi,
is self-hosted (OFL).

### 4.2 traffic-oracle

**Stack:** Python 3.12, FastAPI, asyncpg, valkey, nats-py, OR-Tools, NetworkX, ONNX Runtime. **Source:**
`services/traffic-oracle/src/traffic_oracle/`.

The system of record and the numeric engine. Every write of city state (events, routes, sightings,
recommendations, dispatches, signal plans, OSINT situations, decision-support records) goes through it.

| Module | Responsibility |
|---|---|
| `data/` | Settings, database pool, Valkey cache, pgRouting queries |
| `ingest/` | NATS consumers (`corridor.traffic.live`, `.emulated`, `.anomaly`, `corridor.units.emulated`); Arrow decode; buffered writes to `traffic.observations`; newest row per segment to Valkey |
| `predict/` | The platform's traffic forecast ladder, with labelled fallbacks |
| `optimize/` | Routing (OR-Tools, pgRouting k-shortest), diversion planner |
| `adaptive/` | **Active Movement Adaptation** (below) |
| `simulation/` | A seeded Monte-Carlo twin of corridor events; the scenario library export |
| `events/` | Corridor events: create, the live board, lifecycle, routes |
| `vehicles/`, `enforcement/` | The watchlist with lawful basis and capped retention; the ANPR ingest seam; e-challan rules that only create PENDING recommendations; the stolen-vehicle rule |
| `units/` | Five-agency dispatch channel and lifecycle |
| `signals/` | City signal plans: default-off writer, twin shadow evaluation before any write, snapshot and restore |
| `city/` | City fusion, entities, the feed, cameras, plate masking of every label and text |
| `osint/` | Machine ingest of redacted signals, the trust boundary, re-fusion, officer promotion |
| `decision_support/` | Courses of action, AHP + lexical veto + TOPSIS, wargames, the human-gated decision |
| `ops/` | The degradation ledger |
| `coordination.py` | Guarded router registration: a module that cannot import is replaced by a stub answering 503 "not deployed", so the oracle always boots |

**Active Movement Adaptation** (`adaptive/` with `signals/`), six stages:

1. **Situation** — each active subject (a corridor event or movement) is classified GREEN / AMBER / RED / BLACK
   from congestion, weather, crowd, anomaly and GPS-age scores. Emulated traffic can drive only an emulated event.
2. **Hysteresis** — a class change must persist through its dwell window before adoption.
3. **Protocol floors** — advance-closure floors by protection class (Z+ 180 s, Z 120 s, Y 60 s) on every publish.
4. **Twin shadow evaluation** — any deviation from baseline must beat it in a paired twin run, or the engine
   fails closed to baseline.
5. **Audited persistence** — every observation to `adaptive.situation_log`, every publish to
   `adaptive.param_overrides`, mirrored to Valkey (30 s TTL).
6. **City signal plans** — the city band (the most severe subject) maps to a bounded green-split shift (AMBER 6 %,
   RED 12 %, BLACK 18 % of the cycle, with a cross-street floor); cycle and offsets never change. The writer is off
   by default (`VVIP_SIGNAL_POLICY_WRITER`), every apply is operator-triggered and attributed, and the prior
   program is snapshotted for restore.

### 4.3 convoy-brain

**Stack:** Python 3.12, FastAPI, httpx, valkey. **Source:** `services/convoy-brain/src/convoy_brain/`.

The brain orchestrates the platform's decision AI. It asks the models, runs deterministic tools through the
oracle, checks every claim, and turns anything that would change a plan into a proposal for a named officer.

- **Two tiers.** The strategic tier is a 27B decider model (`pplx-decider-v1.2`) served by model-host as **typed questions** (choice,
  probability, score), never as a chat model. The tactical tier is a Gemma 4 12B model on llama-server, which drafts
  tool arguments against each tool's JSON schema and words answers. Below both sits a deterministic heuristic floor.
  Every fallback is recorded.
- **Workflows.** Pre-movement planning, live escort (a background task per movement; one open proposal at a time;
  approval timeout 90 s by default, configurable 15–600 s; on timeout the current plan holds) and post-clearance.
- **Grounding validator** (`grounding.py`): checks argument provenance before a tool runs, resolves typed road names
  against the network, and checks every sentence of an answer against the turn's tool results.
- **MCP** (`POST /mcp`, JSON-RPC 2.0): 29 tools, read-only by construction. A regular expression refuses any tool
  whose name contains approve, decide, earmark, dispatch_request, withdraw or transition.
- **Memory.** Each movement's context and its decisions log live in Valkey (`convoy:context:{movement_id}`); the
  embedding service finds similar past situations.

### 4.4 event-emulator

**Stack:** Python 3.12, FastAPI, psycopg, valkey, nats-py, pyarrow. **Source:** `services/event-emulator/`.

The emulated half of the city. It injects **causes only** (procession schedules, marathon waves, weather onset,
incidents, ambulance requests, departures, emulated ANPR reads, patrolling units) through the real services' real
APIs, and never produces outcomes (decisions, bands, recommendations). Every row it writes is labelled emulated.
Runs are deterministic (a tape is a function of spec, seed and start time), run-scoped, stoppable and replayable;
a tape whose route is not a legal path on the current network is refused. The **living city**
(`EMULATOR_LIVING_CITY`, off by default) runs a deterministic day program of overlapping emulated causes, and is
refused unless the public pages label emulated events.

### 4.5 signal-ingress

**Stack:** Rust, tokio, arrow, async-nats. **Source:** `services/signal-ingress/`.

Four feed adapters (government traffic, mapping API, fleet GPS, crowdsource) observe one synthetic congestion field
over the Mumbai segments compiled into the binary (`src/feeds/segments_mumbai.rs`, generated by
`scripts/gen_ingress_segments.py` from the City Pack). **No live connector is wired: every row is published as synthetic.** Pipeline:
feeds → bounded channel → eight plausibility checks (future timestamp, stale data, speed jump, phantom reading,
speed z-score, congestion outlier, road-class mismatch, spatial mismatch) → batcher (100 rows or 100 ms) → Arrow
IPC → NATS `corridor.traffic.live`; anomalies to `corridor.traffic.anomaly` with a `feed_quality` field.

### 4.6 corridor-store

PostgreSQL 16 with PostGIS, pgRouting, pgvector and pg_trgm. `scripts/migrate.py` applies `migrations/001–026` in
order and ledgers each (name, checksum, applied time). The seed is generated from the City Pack (§6) and applied in
a fixed order: `sample_corridor.sql` (empty store only) → `reanchor_osm_network.sql` (idempotent, ids preserved) →
`post_seed_derivations.sql` → `display_geometry_osm.sql`.

### 4.7 OSINT services

Off by default (`SAJAG_OSINT=0`). Four Python packages, one runtime container:

| Package | Runs in | Responsibility |
|---|---|---|
| `osint-common` | ingress and oracle | The types (`RawOsintSignal`, situations), the closed vocabulary of event classes, the ethics checks (no person keys, PII detection) |
| `osint-ingress` | its own container, `:8193` | Scheduler and connectors (NDMA Sachet CAP for Maharashtra, Google News RSS, Mumbai outlets' RSS where reachable, GDELT, Reddit RSS, official pages), the allow-listed HTTPS client, robots.txt, redaction at parse, the capture cache, publishing with an outbox |
| `osint-geo` | oracle | Offline gazetteer resolver with transliteration; snapping to the network |
| `osint-analysis` | oracle | Classify, fuse, correlate, score credibility, attach to live events, flag second-order effects |

Rules enforced in code: names and ages are redacted at parse; a single social post is never surfaced and is capped
at credibility 0.30; `OFFICIAL-VERIFIED` needs an official source; a surfaced situation must be located in the city;
`crime_incident` and `vehicle_pursuit` can never come from OSINT.

**Scope: roads, crowds, weather, hazards, closures and services only.** The oracle's ingest screens every signal
with `osint_common.scope`, a deterministic gate (English, Marathi and Hindi cue lists; no model): a person-crime
report, a clash between groups or a political item (elections, polls, candidates, party workers, protests,
morchas and bandhs) is rejected as `out_of_scope_crime`, `out_of_scope_conflict` or `out_of_scope_political` and never stored;
the classifier's `reported_crime`, `public_conflict` and `unrest` classes are refused the same way. A procession or
gathering that bears on a road is kept as a crowd or closure situation, its political terms replaced by
`[WITHHELD]`, so only the place and the road impact remain. Party names are never written in the code: a token is
hashed and compared. Stored signals from before the rule are left out of every re-fusion (their situations are
withdrawn on the next cycle), and `scripts/osint_scope_cleanup.py` (dry-run by default) retires older ones. The
counts by reason are in the ingest reply (`scope`) and the `osint.ingest.counts` log line; no text is logged.

### 4.8 embedding-service

`127.0.0.1:8085`, run by `sajag-embed.service`. Late-interaction memory for "similar past situations":
`pplx-embed-v2-late-0.6b` multi-vector embeddings (128-d per token, MaxSim rerank) with `bge-m3` dense recall
(1,024-d). Routes: `POST /embed/documents`, `POST /search`, `POST /incidents`, `GET /incidents/recent`,
`GET /health`.

### 4.9 model-host and llama-server

- **model-host** (`127.0.0.1:8083`) serves the decider (`pplx-decider-v1.2`, a Qwen3.8-27B fine-tune, 48.6 GiB BF16,
  protocol v3 joint; switched from `pplx-decider-v1-27b` on 29 Oct 2026, p95 1.0 s, see [`docs/ai/decider.md`](ai/decider.md)). API:
  `POST /decide` with `{state, questions}`, at most 6 questions batched into one forward pass; question types
  `choice`, `noul` (a probability), `score`. Explicit errors: 429 when 8 requests are queued, 503 while loading, 413
  when the state exceeds 8,192 tokens (never truncated). No outbound calls.
- **llama-server** (llama.cpp) serves the tactical Gemma 4 12B Q4_K_M GGUF on `127.0.0.1:8084` with 2 parallel
  slots of 8,192 tokens, Prometheus metrics and the GGUF chat template. The twin also uses it to word rationales.

### 4.10 cityfeeds

**Stack:** Python 3.12. **Source:** `services/cityfeeds/`; `127.0.0.1:8199`, run by `sajag-feeds.service`; reached
through the deck as `/api/cityfeeds`. It reads open sources on a polite schedule and labels every number: air
quality at the city's CPCB/MPCB monitoring sites (Open-Meteo CAMS, with WAQI and OpenAQ readings when keyed), heat,
the nearest Arabian Sea cyclone (GDACS), satellite thermal anomalies in the metro box (NASA FIRMS, "not a confirmed
fire"), earthquakes (USGS), the next high water (from hydro, MODELLED) and, for officers, a nearby Mapillary street
photo ("Reference photo · not live", with the date it was taken). Like the AI services it drafts proposals and
never acts. Details: [`ai/cityfeeds.md`](ai/cityfeeds.md).

---

## 5. The AI services

All five are FastAPI services on loopback, reached by the deck through `/api/<service>`. They share one pattern:
**lazy model loading, unload when idle, refuse below a memory floor, label every output, and return proposals,
never actions.**

```mermaid
flowchart LR
    subgraph IN["Inputs"]
        oracle["oracle state<br/>GET only"]
        rain["Open-Meteo rain<br/>LIVE"]
        tide["Apollo Bunder tide<br/>MODELLED"]
        pumps["BMC pump adapter<br/>EMULATED"]
        voice["officer's voice"]
        still["camera still"]
    end
    subgraph SVC["AI services"]
        fc["forecast<br/>Chronos-2"]
        hy["hydro<br/>ponding model"]
        sp["speech<br/>IndicConformer mr·hi · Indic Parler-TTS"]
        vi["vision<br/>Qwen3-VL-8B"]
        tw["twin<br/>cell-transmission model"]
    end
    subgraph OUT["Outputs, all for a named officer"]
        p1["diversion proposals<br/>p10–p90 bands"]
        p2["reroute · ambulance window<br/>live-wire request · advisory draft"]
        p3["field report<br/>UNVERIFIED-FIELD"]
        p4["road state<br/>UNVERIFIED-CAMERA"]
        p5["signal-timing proposal<br/>MODELLED, PROPOSED"]
        audio["advisory audio mr · hi · en<br/>synthetic voice"]
    end
    oracle --> fc
    rain --> hy
    tide --> hy
    pumps --> hy
    hy -->|"rain covariate"| fc
    oracle --> tw
    fc -->|"forecast crossing"| tw
    voice --> sp
    still --> vi
    fc --> p1
    hy --> p2
    sp --> p3
    sp --> audio
    vi --> p4
    tw --> p5
```

| Service | Port | Model (licence) | Runtime | Memory (measured) | Fallback |
|---|---|---|---|---|---|
| forecast | 8195 | Chronos-2 `amazon/chronos-2` (Apache-2.0); TimesFM 2.5 for backtests (Apache-2.0) | PyTorch, GPU | 456 MiB weights, 1.6 GiB peak | Seasonal-naive baseline, stated in `model_note` |
| hydro | 8197 | None (a conceptual model) | Python, CPU | < 512 MiB | Cached rain; offline mode |
| speech | 8194 | `ai4bharat/indic-conformer-600m-multilingual` for Marathi and Hindi (MIT, gated); `openai/whisper-large-v3-turbo` for English and language detection (MIT); `ai4bharat/indic-parler-tts` for Marathi, Hindi and English (Apache-2.0); Svara-TTS v1 (Apache-2.0) + SNAC 24 kHz (MIT) as the fallback | IndicConformer through its pinned remote code (ONNX graphs, RNN-T decoder); Whisper in transformers fp16; Parler in its own venv (parler-tts pins transformers 4.46.1) as a child process over pipes; Svara on llama.cpp (Q8_0 GGUF) | IndicConformer loads against a 4 GiB budget; 5–8 GiB Parler once loaded (11.5 GiB peak while loading) | 503 when memory is short; typed reports need no model |
| vision | 8196 | Qwen3-VL-8B-Instruct Q4_K_M (Apache-2.0) | llama.cpp `llama-server` on 8201 | 7.6 GiB | 503 when memory is short |
| twin | 8198 | None for the timing; the tactical LLM only words the rationale | numpy, CPU | < 768 MiB | Template rationale |

### 5.1 Corridor forecasting (`services/forecast`)

```mermaid
flowchart LR
    hist["history per segment<br/>oracle hourly aggregates + raw rows<br/>(inside the Mumbai bbox only)"] --> q{"≥ 2 days<br/>of real history?"}
    q -->|yes| real["oracle history<br/>LIVE or SIMULATED feed"]
    q -->|no| syn["synthetic Mumbai history<br/>seeded, SIMULATED"]
    real --> vc["V/C from speed<br/>inverse BPR, MODELLED"]
    syn --> vc
    cov["covariates<br/>rain · gate closure · events"] --> model
    vc --> model["Chronos-2<br/>15–120 min, p10/p50/p90"]
    model --> base["seasonal-naive baseline<br/>beside every step"]
    base --> cross{"p50 V/C crosses 0.8<br/>within the horizon?"}
    cross -->|yes| prop["diversion proposal<br/>shortest detour avoiding<br/>other crossing segments"]
    cross -->|no| none["no proposal"]
    prop --> officer["await_officer"]
```

- Covariates: rain (from hydro, LIVE), outfall blocking from the Apollo Bunder tide model (MODELLED), active
  events (a visarjan procession, a Wankhede egress, a station surge).
- Backtest on simulated traffic over the reference pack's network (28 Oct 2026, 780 series): Chronos-2 with
  covariates MAE 0.0429 V/C, coverage 0.797, +54.9 % skill over the baseline. These numbers show the pipeline works;
  they do not measure accuracy on Mumbai roads. The backtest on the Mumbai network (`GET /forecast/metrics`):
  not yet re-run on Mumbai's network.
- Every response carries `data_labels` and `data_note` ("Forecast on simulated traffic" until the oracle stores real
  Mumbai traffic).

### 5.2 Waterlogging nowcast (`services/hydro`)

```mermaid
flowchart TB
    rain["rain nowcast, city grid<br/>Open-Meteo, LIVE<br/>IDW to each segment"] --> step
    tide["Arabian Sea tide at Apollo Bunder<br/>harmonic model, MODELLED<br/>outfalls blocked at ≥ 4.5 m"] --> cap
    pumps["pump availability a<br/>BMC pumping stations, EMULATED"] --> cap
    sus["susceptibility S<br/>DEM + drains + BMC hotspots + Mithi, MODELLED"] --> copen
    copen["C_open = C_MAX − (C_MAX − C_MIN)·S<br/>bounds in hydro config"] --> cap
    cap["C(t) = C_open · (1 − 0.5·gate) · (0.6 + 0.4·a)"] --> step
    step["every 15 min:<br/>W ← max(0, W + (0.85·rain − C)·Δt)"] --> depth
    depth["depth = W/10 · (1 + 2·S) cm<br/>elevated decks: 0"] --> cls
    cls["class 0 dry · 1 shallow · 2 deep · 3 impassable<br/>lead time to peak and to class 2"] --> flag{"class ≥ 2?"}
    flag -->|yes| props["proposals: reroute · ambulance window ·<br/>live-wire request · one advisory draft (en, mr)"]
```

- **The physics is Mumbai's.** The island city drains to the Arabian Sea through outfalls that a high tide backs up
  (floodgates at only 3 of the 45 outfalls, CAG report as reported by Scroll and HT, 3 Jul 2019). BMC's own
  statement of the trigger: waterlogging is unavoidable when about 300 mm of rain falls in a short span and
  coincides with a high tide of about 4.5 m (BMC chief engineer, Free Press Journal, 2025); a tide of 4.5 m or more
  with very heavy rain is the recognised flood trigger (India TV, 27 May 2025). The model encodes exactly
  that: while the modelled tide is at or above 4.5 m the outfalls are blocked, the drainage capacity halves, and
  the bucket fills.
- **Tide.** A harmonic model for Apollo Bunder (Mumbai harbour), labelled MODELLED (approximate); ADR-15 gives the
  reasons. Constants: Admiralty harmonic constants for Mumbai (Apollo Bunder) as given by Unnikrishnan (2022), with N2 and K2 inferred and the mean level fitted. Validation against published Apollo Bunder
  predictions: every BMC-listed high water of 24–28 June and 24–27 July 2025 within 20 min and 0.12 m, low waters within 10 min and 0.25 m (the BMC's high-tide advisories as printed by the Free Press Journal).
- **Pumps.** The six major BMC storm-water pumping stations (Haji Ali, Irla, Love Grove, Cleveland Bunder,
  Britannia, Gazdarbandh) are on the map with an emulated availability. Their real state is not public, and in
  2025 only 4 of 6 pumps at King's Circle were reported working (Free Press Journal), which is why pump state is an
  input and not an assumption.
- **The Mithi.** The Kurla stretch of the Mithi (`mithi_kurla`) is a named hotspot in the susceptibility layer. Its
  level has no open live feed, so no level is shown; on 18–19 Aug 2025 it stood at about 3.9 m against a 4 m danger mark and
  350–500 people were moved near Kurla (reports differ; The Statesman, HT).
- **Hotspots.** BMC counts 386–498 chronic or waterlogging spots by year (Free Press Journal); the on-network ones
  (Hindmata, King's Circle, Sion, Dadar TT, Parel, Andheri Subway, Milan Subway, Kurla) raise susceptibility. The
  capacity bounds and the other parameters are stated assumptions in `services/hydro`.
- **Validation.** The replay of 18–19 August 2025: with the rain gauges' observed totals, the model flagged 9 of the 12 places reported flooded on its network (King's Circle, Andheri Subway, Gandhi Market, Byculla, Dadar TT, Vile Parle, Hindmata, Chembur, Kurla by the Mithi) and missed Sion, Khar and Goregaon. Its own flag came after the first news report at most places (median 51 minutes late: the bucket model fills slowly); with the observed rain as a perfect 2-hour nowcast (hindsight) it would have led the first report at 8 of the 9 (median 69 minutes). The Open-Meteo archive carried a third of the gauges' rain and flagged nothing, which is the case for a live rain-gauge feed. A second replay, 26 May 2025, flagged 5 of 15 reported places. Gridded rain can miss a convective burst (on the
  reference pack's 2025 storm night the Open-Meteo archive held 20.5 mm against 248.8 mm at the IMD gauge), which is
  why a gauge feed (IMD or BMC automatic weather stations) is the pilot's first need.

### 5.3 Voice in Marathi, Hindi and English (`services/speech`)

- `POST /speech/report` takes the browser recording (`audio/webm` or `audio/wav`) or JSON `{"text": …}`. Marathi
  and Hindi go to IndicConformer, English to Whisper. The transcript is matched to a place (fuzzy over `landmarks.json`, the gazetteer and spoken aliases such as
  "हिंदमाता", "किंग्ज सर्कल" or "Andheri subway", with a cross-script consonant skeleton) and to a kind and severity (keyword rules with negation; the deciding words are
  returned). The report is always `UNVERIFIED-FIELD` with `requires_confirmation: true`.
- `POST /speech/speak` returns 24 kHz WAV for Marathi, English or Hindi, with `X-Speech-Label: synthetic-voice`.
  Synthesis is seeded, so one text gives one waveform and the cache is exact.
- Audio is decoded in memory and dropped; there is no speaker identification and no voice storage.
- Evaluation (synthetic round trip: Indic Parler-TTS speaks Mumbai field phrases in Marathi, Hindi and English
  with several trained voices, the ASR transcribes them): Marathi WER 7.1 %, place right in 56 of 56; Hindi WER 14.0 %, 50 of 52 (IndicConformer, synthetic voices); English WER 10.2 % (Whisper turbo) Details in
  [`docs/ai/speech.md`](ai/speech.md). Synthetic audio is not a field set; real recordings are a pilot need.

### 5.4 Road-state vision (`services/vision`)

- `POST /vision/road-state` with a JPEG or PNG returns one of `waterlogged`, `blocked`, `tree_fall`,
  `stalled_vehicle`, `crash_debris`, `congested`, `clear`, `unknown`, a depth band judged against vehicles and
  kerbs (`none`, `below_kerb`, `up_to_wheel_hub`, `above_wheel_hub`), a vehicle estimate and a rationale of at most
  25 words. State `UNVERIFIED-CAMERA`, `requires_confirmation: true`.
- Three layers keep it to roads and vehicles: the system prompt; a query screen that answers person and plate
  questions with 403 before the model is called; and a sentence-level output filter.
- Decoding is constrained by a JSON schema with enums, so the state can never be outside the list. Image metadata
  is stripped.
- Evaluation (12 credited public street photos gathered for the reference pack; a Mumbai photo set, monsoon
  subways included, is still to be built): 11/12 correct; 9/9 refusal probes; median 3.0 s warm.

### 5.5 Signal-timing twin (`services/twin`)

```mermaid
flowchart LR
    req["focus: a junction, a corridor,<br/>or a forecast crossing"] --> dem["demand<br/>LIVE from the oracle if ≥ half the segments,<br/>else SIMULATED weekday profile"]
    dem --> warm["15-min warm-up"]
    warm --> batch["one batched run, 45 min:<br/>do-nothing + ~14 candidates<br/>(extend green, max-pressure,<br/>Webster, green wave)"]
    batch --> guards{"guards:<br/>focus delay −3 % or better;<br/>network delay not up;<br/>cross street ≤ +25 %;<br/>no new spill-back"}
    guards -->|none pass| hold["answer: hold"]
    guards -->|eligible| rank["rank: −(0.45 focus + 0.35 network<br/>+ 0.20 max queue)"]
    rank --> sens["sensitivity at 90 % and 110 % demand<br/>→ confidence (a heuristic)"]
    sens --> prop["proposal object<br/>MODELLED · PROPOSED ·<br/>requires a named officer"]
    prop --> llm["rationale in English and Marathi<br/>from the local LLM; every number<br/>checked against the metrics;<br/>else a template"]
```

- A cell-transmission model (Daganzo) of the whole Mumbai network: 72 junctions and 86
  segments (202 km). For scale, on the reference pack's network (49 junctions, 123 directed links, 5,979 cells)
  30 minutes of simulation take 0.12 s on the CPU and 20 candidates in one batch take 0.85 s; the cost grows with the
  cell count. Results on the Mumbai network: 6 s more green for the Dr Ambedkar Road movement for 30 min: junction delay −14.7 %, network −0.3 %, cross street +20.0 % (shown, inside the 25 % guard), on SIMULATED demand, best of 14 candidates
- Typical focus junctions: `sion_circle`, `kings_circle`, `dadar_tt`, `kalanagar`, `worli_naka`, `haji_ali`.
- Baselines: Webster's cycle and split, and cyclic max-pressure, both simulated against the current program
  (`GET /twin/baselines/{junction}`).
- The twin never writes a signal and has no client for the writer. An approved proposal goes to the oracle's signal
  writer (snapshot, gate, restore), which itself is off by default.

---

## 6. The City Pack

A city is a folder: `cities/<id>/` holds `city.json`, `landmarks.json`, `corridors.json` and `osm/`. Everything
else is derived.

```mermaid
flowchart LR
    subgraph PACK["cities/mumbai/"]
        cj["city.json<br/>names mr/en/hi, bbox, plates,<br/>agencies, emergency numbers"]
        lm["landmarks.json<br/>canonical place ids"]
        co["corridors.json<br/>curated corridors"]
        osm["osm/*.overpass.json.gz<br/>ODbL"]
    end
    build["scripts/city_build.py mumbai<br/>(deterministic, offline)"]
    PACK --> build
    build --> gen["scripts/gen_osm_network.py --city mumbai"]
    gen --> net["cities/mumbai/network.json"]
    gen --> seed["corridor-store seed SQL<br/>sample · reanchor · display"]
    gen --> ev["scripts/data/osm_network.json<br/>(evidence)"]
    build --> rs["signal-ingress<br/>segments_mumbai.rs"]
    build --> uc["oracle use-case scenarios<br/>scripts/scenario_library.json"]
    net --> twin["twin"]
    net --> fc["forecast"]
    net --> hy["hydro"]
    lm --> sp["speech place matcher"]
    cj --> deck["deck city module"]
```

- The Mumbai pack: `city.json` holds the names in English, Marathi and Hindi, the bbox (18.89–19.28 N,
  72.77–72.99 E), MH plates (`MH NN X[X] NNNN`; Sajag never infers an RTO office from a code), the emergency numbers
  (112, 100, 108, 101 and BMC 1916), eighteen agencies (Mumbai Police, Mumbai Traffic Police, BMC and its disaster
  management, MMRDA, Maharashtra SDMA, Mumbai Fire Brigade, ambulance (108), 112, IMD Mumbai, BEST, Central and
  Western Railway, Mumbai Metro, MSRDC, Mumbai Port Authority, among others) and the hydrology (Arabian Sea, Mithi,
  Apollo Bunder, the BMC pumping stations). `landmarks.json` holds the canonical place ids and spellings in all three
  languages: junctions (`hindmata`, `kings_circle`, `sion_circle`, `dadar_tt`, `kalanagar`, `worli_naka`,
  `haji_ali`, `bkc` …), stations (`csmt`, `churchgate`, `dadar`, `kurla`, `andheri` …), venues (`wankhede`,
  `girgaon_chowpatty`, `marine_drive`), hospitals (`kem`, `sion_hospital` …) and the hydro points. The road network
  has 72 junctions and 86 segments (202 km).
- `--check` rebuilds into a temporary folder and compares (4.5 s on 28 Oct 2026). Run twice, the second run changes
  nothing.
- A second, reference pack (`cities/kolkata/`) is kept as the worked example of every file a pack holds, and
  `services/corridor-store/tests/test_city_build.py` builds both.
- Per new city, what changes: the four pack files, a hotspot list and susceptibility build for hydro, the tide
  station, place aliases for speech, the language list, and the agency marks. The services do not change.

---

## 7. Data model

### 7.1 Schemas

| Schema | Tables (selected) | Migrations |
|---|---|---|
| `corridor` | `road_segments`, `junctions`, `segment_adjacency`, `signal_programs`, `signal_program_history`, `signal_plan_log`, `cameras`, `agency_stations`, `vehicles`, `vehicle_earmarks`, `vehicle_sightings`, `vehicle_lookup_audit`, `dispatches`, `dispatch_events`, `protocol_params` | 001, 006, 007, 010–013, 020, 024–025 |
| `traffic` | `observations` (partitioned daily), `hourly_aggregates`, `hourly_aggregates_synthetic`, `synthetic_observations`, `anomaly_log`, `incidents`, `memory_docs`, `segment_embeddings`, `memory_segment_embeddings` | 001–004, 019 |
| `events` | `corridor_events`, `event_routes`, `event_phases`, `event_profiles`, `event_status_log`, `enforcement_recommendations` | 007, 008, 010, 013, 017, 018 |
| `convoy` | `movements`, `planned_routes`, `diversions` | 001 |
| `adaptive` | `situation_log`, `param_overrides` | 005 |
| `simulation`, `emulator` | `runs`, `calibrations`, `emulation_runs` | 006, 009, 016 |
| `osint` | `raw_signals`, `gazetteer`, `geocodes`, `resolved_events`, `event_sources` | 021, 023 |
| `decision` | `decision_support`, `coa`, `coa_sim_runs`, `dss_decision_log` | 022 |

### 7.2 Core entities

```mermaid
erDiagram
    ROAD_SEGMENTS ||--o{ OBSERVATIONS : "measured on"
    ROAD_SEGMENTS ||--o{ HOURLY_AGGREGATES : "rolled up"
    JUNCTIONS ||--o{ ROAD_SEGMENTS : "joins"
    JUNCTIONS ||--o| SIGNAL_PROGRAMS : "runs"
    SIGNAL_PROGRAMS ||--o{ SIGNAL_PLAN_LOG : "changed by"
    CORRIDOR_EVENTS ||--o{ EVENT_ROUTES : "has"
    CORRIDOR_EVENTS ||--o{ EVENT_STATUS_LOG : "audited by"
    CORRIDOR_EVENTS ||--o{ DISPATCHES : "requests"
    VEHICLES ||--o{ VEHICLE_SIGHTINGS : "read as"
    VEHICLE_SIGHTINGS ||--o{ ENFORCEMENT_RECOMMENDATIONS : "may raise"
    CAMERAS ||--o{ VEHICLE_SIGHTINGS : "reads"
    RESOLVED_EVENTS ||--o| DECISION_SUPPORT : "analysed in"
    DECISION_SUPPORT ||--o{ DSS_DECISION_LOG : "decided in"

    ROAD_SEGMENTS {
        bigint segment_id PK
        bigint osm_way_id
        text road_name
        text road_class
        smallint lanes
        smallint speed_limit_kmh
        boolean oneway
        geometry geom
    }
    JUNCTIONS {
        bigint junction_id PK
        text junction_type
        boolean signal_control
        geometry geom
    }
    OBSERVATIONS {
        bigint observation_id PK
        bigint segment_id FK
        timestamptz timestamp_utc
        real speed_kmh
        real congestion_idx
        text source
    }
    HOURLY_AGGREGATES {
        bigint segment_id FK
        timestamptz hour_utc
        real avg_speed_kmh
        integer observation_cnt
    }
    SIGNAL_PROGRAMS {
        bigint junction_id PK
        integer cycle_sec
        jsonb phases
        integer offset_sec
        text source
    }
    SIGNAL_PLAN_LOG {
        bigint plan_id PK
        uuid event_id
        text band
        text shadow_eval
        text actor
        timestamptz applied_at
    }
    CORRIDOR_EVENTS {
        uuid event_id PK
        text event_kind
        text protection_class
        text crowd_class
        text status
        timestamptz planned_start
        timestamptz planned_end
        jsonb metadata
    }
    EVENT_ROUTES {
        uuid route_id PK
        uuid event_id FK
        smallint route_rank
        text label
    }
    EVENT_STATUS_LOG {
        bigint seq PK
        uuid event_id FK
        text from_status
        text to_status
        text actor
        timestamptz at
    }
    DISPATCHES {
        uuid dispatch_id PK
        uuid event_id FK
        text agency
        text status
        text requested_by
        text decided_by
        timestamptz approved_at
    }
    VEHICLES {
        uuid vehicle_id PK
        text plate
        text vehicle_class
    }
    VEHICLE_SIGHTINGS {
        uuid sighting_id PK
        uuid vehicle_id FK
        text camera_id FK
        timestamptz t
        text source
    }
    ENFORCEMENT_RECOMMENDATIONS {
        uuid recommendation_id PK
        uuid sighting_id FK
        text rule_id
        text status
        text decided_by
        jsonb audit_tail
    }
    CAMERAS {
        text camera_id PK
        text kind
        text source
        bigint junction_id
        bigint segment_id
    }
    RESOLVED_EVENTS {
        uuid osint_event_id PK
        text event_class
        text sajag_event_kind
        bigint segment_id
        real credibility
        text verification_state
        int source_count
    }
    DECISION_SUPPORT {
        uuid dss_id PK
        text event_urn
        text state
        jsonb recommendation
        text decided_by
        timestamptz decided_at
    }
    DSS_DECISION_LOG {
        bigint log_id PK
        uuid dss_id FK
        text decision
        text officer
        timestamptz at
    }
```

Rules held by the schema: a watchlist entry needs an enumerated lawful basis and a retention capped at 90 days
(CHECK); recommendation and status logs are append-only; every decision row carries the officer's name; vehicle
lookups by an officer are audited (`vehicle_lookup_audit`, which stores only the masked mark).

### 7.3 Valkey keys and NATS subjects

| Key or subject | Writer | Reader |
|---|---|---|
| `traffic:latest:{segment_id}` | oracle ingest (live feed) | oracle, adaptive engine |
| `traffic:emulated:latest:{segment_id}` | oracle ingest (emulated feed) | emulated events only |
| `adaptive:inputs:{id}`, `emulator:source:{id}` | event-emulator | adaptive engine |
| `convoy:context:{movement_id}` | convoy-brain | convoy-brain |
| `units:emulated:{unit_id}` | oracle ingest | `GET /api/v1/units` |
| NATS `corridor.traffic.live` | signal-ingress | oracle |
| NATS `corridor.traffic.emulated` | event-emulator | oracle |
| NATS `corridor.traffic.anomaly` | signal-ingress | oracle |
| NATS `corridor.units.emulated` | event-emulator | oracle |

The AI services hold no database state. hydro and forecast cache in memory; speech caches synthesized audio by text
hash on a volume.

---

## 8. APIs

Through the deck, each service is reached under its prefix with the prefix stripped: the deck path
`/api/hydro/hydro/nowcast` reaches hydro as `/hydro/nowcast`.

| Service | Route | Purpose |
|---|---|---|
| hydro | `GET /health` | Labels, rain-feed state, network, tide now |
| | `GET /hydro/nowcast` | Per segment: class, depth band, lead times, labelled drivers; class counts; flagged list; proposals |
| | `GET /hydro/tide?hours=1..72` | Apollo Bunder tide series, extremes, gate state, sources (MODELLED) |
| | `GET /hydro/rain` | The grid nowcast and city mean (LIVE) |
| | `GET /hydro/pumps` | BMC pumping-station state (EMULATED) |
| | `POST /hydro/replay?event=<date>` | The replay of a past Mumbai storm (18–19 August 2025) |
| forecast | `GET /forecast/segments?horizon_min=15..120` | Bands per segment, crossings, proposals, data labels |
| | `GET /forecast/segment/{id}` | One segment (404 unknown, 409 not forecast) |
| | `GET /forecast/metrics` | Rolling backtest |
| | `POST /forecast/refresh?backtest=false` | Recompute |
| speech | `POST /speech/transcribe?lang=mr\|en\|hi\|auto` | Transcript |
| | `POST /speech/report?lang=…` | Structured field report (UNVERIFIED-FIELD) |
| | `POST /speech/speak` | WAV, synthetic voice |
| vision | `POST /vision/road-state[?question=]` | Road state (UNVERIFIED-CAMERA); 403 on person or plate questions |
| twin | `GET /twin/network` | Network, cells, junction control, assumptions |
| | `POST /twin/simulate` | A plan against do-nothing |
| | `POST /twin/propose` | The ranked candidates and the proposal (or hold) |
| | `GET /twin/baselines/{junction}` | Current, Webster, max-pressure |
| oracle | `/api/v1/events`, `/api/v1/vehicles`, `/api/v1/enforcement`, `/api/v1/units`, `/api/v1/signals`, `/api/v1/adaptive`, `/api/v1/osint`, `/api/v1/decision-support`, `/api/traffic/segments` | The platform's system of record |
| brain | `/movements`, `/escorts`, `/chat`, `/mcp` | Planning, escorts, the assistant |
| cityfeeds | `GET /feeds/summary`, `GET /feeds/street-image.jpg` | Open city feeds with labels; a street photo for officers |

Every AI service answers `GET /health`. Status codes are explicit: 403 is a policy answer (vision), 409 a state
conflict, 422 invalid input, 429 a rate limit, 503 "the model cannot load now". Samples of each answer are in
[`samples/`](samples/).

---

## 9. Key flows

### 9.1 Live picture → proposal → officer decision → audit

```mermaid
sequenceDiagram
    autonumber
    participant Feed as Feeds and AI services
    participant Ora as traffic-oracle
    participant Deck as command-deck
    participant Ofc as Named officer
    participant Ad as Adapter (signal, advisory)

    Feed->>Ora: observations, situations (labelled)
    Feed-->>Deck: proposals via /api/forecast, /api/hydro, /api/twin
    Deck->>Ofc: Decide: one card, why, what changes, labels
    alt approves
        Ofc->>Deck: Approve (name attached)
        Deck->>Ora: POST decision with x-sajag-officer
        Ora->>Ora: validate, append to the audit log
        Ora->>Ad: apply (emulated adapter today)
        Ora-->>Deck: Approved, recorded with the officer's name
    else rejects
        Ofc->>Deck: Reject with a reason
        Deck->>Ora: POST decision
        Ora->>Ora: append to the audit log
    else no answer before the deadline
        Ora->>Ora: proposal expires, logged
        Note over Ora,Ad: the current plan holds — nothing is applied
    end
```

The server refuses a decision without a named officer (409 or 422; the deployed stack sets
`VVIP_REQUIRE_OFFICER=1`). Approve
controls exist only in Decide and the analyst workspace, never on the map, in the assistant or on public pages.

| Decide: signal timing | Audit trail |
|---|---|
| ![Decide: a signal-timing proposal tested in the twin](screenshots/decide-ai.jpg) | ![The audit trail in the Analyst workspace](screenshots/audit.jpg) |
| *A signal change tested in the twin against doing nothing, the cross street's cost shown too (MODELLED).* | *Every action with its time, actor and object; filters for officers, machines and the system.* |

### 9.2 A field voice report

```mermaid
sequenceDiagram
    autonumber
    participant Ofc as Officer (phone or console)
    participant Deck as command-deck
    participant Sp as speech :8194
    participant Ora as traffic-oracle

    Ofc->>Deck: records a report in Marathi, Hindi or English (MediaRecorder)
    Deck->>Sp: POST /speech/report (audio/webm)
    Sp->>Sp: decode in memory, ASR, place match, kind and severity rules
    Sp-->>Deck: report: place, candidates, kind, severity, cues, UNVERIFIED-FIELD
    Note over Sp: audio dropped — no speaker identification
    Deck->>Ofc: "Field report · unverified" with the transcript
    Ofc->>Deck: confirm, edit or dismiss
    Deck->>Ora: confirmed report enters the board, attributed
```

| Field report by voice | Field report in Marathi |
|---|---|
| ![A field report spoken in English](screenshots/voice-report-en.jpg) | ![A field report spoken in Marathi](screenshots/voice-report.jpg) |
| *Speech becomes place, kind and severity with the words that decided it; unverified until an officer confirms.* | *Spoken Marathi, transcribed on the server and matched to its place.* |

### 9.3 A waterlogging alert reaching citizens

1. A heavy burst arrives an hour before a 4.6 m high tide at Apollo Bunder. hydro flags Dr Ambedkar Road at
   Hindmata at class 2 with a 45-minute lead, and King's Circle at class 1 (MODELLED drivers shown: rain LIVE, tide
   MODELLED, pumps EMULATED).
2. The deck shows the reroute, the ambulance window to KEM, the live-wire request and one advisory draft in English
   and Marathi; the advisories page words it for every audience in all three languages.
3. An officer approves the advisory; it appears on `/citizen`, where the Listen button calls `/api/speech/speak`
   (allow-listed, rate-limited) and the audio is marked "synthetic voice".

| Decide: waterlogging | Advisories |
|---|---|
| ![Decide: waterlogging proposals in the exercise](screenshots/decide-waterlogging.jpg) | ![Advisories in three languages](screenshots/advisories.jpg) |
| *A reroute around deep water in the storm-replay exercise (MODELLED, Hindsight).* | *One fact for four audiences in three languages, marked exercise text; drafted, never sent on its own.* |

### 9.4 The ambulance (108) corridor request

The crew taps one button on `/driver` (for example a 108 unit on Dr Ambedkar Road heading to KEM during a
waterlogging alert); the request (rate-capped per client) becomes a PENDING dispatch for a named duty officer; the
crew sees the status. The crew always follows 108 control; Sajag claims no partnership with the
108 operator.

| Ambulance (108) crew | Decide: a 108 corridor request |
|---|---|
| ![The ambulance crew page on a phone](screenshots/driver.jpg) | ![Decide: an ambulance (108) corridor request](screenshots/decide-corridor.jpg) |
| *One request for a corridor window, its four steps; a duty officer decides.* | *A 108 crew's corridor request: the golden hour left and what changes if approved, for a named officer.* |

---

## 10. State machines

### 10.1 A proposal

```mermaid
stateDiagram-v2
    [*] --> PROPOSED: AI service, rules engine or decision support
    PROPOSED --> APPROVED: named officer approves
    PROPOSED --> REJECTED: named officer rejects
    PROPOSED --> EXPIRED: deadline passes (escorts) or superseded
    APPROVED --> APPLIED: adapter acts (emulated today)
    APPLIED --> REVERTED: duration ends or officer restores
    EXPIRED --> [*]: current plan holds
    REJECTED --> [*]
    REVERTED --> [*]
```

### 10.2 A corridor event

```mermaid
stateDiagram-v2
    [*] --> planning
    planning --> approved: officer
    planning --> cancelled
    approved --> active: start
    approved --> cancelled
    active --> completed: clear
    active --> cancelled
    completed --> [*]
    cancelled --> [*]
```

Every transition is written to `events.event_status_log` with its actor.

### 10.3 A field or camera reading

`UNVERIFIED-FIELD` / `UNVERIFIED-CAMERA` → confirmed by a named officer (enters the board as an event) or dismissed.
Neither state ever triggers an action by itself.

---

## 11. Security

### 11.1 Trust boundaries

```mermaid
flowchart LR
    subgraph Z0["Untrusted: LAN and internet"]
        b["Browser"]
        src["Open sources<br/>news, alerts, rain"]
    end
    subgraph Z1["Edge: the deck, 0.0.0.0:5373"]
        gate["operator gate<br/>CSP, proxy pinning,<br/>ingest refusal"]
    end
    subgraph Z2["Loopback services"]
        svc["oracle · brain · emulator ·<br/>AI services · model hosts · stores"]
    end
    b --> gate --> svc
    src -->|"allow-listed HTTPS,<br/>redaction at parse"| svc
```

### 11.2 Operator gate

- Opt-in with `SAJAG_OPERATOR_PIN`. `POST /api/session` takes the officer's name and the PIN and sets a signed,
  HttpOnly session cookie (`SAJAG_SESSION_SECRET`; `SAJAG_SESSION_SECURE=1` behind TLS).
- Without the cookie, every proxied request is default-denied (403), decided on the canonical (once-decoded) path.
- Public exceptions: road geometry, liveness probes, the ambulance request (rate-capped), and for the AI services an
  allow-list: `GET` of the hydro nowcast, tide and rain (no forced refresh), and `POST /api/speech/speak` with a JSON
  body of at most 400 characters, at most 10 requests per client per minute. Transcription, field reports, vision,
  the twin, forecasts, the replay and every proposal need a signed-in officer.
- `sajag_up.sh --status` reports a deck on the LAN with the gate off as DEGRADED.

### 11.3 Officer attribution

Every decision carries the officer's name (`x-sajag-officer`), checked on loopback by the oracle and written to the
audit tables. "Naming yourself shows full registration marks on this console and records your name with the
decision. Attribution, not sign-in."

### 11.4 Content-security policy and headers

Nonce-based CSP per document: self, Google Fonts, OSM tiles and Cesium ion; `frame-ancestors 'none'`. Public pages
get no `eval` and no blob scripts; operator pages allow what Cesium needs. Every response: `nosniff`, a referrer
policy, `DENY` framing, and a permissions policy with no geolocation (the citizen page promises it collects no
location). The permissions policy allows the microphone for the deck's own origin only on the operator pages that
host the voice-report sheet; public pages deny it.

### 11.5 Network exposure

Only the deck binds the LAN. Every other service, model host and store binds 127.0.0.1. The deck's proxy targets
are fixed loopback hosts (only ports are configurable), and the upstream origin is re-checked after URL
construction. Outbound calls: Open-Meteo (hydro), allow-listed OSINT hosts (osint-ingress), the open feeds (cityfeeds), and
Cesium ion from the officer's browser when a token is set. Model weights are never downloaded at run time.

### 11.6 Vehicles only, plate masking

- No person, face or biometric field exists in the schema. Camera sites store location and identity only.
- Plates are masked (`MH01AB•••4`) on every surface until a named officer is on duty; exports, share links and
  saved views are always masked. The oracle masks every label and feed text it sends; the deck masks everything it
  renders; both use the same rule (a test keeps them in parity).
- Vision refuses person and plate questions (403) and filters person sentences from its output.

| Decide: the mark masked until an officer is named | Assistant: vehicles, never people |
|---|---|
| ![Decide: the stolen-vehicle sheet with the mark masked](screenshots/decide-masked.jpg) | ![The assistant answering a question about a person with vehicle facts only](screenshots/assistant-refusal.jpg) |
| *No officer named: the mark is masked and every button waits for a name.* | *Asked about the driver, it answers about the vehicle only: no owner or personal details exist.* |

### 11.7 Secrets

Secrets live only in `~/.config/sajag/sajag.env` (mode 600), set with `scripts/sajag_env.sh --set KEY -` so
the value never appears in argv or shell history. `scripts/secret_scan.sh` and a CI job scan the tree. No service
logs a secret. See [`ENVIRONMENT.md`](ENVIRONMENT.md).

### 11.8 Container hardening

The twin runs with a read-only root filesystem, every capability dropped, `no-new-privileges`, a non-root user and
a memory cap. The AI services have memory limits (forecast 6 GiB, hydro 512 MiB, speech 20 GiB, vision 1 GiB, twin
768 MiB) and rotated logs.

---

## 12. Privacy

Sajag is designed in the spirit of the Digital Personal Data Protection Act, 2023:

| Principle | In Sajag |
|---|---|
| Purpose limitation | Traffic, rain and crowd operations; no profiling of people |
| Data minimisation | Vehicles and places only; no faces; plates masked by default |
| Storage limitation | Watchlist retention capped at 90 days (schema CHECK); observations partitioned daily and dropped after 14 days; OSINT capture cache bounded (72 h or 200 MB) |
| Voice | Audio decoded in memory and dropped; only the transcript leaves the speech service, and it enters the board only when an officer confirms the report |
| Images | Processed in memory and re-encoded, which strips metadata; the vision service stores no image |
| OSINT | Aggregate only; names and ages redacted at parse; news and social URLs reduced to the outlet's domain and a hash |
| Citizens | Public pages collect no location and need no account |
| On premises | Data stays on the edge server; no cloud inference |

---

## 13. Reliability and degradation

- **Fail closed.** A missing officer, a failed shadow evaluation or an unreachable adapter never turns into an
  action. The adaptive engine falls back to baseline; the signal writer writes nothing.
- **Explicit degradation.** The oracle's guarded router registration answers 503 "not deployed" for a module that
  cannot import, and its degradation ledger lists every degraded path.
- **Models.** Lazy load, idle unload (forecast 600 s; speech and vision 10 minutes), memory floors (speech 12 GiB,
  vision 8 + 12 GiB) and 503 when a model cannot load. The forecast serves its baseline if the model breaks and says
  so; the twin uses a template when the LLM is busy or wrong; typed voice reports need no model.
- **Feeds.** hydro serves cached rain when rate-limited and runs offline (`SAJAG_HYDRO_OFFLINE=1`). OSINT parses its
  newest capture, labelled `cached-sample`, when a live fetch fails.
- **Connectivity.** Everything runs on one box; a red-alert monsoon night or a cyclone that cuts the internet leaves
  the console, the models, the tide model and the twin working.
- **Boot.** `sajag.target` starts the stack at boot; `sajag_up.sh --boot` waits for Docker and converges.

---

## 14. Observability

| Signal | Where |
|---|---|
| Readiness | `scripts/sajag_up.sh --status` (one row per component and a security row) |
| Health | `GET /health` on every service; AI services report model slot, memory, labels and upstream reachability |
| Metrics | Prometheus `/metrics` on convoy-brain, model-host and llama-server |
| Audit | `events.event_status_log`, `events.enforcement_recommendations.audit_tail`, `corridor.signal_plan_log`, `decision.dss_decision_log`, `corridor.vehicle_lookup_audit`, the brain's decisions log |
| Degradation | `GET /api/v1/ops/degradation-taxonomy` |
| Logs | Docker json-file logs, rotated (10 MB × 3 for the twin); `SAJAG_LOG_DIR` for host units |
| NATS | Monitoring on `127.0.0.1:8233` (`/varz`, `/connz`) |

---

## 15. Deployment and capacity

### 15.1 Reference hardware

One NVIDIA GB10 edge server (arm64, 121 GiB unified memory) beside the control room. The platform services also run
on any x86-64 or arm64 machine with Docker; without the model hosts the brain falls back to its heuristic tier and
says so.

### 15.2 Memory budget (measured on the reference box)

| Process | Resident |
|---|---|
| Decider (model-host) | 49.0 GiB |
| Tactical LLM (llama-server, Gemma 4 12B Q4_K_M, 2 × 8k slots) | 7.3 GiB |
| Embeddings (pplx-embed + bge-m3) | ≈2.2 GiB |
| Platform services and stores | ≈12 GiB planned |
| Qwen3-VL-8B (vision, on demand) | 7.6 GiB |
| Speech ASR (on demand: IndicConformer for mr/hi, Whisper turbo for en) / TTS (on demand) | 4 GiB load budget per ASR model / ≈4.8 GiB |
| Chronos-2 (on demand) | 1.6 GiB peak |

The on-demand models load lazily and unload when idle, so the box keeps headroom for the resident ones.
When a speech or vision load would break its 8 GiB floor, the service first asks the other on-demand services
to release every model not serving a request (`POST /admin/release`, loopback), waits up to 5 s and re-checks the
same floor (a load that passed the floor but ran out of GPU memory makes room the same way and is tried once more);
released models reload on their next use, and the resident models are never touched.

### 15.3 Scaling

- **More cities:** a new City Pack and a build (§6); one box per city or district control room.
- **More load:** the deck is stateless behind its proxy and can be replicated; the oracle is the single writer to
  the store; the AI services are independent processes that can move to a second box (their URLs are settings).
- **Pilot costs** and the next packs are in [`../PRODUCT.md`](../PRODUCT.md).

---

## 16. Testing strategy

| Level | What | Count |
|---|---|---|
| Unit and API (Python) | Every service, offline, outbound calls mocked | 6,443 passed |
| Real-model (opt-in) | forecast `-m model`, speech and vision `-m slow` | run on the box with weights |
| Rust | signal-ingress | 121 passed |
| Deck | `svelte-check`, design-token and copy lints, Marathi-script check, 46 unit suites, contract replay, proxy guard | see [`SAMPLE_DATA_AND_TESTS.md`](SAMPLE_DATA_AND_TESTS.md) |
| City Pack | `city_build.py --check`; a test builds two cities (Mumbai and the reference pack) | pass |
| Gates | `run_gates.sh` over the tree | 69 green |
| Browser smokes and journeys | Screens against a running stack | on demand |
| Acceptance ladder | `scripts/verify_all.sh` (offline) and `--live` | on demand |

Principles: an ethics rule is tested as behaviour (a 409, a 403, a refusal before the model call), never only as
copy; tests that need a live service or a model are opt-in and say so; a test that hard-codes city facts reads them
from the City Pack.

---

## 17. Architecture decision records

Each record states the context, the decision and its consequences.

### ADR-01 — All AI runs on premises

- **Context.** City operations data (traffic, plates, officer decisions) should stay with the city, and the
  control room must keep working on the nights it matters most: a red-alert monsoon night, or a west-coast cyclone
  such as Tauktae (May 2021), when power and links are at risk.
- **Decision.** Every model runs on one edge server beside the control room; no cloud inference; weights are fetched
  once at install and served with `HF_HUB_OFFLINE=1`.
- **Consequences.** No per-call fees and no data egress; the console works offline. Model choice is bounded by one
  box's memory (§15.2), so models are small or quantized and load on demand.

### ADR-02 — The City Pack: a city is a folder

- **Context.** The platform was first built for another city, and city facts ran through the whole codebase.
- **Decision.** Move everything city-specific into `cities/<id>/` and generate every derived file with
  `scripts/city_build.py`, deterministically and offline, with a `--check` mode.
- **Consequences.** A new district is a new folder and a build; a test builds two packs; drift between the pack and
  the services is caught by `--check`.

### ADR-03 — Chronos-2 zero-shot instead of training a model

- **Context.** There is no recorded Mumbai traffic history (from Mumbai Traffic Police detectors or any feed) to
  train on yet.
- **Decision.** Use Chronos-2, a zero-shot, covariate-aware foundation model (Apache-2.0), with TimesFM 2.5 as a
  second contender and a seasonal-naive baseline beside every forecast; label everything "forecast on simulated traffic"
  until real history exists.
- **Consequences.** Forecasts from day one with honest labels and a backtest; when history accumulates, the same
  pipeline reads it (`data_source=auto`). A trained model can be added later as another contender.

### ADR-04 — Test every signal change in a twin before an officer sees it

- **Context.** "Give the busy road more green" often moves the queue to the cross street or the next junction.
- **Decision.** Every signal-timing proposal is simulated over the whole network in a cell-transmission model
  against doing nothing, with guards (network delay, cross street, spill-back, minimum gain), a sensitivity check
  and a confidence; the twin has no client for the signal writer.
- **Consequences.** Proposals arrive with their modelled side effects; "hold" is a valid answer. Macroscopic
  limits (PCU, assumed turning ratios, template programs) are stated in each proposal.

### ADR-05 — The LLM words, it never decides timings or numbers

- **Context.** A language model can invent numbers.
- **Decision.** The twin and the ranking choose; the LLM writes a short rationale in English and Marathi, and a
  validator rejects any number not in the twin metrics and any Marathi with stray Latin or another script, falling
  back to a template.
- **Consequences.** Rationales are readable and safe; the validator checks numbers and script, not meaning.

### ADR-06 — English first, Marathi and Hindi throughout

- **Context.** Marathi is the state language and the language of many field officers and residents; Hindi is
  spoken across the city; officers across agencies and visitors share English.
- **Decision.** UI languages `en`, `mr`, `hi`; every page, public pages included, opens in English and switches to
  मराठी or हिंदी in one tap, remembered per browser; Noto Sans Devanagari self-hosted for both; voice reports in
  Marathi, Hindi or English; advisories read aloud in the page's language; a Marathi-script lint on every pack
  (Devanagari only, Marathi's ळ and eyelash ऱ allowed, no other script mixed in); place matching across scripts.
- **Consequences.** Every string exists three times and the lint enforces parity; a native read is still advised
  before a pilot.

### ADR-07 — Emulated adapters with honest labels

- **Context.** BMC pump and sensor data, Mumbai Traffic Police signal controllers and detectors, ANPR, CCTV,
  108 fleet GPS and BEST and railway running status are not public.
- **Decision.** Build each integration as an adapter interface with an emulated implementation that labels every
  record EMULATED; the pilot plan names the access each one needs.
- **Consequences.** The full flow can be shown and tested today without pretending; swapping in a real feed changes
  one class.

### ADR-08 — Vehicles-only vision

- **Context.** A general vision-language model will describe people if asked.
- **Decision.** Constrain Qwen3-VL to road states with a JSON schema, refuse person and plate questions before the
  model is called (403), and filter person sentences from its output; depth bands are judged against vehicles and
  kerbs, never a person's body.
- **Consequences.** The guarantee holds even if the model ignores its prompt (tested on real unguarded output). The
  person filter works on English text, so the model is instructed to answer in English.

### ADR-09 — The AI proposes; a named officer decides; no answer means the plan holds

- **Context.** Automated actions on roads affect lakhs of people and must be accountable.
- **Decision.** Every AI output is a proposal (`requires_officer: true`); the server refuses unnamed decisions;
  time-boxed proposals expire to "the current plan holds"; the assistant's tools cannot approve.
- **Consequences.** Slower than full automation by design; every action has a name in the audit log.

### ADR-10 — Loopback-only services behind one deck proxy

- **Context.** Several services can write city state.
- **Decision.** Only the deck binds the LAN; it proxies fixed loopback targets, pins the upstream origin, refuses
  machine-ingest paths from browsers, and applies the operator gate and an allow-list for public AI reads.
- **Consequences.** One place to audit exposure; the deck must be the only route for browsers (tested by
  `no-live-port`).

### ADR-11 — A conceptual ponding model for waterlogging, not a sewer model

- **Context.** BMC's storm-water drain network data is not public, and a nowcast must run every few minutes on the
  CPU.
- **Decision.** A bucket model per segment with stated parameters, drainage capacity bounded by public statements,
  driven by rain, the tide and pump state, with terrain susceptibility from open data and BMC's named hotspots;
  replayed against the reports of a past Mumbai storm (18–19 August 2025).
- **Consequences.** Explainable and fast; not calibrated beyond one event; a hydraulic model (for example SWMM) can
  replace it when BMC data is available.

### ADR-12 — Open models with a measured choice and a documented fallback

- **Context.** Voice must work in Marathi, Hindi and English on one box, with open weights.
- **Decision.** AI4Bharat IndicConformer 600M multilingual for Marathi and Hindi (one model, 22 Indian languages,
  remote code pinned to a reviewed commit); Whisper large-v3-turbo for English and language detection; AI4Bharat
  Indic Parler-TTS for speech in all three languages, with its trained Marathi, Hindi and English voices; Svara-TTS
  on llama.cpp as the fallback. Every model sits behind the same small interface and is chosen by measurement on the
  same audio.
- **Consequences.** One API for three languages and an upgrade path that changes no API. Indic Parler-TTS beat
  Svara on the earlier round trip (WER 8.2 % against 11.2 %, half the synthesis time) and is live. The Marathi and
  Hindi measurement: Marathi WER 7.1 %, place right in 56 of 56; Hindi WER 14.0 %, 50 of 52 (IndicConformer, synthetic voices); English WER 10.2 % (Whisper turbo)

### ADR-13 — llama.cpp for the vision model and TTS

- **Context.** The edge server is arm64 and shared with resident models.
- **Decision.** Run Qwen3-VL-8B (Q4_K_M) and Svara-TTS (Q8_0) on `llama-server`, started on demand on loopback,
  stopped when idle, refused below a memory floor.
- **Consequences.** No heavy Python ML stack in the vision service; schema-constrained decoding; TTS about 2.4× faster
  than transformers on the box.

### ADR-14 — One PostGIS store as the system of record

- **Context.** Events, routes, decisions and audit must be consistent and spatial.
- **Decision.** PostgreSQL 16 with PostGIS, pgRouting and pgvector; the oracle is the single writer; additive,
  ledgered migrations.
- **Consequences.** Simple operations and one backup; the AI services stay stateless.

### ADR-15 — A tide model from cited constants instead of an unavailable table

- **Context.** Mumbai's flood trigger is a heavy burst at a high tide of about 4.5 m (BMC, Free Press Journal 2025),
  so the nowcast needs the tide at the harbour every 15 minutes. The official Apollo Bunder predictions are published
  in the Survey of India tide tables, which are not available as open data.
- **Decision.** Compute the Apollo Bunder tide from cited harmonic constants (the sources are listed in
  `services/hydro`), check it against published high-water predictions, and label it MODELLED (approximate). The
  outfalls are treated as blocked while the modelled level is at or above 4.5 m.
- **Consequences.** A usable gate-closure signal now; replace with the official constants or a gauge feed (Mumbai
  Port Authority or the Survey of India) in a pilot.

---

## 18. Known limitations

- Traffic is simulated until the oracle receives a real Mumbai feed (Mumbai Traffic Police detectors or a licensed
  mapping feed); forecasts and twin demand say so.
- Rain is a model nowcast; gridded products can miss a convective burst. A gauge feed (BMC or IMD automatic weather
  stations at Santacruz, Colaba and across the wards) is the pilot's first need.
- BMC pumps, signal controllers, ANPR and CCTV are emulated or not connected; the Mithi level has no open live feed and is not shown.
- The tide is a harmonic model, not the official table or a gauge.
- The road network covers 86 arterial segments (202 km); many of the hundreds of BMC flooding
  spots are off it.
- Suburban rail and BEST running status are not read; a station surge is a scenario, not a measurement.
- Speech was evaluated on synthetic audio; vision on 12 photos from the reference pack's city. Real Mumbai field sets
  (monsoon subways, Marathi and Hindi voice) are needed before a pilot.
- The twin is macroscopic with assumed turning ratios and template programs.
- The regional SAR flood-extent layer (Prithvi-EO-2.0 on Sentinel-1) is planned, not built.
