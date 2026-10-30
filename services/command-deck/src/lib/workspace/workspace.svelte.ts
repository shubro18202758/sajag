/**
 * The workspace store (SPEC §7.1, plan X6 — frozen): one view, one set of
 * docks, one time window, one filter set, the pinned objects, saved views,
 * watches and the omnibar's open state. The selection lives beside it in
 * gods-eye/entities/selection.svelte.ts (one selection for every view).
 *
 *   timeWindow     null ⇔ live. setTimeWindow() turns live off; returnToLive()
 *                  clears it. A window never deletes data and never changes
 *                  what the stores poll; protected objects never fade (§7.3).
 *   filters        addFilter / removeFilter / clearFilters
 *   objectSet      derived and memoised (a model rebuild — the 4 s tick — or
 *                  a filter or selection change): (selection ∪ linked) ∩
 *                  filters, or every object ∩ filters when nothing is
 *                  selected or the omnibar's results are explored (a `urns`
 *                  filter); at most 500 objects
 *   protectedHidden  the protected objects the filters hide ("n live objects
 *                  hidden", shown by the frame's filter bar with a Show action)
 *   savedViews     saveView / applyView / renameView / deleteView — masked
 *   watches        addWatch / removeWatch — masked; never mute an interrupt
 *   omnibar        {open, query}: openOmnibar(q?) / closeOmnibar() (plan X25)
 *   toHash/fromHash  the workspace keys of a share link (hash.ts), composed
 *                  with S3's camera/layers/`sel` encoding; URNs only
 *   escape()       Esc: closes, then clears; it never navigates
 */
import { selection } from '$lib/gods-eye/entities/selection.svelte';
import { parseUrn } from '$lib/gods-eye/city-api';
import { FILTER_FIELDS, WORKSPACE_KEYS, decodeWorkspaceKeys, encodeWorkspaceKeys, safeText } from './hash';
import { maskMarks } from './mask';
import { browserStorage, cleanName, loadSavedViews, newSavedView, storeSavedViews } from './saved-views';
import { createSelectors, type World } from './selectors';
import { cleanWatch, loadWatches, newWatchId, passesFilters, storeWatches } from './watches';
import { liveWorld } from './world.svelte';
import type { BottomSize, DecisionUnitSummary, Docks, Filter, ObjectRow, SavedView, View, Watch } from './types';

export const OBJECT_SET_MAX = 500;
export const PINNED_MAX = 6;
/** Below this width only one side dock is open at a time (SPEC §3.7). */
export const ONE_DOCK_BELOW_PX = 1440;

const istHour = new Intl.DateTimeFormat('en-GB', { timeZone: 'Asia/Kolkata', hour: '2-digit', hourCycle: 'h23' });

/** The IST hour bucket of a moment ("20:00"), the Histogram's Hour values. */
export function hourOf(t: number): string {
	return `${istHour.format(t)}:00`;
}

export interface WorkspaceDeps {
	world: () => World;
	storage?: () => Storage | null;
	now?: () => number;
}

interface Memo {
	graph: number;
	filters: readonly Filter[];
	items: readonly string[];
	primary: string | null;
	rows: readonly ObjectRow[];
	hidden: readonly ObjectRow[];
}

let filterSeq = 0;

export class Workspace {
	view = $state<View>('map');
	docks = $state<Docks>({ left: false, right: true, bottom: 'compact' });
	leftTab = $state('');
	rightTab = $state('');
	bottomTab = $state<string>('timeline');
	/** null ⇔ live. */
	timeWindow = $state.raw<[number, number] | null>(null);
	filters = $state.raw<readonly Filter[]>([]);
	/** Inspector tabs (≤ 6). */
	pinned = $state.raw<readonly string[]>([]);
	omnibar = $state({ open: false, query: '' });
	/** The decision unit a link card asked its home to open ({kind, id}, bumped seq). */
	focusDecision = $state.raw<{ kind: string; id: string; seq: number } | null>(null);

