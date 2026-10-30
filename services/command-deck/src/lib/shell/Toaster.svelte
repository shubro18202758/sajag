<script lang="ts">
	/**
	 * Toaster — the shell's toast region (`data-shell="toaster"`): the toast
	 * store wired into the src/lib/ui Toaster primitive (top centre under the
	 * navbar, at most 3, 5 s each, paused while hovered). Outcomes only.
	 *
	 * A kind maps onto the colour roles (SPEC §2.4): an act the operator took
	 * reads as done (success, tick); info and an error outcome stay neutral,
	 * the error with its glyph (red is the alert role, never "failed").
	 */
	import { INTENT_ICON } from '$lib/design/icons';
	import UiToaster from '$lib/ui/Toaster.svelte';
	import type { ToastSpec as UiToast } from '$lib/ui/types';
	import { toasts, type ToastItem } from './toast.svelte';

	let { position = 'top' }: { position?: 'top' | 'bottom' } = $props();

	function toUi(item: ToastItem): UiToast {
		// title and body read as one sentence ("Decision approved: PI-2207 · e-challan"); a colon, never
		// another " · ", so a body that already carries its one data separator never becomes a chain (SPEC §3.5)
		const message = item.body ? `${item.title}: ${item.body}` : item.title;
		if (item.kind === 'act') return { id: item.id, message, intent: 'success', timeout: item.ttl };
		if (item.kind === 'error') return { id: item.id, message, intent: 'none', icon: INTENT_ICON.danger, timeout: item.ttl };
		return { id: item.id, message, intent: 'none', icon: INTENT_ICON.none, timeout: item.ttl };
	}

	const shown = $derived(toasts.items.map(toUi));
</script>

<UiToaster toasts={shown} max={3} {position} ondismiss={(id) => toasts.dismiss(Number(id))} data-shell="toaster" />
