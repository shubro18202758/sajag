<script lang="ts">
	/**
	 * CommsFrame — the V3 shell around /comms (V3-SPEC §3.1, §6.7; V3-P6A).
	 *
	 * /comms lives in the (deck) route group, whose layout wraps every page in the chrome the Analyst surfaces still
	 * use (V3-P6B recomposes that layout). The route's `+layout@.svelte` resets out of it and renders THIS frame, so
	 * Advisories carries the V3 rail and slim top bar whichever chrome the (deck) layout has at the time — never two
	 * shells. It does what the (v3) group layout does for its pages: the V3 tokens (loaded here only, so no other route
	 * downloads them), the command theme and the operator gate's session (read once per mount, so the signed-in officer
	 * becomes the duty officer on this page exactly as on every other operator page).
	 *
	 * When /comms moves into the (v3) group the frame is deleted with the `@` layout and the page renders directly
	 * (INTEGRATION.patch says how).
	 */
	import { onMount } from 'svelte';
	import '$lib/v3/tokens.css';
	import V3Shell from '$lib/v3/shell/V3Shell.svelte';
	import { operatorSession } from '$lib/shell/session.svelte';

	let { children } = $props();

	onMount(() => {
		void operatorSession.refresh();
	});

	$effect(() => {
		document.documentElement.dataset.theme = 'command';
	});
</script>

<V3Shell>
	{@render children?.()}
</V3Shell>
