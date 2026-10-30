/**
 * Advisories' pure view model (V3-SPEC §6.7) — no store, no DOM, so tests/v3-comms.unit.mjs drives it directly.
 *
 * The withholding RULES are not here: they stay in $lib/comms/{advisory,osint}.ts and the route (fail-closed, badge once,
 * empty columns hidden). This file only shapes what is shown around them: the draft's quiet exercise tag, the facts that
 * were used, the roving keys of the event list.
 */
import type { AdvisoryFacts } from '$lib/comms/advisory';

/** The draft text without its leading bracketed marker (the exercise prefix, or an OSINT label), and the marker. */
export function splitMarker(text: string): { marker: string | null; rest: string } {
	const m = text.match(/^\[[^\]]+\]\s*/);
	return m ? { marker: m[0].trim(), rest: text.slice(m[0].length) } : { marker: null, rest: text };
}

/** One line of the "Facts used" disclosure. `value` is null when the feed did not state it. */
export interface FactRow {
	key: 'kind' | 'road' | 'hold' | 'when' | 'alt';
	value: string | null;
}

/**
 * The facts a draft was written from, in the order an officer checks them. A fact that was READ but is not stated
 * (value null) and a fact whose read FAILED are told apart by the caller (it passes the words); here null only means
 * "nothing to print".
 */
export function factRows(
	facts: AdvisoryFacts,
	w: { kind: string; hold: string | null; when: string; alt: string | null },
): FactRow[] {
	return [
		{ key: 'kind', value: w.kind },
		{ key: 'road', value: facts.stretch.roadName },
		{ key: 'hold', value: w.hold },
		{ key: 'when', value: facts.holdMinutes != null ? w.when : null },
		{ key: 'alt', value: w.alt },
	];
}

/** Arrow-key movement in the event list (a radio group): the index to focus, wrapping; null for any other key. */
export function rovingIndex(key: string, current: number, count: number): number | null {
	if (count <= 0) return null;
	if (key === 'ArrowDown' || key === 'ArrowRight') return (current + 1) % count;
	if (key === 'ArrowUp' || key === 'ArrowLeft') return (current - 1 + count) % count;
	if (key === 'Home') return 0;
	if (key === 'End') return count - 1;
	return null;
}

/**
 * What the event list marks on a row. The row mark is a HINT from the board row (kind and provenance); the one statement
 * of a withholding is the badge on the selected event's header, driven by the resolved facts.
 */
export function rowWithheld(ev: { eventKind: string }, isPublic: (kind: string) => boolean, osint: unknown): boolean {
	return !!osint || !isPublic(ev.eventKind);
}
