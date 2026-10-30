<script lang="ts">
	/**
	 * The anatomy every Home card shares (V3-SPEC §5.2, L1): a picture with one state tag on it, then art + kind
	 * line + title, two lines of why, and a foot that ends in one verb. The whole card is one link (a keyboard stop;
	 * screen readers hear `aria`); hover lifts it 3 px (none under reduced motion). A decision card wears the orange
	 * border.
	 *
	 * The picture (V3-P7): an operation, a report or a planned event leads with artwork — the kind's key art, or a
	 * credited reference photo of the place — with the real map of the place as an inset in the corner; a decision
	 * keeps the place's map as the picture (where it happens matters) with the vehicle class's studio shot or the
	 * kind's key art over the corner.
	 */
	import type { Snippet } from 'svelte';
	import MapThumb from '../map/MapThumb.svelte';
	import type { LonLat } from '../map/mercator';
	import Cover from '../media/Cover.svelte';
	import VehicleShot from '../media/VehicleShot.svelte';
	import type { CoverVM, InsetVM, ThumbVM } from './view';

	let {
		href,
		aria,
		thumb,
		art,
		kind,
		title,
		decide = false,
		roads = null,
		testid = 'v3-card',
		data = {},
		badge,
		titleExtra,
		children,
		foot,
		cover = null,
		inset = null,
		lang,
	}: {
		cover?: CoverVM | null;
		inset?: InsetVM;
		lang: string;
		href: string;
		aria: string;
		thumb: ThumbVM;
		art: string;
		kind: string;
		title: string;
		decide?: boolean;
		roads?: readonly (readonly LonLat[])[] | null;
		testid?: string;
		data?: Record<string, string>;
		badge?: Snippet;
		titleExtra?: Snippet;
		children?: Snippet;
		foot?: Snippet;
	} = $props();
</script>

