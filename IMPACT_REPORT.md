# IMPACT REPORT — rolling corridor holds vs blanket freeze (Mumbai)

*Generated 2026-10-30T10:15:39+00:00 by `scripts/impact_run.py` (deterministic;
re-run to regenerate). **MODELLED** — a deterministic model, not a field
measurement; see the honesty contract in the script header and the
assumptions table below.*

## What is compared

- **Baseline (today):** blanket freeze at every corridor junction for the full
  passage window — **15–45 minutes** (assumption: the range the platform is
  designed against; to be replaced by measured Mumbai movement logs); the
  model's central case uses **25 min**.
- **Platform (this repo):** predictive rolling holds — closures activated
  60–180 s ahead of the convoy, released as it passes — **~2.5 min**
  per junction.

## Network under test (Sajag's Mumbai road network, on real OpenStreetMap roads)

86 segments, **72 junctions**, 202.4 km
(great-circle length of the served geometry), mean 4.7 lanes —
read from the committed generator output (`scripts/data/osm_network.json`) — the network a deployed stack serves; re-run without `--offline` to read a running stack. Every segment is drawn along the real road of its name between
real intersections (City Pack `cities/mumbai/`, `scripts/gen_osm_network.py
--city mumbai`); road geometry © OpenStreetMap contributors, ODbL 1.0.
Arrival rate modelled at
**41 vehicles/min/junction** (30 veh/km/lane, the repo
simulator's own density default × 17.6 km/h, the rush-hour average speed of
the TomTom Traffic Index 2025 for Mumbai × the mean lane count).

*Scale note: the model freezes every junction of the network under test for
one movement — the whole 86-segment city network, an upper-bound
framing kept from the original model. A single movement crosses a subset of
it; what transfers to any corridor is the per-junction figure (central case
≈ 19,282 → ≈ 193 commuter-minutes per frozen junction) and
the reduction ratio, which does not depend on the junction count.*

