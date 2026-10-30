/**
 * The workspace's registration-mark mask (C6; SPEC §7.5: every egress path
 * is masked, whether or not an officer is named; §9.3: no raw mark in DOM
 * text without a named officer).
 *
 * plates.ts (S3) mirrors the oracle's rule (city/common.py), which matches a
 * mark as the server writes it: upper case, a space or a dash between the
 * parts. Text an OPERATOR types reaches the workspace's egress paths (a
 * filter label from the omnibar, a saved view's name, a watch's title, a
 * share link) in any case and spelling, and server props can carry a raw
 * mark inside free text (an e-challan's proposal, an earmark reason, a
 * pursuit's title), so this mask is case-insensitive and takes a space, a
 * dash, a dot, a slash or an underscore (up to three) between the parts:
 *
 *   MH47EM9001 · mh47em9001 · Mh 47 Em 9001 · MH-47-EM-9001 · MH.47.EM.9001 · MH/47/EM/9001
 *
 * all keep their state code, RTO number and series and hide the 4-digit
 * number but its last digit (…•••1), as the oracle's mask does.
 *
 * Only a REAL Indian registration mark matches the any-case rule (review r3):
 *   - the state code is one of the Indian state and union-territory codes
 *     (STATE_CODES, any case), never any two letters;
 *   - a date's shape is never a mark: a month in mixed or lower case
 *     ("Oct", "nov"), a separator, then the number — so a date or a time
 *     ("As of 24 Oct 2026", "AS 24 Oct 2026", "on 12 oct 2026", "at 10 am
 *     2026") is never read as one. The case tells them apart (orchestrator,
 *     review r3): marks from the oracle and in operator text are upper
 *     case, prose dates are not. So an UPPER-case state code with an
 *     UPPER-case series is a mark even when the series spells a month
 *     ("MH 01 MAY 1234", "DL 8 SEP 1234", "MH-01-OCT-1234"), and a series
 *     glued to its number is one in any case ("DL8SEP1234", a Delhi
 *     two-wheeler's S-EP series): no date is written either way, and
 *     refusing them would leak a real mark. (An all-caps date after a
 *     state-code word, "AS 24 OCT 2026", therefore reads as a mark: the
 *     ethics rail prefers masking.)
 *
 * After that rule, and over the text it already masked, the oracle's own
 * upper-case pass runs too (FIX-C: one rule everywhere): an UPPER-case
 * mark shape masks whatever its first two letters — "XY12AB1234", because
 * the watchlist's normalize_plate accepts any two letters, so a plate it
 * holds never leaves the oracle raw in a reason or a title — with a space
 * or a dash between the parts, exactly as the oracle (city/common.py,
 * _PLATE_UPPER_RE) always masked it. There is no date-shape refusal on
 * this pass (case-sensitive: prose dates are not upper case; "AS OF 24
 * OCT 2026" masks as it always did), and uuids are held out of it too.
 * Text that holds no mark comes back byte for byte (the same string), so
 * running the mask over an officer's note or a streamed answer alters
 * nothing but a mark (SPEC §3.4: those are never rewritten).
 *
 * Ids are never marks: a UUID (a URN's id) is held out of the mask's reach,
 * so a hex group such as `ab12-3456` is never mistaken for one.
 */

/**
 * The Indian state and union-territory codes a registration mark starts
 * with (the reviewer's list, plus TG: Telangana's code since 2024; OR and DN
 * are older codes still on the road).
 */
export const STATE_CODES: readonly string[] = Object.freeze([
	'AN', 'AP', 'AR', 'AS', 'BR', 'CG', 'CH', 'DD', 'DL', 'DN', 'GA', 'GJ', 'HP', 'HR', 'JH', 'JK', 'KA', 'KL', 'LA', 'LD',
	'MH', 'ML', 'MN', 'MP', 'MZ', 'NL', 'OD', 'OR', 'PB', 'PY', 'RJ', 'SK', 'TG', 'TN', 'TR', 'TS', 'UK', 'UP', 'WB',
]);

