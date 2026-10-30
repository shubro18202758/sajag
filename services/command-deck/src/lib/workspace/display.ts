/**
 * The display-label layer (SPEC §3.4, review A10): every view applies it to
 * server and upstream text. Raw values stay available under "Show system
 * fields" in the inspector and in tooltips.
 *
 *   displayTitle(event)   test labels → a Test tag, "(Emulated)" → a provenance
 *                         tag, "PURSUIT — stolen <mark> (FIR …)" → "Pursuit of
 *                         <mark>" (the FIR moves to Properties), ALL-CAPS words
 *                         sentence-cased, "))" → ")"
 *   displayText(row)      snake_case → words, rule codes through the
 *                         vocabulary, machine codes dropped, a trailing
 *                         "— emulator run N: …" and "by <actor>" dropped
 *   displayRowText(row)   a feed row's full text: the oracle's words through
 *                         displayText, then the officer's note EXACTLY as
 *                         sent (noteOf splits it off)
 *   displayActor(raw)     traffic-oracle → Rules engine, convoy-brain → Sajag AI,
 *                         … ; scenario suffixes dropped
 *   displayReason(raw)    the first clause of an earmark reason
 *   brief(row)            one short verb phrase per audit or activity row
 *   displayTool(name)     an assistant step in words
 *
 * Never altered (shown exactly as received): tokens containing a digit or •
 * (ids and masked marks); the acronym allowlist; streamed AI and probe
 * answers (callers never pass them here); officer-entered notes (a feed
 * row's note is split off before anything is humanised: displayRowText);
 * the advisory exercise marker and server text a test pins verbatim
 * (protected spans below, e.g. "e-challan withheld (vehicle reported
 * stolen, FIR …)").
 *
 * Pure and cached per raw string (SPEC §13.4).
 */
import { t } from '$lib/i18n/strings';
import '$lib/i18n/packs.workspace';
import { maskPlatesInText } from '$lib/gods-eye/plates';
import { CITY_ACRONYMS } from '$lib/city';
import {
	ACRONYMS,
	ACTOR_RULES,
	HUMAN,
	SCENARIO_SUFFIX_RE,
	TEST_PREFIX_RE,
	TOOL_NAMES,
	human,
	isTestText,
} from './vocabulary';

// ── caches ────────────────────────────────────────────────────────────────

const CACHE_MAX = 4000;

function cached<T>(fn: (raw: string) => T): (raw: string) => T {
	const memo = new Map<string, T>();
	return (raw: string) => {
		const hit = memo.get(raw);
		if (hit !== undefined) return hit;
		const out = fn(raw);
		if (memo.size >= CACHE_MAX) memo.clear();
		memo.set(raw, out);
		return out;
	};
}

// ── protected spans (shown verbatim) ──────────────────────────────────────

/**
 * Server text pinned verbatim (SPEC §3.4, §12.5): the stolen-vehicle rule's
 * withheld note and the advisory exercise marker. These spans pass through
 * every transform untouched.
 */
const VERBATIM_RES: readonly RegExp[] = [
	/e-challan withheld \(vehicle reported stolen[^)]*\)/g,
	/\[SIMULATED FEED · EMULATED[^\]]*\]/g,
];

/** Run `fn` over `text` with the verbatim spans held out of its reach. */
function protect(text: string, fn: (s: string) => string): string {
	const held: string[] = [];
	let s = text;
	for (const re of VERBATIM_RES) {
		s = s.replace(re, (m) => {
			held.push(m);
			return `\u0000${held.length - 1}\u0000`;
		});
	}
	const out = fn(s);
	return held.length ? out.replace(/\u0000(\d+)\u0000/g, (_m, i: string) => held[Number(i)] ?? '') : out;
}

// ── sentence case ─────────────────────────────────────────────────────────

