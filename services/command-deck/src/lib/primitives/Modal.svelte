<script lang="ts">
	/**
	 * Modal — the legacy dialog, rebuilt as src/lib/ui's Dialog (SPEC §5.2):
	 * a 40 px header with the title and a close button, the body, the
	 * backdrop; Escape and an outside click close it, focus is trapped and
	 * returns to the opener. NEVER for fail-closed signal refusals — those
	 * render inline ("held at baseline"); this is for evidence detail and
	 * confirmations. `data-prim="modal"` stays on the dialog panel.
	 */
	import Dialog from '$lib/ui/Dialog.svelte';

	interface Props {
		open: boolean;
		title: string;
		width?: string;
		onClose: () => void;
		children?: import('svelte').Snippet;
	}

	let { open, title, width = '560px', onClose, children }: Props = $props();
</script>

<Dialog {open} {title} {width} onclose={onClose} data-prim="modal">
	{@render children?.()}
</Dialog>
