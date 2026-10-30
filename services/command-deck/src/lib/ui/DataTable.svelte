<script lang="ts" generics="R">
	/**
	 * DataTable (SPEC §3.6, §5.1) — the dense table of the workspace.
	 *
	 * - 28 px rows at 12 px under a sticky 30 px header; `density="two-line"`
	 *   gives 44 px rows with a muted second line per cell (decided items).
	 * - every cell wraps its content in `.c`, a flex row on a 16 px line box,
	 *   so glyphs never need vertical-align offsets; the `icon` column is a
	 *   fixed 32 px with overflow visible (never ellipsised).
	 * - one format per column: a `time` column renders every value through
	 *   colStamp() (IST; hh:mm, or the dated form on every row once the days
	 *   differ) and sorts by the instant; `format` is a per-column text hook;
	 *   a bare Date value still renders in IST (fmtStamp), never as UTC ISO.
	 * - selection: `selected` keys get .is-selected (the data active-state
	 *   rule: ONE primary veil on the row and a 2 px left bar); onselect on
	 *   click and on Enter/Space; Up/Down move and select.
	 * - sort: sortable headers toggle asc/desc (aria-sort); the table sorts
	 *   unless `manualSort` (then the caller sorts on onsort).
	 * - expandable: a detail row under a row (the `expandable` snippet),
	 *   toggled by the leading chevron, Right/Left or Space.
	 * - virtual: past 200 rows (`virtual="auto"`) only the rows in view are
	 *   in the DOM; expanded detail heights are measured.
	 * - rowAttrs adds data-* hooks per row; `dim` fades rows (outside the
	 *   time window).
	 * - widths: a px `width` is fixed; the other columns share what is left
	 *   but never shrink below their `minWidth` (default 64 px): past that
	 *   floor the table widens and the root scrolls sideways (a 344 px dock,
	 *   a 1366 px screen) instead of crushing a column to "S.".
	 * - rowKey(row, index) gets the row's index in `rows`, never its sorted
	 *   position, so a selection or an open detail stays with its row when
	 *   the sort changes (a stable id is still the better key).
	 *
	 * The root is the scroll viewport: give it a height (or `height`).
	 */
	import type { Snippet } from 'svelte';
	import type { HTMLAttributes } from 'svelte/elements';
	import Icon from './Icon.svelte';
	import NonIdealState from './NonIdealState.svelte';
	import Tooltip from './Tooltip.svelte';
	import { colStamp, fmtStamp, toMs, type Moment } from './format/format';
	import { uiLang, ut } from './lang';
	import type { DataColumn, SortState } from './types';

	interface Props extends Omit<HTMLAttributes<HTMLDivElement>, 'onselect' | 'ontoggle'> {
		columns: readonly DataColumn<R>[];
		rows: readonly R[];
		rowKey: (row: R, index: number) => string;
		selected?: ReadonlySet<string> | readonly string[] | string | null;
		onselect?: (key: string, row: R, e: MouseEvent | KeyboardEvent) => void;
		sort?: SortState | null;
		onsort?: (sort: SortState | null) => void;
		manualSort?: boolean;
		density?: 'compact' | 'two-line';
		virtual?: boolean | 'auto';
		expandable?: Snippet<[R]>;
		expanded?: readonly string[];
		ontoggle?: (key: string, open: boolean) => void;
		dim?: (row: R) => boolean;
		rowAttrs?: (row: R) => Record<string, string | undefined>;
		empty?: Snippet | string | null;
		height?: string;
		caption?: string;
		lang?: string;
	}

	let {
		columns,
		rows,
		rowKey,
		selected = null,
		onselect,
		sort = $bindable(null),
		onsort,
		manualSort = false,
		density = 'compact',
		virtual = 'auto',
		expandable,
		expanded = $bindable([]),
		ontoggle,
		dim,
		rowAttrs,
		empty = null,
		height,
		caption,
		lang,
		class: cls = '',
		...rest
	}: Props = $props();

	const ctxLang = uiLang();
	const L = $derived(lang ?? ctxLang());

	const OVERSCAN = 8;
	const rowH = $derived(density === 'two-line' ? 44 : 28);

	// ── sorting ────────────────────────────────────────────────────────────
	function valueOf(col: DataColumn<R>, row: R): unknown {
		return col.value ? col.value(row) : (row as Record<string, unknown>)[col.key];
	}

	/** The sort key: a time column sorts by the instant (epoch ms). */
	function sortKey(col: DataColumn<R>, row: R): unknown {
		const v = valueOf(col, row);
		return col.time ? toMs(v as Moment) : v;
	}

	function compare(a: unknown, b: unknown): number {
		const na = a == null || a === '' || (typeof a === 'number' && Number.isNaN(a));
		const nb = b == null || b === '' || (typeof b === 'number' && Number.isNaN(b));
		if (na || nb) return na === nb ? 0 : na ? 1 : -1;
		if (typeof a === 'number' && typeof b === 'number') return a - b;
		if (a instanceof Date && b instanceof Date) return a.getTime() - b.getTime();
		return String(a).localeCompare(String(b), undefined, { numeric: true, sensitivity: 'base' });
	}

	/** The rows' indices in `rows`, in display order (a stable sort). */
	const order = $derived.by(() => {
		const idx = rows.map((_, i) => i);
		if (manualSort || !sort) return idx;
		const col = columns.find((c) => c.key === sort?.key);
		if (!col) return idx;
		const dir = sort.dir === 'desc' ? -1 : 1;
		const k = rows.map((r) => sortKey(col, r));
		return idx.sort((a, b) => compare(k[a], k[b]) * dir || a - b);
	});
	const sorted = $derived(order.map((i) => rows[i]));

	// ── time columns: one format for the whole column (colStamp, IST) ──────
	const stamps = $derived.by(() => {
		const out = new Map<string, Map<R, string>>();
		for (const c of columns) {
			if (!c.time) continue;
			const opts = typeof c.time === 'object' ? c.time : {};
			const list = rows.map((r) => valueOf(c, r) as Moment);
			const text = colStamp(list, opts.anchor ?? Date.now(), { seconds: opts.seconds });
			const byRow = new Map<R, string>();
			rows.forEach((r, i) => byRow.set(r, text[i]));
			out.set(c.key, byRow);
		}
		return out;
	});

	function sortBy(col: DataColumn<R>) {
		if (!col.sortable) return;
		const next: SortState = sort?.key === col.key && sort.dir === 'asc' ? { key: col.key, dir: 'desc' } : { key: col.key, dir: 'asc' };
		sort = next;
		onsort?.(next);
	}

	// ── selection, expansion ─────────────────────────────────────────────
	// the key gets the row's own index, so an index-based rowKey survives a re-sort
	const keys = $derived(order.map((i) => rowKey(rows[i], i)));
	const selectedSet = $derived(
		selected == null
			? new Set<string>()
			: typeof selected === 'string'
				? new Set([selected])
				: new Set(selected as Iterable<string>)
	);
	const openSet = $derived(new Set(expanded));

	function toggle(key: string) {
		const open = !openSet.has(key);
		expanded = open ? [...expanded, key] : expanded.filter((k) => k !== key);
		ontoggle?.(key, open);
	}

	// ── virtualisation ───────────────────────────────────────────────────
	let scrollEl: HTMLDivElement | undefined = $state();
	let scrollTop = $state(0);
	let viewH = $state(0);
	let headH = $state(30);
	let detailH = $state<Record<string, number>>({});

	const isVirtual = $derived(virtual === true || (virtual === 'auto' && sorted.length > 200));
	const tops = $derived.by(() => {
		const out = new Array<number>(keys.length + 1);
		out[0] = 0;
		for (let i = 0; i < keys.length; i++) {
			const extra = expandable && openSet.has(keys[i]) ? (detailH[keys[i]] ?? 0) : 0;
			out[i + 1] = out[i] + rowH + extra;
		}
		return out;
	});

	function firstAtOrAfter(y: number): number {
		let lo = 0;
		let hi = keys.length;
		while (lo < hi) {
			const mid = (lo + hi) >> 1;
			if (tops[mid + 1] <= y) lo = mid + 1;
			else hi = mid;
		}
		return lo;
	}

	const range = $derived.by(() => {
		if (!isVirtual) return { start: 0, end: keys.length };
		const top = Math.max(0, scrollTop - headH);
		const bottom = top + (viewH || 600);
		const start = Math.max(0, firstAtOrAfter(top) - OVERSCAN);
		const end = Math.min(keys.length, firstAtOrAfter(bottom) + 1 + OVERSCAN);
		return { start, end };
	});
	const padTop = $derived(isVirtual ? tops[range.start] : 0);
	const padBottom = $derived(isVirtual ? tops[keys.length] - tops[range.end] : 0);
	const visible = $derived(sorted.slice(range.start, range.end));
	const colCount = $derived(columns.length + (expandable ? 1 : 0));

	// ── keyboard ─────────────────────────────────────────────────────────
	let focusIndex = $state(-1);

	function rowEl(i: number): HTMLElement | null {
		return scrollEl?.querySelector<HTMLElement>(`tr[data-row-index="${i}"]`) ?? null;
	}

	function focusRow(i: number) {
		if (i < 0 || i >= keys.length) return;
		focusIndex = i;
		const el = rowEl(i);
		if (el) {
			el.focus({ preventScroll: false });
			return;
		}
		if (scrollEl) scrollEl.scrollTop = Math.max(0, tops[i] - (viewH || 600) / 2);
		requestAnimationFrame(() => rowEl(i)?.focus());
	}

	function onRowKey(e: KeyboardEvent, i: number, key: string, row: R) {
		if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
			const j = i + (e.key === 'ArrowDown' ? 1 : -1);
			if (j < 0 || j >= keys.length) return;
			e.preventDefault();
			focusRow(j);
			onselect?.(keys[j], sorted[j], e);
		} else if (e.key === 'Enter') {
			e.preventDefault();
			onselect?.(key, row, e);
		} else if (e.key === ' ' && expandable) {
			e.preventDefault();
			toggle(key);
		} else if (e.key === 'ArrowRight' && expandable && !openSet.has(key)) {
			e.preventDefault();
			toggle(key);
		} else if (e.key === 'ArrowLeft' && expandable && openSet.has(key)) {
			e.preventDefault();
			toggle(key);
		} else if (e.key === 'Home' || e.key === 'End') {
			e.preventDefault();
			focusRow(e.key === 'Home' ? 0 : keys.length - 1);
		}
	}

	const tabStop = $derived.by(() => {
		let t = focusIndex;
		if (t < 0 || t >= keys.length) {
			const sel = keys.findIndex((k) => selectedSet.has(k));
			t = sel >= 0 ? sel : 0;
		}
		// a virtual table renders only the rows near the view: when the tab
		// stop has scrolled out of the DOM, the first rendered row takes it,
		// so Tab always reaches the table
		return t >= range.start && t < range.end ? t : range.start;
	});

	/** A default cell's text: the column's format hook, its stamp, else the value (a Date in IST). */
	function cellText(c: DataColumn<R>, row: R): string {
		const v = valueOf(c, row);
		if (c.format) return c.format(v, row);
		if (c.time) return stamps.get(c.key)?.get(row) ?? '—';
		if (v == null || v === '') return '—';
		if (v instanceof Date) return fmtStamp(v);
		return String(v);
	}

	const widthOf = (c: DataColumn<R>) =>
		c.icon ? '32px' : typeof c.width === 'number' ? `${c.width}px` : (c.width ?? undefined);

	// ── widths: never crush a column ─────────────────────────────────────
	const MIN_COL = 64;
	const XCOL = 28;
	/** A column's fixed width in px, or null when it shares the room left (no width, or a % / rem width). */
	function fixedPx(c: DataColumn<R>): number | null {
		if (c.icon) return 32;
		if (typeof c.width === 'number') return c.width;
		const m = typeof c.width === 'string' ? /^\s*(\d+(?:\.\d+)?)px\s*$/.exec(c.width) : null;
		return m ? Number(m[1]) : null;
	}
	const minOf = (c: DataColumn<R>) => fixedPx(c) ?? Math.max(0, c.minWidth ?? MIN_COL);
	/**
	 * The table's floor: the fixed columns, plus the shared ones' count times
	 * their largest minimum. A fixed layout splits the room that is left
	 * equally, so at this width every shared column gets at least its own
	 * minimum; below it the root scrolls sideways.
	 */
	const tableMin = $derived.by(() => {
		let fixed = expandable ? XCOL : 0;
		let shared = 0;
		let widest = 0;
		for (const c of columns) {
			const px = fixedPx(c);
			if (px != null) fixed += px;
			else {
				shared++;
				widest = Math.max(widest, minOf(c));
			}
		}
		return Math.round(fixed + shared * widest);
	});
