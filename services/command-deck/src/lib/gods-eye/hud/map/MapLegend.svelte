<script lang="ts">
	/**
	 * MapLegend — the map's key (SPEC §5.3; prototype legendHTML): the
	 * neutral flow ramp (free → jammed by brightness and width), then the
	 * markers: colour is state only — the watchlisted vehicle (red ring), a
	 * waiting decision (orange dot), the selection (blue ring), every other
	 * object neutral with its type glyph, co-located markers (a count chip),
	 * the convoy and its route (turquoise), corridor events (violet).
	 */
	import type { HTMLAttributes } from 'svelte/elements';
	import { t } from '$lib/i18n/strings';
	import '$lib/i18n/packs.map';
	import Button from '$lib/ui/Button.svelte';

	interface Props extends HTMLAttributes<HTMLDivElement> {
		lang?: string;
		/** The flow layer's rows are simulated (the ramp's caption says so). */
		simulated?: boolean;
		onclose?: () => void;
	}

	let { lang = 'en', simulated = false, onclose, class: cls = '', ...rest }: Props = $props();

	const WIDTHS = [1.5, 2, 2.5, 3.5, 4.5];
</script>

{#snippet disc(stroke: string, width = 1.5)}
	<svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
		<circle cx="8" cy="8" r="6" fill="var(--v-map-marker-fill)" stroke={stroke} stroke-width={width} />
	</svg>
{/snippet}

<div data-map="legend" role="dialog" aria-label={t(lang, 'map_legend_title')} class={['legend', cls]} {...rest}>
	<div class="head">
		<span class="title">{t(lang, 'map_legend_title')}</span>
		{#if onclose}
			<Button minimal small icon="small-cross" tooltip={t(lang, 'map_legend_close')} aria-label={t(lang, 'map_legend_close')} onclick={onclose} />
		{/if}
	</div>
	<div class="sub">{t(lang, simulated ? 'map_legend_flow_simulated' : 'map_legend_flow')}</div>
	<svg class="ramp" width="208" height="14" viewBox="0 0 208 14" aria-hidden="true">
		{#each WIDTHS as w, i (i)}
			<path
				d={`M${i * 42 + 2},7 L${(i + 1) * 42 - 4},7`}
				stroke={`var(--v-flow-${i + 1})`}
				stroke-width={w}
				stroke-linecap="round"
				opacity={i === 0 ? 0.6 : 1}
			/>
		{/each}
	</svg>
	<div class="sub">{t(lang, 'map_legend_markers')}</div>
	<div class="row">{@render disc('var(--v-map-alert)', 2.5)}<span>{t(lang, 'map_legend_alert')}</span></div>
	<div class="row">
		<svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="5" fill="var(--v-map-decision)" /></svg>
		<span>{t(lang, 'map_legend_decision')}</span>
	</div>
	<div class="row">{@render disc('var(--v-map-select)', 2.5)}<span>{t(lang, 'map_legend_selected')}</span></div>
	<div class="row">{@render disc('var(--v-map-marker)')}<span>{t(lang, 'map_legend_neutral')}</span></div>
	<div class="row">
		<svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
			<circle cx="8" cy="8" r="7" fill="var(--v-surface-4)" />
			<text x="8" y="11.9" text-anchor="middle" font-size="11" font-weight="600" fill="var(--v-map-label-ink)">2</text>
		</svg>
		<span>{t(lang, 'map_legend_cluster')}</span>
	</div>
	<div class="row">{@render disc('var(--v-map-route)', 2.5)}<span>{t(lang, 'map_legend_route')}</span></div>
	<div class="row">{@render disc('var(--v-map-event)', 2.5)}<span>{t(lang, 'map_legend_event')}</span></div>
</div>

<style>
	.legend {
		width: 256px;
		padding: 8px 12px 10px;
		border-radius: var(--v-radius-panel);
		background: var(--v-surface-1);
		box-shadow: var(--v-elev-2);
		font-family: var(--v-font-ui);
		font-size: var(--v-text-xs);
		color: var(--v-ink-1);
	}

	.head {
		display: flex;
		align-items: center;
		justify-content: space-between;
		min-height: 24px;
	}

	.title {
		font-weight: 600;
	}

	.sub {
		margin: 6px 0 2px;
		color: var(--v-ink-2);
	}

	.ramp {
		display: block;
	}

	.row {
		display: flex;
		align-items: center;
		gap: 8px;
		min-height: 22px;
		padding: 2px 0;
		line-height: 16px;
	}

	.row svg {
		flex: 0 0 auto;
	}

	text {
		font-family: var(--v-font-ui);
	}
</style>
