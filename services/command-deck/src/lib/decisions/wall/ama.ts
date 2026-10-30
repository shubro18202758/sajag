/**
 * The AMA card's shadow-evaluation row in words (F-12), pure.
 *
 * The oracle publishes a BASELINE parameter set with shadow_eval
 * 'unavailable' and the detail 'shadow_eval_not_required': nothing was
 * evaluated because a baseline needs no twin run. That reads "Not
 * required", never "Unavailable" (which says the evaluation could not run).
 * The time beside it is the PUBLISH time of the set the word comes from —
 * dated when it is not today, and only when the word comes from that set
 * (a word read off the band evidence carries no publish time).
 */
export const SHADOW_NOT_REQUIRED = 'shadow_eval_not_required';

export interface ShadowInput {
	/** The newest published set's evaluation (null when none published). */
	newest: { shadowEval: string | null; shadowEvalDetail?: string | null; ts?: string | number | null } | null;
	/** The band evidence's evaluation (the fallback source). */
	evidence: { shadowEval: string | null; failClosedReason?: string | null } | null;
}

export interface ShadowRow {
	/** The state key: passed | failed_closed | unavailable | not_required | <raw>. */
	state: string;
	/** The reason to show beside it (raw, the display layer words it), or null. */
	why: string | null;
	/** Epoch ms or ISO of the publish the word belongs to, or null. */
	publishedAt: string | number | null;
}

export function shadowRow(input: ShadowInput): ShadowRow | null {
	const fromNewest = input.newest?.shadowEval ?? null;
	const raw = fromNewest ?? input.evidence?.shadowEval ?? null;
	if (!raw) return null;
	const detail = fromNewest ? (input.newest?.shadowEvalDetail ?? null) : (input.evidence?.failClosedReason ?? null);
	const notRequired = detail === SHADOW_NOT_REQUIRED || raw === 'not_required' || raw === SHADOW_NOT_REQUIRED;
	return {
		state: notRequired ? 'not_required' : raw,
		why: detail && detail !== SHADOW_NOT_REQUIRED ? detail : null,
		publishedAt: fromNewest ? (input.newest?.ts ?? null) : null,
	};
}
