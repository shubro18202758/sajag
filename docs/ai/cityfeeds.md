# City feeds (`services/cityfeeds`)

The duty officer's picture of Mumbai needs more than roads and rain. It also needs the air the city breathes in the winter months, the humid heat on a traffic post, a cyclone in the Arabian Sea, the Mithi river, fires and the ground itself. `services/cityfeeds` brings these together from **open sources**, and labels anything that is not one:

- it reads each feed on a polite schedule;
- it normalises the answer and labels every number honestly;
- it drafts **proposals** that a named officer decides.

Port: 8199 in production (loopback, `infra/systemd/sajag-feeds.service`); 9201 in development.

| Chip | What it shows | Source | Label |
|---|---|---|---|
| Air | The city's indicative National AQI and band (worst of the named sites), the next 48 h; the stations' own readings beside it | Open-Meteo air-quality API (CAMS) at the CPCB/MPCB sites, CPCB breakpoints; the stations' readings through WAQI and OpenAQ (`WAQI_TOKEN`, `OPENAQ_API_KEY`); CPCB via data.gov.in when `DATA_GOV_IN_API_KEY` is set | LIVE feed · MODELLED values · INDICATIVE AQI; OBSERVED for station readings |
| Heat | Heat index now and its band; the 48-h peak; IMD heatwave days | Open-Meteo forecast at IMD Santacruz and Colaba; NWS heat index; IMD criteria for coastal stations | LIVE feed · MODELLED |
| Cyclone | Nearest active Arabian Sea storm, distance, bearing and GDACS alert | GDACS event list and geometry | LIVE · distances MODELLED |
| River | The Mithi at Kurla against its 4 m danger mark; Mithi mentions in the Mumbai news | the hydro service's emulated gauge (the BMC's river sensors are not public); reachable Mumbai RSS feeds | EMULATED · news AGGREGATE |
| Quake | USGS events within 500 km in 30 days; the latest | USGS FDSN event service | LIVE |
| Tide | The next high water at Apollo Bunder | the hydro service's tide model | MODELLED |
| Fires | Satellite thermal anomalies in the city box, 24 h, with the nearest landmark | NASA FIRMS public South Asia files (VIIRS ×3, MODIS); the area API with `FIRMS_MAP_KEY` | LIVE · "not a confirmed fire" |

## Every feed

### Air quality (`air.py`, `air_observed.py`)

Mumbai's air is worst from October to February, when construction dust meets calm winds.

- **Points:** the continuous ambient air-quality monitoring sites the city knows by name, among them Bandra Kurla Complex, Colaba, Worli, Chakala-Andheri, Powai, Kurla, Sion, Borivali, Mazgaon, Deonar and Chembur. CPCB lists each site with its operator (MPCB and others).
  - The stations' surveyed positions are not published in a form this box can read. Each point is the **named site's public location** (the locality or campus), cited per point in `STATIONS.coord_source`, good to about ±1 km.
- **Modelled values:** Open-Meteo `/v1/air-quality`, which serves the CAMS global atmospheric-composition forecast (ECMWF Copernicus). The service reads hourly PM2.5, PM10, NO₂, O₃, US AQI and European AQI, for the past 24 h and the next 48 h, in one call for all the points.
  - **The CAMS grid is coarse.** Neighbouring sites share a grid cell and therefore a value. The answer says so (`grid_cells`), and the sheet repeats it.
- **Observed values:** the stations' own PM2.5 and PM10 through OpenAQ (provider CPCB) and WAQI's nearest station, both with live keys. They are labelled OBSERVED and shown beside the modelled values, never merged into them.
- **National AQI:** CPCB's *National Air Quality Index* (Control of Urban Pollution Series CUPS/82/2014-15, Table 6; https://cpcb.nic.in/National-Air-Quality-Index/).
  - **Method:** each sub-index is a linear interpolation inside its band, on 24-hour means. The AQI is the larger sub-index, and that pollutant is "prominent".

    | Band | AQI | PM2.5 (µg/m³, 24 h) | PM10 (µg/m³, 24 h) |
    |---|---|---|---|
    | Good | 0–50 | 0–30 | 0–50 |
    | Satisfactory | 51–100 | 31–60 | 51–100 |
    | Moderate | 101–200 | 61–90 | 101–250 |
    | Poor | 201–300 | 91–120 | 251–350 |
    | Very poor | 301–400 | 121–250 | 351–430 |
    | Severe | 401–500 | 250+ (closed at 380) | 430+ (closed at 510) |

  - **Why it is only INDICATIVE:**
    - only PM2.5 and PM10 are used, while CPCB needs at least three pollutants, one of them PM;
    - the modelled values are a model's, not a station's.

    The label says exactly that: "not an official CPCB AQI".
