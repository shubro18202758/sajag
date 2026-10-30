/**
 * The /plan page's pure rules (V3-SPEC §6.6 "Where to?", colleague review "the planner on its own page"). The
 * planner itself is NOT here: the plan document, the launch gate and the escort lifecycle are the corridor's own
 * (src/lib/corridor/plan.ts and escort-state.svelte.ts, imported unchanged). This module only says how the page
 * walks through them — which step is showing, which places match a search, when the movement leaves, what the
 * plan's figures read as, and how a launch that did not start is worded — so tests/v3-plan.unit.mjs can drive
 * every rule without a browser.
 *
 * Honesty rules held here:
 *   - the class table is the planner's protocol table (shared/schemas/protocol_params.json, pinned by the test);
 *   - a route shows only the figures the plan reports (time, distance, roads) — never an invented one;
 *   - the escort runs the plan's RECOMMENDED route (the launch call carries no route): the other candidates are
 *     for comparison, and the page says so;
 *   - a launch that did not start is never called "refused" unless the brain refused it in words.
 */
import type { MovementPlanDoc, PlanRouteCandidate } from '$lib/api/client';
import type { LonLat } from '../map/mercator';
import type { ThumbLine, ThumbOverlay, ThumbPoint } from '../map/overlay';

// ── the protection classes ────────────────────────────────────────────────────

export type ClassId = 'Z+' | 'Z' | 'Y' | 'X';

/**
 * Each class as the planner applies it — the lane floor (MIN_LANES) and the advance-closure floor in seconds
 * (ADVANCE_CLOSURE_FLOOR_SEC; null = no floor). Mirrors shared/schemas/protocol_params.json `protection_classes`
 * (the brain's and the oracle's generated protocol_params_gen.py); tests/v3-plan.unit.mjs reads that file and
 * fails on any drift.
 */
export const PROTECTION_CLASSES: readonly { id: ClassId; minLanes: number; advanceClosureSec: number | null }[] = [
	{ id: 'Z+', minLanes: 6, advanceClosureSec: 180 },
	{ id: 'Z', minLanes: 4, advanceClosureSec: 120 },
	{ id: 'Y', minLanes: 2, advanceClosureSec: 60 },
	{ id: 'X', minLanes: 1, advanceClosureSec: null },
];

// ── the steps ─────────────────────────────────────────────────────────────────

export type PlanStep = 'where' | 'routes' | 'launch' | 'live';
export const STEPS: readonly PlanStep[] = ['where', 'routes', 'launch', 'live'];

/**
 * The step the page shows, from the shared escort lifecycle's phase and the page's own two flags:
 *   live    an escort runs (this console's or an adopted one), is stopping, or has ended and is not reset;
 *   launch  the officer chose Continue on a plan that may depart (or a launch is in flight);
 *   routes  a plan document is in (approved, conditional, hold or no route) and the officer is not editing;
 *   where   otherwise (no plan yet, or editing the trip).
 */
export function stepOf(s: { phase: string; hasDoc: boolean; offered: boolean; confirming: boolean; editing: boolean }): PlanStep {
	if (s.phase === 'escorting' || s.phase === 'stopping' || s.phase === 'ended') return 'live';
	if (s.phase === 'starting') return 'launch';
	if (s.hasDoc && !s.editing) return s.confirming && s.offered ? 'launch' : 'routes';
	return 'where';
}

// ── places ────────────────────────────────────────────────────────────────────

const fold = (v: string) =>
	v
		.normalize('NFKD')
		.replace(/[̀-ͯ]/g, '')
		.toLowerCase()
		.replace(/[^\p{L}\p{M}\p{N}]+/gu, ' ')
		.trim();

/**
 * The planner's places matching a search, best first: a name that starts with the query, then a word that does,
 * then a name containing it. An empty query lists every place. Indices into `pois` (the corridor's PLAN_POIS).
 */
export function matchPlaces(query: string, pois: readonly { name: string; alt?: string }[]): number[] {
	const q = fold(query);
	const all = pois.map((_, i) => i);
	if (!q) return all;
	const rankOf = (name: string) => {
		const n = fold(name);
		if (n.startsWith(q)) return 0;
		if (n.split(' ').some((w) => w.startsWith(q))) return 1;
		return n.includes(q) ? 2 : 3;
	};
	// the page's spelling first; the English one (a Marathi or Hindi page) still finds the place
	const rank = (i: number) => Math.min(rankOf(pois[i].name), pois[i].alt ? rankOf(pois[i].alt!) : 3);
	return all.filter((i) => rank(i) < 3).sort((a, b) => rank(a) - rank(b) || a - b);
}

