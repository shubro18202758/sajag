/**
 * Sajag icon set — Blueprint icon path data and the frozen icon maps (SPEC §4).
 *
 * Icon path data and colour values from Blueprint (@blueprintjs/icons 6.14.1,
 * @blueprintjs/colors 5.1.16), Copyright Palantir Technologies, Inc., Apache-2.0.
 * Modified: subset. Full licence text: ./LICENSE-blueprint.txt.
 *
 * Transcribed verbatim from the redesign prototype (prototype/assets/icons.js,
 * itself read as text from the published @blueprintjs/icons 6.14.1 package —
 * never imported or executed): 206 icons on the 16 px grid, 24 of them also on
 * the 20 px grid. No npm dependency, no icon font, no CDN.
 *
 * Person glyphs (mugshot, person, people, blocked-person, follower, following,
 * id-number) are excluded on purpose: Sajag tracks vehicles only. The one
 * person-shaped glyph is `user`, reserved for the named officer.
 *
 * The frozen maps below are the only source of a kind's glyph. The glyph lint
 * (tests/design-tokens.mjs) refuses a kind icon name passed as a literal
 * anywhere outside this file: use kindIcon(kind) / eventKindIcon(kind), or the
 * ACTOR_ICON / ACTION_ICON / MODULE_ICON / INTENT_ICON / PROVENANCE_ICON maps
 * when the same glyph means something else.
 */
import { CORE_16, CORE_20, ICON_NAMES } from './icons-core';

