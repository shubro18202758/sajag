/**
 * Relations named from both ends (SPEC §7.2, plan X5). A link between two
 * objects reads differently from each side: from a vehicle its reads are
 * "Lawful reads"; from a read, the vehicle is "Vehicle". Every pair of kinds
 * has a name, so nothing ever falls into a generic "Linked" group (revision
 * 1's bug, where a read was filed under "Linked" instead of its reads).
 *
 * Relation ids are the oracle's own (city/dossier.py) wherever it names one,
 * so `rel-group[data-relation]` reads the same for a dossier relation and for
 * a link the snapshot implies. The OSINT pairs follow contract C-T:
 *   osint_event → place  "Reported at"     place → osint_event   "Reports here"
 *   osint_event → event  "Corroborates" / "Promoted to"
 *   event → osint_event  "Corroborated by" / "Promoted from"
 *   osint_event → segment "On road"        osint_event → junction "At junction"
 */
import { t } from '$lib/i18n/strings';
import '$lib/i18n/packs.workspace';

/** fromKind → toKind → relation id (what `to` is to `from`). */
const REL: Readonly<Record<string, Readonly<Record<string, string>>>> = {
	vehicle: { sighting: 'sighting', camera: 'seen_by_camera', recommendation: 'recommendation', event: 'pursuit' },
	sighting: { vehicle: 'vehicle', camera: 'camera', recommendation: 'recommendation', segment: 'road' },
	recommendation: { vehicle: 'vehicle', sighting: 'evidence_sighting', camera: 'camera', segment: 'segment', event: 'pursuit' },
	camera: { junction: 'junction', sighting: 'recent_hit', vehicle: 'vehicle_seen', segment: 'segment', recommendation: 'recommendation' },
	event: {
		vehicle: 'pursued_vehicle',
		recommendation: 'authorizing_recommendation',
		dispatch: 'dispatch',
		unit: 'unit',
		segment: 'route_segment',
		junction: 'signal_junction',
		convoy: 'convoy',
		osint_event: 'corroborated_by',
	},
	junction: { segment: 'adjacent_segment', dispatch: 'dispatch_waypoint', camera: 'camera', event: 'signal_event', osint_event: 'reports_here' },
	unit: { dispatch: 'dispatch', event: 'assigned_event' },
	dispatch: { event: 'event', unit: 'unit', junction: 'waypoint_junction' },
	convoy: { event: 'event' },
	anomaly: { segment: 'segment' },
	segment: {
		junction: 'adjacent_junction',
		event: 'spine_of',
		anomaly: 'anomaly',
		camera: 'camera',
		recommendation: 'decision_on_road',
		sighting: 'read_on_road',
		osint_event: 'reports_here',
	},
	osint_event: { place: 'reported_at', event: 'corroborates', segment: 'on_road', junction: 'at_junction' },
	place: { osint_event: 'reports_here' },
};

/**
 * The relations whose reverse depends on which variant was named (C-T): a
 * report that was PROMOTED to an event reads "Promoted from" on the event, one
 * that corroborates it reads "Corroborated by". Every other reverse is the
 * kinds' pair from the other end.
 */
const VARIANT_REVERSE: Readonly<Record<string, string>> = {
	promoted_to: 'promoted_from',
	promoted_from: 'promoted_to',
	corroborates: 'corroborated_by',
	corroborated_by: 'corroborates',
};

/** Relation ids a dossier may send that this table names (the oracle's own). */
const KNOWN_HINTS = new Set([...Object.values(REL).flatMap((m) => Object.values(m)), ...Object.keys(VARIANT_REVERSE)]);

/**
 * The relation id of `to` as seen from `from`. A hint (the oracle's relation
 * name) wins when this table knows it, or when the pair has no name of its
 * own; an unknown pair falls back to the other end's kind (`sighting`,
 * `camera` …), never a generic "linked".
 */
export function relId(fromKind: string, toKind: string, hint?: string | null): string {
	const own = REL[fromKind]?.[toKind];
	if (hint && hint !== 'related' && /^[a-z][a-z0-9_]{0,47}$/.test(hint) && (KNOWN_HINTS.has(hint) || !own)) return hint;
	return own ?? toKind;
}

/** The relation id seen from the other end of a link named `rel` from `fromKind`'s side. */
export function reverseRel(rel: string, fromKind: string, toKind: string): string {
	return VARIANT_REVERSE[rel] ?? REL[toKind]?.[fromKind] ?? fromKind;
}

/**
 * The display name of a relation from `fromKind` to `toKind` (EN unless
 * `lang`): "Lawful reads", "Seen by cameras", "Reported at" … An unknown
 * relation reads as the other kind's plural ("Sightings"), never "Linked".
 */
export function relName(fromKind: string, toKind: string, hint?: string | null, lang = 'en'): string {
	return relLabel(relId(fromKind, toKind, hint), toKind, lang);
}

/** The display name of relation id `rel` whose other end is `toKind`. */
export function relLabel(rel: string, toKind: string, lang = 'en'): string {
	const key = `ws_rel_${rel}`;
	const named = t(lang, key);
	if (named !== key) return named;
	const plural = t(lang, `ws_kinds_${toKind}`);
	if (plural !== `ws_kinds_${toKind}`) return plural;
	const words = rel.replace(/_/g, ' ');
	return words.charAt(0).toUpperCase() + words.slice(1);
}
