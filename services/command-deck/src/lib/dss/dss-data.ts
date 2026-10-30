/**
 * The decision-support view-model (plan X22, contracts C-U/C-T) — PURE
 * helpers over the parsed C-U object and the entity props. No store, no
 * runes: everything here takes its language explicitly so the unit tests can
 * pin the exact sentences. State (the fetched objects, the officer's COA
 * selection, refusals) lives in `dss-store.svelte.ts`; the wire parser lives
 * in ops/client.ts.
 *
 * The ethics line this module exists for: the engine proposes, a named
 * officer decides (osint SPEC §1.7). A vetoed or resource-infeasible COA is
 * listed with its reason and can never be selected for approval; the
 * resource-blocked best response is stated with what is missing, never
 * hidden; "do nothing" is never presented for an injury situation without
 * its stated reason.
 */
import { t } from '$lib/i18n/strings';
import '$lib/i18n/packs.dss';
import type { DecisionSupport, DssAction, DssCoa } from '$lib/ops/client';
import type { DecisionUnitSummary } from '$lib/workspace/types';
import { homeOf } from '$lib/decisions/homes';

/** The pack sentence for `key` in `lang` (the dss pack registers before use). */
const t$ = t;

// ── the entity props.dss summary (C-T DssSummary, snake wire) ───────────

export interface DssSummary {
	dssId: string;
	state: string;
	topCoaId: string | null;
	topCoaLabel: string | null;
	generatedAt: string | null;
	horizonMin: number | null;
	expiresAt: string | null;
}

const str = (v: unknown): string | null => (typeof v === 'string' && v.length ? v : null);
const num = (v: unknown): number | null => (typeof v === 'number' && Number.isFinite(v) ? v : null);
const rec = (v: unknown): Record<string, unknown> => (v && typeof v === 'object' && !Array.isArray(v) ? (v as Record<string, unknown>) : {});

/** props.dss → the summary, or null (tolerant: unknown fields ignored). */
export function parseDssSummary(v: unknown): DssSummary | null {
	const r = rec(v);
	const dssId = str(r.dss_id);
	if (!dssId) return null;
	return {
		dssId,
		state: str(r.state) ?? 'proposed',
		topCoaId: str(r.top_coa_id),
		topCoaLabel: str(r.top_coa_label),
		generatedAt: str(r.generated_at),
		horizonMin: num(r.horizon_min),
		expiresAt: str(r.expires_at),
	};
}

/** Epoch ms of the summary's expiry (0 when unparseable — never a deadline). */
export function expiresMs(s: DssSummary | null | undefined): number {
	const t = s?.expiresAt ? Date.parse(s.expiresAt) : NaN;
	return Number.isFinite(t) ? t : 0;
}

/** True while the oracle still owes the officer a decision (C-T lazy expiry). */
export function isWaiting(s: DssSummary | null | undefined, now: number): boolean {
	return !!s && s.state === 'proposed' && expiresMs(s) > now;
}

// ── the subject's severity (plan X22) ───────────────────────────────────

export interface SecondOrderFlag {
	kind: string | null;
	urn: string | null;
	segmentId: number | null;
	note: string | null;
}

export function parseSecondOrder(v: unknown): SecondOrderFlag[] {
	if (!Array.isArray(v)) return [];
	const out: SecondOrderFlag[] = [];
	for (const raw of v) {
		const r = rec(raw);
		out.push({ kind: str(r.kind), urn: str(r.urn), segmentId: num(r.segment_id), note: str(r.note) });
	}
	return out;
}

const PRIORITY_RE = /\b(108|ambulance|protected|escort|pursuit|golden)\b/i;

/**
 * A second-order flag naming a protected corridor or a 108 route (plan X22
 * severity 3): the flag's own words say so, or its urn names a live
 * protected movement or pursuit.
 */
