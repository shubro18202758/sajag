/**
 * The city-feeds string pack — the City chip row (Air · Heat · Cyclone · River · Quake), its sheet, the air and
 * cyclone map layers and the citizen page's "Air today". EN here; HI and MR in ./packs.feeds.hi.ts and
 * ./packs.feeds.mr.ts, complete for every key (tests/cityfeeds.unit.mjs checks it). Every key starts with `cf_`.
 *
 * Copy rules (as packs.ai): sentence case, no ALL-CAPS word outside the acronym list, at most one " · " per
 * string, titles ≤ 32 characters. Honest labels say what a number is: live, modelled, indicative, aggregate,
 * recorded. Numbers stay in Latin digits in the console; the public card renders them in the reader's digits.
 * A proposal is always a proposal; a named officer decides; if no one decides, the current plan holds.
 */
import { registerPack } from '$lib/i18n/strings';
import { langChunks } from '$lib/i18n/load';

type Fn = (...args: unknown[]) => string;
export type FeedsPack = Record<string, string | Fn>;

const s = (v: unknown) => String(v ?? '');

const en = {
	// ── the chip row ──
	cf_row_aria: 'City situation: air, heat, cyclone, river and quake',
	cf_row_title: 'City',
	cf_chip_air: 'Air',
	cf_chip_heat: 'Heat',
	cf_chip_cyclone: 'Cyclone',
	cf_chip_river: 'River',
	cf_chip_quake: 'Quake',
	cf_unavailable: 'Unavailable',
	cf_open_tip: 'Open the sources and the proposal drafts',
	cf_air_val: (n: unknown) => `AQI ${s(n)}`,
	cf_naqi_good: 'Good',
	cf_naqi_satisfactory: 'Satisfactory',
	cf_naqi_moderate: 'Moderate',
	cf_naqi_poor: 'Poor',
	cf_naqi_very_poor: 'Very poor',
	cf_naqi_severe: 'Severe',
	cf_heat_val: (n: unknown) => `${s(n)} °C`,
	cf_hi_normal: 'Comfortable',
	cf_hi_caution: 'Caution',
	cf_hi_extreme_caution: 'Extreme caution',
	cf_hi_danger: 'Danger',
	cf_hi_extreme_danger: 'Extreme danger',
	cf_cyc_none: 'No active cyclone',
	cf_cyc_val: (name: unknown, km: unknown) => `${s(name)}, ${s(km)} km away`,
	cf_alert_none: 'None',
	cf_alert_green: 'Green alert',
	cf_alert_orange: 'Orange alert',
	cf_alert_red: 'Red alert',
	cf_river_val: (n: unknown) => `${s(n)} above warning`,
	cf_river_none: 'All below warning',
	cf_river_normal: 'Normal',
	cf_river_no_threshold: 'Normal',
	cf_river_near_frl: 'Reservoir near full',
	cf_river_above_warning: 'Above warning',
	cf_river_above_danger: 'Above danger',
	cf_quake_val: (n: unknown) => `${s(n)} in 30 days`,
	cf_quake_none: 'None in 30 days',
	cf_quake_quiet: 'Quiet',
	cf_quake_recent: 'Recent',
	cf_tag_indicative: 'Indicative',
	cf_tag_indicative_tip: 'National AQI bands applied to modelled values. Not an official CPCB AQI.',
	cf_tag_aggregate: 'Aggregate',
	cf_tag_aggregate_tip: 'A count of news items, never about a person.',
	cf_tag_recorded: 'Recorded',
	cf_tag_recorded_tip: 'Offline mode: a recorded answer, not today’s feed.',
	cf_tag_stale: 'Stale',
	cf_tag_stale_tip: 'The feed did not answer just now; this is its last answer.',
	cf_tag_gdacs_tip: 'From GDACS, a live open feed. Distances from Mumbai are computed here.',
	cf_tag_proposal: 'Proposal waiting',
	cf_down: 'City feeds are not answering. Decisions still work.',

	// ── map layers (the Layers sheet) ──
	cf_sheet: 'City feeds',
	cf_l_air: 'Air quality',
	cf_l_cyclone: 'Cyclone track',
	cf_l_air_about: 'National AQI at the monitoring sites',
	cf_l_cyc_about: 'Arabian Sea cyclone track and wind buffers',
	cf_l_air_sub: (n: unknown, band: unknown) => `${s(n)} sites, worst ${s(band).toLowerCase()}`,
	cf_l_cyc_none: 'No active cyclone',
	cf_l_cyc_sub: (n: unknown, km: unknown) => `${s(n)} active, nearest ${s(km)} km away`,
	cf_l_none: 'No data',
	cf_l_feed: 'Feed unavailable',
	cf_l_loading: 'Loading…',
	cf_lg_air: 'Air quality (National AQI band)',
	cf_lg_cyclone: 'Cyclone track and wind buffers',

	// ── the sheet ──
	cf_sheet_close: 'Close',
	cf_title_air: 'Air quality',
	cf_title_heat: 'Heat',
	cf_title_cyclone: 'Cyclones',
	cf_title_river: 'Rivers and the Mithi',
	cf_title_quake: 'Earthquakes',
	cf_what_air: 'Modelled air quality (Open-Meteo, CAMS) at the MPCB and CPCB monitoring sites, banded with CPCB’s National AQI. Indicative: not the stations’ own readings.',
	cf_what_heat: 'Temperature and humidity at Santacruz and Colaba (Open-Meteo), the heat index, and IMD’s heatwave test run on the forecast.',
	cf_what_cyclone: 'Cyclones and floods around the Arabian Sea from GDACS: track, wind buffers and alert level. IMD’s RSMC bulletins are the official word.',
	cf_what_river: 'Water levels observed by the Central Water Commission at its river stations nearest Mumbai, against CWC’s warning levels, and how often the news mentions the Mithi rising.',
	cf_what_quake: 'USGS catalogue events within 500 km of Mumbai over the last year. Mumbai is in seismic zone 3.',
	cf_sources: 'Sources',
	cf_figures: 'Now',
	cf_proposal: 'Proposal',
	cf_no_proposal: 'No proposal now',
	cf_none_air: 'A health advisory is drafted when the air is moderate or worse now, or poor or worse within 48 hours.',
	cf_none_heat: 'A duty-shift advisory is drafted at a heat index of 41 °C, at 32 °C from April to June, or on an IMD heatwave day.',
	cf_none_cyclone: 'Pre-positioning is drafted when Mumbai is inside a wind buffer, a track comes within 300 km, or an orange or red alert is within 600 km.',
	cf_officer: 'A named officer decides. If no one decides, the current plan holds.',
	cf_loading: 'Loading…',
	cf_sheet_down: 'This feed did not answer. Nothing is shown as zero.',
	cf_f_worst: (site: unknown) => `Worst site: ${s(site)}`,
	cf_f_pm: (a: unknown, b: unknown) => `PM2.5 ${s(a)}, PM10 ${s(b)} µg/m³ (24-hour mean)`,
	cf_f_next: (band: unknown, aqi: unknown) => `Next 48 hours: ${s(band).toLowerCase()} (AQI ${s(aqi)})`,
	cf_f_grid: (cells: unknown, sites: unknown) => `The model's grid: ${s(cells)} cell(s) cover the ${s(sites)} sites, so neighbours often share a value`,
	cf_f_heat: (t: unknown, rh: unknown, app: unknown) => `Air ${s(t)} °C, humidity ${s(rh)}%, feels like ${s(app)} °C`,
	cf_f_peak: (v: unknown, at: unknown) => `Peak heat index in 48 hours: ${s(v)} °C at ${s(at)} IST`,
	cf_f_season_in: 'Pre-monsoon heat season (April to June)',
	cf_f_season_out: 'Outside the April to June heat season',
	cf_f_heatwave: (n: unknown) => `${s(n)} forecast day(s) meet IMD’s heatwave test`,
	cf_f_cyc: (name: unknown, km: unknown, dir: unknown) => `${s(name)} is ${s(km)} km ${s(dir)} of Mumbai`,
	cf_f_closest: (km: unknown) => `Its track comes no closer than ${s(km)} km`,
	cf_f_buffer: (kmh: unknown) => `Mumbai is inside its ${s(kmh)} km/h wind buffer`,
	cf_f_severity: (v: unknown) => `GDACS: ${s(v)}`,
	cf_f_river: (name: unknown, level: unknown, warn: unknown) => `${s(name)}: ${s(level)} m (warning ${s(warn)} m)`,
	cf_f_river_nowarn: (name: unknown, level: unknown) => `${s(name)}: ${s(level)} m`,
	cf_f_news: (n: unknown) => `${s(n)} news mention(s) of the Mithi rising in 72 hours`,
	cf_f_quake: (mag: unknown, place: unknown, km: unknown) => `M${s(mag)}, ${s(place)}, ${s(km)} km away`,
	cf_f_quake_count: (n: unknown) => `${s(n)} event(s) in the last year`,
	cf_f_observed: (band: unknown, aqi: unknown, site: unknown) => `Observed at the CPCB stations: ${s(band).toLowerCase()} (AQI ${s(aqi)}), worst at ${s(site)}`,
	cf_f_observed_sites: (n: unknown) => `Observed station readings at ${s(n)} site(s)`,
	cf_f_observed_none: 'Station measurements are not connected yet: the values above are modelled',
	cf_f_tide_port: (status: unknown) => `Port tide table: not readable (the port’s site answers with code ${s(status)})`,
	cf_f_tide_linked: (n: unknown) => `Port tide notices: ${s(n)} listed (linked, not parsed)`,
	cf_f_tide_noanswer: 'Port tide table: the port’s site did not answer',

	// ── the citizen page: Air today ──
	cf_pub_title: 'Air today',
	cf_pub_lead: 'Mumbai’s air from a model, in India’s National AQI bands.',
	cf_pub_head: (band: unknown, aqi: unknown) => `Mumbai’s air today is ${s(band).toLowerCase()} (AQI about ${s(aqi)}).`,
	cf_pub_adv_good: 'Enjoy the outdoors.',
	cf_pub_adv_satisfactory: 'People who are very sensitive may feel slight breathing discomfort.',
	cf_pub_adv_moderate: 'If you have asthma, lung or heart disease, keep long outdoor exertion short. Children and older people too.',
	cf_pub_adv_poor: 'Cut down long or heavy outdoor exertion. Keep windows shut in the evening smog hours.',
	cf_pub_adv_very_poor: 'Avoid outdoor exertion. Children, older people and the unwell should stay indoors.',
	cf_pub_adv_severe: 'Stay indoors if you can. Wear a well-fitted N95 mask if you must go out.',
	cf_pub_tag: 'Modelled',
	cf_pub_tag_tip: 'From an air-quality model, banded with the National AQI. Not a station reading.',
	cf_pub_down: 'Air quality is not available right now.',
	cf_pub_loading: 'Loading air quality…',
	cf_pub_worst: (site: unknown) => `Highest near ${s(site)}.`,
	cf_pub_tomorrow: (band: unknown) => `Next 48 hours: ${s(band).toLowerCase()}.`,
	cf_pub_source: 'Open-Meteo (CAMS) · CPCB National AQI bands',
	cf_pub_lead_obs: 'Mumbai’s air as the CPCB monitoring stations measured it, in India’s National AQI bands.',
	cf_pub_tag_obs: 'Measured',
	cf_pub_tag_obs_tip: 'The CPCB stations’ own 24-hour averages (via OpenAQ), banded with the National AQI. Two pollutants only, so indicative.',
	cf_pub_tomorrow_model: (band: unknown) => `Model outlook for the next 48 hours: ${s(band).toLowerCase()}.`,
	cf_pub_source_obs: 'CPCB stations via OpenAQ · CPCB National AQI bands. Outlook: Open-Meteo (CAMS)',
};

export type FeedsKey = keyof typeof en;

registerPack('en', en);

export const FEEDS_PACK_KEYS: readonly FeedsKey[] = Object.keys(en) as FeedsKey[];
export const FEEDS_PACKS: Record<string, FeedsPack> = { en };

/** Register one language chunk (lib/i18n/load.ts's landing site; additive, first registration wins). */
export function adopt(code: 'hi' | 'mr', pack: FeedsPack): void {
	FEEDS_PACKS[code] = pack;
	registerPack(code, pack);
}

if (process.env.NODE_ENV !== 'production' || import.meta.env.SSR !== false) {
	adopt('hi', (await import('./packs.feeds.hi')).hi);
	adopt('mr', (await import('./packs.feeds.mr')).mr);
} else {
	await langChunks('packs.feeds', (code) =>
		code === 'hi' ? import('./packs.feeds.hi').then((c) => adopt('hi', c.hi)) : import('./packs.feeds.mr').then((c) => adopt('mr', c.mr)),
	);
}
