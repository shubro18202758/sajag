/**
 * The map's view state under chrome v2 and the rules that turn it into
 * opacity (SPEC §5.3 "Hierarchy under a selection", "Time window"; §7.3).
 *
 *   SELECTION  with something selected, everything it is not linked to
 *              steps back: unrelated cameras to 50 %, infrastructure
 *              (junctions, roads, feed anomalies) to 30 %, other unrelated
 *              objects to 50 %; the flow layer to 60 % and 0.5 px thinner
 *              (flowDim). The selection and its links stay at full strength.
 *   WINDOW     a time window fades every time-bearing object outside it to
 *              30 % — never a PROTECTED object (the active movement, its
 *              convoy and route, open pursuits and their vehicles, objects
 *              with a waiting decision, vehicles with a watchlist read in the
 *              last 30 min; the page computes the set) and never
 *              infrastructure (cameras, junctions, roads). The window never
 *              deletes anything.
 *   KINDS      a kind filter hides the kinds it leaves out (protected ones
 *              too: the page warns "n live objects hidden") — the markers
 *              through the canvas's pass, and every layer's own lines,
 *              zones and routes (kindShown: the flow network 'segment',
 *              event spines and zones 'event', the convoy's route
 *              'convoy', a vehicle's track and heading 'vehicle', a
 *              unit's way to its waypoint 'dispatch').
 *
 * Pure: the canvas builds a MapView, the layers read it through their
 * context (`ctx.view()`), the unit tests drive it directly.
 */

export type MapChrome = 'legacy' | 'v2';

export interface MapView {
	chrome: MapChrome;
	/** The primary selection (a URN), or null. */
	selection: string | null;
	/** Every selected URN (the primary included); empty without a selection. */
	items: readonly string[];
	/** URNs linked to the selection (the selection itself excluded). */
	related: ReadonlySet<string>;
	/** The time window [from, to] in epoch ms, or null when live. */
	window: readonly [number, number] | null;
	/** Objects that never fade or dim (SPEC §7.3). */
	protected: ReadonlySet<string>;
	/** Kinds shown; null shows every kind. */
	kinds: ReadonlySet<string> | null;
	/** URNs with a waiting decision (one orange dot each). */
	decisions: ReadonlySet<string>;
	/** Bumped on every change (layers key their redraw on it). */
	version: number;
	/** chrome v3: no district-scale area ring (the page shows an official district warning as a chip). */
	noAreas?: boolean;
	/**
	 * chrome v3 FOCUS mode: with a selection, everything it is not linked to steps much further back (one event at a
	 * time); a protected object (a live movement, an open pursuit, a waiting decision) is dimmed less, never hidden.
	 */
	focus?: boolean;
}

const EMPTY: ReadonlySet<string> = new Set();

/** A view with nothing selected, no window, no filter (legacy pages and tests). */
export function emptyView(chrome: MapChrome = 'legacy'): MapView {
	return { chrome, selection: null, items: [], related: EMPTY, window: null, protected: EMPTY, kinds: null, decisions: EMPTY, version: 0 };
}

/** Infrastructure never fades with the window (SPEC §7.3). */
export const NEVER_FADES = new Set(['camera', 'junction', 'segment', 'road']);

/** Kinds that step back to the infrastructure level under a selection. */
export const INFRASTRUCTURE = new Set(['junction', 'segment', 'road', 'anomaly']);

/** The opacities of SPEC §5.3 (frozen numbers, unit-tested). */
export const MAP_OPACITY = Object.freeze({
	/** A time-bearing object outside the window. */
	outsideWindow: 0.3,
	/** An unrelated camera under a selection. */
	unrelatedCamera: 0.5,
	/** Unrelated infrastructure under a selection. */
	unrelatedInfrastructure: 0.3,
	/** Any other unrelated object under a selection. */
	unrelated: 0.5,
	/** The flow layer under a selection (and 0.5 px thinner). */
	flowUnderSelection: 0.6,
	/** A pursuit choke the vehicle has likely passed. */
	passed: 0.4,
	/** chrome v3 focus mode: an unrelated object under a selection. */
	focusUnrelated: 0.22,
	/** chrome v3 focus mode: an unrelated PROTECTED object (dimmed, never hidden). */
	focusProtected: 0.6,
});

