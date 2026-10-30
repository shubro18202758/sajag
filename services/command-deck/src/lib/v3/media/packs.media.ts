/**
 * The imagery string pack: the honest labels and alternative texts of the artwork, the reference photos and the
 * agency marks. EN here; HI and MR in ./packs.media.hi.ts and ./packs.media.mr.ts, complete for every key
 * (tests/v3-media.unit.mjs checks it). Registered additively through registerPack(); every key starts with `v3i_` (imagery).
 *
 * Honest labels: an illustration says it is one; a photo always says "Reference photo · not live" with its credit; a
 * mark belongs to its owner and Sajag says it is not affiliated with or endorsed by them.
 */
import { registerPack } from '$lib/i18n/strings';
import { langChunks } from '$lib/i18n/load';

type Fn = (...args: unknown[]) => string;
export type MediaPack = Record<string, string | Fn>;

const s = (v: unknown) => String(v ?? '');

const en = {
	v3i_ref_photo: 'Reference photo · not live',
	v3i_photo_alt: (title: unknown) => `Reference photo of ${s(title)}, not a live image`,
	v3i_photo_tip: (title: unknown, credit: unknown) => `${s(title)}. ${s(credit)}. What the place looks like, not what is happening there now.`,
	v3i_illustration: 'Illustration',
	v3i_art_alt: (kind: unknown) => `Illustration: ${s(kind)}`,
	v3i_vehicle_alt: (cls: unknown) => `Illustration of the vehicle class: ${s(cls)}`,
	v3i_convoy_alt: 'Illustration: a lead vehicle, the protected car and a tail vehicle',
	v3i_cls_taxi: 'Kaali-peeli taxi',
	v3i_cls_car: 'Car',
	v3i_cls_suv: 'Utility vehicle',
	v3i_cls_two_wheeler: 'Two-wheeler',
	v3i_cls_auto_rickshaw: 'Auto-rickshaw',
	v3i_cls_toto: 'E-rickshaw',
	v3i_cls_bus: 'Bus',
	v3i_cls_truck: 'Goods truck',
	v3i_cls_tempo: 'Tempo',
	v3i_cls_ambulance: 'Ambulance',
	v3i_cls_patrol: 'Patrol vehicle',
	v3i_cls_fire_tender: 'Fire tender',
	v3i_cls_convoy: 'Convoy',
	v3i_cls_convoy_zplus: 'a class Z plus convoy with an ambulance at the tail',
	v3i_cls_convoy_y: 'a class Y escort, one lead vehicle',
	v3i_cls_convoy_x: 'the protected car alone, class X',
	v3i_scene_dawn: 'Illustration: Mumbai at dawn, the Sea Link across the bay',
	v3i_scene_day: 'Illustration: Mumbai by day, the Sea Link over the Arabian Sea and the towers of Worli',
	v3i_scene_dusk: 'Illustration: Mumbai at dusk, the first lights on the Sea Link',
	v3i_scene_night: 'Illustration: Mumbai at night, the Sea Link lit over the sea',
	'v3i_scene_all-clear': 'Illustration: a calm morning on the seafront, the Sea Link beyond, the signals green',
	v3i_mark_alt: (name: unknown) => `${s(name)} mark`,
	v3i_marks_credit: 'Agency and source marks belong to their owners. Sajag is a prototype and is not affiliated with or endorsed by them.',
	v3i_photos_credit: 'Reference photos: Wikimedia Commons contributors, each under its own licence.',
	v3i_photos_link: 'Photo credits',
	v3i_art_credit: 'Vehicle and scene artwork: original illustrations, not photographs or sensor images.',
	v3i_reported_by: (name: unknown) => `Reported by ${s(name)}`,
	v3i_on_map: 'Map of the place',
	v3i_agency_police: 'Mumbai Police',
	v3i_agency_traffic: 'Mumbai Traffic Police',
	v3i_agency_ems: 'Ambulance (108)',
	v3i_agency_municipal: 'Brihanmumbai Municipal Corporation (BMC)',
	v3i_agency_disaster: 'BMC Disaster Management (1916)',
	v3i_agency_ndma: 'National Disaster Management Authority',
	v3i_agency_imd: 'India Meteorological Department',
	v3i_agency_metro: 'Mumbai Metro',
	v3i_agency_wbtc: 'BEST Undertaking (buses)',
	v3i_agency_osm: 'OpenStreetMap',
	v3i_agency_citizens: 'Citizens',
	v3i_gal_keyart: 'Key art',
	v3i_gal_shots: 'Vehicle shots',
	v3i_gal_scenes: 'City scenes',
	v3i_gal_photos: 'Reference photos',
	v3i_gal_marks: 'Agency and source marks',
};

export type MediaKey = keyof typeof en;

registerPack('en', en);

export const MEDIA_PACK_KEYS: readonly MediaKey[] = Object.keys(en) as MediaKey[];
export const MEDIA_PACKS: Record<string, MediaPack> = { en };

/** Register one language chunk (lib/i18n/load.ts's landing site; additive, first registration wins). */
export function adopt(code: 'hi' | 'mr', pack: MediaPack): void {
	MEDIA_PACKS[code] = pack;
	registerPack(code, pack);
}

/*
 * Language chunks (the deck's FIX-E-PERF2 pattern): HI and MR live only in their own files. The server render and every
 * non-production run register both before this module finishes evaluating; the production browser awaits the document's
 * language and loads the other on the first switch.
 */
if (process.env.NODE_ENV !== 'production' || import.meta.env.SSR !== false) {
	adopt('hi', (await import('./packs.media.hi')).hi);
	adopt('mr', (await import('./packs.media.mr')).mr);
} else {
	await langChunks('packs.media', (code) =>
		code === 'hi' ? import('./packs.media.hi').then((c) => adopt('hi', c.hi)) : import('./packs.media.mr').then((c) => adopt('mr', c.mr)),
	);
}
