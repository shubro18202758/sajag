/**
 * The comms desk's OSINT rule (plan X17, the public firewall's desk face).
 *
 * An OSINT-sourced event — the oracle's provenance column (021: source_kind
 * 'osint') or a metadata.source 'osint' marker, exactly the predicate the
 * public projection drops (public-api.server.ts isOsintRow) — is WITHHELD
 * from the two audiences outside the control room: citizens and 108
 * control (who pass it on to drivers). A promoted report of a PUBLIC kind
 * (a mass gathering, a procession) is withheld too: promotion lets officers
 * RESPOND to a reported situation; it does not verify it for the public.
 * No copyable draft and no all-clear is composed for those audiences; the
 * desk says why, with the report's verification label (the same pack text
 * ProvenanceTag prints: "Unverified OSINT", "News-reported", …).
 *
 * Zone officers and the municipal desk still get their drafts, each opening
 * with the verification label, so a copied internal draft can never pass
 * for a verified road hold.
 *
 * Pure (no reads): comms/facts.ts sets AdvisoryFacts.osint from the event
 * row, advisory.ts withholds on it, and the page reads commsWithholding()
 * for the badge.
 */

import { registerPack, t } from '$lib/i18n/strings';
import '$lib/i18n/packs.ui';
import type { Audience } from './advisory';

/** The honest labels an open-source report can carry (migration 021). */
export const OSINT_STATES = ['UNVERIFIED-OSINT', 'NEWS-REPORTED', 'OFFICIAL-VERIFIED', 'CONFIRMED'] as const;
export type OsintState = (typeof OSINT_STATES)[number];

/** The ui pack keys ProvenanceTag prints for each state (packs.ui.ts). */
const LABEL_KEY: Record<OsintState, string> = {
	'UNVERIFIED-OSINT': 'ui_verif_unverified',
	'NEWS-REPORTED': 'ui_verif_news',
	'OFFICIAL-VERIFIED': 'ui_verif_official',
	CONFIRMED: 'ui_verif_confirmed',
};

/** The audiences an OSINT-sourced event is never drafted for. */
export const OSINT_WITHHELD_AUDIENCES: readonly Audience[] = ['citizens', 'ambulance108'];

/** An event's open-source mark: how far its report is verified (null = no state stated). */
export interface OsintMark {
	verification: OsintState | null;
}

/** The provenance an event row carries (ops-board CorridorEvent or the raw wire row). */
export interface OsintFields {
	sourceKind?: string | null;
	verificationState?: string | null;
	metadata?: { source?: string | null } | null;
}

/** Whether an event is OSINT-sourced: source_kind 'osint' or metadata.source 'osint'. */
export function isOsintSourced(ev: OsintFields | null | undefined): boolean {
	return !!ev && (ev.sourceKind === 'osint' || ev.metadata?.source === 'osint');
}

/** One of the four open-source states, or null for anything else. */
export function osintState(v: unknown): OsintState | null {
	return typeof v === 'string' && (OSINT_STATES as readonly string[]).includes(v) ? (v as OsintState) : null;
}

/** The event's open-source mark, or null when it is not OSINT-sourced. */
export function osintMarkOf(ev: OsintFields | null | undefined): OsintMark | null {
	return isOsintSourced(ev) ? { verification: osintState(ev?.verificationState) } : null;
}

/** The raw events-API row's provenance in OsintFields form (snake_case wire keys). */
export function osintFieldsOfRow(row: Record<string, unknown>): OsintFields {
	const meta = row.metadata && typeof row.metadata === 'object' ? (row.metadata as Record<string, unknown>) : null;
	return {
		sourceKind: typeof row.source_kind === 'string' ? row.source_kind : null,
		verificationState: typeof row.verification_state === 'string' ? row.verification_state : null,
		metadata: { source: typeof meta?.source === 'string' ? meta.source : null },
	};
}

