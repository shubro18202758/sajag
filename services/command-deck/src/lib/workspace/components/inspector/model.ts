/**
 * The inspector's view model, as plain data (SPEC §5.3 ObjectInspector):
 * the Links tab's groups, the Activity tab's one-line rows, the link cards
 * to decision homes. Pure: the components render it, the unit test reads it.
 *
 *   Links      grouped by relation (`rel-group[data-relation]`), each with a
 *              count; a group whose rows share one state states it ONCE in
 *              its header; one time format per group (colStamp)
 *   Activity   one row per entry: time, actor glyph, actor, brief(row); the
 *              full text in the row's expander, its officer note exactly as
 *              sent (displayRowText); filters All / Officers / Machine /
 *              System. Once the rows span days, every row's day sits under
 *              its clock (one format for the column, SPEC §3.3), so a dated
 *              stamp never eats the line in a 344–400 px dock
 *   Actions    a link card to the home of every decision unit whose subject
 *              is this object, unless a registered section links that unit
 *              kind itself (ownsUnitKinds) — never a second Approve button
 */
import { ACTOR_ICON, type IconName } from '$lib/design/icons';
import { colStamp, fmtDay, fmtTime, istDay, toMs } from '$lib/ui/format/format';
import type { FeedRow } from '$lib/gods-eye/city-api';
import type { VerificationState } from '$lib/ops/types';
import { actorName, actorParts, brief, displayRowText } from '../../display';
import { stateWord } from '../../kinds/generic';
import { relLabel } from '../../relations';
import type { DecisionUnitSummary, ObjectLink, ObjectRow } from '../../types';

// ── links ─────────────────────────────────────────────────────────────────

export interface LinkGroup {
	relation: string;
	label: string;
	kind: string;
	rows: ObjectRow[];
	/** The one state every row shares (stated once in the header), or null when mixed. */
	sharedState: string | null;
	/** One time per row, one format for the whole group. */
	times: string[];
}

/** Relations shown first (the oracle's order of importance); the rest follow by size. */
const RELATION_ORDER = [
	'pursued_vehicle',
	'vehicle',
	'pursuit',
	'authorizing_recommendation',
	'recommendation',
	'evidence_sighting',
	'sighting',
	'seen_by_camera',
	'camera',
	'recent_hit',
	'reported_at',
	'promoted_to',
	'corroborates',
	'promoted_from',
	'corroborated_by',
	'reports_here',
	'dispatch',
	'unit',
	'convoy',
	'event',
	'assigned_event',
	'waypoint_junction',
	'junction',
	'at_junction',
	'on_road',
	'signal_junction',
	'dispatch_waypoint',
	'route_segment',
	'road',
	'segment',
	'adjacent_segment',
	'adjacent_junction',
	'spine_of',
	'signal_event',
	'anomaly',
];

/** States a group never states (they are every row's default, not news). */
const QUIET_STATES = new Set(['active', 'flowing', 'green', 'stolen_vehicle']);

export function linkGroups(links: readonly ObjectLink[], lang: string, now: number): LinkGroup[] {
	const by = new Map<string, ObjectRow[]>();
	const seen = new Set<string>();
	for (const l of links) {
		if (seen.has(l.row.urn)) continue;
		seen.add(l.row.urn);
		const list = by.get(l.relation);
		if (list) list.push(l.row);
		else by.set(l.relation, [l.row]);
	}
	const rank = (rel: string) => {
		const i = RELATION_ORDER.indexOf(rel);
		return i < 0 ? RELATION_ORDER.length : i;
	};
	return [...by.entries()]
		.sort((a, b) => rank(a[0]) - rank(b[0]) || b[1].length - a[1].length || a[0].localeCompare(b[0]))
		.map(([relation, rows]) => {
			const sorted = [...rows].sort((a, b) => (b.t ?? 0) - (a.t ?? 0));
			const states = new Set(sorted.map((r) => r.state ?? ''));
			const only = states.size === 1 ? sorted[0].state : null;
			return {
				relation,
				label: relLabel(relation, sorted[0].kind, lang),
				kind: sorted[0].kind,
				rows: sorted,
				sharedState: only && !QUIET_STATES.has(only) && sorted[0].kind !== 'camera' ? only : null,
				times: colStamp(
					sorted.map((r) => r.t),
					now,
				).map((s, i) => (sorted[i].t == null ? '' : s)),
			};
		});
}

