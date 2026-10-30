<script lang="ts">
	/**
	 * ReplaySheet — "Replay 19 Aug 2025": POST /hydro/replay run through the same ponding model with IMD's OBSERVED
	 * rain (the IMD observatory's 3-hourly totals and the peak hour; the 15-minute shape MODELLED), and what it shows:
	 *
	 *   the night     how many roads were deep or impassable as the water rose (a step chart, 22 Sep 18:00 to the
	 *                 modelled peak), the modelled gate closure and IMD's peak hour marked on it
	 *   the check     the places the news reported waterlogged, each with the time the model first flagged it —
	 *                 and the honest reading: almost the whole city was under water, so this shows the model was
	 *                 not blind, not that it tells streets apart; off-network reports are listed, not scored
	 *   the archive   the gridded reanalysis held a tenth of the rain: fed only that, nothing is flagged — the case
	 *                 for a gauge feed
	 *
	 * "Show on the map" opens the map in hindsight (/map?replay=2025-08-19). Every figure is the service's.
	 */
	import { t } from '$lib/i18n/strings';
	import { fmtTime } from '$lib/ui/format/format';
	import Glyph from '$lib/v3/Glyph.svelte';
	import ProvTag from './ProvTag.svelte';
	import { replayTimeline, type ReplayTimeline } from '../model';
	import type { HydroReplay } from '../types';
	import '../packs.ai';

	let { replay, loading = false, failed = false, lang, onclose, onretry }: { replay: HydroReplay | null; loading?: boolean; failed?: boolean; lang: string; onclose: () => void; onretry?: () => void } = $props();

	const L = (key: string, ...a: unknown[]) => t(lang, key, ...a);
	const tl = $derived(replayTimeline(replay));
	const tlRef = $derived(tl);

	// the chart: x = time (window start → modelled peak), y = roads (0 → every road)
	const W = 640;
	const H = 180;
	const PAD = { l: 34, r: 22, t: 10, b: 24 };
	const chart = $derived.by(() => {
		const tl: ReplayTimeline | null = tlRef;
		if (!tl || !tl.ticks.length) return null;
		const x0 = tl.start;
		const x1 = tl.peak;
		const span = Math.max(1, x1 - x0);
		const ymax = Math.max(10, tl.counts.roads);
		const X = (ms: number) => PAD.l + ((Math.min(x1, Math.max(x0, ms)) - x0) / span) * (W - PAD.l - PAD.r);
		const Y = (n: number) => H - PAD.b - (n / ymax) * (H - PAD.t - PAD.b);
		const step = (val: (k: { deep: number; impassable: number; at: number }) => number) => {
			let d = `M${X(tl.ticks[0].at).toFixed(1)},${Y(0).toFixed(1)}`;
			let prev = 0;
			for (const k of tl.ticks) {
				const v = val(k);
				d += ` L${X(k.at).toFixed(1)},${Y(prev).toFixed(1)} L${X(k.at).toFixed(1)},${Y(v).toFixed(1)}`;
				prev = v;
			}
			d += ` L${X(x1).toFixed(1)},${Y(prev).toFixed(1)} L${X(x1).toFixed(1)},${Y(0).toFixed(1)} Z`;
			return d;
		};
		const hours: { x: number; label: string }[] = [];
		// every two hours on the IST clock (IST = UTC + 5:30)
		const IST = 5.5 * 3_600_000;
		const first = Math.ceil((x0 + IST) / 7_200_000) * 7_200_000 - IST;
		for (let ms = first; ms <= x1; ms += 7_200_000) hours.push({ x: X(ms), label: fmtTime(ms) });
		const last = tl.ticks[tl.ticks.length - 1];
		return {
			deep: step((k) => k.deep + k.impassable),
			imp: step((k) => k.impassable),
			gates: tl.gates.filter((g) => g.from < x1).map((g) => ({ x: X(g.from), w: Math.max(2, X(g.to) - X(g.from)) })),
			peak: tl.peakHour ? { x: X(tl.peakHour.from), w: Math.max(2, X(tl.peakHour.to) - X(tl.peakHour.from)) } : null,
			first: tl.firstFlag ? X(tl.firstFlag) : null,
			hours,
			yTicks: [0, Math.round(ymax / 2), ymax].map((n) => ({ y: Y(n), n })),
			alt: L('ai_rp_chart_alt', last.deep, last.impassable, fmtTime(last.at)),
		};
	});
	const sources = $derived(replay ? Object.values((replay as unknown as { sources?: Record<string, { publisher: string; date: string; url: string }> }).sources ?? {}) : []);
