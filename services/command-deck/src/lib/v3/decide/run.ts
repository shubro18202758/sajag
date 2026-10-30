/**
 * The one way Decide decides (V3-SPEC §5.3, §6.2): a unit's verb runs its EXISTING writer in
 * decisions/writers.ts — the writer is the write path (its officer gate, its busy and double-click guard,
 * its refusal codes, the ops store's own gate and re-poll). This module adds no request of its own; it
 * only records what came back so the sheet can say it:
 *
 *   - success → the outcome sentence (dec_done_*), the officer, the time, the writer's next step; the v2
 *     decision outcome log hears it too (the /ops column and the Inbox show the same receipt);
 *   - refusal → the deck's sentence for the code AND the server's own words, verbatim, in the sheet —
 *     never a toast, never retried by itself;
 *   - nothing is sent without a named officer: the writer refuses 'officer-required' before any request,
 *     and the store refuses again.
 *
 * A second call while the first is in flight gets the SAME promise (one POST per double click), and the
 * writer refuses a late repeat within SETTLE_MS of a success ('already-decided').
 */
import { ops } from '$lib/ops/store.svelte';
import { t } from '$lib/i18n/strings';
import '$lib/i18n/packs.decisions';
import '$lib/i18n/packs.dss';
import { maskPlatesInText } from '$lib/ops/format';
import { refusalText, type WriterResult } from '$lib/decisions/writers';
import { decisionOutcomes } from '$lib/decisions/cards/outcomes.svelte';
import type { Unit } from '$lib/decisions/units';
import { doneKey, keyOf, tallyOf, writerOf } from './model';
import { decideSession, type DecideOutcome } from './session.svelte';

/**
 * The sentence for a refusal: the writer's own for its code; for a bare 'failed' (the writer has no
 * sentence for it) either "the service answered — here are its words" or, with no words at all, the honest
 * "no confirmation came back" — never "refused" for a request that may not have arrived.
 */
export function refusalWords(table: Record<string, string>, res: WriterResult, L: (key: string, ...a: unknown[]) => string): string {
	if (res.refusal === 'failed' && !(res.refusal in table)) return L(res.detail ? 'v3d_refuse_said' : 'v3d_refuse_failed');
	return refusalText({ refusals: table } as Parameters<typeof refusalText>[0], res.refusal);
}

const inflight = new Map<string, Promise<DecideOutcome | null>>();

/** True while a verb of this unit is being sent from Decide. */
export function deciding(u: Unit): boolean {
	const k = keyOf(u);
	for (const key of inflight.keys()) if (key.startsWith(`${k}|`)) return true;
	return false;
}

/**
 * Run `action` on `u` as the console's named officer. `args` carries the reason (`note`) and, for a
 * decision-support unit, the chosen course of action (`coaId`) — the writer posts exactly that one.
 * Returns the recorded outcome, or null when the verb has no writer.
 */
export function runDecision(u: Unit, action: string, args: { note?: string; coaId?: string | null } = {}, lang = ops.lang): Promise<DecideOutcome | null> {
	const w = writerOf(u, action);
	if (!w) return Promise.resolve(null);
	const flightKey = `${keyOf(u)}|${action}`;
	const running = inflight.get(flightKey);
	if (running) return running;
	const p = (async (): Promise<DecideOutcome | null> => {
		const officer = ops.dutyOfficer.trim();
		const runArgs: Record<string, unknown> = { note: args.note ?? '' };
		if (args.coaId) runArgs.coaId = args.coaId;
		let res: WriterResult;
		try {
			res = (await w.run(u, officer, runArgs)) as WriterResult;
		} catch (err) {
			res = { ok: false, refusal: 'failed', detail: err instanceof Error ? err.message : String(err), posts: 0 };
		}
		const L = (key: string, ...a: unknown[]) => t(lang, key, ...a);
		const verb = L(doneKey(u, action));
		let next: string | null = null;
		if (res.ok) {
			try {
				next = w.nextStep?.(u, args.coaId ? { coaId: args.coaId } : undefined) || null;
			} catch {
				next = null;
			}
		}
		const outcome: DecideOutcome = {
			key: keyOf(u),
			unit: u,
			action,
			ok: res.ok,
			verb,
			officer,
			at: Date.now(),
			next,
			refusal: res.ok ? null : refusalWords(w.refusals, res, L),
			detail: res.ok ? null : (res.detail ?? null),
			posts: res.posts ?? 0,
		};
		decideSession.record(outcome, res.ok ? tallyOf(action) : null);
		if (res.ok) {
			decisionOutcomes.push({ kind: u.kind, id: u.id, title: maskPlatesInText(u.title), verb, officer, at: outcome.at, ok: true, detail: null });
		}
		return outcome;
	})().finally(() => inflight.delete(flightKey));
	inflight.set(flightKey, p);
	return p;
}