	#views = $state.raw<readonly SavedView[]>([]);
	#watches = $state.raw<readonly Watch[]>([]);
	#lastBottom: Exclude<BottomSize, 'off'> = 'compact';
	#memo: Memo | null = null;
	#selectors;

	constructor(private deps: WorkspaceDeps) {
		this.#selectors = createSelectors(deps.world);
		// storage is read once, here: a getter read inside a template never writes state
		const storage = this.#storage();
		this.#views = loadSavedViews(storage);
		this.#watches = loadWatches(storage);
	}

	// ── live ─────────────────────────────────────────────────────────────

	get live(): boolean {
		return this.timeWindow === null;
	}

	/** Set the time window (turns live off). Reversed ends are swapped; a non-finite or empty window is ignored. */
	setTimeWindow(a: number, b: number): void {
		if (!Number.isFinite(a) || !Number.isFinite(b) || a === b) return;
		this.timeWindow = a < b ? [a, b] : [b, a];
	}

	/** Clear the window: live again, the cursor follows now. */
	returnToLive(): void {
		this.timeWindow = null;
	}

	// ── filters ──────────────────────────────────────────────────────────

	/**
	 * Add a filter. Its label and values are MASKED here, in any case and
	 * spelling (mask.ts): a label can carry what an operator typed, and a
	 * filter reaches the share hash and saved views (SPEC §7.5).
	 */
	addFilter(f: Omit<Filter, 'id'>): Filter {
		if (!(FILTER_FIELDS as readonly string[]).includes(f.field)) throw new Error(`unknown filter field: ${String(f.field)}`);
		const values =
			f.field === 'urns'
				? f.values.filter((u) => typeof u === 'string' && !!parseUrn(u))
				: f.values.filter((v) => typeof v === 'string').map((v) => maskMarks(v));
		filterSeq += 1;
		const filter: Filter = {
			id: `flt-${filterSeq}`,
			field: f.field,
			values: values.slice(0, 500),
			label: safeText(f.label, 80) ?? f.field,
		};
		this.filters = [...this.filters, filter];
		return filter;
	}

	removeFilter(id: string): void {
		this.filters = this.filters.filter((f) => f.id !== id);
	}

	clearFilters(): void {
		if (this.filters.length) this.filters = [];
	}

	// ── the object set ───────────────────────────────────────────────────

	get objectSet(): readonly ObjectRow[] {
		return this.#compute().rows;
	}

	/** The protected objects the current filters hide (§7.3). */
	get protectedHidden(): readonly ObjectRow[] {
		return this.#compute().hidden;
	}

	#compute(): Memo {
		const graph = this.deps.world().graph();
		const filters = this.filters;
		const items = selection.items;
		const primary = selection.current;
		const m = this.#memo;
		if (m && m.graph === graph.version && m.filters === filters && m.items === items && m.primary === primary) return m;