/** A group's shared state as the header says it ("approved"), or null. */
export function sharedStateWord(g: LinkGroup, lang: string): string | null {
	return g.sharedState ? (stateWord(g.sharedState, lang)?.toLowerCase() ?? null) : null;
}

// ── activity ──────────────────────────────────────────────────────────────

export type ActivityFilter = 'all' | 'human' | 'machine' | 'system';

export interface ActivityRow {
	id: string;
	t: number;
	/** The column's stamp (colStamp): "22:08", or "23 Oct 22:08" on every row once the days differ. */
	time: string;
	/** The clock, always hh:mm. */
	clock: string;
	/** The row's IST day ("23 Oct") when the rows span days (shown under the clock on every row), else null. */
	day: string | null;
	actorKind: FeedRow['actorKind'];
	glyph: IconName;
	/** The actor glyph is the AI's (drawn in the AI indigo). */
	ai: boolean;
	who: string;
	test: boolean;
	brief: string;
	full: string;
	source: FeedRow['source'];
	/** An OSINT row's verification label (ethics rule 7: its tag says it), else null. */
	verification: VerificationState | null;
}

/** The actor's glyph (SPEC §4.2): officer, Sajag AI, rules engine or policy, sensor, system. */
export function actorGlyph(kind: FeedRow['actorKind'], actor: string | null): { glyph: IconName; ai: boolean } {
	const a = actor ?? '';
	if (kind === 'human') return { glyph: ACTOR_ICON.officer, ai: false };
	if (kind === 'system' || /^system/i.test(a)) return { glyph: ACTOR_ICON.system, ai: false };
	if (/brain|decider|gemma|model|assistant|sajag ai/i.test(a)) return { glyph: ACTOR_ICON.ai, ai: true };
	if (/^EM-|cam/i.test(a)) return { glyph: ACTOR_ICON.sensor, ai: false };
	return { glyph: ACTOR_ICON.rules, ai: false };
}

export function activityRows(rows: readonly FeedRow[], filter: ActivityFilter, now: number, lang = 'en'): ActivityRow[] {
	const sorted = [...rows].sort((a, b) => b.t - a.t);
	const shown = filter === 'all' ? sorted : sorted.filter((r) => r.actorKind === filter);
	const times = colStamp(
		shown.map((r) => r.t),
		now,
	);
	const today = istDay(now);
	const dated = shown.some((r) => istDay(r.t) !== today);
	return shown.map((r, i) => {
		const actor = r.actor ? actorParts(r.actor) : null;
		const g = actorGlyph(r.actorKind, r.actor);
		return {
			id: r.id,
			t: r.t,
			time: times[i],
			clock: fmtTime(r.t),
			day: dated ? fmtDay(r.t) : null,
			actorKind: r.actorKind,
			glyph: g.glyph,
			ai: g.ai,
			who: actor ? actorName(actor, lang) : r.actorKind,
			test: actor?.test ?? false,
			brief: brief(r, lang),
			full: displayRowText(r),
			source: r.source,
			verification: r.source === 'osint' ? r.verificationState : null,
		};
	});
}

// ── key figures ───────────────────────────────────────────────────────────

/**
 * The day a key figure's time carries (SPEC §3.3): null when it falls on the
 * anchor's IST day (the clock alone says it), else "23 Oct" — shown under
 * the clock, so a read 18 h old never reads as a bare 22:08 beside a
 * subtitle that says "23 Oct 22:08".
 */
export function figureDay(ms: number | null | undefined, anchor: number): string | null {
	const v = toMs(ms);
	if (!Number.isFinite(v)) return null;
	return istDay(v) === istDay(anchor) ? null : fmtDay(v);
}

/** How many rows each filter shows. */
export function activityCounts(rows: readonly FeedRow[]): Record<ActivityFilter, number> {
	const out: Record<ActivityFilter, number> = { all: rows.length, human: 0, machine: 0, system: 0 };
	for (const r of rows) out[r.actorKind] += 1;
	return out;
}

// ── link cards to decision homes ───────────────────────────────────────────

/** The units this object is the subject of, minus the kinds a registered section links itself. */
export function linkCards(urn: string, units: readonly DecisionUnitSummary[], owned: ReadonlySet<string>): DecisionUnitSummary[] {
	return units.filter((u) => u.subjectUrn === urn && !owned.has(u.kind));
}
