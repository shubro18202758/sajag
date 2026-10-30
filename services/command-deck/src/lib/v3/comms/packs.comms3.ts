/**
 * The V3 Advisories string pack (V3-SPEC §6.7, §7.8) — only what the recomposed /comms prints that the existing packs
 * (strings.citizen: the desk's own words, the audiences, the withheld notices; packs.v3: the shell) do not already say.
 * EN here; HI and MR in ./packs.comms3.hi.ts and ./packs.comms3.mr.ts, complete for every key (tests/v3-comms.unit.mjs
 * checks it). Registered additively through registerPack(); loaded only by /comms. Every key starts with `v3c_`.
 *
 * Copy rules (v2 §11 + V3 §7.6): sentence case, no ALL-CAPS word outside the acronym list, at most one " · " per string,
 * titles ≤ 32 characters. Honest labels: nothing here says a draft was sent — a draft is a draft.
 */
import { registerPack } from '$lib/i18n/strings';
import { langChunks } from '$lib/i18n/load';

type Fn = (...args: unknown[]) => string;
export type CommsPack = Record<string, string | Fn>;

const s = (v: unknown) => String(v ?? '');

const en = {
	v3c_sub: 'Drafts for an officer to copy and send',
	v3c_events: 'Events',
	v3c_events_aria: 'Events an advisory can be written for',
	v3c_map_alt: (title: unknown) => `Map of the place for ${s(title)}`,
	v3c_no_place: 'No map position for this event yet',
	v3c_open_event: 'Open the event',
	v3c_row_withheld: 'Withheld from citizens',
	v3c_facts_used: 'Facts used',
	v3c_f_kind: 'Event kind',
	v3c_f_road: 'Stretch',
	v3c_f_hold: 'Hold',
	v3c_f_when: 'From',
	v3c_f_alt: 'Alternate',
	v3c_f_unknown: 'Not stated',
	v3c_sheet_aria: 'Draft log and dispatch threads',
	v3c_close: 'Close',
	v3c_copy_lang: (name: unknown) => `Copy the ${s(name)} draft`,
	v3c_copied_inline: 'Copied',
	v3c_tpl_hint: 'What a citizen would read for this kind of event',
	v3c_withheld_pick: 'Choose another audience to see its drafts',
};

export type CommsKey = keyof typeof en;

registerPack('en', en);

export const COMMS3_PACK_KEYS: readonly CommsKey[] = Object.keys(en) as CommsKey[];
export const COMMS3_PACKS: Record<string, CommsPack> = { en };

/** Register one language chunk (lib/i18n/load.ts's landing site; additive, first registration wins). */
export function adopt(code: 'hi' | 'mr', pack: CommsPack): void {
	COMMS3_PACKS[code] = pack;
	registerPack(code, pack);
}

/*
 * Language chunks (the deck's FIX-E-PERF2 pattern): HI and MR live only in their own files. The server render and every
 * non-production run register both before this module finishes evaluating; the production browser awaits the document's
 * language and loads the other on the first switch.
 */
if (process.env.NODE_ENV !== 'production' || import.meta.env.SSR !== false) {
	adopt('hi', (await import('./packs.comms3.hi')).hi);
	adopt('mr', (await import('./packs.comms3.mr')).mr);
} else {
	await langChunks('packs.comms3', (code) =>
		code === 'hi' ? import('./packs.comms3.hi').then((c) => adopt('hi', c.hi)) : import('./packs.comms3.mr').then((c) => adopt('mr', c.mr)),
	);
}
