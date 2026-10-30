<script lang="ts">
	/**
	 * Histogram (SPEC §5.3, §8.9) — the left dock's filter panel over the rows
	 * in the table.
	 *
	 * - Scope: the rows IN THE TABLE. `rows` when the page passes them;
	 *   without props (the left dock mounts its tabs without props) the rows
	 *   the mounted ObjectTable publishes — whatever the page passed it — or,
	 *   while no table is mounted, the shared scope a table would show
	 *   (tableScope.inTable()). The top line says how many.
	 * - Groups: Kind, State, Source, Hour (IST, sorted BY TIME), Road,
	 *   Camera. Each header: the title, "1 value" / "n values" (the values a
	 *   filter can keep: one bar each), and a filter glyph when a filter on
	 *   that field is in force.
	 * - Rows: 24 px, a check box (a check mark when selected), the value, a
	 *   bar scaled to the group's largest value, the count — and a filter on
	 *   a bar's value keeps exactly its count. The eight largest values show;
	 *   "Show n more" lists the rest (Hour shows every hour). Rows without a
	 *   value are counted under the group, never filterable. Road reads the
	 *   road a row records itself (the store's road filter); its line says
	 *   so, since the table's Place column also names a camera's road.
	 * - A pick counts only while its value is still a bar (bins.livePicks):
	 *   when the rows change under it, it drops out.
	 * - The open-source bar (the source glyph, "Open-source") carries its
	 *   rows by verification state as indented lines to read, with no check
	 *   box: the store's filters have no verification field, so a state
	 *   cannot be picked on its own.
	 * - Footer: "Filter to" turns primary only once a value is selected and
	 *   calls workspace.addFilter (one filter per group: values OR-ed, groups
	 *   AND-ed). "Filter out" keeps the other values the table holds now —
	 *   only where that is exact (every row has a value). "Clear" drops the
	 *   selection, never the filters in force (the filter bar removes those).
	 */
	import { PROVENANCE_ICON } from '$lib/design/icons';
	import { Button, Icon, NonIdealState, Section, Tooltip, provideUiLang } from '$lib/ui';
	import { t } from '$lib/i18n/strings';
	import '$lib/i18n/packs.views';
	import { commandBar } from '$lib/shell/command-bar.svelte';
	import { workspace } from '../../workspace.svelte';
	import { tableScope } from '../table/scope.svelte';
	import type { ObjectRow } from '../../types';
	import {
		HIST_FIELDS,
		TOP_VALUES,
		canFilterOut,
		filtersOut,
		filtersTo,
		hasPicks,
		histogram,
		livePicks,
		valuesLabel,
		type HistBin,
		type HistField,
		type HistGroup,
	} from './bins';

	let { rows: rowsProp }: { rows?: readonly ObjectRow[] } = $props();

	provideUiLang(() => commandBar.lang);
	const lang = $derived(commandBar.lang);
	const L = (key: string, ...args: unknown[]) => t(lang, key, ...args);

	const rows = $derived(rowsProp ?? tableScope.inTable());
	const groups = $derived(histogram(rows, lang));

	/** Selected filter values per field. */
	let picked = $state<Partial<Record<HistField, string[]>>>({});
	let open = $state<Record<HistField, boolean>>({ kind: true, state: true, source: true, hour: true, road: true, camera: true });
	let more = $state<Partial<Record<HistField, boolean>>>({});

	// only picks that still name a bar count (bins.livePicks): a stale pick never leaves "Filter to" primary over nothing
	const selection = $derived(livePicks(groups, picked));
	const anyPicked = $derived(hasPicks(selection));
	const toFilters = $derived(filtersTo(groups, selection, lang));
	const outFilters = $derived(anyPicked ? filtersOut(groups, selection, lang) : null);
	const filtered = $derived(new Set(workspace.filters.map((f) => f.field)));

	function isOn(field: HistField, value: string): boolean {
		return selection.get(field)?.has(value) ?? false;
	}

	function toggle(field: HistField, value: string) {
		// a pick whose bar has gone is dropped here, never revived later
		const cur = [...(selection.get(field) ?? [])];
		picked[field] = cur.includes(value) ? cur.filter((v) => v !== value) : [...cur, value];
	}

	function clear() {
		picked = {};
	}

	function apply(list: readonly { field: HistField | string; values: readonly string[]; label: string }[] | null) {
		if (!list?.length) {
			clear();
			return;
		}
		for (const f of list) {
			// a new filter on a field replaces the one in force there: the values were counted inside it
			for (const old of workspace.filters) if (old.field === f.field) workspace.removeFilter(old.id);
			workspace.addFilter({ field: f.field as HistField, values: f.values, label: f.label });
		}
		clear();
	}

	function shown(g: HistGroup): HistBin[] {
		if (g.field === 'hour' || more[g.field] || g.bins.length <= TOP_VALUES) return g.bins;
		return g.bins.slice(0, TOP_VALUES);
	}

	/** The bar's share of the group's largest value (a sliver for the smallest, never nothing). */
	const pct = (b: HistBin, g: HistGroup) => (g.max ? Math.max(4, Math.round((b.n / g.max) * 100)) : 0);

	const outReason = $derived(!anyPicked ? L('vw_h_select_first') : outFilters ? null : L('vw_h_out_inexact'));
	const filterLabelOf = (field: HistField) =>
		workspace.filters
			.filter((f) => f.field === field)
			.map((f) => f.label)
			.join('; ');
