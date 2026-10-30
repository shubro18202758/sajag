/**
 * Plate display rail (C6) — vehicles are identified by ANPR plate only,
 * and a plate is shown MASKED (MH47EM•••1) on every canvas, dossier and
 * feed surface unless a named duty officer is on console (SPEC §9.3: no
 * raw mark in DOM text without a named officer).
 *
 * The mark rule is the workspace's (src/lib/workspace/mask.ts, imported,
 * never copied: one rule for the whole deck). The oracle (city/common.py)
 * masks every label and feed text it sends, but only a mark as the server
 * writes it — upper case, a space or a dash between the parts. Text that
 * reaches these sinks is often not the server's: an officer's typed note,
 * a pursuit's title, an emulator tape, a brain answer, an evidence payload.
 * So a mark is masked here in any case and spelling:
 *
 *   MH47EM9001 · mh47em9001 · Mh 47 Em 9001 · MH.47.EM.9001 · MH/47/EM/9001 · MH_47_EM_9001
 *
 * all keep their state code, RTO number and series and hide the 4-digit
 * number but its last digit (…•••1). The rule, from mask.ts:
 *   - a mark starts with one of the 39 Indian state / union-territory
 *     codes (STATE_CODES), in any case — never any two letters;
 *   - up to three of space, `.`, `-`, `/`, `_` between the parts;
 *   - a UUID (a URN's id) is held out, so a hex group is never a mark;
 *   - a spaced candidate whose series spells a month is a date and is left
 *     alone ("24 Oct 2026", "on 12 oct 2026") unless the state code and the
 *     series are both upper case ("MH 01 MAY 1234" is a mark);
 *   - text that holds no mark comes back as it was, byte for byte.
 * An upper-case mark masks exactly as it did before (and as the oracle's
 * mask does): MH47EM9001 → MH47EM•••1, MH 02 AB 1234 → MH 02 AB •••4. The
 * one narrowing is mask.ts's (review r3): two letters that are no state
 * code ("AB12CD3456") no longer read as a mark.
 * A named duty officer sees every text raw.
 */

import { MARK_MASK, maskMarks } from '$lib/workspace/mask';

/** Mask every registration mark inside a free-text string (any case and spelling). */
export function maskPlatesInText(text: string | null | undefined): string {
	if (!text) return '';
	return maskMarks(text);
}

/** `MH47EM9001` → `MH47EM•••1` (null-safe; short plates keep their last char only). */
export function maskPlate(plate: string | null | undefined): string | null {
	if (!plate) return null;
	const masked = maskPlatesInText(plate);
	if (masked !== plate) return masked;
	return plate.length >= 6 ? `${plate.slice(0, -4)}${MARK_MASK}${plate.slice(-1)}` : `${MARK_MASK}${plate.slice(-1)}`;
}

/** The plate as this console may show it: raw only for a named duty officer. */
export function displayPlate(plate: string | null | undefined, officerNamed: boolean): string | null {
	if (!plate) return null;
	return officerNamed ? plate : maskPlate(plate);
}

/** Free text (titles, descriptions) as this console may show it. */
export function displayText(text: string | null | undefined, officerNamed: boolean): string {
	if (!text) return '';
	return officerNamed ? text : maskPlatesInText(text);
}

/**
 * Every string in a plain JSON value (keys too) through the mask. The walk
 * masks each string on its own: masking the serialised JSON text would miss
 * a mark right after an escape ("…\nwb01xx0007": no word boundary between
 * the escape's letter and the mark) and could read an escape's letter as a
 * state code's first letter ("\tn01…").
 */
function maskJson(value: unknown, path: WeakSet<object>): unknown {
	if (typeof value === 'string') return maskMarks(value);
	if (value === null || typeof value !== 'object') return value;
	if (path.has(value)) return '[circular]';
	path.add(value);
	const out = Array.isArray(value)
		? value.map((v) => maskJson(v, path))
		: Object.fromEntries(Object.entries(value as Record<string, unknown>).map(([k, v]) => [maskMarks(k), maskJson(v, path)]));
	path.delete(value);
	return out;
}

/**
 * A structured evidence payload (an audit row's `detail`, shown as JSON in
 * the evidence modal) as this console may show it: every registration mark
 * in any string value (and key) masked unless a named duty officer is on
 * console. The payload is read as JSON (what the modal prints: toJSON,
 * dates as strings, no functions), then every string is masked on its own,
 * so the result holds the same values but for the marks. The input is
 * never mutated.
 */
export function displayDetail(detail: unknown, officerNamed: boolean): unknown {
	if (officerNamed || detail === undefined || detail === null) return detail;
	if (typeof detail === 'string') return maskPlatesInText(detail);
	if (typeof detail !== 'object') return detail;
	let plain: unknown = detail;
	try {
		const json = JSON.stringify(detail);
		if (json !== undefined) plain = JSON.parse(json);
	} catch {
		// a cycle or a BigInt: walk the payload itself (cycles cut), never hand it back raw
	}
	return maskJson(plain, new WeakSet());
}
