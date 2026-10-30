<script lang="ts">
	/**
	 * (public) — citizen/driver surfaces. Daylight theme (the V3 day tokens) + the
	 * V3 PublicShell chrome (V3-SPEC §6.8). The server already renders these routes with
	 * data-theme="daylight" (hooks.server.ts transformPageChunk — no dark
	 * flash on a phone); this effect covers client-side navigation in from
	 * the deck, and on unmount the theme resets to command so the operator
	 * deck never inherits paper tokens.
	 */
	import PublicShell from '$lib/v3/public/PublicShell.svelte';

	let { children } = $props();

	$effect(() => {
		document.documentElement.dataset.theme = 'daylight';
		return () => {
			document.documentElement.dataset.theme = 'command';
		};
	});
</script>

<PublicShell>
	{@render children?.()}
</PublicShell>
