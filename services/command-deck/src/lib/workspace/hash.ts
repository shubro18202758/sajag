/**
 * The workspace's share-hash keys (plan R24, SPEC §7.5). share-link.ts (S3)
 * keeps the camera, layers and `sel`; these optional keys carry the rest of
 * a view, and old receivers ignore them:
 *
 *   view   map | graph | table | split
 *   t0,t1  the time window, epoch ms (absent = live)
 *   f      the filters: base64url JSON [{field, values, label}]
 *   dock   three characters: left 0|1, right 0|1, bottom c(ompact)|f(ull)|o(ff)
 *   items  the selection, comma-separated URNs (≤ 50)
 *
 * Egress is always masked (C6): URNs only, never a registration mark; every
 * filter label and value passes through the mark mask on the way out AND on
 * the way in. The mask is the workspace's own (mask.ts): case-insensitive
 * and separator-tolerant, because a label or a name can carry what an
 * operator TYPED ("mh47em9001", "MH.47.EM.9001"), not only server text. The
 * decoder never trusts the hash: an oversize, malformed or hostile value (a
 * script, a `javascript:` URL, bad base64, an out-of-range time, an unknown
 * field, a URN outside the C-C grammar) is dropped, never applied.
 */
import { parseUrn } from '$lib/gods-eye/city-api';
import { hasRawMark, maskMarks } from './mask';
import type { Docks, Filter, FilterField, View } from './types';

export const VIEWS: readonly View[] = ['map', 'graph', 'table', 'split'];
export const FILTER_FIELDS: readonly FilterField[] = ['kind', 'state', 'source', 'hour', 'road', 'camera', 'urns'];

/** The keys this module owns (share-link.ts passes them through untouched). */
export const WORKSPACE_KEYS = ['view', 't0', 't1', 'f', 'dock', 'items'] as const;

export interface WorkspaceKeys {
	view: View;
	timeWindow: [number, number] | null;
	filters: readonly Filter[];
	docks: Docks;
	items: readonly string[];
}

const T_MIN = Date.UTC(2000, 0, 1);
const T_MAX = Date.UTC(2100, 0, 1);
const WINDOW_MAX_MS = 31 * 86_400_000;
const F_MAX_CHARS = 4096;
const FILTERS_MAX = 12;
const VALUES_MAX = 500;
const VALUE_MAX_CHARS = 128;
const LABEL_MAX_CHARS = 80;
const ITEMS_MAX = 50;

// ── base64url (UTF-8) ───────────────────────────────────────────────────

