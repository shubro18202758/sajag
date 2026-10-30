<script lang="ts">
	/**
	 * ForecastBand — a road's next two hours in the selection card: the median (p50) V/C at +30, +60 and +120 min,
	 * each over its p10–p90 band on a 0–1.2 track with the 0.8 threshold marked, and the word for it ("Likely over
	 * 0.8"). The forecast's own labels ride with it (Modelled; Simulated while the history is simulated).
	 */
	import { t } from '$lib/i18n/strings';
	import ProvTag from './ProvTag.svelte';
	import { crossingWord, forecastPoints } from '../model';
	import { provList } from '../labels';
	import type { ForecastSegment } from '../types';
	import '../packs.ai';

	let { seg, threshold = 0.8, labels = [], lang, loading = false }: { seg: ForecastSegment | null; threshold?: number; labels?: readonly string[]; lang: string; loading?: boolean } = $props();

	const L = (key: string, ...a: unknown[]) => t(lang, key, ...a);
	const pts = $derived(forecastPoints(seg));
	const MAX = 1.2;
	const pct = (v: number) => `${Math.max(0, Math.min(100, (v / MAX) * 100)).toFixed(1)}%`;
	const provs = $derived(provList(['MODELLED', ...labels]));
	const WORD = { over: 'ai_fc_over', likely: 'ai_fc_likely', possible: 'ai_fc_possible', under: 'ai_fc_under' } as const;
</script>

<section class="fb" aria-label={L('ai_fc_title')} data-testid="ai-forecast-band">
	<div class="head">
		<span class="ttl">{L('ai_fc_title')}</span>
		<span class="provs">{#each provs as p (p)}<ProvTag prov={p} {lang} />{/each}</span>
	</div>
	{#if seg && pts.some(Boolean)}
		<div class="cols">
			{#each pts as p, i (i)}
				<div class="col" data-lead={p?.lead ?? ''}>
					<span class="lead">{L('ai_fc_lead', [30, 60, 120][i])}</span>
					{#if p}
						{@const w = crossingWord(p.vc, threshold)}
						<b class={['val', `w-${w}`]}>{p.vc.p50.toFixed(2)}</b>
						<span class="track" aria-hidden="true">
							<span class="band" style:left={pct(p.vc.p10)} style:width={`calc(${pct(p.vc.p90)} - ${pct(p.vc.p10)})`}></span>
							<span class="thr" style:left={pct(threshold)}></span>
							<span class="mid" style:left={pct(p.vc.p50)}></span>
						</span>
						<span class="rng">{L('ai_fc_band', p.vc.p10.toFixed(2), p.vc.p90.toFixed(2))}</span>
						<span class={['word', `w-${w}`]}>{L(WORD[w])}</span>
					{:else}
						<b class="val">—</b>
					{/if}
				</div>
			{/each}
		</div>
		<p class="note">{#if seg.now}<span>{L('ai_fc_now', seg.now.vc.toFixed(2))}</span><span class="sep" aria-hidden="true">·</span>{/if}<span>{L('ai_fc_note')}</span></p>
	{:else}
		<p class="note">{loading ? L('ai_fc_loading') : L('ai_fc_none')}</p>
	{/if}
</section>

<style>
	.fb {
		display: flex;
		flex-direction: column;
		gap: 8px;
		padding: 12px 14px;
		border: 1px solid var(--v3-line-1);
		border-radius: var(--v3-radius-m);
		background: var(--v3-s1);
	}

	.head {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 8px;
	}

	.ttl {
		color: var(--v3-t1);
		font-size: var(--v3-text-meta);
		font-weight: 650;
	}

	.provs {
		display: inline-flex;
		gap: 4px;
	}

	.cols {
		display: grid;
		grid-template-columns: repeat(3, minmax(0, 1fr));
		gap: 12px;
	}

	.col {
		display: flex;
		flex-direction: column;
		gap: 3px;
		min-width: 0;
	}

	.lead,
	.rng {
		color: var(--v3-t3);
		font-size: var(--v3-text-micro);
	}

	.val {
		color: var(--v3-t1);
		font-size: var(--v3-text-sub);
		font-weight: 700;
		font-variant-numeric: tabular-nums;
	}

	.track {
		position: relative;
		display: block;
		height: 10px;
		border-radius: 4px;
		background: var(--v3-s3);
	}

	.band {
		position: absolute;
		top: 0;
		bottom: 0;
		border-radius: 4px;
		background: var(--v3-t2);
		opacity: 0.45;
	}

	.thr {
		position: absolute;
		top: -4px;
		bottom: -4px;
		width: 0;
		border-left: 2px dotted var(--v3-t2);
	}

	.mid {
		position: absolute;
		top: -2px;
		bottom: -2px;
		width: 4px;
		margin-left: -2px;
		border-radius: 2px;
		background: var(--v3-t1);
	}

	.word {
		color: var(--v3-t2);
		font-size: var(--v3-text-micro);
		font-weight: 600;
	}

	.word.w-over,
	.word.w-likely {
		color: var(--v3-t1);
	}

	.sep {
		margin: 0 6px;
	}

	.note {
		margin: 0;
		color: var(--v3-t3);
		font-size: var(--v3-text-micro);
	}
</style>