/** Whether `audience` must not receive a draft of an event with this mark. */
export function osintWithheldFrom(mark: OsintMark | null | undefined, audience: Audience): boolean {
	return !!mark && OSINT_WITHHELD_AUDIENCES.includes(audience);
}

/** The visible verification label ("Unverified OSINT", "News-reported", … or "Open-source"). */
export function osintLabel(mark: OsintMark, lang: string): string {
	return t(lang, mark.verification ? LABEL_KEY[mark.verification] : 'ui_prov_osint');
}

/** The withheld notice a citizen or 108 draft of an OSINT event shows instead of text. */
export function osintWithheldText(mark: OsintMark, lang: string): string {
	if (!mark.verification) return t(lang, 'comms_osint_withheld_unstated');
	return t(lang, 'comms_osint_withheld', osintLabel(mark, lang));
}

/** The marker an internal (zone / municipal) draft of an OSINT event opens with. */
export function osintDraftMarker(mark: OsintMark, lang: string): string {
	if (!mark.verification) return t(lang, 'comms_osint_marker_unstated');
	return t(lang, 'comms_osint_marker', osintLabel(mark, lang));
}

/** What the desk shows for an OSINT event: the badge text, its label and the withheld audiences. */
export interface CommsWithholding {
	badge: string;
	label: string;
	audiences: readonly Audience[];
}

/**
 * The comms-withheld-badge for an OSINT-sourced event (null otherwise): its
 * text names the verification label and the audiences it is withheld from.
 */
export function commsWithholding(mark: OsintMark | null | undefined, lang: string): CommsWithholding | null {
	if (!mark) return null;
	const label = osintLabel(mark, lang);
	return { badge: t(lang, 'comms_osint_badge', label), label, audiences: OSINT_WITHHELD_AUDIENCES };
}

registerPack('en', {
	comms_osint_withheld: (label: unknown) =>
		`Open-source report (${String(label)}) — no citizen or 108 advisory is drafted for it.`,
	comms_osint_badge: (label: unknown) => `${String(label)} — withheld from citizens and 108`,
	comms_osint_marker: (label: unknown) => `[${String(label)} — open-source report]`,
	comms_osint_withheld_unstated:
		'Open-source report, no verification stated — no citizen or 108 advisory is drafted for it.',
	comms_osint_marker_unstated: '[Open-source report, no verification stated]',
});
registerPack('hi', {
	comms_osint_withheld: (label: unknown) =>
		`खुले स्रोत की रिपोर्ट (${String(label)}) — इसके लिए नागरिक या 108 सलाह नहीं बनाई जाती।`,
	comms_osint_badge: (label: unknown) => `${String(label)} — नागरिकों और 108 से रोका गया`,
	comms_osint_marker: (label: unknown) => `[${String(label)} — खुले स्रोत की रिपोर्ट]`,
	comms_osint_withheld_unstated:
		'खुले स्रोत की रिपोर्ट, कोई सत्यापन नहीं बताया गया — इसके लिए नागरिक या 108 सलाह नहीं बनाई जाती।',
	comms_osint_marker_unstated: '[खुले स्रोत की रिपोर्ट, कोई सत्यापन नहीं बताया गया]',
});
registerPack('mr', {
	comms_osint_withheld: (label: unknown) =>
		`खुल्या स्रोताचा अहवाल (${String(label)}) — यासाठी नागरिक किंवा 108 साठी कोणतीही सूचना तयार केली जात नाही.`,
	comms_osint_badge: (label: unknown) => `${String(label)} — नागरिक आणि 108 पासून रोखले`,
	comms_osint_marker: (label: unknown) => `[${String(label)} — खुल्या स्रोताचा अहवाल]`,
	comms_osint_withheld_unstated:
		'खुल्या स्रोताचा अहवाल, पडताळणीचा उल्लेख नाही — यासाठी नागरिक किंवा 108 साठी कोणतीही सूचना तयार केली जात नाही.',
	comms_osint_marker_unstated: '[खुल्या स्रोताचा अहवाल, पडताळणीचा उल्लेख नाही]',
});
