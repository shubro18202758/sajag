/**
 * What the landing page (/welcome) shows, as data — the page is static content and static assets only: no API call,
 * no store, no operator code. tests/welcome.unit.mjs reads this module (the links, the pictures, the captions), so a
 * change here is a change the test sees.
 *
 * Pictures, each with its honest label:
 *   - reference photos of Mumbai (static/photos, Wikimedia Commons): always "Reference photo · not live" + credit,
 *     drawn by Cover on the picture itself; chosen by PLACE (landmarks.json ids), so the page follows the photo set
 *     on file instead of naming files;
 *   - key art and the Sea Link scenes (static/artwork): original illustrations, captioned "Illustration";
 *   - agency and source marks (static/logos): as-is, with the owners' credit line;
 *   - one console screenshot in the hero window, taken on the city's network with exercise (emulated) data and every
 *     plate masked (static/landing/NOTICE.md), captioned "Console screenshot · exercise data" on the picture.
 */
import { PHOTOS, type PlacePhoto } from '../media/photos';
import { markFor, type Mark } from '../media/logos';
import { AGENCIES, CITY_BBOX, inBox } from '$lib/city';

/** Where each door leads. The console is an operator document (its own CSP), so links into it reload. */
export const HREF = {
	console: '/',
	analyst: '/analyst',
	citizen: '/citizen',
	driver: '/driver',
	source: 'https://github.com/shubro18202758/sajag',
	photoCredits: '/photos/NOTICE.md',
} as const;

/** The operator routes: a link to one of them must load a new document (data-sveltekit-reload). */
export const OPERATOR_HREFS: readonly string[] = [HREF.console, HREF.analyst];

/** A console screenshot (static/landing/console-<file>-{800,1600}.webp), the honest caption is the page's. */
export interface Shot {
	key: 'decide';
	src: string;
	srcset: string;
	w: number;
	h: number;
	alt: string;
}

function shot(key: Shot['key'], file: string, w: number, h: number, alt: string): Shot {
	return { key, src: `/landing/${file}-1600.webp`, srcset: `/landing/${file}-800.webp 800w, /landing/${file}-1600.webp 1600w`, w, h, alt };
}

export const SHOTS: Readonly<Record<Shot['key'], Shot>> = {
	decide: shot('decide', 'console-decide', 1600, 1000, 'v3l_shot_alt_decide'),
};

/** The console shown in the hero window: Decide, one emulated request waiting for a named officer. */
export const HERO_SHOT: Shot['key'] = 'decide';

/**
 * The pictures by place, best first (landmarks.json ids, or a subject: taxi, bus, local train …). The hero: the
 * Bandra–Worli Sea Link or Marine Drive at night; the closing band: the seafront at dusk; the strip: the places and
 * the vehicles of the city. A photo at night is preferred for the hero (its slug or title says so).
 */
export const HERO_PLACES = ['sea_link', 'marine_drive', 'gateway', 'csmt'] as const;
/**
 * The brand's curated choice, used first when the photo set holds it (the place rules below are the fallback for a set
 * without these slugs): the Bandra–Worli Sea Link lit at night, Marine Drive (the Queen's Necklace) to close, and the
 * strip — CSMT, the Gateway of India, a kaali-peeli taxi, a BEST double-decker, a suburban local.
 */
export const HERO_PHOTO_SLUG = 'sea-link-night';
export const END_PHOTO_SLUG = 'marine-drive';
export const CITY_PHOTO_SLUGS = ['csmt', 'gateway-of-india', 'kaali-peeli-taxi', 'best-double-decker', 'local-train'] as const;
export const END_PLACES = ['marine_drive', 'girgaon_chowpatty', 'juhu_beach', 'gateway', 'sea_link', 'worli_naka'] as const;
export const CITY_PLACES = ['csmt', 'gateway', 'taxi', 'bus', 'best', 'local_train', 'train', 'wankhede', 'lalbaugcha_raja', 'pandal', 'girgaon_chowpatty', 'dadar', 'bkc', 'atal_setu'] as const;

/**
 * The photos taken in the city (a photo of the city's own box; a subject photo carries the city centroid). A deck
 * whose photo set is not the city's yet still renders (every photo keeps its own title and credit, never relabelled);
 * tests/welcome.unit.mjs fails until the set is the city's.
 */
function cityOnly(): PlacePhoto[] {
	const here = PHOTOS.filter((p) => inBox(p.lon, p.lat, CITY_BBOX, 0.05));
	return here.length >= 3 ? here : [...PHOTOS];
}

const isNight = (p: PlacePhoto) => /night|dusk|lit\b/i.test(`${p.slug} ${p.title}`);

function pick(places: readonly string[], skip: ReadonlySet<string>, prefer?: (p: PlacePhoto) => boolean): PlacePhoto | null {
	const pool = cityOnly().filter((p) => !skip.has(p.slug));
	for (const place of places) {
		const here = pool.filter((p) => p.place === place);
		const best = (prefer && here.find(prefer)) || here[0];
		if (best) return best;
	}
	return (prefer && pool.find((p) => p.near && prefer(p))) || pool.find((p) => p.near) || pool[0] || null;
}

/** A curated slug when the set holds it (and it is the city's), else null. */
function curated(slug: string, skip: ReadonlySet<string> = new Set()): PlacePhoto | null {
	const p = PHOTOS.find((x) => x.slug === slug) ?? null;
	return p && !skip.has(p.slug) && cityOnly().includes(p) ? p : null;
}

