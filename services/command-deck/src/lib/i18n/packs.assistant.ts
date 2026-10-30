/**
 * The assistant string pack (EN / HI / MR): the AssistantPanel — its scope
 * line, steps and Details, the link cards that stand in for Apply, the
 * context column and the /chat page chrome (UI-S6B). Registered additively
 * through registerPack(); the core packs stay untouched. Every key starts
 * with `asst_`.
 *
 * EN is sentence case, with no ALL-CAPS word outside the acronym allowlist,
 * at most one " · " per string, and titles of at most 32 characters
 * (tests/copy-lint.mjs, target file style-lint.targets/s6b.json). HI and MR
 * are complete for every key. Copy describes only what the system does
 * (SPEC §9.3): the assistant reads and proposes — it never decides, and
 * every decision mention opens the decision's one home.
 */
import { registerPack } from './strings';
import { langChunks } from './load';

type Fn = (...args: unknown[]) => string;
type Pack = Record<string, string | Fn>;

const s = (v: unknown) => String(v ?? '');

const en: Pack = {
	// ── chrome ─────────────────────────────────────────────────────────────
	asst_tab: 'Assistant',
	asst_page_title: 'Assistant',
	asst_page_sub: 'It reads the city and proposes. Proposals open where a person reviews them — nothing is applied here.',
	asst_actor: 'Sajag assistant · read only',
	asst_context_title: 'Context',
	asst_context_none: 'Nothing selected',
	asst_context_hint: 'Select an object to scope the assistant to it',
	asst_decisions: 'Decisions waiting',
	asst_citations: 'Cited objects',
	asst_clear: 'Clear conversation',

	// ── scope line ─────────────────────────────────────────────────────────
	// The scope line reads "Scoped to <subject> and this view" (SPEC §5.3):
	// the words wrap around the subject's object tag, so the sentence is a
	// prefix and a suffix — HI and MR put the subject first.
	asst_scope_prefix: 'Scoped to',
	asst_scope: (what: unknown) => `Scoped to ${s(what)} and this view`,
	asst_scope_suffix: 'and this view',
	asst_scope_view: 'Scoped to this view',

	// ── steps and Details ──────────────────────────────────────────────────
	asst_steps: 'Steps',
	asst_details: 'Details',
	asst_details_tools: 'Tool calls',
	asst_lookups_label: 'What the lookups returned',
	asst_grounding_removed: (n: unknown) => (Number(n) === 1 ? '1 statement removed: not in the lookups' : `${s(n)} statements removed: not in the lookups`),
	asst_details_model: 'Model',
	asst_details_tier: 'Tier',
	asst_details_session: 'Session',
	asst_steps_toggle: 'Show steps',
	asst_thoughts_toggle: 'Show reasoning',

	// ── link cards (no Apply, no Approve — SPEC §5.3) ─────────────────────
	asst_proposed_map: (what: unknown) => `Proposed on the map: ${s(what)}`,
	asst_review_map: 'Review it on the map',
	asst_decision_card: 'Decision waiting',

	// ── citation tooltips (per surface): the dock's citation selects on the
	// CURRENT map — "Open in City command" would lie there (audit E, S3) ───
	asst_cite_select_map: 'Select on the map',

	// ── corridor event states (the scope line's one state word) ───────────
	asst_ev_state_planned: 'Planned',
	asst_ev_state_active: 'Active',
	asst_ev_state_completed: 'Completed',
	asst_ev_state_cancelled: 'Cancelled',
	asst_interrupted: 'Stopped — the panel was closed before the answer finished.',

	// ── empty state and the labelled sample ────────────────────────────────
	asst_empty_title: 'Ask the assistant',
	asst_sample_note: 'Labelled sample turn, composed for review. No model was called.',

	// ── /citizen's emulated-holds banner (SPEC §6.6): the count of the very
	// hold rows listed below, from the same derivation as the cards ────────
	asst_citizen_hold_one: '1 emulated hold listed below.',
	asst_citizen_hold_many: (n: unknown) => `${n} emulated holds listed below.`,

	// ── /driver's request button: enabled-looking, the reason inline (§6.6) ─
	asst_driver_choose_stretch: 'Choose your location first — then request the corridor.',
};



registerPack('en', en);

/**
 * Register one language chunk (lib/i18n/load.ts's landing site; additive,
 * first registration wins — the core's documented semantics).
 */
export function adopt(code: 'hi' | 'mr', pack: Pack): void {
	registerPack(code, pack);
}

/*
 * Language chunks (FIX-E-PERF2): this module's HI and MR strings live ONLY in
 * ./packs.assistant.hi.ts and ./packs.assistant.mr.ts. The server render and every non-production
 * run (vite dev, the node test harness) register both before this module
 * finishes evaluating (SSR paints the persisted language). The production
 * browser registers the loader instead and awaits the document's language
 * before this module finishes evaluating — hydration waits for it, so a cold
 * HI/MR load never flashes English — and the other language loads on the
 * first switch (lib/i18n/load.ts). The prod client build folds the condition
 * to its else branch.
 */
if (process.env.NODE_ENV !== 'production' || import.meta.env.SSR !== false) {
	adopt('hi', (await import('./packs.assistant.hi')).hi);
	adopt('mr', (await import('./packs.assistant.mr')).mr);
} else {
	await langChunks('packs.assistant', (code) =>
		code === 'hi' ? import('./packs.assistant.hi').then((c) => adopt('hi', c.hi)) : import('./packs.assistant.mr').then((c) => adopt('mr', c.mr)),
	);
}
