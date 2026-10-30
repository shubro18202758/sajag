<script lang="ts">
	/**
	 * LayersSheet (V3-SPEC §5.6) — one level down from the clean map: the base map (Satellite 3D · City map), the map
	 * style of every thumbnail (Satellite · Map: MapStyleSwitch, V3-P4C), then the
	 * layers that start off — Operations (units, dispatches) and City (ANPR cameras, junctions and signals,
	 * traffic flow, named places, feed checks) — each a switch with what it holds now and its provenance in words
	 * (a simulated feed says "Simulated", the scenario emulator's units say "Emulated"; the waterlogging nowcast says
	 * "Modelled", or "Hindsight" while the 19 Aug 2025 replay is on the map), then Forecasts (waterlogging risk,
	 * on by default; the traffic forecast). The Vehicles-only rule
	 * closes the sheet. Rows come from the mounted canvas (mapChrome.rows); toggles go back through it.
	 */
	import { t } from '$lib/i18n/strings';
	import type { LayerRow } from '$lib/gods-eye/hud/map/map-state.svelte';
	import Glyph from '../Glyph.svelte';
	import V3Tag from '../ui/V3Tag.svelte';
	import MapThumb from './MapThumb.svelte';
	import { CITY_CORE_BBOX, bboxArray } from '$lib/city';
	import MapStyleSwitch from './MapStyleSwitch.svelte';
	import { SHEET, aiLayerSub } from './model';
	import './packs.map3';
	import '$lib/ai/packs.ai';
	import '$lib/cityfeeds/packs.feeds';
	import { cityFeeds } from '$lib/cityfeeds/store.svelte';
	import { feedRowDetail } from '$lib/cityfeeds/model';

	/** The base-map pictures frame the city's central district (City Pack). */
	const CORE = bboxArray(CITY_CORE_BBOX);

	let {
		rows,
		is3d,
		can3d,
		why3d,
		lang,
		onlayer,
		on3d,
		onclose,
		hindsightOn = false,
	}: {
		rows: readonly LayerRow[];
		is3d: boolean;
		can3d: boolean;
		why3d: string;
		lang: string;
		onlayer: (id: string, on: boolean) => void;
		on3d: (on: boolean) => void;
		onclose: () => void;
		/** The 19 Aug 2025 replay is on the map (the waterlogging row says "Hindsight"). */
		hindsightOn?: boolean;
	} = $props();

	const byId = $derived(new Map(rows.map((r) => [r.id, r])));

	function sub(r: LayerRow | undefined, id: string): string {
		// the city-feed rows add the shared summary's detail (the worst air band, the nearest cyclone's distance)
		const extra = feedRowDetail(id, cityFeeds.summary);
		const ai = aiLayerSub(id, r && extra ? { ...r, detail: extra } : r, hindsightOn, (k, ...a) => t(lang, k, ...a));
		if (ai != null) return ai;
		if (!r) return t(lang, 'v3m_l_none');
		if (r.paused) return t(lang, 'v3m_l_paused');
		// an OFF layer counts nothing: say what it would show, never "none"
		if (!r.visible) return t(lang, `v3m_l_${id}_about`);
		if (r.error) return t(lang, 'v3m_l_feed');
		if (r.empty) return t(lang, 'v3m_l_none');
		if (id === 'flow' && r.simulated) return t(lang, 'v3m_l_flow_sim', r.count);
		if (id === 'cameras') return t(lang, 'v3m_l_cameras_sub', r.count);
		if (id === 'places') return t(lang, 'v3m_l_places_sub');
		if (id === 'landmarks') return t(lang, 'v3m_l_landmarks_sub', r.count);
		if (id === 'livevalues') return t(lang, 'v3m_l_livevalues_sub', r.count);
		return t(lang, 'v3m_l_count', r.count);
	}
</script>

