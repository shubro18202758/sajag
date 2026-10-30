/**
 * Canonical selectors (SPEC §7.4, review A6): one function per quantity,
 * and every label states its scope word, so different scopes may give
 * different numbers on purpose and the label always says which.
 *
 *   linked(urn)          "linked" — 1-hop objects, the selection excluded
 *   reads(vehicleUrn)    "reads" — the vehicle's lawful, retained reads
 *   count(kind)          the registry count (the layer tree shows the same)
 *   inWindow(o, w)       "in window" — protected objects never fade (§7.3)
 *   feedIn(a, b)         "in view" — city feed rows in [a, b]
 *   decisionUnits()      "decisions" — every registered unit source,
 *                        concatenated, each unit counted once
 *   watchReads(a, b)     "watchlist reads" — ANPR hits in [a, b]
 *
 * The selectors read a World: the live one (world.svelte.ts: the city
 * registry, the recent dossiers, the registered sources, the city feed) or a
 * fixture (tests/workspace.unit.mjs). They are pure over it.
 */
import { t } from '$lib/i18n/strings';
import '$lib/i18n/packs.workspace';
import type { FeedRow } from '$lib/gods-eye/city-api';
import type { DecisionUnitSummary, ObjectGraph, ObjectLink, ObjectRow } from './types';

/**
 * THE definition of a vehicle's reads (SPEC §7.4): every object linked to it
 * that is a sighting with a time, each once, oldest first — whatever
 * relation names the link. `reads(vehicleUrn)` and the vehicle's "Reads"
 * figure both count exactly this.
 */
export function readsOf(links: readonly ObjectLink[], self?: string | null): ObjectRow[] {
	const seen = new Set<string>(self ? [self] : []);
	const out: ObjectRow[] = [];
	for (const l of links) {
		if (seen.has(l.row.urn)) continue;
		seen.add(l.row.urn);
		if (l.row.kind === 'sighting' && l.row.t != null) out.push(l.row);
	}
	return out.sort((a, b) => (a.t ?? 0) - (b.t ?? 0));
}

/** What the selectors read. */
export interface World {
	graph(): ObjectGraph;
	/** The rows of the registry snapshot (count(kind) reads these). */
	registry(): readonly ObjectRow[];
	/** The city feed rows loaded (newest first or any order). */
	feed(): readonly FeedRow[];
	/** Every registered decision-unit source's units, concatenated. */
	units(): readonly DecisionUnitSummary[];
	now(): number;
}

/** Kinds that carry a time and fade outside a window; infrastructure never fades. */
export const TIMED_KINDS: ReadonlySet<string> = new Set(['sighting', 'recommendation', 'anomaly', 'event', 'dispatch', 'osint_event']);

/** A vehicle read on the watchlist within this long is protected (§7.3). */
export const WATCH_READ_PROTECT_MS = 30 * 60_000;

const OPEN_EVENT_STATES = new Set(['active', 'planning', 'planned', 'live', 'open']);

export interface Selectors {
	linked(urn: string | null | undefined): ObjectRow[];
	/** linked(urn) grouped by relation (Σ groups = linked). */
	linkGroups(urn: string | null | undefined): Map<string, ObjectRow[]>;
	reads(vehicleUrn: string | null | undefined): ObjectRow[];
	count(kind: string): number;
	protectedUrns(): Set<string>;
	inWindow(o: ObjectRow, w: readonly [number, number] | null | undefined): boolean;
	feedIn(a: number, b: number): FeedRow[];
	/** Feed rows in [a, b] that name the selection or one of its linked objects ("Linked n"). */
	linkedFeedIn(urn: string | null | undefined, a: number, b: number): FeedRow[];
	decisionUnits(): DecisionUnitSummary[];
	watchReads(a: number, b: number): FeedRow[];
}

