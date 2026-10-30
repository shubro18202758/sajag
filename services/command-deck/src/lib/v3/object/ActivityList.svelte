<script lang="ts">
	/**
	 * ActivityList (V3-SPEC §5.4, §6.3) — the record's audit as a vertical timeline, oldest first: time (IST,
	 * the day too once the rows span days), a dot (orange while a decision waits at the end, violet for the
	 * assistant's own steps), who, and the one-line brief (the inspector's activityRows; masked unless a duty
	 * officer is named). `limit` keeps the last n (the side card); the Timeline tab shows them all, the full
	 * text in each row's details.
	 */
	import { t } from '$lib/i18n/strings';
	import './packs.object';
	import { clockOf, type ActivityVM } from './view';

	let {
		rows,
		lang,
		limit = null,
		waits = null,
		full = false,
	}: { rows: readonly ActivityVM[]; lang: string; limit?: number | null; waits?: string | null; full?: boolean } = $props();

	const shownRows = $derived(limit != null ? rows.slice(-limit) : rows);
</script>

{#if shownRows.length || waits}
	<ol class="tl" data-testid="obj-activity" data-count={rows.length}>
		{#each shownRows as r (r.id)}
			<li class={['it', r.ai && 'ai']} data-actor-kind={r.actorKind}>
				<span class="tm">{clockOf(r)}</span>
				<span class="dt" aria-hidden="true"></span>
				<span class="body">
					<span class="who">{r.who}</span>
					<span class="what">{r.text}</span>
					{#if full && r.full && r.full !== r.text}
						<details><summary>{t(lang, 'obj_tl_all')}</summary><p>{r.full}</p></details>
					{/if}
				</span>
			</li>
		{/each}
		{#if waits}
			<li class="it dec"><span class="tm">{t(lang, 'obj_tl_now')}</span><span class="dt" aria-hidden="true"></span><span class="body"><span class="what">{waits}</span></span></li>
		{/if}
	</ol>
{:else}
	<p class="empty">{t(lang, 'obj_tl_empty')}</p>
{/if}

<style>
	.tl {
		display: flex;
		flex-direction: column;
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.it {
		position: relative;
		display: grid;
		grid-template-columns: 96px 22px minmax(0, 1fr);
		gap: 10px;
		padding: 8px 0;
		font-size: 14px;
		line-height: 20px;
	}

	.it::before {
		position: absolute;
		top: 0;
		bottom: 0;
		left: 116px;
		width: 2px;
		background: var(--v3-s4);
		content: '';
	}

	.it:first-child::before {
		top: 14px;
	}

	.it:last-child::before {
		bottom: calc(100% - 14px);
	}

	.it:only-child::before {
		display: none;
	}

	.tm {
		color: var(--v3-t2);
		font-variant-numeric: tabular-nums;
		text-align: right;
	}

	.dt {
		position: relative;
		z-index: 1;
		width: 10px;
		height: 10px;
		margin: 6px auto 0;
		border-radius: 50%;
		background: var(--v3-t2);
	}

	.ai .dt {
		background: var(--v3-ai);
	}

	.dec .dt {
		background: var(--v3-decide);
		box-shadow: 0 0 0 4px var(--v3-decide-veil);
	}

	.body {
		display: flex;
		flex-direction: column;
		min-width: 0;
	}

	.who {
		color: var(--v3-t3);
		font-size: var(--v3-text-micro);
		font-weight: 600;
		line-height: var(--v3-lh-micro);
	}

	.what {
		color: var(--v3-t1);
		overflow-wrap: anywhere;
	}

	details {
		margin-top: 4px;
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
	}

	summary {
		cursor: pointer;
		color: var(--v3-brand-text);
		font-weight: 600;
	}

	details p {
		margin: 4px 0 0;
		white-space: pre-wrap;
	}

	.empty {
		margin: 0;
		color: var(--v3-t2);
		font-size: 14px;
	}
</style>