export function heroPhoto(): PlacePhoto {
	const p = curated(HERO_PHOTO_SLUG) ?? pick(HERO_PLACES, new Set(), isNight);
	if (!p) throw new Error('landing: no reference photo of the city on file');
	return p;
}

export function endPhoto(): PlacePhoto {
	const skip = new Set([heroPhoto().slug]);
	const p = curated(END_PHOTO_SLUG, skip) ?? pick(END_PLACES, skip, (x) => /dusk|sunset|evening/i.test(`${x.slug} ${x.title}`));
	if (!p) throw new Error('landing: no second reference photo of the city on file');
	return p;
}

/** The city strip under the hero: five reference photos of the places Sajag watches over (each with its label and credit). */
export function cityPhotos(n = 5): PlacePhoto[] {
	const used = new Set([heroPhoto().slug, endPhoto().slug]);
	const out: PlacePhoto[] = [];
	for (const slug of CITY_PHOTO_SLUGS) {
		if (out.length >= n) break;
		const p = curated(slug, used);
		if (p) {
			out.push(p);
			used.add(p.slug);
		}
	}
	for (const place of CITY_PLACES) {
		if (out.length >= n) break;
		const p = cityOnly().find((x) => x.place === place && !used.has(x.slug));
		if (p) {
			out.push(p);
			used.add(p.slug);
		}
	}
	for (const p of cityOnly()) {
		if (out.length >= n) break;
		if (!used.has(p.slug)) {
			out.push(p);
			used.add(p.slug);
		}
	}
	return out;
}

/**
 * TODO-IMPACT — the three modelled figures for Mumbai. They come from IMPACT_REPORT.md once the Mumbai impact run is
 * in; until then each `value` is null and the page shows the metric with "Being modelled" in place of a number. Never
 * fill one with a figure that is not in the report (the report keeps each figure's assumptions); the earlier city's
 * figures do not carry over.
 */
export const TODO_IMPACT = {
	pending: true,
	source: 'IMPACT_REPORT.md (Mumbai run pending; MODELLED when in)',
	figures: [
		{ key: 'hold', value: null as string | null },
		{ key: 'delay', value: null as string | null },
		{ key: 'golden', value: null as string | null },
	],
};

/**
 * How it works: three steps, each with the key art of its moment in Mumbai — a monsoon burst at high tide (see),
 * a flooded subway and its diversion (decide), the advisory going out (act).
 */
export const STEPS = [
	{ n: 1, key: 'see', art: '/artwork/events/weather.svg' },
	{ n: 2, key: 'decide', art: '/artwork/events/flooding.svg' },
	{ n: 3, key: 'act', art: '/artwork/events/advisory.svg' },
] as const satisfies readonly { n: number; key: string; art: string }[];

/** For everyone: four seats, each with the key art of its work and the door it uses. */
export const AUDIENCES = [
	{ key: 'officer', art: '/artwork/events/protected_movement.svg', href: HREF.console, seat: 'console' },
	{ key: 'analyst', art: '/artwork/scenes/night.svg', href: HREF.analyst, seat: 'console' },
	{ key: 'citizen', art: '/artwork/events/cyclone.svg', href: HREF.citizen, seat: 'public' },
	{ key: 'driver', art: '/artwork/events/green_corridor.svg', href: HREF.driver, seat: 'public' },
] as const satisfies readonly { key: string; art: string; href: string; seat: 'console' | 'public' }[];

/** The principles, each with the glyph that signs it (`sign`; one glyph per noun, never a person). */
export const PRINCIPLES = [
	{ key: 'vehicles', sign: 'car' },
	{ key: 'masked', sign: 'lock' },
	{ key: 'officer', sign: 'badge' },
	{ key: 'holds', sign: 'clock' },
	{ key: 'victim', sign: 'shield' },
	{ key: 'labels', sign: 'verified' },
] as const satisfies readonly { key: string; sign: string }[];

/** Built on: four foundations, each with the marks of its sources (or the glyph that signs it). */
export const BUILT = [
	{ key: 'roads', marks: ['openstreetmap', 'copernicus'], sign: null },
	{ key: 'city', marks: ['cesium'], sign: null },
	{ key: 'alerts', marks: ['imd', 'ndma_sachet', 'open_meteo'], sign: null },
	{ key: 'ai', marks: [], sign: 'spark' },
] as const satisfies readonly { key: string; marks: readonly string[]; sign: string | null }[];

/** The data sources the row always ends with. */
export const SOURCE_MARKS = ['openstreetmap', 'open_meteo', 'copernicus'] as const;

/** The brand's curated agency row (city.json agency ids), in its order. */
export const MARK_ROW_AGENCIES = ['mumbai_police', 'bmc', 'mmrda', 'best', 'cr', 'metro', 'msrdc', 'port', 'ndma', 'imd'] as const;

/**
 * The agencies and sources whose marks the row shows (static/logos; city.json agency ids, the owners' credit line sits
 * under it): the curated row's agencies that the pack holds and that have a mark on file, then the data sources. An
 * agency with no mark keeps its generic badge elsewhere and is left out of the row.
 */
export const MARK_ROW: readonly string[] = [
	...MARK_ROW_AGENCIES.filter((id) => AGENCIES.some((a) => a.id === id) && markFor(id)?.key === id),
	...SOURCE_MARKS,
];

export function marks(keys: readonly string[]): Mark[] {
	return keys.map((k) => markFor(k)).filter((m): m is Mark => m !== null);
}
