/**
 * The workspace's shared types (SPEC §7, plan contracts X5 and X6).
 *
 * Every rendering of an object — map marker, graph node, table row, object
 * tag, omnibar result, inbox row, inspector — reads one ObjectRow. The row's
 * label is always the masked one (plate_masked): a raw registration mark is
 * shown only to a named duty officer, and only through ops.plate / plates.ts
 * at the moment of rendering, never stored in a row.
 */
import type { Component } from 'svelte';
import type { IconName } from '$lib/design/icons';
import type { VerificationState } from '$lib/ops/types';
import type { Dossier } from '$lib/gods-eye/city-api';

/** Where an object comes from (plan X5). */
export type ObjectSource = 'live' | 'emulated' | 'simulated' | 'test' | 'osint';

/** The hue a state may take (SPEC §2.4 roles only). */
export type StateIntent = 'none' | 'primary' | 'success' | 'warning' | 'danger';

/** One view-model for every rendering of an object (plan contract X5). */
export interface ObjectRow {
	urn: string;
	kind: string;
	id: string;
	/** The display label: masked mark, humanised title (display.ts). */
	label: string;
	/** A place or a state word, or null. */
	sublabel: string | null;
	icon: IconName;
	state: string | null;
	stateIntent: StateIntent;
	/** Epoch ms of the object's own time (null for infrastructure). */
	t: number | null;
	/** Epoch ms of the end of a span (events, dispatches), or null. */
	end: number | null;
	lon: number | null;
	lat: number | null;
	source: ObjectSource;
	verification: VerificationState | null;
	credibility: number | null;
	/** A rehearsal or test object: always tagged, kept out of counts by default. */
	test: boolean;
	/** The label carries a masked registration mark. */
	masked: boolean;
	props: Readonly<Record<string, unknown>>;
}

/** A link from an object, named from that object's end (relName). */
export interface ObjectLink {
	/** The relation id (snake_case, the oracle's name where it gave one): rel-group[data-relation]. */
	relation: string;
	row: ObjectRow;
}

/** The object model the selectors, the omnibar, the inspector and the table read. */
export interface ObjectGraph {
	/** Monotonic build id (memo keys). */
	readonly version: number;
	readonly size: number;
	get(urn: string | null | undefined): ObjectRow | null;
	all(): readonly ObjectRow[];
	byKind(kind: string): readonly ObjectRow[];
	/** 1-hop links of `urn`, both directions, deduplicated, named from `urn`'s end. */
	links(urn: string): readonly ObjectLink[];
}

// ── store (plan X6, frozen) ──────────────────────────────────────────────

export type View = 'map' | 'graph' | 'table' | 'split';

export type BottomSize = 'compact' | 'full' | 'off';

export interface Docks {
	left: boolean;
	right: boolean;
	bottom: BottomSize;
}

export type FilterField = 'kind' | 'state' | 'source' | 'hour' | 'road' | 'camera' | 'urns';

export type Filter = { id: string; field: FilterField; values: readonly string[]; label: string };

export type SavedView = { id: string; name: string; createdAt: number; hash: string /* masked: URNs only */ };

export type Watch = { id: string; title: string; subjectUrn: string | null; filters: readonly Filter[] };

// ── registry (plan X6, frozen) ───────────────────────────────────────────

export type TabRoute = '/' | '/gods-eye' | '/ops' | '/chat';

export type TabContext = {
	route: TabRoute;
	mode: 'workspace' | 'map';
	live: { movement: boolean; pursuit: boolean };
};

export type TabSpec = {
	id: string;
	/** An i18n key (preferred) or the literal label. */
	label: string;
	icon: IconName;
	// eslint-disable-next-line @typescript-eslint/no-explicit-any
	component: Component<any>;
	order: number;
	when?: (ctx: TabContext) => boolean;
	/**
	 * The panel's deferred module(s), for a lazily loaded panel: the frame
	 * calls it once, on the operator's first press (pointer or key) — never on
	 * a cold, interaction-free load — so the panel is in when it is first asked
	 * for (the omnibar's first-use rule).
	 */
	prefetch?: () => Promise<unknown>;
};

export type ObjectAction = {
	id: string;
	label: string;
	icon: IconName;
	intent?: 'primary' | 'danger';
	disabled?: boolean;
	disabledReason?: string;
	run(): void | Promise<void>;
};

export type DecisionHome = 'inbox' | 'decisions' | 'movement' | 'map';

export type DecisionUnitSummary = {
	kind: string;
	id: string;
	subjectUrn: string;
	title: string;
	deadline: number | null;
	severity: 0 | 1 | 2 | 3;
	homes: Record<'/' | '/gods-eye' | '/ops', DecisionHome>;
};

/** The props every registered inspector section receives. */
export type InspectorSectionProps = { row: ObjectRow; dossier: Dossier | null };
