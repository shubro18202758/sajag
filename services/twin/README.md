# twin: the signal-timing twin

Every AI signal-timing proposal in Sajag is first tested here, in a
macroscopic traffic model of the city (the "twin"), before an officer sees
it. The twin simulates each candidate change against **doing nothing** over
the whole road network and returns a **proposal object**, never an action:

```json
{
  "kind": "extend_green",
  "junction_ids": [20],
  "change": {"summary": "Give the main-road (through) movement at Dadar TT Circle 6 s more green for 30 min ...",
             "programs": {"20": {"cycle_sec": 110, "offset_sec": 0, "phases": [{"green_sec": 56, "movements": ["through"]}, {"green_sec": 36, "movements": ["cross"]}]}},
             "revert_to": {"20": {"...": "the current program"}}},
  "duration_min": 30,
  "twin_metrics": {"delay_change_pct": -6.6, "max_queue_change_m": 0, "cross_street_delay_change_pct": 13.1,
                   "network_delay_change_pct": -0.1, "spillback_change_min": 0, "...": "do-nothing and with-change values, per approach, queue series"},
  "confidence": {"score": 0.37, "level": "low", "basis": ["..."]},
  "assumptions": ["..."],
  "verification_state": "MODELLED",
  "requires": "named officer approval",
  "status": "PROPOSED",
  "if_no_decision": "the current plan holds",
  "rationale": {"en": "...", "mr": "...", "source": {"en": "llm", "mr": "llm"}}
}
```

The twin has no client for the platform's signal writer: it cannot change a
signal. A named officer approves or rejects a proposal; if no one decides,
the current plan holds.

## Honest labels

* Every result is **MODELLED** (a traffic model, not measured traffic).
* Demand is **SIMULATED** (the assumed Mumbai weekday profile below) unless
  the traffic-oracle answers with live state for at least half the
  segments; then it is **LIVE**, or **EMULATED** when the oracle marks its
  rows synthetic.
* Signal programs are the network's **MODELLED** templates (`osm_assumed`),
  not controller timings. A crossing with no program gets the same template,
  labelled `twin-assumed template`.
* The confidence score is a modelled heuristic, not a probability.

## Method

**Network.** `cities/<city>/network.json` (schema `sajag.network/1`, or the
evidence file `scripts/data/osm_network.json`). Each segment becomes one or
two directed links; `lanes` counts both directions on a two-way road, so a
link gets half. Each approach is mapped to the program's movement label the
way traffic-oracle does it (`enforcement/rules.py` `through_legs`): the best
pair of legs within 75 deg of straight is `through`, the other legs are
`cross`. Junction control is `programmed` (the network has a program),
`assumed` (a named crossing, or 3+ legs that are not a flyover interchange),
`uncontrolled` (one road continuing into the next) or `boundary`. When a
crossing's cross road is not in the network (12 of the 72 junctions of the
Mumbai network v1), a virtual 2-lane cross street is
added so cross-traffic delay is still counted.

**Cell-transmission model** (Daganzo 1994/1995), vectorised in numpy with a
leading candidate axis so many plans run in one pass:

* cells no shorter than one free-flow step (`dx >= vf*dt`, dt = 2 s, at
  least 40 m): 8,730 cells on the Mumbai network v1;
* triangular fundamental diagram per lane: saturation flow by road class
  (1,000-1,900 PCU/h/lane), jam density 140 PCU/km/lane, free-flow speed =
  speed limit, backward wave speed `w = q_max / (k_jam - k_crit)`;
* sending `S = min(n vf dt/dx, Q)`, receiving `R = min(Q, w dt/dx (N - n))`;
* junctions: movements with turning ratios plus a side-street sink; a signal
  caps an approach at `Q * g` (g = green fraction of the step from the
  platform's phase clock `(epoch - offset) mod cycle`, lost time at the end
  of the cycle); a proportional merge; first-in-first-out at the diverge,
  relaxed by lane count (a blocked turn holds back `1/lanes` of the
  approach), never sending more than an exit can take;
