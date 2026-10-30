/**
 * Decision outcomes this console just recorded (SPEC §5.3 ProposalCard:
 * "after the decision the card collapses to an outcome row (officer, time),
 * the next step becomes active, a toast confirms, and the audit row lands").
 *
 * A decided unit leaves the queue on the next poll, so the outcome row lives
 * here for OUTCOME_TTL_MS: the /ops Decisions column and the Inbox show it
 * where the unit was. The officer and the title are kept as printed (the
 * title masked); nothing is persisted.
 */

export interface DecisionOutcome {
	kind: string;
	id: string;
	/** The unit's title at decision time, masked. */
	title: string;
	/** What was done ("Pursuit authorised", "E-challan rejected"). */
	verb: string;
	officer: string;
	at: number;
	ok: boolean;
	/** The server's sentence when it refused (verbatim). */
	detail: string | null;
}

export const OUTCOME_TTL_MS = 90_000;

class OutcomeLog {
	items = $state<DecisionOutcome[]>([]);

	push(o: DecisionOutcome): void {
		this.items = [o, ...this.items.filter((x) => !(x.kind === o.kind && x.id === o.id && x.verb === o.verb))].slice(0, 12);
	}

	/** The outcomes still shown at `now` (newest first). */
	recent(now = Date.now()): DecisionOutcome[] {
		return this.items.filter((o) => now - o.at < OUTCOME_TTL_MS);
	}

	/** The newest outcome of one unit, while it is shown. */
	of(kind: string, id: string, now = Date.now()): DecisionOutcome | null {
		return this.recent(now).find((o) => o.kind === kind && o.id === id) ?? null;
	}

	clear(): void {
		this.items = [];
	}
}

export const decisionOutcomes = new OutcomeLog();