/** Every icon name in the set (16 px grid). */
export type IconName =
	| 'annotation'
	| 'antenna'
	| 'applications'
	| 'area-of-interest'
	| 'arrow-down'
	| 'arrow-left'
	| 'arrow-right'
	| 'arrow-top-right'
	| 'arrow-up'
	| 'automatic-updates'
	| 'badge'
	| 'ban-circle'
	| 'bookmark'
	| 'build'
	| 'calendar'
	| 'camera'
	| 'caret-down'
	| 'caret-right'
	| 'caret-up'
	| 'cell-tower'
	| 'changes'
	| 'chat'
	| 'chevron-down'
	| 'chevron-left'
	| 'chevron-right'
	| 'chevron-up'
	| 'circle'
	| 'circle-arrow-right'
	| 'clipboard'
	| 'code'
	| 'cog'
	| 'collapse-all'
	| 'column-layout'
	| 'comment'
	| 'compass'
	| 'console'
	| 'cross'
	| 'cross-circle'
	| 'cube'
	| 'dashboard'
	| 'data-connection'
	| 'data-lineage'
	| 'data-search'
	| 'database'
	| 'detection'
	| 'diagram-tree'
	| 'disable'
	| 'document'
	| 'dot'
	| 'double-chevron-right'
	| 'drag-handle-vertical'
	| 'draw'
	| 'drawer-left'
	| 'drawer-right'
	| 'drive-time'
	| 'duplicate'
	| 'edit'
	| 'endorsed'
	| 'error'
	| 'exchange'
	| 'expand-all'
	| 'explain'
	| 'export'
	| 'eye-off'
	| 'eye-on'
	| 'eye-open'
	| 'fast-forward'
	| 'feed'
	| 'filter'
	| 'filter-list'
	| 'filter-remove'
	| 'flag'
	| 'flash'
	| 'flow-linear'
	| 'folder-close'
	| 'folder-open'
	| 'fork'
	| 'full-circle'
	| 'fullscreen'
	| 'function'
	| 'gantt-chart'
	| 'geolocation'
	| 'geosearch'
	| 'git-merge'
	| 'globe'
	| 'globe-network'
	| 'graph'
	| 'graph-remove'
	| 'grid-view'
	| 'hand'
	| 'heatmap'
	| 'help'
	| 'high-priority'
	| 'history'
	| 'home'
	| 'horizontal-bar-chart'
	| 'inbox'
	| 'info-sign'
	| 'inheritance'
	| 'intersection'
	| 'issue'
	| 'key-command'
	| 'known-vehicle'
	| 'lab-test'
	| 'layers'
	| 'layout-circle'
	| 'layout-hierarchy'
	| 'lightbulb'
	| 'lightning'
	| 'link'
	| 'list'
	| 'list-columns'
	| 'locate'
	| 'lock'
	| 'map'
	| 'map-create'
	| 'map-marker'
	| 'maximize'
	| 'menu'
	| 'minimize'
	| 'minus'
	| 'more'
	| 'mountain'
	| 'move'
	| 'new-link'
	| 'new-object'
	| 'notifications'
	| 'notifications-updated'
	| 'offline'
	| 'outdated'
	| 'panel-stats'
	| 'panel-table'
	| 'path'
	| 'path-search'
	| 'pause'
	| 'pin'
	| 'play'
	| 'playbook'
	| 'plus'
	| 'polygon-filter'
	| 'predictive-analysis'
	| 'properties'
	| 'property'
	| 'pulse'
	| 'random'
	| 'record'
	| 'redo'
	| 'refresh'
	| 'route'
	| 'satellite'
	| 'search'
	| 'search-around'
	| 'select'
	| 'selection'
	| 'send-message'
	| 'send-to'
	| 'send-to-graph'
	| 'send-to-map'
	| 'share'
	| 'shield'
	| 'signal-search'
	| 'small-cross'
	| 'small-info-sign'
	| 'small-tick'
	| 'sort'
	| 'sort-asc'
	| 'sort-desc'
	| 'split-columns'
	| 'star'
	| 'star-empty'
	| 'step-backward'
	| 'step-forward'
	| 'stop'
	| 'stopwatch'
	| 'swap-horizontal'
	| 'symbol-diamond'
	| 'tag'
	| 'take-action'
	| 'target'
	| 'th'
	| 'th-filtered'
	| 'th-list'
	| 'tick'
	| 'tick-circle'
	| 'time'
	| 'timeline-area-chart'
	| 'timeline-bar-chart'
	| 'timeline-events'
	| 'translate'
	| 'trash'
	| 'trending-down'
	| 'trending-up'
	| 'truck'
	| 'two-columns'
	| 'undo'
	| 'unknown-vehicle'
	| 'unlock'
	| 'unpin'
	| 'updated'
	| 'user'
	| 'walk'
	| 'warning-sign'
	| 'widget'
	| 'zoom-in'
	| 'zoom-out'
	| 'zoom-to-fit';

/**
 * The complete tables, frozen and in the original order, for callers that list
 * or read the whole set (the /design gallery, the tests). They live in a pure
 * module of their own: a route that never names them does not ship them.
 */
export { ICONS_16, ICONS_20 } from './icons-all';

/*
 * What the deck DRAWS from (FIX-E-PERF2): the first-paint half (icons-core —
 * every glyph `/`, `/ops` and `/gods-eye` render in their first viewport, and
 * every map-marker glyph) is in at once; the deferred half (icons-rest) joins
 * on first use: an <Icon> whose glyph is not in yet asks for it and re-renders
 * (lib/ui/Icon.svelte), the operator's first pointer or key press prefetches
 * it, and a lazy panel awaits it beside its own module when it is in flight.
 */
const LIVE_16: Record<string, readonly string[]> = { ...CORE_16 };
const LIVE_20: Record<string, readonly string[]> = { ...CORE_20 };
const NAMES: ReadonlySet<string> = new Set(ICON_NAMES);

let restIcons: Promise<void> | null = null;
let restLanded = false;

/** Merge the deferred half into the drawing tables (idempotent; resolves once merged). */
export function loadRestIcons(): Promise<void> {
	if (!restIcons) {
		restIcons = import('./icons-rest')
			.then((m) => {
				Object.assign(LIVE_16, m.REST_16);
				Object.assign(LIVE_20, m.REST_20);
				restLanded = true;
			})
			.catch((err) => {
				restIcons = null; // a later use retries; the glyph keeps its empty box meanwhile
				throw err;
			});
	}
	return restIcons;
}

