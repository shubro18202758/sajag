# Sajag wireframes

These are **low-fidelity wireframes**: greyscale boxes, placeholder figures and numbered annotations that show the layout, the order of information and the rules each screen keeps. They are not pixel specifications, and the figures in them are samples. The live screens are in [`docs/screenshots/`](../screenshots/).

Conventions in every file:

- Greyscale. Colour carries meaning only: orange = waits for a named officer's decision; red = danger (impassable water, a stolen vehicle); green = approved or healthy; blue = a link, or text an AI wrote. No yellow anywhere: the Sajag mark is white (black on paper) with one blue dot.
- A dashed outline means modelled, simulated, emulated or unverified (or a panel shown only when needed). Every such figure carries its honest label: `Live`, `Modelled`, `Simulated`, `Emulated`, "Field report · unverified", "Camera · AI reading · unverified", "Reference photo · not live".
- Hatched areas are maps or pictures.
- Console screens are drawn at 1440 px wide (rail 76 px, top bar 60 px); phone screens at 400 px wide.
- Text uses `Inter, Noto Sans Devanagari, system-ui, sans-serif`, so Marathi and Hindi render where that font is installed.
- "A. Patil" is a sample officer name. Places are Mumbai's, with the ids and spellings of `cities/mumbai/landmarks.json`; every figure is a sample, not a measurement.

| File | Screen | Deck route | What to look at |
|---|---|---|---|
| [wf-shell.svg](wf-shell.svg) | The operator shell around every console screen | `(v3)/+layout.svelte` (all operator pages) | The rail (Home · Map · Decide · Plan · Assistant · Advisories, Analyst apart), the orange Decide badge, search (Ctrl K), Report (voice), the language menu मराठी · English · हिंदी, alerts, the officer pill before and after naming, and the honest-label legend. |
| [wf-home.svg](wf-home.svg) | Home | `(v3)/home` (served at `/`) | Three jobs in order: what needs you (proposals waiting for a named officer, orange), what is happening (a simulated Ganeshotsav crowd event at Lalbaugcha Raja, the modelled waterlogging nowcast for Hindmata, an unverified field report), what is coming (a forecast crossing at Kalanagar on simulated traffic, the modelled Apollo Bunder tide, a planned Mantralaya → Mumbai Airport T2 movement). |
| [wf-map.svg](wf-map.svg) | Map | `(v3)/map` | Layer toggles, each with its label (traffic flow simulated, waterlogging risk 0–3 modelled, forecast bands, cameras at modelled positions, BMC pumps emulated, events) over the Dadar–Parel area (Hindmata, Dadar TT, King's Circle, Sion Circle, Lalbaug), and the selected Dr Ambedkar Road segment at Hindmata with its risk class, depth band, lead time and four drivers (rain live, Apollo Bunder tide modelled, pumps emulated, ground modelled). |
| [wf-decide.svg](wf-decide.svg) | Decide | `(v3)/decide`, `(v3)/decide/[unit]` | One proposal at a time: +6 s green at Sion Circle for 30 min with the twin's metrics (delay −7.0%, cross street +18.5%, network −0.2%, confidence medium), all modelled; "If no one decides, the current plan holds"; Approve / Edit / Reject only with a named officer; the audit line. |
| [wf-object.svg](wf-object.svg) | Object page for `segment:1033`, Dr Ambedkar Road → Hindmata | `(v3)/o/[urn]` | Identity and tags, live state with a label per figure, the p10–p90 forecast band with the 0.8 V/C threshold, waterlogging class and drivers, the hindsight replay of a past Mumbai storm, related proposals, a nearby camera's unverified AI reading, and the audit trail. |
| [wf-voice.svg](wf-voice.svg) | Field report by voice (the sheet behind "Report" in the top bar) | top bar entry on any operator screen; the board entry opens at `(v3)/o/[urn]` | Speak in Marathi, Hindi or English (shown: हिंदमाताला पाणी साचले आहे, गाड्या अडकत आहेत, "water has collected at Hindmata, vehicles are getting stuck"), read back the transcript, matched place and candidates, kind, severity and cue words, send as "Field report · unverified"; a named officer then confirms, edits or dismisses it. |
| [wf-citizen.svg](wf-citizen.svg) | Citizen: check your road | `(public)/citizen` | English by default (Marathi and Hindi one press away; drawn here in Marathi), no sign-in, no location: road search, the road's waterlogging status in plain words (modelled), the Listen button with its "synthetic voice" note, the Arabian Sea tide and the rain with their labels, an officer-approved advisory, 112 and ambulance (108). |
| [wf-driver.svg](wf-driver.svg) | Driver: ambulance (108) green corridor | `(public)/driver` | Unit, stretch (Dr Ambedkar Road towards KEM Hospital) and urgency, one request button, the status in orange while it waits for a named duty officer, the corridor map, and the line that the crew always follows 108 control. |
| [wf-plan.svg](wf-plan.svg) | Plan a movement | `(v3)/plan` | The four steps (Where to · Routes · Launch · Live), the trip (Mantralaya → Mumbai Airport T2) and protection class, routes ranked with twin estimates on simulated traffic, and a launch that needs a named officer. |

The landing page (`(landing)/welcome`) and the Assistant (`(v3)/assistant`) have no wireframe here; see their screenshots.