/** The canonical selectors over a world (live or fixture). */
export function createSelectors(world: () => World): Selectors {
	const linked = (urn: string | null | undefined): ObjectRow[] => {
		if (!urn) return [];
		const seen = new Set<string>([urn]);
		const out: ObjectRow[] = [];
		for (const l of world().graph().links(urn)) {
			if (seen.has(l.row.urn)) continue;
			seen.add(l.row.urn);
			out.push(l.row);
		}
		return out;
	};

	const linkGroups = (urn: string | null | undefined): Map<string, ObjectRow[]> => {
		const groups = new Map<string, ObjectRow[]>();
		if (!urn) return groups;
		const seen = new Set<string>([urn]);
		for (const l of world().graph().links(urn)) {
			if (seen.has(l.row.urn)) continue;
			seen.add(l.row.urn);
			const list = groups.get(l.relation);
			if (list) list.push(l.row);
			else groups.set(l.relation, [l.row]);
		}
		return groups;
	};

	const decisionUnits = (): DecisionUnitSummary[] => {
		const seen = new Set<string>();
		const out: DecisionUnitSummary[] = [];
		for (const u of world().units()) {
			if (!u || typeof u.id !== 'string') continue;
			const key = `${u.kind}:${u.id}`;
			if (seen.has(key)) continue;
			seen.add(key);
			out.push(u);
		}
		return out.sort((a, b) => (a.deadline ?? Infinity) - (b.deadline ?? Infinity) || b.severity - a.severity);
	};

	// protectedUrns is read once per row by inWindow: memoised per model build, feed, units and minute
	let memo: { key: string; set: Set<string> } | null = null;
	const feedIds = new WeakMap<object, number>();
	let feedSeq = 0;
	const feedId = (rows: readonly FeedRow[]) => {
		let id = feedIds.get(rows);
		if (id == null) feedIds.set(rows, (id = ++feedSeq));
		return id;
	};

	const protectedUrns = (): Set<string> => {
		const w = world();
		const g = w.graph();
		const units = decisionUnits();
		const key = `${g.version}|${feedId(w.feed())}|${units.map((u) => u.subjectUrn).join(',')}|${Math.floor(w.now() / 60_000)}`;
		if (memo?.key === key) return memo.set;
		const out = new Set<string>();
		for (const ev of g.byKind('event')) {
			const kind = ev.props.event_kind;
			const open = ev.state == null || OPEN_EVENT_STATES.has(ev.state);
			if (!open) continue;
			if (kind === 'protected_movement') {
				out.add(ev.urn);
				for (const l of g.links(ev.urn)) if (l.row.kind === 'convoy' || l.relation === 'route_segment' || l.relation === 'convoy') out.add(l.row.urn);
			}
			if (kind === 'vehicle_pursuit') {
				out.add(ev.urn);
				for (const l of g.links(ev.urn)) if (l.row.kind === 'vehicle') out.add(l.row.urn);
			}
		}
		for (const c of g.byKind('convoy')) out.add(c.urn);
		for (const u of units) if (u.subjectUrn) out.add(u.subjectUrn);
		const since = w.now() - WATCH_READ_PROTECT_MS;
		for (const f of w.feed()) {
			if (f.kind !== 'anpr' || f.t < since) continue;
			for (const u of f.urns) if (u.startsWith('vehicle:')) out.add(u);
		}
		memo = { key, set: out };
		return out;
	};

	const inRange = (f: FeedRow, a: number, b: number) => f.t >= a && f.t <= b;

	return {
		linked,
		linkGroups,
		reads(vehicleUrn) {
			return vehicleUrn ? readsOf(world().graph().links(vehicleUrn), vehicleUrn) : [];
		},
		count(kind) {
			return world()
				.registry()
				.filter((o) => o.kind === kind && !o.test).length;
		},
		protectedUrns,
		inWindow(o, w) {
			if (!w) return true;
			if (!TIMED_KINDS.has(o.kind) || o.t == null) return true;
			if (protectedUrns().has(o.urn)) return true;
			const end = o.end != null && o.end > o.t ? o.end : o.t;
			return end >= w[0] && o.t <= w[1];
		},
		feedIn(a, b) {
			return world()
				.feed()
				.filter((f) => inRange(f, a, b));
		},
		linkedFeedIn(urn, a, b) {
			if (!urn) return [];
			const scope = new Set([urn, ...linked(urn).map((o) => o.urn)]);
			return world()
				.feed()
				.filter((f) => inRange(f, a, b) && f.urns.some((u) => scope.has(u)));
		},
		decisionUnits,
		watchReads(a, b) {
			return world()
				.feed()
				.filter((f) => f.kind === 'anpr' && inRange(f, a, b));
		},
	};
}

// ── labels: every count says its scope ─────────────────────────────────────

/** "51 linked" */
export function linkedLabel(n: number, lang = 'en'): string {
	return t(lang, 'ws_scope_linked', n);
}

/** "Reads 21" (the key figure) — lawful reads, retained. */
export function readsLabel(n: number, lang = 'en'): string {
	return t(lang, 'ws_scope_reads', n);
}

/** "Sightings 22" — the registry count, as the Explorer and the layer tree show it. */
export function countLabel(kind: string, n: number, lang = 'en'): string {
	const key = `ws_kinds_${kind}`;
	const name = t(lang, key);
	return `${name === key ? kind : name} ${n}`;
}

/** "18 of 51 linked in window" */
export function inWindowLabel(k: number, n: number, lang = 'en'): string {
	return t(lang, 'ws_scope_in_window', k, n);
}

/** "Rows in view 189" */
export function inViewLabel(n: number, lang = 'en'): string {
	return t(lang, 'ws_scope_in_view', n);
}

/** "1 decision" / "3 decisions" */
export function decisionsLabel(n: number, lang = 'en'): string {
	return t(lang, n === 1 ? 'ws_scope_decision' : 'ws_scope_decisions', n);
}

/** "19 watchlist reads, 24 h" */
export function watchReadsLabel(n: number, lang = 'en'): string {
	return t(lang, 'ws_scope_watch_reads', n);
}
