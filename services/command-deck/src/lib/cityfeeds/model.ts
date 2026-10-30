/**
 * City feeds — the pure rules the chips, the sheet, the two map layers and the citizen card share (no store, no
 * DOM; tests/cityfeeds.unit.mjs drives them).
 *
 *   CHIP ROW     Air · Heat · Cyclone · River · Quake, in that order (the tide stays on the Rain · Tide chip).
 *   TONES        a band → one of five tones, and a tone → the EXISTING band-ladder tokens (colour only for meaning):
 *                good → --v-band-green, fair → --v-band-amber, poor → --v-band-red, severe → --v-band-black-fill with
 *                the --v-band-black-hairline ring, neutral → --v-map-marker. No new colour token.
 *   CHIP TEXT    value, band word and honest label of each chip, from the summary only (a missing value says
 *                "unavailable", never zero).
 *   LAYER ROWS   the Layers-sheet line of the air and cyclone layers ("No active cyclone" when there is none).
 *   CITIZEN      "Air today": the sentence a reader sees and hears, from the city's indicative National AQI band.
 */
import type { Chip, ChipId, FeedSummary } from './types';

export const CHIP_ROW: readonly ChipId[] = ['air', 'heat', 'cyclone', 'river', 'quake'];

export const CHIP_GLYPH: Readonly<Record<ChipId, string>> = Object.freeze({
	air: 'globe',
	heat: 'thermal',
	cyclone: 'target',
	river: 'wave',
	quake: 'signal',
	tide: 'timeline',
});

export type Tone = 'good' | 'fair' | 'poor' | 'severe' | 'neutral';

/** CPCB National AQI band order (services/cityfeeds/air.py NAQI_BANDS). */
export const NAQI_ORDER = ['good', 'satisfactory', 'moderate', 'poor', 'very_poor', 'severe'] as const;

const TONE_OF: Readonly<Record<ChipId, Readonly<Record<string, Tone>>>> = Object.freeze({
	air: { good: 'good', satisfactory: 'good', moderate: 'fair', poor: 'poor', very_poor: 'poor', severe: 'severe' },
	heat: { normal: 'good', caution: 'fair', extreme_caution: 'fair', danger: 'poor', extreme_danger: 'severe' },
	cyclone: { none: 'good', green: 'good', orange: 'fair', red: 'poor' },
	river: { normal: 'good', no_threshold: 'good', near_frl: 'fair', above_warning: 'poor', above_danger: 'severe' },
	quake: { quiet: 'good', recent: 'fair' },
	tide: {},
});

export function toneOf(id: ChipId, band: string | null | undefined): Tone {
	return (band && TONE_OF[id][band]) || 'neutral';
}

/** The CSS custom properties a tone paints with (existing semantic tokens only). */
export const TONE_TOKEN: Readonly<Record<Tone, { fill: string; ring: string | null }>> = Object.freeze({
	good: { fill: '--v-band-green', ring: null },
	fair: { fill: '--v-band-amber', ring: null },
	poor: { fill: '--v-band-red', ring: null },
	severe: { fill: '--v-band-black-fill', ring: '--v-band-black-hairline' },
	neutral: { fill: '--v-map-marker', ring: null },
});

/** The air layer's marker radius (px) per National AQI band: a worse band also draws larger (never colour alone). */
export function airRadius(band: string | null | undefined): number {
	const i = NAQI_ORDER.indexOf((band ?? '') as (typeof NAQI_ORDER)[number]);
	return i < 0 ? 7 : 8 + 2 * i;
}

type L = (key: string, ...args: unknown[]) => string;

export interface ChipVM {
	id: ChipId;
	value: string;
	band: string;
	tone: Tone;
	label: string;
	stale: boolean;
	proposal: boolean;
	available: boolean;
}

const num = (v: unknown): number | null => (typeof v === 'number' && Number.isFinite(v) ? v : null);