* side-street traffic enters every link through a point queue.

**Demand.** Target flow per link and minute = v/c (by road class, at the
profile peak) x time-of-day factor x directional factor (evening: away from
the centre +12%, towards it -12%; morning the reverse) x the link's
effective capacity (saturation flow x the green share at its signal). The
turning ratios at each junction are fitted by biproportional (Furness)
balancing so every link carries its target flow in steady state (no
amplification by traffic circulating through the network). A forecast
crossing in a request (`{junction, segment_ids, vc, in_min}`) ramps the
named approaches to that v/c. The first 15 minutes are a warm-up, so queues
at signals are in a cyclic steady state when measurement starts.

**Baselines.**

* *Webster*: `C0 = (1.5 L + 5) / (1 - Y)` and greens in proportion to the
  critical flow ratios, clamped to 60-180 s, minimum green 15 s, flagged
  `oversaturated` at Y >= 0.95.
* *Max-pressure* in its cyclic form (Varaiya 2013; Le et al. 2015): the
  program's cycle, phase order, offset and lost time stay; each cycle the
  split moves towards the split proportional to the cycle-average phase
  pressure (saturation flow x queue upstream minus turning-weighted queue
  downstream; queue = occupancy above critical density), by at most 4 s per
  phase per cycle, with a 2 s deadband and a 15 s minimum green.

**Proposal engine** (`POST /twin/propose`):

1. A do-nothing run finds the most delayed movement at each focus junction.
2. Candidates: extend that movement's green by 6/10/15/20 s for 20 or 30 min
   (taken from the other phase, cycle and offset unchanged, nothing below
   15 s); the other movement by 6/10 s; max-pressure for 20/30 min;
   Webster's cycle and split for 20/30 min (this one changes the cycle, so
   the summary says coordination with neighbours is not kept); on a
   corridor, a green wave (offsets for a platoon at 70% and 85% of the
   free-flow speed) and the corridor movement +6/+10 s at every signal.
3. All candidates (about 14 for one junction) and do-nothing run in one
   batched pass over the whole network from the same warmed-up state (45 min
   horizon by default).
4. Guards: a candidate is eligible only if it cuts delay at the focus by at
   least 3%, does not raise network delay (it would only move the jam),
   does not raise cross-street delay by more than 25% (request
   `cross_street_tolerance_pct`) and adds no spill-back in the network.
5. Score (eligible ones first): `-(0.45 focus delay % + 0.35 network delay %
   + 0.20 max queue %)`.
6. Confidence: is the gain still there at 90% and 110% of the demand, times
   0.7 for SIMULATED (0.85 EMULATED, 1.0 LIVE) demand, times 0.8 when the
   junction's baseline is a twin-assumed template.
7. If nothing passes the guards, the answer is **hold** and the full ranking
   says why.

**Rationale.** The twin and the ranking choose the timing; the local LLM
(`:8084`, OpenAI-compatible) only explains a result that is already fixed.
One short call for English, then one for Marathi, one at a time across the
process (a second request gets the template instead of queueing), 20 s
timeout. Each reply is checked on its own: every number must appear in the
facts built from the twin metrics (Western or Marathi digits), and the
Marathi must be Marathi (no stray Latin words beyond the place names in the
facts, no other script). A missing or failed language falls back to a
template that uses only metric numbers. The validator checks numbers and
script, not meaning.

## API

| | |
|---|---|
| `GET /health` | service, network, oracle and LLM status |
| `GET /twin/network` | which network, cells, links, movements, junction control, assumptions |
| `POST /twin/simulate` | `{start, horizon_min, demand: {mode, scale, forecasts}, plan: {windows: [{junction, from_min, to_min, control: fixed\|max_pressure, program}]}, focus_junctions}` -> metrics, do-nothing, change, queue time series (per minute), timing |
| `POST /twin/propose` | `{junction_ids \| corridor: {segment_ids \| junctions}, horizon_min (30-60), start, demand_mode, forecast, cross_street_tolerance_pct, explain}` -> do-nothing, ranked candidates, the proposal (or hold), timing |
| `GET /twin/baselines/{junction}` | current program, Webster (cycle, splits, Y, flows used) and max-pressure, each simulated against the current program |

