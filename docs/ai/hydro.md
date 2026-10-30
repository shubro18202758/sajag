# Waterlogging nowcast (`services/hydro`)

Mumbai's signature problem is rain at high tide. The city is a narrow island and its suburbs between the Arabian Sea, Thane Creek and the Mithi river. When a heavy burst coincides with a high tide, the sea outfalls back up and the water has nowhere to go. The same low spots flood every year, subways close, local trains stop, and one stranded corridor spills onto the next.

The BMC puts the physics plainly: waterlogging is unavoidable when about 300 mm of rain falls in a short span and coincides with a high tide of about 4.5 m (BMC chief engineer, Free Press Journal, 2025). A tide of 4.5 m or more plus very heavy rain is the recognised flood trigger (India TV explainer, 27 May 2025). Even a 3.41 m morning tide with heavy rain flooded Andheri Subway, Hindmata and King's Circle (June 2025 report).

`services/hydro` combines four drivers for every segment of the city network:

- the live rain nowcast;
- the Arabian Sea tide at Apollo Bunder (a harmonic model);
- the state of the BMC storm-water pumping stations;
- terrain and drainage susceptibility.

From these it computes a **depth-risk class 0–3** with a lead time. It drafts **proposals** for each flagged road: a reroute, an ambulance (108) window and a live-wire hazard request; plus one request to BMC disaster control (1916) to stage dewatering pumps and one public advisory in English, Marathi and Hindi. A named officer decides every one of them. The Mithi river level (EMULATED) is shown beside the nowcast by `services/cityfeeds` (`river.py`); it is not a driver of the ponding equation.

| Driver | Source | Label |
|---|---|---|
| Rain | Open-Meteo forecast API, `minutely_15` precipitation at a fixed set of landmark points from `cities/mumbai/landmarks.json`, past 24 h and next 2 h. No key; cached 10 min; at most one call per 30 s; daily cap. | **LIVE** (a model nowcast, not a rain gauge) |
| Tide | Harmonic model at Apollo Bunder (Mumbai harbour) | **MODELLED (approximate)** |
| Mithi river (shown beside it, served by `services/cityfeeds`) | Level near Kurla against the 4 m danger mark. The BMC's river sensors (IFLOWS-Mumbai) are not public. | **EMULATED** until access is granted |
| Susceptibility | Copernicus DEM GLO-30 + OSM drains, nullahs and the Mithi + reported hotspots | **MODELLED** |
| Pumps | BMC storm-water pumping-station adapter | **EMULATED** until access is granted |

Port: 8197 in production (loopback); 9152 in development.

## Mumbai's drainage, in sourced numbers

These numbers frame the model. Each carries its source; where reports disagree, the range is given.

| Fact | Figure | Source |
|---|---|---|
| Flood trigger | ~300 mm in a short span at a ~4.5 m tide makes waterlogging unavoidable | BMC chief engineer, Free Press Journal, 2025 |
| Tide trigger | a tide of ≥ 4.5 m with very heavy rain | India TV explainer, 27 May 2025 |
| Old drain capacity | "enough to handle only 25 mm rainfall per hour" | CAG report as reported by PTI, Scroll, 3 Jul 2019 |
| Outfall gates (2019) | floodgates at only 3 of the 45 outfalls; "due to flat gradients, drains are affected by tides" | CAG report, as reported by Scroll and HT, 3 Jul 2019 |
| Design standards | legacy drains "designed for the rainfall intensity of 25 mm per hour at low tide with run-off coefficient of 0.5"; BRIMSTOWAD criteria "50 mm/hour with run-off coefficient as 1"; 25 of 53 nullahs upgraded to 50 mm/h (CAG) | BMC Storm Water Drains department, RTI manual, chapter 1; Scroll, 2019 |
| Drain capacity now | "the capacity to handle only 55 mm of rainwater per hour"; widening to 120 mm/h planned | Free Press Journal, 11 Jun 2025 |
| Chronic spots | hundreds of known flooding spots: BMC counts 386–498 by year (386 chronic spots, 280 treated, in one report; 453 → 498 waterlogging spots in a later one) | Free Press Journal reports |
| Pumping stations | 6 major + 10 mini storm-water pumping stations; the major ones are Haji Ali, Irla, Love Grove, Cleveland Bunder, Britannia and Gazdarbandh (plus the Mahul and Mogra projects); the six major hold 43 pumps, 2.58 lakh litres per second in all | Free Press Journal; BMC via PTI, 19 Aug 2025 |
| Dewatering pumps | raised from 414 to 514 after 26 May 2025, later 547 | Free Press Journal |
| Pumps that failed | in 2025 only 4 of 6 pumps at King's Circle worked; non-working mini pumping stations flooded Chunabhatti and Yellow Gate | Free Press Journal |