/** One chip's words from the summary — value, band word, tone and honest label. */
export function chipVM(id: ChipId, chip: Chip | undefined, L: L): ChipVM {
	const off = (): ChipVM => ({ id, value: L('cf_unavailable'), band: '', tone: 'neutral', label: 'UNAVAILABLE', stale: false, proposal: false, available: false });
	if (!chip || chip.label === 'UNAVAILABLE') return off();
	const d = chip.detail ?? {};
	const base = { id, tone: toneOf(id, chip.band), label: chip.label, stale: !!chip.stale, proposal: !!chip.proposal, available: true };
	switch (id) {
		case 'air': {
			const v = num(chip.value);
			if (v == null) return off();
			return { ...base, value: L('cf_air_val', Math.round(v)), band: L(`cf_naqi_${chip.band}`) };
		}
		case 'heat': {
			const v = num(chip.value);
			if (v == null) return off();
			return { ...base, value: L('cf_heat_val', Math.round(v)), band: L(`cf_hi_${chip.band}`) };
		}
		case 'cyclone': {
			if (!chip.value) return { ...base, value: L('cf_cyc_none'), band: '', tone: 'good' };
			return { ...base, value: L('cf_cyc_val', String(chip.value), num(d.distance_km) ?? '?'), band: L(`cf_alert_${chip.band}`) };
		}
		case 'river': {
			const v = num(chip.value);
			if (v == null) return off();
			return { ...base, value: v ? L('cf_river_val', v) : L('cf_river_none'), band: L(`cf_river_${chip.band}`) };
		}
		case 'quake': {
			const v = num(chip.value);
			if (v == null) return off();
			const last = (d.latest ?? null) as { mag?: number; distance_km?: number } | null;
			return { ...base, value: v ? L('cf_quake_val', v) : L('cf_quake_none'), band: L(`cf_quake_${chip.band}`) + (v && last?.mag ? ` · M${last.mag}` : '') };
		}
		default:
			return off();
	}
}

export function chipRow(summary: FeedSummary | null, L: L): ChipVM[] {
	return CHIP_ROW.map((id) => chipVM(id, summary?.chips?.[id], L));
}

/** The Layers-sheet line for the city-feed layers (pack keys of ./packs.feeds), or null for any other layer. */
export function feedLayerSub(
	id: string,
	row: { visible: boolean; count: number; error: string | null; detail?: Record<string, number> } | undefined,
	L: L,
): string | null {
	if (id !== 'air' && id !== 'cyclone') return null;
	if (!row) return L('cf_l_none');
	if (!row.visible) return L(id === 'air' ? 'cf_l_air_about' : 'cf_l_cyc_about');
	if (row.error) return L('cf_l_feed');
	if (id === 'air') {
		const worst = row.detail?.worst_band;
		const band = worst != null && worst >= 0 ? NAQI_ORDER[worst] : null;
		return row.count ? L('cf_l_air_sub', row.count, band ? L(`cf_naqi_${band}`) : '—') : L('cf_l_loading');
	}
	if (!row.count) return L('cf_l_cyc_none');
	return L('cf_l_cyc_sub', row.count, row.detail?.distance_km ?? '?');
}

/** The band of the WORST site among the stations, as an index into NAQI_ORDER (-1 when none has a value). */
export function worstBandIndex(bands: readonly (string | null | undefined)[]): number {
	let w = -1;
	for (const b of bands) w = Math.max(w, NAQI_ORDER.indexOf((b ?? '') as (typeof NAQI_ORDER)[number]));
	return w;
}

/** The citizen card's two sentences (the band and what to do), from the city's band; null without a band. */
export function airToday(band: string | null | undefined, aqi: number | null, L: L): { head: string; advice: string } | null {
	if (!band || aqi == null || !NAQI_ORDER.includes(band as (typeof NAQI_ORDER)[number])) return null;
	return { head: L('cf_pub_head', L(`cf_naqi_${band}`), Math.round(aqi)), advice: L(`cf_pub_adv_${band}`) };
}

/** One source line in the sheet: who publishes it and where. */
export interface SourceRow {
	name: string;
	url: string;
}

