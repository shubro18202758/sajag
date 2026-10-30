/**
 * The V3 Assistant's pure rules (V3-SPEC §5.7, §7.6; V3-P4) — no store, no DOM; tests/v3-assistant.unit.mjs drives them.
 * The conversation itself is the shared ChatSession ($lib/assistant/session.svelte.ts); this module only decides
 * what an officer reads:
 *
 *   CAUTIONS   the brain's diagnostics (done.operator_alerts codes, done.degraded, the tiers used) → at most one human
 *              sentence each (§7.6): a disagreement, low confidence, a novel situation, the backup model, a reduced
 *              mode. An unknown code becomes the generic "needs a check" sentence — never the code. The grounding
 *              check's removal note is the shared answer.ts rule (groundingOf), kept as the brain said it.
 *   STEPS      a tool call in words, in the officer's language (an unknown tool: the deck's own words, else "Looked
 *              something up"); the traffic-twin steps carry "simulated"; the lookup detail has every tool name and
 *              snake_case field turned into words.
 *   SCRUB      the answer text keeps the brain's prose, but a known tool name or alert code inside it is replaced by
 *              its words — no raw code reaches the page.
 *   CHIPS      the answer split around the objects it cites (longest label first), so a cited object reads as a chip
 *              inside the sentence; a mark is masked before it gets here (ops.text).
 *   MODEL      the "Model and trace details" line from the tiers used, in words; never the model id.
 */
import { displayTool } from '$lib/workspace/display';
import { human } from '$lib/workspace/vocabulary';

/** The brain's operator-alert codes and the sentence each becomes (orchestrator.alert_text). */
export const CAUTION_KEY: Readonly<Record<string, string>> = {
	decider_gemma_disagreement: 'v3a_caution_disagree',
	low_confidence_decision: 'v3a_caution_low_conf',
	novel_situation_confident_answer: 'v3a_caution_novel',
	decider_unavailable: 'v3a_caution_backup',
	novelty_check_unavailable: 'v3a_caution_novelty_check',
};

/** Codes answered elsewhere (the grounding note), never a caution. */
const NOT_A_CAUTION = new Set(['ungrounded_claims_removed']);

/** "decider_gemma_disagreement: decider X vs Gemma Y — …" → "decider_gemma_disagreement" (null: not a code line). */
export function alertCode(line: string): string | null {
	const m = /^\s*([a-z][a-z0-9]*(?:_[a-z0-9]+)+)\b/.exec(line);
	return m ? m[1] : null;
}

export interface DoneLike {
	operatorAlerts: readonly string[];
	degraded: boolean;
	tiersUsed: readonly string[];
}

/** The cautions one finished turn shows: pack keys, deduplicated, in a stable order. */
export function cautionsOf(done: DoneLike | null | undefined): string[] {
	if (!done) return [];
	const out: string[] = [];
	const add = (k: string) => {
		if (!out.includes(k)) out.push(k);
	};
	for (const line of done.operatorAlerts) {
		const code = alertCode(line);
		if (code && NOT_A_CAUTION.has(code)) continue;
		add(code && CAUTION_KEY[code] ? CAUTION_KEY[code] : 'v3a_caution_other');
	}
	const tiers = done.tiersUsed.map((x) => x.split(':')[0]);
	if (tiers.includes('gemma') && !tiers.includes('decider') && !out.includes('v3a_caution_disagree')) add('v3a_caution_backup');
	if (done.degraded) add('v3a_caution_degraded');
	return out;
}

/** The "Model and trace details" line: which kind of model answered, in words (never the model id). */
export function modelKey(tiersUsed: readonly string[] | null | undefined): string {
	if (!tiersUsed?.length) return 'v3a_model_none';
	const tiers = tiersUsed.map((x) => x.split(':')[0]);
	const confirmed = tiersUsed.some((x) => x === 'decider:confirmed_by_gemma');
	if (tiers.includes('decider')) return confirmed || tiers.includes('gemma') ? 'v3a_model_decider_checked' : 'v3a_model_decider';
	if (tiers.includes('gemma')) return 'v3a_model_backup';
	return 'v3a_model_rules';
}

/** Tools whose figures come from the traffic twin (a simulation): their step says "simulated". */
export const SIMULATED_TOOLS: ReadonlySet<string> = new Set(['simulate_twin', 'evaluate_scenarios']);

/** A tool step in the officer's words: the pack's own (`v3a_tool_<name>`), else the deck's words, else a plain "looked something up". */
export function toolLabel(name: string, L: (key: string, ...a: unknown[]) => string): string {
	const key = `v3a_tool_${name}`;
	const own = L(key);
	if (own !== key) return own;
	const deck = displayTool(name);
	return deck && !/_/.test(deck) ? deck : L('v3a_tool_other');
}

