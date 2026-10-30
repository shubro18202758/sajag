/**
 * The one way an AI proposal is decided: a NAMED officer approves or rejects it, and the decision is recorded in
 * the platform's decision log — `POST /api/v1/ai-proposals/decision` on the traffic-oracle (human-gated: the
 * deck-verified officer header or the body officer, 409 officer-required before anything is looked up; 409
 * already-decided for a second decision; it NEVER actuates anything). Patch:
 * .orchestration/patches/int-ops-oracle-ai-proposals.patch.
 *
 * Until that route is deployed (404), or while its table is not migrated (503), the decision is kept on THIS
 * console only and says so in its outcome — never presented as recorded in the platform. An exercise card (the
 * 19 Aug 2025 hindsight replay) is always console-only: an exercise never enters the decision log.
 *
 * Nothing here changes a road, a signal, a dispatch or a public message. The outcome names the separate next step.
 */
import { AI_PATHS } from './client';
import type { AiCard } from './model';
import type { AiDecisionRow } from './types';

export interface AiDecisionInput {
	decision: 'approve' | 'reject';
	officer: string;
	note?: string;
}

export type AiDecisionResult =
	| { ok: true; row: AiDecisionRow }
	| { ok: false; refusal: 'officer-required' | 'reason-required' | 'already-decided' | 'sign-in' | 'failed'; detail: string | null; row?: AiDecisionRow };

/** What the oracle accepts (unknown keys are refused there): the proposal mapped, never forwarded raw. */
export function decisionBody(card: AiCard, input: AiDecisionInput): Record<string, unknown> {
	const evidence: Record<string, unknown> = {};
	if (card.fc) evidence.forecast = card.fc;
	if (card.hy) evidence.hydro = { ...card.hy, textEn: card.hy.textEn ?? undefined, textMr: card.hy.textMr ?? undefined };
	if (card.tw) evidence.twin = { junction: card.tw.junction, change: card.tw.change, duration_min: card.tw.durationMin, delay_change_pct: card.tw.delayPct, cross_street_delay_change_pct: card.tw.crossPct, network_delay_change_pct: card.tw.networkPct, max_queue_change_m: card.tw.queueM, do_nothing: card.tw.before, with_change: card.tw.after, confidence: card.tw.confidence };
	if (card.viaNames.length) evidence.via_names = card.viaNames;
	const body: Record<string, unknown> = {
		proposal: {
			proposal_id: card.id.slice(0, 160),
			source: card.source,
			kind: card.kind.toLowerCase().replace(/[^a-z0-9_]/g, '_').slice(0, 60),
			subject_urn: card.subjectUrn.slice(0, 160),
			summary: (card.summary || card.id).slice(0, 1500),
			labels: card.labels.slice(0, 8).map((l) => l.slice(0, 40)),
			state: 'proposed',
			evidence: JSON.parse(JSON.stringify(evidence)),
		},
		decision: input.decision,
		officer: input.officer,
	};
	const note = input.note?.trim();
	if (note) body.note = note.slice(0, 500);
	return body;
}

function consoleRow(card: AiCard, input: AiDecisionInput, at = Date.now()): AiDecisionRow {
	return {
		log_id: null,
		proposal_id: card.id,
		source: card.source,
		kind: card.kind,
		subject_urn: card.subjectUrn,
		decision: input.decision,
		officer: input.officer,
		note: input.note?.trim() || null,
		decided_at: new Date(at).toISOString(),
		recorded: 'console',
	};
}

const inflight = new Map<string, Promise<AiDecisionResult>>();

