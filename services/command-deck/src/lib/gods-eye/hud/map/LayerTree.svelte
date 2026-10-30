<script lang="ts">
	/**
	 * LayerTree — the map's layers by group (SPEC §5.3 "LayerTree [S3]";
	 * plan contract X7): Traffic, Enforcement, Response, Corridors, Reported
	 * events, in that order; an empty group is hidden. Each row: an
	 * EyeToggle, a symbol (a hue sample only for the layers that carry a
	 * hue — the watchlist track, the decision dot, the event line, the route
	 * line, the flow ramp; otherwise the type glyph), the label, a compact
	 * provenance glyph and a count. An empty layer dims and reads "None now".
	 * The base map is a Photoreal · Streets · Dark segmented control.
	 *
	 * It reads the mounted canvas's rows (map-state.svelte.ts), so a page may
	 * mount it in a dock (`onLayers`) or the canvas shows it in its own
	 * panel; the toggles go back to the canvas.
	 *
	 * Test hooks (SPEC §12.2, §12.4): rows carry `data-layer` and
	 * `data-visible`, their hint as the title and `.warn` on a feed problem;
	 * a click on the row (or its eye) toggles the layer; the flow row's
	 * simulated glyph is `chip-simulated`; the Photoreal option carries
	 * `data-layer="photoreal-3d"` with the photoreal layer's hint.
	 */
	import type { HTMLAttributes } from 'svelte/elements';
	import { t } from '$lib/i18n/strings';
	import '$lib/i18n/packs.map';
	import { INTENT_ICON, kindIcon, type IconName } from '$lib/design/icons';
	import Button from '$lib/ui/Button.svelte';
	import EyeToggle from '$lib/ui/EyeToggle.svelte';
	import Icon from '$lib/ui/Icon.svelte';
	import ProvenanceTag from '$lib/ui/ProvenanceTag.svelte';
	import SegmentedControl from '$lib/ui/SegmentedControl.svelte';
	import { LAYER_GROUPS, type LayerGroup } from '../../registry';
	import { mapChrome, type BasemapStyle, type LayerRow } from './map-state.svelte';

	interface Props extends HTMLAttributes<HTMLDivElement> {
		/** Language (default: the canvas's). */
		lang?: string;
		/** Show a close control (the canvas's own panel). */
		onclose?: () => void;
	}

	let { lang, onclose, class: cls = '', ...rest }: Props = $props();

	const L = $derived(lang ?? mapChrome.lang);
	let collapsed = $state<Record<string, boolean>>({});

	const groups = $derived(
		LAYER_GROUPS.map((g) => ({ id: g, rows: mapChrome.rows.filter((r) => r.group === g) })).filter((g) => g.rows.length > 0),
	);

	/** The object kind a layer draws (its type glyph). */
	const LAYER_KIND: Record<string, string> = {
		flow: 'road',
		signals: 'junction',
		anomalies: 'anomaly',
		traces: 'vehicle',
		enforcement: 'recommendation',
		cameras: 'camera',
		units: 'unit',
		dispatch: 'dispatch',
		events: 'event',
		convoy: 'convoy',
		osint: 'osint_event',
		places: 'place',
	};
	const glyphOf = (id: string): IconName => kindIcon(LAYER_KIND[id] ?? id);

	const GROUP_KEY: Record<LayerGroup, string> = {
		traffic: 'map_group_traffic',
		enforcement: 'map_group_enforcement',
		response: 'map_group_response',
		corridors: 'map_group_corridors',
		intelligence: 'map_group_intelligence',
	};

	const basemapOptions = $derived([
		{
			value: 'photoreal' as BasemapStyle,
			label: t(L, 'map_basemap_photoreal'),
			disabled: !mapChrome.photoreal.available,
			attrs: { 'data-layer': 'photoreal-3d', title: mapChrome.photoreal.hint || t(L, 'map_layer_photoreal') },
		},
		{ value: 'streets' as BasemapStyle, label: t(L, 'map_basemap_streets') },
		{ value: 'dark' as BasemapStyle, label: t(L, 'map_basemap_dark') },
	]);

	function toggle(row: LayerRow) {
		mapChrome.setLayer(row.id, !row.visible);
	}

	function onRowKey(e: KeyboardEvent, row: LayerRow) {
		if (e.key === 'Enter' || e.key === ' ') {
			e.preventDefault();
			toggle(row);
		}
	}
