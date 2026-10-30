<script lang="ts">
	/**
	 * (deck) — the operator surfaces that are v2 pages (/analyst, /ops, /gods-eye, /chat, /comms and the /design
	 * galleries), drawn inside the V3 shell (V3-P6B): the same rail and top bar, in the same pixels, as every V3
	 * screen (V3-SPEC §3.1, the colleague review: uniform navigation). Command theme (command-graphite) and the V3
	 * tokens; the pages supply the command-bar state they own and keep their own layouts, stores and test ids.
	 *
	 * What only these pages need — the Analyst views, the band tag, the Inbox, the Data button, Policies, More and
	 * the live strip — is the OpsBand under the top bar. The page then sits in the same flex column the v2 shell's
	 * `main` was, so no page's geometry changes (only the chrome above it).
	 *
	 * The operator gate's session is read HERE, once per mount of any operator route: with the gate on
	 * (SAJAG_OPERATOR_PIN) the officer the deck verified becomes the duty officer everywhere — the ops store (started
	 * by every one of those pages) follows the shell's session state and adopts it: plates unmask for them, writer
	 * controls unlock, and the manual officer fields lock to that name, which is the name the server audits
	 * (x-sajag-officer). Signing out releases it. This layout itself stays on the design-shell side of the R4
	 * boundary (it never imports the ops store).
	 */
	import { onMount } from 'svelte';
	import '$lib/v3/tokens.css';
	import V3Shell from '$lib/v3/shell/V3Shell.svelte';
	import OpsBand from '$lib/v3/shell/OpsBand.svelte';
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
	<div class="deck-frame" data-shell="command">
		<OpsBand />
		<div class="deck-main">
			{@render children?.()}
		</div>
	</div>
</V3Shell>

<style>
	.deck-frame {
		display: flex;
		flex-direction: column;
		height: 100%;
		min-width: 0;
		min-height: 0;
	}

	/* what the v2 shell's `main` was: the page's flex column, scrolling when it must */
	.deck-main {
		display: flex;
		flex: 1 1 auto;
		flex-direction: column;
		min-width: 0;
		min-height: 0;
		overflow: auto;
	}
</style>
