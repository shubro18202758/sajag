/**
 * A corridor event's open-source provenance, as the wall shows it (SPEC §9.2;
 * OSINT SPEC §0.5; ethics rule 7).
 *
 * A promoted OSINT event (`sourceKind === 'osint'`) states, VISIBLY, how far
 * its report has been verified, and its credibility. The label is the same
 * one ProvenanceTag prints for that state, so the row and the tag never
 * disagree:
 *   UNVERIFIED-OSINT   "Unverified OSINT"
 *   NEWS-REPORTED      "News-reported"
 *   OFFICIAL-VERIFIED  "Official, verified"
 *   CONFIRMED          "Confirmed by officer"
 *   anything else      "Open-source" (no state claimed)
 * Credibility is shown only when it is a number in 0..1, as "credibility 0.65".
 * A non-OSINT event has no open-source provenance: null.
 */
import { t } from '$lib/i18n/strings';
import '$lib/i18n/packs.ui';
import '$lib/i18n/packs.wall';
import { titleParts } from '$lib/workspace/display';
import type { CorridorEvent } from '$lib/ops/types';

export const OSINT_STATES = ['UNVERIFIED-OSINT', 'NEWS-REPORTED', 'OFFICIAL-VERIFIED', 'CONFIRMED'] as const;
export type OsintState = (typeof OSINT_STATES)[number];

const LABEL_KEY: Record<OsintState, string> = {
	'UNVERIFIED-OSINT': 'ui_verif_unverified',
	'NEWS-REPORTED': 'ui_verif_news',
	'OFFICIAL-VERIFIED': 'ui_verif_official',
	CONFIRMED: 'ui_verif_confirmed',
};

export interface EventProvenance {
	source: 'osint';
	/** One of the four open-source states, or null when the event states none this console knows. */
	verification: OsintState | null;
	/** The visible verification label. */
	label: string;
	/** 0..1, or null when the event carries none (or a value out of range). */
	credibility: number | null;
	/** "credibility 0.65", or null. */
	credibilityText: string | null;
}

type ProvenanceFields = Pick<CorridorEvent, 'sourceKind' | 'verificationState' | 'credibility'>;

/** The open-source state of an event, or null for any value that is not one of the four. */
export function osintState(ev: Pick<CorridorEvent, 'verificationState'>): OsintState | null {
	const v = ev.verificationState;
	return typeof v === 'string' && (OSINT_STATES as readonly string[]).includes(v) ? (v as OsintState) : null;
}

/** The event's open-source provenance for display, or null when it is not an OSINT event. */
export function eventProvenance(ev: ProvenanceFields, lang = 'en'): EventProvenance | null {
	if (ev.sourceKind !== 'osint') return null;
	const verification = osintState(ev);
	const label = t(lang, verification ? LABEL_KEY[verification] : 'ui_prov_osint');
	const c = ev.credibility;
	const credibility = typeof c === 'number' && Number.isFinite(c) && c >= 0 && c <= 1 ? c : null;
	return {
		source: 'osint',
		verification,
		label,
		credibility,
		credibilityText: credibility == null ? null : t(lang, 'wall_ops_credibility', credibility.toFixed(2)),
	};
}

// ── the row provenance rule (SPEC §9.2) ─────────────────────────────────────

type RowFields = Pick<CorridorEvent, 'name' | 'metadata' | 'emulated'>;

/**
 * A test or rehearsal event: its title carries a test label (stripped by the
 * display layer) or its metadata a label. Such a row ALWAYS carries a visible
 * "Test" tag, and is kept out of the wall's counts.
 */
export function isTestEvent(ev: Pick<CorridorEvent, 'name' | 'metadata'>): boolean {
	return titleParts(ev.name ?? '').test || !!ev.metadata?.label;
}

/** The scenario emulator staged the event (its flag, or the "(Emulated)" its title carried). */
export function isEmulatedEvent(ev: RowFields): boolean {
	return !!ev.emulated || titleParts(ev.name ?? '').emulated;
}

/** The events that count: test and rehearsal rows are left out (SPEC §9.2). */
export function countable<T extends Pick<CorridorEvent, 'name' | 'metadata'>>(events: readonly T[]): T[] {
	return events.filter((e) => !isTestEvent(e));
}

/** The wall's "N in history" (F-13): the history's events that count — test and rehearsal rows left out, like the open count beside it. */
export function historyCount(history: ReadonlyArray<{ event: Pick<CorridorEvent, 'name' | 'metadata'> }>): number {
	return countable(history.map((h) => h.event)).length;
}

/**
 * A uniform list states its provenance once, in the header, and its rows carry
 * none; a mixed list marks each emulated row with the compact glyph. Returns
 * 'emulated' when EVERY row of a non-empty list is emulated, else null.
 */
export function uniformProvenance(rows: readonly RowFields[]): 'emulated' | null {
	return rows.length > 0 && rows.every(isEmulatedEvent) ? 'emulated' : null;
}

/** The header's one statement for a uniform list: "Emulated" (one row) or "All 12 emulated". */
export function uniformLabel(n: number, lang = 'en'): string {
	return n === 1 ? t(lang, 'ui_prov_emulated') : t(lang, 'wall_ops_all_emulated', n);
}