/** Month abbreviations (a whole series that spells one, any case). */
const MONTH_RE = /^(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)$/i;
/** Up to three separator characters between the parts of a mark. */
const SEP = '[\\s.\\-/_]{0,3}';
/**
 * The mark's shape, case-insensitive (the `i` flag): group 1 the head (kept),
 * 2 the state code, 3 the optional series, 4 the separator after it, 5 the
 * 4-digit number. A candidate in a date's shape is refused by isDateShape.
 */
const MARK_SRC = `\\b(((?:${STATE_CODES.join('|')}))${SEP}\\d{1,2}${SEP}(?:([a-z]{1,3})(${SEP}))?)(\\d{4})\\b`;
const MARK_RE = new RegExp(MARK_SRC, 'gi');
const ANY_MARK_RE = new RegExp(MARK_SRC, 'i');
/**
 * The oracle's pre-change rule, kept as a SUPERSET pass (fail closed): an
 * UPPER-case mark shape whatever its first two letters, a space or a dash
 * (one, or none) between the parts, an optional 1-3 letter series — the
 * same pattern as the oracle's `_PLATE_UPPER_RE`, case-sensitive, run AFTER
 * the state-code rule over the once-masked text. Group 1 the head (kept),
 * 2 the 4-digit number (masked, its last digit kept); no date refusal here.
 */
const UPPER_MARK_SRC = '\\b([A-Z]{2}[ -]?\\d{1,2}[ -]?(?:[A-Z]{1,3}[ -]?)?)(\\d{4})\\b';
const UPPER_MARK_RE = new RegExp(UPPER_MARK_SRC, 'g');
const ANY_UPPER_MARK_RE = new RegExp(UPPER_MARK_SRC);
const UUID_RE = /\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b/gi;

export const MARK_MASK = '•••';

const isUpper = (s: string) => s === s.toUpperCase();

/**
 * A candidate that is a date, not a mark: its series spells a month and a
 * separator stands before the number ("Oct 2026"), unless the state code and
 * the series are both upper case (a mark as the oracle and operators write
 * it: "MH 01 MAY 1234").
 */
function isDateShape(state: string, series: string | undefined, sepAfter: string | undefined): boolean {
	if (!series || !sepAfter || !MONTH_RE.test(series)) return false;
	return !(isUpper(state) && isUpper(series));
}

/** Mask every registration mark in `text`, in any case and spelling (ids untouched; text without a mark is returned as is). */
export function maskMarks(text: string | null | undefined): string {
	if (!text) return '';
	if (!ANY_MARK_RE.test(text) && !ANY_UPPER_MARK_RE.test(text)) return text;
	const held: string[] = [];
	const s = text.replace(UUID_RE, (u) => {
		held.push(u);
		return `\u0000${held.length - 1}\u0000`;
	});
	const masked = s.replace(MARK_RE, (m: string, head: string, state: string, series: string | undefined, sepAfter: string | undefined, num: string) =>
		isDateShape(state, series, sepAfter) ? m : `${head}${MARK_MASK}${num.slice(-1)}`,
	);
	const out = masked.replace(UPPER_MARK_RE, (_m: string, head: string, num: string) => `${head}${MARK_MASK}${num.slice(-1)}`);
	return held.length ? out.replace(/\u0000(\d+)\u0000/g, (_m, i: string) => held[Number(i)] ?? '') : out;
}

/**
 * True when `text` holds a raw registration mark in any case or spelling (a UUID is an id, never a mark) —
 * every shape the mask masks: a state-code mark that is not a date, or an upper-case shape the superset
 * pass takes, so hasRawMark stays consistent with maskMarks (hash.ts reads it over saved content).
 */
export function hasRawMark(text: string | null | undefined): boolean {
	if (!text) return false;
	const s = text.replace(UUID_RE, ' ');
	for (const m of s.matchAll(MARK_RE)) if (!isDateShape(m[2], m[3], m[4])) return true;
	return ANY_UPPER_MARK_RE.test(s);
}
