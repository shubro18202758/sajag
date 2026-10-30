/**
 * The V3 Assistant string pack (V3-SPEC §5.7, §7.6, §7.8) — every string /assistant prints that the assistant pack
 * (packs.assistant: the grounding note, the interrupted turn) and the V3 pack (packs.v3) do not already say. EN
 * here; HI and MR in ./packs.asst3.hi.ts and ./packs.asst3.mr.ts, complete for every key (tests/v3-assistant.unit.mjs
 * checks it). Registered additively; loaded only by /assistant. Every key starts with `v3a_`.
 *
 * Copy rules (§7.6): say what happens, what does not, and how sure. Model diagnostics become ONE human sentence
 * (the caution keys); raw codes, tool names and model ids stay in Analyst → AI trace and never reach this page.
 * The assistant reads and proposes; it never approves, dispatches or unmasks — the copy says so where it matters.
 */
import { registerPack } from '$lib/i18n/strings';
import { langChunks } from '$lib/i18n/load';

type Fn = (...args: unknown[]) => string;
export type AsstPack = Record<string, string | Fn>;

const s = (v: unknown) => String(v ?? '');
const n = (v: unknown) => Number(v);

const en = {
	// ── the screen ──
	v3a_title: 'Assistant',
	v3a_sub: 'Ask in English, हिन्दी or मराठी · it proposes, you decide',
	v3a_conversation: 'Conversation',
	v3a_empty_title: 'Ask about the city',
	v3a_empty_body: 'It reads live operations, decisions, reported events and the traffic feed. It never sees people, and it cannot approve anything.',

	// ── the turns ──
	v3a_you: 'You',
	v3a_bot: 'Sajag assistant',
	v3a_read_only: 'read only',
	v3a_working: 'working',
	v3a_thinking: 'Reading the city',
	v3a_no_prose: 'The answer came back without readable text. The full record is in Analyst, under AI trace.',
	v3a_error: 'The assistant did not answer. Nothing was changed; ask again in a moment.',
	v3a_offline: 'The assistant is not answering right now. The rest of the console keeps working.',
	v3a_steps: (k: unknown) => `How I worked this out · ${s(k)} ${n(k) === 1 ? 'step' : 'steps'}`,
	v3a_step_simulated: 'simulated',
	v3a_step_failed: 'did not answer',
	v3a_lookups: 'What the lookups returned',
	v3a_rule: 'Proposals open where an officer decides. I can’t approve, dispatch or show full registration marks.',

	// ── the cautions (one human sentence per diagnostic, §7.6) ──
	v3a_caution_disagree: 'Two of my models disagreed on the next step; I used the cautious one. Check before acting.',
	v3a_caution_low_conf: 'I’m not confident here; treat this as a starting point.',
	v3a_caution_novel: 'This situation is new to me, so I didn’t rely on my most confident guess. Check before acting.',
	v3a_caution_backup: 'Answered by the backup model.',
	v3a_caution_novelty_check: 'I couldn’t check whether this situation is new. Treat the answer with care.',
	v3a_caution_degraded: 'Answered in a reduced mode; some lookups did not run.',
	v3a_caution_other: 'Something in this answer needs a check. The details are in Analyst, under AI trace.',

	// ── proposal cards (never Apply, never Approve) ──
	v3a_proposal: 'Proposal',
	v3a_waiting: 'Waits for a decision',
	v3a_left: (at: unknown) => `${s(at)} left`,
	v3a_open_decide: 'Open to decide',
	v3a_show_map: 'Show on map',
	v3a_map_proposal: 'Proposed on the map',
	v3a_map_proposal_body: 'A camera move waits on the map for you to apply or dismiss. Nothing moves until you do.',

	// ── the dock ──
	v3a_ask: 'Ask about the city, a road or an event',
	v3a_send: 'Send',
	v3a_stop: 'Stop',
	v3a_scope: 'Reads the whole city · it proposes only and cannot approve, unmask or dispatch',
	v3a_clear: 'Clear conversation',
	v3a_suggest: 'Suggestions',
	v3a_s_next_hour: 'What needs me in the next hour?',
	v3a_s_events: 'Which events are active right now?',
	v3a_s_stolen: 'Where was the stolen vehicle last read?',
	v3a_s_units: 'Where are the units right now?',
	v3a_s_traffic: 'How is traffic on the Western Express Highway right now?',

	// ── the context panel ──
	v3a_ctx_title: 'In this conversation',
	v3a_ctx_sub: 'Tap one to open it. Selecting it here selects it everywhere.',
	v3a_ctx_none: 'Objects the assistant names will appear here.',
	v3a_ctx_waits: 'a decision waits',
	v3a_how: 'How it works',
	v3a_how_reads: 'Reads live operations, decisions, reported events and the traffic feed. Never people.',
	v3a_how_decide: 'Every proposal opens in Decide, where a named officer approves or rejects it.',
	v3a_how_exercise: 'This console runs on exercise data; answers say when a figure is simulated.',
	v3a_trace: 'Model and trace details',
	v3a_model_decider: 'Decision model',
	v3a_model_decider_checked: 'Decision model, checked by a second model',
	v3a_model_backup: 'Backup model',
	v3a_model_rules: 'Rules and lookups, no model',
	v3a_model_none: 'No answer yet',
	v3a_last_answer: (sec: unknown) => `Last answer took ${s(sec)} s`,
	v3a_session_kept: 'The conversation is kept while this tab is open.',
	v3a_trace_where: 'Every step, with its raw names, is in Analyst under AI trace.',
	v3a_open_analyst: 'Open Analyst',

	// ── tool steps in words (the brain's tools; an unknown one falls back to the deck's own words) ──
	v3a_tool_city_get_dossier: 'Read the object’s record',
	v3a_tool_city_feed: 'Read the city feed',
	v3a_tool_city_query_entities: 'Looked up objects in the city',
	v3a_tool_city_decision_support: 'Read the decision support',
	v3a_tool_list_enforcement_recommendations: 'Listed the decisions waiting',
	v3a_tool_get_interception_plan: 'Read the interception plan',
	v3a_tool_get_active_corridor_events: 'Listed the active events',
	v3a_tool_get_live_traffic: 'Read live traffic',
	v3a_tool_predict_traffic_flow: 'Predicted traffic on the roads',
	v3a_tool_predict_eta: 'Estimated the arrival time',
	v3a_tool_get_signal_state: 'Read the signals',
	v3a_tool_get_situation_log: 'Read the situation log',
	v3a_tool_list_units: 'Listed the units',
	v3a_tool_list_dispatches: 'Listed the dispatches',
	v3a_tool_find_convoy_routes: 'Found routes for the movement',
	v3a_tool_plan_diversions: 'Planned diversions',
	v3a_tool_query_shortest_path: 'Found the shortest route',
	v3a_tool_query_k_shortest_paths: 'Compared routes',
	v3a_tool_query_segment_details: 'Read a road’s details',
	v3a_tool_query_segments_in_bbox: 'Listed roads in the area',
	v3a_tool_get_historical_pattern: 'Read the usual pattern',
	v3a_tool_simulate_twin: 'Ran the plan in the traffic twin',
	v3a_tool_evaluate_scenarios: 'Compared plans in the traffic twin',
	v3a_tool_other: 'Looked something up',
};

export type AsstKey = keyof typeof en;

registerPack('en', en);

export const ASST3_PACK_KEYS: readonly AsstKey[] = Object.keys(en) as AsstKey[];
export const ASST3_PACKS: Record<string, AsstPack> = { en };

/** Register one language chunk (lib/i18n/load.ts's landing site; additive, first registration wins). */
export function adopt(code: 'hi' | 'mr', pack: AsstPack): void {
	ASST3_PACKS[code] = pack;
	registerPack(code, pack);
}

/*
 * Language chunks (the deck's FIX-E-PERF2 pattern, as packs.v3): HI and MR live only in their own files.
 */
if (process.env.NODE_ENV !== 'production' || import.meta.env.SSR !== false) {
	adopt('hi', (await import('./packs.asst3.hi')).hi);
	adopt('mr', (await import('./packs.asst3.mr')).mr);
} else {
	await langChunks('packs.asst3', (code) =>
		code === 'hi' ? import('./packs.asst3.hi').then((c) => adopt('hi', c.hi)) : import('./packs.asst3.mr').then((c) => adopt('mr', c.mr)),
	);
}
