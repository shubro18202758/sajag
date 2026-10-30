<script lang="ts">
	/**
	 * ObjectTable (SPEC §5.3, §7.3, §8.9, §9.2) — the workspace's table view,
	 * on ui/DataTable (28 px rows, sticky header, virtualised past 200 rows).
	 *
	 * - Rows: `rows` — the selection and its linked objects, an Explorer
	 *   kind, or the omnibar's results. Without props: the shared table scope
	 *   (scope.svelte.ts) — the objectSet rule over the selection another
	 *   view made, so a click in the table never re-scopes it. Whatever the
	 *   rows, the mounted table publishes them to the shared scope, so a
	 *   Histogram without props counts exactly these rows.
	 * - Columns: glyph · Object · Type · State · Time (IST, one format for
	 *   the column) · Place · Speed · Links, and Source only when the rows
	 *   are mixed (non-live rows carry the compact provenance glyph; live rows
	 *   are unmarked). A uniform list states its provenance once, in the
	 *   header. An open-source row states its credibility beside its label,
	 *   and its verification state too whenever the header does not state
	 *   one state for every row (the states differ, or the rows are mixed:
	 *   ethics rule 7 — the label is never left to a glyph's tooltip).
	 *   Place, Speed and Links step aside when the pane is too narrow
	 *   (Columns brings them back).
	 * - Header: "MH47EM•••1 and its 51 linked objects · 50 rows · kind filter"
	 *   (`header` replaces the title part). The selection names the rows only
	 *   when they are its scope; rows the page passed without a `header` are
	 *   named by their kind, or "Objects".
	 * - Fading: with a time window, rows outside it fade to 40 %; protected
	 *   objects and infrastructure never fade (selectors.inWindow).
	 * - Selection: a click replaces, Ctrl/Cmd+click toggles, Shift+click adds
	 *   (selection.select(urn, {mode})); the selection is every view's.
	 * - Empty: an Explorer kind with none linked to the selection says so,
	 *   with "Clear the selection" (every object of the kind then shows).
	 * - Export: a .csv of the rows in view order, ALWAYS masked whatever the
	 *   officer state, with provenance, verification and credibility columns
	 *   (csv.ts); `onExportCsv` hands the export to the page instead.
	 */
	import { onDestroy, untrack } from 'svelte';
	import { ACTION_ICON } from '$lib/design/icons';
	import {
		Button,
		DataTable,
		Icon,
		Menu,
		NonIdealState,
		Popover,
		ProvenanceTag,
		Tag,
		Tooltip,
		provideUiLang,
		type DataColumn,
		type MenuItemSpec,
		type SortState,
	} from '$lib/ui';
	import { t } from '$lib/i18n/strings';
	import '$lib/i18n/packs.views';
	import { commandBar } from '$lib/shell/command-bar.svelte';
	import { selection } from '$lib/gods-eye/entities/selection.svelte';
	import { kindMany, kindOne, shortStateWord, verificationWord } from '../../kinds/generic';
	import { maskMarks } from '../../mask';
	import { localTitle } from '../../display';
	import { liveWorld, selectors } from '../../world.svelte';
	import { workspace } from '../../workspace.svelte';
	import type { ObjectRow } from '../../types';
	import RunsText from '../inspector/RunsText.svelte';
	import { exploredKind } from '../explorer/model';
	import { downloadCsv, toCsv } from './csv';
	import { tableScope } from './scope.svelte';
	import {
		OPTIONAL_COLUMNS,
		clickMode,
		columnKeys,
		emptyReason,
		fades,
		headerMeta,
		isMixed,
		labelRuns,
		placeOf,
		rowVerification,
		speedOf,
		tableTitle,
		tagVerification,
		uniformSource,
		uniformVerification,
		type OptionalColumn,
	} from './model';

	interface Props {
		rows?: readonly ObjectRow[];
		/** The title part of the header (default: the selection and its links, the kind, or the search). */
		header?: string | null;
		onExportCsv?: () => void;
		/** The day that reads as today in the Time column (default now). */
		now?: number;
	}

	let { rows: rowsProp, header = null, onExportCsv, now: nowProp }: Props = $props();

	provideUiLang(() => commandBar.lang);
	const lang = $derived(commandBar.lang);
	const L = (key: string, ...args: unknown[]) => t(lang, key, ...args);

	// default: the shared table scope — a click here changes the selection, never these rows
	const rows = $derived(rowsProp ?? tableScope.rows());
	const graph = $derived(liveWorld.graph());
	const get = (urn: string) => graph.get(urn);
	const win = $derived(workspace.timeWindow);
	const anchor = $derived(nowProp ?? Date.now());

	// the rows in the table, for a Histogram mounted without props (the dock's tab): it counts exactly these
	// (the effect depends on the rows only, never on the published list it writes)
	const tableId = Symbol('object-table');
	$effect(() => {
		const shown = rows;
		untrack(() => tableScope.publish(tableId, shown));
	});
	onDestroy(() => tableScope.release(tableId));

	const mixed = $derived(isMixed(rows));
	const uniform = $derived(uniformSource(rows));
	const uniformVerif = $derived(uniform === 'osint' ? tagVerification('osint', uniformVerification(rows)) : null);
	const prot = $derived(win ? selectors.protectedUrns() : new Set<string>());

	// ── the header ───────────────────────────────────────────────────────
	const exploring = $derived(workspace.filters.some((f) => f.field === 'urns'));
	const kindExplored = $derived(exploredKind(workspace.filters));
	/** The rows are the selection's scope: the default rows, or the store's own objectSet passed through. */
	const selectionScope = $derived(!rowsProp || rowsProp === workspace.objectSet);
	const scopeUrn = $derived(!selectionScope ? null : rowsProp ? selection.current : (tableScope.scope?.primary ?? null));
	const scopeRow = $derived(scopeUrn ? graph.get(scopeUrn) : null);
	const title = $derived(
		tableTitle({
			header,
			selectionScope,
			hasSubject: !!scopeRow,
			exploring,
			exploredKind: kindExplored,
			passed: !!rowsProp,
			rows,
		}),
	);
	const subject = $derived(title.kind === 'subject' ? scopeRow : null);
	const subjectLinks = $derived(subject ? selectors.linked(subject.urn).length : 0);
	const titleText = $derived.by(() => {
		switch (title.kind) {
			case 'header':
				return title.text;
			case 'results':
				return L('vw_t_results');
			case 'kind':
				return kindMany(title.of, lang);
			case 'objects':
				return L('vw_t_objects');
			default:
				return L('vw_t_all_objects');
		}
	});
	const meta = $derived(headerMeta(rows.length, workspace.filters, lang));
	const picked = $derived(selection.items.length);
	const tagged = $derived(!!uniform && uniform !== 'live');

	// ── the empty table explains itself ──────────────────────────────────
	const empty = $derived(emptyReason({ rows: rows.length, exploredKind: kindExplored, subject: !!subject }));

	// ── columns ──────────────────────────────────────────────────────────
	const OPTIONAL = OPTIONAL_COLUMNS;
	type Optional = OptionalColumn;
	let width = $state(0);
	let userHidden = $state<Optional[]>([]);
	let userShown = $state<Optional[]>([]);

	const FIXED: Record<string, number> = { icon: 32, kind: 128, state: 120, t: 112, speed: 84, links: 64, source: 96 };
	const MIN_SHARED = 180;
	/** Optional columns step aside, least useful first, until the rest fits the pane. */
	const autoHidden = $derived.by(() => {
		const out = new Set<Optional>();
		if (!width) return out;
		const floor = () => {
			let px = FIXED.icon + FIXED.kind + FIXED.state + FIXED.t + (mixed ? FIXED.source : 0);
			let shared = 1;
			if (!out.has('speed')) px += FIXED.speed;
			if (!out.has('links')) px += FIXED.links;
			if (!out.has('place')) shared++;
			return px + shared * MIN_SHARED;
		};
		for (const c of ['links', 'speed', 'place'] as const) {
			if (floor() <= width) break;
			out.add(c);
		}
		return out;
	});
	const visible = (c: Optional) => !userHidden.includes(c) && (!autoHidden.has(c) || userShown.includes(c));

	function toggleColumn(c: Optional) {
		if (visible(c)) {
			userShown = userShown.filter((x) => x !== c);
			userHidden = [...userHidden, c];
		} else {
			userHidden = userHidden.filter((x) => x !== c);
			userShown = [...userShown, c];
		}
	}

	const linkCount = (urn: string) => selectors.linked(urn).length;

	/** Every column the table can show; columnKeys() picks them (Source only for mixed rows). */
	const defs = $derived<Record<string, DataColumn<ObjectRow>>>({
		icon: { key: 'icon', icon: true, render: glyphCell },
		label: { key: 'label', title: L('vw_t_col_object'), minWidth: MIN_SHARED, sortable: true, value: (r) => r.label, render: objectCell },
		kind: { key: 'kind', title: L('vw_t_col_type'), width: FIXED.kind, sortable: true, value: (r) => kindOne(r.kind, lang) },
		state: { key: 'state', title: L('vw_t_col_state'), width: FIXED.state, sortable: true, value: (r) => shortStateWord(r.state, lang) ?? '', render: stateCell },
		t: { key: 't', title: L('vw_t_col_time'), width: FIXED.t, sortable: true, time: { anchor }, hint: win ? L('vw_t_window_hint') : undefined },
		place: { key: 'place', title: L('vw_t_col_place'), minWidth: MIN_SHARED, sortable: true, value: (r) => placeOf(r, get) ?? '', format: (v) => (typeof v === 'string' && v ? v : '—') },
		speed: {
			key: 'speed',
			title: L('vw_t_col_speed'),
			width: FIXED.speed,
			num: true,
			sortable: true,
			value: (r) => speedOf(r),
			format: (v) => (typeof v === 'number' ? `${Math.round(v)} ${L('ws_unit_kmh')}` : '—'),
		},
		source: { key: 'source', title: L('vw_t_col_source'), width: FIXED.source, sortable: true, value: (r) => r.source, render: sourceCell, hint: L('vw_t_source_hint') },
		links: { key: 'links', title: L('vw_t_col_links'), width: FIXED.links, num: true, sortable: true, value: (r) => linkCount(r.urn), hint: L('vw_t_links_hint') },
	});
	const columns = $derived(columnKeys(rows, visible).map((k) => defs[k]));

	let sort = $state<SortState | null>({ key: 't', dir: 'desc' });

	const columnItems = $derived<MenuItemSpec[]>(
		OPTIONAL.map((c) => ({
			id: c,
			label: L(`vw_t_col_${c}`),
			selected: visible(c),
			icon: visible(c) ? ACTION_ICON.layer_visible : ACTION_ICON.layer_hidden,
			attrs: { 'data-column': c },
			onclick: () => toggleColumn(c),
		})),
	);

	// ── export ───────────────────────────────────────────────────────────
	/** The rows in the table's own order (its sort), for the export. */
	function viewOrder(): ObjectRow[] {
		const s = sort;
		const col = s ? columns.find((c) => c.key === s.key) : null;
		if (!s || !col) return [...rows];
		const dir = s.dir === 'desc' ? -1 : 1;
		const key = (r: ObjectRow): unknown => (col.key === 't' ? r.t : col.value ? col.value(r) : (r as unknown as Record<string, unknown>)[col.key]);
		const k = new Map(rows.map((r) => [r, key(r)] as const));
		return [...rows].sort((a, b) => {
			const x = k.get(a);
			const y = k.get(b);
			const nx = x == null || x === '';
			const ny = y == null || y === '';
			if (nx || ny) return nx === ny ? 0 : nx ? 1 : -1;
			if (typeof x === 'number' && typeof y === 'number') return (x - y) * dir;
			return String(x).localeCompare(String(y), undefined, { numeric: true, sensitivity: 'base' }) * dir;
		});
	}

	function exportCsv() {
		if (onExportCsv) {
			onExportCsv();
			return;
		}
		downloadCsv(toCsv(viewOrder(), { lang, get, links: linkCount }));
	}

	/** A click selects (every view follows); the table keeps its scope, even when a Ctrl+click empties the selection. */
	function pick(row: ObjectRow, e: MouseEvent | KeyboardEvent) {
		tableScope.select(row.urn, clickMode(e));
	}
