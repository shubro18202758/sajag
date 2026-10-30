/**
 * src/lib/ui string pack (EN / HI / MR) — the primitives' internal copy:
 * close and dismiss labels, provenance and verification labels, the masked
 * mark's explanation, the shortcut list, relative-time units. Registered
 * additively through registerPack(); the core packs stay untouched.
 *
 * Every key starts with `ui_`. EN is sentence case, no ALL-CAPS word outside
 * the acronym allowlist, at most one " · " per string, section titles at most
 * 32 characters (tests/copy-lint.mjs, target file style-lint.targets/s1.json).
 * HI and MR are complete for every key (tests/design-tokens.mjs checks it).
 *
 * Copy describes only what the system does (SPEC §9.1): the provenance and
 * verification labels are the plan's X2 contract; "Confirmed by officer" is a
 * label for a state the deck can display, not a claim that anything sets it.
 */
import { registerPack } from './strings';
import { langChunks } from './load';

type Fn = (...args: unknown[]) => string;
type UiPack = Record<string, string | Fn>;

const en = {
	ui_close: 'Close',
	ui_dismiss: 'Dismiss',
	ui_remove: 'Remove',
	ui_clear: 'Clear',
	ui_cancel: 'Cancel',
	ui_confirm: 'Confirm',
	ui_loading: 'Loading',
	ui_more: 'More',
	ui_err_404_title: 'Page not found',
	ui_err_404_body: 'There is no page at this address. Open a module from the bar, or go to the corridor workspace.',
	ui_err_title: 'This page could not be shown',
	ui_err_body: 'Something went wrong while loading it. Reload the page, or go to the corridor workspace.',
	ui_err_home: 'Open the corridor workspace',
	ui_expand: 'Expand',
	ui_collapse: 'Collapse',
	ui_show_details: 'Show details',
	ui_hide_details: 'Hide details',
	ui_sort_asc: 'Sorted ascending',
	ui_sort_desc: 'Sorted descending',
	ui_sort_by: (col: unknown) => `Sort by ${String(col)}`,
	ui_table_empty: 'Nothing to show',
	ui_location: 'Location',
	ui_notifications: 'Notifications',
	ui_resize: 'Resize',
	ui_trend: 'Trend',

	// the masked registration mark (Plate)
	ui_masked: 'Masked',
	ui_masked_tip: 'Registration mark masked until a duty officer is named.',

	// provenance (plan X2): labels, then the tooltip line
	ui_prov_emulated: 'Emulated',
	ui_prov_simulated: 'Simulated',
	ui_prov_test: 'Test',
	ui_prov_osint: 'Open-source',
	ui_prov_emulated_tip: 'From the scenario emulator. Not a field reading.',
	ui_prov_simulated_tip: 'Simulated traffic feed: synthetic observations.',
	ui_prov_test_tip: 'Rehearsal or test data.',
	ui_prov_osint_tip: 'From open sources. No verification state yet.',
	ui_prov_unknown: 'Unknown source',
	ui_prov_unknown_tip: 'The row names a source this console does not recognise.',
	ui_verif_unverified: 'Unverified OSINT',
	ui_verif_news: 'News-reported',
	ui_verif_official: 'Official, verified',
	ui_verif_confirmed: 'Confirmed by officer',
	ui_verif_unverified_tip: 'Open-source report, not corroborated by news or an official source.',
	ui_verif_news_tip: 'Reported by news outlets. Not verified by an official source.',
	ui_verif_official_tip: 'Issued by an official source, such as a public alert.',
	ui_verif_confirmed_tip: 'Confirmed by a named officer.',

	// layer visibility (EyeToggle)
	ui_eye_show: 'Show',
	ui_eye_hide: 'Hide',
	ui_eye_none: 'None now',

	// TimeField (IST, 24-hour)
	ui_time_ist: 'IST',
	ui_time_hint: 'IST, 24-hour clock',
	ui_time_invalid: 'Enter a time as hh:mm',
	ui_time_invalid_s: 'Enter a time as hh:mm:ss',

	// relative time (format.ts fmtAgo / fmtDuration)
	ui_now: 'Now',
	ui_ago: (x: unknown) => `${String(x)} ago`,
	ui_in: (x: unknown) => `in ${String(x)}`,
	ui_unit_s: 's',
	ui_unit_min: 'min',
	ui_unit_h: 'h',
	ui_unit_d: 'd',

	// the shortcuts dialog
	ui_hotkeys_title: 'Keyboard shortcuts',
	ui_hk_global: 'Global',
	ui_hk_docks: 'Docks',
	ui_hk_lists: 'Lists and tables',
	ui_hk_omnibar: 'Search objects and commands',
	ui_hk_search: 'Focus search',
	ui_hk_help: 'Show shortcuts',
	ui_hk_escape: 'Close, then clear',
	ui_hk_left_dock: 'Show or hide the left dock',
	ui_hk_right_dock: 'Show or hide the right dock',
	ui_hk_timeline: 'Show or hide the timeline',
	ui_hk_next: 'Next item',
	ui_hk_prev: 'Previous item',
	ui_hk_open: 'Open the item',
	ui_hk_rule: 'No single key approves, unmasks, penalises, dispatches or publishes.',

	// the sources figure of an OSINT report (workspace inspector): reports
	// only — a district context member rides beside as a note, never inside
	// the count
	ui_fig_report: (n: unknown) => `${n} report`,
	ui_fig_reports: (n: unknown) => `${n} reports`,
	ui_fig_context_note: 'District warning in effect'
} satisfies UiPack;

export type UiKey = keyof typeof en;



registerPack('en', en);

/** For tests and the /design gallery: the key list and the three packs. */
export const UI_PACK_KEYS: readonly UiKey[] = Object.keys(en) as UiKey[];
export const UI_PACKS: Record<string, UiPack> = { en };

/**
 * Register one language chunk (lib/i18n/load.ts's landing site; additive,
 * first registration wins — the core's documented semantics).
 */
export function adopt(code: 'hi' | 'mr', pack: UiPack): void {
	UI_PACKS[code] = pack;
	registerPack(code, pack);
}

/*
 * Language chunks (FIX-E-PERF2): this module's HI and MR strings live ONLY in
 * ./packs.ui.hi.ts and ./packs.ui.mr.ts. The server render and every non-production
 * run (vite dev, the node test harness) register both before this module
 * finishes evaluating (SSR paints the persisted language). The production
 * browser registers the loader instead and awaits the document's language
 * before this module finishes evaluating — hydration waits for it, so a cold
 * HI/MR load never flashes English — and the other language loads on the
 * first switch (lib/i18n/load.ts). The prod client build folds the condition
 * to its else branch.
 */
if (process.env.NODE_ENV !== 'production' || import.meta.env.SSR !== false) {
	adopt('hi', (await import('./packs.ui.hi')).hi);
	adopt('mr', (await import('./packs.ui.mr')).mr);
} else {
	await langChunks('packs.ui', (code) =>
		code === 'hi' ? import('./packs.ui.hi').then((c) => adopt('hi', c.hi)) : import('./packs.ui.mr').then((c) => adopt('mr', c.mr)),
	);
}