const WORD_RE = /(^|[\s(·—–:,;"'\u0000])([A-Z][A-Z'’]*(?:-[A-Z][A-Z'’]*)*)(?=$|[\s),.;:·—–"'\u0000])/g;

/**
 * Sentence-case every ALL-CAPS word outside the acronym allowlist and the city's own initialisms
 * (CITY_ACRONYMS: "WEH", "LBS Marg", "Dadar TT Circle" keep their signage spelling). Tokens
 * with a digit or • (ids, marks) never match. A word that starts a sentence
 * (or follows ":", "—", "(" or "·") keeps a capital.
 */
export function decap(s: string): string {
	return s.replace(WORD_RE, (all, pre: string, w: string, off: number, str: string) => {
		if (w.length < 2 || ACRONYMS.has(w) || CITY_ACRONYMS.has(w)) return all;
		const lower = w.toLowerCase();
		const before = str.slice(0, off + pre.length).trimEnd();
		const start = before === '' || /[.:—(·–]$/.test(before);
		return pre + (start ? lower.charAt(0).toUpperCase() + lower.slice(1) : lower);
	});
}

/** The first letter of a sentence in upper case (the rest untouched). */
export const capFirst = (s: string) => s.replace(/^\s*\S/, (c) => c.toUpperCase());

// ── titles ────────────────────────────────────────────────────────────────

export interface TitleParts {
	/** The title as shown. */
	title: string;
	/** A test label was stripped: show a Test tag. */
	test: boolean;
	/** "(Emulated)" was stripped: show the provenance tag. */
	emulated: boolean;
	/** The FIR reference a pursuit title carried (for Properties), or null. */
	fir: string | null;
	/** The pursued vehicle's mark when the title is a pursuit's (F-16: the title is localised), else null. */
	pursuit: string | null;
}

const PURSUIT_RE = /^PURSUIT\s+—\s+(?:stolen\s+)?(\S+)(?:\s+\(([^)]*)\))?/i;

export const titleParts = cached((raw: string): TitleParts => {
	let s = String(raw ?? '').trim();
	const m = PURSUIT_RE.exec(s);
	if (m) {
		const fir = m[2]?.replace(/^FIR\s+/i, '').trim() || null;
		return { title: `Pursuit of ${m[1]}`, test: false, emulated: false, fir, pursuit: m[1] };
	}
	let test = false;
	let emulated = false;
	s = s.replace(TEST_PREFIX_RE, () => {
		test = true;
		return '';
	});
	s = s.replace(/\s+—\s+JOURNEY CHECK \(automated\)\)?$/i, () => {
		test = true;
		return '';
	});
	s = s.replace(/^ACCEPTANCE TEST\s+—\s+/i, () => {
		test = true;
		return '';
	});
	s = s.replace(/\s*\(Emulated\)\s*$/i, () => {
		emulated = true;
		return '';
	});
	s = s.replace(/\)\)/g, ')');
	const title = protect(s, (x) => capFirst(decap(x))).trim();
	return { title: title || String(raw ?? ''), test, emulated, fir: null, pursuit: null };
});

/** The English pursuit title the display layer builds ("Pursuit of <mark>"), as rows carry it. */
const SHOWN_PURSUIT_RE = /^Pursuit of (\S+)$/;

/**
 * A shown title in `lang` (F-16): the one phrase the display layer itself
 * writes into titles — "Pursuit of <mark>" — reads in the console's
 * language; every other title is server text and stays as sent. Rows are
 * built once for every language, so views localise at render time.
 */
export function localTitle(shown: string, lang = 'en'): string {
	if (lang === 'en' || !shown) return shown;
	const m = SHOWN_PURSUIT_RE.exec(shown);
	return m ? t(lang, 'ws_title_pursuit_of', m[1]) : shown;
}

/** An event's (or any object's) title as shown, in `lang`. Accepts the raw title or an object carrying it. */
export function displayTitle(event: string | { title?: string | null; label?: string | null } | null | undefined, lang = 'en'): string {
	const raw = typeof event === 'string' ? event : (event?.title ?? event?.label ?? '');
	return raw ? localTitle(titleParts(raw).title, lang) : '';
}

// ── free text ─────────────────────────────────────────────────────────────

