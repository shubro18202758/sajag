/**
 * Active events (SPEC §5.3 Explorer, §9.2, §12.4) — the words and the row
 * facts the ActiveEvents list renders, exported pure for
 * tests/corridor.unit.mjs: the compact provenance glyph's hidden text is
 * exactly "Emulated", the rehearsal label's visible tag reads exactly
 * "Test" (its title carries the plan label), and a promoted OSINT report
 * carries its verification tag.
 */
import type { CorridorEvent, SourceKind, VerificationState } from '$lib/ops/types';

/** The compact emulated glyph's hidden text (X2 labels; ops-wall-smoke:1420). */
export const EMULATED_TEXT = 'Emulated';

/** The rehearsal tag's visible text (ops-wall-smoke:1545). */
export const TEST_TEXT = 'Test';

/**
 * The traffic flow's provenance label, the way the wall's metric strip
 * derives it (audit C S2): the traffic feed's own label wins; before it has
 * answered, the corridor summary's provenance stands in — an emulated
 * summary reads as 'simulated'. 'mixed' rides through: a partly simulated
 * feed is still a simulated flow. The /ops map tile's legend takes its
 * "Simulated flow" item from this, never from the feed alone.
 */
export function flowProvenance(trafficLabel: string | null | undefined, summaryProvenance: string | null | undefined): string | null {
	if (trafficLabel) return trafficLabel;
	if (summaryProvenance == null) return null;
	return summaryProvenance === 'emulated' ? 'simulated' : summaryProvenance;
}

/** Where an event row's provenance shows (never for a live row). */
export function eventProvenance(ev: CorridorEvent): 'emulated' | 'osint' | null {
	if (ev.sourceKind === 'osint') return 'osint';
	return ev.emulated ? 'emulated' : null;
}

/** The row's verification tag (a promoted OSINT report's C-T state). */
export function eventVerification(ev: CorridorEvent): VerificationState | null {
	return ev.sourceKind === 'osint' ? (ev.verificationState ?? null) : null;
}

/** The rehearsal label (event metadata.label) — the Test tag's title carries it. */
export function eventTestLabel(ev: CorridorEvent): string | null {
	const label = ev.metadata?.label;
	return typeof label === 'string' && label.trim() ? label.trim() : null;
}

/** Events the Active events list shows: live board rows (never fixtures), openest-first. */
export function activeEventRows(events: readonly CorridorEvent[]): CorridorEvent[] {
	return events
		.filter((e) => e.source !== 'offline-fixture')
		.slice()
		.sort((a, b) => order(a) - order(b) || (a.eventId < b.eventId ? -1 : 1));
}

const OPEN: Record<string, number> = { active: 0, live: 0, approved: 1, planning: 2, planned: 2 };
const order = (e: CorridorEvent): number => OPEN[e.state] ?? 3;

/** The source kind the row's glyph shows (event kind, never a person). */
export function rowSourceKind(ev: CorridorEvent): SourceKind | null {
	return ev.sourceKind ?? null;
}