</script>

{#snippet glyphCell(r: ObjectRow)}
	<Tooltip content={kindOne(r.kind, lang)}><span class="glyph" data-kind={r.kind}><Icon name={r.icon} /></span></Tooltip>
{/snippet}

{#snippet objectCell(r: ObjectRow)}
	{@const verif = rowVerification(r, uniformVerif)}
	<span class="obj"><RunsText runs={labelRuns(localTitle(r.label, lang))} anchor={anchor} /></span>
	{#if verif}
		<span class="verif" data-testid="object-table-verification" data-verification={verif}>{verificationWord(verif, lang)}</span>
	{/if}
	{#if r.source === 'osint' && r.credibility != null && Number.isFinite(r.credibility)}
		<Tooltip content={L('vw_t_credibility_hint')}><span class="cred" data-testid="object-table-credibility" data-credibility={r.credibility.toFixed(2)}>{L('vw_t_credibility', r.credibility.toFixed(2))}</span></Tooltip>
	{/if}
	{#if r.test}<ProvenanceTag source="test" data-testid="object-table-test" />{/if}
{/snippet}

{#snippet emptyState()}
	{#if empty === 'kind-not-linked' && subject && kindExplored}
		<NonIdealState
			iconSize={20}
			icon="search"
			title={L('vw_t_empty_kind', kindMany(kindExplored, lang), maskMarks(subject.label))}
			description={L('vw_t_empty_kind_hint', kindMany(kindExplored, lang))}
			data-testid="object-table-empty-kind"
		>
			{#snippet action()}<Button small onclick={() => selection.clear()} data-testid="object-table-clear-selection">{L('vw_t_clear_selection')}</Button>{/snippet}
		</NonIdealState>
	{:else}
		<NonIdealState iconSize={20} icon="search" description={L('vw_t_empty')} />
	{/if}
{/snippet}

{#snippet stateCell(r: ObjectRow)}
	{@const word = shortStateWord(r.state, lang)}
	{#if !word}<span class="dash">—</span>
	{:else if r.stateIntent === 'warning' || r.stateIntent === 'success'}<Tag intent={r.stateIntent}>{word}</Tag>
	{:else}<span class="word">{word}</span>{/if}
{/snippet}

{#snippet sourceCell(r: ObjectRow)}
	{#if r.source !== 'live'}<ProvenanceTag source={r.source} verification={tagVerification(r.source, r.verification)} compact />{/if}
{/snippet}

<div class="ot" data-testid="object-table" data-rows={rows.length} data-mixed={mixed} data-source={uniform ?? 'mixed'} bind:clientWidth={width}>
	<header class="head">
		<span class="title" data-testid="object-table-title" data-title={title.kind}>
			{#if subject}<RunsText runs={labelRuns(localTitle(subject.label, lang))} />{` ${L('vw_t_linked', subjectLinks)}`}{:else}{titleText}{/if}
		</span>
		{#if uniform && uniform !== 'live'}
			<span class="sr" aria-hidden="true">{' · '}</span><ProvenanceTag source={uniform} verification={uniformVerif} data-testid="object-table-provenance" />
		{/if}
		<!-- one data separator between the title and the meta ("… linked objects · 50 rows · kind filter");
		     a uniform provenance tag stands between them instead, the separator then only in the text -->
		<span class="meta" data-testid="object-table-meta">
			<span class={['lead', tagged && 'sr']} aria-hidden="true">{' · '}</span>{#each meta as m, i (i)}{#if i}<span class="sep" aria-hidden="true">{' · '}</span>{/if}<span>{m}</span>{/each}
		</span>
		{#if picked > 1}<Tag intent="primary" data-testid="object-table-selected">{L('vw_t_selected', picked)}</Tag>{/if}
		<span class="grow"></span>
		<Popover placement="bottom-end">
			<Button small minimal icon="list-columns" data-testid="object-table-columns">{L('vw_t_columns')}</Button>
			{#snippet content({ close })}
				<Menu items={columnItems} label={L('vw_t_columns')} onselect={() => close()} />
			{/snippet}
		</Popover>
		<Button small minimal icon="export" tooltip={L('vw_t_export_hint')} disabled={!rows.length} data-testid="object-table-export" onclick={exportCsv}>{L('vw_t_export')}</Button>
	</header>
	<DataTable
		class="grid"
		{columns}
		{rows}
		rowKey={(r: ObjectRow) => r.urn}
		selected={selection.items}
		bind:sort
		onselect={(_k, r, e) => pick(r, e)}
		dim={(r: ObjectRow) => fades(r, win, selectors.inWindow)}
		rowAttrs={(r: ObjectRow) => ({
			'data-urn': r.urn,
			'data-kind': r.kind,
			'data-source': r.source,
			'data-faded': win ? String(fades(r, win, selectors.inWindow)) : undefined,
			'data-protected': prot.has(r.urn) ? 'true' : undefined,
		})}
		empty={emptyState}
		caption={L('vw_t_caption')}
		{lang}
	/>
</div>

<style>
	.ot {
		position: absolute;
		inset: 0;
		display: flex;
		flex-direction: column;
		min-width: 0;
		background: var(--v-canvas);
		color: var(--v-ink-1);
		font-family: var(--v-font-ui);
	}

	.head {
		display: flex;
		align-items: center;
		gap: 8px;
		height: 40px;
		padding: 0 8px 0 16px;
		border-bottom: 1px solid var(--v-line-2);
		background: var(--v-surface-1);
		flex: 0 0 auto;
		min-width: 0;
	}

	/* block, not flex: the label's runs (text, Id, Plate) flow inline and keep their spaces */
	.title {
		display: block;
		flex: 0 1 auto;
		min-width: 0;
		overflow: hidden;
		font-size: var(--v-text-base);
		font-weight: 600;
		line-height: 18px;
		white-space: nowrap;
		text-overflow: ellipsis;
	}

	.meta {
		flex: 0 1 auto;
		min-width: 0;
		overflow: hidden;
		color: var(--v-ink-2);
		font-size: var(--v-text-xs);
		font-variant-numeric: tabular-nums;
		white-space: nowrap;
		text-overflow: ellipsis;
	}

	.grow {
		flex: 1 1 auto;
	}

	/* in the text only: tests read textContent ("… linked objects · Emulated · 50 rows"); the separators are
	   aria-hidden, so assistive tech reads the parts without the dots */
	.sr {
		position: absolute;
		width: 1px;
		height: 1px;
		margin: -1px;
		padding: 0;
		overflow: hidden;
		clip: rect(0 0 0 0);
		white-space: nowrap;
		border: 0;
	}

	.ot :global(.grid) {
		flex: 1 1 auto;
		min-height: 0;
	}

	/* Shift+click adds to the selection: it never selects the cells' text */
	.ot :global(tbody) {
		user-select: none;
	}

	.glyph {
		display: inline-flex;
		color: var(--v-ink-2);
	}

	.obj {
		display: block;
		flex: 0 1 auto;
		min-width: 0;
		overflow: hidden;
		white-space: nowrap;
		text-overflow: ellipsis;
	}

	/* an open-source report's verification and credibility stay beside its label: the label gives way first */
	.verif,
	.cred {
		flex: 0 0 auto;
		color: var(--v-ink-2);
		font-size: var(--v-text-xs);
		font-variant-numeric: tabular-nums;
		white-space: nowrap;
	}

	.word {
		overflow: hidden;
		color: var(--v-ink-1);
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.dash {
		color: var(--v-ink-2);
	}
</style>
