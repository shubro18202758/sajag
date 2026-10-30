<script lang="ts">
	/**
	 * MapStyleSwitch (V3-P4C) — "Map style: Satellite · Map". One two-way switch for the style of every map thumbnail
	 * (Home, Decide, the object pages, the Layers sheet's pictures), remembered per browser (map-style.svelte.ts).
	 * Satellite is the default whenever the deck has the Cesium ion key; without the key it is off with its reason
	 * (the keyless map is all there is), and it stays off for the rest of the session once ion has refused (a dead
	 * token, a spent quota, the request cap) — the maps then show the night map and this says so. Used in the
	 * Layers sheet; the header menu uses it too (INTEGRATION.patch). Lives outside /map's pack: its words are in
	 * packs.mapstyle.ts, all three languages.
	 */
	import { onMount } from 'svelte';
	import { t } from '$lib/i18n/strings';
	import Glyph from '../Glyph.svelte';
	import { mapStyle } from './map-style.svelte';
	import './packs.mapstyle';

	let { lang, label = true, hint = false, class: cls = '' }: { lang: string; label?: boolean; hint?: boolean; class?: string } = $props();

	onMount(() => void mapStyle.ensure());

	const canSat = $derived(mapStyle.keyed !== false && mapStyle.degraded === null);
	/** What is pressed: the choice, but never satellite where it cannot be had. */
	const value = $derived(canSat ? mapStyle.want : 'map');
	const why = $derived(mapStyle.degraded !== null ? t(lang, 'v3ms_paused') : t(lang, 'v3ms_needs_key'));
</script>

<div class={['mss', cls]} data-v3="map-style-switch" data-testid="v3-map-style">
	{#if label}<span class="lab" id="v3-mss-label">{t(lang, 'v3ms_label')}</span>{/if}
	<div class="seg" role="group" aria-label={t(lang, 'v3ms_label')}>
		<button
			type="button"
			aria-pressed={value === 'satellite'}
			aria-disabled={!canSat ? 'true' : undefined}
			class={['opt', value === 'satellite' && 'is-on']}
			title={canSat ? t(lang, 'v3ms_tip_satellite') : why}
			data-map-style="satellite"
			onclick={() => {
				if (canSat) mapStyle.setPref('satellite');
			}}><Glyph name="globe" size={16} />{t(lang, 'v3ms_satellite')}</button
		>
		<button
			type="button"
			aria-pressed={value === 'map'}
			class={['opt', value === 'map' && 'is-on']}
			title={t(lang, 'v3ms_tip_map')}
			data-map-style="map"
			onclick={() => mapStyle.setPref('map')}><Glyph name="map" size={16} />{t(lang, 'v3ms_map')}</button
		>
	</div>
	{#if !canSat}<p class="why">{why}</p>{:else if hint}<p class="why">{t(lang, 'v3ms_hint')}</p>{/if}
</div>

<style>
	.mss {
		display: flex;
		flex-direction: column;
		gap: 6px;
		min-width: 0;
	}

	.lab {
		color: var(--v3-t3);
		font-size: var(--v3-text-micro);
		line-height: var(--v3-lh-micro);
		font-weight: 600;
	}

	.seg {
		display: inline-flex;
		padding: 3px;
		gap: 2px;
		border: 1px solid var(--v3-line-2);
		border-radius: var(--v3-radius-m);
		background: var(--v3-s1);
	}

	.opt {
		flex: 1;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		gap: 6px;
		min-height: 36px;
		padding: 0 12px;
		border: 0;
		border-radius: calc(var(--v3-radius-m) - 3px);
		background: none;
		color: var(--v3-t2);
		font: inherit;
		font-size: 14px;
		font-weight: 600;
		cursor: pointer;
	}

	.opt.is-on {
		background: var(--v3-s3);
		color: var(--v3-t1);
	}

	.opt[aria-disabled='true'] {
		cursor: not-allowed;
		opacity: 0.55;
	}

	.opt:focus-visible {
		outline: 2px solid var(--v3-brand);
		outline-offset: 1px;
	}

	.why {
		margin: 0;
		color: var(--v3-t3);
		font-size: var(--v3-text-micro);
		line-height: var(--v3-lh-micro);
	}
</style>
