/**
 * The workspace provider registry (SPEC §5.3, plan X6). The frame and the
 * inspector never import a provider: providers (analysis, decisions,
 * corridor, assistant, osint, dss …) register into these slots from their
 * own `register.ts`, and `registerProviders()` (providers.ts) calls them all.
 * Before a provider has merged, its tab simply does not appear.
 *
 * Every call is ADDITIVE and keyed by id (plan R27): entries accumulate per
 * slot or per kind; registering an id that is already there REPLACES that
 * entry (HMR re-registration and a second registerProviders() stay
 * idempotent); reads return every entry sorted by `order`, then `id`.
 * Nothing is ever a single value per kind, so two providers registering for
 * one kind in the same wave never erase each other.
 *
 *   actionsFor(row)  every provider's actions for the row's kind (and '*'),
 *                    a later action whose action.id repeats an earlier one
 *                    dropped
 *   ownsUnitKinds    a section that links a decision unit kind itself; the
 *                    inspector's Actions tab then adds no link card of its
 *                    own for that kind on that object (never two cards for
 *                    one unit)
 */
import type { Component } from 'svelte';
import { registryClock } from './registry-clock.svelte';
import type { DecisionUnitSummary, InspectorSectionProps, ObjectAction, ObjectRow, TabContext, TabSpec } from './types';

interface Entry<T> {
	id: string;
	order: number;
	value: T;
}

/** An additive, id-keyed list: the same id replaces its entry; reads sort by order, then id. */
class Slot<T> {
	private entries: Entry<T>[] = [];

	set(id: string, order: number, value: T) {
		const i = this.entries.findIndex((e) => e.id === id);
		const entry = { id, order: Number.isFinite(order) ? order : 0, value };
		if (i >= 0) this.entries[i] = entry;
		else this.entries.push(entry);
		registryClock.bump();
	}

	list(): Entry<T>[] {
		return [...this.entries].sort((a, b) => a.order - b.order || (a.id < b.id ? -1 : a.id > b.id ? 1 : 0));
	}

	get size(): number {
		return this.entries.length;
	}

	clear() {
		this.entries = [];
	}
}

function keyed<T>(map: Map<string, Slot<T>>, key: string): Slot<T> {
	let s = map.get(key);
	if (!s) map.set(key, (s = new Slot<T>()));
	return s;
}

function checkId(id: unknown, what: string): string {
	if (typeof id !== 'string' || !id.trim()) throw new Error(`${what}: an id is required (plan R27)`);
	return id;
}

// ── tabs ────────────────────────────────────────────────────────────────

const leftTabs = new Slot<TabSpec>();
const rightTabs = new Slot<TabSpec>();
const bottomTabs = new Slot<TabSpec>();

export function registerLeftTab(t: TabSpec): void {
	leftTabs.set(checkId(t.id, 'registerLeftTab'), t.order, t);
}

export function registerRightTab(t: TabSpec): void {
	rightTabs.set(checkId(t.id, 'registerRightTab'), t.order, t);
}

export function registerBottomTab(t: TabSpec): void {
	bottomTabs.set(checkId(t.id, 'registerBottomTab'), t.order, t);
}

function readTabs(slot: Slot<TabSpec>, ctx?: TabContext): TabSpec[] {
	void registryClock.value;
	const all = slot.list().map((e) => e.value);
	if (!ctx) return all;
	return all.filter((t) => {
		try {
			return t.when ? t.when(ctx) : true;
		} catch {
			return false;
		}
	});
}

/** The registered left-dock tabs (the rail), filtered by `when(ctx)` when a context is given. */
export function leftTabsFor(ctx?: TabContext): TabSpec[] {
	return readTabs(leftTabs, ctx);
}

export function rightTabsFor(ctx?: TabContext): TabSpec[] {
	return readTabs(rightTabs, ctx);
}

export function bottomTabsFor(ctx?: TabContext): TabSpec[] {
	return readTabs(bottomTabs, ctx);
}

// ── activity renderers ──────────────────────────────────────────────────

const activityRenderers = new Slot<Component<InspectorSectionProps>>();

/** A component the inspector's Activity tab renders after its own rows (props {row, dossier}). */
export function registerActivityRenderer(c: Component<InspectorSectionProps>, opts: { id: string; order?: number }): void {
	activityRenderers.set(checkId(opts?.id, 'registerActivityRenderer'), opts.order ?? 0, c);
}

export function activityRenderersList(): { id: string; component: Component<InspectorSectionProps> }[] {
	void registryClock.value;
	return activityRenderers.list().map((e) => ({ id: e.id, component: e.value }));
}

// ── object sources ──────────────────────────────────────────────────────

const objectSources = new Slot<() => readonly ObjectRow[]>();

/** Rows known outside the registry snapshot (history, decision subjects); read on every model rebuild. */
export function registerObjectSource(fn: () => readonly ObjectRow[], opts: { id: string }): void {
	objectSources.set(checkId(opts?.id, 'registerObjectSource'), 0, fn);
}

