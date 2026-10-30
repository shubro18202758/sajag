/**
 * osint layer — reported situations on the map (osint:, OS-DECK-A).
 *
 * Feed: the city registry's `osint_event` entities — surfaced open-source
 * situations (contract C-T; the snapshot's ONE GET /city/entities, no GET
 * of its own). A situation is about a PLACE, never a person: a NEUTRAL
 * 21 px disc with the report glyph (kindIcon('osint_event') — every other
 * object is neutral too, SPEC §2.4); hue appears only as ONE decision mark
 * in --v-map-decision on the report whose decision-support proposal is
 * proposed and unexpired, in BOTH chromes (the canvas's pass reads
 * dssWaitingUrns via cityDecisionUrns, so the dot survives selection,
 * clustering and hover; the legacy chrome bakes the same decision image).
 * The waiting dot is the decision IMAGE alone — never a decision ROLE on
 * the marker's ring, which painted a second orange mark beside it (fix
 * round 2, item 10). An AREA-level report draws the same glyph inside a
 * larger translucent neutral ring at its representative point — it reads as
 * an area, never as a precise pin, and the dossier says why ("District-level
 * report"). A state-level report is never in the snapshot (the pipeline
 * holds it, outside_city); should one ever arrive without a point, nothing
 * is drawn and the layer counts it under "not mapped".
 *
 * Labels and clustering belong to the canvas's v2 pass (the marker is
 * tagged: hover label, cluster member); the LEGACY chrome draws the same
 * tagged markers with the overlay-label plate. The time window, the
 * protected set and the selection act through the pass (markerStyle); the
 * layer re-reads the view so a change redraws promptly. The kind filter
 * hides the area ring here (a line of this layer) and the markers in the
 * canvas's pass.
 *
 * Pick ids `osint:<uuid>` (the marker) and `osint:area-<uuid>` (its area
 * ring) → URN `osint_event:<uuid>`: a click selects the same object the
 * omnibar, the table and the dossier address.
 */

import { ops } from '$lib/ops/store.svelte';
import { t } from '$lib/i18n/strings';
import '$lib/i18n/packs.osint';
import { dssWaiting, readReport } from '$lib/osint/model';
import { cityRegistry } from '../entities/registry.svelte';
import { displayText } from '../plates';
import type { CityEntity } from '../city-api';
import type { GodsEyeLayer, GodsEyeLayerContext, GodsEyeLayerInstance } from '../registry';
import { canvasFont, cssColor } from '../theme';
import { DRAPE_Z, clampedLabel, drapeAudit, drapedRing, ground } from './draping';
import { decisionUrns } from './enforcement';
import { labelPlate } from './labels';
import { kindIcon } from '$lib/design/icons';
import { chromeOf, kindShown, kindsSignature, markerStyle, viewOf, type MapView } from '../hud/map/view';
import { inkAlpha, mapInk, markerBillboard, tagMarker, type MarkerMeta } from '../hud/map/symbols';
import { verificationWord } from '$lib/workspace/kinds/generic';

export const OSINT_PICK_PREFIX = 'osint:';

/** The area ring's radius (m): district scale, deliberately not street scale. */
export const OSINT_AREA_RADIUS_M = 3000;

/** The marker label keeps to one line (the pick card and the dossier carry the rest). */
const LABEL_MAX_CHARS = 48;

const LABEL_FAR = 16_000;

/**
 * The report id behind a pick id (`osint:<id>` or `osint:area-<id>`), null
 * when the id is not one of this layer's. Ids are uuids (C-C), so the
 * leading `area-` is unambiguous.
 */
export function osintIdFromPick(pickId: string): string | null {
	if (!pickId.startsWith(OSINT_PICK_PREFIX)) return null;
	return pickId.slice(OSINT_PICK_PREFIX.length).replace(/^area-/, '') || null;
}

/**
 * The URNs whose decision-support proposal waits (proposed AND unexpired —
 * `model.dssWaiting` is the ONE expiry check): the layer's own mark AND the
 * canvas's decision dot read this set, so the dot stays visible on a
 * selected or clustered marker (R3).
 */
export function dssWaitingUrns(rows: readonly CityEntity[], now: number): Set<string> {
	const out = new Set<string>();
	for (const e of rows) if (dssWaiting(readReport(e.props), now)) out.add(e.urn);
	return out;
}

/**
 * The map pass's decision set for one city picture (R3), PURE: the
 * enforcement dots (a unit's recommendations over the stolen set), the
 * requested dispatches, and the reported situations whose decision-support
 * proposal waits (`dssWaitingUrns` — `model.dssWaiting` is the ONE expiry
 * check). The canvas's `decisionSet` is this builder over the live
 * registry, and the unit test asserts the waiting OSINT URN rides the
 * `view.decisions` it feeds — that is what keeps the dot on a selected or
 * clustered marker.
 */
/** A marker's decision mark: its own waiting decision, or — for a collapsed cluster's lead (not spread out) — any
 *  member's. A waiting report absorbed into a cluster must never lose its dot. */
