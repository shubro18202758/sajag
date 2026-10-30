# Signal-timing proposals, tested in a twin (AI capability E)

**What it does.** When a junction or corridor is under stress, now or in a
forecast, Sajag proposes a signal-timing change and shows the duty officer
what it is expected to do, before anyone touches a signal. The proposal is
computed and checked in a macroscopic traffic model of Mumbai (the "twin",
`services/twin`, port 8198). The officer approves or rejects it; if no one
decides, the current plan holds.

Mumbai's pinch points are where this matters: Kalanagar at the Bandra end of
the Western Express Highway, Dadar TT, Sion Circle and King's Circle on Dr
Ambedkar Road, Haji Ali and Worli Naka on the western sea face, Mahim
Causeway, and the Andheri approaches. TomTom's Traffic Index 2025 puts the
city's rush-hour average at about 17–21 km/h depending on the definition, and
the time lost to peak-hour traffic at about 126 hours in 2025.

**Labels.** Twin results are MODELLED. Demand is SIMULATED unless the
traffic-oracle has live state for the city (then LIVE, or EMULATED for the
emulated feed). Signal programs are MODELLED templates: Mumbai Traffic Police
signal controller programs are an agency feed and are not public. The signal
adapter is EMULATED.

## Flow

```
live state (oracle, GET)  ─┐
forecast crossing (cap. A) ─┼─> twin: demand -> warm-up -> do-nothing + candidates (one batched run)
junction / corridor        ─┘          -> guards -> ranking -> sensitivity (90% / 110% demand)
                                        -> proposal object (MODELLED, PROPOSED)
                                        -> rationale: local LLM explains in English and Marathi;
                                           every number checked against the twin metrics
                                        -> deck: proposal card for a named officer
                                        -> officer approves -> the platform's signal writer
                                           (traffic-oracle; snapshot, gate, restore) -- not the twin
```

The twin never writes a signal and has no client for the writer. It reads
the oracle with GET requests only.

## Why a twin, and which one

A rule like "give the busy road more green" often just moves the queue to
the cross street or to the next junction. On a dense grid such as Dadar and
Parel, the next junction is a few hundred metres away. The twin checks for
that. Every candidate runs on the whole network for 30–60 minutes against
doing nothing, and a candidate is rejected if it:

* raises delay across the network (it would only move the jam);
* raises cross-street delay by more than 25%;
* adds spill-back anywhere; or
* cuts delay at the focus by less than 3% (not worth an officer's time).

It is a **cell-transmission model** (Daganzo), the standard macroscopic
model of queues and spill-back. It is fast enough to run every candidate
over the whole city on the CPU. The Mumbai network has 72
junctions and 86 segments (202 km). For scale: on the
Kolkata reference pack (network v2: 49 junctions, 123 directed links, 5,979
cells), 30 minutes take 0.12 s and 20 candidates in one batch 0.85 s.

**Baselines** are evaluated in the same twin and also enter the proposal
ranking:
* Webster's optimal cycle and split, from the twin's own flows.
* Max-pressure control, in its cyclic form so coordination and lost time are
  kept.

`GET /twin/baselines/{junction}` shows both against the current program.

## The proposal object

| field | meaning |
|---|---|
| `junction_ids`, `junctions`, `targets` | where (`junction:<id>`, the platform's URN form; ids from `cities/mumbai/landmarks.json`, e.g. `junction:sion_circle`) |
| `change` | `kind` (extend_green, green_wave, max_pressure, webster_retime) and a summary in English and Marathi. It also carries the programs in the platform's vocabulary (`cycle_sec`, `offset_sec`, `phases[{green_sec, movements}]`) and `revert_to` |
| `duration_min` | how long the change runs before reverting |
| `twin_metrics` | `delay_change_pct` (at the focus), `max_queue_change_m`, `cross_street_delay_change_pct`, `network_delay_change_pct`, `spillback_change_min`, with do-nothing and with-change values per approach and queue time series |
| `confidence` | whether the gain holds at 90% and 110% demand, scaled by the demand source and by whether the baseline program is assumed. A modelled heuristic, not a probability |
| `assumptions` | every modelling assumption, in plain words |
| `verification_state` | `MODELLED` |
| `requires` / `requires_officer` | `named officer approval` / `true` |
| `status`, `if_no_decision` | `PROPOSED`, `the current plan holds` |
| `rationale` | English and Marathi; `source` per language (`llm` or `template`) |

## The LLM's place

The LLM never chooses the timing; the twin and the ranking do. The local
tactical LLM (`:8084`, shared with a live system) gets the finished metrics
and writes two short sentences in English, then two in Marathi, one call at
a time with a 20 s timeout. Each reply is rejected if it:
* contains a number that is not in the twin metrics (Western or Devanagari
  digits);
* is too long; or
* for Marathi, contains stray Latin words or another script.

A rejected or missing language falls back to a template that uses only
metric numbers. The 12B model sometimes emits a garbage token in an Indian
language, which the check catches.

## Mumbai at the evening peak (SIMULATED demand)

The foci the twin is run on, with the corridors they sit on:

| Focus (id) | Corridor | Why it is a focus |
|---|---|---|
| Kalanagar (`kalanagar`) | WEH, Bandra end; BKC connector | the WEH meets the Sea Link and BKC traffic |
| Sion Circle (`sion_circle`) | Dr Ambedkar Road, Sion–Panvel highway, LBS Marg | the eastern gateway to the Island City |
| King's Circle (`kings_circle`) | Dr Ambedkar Road | a monsoon flooding hotspot on the same road |
| Dadar TT (`dadar_tt`) | Dr Ambedkar Road | dense grid around Dadar station |
| Worli Naka (`worli_naka`), Haji Ali (`haji_ali`) | Annie Besant Road, the sea face, the Coastal Road | sea-face traffic to and from the Sea Link and the Coastal Road |
| Dr Ambedkar Road corridor | Parel → Dadar TT → King's Circle → Sion | a green-wave candidate across several signals |

Results on the Mumbai network: 6 s more green for the Dr Ambedkar Road movement for 30 min: junction delay −14.7 %, network −0.3 %, cross street +20.0 % (shown, inside the 25 % guard), on SIMULATED demand, best of 14 candidates

What the reference pack showed. On the Kolkata reference pack at the 18:00
evening peak (45-minute horizon, simulated demand), accepted proposals cut
delay at the focus by 5–15 %, often at the price of more cross-street delay,
with network delay down by 0.1–1.5 %. A corridor green wave that cut corridor
delay by about a fifth was **rejected**, because network delay rose and the
cross streets lost too much. One very large gain at a junction with an assumed
program mostly showed that the generic template did not fit that junction's
geometry, not that a real controller was mistimed. That is why proposals at
junctions with assumed programs get a lower confidence. These are results on
another city's simulated demand; they are not Mumbai results.

## Limits

* Macroscopic; PCU only; turning ratios assumed; most crossings run an
  assumed template, because Mumbai Traffic Police signal programs are not
  public.
* Demand is SIMULATED until the oracle serves Mumbai live state.
* Two-phase programs: no protected turns.
* The validator checks numbers and script, not meaning.

See `services/twin/README.md` for the equations, parameters, API and
validation results.