/** The sources behind each chip (proper names; the service's own source lines are added at run time). */
export const CHIP_SOURCES: Readonly<Record<ChipId, readonly SourceRow[]>> = Object.freeze({
	air: [
		{ name: 'Open-Meteo air-quality API (CAMS, ECMWF Copernicus)', url: 'https://open-meteo.com/en/docs/air-quality-api' },
		{ name: 'CPCB National Air Quality Index (CUPS/82/2014-15)', url: 'https://cpcb.nic.in/National-Air-Quality-Index/' },
		{ name: 'WBPCB monitoring sites', url: 'https://www.wbpcb.gov.in/' },
	],
	heat: [
		{ name: 'Open-Meteo forecast API', url: 'https://open-meteo.com/en/docs' },
		{ name: 'IMD: FAQ on heat wave (plains criteria)', url: 'https://internal.imd.gov.in/section/nhac/dynamic/FAQ_heat_wave.pdf' },
		{ name: 'NWS: the heat index equation', url: 'https://www.wpc.ncep.noaa.gov/html/heatindex_equation.shtml' },
		{ name: 'NDMA heat wave guidelines (2019)', url: 'https://ndma.gov.in/sites/default/files/PDF/Guidelines/heatwaveguidelines.pdf' },
	],
	cyclone: [
		{ name: 'GDACS (European Commission JRC and UN OCHA)', url: 'https://www.gdacs.org/' },
		{ name: 'IMD RSMC New Delhi (official bulletins)', url: 'https://rsmcnewdelhi.imd.gov.in/' },
	],
	river: [
		{ name: 'Central Water Commission flood forecasting', url: 'https://ffs.india-water.gov.in/' },
		{ name: 'Damodar Valley Corporation (release notes)', url: 'https://www.dvc.gov.in/' },
	],
	quake: [{ name: 'USGS earthquake catalogue (FDSN)', url: 'https://earthquake.usgs.gov/fdsnws/event/1/' }],
	tide: [{ name: 'Sajag hydro tide model (Apollo Bunder, Mumbai harbour)', url: '' }],
});

/** The wind buffer (km/h) the city centre lies inside: the service's city-neutral field, else its older name. */
export function inWindBufferKmh(nr: { city_in_wind_buffer_kmh?: number | null; kolkata_in_wind_buffer_kmh?: number | null } | null | undefined): number | null {
	const v = nr?.city_in_wind_buffer_kmh ?? nr?.kolkata_in_wind_buffer_kmh ?? null;
	return typeof v === 'number' && Number.isFinite(v) && v > 0 ? v : null;
}

const n1 = (v: unknown, d = 1): string => (typeof v === 'number' && Number.isFinite(v) ? String(Number(v.toFixed(d))) : '—');

/**
 * The sheet's "Now" lines for a chip, from its detailed answer (GET /feeds/<id>) — only numbers the service gave,
 * never a guess. `lang` picks the Marathi site and band names where the service carries them.
 */
