<script lang="ts" module>
	import { t } from '$lib/i18n/strings';
	import type { DataStatus } from './command-bar.svelte';

	const DECIDER_WORDS = new Set(['loaded', 'loading', 'unreachable']);

	/** The decider's state in words ("loaded"); an unknown state reads "state unknown". */
	export function deciderWord(lang: string, state: string): string {
		return DECIDER_WORDS.has(state) ? t(lang, `shell_decider_${state}`) : t(lang, 'shell_decider_unknown');
	}

	/** p95 in seconds, one decimal ("2.3"). */
	export function p95Text(p95: number | null): string | null {
		return p95 == null || !Number.isFinite(p95) ? null : p95.toFixed(1);
	}

	/**
	 * The Data button's summary — its visually hidden text AND its tooltip:
	 * "Decision model loaded, p95 2.3 s, novelty check on; all feeds answering".
	 */
	export function dataSummary(lang: string, s: DataStatus): string {
		const head = [t(lang, 'shell_data_decider', deciderWord(lang, s.decider))];
		const p95 = p95Text(s.p95);
		if (p95 != null) head.push(t(lang, 'shell_data_p95', p95));
		head.push(t(lang, 'shell_data_novelty', s.novelty ? t(lang, 'shell_data_on') : t(lang, 'shell_data_off')));
		// a feed this page does not read ('none') is neither answering nor failing: it is not counted
		const read = s.feeds.filter((f) => f.status !== 'none');
		const bad = read.filter((f) => f.status !== 'ok').length;
		const tail = bad ? t(lang, 'shell_data_feeds_bad', bad, read.length) : t(lang, 'shell_data_feeds_ok');
		return `${head.join(', ')}; ${tail}`;
	}
</script>

<script lang="ts">
	/**
	 * The Data and services popover (SPEC §5.3, §8.10): every feed and service
	 * behind the console with its state, then the decision model's posture.
	 * What the page supplied in commandBar.dataStatus, nothing invented, so
	 * no "As of" time either: dataStatus carries no timestamp, and the moment
	 * the popover opened is not the time of the data (SPEC §9.1).
	 */
	import { sentenceStart } from '$lib/primitives/text';
	import Icon from '$lib/ui/Icon.svelte';
	import Tag from '$lib/ui/Tag.svelte';
	import { FEED_LOSS_ICON } from './icons';

	let { status, lang }: { status: DataStatus; lang: string } = $props();

	const tierWord = $derived.by(() => {
		const k = `shell_tier_${status.tier}`;
		const w = t(lang, k);
		return w === k ? status.tier : w;
	});
</script>

<div class="panel" data-shell="data-panel">
	<div class="head">
		<div class="h">{t(lang, 'shell_data')}</div>
	</div>
	{#if status.feeds.length}
		<table class="rows">
			<tbody>
				{#each status.feeds as f (f.name)}
					<tr data-feed={f.name} data-status={f.status}>
						<td class="name">{f.name}</td>
						<td class="label">{f.label}</td>
						<td class="state">
							{#if f.status === 'ok'}
								<Tag intent="success">{t(lang, 'shell_feed_ok')}</Tag>
							{:else if f.status === 'degraded'}
								<Tag>{t(lang, 'shell_feed_degraded')}</Tag>
							{:else if f.status === 'none'}
								<span class="none">{t(lang, 'shell_feed_none')}</span>
							{:else}
								<Tag icon={FEED_LOSS_ICON}>{t(lang, 'shell_feed_down')}</Tag>
							{/if}
						</td>
					</tr>
				{/each}
			</tbody>
		</table>
	{/if}
	<div class="model">
		<div class="row">
			<span class="k">{t(lang, 'shell_data_model')}</span>
			<span class="v">
				<!-- a tag word is sentence case ("Loaded"); the lower-case word is for the summary sentence -->
				{#if status.decider === 'loaded'}<Tag intent="success">{sentenceStart(deciderWord(lang, status.decider))}</Tag>{:else}<Tag>{sentenceStart(deciderWord(lang, status.decider))}</Tag>{/if}
				{#if p95Text(status.p95) != null}<span class="n">{t(lang, 'shell_data_p95', p95Text(status.p95))}</span>{/if}
			</span>
		</div>
		<div class="row">
			<span class="k">{t(lang, 'shell_data_novelty_row')}</span>
			<span class="v">{status.novelty ? t(lang, 'shell_data_on') : t(lang, 'shell_data_off')}</span>
		</div>
		<div class="row">
			<span class="k">{t(lang, 'shell_data_tier')}</span>
			<span class="v">{tierWord}</span>
		</div>
	</div>
	{#if status.worst === 'down'}
		<div class="loss"><Icon name={FEED_LOSS_ICON} size={16} />{t(lang, 'live_feed_loss')}</div>
	{/if}
</div>

<style>
	.panel {
		box-sizing: border-box;
		width: 360px;
		max-width: calc(100vw - 16px);
		font-family: var(--v-font-ui);
		font-size: var(--v-text-base);
		line-height: calc(var(--v-text-base) + 4px);
	}

	.head {
		padding: 12px 16px 8px;
	}

	.h {
		font-weight: 600;
		line-height: calc(var(--v-text-base) + 2px);
	}

	.rows {
		width: calc(100% - 32px);
		margin: 0 16px 8px;
		border-collapse: collapse;
		font-size: var(--v-text-xs);
		line-height: calc(var(--v-text-xs) + 4px);
	}

	.rows td {
		height: 28px;
		padding: 0;
		border-bottom: 1px solid var(--v-line-1);
		vertical-align: middle;
	}

	.rows tr:last-child td {
		border-bottom: 0;
	}

	.name {
		color: var(--v-ink-1);
		font-size: var(--v-text-base);
		white-space: nowrap;
	}

	/* a feed this page does not read: plain ink-2 words, no status tag (F-04) */
	.none {
		color: var(--v-ink-2);
		font-size: var(--v-text-xs);
		white-space: nowrap;
	}

	.label {
		max-width: 150px;
		padding: 0 8px;
		overflow: hidden;
		color: var(--v-ink-2);
		text-align: right;
		text-overflow: ellipsis;
		font-variant-numeric: tabular-nums;
		white-space: nowrap;
	}

	.state {
		width: 1%;
		text-align: right;
		white-space: nowrap;
	}

	.model {
		padding: 8px 16px 12px;
		border-top: 1px solid var(--v-line-2);
		font-size: var(--v-text-xs);
		line-height: 24px;
	}

	.row {
		display: flex;
		align-items: center;
		gap: 8px;
		min-height: 28px;
	}

	.k {
		flex: 1 1 auto;
		color: var(--v-ink-1);
		font-size: var(--v-text-base);
	}

	.v {
		display: inline-flex;
		align-items: center;
		gap: 8px;
		color: var(--v-ink-2);
		white-space: nowrap;
	}

	.n {
		font-variant-numeric: tabular-nums;
	}

	.loss {
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 8px 16px 12px;
		border-top: 1px solid var(--v-line-1);
		color: var(--v-ink-1);
		font-size: var(--v-text-xs);
	}

	.loss :global([data-ui='icon']) {
		color: var(--v-ink-2);
	}
</style>
