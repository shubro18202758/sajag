/**
 * Entity selection — the one "what am I looking at" every view shares: the
 * map, the inspector, the omnibar, the table, the graph and the timeline.
 * Selecting an object in one view selects it in all of them.
 *
 *   current   the primary object (the inspector shows it; the canvas rings
 *             it); null = nothing selected
 *   items     the ordered selection, at most 50 URNs: [] when nothing is
 *             selected, [current] for a single selection, more after an
 *             additive pick (omnibar Shift+Enter, graph Shift+click, table
 *             Ctrl/Shift+click) or a lasso (selectMany)
 *   hover     the URN under the pointer (canvas hover, rail hover)
 *
 *   select(urn, {fly, source, pick, mode})   mode 'replace' (the default:
 *             every existing caller), 'add' (append, the new object becomes
 *             the primary) or 'toggle' (add, or remove when present); `fly`
 *             asks the mounted canvas to fly the camera to the object (a
 *             monotonically increasing request seq, like the focus bus: a
 *             canvas serves only requests made after it mounted)
 *   selectMany(urns, {source, primary})      replace the selection with a
 *             set (lasso, "Explore all", graph box-select); the primary is
 *             `primary` when it is in the set, else the first URN
 *   clear()   nothing selected
 *
 * Only URNs of the C-C grammar are kept (parseUrn): a hostile or malformed
 * string never enters the selection. Event URNs keep the ops store's
 * selection in sync (ops.selectEvent), so the band, audit tail, pursuit
 * overlay and board follow the map. The sync is one-way (map → board): a
 * board auto-selection on load is not a human pick and never opens a dossier
 * on its own.
 */

import { ops } from '$lib/ops/store.svelte';
import { parseUrn } from '../city-api';

/** What the canvas picked to produce a selection (the inspector's map line). */
export interface MapPick {
	pickId: string;
	layer: string;
	text: string;
}

/**
 * Who made the selection: 'agent' = an AI-suggested directive a human
 * applied; 'palette' = ⌘K (legacy name); 'omnibar' = the omnibar; 'chat' =
 * a citation chip a human clicked on the agent console (a human pick from
 * the chat, not an AI suggestion); 'lasso' = a map shape; 'graph', 'table',
 * 'timeline', 'inbox' = those views.
 */
export type SelectionSource =
	| 'map'
	| 'rail'
	| 'dossier'
	| 'tour'
	| 'vitals'
	| 'share'
	| 'replay'
	| 'agent'
	| 'palette'
	| 'chat'
	| 'graph'
	| 'table'
	| 'timeline'
	| 'inbox'
	| 'omnibar'
	| 'lasso';

export type SelectionMode = 'replace' | 'add' | 'toggle';

export type FlyOutcome = 'pending' | 'flying' | 'landed' | 'no-position' | 'no-canvas' | 'cancelled';

/** The most objects one selection holds (SPEC §7.1). */
export const SELECTION_MAX = 50;

class EntitySelection {
	current = $state<string | null>(null);
	/** The ordered selection (≤ 50); [] or [current] for a single selection. */
	items = $state<string[]>([]);
	hover = $state<string | null>(null);
	source = $state<SelectionSource | null>(null);
	/** The canvas pick behind the current selection (null for rail/dossier picks). */
	pick = $state<MapPick | null>(null);
	/** Epoch ms of the newest selection change (dossier staleness, tests). */
	selectedAt = $state(0);

	/** Fly requests: the canvas reacts to each increment. */
	flySeq = $state(0);
	flyUrn = $state<string | null>(null);
	flyOutcome = $state<FlyOutcome | null>(null);
	flyNote = $state<string | null>(null);
	/** Request → landing of the newest fly request (ms, page clock) — the fly-to latency an operator feels. */
	flyLandedMs = $state<number | null>(null);
	private flyRequestedAt = 0;

