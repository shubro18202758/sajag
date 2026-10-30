<script lang="ts">
	/**
	 * (v3) — the V3 operator surfaces (V3-SPEC §10 P0/P1): /home and /v3-gallery for now. Command theme,
	 * the V3 tokens (loaded here only, so no existing route downloads them) and the V3 shell.
	 *
	 * The operator gate's session is read once per mount, as the (deck) layout does: with the gate on the
	 * signed-in officer becomes the duty officer on every page that starts the ops store.
	 */
	import { onMount, untrack } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import '$lib/v3/tokens.css';
	import V3Shell from '$lib/v3/shell/V3Shell.svelte';
	import { operatorSession } from '$lib/shell/session.svelte';
	import { selection } from '$lib/gods-eye/entities/selection.svelte';
	import { objectHref } from '$lib/v3/object/model';

	let { children } = $props();

	onMount(() => {
		void operatorSession.refresh();
	});

	$effect(() => {
		document.documentElement.dataset.theme = 'command';
	});

	// Enter on an object in the Omnibar opens its page (`/o/<urn>`, V3-SPEC §5.1) on the V3 screens that have no
	// selection surface of their own; the Map keeps selecting in place (its selection card), and the v2 screens
	// (another layout) keep selecting in place too. Only a pick made after this layout mounted counts: the
	// selection store outlives navigations, and an old pick must not navigate when a V3 screen opens.
	const mountedAt = Date.now();
	$effect(() => {
		const at = selection.selectedAt;
		const urn = selection.current;
		if (!urn || selection.source !== 'omnibar' || at < mountedAt) return;
		untrack(() => {
			if ($page.route.id === '/(v3)/map') return;
			const href = objectHref(urn);
			if (href && decodeURIComponent($page.url.pathname) !== decodeURIComponent(href)) void goto(href);
		});
	});
</script>

<V3Shell>
	{@render children?.()}
</V3Shell>
