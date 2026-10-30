/**
 * The Explorer's model (SPEC §5.3, §7.4): the object types with their
 * registry counts and one state word each, and the saved view in force.
 *
 *   explorerKinds()  the canonical kinds in a fixed order, then any other
 *                    kind the registry holds (an open-source report and a
 *                    place appear through the generic adapter); each with
 *                    count(kind) — THE registry count, the same figure the
 *                    layer tree and the vitals card show — and one state word
 *                    ("2 open", "6 pending", "on watchlist")
 *   viewSignature()  what makes a view this view (mode, window, filters,
 *                    items, selection) — a saved view whose signature differs
 *                    from the workspace's now reads "edited"
 *
 * Pure: the selectors and rows are passed in (the unit test runs it on
 * fixtures).
 */
import { t } from '$lib/i18n/strings';
import '$lib/i18n/packs.views';
import { decodeWorkspaceKeys, encodeWorkspaceKeys } from '../../hash';
import { kindMany, shortStateWord } from '../../kinds/generic';
import type { Filter, ObjectRow, View } from '../../types';

/** The Explorer's kinds, in the order an analyst reads the city (unknown kinds follow, alphabetically). */
export const KIND_ORDER: readonly string[] = [
	'event',
	'osint_event',
	'vehicle',
	'sighting',
	'recommendation',
	'dispatch',
	'camera',
	'junction',
	'segment',
	'place',
	'anomaly',
	'unit',
	'convoy',
];

/** States that make an event open (planned, approved or running). */
export const OPEN_EVENT_STATES: ReadonlySet<string> = new Set(['active', 'planning', 'planned', 'approved', 'live', 'open']);

export interface ExplorerKind {
	kind: string;
	label: string;
	/** count(kind): the registry count (test objects excluded). */
	n: number;
	/** One state word, or null when nothing about the kind needs saying. */
	word: string | null;
}

/** The state that speaks for each kind, in priority order. */
const SPOKEN: readonly string[] = ['pending', 'requested', 'proposed', 'active', 'en_route', 'on_scene'];

function stateWordOf(kind: string, rows: readonly ObjectRow[], lang: string): string | null {
	const live = rows.filter((r) => !r.test);
	if (!live.length) return null;
	if (kind === 'event') {
		const open = live.filter((r) => r.state == null || OPEN_EVENT_STATES.has(r.state)).length;
		return open ? t(lang, 'vw_ex_open', open) : null;
	}
	if (kind === 'vehicle') return live.some((r) => r.state === 'flagged') ? t(lang, 'vw_ex_watchlist') : null;
	if (kind === 'osint_event') {
		const unverified = live.filter((r) => r.verification === 'UNVERIFIED-OSINT').length;
		return unverified ? t(lang, 'vw_ex_unverified', unverified) : null;
	}
	for (const s of SPOKEN) {
		const n = live.filter((r) => r.state === s).length;
		if (!n) continue;
		const key = `vw_ex_state_${s}`;
		const v = t(lang, key, n);
		return v === key ? `${n} ${(shortStateWord(s, lang) ?? s).toLowerCase()}` : v;
	}
	return null;
}

/** The Explorer's object types: canonical kinds (dimmed at 0) and every other kind the registry holds. */
export function explorerKinds(registry: readonly ObjectRow[], count: (kind: string) => number, lang = 'en'): ExplorerKind[] {
	const byKind = new Map<string, ObjectRow[]>();
	for (const r of registry) {
		const list = byKind.get(r.kind);
		if (list) list.push(r);
		else byKind.set(r.kind, [r]);
	}
	const extra = [...byKind.keys()].filter((k) => !KIND_ORDER.includes(k)).sort();
	return [...KIND_ORDER, ...extra].map((kind) => ({
		kind,
		label: kindMany(kind, lang),
		n: count(kind),
		word: stateWordOf(kind, byKind.get(kind) ?? [], lang),
	}));
}

/** The store keeps a watch title of at most 80 characters, without control characters, `<`, `>` or backticks. */
export const WATCH_TITLE_MAX = 80;

/**
 * A watch title the store accepts (watches.ts cleanWatch → hash.ts
 * safeText): the characters it refuses become spaces, runs of space
 * collapse, and a long title is cut to 80 characters with an ellipsis.
 * Null when nothing is left (the caller then names the watch by its kind).
 */
export function watchTitle(text: string | null | undefined): string | null {
	if (typeof text !== 'string') return null;
	// eslint-disable-next-line no-control-regex
	const s = text.replace(/[\u0000-\u001f\u007f<>`]/g, ' ').replace(/\s+/g, ' ').trim().replace(/^(?:javascript|data|vbscript)\s*:\s*/i, '');
	if (!s) return null;
	return s.length > WATCH_TITLE_MAX ? `${s.slice(0, WATCH_TITLE_MAX - 1).trimEnd()}…` : s;
}

/** The Explorer kind a workspace's filters explore: exactly one kind filter with exactly one value, else null. */
export function exploredKind(filters: readonly Filter[]): string | null {
	const kinds = filters.filter((f) => f.field === 'kind');
	return kinds.length === 1 && kinds[0].values.length === 1 ? kinds[0].values[0] : null;
}

export interface ViewState {
	view: View;
	timeWindow: readonly [number, number] | null;
	filters: readonly Filter[];
	items: readonly string[];
	sel: string | null;
}

/** A view's signature: its workspace keys (docks left out: they move with the screen) and its selection. */
export function viewSignature(s: ViewState): string {
	const keys = encodeWorkspaceKeys({ view: s.view, timeWindow: s.timeWindow ? [s.timeWindow[0], s.timeWindow[1]] : null, filters: s.filters, items: s.items });
	return `${keys}|sel=${s.sel ?? ''}`;
}

/** The signature a saved view's hash records. */
export function savedSignature(hash: string): string {
	const k = decodeWorkspaceKeys(hash);
	let sel: string | null = null;
	try {
		sel = new URLSearchParams(hash.replace(/^#/, '')).get('sel');
	} catch {
		sel = null;
	}
	return viewSignature({ view: k.view ?? 'map', timeWindow: k.timeWindow ?? null, filters: k.filters ?? [], items: k.items ?? (sel ? [sel] : []), sel });
}
