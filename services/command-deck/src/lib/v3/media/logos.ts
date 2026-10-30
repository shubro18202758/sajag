/**
 * Agency and data-source marks (static/logos; owners and sources in static/logos/NOTICE.md). Used as-is — trimmed and
 * resized only, never redrawn or recoloured — on a light plate where a mark needs one. The marks belong to their
 * owners; Sajag is a prototype and is not affiliated with or endorsed by them (the credit line says so where credits
 * live). When a mark is missing, the caller falls back to the generic agency tile (static/illustrations/agencies).
 */
import { MARK_ROWS } from './logos.data';

export interface Mark {
	key: string;
	/** The owner's name as the owner writes it (EN; the pack has HI / MR). */
	name: string;
	src: string;
	w: number;
	h: number;
	/** 'light': a white plate (a dark or transparent mark that would vanish on the night ground); 'dark': a dark plate (white lettering); 'none'. */
	plate: 'light' | 'dark' | 'none';
}

export const MARKS: readonly Mark[] = MARK_ROWS;
const BY_KEY = new Map(MARKS.map((m) => [m.key, m]));

/** Roles the deck speaks of → the marks that stand for them, best first (keys are cities/mumbai/city.json agency ids). */
// Mumbai Fire Brigade, ERSS 112, the ambulance (108) service and citizen volunteers have no mark on file: they keep the
// generic badge. Mumbai Traffic Police has no separate mark (its roles resolve to the Mumbai Police badge); the
// Maharashtra SDMA has no mark on file either, so the disaster roles fall through to NDMA (markFor('msdma') stays null).
// Central and Western Railway share the Indian Railways logo their sites carry.
const ROLE: Readonly<Record<string, readonly string[]>> = {
	police: ['mumbai_police', 'maha_police'],
	zone: ['mumbai_police', 'maha_police'],
	patrol: ['mumbai_police', 'maha_police'],
	traffic: ['mtp', 'mumbai_police'],
	mtp: ['mumbai_police'],
	mtp_traffic: ['mtp', 'mumbai_police'],
	kp_traffic: ['mtp', 'mumbai_police'], // legacy alias
	state_police: ['maha_police'],
	municipal: ['bmc'],
	corporation: ['bmc'],
	civic: ['bmc'],
	bmc_dm: ['bmc'],
	'1916': ['bmc'],
	development: ['mmrda'],
	mmrda: ['mmrda'],
	disaster: ['msdma', 'ndma'],
	sdrf: ['msdma', 'ndma'],
	sdma: ['msdma', 'ndma'],
	ndrf: ['ndma'],
	sachet: ['ndma_sachet'],
	weather: ['imd'],
	metro: ['metro'],
	bus: ['best'],
	transport: ['best'],
	best: ['best'],
	rail: ['cr', 'wr'],
	railway: ['cr', 'wr'],
	local: ['cr', 'wr'],
	suburban: ['cr', 'wr'],
	roads: ['msrdc'],
	sea_link: ['msrdc'],
	expressway: ['msrdc'],
	port: ['port'],
	osm: ['openstreetmap'],
	rain: ['open_meteo'],
	nowcast: ['open_meteo'],
	satellite: ['copernicus'],
	sentinel: ['copernicus'],
	dem: ['copernicus'],
	globe: ['cesium'],
};

/** The mark for a role, an agency or a source name (null when none is on file). */
export function markFor(role: string | null | undefined): Mark | null {
	const k = (role ?? '').toLowerCase().trim().replace(/[\s-]+/g, '_');
	if (!k) return null;
	const direct = BY_KEY.get(k);
	if (direct) return direct;
	for (const key of ROLE[k] ?? []) {
		const m = BY_KEY.get(key);
		if (m) return m;
	}
	return null;
}

/** A source's mark from its publisher / feed name or domain (Sachet, IMD, Open-Meteo, the BMC …); null when none is on file. */
export function sourceMark(publisher: string | null | undefined): Mark | null {
	const p = (publisher ?? '').toLowerCase();
	if (!p) return null;
	// Specific bodies first: several of their names contain a more generic pattern ('BMC Disaster Management',
	// 'Mumbai Metropolitan Region …', 'Brihanmumbai Electric Supply …'). An MSDMA source stays unmarked rather than
	// borrowing the NDMA seal.
	if (/sachet/.test(p)) return markFor('sachet');
	if (/\bmsdma\b|maharashtra (state )?disaster/.test(p)) return markFor('msdma');
	if (/best undertaking|bestundertaking|brihanmumbai electric/.test(p) || /\bBEST\b/.test(publisher ?? '')) return markFor('best');
	if (/\bbmc\b|\bmcgm\b|brihanmumbai (municipal|mahanagar)|municipal corporation of greater mumbai/.test(p)) return markFor('bmc');
	if (/\bmmrda\b|mumbai metropolitan region/.test(p)) return markFor('mmrda');
	if (/ndma|disaster management/.test(p)) return markFor('ndma');
	if (/\bimd\b|meteorolog|mausam|colaba|santacruz/.test(p)) return markFor('imd');
	if (/open-?meteo/.test(p)) return markFor('open_meteo');
	if (/copernicus|sentinel/.test(p)) return markFor('copernicus');
	if (/openstreetmap|\bosm\b/.test(p)) return markFor('openstreetmap');
	if (/maharashtra police|mahapolice/.test(p)) return markFor('maha_police');
	if (/traffic police|trafficpolice/.test(p)) return markFor('traffic');
	if (/mumbai police|mumbaipolice/.test(p)) return markFor('mumbai_police');
	if (/police/.test(p)) return markFor('police');
	if (/central railway|cr\.indianrailways/.test(p)) return markFor('cr');
	if (/western railway|wr\.indianrailways/.test(p)) return markFor('wr');
	if (/\bmmrcl?\b|\bmmmocl\b|mumbai metro|\bmetro\b/.test(p)) return markFor('metro');
	if (/\bmsrdc\b|state road development/.test(p)) return markFor('msrdc');
	if (/mumbai port|mumbaiport/.test(p)) return markFor('port');
	return null;
}