const textOf = cached((raw: string): string =>
	protect(raw, (input) => {
		let s = input;
		s = s.replace(/\(twin_not_calibrated:[^)]*\)/g, '(twin not calibrated)');
		// an internal contract code in server text — "(C6)", "(C-F)", "(C-D2)" — is not operator copy (F-17)
		s = s.replace(/\s*\(C(?:\d{1,2}|-[A-Z]{1,2}\d{0,2})\)/g, '');
		s = s.replace(/,\s*(?:none|[A-Z]+):[A-Z_]+:[A-Z_]+:[A-Z_]+/g, '');
		s = s.replace(/\b(?:none|[A-Z]+):[A-Z_]+:[A-Z_]+:[A-Z_]+\b/g, '');
		s = s.replace(/\bR_[A-Z_]+\b/g, (c) => HUMAN[c] ?? c);
		// snake_case words (never a token with a digit: ids stay as sent)
		s = s.replace(/\b[a-z]+(?:_[a-z]+)+\b/g, (w) => (HUMAN[w] ?? w.replace(/_/g, ' ')).replace(/^[A-Z](?=[a-z])/, (c) => c.toLowerCase()));
		s = s.replace(/\s+—\s+emulator run \d+:[^.]*$/, '');
		// a TRAILING "by <actor>" only: an actor never holds " — " or ": ", so a note after it is never eaten
		s = s.replace(/\)\s+by\s+(?:(?!\s—\s|:\s)[^()])+(?:\([^)]*\))?$/, ')');
		s = s.replace(/\s*\((?:God's Eye Morning|God’s Eye Morning|demo reset|showcase script)\)/gi, '');
		s = s.replace(/\s*\(Emulated\)/g, '');
		s = s.replace(TEST_PREFIX_RE, '');
		s = s.replace(/\)\)/g, ')');
		return decap(s).replace(/\s{2,}/g, ' ').trim();
	}),
);

/** Server or upstream free text as shown. Accepts the raw string or a row carrying `text`. */
export function displayText(row: string | { text?: string | null } | null | undefined): string {
	const raw = typeof row === 'string' ? row : (row?.text ?? '');
	return raw ? textOf(raw) : '';
}

// ── officer notes (shown exactly as sent) ─────────────────────────────────

/** A feed row whose text may end in an officer's note. */
export interface NoteRow {
	kind?: string | null;
	text?: string | null;
	/** Who wrote the row: a note is an OFFICER's only on a human row (a machine's "— emulator run N: …" is not one). */
	actorKind?: string | null;
	props?: Readonly<Record<string, unknown>> | null;
}

/** A feed row's text split at its officer note: the oracle's words, the separator, the note as sent. */
export interface NoteSplit {
	head: string;
	sep: string;
	note: string;
}

/** Where the oracle appends a note (traffic_oracle/city/feed.py): ": <note>" (enforcement), " — <note>" (event, dispatch). */
const NOTE_SEPS = [': ', ' — '] as const;
/** The oracle clips a feed text at 600 characters (city/common.py feed_item): a clipped note still starts where it started. */
const FEED_TEXT_MAX = 600;

/**
 * The fixed words the oracle writes BEFORE an officer's note, per row kind
 * (city/feed.py: enforcement_items, event_log_item, dispatch_item); group 1
 * is the separator. Read only when the row carries no props.note (a reduced
 * capture, an older oracle). An actor never holds " — " or ": ".
 */
const NOTE_AFTER: Readonly<Record<string, readonly RegExp[]>> = {
	enforcement: [
		/^Stolen-vehicle sighting of \S+ confirmed by [^:]+? — pursuit authorised; e-challan withheld(: )/,
		/^Stolen-vehicle sighting of \S+ dismissed by [^:]+?(: )/,
		/^e-challan (?:APPROVED|REJECTED) by [^()]+? \([^()]*\)(: )/,
	],
	event: [/^Event \w+: .* \([^()]* → [^()]*\) by [^—]+?( — )/, /^Route updated: .* by [^—]+?( — )/],
	dispatch: [/^.+?: \S+ → \S+ by [^—]+?( — )/, /^.+ requested for .+ by [^—]+?( — )/],
};

/**
 * The officer's note a feed row's text ends with, split off — or null when
 * there is none. The row's own `props.note` says where it starts (the text
 * carries it masked: the oracle masks the whole text it sends); without it
 * the oracle's fixed words before a note do. The note is returned as the
 * text carries it, never rewritten.
 */
export function noteOf(row: NoteRow): NoteSplit | null {
	const text = String(row.text ?? '');
	if (!text || (row.actorKind != null && row.actorKind !== 'human')) return null;
	const raw = row.props?.note;
	if (typeof raw === 'string' && raw.trim()) {
		const sent = maskPlatesInText(raw);
		for (const sep of NOTE_SEPS) {
			if (text.endsWith(sep + sent) && text.length > sep.length + sent.length) {
				const at = text.length - sent.length - sep.length;
				return { head: text.slice(0, at), sep, note: text.slice(at + sep.length) };
			}
		}
		if (text.length >= FEED_TEXT_MAX) {
			for (const sep of NOTE_SEPS) {
				for (let at = text.lastIndexOf(sep); at > 0; at = text.lastIndexOf(sep, at - 1)) {
					const tail = text.slice(at + sep.length);
					if (tail && sent.startsWith(tail)) return { head: text.slice(0, at), sep, note: tail };
				}
			}
		}
	}
	for (const re of NOTE_AFTER[row.kind ?? ''] ?? []) {
		const m = re.exec(text);
		if (!m) continue;
		const note = text.slice(m[0].length);
		if (note.trim()) return { head: text.slice(0, m[0].length - m[1].length), sep: m[1], note };
	}
	return null;
}

