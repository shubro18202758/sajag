<script lang="ts">
	/**
	 * MapTools (V3-SPEC §5.6, §6.5, §6.10) — the map's tools, bottom right, one column: satellite 3D city (a one-tap switch to the city map and back), the
	 * thermal-style view (on the MAIN toolbar by user decision; its tooltip says what it is — a visual filter, no
	 * thermal sensor — and it is pressed while on), measure, follow, zoom in / out, north up. At 1366 px follow and
	 * north step back (the selection card keeps Follow). Every button drives the canvas's own tool through
	 * mapChrome.act; nothing here moves the camera itself.
	 */
	import { t } from '$lib/i18n/strings';
	import '$lib/i18n/packs.map';
	import Glyph from '../Glyph.svelte';
	import './packs.map3';

	let {
		is3d,
		can3d,
		why3d,
		sensor,
		tool,
		follow,
		heading,
		statsOpen,
		legendOpen,
		lang,
		on3d,
		onstats,
		onlegend,
		onthermal,
		onmeasure,
		onfollow,
		onzoom,
		onnorth,
	}: {
		is3d: boolean;
		can3d: boolean;
		/** Why the 3D city is not available here (the key it needs). */
		why3d: string;
		sensor: string;
		tool: string;
		follow: { pressed: boolean; disabled: boolean; title: string } | null;
		heading: number;
		/** The corridor stats panel and the legend (review items 2 and 3: closed / shown by the officer). */
		statsOpen: boolean;
		legendOpen: boolean;
		lang: string;
		on3d: () => void;
		onstats: () => void;
		onlegend: () => void;
		onthermal: () => void;
		onmeasure: () => void;
		onfollow: () => void;
		onzoom: (sign: 1 | -1) => void;
		onnorth: () => void;
	} = $props();

	const thermalOn = $derived(sensor !== 'raw');
</script>

<div class="tools" role="toolbar" aria-orientation="vertical" aria-label={t(lang, 'v3m_tools')} data-testid="v3-map-tools" data-ge-keepout>
	<button
		type="button"
		class={['tb', 'v3-glass', is3d && 'is-pressed']}
		aria-pressed={is3d}
		aria-disabled={!can3d && !is3d ? 'true' : undefined}
		title={!can3d && !is3d ? why3d : t(lang, is3d ? 'v3m_3d_off' : 'v3m_3d_on')}
		aria-label={t(lang, 'v3m_3d')}
		data-map-tool="3d"
		onclick={() => {
			if (can3d || is3d) on3d();
		}}><Glyph name="cube" size={20} /></button
	>
	<button
		type="button"
		class={['tb', 'v3-glass', thermalOn && 'is-pressed']}
		aria-pressed={thermalOn}
		title={t(lang, 'map_tool_thermal_tip')}
		aria-label={t(lang, 'map_tool_thermal')}
		data-map-tool="thermal"
		onclick={onthermal}><Glyph name="thermal" size={20} /></button
	>
	<button
		type="button"
		class={['tb', 'v3-glass', statsOpen && 'is-pressed']}
		aria-pressed={statsOpen}
		aria-controls="v3-stats-panel"
		title={t(lang, 'v3m_stats')}
		aria-label={t(lang, 'v3m_stats')}
		data-map-tool="stats"
		onclick={onstats}><Glyph name="graph" size={20} /></button
	>
	<button
		type="button"
		class={['tb', 'v3-glass', legendOpen && 'is-pressed']}
		aria-pressed={legendOpen}
		title={t(lang, 'map_tool_legend')}
		aria-label={t(lang, 'map_tool_legend')}
		data-map-tool="legend"
		onclick={onlegend}><Glyph name="info" size={20} /></button
	>
	<button
		type="button"
		class={['tb', 'v3-glass', tool === 'measure' && 'is-pressed']}
		aria-pressed={tool === 'measure'}
		title={t(lang, 'map_tool_measure')}
		aria-label={t(lang, 'map_tool_measure')}
		data-map-tool="measure"
		onclick={onmeasure}><Glyph name="ruler" size={20} /></button
	>
	{#if follow}
		<button
			type="button"
			class={['tb', 'v3-glass', 'wide-only', follow.pressed && 'is-pressed']}
			aria-pressed={follow.pressed}
			aria-disabled={follow.disabled ? 'true' : undefined}
			title={follow.title}
			aria-label={t(lang, 'map_tool_follow')}
			data-map-tool="follow"
			onclick={() => {
				if (!follow.disabled) onfollow();
			}}><Glyph name="target" size={20} /></button
		>
	{/if}
	<div class="grp v3-glass">
		<button type="button" class="tb" title={t(lang, 'map_zoom_in')} aria-label={t(lang, 'map_zoom_in')} data-map-tool="zoom-in" onclick={() => onzoom(1)}><Glyph name="plus" size={20} /></button>
		<button type="button" class="tb" title={t(lang, 'map_zoom_out')} aria-label={t(lang, 'map_zoom_out')} data-map-tool="zoom-out" onclick={() => onzoom(-1)}
			><svg class="minus" viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" focusable="false"><path d="M5 12h14" /></svg></button
		>
	</div>
	<button type="button" class="tb v3-glass wide-only" title={t(lang, 'map_reset_north')} aria-label={t(lang, 'map_reset_north')} data-map-tool="north" onclick={onnorth}
		><span class="compass" style:transform={`rotate(${-heading}deg)`}><Glyph name="compass" size={20} /></span></button
	>
</div>

<style>
	.tools {
		display: flex;
		flex-direction: column;
		gap: 8px;
		pointer-events: auto;
	}

	.tb {
		display: grid;
		place-items: center;
		width: 46px;
		height: 46px;
		border: 1px solid var(--v3-glass-border);
		border-radius: 14px;
		background: var(--v3-glass-surface);
		box-shadow: var(--v3-elev-1);
		color: var(--v3-t1);
		cursor: pointer;
		transition: background var(--v3-dur-1), color var(--v3-dur-1);
	}

	.tb:hover {
		background: var(--v3-s3);
	}

	.tb:focus-visible {
		outline: 2px solid var(--v3-brand);
		outline-offset: 2px;
	}

	.tb.is-pressed {
		background: var(--v3-primary-bg);
		color: var(--v3-primary-ink);
	}

	.tb[aria-disabled='true'] {
		color: var(--v3-t3);
		cursor: not-allowed;
	}

	.grp {
		display: flex;
		flex-direction: column;
		overflow: hidden;
		border: 1px solid var(--v3-glass-border);
		border-radius: 14px;
		box-shadow: var(--v3-elev-1);
	}

	.grp {
		background: var(--v3-glass-surface);
	}

	.grp .tb {
		border: 0;
		border-radius: 0;
		box-shadow: none;
		background: none;
	}

	.grp .tb:hover {
		background: var(--v3-s3);
	}

	.grp .tb + .tb {
		border-top: 1px solid var(--v3-line-2);
	}

	.minus {
		fill: none;
		stroke: currentColor;
		stroke-width: 1.8;
		stroke-linecap: round;
	}

	.compass {
		display: grid;
		place-items: center;
		transition: transform var(--v3-dur-2) var(--v3-ease);
	}

	@media (max-width: 1500px) {
		.tools {
			gap: 6px;
		}

		.tb {
			width: 42px;
			height: 42px;
		}

		.wide-only {
			display: none;
		}
	}

	@media (prefers-reduced-motion: reduce) {
		.tb,
		.compass {
			transition: none;
		}
	}
</style>
