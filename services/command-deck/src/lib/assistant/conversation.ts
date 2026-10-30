/**
 * The assistant's conversation outlives its panel. A citation on the `/` dock selects the object, which switches
 * the dock to the Inspector and unmounts the panel; a page change does the same. The officer comes back to the same
 * turns and the same brain session (audit E-ASSIST R2). One kept conversation per panel variant; "Clear
 * conversation" forgets it.
 */

export interface KeptConversation<M = unknown> {
	messages: M[];
	sessionId: string | null;
	seq: number;
	/** The scope the brain session belongs to (its event). */
	scope: string;
}

const kept = new Map<string, KeptConversation>();

export function keptConversation<M>(variant: string): KeptConversation<M> | null {
	return (kept.get(variant) as KeptConversation<M> | undefined) ?? null;
}

export function keepConversation<M>(variant: string, c: KeptConversation<M>): void {
	kept.set(variant, c as KeptConversation);
}

export function forgetConversation(variant: string): void {
	kept.delete(variant);
}
