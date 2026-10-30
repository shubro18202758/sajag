/**
 * The wall's bridge to the decision units (wave C). UI-S5A registers the
 * real units source (decisions/register.ts, `registerDecisionUnits(…, {id:
 * 'decisions'})`), and every count of "decisions" — the navbar's Inbox, the
 * metric strip — reads `selectors.decisionUnits()`. Until that source is
 * registered, this one derives the same units from the ops store under the
 * SAME id, so the real source replaces it (registry R27: same id, one
 * entry) and nothing is ever counted twice. Call it AFTER
 * registerProviders(); it does nothing when any units source exists.
 *
 * Units (SPEC §5.4, §7.4 "units = vehicles-with-pending + e-challans +
 * escorts + requests"): one per stolen vehicle with pending
 * R_STOLEN_SIGHTING rows (however many sightings), one per other pending
 * recommendation, one per open escort proposal (time-boxed: its deadline),
 * one per requested dispatch.
 */
import { registerDecisionUnits, registrySize } from '$lib/workspace/registry';
import type { DecisionUnitSummary } from '$lib/workspace/types';
import type { DispatchRecord, EnforcementRecommendation, EscortProposal } from '$lib/ops/types';

export const UNITS_SOURCE_ID = 'decisions';

const OPS_HOMES = { '/': 'inbox', '/gods-eye': 'inbox', '/ops': 'decisions' } as const;
const ESCORT_HOMES = { '/': 'movement', '/gods-eye': 'movement', '/ops': 'decisions' } as const;

export interface UnitInputs {
	recommendations: readonly EnforcementRecommendation[];
	escorts: readonly EscortProposal[];
	dispatches: readonly DispatchRecord[];
	/** A registration mark as this console may print it. */
	plate: (raw: string | null) => string | null;
}

/** Pure: the decision units the ops store's pending items make. Exported for tests. */
export function unitsFrom(i: UnitInputs): DecisionUnitSummary[] {
	const out: DecisionUnitSummary[] = [];
	const stolen = new Map<string, EnforcementRecommendation[]>();
	for (const r of i.recommendations) {
		if (r.status !== 'pending') continue;
		if (r.ruleId === 'R_STOLEN_SIGHTING' && r.vehicleId) {
			const list = stolen.get(r.vehicleId);
			if (list) list.push(r);
			else stolen.set(r.vehicleId, [r]);
			continue;
		}
		out.push({
			kind: 'echallan',
			id: r.recommendationId,
			subjectUrn: r.vehicleId ? `vehicle:${r.vehicleId}` : `recommendation:${r.recommendationId}`,
			title: i.plate(r.plate) ?? r.recommendationId.slice(0, 8),
			deadline: null,
			severity: 2,
			homes: { ...OPS_HOMES },
		});
	}
	for (const [vehicleId, recs] of stolen) {
		out.push({
			kind: 'stolen-sighting',
			id: vehicleId,
			subjectUrn: `vehicle:${vehicleId}`,
			title: i.plate(recs[0].plate) ?? vehicleId.slice(0, 8),
			deadline: null,
			severity: 3,
			homes: { ...OPS_HOMES },
		});
	}
	for (const p of i.escorts) {
		out.push({
			kind: 'escort-proposal',
			id: p.approvalId,
			subjectUrn: `convoy:${p.movementId}`,
			title: p.kind,
			deadline: p.expiresAt ?? null,
			severity: 3,
			homes: { ...ESCORT_HOMES },
		});
	}
	for (const d of i.dispatches) {
		if (d.status !== 'requested') continue;
		out.push({
			kind: 'corridor-request',
			id: d.dispatchId,
			subjectUrn: `dispatch:${d.dispatchId}`,
			title: d.unitId ?? d.dispatchId.slice(0, 8),
			deadline: null,
			severity: 2,
			homes: { ...OPS_HOMES },
		});
	}
	return out;
}

/** Register the bridge source when (and only when) no units source exists. */
export function ensureUnitsSource(read: () => UnitInputs): boolean {
	if (registrySize().units > 0) return false;
	registerDecisionUnits(() => unitsFrom(read()), { id: UNITS_SOURCE_ID });
	return true;
}