</script>

{#snippet symbol(row: LayerRow)}
	{#if row.id === 'flow'}
		<svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
			{#each [1, 2, 3, 4, 5] as s, i (s)}
				<rect x={i * 3.2} y={8 - (0.5 + i * 0.45)} width="2.4" height={1 + i * 0.9} rx="0.4" fill={`var(--v-flow-${s})`} />
			{/each}
		</svg>
	{:else if row.id === 'traces'}
		<svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
			<path d="M2 12 L7 6 L10 9 L14 4" fill="none" stroke="var(--v-map-casing)" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" />
			<path d="M2 12 L7 6 L10 9 L14 4" fill="none" stroke="var(--v-map-alert)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
		</svg>
	{:else if row.id === 'enforcement'}
		<svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
			<circle cx="8" cy="8" r="4.5" fill="var(--v-map-decision)" stroke="var(--v-map-casing)" stroke-width="1.5" />
		</svg>
	{:else if row.id === 'events' || row.id === 'convoy'}
		<svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
			<path d="M2 11 C5 4, 9 13, 14 5" fill="none" stroke={row.id === 'events' ? 'var(--v-map-event)' : 'var(--v-map-route)'} stroke-width="2.25" stroke-linecap="round" />
		</svg>
	{:else}
		<Icon name={glyphOf(row.id)} size={16} />
	{/if}
{/snippet}

<div data-map="layer-tree" class={['layer-tree', cls]} {...rest}>
	<div class="head">
		<span class="title">{t(L, 'map_layers_title')}</span>
		<span class="grow"></span>
		<Button minimal small icon="list" pressed={mapChrome.legendOpen} onclick={() => mapChrome.toggleLegend()}>{t(L, 'map_tool_legend')}</Button>
		{#if onclose}
			<Button minimal small icon="small-cross" tooltip={t(L, 'map_tool_layers')} aria-label={t(L, 'map_tool_layers')} onclick={onclose} />
		{/if}
	</div>
	<ul class="tree" role="tree" aria-label={t(L, 'map_layers_title')}>
		{#each groups as g (g.id)}
			<li class="group" role="treeitem" aria-expanded={!collapsed[g.id]} aria-selected="false">
				<button type="button" class="group-head" onclick={() => (collapsed = { ...collapsed, [g.id]: !collapsed[g.id] })}>
					<Icon name={collapsed[g.id] ? 'chevron-right' : 'chevron-down'} size={16} />
					<span>{t(L, GROUP_KEY[g.id])}</span>
				</button>
				{#if !collapsed[g.id]}
					<ul role="group">
						{#each g.rows as row (row.id)}
							<li
								role="treeitem"
								aria-selected="false"
								tabindex="0"
								class={['tree-row', row.empty && 'dim empty', row.error && 'warn', row.paused && 'paused']}
								data-layer={row.id}
								data-visible={row.visible ? 'true' : 'false'}
								title={row.paused ? `${row.hint} · ${t(L, 'map_layer_paused')}` : row.hint}
								onclick={() => toggle(row)}
								onkeydown={(e) => onRowKey(e, row)}
							>
								<!-- "None now" reads at the row's end (prototype), so the eye keeps its place -->
								<EyeToggle visible={row.visible} label={row.label} lang={L} onchange={(v) => mapChrome.setLayer(row.id, v)} />
								<span class="lsym">{@render symbol(row)}</span>
								<span class="label">{row.label}</span>
								<span class="sec">
									{#if row.error}
										<span class="feed-warn" title={row.error}><Icon name={INTENT_ICON.warning} size={12} /></span>
									{/if}
									{#if row.simulated}
										<ProvenanceTag source="simulated" compact lang={L} data-testid="chip-simulated" />
									{:else if row.emulated}
										<ProvenanceTag source="emulated" compact lang={L} />
									{/if}
									{#if row.empty}<span class="none">{t(L, 'ui_eye_none')}</span>{:else}<span class="count">{row.count}</span>{/if}
								</span>
							</li>
						{/each}
					</ul>
				{/if}
			</li>
		{/each}
	</ul>
	<div class="basemap">
		<span class="title">{t(L, 'map_basemap_title')}</span>
		<SegmentedControl
			fill
			small
			options={basemapOptions}
			value={mapChrome.basemap}
			label={t(L, 'map_basemap_title')}
			onchange={(v) => mapChrome.setBasemap(v)}
		/>
	</div>
</div>

<style>
	.layer-tree {
		display: flex;
		flex-direction: column;
		min-height: 0;
		font-family: var(--v-font-ui);
		font-size: var(--v-text-base);
		color: var(--v-ink-1);
		background: var(--v-surface-1);
	}

	.head {
		display: flex;
		align-items: center;
		gap: 8px;
		height: 40px;
		padding: 0 8px 0 16px;
		border-bottom: 1px solid var(--v-line-2);
		flex: 0 0 auto;
	}

	.title {
		font-weight: 600;
		font-size: var(--v-text-base);
	}

	.grow {
		flex: 1 1 auto;
	}

	.tree,
	.tree ul {
		list-style: none;
		margin: 0;
		padding: 0;
	}

	.tree {
		padding: 4px 0;
		overflow: auto;
		min-height: 0;
	}

	.group-head {
		display: flex;
		align-items: center;
		gap: 4px;
		width: 100%;
		height: 30px;
		padding: 0 12px 0 8px;
		border: 0;
		background: transparent;
		color: var(--v-ink-1);
		font: inherit;
		font-weight: 600;
		cursor: pointer;
		text-align: left;
	}

	.group-head:hover {
		background: var(--v-row-hover);
	}

	.group-head :global([data-ui='icon']) {
		color: var(--v-ink-2);
	}

	.tree-row {
		display: flex;
		align-items: center;
		gap: 0;
		height: 30px;
		padding: 0 12px 0 28px;
		cursor: pointer;
		position: relative;
	}

	.tree-row:hover {
		background: var(--v-row-hover);
	}

	.tree-row:focus-visible {
		outline: 2px solid var(--v-focus);
		outline-offset: -2px;
	}

	.tree-row :global([data-ui='eye-toggle']) {
		margin-right: 4px;
	}

	.lsym {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 16px;
		height: 16px;
		margin-right: 8px;
		flex: 0 0 auto;
		color: var(--v-ink-2);
	}

	.label {
		flex: 1 1 auto;
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.sec {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		flex: 0 0 auto;
		color: var(--v-ink-2);
		font-size: var(--v-text-xs);
	}

	.count {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		min-width: 20px;
		height: 20px;
		padding: 0 6px;
		border-radius: var(--v-radius-pill);
		background: var(--v-neutral-veil);
		color: var(--v-ink-1);
		font-variant-numeric: tabular-nums;
	}

	.dim .label,
	.dim .lsym,
	.dim :global([data-ui='eye-toggle'] button) {
		color: var(--v-ink-disabled);
	}

	.none {
		color: var(--v-ink-disabled);
		white-space: nowrap;
	}

	.paused .label {
		color: var(--v-ink-2);
	}

	.feed-warn {
		display: inline-flex;
		color: var(--v-danger-text);
	}

	.basemap {
		display: flex;
		flex-direction: column;
		gap: 8px;
		padding: 12px 16px;
		border-top: 1px solid var(--v-line-2);
		flex: 0 0 auto;
	}
</style>
