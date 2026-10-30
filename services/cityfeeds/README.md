# cityfeeds: open Mumbai situational feeds

This service fetches, caches and normalises the open feeds that describe Mumbai right now. It feeds the god's-eye **City** row (Air · Heat · Cyclone · River · Quake · Tide · Alert), the air and cyclone map layers, and the citizen page's "Air today". Every item carries an honest label:

- **LIVE**: a third-party open feed answered.
- **OBSERVED**: a monitoring station's own measurement, from a keyed service.
- **MODELLED**: computed here, or a model's value.
- **INDICATIVE**: National AQI bands applied to values that are not CPCB's AQI.
- **EMULATED**: a stand-in for a feed that is not public (the Mithi gauge).
- **PUBLISHED**: a figure an agency published, with its source.
- **AGGREGATE**: news mentions, counted.
- **UNAVAILABLE**: the feed did not answer; nothing is shown as zero.

In offline mode the recorded fixtures answer, labelled **RECORDED**.

The service drafts three kinds of **proposal**, never actions; a named officer decides each one:

- an **air** health advisory in मराठी, English and हिंदी (on Diwali nights from Moderate, naming the smoke);
- a **heat** duty-shift advisory for exposed Mumbai Traffic Police junction posts (CSMT, Haji Ali, Worli Naka, Dadar TT, Sion Circle, Kalanagar, Saki Naka, Ghatkopar), in Mumbai's two heat seasons (March–May and the "October heat");
- a **cyclone** plan to pre-position tree-cutting teams (BMC garden department and 1916 disaster control, Mumbai Fire Brigade, the power utility) on ten arterials (WEH, EEH, Dr Ambedkar Road, LBS Marg, SV Road, JVLR, SCLR, Andheri–Kurla Road, Sion–Panvel Highway, Marine Drive).

The arterials and posts are read from `cities/mumbai/network.json` by road name and junction key; no segment id is hard-coded.

## Sources and their state (checked live from this box on 30 Oct 2026)

