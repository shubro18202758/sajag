/**
 * The table's scope (SPEC §5.3, §7.4): the rows the ObjectTable shows when
 * the page gives it none, and the rows the Histogram counts.
 *
 *   rows()     (scope ∪ its linked objects) ∩ filters — the store's
 *              objectSet rule — where the scope is the selection as another
 *              view made it (the map, the inspector, the omnibar, a share
 *              link, a lasso). With no selection, or while the omnibar's
 *              results are explored (a `urns` filter): every object ∩
 *              filters.
 *   inTable()  the rows IN THE TABLE: what the mounted ObjectTable shows
 *              (it publishes its rows — its `rows` prop, or rows()), and
 *              rows() while no table is mounted. A Histogram without props
 *              (the left dock mounts its tabs without props) counts these,
 *              so it always counts exactly the table's rows, whatever the
 *              page passed the table.
 *   select()   a click in the table changes the SELECTION (every view
 *              follows it), never the table under the cursor: a selection
 *              the table itself made keeps the scope it had — a Ctrl+click
 *              that empties the selection included. Another view's pick
 *              (or its clear) moves the scope.
 */
import { selection, type SelectionMode } from '$lib/gods-eye/entities/selection.svelte';
import { liveWorld, selectors } from '../../world.svelte';
import { OBJECT_SET_MAX, workspace } from '../../workspace.svelte';
import type { ObjectRow } from '../../types';
import { scopedRows, type TableScopeState } from './model';

interface Published {
	id: symbol;
	rows: readonly ObjectRow[];
}

class TableScope {
	/** The last selection another view made (plain memory: read inside derivations, never a signal). */
	#last: TableScopeState | null = null;
	#seen = false;
	/**
	 * The selection's items as the table's own newest click left them. The
	 * store makes a new array on every change, so this identity says "the
	 * table made the selection as it is now" — even when that click emptied
	 * it (the store then forgets the source).
	 */
	#ownItems: readonly string[] | null = null;
	/** The tables mounted now, each with the rows it shows (the newest last). */
	#tables = $state.raw<readonly Published[]>([]);

	/** The scope: the selection another view made; a selection made in the table keeps the previous one. */
	get scope(): TableScopeState | null {
		const primary = selection.current;
		const items = selection.items;
		const fromTable = selection.source === 'table' || (this.#ownItems !== null && items === this.#ownItems);
		if (!fromTable || !this.#seen) {
			this.#last = primary ? { primary, items } : null;
			this.#seen = true;
		}
		return this.#last;
	}

	/** The rows the table shows (and the histogram counts) when the page gives them none. */
	rows(): readonly ObjectRow[] {
		return scopedRows(liveWorld.graph(), (u) => selectors.linked(u), this.scope, workspace.filters, OBJECT_SET_MAX);
	}

	/** The rows the mounted table shows (the newest table's), or null when none is mounted. */
	get shown(): readonly ObjectRow[] | null {
		const list = this.#tables;
		return list.length ? list[list.length - 1].rows : null;
	}

	/** The rows in the table: the mounted table's, else the default scope's (what a table would show). */
	inTable(): readonly ObjectRow[] {
		return this.shown ?? this.rows();
	}

	/** A click in the table (a plain click replaces, Ctrl/Cmd toggles, Shift adds): the selection moves, the scope stays. */
	select(urn: string, mode: SelectionMode = 'replace'): void {
		selection.select(urn, { source: 'table', mode });
		this.#ownItems = selection.items;
	}

	/** A mounted table states the rows it shows (called again whenever they change). */
	publish(id: symbol, rows: readonly ObjectRow[]): void {
		const list = this.#tables;
		const i = list.findIndex((p) => p.id === id);
		if (i >= 0 && list[i].rows === rows) return;
		this.#tables = i >= 0 ? list.map((p, j) => (j === i ? { id, rows } : p)) : [...list, { id, rows }];
	}

	/** A table unmounts: its rows stop counting (another mounted table's, if any, count again). */
	release(id: symbol): void {
		if (this.#tables.some((p) => p.id === id)) this.#tables = this.#tables.filter((p) => p.id !== id);
	}
}

export const tableScope = new TableScope();