| Segment | Road | Class | Lanes | Speed | km |
|---|---|---|---|---|---|
| 1001 | Marine Drive | primary | 6 | 65 | 0.9 |
| 1002 | Marine Drive | primary | 6 | 65 | 1.1 |
| 1003 | Marine Drive | primary | 6 | 65 | 1.9 |
| 1004 | V. N. Road | secondary | 6 | 40 | 0.4 |
| 1005 | V. N. Road - D N Road | primary | 4 | 50 | 1.3 |
| 1006 | Mumbai Coastal Road (northbound) | motorway | 4 | 80 | 10.4 |
| 1007 | Mumbai Coastal Road (southbound) | motorway | 4 | 80 | 10.6 |
| 1008 | Bandra-Worli Sea Link (northbound) | motorway | 4 | 80 | 3.9 |
| 1009 | Bandra-Worli Sea Link (southbound) | motorway | 4 | 80 | 3.9 |
| 1010 | Sea Link Worli exit ramp | motorway | 2 | 40 | 0.8 |
| 1011 | Sea Link approach (northbound, Western Freeway) | motorway | 6 | 120 | 1.6 |
| 1012 | Sea Link approach (southbound, from SV Road) | motorway | 6 | 100 | 1.2 |
| 1013 | Western Express Highway | motorway | 6 | 80 | 1.2 |
| 1014 | Western Express Highway | motorway | 6 | 40 | 1.9 |
| 1015 | Western Express Highway | motorway | 6 | 80 | 4.3 |
| 1016 | Western Express Highway | motorway | 6 | 40 | 2.6 |
| 1017 | Western Express Highway | trunk | 2 | 60 | 2.8 |
| 1018 | Western Express Highway | trunk | 4 | 60 | 3.3 |
| 1019 | Western Express Highway | trunk | 4 | 60 | 7.4 |
| 1020 | Sahar Elevated Road | primary | 4 | 50 | 2.3 |
| 1021 | Mahim Causeway | primary | 4 | 50 | 0.7 |
| 1022 | Swami Vivekanand Road | primary | 4 | 50 | 0.6 |
| 1023 | Swami Vivekanand Road | primary | 4 | 50 | 3.4 |
| 1024 | Swami Vivekanand Road | primary | 4 | 50 | 0.6 |
| 1025 | Swami Vivekanand Road | primary | 4 | 50 | 2.1 |
| 1026 | Swami Vivekanand Road | primary | 4 | 50 | 1.0 |
| 1027 | P V Avsare Marg (Milan Subway road) | tertiary | 2 | 30 | 0.5 |
| 1028 | G K Gokhale Bridge | primary | 4 | 30 | 0.5 |
| 1029 | Teli Galli - N S Phadke Marg | tertiary | 2 | 30 | 0.6 |
| 1030 | Sahar Road (Andheri Subway approach) | secondary | 2 | 40 | 0.5 |
| 1031 | Andheri-Kurla Road | secondary | 2 | 40 | 0.6 |
| 1032 | Andheri-Kurla Road | primary | 4 | 50 | 3.7 |
| 1033 | Andheri-Kurla Road | primary | 4 | 50 | 2.2 |
| 1034 | Saki Vihar Road | primary | 4 | 50 | 2.6 |
| 1035 | Jogeshwari-Vikhroli Link Road | primary | 6 | 50 | 5.1 |
| 1036 | Jogeshwari-Vikhroli Link Road | primary | 6 | 50 | 4.3 |
| 1037 | Jogeshwari-Vikhroli Link Road | primary | 6 | 50 | 1.4 |
| 1038 | Lal Bahadur Shastri Marg | primary | 4 | 50 | 2.2 |
| 1039 | Lal Bahadur Shastri Marg | primary | 4 | 50 | 0.7 |
| 1040 | Lal Bahadur Shastri Marg | primary | 4 | 50 | 1.2 |
| 1041 | Lal Bahadur Shastri Marg | primary | 4 | 50 | 3.8 |
| 1042 | Lal Bahadur Shastri Marg | primary | 4 | 120 | 5.4 |
| 1043 | Eastern Express Highway (Sion) | primary | 4 | 50 | 1.5 |
| 1044 | Eastern Express Highway | trunk | 8 | 60 | 4.7 |
| 1045 | Eastern Express Highway | secondary | 4 | 40 | 1.5 |
| 1046 | Eastern Express Highway | trunk | 8 | 60 | 1.7 |
| 1047 | Eastern Express Highway | trunk | 4 | 60 | 1.0 |
| 1048 | Eastern Express Highway | trunk | 8 | 60 | 5.3 |
| 1049 | Santacruz-Chembur Link Road | trunk | 6 | 60 | 3.3 |
| 1050 | Santacruz-Chembur Link Road | trunk | 4 | 100 | 3.2 |
| 1051 | Santacruz-Chembur Link Road (LBS Marg link) | trunk | 6 | 60 | 0.4 |
| 1052 | Bandra Kurla Complex Road | primary | 10 | 50 | 2.9 |
| 1053 | Bandra Kurla Complex Road | primary | 6 | 50 | 1.6 |
| 1054 | Sion-Panvel Highway | trunk | 8 | 60 | 0.8 |
| 1055 | Sion-Panvel Highway | trunk | 10 | 60 | 4.4 |
| 1056 | Ghatkopar-Mankhurd Link Road | trunk | 6 | 60 | 2.7 |
| 1057 | Mankhurd - EEH link road | trunk | 4 | 40 | 2.0 |
| 1058 | Eastern Freeway | motorway | 4 | 100 | 5.0 |
| 1059 | Eastern Freeway | motorway | 4 | 100 | 10.9 |
| 1060 | P D Mello Road | primary | 4 | 50 | 2.8 |
| 1061 | D N Road - JJ Flyover (Mohammed Ali Road) | primary | 4 | 30 | 2.9 |
| 1062 | Sir JJ Road - Dr Ambedkar Road | trunk | 8 | 60 | 1.8 |
| 1063 | Dr Ambedkar Road | trunk | 6 | 60 | 1.3 |
| 1064 | Dr Ambedkar Road | trunk | 6 | 60 | 0.9 |
| 1065 | Dr Ambedkar Road | trunk | 8 | 60 | 1.0 |
| 1066 | Dr Ambedkar Road (Hindmata - Dadar TT) | trunk | 6 | 60 | 1.6 |
| 1067 | Dr Ambedkar Road | trunk | 6 | 60 | 1.6 |
| 1068 | Dr Ambedkar Road | trunk | 6 | 60 | 0.8 |
| 1069 | Dr Ambedkar Road | trunk | 8 | 60 | 1.0 |
| 1070 | Dr E Borges Road | secondary | 2 | 40 | 0.4 |
| 1071 | Tilak Bridge | primary | 4 | 50 | 1.0 |
| 1072 | Senapati Bapat Marg | primary | 4 | 50 | 2.2 |
| 1073 | Lady Jamshetji Road - Senapati Bapat Marg | primary | 4 | 50 | 2.8 |
| 1074 | Pandurang Budhkar Marg | secondary | 4 | 40 | 1.5 |
| 1075 | Dr Annie Besant Road | primary | 6 | 50 | 2.9 |
| 1076 | Dr Annie Besant Road | primary | 4 | 50 | 0.7 |
| 1077 | Dr Annie Besant Road - Khan Abdul Gaffar Khan Road | primary | 4 | 50 | 2.1 |
| 1078 | Keshavrao Khadye Marg | secondary | 2 | 40 | 1.0 |
| 1079 | Sane Guruji Marg (Arthur Road) | secondary | 2 | 40 | 1.5 |
| 1080 | Dr A R Nair Road | secondary | 2 | 40 | 1.5 |
| 1081 | Sir JJ Road - Maulana Azad Road | primary | 4 | 50 | 0.6 |
| 1082 | Maulana Azad Road - Vallabhbhai Patel Road | secondary | 2 | 40 | 2.3 |
| 1083 | Jagannath Shankarsheth Marg | secondary | 2 | 40 | 0.7 |
| 1084 | N S Patkar Marg - Hughes Road | secondary | 2 | 40 | 1.1 |
| 1085 | Peddar Road (Dr G Deshmukh Marg) | primary | 4 | 50 | 2.1 |
| 1086 | Walkeshwar Road (Raj Bhavan approach) | secondary | 2 | 40 | 2.2 |


