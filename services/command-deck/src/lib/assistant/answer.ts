/**
 * The assistant's answer, split for an officer (FIX-G-BRAIN deck items).
 *
 * The brain's deterministic and grounded answers append the raw lookup
 * results to the prose — " What the lookups returned: city_query_entities
 * …; predict_eta refused: route_length_m …". Tool names and arguments are
 * diagnostics, never the answer: the answer is the prose BEFORE that marker,
 * the lookup detail goes to the collapsible steps.
 *
 * The grounding check's removals reach the deck as `done.grounding.removed`
 * (a list of removed claims) or, from today's brain, as the operator alert
 * "ungrounded_claims_removed: N claim(s) no tool reported were removed from
 * the answer". Either is ONE plain line ("N statements removed: not in the
 * lookups"); the alert is then not repeated in the raw alert list.
 */
const LOOKUPS_MARK = /\s*What the lookups returned:\s*/;

export interface SplitAnswer {
	/** The answer an officer reads. */
	answer: string;
	/** The lookup detail (for the steps), or null when the prose carries none. */
	lookups: string | null;
}

export function splitLookups(prose: string): SplitAnswer {
	const m = LOOKUPS_MARK.exec(prose);
	if (!m) return { answer: prose, lookups: null };
	const answer = prose.slice(0, m.index).trim();
	const lookups = prose.slice(m.index + m[0].length).trim().replace(/\.$/, '').trim();
	// a prose that IS only the lookup dump keeps it as the answer (never an empty bubble)
	if (!answer) return { answer: prose.trim(), lookups: null };
	return { answer, lookups: lookups || null };
}

const REMOVED_ALERT = /^ungrounded_claims_removed:\s*(\d+)\s+claim/i;

/** How many statements the grounding check removed (null: none said), and the alerts left to list. */
export function groundingOf(done: { operatorAlerts: readonly string[]; groundingRemoved?: number | null }): {
	removed: number | null;
	alerts: string[];
} {
	let removed = done.groundingRemoved ?? null;
	const alerts: string[] = [];
	for (const a of done.operatorAlerts) {
		const m = REMOVED_ALERT.exec(a);
		if (m) removed = Math.max(removed ?? 0, Number(m[1]));
		else alerts.push(a);
	}
	return { removed: removed != null && removed > 0 ? removed : null, alerts };
}
