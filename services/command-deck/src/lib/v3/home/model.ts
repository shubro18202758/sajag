/**
 * Home's pure rules (V3-SPEC §6.1) — no store, no DOM, unit-tested by tests/home.unit.mjs:
 *
 *   pickFeatured     the featured decision: the soonest-deadline unit (decisionUnits() order — deadline
 *                    first, none last, then severity), with the §12.3 hysteresis: a featured unit stays
 *                    featured while its deadline is within 15 s of the new soonest one, so two near
 *                    deadlines never flip the hero back and forth;
 *   reportTally      reported events by verification (official · news · unverified);
 *   liveOpsOf /      the corridor events that are running now / start within 72 h (board rows only,
 *   plannedOf        never the offline fixtures), soonest first;
 *   artFor / glyphFor  the illustration and the glyph of an event kind or an OSINT class;
 *   splitLabel       "Road accident · Ruby crossing (EM Bypass)" → kind line + title;
 *   countdownText    "0:47" under an hour, "1 h 34 min" past it.
 */
import { fmtCountdown, fmtDuration } from '$lib/ui/format/format';

/** A unit's identity across polls. */
export const unitKey = (u: { kind: string; id: string }) => `${u.kind}:${u.id}`;

/** The hero's hysteresis (V3-SPEC §12.3). */
export const FEATURE_HYSTERESIS_MS = 15_000;

/**
 * The featured decision. `units` must already be in decisionUnits() order (soonest deadline first);
 * `prevKey` is the unit featured until now. Returns null when nothing waits.
 */
export function pickFeatured<T extends { kind: string; id: string; deadline: number | null }>(
	units: readonly T[],
	prevKey: string | null,
	now: number,
	hysteresisMs = FEATURE_HYSTERESIS_MS,
): T | null {
	const live = units.filter((u) => u.deadline == null || u.deadline > now);
	const soonest = live[0] ?? null;
	if (!soonest || !prevKey) return soonest;
	const prev = live.find((u) => unitKey(u) === prevKey);
	if (!prev || prev === soonest) return soonest;
	if (prev.deadline == null && soonest.deadline == null) return prev;
	if (prev.deadline == null) return soonest;
	return prev.deadline - (soonest.deadline ?? Infinity) <= hysteresisMs ? prev : soonest;
}

/** The units in the order the rail shows them, the featured one first. */
export function railOrder<T extends { kind: string; id: string }>(units: readonly T[], featured: T | null): T[] {
	if (!featured) return [...units];
	return [featured, ...units.filter((u) => unitKey(u) !== unitKey(featured))];
}

export interface ReportTally {
	official: number;
	news: number;
	unverified: number;
	other: number;
	total: number;
}

/** Reported events by their honest label (C-T verification_state). */
export function reportTally(reports: readonly { verificationState: string | null }[]): ReportTally {
	const t: ReportTally = { official: 0, news: 0, unverified: 0, other: 0, total: reports.length };
	for (const r of reports) {
		const v = r.verificationState ?? '';
		if (v === 'OFFICIAL-VERIFIED' || v === 'CONFIRMED') t.official++;
		else if (v === 'NEWS-REPORTED') t.news++;
		else if (v === 'UNVERIFIED-OSINT') t.unverified++;
		else t.other++;
	}
	return t;
}

interface EventLike {
	eventId: string;
	eventKind: string;
	state: string;
	source: string;
	windowStart: string | null;
}

const LIVE_STATES = new Set(['active', 'live']);
const PLANNED_STATES = new Set(['planned', 'planning', 'approved']);
const KIND_RANK: Record<string, number> = { protected_movement: 0, vehicle_pursuit: 1 };

/** The running operations: live board rows (never fixtures), movements and pursuits first. */
export function liveOpsOf<T extends EventLike>(events: readonly T[]): T[] {
	return events
		.filter((e) => e.source !== 'offline-fixture' && LIVE_STATES.has(e.state))
		.sort((a, b) => (KIND_RANK[a.eventKind] ?? 2) - (KIND_RANK[b.eventKind] ?? 2) || (a.eventId < b.eventId ? -1 : 1));
}

