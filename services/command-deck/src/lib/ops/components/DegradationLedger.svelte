<script lang="ts">
	/**
	 * Degradation ledger (ownership UI-S5B), inside the /ops Lab and system
	 * section: the recurring-failure taxonomy mined from the brain's
	 * decisions_log audit trail (GET /ops/degradation-taxonomy). Every row is
	 * a cause the log actually carries — a novelty-latch firing, a tier-0
	 * miss, a tactical fallback, a failed turn — with its count, first and
	 * last seen (IST) and the reference of one real row. An empty log says so
	 * honestly; a failing endpoint keeps the last-good ledger with the reason.
	 */
	import { Id, NonIdealState, Tooltip } from '$lib/ui';
	import { colStamp } from '$lib/ui/format/format';
	import { t } from '$lib/i18n/strings';
	import '$lib/i18n/packs.wall';
	import { ops } from '$lib/ops/store.svelte';
	import { displayText } from '$lib/workspace/display';

	const lang = $derived(ops.lang);
	const L = (key: string, ...args: unknown[]) => t(lang, key, ...args);
	const tax = $derived(ops.degradation);
	const entries = $derived(tax?.entries ?? []);
	const last = $derived(colStamp(entries.map((e) => (e.lastSeen ?? e.firstSeen ?? NaN) * 1000)));

	/** "novelty_latch:novel" → "Novelty latch · novel" (the raw cause stays in the tooltip). */
	function causeWord(cause: string): string {
		const [family, detail] = cause.split(':', 2);
		const key = `wall_ledger_${family}`;
		const w = L(key);
		const head = w === key ? displayText(family) : w;
		return detail ? `${head} · ${displayText(detail)}` : head;
	}
</script>

<div class="ledger" data-wall="ledger">
	<div class="sub-head">
		<h3 class="h">{L('wall_ledger')}</h3>
		<span class="grow"></span>
		{#if tax}<span class="muted tn">{L('wall_ledger_scan', tax.rowsScanned, tax.contextsScanned)}</span>{/if}
	</div>
	{#if ops.degradationNote}<p class="note">{ops.degradationNote}</p>{/if}
	{#if entries.length}
		<table class="wdt" aria-label={L('wall_ledger')}>
			<colgroup><col /><col style:width="56px" /><col style:width="72px" /><col style:width="112px" /></colgroup>
			<thead>
				<tr>
					<th scope="col">{L('wall_ledger_cause')}</th>
					<th scope="col" class="num">{L('wall_ledger_count')}</th>
					<th scope="col" class="num">{L('wall_ledger_last')}</th>
					<th scope="col">{L('wall_ledger_sample')}</th>
				</tr>
			</thead>
			<tbody>
				{#each entries as e, i (e.cause)}
					<tr data-cause={e.cause}>
						<td><div class="c"><Tooltip content={e.cause}><span class="ell">{causeWord(e.cause)}</span></Tooltip></div></td>
						<td class="num"><div class="c tn">{e.count}</div></td>
						<td class="num"><div class="c tn">{last[i]}</div></td>
						<td><div class="c"><span class="ell" title={e.sampleRef}><Id value={e.sampleRef} /></span></div></td>
					</tr>
				{/each}
			</tbody>
		</table>
		{#if tax?.truncated}<p class="note">{L('wall_ledger_truncated')}</p>{/if}
	{:else}
		<div class="empty">
			<NonIdealState icon="tick-circle" iconSize={20} layout="horizontal" description={tax ? L('wall_ledger_empty') : L('wall_ledger_waiting')} />
		</div>
	{/if}
</div>

<style>
	.ledger {
		display: flex;
		flex-direction: column;
		gap: 6px;
		padding: 8px 0 12px;
		font-size: var(--v-text-xs);
		line-height: 16px;
	}

	.sub-head {
		display: flex;
		align-items: center;
		gap: 8px;
		min-width: 0;
		min-height: 28px;
		padding: 0 16px;
	}

	.h {
		margin: 0;
		font-size: var(--v-text-base);
		font-weight: 600;
		line-height: 18px;
		white-space: nowrap;
	}

	.grow {
		flex: 1 1 auto;
	}

	.muted {
		color: var(--v-ink-2);
	}

	.tn {
		font-variant-numeric: tabular-nums;
	}

	.ell {
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.note {
		margin: 0;
		padding: 0 16px;
		color: var(--v-ink-2);
	}

	.empty {
		padding: 0 16px;
	}
</style>
