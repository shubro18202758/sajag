<script lang="ts">
	/**
	 * The Explorer's watches (SPEC §5.3, §7.3): what an analyst follows. A
	 * row carries its title only; the count sits at the right edge.
	 *
	 *   Decision needed        decisions waiting as units — decisionUnits()
	 *                          (the navbar's and the Inbox's count) once a
	 *                          unit source is registered, else the same §7.4
	 *                          rule on the registry: the vitals card's figure
	 *                          (figures.ts decisionsWaiting), never another
	 *   Watchlist reads, 24 h  selectors.watchReads(now − 24 h, now)
	 *   this browser's watches an object (its feed rows in 24 h) or a
	 *                          filtered set (the objects it matches now);
	 *                          stored masked
	 *
	 * The copy says what this list does (it counts here); it promises no Inbox
	 * row until the Inbox reads the watches. A watch NEVER mutes an interrupt
	 * (an escort proposal, a watchlist read, a band change during a movement,
	 * a feed loss): there is no mute here.
	 */
	import { kindIcon } from '$lib/design/icons';
	import { Button, Icon, Menu, Popover, Section, Tag, Tooltip, type MenuItemSpec } from '$lib/ui';
	import { t } from '$lib/i18n/strings';
	import '$lib/i18n/packs.views';
	import { selection } from '$lib/gods-eye/entities/selection.svelte';
	import { ops } from '$lib/ops/store.svelte';
	import { kindOne } from '../../kinds/generic';
	import { registrySize } from '../../registry';
	import { hourOf, workspace } from '../../workspace.svelte';
	import { liveWorld, selectors } from '../../world.svelte';
	import { matchesWatch } from '../../watches';
	import type { Watch } from '../../types';
	import { decisionsWaiting } from '../vitals/figures';
	import { watchTitle } from './model';

	let { lang }: { lang: string } = $props();
	const L = (key: string, ...args: unknown[]) => t(lang, key, ...args);

	let open = $state(true);
	let now = $state(Date.now());
	$effect(() => {
		const id = setInterval(() => (now = Date.now()), 30_000);
		return () => clearInterval(id);
	});

	const DAY = 24 * 3_600_000;
	// the vitals card's rule (figures.ts): units once a source is registered, else the registry rule
	const units = $derived(
		decisionsWaiting({ selectors, registry: liveWorld.registry(), unitSources: registrySize().units, escortProposals: ops.escortProposals.length }).n,
	);
	const reads = $derived(selectors.watchReads(now - DAY, now).length);
	const watches = $derived(workspace.watches);
	const graph = $derived(liveWorld.graph());

	/** An object watch: its feed rows in the last 24 h; a filter watch: the objects it matches now. */
	function countOf(w: Watch): number {
		if (w.subjectUrn) return selectors.feedIn(now - DAY, now).filter((f) => f.urns.includes(w.subjectUrn as string)).length;
		let n = 0;
		for (const r of graph.all()) if (matchesWatch(w, r, hourOf)) n++;
		return n;
	}

	const selected = $derived(selection.current ? graph.get(selection.current) : null);
	/** Set when the store refused a watch (shown under the list until the next add). */
	let refused = $state(false);

	/** Add a watch; the store refuses an unusable one by throwing — never out of a menu click. */
	function add(w: Omit<Watch, 'id'>) {
		try {
			workspace.addWatch(w);
			refused = false;
		} catch {
			refused = true;
		}
	}

	function watchSelection() {
		if (!selected) return;
		// the store keeps 80 characters without < > ` or control characters: a long label is cut, never refused
		add({ title: watchTitle(selected.label) ?? kindOne(selected.kind, lang), subjectUrn: selected.urn, filters: [] });
	}

	function watchFilters() {
		const filters = workspace.filters;
		if (!filters.length) return;
		add({ title: watchTitle(filters.map((f) => f.label).join('; ')) ?? L('vw_w_filters_title'), subjectUrn: null, filters });
	}

	const addItems = $derived<MenuItemSpec[]>([
		{
			id: 'selection',
			label: L('vw_w_add_selection'),
			icon: 'locate',
			disabled: !selected,
			disabledReason: L('vw_w_add_selection_off'),
			attrs: { 'data-testid': 'watch-add-selection' },
			onclick: watchSelection,
		},
		{
			id: 'filters',
			label: L('vw_w_add_filters'),
			icon: 'filter',
			disabled: !workspace.filters.length,
			disabledReason: L('vw_w_add_filters_off'),
			attrs: { 'data-testid': 'watch-add-filters' },
			onclick: watchFilters,
		},
	]);
