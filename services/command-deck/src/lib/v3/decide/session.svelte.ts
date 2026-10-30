/**
 * Decide's session state (V3-SPEC §6.2) — what this console decided while /decide was open, so the sheet
 * can collapse to its outcome after the unit leaves the queue (the next poll drops a decided unit) and the
 * queue's "Decided on this console" tally can count it. Nothing is persisted and nothing is sent: the audit
 * trail of record is the oracle's / the brain's (the Analyst view reads it).
 *
 *   outcomes   unit key → the outcome of a decision taken HERE (ok, or a refusal shown verbatim), with the
 *              unit as it was when decided (the sheet's header after the unit is gone)
 *   expired    unit key → a time-boxed proposal this console watched run out unanswered (plan kept)
 *   tally      approved · rejected · deferred · expired (plan kept), for this console session
 */
import type { Unit } from '$lib/decisions/units';

export interface DecideOutcome {
	key: string;
	/** The unit as it was when decided (masked marks still go through ops.plate when shown). */
	unit: Unit;
	action: string;
	ok: boolean;
	/** The outcome words (dec_done_*), in the console's language at decision time. */
	verb: string;
	officer: string;
	at: number;
	/** The writer's next separate step, when it has one. */
	next: string | null;
	/** A refusal: the deck's sentence and the server's own words, verbatim. */
	refusal: string | null;
	detail: string | null;
	posts: number;
}

class DecideSession {
	outcomes = $state<Record<string, DecideOutcome>>({});
	expired = $state<Record<string, { unit: Unit; at: number }>>({});
	tally = $state({ approved: 0, rejected: 0, deferred: 0, expired: 0 });

	record(o: DecideOutcome, tally: 'approved' | 'rejected' | 'deferred' | null): void {
		this.outcomes = { ...this.outcomes, [o.key]: o };
		if (o.ok && tally) this.tally = { ...this.tally, [tally]: this.tally[tally] + 1 };
	}

	/** A time-boxed unit ran out unanswered while this console watched it (counted once). */
	markExpired(key: string, unit: Unit, at: number): void {
		if (this.expired[key] || this.outcomes[key]?.ok) return;
		this.expired = { ...this.expired, [key]: { unit, at } };
		this.tally = { ...this.tally, expired: this.tally.expired + 1 };
	}

	/** Forget a refusal so the officer can try again (a success is never forgotten). */
	clearRefusal(key: string): void {
		const o = this.outcomes[key];
		if (!o || o.ok) return;
		const next = { ...this.outcomes };
		delete next[key];
		this.outcomes = next;
	}

	reset(): void {
		this.outcomes = {};
		this.expired = {};
		this.tally = { approved: 0, rejected: 0, deferred: 0, expired: 0 };
	}
}

export const decideSession = new DecideSession();
