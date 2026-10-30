/**
 * One adapter per known kind (SPEC §7.2, plan X5), and the generic adapter
 * for every other kind (`osint_event`, `place`, kinds a later contract adds).
 */
import type { CityEntity } from '$lib/gods-eye/city-api';
import type { ObjectRow } from '../types';
import { cameraAdapter } from './camera';
import { maskView, maskedRow, type RowCtx } from './common';
import { dispatchAdapter } from './dispatch';
import { eventAdapter } from './event';
import { genericAdapter, type ImpliedLink, type KindAdapter } from './generic';
import { anomalyAdapter, convoyAdapter, junctionAdapter, segmentAdapter, unitAdapter } from './infrastructure';
import { recommendationAdapter } from './recommendation';
import { sightingAdapter } from './sighting';
import { vehicleAdapter } from './vehicle';

/**
 * The masking guard every adapter is served through (C6, SPEC §9.3): its
 * rows carry a masked label and sublabel whoever is on console (rows reach
 * the omnibar, the search, the table and CSV), and a view built with no
 * named duty officer is masked whole — whatever server text an adapter
 * shows (an e-challan's proposal, an earmark reason, a pursuit's title).
 */
function guarded(a: KindAdapter): KindAdapter {
	return {
		...a,
		row: (e, ctx) => maskedRow(a.row(e, ctx)),
		view: (row, ctx) => (ctx.officer ? a.view(row, ctx) : maskView(a.view(row, ctx))),
	};
}

const OWN: Readonly<Record<string, KindAdapter>> = {
	event: eventAdapter,
	vehicle: vehicleAdapter,
	sighting: sightingAdapter,
	camera: cameraAdapter,
	junction: junctionAdapter,
	unit: unitAdapter,
	convoy: convoyAdapter,
	dispatch: dispatchAdapter,
	recommendation: recommendationAdapter,
	anomaly: anomalyAdapter,
	segment: segmentAdapter,
};

/** Every known kind's adapter, through the masking guard. */
export const ADAPTERS: Readonly<Record<string, KindAdapter>> = Object.freeze(
	Object.fromEntries(Object.entries(OWN).map(([kind, a]) => [kind, guarded(a)])),
);

/** The generic adapter (osint_event, place, any later kind), through the masking guard. */
const GENERIC: KindAdapter = guarded(genericAdapter);

/** The adapter of a kind (masked: see guarded); the generic adapter for any kind without one. */
export function adapterFor(kind: string): KindAdapter {
	return Object.prototype.hasOwnProperty.call(ADAPTERS, kind) ? ADAPTERS[kind] : GENERIC;
}

/** The row a city entity becomes (every kind yields one). */
export function rowOf(e: CityEntity, ctx: RowCtx = {}): ObjectRow {
	return adapterFor(e.kind).row(e, ctx);
}

/**
 * The links a row's props imply (rows from history carry no `links`): each
 * with the relation the props name, or null when the kinds name it.
 */
export function impliedLinks(row: ObjectRow): { urn: string; rel: string | null }[] {
	const list = adapterFor(row.kind).implied?.(row) ?? [];
	return list.map((l) => (typeof l === 'string' ? { urn: l, rel: null } : { urn: l.urn, rel: l.rel }));
}

export { GENERIC as genericAdapter };
export type { KindAdapter, ImpliedLink };
export { recommendationRow } from './recommendation';
export { eventRow } from './event';
export { dispatchRow } from './dispatch';