/** How much thinner (px) the flow layer draws under a selection. */
export const FLOW_THIN_PX = 0.5;

/**
 * The kind filter shows `kind` (no filter shows every kind). The canvas's
 * pass hides the markers it leaves out; every layer skips its lines, zones
 * and routes for them (SPEC §5.3 "Kind filters hide objects").
 */
export function kindShown(view: Pick<MapView, 'kinds'>, kind: string): boolean {
	return !view.kinds || view.kinds.has(kind);
}

/** The kind filter's part of a layer's redraw signature (null: no filter). */
export function kindsSignature(view: Pick<MapView, 'kinds'> | null | undefined): string[] | null {
	return view?.kinds ? [...view.kinds].sort() : null;
}

/** `t` lies inside the window (inclusive). A null time is never outside. */
export function inWindow(t: number | null | undefined, w: MapView['window']): boolean {
	if (!w || t == null || !Number.isFinite(t)) return true;
	return t >= w[0] && t <= w[1];
}

export interface MapObject {
	urn: string | null;
	kind: string;
	/** The object's own time (epoch ms), null when it has none. */
	t?: number | null;
}

export interface MarkerStyle {
	show: boolean;
	alpha: number;
	selected: boolean;
	related: boolean;
	decision: boolean;
	protected: boolean;
}

/** One object's opacity and state marks under the view. Pure. */
export function markerStyle(o: MapObject, view: MapView): MarkerStyle {
	const urn = o.urn ?? '';
	const selected = !!urn && (urn === view.selection || view.items.includes(urn));
	const related = !!urn && view.related.has(urn);
	const isProtected = !!urn && view.protected.has(urn);
	const decision = !!urn && view.decisions.has(urn);
	const show = kindShown(view, o.kind);
	let alpha = 1;
	if (view.selection && !selected && !related && !isProtected) {
		alpha = view.focus ? MAP_OPACITY.focusUnrelated : o.kind === 'camera' ? MAP_OPACITY.unrelatedCamera : INFRASTRUCTURE.has(o.kind) ? MAP_OPACITY.unrelatedInfrastructure : MAP_OPACITY.unrelated;
	} else if (view.focus && view.selection && !selected && !related) alpha = MAP_OPACITY.focusProtected;
	if (view.window && !isProtected && !selected && !NEVER_FADES.has(o.kind) && !inWindow(o.t ?? null, view.window)) {
		alpha = Math.min(alpha, MAP_OPACITY.outsideWindow);
	}
	return { show, alpha, selected, related, decision, protected: isProtected };
}

/** The flow layer's dimming under the view: opacity factor and width reduction. */
export function flowDim(view: MapView): { alpha: number; thinPx: number } {
	return view.selection ? { alpha: MAP_OPACITY.flowUnderSelection, thinPx: FLOW_THIN_PX } : { alpha: 1, thinPx: 0 };
}

/** A stable signature of the view's parts a layer redraws on. */
export function viewSignature(view: MapView): string {
	return `${view.chrome}|${view.version}`;
}

/** A layer context's chrome ('legacy' when it does not say). */
export function chromeOf(ctx: { chrome?: MapChrome } | null | undefined): MapChrome {
	return ctx?.chrome === 'v2' ? 'v2' : 'legacy';
}

/** A layer context's current view (an empty view of its chrome when it has none). */
export function viewOf(ctx: { chrome?: MapChrome; view?: () => MapView } | null | undefined): MapView {
	return ctx?.view?.() ?? emptyView(chromeOf(ctx));
}