</script>

<div class="scrim" role="presentation" onclick={onclose}></div>
<div class="rs" role="dialog" aria-modal="true" aria-labelledby="ai-replay-h" data-testid="ai-replay" data-ready={tl ? 'true' : 'false'}>
	<header class="top">
		<div class="art"><img src="/artwork/events/flooding.svg" alt="" width="640" height="360" /></div>
		<div class="ttl">
			<h2 id="ai-replay-h">{L('ai_rp_title')}</h2>
			<p class="lbl">{L('ai_rp_label')}</p>
			<div class="provs"><ProvTag prov="observed" {lang} /><ProvTag prov="modelled" {lang} /><ProvTag prov="hindsight" {lang} /></div>
		</div>
		<button type="button" class="x" aria-label={L('ai_rp_close')} title={L('ai_rp_close')} onclick={onclose}><Glyph name="close" size={20} /></button>
	</header>

	<div class="body">
		{#if tl && chart}
			<div class="figs">
				{#if tl.totals.mm != null && tl.totals.peakMmH != null}<div class="fig"><b>{tl.totals.mm.toFixed(1)} mm</b><span>{L('ai_rp_rain', tl.totals.peakMmH.toFixed(0))}</span></div>{/if}
				{#if tl.firstFlag}<div class="fig"><b>{fmtTime(tl.firstFlag)}</b><span>{L('ai_rp_first')}</span></div>{/if}
				<div class="fig"><b>{tl.hit.flagged} / {tl.hit.onNetwork}</b><span>{L('ai_rp_hits')}</span></div>
			</div>

			<section class="chart">
				<h3>{L('ai_rp_chart')}</h3>
				<svg viewBox="0 0 {W} {H}" role="img" aria-label={chart.alt} data-testid="ai-replay-chart">
					{#each chart.gates as g, i (i)}<rect class="gate" x={g.x} y={PAD.t} width={g.w} height={H - PAD.t - PAD.b} />{/each}
					{#if chart.peak}<rect class="peak" x={chart.peak.x} y={PAD.t} width={chart.peak.w} height={H - PAD.t - PAD.b} />{/if}
					{#each chart.yTicks as y (y.n)}<line class="grid" x1={PAD.l} x2={W - PAD.r} y1={y.y} y2={y.y} /><text class="ax" x={PAD.l - 6} y={y.y + 4} text-anchor="end">{y.n}</text>{/each}
					<path class="deep" d={chart.deep} />
					<path class="imp" d={chart.imp} />
					{#if chart.first != null}<line class="first" x1={chart.first} x2={chart.first} y1={PAD.t} y2={H - PAD.b} />{/if}
					{#each chart.hours as h (h.x)}<text class="ax" x={h.x} y={H - 6} text-anchor="middle">{h.label}</text>{/each}
				</svg>
				<div class="legend">
					<span><i class="k-deep"></i>{L('ai_rp_deep')}</span>
					<span><i class="k-imp"></i>{L('ai_rp_imp')}</span>
					<span><i class="k-gate"></i>{L('ai_rp_gates')}</span>
					<span><i class="k-peak"></i>{L('ai_rp_peak')}</span>
				</div>
			</section>

			<section class="rep">
				<h3>{L('ai_rp_reported')}</h3>
				<ul>
					{#each tl.reported as r (r.place)}
						<li data-flagged={r.flagged ? 'true' : 'false'}>
							<span class="pl">{r.place}</span>
							<span class={['fl', r.flagged && 'yes']}>{r.flagged && r.at != null ? L('ai_rp_flag_at', fmtTime(r.at)) : L('ai_rp_not_flagged')}</span>
							{#if r.maxClass != null}<span class="cls c{r.maxClass}">{L(`ai_risk_${Math.min(3, r.maxClass)}`)}</span>{/if}
						</li>
					{/each}
				</ul>
				<p class="note">{L('ai_rp_hits_note')}</p>
				{#if tl.offNetwork.length}<p class="note">{L('ai_rp_off', tl.offNetwork.join(', '))}</p>{/if}
				{#if tl.totals.archiveMm != null}<p class="note arch"><ProvTag prov="archive" {lang} /> {L('ai_rp_archive', tl.totals.archiveMm.toFixed(1))}</p>{/if}
			</section>

			{#if sources.length}
				<details class="src">
					<summary>{L('ai_rp_sources')}</summary>
					<ul>
						{#each sources as s (s.url)}<li><a href={s.url} target="_blank" rel="noopener noreferrer">{s.publisher}</a>, {s.date}</li>{/each}
					</ul>
				</details>
			{/if}
		{:else if failed}
			<p class="state">{L('ai_rp_failed')} {#if onretry}<button type="button" class="link" onclick={onretry}>{L('ai_retry')}</button>{/if}</p>
		{:else}
			<p class="state" aria-busy={loading}>{L('ai_rp_loading')}</p>
		{/if}
	</div>

	<footer class="foot">
		<a class="btn primary" href="/map?replay=2025-08-19" data-testid="ai-replay-map"><Glyph name="map" size={18} />{L('ai_rp_map')}</a>
		<button type="button" class="btn" onclick={onclose}>{L('ai_rp_close')}</button>
	</footer>
</div>

<style>
	.scrim {
		position: fixed;
		inset: 0;
		z-index: 60;
		background: var(--v3-scrim-mid);
	}

	.rs {
		position: fixed;
		top: 50%;
		left: 50%;
		z-index: 61;
		display: flex;
		flex-direction: column;
		width: min(760px, calc(100vw - 32px));
		max-height: calc(100vh - 48px);
		overflow: hidden;
		transform: translate(-50%, -50%);
		border: 1px solid var(--v3-line-2);
		border-radius: var(--v3-radius-xl);
		background: var(--v3-s1);
		box-shadow: var(--v3-elev-2);
		color: var(--v3-t1);
	}

	.top {
		position: relative;
		display: flex;
		align-items: flex-end;
		gap: 14px;
		min-height: 120px;
		padding: 18px 22px 14px;
	}

	.art {
		position: absolute;
		inset: 0;
		overflow: hidden;
	}

	.art img {
		width: 100%;
		height: 100%;
		object-fit: cover;
		object-position: 50% 60%;
	}

	.art::after {
		content: '';
		position: absolute;
		inset: 0;
		background: linear-gradient(to bottom, transparent 10%, var(--v3-s1));
	}

	.ttl {
		position: relative;
		display: flex;
		flex: 1;
		flex-direction: column;
		gap: 4px;
	}

	h2 {
		margin: 0;
		font-size: var(--v3-text-heading);
		line-height: var(--v3-lh-heading);
		font-weight: 700;
	}

	.lbl {
		margin: 0;
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
	}

	.provs {
		display: flex;
		gap: 6px;
	}

	.x {
		position: absolute;
		top: 12px;
		right: 12px;
		display: grid;
		place-items: center;
		width: 36px;
		height: 36px;
		border: 1px solid var(--v3-line-2);
		border-radius: 18px;
		background: var(--v3-glass);
		color: var(--v3-t1);
		cursor: pointer;
	}

	.body {
		display: flex;
		flex-direction: column;
		gap: 18px;
		padding: 6px 22px 16px;
		overflow: auto;
	}

	.figs {
		display: grid;
		grid-template-columns: repeat(3, minmax(0, 1fr));
		gap: 10px;
	}

	.fig {
		display: flex;
		flex-direction: column;
		gap: 4px;
		padding: 12px 14px;
		border-radius: var(--v3-radius-m);
		background: var(--v3-s2);
	}

	.fig b {
		font-size: var(--v3-text-sub);
		font-weight: 700;
		font-variant-numeric: tabular-nums;
	}

	.fig span {
		color: var(--v3-t2);
		font-size: var(--v3-text-micro);
		line-height: var(--v3-lh-micro);
	}

	h3 {
		margin: 0 0 8px;
		font-size: var(--v3-text-meta);
		font-weight: 650;
		color: var(--v3-t2);
	}

	svg {
		display: block;
		width: 100%;
		height: auto;
	}

	.grid {
		stroke: var(--v3-line-1);
	}

	.ax {
		fill: var(--v3-t3);
		font-size: 11px;
	}

	.gate {
		fill: var(--v3-s3);
	}

	.peak {
		fill: none;
		stroke: var(--v3-t2);
		stroke-dasharray: 4 3;
	}

	.deep {
		fill: var(--v-map-water);
		fill-opacity: 0.45;
	}

	.imp {
		fill: var(--v-map-water);
		fill-opacity: 0.95;
	}

	.first {
		stroke: var(--v3-t1);
		stroke-width: 1.5;
	}

	.legend {
		display: flex;
		flex-wrap: wrap;
		gap: 14px;
		margin-top: 6px;
		color: var(--v3-t2);
		font-size: var(--v3-text-micro);
	}

	.legend span {
		display: inline-flex;
		align-items: center;
		gap: 6px;
	}

	.legend i {
		display: inline-block;
		width: 14px;
		height: 8px;
		border-radius: 2px;
	}

	.k-deep {
		background: var(--v-map-water);
		opacity: 0.45;
	}

	.k-imp {
		background: var(--v-map-water);
	}

	.k-gate {
		background: var(--v3-s3);
	}

	.k-peak {
		border: 1px dashed var(--v3-t2);
	}

	.rep ul {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 6px 18px;
		margin: 0 0 8px;
		padding: 0;
		list-style: none;
	}

	.rep li {
		display: flex;
		align-items: center;
		gap: 8px;
		min-width: 0;
		font-size: var(--v3-text-meta);
	}

	.pl {
		flex: 1;
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.fl {
		color: var(--v3-t3);
		font-variant-numeric: tabular-nums;
	}

	.fl.yes {
		color: var(--v3-t1);
	}

	.cls {
		padding: 1px 8px;
		border-radius: 10px;
		background: var(--v3-s3);
		color: var(--v3-t2);
		font-size: var(--v3-text-micro);
	}

	.cls.c3 {
		color: var(--v3-t1);
		box-shadow: inset 0 0 0 1px var(--v-map-water);
	}

	.note {
		margin: 4px 0 0;
		color: var(--v3-t3);
		font-size: var(--v3-text-micro);
		line-height: var(--v3-lh-micro);
	}

	.arch {
		display: flex;
		align-items: flex-start;
		gap: 6px;
	}

	.src summary {
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
		cursor: pointer;
	}

	.src ul {
		margin: 6px 0 0;
		padding-left: 18px;
		color: var(--v3-t3);
		font-size: var(--v3-text-micro);
	}

	.src a {
		color: var(--v3-brand-text);
	}

	.state {
		margin: 24px 0;
		color: var(--v3-t2);
	}

	.foot {
		display: flex;
		justify-content: flex-end;
		gap: 10px;
		padding: 12px 22px 18px;
		border-top: 1px solid var(--v3-line-1);
	}

	.btn {
		display: inline-flex;
		align-items: center;
		gap: 8px;
		height: 40px;
		padding: 0 18px;
		border: 1px solid var(--v3-line-2);
		border-radius: 12px;
		background: none;
		color: var(--v3-t1);
		font: inherit;
		font-weight: 650;
		text-decoration: none;
		cursor: pointer;
	}

	.btn.primary {
		border-color: transparent;
		background: var(--v3-primary-bg);
		color: var(--v3-primary-ink);
	}

	.btn:focus-visible,
	.x:focus-visible {
		outline: 2px solid var(--v3-brand);
		outline-offset: 2px;
	}

	.link {
		border: 0;
		background: none;
		color: var(--v3-brand-text);
		font: inherit;
		font-weight: 600;
		cursor: pointer;
	}
</style>
