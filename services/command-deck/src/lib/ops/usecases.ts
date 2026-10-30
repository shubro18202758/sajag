/**
 * The corridor-event use-case profiles: the eight seeded event profiles
 * (migration 008) and the five city-feeds scenarios (a market fire, a river
 * release with waterlogging, festival-night air quality, a heatwave and a
 * Nor'wester). Every one is SIMULATED.
 *
 * Every field is the emulator's use-case library's (event-emulator
 * use_case_library.json: scenario_id, route spine, seed, baseline closure
 * policy, departure, replications, horizon, name, description, event kind,
 * crowd and protection class), generated into usecases.generated.ts by
 * scripts/gen_deck_usecases.mjs — a new city's library is one regenerated
 * module. The route spines are the library's on the city's (OpenStreetMap)
 * network, cities/<id>/network.json — each a legal path, one-ways driven
 * their own way (the contract tests hold them equal). They serve three
 * purposes:
 *
 *   1. OFFLINE FIXTURES for the multi-event board when GET /api/v1/events/active
 *      is not deployed yet (rows are tagged `offline-fixture` and labelled).
 *   2. Scenario picker + explicit fields for the twin shadow-eval panel.
 *   3. Launch presets surfaced to the emulator panel (use_case_id values).
 *
 * event_kind and crowd_class are the showcase's mapping of each profile onto
 * the generalized axes; the mapping follows the profile descriptions.
 */

import { USE_CASE_ROWS } from './usecases.generated';
import type {
	ClosurePolicySpec,
	CrowdClass,
	EventKind,
	EventPhase,
	ProtectionClass,
} from './types';

export interface UseCaseProfile {
	id: string;
	scenarioId: string;
	name: string;
	eventKind: EventKind;
	protectionClass: ProtectionClass;
	crowdClass: CrowdClass;
	routeSegmentIds: number[];
	departureTime: string; // ISO 8601 with +05:30
	baselinePolicy: ClosurePolicySpec;
	seed: number;
	nReplications: number;
	horizonMin: number;
	phases: EventPhase[];
	description: string;
}

const ISO_IST = (d: string) => d; // configs already carry +05:30 offsets

function movementPhases(
	departure: string,
	horizonMin: number,
	policy: ClosurePolicySpec,
	extra?: EventPhase[],
): EventPhase[] {
	const start = new Date(departure).toISOString();
	const end = new Date(new Date(departure).getTime() + horizonMin * 60_000).toISOString();
	const main: EventPhase = {
		label: 'movement window',
		startTime: start,
		endTime: end,
		closurePolicy: {
			advanceClosureSec: policy.advanceClosureSec,
			closureType: policy.closureType,
		},
		state: 'planned',
	};
	return extra ? [...extra, main] : [main];
}

/**
 * The deck's own schedule windows before a scenario's movement window (a festival's nights, a camp's days, a published
 * work zone), by use-case id: shown on the board as the event's earlier phases. A library scenario without one has the
 * movement window only.
 */
const EXTRA_PHASES: Readonly<Record<string, EventPhase[]>> = {
	ganesh_visarjan_girgaon: [
		{
			label: 'Ganeshotsav nights (pandal darshan, 18:00–04:00 daily)',
			startTime: '2025-09-04T12:30:00.000Z',
			endTime: '2025-09-06T22:30:00.000Z',
			closurePolicy: null,
			state: 'planned',
		},
	],
	gateway_ferry_transit: [
		{
			label: 'Gateway of India ferry wharf (multi-day schedule, holiday crowds)',
			startTime: '2027-01-09T18:30:00.000Z',
			endTime: null,
			closurePolicy: null,
			state: 'planned',
		},
	],
	metro_work_zone: [
		{
			label: 'published lane loss — Diamond Harbour Road (Metro works, 1 Oct – 31 Dec)',
			startTime: '2026-09-30T18:30:00.000Z',
			endTime: '2026-12-30T18:30:00.000Z',
			closurePolicy: { advanceClosureSec: null, closureType: 'partial_closure' },
			state: 'planned',
		},
	],
};

export const USE_CASES: UseCaseProfile[] = USE_CASE_ROWS.map((r) => {
	const policy = { advanceClosureSec: r.baselinePolicy.advanceClosureSec, closureType: r.baselinePolicy.closureType } as ClosurePolicySpec;
	return {
		id: r.id,
		scenarioId: r.scenarioId,
		name: r.name,
		eventKind: r.eventKind as EventKind,
		protectionClass: r.protectionClass as ProtectionClass,
		crowdClass: r.crowdClass as CrowdClass,
		routeSegmentIds: [...r.routeSegmentIds],
		departureTime: ISO_IST(r.departureTime),
		baselinePolicy: policy,
		seed: r.seed,
		nReplications: r.nReplications,
		horizonMin: r.horizonMin,
		phases: movementPhases(r.departureTime, r.horizonMin, policy, EXTRA_PHASES[r.id]),
		description: r.description,
	};
});

/** The library's flagship (its description opens with "FLAGSHIP."), else the first crowd scenario, else the first. */
export const FLAGSHIP_USE_CASE: UseCaseProfile | undefined =
	USE_CASES.find((u) => /^FLAGSHIP\b/.test(u.description)) ?? USE_CASES.find((u) => u.eventKind === 'mass_gathering' || u.eventKind === 'procession') ?? USE_CASES[0];

export function useCaseById(id: string): UseCaseProfile | undefined {
	return USE_CASES.find((u) => u.id === id || u.scenarioId === id);
}
