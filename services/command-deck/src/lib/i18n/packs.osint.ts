/**
 * The OSINT string pack (EN / HI / MR) — the reported-situation and place
 * surfaces (OS-DECK-A): the report and place inspector sections, the source
 * list, the six reported-situation kinds (`kind_*` so `kindLabel` resolves
 * them in every language; the core pack already carries them — registerPack
 * is first-wins, so these are the pack's own copy, kept in parity by
 * tests/osint.unit.mjs).
 *
 * Every new key starts with `os_`. EN is sentence case, no ALL-CAPS word
 * outside the acronym allowlist, at most one " · " per string, section
 * titles at most 32 characters (tests/copy-lint.mjs; targets file
 * style-lint.targets/osint.json). Registered additively through
 * registerPack(); the core packs stay untouched.
 *
 * Copy describes only what the system does (SPEC §9.1, ethics rules 1–3):
 * a reported situation is for RESPONSE and never identifies people; a
 * news/social link is withheld because its URL may name a person; social
 * posts enter only as an aggregate signal about a place.
 */
import { registerPack } from './strings';
import { langChunks } from './load';

type Fn = (...args: unknown[]) => string;
type OsintPack = Record<string, string | Fn>;

const en = {
	// the six reported-situation kinds (kindLabel; parity with the core pack)
	kind_reported_crime: 'Reported crime',
	kind_public_disorder: 'Public disorder',
	kind_road_accident: 'Road accident',
	kind_hazard: 'Hazard',
	kind_flooding: 'Waterlogging',
	kind_infra_failure: 'Infrastructure failure',

	// section titles
	os_group_situation: 'Situation',
	os_group_verification: 'Verification',
	os_group_location: 'Location',
	os_group_sources: 'Sources',
	os_group_live: 'Live state',
	os_group_place: 'Place',

	// situation rows
	os_class: 'Class',
	os_subtype: 'Subtype',
	os_correlated: 'Correlated classes',
	os_summary: 'Summary',
	os_event_kind_reported_crime: 'Reported crime',
	os_event_kind_public_disorder: 'Public disorder',
	os_event_kind_road_accident: 'Road accident',
	os_event_kind_hazard: 'Hazard',
	os_event_kind_flooding: 'Waterlogging',
	os_event_kind_infra_failure: 'Infrastructure failure',
	os_event_kind_other: 'Corridor event',

	// verification rows (de-duplicated with the header: no credibility or tier row here)
	os_independent_publishers: 'Independent publishers',
	os_cross_type: 'Cross-type corroboration',
	os_yes: 'Yes',
	os_no: 'No',

	// location rows and the district note
	os_toponym: 'Place',
	os_road: 'Road',
	os_junction: 'Junction',
	os_geocode: 'Geocode confidence',
	os_bucket_high: 'high',
	os_bucket_medium: 'medium',
	os_bucket_low: 'low',
	os_area_note: 'District-level report: not a street location',

	// sources
	os_source_link_withheld: 'Source link withheld (may name a person)',
	// the context note, the deck's OWN two keys (official vs report) — the oracle's EN
	// strings are matched, never shown raw
	os_context_official: 'District warning in effect',
	os_context_report: 'District-level report in effect',
	// the figure's hint words (mid-sentence after the count, so they start lower case)
	os_fig_context_official: 'district warning in effect',
	os_fig_context_report: 'district-level report in effect',
	// the dossier's per-signal sources: a cached-sample tag only when the copy really is
	// one (fetch_mode is 'live' or 'cached-sample'), and each tier in words (S3 round 2)
	os_fetch_cached: 'cached sample',
	os_tier_official: 'Official',
	os_tier_aggregator: 'Aggregator',
	os_tier_news_regional: 'News regional',
	os_tier_news_national: 'News national',
	os_tier_social_unverified: 'Social unverified',

	// the map pick card and the layer line (fix round 2, items 6 and 14: the same words
	// in every language; the count rides the layer hint mid-sentence, lower case)
	os_pick_reported: 'Reported',
	os_pick_credibility: 'credibility',
	os_pick_street: 'A reported situation for response.',
	os_pick_district: 'A district-level report, shown at the district’s reference point. The report covers the whole district, not this spot.',
	os_pick_area_ring: 'A marker ring around the district’s reference point, not the area the report covers.',
	os_pick_never_people: 'Reported situations are about places, never people.',
	os_layer_held_one: 'single-post social report held city-wide (never shown)',
	os_layer_down: 'city fusion service unavailable — reported situations not shown',
	os_layer_on_canvas: (n: unknown) => `${n} reported situations on canvas`,
	os_layer_area: (n: unknown) => `${n} area-level`,
	os_layer_waiting: (n: unknown) => `${n} awaiting a decision`,
	os_layer_unmapped: (n: unknown) => `${n} without a city point`,
	os_pick_at: (place: unknown) => `at ${place}`,
	os_layer_held_many: 'single-post social reports held city-wide (never shown)',

	// live state
	os_attach: 'State',
	os_attach_novel: 'New situation (first report)',
	os_corroborates: 'Corroborates a live object',
	os_promoted_to: 'Promoted to a corridor event',

	// place
	os_place_name: 'Name',
	os_place_type: 'Feature type',
	os_surface_forms: 'Also known as',
	os_place_reports: 'Linked reports',

	// the one rule note (ethics rules 1–3)
	os_rule_note: 'Reported situation for response. Sajag never identifies people.',

	// the reported-situation row state (generic.ts stateWord: no workspace key exists for
	// 'surfaced', so the osint pack names it — the header tag localizes in HI/MR too)
	os_state_surfaced: 'Surfaced',

	// non-decision actions (id osint.map; Show on map is the workspace's own core action)
	os_act_search_around: 'Search around the place',
	os_act_sources: 'Open the source list',
} satisfies OsintPack;



registerPack('en', en);

/** The pack's own tables (tests/osint.unit.mjs: the EN/HI/MR key-parity check). */
export const OSINT_PACKS: Record<string, OsintPack> = { en };
export type OsintKey = keyof typeof en;

/**
 * Register one language chunk (lib/i18n/load.ts's landing site; additive,
 * first registration wins — the core's documented semantics).
 */
export function adopt(code: 'hi' | 'mr', pack: OsintPack): void {
	OSINT_PACKS[code] = pack;
	registerPack(code, pack);
}

/*
 * Language chunks (FIX-E-PERF2): this module's HI and MR strings live ONLY in
 * ./packs.osint.hi.ts and ./packs.osint.mr.ts. The server render and every non-production
 * run (vite dev, the node test harness) register both before this module
 * finishes evaluating (SSR paints the persisted language). The production
 * browser registers the loader instead and awaits the document's language
 * before this module finishes evaluating — hydration waits for it, so a cold
 * HI/MR load never flashes English — and the other language loads on the
 * first switch (lib/i18n/load.ts). The prod client build folds the condition
 * to its else branch.
 */
if (process.env.NODE_ENV !== 'production' || import.meta.env.SSR !== false) {
	adopt('hi', (await import('./packs.osint.hi')).hi);
	adopt('mr', (await import('./packs.osint.mr')).mr);
} else {
	await langChunks('packs.osint', (code) =>
		code === 'hi' ? import('./packs.osint.hi').then((c) => adopt('hi', c.hi)) : import('./packs.osint.mr').then((c) => adopt('mr', c.mr)),
	);
}