/** True once every glyph can be drawn (the deferred half merged). */
export function restIconsLoaded(): boolean {
	return restLanded;
}

/** The deferred half's flight when something already asked for it, else null (never starts one). */
export function restIconsInFlight(): Promise<void> | null {
	return restLanded ? null : restIcons;
}

/** True when `name` can be drawn right now (a first-paint glyph, or the deferred half has landed). */
export function iconReady(name: string): boolean {
	return Object.prototype.hasOwnProperty.call(LIVE_16, name);
}

/*
 * Outside the production browser — the server render, vite dev and the node
 * test harness — the deferred half merges before this module finishes
 * evaluating, so SSR draws every glyph. In the production browser, a page whose
 * server render drew a deferred glyph (a route other than the three budget
 * routes, whose first viewports the core covers) waits for the deferred half
 * before this module finishes evaluating: hydration never blanks a glyph the
 * server drew. Otherwise the half loads on first use; the operator's first
 * pointer or key press prefetches it, so a menu or panel opened by that press
 * has its glyphs.
 */
if (process.env.NODE_ENV !== 'production' || import.meta.env.SSR !== false) {
	await loadRestIcons();
} else if (typeof document !== 'undefined') {
	const ssrDrewDeferred = [...document.querySelectorAll('svg[data-icon]')].some((s) => {
		const n = s.getAttribute('data-icon');
		return !!n && NAMES.has(n) && !iconReady(n);
	});
	if (ssrDrewDeferred) await loadRestIcons().catch(() => {});
	const prefetch = () => void loadRestIcons().catch(() => {});
	for (const type of ['pointerdown', 'keydown']) window.addEventListener(type, prefetch, { once: true, capture: true, passive: true });
}

// ── helpers ──────────────────────────────────────────────────────────────────

/** True when `name` is an icon in the set (use before trusting a string from data) — whatever has loaded. */
export function isIconName(name: unknown): name is IconName {
	return typeof name === 'string' && NAMES.has(name);
}

/**
 * The paths and grid for an icon drawn at `size` px: the 20 px drawing when the
 * icon has one and size ≥ 20, else the 16 px drawing scaled. Unknown names give
 * no paths (the Icon component then renders an empty box of the same size); so
 * does a deferred glyph until its half lands (iconReady/loadRestIcons).
 */
export function iconPaths(name: IconName | string, size = 16): { paths: readonly string[]; grid: 16 | 20 } {
	if (!isIconName(name) || !iconReady(name)) return { paths: [], grid: 16 };
	const big = size >= 20 ? LIVE_20[name] : undefined;
	return big ? { paths: big, grid: 20 } : { paths: LIVE_16[name], grid: 16 };
}

// ── frozen maps (SPEC §4.2 and plan contract X1) ─────────────────────────────

/**
 * Object kind → glyph. Type is the glyph; colour is never a type (SPEC §2.4).
 * `segment` is the city entity kind of a road; `road` is its display alias.
 */
export const KIND_ICON = Object.freeze({
	vehicle: 'drive-time',
	sighting: 'detection',
	camera: 'camera',
	junction: 'intersection',
	segment: 'flow-linear',
	road: 'flow-linear',
	recommendation: 'take-action',
	event: 'timeline-events',
	dispatch: 'send-to',
	unit: 'badge',
	anomaly: 'pulse',
	convoy: 'route',
	osint_event: 'geosearch',
	place: 'map-marker'
} as const satisfies Record<string, IconName>);

