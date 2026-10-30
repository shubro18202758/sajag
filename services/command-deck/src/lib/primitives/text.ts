/**
 * Sentence case for the rebuilt legacy primitives' visible labels (SPEC §1.5,
 * §11): the label as given, its first letter capitalised when it is a
 * lower-case Latin letter ("live" → "Live", "approved by …" stays a phrase).
 * Devanagari and Marathi have no case and pass through unchanged; nothing
 * else in the string is touched (acronyms stay as given), and a first token
 * that carries a digit or a • (an id or a masked mark, SPEC §3.4 "never
 * altered") is left exactly as it is.
 */
export function sentenceStart(text: string | null | undefined): string {
	const s = text ?? '';
	const first = s.charAt(0);
	if (!(first >= 'a' && first <= 'z')) return s;
	const token = s.split(/\s/, 1)[0];
	if (/[\d•]/.test(token)) return s;
	return first.toUpperCase() + s.slice(1);
}
