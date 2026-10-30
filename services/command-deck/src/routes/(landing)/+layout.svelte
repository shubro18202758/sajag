<script lang="ts">
	/**
	 * (landing) — the public front door (/welcome, V3-LANDING). Night theme: the console's ground, rendered by the
	 * server too (hooks.server.ts gives every route outside (public) data-theme="command"), and the STRICT public
	 * content-security policy (only the (deck) and (v3) operator groups get the relaxed one). It loads the V3 tokens and
	 * nothing else: no shell, no store, no operator code. The page itself scrolls as a document.
	 */
	import '$lib/v3/tokens.css';

	let { children } = $props();

	$effect(() => {
		document.documentElement.dataset.theme = 'command';
	});
</script>

{@render children?.()}
