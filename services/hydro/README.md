# hydro: Mumbai waterlogging nowcast

Mumbai's signature problem: a heavy burst at high tide. The storm-water outfalls to the Arabian Sea and the
creeks are submerged, their flood gates shut, the low spots drain by pumps alone, and the same places flood
every monsoon. This service gives every segment of the Mumbai road network (86 arterial segments, network v1)
a **depth-risk class 0–3** for the next 2 hours. Each class comes with an expected depth band, a lead time and
four labelled drivers:

- **rain:** the Open-Meteo nowcast at 18 canonical Mumbai landmarks (LIVE; a model product, not a gauge);
- **tide:** the Apollo Bunder (Mumbai harbour) harmonic model (MODELLED, approximate). The outfalls back up
  from 3.4 m and the gates are shut from 4.5 m, the BMC's high-tide threshold;
- **susceptibility:** from terrain and drainage, built from Copernicus DEM GLO-30, OSM drains and nallahs,
  and sourced flooding spots (MODELLED);
- **pump-station state:** the BMC storm-water pumping stations, **EMULATED** until the BMC's telemetry
  (IFLOWS-Mumbai) is connected.

For flagged roads (risk ≥ 2) the service drafts **proposals**, never actions. A named officer approves each
one; if no one answers, nothing changes:

- a reroute, with Mumbai Traffic Police and BEST (bus diversions) as the agencies to notify;
- an ambulance (108) window naming the nearest major hospital (KEM, Sion, Nair, JJ, Cooper);
- a request to BMC disaster control (1916) to stage mobile dewatering pumps;
- a live-wire hazard request to the area's power distribution utility;
- one public advisory in English, Marathi and Hindi.

## API (production port 8197, loopback)

| Route | Returns |
|---|---|
| `GET /health` | Service state |
| `GET /hydro/nowcast` | Per segment: class, depth band, lead time (to the peak class and to deep water), drivers with labels; proposals |
| `GET /hydro/tide?hours=1..72` | Apollo Bunder series, high and low waters, outfall restriction and gate state, sources |
| `GET /hydro/rain` | The 18-point Open-Meteo nowcast and the city mean. Cached 10 min; at most one call per 30 s; daily cap. `SAJAG_HYDRO_OFFLINE=1` makes no outbound calls. |
| `GET /hydro/pumps` | BMC pumping-station state (EMULATED) and the published totals |
| `POST /hydro/replay?event=2025-08-19` | Replay of a real storm (`2025-08-19`, default, or `2025-05-26`): the Open-Meteo archive run, a gauge-anchored run and a flat-shape sensitivity, checked against the places the news reported |

`SAJAG_HYDRO_CITY_DIR` points at another city pack; by default the service reads `cities/mumbai/network.json`
and falls back to the bundled snapshot.

## How it works

A conceptual ponding model on 15-minute steps (`model.py`, every parameter stated):

- **Drainage capacity** (runoff the drains carry): 12.5–50 mm/h by susceptibility. Both bounds are the BMC's
  own design figures (BMC Storm Water Drains RTI manual): the legacy network is "designed for the rainfall
  intensity of 25 mm per hour at low tide with run-off coefficient of 0.5" (25 × 0.5); the BRIMSTOWAD criteria
  are "50 mm/hour with run-off coefficient as 1". The CAG found 25 of 53 nullahs upgraded to 50 mm/h
  (Scroll, 2019), hence the range.
- **Outfalls at high tide:** capacity falls by up to half as the outfalls back up (graded from 3.4 m, gates
  shut at 4.5 m; assumption).
- **Pump availability:** scales capacity between 60 % and 100 %.
- **Runoff:** 0.85 (assumption; BRIMSTOWAD designs for 1.0).
- **Depth at the road:** ponded water × (1 + 2·S).
- **Classes:** 0 (< 2 cm), 1 (2–10 cm), 2 (10–30 cm), 3 (> 30 cm).
- **Elevated and grade-separated segments** (the Sea Link and its approaches, the Coastal Road, the Eastern
  Freeway, Sahar Elevated Road, Gokhale and Tilak bridges, the JJ flyover) never pond. The Western Express
  Highway runs at grade and is scored like any road.
- **Road subways** (Milan, Andheri): the dip under the railway is too small for a 30 m surface model, so their
  susceptibility is floored at 0.9 (MODELLED rule).

### The tide (`tide.py`, MODELLED)

Apollo Bunder constants M2/S2/K1/O1 from the Admiralty Tide Tables as tabulated by Unnikrishnan (2022, Current
Science 123(8)); phases referred to IST; N2 and K2 inferred; the mean level (2.61 m above chart datum) fitted
to the BMC's published high waters. Checks against the BMC's tide tables (printed by the Free Press Journal
and PTI):

