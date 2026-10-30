/**
 * The omnibar's search (SPEC §8.1): over every object type, grouped by type
 * with counts; `kind:`, `state:` and `source:` tokens filter; `>` lists
 * commands, including the legacy grammar (`fly to <plate|URN|junction|
 * road>`, `show <agency> units near <road>`, `layer <id> on|off`,
 * `sensor <mode>`, `ask <question>`), which also works without the `>`.
 *
 * Registration marks (§8.1, pinned by agent-canvas-smoke): a full mark, or a
 * prefix of 6 or more characters, is matched ONLY against watchlisted
 * vehicles' marks (the registry's vehicles are watchlist entries) — never
 * against reads or recommendations, never as a person search (there is
 * none). The result is masked until a duty officer is named; when nothing
 * matches the omnibar says so honestly (MARK_EMPTY, verbatim). With an
 * officer named, a COMPLETE mark additionally offers the officer-only,
 * audited full-plate lookup (isFullMark / lookupOfferActive here; the
 * client and its presenter are vehicle-lookup.ts) — the frozen watchlist
 * behaviour above is what a console without an officer keeps.
 *
 * Fast: a row's haystack is computed once per row object (rows are
 * immutable per model build), so a keystroke is a linear scan of short
 * strings (< 5 ms for a thousand objects).
 */
import { t } from '$lib/i18n/strings';
import '$lib/i18n/packs.workspace';
import '$lib/i18n/packs.map';
import { STATE_CODES, maskMarks } from './mask';
import { HUMAN, human } from './vocabulary';
import { landmarkName } from '$lib/city';
import type { ObjectRow } from './types';

/** The honest empty state of a full-mark query (SPEC §8.1), EN, verbatim. */
export const MARK_EMPTY_EN =
	'No watchlisted vehicle has this registration mark. Full marks are matched against the watchlist only, never against reads. A match is shown masked until a duty officer is named.';

/** The empty state in `lang`: a title and a body (their EN join is MARK_EMPTY_EN). */
export function markEmptyState(lang = 'en'): { title: string; body: string } {
	return { title: t(lang, 'ws_omni_mark_none'), body: t(lang, 'ws_omni_mark_rule') };
}

/** How kinds rank among equally good matches. */
const KIND_WEIGHT: Readonly<Record<string, number>> = {
	vehicle: 6,
	event: 5,
	osint_event: 5,
	camera: 4,
	junction: 4,
	segment: 4,
	place: 4,
	recommendation: 3,
	sighting: 3,
	dispatch: 3,
	unit: 3,
	convoy: 3,
	anomaly: 2,
};

/** EN kind names the `kind:` token and the haystack know. */
const KIND_WORDS: Readonly<Record<string, string>> = {
	vehicle: 'vehicle watchlist',
	sighting: 'sighting read',
	camera: 'camera',
	junction: 'junction',
	segment: 'road segment',
	recommendation: 'recommendation e-challan',
	event: 'event',
	dispatch: 'dispatch',
	unit: 'unit',
	convoy: 'convoy',
	anomaly: 'anomaly',
	osint_event: 'reported event report osint',
	place: 'place',
};

// ── registration marks ─────────────────────────────────────────────────────

/** A query as a mark: upper case, no spaces, dashes or dots. */
export function normMark(s: unknown): string {
	return String(s ?? '')
		.replace(/[\s\-.]/g, '')
		.toUpperCase();
}

const MARK_PREFIX_RE = /^[A-Z]{2}\d{1,2}[A-Z]{0,3}\d{0,4}$/;

/** True when the (normalised) query is a full registration mark or a mark prefix of 6+ characters. */
export function isMarkQuery(q: string): boolean {
	const n = normMark(q);
	return n.length >= 6 && MARK_PREFIX_RE.test(n);
}

/** True when the (normalised) query is a COMPLETE registration mark — the oracle's
 *  plates.py PLATE_PATTERNS, mirrored so a full mark here is a 422-free mark there. */
const FULL_MARK_RE = /^(?:[A-Z]{2}\d{1,2}[A-Z]{0,3}\d{1,4}|\d{2}BH\d{4}[A-Z]{1,2})$/;