export function hasPriorityFlag(flags: SecondOrderFlag[], events?: readonly { eventId: string; eventKind: string }[]): boolean {
	for (const f of flags) {
		if (PRIORITY_RE.test(`${f.kind ?? ''} ${f.note ?? ''}`)) return true;
		const id = f.urn?.startsWith('event:') ? f.urn.slice(6) : null;
		if (id && events?.some((e) => e.eventId === id && (e.eventKind === 'protected_movement' || e.eventKind === 'vehicle_pursuit'))) return true;
	}
	return false;
}

const INJURY_CLASSES = new Set(['road_accident', 'reported_crime', 'public_disorder']);
const INJURY_RE = /\b(injur|casualt|kill|hurt|hospital|critical)/i;

/** An injury situation (severity 2 with an official or news label). */
export function injurySituation(eventClass: string | null, summary: string | null | undefined): boolean {
	return !!eventClass && INJURY_CLASSES.has(eventClass) && INJURY_RE.test(summary ?? '');
}

/** The unit's severity: 3 priority flag · 2 official/news injury · 1 rest. */
export function severityFor(flags: SecondOrderFlag[], verification: string | null, eventClass: string | null, summary: string | null | undefined, events?: readonly { eventId: string; eventKind: string }[]): 0 | 1 | 2 | 3 {
	if (hasPriorityFlag(flags, events)) return 3;
	if ((verification === 'OFFICIAL-VERIFIED' || verification === 'NEWS-REPORTED') && injurySituation(eventClass, summary)) return 2;
	return 1;
}

// ── the card view-model over a parsed C-U object ────────────────────────

/** The COA with `coaId`, or null. */
export function coaById(dss: DecisionSupport | null | undefined, coaId: string | null | undefined): DssCoa | null {
	if (!dss || !coaId) return null;
	return dss.coaSet.find((c) => c.coaId === coaId) ?? null;
}

/** The COA list in the engine's ranking order (vetoed and infeasible last, never dropped). */
export function rankedRows(dss: DecisionSupport | null | undefined): DssCoa[] {
	if (!dss) return [];
	const byId = new Map(dss.coaSet.map((c) => [c.coaId, c]));
	const ranked = dss.recommendation.rankedCoaIds.map((id) => byId.get(id)).filter((c): c is DssCoa => !!c);
	if (ranked.length === dss.coaSet.length) return ranked;
	return [...dss.coaSet].sort((a, b) => (a.rank ?? 99) - (b.rank ?? 99) || (b.closeness ?? 0) - (a.closeness ?? 0));
}

/** A COA the officer may approve: not vetoed, resourced. */
export function coaSelectable(c: DssCoa | null | undefined): boolean {
	return !!c && !c.vetoed && c.feasible;
}

/** Why a COA cannot be approved — its own reason, verbatim where the engine gave one. */
export function coaBlockReason(lang: string, c: DssCoa | null | undefined): string {
	if (!c) return '';
	if (c.vetoed) {
		const reason = (c.vetoReason ?? '').toLowerCase();
		if (reason.includes('person')) return t$(lang, 'dss_veto_persons');
		return t$(lang, 'dss_vetoed', c.vetoReason ?? '');
	}
	const shortfalls = c.shortfalls.filter(Boolean).join('; ');
	return shortfalls ? t$(lang, 'dss_infeasible', shortfalls) : t$(lang, 'dss_infeasible_unstated');
}

/**
 * "Feasible", or "Resource-infeasible: police need 2, 1 free" (plan X22).
 * A COA that cannot be approved states its reason ONCE — the row head
 * carries `coaBlockReason`, so this line stays empty for it (FIX-E-DSSCARD:
 * the reason printed twice).
 */
export function feasibilityLine(lang: string, c: DssCoa | null | undefined): string {
	if (!c) return '';
	if (!coaSelectable(c)) return '';
	return t$(lang, 'dss_feasible');
}