// ── departure ─────────────────────────────────────────────────────────────────

export type DepartureChoice = 'in30' | 'in60' | 'at';

/**
 * When the movement leaves (epoch ms): in 30 min (the planner's own default), in an hour, or at an IST wall time
 * ("hh:mm", already normalised; `istToMs` turns it into today's instant). A time already past today means
 * tomorrow — said on the page, never silently a past departure. NaN when the time is not a valid one.
 */
export function departureMs(choice: DepartureChoice, hhmm: string | null, now: number, istToMs: (hhmm: string, anchor: number) => number): number {
	if (choice === 'in30') return now + 30 * 60_000;
	if (choice === 'in60') return now + 60 * 60_000;
	if (!hhmm) return NaN;
	const at = istToMs(hhmm, now);
	if (!Number.isFinite(at)) return NaN;
	return at < now ? at + 24 * 3600_000 : at;
}

/** True when `ms` falls on a later IST calendar day than `now` ("tomorrow"). */
export function isLaterIstDay(ms: number, now: number): boolean {
	const day = (v: number) => Math.floor((v + 5.5 * 3600_000) / 86_400_000);
	return Number.isFinite(ms) && day(ms) > day(now);
}

// ── the routes ────────────────────────────────────────────────────────────────

export interface RouteFigures {
	/** Whole minutes, at least 1 — only when the plan reports a time. */
	minutes: number | null;
	/** Kilometres, one decimal — only when the plan reports a distance. */
	km: string | null;
	/** The number of named roads — only when the plan names them. */
	roads: number | null;
}

/** The figures a candidate reports (and nothing else). */
export function routeFigures(r: PlanRouteCandidate): RouteFigures {
	const sec = r.estimated_time_sec;
	const m = r.distance_m ?? r.total_distance_m;
	return {
		minutes: sec != null && Number.isFinite(sec) && sec > 0 ? Math.max(1, Math.round(sec / 60)) : null,
		km: m != null && Number.isFinite(m) && m > 0 ? (m / 1000).toFixed(1) : null,
		roads: r.road_names?.length ? r.road_names.length : null,
	};
}

/** The route the page previews: the officer's pick when it is still a candidate, else the recommended one. */
export function previewRouteId(candidates: readonly PlanRouteCandidate[], picked: string | null, recommended: string | null): string | null {
	if (picked && candidates.some((c) => c.route_id === picked)) return picked;
	return recommended ?? candidates[0]?.route_id ?? null;
}

/** A road segment's line, as the ops store loads it (ops.segmentLines). */
export interface SegmentGeom {
	segmentId: number;
	coordinates: readonly (readonly number[])[];
}

/** A candidate's line, segment by segment, from the deck's own road geometry; segments it does not know are skipped. */
export function routeLine(route: PlanRouteCandidate, segments: readonly SegmentGeom[]): LonLat[][] {
	const byId = new Map(segments.map((s) => [s.segmentId, s]));
	const out: LonLat[][] = [];
	for (const id of route.segment_ids ?? []) {
		const s = byId.get(id);
		if (s && s.coordinates.length >= 2) out.push(s.coordinates.map((c) => [c[0], c[1]] as LonLat));
	}
	return out;
}

/**
 * What the map draws: the start and the destination, and — once a plan is in — every candidate, the previewed one
 * in the route colour (teal: a protected movement's route) over the others dashed. With no candidates (or before
 * a plan) the two places alone.
 */
export function planOverlay(o: {
	from: { name: string; coord: readonly [number, number] } | null;
	to: { name: string; coord: readonly [number, number] } | null;
	candidates: readonly PlanRouteCandidate[];
	previewId: string | null;
	segments: readonly SegmentGeom[];
	fromSub?: string | null;
	toSub?: string | null;
}): ThumbOverlay {
	const lines: ThumbLine[] = [];
	const lit: ThumbLine[] = [];
	for (const c of o.candidates) {
		for (const coords of routeLine(c, o.segments)) {
			if (c.route_id === o.previewId) lit.push({ coords, style: 'route' });
			else lines.push({ coords, style: 'dashed' });
		}
	}
	const points: ThumbPoint[] = [];
	if (o.from) points.push({ at: [o.from.coord[0], o.from.coord[1]], tone: 'brand', glyph: 'pin', label: o.from.name, sub: o.fromSub ?? null, labelSide: 'r' });
	if (o.to && (!o.from || o.to.name !== o.from.name))
		points.push({ at: [o.to.coord[0], o.to.coord[1]], tone: 'route', glyph: 'flag', label: o.to.name, sub: o.toSub ?? null, labelSide: 'r' });
	return { lines: [...lines, ...lit], points };
}