/** Decide one card as the named officer (one request per double click; the same promise while in flight). */
export function decideAiCard(card: AiCard, input: AiDecisionInput, fetchImpl: typeof fetch = fetch): Promise<AiDecisionResult> {
	const officer = input.officer.trim();
	if (officer.length < 2) return Promise.resolve({ ok: false, refusal: 'officer-required', detail: null });
	if (input.decision === 'reject' && !input.note?.trim()) return Promise.resolve({ ok: false, refusal: 'reason-required', detail: null });
	if (card.exercise) return Promise.resolve({ ok: true, row: consoleRow(card, { ...input, officer }) });
	const key = `${card.id}|${input.decision}`;
	const running = inflight.get(key);
	if (running) return running;
	const p = (async (): Promise<AiDecisionResult> => {
		let res: Response;
		try {
			res = await fetchImpl(`${AI_PATHS.decisions}/decision`, {
				method: 'POST',
				headers: { 'content-type': 'application/json' },
				body: JSON.stringify(decisionBody(card, { ...input, officer })),
				signal: AbortSignal.timeout(20_000),
			});
		} catch (err) {
			return { ok: false, refusal: 'failed', detail: err instanceof Error ? err.message : String(err) };
		}
		const text = await res.text().catch(() => '');
		let doc: Record<string, unknown> = {};
		try {
			doc = text ? (JSON.parse(text) as Record<string, unknown>) : {};
		} catch {
			doc = {};
		}
		if (res.ok) {
			return {
				ok: true,
				row: {
					log_id: typeof doc.log_id === 'number' ? doc.log_id : null,
					proposal_id: String(doc.proposal_id ?? card.id),
					source: String(doc.source ?? card.source),
					kind: String(doc.kind ?? card.kind),
					subject_urn: String(doc.subject_urn ?? card.subjectUrn),
					decision: doc.decision === 'reject' ? 'reject' : input.decision,
					officer: String(doc.officer ?? officer),
					note: typeof doc.note === 'string' ? doc.note : (input.note?.trim() ?? null),
					decided_at: String(doc.decided_at ?? new Date().toISOString()),
					recorded: 'platform',
				},
			};
		}
		// the decision log is not deployed (404) or not migrated (503): kept on this console, and it says so
		if (res.status === 404 || res.status === 503) return { ok: true, row: consoleRow(card, { ...input, officer }) };
		if (res.status === 401 || res.status === 403) return { ok: false, refusal: 'sign-in', detail: String(doc.detail ?? '') || null };
		if (res.status === 409 && doc.detail === 'already-decided') {
			return {
				ok: false,
				refusal: 'already-decided',
				detail: typeof doc.reason === 'string' ? doc.reason : null,
				row: { ...consoleRow(card, { decision: doc.decision === 'reject' ? 'reject' : 'approve', officer: String(doc.officer ?? '') }), decided_at: String(doc.decided_at ?? ''), recorded: 'platform' },
			};
		}
		if (res.status === 409 && doc.detail === 'officer-required') return { ok: false, refusal: 'officer-required', detail: typeof doc.reason === 'string' ? doc.reason : null };
		const said = typeof doc.reason === 'string' ? doc.reason : typeof doc.detail === 'string' ? doc.detail : text.slice(0, 200);
		return { ok: false, refusal: 'failed', detail: `${res.status}${said ? `: ${said}` : ''}` };
	})().finally(() => inflight.delete(key));
	inflight.set(key, p);
	return p;
}

/** The platform's decision record, newest first (null when the route is not deployed). */
export async function fetchDecisions(fetchImpl: typeof fetch = fetch): Promise<AiDecisionRow[] | null> {
	const res = await fetchImpl(`${AI_PATHS.decisions}/decisions?limit=200`, { signal: AbortSignal.timeout(10_000) });
	if (res.status === 404 || res.status === 503) return null;
	if (!res.ok) throw new Error(`${res.status}`);
	const doc = (await res.json()) as { decisions?: unknown };
	const rows = Array.isArray(doc.decisions) ? (doc.decisions as Record<string, unknown>[]) : [];
	return rows
		.filter((r) => typeof r.proposal_id === 'string')
		.map((r) => ({
			log_id: typeof r.log_id === 'number' ? r.log_id : null,
			proposal_id: String(r.proposal_id),
			source: String(r.source ?? ''),
			kind: String(r.kind ?? ''),
			subject_urn: String(r.subject_urn ?? ''),
			decision: r.decision === 'reject' ? 'reject' : 'approve',
			officer: String(r.officer ?? ''),
			note: typeof r.note === 'string' ? r.note : null,
			decided_at: String(r.decided_at ?? ''),
			recorded: 'platform',
		}));
}
