/**
 * Reference photographs of real places (static/photos; credits and licences in static/photos/NOTICE.md). A photo is
 * ALWAYS shown with "Reference photo · not live" and its credit, never where a live camera or a map is expected, and
 * never as the current situation: it shows what the place looks like, not what is happening there.
 */
import { PHOTO_ROWS } from './photos.data';

export interface PlacePhoto {
	slug: string;
	title: string;
	/** The curated place key: a landmarks.json id (sea_link, csmt, marine_drive …) or a subject (taxi, local_train, visarjan …). */
	place: string;
	lat: number;
	lon: number;
	/** The coordinates are the photo's own place (false: the city's centroid; never matched by distance). */
	near: boolean;
	author: string;
	license: string;
	licenseUrl: string;
	/** The Wikimedia Commons file page. */
	source: string;
	/** "Photo: <author> · <licence> · Wikimedia Commons". */
	credit: string;
}

export const PHOTOS: readonly PlacePhoto[] = PHOTO_ROWS;
const BY_SLUG = new Map(PHOTOS.map((p) => [p.slug, p]));

/**
 * Slugs of the earlier city's set, kept resolvable until every caller names a Mumbai photo: each maps to the Mumbai
 * photo that plays the same part (the landing's hero bridge at night, its closing waterfront, its city strip). Never a
 * claim that the two places look alike; a caller that names a place uses photoForPlace / photoForText instead.
 */
const LEGACY_SLUG: Readonly<Record<string, string>> = {
	'howrah-bridge-night': 'sea-link-night',
	'howrah-bridge-day': 'sea-link-day',
	'hooghly-dusk': 'marine-drive',
	'victoria-memorial': 'csmt',
	'vidyasagar-setu': 'atal-setu',
	'yellow-taxis': 'kaali-peeli-taxi',
	'heritage-tram': 'best-double-decker',
	'kumartuli-idols': 'ganesh-visarjan',
	'durga-puja-pandal': 'ganesh-visarjan',
	'metro-train': 'mumbai-metro',
};

export function photoBySlug(slug: string | null | undefined): PlacePhoto | null {
	if (!slug) return null;
	return BY_SLUG.get(slug) ?? BY_SLUG.get(LEGACY_SLUG[slug] ?? '') ?? null;
}

export function photoSrc(p: PlacePhoto, w: 640 | 1600 = 640): string {
	return `/photos/${p.slug}-${w}.webp`;
}

export function photoSrcset(p: PlacePhoto): string {
	return `${photoSrc(p, 640)} 640w, ${photoSrc(p, 1600)} 1600w`;
}

/** A place photographed more than once by time of day (the Sea Link by day and at night): the one that matches the IST hour. */
function variant(list: readonly PlacePhoto[], hour: number | null): PlacePhoto | null {
	if (!list.length) return null;
	if (hour == null || list.length === 1) return list[0];
	const want = hour >= 7 && hour < 17 ? ['day', 'dusk'] : hour >= 17 && hour < 19 ? ['dusk', 'night'] : ['night', 'dusk'];
	for (const w of want) {
		const hit = list.find((p) => p.slug.endsWith(`-${w}`));
		if (hit) return hit;
	}
	return list[0];
}

/** A photo of a curated place key. */
export function photoForPlace(place: string | null | undefined, hour: number | null = null): PlacePhoto | null {
	if (!place) return null;
	return variant(
		PHOTOS.filter((p) => p.place === place),
		hour,
	);
}

const R = 6_371_000;
function metres(aLon: number, aLat: number, bLon: number, bLat: number): number {
	const r = Math.PI / 180;
	const dLat = (bLat - aLat) * r;
	const dLon = (bLon - aLon) * r;
	const h = Math.sin(dLat / 2) ** 2 + Math.cos(aLat * r) * Math.cos(bLat * r) * Math.sin(dLon / 2) ** 2;
	return 2 * R * Math.asin(Math.min(1, Math.sqrt(h)));
}

/** The nearest photographed place within `maxM` metres of a point (only photos whose coordinates are their own). */
export function photoNear(lon: number | null | undefined, lat: number | null | undefined, maxM = 900, hour: number | null = null): PlacePhoto | null {
	if (lon == null || lat == null || !Number.isFinite(lon) || !Number.isFinite(lat)) return null;
	let best: PlacePhoto | null = null;
	let bestD = Infinity;
	for (const p of PHOTOS) {
		if (!p.near) continue;
		const d = metres(lon, lat, p.lon, p.lat);
		if (d < bestD) {
			best = p;
			bestD = d;
		}
	}
	if (!best || bestD > maxM) return null;
	const place = best.place;
	return variant(PHOTOS.filter((p) => p.place === place && p.near), hour) ?? best;
}