<a class={['card', decide && 'decide']} {href} aria-label={aria} data-testid={testid} {...Object.fromEntries(Object.entries(data).map(([k, v]) => [`data-${k}`, v]))}>
	{#if cover}
		<Cover class="thumb" art={cover.art} photo={cover.photo} alt={cover.alt} {lang} compact sizes="(max-width: 1500px) 400px, 520px">
			{#if badge}<span class="badge-tl">{@render badge()}</span>{/if}
			<span class="map-inset" aria-hidden="true">
				<MapThumb class="inset-map" overlay={thumb.overlay} zoom={Math.max(11, (thumb.zoom ?? 15) - 1)} frameOn={thumb.frameOn ?? 'all'} alt={thumb.alt} markerR={9} {roads} />
			</span>
		</Cover>
	{:else}
		<!-- with an inset in the bottom-right corner, the place is framed in the part of the map it leaves free -->
		<MapThumb class="thumb" overlay={thumb.overlay} zoom={thumb.zoom ?? 15} frameOn={thumb.frameOn ?? 'all'} focus={inset ? [0.38, 0.5] : [0.5, 0.5]} alt={thumb.alt} {roads}>
			{#if badge}<span class="badge-tl">{@render badge()}</span>{/if}
			{#if inset}
				<span class={['art-inset', inset.kind]} aria-hidden="true">
					{#if inset.kind === 'vehicle'}<VehicleShot cls={inset.cls} {lang} width={150} decorative />{:else}<img src={inset.art} alt="" width="160" height="90" loading="lazy" decoding="async" />{/if}
				</span>
			{/if}
		</MapThumb>
	{/if}
	<span class="body">
		<span class="head">
			<img class="art" src={art} alt="" width="44" height="44" loading="lazy" />
			<span class="ht">
				<span class="micro">{kind}</span>
				<span class="t"><span class="tt" title={title}>{title}</span>{@render titleExtra?.()}</span>
			</span>
		</span>
		{@render children?.()}
		{#if foot}<span class="foot">{@render foot()}</span>{/if}
	</span>
</a>

<style>
	.card {
		position: relative;
		display: flex;
		flex: 1;
		flex-direction: column;
		min-width: 0;
		overflow: hidden;
		border: 1px solid var(--v3-line-1);
		border-radius: var(--v3-radius-l);
		background: var(--v3-s1);
		color: var(--v3-t1);
		text-decoration: none;
		transition:
			transform var(--v3-dur-2) var(--v3-ease),
			border-color var(--v3-dur-2),
			box-shadow var(--v3-dur-2);
		/* a card that joins a rail (a new decision, a new report) arrives softly: 200 ms */
		animation: v3c-enter var(--v3-dur-2) var(--v3-ease) both;
	}

	@keyframes v3c-enter {
		from {
			opacity: 0;
			transform: translateY(8px);
		}
		to {
			opacity: 1;
			transform: none;
		}
	}

	.card:hover {
		transform: translateY(-3px);
		border-color: var(--v3-line-3);
		box-shadow: var(--v3-elev-1);
	}

	.card.decide {
		border-color: var(--v3-decide-line);
	}

	.card:focus-visible {
		outline: 2px solid var(--v3-brand);
		outline-offset: 2px;
	}

	.card :global(.thumb) {
		aspect-ratio: 16 / 8.2;
		flex: none;
	}

	.map-inset {
		position: absolute;
		top: 10px;
		right: 10px;
		z-index: 2;
		width: 34%;
		aspect-ratio: 16 / 10;
		overflow: hidden;
		border: 1px solid var(--v3-line-3);
		border-radius: var(--v3-radius-m);
		box-shadow: var(--v3-elev-1);
	}

	.map-inset :global(.inset-map) {
		width: 100%;
		height: 100%;
	}

	/* bottom-right, clear of the state tags (top-left) and above the imagery credit line */
	.art-inset {
		position: absolute;
		right: 10px;
		bottom: 26px;
		z-index: 2;
		display: grid;
		place-items: center;
		width: 32%;
		aspect-ratio: 16 / 10;
		overflow: hidden;
		border: 1px solid var(--v3-glass-border);
		border-radius: var(--v3-radius-m);
		background: var(--v3-glass-bg);
		-webkit-backdrop-filter: var(--v3-glass-blur);
		backdrop-filter: var(--v3-glass-blur);
		box-shadow: var(--v3-elev-1);
	}

	.art-inset.vehicle :global(.shot) {
		width: 100%;
		height: 100%;
	}

	.art-inset.art img {
		display: block;
		width: 100%;
		height: 100%;
		object-fit: cover;
	}

	.badge-tl {
		position: absolute;
		left: 12px;
		top: 12px;
		z-index: 2;
		display: flex;
		gap: 6px;
	}

	.body {
		display: flex;
		flex: 1;
		flex-direction: column;
		gap: 6px;
		padding: 14px 16px 16px;
	}

	.head {
		display: flex;
		align-items: center;
		gap: 12px;
		min-width: 0;
	}

	.art {
		flex: none;
		width: 44px;
		height: 44px;
		border-radius: var(--v3-radius-m);
	}

	.ht {
		display: flex;
		flex-direction: column;
		gap: 2px;
		min-width: 0;
	}

	.micro {
		color: var(--v3-t3);
		font-size: var(--v3-text-micro);
		line-height: var(--v3-lh-micro);
		font-weight: 600;
	}

	.t {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 4px 8px;
		min-width: 0;
		font-size: 16px;
		line-height: 22px;
		font-weight: 650;
	}

	.tt {
		display: -webkit-box;
		-webkit-line-clamp: 2;
		line-clamp: 2;
		-webkit-box-orient: vertical;
		overflow: hidden;
		overflow-wrap: anywhere;
	}

	.foot {
		display: flex;
		align-items: center;
		gap: 8px;
		margin-top: auto;
		padding-top: 8px;
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
		font-weight: 500;
	}

	@media (prefers-reduced-motion: reduce) {
		.card,
		.card:hover {
			transform: none;
			transition: none;
			animation: none;
		}
	}
</style>
