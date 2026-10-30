<script lang="ts">
	/**
	 * A road's next two hours (PLAN §2.4 A) on its object page: the corridor forecast's V/C every 15 minutes with the
	 * p10–p90 band, the seasonal baseline, the 0.8 "heavy" line and the moment the median crosses it, from the
	 * on-premises forecast service (Chronos-2). Labelled SIMULATED while the history it learns from is simulated (the
	 * service's own data label), with its note. A pre-emptive proposal, when there is one, is shown as words: it waits
	 * for an officer on Decide; nothing here acts.
	 */
	import { onMount } from 'svelte';
	import { t } from '$lib/i18n/strings';
	import Glyph from '../Glyph.svelte';
	import '../field/packs.field';
	import { FieldApiError, fetchSegmentForecast } from '../field/api';
	import { forecastChart, type SegmentForecast } from '../field/model';
	import { fx } from '../field/reads';
	import Panel from './Panel.svelte';

	let { segmentId, lang }: { segmentId: number; lang: string } = $props();
	const L = (key: string, ...args: unknown[]) => t(lang, key, ...args);

	let fc = $state<SegmentForecast | null>(null);
	let phase = $state<'loading' | 'ready' | 'none' | 'down'>('loading');

	onMount(() => {
		const ctl = new AbortController();
		fetchSegmentForecast(segmentId, ctl.signal)
			.then((f) => {
				fc = f;
				phase = 'ready';
			})
			.catch((err) => {
				if (ctl.signal.aborted) return;
				phase = err instanceof FieldApiError && (err.status === 404 || err.status === 409) ? 'none' : 'down';
			});
		return () => ctl.abort();
	});

	const chart = $derived(fc ? forecastChart(fc, 680, 200) : null);
	const last = $derived(fc?.steps.at(-1) ?? null);
	const simulated = $derived(fc ? fc.dataLabel.toUpperCase().startsWith('SIMULATED') : false);
</script>

