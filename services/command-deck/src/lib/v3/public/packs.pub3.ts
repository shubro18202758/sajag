/**
 * The V3 public-pages string pack (V3-SPEC §6.8, §7.8) — only what the restyled /citizen and /driver print that the
 * deck's public strings (strings.ts, strings.citizen.ts) do not already say. EN here; HI and MR in ./packs.pub3.hi.ts and
 * ./packs.pub3.mr.ts, complete for every key (tests/v3-public.unit.mjs checks it). Registered additively through
 * registerPack(); loaded only by the public pages. Every key starts with `v3p_`.
 *
 * Copy rules (v2 §11 + V3 §7.6): sentence case, at most one " · " per string. The public pages never say a draft or a
 * simulation is real: provenance words (simulated feed, emulated, offline preview) are the deck's own and stay.
 */
import { registerPack } from '$lib/i18n/strings';
import { langChunks } from '$lib/i18n/load';

type Fn = (...args: unknown[]) => string;
export type PubPack = Record<string, string | Fn>;

const s = (v: unknown) => String(v ?? '');

const en = {
	v3p_skip: 'Skip to the page',
	v3p_logo: 'Sajag',
	v3p_lang_short_en: 'EN',
	v3p_lang_short_hi: 'हिं',
	v3p_lang_short_mr: 'मरा',
	v3p_hold_map_alt: 'Map of the roads that hold for this event',
	v3p_step: (n: unknown) => `Step ${s(n)}`,
	v3p_sat_credit: 'Map data © OpenStreetMap contributors',
	v3p_map_title: 'The corridor map',
	v3p_open_driver: 'Open the driver page',
	v3p_view_tabs: 'Public pages',
};

export type PubKey = keyof typeof en;

registerPack('en', en);

export const PUB3_PACK_KEYS: readonly PubKey[] = Object.keys(en) as PubKey[];
export const PUB3_PACKS: Record<string, PubPack> = { en };

/** Register one language chunk (lib/i18n/load.ts's landing site; additive, first registration wins). */
export function adopt(code: 'hi' | 'mr', pack: PubPack): void {
	PUB3_PACKS[code] = pack;
	registerPack(code, pack);
}

/*
 * Language chunks (the deck's FIX-E-PERF2 pattern): HI and MR live only in their own files. The server render and every
 * non-production run register both before this module finishes evaluating; the production browser awaits the document's
 * language and loads the other on the first switch.
 */
if (process.env.NODE_ENV !== 'production' || import.meta.env.SSR !== false) {
	adopt('hi', (await import('./packs.pub3.hi')).hi);
	adopt('mr', (await import('./packs.pub3.mr')).mr);
} else {
	await langChunks('packs.pub3', (code) =>
		code === 'hi' ? import('./packs.pub3.hi').then((c) => adopt('hi', c.hi)) : import('./packs.pub3.mr').then((c) => adopt('mr', c.mr)),
	);
}