/** Planned events starting within `horizonMs` (72 h), soonest first. */
export function plannedOf<T extends EventLike>(events: readonly T[], now: number, horizonMs = 72 * 3_600_000): T[] {
	const at = (e: T) => {
		const ms = e.windowStart ? Date.parse(e.windowStart) : NaN;
		return Number.isFinite(ms) ? ms : Infinity;
	};
	return events
		.filter((e) => e.source !== 'offline-fixture' && PLANNED_STATES.has(e.state))
		.filter((e) => at(e) === Infinity || (at(e) >= now - 3_600_000 && at(e) <= now + horizonMs))
		.sort((a, b) => at(a) - at(b));
}

/** The event-art tiles that exist (static/illustrations/events/*.svg). */
export const EVENT_ART = new Set([
	'protected_movement',
	'procession',
	'mass_gathering',
	'race',
	'ceremonial',
	'egress_surge',
	'emergency_evacuation',
	'work_zone',
	'crime_incident',
	'vehicle_pursuit',
	'reported_crime',
	'public_disorder',
	'road_accident',
	'hazard',
	'flooding',
	'infra_failure',
	'weather',
	'advisory',
	'green_corridor',
]);

/** OSINT classes that read as an event kind's art. */
const CLASS_ALIAS: Record<string, string> = {
	accident: 'road_accident',
	road_crash: 'road_accident',
	waterlogging: 'flooding',
	flood: 'flooding',
	weather_hazard: 'weather',
	weather_warning: 'weather',
	heavy_rain: 'weather',
	cyclone: 'weather',
	robbery: 'reported_crime',
	theft: 'reported_crime',
	crime: 'reported_crime',
	protest: 'public_disorder',
	gathering: 'mass_gathering',
	fire: 'hazard',
	building_collapse: 'infra_failure',
	power_outage: 'infra_failure',
	signal_failure: 'infra_failure',
};

/** The illustration for an event kind / OSINT class (the advisory tile when none fits). */
export function artFor(kind: string | null | undefined): string {
	const k = (kind ?? '').toLowerCase();
	const name = EVENT_ART.has(k) ? k : (CLASS_ALIAS[k] ?? 'advisory');
	return `/illustrations/events/${name}.svg`;
}

const KIND_GLYPH: Record<string, string> = {
	protected_movement: 'convoy',
	procession: 'flag',
	mass_gathering: 'stadium',
	race: 'flag',
	ceremonial: 'flag',
	egress_surge: 'stadium',
	emergency_evacuation: 'alert',
	work_zone: 'cone',
	crime_incident: 'anpr',
	vehicle_pursuit: 'pursuit',
	reported_crime: 'news',
	public_disorder: 'target',
	road_accident: 'alert',
	hazard: 'alert',
	flooding: 'wave',
	infra_failure: 'building',
	weather: 'wave',
	advisory: 'megaphone',
	green_corridor: 'ambulance',
};

/** The map glyph of an event kind / OSINT class (type is the icon; state is the colour). */
export function glyphFor(kind: string | null | undefined): string {
	const k = (kind ?? '').toLowerCase();
	return KIND_GLYPH[k] ?? KIND_GLYPH[CLASS_ALIAS[k] ?? ''] ?? 'pin';
}

/** "Kind · Place" → { kind, title }; a label without the separator is all title. */
export function splitLabel(label: string): { kind: string | null; title: string } {
	const at = label.indexOf(' · ');
	if (at <= 0) return { kind: null, title: label };
	return { kind: label.slice(0, at), title: label.slice(at + 3) };
}

/** Time left, as a card says it: "0:47" under an hour, "1 h 34 min" past it. */
export function countdownText(leftMs: number, lang: string): string {
	const s = Math.max(0, leftMs / 1000);
	return s >= 3600 ? fmtDuration(s, lang) : fmtCountdown(s);
}

/** The greeting for an IST hour. */
export function greetingKey(hourIst: number): string {
	if (hourIst >= 5 && hourIst < 12) return 'v3_greet_morning';
	if (hourIst >= 12 && hourIst < 17) return 'v3_greet_afternoon';
	return 'v3_greet_evening';
}

/** The pulse sentence for a band (null = not known: never shown as green). */
export function bandSentenceKey(band: string | null | undefined): string {
	switch (band) {
		case 'GREEN':
			return 'v3_city_green';
		case 'AMBER':
			return 'v3_city_amber';
		case 'RED':
			return 'v3_city_red';
		case 'BLACK':
			return 'v3_city_black';
		default:
			return 'v3_city_unknown';
	}
}