| Date | BMC | Model |
|---|---|---|
| 24–28 Jun 2025 (5 high waters) | 4.59–4.75 m, 11:15–14:26 | within 18 min and 0.06 m |
| 24–27 Jul 2025 (4 high waters) | 4.57–4.67 m | within 12 min and 0.08 m |
| 24 Jul 2025, full day | LW 05:07 0.43 · HW 11:58 4.57 · LW 18:13 1.62 · HW 23:40 3.72 | LW 05:08 0.64 · HW 11:54 4.65 · LW 18:10 1.43 · HW 23:45 3.74 |
| 27 May 2025 (not used in the fit) | 4.88 m at 12:13 · 4.18 m at 23:56 | 4.69 m at 12:12 · 4.14 m at 23:52 |

Times land within 20 minutes; heights within ~0.1 m in the monsoon months, ~0.2 m low in late May.

### Pumping stations (`ffews.py`, EMULATED)

The six major stations (Haji Ali, Love Grove, Cleveland Bunder, Britannia, Irla, Gazdarbandh; 43 pumps and
2.58 lakh litres per second in aggregate — BMC via PTI, 19 Aug 2025) and four of the ten mini stations
(Hindmata, Gandhi Market, Yellow Gate, Chunabhatti — PTI, 28 May 2025). Names and the published totals are
real; per-station pump counts (summing to 43) and all state are invented. The adapter interface is what a
real feed will implement.

## Replays: two real storms

`eval/replay_2025-08-19.json` and `eval/replay_2025-05-26.json` are the recorded runs (the Open-Meteo archive
was called live on 30 Oct 2026). A report's time is when it was published, not when the water rose, so a
"lead before the first report" is an upper bound; an evening round-up published after the window gives no
lead. A flag with no report is never called a false alarm. The "perfect-nowcast lead" is HINDSIGHT: the
observed rain used as if it had been forecast perfectly, so the flag shows up to one 2-hour horizon before the
modelled depth crossing.

### 18–19 August 2025 (red alert; Mithi at 3.9 m; Kranti Nagar evacuated)

Rain, as reported:

- **IMD 20:30–05:30:** Vikhroli 194.5 mm, Santacruz 185, Juhu 173.5, Byculla 167, Bandra 157, Colaba 79.8 (FPJ, 19 Aug 08:39).
- **IMD 24 h to 08:30 on the 19th:** Vikhroli 255.5, Byculla 241, Santacruz 238.2, Juhu 221.5, Bandra 211, Colaba 110.4 (PTI, 19 Aug).
- **IMD 24 h to 08:30 on the 20th:** Vikhroli 229.5, Santacruz 209, Byculla 193.5, Juhu 150, Bandra 137.5, Colaba 107.4 (PTI, 20 Aug).
- **BMC gauges 04:00–15:00:** Vikhroli East 268, Marol 262, Powai 257, Versova 250 (PTI, 19 Aug).

Tide: the model's morning high water is 09:04 at 3.97 m (reported BMC table: 3.75 m at 09:16). The outfalls
are impeded from 07:00 to 11:30, inside the morning burst (the Chief Minister's office: more than 150 mm
between 04:00 and 11:00).

| Run | Segments class ≥ 2 | Reported places flagged (on network) |
|---|---|---|
| Open-Meteo archive (141 mm city mean vs ~447 mm at Santacruz) | 0 | 0 / 12 |
| Gauge-anchored (IMD window totals, archive timing) | 23 | **9 / 12** |
| Sensitivity: same totals, flat within each window | 0 | 0 / 12 |

| Reported place | First report (IST) | Source | Gauge run class | Modelled deep from | Lead before report | Perfect-nowcast lead |
|---|---|---|---|---|---|---|
| King's Circle (Matunga) | 06:20 | FPJ, India.com | 2 ✓ | 10:15 | −235 min | −115 min |
| Andheri Subway (closed) | 08:39 | FPJ, India.com | 2 ✓ | 09:00 | −21 min | +99 min |
| Gandhi Market | 08:39 | FPJ, India.com | 2 ✓ | 10:15 | −96 min | +24 min |
| Byculla | 08:39 | FPJ, Watchers | 2 ✓ | 09:30 | −51 min | +69 min |
| Dadar (TT, Hindu Colony) | 08:39 | FPJ, India.com | 2 ✓ | 10:00 | −81 min | +39 min |
| Vile Parle | 08:39 | FPJ | 2 ✓ | 10:30 | −111 min | +9 min |
| Sion | 08:39 | FPJ | 1 (missed) | — | — | — |
| Hindmata | 10:20 | India.com | 2 ✓ | 10:00 | +20 min | +140 min |
| Khar | 10:20 | India.com | 1 (missed) | — | — | — |
| Chembur | 10:20 | India.com, Watchers | 2 ✓ | 10:30 | −10 min | +110 min |
| Kurla (Kranti Nagar, Mithi) | 15:53 | Business Today, Watchers | 2 ✓ | 10:30 | +323 min | +443 min |
| Goregaon (Oberoi junction, WEH) | 20:05 | Watchers | 1 (missed) | — | — | — |
| Wadala, Sewri station, N M Joshi Marg, Poisar Subway | 10:20–20:05 | India.com, Watchers | off network | — | — | — |