/** The agencies that are a 108 ambulance in a COA's dispatch action. */
const AMBULANCE_AGENCIES: ReadonlySet<string> = new Set(['ambulance', '108']);

/**
 * The 108 delay a COA's row may state (HON-9): only a COA that SENDS a 108
 * has a 108 of its own to delay or speed up — a closure with no ambulance in
 * it shows no "ambulance ±N s", whatever an older engine computed for it.
 * Null when there is nothing to state (no 108 sent, no delay, or 0 s).
 */
export function ambulanceDelayOf(c: DssCoa | null | undefined): number | null {
	if (!c || !c.ambulanceDelaySec) return null;
	const sends108 = c.dispatches.some((a) => AMBULANCE_AGENCIES.has(String(a.params.agency ?? '').toLowerCase()));
	return sends108 ? Math.round(c.ambulanceDelaySec) : null;
}

/** The pre-selected radio: the engine's top COA when it can be approved, else the best that can. */
export function defaultCoaId(dss: DecisionSupport | null | undefined): string | null {
	for (const c of rankedRows(dss)) if (coaSelectable(c)) return c.coaId;
	return null;
}

export const dispatchesOf = (c: DssCoa | null | undefined): DssAction[] => c?.actions.filter((a) => a.verb === 'dispatch') ?? [];
/** The verbs whose approval writes something: dispatch, closure, diversion, signal_hold (C-U approve step 1). */
const ACTUATING = new Set(['dispatch', 'closure', 'diversion', 'signal_hold']);
export const actuatingOf = (c: DssCoa | null | undefined): boolean => !!c && c.actions.some((a) => ACTUATING.has(a.verb));

/** Where each non-writing verb is carried out afterwards (C-U next_steps). */
export function nextStepLine(lang: string, c: DssCoa | null | undefined): string {
	if (!c) return '';
	const homes = new Set<string>();
	for (const a of c.actions) {
		const key =
			a.verb === 'advisory'
				? 'dss_next_advisory'
				: a.verb === 'signal_hold'
					? 'dss_next_signal'
					: a.verb === 'closure' || a.verb === 'diversion'
						? 'dss_next_corridor'
						: a.verb === 'escort_switch'
							? 'dss_next_movement'
							: a.verb === 'request_cctv'
								? 'dss_next_iccc'
								: null;
		if (key) homes.add(t$(lang, key));
	}
	return [...homes].join(' · ');
}

/** Why Approve cannot act right now — null when it can. The view-model the card and the writer share. */
export function approveBlocked(lang: string, officer: string | null | undefined, selected: DssCoa | null | undefined): string | null {
	if (!officer || officer.trim().length < 2) return t$(lang, 'dss_reason_officer');
	if (!selected) return t$(lang, 'dss_reason_no_coa');
	if (!coaSelectable(selected)) return coaBlockReason(lang, selected);
	return null;
}

/**
 * Why Defer cannot act right now — null when it can (FIX-E-DSSCARD: Defer
 * was gated on Approve's own rules and sent an empty note, so it was dead).
 * Only the named officer and the footer's reason gate it; a chosen or
 * feasible COA is not a deferral's business (the writer refuses again on
 * either, before any request). Its own officer sentence names DEFER — the
 * approve sentence says "approve", which was the wrong gate copy here
 * (fix round 2).
 */
export function deferBlocked(lang: string, officer: string | null | undefined, note: string | null | undefined): string | null {
	if (!officer || officer.trim().length < 2) return t$(lang, 'dss_reason_officer_defer');
	if (!note || !note.trim()) return t$(lang, 'dss_defer_hint');
	return null;
}

/** "Sajag AI's pick: <kind> · confidence <c>" — only when the decider gave one. */
export function strategyPriorLine(lang: string, dss: DecisionSupport | null | undefined): string {
	const p = dss?.recommendation.strategyPrior ?? null;
	if (!p) return '';
	const kind = (p.kind ?? '').replace(/_/g, ' ');
	const confidence = p.confidence ?? p.probability;
	return confidence != null ? t$(lang, 'dss_ai_pick_c', kind, Math.round(confidence * 100) / 100) : t$(lang, 'dss_ai_pick', kind);
}

