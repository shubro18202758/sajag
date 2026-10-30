/**
 * Redactions in a report's text (V3-SPEC §7.6): the placeholders the OSINT pipeline leaves where it
 * removed something about a person ([PERSON], [AGE], [CONTACT], [URL] …) — split out so RedactedText can
 * show each as a chip ("name withheld", "age withheld", "detail withheld"), never the bracketed code.
 */
// WITHHELD / REDACTED: the generic marker a source's text carries where the pipeline removed a detail it could not
// classify (an IMD bulletin's Marathi text, for one) — shown as "detail withheld", never the bracketed code
const TOKEN = /\[(PERSON|NAME|AGE|CONTACT|PHONE|EMAIL|ADDRESS|HANDLE|URL|LINK|WITHHELD|REDACTED)\]/g;

export interface RedactionPart {
	text: string;
	token: string | null;
}

export function redactionParts(text: string): RedactionPart[] {
	const out: RedactionPart[] = [];
	let last = 0;
	for (const m of text.matchAll(TOKEN)) {
		const at = m.index ?? 0;
		if (at > last) out.push({ text: text.slice(last, at), token: null });
		out.push({ text: m[0], token: m[1] });
		last = at + m[0].length;
	}
	if (last < text.length) out.push({ text: text.slice(last), token: null });
	return out;
}

/** The pack key of a redaction token's chip. */
export function redactionKey(token: string): string {
	if (token === 'PERSON' || token === 'NAME' || token === 'HANDLE') return 'v3_redact_name';
	if (token === 'AGE') return 'v3_redact_age';
	return 'v3_redact_other';
}