</script>

<div class="hist" data-testid="histogram" data-rows={rows.length}>
	<div class="scope" data-testid="histogram-scope">{L('vw_h_rows', rows.length)}</div>
	<div class="groups">
		{#if !rows.length}
			<NonIdealState icon="horizontal-bar-chart" iconSize={32} title={L('vw_h_empty')} description={L('vw_h_empty_hint')} />
		{:else}
			{#each groups as g (g.field)}
				{#if g.bins.length || g.missing}
					<Section title={g.title} sub={valuesLabel(g.bins.length, lang)} collapsible bind:open={open[g.field]} data-hist-group={g.field} data-values={g.bins.length}>
						{#snippet right()}
							{#if filtered.has(g.field)}
								<Tooltip content={L('vw_h_filtered', filterLabelOf(g.field))}>
									<span class="fglyph" data-testid="histogram-filtered"><Icon name="filter" size={12} /></span>
								</Tooltip>
							{/if}
						{/snippet}
						<div class="bins" role="group" aria-label={g.title}>
							{#each shown(g) as b (b.key)}
								{@const on = isOn(g.field, b.value)}
								<Tooltip content={b.parts ? L('vw_h_osint_hint') : null} placement="right">
									<button
										type="button"
										role="checkbox"
										aria-checked={on}
										class={['bin', on && 'is-selected']}
										data-value={b.value}
										data-n={b.n}
										onclick={() => toggle(g.field, b.value)}
									>
										<span class="box" aria-hidden="true">{#if on}<Icon name="small-tick" size={16} />{/if}</span>
										<span class="lbl">{#if g.field === 'source' && b.value === 'osint'}<Icon name={PROVENANCE_ICON.osint} size={12} />{/if}<span class="lt">{b.label}</span></span>
										<span class="track" aria-hidden="true"><i style:width="{pct(b, g)}%"></i></span>
										<span class="n">{b.n}</span>
									</button>
								</Tooltip>
								{#if b.parts}
									<!-- read, never picked: the store's filters have no verification field -->
									<ul class="parts" aria-label={L('vw_h_parts', b.label)} data-testid="histogram-parts" data-value={b.value}>
										{#each b.parts as p (p.verification ?? '')}
											<li class="part" data-verification={p.verification ?? 'none'} data-n={p.n}>
												<span class="pl">{p.label}</span>
												<span class="n">{p.n}</span>
											</li>
										{/each}
									</ul>
								{/if}
							{/each}
							{#if g.field !== 'hour' && g.bins.length > TOP_VALUES}
								<button type="button" class="more" onclick={() => (more[g.field] = !more[g.field])}>
									{more[g.field] ? L('vw_h_show_less') : L('vw_h_show_more', g.bins.length - TOP_VALUES)}
								</button>
							{/if}
							{#if g.missing && g.field === 'road'}
								<!-- the store's road filter reads the road a row records itself; the Place column also names a camera's road -->
								<Tooltip content={L('vw_h_missing_road_hint')} placement="right">
									<span class="missing" data-missing={g.missing} data-testid="histogram-missing-road">{L('vw_h_missing_road', g.missing)}</span>
								</Tooltip>
							{:else if g.missing}
								<p class="missing" data-missing={g.missing}>{L(g.field === 'hour' ? 'vw_h_missing_time' : 'vw_h_missing', g.missing)}</p>
							{/if}
						</div>
					</Section>
				{/if}
			{/each}
		{/if}
	</div>
	<footer class="foot">
		<Button small disabled={!outFilters} disabledReason={outReason} data-testid="histogram-filter-out" onclick={() => apply(outFilters)}>{L('vw_h_filter_out')}</Button>
		<Button
			small
			intent={anyPicked ? 'primary' : 'none'}
			icon="filter"
			disabled={!anyPicked}
			disabledReason={L('vw_h_select_first')}
			data-testid="histogram-filter-to"
			onclick={() => apply(toFilters)}>{L('vw_h_filter_to')}</Button
		>
		<span class="grow"></span>
		<Button small minimal disabled={!anyPicked} data-testid="histogram-clear" onclick={clear}>{L('vw_h_clear')}</Button>
	</footer>
</div>

<style>
	.hist {
		display: flex;
		flex-direction: column;
		min-height: 100%;
		color: var(--v-ink-1);
		font-family: var(--v-font-ui);
	}

	.scope {
		display: flex;
		align-items: center;
		height: 32px;
		padding: 0 16px;
		border-bottom: 1px solid var(--v-line-2);
		color: var(--v-ink-2);
		font-size: var(--v-text-xs);
		font-variant-numeric: tabular-nums;
		flex: 0 0 auto;
	}

	.groups {
		flex: 1 1 auto;
		min-height: 0;
	}

	.fglyph {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 20px;
		height: 20px;
		border-radius: var(--v-radius-chip);
		background: var(--v-primary-veil);
		color: var(--v-primary-text);
	}

	.fglyph :global([data-ui='icon']) {
		color: var(--v-primary-text);
	}

	.bins {
		display: flex;
		flex-direction: column;
		padding: 0 0 8px;
	}

	.bin {
		display: grid;
		grid-template-columns: 16px minmax(0, 1fr) 64px 32px;
		align-items: center;
		gap: 8px;
		height: 24px;
		margin: 0;
		padding: 0 12px 0 16px;
		border: 0;
		background: transparent;
		color: var(--v-ink-1);
		font: inherit;
		font-size: var(--v-text-xs);
		line-height: 16px;
		text-align: left;
		cursor: pointer;
	}

	.bin:hover {
		background: var(--v-row-hover);
	}

	.bin:focus-visible {
		outline: 2px solid var(--v-focus);
		outline-offset: -2px;
	}

	.box {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 16px;
		height: 16px;
		border-radius: calc(var(--v-radius-chip) - 1px);
		box-shadow: inset 0 0 0 1px var(--v-line-strong);
		color: var(--v-on-fill);
	}

	.bin:hover .box {
		box-shadow: inset 0 0 0 1px var(--v-ink-2);
	}

	.bin.is-selected .box {
		background: var(--v-primary);
		box-shadow: none;
	}

	.box :global([data-ui='icon']) {
		color: var(--v-on-fill);
	}

	.lbl {
		display: flex;
		align-items: center;
		gap: 4px;
		min-width: 0;
	}

	.lbl :global([data-ui='icon']) {
		flex: 0 0 auto;
		color: var(--v-ink-2);
	}

	.lt {
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.track {
		display: flex;
		align-items: center;
		height: 8px;
	}

	.track i {
		display: block;
		height: 8px;
		min-width: 2px;
		border-radius: 2px;
		background: color-mix(in srgb, var(--v-ink-2) 55%, transparent);
	}

	.bin.is-selected .track i {
		background: var(--v-ink-1);
	}

	.n {
		color: var(--v-ink-2);
		font-variant-numeric: tabular-nums;
		text-align: right;
	}

	.bin.is-selected .n {
		color: var(--v-ink-1);
	}

	/* the open-source bar's verification states: indented under its label, no box, no bar — read, never picked */
	.parts {
		margin: 0;
		padding: 0 0 2px;
		list-style: none;
	}

	.part {
		display: grid;
		grid-template-columns: minmax(0, 1fr) 32px;
		align-items: center;
		gap: 8px;
		height: 20px;
		padding: 0 12px 0 52px;
		color: var(--v-ink-2);
		font-size: var(--v-text-xs);
		line-height: 16px;
	}

	.pl {
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.more {
		align-self: flex-start;
		height: 24px;
		margin: 0 0 0 40px;
		padding: 0;
		border: 0;
		background: transparent;
		color: var(--v-primary-text);
		font: inherit;
		font-size: var(--v-text-xs);
		cursor: pointer;
	}

	.more:hover {
		text-decoration: underline;
	}

	.missing {
		display: block;
		margin: 4px 0 0;
		padding: 0 16px 0 40px;
		color: var(--v-ink-2);
		font-size: var(--v-text-xs);
		line-height: 16px;
		font-variant-numeric: tabular-nums;
	}

	.foot {
		position: sticky;
		bottom: 0;
		display: flex;
		align-items: center;
		gap: 8px;
		height: 48px;
		padding: 0 12px;
		border-top: 1px solid var(--v-line-2);
		background: var(--v-surface-1);
		flex: 0 0 auto;
	}

	.grow {
		flex: 1 1 auto;
	}
</style>