<section class="sheet v3-glass" id="v3-layers-sheet" aria-labelledby="v3-layers-h" data-testid="v3-layers-sheet" data-ge-keepout>
	<div class="head">
		<h2 id="v3-layers-h">{t(lang, 'v3m_sheet')}</h2>
		<button type="button" class="x" aria-label={t(lang, 'v3m_sheet_close')} title={t(lang, 'v3m_sheet_close')} onclick={onclose}><Glyph name="close" size={18} /></button>
	</div>
	<div class="micro">{t(lang, 'v3m_base')}</div>
	<div class="base" role="radiogroup" aria-label={t(lang, 'v3m_base')}>
		<button
			type="button"
			role="radio"
			aria-checked={is3d}
			aria-disabled={!can3d ? 'true' : undefined}
			title={!can3d ? why3d : undefined}
			class={['bm', is3d && 'is-selected']}
			data-base="3d"
			onclick={() => {
				if (can3d) on3d(true);
			}}
		>
			{#if can3d}
				<MapThumb class="bthumb" style="satellite" bbox={CORE} zoom={13} maxTiles={4} alt={t(lang, 'v3m_base_3d')} markerR={0} />
			{:else}
				<span class="bthumb cube" aria-hidden="true"><Glyph name="cube" size={26} /></span>
			{/if}
			{t(lang, 'v3m_base_3d')}
		</button>
		<button type="button" role="radio" aria-checked={!is3d} class={['bm', !is3d && 'is-selected']} data-base="city" onclick={() => on3d(false)}>
			<MapThumb class="bthumb" style="night" bbox={CORE} zoom={13} maxTiles={4} alt={t(lang, 'v3m_base_city')} markerR={0} />
			{t(lang, 'v3m_base_city')}
		</button>
	</div>
	{#if !can3d}<p class="hint">{why3d}</p>{/if}
	<MapStyleSwitch {lang} hint class="mstyle" />
	{#each SHEET as sec (sec.key)}
		<div class="micro gap">{t(lang, sec.key)}</div>
		{#each sec.rows as row (row.id)}
			{@const r = byId.get(row.id)}
			<div class="lr" data-layer-row={row.id}>
				<span class="lt">
					<span class="ln">{t(lang, row.key)}{#if row.id === 'waterlog'}<V3Tag size="sm" tone="dashed" glyph={hindsightOn ? 'history' : 'graph'} title={t(lang, hindsightOn ? 'ai_prov_hindsight_tip' : 'ai_prov_modelled_tip')}>{t(lang, hindsightOn ? 'ai_prov_hindsight' : 'ai_prov_modelled')}</V3Tag>{:else if row.id === 'air'}<V3Tag size="sm" tone="dashed" glyph="graph" title={t(lang, 'cf_tag_indicative_tip')}>{t(lang, 'ai_prov_modelled')}</V3Tag>{:else if row.id === 'cyclone'}<V3Tag size="sm" tone="neutral" glyph="verified" title={t(lang, 'cf_tag_gdacs_tip')}>{t(lang, 'ai_prov_live')}</V3Tag>{:else if r?.simulated}<V3Tag size="sm" tone="dashed" glyph="shuffle" title={t(lang, 'v3_prov_simulated_tip')}>{t(lang, 'v3_prov_simulated')}</V3Tag>{:else if r?.emulated}<V3Tag size="sm" tone="dashed" glyph="flask" title={t(lang, 'v3_prov_emulated_tip')}>{t(lang, 'v3_prov_emulated')}</V3Tag>{/if}</span>
					<span class="sub">{sub(r, row.id)}</span>
				</span>
				<button
					type="button"
					role="switch"
					class={['sw2', r?.visible && 'is-pressed']}
					aria-checked={!!r?.visible}
					aria-label={t(lang, row.key)}
					disabled={!r}
					data-layer={row.id}
					onclick={() => r && onlayer(row.id, !r.visible)}
				></button>
			</div>
		{/each}
	{/each}
	<p class="note"><Glyph name="shield" size={17} />{t(lang, 'v3m_vehicles_only')}</p>
</section>

<style>
	.sheet {
		display: flex;
		flex-direction: column;
		gap: 4px;
		padding: 16px 18px;
		border: 1px solid var(--v3-glass-border);
		border-radius: var(--v3-radius-l);
		background: var(--v3-glass-surface);
		box-shadow: var(--v3-elev-2);
		max-height: 100%;
		overflow: auto;
		scrollbar-width: thin;
		pointer-events: auto;
		animation: drop var(--v3-dur-2) var(--v3-ease);
	}

	@keyframes drop {
		from {
			opacity: 0;
			transform: translateY(-6px);
		}
	}

	.head {
		display: flex;
		align-items: center;
	}

	h2 {
		margin: 0;
		font-size: var(--v3-text-sub);
		line-height: var(--v3-lh-sub);
		font-weight: 650;
	}

	.x {
		margin-left: auto;
		display: grid;
		place-items: center;
		width: 36px;
		height: 36px;
		border: 0;
		border-radius: 18px;
		background: none;
		color: var(--v3-t2);
		cursor: pointer;
	}

	.x:hover {
		background: var(--v3-s2);
	}

	.micro {
		color: var(--v3-t3);
		font-size: var(--v3-text-micro);
		line-height: var(--v3-lh-micro);
		font-weight: 600;
	}

	.micro.gap {
		margin-top: 10px;
	}

	.base {
		display: flex;
		gap: 8px;
		margin: 4px 0 4px;
	}

	.bm {
		flex: 1;
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 6px;
		padding: 6px;
		border: 1.5px solid var(--v3-line-2);
		border-radius: var(--v3-radius-m);
		background: none;
		color: var(--v3-t2);
		font: inherit;
		font-size: var(--v3-text-micro);
		font-weight: 650;
		cursor: pointer;
	}

	.bm.is-selected {
		border-color: var(--v3-t1);
		background: var(--v3-s2);
		color: var(--v3-t1);
	}

	.bm[aria-disabled='true'] {
		cursor: not-allowed;
		opacity: 0.6;
	}

	.bm :global(.bthumb) {
		width: 100%;
		height: 46px;
		border-radius: var(--v3-radius-s);
		overflow: hidden;
	}

	.cube {
		display: grid;
		place-items: center;
		background: var(--v3-map-bg);
		color: var(--v3-route-text);
	}

	.sheet :global(.mstyle) {
		margin: 8px 0 2px;
	}

	.hint {
		margin: 0 0 4px;
		color: var(--v3-t3);
		font-size: var(--v3-text-micro);
	}

	.lr {
		display: flex;
		align-items: center;
		gap: 12px;
		padding: 8px 0;
	}

	.lt {
		display: flex;
		flex-direction: column;
		min-width: 0;
	}

	.ln {
		display: inline-flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 6px;
		font-size: 14px;
	}

	.sub {
		color: var(--v3-t3);
		font-size: var(--v3-text-micro);
	}

	.sw2 {
		position: relative;
		flex: none;
		margin-left: auto;
		width: 40px;
		height: 24px;
		border: 0;
		border-radius: 12px;
		background: var(--v3-s4);
		cursor: pointer;
	}

	.sw2::after {
		content: '';
		position: absolute;
		top: 3px;
		left: 3px;
		width: 18px;
		height: 18px;
		border-radius: 9px;
		background: var(--v3-t2);
		transition: left var(--v3-dur-1);
	}

	.sw2.is-pressed {
		background: var(--v3-brand-strong);
	}

	.sw2.is-pressed::after {
		left: 19px;
		background: var(--v3-on-brand);
	}

	.sw2:disabled {
		opacity: 0.4;
		cursor: not-allowed;
	}

	.sw2:focus-visible,
	.bm:focus-visible,
	.x:focus-visible {
		outline: 2px solid var(--v3-brand);
		outline-offset: 2px;
	}

	.note {
		display: flex;
		gap: 10px;
		align-items: flex-start;
		margin: 10px 0 0;
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
		line-height: 19px;
	}

	.note :global(.v3-glyph) {
		margin-top: 1px;
		color: var(--v3-t3);
	}

	@media (prefers-reduced-motion: reduce) {
		.sheet {
			animation: none;
		}

		.sw2::after {
			transition: none;
		}
	}
</style>