/** Every registered source's rows, concatenated (a throwing source contributes nothing). */
export function sourceRows(): ObjectRow[] {
	void registryClock.value;
	const out: ObjectRow[] = [];
	for (const e of objectSources.list()) {
		try {
			out.push(...e.value());
		} catch {
			// a provider's failure never blanks the workspace
		}
	}
	return out;
}

// ── inspector sections ──────────────────────────────────────────────────

export interface InspectorSection {
	id: string;
	order: number;
	component: Component<InspectorSectionProps>;
	ownsUnitKinds: readonly string[];
}

const sections = new Map<string, Slot<InspectorSection>>();

/**
 * A section of the inspector for objects of `kind` (props {row, dossier}).
 * `ownsUnitKinds` lists the decision-unit kinds the section links itself.
 */
export function registerInspectorSection(
	kind: string,
	component: Component<InspectorSectionProps>,
	opts: { id: string; order: number; ownsUnitKinds?: readonly string[] },
): void {
	const id = checkId(opts?.id, 'registerInspectorSection');
	keyed(sections, kind).set(id, opts.order, { id, order: opts.order, component, ownsUnitKinds: [...(opts.ownsUnitKinds ?? [])] });
}

/** Every section registered for `kind`, by order then id. */
export function inspectorSectionsFor(kind: string): InspectorSection[] {
	void registryClock.value;
	return sections.get(kind)?.list().map((e) => e.value) ?? [];
}

/** The unit kinds the sections registered for `kind` link themselves. */
export function ownedUnitKinds(kind: string): Set<string> {
	return new Set(inspectorSectionsFor(kind).flatMap((s) => s.ownsUnitKinds));
}

// ── actions ─────────────────────────────────────────────────────────────

const actions = new Map<string, Slot<(row: ObjectRow) => readonly ObjectAction[]>>();

/** Actions (never decisions) for objects of `kind` ('*' for every kind). */
export function registerActions(kind: string, fn: (row: ObjectRow) => readonly ObjectAction[], opts: { id: string; order?: number }): void {
	keyed(actions, kind).set(checkId(opts?.id, 'registerActions'), opts.order ?? 0, fn);
}

/** Every provider's actions for `row` (its kind, then '*'), sorted by order then id; a repeated action.id is dropped. */
export function actionsFor(row: ObjectRow): readonly ObjectAction[] {
	void registryClock.value;
	const entries = [...(actions.get(row.kind)?.list() ?? []), ...(actions.get('*')?.list() ?? [])].sort(
		(a, b) => a.order - b.order || (a.id < b.id ? -1 : a.id > b.id ? 1 : 0),
	);
	const seen = new Set<string>();
	const out: ObjectAction[] = [];
	for (const e of entries) {
		let list: readonly ObjectAction[] = [];
		try {
			list = e.value(row) ?? [];
		} catch {
			list = [];
		}
		for (const a of list) {
			if (!a || seen.has(a.id)) continue;
			seen.add(a.id);
			out.push(a);
		}
	}
	return out;
}

// ── decision units ──────────────────────────────────────────────────────

const unitSources = new Slot<() => readonly DecisionUnitSummary[]>();

/** A source of decision units (S2 cannot import S5: decisions register their units here). */
export function registerDecisionUnits(fn: () => readonly DecisionUnitSummary[], opts: { id: string }): void {
	unitSources.set(checkId(opts?.id, 'registerDecisionUnits'), 0, fn);
}

/** Every registered unit source's units, concatenated in source order (selectors.decisionUnits dedupes). */
export function unitSourceRows(): DecisionUnitSummary[] {
	void registryClock.value;
	const out: DecisionUnitSummary[] = [];
	for (const e of unitSources.list()) {
		try {
			out.push(...e.value());
		} catch {
			// a provider's failure never blanks the count
		}
	}
	return out;
}

// ── inspection (the frame's non-ideal state, tests) ─────────────────────

/** How many entries each slot holds. */
export function registrySize(): { left: number; right: number; bottom: number; sections: number; actions: number; sources: number; units: number; activity: number } {
	void registryClock.value;
	let sectionCount = 0;
	for (const s of sections.values()) sectionCount += s.size;
	let actionCount = 0;
	for (const s of actions.values()) actionCount += s.size;
	return {
		left: leftTabs.size,
		right: rightTabs.size,
		bottom: bottomTabs.size,
		sections: sectionCount,
		actions: actionCount,
		sources: objectSources.size,
		units: unitSources.size,
		activity: activityRenderers.size,
	};
}

/** True when any provider registered a tab (the frame shows a non-ideal state otherwise). */
export function hasProviders(): boolean {
	const s = registrySize();
	return s.left + s.right + s.bottom > 0;
}

/** Forget every registration (tests and the harness's empty frame only). */
export function resetRegistry(): void {
	for (const s of [leftTabs, rightTabs, bottomTabs, activityRenderers, objectSources, unitSources] as Slot<unknown>[]) s.clear();
	sections.clear();
	actions.clear();
	registryClock.bump();
}