const SNAKE = /\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b/g;

/** The lookup detail with every tool name and snake_case field turned into words (no raw identifier left). */
export function humaniseLookups(text: string, L: (key: string, ...a: unknown[]) => string): string {
	return text.replace(SNAKE, (w) => {
		const key = `v3a_tool_${w}`;
		const own = L(key);
		if (own !== key) return own;
		return human(w).toLowerCase();
	});
}

/** The brain's tool names (convoy-brain's registry): the identifiers the page must never print raw. */
export const BRAIN_TOOLS: readonly string[] = [
	'city_decision_support', 'city_feed', 'city_get_dossier', 'city_query_entities', 'evaluate_scenarios', 'find_convoy_routes',
	'get_active_corridor_events', 'get_historical_pattern', 'get_interception_plan', 'get_live_traffic', 'get_signal_state',
	'get_situation_log', 'list_dispatches', 'list_enforcement_recommendations', 'list_units', 'plan_diversions', 'predict_eta',
	'predict_traffic_flow', 'query_k_shortest_paths', 'query_segment_details', 'query_segments_in_bbox', 'query_shortest_path',
	'simulate_twin', 'get_corridor_summary', 'get_city_band', 'list_active_events', 'plan_corridor',
];

/** The answer's prose with known tool names and alert codes in words (the rest of the prose is the brain's, unchanged). */
export function scrubCodes(text: string, L: (key: string, ...a: unknown[]) => string): string {
	const known = new Set([...BRAIN_TOOLS, ...Object.keys(CAUTION_KEY), 'ungrounded_claims_removed']);
	return text.replace(SNAKE, (w) => {
		if (!known.has(w)) return w;
		if (CAUTION_KEY[w] || w === 'ungrounded_claims_removed') return human(w).toLowerCase();
		return toolLabel(w, L).toLowerCase();
	});
}

export interface Chip {
	urn: string;
	label: string;
}

export type Segment = { text: string } | { chip: Chip };

/**
 * The prose split around the cited objects' labels, so each cited object reads as a chip inside its sentence.
 * Longest label first (a mark beats a road it contains); labels shorter than 3 characters are never chips.
 */
export function segmentProse(text: string, chips: readonly Chip[]): Segment[] {
	const usable = [...new Map(chips.filter((c) => c.label && c.label.trim().length >= 3).map((c) => [c.label, c])).values()].sort((a, b) => b.label.length - a.label.length);
	if (!usable.length) return text ? [{ text }] : [];
	const out: Segment[] = [];
	let rest = text;
	while (rest) {
		let best: { at: number; chip: Chip } | null = null;
		for (const c of usable) {
			const at = rest.indexOf(c.label);
			if (at >= 0 && (!best || at < best.at || (at === best.at && c.label.length > best.chip.label.length))) best = { at, chip: c };
		}
		if (!best) {
			out.push({ text: rest });
			break;
		}
		if (best.at > 0) out.push({ text: rest.slice(0, best.at) });
		out.push({ chip: best.chip });
		rest = rest.slice(best.at + best.chip.label.length);
	}
	return out;
}

/** A map directive's words without its verb ("fly to EM-CAM-03" → "EM-CAM-03"). */
export function directiveLabel(label: string): string {
	return label.replace(/^(track|fly to|highlight|note on|sensor|layer)\s+/i, '');
}

/** The city-level suggestions (label: the officer's language; message: what goes on the wire). */
export const SUGGESTIONS: readonly { key: string; label: string; message: string }[] = [
	{ key: 'next-hour', label: 'v3a_s_next_hour', message: 'What needs my decision in the next hour? List the decisions waiting, soonest first.' },
	{ key: 'events', label: 'v3a_s_events', message: 'Which corridor events are active right now?' },
	{ key: 'stolen', label: 'v3a_s_stolen', message: 'Where was the stolen vehicle last read?' },
	{ key: 'traffic', label: 'v3a_s_traffic', message: 'Which roads are slowest right now?' },
	{ key: 'units', label: 'v3a_s_units', message: 'Where are the agency units right now?' },
];

const CHIP_GLYPH: Readonly<Record<string, string>> = {
	vehicle: 'car',
	camera: 'anpr',
	sighting: 'anpr',
	recommendation: 'anpr',
	junction: 'signal',
	segment: 'route',
	road: 'route',
	convoy: 'convoy',
	dispatch: 'ambulance',
	unit: 'shield',
	place: 'pin',
	osint_event: 'news',
	event: 'flag',
	anomaly: 'info',
};

/** An object chip's glyph by its kind (type is the icon; state is the colour). */
export function chipGlyph(kind: string | null | undefined): string {
	return CHIP_GLYPH[kind ?? ''] ?? 'pin';
}