/** Corridor-event kind → glyph; every other kind falls back to `timeline-events`. */
export const EVENT_KIND_ICON = Object.freeze({
	vehicle_pursuit: 'path-search',
	protected_movement: 'route',
	procession: 'walk',
	work_zone: 'build',
	mass_gathering: 'timeline-events',
	race: 'timeline-events',
	ceremonial: 'timeline-events',
	egress_surge: 'timeline-events',
	emergency_evacuation: 'timeline-events',
	crime_incident: 'timeline-events',
	reported_crime: 'high-priority',
	public_disorder: 'issue',
	road_accident: 'warning-sign',
	hazard: 'flash',
	flooding: 'area-of-interest',
	infra_failure: 'error'
} as const satisfies Record<string, IconName>);

/**
 * Actor → glyph. A ProposalCard header shows the proposer's glyph. `ai` is drawn
 * in the AI indigo (--v-ai-text) and nowhere else; `lightbulb` is retired.
 */
export const ACTOR_ICON = Object.freeze({
	officer: 'user',
	ai: 'predictive-analysis',
	rules: 'function',
	policies: 'function',
	sensor: 'camera',
	system: 'cog'
} as const satisfies Record<string, IconName>);

/** Action → glyph (SPEC §4.2 plus plan contract X1). */
export const ACTION_ICON = Object.freeze({
	show_on_map: 'send-to-map',
	search_around: 'search-around',
	add_to_graph: 'send-to-graph',
	explain: 'explain',
	find_paths: 'path-search',
	layer_visible: 'eye-open',
	layer_hidden: 'eye-off',
	brush_grip: 'drag-handle-vertical',
	return_to_live: 'fast-forward',
	masked: 'lock',
	emulated: 'lab-test',
	simulated: 'random',
	test: 'playbook',
	rule_no_fine: 'disable',
	policies: 'shield',
	inbox: 'inbox',
	promote: 'arrow-up',
	decision_support: 'diagram-tree',
	osint: 'globe'
} as const satisfies Record<string, IconName>);

/** Navbar module → glyph. */
export const MODULE_ICON = Object.freeze({
	city: 'globe-network',
	corridor: 'route',
	situation: 'dashboard',
	advisories: 'feed',
	assistant: 'chat'
} as const satisfies Record<string, IconName>);

/** Intent → the glyph a Callout or a toast shows for it. */
export const INTENT_ICON = Object.freeze({
	none: 'info-sign',
	primary: 'info-sign',
	success: 'tick-circle',
	warning: 'warning-sign',
	danger: 'error'
} as const satisfies Record<string, IconName>);

/** Provenance source → glyph (plan contract X2). */
export const PROVENANCE_ICON = Object.freeze({
	emulated: 'lab-test',
	simulated: 'random',
	test: 'playbook',
	osint: 'globe'
} as const satisfies Record<string, IconName>);

export type KindIconKey = keyof typeof KIND_ICON;
export type EventKindIconKey = keyof typeof EVENT_KIND_ICON;

/** The glyph of an object kind; `dot` for an unknown kind. Never throws. */
export function kindIcon(kind: string | null | undefined): IconName {
	if (typeof kind === 'string' && Object.prototype.hasOwnProperty.call(KIND_ICON, kind)) {
		return KIND_ICON[kind as KindIconKey];
	}
	return 'dot';
}

/** The glyph of a corridor-event kind; `timeline-events` for an unknown kind. Never throws. */
export function eventKindIcon(kind: string | null | undefined): IconName {
	if (typeof kind === 'string' && Object.prototype.hasOwnProperty.call(EVENT_KIND_ICON, kind)) {
		return EVENT_KIND_ICON[kind as EventKindIconKey];
	}
	return 'timeline-events';
}

/**
 * The glyph of an object, events by their kind: `objectIcon('event', 'procession')`
 * is `walk`, `objectIcon('camera')` is `camera`.
 */
export function objectIcon(kind: string | null | undefined, eventKind?: string | null): IconName {
	return kind === 'event' ? eventKindIcon(eventKind) : kindIcon(kind);
}
