<script lang="ts">
	/**
	 * ProposalCard (V3-SPEC §5.7) — something waiting for an officer that this turn touched: the real map of the place
	 * (MapThumb), a "Proposal" tag when the assistant proposed it (violet) or "Waits for a decision" when a rule
	 * did, the time left, the title and why, then "Open to decide" (the decision's ONE home in Decide) and "Show on
	 * map". NEVER Apply, never Approve: the assistant reads and proposes, a named officer decides.
	 * A map proposal (a camera move the brain suggested) is the same card without a map: it waits on /map, where
	 * the officer applies or dismisses it.
	 */
	import Glyph from '../Glyph.svelte';
	import V3Tag from '../ui/V3Tag.svelte';
	import MapThumb from '../map/MapThumb.svelte';
	import type { LonLat } from '../map/mercator';
	import type { InsetVM, ThumbVM } from '../home/view';
	import VehicleShot from '../media/VehicleShot.svelte';

	let {
		thumb = null,
		roads = null,
		tag,
		ai = false,
		timer = null,
		title,
		why,
		openHref = null,
		openText,
		mapText,
		onshowmap,
		kind = 'decision',
		inset = null,
		lang = 'en',
	}: {
		inset?: InsetVM;
		lang?: string;
		thumb?: ThumbVM | null;
		roads?: readonly (readonly LonLat[])[] | null;
		tag: string;
		ai?: boolean;
		timer?: string | null;
		title: string;
		why: string;
		openHref?: string | null;
		openText: string;
		mapText: string;
		onshowmap: () => void;
		kind?: 'decision' | 'map';
	} = $props();
</script>

<article class={['prop', !thumb && 'flat']} data-testid="v3-proposal" data-kind={kind}>
	{#if thumb}
		<div class="pm">
			<MapThumb overlay={thumb.overlay} zoom={thumb.zoom ?? 15} frameOn={thumb.frameOn ?? 'all'} alt={thumb.alt} {roads} />
			{#if inset}
				<span class={['inset', inset.kind]} aria-hidden="true">
					{#if inset.kind === 'vehicle'}<VehicleShot cls={inset.cls} {lang} width={140} decorative />{:else}<img src={inset.art} alt="" width="160" height="90" loading="lazy" decoding="async" />{/if}
				</span>
			{/if}
		</div>
	{/if}
	<div class="pb">
		<div class="row">
			<V3Tag size="sm" tone={ai ? 'ai' : 'neutral'} glyph={ai ? 'spark' : kind === 'map' ? 'map' : 'decide'}>{tag}</V3Tag>
			{#if timer}<V3Tag size="sm" tone="decide" glyph="clock">{timer}</V3Tag>{/if}
		</div>
		<h3 class="h3">{title}</h3>
		{#if why}<p class="meta">{why}</p>{/if}
		<div class="row acts">
			{#if openHref}<a class="btn" href={openHref} data-testid="v3-proposal-open">{openText}<Glyph name="arrowR" size={16} /></a>{/if}
			<button type="button" class="link" data-testid="v3-proposal-map" onclick={onshowmap}>{mapText}</button>
		</div>
	</div>
</article>

<style>
	.prop {
		display: grid;
		grid-template-columns: 200px minmax(0, 1fr);
		overflow: hidden;
		border: 1px solid var(--v3-line-2);
		border-radius: 18px;
		background: var(--v3-s1);
	}

	.prop.flat {
		grid-template-columns: minmax(0, 1fr);
	}

	.inset {
		position: absolute;
		top: 10px;
		right: 10px;
		z-index: 2;
		display: grid;
		place-items: center;
		width: 36%;
		aspect-ratio: 16 / 10;
		overflow: hidden;
		border: 1px solid var(--v3-line-2);
		border-radius: var(--v3-radius-m);
		background: var(--v3-glass);
		box-shadow: var(--v3-elev-1);
	}

	.inset :global(.shot),
	.inset img {
		display: block;
		width: 100%;
		height: 100%;
		object-fit: cover;
	}

	.inset.vehicle :global(.shot) {
		object-fit: contain;
	}

	.pm {
		position: relative;
		min-height: 150px;
		background: var(--v3-map-bg);
	}

	.pm :global([data-v3='map-thumb']) {
		position: absolute;
		inset: 0;
		width: 100%;
		height: 100%;
	}

	.pb {
		display: flex;
		flex-direction: column;
		gap: 8px;
		padding: 16px 18px;
		min-width: 0;
	}

	.row {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 8px;
	}

	.acts {
		margin-top: 4px;
		gap: 16px;
	}

	.h3 {
		margin: 0;
		font-size: var(--v3-text-sub);
		line-height: var(--v3-lh-sub);
		font-weight: 620;
	}

	.meta {
		margin: 0;
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
		line-height: var(--v3-lh-meta);
	}

	.btn {
		display: inline-flex;
		align-items: center;
		gap: 8px;
		height: 36px;
		padding: 0 14px;
		border-radius: 18px;
		background: var(--v3-primary-bg);
		color: var(--v3-primary-ink);
		font-size: 14px;
		font-weight: 650;
		text-decoration: none;
		white-space: nowrap;
	}

	.btn:hover {
		background: var(--v3-primary-hover);
	}

	.link {
		border: 0;
		background: none;
		padding: 0;
		color: var(--v3-brand-text);
		font: inherit;
		font-size: 15px;
		font-weight: 600;
		cursor: pointer;
	}

	.btn:focus-visible,
	.link:focus-visible {
		outline: 2px solid var(--v3-brand);
		outline-offset: 2px;
	}

	@media (max-width: 1500px) {
		.prop {
			grid-template-columns: 150px minmax(0, 1fr);
		}
	}
</style>