export function markShowsDecision(own: boolean, isLead: boolean, spreadOut: boolean, members: readonly string[] | undefined, waits: (id: string) => boolean): boolean {
	return own || (isLead && !spreadOut && !!members?.some(waits));
}

export function cityDecisionUrns(input: {
	recommendations: readonly CityEntity[];
	stolen: ReadonlySet<string>;
	dispatches: readonly CityEntity[];
	osint: readonly CityEntity[];
	enforcementOn: boolean;
	now: number;
}): Set<string> {
	const out = input.enforcementOn ? decisionUrns(input.recommendations, input.stolen) : new Set<string>();
	for (const d of input.dispatches) if (d.state === 'requested') out.add(d.urn);
	for (const urn of dssWaitingUrns(input.osint, input.now)) out.add(urn);
	return out;
}

/** The hover label: the situation's own label, masked (C6), one line. */
function labelText(e: CityEntity, officer: boolean): string {
	const shown = displayText(e.label, officer);
	return shown.length > LABEL_MAX_CHARS ? `${shown.slice(0, LABEL_MAX_CHARS - 1)}…` : shown;
}

/**
 * The pick card's words, LOCALIZED (item 8, fix round 2 — the packs'
 * `os_pick_*` keys, EN/HI/MR; a language switch redraws the layer because
 * `ops.lang` rides the draw signature). The label already names the place
 * ("Road accident · Ruby crossing (EM Bypass)"), so " at <toponym>" is
 * added only when the toponym is not in it — never the doubled name.
 */
function describe(e: CityEntity, extra: string, officer: boolean): string {
	const lang = ops.lang;
	const verification = typeof e.props.verification_state === 'string' ? verificationWord(e.props.verification_state, lang) : null;
	const credibility = typeof e.props.credibility === 'number' ? ` · ${t(lang, 'os_pick_credibility')} ${e.props.credibility.toFixed(2)}` : '';
	const label = displayText(e.label, officer);
	const toponym = typeof e.props.toponym === 'string' ? displayText(e.props.toponym, officer) : null;
	const where = toponym != null && toponym !== '' && !label.includes(toponym) ? ` ${t(lang, 'os_pick_at', toponym)}` : '';
	return `${label}${where}. ${verification ? `${t(lang, 'os_pick_reported')} (${verification})${credibility}. ` : ''}${extra} ${t(lang, 'os_pick_never_people')}`;
}

