# Screenshots

The product end to end, as it ran on the live Sajag stack on the Kolkata City Pack on 29 Oct 2026, 22:50–23:40 IST
(the deck on port 5373 of the one on-premises server). They are placed beside the text they explain in
[`README.md`](../../README.md), [`PRODUCT.md`](../../PRODUCT.md) (§6, screen by screen),
[`TECHNICAL_DESIGN.md`](../TECHNICAL_DESIGN.md), [`DESIGN_NOTES.md`](../DESIGN_NOTES.md) and
[`SAMPLE_DATA_AND_TESTS.md`](../SAMPLE_DATA_AND_TESTS.md); the README's gallery has them all.

## How they were taken

- **The camera:** [`scripts/showcase/console_shots.mjs`](../../scripts/showcase/console_shots.mjs) re-takes the whole
  set (`--list` prints it). Console screens at 1440 × 900, the three live-map heroes at 1920 × 1080, signed in as
  "Demo duty officer" (a console screen needs a named officer, so the registration marks it shows are the emulated
  EM-series exercise marks); the public pages in an anonymous browser, so marks stay masked there, the phone pages
  at 390 × 844 rendered at 2× (780 × 1688). JPEG quality 85. English throughout, except `home-mr.jpg` (the console
  in Marathi) and `voice-report.jpg` (a report spoken in Marathi).
- **Read-only:** the camera answers every write to the deck itself (no approval, rejection, dispatch, plan, escort
  or field report was sent); only the AI services' compute calls (speech, vision, twin, hydro, forecast), the
  assistant's chat turn and the map's live traffic read pass. The live map was given 60–90 s to fill its roads,
  places, readings and units before each map shot.
- **The staged evening:** `scripts/demo_reset.sh --apply --cancel-debris` (Durga Puja night in North Kolkata and the
  cloudburst at high tide, both SIMULATED; the stolen-vehicle sweep: EMULATED ANPR reads of the exercise vehicle
  WB06EM9001 under a demo FIR, one sighting PENDING for an officer), then `scripts/demo_tour.sh seed event-library
  escort green-corridor dss` (the scenario library's events, the Nabanna → Kolkata Airport protected movement with
  EMULATED convoy GPS, ambulance (108) corridor requests and one decision-support case). Both were reset afterwards.
- **What is live:** the rain nowcast, the city feeds (air, heat, cyclone, river, earthquake), the official weather
  warning and the reported situations (official notices and news, aggregate, at places; crime, clashes and politics
  are refused at ingest and none is shown here). Traffic is SIMULATED and every such figure says so.
- **Waterlogging:** Kolkata was dry that night (class 0 on every road is the honest answer), so the waterlogging
  shots use the console's replay of the 22–23 Sep 2025 storm, labelled **Hindsight**, as the console offers it.