## The VIP movement corridor (central case, MODELLED)

The VIP movement the platform plans — Mantralaya along Marine Drive, the Coastal
Road, the Bandra–Worli Sea Link and the Western Express Highway to Airport T2 (segments
1001, 1002, 1006, 1008, 1011, 1013, 1014, 1015, 1020; 27.6 km) — crosses
**10 junctions**. Frozen for 25 min each
the model gives **192,820 commuter-minutes** of
delay per movement; with ~2.5 min rolling holds,
**1,928**. Same model, same assumptions as
below; only the junction count is the corridor's own.

## Commuter impact per movement, whole network frozen (central case, MODELLED)

| Metric | Baseline | Platform |
|---|---|---|
| Hold per junction | 25 min | 2.5 min |
| Commuter-minutes of delay | **1,388,302** | **13,883** |
| Vehicles caught in holds | 74,043 | 7,404 |
| Fuel idled (litres) | 12,495 | 125 |
| CO₂ (kg) | 31,237 | 312 |

**Reduction in junction-freeze commuter delay: 100×**
(conservative case 15→3 min with
−40% arrivals: **25×**; optimistic 45→2 min:
**506×**). The mechanism is structural — delay scales with
hold duration **squared** — which is why even the conservative bound clears the
platform's original "6×" aspiration. *We no longer lead with "6×"; we lead with
the mechanism and this range, modelled.*

## Emergency patients (the acute case)

- 12 ambulance trips/day are modelled as crossing
  the corridor during a movement window (assumption — basis below).
- Per intersecting trip the platform returns **11 minutes**
  (assumed holds 5–20 min, midpoint 12; platform ≤ 1 min
  with an approved window).
- **≈ 132 golden-hour minutes per movement-day ·
  ≈ 33,000 per year** at 250 movement-days/yr.

## Mumbai context (sourced; quoted beside the model, not inputs to it)

- ~126 hours lost to peak-hour traffic per commuter in 2025; Mumbai 18th most congested city globally; worst day 16 Sep 2025 (+129% congestion) (TomTom Traffic Index 2025)
- Ambulance (108): older Mumbai figures ~18.75 min to the patient and ~26.25 min to hospital; peak-hour responses of 20-45 min reported in Andheri, Kurla and South Mumbai (BW Healthcare World; The Bridge Chronicle; Bloomberg Quint)
- Suburban locals carry ~68 lakh riders a day on average in 2025-26 (CR ~38.7 lakh, WR ~29.5 lakh): when tracks flood at Sion / Kurla they spill onto the roads (Free Press Journal, from railway data)
- Atal Setu (Sewri - Nhava Sheva, 22 km): ~22,689 vehicles a day in its first year against a projected 56,000 (MMRDA via PTI / Deccan Herald)

## Annualised (central case, MODELLED)

- On the VIP movement corridor alone: **795,382 commuter-hours
  a year** (labelled movement-day assumption below).
- Upper bound, every junction of the network frozen for each movement:
  5,726,747 commuter-hours a year.
- Upper bound, fuel and CO₂: 3,092,450 litres
  of fuel and 7,731.1 tonnes
  of CO₂ avoided.

## Assumptions ledger (every number, sourced or labelled)

| Constant | Value | Source |
|---|---|---|
| Traffic density | 30 veh/km/lane | repo simulator default (`scenario_sim.py`) |
| Peak approach speed | 17.6 km/h | TomTom Traffic Index 2025, Mumbai rush-hour average 17.6 km/h (17-21 km/h by definition) |
| Baseline blanket hold | 25 min (15–45) | **assumption** (the design range; measure from movement logs) |
| Platform rolling hold | 2.5 min | platform design (60–180 s activation) |
| Discharge factor | 1.5 | **assumption** (textbook oversaturation shape) |
| Junctions frozen per movement | 72 | **assumption** (every junction of the network under test — see the scale note) |
| Ambulance trips crossing/movement-day | 12 | **assumption** (falsify with ambulance (108) dispatch data) |
| Ambulance baseline delay | 12 min (5–20) | **assumption** (range of reported VIP-movement holds; measure locally) |
| Movement-days/year | 250 | **assumption** (RTI-able; Mantralaya / airport movements) |
| Idle consumption / CO₂ | 0.9 L/h · 2.5 kg/L | standard factors |

**To falsify or improve this report:** replace any assumption with measured
data and re-run `python3 scripts/impact_run.py` (a running stack) or
`python3 scripts/impact_run.py --offline` (the committed network) — the report
and `scripts/impact_results.json` regenerate deterministically.

*Road network: (c) OpenStreetMap contributors, ODbL 1.0 — https://www.openstreetmap.org/copyright.*
