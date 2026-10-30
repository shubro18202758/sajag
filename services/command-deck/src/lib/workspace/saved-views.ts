/**
 * Saved views (SPEC §7.5): a named view kept in this browser's localStorage.
 * The logic only — the Explorer's list (UI-S2X) reads workspace.savedViews.
 *
 * What is stored is MASKED: a saved view is a share hash (URNs only, never a
 * registration mark; hash.ts masks every filter label and value) plus a
 * masked name — masked in any case and spelling (mask.ts), since a name is
 * what an operator typed. An officer's unmasked view is never written anywhere.
 * Storage can be missing, full or blocked (a private window): every access
 * is wrapped, and the workspace works without it.
 */
import { decodeWorkspaceKeys, encodeWorkspaceKeys, safeText } from './hash';
import { maskMarks } from './mask';
import type { SavedView } from './types';

export const SAVED_VIEWS_KEY = 'sajag.workspace.savedViews.v1';
export const SAVED_VIEWS_MAX = 50;
const NAME_MAX = 64;

/** The storage of this browser, or null when there is none (SSR, blocked). */
export function browserStorage(): Storage | null {
	try {
		return typeof localStorage === 'undefined' ? null : localStorage;
	} catch {
		return null;
	}
}

/** A view's name as it may be stored: trimmed, at most 64 characters, marks masked; null when unusable. */
export function cleanName(name: unknown): string | null {
	if (typeof name !== 'string') return null;
	return safeText(name.slice(0, NAME_MAX), NAME_MAX);
}

/**
 * A hash re-encoded through the workspace keys (and the S3 keys left as
 * they are, URNs only): anything hostile is dropped and every mark masked.
 */
export function cleanHash(hash: string): string {
	const body = hash.replace(/^#/, '');
	let params: URLSearchParams;
	try {
		params = new URLSearchParams(body);
	} catch {
		return '';
	}
	const ws = new URLSearchParams(encodeWorkspaceKeys(decodeWorkspaceKeys(params)));
	const out = new URLSearchParams();
	for (const [k, v] of params) {
		if (['view', 't0', 't1', 'f', 'dock', 'items'].includes(k)) continue;
		// the camera keys are numbers, layers ids, sel a URN: never a mark, masked anyway
		out.set(k, maskMarks(v));
	}
	for (const [k, v] of ws) out.set(k, v);
	return out.toString();
}

function valid(v: unknown): v is SavedView {
	if (!v || typeof v !== 'object') return false;
	const r = v as Record<string, unknown>;
	return typeof r.id === 'string' && typeof r.name === 'string' && typeof r.createdAt === 'number' && typeof r.hash === 'string';
}

export function loadSavedViews(storage: Storage | null): SavedView[] {
	if (!storage) return [];
	try {
		const raw = storage.getItem(SAVED_VIEWS_KEY);
		if (!raw) return [];
		const list: unknown = JSON.parse(raw);
		if (!Array.isArray(list)) return [];
		const out: SavedView[] = [];
		for (const v of list) {
			if (!valid(v)) continue;
			const name = cleanName(v.name);
			if (!name) continue;
			out.push({ id: v.id.slice(0, 40), name, createdAt: v.createdAt, hash: cleanHash(v.hash) });
			if (out.length >= SAVED_VIEWS_MAX) break;
		}
		return out;
	} catch {
		return [];
	}
}

export function storeSavedViews(storage: Storage | null, views: readonly SavedView[]): boolean {
	if (!storage) return false;
	try {
		storage.setItem(SAVED_VIEWS_KEY, JSON.stringify(views.slice(0, SAVED_VIEWS_MAX)));
		return true;
	} catch {
		return false;
	}
}

let seq = 0;

/** A new saved view (masked name and hash). */
export function newSavedView(name: string, hash: string, now: number): SavedView {
	seq += 1;
	return {
		id: `v${now.toString(36)}${seq.toString(36)}`,
		name: cleanName(name) ?? 'Untitled view',
		createdAt: now,
		hash: cleanHash(hash),
	};
}
