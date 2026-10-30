/**
 * Toast store — OUTCOME toasts only (SPEC §7.3): a toast confirms what the
 * operator did, for 5 s. Interrupts (a proposal, a watchlist read, a band
 * change, a feed loss) never toast: they reach the LiveStrip and the inbox.
 * System chatter belongs in the audit stream, never here.
 *
 *   import { toasts } from '$lib/shell/toast.svelte';
 *   toasts.push({ kind: 'act', title: 'Decision approved', body: 'PI-2207 · e-challan' });
 *
 * The shell's Toaster hands these to src/lib/ui/Toaster (top centre under
 * the navbar, at most 3, newest first); the primitive runs each toast's
 * timer and pauses it while hovered.
 */

export type ToastKind = 'info' | 'act' | 'error';

export interface ToastSpec {
	kind: ToastKind;
	title: string;
	body?: string;
	/** Auto-dismiss after this many ms (default 5000); 0 = until dismissed. */
	ttl?: number;
}

export interface ToastItem extends ToastSpec {
	id: number;
}

/** Outcome toasts stay 5 s (SPEC §7.3). */
export const TOAST_TTL_MS = 5000;

class ToastStore {
	/** $state class field — Svelte does not deep-proxy class instances,
	 * so reactivity must live on the field itself. */
	items: ToastItem[] = $state([]);
	private seq = 0;
	/** At most 3 visible. */
	static readonly MAX = 3;

	push(spec: ToastSpec): number {
		const id = ++this.seq;
		const ttl = spec.ttl ?? TOAST_TTL_MS;
		this.items = [{ ...spec, ttl, id }, ...this.items].slice(0, ToastStore.MAX);
		return id;
	}

	dismiss(id: number): void {
		this.items = this.items.filter((t) => t.id !== id);
	}

	clear(): void {
		this.items = [];
	}
}

export const toasts = new ToastStore();