- **Forecast:** two rolling 24-h windows (0–24 h and 24–48 h) of the modelled PM. This is what makes the Diwali-night advisory useful a day ahead.

### Heat (`heat.py`)

- **Points:** IMD's two Mumbai observatories, **Santacruz** and **Colaba**. The values come from Open-Meteo's forecast (temperature, humidity, apparent temperature and the daily maximum). Mumbai's heat is humid, so the heat index matters more than the maximum alone.
- **Heat index:** the US National Weather Service's Rothfusz regression, with both adjustments (https://www.wpc.ncep.noaa.gov/html/heatindex_equation.shtml). The bands are:
  - caution 27–32 °C;
  - extreme caution 32–41 °C;
  - danger 41–54 °C;
  - extreme danger ≥ 54 °C.
- **IMD heatwave, coastal stations:** a heatwave may be declared when the maximum departs from normal by 4.5 °C or more, provided the actual maximum is at least 37 °C. Source: IMD, *FAQ on Heat Wave* (https://internal.imd.gov.in/section/nhac/dynamic/FAQ_heat_wave.pdf).
  - The departure is taken from the Santacruz monthly normal maximum (IMD normals).
  - It runs on the **forecast** maximum, so it is MODELLED, never an IMD declaration.

### Cyclones and floods (`cyclones.py`)

- **GDACS** (the European Commission JRC and UN OCHA) has an open JSON API:
  - `geteventlist/SEARCH?eventlist=TC;FL` over the last 30 days;
  - `polygons/getgeometry` per cyclone, which returns:
    - the track legs, with their category;
    - the past and forecast positions;
    - the cumulative wind buffers: green 60 km/h, orange 90 km/h, red 120 km/h;
    - the uncertainty cone.
- **Region:** an event counts as regional when its centroid lies over the Arabian Sea and the north Indian Ocean near the west coast.
- **Computed here:**
  - the distance and bearing from Mumbai;
  - the closest approach of the track;
  - whether Mumbai lies inside a wind buffer (ray casting).
- **History, for context:** Cyclone **Tauktae** (May 2021) passed off the Mumbai coast with high winds, tree falls across the city and sea surge on Marine Drive and the Worli sea face. It is the reference case for the pre-positioning proposal below; it is not replayed.
- **Reliability:** GDACS's list API sometimes answers `400 Timeout expired` when its pool is busy. The client retries once, with a 45 s timeout, in the background, so no deck request waits on it.
- **IMD RSMC New Delhi** (https://rsmcnewdelhi.imd.gov.in/) is the official cyclone authority for the North Indian Ocean. Its bulletins are PDF and text pages, **not machine-readable**, so they are linked in the sheet and the pick text, not parsed.

### The Mithi river (`river.py`)

- **Level:** the Mithi at Kurla (landmark `mithi_kurla`) from the hydro service's emulated gauge, against the **4 m danger mark**. The BMC's river-level sensors are not public, so the chip says **EMULATED** on every reading. On 18–19 Aug 2025 the river stood at about 3.9 m (some reports: above the mark) and 350–500 people were evacuated near Kurla (The Statesman, Mongabay, HT, Aug 2025).
- **News signal:** a count of the items of the last 72 h in the reachable Mumbai feeds (in English, Marathi and Hindi) that mention the Mithi or an evacuation along it.
  - **Terms:** in English, Mithi, danger mark, Kranti Nagar, evacuated; in Marathi, मिठी नदी, धोक्याची पातळी, स्थलांतर; in Hindi, मीठी नदी, खतरे का निशान.
  - **What is kept:** only the count, the outlet and the link. Label: AGGREGATE. No person is named or kept.
  - The feeds are read at most every 30 minutes.

### Earthquakes (`quakes.py`)

- **Source:** the USGS FDSN event service, asked server-side for M ≥ 2.5 within 500 km of the city centre over 365 days. One small call an hour.
- **Mumbai is in seismic zone III** (IS 1893 (Part 1): 2016).
- **Completeness:** the catalogue is complete over the region only to a moderate magnitude, so "none in 30 days" means none catalogued.

### Tide (`tide_table.py`)

- **What the endpoint returns:** `GET /feeds/tide-table` shows the hydro service's **MODELLED** high and low waters at Apollo Bunder (`GET :8197/hydro/tide`). No published tide table is read for Mumbai, and the endpoint says so (**PUBLISHED: UNAVAILABLE**).
- **Comparison:** `compare()` is written and tested. It pairs each published extreme with the nearest modelled one of the same kind, in minutes and metres, ready for the day a table can be read.
- High waters of 4.5 m or more are what the BMC and the news treat as the flood trigger when they meet heavy rain (India TV, 27 May 2025).

### Fires (`fires.py`)

- **Source:** NASA FIRMS active-fire detections (VIIRS on three satellites, and MODIS) in the city box over the last 24 h, from FIRMS's public South Asia files, or the area API with `FIRMS_MAP_KEY`.
- **What is shown:** each detection with its time and the nearest landmark. Label: "satellite thermal anomaly · not a confirmed fire". A thermal anomaly can be an industrial flare or a dump fire as well as a building fire; Mumbai Fire Brigade confirms.

### Civic notices (`notices.py`)

- **Rule:** an agency notice page is read only after its robots rules are checked, and only notices about **places and roads** are kept: road works, diversions, drains, desilting, monsoon preparation, construction, AQI and so on.
  - **Never anything about a person:** hearings, payments, deaths, recruitment, councillors and the like are excluded by a second word list.
- **Mumbai Traffic Police:** the department's public site is read (robots rules checked; full certificate checking). On 30 Oct 2026 it answered and carried **no current traffic notice**: its notices page was last updated on 28 Aug 2025, and current advisories go out on social media, which Sajag does not read. The chip says so rather than showing zero as "all clear".
- **BMC pages:** not read; the BMC's waterlogging and pump information is not published as a page Sajag can read without guessing at its layout.

### Street photos (`street_image.py`)

- **What it is for:** the Road state panel on a camera's page offers the nearest public Mapillary photo as a still to read (the vision model's answer stays `UNVERIFIED-CAMERA`; [`vision.md`](vision.md#the-stills-the-deck-sends)). It is labelled "Reference photo · not live" with the date it was taken (it can be years old) and "© Mapillary contributors, CC BY-SA 4.0". Mapillary blurs faces and number plates before it publishes.
- **Two routes:**
  - `GET /feeds/street-image?lat=&lon=` gives the facts: the nearest non-panoramic image within a 150 m box (the nearest of up to 500 the Graph API returns for it), its capture time, distance, compass angle and attribution, or `needs MAPILLARY_TOKEN` (no call without the key). Lookups are cached per point for 24 h, at most 500 a day.
  - `GET /feeds/street-image.jpg?lat=&lon=` gives that photo's **bytes**, because the deck's pages load images from their own origin only (the CSP is unchanged). Otherwise it answers JSON: 503 without the key or offline (no call), 404 with nothing in range, 502 when Mapillary or its CDN gave nothing usable.
- **Fetch rules for the bytes:**
  - only the `thumb_1024_url` the Graph API returned, over https, on Mapillary's CDN hosts (`scontent…fbcdn.net`, matched in full);
  - redirects followed by hand, at most two, and only to those hosts;
  - at most 4 MB (the declared length is checked first, then the stream is cut off);
  - `image/jpeg` or `image/png` only, and the body must start with that type's bytes;
  - 8 s in all;
  - the token travels only on the Graph API request, never to the CDN; errors are scrubbed with `keys.redact` (no key and no signed URL query string);
  - a cached lookup whose signed thumbnail URL has expired (CDN 403/404/410) is asked for afresh once.
- **Storage:** none on disk. The last 12 photos stay in memory for 30 minutes; at most 500 photo fetches a day. The answer carries `cache-control: no-store`.
- **Checked on 30 Oct 2026** on Mumbai (dev instance, the real key): 16 of 18 sampled modelled camera sites have a photo within 150 m; the `.jpg` route served a 124 KB still. (Earlier, on the Kolkata reference pack: a 1024×768 JPEG taken in 2018, 35 m away.)

## The polite fetcher (`fetch.py`)

- **Limits:** each feed has a cache age, a minimum interval between refreshes and a daily cap (the table in `services/cityfeeds/README.md`).
- **Stale-while-revalidate:** once a feed has answered, an expired cache answers at once and one background refresh starts. A slow upstream never holds a deck request.
- **First request:** the first request for a feed waits at most 25 s.
- **Failures:** a failed refresh keeps the last answer, marked `stale` with the error. A feed that never answered is `UNAVAILABLE`, never zero.
- **Keep-fresh loop:** a loop touches every feed once a minute.
- **Offline mode:** `SAJAG_FEEDS_OFFLINE=1` makes no call. Recorded fixtures (`src/cityfeeds/fixtures/`) answer, labelled `RECORDED`. The fixtures were recorded on Mumbai on 30 Oct 2026 (`scripts/record_fixtures.py`). To keep them clean, the news fixture keeps dates only; a headline and its link are kept only when the item mentions the Mithi or waterlogging, so a city's politics, crime and people never land in the repository.

## Proposals (never actions)

Proposals have the same shape as hydro's and forecast's:

- `state: proposed`;
- `actions[]` of `{verb, target_urn, params, requires_officer: true, reversible: true}`;
- `recommendation.decision: await_officer`;
- `human_gate: {required_role: duty_officer, officer: null, decided_at: null}`.

When a trigger does not hold, the answer says why, with the threshold (`{"none": "…"}`). The deck shows it in the reader's language.

| Proposal | When | What |
|---|---|---|
| **Air health advisory** | City band Moderate or worse now, or Poor or worse within 48 h. On a **firecracker night** (Diwali, 8 Nov 2026 ±1 day) Moderate within 48 h is enough. | A public advisory in English, मराठी and हिंदी, from CPCB's band health statements. On a firecracker night it adds a line on the smoke after dark. At Poor or worse, a note to Mumbai Traffic Police: N95 masks at the busiest junction posts and shorter turns. |
| **Heat duty-shift advisory** | Heat index ≥ 41 °C (danger) within 48 h; an IMD-criteria heatwave day in the forecast; or ≥ 32 °C from April to June | Turns of at most 2 h at exposed posts through 11:00–16:00 IST, with water, ORS and shade, per NDMA's 2019 heat-wave guidelines: Kalanagar, Sion Circle, Dadar TT, King's Circle, Haji Ali, Worli Naka, CSMT and the Western Express Highway at Andheri. Plus a citizen advisory in three languages. |
| **Cyclone pre-positioning** | Mumbai inside a GDACS wind buffer; the track within 300 km; or an Orange or Red alert within 600 km | Tree-cutting teams (BMC's garden department, Mumbai Fire Brigade, the power utility for wires) staged on the arterials: the WEH at Kalanagar, the EEH at Sion, Dr Ambedkar Road at King's Circle, LBS Marg at Ghatkopar, SV Road at Andheri, the JVLR at Powai, Marine Drive and the Worli sea face. A sea-face advisory for Marine Drive, Worli and Juhu. After landfall, the roads reopen one by one. The officer decides where and when. |

## Deck surfaces

- **Proxy:** `/api/cityfeeds` → `127.0.0.1:${CITYFEEDS_PORT:-8199}`, prefix stripped (`hooks.server.ts`, and `vite.config.ts`'s `devAiProxies`). With the operator gate on, everything is denied except the citizen page's two reads: `GET /feeds/summary` and `GET /feeds/air`, with no `force`. The street photo routes are for signed-in officers only.
- **Road state panel** (`$lib/v3/object/RoadStatePanel.svelte`, a camera's page): "Nearby street photo" beside the sample stills and Upload. The panel asks for the facts when it opens; without the key, with nothing in range or with no camera position, the choice is disabled with a one-line note.
- **City row** (`$lib/cityfeeds/CityChips.svelte`):
  - **Where:** on the map under Rain · Tide, and on Home under "Next 2 hours".
  - **Each chip:** Air · Heat · Cyclone · River · Quake, each with its value, its band in words with a dot in the band's colour, and its honest label.
  - **Sheet:** a click opens the sheet (`FeedSheet.svelte`) with the figures, the proposal draft (or why there is none) and the sources.
- **Map layers** (both start off and are listed in the Layers sheet under "City feeds"):
  - **`air`:** the sites on the **existing** band ladder (`--v-band-green / -amber / -red / -black-fill`, no new colour token). A worse band also draws a larger dot, with a 450 m veil and an "AQI n" label.
  - **`cyclone`:** the GDACS buffers, track, positions and cone. It also draws a **bearing marker** at the city centre, so a storm 1,000 km away is still visible on the city map. With no active storm its row says "No active cyclone". The legend gains a line for each layer while it is on.
- **Citizen page:** "Air today" (`$lib/v3/public/AirToday.svelte`). It gives the city's band in one plain sentence and the advice, in the reader's language (Marathi digits only through the formatter), with a Listen button (the shared `ListenButton`) and the Modelled tag.
- **Strings:** `$lib/cityfeeds/packs.feeds.ts`, with `.mr.ts` and `.hi.ts`.

## Limits

- The modelled air values are a global model's on a coarse grid. The stations' own readings (OpenAQ, WAQI) are shown beside them as OBSERVED; the National AQI stays INDICATIVE because it uses two pollutants. CPCB's own bulletin on data.gov.in takes over the National AQI when `DATA_GOV_IN_API_KEY` is set.
- The site positions are locality-level.
- The heatwave test uses a monthly normal, not IMD's daily normal.
- The Mithi level is EMULATED until the BMC's sensors are available; only the news count is real, and it is aggregate.
- No published Mumbai tide table is read; the tide stays MODELLED.
- The Mumbai Traffic Police notices page is read but was last updated on 28 Aug 2025; current advisories are on social media, which Sajag does not read.
- WAQI answers, but on 30 Oct 2026 none of its 19 Mumbai stations carried a current value (all "-", last updated 23 Jun 2026); OpenAQ matched all 12 sites and is what the observed column shows.