</script>

<Section title={L('vw_w_title')} collapsible bind:open data-explorer-section="watches">
	{#snippet right()}
		<Tooltip content={L('vw_w_hint')}>
			<button type="button" class="hint" aria-label={L('vw_w_hint')}><Icon name="info-sign" size={12} /></button>
		</Tooltip>
		<Popover placement="bottom-end">
			<Button minimal small icon="plus" tooltip={L('vw_w_add')} aria-label={L('vw_w_add')} data-testid="watch-add" />
			{#snippet content({ close })}<Menu items={addItems} label={L('vw_w_add')} onselect={() => close()} />{/snippet}
		</Popover>
	{/snippet}
	<ul class="list" data-testid="watches">
		<li class="row" data-watch="decision-needed" data-count={units}>
			<span class="glyph"><Icon name="inbox" /></span>
			<span class="label">{L('vw_w_decision')}</span>
			{#if units}<Tag round intent="warning" data-testid="watch-decision-count">{units}</Tag>{:else}<span class="n" data-testid="watch-decision-count">0</span>{/if}
		</li>
		<li class="row" data-watch="watchlist-reads" data-count={reads}>
			<span class="glyph"><Icon name={kindIcon('sighting')} /></span>
			<span class="label">{L('vw_w_reads')}</span>
			<span class="n">{reads}</span>
		</li>
		{#each watches as w (w.id)}
			{@const n = countOf(w)}
			<li class="row" data-watch={w.id} data-count={n}>
				<span class="glyph"><Icon name="notifications" /></span>
				<span class="label" title={w.title}>{w.title}</span>
				<Tooltip content={w.subjectUrn ? L('vw_w_count_subject', n) : L('vw_w_count_filters', n)}><span class="n">{n}</span></Tooltip>
				<Button minimal small icon="small-cross" class="rm" tooltip={L('vw_w_remove')} aria-label={L('vw_w_remove')} onclick={() => workspace.removeWatch(w.id)} />
			</li>
		{/each}
	</ul>
	{#if refused}<p class="empty" role="status" data-testid="watch-refused">{L('vw_w_refused')}</p>{/if}
	{#if !watches.length}<p class="empty">{L('vw_w_empty')}</p>{/if}
</Section>

<style>
	.list {
		margin: 0;
		padding: 0 0 4px;
		list-style: none;
	}

	.row {
		position: relative;
		display: flex;
		align-items: center;
		gap: 8px;
		height: 30px;
		padding: 0 12px 0 16px;
		color: var(--v-ink-1);
		font-size: var(--v-text-base);
	}

	.row:hover {
		background: var(--v-row-hover);
	}

	.glyph {
		display: inline-flex;
		color: var(--v-ink-2);
	}

	.label {
		flex: 1 1 auto;
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.n {
		min-width: 20px;
		color: var(--v-ink-2);
		font-size: var(--v-text-xs);
		font-variant-numeric: tabular-nums;
		text-align: right;
	}

	/* the remove button covers the count on hover or focus: counts stay in one column */
	.row :global(.rm) {
		position: absolute;
		top: 3px;
		right: 8px;
		background: var(--v-surface-1);
		opacity: 0;
	}

	.row:hover :global(.rm),
	.row:focus-within :global(.rm) {
		opacity: 1;
	}

	.hint {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 24px;
		height: 24px;
		margin: 0;
		padding: 0;
		border: 0;
		border-radius: var(--v-radius-chip);
		background: transparent;
		color: var(--v-ink-2);
		cursor: help;
	}

	.hint:focus-visible {
		outline: 2px solid var(--v-focus);
	}

	.hint :global([data-ui='icon']) {
		color: var(--v-ink-2);
	}

	.empty {
		margin: 0;
		padding: 0 16px 12px;
		color: var(--v-ink-2);
		font-size: var(--v-text-xs);
		line-height: 16px;
	}
</style>
