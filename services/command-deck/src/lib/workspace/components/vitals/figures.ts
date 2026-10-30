/**
 * The City vitals card's figures (SPEC §6.2, §7.4) — one selector per
 * quantity, so the card and the Explorer can never disagree:
 *
 *   open events           corridor events planned, approved or running
 *                         (registry rows, test objects left out)
 *   decisions waiting     decisionUnits() — the Inbox's, the navbar's and the
 *                         Watches' count (units, not rows). Until a decision
 *                         provider registers a unit source, the units are
 *                         counted from the registry by the same rule
 *                         (§7.4: vehicles with a pending sighting + e-challans
 *                         + escort proposals + dispatch requests)
 *   watchlisted vehicles  count('vehicle') — the registry count, the same
 *                         figure as the Explorer
 *   cameras answering     cameras the registry lists as active, of count('camera')
 *   feed anomalies        count('anomaly') — roads with an anomaly in 15 min
 *   reported events       count('osint_event'), shown only when there are any
 *   traffic feed          its provenance: simulated when the corridor summary
 *                         says so or a road's observation is synthetic
 *
 * Pure: the selectors and the registry rows are passed in.
 */
import type { Selectors } from '../../selectors';
import type { ObjectRow } from '../../types';
import { OPEN_EVENT_STATES } from '../explorer/model';

export interface CardFigures {
	openEvents: number;
	decisions: number;
	/** True when the count is decisionUnits() (a unit source is registered). */
	decisionsFromUnits: boolean;
	watchlisted: number;
	cameras: { answering: number; total: number };
	anomalies: number;
	reported: number;
	trafficSimulated: boolean;
}

export interface CardInput {
	selectors: Pick<Selectors, 'count' | 'decisionUnits'>;
	/** The registry snapshot's rows (liveWorld.registry()). */
	registry: readonly ObjectRow[];
	/** How many decision-unit sources are registered (registrySize().units). */
	unitSources: number;
	/** Escort proposals waiting (they are not registry objects). */
	escortProposals?: number;
	/** The corridor summary says the traffic feed is simulated. */
	corridorSimulated?: boolean;
}

/** A recommendation that is evidence (a stolen-vehicle sighting: a pursuit authorisation, never a fine). */
export function isEvidenceRec(props: Readonly<Record<string, unknown>>): boolean {
	return props.rule_kind === 'evidence' || (props.rule_kind == null && props.rule_id === 'R_STOLEN_SIGHTING');
}

/** The fields the unit rule reads (an ObjectRow or a registry CityEntity). */
export interface UnitInput {
	urn: string;
	kind: string;
	state: string | null;
	test?: boolean;
	props: Readonly<Record<string, unknown>>;
}

const isEvidence = (r: UnitInput) => isEvidenceRec(r.props);

/**
 * Decision units counted from the registry (no unit source registered yet):
 * one per vehicle with a pending stolen-vehicle sighting, one per pending
 * e-challan, one per dispatch request, one per escort proposal.
 */
export function registryUnits(registry: readonly UnitInput[], escortProposals = 0): number {
	const vehicles = new Set<string>();
	let echallans = 0;
	let requests = 0;
	for (const r of registry) {
		if (r.test) continue;
		if (r.kind === 'recommendation' && r.state === 'pending') {
			if (isEvidence(r)) vehicles.add(typeof r.props.vehicle_id === 'string' ? r.props.vehicle_id : r.urn);
			else echallans++;
		} else if (r.kind === 'dispatch' && r.state === 'requested') requests++;
	}
	return vehicles.size + echallans + requests + Math.max(0, escortProposals);
}

/**
 * Decisions waiting, as units — THE count the card, the Info tab and the
 * Explorer's Watches ("Decision needed") all show: decisionUnits() once a
 * decision provider registers a unit source (the Inbox's and the navbar's
 * count), else the same §7.4 rule on the registry (registryUnits), so no two
 * surfaces disagree before the provider loads.
 */
export function decisionsWaiting(input: {
	selectors: Pick<Selectors, 'decisionUnits'>;
	registry: readonly UnitInput[];
	unitSources: number;
	escortProposals?: number;
}): { n: number; fromUnits: boolean } {
	const fromUnits = input.unitSources > 0;
	return { n: fromUnits ? input.selectors.decisionUnits().length : registryUnits(input.registry, input.escortProposals ?? 0), fromUnits };
}

/** True when any road's observation is synthetic (the traffic feed is simulated). */
export function roadsSimulated(registry: readonly ObjectRow[]): boolean {
	return registry.some((r) => (r.kind === 'segment' || r.kind === 'anomaly') && r.source === 'simulated');
}

export function cardFigures(input: CardInput): CardFigures {
	const { selectors: q, registry } = input;
	const waiting = decisionsWaiting(input);
	let openEvents = 0;
	let answering = 0;
	for (const r of registry) {
		if (r.test) continue;
		if (r.kind === 'event' && (r.state == null || OPEN_EVENT_STATES.has(r.state))) openEvents++;
		if (r.kind === 'camera' && r.state === 'active') answering++;
	}
	return {
		openEvents,
		decisions: waiting.n,
		decisionsFromUnits: waiting.fromUnits,
		watchlisted: q.count('vehicle'),
		cameras: { answering, total: q.count('camera') },
		anomalies: q.count('anomaly'),
		reported: q.count('osint_event'),
		trafficSimulated: !!input.corridorSimulated || roadsSimulated(registry),
	};
}
