# Data sources

Every outside source Sajag reads for Mumbai, what it gives, and how it is labelled. Each public endpoint named here
was checked from the build server on **30 Oct 2026 between 14:40 and 15:00 IST**, with one or two polite read-only
requests per host and a user agent that names Sajag. The "Check, 30 Oct 2026" column says what the source did when
we asked it. Keys were read from the environment only and never printed.

**The rule.** A source is in one of two buckets:

1. **Public, open or a free public service**: read **live**. If the free service needs a personal key, the code is
   wired and goes live the moment the key is in `~/.config/sajag/sajag.env` (read only from the environment,
   never printed or committed). Until then it makes no call and its health says `needs <ENV_VAR>`.
2. **Proprietary, or needs an agency's access or licence**: **emulated or simulated**, and labelled `EMULATED` (a
   stand-in for a feed) or `SIMULATED` (a scenario) wherever it shows. Never half-wired.

A public source never falls back to a recorded sample while a real route exists. When a live source fails, the
service keeps its **last live answer** and says how old it is; recorded samples answer only in offline mode, and
are labelled `RECORDED` (city feeds) or `cached-sample` (OSINT).

Labels used below: **LIVE** (a third-party feed answered), **OBSERVED** (a station's own measurement), **MODELLED**
(a model's or our computed value), **INDICATIVE** (National AQI bands applied to values that are not CPCB's AQI),
**AGGREGATE** (counts only), **OFFICIAL-VERIFIED** (an official publisher, OSINT tier), **EMULATED**, **SIMULATED**,
**UNAVAILABLE** (asked, did not answer; never shown as zero), "Reference photo · not live".

**Status words in the tables.** *Live* means the endpoint answered on 30 Oct and Sajag reads it. *Needs a free key*
means the code is wired but the key is not set on this server. *Not read* means we checked it and Sajag does not use
it, with the reason. The Mumbai box everywhere is the City Pack's `bbox` in `cities/mumbai/city.json`:
18.89–19.28 N, 72.77–72.99 E (Island City, Western and Eastern Suburbs, and the edge of Thane).

## At a glance

| Bucket | Sources |
|---|---|
| **LIVE** (no key) | Open-Meteo forecast, air quality and archive; NDMA SACHET CAP (Maharashtra feed); IMD CAP mirror; Mumbai Traffic Police public notices; GDACS; USGS; NASA FIRMS public files; OpenStreetMap tiles; Google News RSS; Mumbai outlets' RSS in English (TOI, HT, Mid-day, Indian Express, The Hindu, Free Press Journal), Marathi (Maharashtra Times, ABP Majha, TV9 Marathi) and Hindi (ABP Live, TV9 Hindi); r/mumbai (aggregate); GDELT bulk events |
| **LIVE** (free key set on this server) | OpenAQ v3 (CPCB/MPCB stations); WAQI; NASA FIRMS area API; Mapillary; Cesium ion |
| **Needs a free key** | CPCB real-time AQI on data.gov.in (`DATA_GOV_IN_API_KEY` not set) |
| **MODELLED** | Arabian Sea tide at Apollo Bunder (harmonic model); waterlogging risk, susceptibility, impact |
| **EMULATED** | BMC rain gauges and storm-water pumping stations; Mithi level; MTP signal controllers and detectors; ANPR; CCTV; ambulance (108) and fleet GPS; BEST bus positions; suburban rail and Metro running status |
| **SIMULATED** | Scenario traffic and events; paid traffic-speed feeds; crowd reports |
| **Checked, not read** | Loksatta, Navbharat Times and Lokmat feeds; BMC and Maharashtra SDMA portals; Mumbai Port Authority |

## 1. City feeds (`services/cityfeeds`, port 8199)

| Source | What it gives | Host | Key | Check, 30 Oct 2026 | Label |
|---|---|---|---|---|---|
| Open-Meteo air-quality API (CAMS model) | PM2.5, PM10, NO₂, O₃ at Mumbai's CPCB/MPCB station sites; 48-h forecast | `air-quality-api.open-meteo.com` | none | **Live:** HTTP 200 in 0.6 s for the Dadar / Matunga centre (24 hourly values) | LIVE feed, values MODELLED, National AQI INDICATIVE |
| CPCB real-time AQI on data.gov.in | Observed pollutant averages at every CAAQMS station in Mumbai | `api.data.gov.in` | `DATA_GOV_IN_API_KEY` | **Needs a free key:** not set on this server. Without a key the API answers 400 "Authorization field missing", so no call is made, and the National AQI comes from OpenAQ's copy of the same CPCB data (below) | OBSERVED (National AQI from its PM averages: INDICATIVE) |
| OpenAQ v3 | The CAAQMS stations' own PM2.5 and PM10: the latest value and the 24-hour means of the hourly values. OpenAQ's provider for these stations is CPCB, so with at least 16 hours (CPCB's rule) the means give the National AQI when data.gov.in has no key | `api.openaq.org` | `OPENAQ_API_KEY` | **Live (key set):** HTTP 200 in 0.7 s. 35 locations in the Mumbai box, **26 reporting within 24 hours**, all from provider CPCB: Bandra Kurla Complex (MPCB and IITM), Colaba, Worli, Siddharth Nagar-Worli, Chakala-Andheri East, Powai, Kurla, Sion, Borivali East (two), Deonar, Chembur, Byculla, Sewri, Shivaji Nagar, Ghatkopar, Kherwadi (Bandra East), Malad West, Mindspace-Malad West, Kandivali West, Mulund West, Khindipada-Bhandup West and three Thane stations. **Mazgaon was not listed.** The other 9 are retired or silent sensors (last values 2021–2026), so only readings under 24 hours old and above zero are read | OBSERVED (National AQI: INDICATIVE) |
| World Air Quality Index (aqicn.org) | Observed AQI (US EPA scale, as WAQI publishes it) from the station nearest each site, named, with its distance | `api.waqi.info` | `WAQI_TOKEN` | **Live (key set), nothing current for Mumbai:** HTTP 200, status `ok`, but the map-bounds call listed **0 stations** in the Mumbai box (the same call on the Kolkata reference pack's box listed 49, so the service and the token work). WAQI's `mumbai` city feed points at a station last updated on 4 Mar 2025. With no station in the box WAQI contributes no reading (never a zero), and Mumbai's observed air comes from OpenAQ | OBSERVED (when a station answers) |
| Open-Meteo forecast API | Temperature, humidity, heat index at the Santacruz and Colaba observatory points | `api.open-meteo.com` | none | **Live:** HTTP 200 in 0.5 s | LIVE feed, MODELLED |
| GDACS (EC JRC and UN OCHA) | Cyclones and floods in a box over the Arabian Sea and the west coast | `www.gdacs.org` | none | **Live:** HTTP 200 in 13.9 s (the list API is slow); 87 cyclone and flood events listed worldwide for October, **no tropical cyclone in the Arabian Sea** | LIVE; distances MODELLED |
| USGS earthquake catalogue | Quakes M ≥ 2.5 within 500 km of the city centre | `earthquake.usgs.gov` | none | **Live:** HTTP 200; 0 quakes since 23 Oct | LIVE |
| Mumbai news RSS (the outlets' feeds in §2) | Mentions of waterlogging and road closures, counted | the outlets' own feeds | none | **Live:** see §2 for each feed's answer | AGGREGATE |
| Sajag hydro service | Modelled Apollo Bunder high and low waters | `127.0.0.1:8197` (this server) | none | Local service | MODELLED |
| NASA FIRMS active fires | Satellite hotspots (VIIRS S-NPP, NOAA-20, NOAA-21, MODIS) in the Mumbai box | `firms.modaps.eosdis.nasa.gov` | none; `FIRMS_MAP_KEY` optional | **Live, both routes:** the public South Asia 24-h S-NPP file answered HTTP 200 (1,400 hotspots for the region, **0 in the Mumbai box**); with the key, the area API for the box (2 days) answered HTTP 200 with 0 hotspots | LIVE; each point "satellite thermal anomaly, not a confirmed fire" |
| Mapillary | The nearest public street-level photo to a camera site: the Road state panel's "Nearby street photo", which the officer can send to the vision model (the answer stays UNVERIFIED-CAMERA). The city feeds fetch the photo's bytes (`/feeds/street-image.jpg`) so the deck stays same-origin | `graph.mapillary.com`; the photo from `scontent…fbcdn.net` (allow-listed, ≤ 4 MB, JPEG/PNG, 8 s, memory only) | `MAPILLARY_TOKEN` | **Live (key set):** HTTP 200. In a box of about 330 m round each site: CSMT 80 images (taken 2015–2025), Dadar TT 111 (2018–2023), Kalanagar 49 (2016–2024), **Hindmata none**. Without a token no call is made and the choice is disabled with a note | Reference photo · not live, with the date taken (CC BY-SA 4.0; faces and plates blurred by Mapillary) |

`GET /health` and `GET /feeds/summary` list each keyed source as `live`, `needs <ENV_VAR>` or `error: <reason>`.
The observed air values sit beside the modelled ones (`/feeds/air` → `observed`, and each site's `observed`); the
summary's air chip keeps its modelled value and adds `observed` (the CPCB National AQI: data.gov.in's averages
when that key is set, else the 24-hour means of OpenAQ's copy of the same stations, with `provider` saying which).

**River levels.** Mumbai's river is the Mithi. Its level is measured by the BMC's own sensors, which are not
public, so the Mithi level in Sajag is **EMULATED** (§7). Sajag reads no Central Water Commission station for
Mumbai.

## 2. OSINT event intelligence (`services/osint-ingress`, port 8193)

Every host is on an exact allow-list (`safe_http.ALLOWED_HOSTS`); robots.txt is honoured. Events are about places,
never persons. Social and news signals are counted in aggregate; a single social post is never surfaced on its own.
The outlets also carry crime and political news: the scope gate (`osint_common/scope.py`) drops crime, conflict and
political items, and keeps a procession or gathering only for its road impact, with political terms withheld.

| Source | What it gives | Host | Key | Check, 30 Oct 2026 | Label |
|---|---|---|---|---|---|
| NDMA SACHET CAP | Official alerts for Maharashtra (the state's own CAP RSS, `rss_maharashtra.xml`); an alert naming Mumbai City or Mumbai Suburban is kept at city level, any other Maharashtra alert at state level | `sachet.ndma.gov.in` | none | **Live:** HTTP 200 in 0.1 s, 10 items: district nowcasts written in Marathi (thunderstorm and light rain for Thane, Ahilyanagar, Nashik and others). The national feed (`rss_india.xml`) also answered 200, with 4 Maharashtra items among its 100 | OFFICIAL-VERIFIED |
| IMD CAP (WMO Alert Hub mirror) | IMD alerts, kept to Maharashtra | `cap-sources.s3.amazonaws.com` | none | **Live:** HTTP 200, empty feed (0 items) | OFFICIAL-VERIFIED |
| IMD Regional Meteorological Centre, Mumbai | Santacruz and Colaba observatory pages, warnings | `mausam.imd.gov.in` (`/mumbai/`) | none | **Reachable:** HTTP 200 (an HTML page). Linked, not parsed: no machine-readable observatory feed. IMD's published Santacruz and Colaba totals are quoted, with source, in the storm replay | linked |
| Mumbai Traffic Police public notices | The department's current traffic notifications (road closures, diversions and alternate routes, parking restrictions), one signal per notice, about places | `mtperp.mahatrafficechallan.gov.in` (`/PublicNotice.htm`, linked as "अधिसूचना" from `trafficpolicemumbai.maharashtra.gov.in`) | none | **Live:** HTTP 200 in 0.8 s; a table of 50 notices, the newest dated 29 Oct 2026 (a road closure with an alternate route, a parking restriction); robots.txt answers 404, so no restriction (RFC 9309) | OFFICIAL-VERIFIED |
| Google News RSS | Mumbai headlines for place and hazard queries | `news.google.com` | none | **Live:** HTTP 200; 100 items for "Mumbai waterlogging" | news tier |
| Times of India, Mumbai | Mumbai headlines (English) | `timesofindia.indiatimes.com` (`/rssfeeds/-2128838597.cms`) | none | **Live:** HTTP 200, 20 items, every link under `/city/mumbai/` | news tier |
| Hindustan Times, Mumbai | Mumbai headlines (English) | `www.hindustantimes.com` (`/feeds/rss/cities/mumbai-news/rssfeed.xml`) | none | **Live:** HTTP 200, 49 items | news tier |
| Mid-day, Mumbai | Mumbai headlines (English) | `www.mid-day.com` (`/Resources/midday/rss/mumbai-news.xml`) | none | **Live:** HTTP 200, 30 items | news tier |
| Indian Express, Mumbai | Mumbai headlines (English) | `indianexpress.com` (`/section/cities/mumbai/feed/`) | none | **Live:** HTTP 200, 200 items | news tier |
| The Hindu, Mumbai | Mumbai headlines (English) | `www.thehindu.com` (`/news/cities/mumbai/feeder/default.rss`) | none | **Live:** HTTP 200, 60 items | news tier |
| Free Press Journal | Headlines (English) | `www.freepressjournal.in` (`/stories.rss`) | none | **Live, site-wide only:** HTTP 200, 110 items. The `section=mumbai` filter is not honoured (items from every section come back), so only items that name a Mumbai place count | news tier |
| Maharashtra Times, Mumbai | Mumbai headlines (Marathi) | `maharashtratimes.com` (`/maharashtra/mumbai-news/rssfeed/2429656.xml`) | none | **Live:** HTTP 200, 50 items. Its generic RSS paths (`rssfeedsdefault.cms`, `rssfeedstopstories.cms`, `rss.cms`) answer 404; the Mumbai section feed works | news tier |
| ABP Majha, Mumbai | Mumbai headlines (Marathi) | `marathi.abplive.com` (`/news/mumbai/feed`) | none | **Live:** HTTP 200, 10 items | news tier |
| TV9 Marathi, Mumbai | Mumbai headlines (Marathi) | `www.tv9marathi.com` (`/mumbai/feed`) | none | **Live:** HTTP 200, 59 items | news tier |
| ABP Live, Maharashtra | Maharashtra headlines (Hindi) | `www.abplive.com` (`/states/maharashtra/feed`) | none | **Live:** HTTP 200, 10 items | news tier |
| TV9 Hindi, Maharashtra | Maharashtra headlines (Hindi) | `www.tv9hindi.com` (`/state/maharashtra/feed`) | none | **Live:** HTTP 200, 30 items | news tier |
| Loksatta | Marathi headlines | `www.loksatta.com` | — | **Not read:** `/feed/` and `/mumbai/feed/` redirect to HTML pages; no RSS found | — |
| Navbharat Times | Hindi headlines | `navbharattimes.indiatimes.com` | — | **Not read:** its RSS index page answers 200 and lists a Mumbai feed, but that feed answered HTTP 404 | — |
| Lokmat | Marathi headlines | `www.lokmat.com` | — | **Not read:** the Mumbai RSS answered HTTP 403 to Sajag's user agent, and robots.txt did not answer within 20 s. A refusal is respected, never worked round | — |
| GDELT 2.1 Events (bulk) | Machine-coded events for Mumbai / Maharashtra | `data.gdeltproject.org`; after a 404, the same file from GDELT's public bucket on `storage.googleapis.com` (that one path shape only) | none | **Live:** HTTP 200 (`lastupdate.txt` named the 09:15 UTC file). The host is a CDN that can cache a 404 for an hour when a 15-minute file is asked for before it is uploaded; the bucket copy has no such cache and passes the same MD5 check | news tier |
| GDELT DOC 2.0 | Article list | `api.gdeltproject.org` | none | **Not re-checked on 30 Oct.** On 29 Oct it answered HTTP 429 to this server even at one request per 15 min: GDELT limits each IP address, and the server shares a campus NAT address. Runs every 30 min with jittered exponential back-off (Retry-After honoured, at most 2 h), and meanwhile shows the last live answer with its real fetch time and age | news tier |
| Reddit r/mumbai RSS | Public posts, aggregate only, authors dropped | `www.reddit.com` (`/r/mumbai/new/.rss`) | none | **Live:** HTTP 200, 25 entries. The front-page feed (`/r/mumbai/.rss`) answered 429 a few minutes earlier: Reddit limits unauthenticated readers, so a refusal backs the connector off and nothing from it is counted meanwhile | social, unverified |
| Common Crawl | Backfill only, never scheduled | `index.commoncrawl.org`, `data.commoncrawl.org` | none | Not scheduled | — |

**Official pages checked for Mumbai and not read.** Each answered, with a verified certificate, but none publishes
a list of current notices that Sajag could read without guessing at page layout:

- **Mumbai Traffic Police home page**, `https://trafficpolicemumbai.maharashtra.gov.in/`: HTTP 200 (Marathi);
  robots.txt allows everything except `/wp-admin/`; its WordPress feed (`/feed/`) answered HTTP 500. Its
  "अधिसूचना" (notifications) link leads to the public notices table above, which is what Sajag reads.
- **Mumbai Police**, `https://mumbaipolice.gov.in/`: HTTP 200; not a traffic-advisory source.
- **BMC**, `https://portal.mcgm.gov.in/` (HTTP 200) and its disaster-management site `https://dm.mcgm.gov.in/`
  (HTTP 200): no documented machine-readable rain-gauge, pump or waterlogging feed, so those stay EMULATED (§7).
- **Maharashtra SDMA**, `https://sdma.maharashtra.gov.in/`: HTTP 200; the state's alerts already reach Sajag as
  CAP through SACHET.

## 3. Rain, tide and forecast (`services/hydro`, `services/forecast`)

| Source | What it gives | Host | Key | Check, 30 Oct 2026 | Label |
|---|---|---|---|---|---|
| Open-Meteo forecast (15-minute precipitation) | Rain nowcast at fixed points over the Mumbai box (the waterlogging spots and arterials) | `api.open-meteo.com` | none | **Live:** HTTP 200 in 0.5 s; 96 fifteen-minute steps for the Hindmata point | LIVE, "model nowcast, not a gauge" |
| Open-Meteo archive | Historical rain for the storm replay (18–19 August 2025) | `archive-api.open-meteo.com` | none | **Live:** HTTP 200; the hourly series for 18–19 Aug 2025 at the Santacruz grid point | ARCHIVE (reanalysis) |
| IMD observed totals | The official rain totals the replay is anchored to (Santacruz, Colaba, Vikhroli) | IMD press releases and bulletins | — | Quoted with source; not fetched at run time | OBSERVED (IMD) |
| Arabian Sea tide at Apollo Bunder | Harmonic tide model from published constants (no public real-time gauge feed is read) | computed | — | — | MODELLED (approximate) |
| Forecast models (Chronos-2, TimesFM) | Weights from Hugging Face, loaded offline | downloaded once | — | Offline at run time (`HF_HUB_OFFLINE=1`) | the forecast is MODELLED; its history SIMULATED unless real |

The tide matters because of how Mumbai floods: when a heavy burst coincides with a high tide of about 4.5 m, the sea
outfalls are closed and the water has nowhere to go (BMC chief engineer, Free Press Journal, 2025). The tide model
gives the phase and the high-water times; the nowcast labels the result MODELLED.

**Mumbai Port Authority**, `https://mumbaiport.gov.in/`: the TLS handshake failed on 30 Oct (curl: certificate
chain does not verify, "unable to get local issuer certificate"). Sajag does not read it and makes no TLS exception
for it; the tide stays MODELLED.

## 4. Maps and imagery (`services/command-deck`, in the browser)

| Source | What it gives | Host | Key | Check, 30 Oct 2026 | Label |
|---|---|---|---|---|---|
| OpenStreetMap raster tiles | Basemap (keyless default) | `tile.openstreetmap.org` | none | **Live:** HTTP 200 for a zoom-12 tile over Dadar | "© OpenStreetMap contributors" |
| Cesium ion: World Terrain, Bing aerial, Google Photorealistic 3D Tiles | 3D city and imagery for signed-in officers | `api.cesium.com`, `*.virtualearth.net`, `tile.googleapis.com` | `SAJAG_CESIUM_ION_TOKEN` | **Live (token set):** HTTP 200 for the World Terrain asset endpoint | "not a live image" |
| Fonts | Typefaces | committed under `static/fonts` | — | Never fetched at run time | — |

Build-time data, committed or provisioned once and never fetched by the running system: the OpenStreetMap road
network, junctions and stations (Overpass extracts committed with the City Pack under `cities/<city>/osm/`, ODbL),
waterways for flood susceptibility, the Copernicus DEM GLO-30 terrain tile (the derived susceptibility is MODELLED),
and the reference photos and agency logos from Wikimedia Commons ("Reference photo · not live"; agency names and
marks belong to their owners, and Sajag is not affiliated with them).

## 5. TLS

Every Mumbai host Sajag reads verifies with full certificate checking, and **no TLS exception is made for any of
them**. The one Mumbai host whose chain did not verify (the port, §3) is simply not read. No proxy, browser
disguise or other way round an access control is used anywhere: every request names Sajag in its user agent.

The city feeds hold no TLS exception at all: the Kolkata reference pack's pinned port certificate (`tls.py`) was
removed with the move to Mumbai, and `services/cityfeeds` reads every host with plain, fully verified HTTPS. One
narrow, documented exception remains for a host of the Kolkata reference pack, a legacy-renegotiation allowance in
`services/osint-ingress/src/osint_ingress/safe_http.py` (`TLS_COMPAT`). It does not switch a certificate check off,
and it does not apply to a Mumbai host.

## 6. Keys you can add (all free)

Add a line to `~/.config/sajag/sajag.env` (mode 600), then restart the city feeds
(`systemctl --user restart sajag-feeds`). Each goes live at once; health shows `live`.

| Variable | Service | On this server, 30 Oct 2026 | Sign up |
|---|---|---|---|
| `DATA_GOV_IN_API_KEY` | CPCB real-time AQI (observed, the National AQI's own inputs) | not set | <https://data.gov.in/> (sign in; the key is under My Account) |
| `WAQI_TOKEN` | World Air Quality Index station AQI | set | <https://aqicn.org/data-platform/token/> |
| `OPENAQ_API_KEY` | OpenAQ v3 station measurements | set | <https://explore.openaq.org/register> (then Account settings → API key) |
| `FIRMS_MAP_KEY` | NASA FIRMS area API (optional; the public files already run without it) | set | <https://firms.modaps.eosdis.nasa.gov/api/map_key/> |
| `MAPILLARY_TOKEN` | Mapillary street-level stills (a client token) | set | <https://www.mapillary.com/dashboard/developers> |
| `SAJAG_CESIUM_ION_TOKEN` | Cesium ion 3D tiles and terrain for signed-in officers (the deck, not the city feeds; recreate the deck instead) | set | <https://ion.cesium.com/> |

## 7. Proprietary and agency feeds: emulated or simulated

These need an agency's access or a paid licence. Each is a stand-in, labelled where it shows.

| Feed | Who holds it | Stand-in | Label shown |
|---|---|---|---|
| Storm-water pumping stations (Haji Ali, Irla, Love Grove, Cleveland Bunder, Britannia, Gazdarbandh) and their pump states | BMC | `services/hydro` pump adapter: real station names and places, invented state | EMULATED ("Pump status is emulated") |
| Rain gauges and waterlogging sensors | BMC (disaster control, 1916) | rain comes from the live Open-Meteo nowcast instead; gauge readings, where shown, are stand-ins | EMULATED |
| Mithi river level | BMC | emulated level against the danger mark | EMULATED |
| Arabian Sea tide gauge | Mumbai Port Authority | harmonic tide model for Apollo Bunder | MODELLED (approximate) |
| Traffic detector stations | Mumbai Traffic Police | `signal-ingress` synthetic rows | SIMULATED FEED |
| Signal controllers | Mumbai Traffic Police | no adapter; timing plans are `osm_assumed` templates; approved timings are recorded, no controller changes | MODELLED; "the signal adapter is emulated" |
| Paid traffic-speed APIs (TomTom, HERE, Google) | commercial | `signal-ingress` synthetic mapping-API feed; no vendor wired | SIMULATED FEED |
| Ambulance (108) and fleet GPS / AVL, escort GPS, patrol units | operators, Mumbai Police | synthetic and emulated positions | EMULATED |
| BEST bus positions and diversions | BEST | emulated positions on the City Pack's roads | EMULATED |
| Suburban rail (Central and Western Railway) and Metro running status | the railways, Metro operators | emulated running status (for example, locals stopped at Sion and Kurla in a storm scenario) | EMULATED |
| Crowdsourced traffic reports | commercial | synthetic | SIMULATED FEED |
| ANPR / number-plate cameras and camera sites | Mumbai Traffic Police | `EmulatedAnprSource` on modelled camera sites; plates in `MH 01 AB 1234` form, masked until a named officer is on duty | EMULATED |
| CCTV video | Mumbai Police | none ingested; sample stills, or the nearest public Mapillary photo (§1) | "Sample still · not live"; "Reference photo · not live" with its date |
| Scenario events, crowds (Ganeshotsav visarjan, Wankhede egress, station surge), historical traffic | — | event emulator, forecast and twin profiles | SIMULATED / EMULATED |

Junction signal entities are badged `emulated`, not `live`: their phase is the stored program's clock, with no
controller behind it (`services/traffic-oracle/src/traffic_oracle/city/entities.py`).

## 8. Checked and not used

- **WAQI for Mumbai** answers, but listed no station in the Mumbai box on 30 Oct (§1); it stays wired and contributes
  no reading, never a zero, until a station appears.
- **Loksatta, Navbharat Times and Lokmat** offered no readable feed to Sajag on 30 Oct (§2). Marathi coverage comes
  from Maharashtra Times, ABP Majha, TV9 Marathi and SACHET's Marathi alerts; Hindi from ABP Live and TV9 Hindi.
- **Mumbai Traffic Police home page** has no notice feed of its own; its notices are read from the public notices
  table on the e-challan portal (§2).
- **Mumbai Port Authority** failed certificate verification (§3).
- **IMD RSMC and RMC Mumbai bulletins** are HTML, PDF and text, linked rather than parsed.
