<script lang="ts">
	/**
	 * HeroMap (V3-SPEC §4.6, §5.4, §6.3) — the real map at the place, 380 px tall (300 below 1500 px): MapThumb
	 * (OSM raster graded to the night palette, no Cesium viewer) with only what matters drawn on it — the
	 * report's dashed "place matched" ring, the road it sits on, a vehicle's lawful reads, an operation's
	 * route. Crumbs top-left, "Open in the map" top-right, the OSM credit bottom-right; a scrim fades it into
	 * the page so the title bar can sit over its lower edge. Never a photo, never anything that reads as a
	 * camera feed.
	 */
	import { t } from '$lib/i18n/strings';
	import './packs.object';
	import Glyph from '../Glyph.svelte';
	import MapThumb from '../map/MapThumb.svelte';
	import type { LonLat } from '../map/mercator';
	import type { HeroVM } from './view';
	import type { PosterVM } from './model';
	import { kindWord } from '../home/view';
	import Cover from '../media/Cover.svelte';
	import VehicleShot from '../media/VehicleShot.svelte';
	import AgencyMark from '../media/AgencyMark.svelte';
	import '../media/packs.media';

	let {
		hero,
		crumbs,
		mapHref,
		lang,
		roads = null,
		poster = null,
	}: {
		poster?: PosterVM;
		hero: HeroVM;
		crumbs: readonly { label: string; href?: string | null }[];
		mapHref: string;
		lang: string;
		roads?: readonly (readonly LonLat[])[] | null;
	} = $props();
</script>

<section class={['banner', poster && 'has-poster']} aria-label={hero.alt} data-testid="obj-hero">
	<MapThumb
		class="stage"
		overlay={hero.overlay}
		alt={hero.alt}
		zoom={hero.zoom}
		focus={[0.56, 0.4]}
		maxTiles={40}
		markerR={22}
		frameOn="points"
		labels
		eager
		credit
		creditLabel={`${t(lang, 'obj_maps_credit')} © OpenStreetMap contributors`}
		{roads}
	/>
	<div class="scrim" aria-hidden="true"></div>
	{#if poster}
		<div class={['poster', poster.kind]} data-testid="obj-poster" data-poster={poster.kind}>
			{#if poster.kind === 'cover'}
				<Cover art={poster.art} photo={poster.photo} alt={t(lang, 'v3i_art_alt', kindWord(poster.label, lang))} {lang} eager sizes="(max-width: 1500px) 360px, 460px" />
			{:else if poster.kind === 'vehicle'}
				<VehicleShot cls={poster.cls} {lang} width={420} />
			{:else}
				<VehicleShot cls={poster.cls} {lang} width={420} decorative />
				<span class="poster-mark"><AgencyMark role={poster.role} {lang} size={40} /></span>
			{/if}
		</div>
	{/if}
	<nav class="crumbs" aria-label={t(lang, 'obj_crumb_home')}>
		{#each crumbs as c, i (i)}
			{#if c.href}
				<a class="crumb" href={c.href}>{#if i === 0}<Glyph name="arrowL" size={16} />{/if}{c.label}</a>
			{:else}
				<span class="crumb" aria-current="page">{c.label}</span>
			{/if}
		{/each}
	</nav>
	<a class="open-map" href={mapHref} data-testid="obj-open-map"><Glyph name="map" size={16} />{t(lang, 'obj_open_map')}</a>
</section>

<style>
	.banner {
		position: relative;
		height: 380px;
		overflow: hidden;
		background: var(--v3-map-bg);
		isolation: isolate;
	}

	.banner :global(.stage) {
		position: absolute;
		inset: 0;
		z-index: 0;
	}

	/* the credit sits above the scrim, under the crumbs: clear of the title bar and of the marker's own label (the place
	   is framed right of centre, so a credit under "Open in the map" ran into it) */
	.banner :global(.stage .credit) {
		top: 64px;
		left: var(--v3-gut);
		right: auto;
		bottom: auto;
		z-index: 4;
	}

	.scrim {
		position: absolute;
		inset: 0;
		z-index: 1;
		pointer-events: none;
		background: linear-gradient(0deg, var(--v3-bg) 0%, var(--v3-scrim-mid) 28%, var(--v3-scrim-soft) 58%, var(--v3-scrim-none) 100%);
	}

	.crumbs {
		position: absolute;
		top: 18px;
		left: var(--v3-gut);
		z-index: 3;
		display: flex;
		gap: 8px;
	}

	.crumb,
	.open-map {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		height: 32px;
		padding: 0 12px;
		border-radius: 16px;
		background: var(--v3-glass);
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
		font-weight: 600;
		text-decoration: none;
		white-space: nowrap;
	}

	a.crumb:hover {
		color: var(--v3-t1);
	}

	.open-map {
		position: absolute;
		top: 18px;
		right: var(--v3-gut);
		z-index: 3;
		height: 36px;
		padding: 0 14px;
		border-radius: 18px;
		color: var(--v3-t1);
		font-size: 14px;
	}

	.open-map:hover {
		background: var(--v3-s3);
	}

	/* the picture beside the map: key art, a credited reference photo, a vehicle class or an agency */
	.poster {
		position: absolute;
		top: 18px;
		right: var(--v3-gut);
		z-index: 2;
		width: clamp(220px, 27%, 440px);
		aspect-ratio: 16 / 9;
		overflow: hidden;
		border: 1px solid var(--v3-line-2);
		border-radius: var(--v3-radius-xl);
		background: var(--v3-glass);
		box-shadow: var(--v3-elev-2);
	}

	.poster :global(.cover) {
		width: 100%;
		height: 100%;
	}

	.poster.vehicle,
	.poster.agency {
		display: grid;
		place-items: center;
	}

	.poster :global(.shot) {
		width: 92%;
		height: auto;
	}

	.poster-mark {
		position: absolute;
		left: 14px;
		bottom: 12px;
	}

	.has-poster .open-map {
		right: calc(var(--v3-gut) + clamp(220px, 27%, 440px) + 14px);
	}

	.crumb:focus-visible,
	.open-map:focus-visible {
		outline: 2px solid var(--v3-brand);
		outline-offset: 2px;
	}

	@media (max-width: 1500px) {
		.banner {
			height: 300px;
		}
	}
</style>
