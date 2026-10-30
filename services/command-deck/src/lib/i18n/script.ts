/**
 * Which language a data text is written in, and whether a reader of the UI language can read it (pure; no DOM, no
 * store). The deck's own words come from its packs in the reader's language; DATA texts (an official warning, a
 * news line, a field report) arrive in whatever language their source wrote them. Rule (English first):
 *
 *   - a text the reader can read is shown as it is;
 *   - Marathi and Hindi are both written in Devanagari, so a reader of either reads both: a Devanagari text is shown
 *     as it is to a Marathi or a Hindi reader;
 *   - a Devanagari text shown to an English reader is NOT machine-translated (an official warning is never re-worded
 *     by a machine): the surface shows an honest English line instead ("Official text in Marathi" or "... in
 *     Hindi") and keeps the original one level down (the object page, a disclosure), marked lang="mr" / lang="hi";
 *   - which of the two languages a Devanagari text is in is told by its function words (Marathi आहे, नाही, मध्ये,
 *     आणि …; Hindi है, नहीं, में, और …); a text with no telling word counts as Marathi, Mumbai's state language;
 *   - a text in any other non-Latin script (e.g. Bengali from another city pack) is 'other': no UI reader reads it
 *     as a UI language, and a surface shows it as the source sent it.
 */

const DEVANAGARI = /[ऀ-ॿ]/g;
const LATIN = /[A-Za-z]/g;
/** Letters of the other Indic scripts and of Arabic/Urdu: none is a UI language. */
const OTHER = /[\u0980-\u09FF\u0A00-\u0A7F\u0A80-\u0AFF\u0B00-\u0B7F\u0B80-\u0BFF\u0C00-\u0C7F\u0C80-\u0CFF\u0D00-\u0D7F\u0600-\u06FF]/g;

/** Whole words only Marathi uses (Hindi has none of them). */
const MARATHI_WORDS = new Set(
	'आहे आहेत होते होता होती नाही नाहीत मध्ये आणि किंवा साठी पासून पर्यंत येथे तेथे करा करावे करावा होईल असेल झाले झाला झाली केले केला केली राहील राहा पाऊस मुसळधार भरती ओहोटी रस्ता रस्ते वाहतूक इशारा'.split(/\s+/),
);
/** Whole words only Hindi uses (Marathi has none of them). */
const HINDI_WORDS = new Set(
	'है हैं था थी थे नहीं में और लिए से को के यह वह गया गई गए करें होगा होगी रहा रही रहे बारिश सड़क सड़कें यातायात चेतावनी'.split(/\s+/),
);

export type Script = 'mr' | 'hi' | 'latin' | 'other' | null;

/** Marathi or Hindi, for a Devanagari text: whichever has more telling words; Marathi on a tie. */
function devanagariLanguage(s: string): 'mr' | 'hi' {
	let mr = 0;
	let hi = 0;
	for (const w of s.split(/[\s,;:!?()[\]{}"'“”‘’«»<>|—–…·•।॥./-]+/)) {
		if (MARATHI_WORDS.has(w)) mr++;
		else if (HINDI_WORDS.has(w)) hi++;
	}
	return hi > mr ? 'hi' : 'mr';
}

/** The language most of a text's letters are in (null for an empty text or one with no letters). Danda and digits do not count. */
export function scriptOf(text: string | null | undefined): Script {
	const s = String(text ?? '');
	const deva = (s.match(DEVANAGARI) ?? []).filter((c) => c !== '।' && c !== '॥' && !/[०-९]/.test(c)).length;
	const other = (s.match(OTHER) ?? []).length;
	const la = (s.match(LATIN) ?? []).length;
	const max = Math.max(deva, other, la);
	if (max === 0) return null;
	// placeholders such as [WITHHELD] are Latin capitals inside a Devanagari line: Devanagari wins when it carries the words
	if (deva > 0 && deva >= other && (deva === max || deva >= la * 0.6)) return devanagariLanguage(s);
	if (other > 0 && (other === max || other >= la * 0.6)) return 'other';
	return 'latin';
}

/** Can a reader of the UI language `lang` read this text as it is? English readers read Latin; Marathi and Hindi readers read Devanagari and Latin. */
export function readableIn(text: string | null | undefined, lang: string): boolean {
	const sc = scriptOf(text);
	if (sc === null || sc === 'latin') return true;
	if (sc === 'mr' || sc === 'hi') return lang === 'mr' || lang === 'hi';
	return false;
}

/** The first text a reader of `lang` can read, else null (e.g. the English and the Marathi copy of one warning). */
export function pickReadable(texts: readonly (string | null | undefined)[], lang: string): string | null {
	for (const t of texts) if (t && readableIn(t, lang)) return t;
	return null;
}