- **Voice reports:** synthetic voices (the speech service's own TTS) played into a fake microphone and transcribed
  by the live ASR on this server; nothing was sent to the board.
- **The masked mark:** `decide-masked.jpg` shows a console with no officer named. The live deck shows no console
  page without a signed-in officer, so it was taken on a development deck (port 5383) serving the same code and
  reading the same live stack with the operator gate off, the camera's write refusal on.
- **The 3D city:** Google Photorealistic 3D Tiles through Cesium ion, labelled "not a live image" on screen.
- Nothing is edited apart from the JPEG encoding.

## Files

| File | Screen | Route | What it shows |
|---|---|---|---|
| `landing.jpg` | Landing | `/welcome` (public) | The mark, the tagline, Open the console and Check your road, the language switch, a labelled console screenshot, the reference photo's label and credit |
| `home.jpg` | Home | `/home` | The featured decision with Review now, the city band and four counts, the systems line, Next 2 hours (MODELLED) with the tide, the Replay 23 Sep 2025 card |
| `map-live-3d.jpg` | The live map, photoreal 3D | `/map` (3D, 1920 × 1080) | Howrah Bridge and the Hooghly; roads in load colours with flow dots; road speed and V/C labels; titled events; emulated units with their state; the official warning; Rain · Tide · Pumps; City panel; Now panel; legend; the 3D credit line |
| `map-live-3d-close.jpg` | The live map, closer | `/map` (3D, 1920 × 1080) | Central Kolkata up close: road speeds and V/C, titled events, emulated units, the stolen vehicle's last read, places |
| `map-live-2d.jpg` | The live map, 2D city map | `/map` (2D, 1920 × 1080) | North to South Kolkata on the dark city map; roads in load colours; places; air sites; events; units; the legend |
| `map-layers.jpg` | Map: layers | `/map` → Layers | The Layers sheet open: base map and style, Units, Dispatches, ANPR cameras, Junctions, Traffic flow, City places, with labels |
| `map-forecast.jpg` | Map: a road's forecast | `/map` → pick a road | The selection card for Rash Behari Avenue: waterlogging risk, depth band, rain; the three-step V/C forecast with p10–p90 and its labels |
| `map-air.jpg` | Map: air and city feeds | `/map` (Air layer) | The air sites over the city, the routes, the City panel with labels |
| `map-waterlogging.jpg` | Map: waterlogging, 23 Sep 2025 | `/map?replay=2025-09-23` | Hindsight: the flagged roads; Bidhan Sarani's card: risk 2 · deep water, 10–30 cm, first deep 03:30, 203 mm observed, the V/C band |
| `replay-2025-08-19.jpg` | Replay of 18–19 Aug 2025 | `/map` → Replay a recorded storm | The replay bar on the morning of 19 Aug 2025, the flagged roads, Back to live |
| `decide-corridor.jpg` | Decide: a 108 corridor request | `/decide` → 108 corridor request | The 108 request sheet: the unit, the golden hour left, what changes if approved, Approve the corridor / Defer |
| `decide-stolen.jpg` | Decide: the stolen-vehicle chain | `/decide` → Stolen vehicle | The stolen-vehicle sheet at step 2, Open the pursuit (the sighting was authorised earlier): four reads and the last read on the map, the mark rule, Dismiss / Open the pursuit |
| `decide-masked.jpg` | Decide: the mark masked until an officer is named | `/decide`, no officer named (dev deck :5383 on the live stack) | The stolen-vehicle sheet with the masked mark, the mark rule and the locked buttons (development deck on the live stack, gate off) |
| `decide-dss.jpg` | Decide: choose a response | `/decide` → Choose a response | The ranked response cards (closure and diversion, verify first, advisory), the recommended one, Approve / Reject / Defer |
| `decide-ai.jpg` | Decide: signal timing | `/decide` → AI proposals | The twin's comparison for Howrah Bridge, Kolkata end: junction, longest queue, cross street, network; the labels; Reject / Approve |
| `decide-waterlogging.jpg` | Decide: waterlogging | `/decide` (Exercise: 23 Sep 2025) | The reroute sheet for Gariahat crossing (risk 3, > 30 cm, 45 min), its labels and what changes; the ambulance-window and live-wire cards in the queue |
| `plan.jpg` | Plan a movement | `/plan` | Step 1 Where to: Nabanna → Kolkata Airport, the four protection classes with lane floors and closure leads, the departure, Find routes |
| `map-escort.jpg` | A protected movement on the map | `/map` → Now → the protected movement | The focused protected movement (Z+, Live, Emulated), its route and units, the selection card |
| `dispatch.jpg` | Dispatch and the live band | `/ops` → Dispatch | The live band; the counts; Decisions; the City map; Dispatch (agency, unit, waypoint, the requests and their states); the audit stream |
| `situation-wall.jpg` | Situation wall | `/ops` | Header counts, Decisions, the City map, the City band chart, City signal plans, the audit stream |
| `object-segment.jpg` | A road's page | `/o/segment:1033` (1440 × 1110) | The road's hero map, limit and lanes, the two-hour V/C forecast (band, median, seasonal baseline, the 0.8 line) with its labels, key facts |
| `object-vehicle.jpg` | A vehicle's page | `/o/vehicle:<id>` | The vehicle's hero with its reads, Emulated · Watchlist · Reported stolen, the lawful basis and retention, the evidence-only rule, the waiting decision |
| `object-osint.jpg` | A reported situation | `/o/osint_event:<id>` | The situation: the notice, the redaction line, How sure are we (0.90), the verification ladder, key facts |
| `road-state.jpg` | Road state from a still | `/o/camera:EM-J12` (1440 × 1320) | The camera page: the sample still and its credit, the reading (state, depth, vehicles, why), the model line, Send to the board, the policy line |
| `road-state-street.jpg` | Road state from a street photo | `/o/camera:EM-CAM-04` (1440 × 1320) | The street-photo tab: the date and credit, the reading (Clear, below the kerb, vehicles, why), the model line |
| `voice-report-en.jpg` | Field report by voice | top bar → Report | The transcript, the matched place, Waterlogging · Medium, the cue words, Unverified field report, Send to the board / Discard |
| `voice-report.jpg` | Field report in Marathi | top bar → Report → मराठी | A Marathi transcript, the matched place (Gariahat crossing), Waterlogging · Medium, the cue words, Unverified field report, Send to the board / Discard |
| `assistant.jpg` | Assistant | `/assistant` | The question, the answer with its synthetic-feed note, How I worked this out, the suggestions |
| `assistant-refusal.jpg` | Assistant: vehicles, never people | `/assistant` | The question, the vehicle-only answer, the grounding note, the decision card |
| `advisories.jpg` | Advisories | `/comms` | The events list, the cloudburst's header, the four audiences, the three-language draft with its exercise marker, Drafted — not delivered |
| `analyst-workspace.jpg` | Analyst workspace | `/analyst` | The live band; the workspace map; Active events; the selected movement's panel; the timeline with Audit and AI trace |
| `analyst-city-map.jpg` | Analyst city map | `/gods-eye` | The 3D city, road labels, cameras, units, the City vitals panel |
| `audit.jpg` | Audit trail | `/analyst` → Audit | The Audit tab: time, kind, actor, what happened, object; the City / Selected event and Officers / Machine / System filters |
| `citizen.jpg` | Citizen | `/citizen` (phone) | Your road (Bidhan Sarani): Dry, the Modelled label, Listen · Synthetic voice, Tide on the Hooghly |
| `driver.jpg` | Ambulance (108) crew | `/driver` (phone) | The request timer, the four steps, the Live audit note |
| `home-mr.jpg` | Home, also in Marathi | `/home` (मराठी) | Home in Marathi: the featured decision, the city band and counts, the systems line, Next 2 hours (modelled), the replay card |

## Not shown, and why

- **The routes step of Plan.** Find routes registers a labelled movement with the planner, an officer's press; the
  camera never writes, so `plan.jpg` stops at step 1 and `map-escort.jpg` shows a protected movement that was
  already running (the emulated base case).
- **An e-challan on the theft victim's vehicle.** The reject-only rule shows on a pending e-challan of the stolen
  exercise vehicle; the evening's reset had rejected the last one and none was pending while the set was taken, so
  none was staged or faked. The rule is visible on the vehicle's page (`object-vehicle.jpg`: "Evidence only. No
  e-challan for a stolen vehicle's owner").
- **Authorise pursuit as step 1, and the interception plan.** An officer had authorised the exercise sighting earlier
  that evening (decisions are final), so the stolen-vehicle sheet stands at step 2, Open the pursuit; the choke plan
  appears only once an officer opens the pursuit, which the camera does not do.