/**
 * The resource-blocked best response, stated prominently (carry-over,
 * FIX-C-DSS): read defensively — the field is absent until the oracle adds
 * it, and there the line is empty. Falls back to the engine's own dissent
 * mention only when the parsed top COA cannot be approved but a higher-
 * closeness infeasible one exists.
 */
export function bestBlockedLine(lang: string, dss: DecisionSupport | null | undefined): string {
	const b = dss?.recommendation.bestBlocked ?? null;
	if (!b) return '';
	const coa = coaById(dss, b.coaId);
	const missing = (b.missing?.length ? b.missing : (coa?.shortfalls ?? [])).join('; ');
	return t$(lang, 'dss_best_blocked', coa?.label ?? b.coaId, missing, unblockSentence(lang, b.unblockAction));
}

/**
 * The unblock clause, in the console's language (FIX-E-DSSCARD: the raw
 * engine enum `request_units` printed verbatim). The one frozen value gets
 * its sentence naming Dispatch; anything else (absent, or a value this deck
 * predates) gets the honest default.
 */
export function unblockSentence(lang: string, unblockAction: string | null | undefined): string {
	return unblockAction === 'request_units' ? t$(lang, 'dss_unblock_request_units') : t$(lang, 'dss_unblock_default');
}

// ── the public-safety floor (FIX-E-DSSCARD; osint_common Recommendation.public_safety_floor) ──

/** The floor's mode: what the officer sees. Null while the wire has none (read defensively). */
export type SafetyFloor = 'hold' | 'verify' | 'none';

/**
 * The parsed object's public-safety floor. The deck's C-U parser carries the
 * field natively (`DssRecommendation.publicSafetyFloor`, fix round 2 — the
 * raw-wire merge is gone); anything absent or unknown reads null and renders
 * no line.
 */
export function publicSafetyFloorOf(dss: DecisionSupport | null | undefined): SafetyFloor | null {
	const f = dss?.recommendation.publicSafetyFloor;
	return f === 'hold' || f === 'verify' || f === 'none' ? f : null;
}

/**
 * The floor line under the card's blocked-best banner: why the do-nothing
 * baseline sits below a response that scores LOWER than it (the floor holds
 * it below every FEASIBLE response — the engine's non-compensatory rule,
 * fix round 2 copy), and — at "verify" — why the officer verifies first.
 * "none" and an absent field render nothing.
 */
export function floorLine(lang: string, dss: DecisionSupport | null | undefined): string {
	const f = publicSafetyFloorOf(dss);
	if (f === 'hold') return t$(lang, 'dss_floor_hold');
	if (f === 'verify') return t$(lang, 'dss_floor_verify');
	return '';
}

/**
 * The decision-unit summary the inspector's dss section feeds
 * `workspace.openDecisionHome` — DecisionLinks' shape (FIX-E-DSSCARD: the
 * section's home link was a raw `/#inbox=…` href that opened nothing on /
 * and navigated away from /gods-eye; the summary routes the click through
 * the workspace's one-home rule instead).
 */
export function dssHomeSummary(s: DssSummary | null | undefined, subjectUrn: string): DecisionUnitSummary | null {
	if (!s) return null;
	return {
		kind: 'dss',
		id: s.dssId,
		subjectUrn,
		title: s.topCoaLabel ?? s.dssId,
		deadline: expiresMs(s) || null,
		severity: 1,
		homes: { '/': homeOf('dss', '/'), '/gods-eye': homeOf('dss', '/gods-eye'), '/ops': homeOf('dss', '/ops') },
	};
}

// ── (the sentences come from the dss pack through `t$` above) ───────────