</script>

<div
	data-ui="data-table"
	class={['wrap', density === 'two-line' && 'two-line', cls]}
	style:height
	bind:this={scrollEl}
	bind:clientHeight={viewH}
	onscroll={() => (scrollTop = scrollEl?.scrollTop ?? 0)}
	{...rest}
>
	<table
		class="dt"
		style:width="max(100%, {tableMin}px)"
		role={onselect ? 'grid' : undefined}
		aria-rowcount={isVirtual ? keys.length + 1 : undefined}
		aria-label={caption}
	>
		<colgroup>
			{#if expandable}<col style:width="{XCOL}px" />{/if}
			{#each columns as c (c.key)}<col style:width={widthOf(c)} />{/each}
		</colgroup>
		<thead bind:offsetHeight={headH}>
			<tr aria-rowindex={isVirtual ? 1 : undefined}>
				{#if expandable}<th class="xcol" aria-hidden="true"></th>{/if}
				{#each columns as c (c.key)}
					{@const sorted_ = sort?.key === c.key}
					<th
						scope="col"
						class={['th', c.icon && 'ic-col', (c.num || c.align === 'right') && 'num', c.align === 'center' && 'center', sorted_ && 'sorted']}
						aria-sort={sorted_ ? (sort?.dir === 'desc' ? 'descending' : 'ascending') : c.sortable ? 'none' : undefined}
						data-min-width={c.icon ? undefined : minOf(c)}
					>
						{#snippet head()}
							{#if c.sortable}
								<button type="button" class="thb" onclick={() => sortBy(c)} aria-label={ut(L, 'ui_sort_by', c.title ?? c.key)}>
									<span class="tht">{c.title ?? ''}</span>
									{#if sorted_}<Icon name={sort?.dir === 'desc' ? 'caret-down' : 'caret-up'} size={16} />{/if}
								</button>
							{:else}
								<span class="tht">{c.title ?? ''}</span>
							{/if}
						{/snippet}
						{#if c.hint}<Tooltip content={c.hint}>{@render head()}</Tooltip>{:else}{@render head()}{/if}
					</th>
				{/each}
			</tr>
		</thead>
		<tbody>
			{#if padTop > 0}<tr class="pad" aria-hidden="true"><td colspan={colCount} style:height="{padTop}px"></td></tr>{/if}
			{#each visible as row, j (keys[range.start + j])}
				{@const i = range.start + j}
				{@const key = keys[i]}
				{@const isOpen = !!expandable && openSet.has(key)}
				<tr
					class={['row', selectedSet.has(key) && 'is-selected', dim?.(row) && 'dim', !!onselect && 'pick']}
					data-row-index={i}
					data-key={key}
					aria-rowindex={isVirtual ? i + 2 : undefined}
					aria-selected={onselect ? selectedSet.has(key) : undefined}
					aria-expanded={expandable ? isOpen : undefined}
					tabindex={i === tabStop ? 0 : -1}
					onclick={(e) => onselect?.(key, row, e)}
					onkeydown={(e) => onRowKey(e, i, key, row)}
					onfocus={() => (focusIndex = i)}
					{...rowAttrs?.(row)}
				>
					{#if expandable}
						<td class="xcol">
							<button
								type="button"
								class="xbtn"
								tabindex="-1"
								aria-label={ut(L, isOpen ? 'ui_hide_details' : 'ui_show_details')}
								onclick={(e) => {
									e.stopPropagation();
									toggle(key);
								}}
							>
								<Icon name={isOpen ? 'chevron-down' : 'chevron-right'} size={16} />
							</button>
						</td>
					{/if}
					{#each columns as c (c.key)}
						<td
							class={[
								'cell',
								c.icon && 'ic-col',
								(c.num || c.align === 'right') && 'num',
								c.align === 'center' && 'center',
								c.time && 'time'
							]}
						>
							{#if density === 'two-line' && !c.icon}
								<!-- each line is a .c row (SPEC §3.6); line 1 at 14 px, line 2 at 12 px -->
								<div class="c l1">
									{#if c.render}{@render c.render(row)}{:else}<span class="txt">{cellText(c, row)}</span>{/if}
								</div>
								{#if c.render2 || c.line2}
									<div class="c l2">
										{#if c.render2}{@render c.render2(row)}{:else}<span class="txt">{c.line2?.(row) ?? ''}</span>{/if}
									</div>
								{/if}
							{:else}
								<div class="c">
									{#if c.render}{@render c.render(row)}{:else}<span class="txt">{cellText(c, row)}</span>{/if}
								</div>
							{/if}
						</td>
					{/each}
				</tr>
				{#if isOpen && expandable}
					<tr class="detail" bind:offsetHeight={detailH[key]}>
						<td colspan={colCount}>{@render expandable(row)}</td>
					</tr>
				{/if}
			{/each}
			{#if padBottom > 0}<tr class="pad" aria-hidden="true"><td colspan={colCount} style:height="{padBottom}px"></td></tr>{/if}
			{#if sorted.length === 0}
				<tr class="empty">
					<td colspan={colCount}>
						{#if typeof empty === 'function'}{@render empty()}{:else}
							<NonIdealState iconSize={20} icon="search" description={empty ?? ut(L, 'ui_table_empty')} />
						{/if}
					</td>
				</tr>
			{/if}
		</tbody>
	</table>
</div>

<style>
	.wrap {
		position: relative;
		min-height: 0;
		overflow: auto;
		color: var(--v-ink-1);
		font-family: var(--v-font-ui);
	}

	/* the deck's custom scrollbar sets only a width, so a sideways bar would
	   take the native 15 px: a table past its floor scrolls on the deck's 6 px */
	.wrap::-webkit-scrollbar {
		height: 6px;
	}

	/* width: max(100%, the floor of the fixed widths and minimums), set inline */
	.dt {
		width: 100%;
		border-collapse: separate;
		border-spacing: 0;
		table-layout: fixed;
		font-size: var(--v-text-xs);
		line-height: calc(var(--v-text-xs) + 4px);
	}

	.th {
		position: sticky;
		top: 0;
		z-index: 1;
		height: 30px;
		padding: 0 8px;
		border-bottom: 1px solid var(--v-line-2);
		background: var(--v-surface-1);
		color: var(--v-ink-2);
		font-weight: 400;
		text-align: left;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.th.sorted {
		color: var(--v-ink-1);
	}

	.thb {
		display: inline-flex;
		align-items: center;
		gap: 2px;
		max-width: 100%;
		margin: 0;
		padding: 0;
		border: 0;
		background: transparent;
		color: inherit;
		font: inherit;
		cursor: pointer;
	}

	.thb:hover {
		color: var(--v-ink-1);
	}

	.thb:focus-visible {
		outline: 2px solid var(--v-focus);
	}

	.tht {
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.num .thb {
		flex-direction: row-reverse;
	}

	.cell {
		height: 28px;
		padding: 0 8px;
		border-bottom: 1px solid var(--v-line-1);
		overflow: hidden;
		vertical-align: middle;
		white-space: nowrap;
	}

	.c {
		display: flex;
		align-items: center;
		gap: 6px;
		min-width: 0;
		line-height: 16px;
	}

	.c :global([data-ui='icon']) {
		color: var(--v-ink-2);
	}

	.txt {
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.num,
	.time {
		font-variant-numeric: tabular-nums;
	}

	.num {
		text-align: right;
	}

	.num .c {
		justify-content: flex-end;
	}

	.center {
		text-align: center;
	}

	.center .c {
		justify-content: center;
	}

	/* the fixed 32 px glyph column: visible overflow, no ellipsis */
	.ic-col {
		padding: 0 0 0 8px;
		overflow: visible;
		text-overflow: clip;
	}

	.xcol {
		width: 28px;
		padding: 0 0 0 4px;
		border-bottom: 1px solid var(--v-line-1);
	}

	.th.xcol,
	thead .xcol {
		position: sticky;
		top: 0;
		z-index: 1;
		height: 30px;
		border-bottom: 1px solid var(--v-line-2);
		background: var(--v-surface-1);
	}

	.xbtn {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 20px;
		height: 20px;
		padding: 0;
		border: 0;
		border-radius: var(--v-radius-chip);
		background: transparent;
		color: var(--v-ink-2);
		cursor: pointer;
	}

	.xbtn:hover {
		background: var(--v-minimal-hover);
		color: var(--v-ink-1);
	}

	.row {
		outline: 0;
	}

	.pick {
		cursor: pointer;
	}

	.row:hover > td {
		background: var(--v-row-hover);
	}

	.row:focus-visible > td {
		box-shadow: inset 0 1px 0 var(--v-focus), inset 0 -1px 0 var(--v-focus);
	}

	/* the data active-state rule: ONE veil, on the row (the same value the
	   root layout's global .is-selected gives it, so the two never stack);
	   the cells stay clear and the first one draws the 2 px left bar */
	.row.is-selected {
		background: var(--v-primary-veil);
	}

	.row.is-selected > td:first-child {
		box-shadow: inset 2px 0 0 var(--v-primary-text);
	}

	.dim > td {
		opacity: 0.4;
	}

	/* two-line rows (decided items) */
	.two-line .cell {
		height: 44px;
		white-space: normal;
	}

	.l1,
	.l2 {
		overflow: hidden;
		white-space: nowrap;
	}

	.c.l1 {
		font-size: var(--v-text-base);
		line-height: calc(var(--v-text-base) + 4px);
	}

	.l2 {
		margin-top: 2px;
		color: var(--v-ink-2);
	}

	.num .l1,
	.num .l2 {
		justify-content: flex-end;
	}

	.detail > td {
		padding: 0;
		border-bottom: 1px solid var(--v-line-1);
		background: var(--v-surface-1);
		white-space: normal;
		cursor: default;
	}

	.pad > td {
		padding: 0;
		border: 0;
	}

	.empty > td {
		border: 0;
	}
</style>