export function sheetFigures(id: ChipId, view: Record<string, unknown> | null, L: L, lang: string): string[] {
	if (!view) return [];
	const out: string[] = [];
	const bandName = (o: { band_en?: string; band_mr?: string; band_hi?: string; band?: string } | null | undefined) =>
		o ? (o.band ? L(`cf_naqi_${o.band}`) : (lang === 'mr' ? o.band_mr : lang === 'hi' ? o.band_hi : o.band_en) ?? '') : '';
	if (id === 'air') {
		const c = view.city as { aqi: number; band: string; worst_site_name: string; worst_site_mr: string; pm25_24h: number | null; pm10_24h: number | null } | null;
		if (c) {
			out.push(L('cf_f_worst', lang === 'mr' ? c.worst_site_mr : c.worst_site_name));
			out.push(L('cf_f_pm', n1(c.pm25_24h), n1(c.pm10_24h)));
		}
		const nx = (view.next_48h_worst as { naqi?: { aqi: number; band: string } } | null)?.naqi;
		if (nx) out.push(L('cf_f_next', bandName(nx), nx.aqi));
		const sites = Array.isArray(view.stations) ? view.stations.length : 0;
		if (typeof view.grid_cells === 'number' && sites) out.push(L('cf_f_grid', view.grid_cells, sites));
		// OBSERVED beside MODELLED: the stations' own CPCB averages when a keyed provider answers, else say so
		const ob = view.observed as { label?: string; sites_observed?: number; city_naqi?: { aqi: number; band: string; site: string } | null } | undefined;
		if (ob?.city_naqi) {
			const st = (view.stations as Array<{ id: string; name: string; name_mr: string }> | undefined)?.find((x) => x.id === ob.city_naqi?.site);
			out.push(L('cf_f_observed', bandName(ob.city_naqi), ob.city_naqi.aqi, st ? (lang === 'mr' ? st.name_mr : st.name) : ob.city_naqi.site));
		} else if (ob && (ob.sites_observed ?? 0) > 0) out.push(L('cf_f_observed_sites', ob.sites_observed));
		else if (ob) out.push(L('cf_f_observed_none'));
	} else if (id === 'heat') {
		const c = view.city as { temp: number; rh: number; apparent: number } | null;
		if (c) out.push(L('cf_f_heat', n1(c.temp), n1(c.rh, 0), n1(c.apparent)));
		const pk = view.peak_48h as { heat_index: number; at_ist: string } | null;
		if (pk) out.push(L('cf_f_peak', n1(pk.heat_index), String(pk.at_ist ?? '').slice(11, 16)));
		out.push(L(view.in_season ? 'cf_f_season_in' : 'cf_f_season_out'));
		const hw = Array.isArray(view.imd_heatwave_days) ? view.imd_heatwave_days.length : 0;
		if (hw) out.push(L('cf_f_heatwave', hw));
	} else if (id === 'cyclone') {
		const nr = view.nearest as { name: string; distance_km: number; bearing: string; closest_approach: { distance_km: number } | null; city_in_wind_buffer_kmh?: number | null; kolkata_in_wind_buffer_kmh?: number | null; severity: string | null } | null;
		if (!nr) out.push(L('cf_cyc_none'));
		else {
			out.push(L('cf_f_cyc', nr.name, nr.distance_km, nr.bearing));
			if (nr.closest_approach) out.push(L('cf_f_closest', nr.closest_approach.distance_km));
			const buffer = inWindBufferKmh(nr);
			if (buffer) out.push(L('cf_f_buffer', buffer));
			if (nr.severity) out.push(L('cf_f_severity', nr.severity));
		}
	} else if (id === 'river') {
		for (const s of (view.stations as Array<{ name?: string; level_m?: number | null; warning_m?: number | null }> | undefined) ?? []) {
			if (s.level_m == null || !s.name) continue;
			out.push(s.warning_m != null ? L('cf_f_river', s.name, n1(s.level_m, 2), n1(s.warning_m, 2)) : L('cf_f_river_nowarn', s.name, n1(s.level_m, 2)));
		}
		const news = (view.news ?? view.dvc_news) as { mentions?: number | null } | null;
		if (news && typeof news.mentions === 'number') out.push(L('cf_f_news', news.mentions));
	} else if (id === 'quake') {
		const last = view.latest as { mag: number; place: string; distance_km: number } | null;
		if (last) out.push(L('cf_f_quake', last.mag, last.place, last.distance_km));
		if (typeof view.count_365d === 'number') out.push(L('cf_f_quake_count', view.count_365d));
	} else if (id === 'tide') {
		// the port's published table, as the port answered (read live over the pinned connection)
		const pub = view.published as { label?: string; status?: number | null; notices?: unknown[] } | undefined;
		if (pub?.label === 'LINKED') out.push(L('cf_f_tide_linked', Array.isArray(pub.notices) ? pub.notices.length : 0));
		else if (pub && typeof pub.status === 'number') out.push(L('cf_f_tide_port', pub.status));
		else if (pub) out.push(L('cf_f_tide_noanswer'));
	}
	return out;
}

/**
 * What the Layers-sheet row of a city-feed layer adds from the shared summary (the canvas's layer rows carry counts,
 * not details): the air layer's worst band, the nearest cyclone's distance. Undefined for any other layer.
 */
export function feedRowDetail(id: string, summary: FeedSummary | null): Record<string, number> | undefined {
	if (id === 'air') {
		const i = NAQI_ORDER.indexOf((summary?.chips?.air?.band ?? '') as (typeof NAQI_ORDER)[number]);
		return i >= 0 ? { worst_band: i } : undefined;
	}
	if (id === 'cyclone') {
		const km = summary?.chips?.cyclone?.detail?.distance_km;
		return typeof km === 'number' ? { distance_km: km } : undefined;
	}
	return undefined;
}