/**
 * A feed row's full text as shown (the Activity row's expander and tooltip):
 * the oracle's words through displayText, then the officer's note exactly as
 * sent — never sentence-cased, never de-snake_cased, never dropped.
 */
export function displayRowText(row: NoteRow): string {
	const n = noteOf(row);
	return n ? `${displayText(n.head)}${n.sep}${n.note}` : displayText(row.text ?? '');
}

// ── actors ────────────────────────────────────────────────────────────────

export interface ActorParts {
	/** The display name (EN for a system actor; a person's name as entered). */
	name: string;
	/** A system actor's pack key (`ws_actor_name_<key>`), or null for a person. */
	key: string | null;
	/** The scenario suffix the raw value carried ("(God's Eye Morning)"), or null. */
	scenario: string | null;
	/** A rehearsal or test actor: show a Test tag. */
	test: boolean;
}

export const actorParts = cached((raw: string): ActorParts => {
	const a = String(raw ?? '').trim();
	const test = isTestText(a);
	for (const [re, out, key] of ACTOR_RULES) if (re.test(a)) return { name: out, key, scenario: null, test };
	const m = SCENARIO_SUFFIX_RE.exec(a);
	const name = (m ? a.slice(0, m.index) : a).trim();
	return { name: name === 'Acceptance Tester' ? 'Acceptance tester' : name || a, key: null, scenario: m ? m[0].trim() : null, test };
});

/** The name of parsed actor parts in `lang`: a system actor in words, a person's name as entered. */
export function actorName(parts: ActorParts, lang = 'en'): string {
	return parts.key ? t(lang, `ws_actor_name_${parts.key}`) : parts.name;
}

/** An actor's display name in `lang` ("traffic-oracle" → "Rules engine"). */
export function displayActor(raw: string | null | undefined, lang = 'en'): string {
	return raw ? actorName(actorParts(raw), lang) : '';
}

// ── reasons ───────────────────────────────────────────────────────────────

const reasonOf = cached((raw: string): string => {
	const [first] = raw.split(/;\s*/);
	return capFirst(decap(first).replace(/ — /, ' · ')).trim();
});

/** An earmark reason's first clause ("Stolen vehicle reported · FIR 4401/2026, Hare Street PS"). */
export function displayReason(raw: string | null | undefined): string {
	return raw ? reasonOf(raw) : '';
}

/** The scenario named after a reason's first clause (system fields only), or null. */
export function displayScenario(raw: string | null | undefined): string | null {
	if (!raw) return null;
	return raw.split(/;\s*/)[1]?.trim() || null;
}

// ── one line per activity row ─────────────────────────────────────────────

export interface BriefRow extends NoteRow {
	kind?: string | null;
	text?: string | null;
	/** The feed row's structured fields (rule_id, action, speed_kmh …): read before any text. */
	props?: Readonly<Record<string, unknown>> | null;
}

/** What an enforcement row records: a stolen-vehicle sighting or an e-challan, filed or decided. */
export interface EnforcementStep {
	on: 'sighting' | 'challan';
	step: 'filed' | 'approved' | 'rejected';
	/** The camera a filed sighting names (its fixed opening carries it), or null. */
	camera: string | null;
}

/**
 * The fixed openings of the oracle's enforcement rows
 * (traffic_oracle/city/feed.py, enforcement_items). An officer's note only
 * ever FOLLOWS them (": <note>"), so these anchored patterns never read it.
 */
