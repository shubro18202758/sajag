/**
 * Decision link cards for objects a unit TOUCHES but is not about (SPEC
 * §5.4 "one unit, one home"; §14.2 S5: decision sections for vehicle,
 * event, recommendation, dispatch and junction). The inspector's Actions
 * tab already links every unit whose subject is the object; this adds the
 * rest, so a pending R_STOLEN_SIGHTING recommendation opened on its own
 * still says where its vehicle's decision is made:
 *
 *   stolen-sighting   each pending sighting and the unspent approval
 *                     (recommendation:<id>); the subject is the vehicle
 *   echallan          the vehicle it would fine (vehicle:<id>)
 *   corridor-request  the 108 request's event and waypoint junction
 *
 * Link cards only: no decision verb is ever rendered here (the decision's
 * one home per route carries it).
 */
import type { DecisionUnitSummary } from '$lib/workspace/types';
import { corridorOf, decisionUnits, echallanOf, stolenOf, type Unit } from '../units';
import { homeOf } from '../homes';

/** The URNs a unit's decision touches besides its subject. */
export function unitRefs(u: Unit): string[] {
	if (u.kind === 'stolen-sighting') {
		const d = stolenOf(u);
		const ids = [...d.recs.map((r) => r.recommendationId), ...(d.approved ? [d.approved.recommendationId] : [])];
		return [...new Set(ids)].map((id) => `recommendation:${id}`);
	}
	if (u.kind === 'echallan') {
		const v = echallanOf(u).rec.vehicleId;
		return v ? [`vehicle:${v}`] : [];
	}
	if (u.kind === 'corridor-request') {
		const d = corridorOf(u).dispatch;
		return [...(d.eventId ? [`event:${d.eventId}`] : []), ...(d.waypointJunction != null ? [`junction:${d.waypointJunction}`] : [])];
	}
	return [];
}

/** Units whose decision touches `urn` while their subject is another object (link cards, never a verb). */
export function unitsReferencing(urn: string, units: readonly Unit[] = decisionUnits()): Unit[] {
	if (!urn) return [];
	return units.filter((u) => u.subjectUrn !== urn && unitRefs(u).includes(urn));
}

/** The registry's summary of a unit (for workspace.openDecisionHome). */
export function summaryOf(u: Unit): DecisionUnitSummary {
	return {
		kind: u.kind,
		id: u.id,
		subjectUrn: u.subjectUrn,
		title: u.title,
		deadline: u.deadline,
		severity: u.severity,
		homes: { '/': homeOf(u.kind, '/'), '/gods-eye': homeOf(u.kind, '/gods-eye'), '/ops': homeOf(u.kind, '/ops') },
	};
}

/** The object kinds the link section is registered for. */
export const LINK_KINDS = ['recommendation', 'vehicle', 'event', 'dispatch', 'junction'] as const;