		const exploring = filters.some((f) => f.field === 'urns');
		let base: ObjectRow[];
		if (primary && !exploring) {
			const seen = new Set<string>();
			base = [];
			for (const u of [primary, ...items]) {
				const r = graph.get(u);
				if (r && !seen.has(r.urn)) {
					seen.add(r.urn);
					base.push(r);
				}
			}
			for (const r of this.#selectors.linked(primary)) {
				if (seen.has(r.urn)) continue;
				seen.add(r.urn);
				base.push(r);
			}
		} else {
			base = [...graph.all()];
		}
		const rows: ObjectRow[] = [];
		for (const r of base) {
			if (passesFilters(r, filters, hourOf)) rows.push(r);
			if (rows.length >= OBJECT_SET_MAX) break;
		}
		const hidden: ObjectRow[] = [];
		if (filters.length) {
			for (const u of this.#selectors.protectedUrns()) {
				const r = graph.get(u);
				if (r && !passesFilters(r, filters, hourOf)) hidden.push(r);
			}
		}
		const memo = { graph: graph.version, filters, items, primary, rows, hidden };
		this.#memo = memo;
		return memo;
	}

	// ── pins ─────────────────────────────────────────────────────────────

	pin(urn: string): void {
		if (!parseUrn(urn) || this.pinned.includes(urn)) return;
		const next = [...this.pinned, urn];
		this.pinned = next.length > PINNED_MAX ? next.slice(next.length - PINNED_MAX) : next;
	}

	unpin(urn: string): void {
		this.pinned = this.pinned.filter((u) => u !== urn);
	}

	togglePin(urn: string): void {
		if (this.pinned.includes(urn)) this.unpin(urn);
		else this.pin(urn);
	}

	// ── docks ────────────────────────────────────────────────────────────

	/** Open or close a side dock; below 1440 px opening one closes the other. */
	setDock(side: 'left' | 'right', open: boolean, width = viewportWidth()): void {
		const next = { ...this.docks, [side]: open };
		if (open && width < ONE_DOCK_BELOW_PX) next[side === 'left' ? 'right' : 'left'] = false;
		this.docks = next;
	}

	/** `[` and `]` toggle a side dock; `\` shows or hides the bottom dock. */
	toggleDock(side: 'left' | 'right' | 'bottom', width = viewportWidth()): void {
		if (side === 'bottom') {
			const b = this.docks.bottom;
			if (b !== 'off') this.#lastBottom = b;
			this.docks = { ...this.docks, bottom: b === 'off' ? this.#lastBottom : 'off' };
			return;
		}
		this.setDock(side, !this.docks[side], width);
	}

	setBottom(size: BottomSize): void {
		if (size !== 'off') this.#lastBottom = size;
		this.docks = { ...this.docks, bottom: size };
	}

	/** Below 1440 px, keep one side dock (the right one wins) — call on resize. */
	fitDocks(width = viewportWidth()): void {
		if (width < ONE_DOCK_BELOW_PX && this.docks.left && this.docks.right) this.docks = { ...this.docks, left: false };
	}

	// ── the omnibar (plan X25) ───────────────────────────────────────────

	openOmnibar(q?: string): void {
		this.omnibar = { open: true, query: typeof q === 'string' ? q.slice(0, 200) : '' };
	}

	closeOmnibar(): void {
		this.omnibar = { open: false, query: '' };
	}

	// ── Esc ──────────────────────────────────────────────────────────────

	/** Esc: close the omnibar, else clear the selection (the inspector closes). Never navigates. True when it acted. */
	escape(): boolean {
		if (this.omnibar.open) {
			this.closeOmnibar();
			return true;
		}
		if (selection.current || selection.items.length) {
			selection.clear();
			return true;
		}
		return false;
	}

	// ── decision homes (link cards) ──────────────────────────────────────

	/** Open a decision unit's home on `route` (a link card's click): the inbox tab, the movement tab, or the map. */
	openDecisionHome(unit: DecisionUnitSummary, route: '/' | '/gods-eye' | '/ops'): string {
		const home = unit.homes[route] ?? 'inbox';
		this.focusDecision = { kind: unit.kind, id: unit.id, seq: (this.focusDecision?.seq ?? 0) + 1 };
		if (home === 'inbox' || home === 'movement') {
			this.rightTab = home;
			this.setDock('right', true);
		} else if (home === 'map') {
			this.view = this.view === 'graph' ? 'split' : this.view === 'table' ? 'map' : this.view;
		}
		return home;
	}

	// ── share hash (plan R24) ────────────────────────────────────────────

	/**
	 * A share hash: `base` (S3's camera/layers/sel encoding, when the page has
	 * a canvas) with the workspace keys added. URNs only, never a mark.
	 */
	toHash(base = ''): string {
		let params: URLSearchParams;
		try {
			params = new URLSearchParams(base.replace(/^#/, ''));
		} catch {
			params = new URLSearchParams();
		}
		for (const k of WORKSPACE_KEYS) params.delete(k);
		if (!params.has('sel') && selection.current && parseUrn(selection.current)) params.set('sel', selection.current);
		const ws = new URLSearchParams(
			encodeWorkspaceKeys({ view: this.view, timeWindow: this.timeWindow, filters: this.filters, docks: this.docks, items: selection.items }),
		);
		for (const [k, v] of ws) params.set(k, v);
		return params.toString();
	}

	/** Apply a share hash's workspace keys (and its selection). Hostile values are dropped by hash.ts. */
	fromHash(h: string): void {
		let params: URLSearchParams;
		try {
			params = new URLSearchParams(h.replace(/^[#?]/, ''));
		} catch {
			return;
		}
		const keys = decodeWorkspaceKeys(params);
		if (keys.view) this.view = keys.view;
		this.timeWindow = keys.timeWindow ?? null;
		this.filters = (keys.filters ?? []).map((f) => {
			filterSeq += 1;
			return { ...f, id: `flt-${filterSeq}` };
		});
		if (keys.docks) this.docks = keys.docks;
		const sel = params.get('sel');
		const primary = sel && parseUrn(sel) ? sel : null;
		if (keys.items?.length) selection.selectMany(keys.items, { source: 'share', primary });
		else if (primary) selection.select(primary, { source: 'share' });
	}

	// ── saved views (masked, this browser) ───────────────────────────────

	get savedViews(): readonly SavedView[] {
		return this.#views;
	}

	/**
	 * Save the view as it is now (SPEC §7.5: the camera, the layers, the
	 * selection, the filters, the window): the page's own hash — S3's camera
	 * and layers keys — composed with the workspace keys and the current
	 * selection. Masked: newSavedView() cleans it (URNs only, never a mark).
	 */
	saveView(name: string): SavedView {
		const view = newSavedView(name, this.toHash(pageHash()), this.#now());
		this.#views = [view, ...this.#views].slice(0, 50);
		storeSavedViews(this.#storage(), this.#views);
		return view;
	}

	applyView(id: string): void {
		const v = this.savedViews.find((x) => x.id === id);
		if (v) this.fromHash(v.hash);
	}

	renameView(id: string, name: string): void {
		const clean = cleanName(name);
		if (!clean) return;
		this.#views = this.#views.map((v) => (v.id === id ? { ...v, name: clean } : v));
		storeSavedViews(this.#storage(), this.#views);
	}

	deleteView(id: string): void {
		this.#views = this.#views.filter((v) => v.id !== id);
		storeSavedViews(this.#storage(), this.#views);
	}

	// ── watches (masked, this browser; never mute an interrupt) ──────────

	get watches(): readonly Watch[] {
		return this.#watches;
	}

	addWatch(w: Omit<Watch, 'id'>): Watch {
		const watch = cleanWatch({ ...w, id: newWatchId(this.#now()) });
		if (!watch) throw new Error('a watch needs a title and a subject or a filter');
		this.#watches = [...this.#watches, watch].slice(-50);
		storeWatches(this.#storage(), this.#watches);
		return watch;
	}

	removeWatch(id: string): void {
		this.#watches = this.#watches.filter((w) => w.id !== id);
		storeWatches(this.#storage(), this.#watches);
	}

	// ── internals ────────────────────────────────────────────────────────

	#storage(): Storage | null {
		return this.deps.storage ? this.deps.storage() : browserStorage();
	}

	#now(): number {
		return this.deps.now ? this.deps.now() : Date.now();
	}
}

function viewportWidth(): number {
	return typeof window === 'undefined' ? 1920 : window.innerWidth;
}

/** The page's hash (S3's camera and layers keys) without its `sel`: a saved view records the selection as it is now. */
function pageHash(): string {
	if (typeof location === 'undefined') return '';
	try {
		const params = new URLSearchParams(location.hash.replace(/^#/, ''));
		params.delete('sel');
		return params.toString();
	} catch {
		return '';
	}
}

/** THE workspace store (the live world, this browser's storage). */
export const workspace = new Workspace({ world: () => liveWorld });