function toBase64Url(text: string): string {
	const bytes = new TextEncoder().encode(text);
	let bin = '';
	for (const b of bytes) bin += String.fromCharCode(b);
	return btoa(bin).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

function fromBase64Url(s: string): string | null {
	if (!/^[A-Za-z0-9_-]+$/.test(s)) return null;
	try {
		const bin = atob(s.replace(/-/g, '+').replace(/_/g, '/') + '='.repeat((4 - (s.length % 4)) % 4));
		const bytes = Uint8Array.from(bin, (c) => c.charCodeAt(0));
		return new TextDecoder('utf-8', { fatal: true }).decode(bytes);
	} catch {
		return null;
	}
}

// ── value guards ────────────────────────────────────────────────────────

/**
 * A safe display string: no control characters or markup, no script URL,
 * every mark masked in any case or spelling (mask.ts); null when hostile.
 */
export function safeText(v: unknown, max: number): string | null {
	if (typeof v !== 'string') return null;
	const s = v.trim();
	if (!s || s.length > max) return null;
	// eslint-disable-next-line no-control-regex
	if (/[\u0000-\u001f\u007f<>`]/.test(s)) return null;
	if (/^\s*(?:javascript|data|vbscript)\s*:/i.test(s)) return null;
	return maskMarks(s);
}

/** A filter as the hash may carry it (ids are local and regenerated); null when anything is off. */
function cleanFilter(raw: unknown, id: string): Filter | null {
	if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return null;
	const r = raw as Record<string, unknown>;
	const field = r.field;
	if (typeof field !== 'string' || !(FILTER_FIELDS as readonly string[]).includes(field)) return null;
	if (!Array.isArray(r.values) || r.values.length === 0 || r.values.length > VALUES_MAX) return null;
	const values: string[] = [];
	for (const v of r.values) {
		if (field === 'urns') {
			if (typeof v !== 'string' || !parseUrn(v)) return null;
			values.push(v);
		} else {
			const s = safeText(v, VALUE_MAX_CHARS);
			if (s == null) return null;
			values.push(s);
		}
	}
	// a label that is there must be clean: a hostile one rejects the filter (never a silent fallback)
	if (r.label != null && safeText(r.label, LABEL_MAX_CHARS) == null) return null;
	const label = safeText(r.label, LABEL_MAX_CHARS) ?? field;
	return { id, field: field as FilterField, values, label };
}

/** Sanitise filters for egress or storage (masked labels and values, valid URNs only). */
export function cleanFilters(filters: readonly unknown[], idOf: (i: number) => string = (i) => `f${i + 1}`): Filter[] {
	const out: Filter[] = [];
	for (const f of filters.slice(0, FILTERS_MAX)) {
		const c = cleanFilter(f, idOf(out.length));
		if (c) out.push(c);
	}
	return out;
}

function cleanItems(list: readonly unknown[]): string[] {
	const seen = new Set<string>();
	const out: string[] = [];
	for (const u of list) {
		if (typeof u !== 'string' || seen.has(u) || !parseUrn(u)) continue;
		seen.add(u);
		out.push(u);
		if (out.length >= ITEMS_MAX) break;
	}
	return out;
}

function windowOk(w: readonly [number, number] | null | undefined): w is [number, number] {
	if (!w) return false;
	const [a, b] = w;
	return Number.isInteger(a) && Number.isInteger(b) && a >= T_MIN && b <= T_MAX && a < b && b - a <= WINDOW_MAX_MS;
}

// ── encode / decode ─────────────────────────────────────────────────────

/** The workspace keys of a view as a query string (no leading '&' or '#'); masked, URNs only. */
export function encodeWorkspaceKeys(state: Partial<WorkspaceKeys>): string {
	const params = new URLSearchParams();
	if (state.view && (VIEWS as readonly string[]).includes(state.view)) params.set('view', state.view);
	if (state.timeWindow && windowOk([Math.round(state.timeWindow[0]), Math.round(state.timeWindow[1])])) {
		params.set('t0', String(Math.round(state.timeWindow[0])));
		params.set('t1', String(Math.round(state.timeWindow[1])));
	}
	if (state.filters?.length) {
		const clean = cleanFilters(state.filters).map((f) => ({ field: f.field, values: f.values, label: f.label }));
		if (clean.length) {
			const f = toBase64Url(JSON.stringify(clean));
			if (f.length <= F_MAX_CHARS) params.set('f', f);
		}
	}
	if (state.docks) {
		const d = state.docks;
		params.set('dock', `${d.left ? 1 : 0}${d.right ? 1 : 0}${d.bottom === 'full' ? 'f' : d.bottom === 'off' ? 'o' : 'c'}`);
	}
	if (state.items?.length) {
		const items = cleanItems(state.items);
		if (items.length) params.set('items', items.join(','));
	}
	return params.toString();
}

/** The workspace keys a hash or query carries; every hostile or malformed value is dropped. */
export function decodeWorkspaceKeys(input: URLSearchParams | string): Partial<WorkspaceKeys> {
	let params: URLSearchParams;
	try {
		params = typeof input === 'string' ? new URLSearchParams(input.replace(/^[#?]/, '')) : input;
	} catch {
		return {};
	}
	const out: Partial<WorkspaceKeys> = {};
	const view = params.get('view');
	if (view && (VIEWS as readonly string[]).includes(view)) out.view = view as View;

	const t0 = params.get('t0');
	const t1 = params.get('t1');
	if (t0 && t1 && /^\d{10,14}$/.test(t0) && /^\d{10,14}$/.test(t1)) {
		const w: [number, number] = [Number(t0), Number(t1)];
		if (windowOk(w)) out.timeWindow = w;
	}

	const f = params.get('f');
	if (f && f.length <= F_MAX_CHARS) {
		const json = fromBase64Url(f);
		if (json != null) {
			try {
				const parsed: unknown = JSON.parse(json);
				if (Array.isArray(parsed) && parsed.length <= FILTERS_MAX) {
					// every filter must pass: a hash with one hostile filter applies none
					const clean = cleanFilters(parsed);
					if (clean.length === parsed.length) out.filters = clean;
				}
			} catch {
				// bad JSON: dropped
			}
		}
	}

	const dock = params.get('dock');
	if (dock && /^[01][01][cfo]$/.test(dock)) {
		out.docks = { left: dock[0] === '1', right: dock[1] === '1', bottom: dock[2] === 'f' ? 'full' : dock[2] === 'o' ? 'off' : 'compact' };
	}

	const items = params.get('items');
	if (items && items.length <= ITEMS_MAX * 120) {
		const parts = items.split(',');
		const clean = cleanItems(parts);
		if (clean.length) out.items = clean;
	}
	return out;
}

/**
 * True when a link, a hash or a query string carries a raw registration mark
 * anywhere (the egress check Copy link runs before it writes). Any case and
 * any spelling counts ("mh47em9001", "MH.47.EM.9001"): the same rule as the
 * mask (mask.ts). The filters (`f`) are read DECODED, never as base64, and a
 * URN's UUID is an id, never a mark.
 */
export function carriesRawMark(s: string): boolean {
	if (!s) return false;
	const cut = s.indexOf('#');
	const head = cut >= 0 ? s.slice(0, cut) : '';
	const body = (cut >= 0 ? s.slice(cut + 1) : s).replace(/^\?/, '');
	let headText = head;
	try {
		headText = decodeURIComponent(head);
	} catch {
		// keep the raw text
	}
	if (hasRawMark(headText)) return true;
	let params: URLSearchParams;
	try {
		params = new URLSearchParams(body);
	} catch {
		return hasRawMark(body);
	}
	for (const [k, v] of params) {
		if (k === 'f') {
			const json = fromBase64Url(v);
			if (hasRawMark(json ?? v)) return true;
		} else if (hasRawMark(`${k}=${v}`)) {
			return true;
		}
	}
	return false;
}