const ENF_SIGHTED_RE = /^Stolen vehicle \S+(?: \(FIR [^)]*\))? sighted at /;
const ENF_SIGHTED_CAM_RE = /^Stolen vehicle \S+(?: \(FIR [^)]*\))? sighted at ([A-Za-z0-9][A-Za-z0-9_.:-]*)(?= on | — |$)/;
const ENF_SIGHTING_DECIDED_RE = /^Stolen-vehicle sighting of \S+ (confirmed|dismissed) by /;
const ENF_CHALLAN_FILED_RE = /^e-challan recommended \(/;
const ENF_CHALLAN_DECIDED_RE = /^e-challan (APPROVED|REJECTED) by /;

const STOLEN_SIGHTING_RULE = 'R_STOLEN_SIGHTING';

/**
 * Classify an enforcement row on its structured fields — `props.rule_id`
 * (R_STOLEN_SIGHTING is a sighting on file, every other rule an e-challan)
 * and `props.action` ("created…", "decision:approved", "decision:rejected")
 * — and, where a field is missing (a reduced capture), on the oracle's
 * fixed openings. Never on keywords anywhere in the text: the officer's free
 * note may say "dismissed" or "approved" about anything. `props.status` is
 * the recommendation's state NOW, not this row's step, so it is not read.
 */
export function enforcementStep(row: BriefRow): EnforcementStep | null {
	const text = String(row.text ?? '');
	const p = row.props ?? {};
	const rule = typeof p.rule_id === 'string' && p.rule_id ? p.rule_id : null;
	const action = typeof p.action === 'string' ? p.action : '';
	let on: EnforcementStep['on'] | null = rule ? (rule === STOLEN_SIGHTING_RULE ? 'sighting' : 'challan') : null;
	let step: EnforcementStep['step'] | null = action.startsWith('created')
		? 'filed'
		: action === 'decision:approved'
			? 'approved'
			: action === 'decision:rejected'
				? 'rejected'
				: null;
	let m: RegExpExecArray | null;
	if (ENF_SIGHTED_RE.test(text)) {
		on ??= 'sighting';
		step ??= 'filed';
	} else if ((m = ENF_SIGHTING_DECIDED_RE.exec(text))) {
		on ??= 'sighting';
		step ??= m[1] === 'confirmed' ? 'approved' : 'rejected';
	} else if (ENF_CHALLAN_FILED_RE.test(text)) {
		on ??= 'challan';
		step ??= 'filed';
	} else if ((m = ENF_CHALLAN_DECIDED_RE.exec(text))) {
		on ??= 'challan';
		step ??= m[1] === 'APPROVED' ? 'approved' : 'rejected';
	}
	if (!on || !step) return null;
	const camera = on === 'sighting' && step === 'filed' ? (ENF_SIGHTED_CAM_RE.exec(text)?.[1] ?? null) : null;
	return { on, step, camera };
}

/** The verbs of the oracle's event rows ("Event <verb>: <title> (…)", city/feed.py _EVENT_VERBS). */
const EVENT_VERBS = new Set(['opened', 'approved', 'activated', 'completed', 'cancelled']);

/**
 * One short verb phrase per audit or activity row ("read the vehicle at
 * 95 km/h", "filed a stolen-vehicle sighting at EM-CAM-03", "approved an
 * e-challan"), in `lang`; the full sentence stays in the row's tooltip and
 * expander. Structured fields first, then the oracle's fixed openings;
 * anything else is the humanised text before its officer note (the note is
 * the full text's, verbatim: displayRowText).
 */
export function brief(row: BriefRow, lang = 'en'): string {
	const text = String(row.text ?? '');
	if (row.kind === 'anpr') {
		const sp = row.props?.speed_kmh;
		const kmh = typeof sp === 'number' && Number.isFinite(sp) ? String(Math.round(sp)) : (/\((\d+) km\/h\)/.exec(text)?.[1] ?? null);
		return kmh ? t(lang, 'ws_brief_read_kmh', kmh) : t(lang, 'ws_brief_read');
	}
	const words = () => displayText(noteOf(row)?.head ?? text);
	if (row.kind === 'enforcement') {
		const s = enforcementStep(row);
		if (!s) return words();
		if (s.on === 'sighting' && s.step === 'filed') return s.camera ? t(lang, 'ws_brief_sighting_filed_at', s.camera) : t(lang, 'ws_brief_sighting_filed');
		return t(lang, `ws_brief_${s.on}_${s.step}`);
	}
	if (row.kind === 'event') {
		const m = /^Event (\w+): (.+?) \(/.exec(text);
		if (m) {
			const verb = m[1].toLowerCase();
			const title = displayTitle(m[2]);
			return EVENT_VERBS.has(verb) ? t(lang, `ws_brief_event_${verb}`, title) : `${verb} ${title}`;
		}
	}
	return words();
}

// ── tools ─────────────────────────────────────────────────────────────────

/** An assistant tool step in words ("city_get_dossier" → "Read the object's dossier"). */
export function displayTool(name: string | null | undefined): string {
	if (!name) return '';
	return TOOL_NAMES[name] ?? human(name);
}

export { human, isTestText };