export function isFullMark(q: string): boolean {
	return FULL_MARK_RE.test(normMark(q));
}

/** True when the omnibar should offer the officer-only full-mark lookup. Pure, so the
 *  unit test asserts it — including the primary case: a full mark with NO watchlist
 *  match. FIX-E-LOOKUP round 1: the predicate is the OFFER's own rule — isFullMark AND
 *  a raw mark shape — because isFullMark alone read a date phrase ("on 12 oct 2026")
 *  as ON-12-OCT-2026, a month-series mark. FIX-E-LOOKUP round 2 (audit E): the raw
 *  shape is the mask's STATE-CODE rule, not hasRawMark's upper-case superset pass —
 *  that pass ignores state codes, so all-caps dates still offered while 1–3-digit
 *  marks plates.py accepts ("MH01AB123") stopped offering. result.mark is NOT part of
 *  the predicate: the watchlist search never sets mark for a BH query, and the offer
 *  must still offer there; a command query refuses through isFullMark (the omnibar
 *  additionally renders only when open). */
export function lookupOfferActive(_result: Pick<SearchResult, 'mark'> | null, q: string, officerOn: boolean): boolean {
	const mark = q.trim();
	if (!officerOn || !isFullMark(mark)) return false;
	// the BH series: plates.py accepts it, the mask's state-code rule structurally cannot see it
	if (/^\d{2}BH\d{4}[A-Z]{1,2}$/.test(normMark(mark))) return true;
	return isStateCodeMark(mark);
}

/** The month word in a candidate's series (mask.ts's isDateShape rule). */
const MONTH_WORD_RE = /^(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)$/i;
/** The separators between a mark's parts that normMark strips (the oracle's set: space, dash, dot). */
const MARK_SEP_SRC = '[\\s.\\-]{0,3}';
/** The mask's state-code mark shape on the raw text: a REAL state code, a 1–2-digit
 *  RTO number, an optional series, a 1–4-digit number — the offer-side twin of
 *  mask.ts's any-case pass (its upper-case superset pass is NOT an offer rule).
 *  Group 2 the state code, 3 the series, 4 the separator after it, 5 the number. */
const STATE_MARK_SRC = '\\b((' + STATE_CODES.join('|') + ')' + MARK_SEP_SRC + '\\d{1,2}' + MARK_SEP_SRC + '([a-z]{0,3})(' + MARK_SEP_SRC + ')?)(\\d{1,4})\\b';
const STATE_MARK_RE = new RegExp(STATE_MARK_SRC, 'i');

/** True when the raw query is a mark under the mask's state-code rule: a real state
 *  code and no date shape (a month series with a separator before the number, unless
 *  state code and series are both upper case — "DL 8 SEP 1234" is a mark as written,
 *  "dl 8 sep 1234" is a date, and "ON 12 OCT 2026" is no mark at all: ON is no state
 *  code). hasRawMark is deliberately NOT reused: its upper-case superset pass masks
 *  fail-closed but must not OFFER. */
function isStateCodeMark(q: string): boolean {
	const m = q.match(STATE_MARK_RE);
	if (!m) return false;
	const state = m[2];
	const series = m[3];
	const sepAfter = m[4];
	if (series && sepAfter && MONTH_WORD_RE.test(series) && !(state === state.toUpperCase() && series === series.toUpperCase())) return false;
	return true;
}

/** What a watchlisted vehicle's mark can be compared on: the raw mark, else the masked mark's visible prefix. */
function markKey(row: ObjectRow): { key: string; full: boolean } | null {
	const raw = typeof row.props.plate === 'string' ? normMark(row.props.plate) : '';
	if (raw && !raw.includes('•')) return { key: raw, full: true };
	const masked = typeof row.props.plate_masked === 'string' ? row.props.plate_masked : row.label;
	const visible = normMark(masked).split('•')[0];
	return visible ? { key: visible, full: false } : null;
}

