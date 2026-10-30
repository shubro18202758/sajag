<script lang="ts">
	/**
	 * BandHistoryChart (SPEC §5.3, §6.3) — the band as a step chart on the
	 * ladder Black / Red / Amber / Green, with a real IST time axis across the
	 * chosen range. Geometry from band-chart.ts (pure, unit-tested): a reading
	 * holds until the next one, nothing is drawn before the first reading,
	 * and BLACK is a translucent fill with a 1 px hairline in the band's red.
	 * The chart fits its container's width.
	 */
	import { t } from '$lib/i18n/strings';
	import '$lib/i18n/packs';
	import '$lib/i18n/packs.wall';
	import type { BandCode } from '$lib/ops/types';
	import { bandChart, type BandReading } from './band-chart';

	interface Props {
		readings: readonly BandReading[];
		window: readonly [number, number];
		current?: { band: BandCode; since: number | null } | null;
		lang: string;
		/** What the series speaks for, for the chart's accessible name. */
		scope: string;
	}

	let { readings, window, current = null, lang, scope }: Props = $props();

	let width = $state(400);
	const model = $derived(bandChart(readings, window, { width, current }));
	const label = $derived(t(lang, 'wall_band_chart_label', scope));
</script>

<div class="chart" bind:clientWidth={width} data-wall="band-chart" data-empty={model.empty ? 'true' : 'false'}>
	<svg width={model.width} height={model.height} viewBox="0 0 {model.width} {model.height}" role="img" aria-label={label}>
		{#each model.rows as r (r.band)}
			<text class="row-label" x="0" y={r.y + 4}>{t(lang, `shell_band_word_${r.band}`)}</text>
			<line class="grid" x1={model.plot.x0} x2={model.plot.x1} y1={r.y} y2={r.y} />
		{/each}
		{#each model.ticks as tk (tk.t)}
			<line class="tick" x1={tk.x} x2={tk.x} y1={model.plot.top} y2={model.plot.bottom} />
			<text class="tick-label" x={tk.x} y={model.height - 2} text-anchor="middle">{tk.label}</text>
		{/each}
		{#each model.joins as j, i (i)}
			<line class="join" x1={j.x} x2={j.x} y1={j.y0} y2={j.y1} />
		{/each}
		{#each model.segments as s (s.t0)}
			<rect
				class="seg"
				data-band={s.band}
				x={s.x}
				y={s.y}
				width={s.w}
				height={s.h}
				rx="2"
				fill={s.fill}
				stroke={s.stroke ?? 'none'}
				stroke-width={s.stroke ? 1 : 0}
			/>
		{/each}
		{#if model.empty}
			<text class="empty" x={(model.plot.x0 + model.plot.x1) / 2} y={model.plot.bottom / 2 + 4} text-anchor="middle">{t(lang, 'wall_band_no_history')}</text>
		{/if}
	</svg>
</div>

<style>
	.chart {
		width: 100%;
		min-width: 0;
		overflow: hidden;
	}

	svg {
		display: block;
		font-family: var(--v-font-ui);
	}

	.row-label,
	.tick-label,
	.empty {
		fill: var(--v-ink-2);
		font-size: 12px;
		font-variant-numeric: tabular-nums;
	}

	.grid {
		stroke: var(--v-line-1);
		stroke-width: 1;
	}

	.tick {
		stroke: var(--v-line-1);
		stroke-width: 1;
		stroke-dasharray: 2 3;
	}

	.join {
		stroke: var(--v-line-strong);
		stroke-width: 1;
	}
</style>
