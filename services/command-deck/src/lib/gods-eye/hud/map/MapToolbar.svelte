<script lang="ts" module>
	export type MapTool = 'select' | 'shape' | 'measure';
	export type ShapeMode = 'select' | 'filter';
</script>

<script lang="ts">
	/**
	 * MapToolbar — the map's tools (SPEC §5.3 "Map chrome [S3]"), top left,
	 * in Blueprint button groups. Every button is a `.chip` (canvas-ux's
	 * hit-test, ≥ 8): Select (pressed by default) · Select within shape (its
	 * menu: select within, or filter to the shape) · Search around · Measure
	 * | Layers · Legend · Thermal-style view (`.chip` of its own, §16.5
	 * confirmed the other way 2026-10-25: one click away, never a sensor;
	 * FIX-E-LOOKUP moved it into the view controls' group, with Layers and
	 * Legend — its menu under the button like the shape menu, and while a
	 * thermal mode is on the toolbar carries the honest visual-filter label)
	 * | Follow (`.chip.lock`, aria-pressed) · Live/Replay (`.chip.mode`) · the
	 * honest imagery chip (`.chip.mode.imagery`: what the base picture is —
	 * Google's photoreal city, the street map, offline — and, in its title,
	 * that it is not a live image) ·
	 * Guided tour · Exit map mode (`.chip.exit`, map mode only). No
	 * Annotate, Capture or 2D (SPEC §10.2).
	 */
	import { t } from '$lib/i18n/strings';
	import '$lib/i18n/packs.map';
	import Button from '$lib/ui/Button.svelte';
	import Menu from '$lib/ui/Menu.svelte';
	import Popover from '$lib/ui/Popover.svelte';
	import type { MenuItemSpec } from '$lib/ui/types';

	interface Props {
		lang?: string;
		tool: MapTool;
		shapeMode: ShapeMode;
		/** A filter-to-shape is applied (its menu offers to clear it). */
		shapeFiltered?: boolean;
		canSearchAround: boolean;
		layersOpen: boolean;
		legendOpen: boolean;
		/** The canvas hosts the LayerTree itself (no page dock): the Layers button is its rail. */
		layersRail?: boolean;
		follow: { pressed: boolean; disabled: boolean; title: string };
		mode: { kind: 'live' | 'window' | 'replay'; runId?: number | string | null };
		/** The imagery chip (label + its full title); null hides it. */
		imagery?: { label: string; title: string } | null;
		showExit: boolean;
		touring: boolean;
		sensor: 'raw' | 'flir-whot' | 'flir-bhot' | 'flir-iron';
		ontool: (tool: MapTool, shapeMode?: ShapeMode) => void;
		onclearshape: () => void;
		onsearcharound: () => void;
		onlayers: () => void;
		onlegend: () => void;
		onfollow: () => void;
		onmode: () => void;
		onexit: () => void;
		ontour: () => void;
		onsensor: (mode: 'raw' | 'flir-whot' | 'flir-bhot' | 'flir-iron') => void;
	}

	let {
		lang = 'en',
		tool,
		shapeMode,
		shapeFiltered = false,
		canSearchAround,
		layersOpen,
		legendOpen,
		layersRail = false,
		follow,
		mode,
		imagery = null,
		showExit,
		touring,
		sensor,
		ontool,
		onclearshape,
		onsearcharound,
		onlayers,
		onlegend,
		onfollow,
		onmode,
		onexit,
		ontour,
		onsensor,
	}: Props = $props();

	let shapeOpen = $state(false);
	let thermalOpen = $state(false);

	const shapeItems: MenuItemSpec[] = $derived([
		{ id: 'select', label: t(lang, 'map_tool_shape_select'), icon: 'polygon-filter', selected: tool === 'shape' && shapeMode === 'select' },
		{ id: 'filter', label: t(lang, 'map_tool_shape_filter'), icon: 'filter', selected: tool === 'shape' && shapeMode === 'filter' },
		{ id: 'div', kind: 'divider' },
		{ id: 'clear', label: t(lang, 'map_tool_shape_clear'), icon: 'filter-remove', disabled: !shapeFiltered, disabledReason: null },
	]);

	const sensorItems: MenuItemSpec[] = $derived([
		{ id: 'raw', label: t(lang, 'map_flir_off'), selected: sensor === 'raw' },
		{ id: 'flir-whot', label: t(lang, 'map_flir_whot'), selected: sensor === 'flir-whot' },
		{ id: 'flir-bhot', label: t(lang, 'map_flir_bhot'), selected: sensor === 'flir-bhot' },
		{ id: 'flir-iron', label: t(lang, 'map_flir_iron'), selected: sensor === 'flir-iron' },
	]);

	const modeLabel = $derived(
		mode.kind === 'replay' ? t(lang, 'map_mode_replay', mode.runId ?? null) : mode.kind === 'window' ? t(lang, 'map_mode_window') : t(lang, 'map_mode_live'),
	);
	const modeTip = $derived(t(lang, mode.kind === 'replay' ? 'map_mode_replay_tip' : mode.kind === 'window' ? 'map_mode_window_tip' : 'map_mode_live_tip'));

	function pickShape(item: MenuItemSpec) {
		shapeOpen = false;
		if (item.id === 'clear') onclearshape();
		else if (item.id === 'select' || item.id === 'filter') ontool('shape', item.id);
	}

	function pickSensor(item: MenuItemSpec) {
		thermalOpen = false;
		if (item.id === 'raw' || item.id === 'flir-whot' || item.id === 'flir-bhot' || item.id === 'flir-iron') onsensor(item.id);
	}