/** Place names in a title or a road name that have a photograph (word-bounded, case-insensitive). */
const WORDS: readonly [RegExp, string][] = [
	// Named places first (EN, then the Marathi / Hindi spellings of cities/mumbai/landmarks.json); visarjan before the
	// beaches and Dadar ("Dadar Chowpatty visarjan" is the procession, not the station); generic subjects last.
	[/\batal\s+setu\b|\bmthl\b|\btrans[\s-]?harbou?r\s+link\b|\bsewri[\s–-]+nhava(\s+sheva)?\b|अटल सेतू|अटल सेतु/i, 'atal_setu'],
	[/\bsea[\s-]?link\b|\bbandra[\s–-]+worli\b|\bbwsl\b|वांद्रे[\s–-]*वरळी|सागरी सेतू|बांद्रा[\s–-]*वर्ली|सी\s?लिंक/i, 'sea_link'],
	[/\bcs(m)?t\b|\bchhatrapati\s+shivaji(\s+maharaj)?\s+terminus\b|\bvictoria\s+terminus\b|\bvt\b|छत्रपत[ीि] शिवाजी( महाराज)? टर्मिनस|सीएसएमटी/i, 'csmt'],
	[/\bmarine\s+drive\b|\bqueen'?s\s+necklace\b|मरीन ड्राइव|मरीन ड्राईव|क्वीन्स नेकलेस/i, 'marine_drive'],
	[/\bgateway\s+of\s+india\b|गेटवे ऑफ इंडिया/i, 'gateway'],
	[/\bbkc\b|\bbandra[\s-]+kurla\s+complex\b|वांद्रे[\s-]*कुर्ला संकुल|बांद्रा[\s-]*कुर्ला कॉम्प्लेक्स|बीकेसी/i, 'bkc'],
	[/\bworli\s+sea\s?face\b|वरळी सी ?फेस|वर्ली सी ?फेस/i, 'worli_sea_face'],
	[/\bhaji\s+ali\b|हाजी अली/i, 'haji_ali'],
	[/\bwankhede\b|वानखेडे|वानखेड़े/i, 'wankhede'],
	[/\b(visarjan|immersion|anant\s+chaturdashi|ganeshotsav|ganpati\s+procession|lalbaugcha\s+raja)\b|विसर्जन|अनंत चतुर्दशी|गणेशोत्सव|लालबागचा राजा/i, 'visarjan'],
	[/\bgirga(on|um)\s+chowpatty\b|गिरगाव चौपाटी|गिरगांव चौपाटी/i, 'girgaon_chowpatty'],
	[/\bjuhu\b|जुहू/i, 'juhu_beach'],
	[/\bdadar\b(?!\s+(chowpatty|beach))|दादर(?!\s*चौपाटी)/i, 'dadar'],
	[/\b(waterlog\w*|water-logged|flooded\s+(street|road|subway|underpass)|flooding)\b|पाणी साचले|पाणी तुंबले|जलभराव|जलजमाव/i, 'waterlogging'],
	[/\b(high[\s-]tide|tidal\s+surge|spring\s+tide)\b|भरती|उधाण|ऊँचा ज्वार|उच्च ज्वार|ज्वार-भाटा/i, 'high_tide'],
	[/\b(local\s+trains?|suburban\s+(rail(way)?|trains?|services?)|(central|western|harbou?r)\s+(railway|line))\b|लोकल/i, 'local_train'],
	[/\bmetro\b(?!\s+(cinema|junction))|मेट्रो/i, 'metro'],
	[/\b(double[\s-]?deckers?|best\s+bus(es)?|bus(es)?)\b|डबल[\s-]?डेकर|बेस्ट बस/i, 'bus'],
	[/\b(taxis?|kaa?li[\s-]?peeli)\b|टॅक्सी|टैक्सी|काळी[\s-]?पिवळी|काली[\s-]?पीली/i, 'taxi'],
];

/** A photo for the first place named in a text (a title, a road, a destination). */
export function photoForText(text: string | null | undefined, hour: number | null = null): PlacePhoto | null {
	if (!text) return null;
	for (const [re, place] of WORDS) if (re.test(text)) return photoForPlace(place, hour);
	return null;
}