/** The watchlisted vehicles whose mark is `q` (or starts with it, 6+ characters). Never reads or recommendations. */
export function matchMark(rows: readonly ObjectRow[], q: string): ObjectRow[] {
	const n = normMark(q);
	if (n.length < 4) return [];
	const out: ObjectRow[] = [];
	for (const r of rows) {
		if (r.kind !== 'vehicle') continue;
		const k = markKey(r);
		if (!k) continue;
		const hit = k.full ? k.key === n || (n.length >= 6 && k.key.startsWith(n)) : n.length >= 6 && n.length <= k.key.length && k.key.startsWith(n);
		if (hit) out.push(r);
	}
	return out;
}

// ── commands ───────────────────────────────────────────────────────────────

export type Command =
	| { type: 'fly'; target: string }
	| { type: 'units'; agency: string | null; road: string }
	| { type: 'layer'; id: string; on: boolean }
	| { type: 'sensor'; mode: string }
	| { type: 'ask'; question: string }
	/**
	 * A command typed up to its argument (F-20): the catalogue's templates fill
	 * "ask ", "fly to " … — the trimmed query is the grammar's head alone. The
	 * omnibar says what to type next, never "No matches".
	 */
	| { type: 'incomplete'; template: CommandTemplate };

export type CommandTemplate = 'fly' | 'units' | 'layer' | 'sensor' | 'ask';

/** A typed example of each template's full form (the grammar is English; places from the City Pack). */
export const COMMAND_EXAMPLES: Readonly<Record<CommandTemplate, string>> = {
	fly: `fly to ${landmarkName('sea_link', 'en')}`,
	units: `show police units near ${landmarkName('dadar_tt', 'en')}`,
	layer: 'layer events on',
	sensor: 'sensor ironbow',
	ask: `ask how is traffic near ${landmarkName('kings_circle', 'en')}`,
};

/** The legacy grammar (with or without a leading `>`), or null. */
export function parseCommand(q: string): Command | null {
	const s = q.replace(/^\s*>\s*/, '').trim();
	let m: RegExpMatchArray | null;
	if ((m = s.match(/^fly\s+to\s+(.+)$/i))) return { type: 'fly', target: m[1].trim() };
	if ((m = s.match(/^show\s+(?:(.+?)\s+)?units?\s+(?:near|on|at)\s+(.+)$/i))) return { type: 'units', agency: m[1]?.trim() || null, road: m[2].trim() };
	if ((m = s.match(/^layer\s+([a-z0-9-]+)\s+(on|off)$/i))) return { type: 'layer', id: m[1].toLowerCase(), on: m[2].toLowerCase() === 'on' };
	if ((m = s.match(/^sensor\s+(.+)$/i))) return { type: 'sensor', mode: sensorMode(m[1]) ?? m[1].trim().toLowerCase() };
	if ((m = s.match(/^ask\s+(.+)$/i))) return { type: 'ask', question: m[1].trim() };
	// a template's head with nothing after it yet (F-20)
	if (/^fly(?:\s+to)?$/i.test(s)) return { type: 'incomplete', template: 'fly' };
	if (/^show(?:\s+\S+)?\s+units?(?:\s+(?:near|on|at))?$/i.test(s)) return { type: 'incomplete', template: 'units' };
	if (/^layer(?:\s+[a-z0-9-]+)?$/i.test(s)) return { type: 'incomplete', template: 'layer' };
	if (/^sensor$/i.test(s)) return { type: 'incomplete', template: 'sensor' };
	if (/^ask$/i.test(s)) return { type: 'incomplete', template: 'ask' };
	return null;
}

// ── the sensor grammar's typeable words (FIX-E-LOOKUP audit E, item 3) ─────
// The omnibar's help lists the palette IN WORDS (map_pal_*), so the grammar
// accepts those words: "sensor ironbow", "sensor white hot", and their HI/MR
// spellings, in any console language — plus the mode ids the canvas speaks.
// An unresolvable word stays the raw mode; the omnibar refuses it WITHOUT
// echoing it inside a localised label.

