/**
 * Per-language pack loading (FIX-E-PERF2).
 *
 * Every i18n pack module keeps its EN strings in place; its HI and MR strings
 * live ONLY in the sibling `.hi.ts` / `.mr.ts` modules. Who registers them:
 *
 *   - the server render and every non-production run (vite dev, the node
 *     test harness): the pack module itself imports both languages before it
 *     finishes evaluating, so SSR paints the persisted language and a test
 *     sees all three;
 *   - the production browser: the pack module registers its loader here
 *     (`langChunks`) and AWAITS the document's language (`<html lang>`, which
 *     the server set from the sajag_lang cookie or the route default) before it
 *     finishes evaluating. SvelteKit hydrates only after every route node's
 *     module graph has evaluated, so a cold HI/MR load hydrates with its
 *     strings already in — no English flash — and a pack module that first
 *     arrives with a lazily loaded panel lands its strings before the panel's
 *     import() resolves. The other languages load on the first switch
 *     (`ensureLang`, called by the ops store's `lang` setter and
 *     `adoptLangCookie`, the shells' language effect and the citizen alert's
 *     language choice).
 *
 * Every landing goes through the module's `adopt()` → `registerPack`, so `t()`'s
 * documented chain (lang → en → raw key) holds while a chunk is in flight — an
 * untranslated key never renders — and `setPacksRegisteredHook`'s subscriber
 * (pack-registry.svelte.ts, the runes side) re-runs every `t()` consumer once
 * the strings arrive. This module imports no pack, so a route ships the EN of
 * exactly the packs it imports, and it stays rune-free for the node harness.
 */
import { isLangChoice } from './lang-cookie';

/** One pack module's landing: import its `code` chunk and adopt it. */
export type LangLoader = (code: 'hi' | 'mr') => Promise<void>;

const loaders = new Map<string, LangLoader>();
/** `${id}:${lang}` → the flight (settled ones stay, so a repeat call is free). */
const flights = new Map<string, Promise<void>>();
/** Languages some caller asked for: a pack module that registers later loads them too. */
const wanted = new Set<'hi' | 'mr'>();

/**
 * The app's reactive hook (pack-registry.svelte.ts registers itself here once;
 * a rune-free harness runs without it).
 */
let onRegistered: ((lang: string) => void) | null = null;

/** Wire the post-registration re-render signal (pack-registry.svelte.ts does). */
export function setPacksRegisteredHook(fn: (lang: string) => void): void {
	onRegistered = fn;
}

/** 'hi' | 'mr' for a language that needs a chunk; null for EN and unknown codes (EN rides the eager graph). */
function chunked(lang: string | null | undefined): 'hi' | 'mr' | null {
	return isLangChoice(lang) && lang !== 'en' ? lang : null;
}

function loadOne(id: string, code: 'hi' | 'mr'): Promise<void> {
	const key = `${id}:${code}`;
	let flight = flights.get(key);
	if (!flight) {
		const load = loaders.get(id);
		if (!load) return Promise.resolve();
		flight = load(code)
			.then(() => {
				onRegistered?.(code); // every t() consumer re-renders with the module's strings
			})
			.catch((err) => {
				flights.delete(key); // a retry may try again; t() kept its EN fallback
				throw err;
			});
		flights.set(key, flight);
	}
	return flight;
}

/**
 * Register every known pack's chunk for `lang` (EN is always in). Resolves once
 * `t(lang, …)` answers in the language for every pack module evaluated so far
 * (a chunk that failed to fetch leaves t()'s EN fallback in place and is
 * retried by the next call; the promise never rejects); concurrent calls share
 * one flight per module; a repeat call is free.
 */
export function ensureLang(lang: string): Promise<void> {
	const code = chunked(lang);
	if (!code) return Promise.resolve();
	wanted.add(code);
	return Promise.all([...loaders.keys()].map((id) => loadOne(id, code).catch(() => {}))).then(() => {});
}

/** The language the server painted (`<html lang>`), when it needs a chunk; null outside a browser. */
function documentLang(): 'hi' | 'mr' | null {
	if (typeof document === 'undefined') return null;
	return chunked(document.documentElement?.lang);
}

/**
 * A pack module's production-browser registration (see the module comment):
 * register its loader, land every language already asked for, and resolve once
 * the document's language is in. A failed fetch never blocks the page — the
 * module finishes with t()'s EN fallback and a later ensureLang retries.
 */
export function langChunks(id: string, load: LangLoader): Promise<void> {
	if (!loaders.has(id)) loaders.set(id, load);
	const doc = documentLang();
	for (const code of wanted) if (code !== doc) void loadOne(id, code).catch(() => {});
	return doc ? loadOne(id, doc).catch(() => {}) : Promise.resolve();
}