function createOsintLayer(): GodsEyeLayerInstance {
	let ctx: GodsEyeLayerContext | null = null;
	let active = false;
	let timer: ReturnType<typeof setInterval> | null = null;
	const entityIds: string[] = [];
	let lastSignature = '';
	let drawn = 0;
	let areas = 0;
	let waiting = 0;
	let notMapped = 0;
	let detail: Record<string, number> = {};

	function draw() {
		if (!ctx || !active) return;
		const { cesium, viewer } = ctx;
		const rows = cityRegistry.byKind('osint_event');
		const officer = ops.officerOn;
		const view: MapView | null = chromeOf(ctx) === 'v2' ? viewOf(ctx) : null;
		const now = Date.now();
		const waitingUrns = dssWaitingUrns(rows, now);
		const sig = JSON.stringify([
			rows.map((e) => [e.id, e.lon, e.lat, e.label, e.t, e.props.area_level === true, waitingUrns.has(e.urn)]),
			officer,
			// the pick card's words ride the language (fix round 2, item 8): a switch redraws
			ops.lang,
			view ? [kindsSignature(view), view.version] : null,
		]);
		if (sig === lastSignature) return;
		lastSignature = sig;

		for (const id of entityIds) viewer.entities.removeById(id);
		entityIds.length = 0;
		drawn = 0;
		areas = 0;
		waiting = 0;
		notMapped = 0;

		const labelInk = cssColor(cesium, '--v-map-label-ink', cesium.Color.WHITE);
		const canvasInk = cssColor(cesium, '--v-map-marker-fill', cesium.Color.GRAY);

		for (const e of rows) {
			if (e.lon == null || e.lat == null) {
				// a state-level report has no city point: held by the pipeline (outside_city),
				// counted here if one ever arrives
				notMapped++;
				continue;
			}
			const style = view ? markerStyle({ urn: e.urn, kind: e.kind, t: e.t }, view) : null;
			const alpha = style ? style.alpha : 1;
			const area = e.props.area_level === true;
			// the decision mark: the layer's own ring AND the canvas's dot read the same set (R3),
			// so a selected or clustered marker keeps its waiting dot
			const decision = waitingUrns.has(e.urn);
			if (decision) waiting++;
			const label = labelText(e, officer);
			const meta: MarkerMeta = {
				urn: e.urn,
				kind: 'osint_event',
				glyph: kindIcon('osint_event'),
				shape: 'disc',
				// NO decision ROLE on the ring (fix round 2, item 10): the role painted a second
				// orange mark beside the dot. The waiting dot is the decision IMAGE alone — baked
				// into this layer's draw ({ decision: true } below, in both chromes) and drawn by
				// the canvas's pass from its decision set (R3); SPEC §5.4, prototype 01.
				cluster: true,
				t: e.t,
				label: [{ text: label }],
				labelWhen: 'hover',
				radius: area ? 14 : undefined,
			};
			const description = describe(
				e,
				area ? t(ops.lang, 'os_pick_district') : t(ops.lang, 'os_pick_street'),
				officer,
			);
			const entity = viewer.entities.add({
				id: `${OSINT_PICK_PREFIX}${e.id}`,
				position: ground(cesium, e.lon, e.lat),
				billboard: markerBillboard(cesium, meta, decision ? { decision: true } : {}),
				// the legacy chrome draws the SAME tagged disc with the overlay-label plate (its
				// labels are not the v2 pass's business); under v2 the pass owns the hover label
				...(view
					? {}
					: {
							label: clampedLabel(cesium, {
								text: label,
								font: canvasFont('12px var(--v-font-ui)'),
								fillColor: labelInk,
								outlineColor: canvasInk,
								outlineWidth: 2,
								style: 2,
								...labelPlate(cesium),
								verticalOrigin: -1,
								pixelOffset: new cesium.Cartesian2(0, 12),
								distanceDisplayCondition: new cesium.DistanceDisplayCondition(0, LABEL_FAR),
							}),
						}),
				description,
			});
			// tagged in BOTH chromes: the v2 pass restyles from the meta; the legacy chrome's
			// decision state is baked into its image, and the tag is what tests (and a page that
			// later opts into v2) read
			tagMarker(entity, meta);
			entityIds.push(entity.id);
			if (area && !view?.noAreas && (!view || kindShown(view, 'osint_event'))) {
				areas++;
				const ring = viewer.entities.add({
					id: `${OSINT_PICK_PREFIX}area-${e.id}`,
					polyline: drapedRing(cesium, {
						lon: e.lon,
						lat: e.lat,
						radiusM: OSINT_AREA_RADIUS_M,
						width: 1.5,
						material: cesium.Color.fromCssColorString(inkAlpha(mapInk('marker'), 0.4 * alpha)),
						z: DRAPE_Z.zone,
					}),
					description: describe(e, t(ops.lang, 'os_pick_area_ring'), officer),
				});
				entityIds.push(ring.id);
			}
			drawn++;
		}
		detail = { drawn, areas, waiting, notMapped, ...(ctx && drawn ? drapeAudit(ctx.viewer, entityIds) : {}) };
	}

	return {
		async status() {
			return { configured: true };
		},
		init(layerCtx) {
			ctx = layerCtx;
		},
		activate() {
			active = true;
			draw();
			timer = setInterval(draw, 2000);
		},
		deactivate() {
			active = false;
			if (timer) clearInterval(timer);
			timer = null;
			if (ctx) for (const id of entityIds) ctx.viewer.entities.removeById(id);
			entityIds.length = 0;
			lastSignature = '';
			drawn = 0;
			areas = 0;
			waiting = 0;
			notMapped = 0;
			detail = {};
		},
		refresh() {
			lastSignature = '';
			void cityRegistry.refresh();
			draw();
		},
		restyle() {
			draw();
		},
		handlePick(pickId) {
			return pickId.startsWith(OSINT_PICK_PREFIX);
		},
		urnOf(pickId) {
			const id = osintIdFromPick(pickId);
			return id ? `osint_event:${id}` : null;
		},
		coverageStats() {
			const served = cityRegistry.served('osint_event');
			const down = cityRegistry.status !== 'idle' && !served;
			// R1: the held social-only situations are counted ONCE, here — never on a per-report
			// view (a count beside one situation reads as corroboration that does not exist).
			// The line is LOCALIZED (fix round 2, item 14): the packs' os_layer_held_* keys.
			const held = cityRegistry.feed('osint_event')?.extra?.held_social;
			const heldLine = typeof held === 'number' && held > 0 ? ` · ${held} ${t(ops.lang, held === 1 ? 'os_layer_held_one' : 'os_layer_held_many')}` : '';
			return {
				count: drawn,
				loading: cityRegistry.status === 'idle',
				hint: down
					? t(ops.lang, 'os_layer_down')
					: `${t(ops.lang, 'os_layer_on_canvas', drawn)}${areas ? ` · ${t(ops.lang, 'os_layer_area', areas)}` : ''}${waiting ? ` · ${t(ops.lang, 'os_layer_waiting', waiting)}` : ''}${
							notMapped ? ` · ${t(ops.lang, 'os_layer_unmapped', notMapped)}` : ''
						}${heldLine}`,
				error: down ? (cityRegistry.note ?? 'osint source not ok') : null,
				detail,
				via: 'city-api',
			};
		},
		destroy() {
			this.deactivate();
		},
	};
}

export const osintLayer: GodsEyeLayer = {
	id: 'osint',
	name: 'Reported situations (open sources)',
	label: 'OSINT',
	requiresKeyId: null,
	pickPrefix: OSINT_PICK_PREFIX,
	defaultOn: true,
	group: 'intelligence',
	create: createOsintLayer,
};