Junctions are named by id or by landmark key (`dadar_tt`, `hindmata`,
`kings_circle`, ...). `start` is `HH:MM` (IST, today) or an ISO time.

## Run

```
cd services/twin
SAJAG_TWIN_PORT=9171 SAJAG_TWIN_NETWORK=../../cities/mumbai/network.json \
  PYTHONPATH=src python -m sajag_twin
```

| variable | default |
|---|---|
| `SAJAG_TWIN_HOST` / `SAJAG_TWIN_PORT` | `127.0.0.1` / `8198` |
| `SAJAG_TWIN_NETWORK` | the City Pack's `network.json` |
| `SAJAG_TWIN_ORACLE_URL` | `http://127.0.0.1:8191` (GET only; empty = off) |
| `SAJAG_TWIN_LLM_URL`, `SAJAG_TWIN_LLM` | `http://127.0.0.1:8084`, `1` |

Container: `infra/docker/Dockerfile.twin` (repo root context; the image
carries `cities/`) and `infra/compose.twin.yml` (host network, binds
127.0.0.1:8198 itself, read-only root, no capabilities, non-root uid 10008).

Tests: `python -m pytest -q -p no:cacheprovider` (51 tests; the Mumbai ones
run when `cities/mumbai/network.json` is in the tree or `SAJAG_TWIN_NETWORK`
names it, and one loads the second City Pack, `cities/kolkata/network.json`,
to keep the twin city-agnostic).

## Validation (tests/test_ctm_physics.py, test_webster.py)

| check | expected | twin |
|---|---|---|
| lane drop 3,600 -> 1,800 PCU/h, demand 2,700 | discharge 1,800 PCU/h | 1,800 PCU/h, exit 1,800 |
| queue-tail (shock) speed | LWR -2.174 m/s (-7.83 km/h) | -2.170 m/s (-0.2%) |
| queue density behind the bottleneck | 190 PCU/km (k_jam - q_b/w) | 190 |
| free-flow platoon over 2 km at 72 km/h | arrives after 100 s | none before 90 s, all by 170 s |
| fixed signal, g/C = 0.5, 3,600 PCU/h sat. | 1,800 PCU/h when saturated; demand when not | within 3% |
| conservation | entered = inside + exited | to 1e-9 |
| Webster C0 vs delay curve (L 12 s, Y 0.6) | minimum near C0 = 57.5 s | minimum at 52 s; delay at C0 within 5% |

Timing on the GB10 CPU, Mumbai network v1 (8,730 cells, 165 directed links,
429 movements, 103 signal groups; measured 30 Oct 2026): 30 min of the whole
network 0.19 s; 60 min 0.63 s. A full proposal (warm-up, do-nothing pass, the
candidates x 45 min, two sensitivity runs) takes 6-8 s without the LLM
(Dadar TT 6.1 s, Hindmata 7.6 s); the two LLM calls add to that.

## Limits

* Macroscopic: flows and queues, not vehicles; no lane changing, no
  pedestrians, no BEST buses or auto-rickshaws as separate classes (PCU only).
* Turning ratios are assumed (straight 1.0, turn 0.6, fitted to target
  flows), not counted; 15% of arriving traffic leaves to side streets at
  each junction.
* Signal programs are templates; on the Mumbai network v1, 39 of the 72
  junctions carry a program (an OpenStreetMap traffic_signals node within
  80 m) and 10 more run the twin's assumed template, so a large gain at such a
  crossing may only show that the template does not fit it.
* Demand is an assumed profile unless the oracle has live state for the
  city; the sandbox oracle still serves the previous city, so every result
  so far is SIMULATED.
* Two-phase programs only in practice (the network's vocabulary); the
  through/cross split cannot express protected turns.
* The rationale validator checks numbers and script, not meaning.
