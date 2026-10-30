/**
 * The inspector's back and forward (Alt+← and Alt+→): the objects it showed,
 * in order. A selection made by going back or forward is not recorded again.
 */
const MAX = 50;

class InspectorHistory {
	stack = $state.raw<readonly string[]>([]);
	at = $state(-1);
	#moving = false;

	/** Record that the inspector now shows `urn` (a new branch drops the forward part). */
	visit(urn: string | null) {
		if (!urn || this.#moving) {
			this.#moving = false;
			return;
		}
		if (this.stack[this.at] === urn) return;
		const next = [...this.stack.slice(0, this.at + 1), urn].slice(-MAX);
		this.stack = next;
		this.at = next.length - 1;
	}

	get canBack(): boolean {
		return this.at > 0;
	}

	get canForward(): boolean {
		return this.at >= 0 && this.at < this.stack.length - 1;
	}

	/** The URN to show after going back (or null); the next visit() of it is not recorded. */
	back(): string | null {
		if (!this.canBack) return null;
		this.at -= 1;
		this.#moving = true;
		return this.stack[this.at];
	}

	forward(): string | null {
		if (!this.canForward) return null;
		this.at += 1;
		this.#moving = true;
		return this.stack[this.at];
	}
}

export const inspectorHistory = new InspectorHistory();
