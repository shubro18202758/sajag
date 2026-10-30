/**
 * The console's city, read from the City Pack (cities/<id>/, generated into city.generated.ts by
 * scripts/gen_deck_city.mjs). Every map view, camera, plate sample, place name and agency name the deck
 * shows comes from here, so a new city is a new pack and a regenerated module, not an edit across the deck.
 *
 *   cityName(lang)            "Mumbai" · "मुंबई" · "मुंबई" (EN fallback for any other code)
 *   CITY_BBOX / NETWORK_BBOX  the boot view and the road network's extent ({minLon, minLat, maxLon, maxLat})
 *   CITY_CORE_BBOX            the central district the base-map pictures frame
 *   CITY_CAMERAS              the 2D and photoreal-3D homes (target, range m, heading °, pitch °)
 *   CITY_VIEWS / cityView(q)  named photoreal obliques (Sea Link, Marine Drive, BKC, Dadar, Andheri …)
 *   landmark(id) / landmarkName(id, lang)   canonical places (landmarks.json ids and spellings)
 *   PLATE / formatPlate / isCityPlate       the pack's registration-mark rule (display only — the mask is
 *                                           workspace/mask.ts and covers every state code)
 */

import { CITY_PACK } from './city.generated';

export type CityLang = 'en' | 'mr' | 'hi';
export type Names = { readonly en: string; readonly mr: string; readonly hi: string };
export type LonLatBox = { readonly minLon: number; readonly minLat: number; readonly maxLon: number; readonly maxLat: number };
export type CityCamera = { readonly lon: number; readonly lat: number; readonly range: number; readonly headingDeg: number; readonly pitchDeg: number };
export type Landmark = (typeof CITY_PACK.landmarks)[number];
export type LandmarkId = Landmark['id'];
export type Agency = (typeof CITY_PACK.agencies)[number];

export const CITY = CITY_PACK;
export const CITY_ID: string = CITY_PACK.id;
export const CITY_TIMEZONE: string = CITY_PACK.timezone;

/** A name in the console's language: mr and hi when asked, else English. */
export function pick(n: Names, lang: string | null | undefined): string {
	return lang === 'mr' ? n.mr : lang === 'hi' ? n.hi : n.en;
}

export const cityName = (lang?: string | null): string => pick(CITY_PACK.name, lang);
export const stateName = (lang?: string | null): string => pick(CITY_PACK.state, lang);
export const regionName = (lang?: string | null): string => pick(CITY_PACK.region, lang);
export const riverName = (lang?: string | null): string | null => (CITY_PACK.river ? pick(CITY_PACK.river, lang) : null);

/** The city centre (city.json `centre`). */
export const CITY_CENTRE: { readonly lon: number; readonly lat: number } = { lon: CITY_PACK.centre.lon, lat: CITY_PACK.centre.lat };

/**
 * The city box the canvas boots over and keeps an idle camera inside (city.json `bbox`). The pack's box is
 * the road network's extent too, so the two are one box; NETWORK_BBOX stays a name of its own because the
 * geometry reads (waypoints, anchors, spine names) mean the network, not the view.
 */
export const CITY_BBOX: LonLatBox = CITY_PACK.bbox;
export const NETWORK_BBOX: LonLatBox = CITY_PACK.bbox;
/** The central district (around the 3D home) the base-map pictures frame. */
export const CITY_CORE_BBOX: LonLatBox = CITY_PACK.coreBbox;

/** [west, south, east, north] — the order MapThumb and the tile maths take. */
export function bboxArray(b: LonLatBox): [number, number, number, number] {
	return [b.minLon, b.minLat, b.maxLon, b.maxLat];
}

/** True when lon/lat lies in `box` grown by `marginDeg` on every side. */
export function inBox(lon: number, lat: number, box: LonLatBox = CITY_BBOX, marginDeg = 0): boolean {
	return lon >= box.minLon - marginDeg && lon <= box.maxLon + marginDeg && lat >= box.minLat - marginDeg && lat <= box.maxLat + marginDeg;
}

/**
 * The default cameras. home3d: an oblique the pack names by two landmarks (for Mumbai, from off Haji Ali north
 * along the Worli seaface to the Bandra–Worli Sea Link); home2d: the city centre (Dadar / Matunga) from higher up,
 * north up, the island city and the near suburbs in view.
 */
export const CITY_CAMERAS: { readonly home2d: CityCamera; readonly home3d: CityCamera } = CITY_PACK.cameras;

/** A named photoreal oblique (city pack `views`): a look from one landmark toward another. */
export type CityView = CityCamera & { readonly id: string; readonly from: string; readonly toward: string };
export const CITY_VIEWS: readonly CityView[] = (CITY_PACK as { views?: readonly CityView[] }).views ?? [];

const VIEW_FOLD = (s: string) => s.toLowerCase().normalize('NFKD').replace(/[^a-z0-9\u0900-\u097f]+/g, ' ').trim();