</script>

<div class="toolbar" role="toolbar" aria-label={t(lang, 'map_toolbar')} data-map="toolbar">
	<div class="group">
		<Button
			minimal
			icon="select"
			class="chip"
			pressed={tool === 'select'}
			tooltip={t(lang, 'map_tool_select')}
			aria-label={t(lang, 'map_tool_select')}
			onclick={() => ontool('select')}
		/>
		<Popover bind:open={shapeOpen} placement="bottom-start" role="menu">
			<Button
				minimal
				icon="polygon-filter"
				class={['chip', shapeFiltered && 'filtered'].filter(Boolean).join(' ')}
				pressed={tool === 'shape'}
				tooltip={tool === 'shape' ? t(lang, 'map_tool_shape_hint') : t(lang, 'map_tool_shape')}
				aria-label={t(lang, 'map_tool_shape')}
			/>
			{#snippet content()}
				<Menu items={shapeItems} label={t(lang, 'map_tool_shape_menu')} autofocus onselect={pickShape} />
			{/snippet}
		</Popover>
		<Button
			minimal
			icon="search-around"
			class="chip"
			disabled={!canSearchAround}
			disabledReason={t(lang, 'map_tool_search_around_none')}
			tooltip={t(lang, 'map_tool_search_around')}
			aria-label={t(lang, 'map_tool_search_around')}
			onclick={onsearcharound}
		/>
		<Button
			minimal
			icon="path"
			class="chip"
			pressed={tool === 'measure'}
			tooltip={tool === 'measure' ? t(lang, 'map_tool_measure_hint') : t(lang, 'map_tool_measure')}
			aria-label={t(lang, 'map_tool_measure')}
			onclick={() => ontool(tool === 'measure' ? 'select' : 'measure')}
		/>
	</div>
	<div class="group">
		<Button
			minimal
			icon="layers"
			class="chip"
			pressed={layersOpen}
			tooltip={t(lang, 'map_tool_layers')}
			aria-label={t(lang, 'map_tool_layers')}
			data-rail={layersRail ? 'layers' : undefined}
			onclick={onlayers}
		/>
		<Button
			minimal
			icon="list"
			class="chip"
			pressed={legendOpen}
			tooltip={t(lang, 'map_tool_legend')}
			aria-label={t(lang, 'map_tool_legend')}
			onclick={onlegend}
		/>
		<!-- FIX-E-LOOKUP: the thermal-style view sits WITH Layers and Legend —
		     the view controls, one click from the layers it restyles. Audit E
		     round 2: ONE Layers + Legend pair — the round-1 diff had left the
		     original group standing beside this one, so every map page showed
		     both twice. -->
		<Popover bind:open={thermalOpen} placement="bottom-start" role="menu">
			<Button
				minimal
				icon="heatmap"
				class="chip"
				pressed={sensor !== 'raw'}
				tooltip={t(lang, 'map_tool_thermal_tip')}
				aria-label={t(lang, 'map_tool_thermal')}
				data-map-tool="thermal"
			/>
			{#snippet content()}
				<div class="thermal">
					<div class="thermal-head">{t(lang, 'map_tool_thermal')}</div>
					<p class="thermal-note">{t(lang, 'map_flir_note')}</p>
					<Menu items={sensorItems} label={t(lang, 'map_tool_thermal')} autofocus onselect={pickSensor} />
				</div>
			{/snippet}
		</Popover>
	</div>
	<div class="group">
		<Button
			minimal
			icon="locate"
			class="chip lock"
			pressed={follow.pressed}
			disabled={follow.disabled && !follow.pressed}
			disabledReason={follow.title}
			title={follow.title}
			aria-label={t(lang, 'map_tool_follow')}
			onclick={onfollow}
		/>
		<Button minimal icon={mode.kind === 'replay' ? 'history' : 'record'} class={`chip mode is-${mode.kind}`} tooltip={modeTip} onclick={onmode}>
			{modeLabel}
		</Button>
		{#if imagery}
			<span class="chip mode imagery" data-map="imagery" title={imagery.title}>{imagery.label}</span>
		{/if}
		<Button
			minimal
			icon={touring ? 'stop' : 'play'}
			class="chip tour"
			pressed={touring}
			tooltip={t(lang, touring ? 'map_tool_tour_stop' : 'map_tool_tour')}
			aria-label={t(lang, 'map_tool_tour')}
			onclick={ontour}
		/>
		{#if showExit}
			<Button minimal icon="minimize" class="chip exit" tooltip={t(lang, 'map_tool_exit')} aria-label={t(lang, 'map_tool_exit')} onclick={onexit} />
		{/if}
	</div>
	{#if sensor !== 'raw'}<span class="thermal-on" data-map-thermal="on">{t(lang, 'map_thermal_on')}</span>{/if}
</div>

<style>
	.toolbar {
		display: flex;
		gap: 6px;
		pointer-events: auto;
		font-family: var(--v-font-ui);
	}

	.group {
		display: inline-flex;
		border-radius: var(--v-radius-btn);
		background: var(--v-surface-1);
		box-shadow: var(--v-elev-1);
	}

	.group :global(.chip) {
		border-radius: 0;
		color: var(--v-ink-1);
	}

	.group > :global(:first-child .chip),
	.group > :global(.chip:first-child) {
		border-radius: var(--v-radius-btn) 0 0 var(--v-radius-btn);
	}

	.group > :global(:last-child .chip),
	.group > :global(.chip:last-child) {
		border-radius: 0 var(--v-radius-btn) var(--v-radius-btn) 0;
	}

	.toolbar :global(.chip.mode) {
		padding: 0 10px 0 8px;
		gap: 6px;
	}

	/* the imagery label: a quiet, non-interactive chip in the group (what the picture is, never a sensor) */
	.imagery {
		display: inline-flex;
		align-items: center;
		height: var(--v-ctl-md);
		padding: 0 10px;
		color: var(--v-ink-2);
		font-size: var(--v-text-xs);
		white-space: nowrap;
		border-left: 1px solid var(--v-line-1);
	}

	.toolbar :global(.chip.filtered) {
		box-shadow: inset 0 -2px 0 var(--v-primary-text);
	}

	/* the honest on-map label while a thermal mode is on (the canvas's own
	   chip pattern: label background, one elevation, clicks pass through) */
	.thermal-on {
		align-self: center;
		max-width: min(48ch, 100%);
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		padding: 3px 8px;
		border-radius: var(--v-radius-chip);
		background: var(--v-map-label-bg);
		box-shadow: var(--v-elev-1);
		color: var(--v-ink-1);
		font-size: var(--v-text-xs);
		line-height: 16px;
		pointer-events: none;
	}

	.thermal {
		font-family: var(--v-font-ui);
	}

	.thermal-head {
		padding: 8px 12px 0;
		font-size: var(--v-text-base);
		font-weight: 600;
		color: var(--v-ink-1);
	}

	.thermal-note {
		margin: 4px 12px 8px;
		font-size: var(--v-text-xs);
		line-height: 16px;
		color: var(--v-ink-2);
	}
</style>
