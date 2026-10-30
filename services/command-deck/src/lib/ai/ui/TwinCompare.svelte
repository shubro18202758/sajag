<script lang="ts">
	/**
	 * TwinCompare — the twin's before/after for a signal-timing proposal, small and clear: four rows (delay at the
	 * junction, the longest queue, the cross street, the whole network), "Do nothing" against "With the change",
	 * a bar pair per row on one scale, and the change in words. Then the confidence (a modelled heuristic, said so)
	 * and the labels: Modelled, and the demand's own (Simulated until the oracle serves live Mumbai traffic).
	 */
	import { t } from '$lib/i18n/strings';
	import ProvTag from './ProvTag.svelte';
	import type { TwinSide } from '../types';
	import '../packs.ai';

	let {
		before,
		after,
		horizonMin,
		confidence = null,
		demand = null,
		lang,
	}: {
		before: TwinSide | null;
		after: TwinSide | null;
		horizonMin: number;
		confidence?: { score: number; level: string } | null;
		demand?: string | null;
		lang: string;
	} = $props();

	const L = (key: string, ...a: unknown[]) => t(lang, key, ...a);
	const ROWS = [
		{ k: 'focus_delay_veh_h', label: 'ai_tc_focus', digits: 1 },
		{ k: 'max_queue_m', label: 'ai_tc_queue', digits: 0 },
		{ k: 'cross_street_delay_veh_h', label: 'ai_tc_cross', digits: 1 },
		{ k: 'network_delay_veh_h', label: 'ai_tc_net', digits: 0 },
	] as const;
	const rows = $derived(
		ROWS.map((r) => {
			const a = before?.[r.k];
			const b = after?.[r.k];
			if (typeof a !== 'number' || typeof b !== 'number') return null;
			const max = Math.max(a, b, 1e-9);
			const pct = a > 0 ? ((b - a) / a) * 100 : 0;
			return { ...r, a, b, wa: (a / max) * 100, wb: (b / max) * 100, pct };
		}).filter((r): r is NonNullable<typeof r> => r !== null),
	);
	const level = $derived(confidence ? L(`ai_conf_${confidence.level}`) : '');
</script>

<section class="tc" aria-label={L('ai_tc_title', Math.round(horizonMin))} data-testid="ai-twin-compare">
	<div class="head">
		<span class="ttl">{L('ai_tc_title', Math.round(horizonMin))}</span>
		<span class="provs"><ProvTag prov="modelled" {lang} />{#if demand}<ProvTag label={demand} {lang} />{/if}</span>
	</div>
	<div class="legend"><span><i class="k-a"></i>{L('ai_tc_none')}</span><span><i class="k-b"></i>{L('ai_tc_with')}</span></div>
	<ul class="rows">
		{#each rows as r (r.k)}
			<li class="row" data-metric={r.k}>
				<span class="lbl">{L(r.label)}</span>
				<span class="bars" aria-hidden="true">
					<span class="bar a" style:width={`${r.wa.toFixed(1)}%`}></span>
					<span class="bar b" style:width={`${r.wb.toFixed(1)}%`}></span>
				</span>
				<span class="nums"><span class="na">{r.a.toFixed(r.digits)}</span> → <b>{r.b.toFixed(r.digits)}</b></span>
				<span class={['pct', r.pct < -0.05 ? 'down' : r.pct > 0.05 ? 'up' : 'same']}>{r.pct > 0 ? '+' : ''}{r.pct.toFixed(1)}%</span>
			</li>
		{/each}
	</ul>
	{#if confidence}<p class="conf">{L('ai_tc_conf', confidence.score.toFixed(2), level)}</p>{/if}
	<p class="note">{L('ai_tc_note')}</p>
</section>

<style>
	.tc {
		display: flex;
		flex-direction: column;
		gap: 10px;
		padding: 14px 16px;
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

	.legend {
		display: flex;
		gap: 16px;
		color: var(--v3-t3);
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
		height: 6px;
		border-radius: 3px;
	}

	.k-a,
	.bar.a {
		background: var(--v3-t3);
		opacity: 0.6;
	}

	.k-b,
	.bar.b {
		background: var(--v3-t1);
	}

	.rows {
		display: flex;
		flex-direction: column;
		gap: 10px;
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.row {
		display: grid;
		grid-template-columns: minmax(0, 1.3fr) minmax(0, 1fr) auto auto;
		align-items: center;
		gap: 10px;
		font-size: var(--v3-text-meta);
	}

	.lbl {
		color: var(--v3-t2);
	}

	.bars {
		display: flex;
		flex-direction: column;
		gap: 3px;
	}

	.bar {
		display: block;
		height: 6px;
		min-width: 2px;
		border-radius: 3px;
	}

	.nums {
		color: var(--v3-t2);
		font-variant-numeric: tabular-nums;
		white-space: nowrap;
	}

	.nums b {
		color: var(--v3-t1);
	}

	.pct {
		min-width: 58px;
		text-align: right;
		font-weight: 700;
		font-variant-numeric: tabular-nums;
		color: var(--v3-t2);
	}

	.pct.down {
		color: var(--v3-ok-text);
	}

	.conf,
	.note {
		margin: 0;
		color: var(--v3-t3);
		font-size: var(--v3-text-micro);
	}

	.conf {
		color: var(--v3-t2);
	}
</style>
