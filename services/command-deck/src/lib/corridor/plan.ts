/**
 * The corridor plan's state machine (SPEC §5.3 PlanPanel [S6], capabilities
 * 15–16) — pure functions over the plan document (contract C-I), so the
 * PlanPanel renders from them and tests/corridor.unit.mjs drives them from
 * fixtures.
 *
 *   approved     the plan may depart; escort offered
 *   conditional  the lane-floor violations are listed; LAUNCH stays locked
 *                until the officer accepts the waiver (planner-waiver) AND
 *                a duty officer is named — the inline Reason says which
 *   hold         the decider delayed departure ("Re-plan after hh:mm");
 *                Launch is locked
 *   no_route     no candidates; Launch is HIDDEN and the status gives the
 *                reason and the next action
 *
 * A hold may also ride a conditional plan (doc.hold): it wins — a plan that
 * cannot depart never launches, whatever its protocol tier says.
 */
import type { MovementPlanDoc, PlanRouteCandidate } from '$lib/api/client';

export type PlanState = 'none' | 'approved' | 'conditional' | 'hold' | 'no_route';

export interface PlanView {
	state: PlanState;
	/** The decider delayed departure (a hold riding a conditional plan counts). */
	held: boolean;
	/** The plan is conditional and the waiver is still open. */
	needsWaiver: boolean;
	/** A plan that may depart at all (approved, or conditional whose waiver can still be given). */
	escortOffered: boolean;
	/** Launch is disabled right now. */
	launchLocked: boolean;
	/** Why (the inline Reason under the launch control), or null. */
	launchLockReason: string | null;
}

export interface PlanViewCopy {
	waiverNeeded: string;
	holdLocked: string;
	officerNeeded: string;
	noPlan: string;
}

/** The plan's own state, with a hold riding a conditional plan winning. */
export function planStateOf(doc: MovementPlanDoc | null): Exclude<PlanState, 'none'> | 'none' {
	if (!doc) return 'none';
	const status = doc.status ?? (doc.primary_route ? 'approved' : 'no_route');
	if (status === 'hold' || doc.hold === true) return 'hold';
	if (status === 'conditional') return 'conditional';
	if (status === 'no_route') return 'no_route';
	return 'approved';
}

/** The lane-floor violations the plan itself lists (its conditional reason). */
export function planViolations(doc: MovementPlanDoc | null): { segmentId: number | null; detail: string }[] {
	if (!doc) return [];
	const out: { segmentId: number | null; detail: string }[] = [];
	for (const r of routeCandidates(doc)) {
		for (const v of r.lane_violations ?? []) {
			out.push({ segmentId: v.segment_id ?? null, detail: v.detail ?? v.type ?? 'lane floor' });
		}
	}
	return out;
}

/** Primary first, then the alternates, each once. */
export function routeCandidates(doc: MovementPlanDoc | null): PlanRouteCandidate[] {
	if (!doc) return [];
	return [doc.primary_route, ...(doc.alternate_routes ?? [])].filter((r): r is PlanRouteCandidate => r != null);
}

/**
 * The launch gate (capability 15): locked until the waiver is accepted and
 * an officer is named — the Reason names whichever is missing first.
 */
export function launchGate(
	doc: MovementPlanDoc | null,
	opts: { waiverAccepted: boolean; officerNamed: boolean },
	copy: PlanViewCopy,
): PlanView {
	const state = planStateOf(doc);
	const held = state === 'hold';
	const candidates = routeCandidates(doc);
	const escortOffered = !!doc && state !== 'no_route' && !held && candidates.length > 0;
	const needsWaiver = state === 'conditional' && !opts.waiverAccepted;
	let lockReason: string | null = null;
	if (!doc) lockReason = copy.noPlan;
	else if (held) lockReason = copy.holdLocked;
	else if (!escortOffered) lockReason = copy.noPlan;
	else if (needsWaiver) lockReason = copy.waiverNeeded;
	else if (!opts.officerNamed) lockReason = copy.officerNeeded;
	return { state, held, needsWaiver, escortOffered, launchLocked: lockReason != null, launchLockReason: lockReason };
}

/**
 * "adds <roads>" — the roads an alternate takes that the primary does not
 * (by signage name; segment ids as the fallback). Figures the plan does not
 * report are never invented: with no road names on either side the label is
 * the honest "adds no new road".
 */
export function candidateAdds(route: PlanRouteCandidate, primary: PlanRouteCandidate | null | undefined): string[] {
	const roadsOf = (r: PlanRouteCandidate | null | undefined): string[] =>
		(r?.road_names ?? []).map((s) => s.trim()).filter(Boolean);
	const have = new Set(roadsOf(primary));
	return roadsOf(route).filter((s) => !have.has(s));
}

/** The "adds" sentence's roads text: two names, then "+n". */
export function addsText(roads: readonly string[]): string {
	if (!roads.length) return '';
	return roads.length > 2 ? `${roads.slice(0, 2).join(', ')} +${roads.length - 2}` : roads.join(', ');
}