	/**
	 * Select `urn` (null clears). `mode` defaults to 'replace'; `fly` asks the
	 * canvas to bring the object into view.
	 */
	select(
		urn: string | null,
		opts: { fly?: boolean; source?: SelectionSource; pick?: MapPick | null; mode?: SelectionMode } = {},
	) {
		const parsed = urn ? parseUrn(urn) : null;
		const next = parsed ? urn : null;
		const mode = opts.mode ?? 'replace';
		if (!next) {
			// an invalid URN never enters the selection; with 'replace' it clears it (today's behaviour)
			if (mode === 'replace') this.apply([], null, null, null);
			return;
		}
		if (mode === 'replace') {
			this.apply([next], next, opts.source ?? 'map', opts.pick ?? null);
		} else if (mode === 'toggle' && this.items.includes(next)) {
			const items = this.items.filter((u) => u !== next);
			const primary = this.current === next ? (items[items.length - 1] ?? null) : this.current;
			this.apply(items, primary, primary ? (this.source ?? opts.source ?? 'map') : null, primary === this.current ? this.pick : null);
			return;
		} else {
			// add (or toggle of an absent object): append, the new object becomes the primary
			const items = this.items.filter((u) => u !== next);
			items.push(next);
			this.apply(capItems(items, next), next, opts.source ?? 'map', opts.pick ?? null);
		}
		if (opts.fly) this.requestFly(next);
		this.syncBoard(next);
	}

	/**
	 * Replace the selection with `urns` (deduplicated, invalid ones dropped,
	 * at most 50). The primary is `primary` when it is in the set, else the
	 * first URN.
	 */
	selectMany(urns: readonly string[], opts: { source?: SelectionSource; primary?: string | null } = {}) {
		const seen = new Set<string>();
		const items: string[] = [];
		for (const u of urns) {
			if (typeof u !== 'string' || seen.has(u) || !parseUrn(u)) continue;
			seen.add(u);
			items.push(u);
			if (items.length >= SELECTION_MAX) break;
		}
		const primary = opts.primary && items.includes(opts.primary) ? opts.primary : (items[0] ?? null);
		this.apply(items, primary, primary ? (opts.source ?? 'lasso') : null, null);
		if (primary) this.syncBoard(primary);
	}

	clear() {
		this.select(null);
	}

	/** True when `urn` is in the selection. */
	has(urn: string | null | undefined): boolean {
		return !!urn && this.items.includes(urn);
	}

	/** Canvas → bus: the outcome of fly request `seq` (stale reports dropped). */
	settleFly(seq: number, outcome: FlyOutcome, note: string | null = null) {
		if (seq !== this.flySeq) return;
		this.flyOutcome = outcome;
		this.flyNote = note;
		if (outcome === 'landed') this.flyLandedMs = Math.round(performance.now() - this.flyRequestedAt);
	}

	private apply(items: string[], primary: string | null, source: SelectionSource | null, pick: MapPick | null) {
		this.items = items;
		this.current = primary;
		this.source = primary ? source : null;
		this.pick = primary ? pick : null;
		this.selectedAt = Date.now();
	}

	private requestFly(urn: string) {
		this.flyUrn = urn;
		this.flySeq += 1;
		this.flyOutcome = 'pending';
		this.flyNote = null;
		this.flyLandedMs = null;
		this.flyRequestedAt = performance.now();
	}

	/**
	 * Map → board: an event pick selects the event on the board (only an
	 * event the board carries; re-selecting is a no-op — selectEvent resets
	 * the band and audit tail).
	 */
	private syncBoard(urn: string) {
		const parsed = parseUrn(urn);
		if (parsed?.kind === 'event' && parsed.id !== ops.selectedEventId && ops.events.some((e) => e.eventId === parsed.id)) {
			ops.selectEvent(parsed.id);
		}
	}
}

/** At most 50 items: the oldest go first, never the primary. */
function capItems(items: string[], primary: string): string[] {
	if (items.length <= SELECTION_MAX) return items;
	const out = [...items];
	while (out.length > SELECTION_MAX) {
		const i = out.findIndex((u) => u !== primary);
		if (i < 0) break;
		out.splice(i, 1);
	}
	return out;
}

export const selection = new EntitySelection();
