/**
 * A timeline tick's tooltip: "01:38:37 · Rules engine: filed a stolen-vehicle
 * sighting at EM-CAM-03", MASKED in every spelling (workspace/mask.ts) —
 * a tooltip is DOM text, and an officer's typed note or a model's answer can
 * carry a mark the oracle's upper-case mask never saw (SPEC §9.3).
 *
 * An open-source report's tooltip ends in its verification label, the plan's
 * X2 words (ProvenanceTag's): "Unverified OSINT", "News-reported",
 * "Official, verified", "Confirmed by officer", or "Open-source" when the
 * row has no state yet (ethics rule 7: every event carries an honest label).
 */
import type { FeedRow } from '$lib/gods-eye/city-api';
import { t } from '$lib/i18n/strings';
import '$lib/i18n/packs.ui';
import { fmtStamp } from '$lib/ui/format/format';
import { actorName, actorParts, brief } from '$lib/workspace/display';
import { maskMarks } from '$lib/workspace/mask';
import { isOsint } from './lanes';

/** The four verification states an open-source row can carry (X2). */
export type OsintVerification = 'UNVERIFIED-OSINT' | 'NEWS-REPORTED' | 'OFFICIAL-VERIFIED' | 'CONFIRMED';

const VERIF_KEY: Readonly<Record<OsintVerification, string>> = {
	'UNVERIFIED-OSINT': 'ui_verif_unverified',
	'NEWS-REPORTED': 'ui_verif_news',
	'OFFICIAL-VERIFIED': 'ui_verif_official',
	CONFIRMED: 'ui_verif_confirmed',
};

/** The row's open-source verification state, or null (none, or a value that is not an OSINT state). */
export function osintVerification(v: unknown): OsintVerification | null {
	return typeof v === 'string' && Object.prototype.hasOwnProperty.call(VERIF_KEY, v) ? (v as OsintVerification) : null;
}

/** The X2 label of an open-source row: its verification state in words, or "Open-source" without one. */
export function osintLabel(v: unknown, lang = 'en'): string {
	const s = osintVerification(v);
	return t(lang, s ? VERIF_KEY[s] : 'ui_prov_osint');
}

/**
 * The tooltip in two parts: the sentence (masked, at most 160 characters)
 * and, for an open-source row, its verification label — drawn apart, so a
 * long sentence is ellipsised before the label and the label never is.
 */
export function rowTipParts(r: FeedRow, anchor: number, lang = 'en'): { text: string; label: string | null } {
	const who = r.actor ? actorName(actorParts(r.actor), lang) : r.actorKind;
	const text = maskMarks(`${fmtStamp(r.t, anchor, { seconds: true })} · ${who}: ${brief(r, lang)}`).slice(0, 160);
	return { text, label: isOsint(r) ? osintLabel(r.verificationState, lang) : null };
}

/** The tooltip as one line: "… · News-reported" for an open-source row. */
export function rowTip(r: FeedRow, anchor: number, lang = 'en'): string {
	const p = rowTipParts(r, anchor, lang);
	return p.label ? `${p.text} · ${p.label}` : p.text;
}