const SENSOR_WORD_MAP: Map<string, string> = (() => {
	const map = new Map<string, string>([
		['raw', 'raw'],
		['flir-whot', 'flir-whot'],
		['flir-bhot', 'flir-bhot'],
		['flir-iron', 'flir-iron'],
		['command', 'raw'],
	]);
	for (const lang of ['en', 'hi', 'mr']) {
		for (const [key, mode] of [
			['map_pal_raw', 'raw'],
			['map_pal_whot', 'flir-whot'],
			['map_pal_bhot', 'flir-bhot'],
			['map_pal_iron', 'flir-iron'],
		] as const) {
			const word = t(lang, key).trim().toLowerCase();
			if (word && word !== key) map.set(word, mode);
		}
	}
	return map;
})();

/** A typed sensor word as the canvas's mode id, or null when it names no mode. */
export function sensorMode(word: string): string | null {
	return SENSOR_WORD_MAP.get(word.trim().toLowerCase()) ?? null;
}

// ── the search ─────────────────────────────────────────────────────────────

export interface SearchGroup {
	kind: string;
	total: number;
	items: ObjectRow[];
	best: number;
}

export interface SearchResult {
	query: string;
	/** The `kind:`, `state:` and `source:` tokens. */
	filters: { kind?: string; state?: string; source?: string };
	/** The words matched against labels (lower case). */
	words: string[];
	groups: SearchGroup[];
	total: number;
	/** Every matching URN (≤ 500), for "Explore all N results in a table". */
	urns: string[];
	/** Set when the query is a full mark or a 6+ mark prefix: only watchlisted vehicles were searched. */
	mark: { matches: ObjectRow[] } | null;
	/** The query starts with `>` (commands only). */
	commandMode: boolean;
	/** The legacy grammar the query spells, if any. */
	command: Command | null;
}

const haystacks = new WeakMap<ObjectRow, string>();

/** The lower-case text a row is matched on (masked: never a raw mark, whatever its props carry). */
export function haystack(row: ObjectRow): string {
	let h = haystacks.get(row);
	if (h != null) return h;
	const p = row.props;
	const ev = (p.evidence ?? {}) as Record<string, unknown>;
	const parts = [
		row.label,
		row.id,
		row.sublabel,
		p.road_name,
		ev.road_name,
		p.camera_id,
		ev.camera_id,
		p.name,
		p.plate_masked,
		// a vehicle's lawful basis in words ("Stolen vehicle (FIR)"): "stolen" finds it
		row.kind === 'vehicle' && typeof p.lawful_basis === 'string' ? human(p.lawful_basis) : null,
		typeof p.rule_id === 'string' ? (HUMAN[p.rule_id] ?? human(p.rule_id)) : null,
		p.agency_label,
		p.unit_id,
		p.toponym,
		p.canonical_name,
		KIND_WORDS[row.kind] ?? row.kind,
	];
	// masked whole (C6): a prop the oracle sends raw never makes a digit-by-digit oracle of the search
	h = maskMarks(parts.filter((x): x is string => typeof x === 'string' && x.length > 0).join(' · ')).toLowerCase();
	haystacks.set(row, h);
	return h;
}