<Panel title={L('fld_fc_title')} testid="obj-forecast" data-state={phase} data-label={fc?.dataLabel ?? ''}>
	{#if phase === 'ready' && fc && chart}
		<div class="top">
			<div class="lead">
				<b class="big fig">{fx(fc.nowVc)}</b>
				<span class="sub">{L('fld_fc_vc')} · {L('fld_fc_now')}</span>
			</div>
			<div class="verdict" data-crossing={fc.crossing ? fc.crossing.inMin : ''}>
				{#if fc.crossing}
					<span class="pill warn"><Glyph name="clock" size={16} />{L('fld_fc_cross', fc.crossing.inMin)}</span>
				{:else if fc.aboveNow}
					<span class="pill warn"><Glyph name="alert" size={16} />{L('fld_fc_above')}</span>
				{:else}
					<span class="pill"><Glyph name="checkc" size={16} />{L('fld_fc_below')}</span>
				{/if}
			</div>
			<div class="tags">
				{#if simulated}<span class="tag" data-label="SIMULATED"><Glyph name="shuffle" size={14} />{L('fld_tag_simulated')}</span>{/if}
				{#if fc.model}<span class="tag solid">{L('fld_fc_model', fc.model)}</span>{/if}
			</div>
		</div>

		<svg class="chart" viewBox={`0 0 ${chart.w} ${chart.h}`} role="img" aria-label={L('fld_fc_chart', fc.roadName)}>
			{#each chart.yTicks as yt (yt.v)}
				<line class="grid" x1={chart.pad.l} x2={chart.w - chart.pad.r} y1={yt.y} y2={yt.y} />
				<text class="ax" x={chart.pad.l - 8} y={yt.y + 4} text-anchor="end">{yt.v.toFixed(1)}</text>
			{/each}
			{#each chart.ticks as tk (tk.min)}
				<text class="ax" x={tk.x} y={chart.h - 6} text-anchor="middle">{tk.min === 0 ? L('fld_fc_now') : `+${tk.min}`}</text>
			{/each}
			<line class="thr" x1={chart.pad.l} x2={chart.w - chart.pad.r} y1={chart.thresholdY} y2={chart.thresholdY} />
			<path class="band" d={chart.band} />
			{#if chart.baseline}<path class="base" d={chart.baseline} />{/if}
			<path class="med" d={chart.median} pathLength="1" />
			{#if chart.nowPt}<circle class="now" cx={chart.nowPt.x} cy={chart.nowPt.y} r="5" />{/if}
			{#if chart.crossPt}
				<line class="cross-l" x1={chart.crossPt.x} x2={chart.crossPt.x} y1={chart.pad.t} y2={chart.h - chart.pad.b} />
				<circle class="cross" cx={chart.crossPt.x} cy={chart.crossPt.y} r="6" />
			{/if}
		</svg>

		<div class="legend">
			<span><i class="sw band-sw"></i>{L('fld_fc_band')}</span>
			<span><i class="sw med-sw"></i>{L('fld_fc_median')}</span>
			{#if chart.baseline}<span><i class="sw base-sw"></i>{L('fld_fc_baseline')}</span>{/if}
			<span><i class="sw thr-sw"></i>{L('fld_fc_threshold')}</span>
		</div>

		{#if last}
			<p class="sum fig">
				{L('fld_fc_summary', fx(fc.nowVc), fx(last.p50), fx(last.p10), fx(last.p90))}{#if fc.nowSpeed !== null}{' · '}{L('fld_fc_speed', Math.round(fc.nowSpeed))}{/if}
			</p>
		{/if}
		{#if fc.proposal}
			<div class="prop" data-testid="obj-forecast-proposal">
				<span class="pk"><Glyph name="spark" size={16} />{L('fld_fc_proposal')}</span>
				<p lang="en">{fc.proposal.summary}</p>
			</div>
		{/if}
		{#if simulated}<p class="note"><Glyph name="info" size={16} />{L('fld_fc_note')}</p>{/if}
	{:else if phase === 'loading'}
		<div class="skel" aria-busy="true"><i></i><i></i><i></i></div>
	{:else}
		<p class="quiet">{phase === 'none' ? L('fld_fc_none') : L('fld_fc_down')}</p>
	{/if}
</Panel>

<style>
	.top {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 14px 20px;
	}

	.lead {
		display: flex;
		flex-direction: column;
	}

	.big {
		font-size: var(--v3-text-stat);
		line-height: var(--v3-lh-stat);
		font-weight: 700;
	}

	.sub,
	.quiet {
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
	}

	.quiet {
		margin: 0;
		font-size: 14px;
	}

	.fig {
		font-variant-numeric: tabular-nums;
	}

	.verdict {
		flex: 1;
	}

	.pill {
		display: inline-flex;
		align-items: center;
		gap: 8px;
		height: 32px;
		padding: 0 14px;
		border-radius: 16px;
		background: var(--v3-s3);
		color: var(--v3-t1);
		font-size: 14px;
		font-weight: 650;
	}

	.pill.warn {
		background: var(--v3-ai-veil);
		color: var(--v3-ai-text);
	}

	.tags {
		display: flex;
		gap: 8px;
	}

	.tag {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		height: 26px;
		padding: 0 10px;
		border: 1px dashed var(--v3-dashed);
		border-radius: 13px;
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
		font-weight: 650;
		white-space: nowrap;
	}

	.tag.solid {
		border-style: solid;
		border-color: var(--v3-line-2);
	}

	.chart {
		display: block;
		width: 100%;
		height: auto;
		overflow: visible;
	}

	.grid {
		stroke: var(--v3-line-1);
		stroke-width: 1;
	}

	.ax {
		fill: var(--v3-t3);
		font-size: 12px;
	}

	.thr {
		stroke: var(--v3-t2);
		stroke-width: 1.2;
		stroke-dasharray: 5 5;
	}


	.band {
		fill: var(--v3-brand-veil);
		stroke: none;
		animation: fade var(--v3-dur-3) var(--v3-ease);
	}

	.base {
		fill: none;
		stroke: var(--v3-t3);
		stroke-width: 1.5;
		stroke-dasharray: 2 4;
		stroke-linecap: round;
	}

	.med {
		fill: none;
		stroke: var(--v3-brand);
		stroke-width: 2.6;
		stroke-linejoin: round;
		stroke-linecap: round;
		stroke-dasharray: 1;
		animation: draw 0.9s var(--v3-ease) both;
	}

	@keyframes draw {
		from {
			stroke-dashoffset: 1;
		}
		to {
			stroke-dashoffset: 0;
		}
	}

	@keyframes fade {
		from {
			opacity: 0;
		}
	}

	.now {
		fill: var(--v3-t1);
		stroke: var(--v3-bg);
		stroke-width: 2;
	}

	.cross {
		fill: var(--v3-ai);
		stroke: var(--v3-bg);
		stroke-width: 2;
	}

	.cross-l {
		stroke: var(--v3-ai);
		stroke-width: 1;
		stroke-dasharray: 3 3;
		opacity: 0.7;
	}

	.legend {
		display: flex;
		flex-wrap: wrap;
		gap: 6px 18px;
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
	}

	.legend span {
		display: inline-flex;
		align-items: center;
		gap: 8px;
	}

	.sw {
		display: inline-block;
		width: 18px;
		height: 10px;
		border-radius: 3px;
	}

	.band-sw {
		background: var(--v3-brand-veil);
	}

	.med-sw {
		height: 3px;
		background: var(--v3-brand);
	}

	.base-sw {
		height: 0;
		border-top: 2px dotted var(--v3-t3);
	}

	.thr-sw {
		height: 0;
		border-top: 2px dashed var(--v3-t2);
	}

	.sum {
		margin: 0;
		color: var(--v3-t1);
		font-size: 14px;
	}

	.prop {
		padding: 12px 14px;
		border: 1px solid var(--v3-line-2);
		border-radius: var(--v3-radius-m);
		background: var(--v3-s2);
	}

	.pk {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		color: var(--v3-ai-text);
		font-size: var(--v3-text-meta);
		font-weight: 700;
	}

	.prop p {
		margin: 6px 0 0;
		font-size: 14px;
		line-height: 20px;
	}

	.note {
		display: flex;
		align-items: flex-start;
		gap: 8px;
		margin: 0;
		color: var(--v3-t3);
		font-size: var(--v3-text-meta);
		line-height: var(--v3-lh-meta);
	}

	.note :global(.v3-glyph) {
		flex: none;
		margin-top: 1px;
	}

	.skel {
		display: flex;
		flex-direction: column;
		gap: 10px;
	}

	.skel i {
		display: block;
		height: 18px;
		border-radius: 6px;
		background: var(--v3-s2);
		animation: pulse 1.2s ease-in-out infinite;
	}

	.skel i:nth-child(2) {
		height: 150px;
	}

	@keyframes pulse {
		50% {
			opacity: 0.5;
		}
	}

	@media (prefers-reduced-motion: reduce) {
		.med,
		.band,
		.skel i {
			animation: none;
		}
	}
</style>
