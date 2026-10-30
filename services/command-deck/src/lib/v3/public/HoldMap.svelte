<script lang="ts">
	/**
	 * The map thumbnail of a held stretch (V3-SPEC §6.8): the real map of the place — natural satellite where the deck holds
	 * the imagery key (MapThumb's shared rule), the day-graded map otherwise — with the stretch drawn on it, solid for a live
	 * event and DASHED for a fixture, emulated or unverified one (never a live road hold). The geometry is the public
	 * segments read; without it the card simply has no map (nothing is drawn that is not known).
	 *
	 * Decorative to the card's text: the map is one role="img" with its alt; the road names are in the card.
	 */
	import { onMount } from 'svelte';
	import MapThumb from '../map/MapThumb.svelte';
	import { holdOverlay, loadSegments } from './geometry';

	let { ids, live, alt }: { ids: readonly number[]; live: boolean; alt: string } = $props();

	let segs = $state.raw<Awaited<ReturnType<typeof loadSegments>> | null>(null);

	onMount(() => {
		let gone = false;
		void loadSegments()
			.then((m) => {
				if (!gone) segs = m;
			})
			.catch(() => undefined);
		return () => {
			gone = true;
		};
	});

	const overlay = $derived(segs ? holdOverlay(ids, segs, live) : null);
</script>

{#if overlay}
	<div class="hm" data-testid="hold-map" data-live={live ? 'yes' : 'no'}>
		<MapThumb class="hm-thumb" {overlay} zoom={16} grade="day" {alt} credit creditLabel="© OpenStreetMap contributors" />
	</div>
{/if}

<style>
	.hm {
		position: relative;
		height: 148px;
		background: var(--v3-map-bg);
	}

	.hm :global(.hm-thumb) {
		position: absolute;
		inset: 0;
	}
</style>
