<script lang="ts">
	/**
	 * The selected event, at the head of the desk (V3-SPEC §6.7): the real map of its place (MapThumb — natural satellite
	 * where the deck is keyed, the night-graded map otherwise), its art, kind line and title, the tags that say where it
	 * came from, and the line of facts the drafts were written from. The withholding badge arrives as a snippet: the PAGE
	 * decides whether and what to state (one badge, fail-closed).
	 */
	import type { Snippet } from 'svelte';
	import MapThumb from '../map/MapThumb.svelte';
	import { mediaForTile } from '../media/art';
	import type { LonLat } from '../map/mercator';
	import type { ThumbOverlay } from '../map/overlay';

	let {
		overlay,
		mapAlt,
		noPlace,
		art,
		kind,
		title,
		roads = null,
		openHref,
		openLabel,
		tags,
		factsLine,
		actions,
	}: {
		overlay: ThumbOverlay | null;
		mapAlt: string;
		noPlace: string;
		art: string;
		kind: string;
		title: string;
		roads?: readonly (readonly LonLat[])[] | null;
		openHref: string | null;
		openLabel: string;
		tags: Snippet;
		factsLine: Snippet;
		actions?: Snippet;
	} = $props();

	// V3-P7: the header leads with the kind's key art (an illustration), the real map of the place inset in its corner
	const keyArtSrc = $derived.by(() => {
		const m = mediaForTile(art);
		return m?.kind === 'art' ? m.src : null;
	});
	const hasPlace = $derived(!!overlay && ((overlay.points?.length ?? 0) > 0 || (overlay.lines?.length ?? 0) > 0));
</script>

<header class="head" data-testid="comms-event-head">
	<div class={['map', keyArtSrc && 'has-art']} data-has-place={hasPlace ? 'yes' : 'no'}>
		{#if keyArtSrc}
			<img class="keyart" src={keyArtSrc} alt="" width="640" height="360" loading="eager" decoding="async" data-testid="comms-event-art" />
			{#if hasPlace && overlay}
				<span class="map-inset"><MapThumb class="thumb" {overlay} zoom={14} alt={mapAlt} markerR={9} {roads} /></span>
			{:else}
				<div class="noplace over"><span>{noPlace}</span></div>
			{/if}
		{:else if hasPlace && overlay}
			<MapThumb class="thumb" {overlay} zoom={15} alt={mapAlt} {roads} />
		{:else}
			<div class="noplace"><img src={art} alt="" width="72" height="72" /><span>{noPlace}</span></div>
		{/if}
	</div>
	<div class="info">
		<div class="line">
			<img class="art" src={art} alt="" width="44" height="44" />
			<div class="who">
				<span class="kind">{kind}</span>
				<h2 class="title">{title}</h2>
			</div>
		</div>
		<div class="tags">{@render tags()}</div>
		<div class="facts">{@render factsLine()}</div>
		<div class="foot">
			{#if openHref}<a class="open" href={openHref}>{openLabel} →</a>{/if}
			{#if actions}<div class="actions">{@render actions()}</div>{/if}
		</div>
	</div>
</header>

<style>
	.head {
		display: grid;
		grid-template-columns: minmax(220px, 300px) minmax(0, 1fr);
		min-height: 168px;
		overflow: hidden;
		border: 1px solid var(--v3-line-1);
		border-radius: var(--v3-radius-xl);
		background: var(--v3-s1);
	}

	.map {
		position: relative;
		min-height: 168px;
		background: var(--v3-map-bg);
	}

	.map :global(.thumb) {
		position: absolute;
		inset: 0;
	}

	.keyart {
		position: absolute;
		inset: 0;
		width: 100%;
		height: 100%;
		object-fit: cover;
	}

	.map-inset {
		position: absolute;
		right: 10px;
		bottom: 10px;
		width: 46%;
		aspect-ratio: 16 / 10;
		overflow: hidden;
		border: 1px solid var(--v3-line-3);
		border-radius: var(--v3-radius-m);
		box-shadow: var(--v3-elev-1);
	}

	.map-inset :global(.thumb) {
		position: absolute;
		inset: 0;
	}

	.noplace.over {
		inset: auto 0 0 0;
		padding: 18px 12px 8px;
		background: linear-gradient(to top, var(--v3-photo-scrim), var(--v3-photo-scrim-none));
		color: var(--v3-photo-ink);
	}

	.noplace {
		position: absolute;
		inset: 0;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 8px;
		padding: 16px;
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
		text-align: center;
	}

	.noplace img {
		opacity: 0.85;
	}

	.info {
		display: flex;
		flex-direction: column;
		gap: 10px;
		min-width: 0;
		padding: 18px 22px;
	}

	.line {
		display: flex;
		align-items: center;
		gap: 14px;
		min-width: 0;
	}

	.art {
		flex: none;
		width: 44px;
		height: 44px;
		border-radius: var(--v3-radius-m);
		background: var(--v3-s3);
	}

	.who {
		min-width: 0;
	}

	.kind {
		display: block;
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
		line-height: var(--v3-lh-meta);
	}

	.title {
		margin: 0;
		overflow: hidden;
		font-size: var(--v3-text-title);
		font-weight: 650;
		line-height: var(--v3-lh-title);
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.tags {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 8px;
	}

	.facts {
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
		line-height: var(--v3-lh-meta);
	}

	.foot {
		display: flex;
		align-items: flex-end;
		justify-content: space-between;
		flex-wrap: wrap;
		gap: 10px;
		margin-top: auto;
	}

	.actions {
		display: flex;
		flex-wrap: wrap;
		gap: 8px;
		margin-left: auto;
	}

	.open {
		color: var(--v3-brand-text);
		font-size: var(--v3-text-meta);
		font-weight: 620;
		text-decoration: none;
	}

	.open:hover {
		text-decoration: underline;
	}

	.open:focus-visible {
		outline: 2px solid var(--v3-brand);
		outline-offset: 3px;
		border-radius: 4px;
	}

	@media (max-width: 1500px) {
		.head {
			grid-template-columns: minmax(180px, 240px) minmax(0, 1fr);
			min-height: 148px;
		}

		.map {
			min-height: 148px;
		}

		.info {
			padding: 14px 18px;
			gap: 8px;
		}
	}
</style>
