<script lang="ts" module>
	import type { Component as LoadedComponent } from 'svelte';
	/** Components already loaded, by loader: a stable loader remounts with no spinner frame. */
	const loaded = new WeakMap<object, LoadedComponent<any>>();
</script>

<script lang="ts">
	/**
	 * LazyMount — a registered panel's lazy loader (plan R9's budget escape
	 * hatch; corridor/lazy's LazyTab is a thin skin over it): the registry
	 * mounts this wrapper; the real component loads on the wrapper's first
	 * mount — the inspector's sections and activity renderers, which carry
	 * props, forward them through. Nothing heavy rides the route's eager
	 * graph: the route JS budget (SPEC §13.12) counts what a route node
	 * pulls statically — and tests/route-coldload.mjs counts what a cold load
	 * fetches, so a wrapper only defers what is really off the first paint.
	 *
	 * Glyphs (FIX-E-PERF2): when the deferred icon half is already in flight
	 * (the operator's press that opened this panel prefetches it) the panel
	 * waits for it beside its own module — in parallel, never in series — so
	 * it never renders a blank glyph; `glyphs` names icons the panel shows
	 * that may be deferred, and loads them with the module when needed.
	 *
	 * `spinner={false}`: an overlay that has nothing to show until it lands (a
	 * closed palette, a map proposal card) renders nothing while loading.
	 * `failure`: the failure line in the caller's own words. A caller that
	 * remounts the wrapper (a {#key}, a toggling {#if}) passes a STABLE `load`
	 * function: once loaded, it renders in the same frame, as a static import
	 * did.
	 */
	import { untrack, type Component, type Snippet } from 'svelte';
	import { Spinner } from '$lib/ui';
	import { iconReady, loadRestIcons, restIconsInFlight } from '$lib/design/icons';

	let {
		load,
		spinner = true,
		glyphs = [],
		failure,
		...rest
	}: {
		load: () => Promise<{ default: Component<any> }>;
		spinner?: boolean;
		glyphs?: readonly string[];
		failure?: Snippet;
	} & Record<string, unknown> = $props();

	let C = $state<Component<any> | null>(untrack(() => loaded.get(load) ?? null)); // a loader seen before: no spinner frame
	let failed = $state(false);

	$effect(() => {
		if (C && loaded.get(load) === C) return;
		const icons = glyphs.some((g) => !iconReady(g)) ? loadRestIcons() : restIconsInFlight();
		Promise.all([load(), icons?.catch(() => {})])
			.then(([m]) => {
				loaded.set(load, m.default);
				C = m.default;
			})
			.catch(() => (failed = true));
	});
</script>

{#if C}
	<C {...rest} />
{:else if failed}
	{#if failure}{@render failure()}{:else}<div class="lazy-failed" role="alert">Failed to load this panel.</div>{/if}
{:else if spinner}
	<div class="lazy-loading"><Spinner /></div>
{/if}

<style>
	.lazy-loading,
	.lazy-failed {
		display: flex;
		align-items: center;
		justify-content: center;
		padding: 24px;
		color: var(--v-ink-2);
		font-size: var(--v-text-xs);
	}
</style>