What this means for the model. With drains rated at a few tens of millimetres an hour, an intense burst exceeds them within minutes. At high tide the outfalls drain little or nothing, so water ponds until the tide falls. Pumps are the only way out while the tide is up, and pump availability matters.

## Tide model (`tide.py`), MODELLED

The tide is computed, not read: Sajag has no machine-readable tide feed for Mumbai harbour.

- **Method:** a harmonic model at **Apollo Bunder** (Mumbai harbour, landmark `apollo_bunder`), summing the principal constituents (M2, S2, K1, O1 and the shallow-water terms the constants call for) with the standard Doodson/Schureman nodal corrections.
- **Constants:** Admiralty harmonic constants for Mumbai (Apollo Bunder) as given by Unnikrishnan (2022), with N2 and K2 inferred and the mean level fitted.
- **Validation** against published predictions for Apollo Bunder: every BMC-listed high water of 24–28 June and 24–27 July 2025 within 20 min and 0.12 m, low waters within 10 min and 0.25 m (the BMC's high-tide advisories as printed by the Free Press Journal).
- **Outside the fit:** the BMC's 27 May 2025 high waters (4.88 m at 12:13, 4.18 m at 23:56) come out at 4.69 m at 12:12 and 4.14 m at 23:52: times within 5 min, levels ~0.2 m low in late May.
- **Outfalls:** the gates count as shut at or above the **4.5 m** high-tide trigger reported above (BMC; India TV, 27 May 2025). The outfalls back up before that (the June 2025 report of a 3.41 m tide flooding Andheri Subway, Hindmata and King's Circle), so the loss of gravity discharge is graded linearly from 3.4 m (none) to 4.5 m (gates shut). The grading is a stated assumption, not a survey of outfall inverts.
- **On the Kolkata reference pack** (`cities/kolkata`) the same code, with constants transferred from a cited river station, matches published predictions within about 20 minutes on high waters and 0.15 m on levels. Tests enforce this.

`GET /hydro/tide` returns the series, the extremes, the outfall state and the sources, labelled **MODELLED (approximate)**.

## The Mithi river, EMULATED

The Mithi rises in the Powai and Vihar area and runs past the airport, Kurla and BKC to Mahim Creek. Its banks at Kurla (Kranti Nagar) are where people were evacuated in August 2025.

- **Danger mark: 4 m.** On 18–19 Aug 2025 the river stood at about 3.9 m against it (some reports say it crossed it), and 350–500 people were evacuated near Kurla (The Statesman, Mongabay, HT, Aug 2025).
- The BMC's river-level sensors are not public. Until access is granted, the level at landmark `mithi_kurla` comes from an emulated stand-in. Every record says **EMULATED**.
- The level is shown beside the nowcast with its danger mark. It is not part of the ponding equation below (see Limits).

## Susceptibility (`scripts/build_susceptibility.py`, committed result `src/hydro/data/susceptibility.json`)

The build script samples every segment every ~30 m. It reads three inputs:

- **Copernicus DEM GLO-30**, the 1° tiles covering the city bbox (18.89–19.28 N, 72.77–72.99 E) from the AWS open-data bucket `copernicus-dem-30m`. © DLR e.V. 2010–2014 and © Airbus Defence and Space GmbH 2014–2018, provided under COPERNICUS by the European Union and ESA.
- **An OSM Overpass extract** of `waterway=canal|drain|river|stream|ditch` in the city bbox (the nullahs and the Mithi), © OpenStreetMap contributors, ODbL. A gzipped copy is kept in `scripts/data/`.
- **The sourced hotspot list** (`src/hydro/data/hotspots.json`).

Features:

- **Ground:** the 10th percentile of samples along the road. The DEM is a surface model with buildings, so a low percentile approximates the ground.
- **Neighbourhood median** within 1.5 km, and the relative elevation against it.
- **City percentile** of the ground.
- **Distance to the nearest mapped nullah or drain**, and to the Mithi.
- **Distance to the nearest reported hotspot.**

The score is MODELLED:

```
S = 0.30·(1 − city percentile) + 0.20·σ(−relative elevation / 1 m) + 0.20·min(1, d_drain / 2 km) + 0.30·exp(−d_hotspot / 400 m)
```

- An unverified hotspot counts at half weight.
- **Elevated and grade-separated** segments keep 15 % of their score and never pond (depth 0, with the reason): the Bandra–Worli Sea Link and its approaches, the Coastal Road, the Eastern Freeway, Sahar Elevated Road, the Gokhale and Tilak bridges and the JJ flyover (13 of the 86 segments). The Western Express Highway runs at grade and is scored like any road.
- **Road subways** under the railway (Milan, Andheri) are floored at 0.9: the dip is too small for a 30 m surface model (MODELLED rule).
- Built on 30 Oct 2026 from the N18/N19 E072 tiles and 984 OSM waterways (683 drains, 207 streams, 79 river ways, 7 canals, 8 ditches); sea and creek cells (≤ 0.5 m) are left out. Shore points with no land cell carry `null`.
- Highest-scoring roads on the Mumbai network: P V Avsare Marg at Milan Subway (0.90, floor), Sahar Road at Andheri Subway (0.90, floor), Sir JJ Road – Dr Ambedkar Road at Byculla (0.83), Dr Ambedkar Road by Byculla (0.80) and by King's Circle (0.78), Keshavrao Khadye Marg (0.77), Swami Vivekanand Road by Vile Parle (0.74), Dr Ambedkar Road between Hindmata and Dadar TT (0.72).

### Reported hotspots

Each hotspot in `hotspots.json` carries its sources. Ids are the canonical ones in `cities/mumbai/landmarks.json` where the place has one.

| Hotspot | Landmark id | Reported in |
|---|---|---|
| Hindmata (Dadar East) | `hindmata` | 26 May 2025 and 18–19 Aug 2025 reporting (DT Next, Deccan Herald, The Statesman, HT); FPJ |
| Dadar TT Circle | `dadar_tt` | 26 May 2025 reporting (DT Next, Deccan Herald) |
| King's Circle (Matunga) | `kings_circle` | Aug 2025 reporting; June 2025 report (3.41 m tide); FPJ (4 of 6 pumps working) |
| Sion Circle | `sion_circle` | Aug 2025 reporting (tracks submerged at Sion) |
| Kurla, Kranti Nagar by the Mithi | `mithi_kurla`, `kurla` | Aug 2025 reporting (evacuations) |
| Andheri Subway | `andheri_subway` | Aug 2025 reporting (closed); June 2025 report |
| Milan Subway (Santacruz) | `milan_subway` | recurring in monsoon reporting (FPJ and others) |
| Parel | `parel` | recurring in monsoon reporting (FPJ and others) |
| Chembur | `chembur` | Aug 2025 reporting |
| Acharya Atre Chowk (Worli) | `acharya_atre_chowk` | 26 May 2025: the Metro Line 3 station flooded (The Week, Deccan Herald) |
| Gandhi Market, Wadala, Vile Parle, Byculla, Dharavi junction, near National College (Bandra), Chunabhatti, Yellow Gate | gazetteer | Aug 2025 reporting; FPJ (Chunabhatti and Yellow Gate: mini pumping stations not working) |

## Pumps: the BMC pumping-station adapter (`ffews.py`), EMULATED

The BMC's pump status is not public, and Sajag has no access to it.

- `FfewsAdapter` is the interface a real feed will implement.
- `EmulatedFfews` is the stand-in used until then. Every record it returns says **EMULATED**.
- The station names are the six major BMC storm-water pumping stations: Haji Ali, Irla, Love Grove, Cleveland Bunder, Britannia (Reay Road) and Gazdarbandh (Khar), at the positions in `landmarks.json` (`haji_ali_ps`, `irla_ps`, `love_grove_ps`, `cleveland_bunder_ps`, `britannia_ps`, `gazdarbandh_ps`), and four of the ten mini stations named in 2025 reporting: Hindmata, Gandhi Market, Yellow Gate and Chunabhatti (PTI, 28 May 2025).
- The published totals are real (43 pumps and 2.58 lakh litres per second across the six major stations; BMC via PTI, 19 Aug 2025); the per-station split (summing to 43) is invented.
- The real feed to connect later is the BMC's own telemetry (IFLOWS-Mumbai and the pumping stations' SCADA).
- Station positions are approximate.
- The pump counts and states are invented: a deterministic rotation in which one pump is down, and every available pump runs in rain. That a pump can be down is real (FPJ, 2025: 4 of 6 working at King's Circle); the rotation is not.

`GET /hydro/pumps` shows this.

## The model (`model.py`): a conceptual ponding model, MODELLED

The model runs on 15-minute steps, for each segment:

```
C_open = C_MAX − (C_MAX − C_MIN)·S                       drainage capacity, mm/h
C(t)   = C_open · (1 − 0.5·gate(t)) · (0.6 + 0.4·a)      blocked outfalls halve it; a = pump availability
W     ← max(0, W + (0.85·rain − C)·Δt)                   ponded water, mm
depth  = W/10 · (1 + 2·S)                                cm at the road; elevated segments: 0
```

The capacity bounds come from public statements:

| Bound | Value | Source |
|---|---|---|
| `C_MIN` | 12.5 mm/h | The legacy network is "designed for the rainfall intensity of 25 mm per hour at low tide with run-off coefficient of 0.5" (BMC Storm Water Drains department, RTI manual, chapter 1): 25 × 0.5 of runoff carried. |
| `C_MAX` | 50 mm/h | The BRIMSTOWAD criteria: "50 mm/hour with run-off coefficient as 1" (same manual). Only part of the network meets it (CAG: 25 of 53 nullahs, Scroll 2019), hence the range by susceptibility. The FPJ's "55 mm per hour" (11 Jun 2025) sits just above it. |

`gate(t)` is the tide model's graded outfall restriction (0 below 3.4 m, 1 at 4.5 m and above). The outfall cut (0.5), the pump floor (0.6), runoff (0.85; BRIMSTOWAD designs for 1.0) and concentration (2) are stated assumptions.

| Class | Depth | Meaning |
|---|---|---|
| 0 | 0–2 cm | Dry |
| 1 | 2–10 cm | Shallow |
| 2 | 10–30 cm | Deep: small cars, two-wheelers and auto-rickshaws stall, ambulances slow, live-wire danger |
| 3 | > 30 cm | Impassable for most vehicles |

**Lead time** is reported two ways:

- `lead_time_min`: minutes until the segment first reaches its peak class within the horizon;
- `lead_time_deep_min`: minutes until it first reaches class 2.

## API

| Route | What it returns |
|---|---|
| `GET /health` | Labels, rain-feed state (calls today, cache age), network, susceptibility build, tide now |
| `GET /hydro/nowcast` | For each segment: `risk_class`, `risk_class_now`, `expected_depth_band`, `modelled_peak_depth_cm`, `lead_time_min`, `lead_time_deep_min`, and `drivers.{rain,tide,susceptibility,pumps}` each with its label. Also class counts, the flagged list and the proposals. |
| `GET /hydro/tide?hours=1..72` | The tide model's output (MODELLED) |
| `GET /hydro/rain` | The Open-Meteo nowcast at the landmark points and the city mean (LIVE) |
| `GET /hydro/pumps` | Station state (EMULATED) |
| `POST /hydro/replay?event=<id>` | A replay of a recorded storm (below). An unknown id answers 404 with the known list. |

### Proposals (never actions)

All proposals are in the decision-support shape: `state: proposed`, `actions` with `requires_officer: true`, `recommendation.decision: await_officer`, and a `human_gate` with no officer. They are generated for each flagged segment (risk ≥ 2):

- **Reroute** (`waterlogging_reroute`): a detour on the city network that avoids other flagged roads where it can. Example: traffic diverted off the Western Express Highway before Andheri Subway closes.
- **Ambulance window** (`ambulance_window`): a note for ambulance (108) crews giving the minutes the road stays passable and the detour, for example towards KEM or Sion Hospital.
- **Live-wire hazard** (`live_wire_hazard`, `for_officer_approval: true`): a request that the area's power utility inspect and, where needed, isolate supply along the road. Standing water and fallen wires are a known monsoon danger.
- **Pump request** (`pump_request`): one request to BMC disaster control (1916) to stage mobile dewatering pumps at the most urgent flagged places (at most 8), naming the serving pumping station and its (EMULATED) availability.
- **One public advisory draft** (`public_advisory_draft`) in English, Marathi and Hindi. It uses Western digits, as the glossary requires in the console.

The advisory template, filled here with illustrative places (not a run output):

> Traffic advisory (draft): waterlogging is likely within the next 120 minutes at: Hindmata (Dadar East), King's Circle (Matunga), Sion Circle, Milan Subway (Santacruz), Andheri Subway. Avoid these roads if you can. Do not touch electric poles or wires in standing water. Emergency 112; ambulance (108); BMC disaster control 1916.

> वाहतूक सूचना (मसुदा): पुढील 120 मिनिटांत या ठिकाणी पाणी साचण्याचा धोका आहे: हिंदमाता (दादर पूर्व), किंग्ज सर्कल (माटुंगा), सायन सर्कल, मिलन सबवे (सांताक्रूझ), अंधेरी सबवे. शक्य असल्यास हे मार्ग टाळा. साचलेल्या पाण्यात विजेचे खांब किंवा तारांना हात लावू नका. आपत्कालीन मदतीसाठी 112; रुग्णवाहिका (108); बृहन्मुंबई महानगरपालिका आपत्ती नियंत्रण 1916.

## Replay: a recorded Mumbai storm

`POST /hydro/replay?event=<id>` runs the same model over a recorded storm, with the tide MODELLED for those dates. Two storms are replayed: **18–19 August 2025** (`event=2025-08-19`, the default) and **26 May 2025** (`event=2025-05-26`). The recorded runs are `services/hydro/eval/replay_2025-08-19.json` and `replay_2025-05-26.json` (the Open-Meteo archive called live on 30 Oct 2026).

**Result, 18–19 Aug 2025.** Driven by IMD's observed window totals (Vikhroli, Santacruz, Juhu, Byculla, Bandra, Colaba; FPJ and PTI, 19–20 Aug), with the timing inside each window taken from the archive's hourly shape, the model flags **9 of the 12** reported flooded places that lie on the network (23 segments at class ≥ 2): King's Circle, Andheri Subway, Gandhi Market, Byculla, Dadar TT, Vile Parle, Hindmata, Chembur and Kurla (Kranti Nagar). It misses Sion, Khar and Goregaon (class 1). Wadala, Sewri, N M Joshi Marg and Poisar Subway are off the network and not scored. The model's own depth crossing comes **after** the first news report at most places (median −51 min; the bucket model fills slowly, and the 06:20 King's Circle report is four hours ahead of it). With the observed rain used as a perfect 2-hour nowcast (HINDSIGHT), the warning would have led the first report at 8 of the 9 places (median +69 min). The modelled morning high water is 09:04 at 3.97 m against the BMC table's 09:16 at 3.75 m; the outfalls are impeded 07:00–11:30, inside the morning burst. The Open-Meteo archive carries 141 mm (city mean) against ~447 mm at Santacruz over the window and flags nothing; the same gauge totals spread flat within each window flag nothing either.

**Result, 26 May 2025.** Driven by the BMC's 12-hour station totals and the observed 09:00–10:00 hour (Nariman Point 104 mm), with the Hindmata, Gandhi Market and Yellow Gate mini pumping stations down as reported (PTI, 28 May), the model flags **5 of 15** reported places (Nariman Point, Churchgate, Oval Maidan, the CSMT exit, Masjid Bunder, from 09:15–09:30) and misses the Dadar–Matunga low area (Hindmata, Dadar TT, King's Circle, Gandhi Market, KEM), Sion and Worli. Most reports were evening round-ups, so no lead is computed. The archive carries 51 mm against 252 mm at Nariman Point and flags nothing.

What this shows: the model is not blind to either storm when it gets gauge rain, it finds most of the August places, and it is slow. Neither run was used to tune it. The case it makes is for a live rain-gauge feed (the BMC's automatic weather stations): gridded products miss both storms.

### The candidate storms

Two recent storms are well reported. Their facts, as reported:

**26 May 2025.** The earliest monsoon onset in decades (the normal onset is around 11 June).

- Colaba recorded 135.4 mm in the 24 h to 08:30 IST. Up to ~295 mm was reported for the day, breaking the May record of 279.4 mm set in 1918.
- About 90 mm fell in 90 minutes and flooded the new Acharya Atre Chowk station of Metro Line 3; services between Acharya Atre Chowk and Worli were suspended.
- Hindmata and Dadar TT flooded. 45 tree falls and 25 fire incidents were reported (FPJ).
- Sources: DT Next, Deccan Herald, The Week, Watchers (26 May 2025); Free Press Journal.

**18–19 Aug 2025.** A red alert.

- Vikhroli recorded ~223–230 mm and Santacruz ~207–238 mm in 24 h (IMD; the reporting windows differ).
- The Mithi stood at ~3.9 m against its 4 m danger mark (some reports: crossed it). 350–500 people were evacuated near Kurla (Kranti Nagar).
- Two overcrowded monorail trains were stranded near Mysore Colony (582–782 rescued; reports differ).
- Tracks were submerged at Sion and Kurla; schools shut; Andheri Subway closed. Sion, Matunga, Dadar, Vile Parle, Hindmata, King's Circle, Gandhi Market, Wadala and Chembur were waterlogged. The police asked people to avoid the shore at high tide and offices to allow work from home.
- Sources: The Statesman, Mongabay, Watchers, Business Today, HT (Aug 2025).

The city's reference flood, **26 July 2005** (944 mm at Santacruz in 24 h), is history here. It is not replayed.

### How a replay runs

The method is the one the model was first validated with:

- **Run A, archive.** Hourly precipitation from the Open-Meteo historical archive (`best_match`, reanalysis/NWP based) at the landmark points.
- **Run B, gauge-anchored.** The same model driven by IMD's observed totals at the city's observatories (Santacruz, Colaba and, where reported, Vikhroli). Within each reported window the hourly shape is MODELLED; in space the totals are interpolated (IDW) between the stations.
- **Pumps** are set as reported for the event where a report exists, otherwise all available.
- **Scoring.** Each reported place that lies on the network is checked: flagged or not, first time at class ≥ 2, and peak class. A flag with no report is **not** counted as a false alarm, because news reports name places, not every street. Places off the network are listed as not scored.

### First validated on the Kolkata reference pack

The model and this replay method were first validated on the Kolkata reference pack (`cities/kolkata`), on an overnight storm of September 2025 that put about 250 mm into 24 h at the city's IMD observatory. Driven by the observed gauge totals, the model flagged all 13 reported places that lay on that network; the first flag came 15 minutes before the peak hour. Almost the whole network flooded that night (60 of 65 segments flagged), so this shows the model is not blind to such an event; it does not show fine discrimination. The archive run carried under a tenth of the observed rain and flagged nothing. Gridded reanalysis and global NWP do not resolve a convective night, which is the case for wiring rain gauges into any pilot.

## Limits and what is not done

- **Rain:** the nowcast is a model product. Over India, Open-Meteo's 15-minute field may be interpolated from hourly models, and gridded products can badly miss a convective burst. A rain-gauge feed (the BMC's automatic weather stations or IMD AWS) is the first thing a pilot needs.
- **Tide:** a harmonic model, not the Survey of India's published tables. Storm surge and monsoon wind set-up on the sea face are not modelled.
- **Mithi:** EMULATED, and shown beside the nowcast rather than coupled into the ponding equation. Backwater from the Mithi into Kurla and BKC drains is not modelled.
- **Susceptibility:** the DEM is a surface model with buildings, and hotspots are positioned by hand (±300 m). Drain capacity, silt and blockage along each nullah are unknown.
- **Subways** (Andheri, Milan) are sumps: they fill faster than the road around them. The model floors their susceptibility at 0.9 but scores them as segments, not as sumps.
- **Pumps:** EMULATED. Station positions are approximate.
- **The model:** a conceptual bucket model with stated parameters, not a hydraulic sewer model (SWMM). It is not calibrated: the parameters are the BMC's design figures and stated assumptions, and the two replays are checks, not fits. It fills more slowly than the city did on 19 Aug 2025.
- **Network:** 86 arterial segments. Many reported places are off it.
- **Not built:** a regional SAR flood-extent layer (Prithvi-EO-2.0 on Sentinel-1) is not part of this service.
