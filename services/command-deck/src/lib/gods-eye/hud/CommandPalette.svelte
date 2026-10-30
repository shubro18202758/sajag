<script lang="ts">
	/**
	 * CommandPalette — kept as the canvas's omnibar mount (plan R30/X25):
	 * GodsEyeCanvas mounts it for hud 'full' and 'wall' on /, /ops and
	 * /gods-eye, with today's props, and it renders the workspace Omnibar —
	 * the ONLY omnibar on those pages (`command-palette`, `palette-input`,
	 * one ⌘K handler). The canvas's map commands (fly to, show <agency>
	 * units near <road>, layer <id> on|off, sensor <mode>) keep working
	 * through these callbacks.
	 *
	 * First use (FIX-E-PERF2): the omnibar is a closed overlay at first paint,
	 * so its module (the search, the vehicle lookup, the command templates)
	 * loads the first time it is asked for — ⌘K / Ctrl+K, `/`, or the navbar
	 * search opening it (workspace.openOmnibar) — never on a cold load. Until
	 * then THIS mount holds the page's one hotkey slot with the omnibar's own
	 * key rules; it hands the slot to the omnibar as it loads, and the omnibar
	 * mounts already open, with the query typed so far. The operator's first
	 * pointer or key press prefetches the module (a Ctrl+K usually finds it
	 * already in).
	 */
	import { onMount } from 'svelte';
	import LazyMount from '$lib/workspace/components/lazy/LazyMount.svelte';
	import { claimHotkey, releaseHotkey, typingIn } from '$lib/workspace/components/omnibar/hotkey';
	import { workspace } from '$lib/workspace/workspace.svelte';
	import type { DirectiveWorld, SENSOR_MODES } from '../directives';

	let {
		layerIds,
		world,
		onfly,
		onhighlight,
		onlayer,
		onsensor,
	}: {
		layerIds: readonly string[];
		/** What the canvas can resolve right now (for streamed directives). */
		world: () => DirectiveWorld;
		/** A point flight (a road's extent, a group of units). */
		onfly: (lon: number, lat: number, rangeM: number) => void;
		onhighlight: (urns: string[]) => void;
		onlayer: (id: string, on: boolean) => void;
		onsensor: (mode: (typeof SENSOR_MODES)[number]) => void;
	} = $props();

	const loadOmnibar = () => import('$lib/workspace/components/omnibar/Omnibar.svelte');
	const slot = Symbol('omnibar-first-use');
	/** This mount is the page's omnibar (the first one mounted, as before). */
	let holding = $state(false);
	/** The omnibar was asked for: load it and mount it (it stays mounted). */
	let wanted = $state(false);
	let handBack: (() => void) | null = null;

	onMount(() => {
		if (!claimHotkey(slot)) return; // a second palette on the page renders nothing, as a second Omnibar did
		holding = true;
		const onKey = (e: KeyboardEvent) => {
			if ((e.metaKey || e.ctrlKey) && !e.altKey && (e.key === 'k' || e.key === 'K')) {
				e.preventDefault();
				if (workspace.omnibar.open) workspace.closeOmnibar();
				else workspace.openOmnibar();
				return;
			}
			if (e.key === '/' && !e.metaKey && !e.ctrlKey && !e.altKey && !e.defaultPrevented && !typingIn(e) && !workspace.omnibar.open) {
				e.preventDefault();
				workspace.openOmnibar();
			}
		};
		window.addEventListener('keydown', onKey);
		// the first press of any kind prefetches the module (it is cached for the mount below)
		const prefetch = () => {
			for (const type of ['pointerdown', 'keydown']) window.removeEventListener(type, prefetch, true);
			void loadOmnibar().catch(() => {});
		};
		for (const type of ['pointerdown', 'keydown']) window.addEventListener(type, prefetch, { capture: true, passive: true });
		handBack = () => {
			window.removeEventListener('keydown', onKey);
			for (const type of ['pointerdown', 'keydown']) window.removeEventListener(type, prefetch, true);
			releaseHotkey(slot);
		};
		return () => {
			handBack?.();
			handBack = null;
			holding = false;
		};
	});

	$effect(() => {
		if (holding && workspace.omnibar.open) wanted = true;
	});

	// the omnibar claims the slot itself as it mounts: hand it over first
	$effect(() => {
		if (!wanted || !handBack) return;
		handBack();
		handBack = null;
	});
</script>

{#if holding && wanted}
	<LazyMount
		load={loadOmnibar}
		spinner={false}
		{layerIds}
		{world}
		{onfly}
		{onhighlight}
		{onlayer}
		{onsensor}
	/>
{/if}