| Feed | Source | Label | Live check, 30 Oct 2026 | Schedule (cache, min interval, daily cap) |
|---|---|---|---|---|
| Air (model) | Open-Meteo air-quality API (CAMS) at twelve CPCB/MPCB/BMC stations, Colaba to Borivali; coordinates from the CPCB station list via OpenAQ | LIVE feed, MODELLED values, INDICATIVE AQI | 12 stations; city AQI 85, Satisfactory (Sewri) | 15 min, 60 s, 200 |
| Air (observed) | OpenAQ v3 (`OPENAQ_API_KEY`): the stations' own CPCB data | OBSERVED | live: 12 of 12 stations matched; observed indicative AQI 98 (Deonar) | 30 min, 5 min, 96 |
| Air (observed) | WAQI (`WAQI_TOKEN`): `/v2/map/bounds`, then `/search/?keyword=mumbai` (bounds lists nothing for Mumbai) | OBSERVED | live, but 0 values: WAQI's 19 Mumbai stations carry no current value (`-`; their feeds were last updated on 23 Jun 2026) | 30 min, 5 min, 96 |
| Air (observed) | CPCB on data.gov.in (`DATA_GOV_IN_API_KEY`), city "Mumbai" | OBSERVED | off: needs `DATA_GOV_IN_API_KEY` (OpenAQ carries the same data) | 30 min, 5 min, 96 |
| Heat | Open-Meteo forecast at IMD's Santacruz (airport) and Colaba observatories; NWS heat index; IMD coastal heatwave test against the Santacruz 1991–2020 normals | LIVE feed, MODELLED | heat index 34.1 °C now; 48-h peak 37.2 °C; the October duty-shift proposal is drafted | 15 min, 60 s, 200 |
| Cyclones and floods | GDACS event list and geometry, Arabian Sea and west-coast box (5–28 N, 55–80 E) | LIVE; distances MODELLED | nothing active in the box | 30 min, 120 s, 96 |
| Alerts | NDMA Sachet CAP RSS, kept when issued for Maharashtra (IMD Mumbai, Maharashtra SDMA) or naming the Mumbai region; CAP XML read for at most 6 kept alerts | LIVE | 100 alerts in the feed, 4 from IMD Mumbai, 1 for Mumbai and Mumbai Suburban (valid until 12:30 IST) | 15 min, 120 s, 120 |
| Mithi river | No public live gauge: the BMC's and IFLOWS-Mumbai's sensors are not open, and CWC has no Mithi station. The Kurla (Kranti Nagar) gauge is a deterministic stand-in shaped by the modelled tide, beside the reported 4 m danger mark | EMULATED | 1.79 m (emulated), "normal" | computed on request |
| Waterlogging news | Mid-day, Times of India Mumbai, Hindustan Times Mumbai, ABP Majha Mumbai (Marathi): items mentioning the Mithi or waterlogging, counted | AGGREGATE | 4 of 4 outlets read, 109 items, 0 mentions | 30 min, 600 s, 48 |
| Quakes | USGS FDSN event service, M ≥ 2.5 within 500 km of Mumbai, last 365 days | LIVE | 1 in 30 days, 5 in 365 | 60 min, 300 s, 48 |
| Tide | Apollo Bunder harmonic model (`tide_model.py`, a byte-for-byte copy of the hydro service's `tide.py`), checked against the BMC's published 2025 high-tide advisories | MODELLED; PUBLISHED (the check) | level 3.26 m now; next high water 4.31 m at 03:16 IST; the 12 published tides are matched within 17 min and 0.21 m (mean 7 min, 0.07 m) | computed on request |
| Notices | Mumbai Traffic Police public site (home and "सूचना" pages; robots.txt disallows only `/wp-admin/`): traffic notices only | LIVE | read; 0 current traffic notices (the site lists none, and its notices page was last updated on 28 Aug 2025) | 6 h, 1 h, 8 |
| Fires | NASA FIRMS: the area API with `FIRMS_MAP_KEY` (2 days), else the public South Asia 24-h files, kept to the Mumbai box | LIVE; "not a confirmed fire" | live (area API): 1 hotspot (Navi Mumbai shore), 0 in 24 h | 3 h, 30 min, 16 |
| Street stills | Mapillary (`MAPILLARY_TOKEN`), the nearest public photo, CC BY-SA 4.0 | Reference photo · not live | live: 16 of 18 sampled modelled camera sites have a photo within 150 m; the .jpg route served a 124 KB still | per point 24 h, 500 a day |

**Not used:**

- **IMD's city-weather pages** (city.imd.gov.in/citywx) are script-rendered, and on 30 Oct 2026 they carried an injected third-party script. They are not read.
- **IMD's current-weather API** (mausam.imd.gov.in/api) answers 401 without a whitelisted address.
- **BMC portal and disaster-management site**: both are script-rendered apps with no public feed.
- **BMC pumping stations**: their status is not public. They are EMULATED in the hydro service.
- **Mumbai Port Authority tide tables**: not machine-readable.

## API (production port 8199, loopback)

| Route | Returns |
|---|---|
| `GET /health` | Service, labels, each feed's schedule and usage today, `keyed_sources` (`live` / `needs <KEY>` / `error: …`) |
| `GET /feeds/summary` | Chips `air · heat · cyclone · river · quake · tide · alert`: value, unit, band, label, source, as-of, mode, stale |
| `GET /feeds/air` | Twelve stations: now, 24-h PM2.5/PM10 means, indicative National AQI, a 48-h forecast of the daily band; OBSERVED values beside them; `proposal` |
| `GET /feeds/heat` | Santacruz and Colaba: heat index now and its 48-h peak, the IMD coastal heatwave test per forecast day; `proposal` |
| `GET /feeds/cyclones` | GeoJSON FeatureCollection: tracks, positions, 60/90/120 km/h wind buffers, cone, flood points; `active`, `nearest`, `proposal` |
| `GET /feeds/alerts` | Sachet CAP alerts for Maharashtra: issuer, text, English headline, severity, area, validity, `for_mumbai`, `active` |
| `GET /feeds/river` | The EMULATED Mithi gauge at Kurla, labelled as such, with the reported danger mark; `news` (mention count) |
| `GET /feeds/quakes` | GeoJSON of the USGS events within 500 km; counts for 30 and 365 days |
| `GET /feeds/tide-table` | `modelled` (Apollo Bunder: level now, gates, next 48 h of high and low waters), `published` (the BMC's 2025 tides with sources; the 2026 calendar's spells), `comparison` |
| `GET /feeds/notices` | Mumbai Traffic Police traffic notices (title, link, date), or why there are none |
| `GET /feeds/fires` | GeoJSON of NASA FIRMS hotspots in the Mumbai box, each with its nearest landmark; `key` state |
| `GET /feeds/street-image?lat=&lon=` | The nearest Mapillary photo (thumbnail URL, capture time, attribution, licence), or `needs MAPILLARY_TOKEN`; never calls the vision model. Mumbai only (18.7–19.5 N, 72.6–73.3 E) |
| `GET /feeds/street-image.jpg?lat=&lon=` | That photo's JPEG/PNG bytes, fetched here so the deck stays same-origin. Only the Graph API's own thumbnail URL on Mapillary's CDN hosts is fetched: no redirect elsewhere, at most 4 MB, type checked, 8 s, `no-store`. Otherwise JSON 503, 404 or 502 |
| `GET /feeds/proposals` | Every drafted proposal, and why the others were not drafted |

`?force=1` refreshes past the cache, still inside the rate limits. The deck's public gate refuses it, and allows only `GET /feeds/summary` and `GET /feeds/air` anonymously. The street photo routes are for signed-in officers only.

**Compatibility:** the deck's cyclone layer and river panel still read `kolkata_in_wind_buffer_kmh` and `dvc_news`. Both are still served, with the same values as `city_in_wind_buffer_kmh` and `news`. Drop them once the deck reads the new names.

## Run and test

```bash
PYTHONPATH=src PORT=9201 python -m cityfeeds                    # dev; SAJAG_FEEDS_OFFLINE=1 for fixtures only
python -m pytest -q -p no:cacheprovider                         # offline: the recorded fixtures, no network
PYTHONPATH=src python scripts/record_fixtures.py [air.json …]   # re-record on purpose (the tests pin 30 Oct 2026)
```

The production unit is `infra/systemd/sajag-feeds.service` (127.0.0.1:8199). It runs from `.venvs/ai-forecast`, which already has every package the service needs. Settings use the `SAJAG_FEEDS_` prefix (none secret).

Five free keys are read by their own names from `~/.config/sajag/sajag.env` (`keys.py`):

- `DATA_GOV_IN_API_KEY`
- `WAQI_TOKEN`
- `OPENAQ_API_KEY`
- `FIRMS_MAP_KEY` (optional)
- `MAPILLARY_TOKEN`

A key is never logged, returned or stored in an error (`keys.redact`). Every host is reached with full certificate verification.

## Limits

- **Air:** the model values are CAMS's, on a coarse grid. The National AQI here uses PM2.5 and PM10 only, so it is indicative. The observed values are OpenAQ's copy of the CPCB station data. WAQI has no current Mumbai values.
- **Heat:** the IMD test runs on the forecast maximum. It is never an IMD declaration.
- **Mithi:** EMULATED. Its level is not a measurement and cannot cross the danger mark on its own. A real feed (IFLOWS-Mumbai or the BMC's sensors) replaces `emulated_mithi` without changing the view.
- **Tide:** a harmonic model. Its mean level is fitted to the BMC's 2025 high waters. Surge and wind set-up are not modelled.
- **Alerts:** a Sachet item counts "for Mumbai" only when its text or CAP area names Mumbai. Polygons are not read.
- **Notices:** Mumbai Traffic Police publishes day-to-day advisories on social media, which this service does not read.
- **Fires:** a hotspot is a satellite pixel hotter than its surroundings at overpass (375 m VIIRS, 1 km MODIS). It is never a confirmed fire, and never says who.
