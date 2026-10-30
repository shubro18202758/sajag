<script lang="ts">
	/**
	 * NextHours — Home's compact "Next 2 hours" (under the city pulse): the top forecast crossings of 0.8 V/C (the
	 * forecast's own labels: Simulated history, Modelled), the roads at waterlogging risk (Modelled), the tide and the
	 * outfall gates (Modelled), and the signal-timing proposals waiting (the twin) — each line links to where it is
	 * worked (Decide, the map). Under it, "Replay 19 Aug 2025" opens the replay sheet. A service that does not answer
	 * says so in one neutral line; decisions still work.
	 *
	 * Simple on the surface, deep underneath: one plain sentence per line and ONE honesty tag for the group (every line
	 * here is a model's output: Modelled). "How these are made" opens the depth — each line's own labels (the forecast's
	 * Simulated history among them) and the forecast's per-road V/C — so no label is lost, only put one level down.
	 */
	import { onMount } from 'svelte';
	import { t } from '$lib/i18n/strings';
	import { fmtTime } from '$lib/ui/format/format';
	import Glyph from '$lib/v3/Glyph.svelte';
	import ProvTag from './ProvTag.svelte';
	import type { Component } from 'svelte';
	import { ai } from '../ai.svelte';
	import { nextHours } from '../model';
	import { provList } from '../labels';
	import '../packs.ai';

	let { lang }: { lang: string } = $props();

	let now = $state(Date.now());
	$effect(() => {
		const id = setInterval(() => (now = Date.now()), 30_000);
		return () => clearInterval(id);
	});

	const L = (key: string, ...a: unknown[]) => t(lang, key, ...a);
	const twinWaiting = $derived(ai.feeds.twin.status === 'ok' ? ai.cards.filter((c) => c.source === 'twin').length : null);
	const nh = $derived(nextHours({ forecast: ai.forecast, nowcast: ai.nowcast, tide: ai.tide, twinWaiting, now }));
	const fcProvs = $derived(provList(['MODELLED', ...nh.forecastLabels]));
	const down = $derived((['forecast', 'hydro', 'tide'] as const).every((n) => ai.feeds[n].status === 'down' || ai.feeds[n].status === 'not-deployed'));
	const atRisk = $derived(nh.risk ? nh.risk.shallow + nh.risk.deep + nh.risk.impassable : null);
	/** The city's Marathi place names (the hydro network carries them) for a Marathi reader. */
	const placeMr = $derived(new Map((ai.nowcast?.segments ?? []).filter((x) => x.place_mr).map((x) => [x.segment_id, x.place_mr as string])));
	const placeOf = (c: { place: string; segmentId: number | null }) => (lang === 'mr' && c.segmentId != null ? (placeMr.get(c.segmentId) ?? c.place) : c.place);

	let replayOpen = $state(false);
	let replayBusy = $state(false);
	/** The replay sheet loads on first open (never in Home's first paint). */
	let ReplaySheet = $state<Component<Record<string, unknown>> | null>(null);
	async function openReplay() {
		if (!ReplaySheet) ReplaySheet = (await import('./ReplaySheet.svelte')).default as unknown as Component<Record<string, unknown>>;
		replayOpen = true;
		replayBusy = true;
		await ai.loadReplay();
		replayBusy = false;
	}

	onMount(() => ai.use('forecast', 'hydro', 'tide', 'twin'));
</script>

<svelte:window
	onkeydown={(e) => {
		if (replayOpen && e.key === 'Escape') replayOpen = false;
	}}
/>