Reading it honestly:

- The model finds 9 of the 12 reported on-network places. Its own depth crossing comes **after** the first
  report at most of them (median −51 min): the bucket model fills slowly, and the 06:20 King's Circle report
  is 4 hours ahead of it.
- With the observed rain as a perfect 2-hour nowcast, the warning would have led the first report at 8 of
  the 9 flagged places (median +69 min). King's Circle stays late.
- The Open-Meteo archive carries a third of the gauges' rain and flags nothing. Spread flat, the gauges'
  totals flag nothing either. The timing within the hour is what crosses the drains' design rates, and only a
  live gauge feed (the BMC's rain gauges) gives it.

### 26 May 2025 (earliest onset in decades; the burst at high tide)

Rain, as reported:

- **BMC station totals 23:00–11:00:** Nariman Point 252 mm, CSMT 215, Colaba 207, Grant Road 202 … Dadar 103, Kurla 76 (FPJ, 26 May).
- **09:00–10:00:** Nariman Point 104 mm, Colaba 83, CSMT 80, Malabar Hill 63 (FPJ, 11:12).

Tide: the modelled high water is 11:28 at 4.57 m; gates shut 11:15–12:00. Pumps were taken as reported: the
Hindmata, Gandhi Market and Yellow Gate mini stations not running, Chunabhatti below capacity (PTI, 28 May).

| Run | Segments class ≥ 2 | Reported places flagged (on network) |
|---|---|---|
| Open-Meteo archive (51 mm city mean vs 252 mm at Nariman Point) | 0 | 0 / 15 |
| Gauge-anchored | 6 | **5 / 15** |
| Sensitivity: flat | 5 | 5 / 15 |

- **Flagged from 09:15–09:30**, where the burst fell: Nariman Point and Mantralaya, Churchgate, Oval Maidan,
  the CSMT exit, Masjid Bunder (P D'Mello Road).
- **Missed (class 0–1):** the Dadar–Matunga bowl (Dadar TT, Five Gardens, Hindmata, King's Circle, Gandhi
  Market, KEM), Sion, Worli, Breach Candy and below the JJ flyover. The stations there reported about 100 mm
  over 12 hours with no hourly figure, and the model's concentration factor under-reads a bowl like Hindmata.
- Most reports were evening round-ups, so this replay gives no lead figure. The underground Acharya Atre Chowk
  metro station that flooded is not a road and is not scored.

## Data files

| File | Contents |
|---|---|
| `src/hydro/data/mumbai_network.json` | Network snapshot from the network stream (v1.1, b7d833f; ids stable; © OSM contributors, ODbL) |
| `src/hydro/data/mumbai_landmarks.json` | Canonical Mumbai landmark ids (en/mr/hi) |
| `src/hydro/data/hotspots.json` | 18 reported flooding spots, each with its sources and coordinate provenance; 3 marked unverified (half weight) |
| `src/hydro/data/susceptibility.json` | Built by `scripts/build_susceptibility.py --dem <N18E072> --dem <N19E072> --waterways <Overpass JSON>` (needs `rasterio`; the image does not) |
| `scripts/data/waterways.overpass.json.gz` | The Overpass extract it was built from (984 ways: drains, nallahs, the Mithi, Oshiwara and Dahisar) |
| `eval/replay_*.json` | The recorded replays |

## Licences and attributions

| Item | Licence or attribution |
|---|---|
| Copernicus DEM GLO-30 | © DLR e.V. 2010–2014 and © Airbus Defence and Space GmbH 2014–2018, provided under COPERNICUS by the European Union and ESA |
| OpenStreetMap | © OpenStreetMap contributors, ODbL 1.0 |
| Open-Meteo | Data under CC BY 4.0; the free API for non-commercial use |
| Tide constants | Admiralty Tide Tables via Unnikrishnan (2022), Current Science 123(8) |

No machine-learning model is used.

## Run and test

```bash
PYTHONPATH=src PORT=8503 python -m hydro
python -m pytest -q -p no:cacheprovider        # offline: Open-Meteo is mocked
```

The image is `infra/docker/Dockerfile.hydro`; the compose stanza is in `infra/compose.ai.yml`.

## Limits

- **Rain:** Open-Meteo is a model nowcast, not a gauge, and its archive carried a third (August) to a fifth
  (May) of the gauges' rain in the replays. The BMC's own rain gauges are the pilot's first need.
- **Replay rain:** window totals are observed. The 15-minute shape is modelled and station positions are
  approximate.
- **Tide:** cited constants, but N2/K2 are inferred and the mean level is fitted.
- **Outfalls:** the 3.4–4.5 m restriction is an assumption, not a survey of outfall levels.
- **Susceptibility:** from a surface DEM and hand-placed hotspots. A bowl like Hindmata reads as only
  moderately low.
- **Pumps:** emulated.
- **The model:** a bucket model, not a sewer model. It fills more slowly than the city did on 19 Aug.
- **Network:** 86 arterial segments. Reports off it are listed, not scored.
