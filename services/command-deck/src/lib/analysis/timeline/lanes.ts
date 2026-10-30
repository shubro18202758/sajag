/**
 * The timeline's seven lanes (SPEC §5.3 "Timeline [S4]") and the colour rule
 * of each tick, pure.
 *
 *   Events · Enforcement · ANPR reads · Dispatch · Signals · Band changes ·
 *   AI decisions
 *
 * A row's lane is its wire kind; an open-source report (feed kind `osint`)
 * rides the Events lane (plan X8), and is still COUNTED as open-source
 * wherever the rail counts kinds (kindCounts: by row.feedKind).
 *
 * Tick colours (only by role, SPEC §2.4): neutral grey by default; blue
 * (3 px, drawn on top) when the row names the selection or one of its linked
 * objects; red for a watchlist read; orange for an enforcement row whose
 * decision still waits; band changes stay neutral. An officer's action is a
 * taller tick (15 px instead of 9).
 */
import type { CityFeedKind, FeedKind } from '$lib/gods-eye/city-api';
import { enforcementStep } from '$lib/workspace/display';

export const LANE_IDS = ['event', 'enforcement', 'anpr', 'dispatch', 'signals', 'ama', 'brain'] as const satisfies readonly FeedKind[];

export type LaneId = (typeof LANE_IDS)[number];

/** The pack key of each lane's name. */
export const LANE_KEY: Readonly<Record<LaneId, string>> = {
	event: 'an_lane_event',
	enforcement: 'an_lane_enforcement',
	anpr: 'an_lane_anpr',
	dispatch: 'an_lane_dispatch',
	signals: 'an_lane_signals',
	ama: 'an_lane_ama',
	brain: 'an_lane_brain',
};

/** What the lane rules read of a feed row (a FeedRow satisfies it). */
export interface LaneRow {
	kind: string;
	feedKind?: string | null;
	urns: readonly string[];
	actorKind: 'human' | 'machine' | 'system';
	severity?: string | null;
	text?: string | null;
	props?: Readonly<Record<string, unknown>> | null;
}

/** The lane a row is drawn in: its wire kind, `osint` → Events (plan X8); null for a kind no lane takes. */
export function laneOf(row: Pick<LaneRow, 'kind' | 'feedKind'>): LaneId | null {
	const k = row.feedKind ?? row.kind;
	if (k === 'osint') return 'event';
	return (LANE_IDS as readonly string[]).includes(k) ? (k as LaneId) : null;
}

/** The row is an open-source report (wire kind `osint`). */
export function isOsint(row: Pick<LaneRow, 'kind' | 'feedKind'>): boolean {
	return (row.feedKind ?? row.kind) === 'osint';
}

/** A named person acted (the taller tick). */
export function isOfficerAction(row: Pick<LaneRow, 'actorKind'>): boolean {
	return row.actorKind === 'human';
}

/** A read of a watchlisted vehicle: the ANPR row carries a hit (or the oracle marked it critical). */
export function isWatchRead(row: LaneRow): boolean {
	if (laneOf(row) !== 'anpr') return false;
	const p = row.props ?? {};
	return (typeof p.hit === 'string' && !!p.hit) || (typeof p.matched_plate_hit === 'string' && !!p.matched_plate_hit) || row.severity === 'critical';
}

/**
 * An enforcement row whose decision still waits: a filed sighting or
 * e-challan (its structured fields, else the oracle's fixed opening) whose
 * recommendation is still pending NOW (`props.status`), or whose text says
 * it awaits a duty officer.
 */
export function awaitsDecision(row: LaneRow): boolean {
	if (laneOf(row) !== 'enforcement') return false;
	const step = enforcementStep({ kind: 'enforcement', text: row.text ?? '', actorKind: row.actorKind, props: row.props ?? {} });
	const status = row.props?.status;
	if (step && step.step !== 'filed') return false;
	if (status === 'pending') return true;
	return status == null && /awaiting a duty officer/i.test(String(row.text ?? ''));
}

/** The row names one of `related` (the selection and its linked objects). */
export function isLinked(row: Pick<LaneRow, 'urns'>, related: ReadonlySet<string> | null | undefined): boolean {
	if (!related || !related.size) return false;
	for (const u of row.urns) if (related.has(u)) return true;
	return false;
}

export type TickTone = 'neutral' | 'linked' | 'watch' | 'decision';

/** The tick's colour role: linked wins (drawn on top), then watchlist read, then a waiting decision; band changes stay neutral. */
export function toneOf(row: LaneRow, related?: ReadonlySet<string> | null): TickTone {
	if (isLinked(row, related)) return 'linked';
	const lane = laneOf(row);
	if (lane === 'ama') return 'neutral';
	if (isWatchRead(row)) return 'watch';
	if (awaitsDecision(row)) return 'decision';
	return 'neutral';
}

/** Rows per lane (osint counted in Events, as drawn). */
export function laneCounts(rows: readonly Pick<LaneRow, 'kind' | 'feedKind'>[]): Record<LaneId, number> {
	const out = Object.fromEntries(LANE_IDS.map((l) => [l, 0])) as Record<LaneId, number>;
	for (const r of rows) {
		const l = laneOf(r);
		if (l) out[l]++;
	}
	return out;
}

/** Rows per WIRE kind (the rail's key and toggles: an open-source row counts as open-source, never as an event). */
export function kindCounts(rows: readonly Pick<LaneRow, 'kind' | 'feedKind'>[]): Record<CityFeedKind, number> {
	const out: Record<CityFeedKind, number> = { event: 0, enforcement: 0, anpr: 0, dispatch: 0, signals: 0, ama: 0, brain: 0, osint: 0 };
	for (const r of rows) {
		const k = (r.feedKind ?? r.kind) as CityFeedKind;
		if (k in out) out[k]++;
	}
	return out;
}