const DELIM = /[\s·:(,–\-/]/;

/**
 * Search `rows` for `q`. Groups are ordered by their best match; each keeps
 * up to `limit` rows (best first, newest first among equals) and its total.
 */
export function search(rows: readonly ObjectRow[], q: string, opts: { limit?: number } = {}): SearchResult {
	const limit = opts.limit ?? 4;
	const query = q.trim();
	const commandMode = query.startsWith('>');
	const command = parseCommand(query);
	const empty: SearchResult = { query, filters: {}, words: [], groups: [], total: 0, urns: [], mark: null, commandMode, command };
	if (!query || commandMode || command) return empty;

	const filters: SearchResult['filters'] = {};
	const words: string[] = [];
	for (const tok of query.toLowerCase().split(/\s+/).filter(Boolean)) {
		const m = /^(kind|state|source):(.+)$/.exec(tok);
		if (m) filters[m[1] as 'kind' | 'state' | 'source'] = m[2];
		else words.push(tok);
	}

	// a registration mark: watchlisted vehicles only (SPEC §8.1)
	const joined = words.join('');
	if (isMarkQuery(joined)) {
		const matches = matchMark(rows, joined);
		return {
			...empty,
			filters,
			words: [joined.toLowerCase()],
			mark: { matches },
			groups: matches.length ? [{ kind: 'vehicle', total: matches.length, items: matches.slice(0, limit), best: 100 }] : [],
			total: matches.length,
			urns: matches.map((r) => r.urn),
		};
	}

	const byKind = new Map<string, { o: ObjectRow; score: number }[]>();
	const urns: string[] = [];
	for (const o of rows) {
		if (filters.kind && !(o.kind.startsWith(filters.kind) || (KIND_WORDS[o.kind] ?? '').split(' ').some((w) => w.startsWith(filters.kind as string)))) continue;
		if (filters.state && !String(o.state ?? '').toLowerCase().startsWith(filters.state)) continue;
		if (filters.source && !(o.source === filters.source || (filters.source === 'test' && o.test))) continue;
		let score = 0;
		if (words.length) {
			const hay = haystack(o);
			let ok = true;
			for (const w of words) {
				const i = hay.indexOf(w);
				if (i < 0) {
					ok = false;
					break;
				}
				score += i === 0 ? 30 : DELIM.test(hay[i - 1]) ? 18 : 6;
			}
			if (!ok) continue;
		} else if (!filters.kind && !filters.state && !filters.source) {
			continue;
		}
		score += KIND_WEIGHT[o.kind] ?? 1;
		if (o.test) score -= 8;
		const list = byKind.get(o.kind);
		if (list) list.push({ o, score });
		else byKind.set(o.kind, [{ o, score }]);
		if (urns.length < 500) urns.push(o.urn);
	}

	const groups: SearchGroup[] = [];
	for (const [kind, list] of byKind) {
		list.sort((a, b) => b.score - a.score || (b.o.t ?? 0) - (a.o.t ?? 0));
		groups.push({ kind, total: list.length, items: list.slice(0, limit).map((x) => x.o), best: list[0].score });
	}
	groups.sort((a, b) => b.best - a.best || b.total - a.total);
	const total = groups.reduce((n, g) => n + g.total, 0);
	return { ...empty, filters, words, groups, total, urns };
}

/** The longest query a filter label quotes (a label is at most 80 characters, hash.ts). */
const LABEL_QUERY_MAX = 40;

/**
 * The label "Explore all N results in a table" gives its filter. A filter
 * reaches the share hash and saved views (SPEC §7.5), so the label NEVER
 * quotes a typed registration mark: a mark query (a full mark or a 6+ prefix,
 * any case or spelling) is labelled with the matched watchlist vehicles'
 * MASKED marks ("Watchlist match: MH01EM•••1"), and any other query is
 * quoted through the mask (mask.ts), clipped to fit.
 */
export function exploreLabel(result: Pick<SearchResult, 'query' | 'mark'>, lang = 'en'): string {
	if (result.mark) {
		const marks = result.mark.matches.map((r) => maskMarks(r.label));
		return marks.length === 1 ? t(lang, 'ws_filter_watch_match', marks[0]) : t(lang, 'ws_filter_watch_matches', marks.length);
	}
	const q = maskMarks(result.query.trim());
	return t(lang, 'ws_filter_results', q.length > LABEL_QUERY_MAX ? `${q.slice(0, LABEL_QUERY_MAX - 1).trimEnd()}…` : q);
}

/** One run of highlighted text. */
export interface Span {
	text: string;
	mark: boolean;
}

/** `text` split into runs with exactly the matched spans marked (case-insensitive, non-overlapping). */
export function highlight(text: string, words: readonly string[]): Span[] {
	if (!text) return [];
	const lower = text.toLowerCase();
	const spans: [number, number][] = [];
	for (const w of words) {
		if (!w) continue;
		const i = lower.indexOf(w.toLowerCase());
		if (i >= 0) spans.push([i, i + w.length]);
	}
	spans.sort((a, b) => a[0] - b[0]);
	const out: Span[] = [];
	let at = 0;
	for (const [a, b] of spans) {
		if (a < at) continue;
		if (a > at) out.push({ text: text.slice(at, a), mark: false });
		out.push({ text: text.slice(a, b), mark: true });
		at = b;
	}
	if (at < text.length) out.push({ text: text.slice(at), mark: false });
	return out;
}