<section class="nh" aria-label={L('ai_h_aria')} data-testid="ai-next-hours">
	<div class="head">
		<h3><span class="spark" title={L('ai_tag')}><Glyph name="spark" size={16} /></span>{L('ai_h_title')}</h3>
		<ProvTag prov="modelled" {lang} />
	</div>
	{#if down}
		<p class="down" role="status">{L('ai_h_down')}</p>
	{:else}
		<ul class="lines">
			<li data-line="forecast">
				<span class="ic"><Glyph name="graph" size={16} /></span>
				<span class="tx">
					{#if nh.crossingCount == null}<span class="dim">{L('ai_fc_loading')}</span>
					{:else if nh.crossingCount}<a href="/decide">{L('ai_h_cross', nh.crossingCount)}</a>{#if nh.crossings.length}<span class="dim"> · {nh.crossings.map((c) => placeOf(c)).join(', ')}</span>{/if}
					{:else}{L('ai_h_cross_none')}{/if}
				</span>
			</li>
			<li data-line="waterlog">
				<span class="ic"><Glyph name="wave" size={16} /></span>
				<span class="tx">
					{#if atRisk == null}<span class="dim">{L('ai_fc_loading')}</span>{:else if atRisk}<a href="/map"><span class="sw" aria-hidden="true"></span>{L('ai_h_risk', atRisk)}</a>{:else}{L('ai_h_risk_none')}{/if}
				</span>
			</li>
			<li data-line="tide">
				<span class="ic"><Glyph name="timeline" size={16} /></span>
				<span class="tx">
					{#if nh.tide}
						{L('ai_h_tide', nh.tide.level.toFixed(2), L(nh.tide.rising ? 'ai_rt_rising' : 'ai_rt_falling'))} · {L(nh.tide.gateClosed ? 'ai_rt_gates_shut' : 'ai_rt_gates_open')}
						{#if nh.tide.nextHigh}<span class="dim"> · {L('ai_rt_high', fmtTime(nh.tide.nextHigh.at), nh.tide.nextHigh.level.toFixed(2))}</span>{/if}
					{:else}<span class="dim">{L('ai_fc_loading')}</span>{/if}
				</span>
			</li>
			<li data-line="twin">
				<span class="ic"><Glyph name="signal" size={16} /></span>
				<span class="tx">
					{#if nh.twinWaiting == null}<span class="dim">{L('ai_fc_loading')}</span>{:else if nh.twinWaiting}<a href="/decide">{L('ai_h_twin', nh.twinWaiting)}</a>{:else}{L('ai_h_twin_none')}{/if}
				</span>
			</li>
		</ul>
		<!-- depth on demand: every line's own labels and the forecast's per-road figures -->
		<details class="how" data-testid="ai-next-hours-how">
			<summary>{L('ai_h_how')}<Glyph name="chevD" size={14} /></summary>
			<dl>
				<dt>{L('ai_h_how_forecast')}</dt>
				<dd>
					<span class="pv">{#each fcProvs as p (p)}<ProvTag prov={p} {lang} />{/each}</span>
					{#if nh.crossings.length}
						<span class="rows">{#each nh.crossings as c, i (i)}<span><b>{placeOf(c)}</b> {c.inMin != null && c.vc != null ? L('ai_h_cross_row', c.inMin, c.vc.toFixed(2)) : ''}</span>{/each}</span>
					{/if}
				</dd>
				<dt>{L('ai_h_how_water')}</dt>
				<dd><span class="pv"><ProvTag prov="modelled" {lang} /></span></dd>
				<dt>{L('ai_h_how_tide')}</dt>
				<dd><span class="pv"><ProvTag prov="modelled" {lang} /></span></dd>
				<dt>{L('ai_h_how_twin')}</dt>
				<dd><span class="pv"><ProvTag prov="modelled" {lang} /></span></dd>
			</dl>
		</details>
	{/if}
	<button type="button" class="replay" data-testid="ai-replay-open" onclick={() => void openReplay()}>
		<span class="r-ic"><Glyph name="history" size={18} /></span>
		<span class="r-tx"><b>{L('ai_h_replay')}</b><span>{L('ai_h_replay_sub')}</span></span>
		<Glyph name="chevR" size={16} />
	</button>
</section>

{#if replayOpen && ReplaySheet}
	<ReplaySheet replay={ai.replay} loading={replayBusy} failed={!replayBusy && !ai.replay && ai.replayState.status !== 'idle'} {lang} onclose={() => (replayOpen = false)} onretry={() => void openReplay()} />
{/if}

<style>
	.nh {
		display: flex;
		flex-direction: column;
		gap: 12px;
		padding: 16px 18px;
		border: 1px solid var(--v3-line-1);
		border-radius: var(--v3-radius-l);
		background: var(--v3-s2);
	}

	.head {
		display: flex;
		align-items: center;
		justify-content: space-between;
	}

	h3 {
		display: inline-flex;
		align-items: center;
		gap: 8px;
		margin: 0;
		font-size: var(--v3-text-body);
		font-weight: 650;
		color: var(--v3-t1);
	}

	.spark {
		display: inline-flex;
		color: var(--v3-ai-text);
	}

	.lines {
		display: flex;
		flex-direction: column;
		gap: 8px;
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.lines li {
		display: grid;
		grid-template-columns: 18px minmax(0, 1fr);
		align-items: start;
		gap: 10px;
		font-size: var(--v3-text-meta);
		line-height: var(--v3-lh-meta);
		color: var(--v3-t1);
		font-variant-numeric: tabular-nums;
	}

	.ic {
		display: inline-flex;
		padding-top: 2px;
		color: var(--v3-t3);
	}

	.tx {
		min-width: 0;
	}

	.tx a {
		color: var(--v3-t1);
		font-weight: 650;
		text-decoration: none;
	}

	.tx a:hover {
		text-decoration: underline;
	}

	.dim {
		color: var(--v3-t3);
	}

	.how {
		color: var(--v3-t3);
		font-size: var(--v3-text-micro);
		line-height: var(--v3-lh-micro);
	}

	.how summary {
		display: inline-flex;
		align-items: center;
		gap: 4px;
		min-height: 24px;
		color: var(--v3-t2);
		font-weight: 600;
		list-style: none;
		cursor: pointer;
	}

	.how summary::-webkit-details-marker {
		display: none;
	}

	.how summary :global(.v3-glyph) {
		transition: transform var(--v3-dur-2) var(--v3-ease);
	}

	.how[open] summary :global(.v3-glyph) {
		transform: rotate(180deg);
	}

	.how summary:hover {
		color: var(--v3-t1);
	}

	.how summary:focus-visible {
		outline: 2px solid var(--v3-brand);
		outline-offset: 2px;
		border-radius: 4px;
	}

	.how dl {
		display: grid;
		grid-template-columns: auto minmax(0, 1fr);
		gap: 8px 12px;
		margin: 8px 0 0;
	}

	.how dt {
		color: var(--v3-t2);
	}

	.how dd {
		display: flex;
		flex-direction: column;
		gap: 4px;
		margin: 0;
	}

	.how .rows {
		display: flex;
		flex-direction: column;
		font-variant-numeric: tabular-nums;
	}

	.how .rows b {
		color: var(--v3-t1);
		font-weight: 600;
	}

	.pv {
		display: inline-flex;
		flex-wrap: wrap;
		gap: 4px;
	}

	.sw {
		display: inline-block;
		width: 14px;
		height: 4px;
		margin-right: 6px;
		vertical-align: middle;
		border-radius: 2px;
		background: var(--v-map-water);
	}

	.down {
		margin: 0;
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
	}

	.replay {
		display: flex;
		align-items: center;
		gap: 12px;
		width: 100%;
		padding: 10px 12px;
		border: 1px solid var(--v3-line-2);
		border-radius: var(--v3-radius-m);
		background: var(--v3-s2);
		color: var(--v3-t1);
		font: inherit;
		text-align: left;
		cursor: pointer;
	}

	.replay:hover {
		border-color: var(--v3-line-3);
	}

	.replay:focus-visible {
		outline: 2px solid var(--v3-brand);
		outline-offset: 2px;
	}

	.r-ic {
		display: grid;
		flex: none;
		place-items: center;
		width: 36px;
		height: 36px;
		border-radius: 18px;
		background: var(--v3-s3);
		color: var(--v-map-water);
	}

	.r-tx {
		display: flex;
		flex: 1;
		flex-direction: column;
		min-width: 0;
		font-size: var(--v3-text-meta);
	}

	.r-tx span {
		color: var(--v3-t2);
		font-size: var(--v3-text-micro);
	}

</style>