/**
 * The plan's lane-floor violations, each once (the corridor lists them per candidate, so a road every candidate
 * shares would repeat), worded with the road's name only when the planner's own detail does not already name it.
 */
export function waiverLines(
	violations: readonly { segmentId: number | null; detail: string }[],
	roadName: (segmentId: number) => string | null,
	segLabel: (segmentId: number) => string,
): string[] {
	const seen = new Set<string>();
	const out: string[] = [];
	for (const v of violations) {
		const key = `${v.segmentId ?? ''}|${v.detail}`;
		if (seen.has(key)) continue;
		seen.add(key);
		if (v.segmentId == null) {
			out.push(v.detail);
			continue;
		}
		const name = roadName(v.segmentId) ?? segLabel(v.segmentId);
		out.push(v.detail.includes(name) ? v.detail : `${name}: ${v.detail}`);
	}
	return out;
}

// ── the plan's state, in words ───────────────────────────────────────────────

export type PlanWord = 'approved' | 'conditional' | 'hold' | 'no_route';

/** The pack key of the plan's state tag. */
export function stateKey(state: string): string {
	return state === 'approved' ? 'v3p_state_approved' : state === 'conditional' ? 'v3p_state_conditional' : state === 'hold' ? 'v3p_state_hold' : state === 'no_route' ? 'v3p_state_no_route' : 'v3p_state_planned';
}

/** The tag's tone: ready is clear green, a waiver or a hold is the decision orange, no route is a fact in ink. */
export function stateTone(state: string): 'ok' | 'decide' | 'neutral' {
	return state === 'approved' ? 'ok' : state === 'conditional' || state === 'hold' ? 'decide' : 'neutral';
}

/** The figures' provenance: the corridor's traffic feed label → the honest tag key, or null when live. */
export function trafficTagKey(label: string | null | undefined): string | null {
	if (label === 'simulated') return 'v3p_sim';
	if (label === 'mixed') return 'v3p_sim_mixed';
	if (label === 'live') return null;
	return 'v3p_sim_unknown';
}

// ── a launch (or a plan) that did not go through ─────────────────────────────

export type FailKind = 'refused' | 'error' | 'no-answer';

/**
 * How a failure the corridor lifecycle reports reads (its text is shown VERBATIM under this lead):
 *   refused    the brain answered in words (a 409's own detail: escortRefusalText keeps it as written);
 *   error      the brain answered with an HTTP error ("503 Service Unavailable: …");
 *   no-answer  nothing came back (the request may or may not have arrived — never called "refused").
 */
export function failKind(text: string | null | undefined): FailKind | null {
	const s = (text ?? '').trim();
	if (!s) return null;
	if (/^(TypeError\b|Failed to fetch|NetworkError|Load failed|The (user|operation) aborted|AbortError|.*\babort(ed)?\b.*request)/i.test(s) || /^net::/i.test(s))
		return 'no-answer';
	if (/^\d{3}\b/.test(s)) return 'error';
	return 'refused';
}

/** The lead sentence's key for a failure kind, for a launch or for a plan. */
export function failLeadKey(kind: FailKind, what: 'launch' | 'plan'): string {
	if (kind === 'no-answer') return what === 'launch' ? 'v3p_fail_launch_none' : 'v3p_fail_plan_none';
	if (kind === 'error') return 'v3p_fail_error';
	return what === 'launch' ? 'v3p_fail_launch_refused' : 'v3p_fail_plan_refused';
}

// ── links ─────────────────────────────────────────────────────────────────────

/** The escort proposal's one decision home (V3 Decide), never carrying a mark. */
export function proposalHref(approvalId: string): string {
	return `/decide/${encodeURIComponent(`escort-proposal:${approvalId}`)}`;
}

/** The corridor event's object page. */
export function eventHref(eventId: string): string {
	return `/o/event:${encodeURIComponent(eventId)}`;
}

/** The plan document's corridor event, if the plan registered one (contract C-I). */
export function planEventId(doc: MovementPlanDoc | null, events: readonly { eventId: string; movementId?: string | null }[], movementId: string | null): string | null {
	if (doc?.event_id) return doc.event_id;
	if (!movementId) return null;
	return events.find((e) => e.movementId === movementId)?.eventId ?? null;
}