/**
 * The named view a typed place resolves to ("sea link", "Bandra–Worli Sea Link", "marine drive", "BKC"), by its id,
 * or its landmark's name in any language (whole name or its first words); null when none matches.
 */
export function cityView(query: string | null | undefined): CityView | null {
	const q = VIEW_FOLD(query ?? '');
	if (!q) return null;
	for (const v of CITY_VIEWS) {
		if (VIEW_FOLD(v.id.replace(/_/g, ' ')) === q) return v;
		const l = CITY_PACK.landmarks.find((x) => x.id === v.id);
		if (!l) continue;
		for (const n of [l.en, l.mr, l.hi]) {
			const f = VIEW_FOLD(n);
			if (f === q || f.startsWith(`${q} `) || f.replace(/\s*\(.*$/, '') === q || f.includes(` ${q}`) && q.length >= 6) return v;
		}
	}
	return null;
}

const LANDMARKS_BY_ID: ReadonlyMap<string, Landmark> = new Map(CITY_PACK.landmarks.map((l) => [l.id, l]));
export const LANDMARKS: readonly Landmark[] = CITY_PACK.landmarks;

export function landmark(id: string): Landmark | null {
	return LANDMARKS_BY_ID.get(id) ?? null;
}

/** A landmark's canonical name in `lang` (the id itself when the pack does not hold it). */
export function landmarkName(id: string, lang?: string | null): string {
	const l = LANDMARKS_BY_ID.get(id);
	return l ? pick(l, lang) : id;
}

/** [lon, lat] of a landmark (null when the pack does not hold it). */
export function landmarkLonLat(id: string): [number, number] | null {
	const l = LANDMARKS_BY_ID.get(id);
	return l ? [l.lon, l.lat] : null;
}

export const AGENCIES: readonly Agency[] = CITY_PACK.agencies;
export function agencyName(id: string, lang?: string | null): string | null {
	const a = CITY_PACK.agencies.find((x) => x.id === id);
	return a ? pick(a, lang) : null;
}

/**
 * Initialisms the city's road and place names carry ("WEH", "LBS Marg", "BKC", "KEM Hospital", "Dadar TT Circle"):
 * the console's sentence-casing (workspace/display.ts decap) keeps them in capitals. City vocabulary only — the
 * product's acronym allowlist is workspace/vocabulary.ts ACRONYMS.
 */
export const CITY_ACRONYMS: ReadonlySet<string> = new Set(CITY_PACK.acronyms);

/**
 * Emergency numbers (city.json `emergency`): unified 112, police, ambulance (108), fire, and the civic disaster
 * control line when the city has one (Mumbai: BMC 1916).
 */
export const EMERGENCY: {
	readonly unified: string;
	readonly police: string;
	readonly ambulance: string;
	readonly fire: string;
	readonly civic_disaster?: string;
} = CITY_PACK.emergency;

/**
 * The pack's registration-mark rule. `regex` is the pack's own (state code, 2-digit RTO number, a 1–3 letter
 * series, up to 4 digits; a space or a dash between parts). DISPLAY ONLY: masking is workspace/mask.ts,
 * which masks a mark of every Indian state code, so a vehicle from another state is hidden as well.
 */
export const PLATE = {
	stateCode: CITY_PACK.plates.stateCode,
	format: CITY_PACK.plates.format,
	regex: new RegExp(CITY_PACK.plates.regex),
	/** RTO numbers samples and fixtures use (plausible codes; the console never infers an office). */
	sampleCodes: CITY_PACK.plates.sampleCodes as readonly string[],
	/** "MH 02 AB 1234" — the pack's format, as the console writes a sample. */
	example: CITY_PACK.plates.example,
} as const;

const PLATE_PARTS = /^([A-Z]{2})[ -]?(\d{1,2})[ -]?([A-Z]{1,3})?[ -]?(\d{1,4})$/;

/** True when `raw` (any case, spaces or dashes between parts) is a mark of this city's state. */
export function isCityPlate(raw: string | null | undefined): boolean {
	if (!raw) return false;
	return PLATE.regex.test(raw.trim().toUpperCase());
}

/**
 * A raw mark in the pack's written form: "mh02ab1234" → "MH 02 AB 1234" (state, zero-padded RTO number,
 * series, number). Text that is not a whole mark comes back trimmed and unchanged. Never applied to a
 * masked mark: format first, then mask (workspace/mask.ts keeps the spacing it is given).
 */
export function formatPlate(raw: string | null | undefined): string {
	const s = (raw ?? '').trim();
	const m = PLATE_PARTS.exec(s.toUpperCase());
	if (!m) return s;
	const [, state, rto, series, num] = m;
	return [state, rto.padStart(2, '0'), series, num].filter(Boolean).join(' ');
}

/** A sample mark for fixtures, the design gallery and tests: `${state} ${code} ${series} ${num}`. */
export function samplePlate(code: string, series: string, num: string): string {
	return `${PLATE.stateCode} ${code} ${series} ${num}`;
}
