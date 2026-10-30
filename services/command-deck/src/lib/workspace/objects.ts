/**
 * The object model (SPEC §7.2, plan X5): one view-model per object for every
 * rendering, and the links between objects named from both ends.
 *
 * buildObjectGraph() fuses three sources into one URN-keyed set:
 *   1. the city registry's snapshot (GET /city/entities): every kind, each
 *      entity with its `links`;
 *   2. the recent dossiers (GET /city/entity/{kind}/{id}): the oracle's own
 *      relation names, and objects the snapshot does not carry (older reads,
 *      decided recommendations, closed pursuits);
 *   3. registered object sources (registerObjectSource): rows known only
 *      from history (events, recommendations, dispatches), whose links come
 *      from their props through the kind adapters.
 *
 * Masking (C6): every label and sublabel is masked (plate_masked, mask.ts),
 * whatever source the row came from; no row stores a raw mark in either.
 * Egress (share links, saved views, copy, CSV) reads labels and URNs only.
 */
import type { CityEntity, Dossier } from '$lib/gods-eye/city-api';
import { impliedLinks, rowOf } from './kinds';
import { maskedRow, type RowCtx } from './kinds/common';
import { relId, reverseRel } from './relations';
import type { ObjectGraph, ObjectLink, ObjectRow } from './types';

export interface GraphInput {
	/** The registry's snapshot (the live picture). */
	entities?: readonly CityEntity[];
	/** Recent dossiers, oldest first: their relations are the oracle's names. */
	dossiers?: readonly Dossier[];
	/** Rows from registered object sources (history, decision subjects). */
	rows?: readonly ObjectRow[];
	ctx?: RowCtx;
}

/**
 * How firmly a link's name is known; a firmer name replaces a weaker one
 * between the same two objects, whatever order the sources arrive in:
 *   KINDS    an unnamed link (a snapshot `links` entry, a plain implied URN):
 *            the pair of kinds names it ("Corroborates" for report → event)
 *   PROPS    the row's own props name it (promoted_event_id → "Promoted to")
 *   DOSSIER  the oracle's dossier relation (its own name)
 */
const NAMED_BY_KINDS = 0;
const NAMED_BY_PROPS = 1;
const NAMED_BY_DOSSIER = 2;

interface Edge {
	rel: string;
	rank: number;
}

let builds = 0;

/** The kind of a URN (the text before the first colon), or null. */
export function kindOfUrn(urn: string): string | null {
	const i = urn.indexOf(':');
	return i > 0 ? urn.slice(0, i) : null;
}

/** Merge a second sighting of the same object into the first: the first wins, gaps are filled. */
function merge(a: ObjectRow, b: ObjectRow): ObjectRow {
	return {
		...a,
		sublabel: a.sublabel ?? b.sublabel,
		t: a.t ?? b.t,
		end: a.end ?? b.end,
		lon: a.lon ?? b.lon,
		lat: a.lat ?? b.lat,
		verification: a.verification ?? b.verification,
		credibility: a.credibility ?? b.credibility,
		test: a.test || b.test,
		props: { ...b.props, ...a.props },
	};
}

/** Build the object graph (pure; ≤ a few thousand rows in a few ms). */
export function buildObjectGraph(input: GraphInput): ObjectGraph {
	const ctx = input.ctx ?? {};
	const rows = new Map<string, ObjectRow>();
	const edges = new Map<string, Map<string, Edge>>();
	const entities: CityEntity[] = [];

	const put = (row: ObjectRow) => {
		const cur = rows.get(row.urn);
		rows.set(row.urn, cur ? merge(cur, row) : row);
	};
	const putEntity = (e: CityEntity) => {
		entities.push(e);
		put(rowOf(e, ctx));
	};

	for (const e of input.entities ?? []) putEntity(e);
	for (const d of input.dossiers ?? []) {
		putEntity(d.entity);
		for (const r of d.related) putEntity(r.entity);
	}
	// a registered source's rows are masked here too (C6): no label or sublabel in the graph holds a raw mark
	for (const row of input.rows ?? []) put(maskedRow(row));

	const setEdge = (from: string, to: string, rel: string, rank: number) => {
		let m = edges.get(from);
		if (!m) edges.set(from, (m = new Map()));
		const cur = m.get(to);
		if (!cur || rank > cur.rank) m.set(to, { rel, rank });
	};
	/** Link a and b, named from both ends; a hint the table takes ranks `rank`, else the kinds name it. */
	const link = (a: string, b: string, hint: string | null, rank: number) => {
		if (!a || !b || a === b) return;
		const ka = kindOfUrn(a);
		const kb = kindOfUrn(b);
		if (!ka || !kb) return;
		const ab = relId(ka, kb, hint);
		const named = !!hint && ab === hint;
		const ba = named ? reverseRel(ab, ka, kb) : relId(kb, ka);
		const r = named ? rank : NAMED_BY_KINDS;
		setEdge(a, b, ab, r);
		setEdge(b, a, ba, r);
	};

	for (const e of entities) for (const l of e.links) link(e.urn, l, null, NAMED_BY_KINDS);
	for (const d of input.dossiers ?? []) for (const r of d.related) link(d.entity.urn, r.entity.urn, r.relation, NAMED_BY_DOSSIER);
	for (const row of rows.values()) for (const l of impliedLinks(row)) link(row.urn, l.urn, l.rel, NAMED_BY_PROPS);

	const all = [...rows.values()];
	let kindIndex: Map<string, ObjectRow[]> | null = null;
	const version = ++builds;

	return {
		version,
		size: rows.size,
		get(urn) {
			return urn ? (rows.get(urn) ?? null) : null;
		},
		all() {
			return all;
		},
		byKind(kind) {
			if (!kindIndex) {
				kindIndex = new Map();
				for (const r of all) {
					const list = kindIndex.get(r.kind);
					if (list) list.push(r);
					else kindIndex.set(r.kind, [r]);
				}
			}
			return kindIndex.get(kind) ?? [];
		},
		links(urn) {
			const out: ObjectLink[] = [];
			for (const [other, e] of edges.get(urn) ?? []) {
				const row = rows.get(other);
				if (row) out.push({ relation: e.rel, row });
			}
			return out;
		},
	};
}

/** The empty graph (no source answered yet). */
export const EMPTY_GRAPH: ObjectGraph = buildObjectGraph({});

export { rowOf, impliedLinks };
export { relId, relName, relLabel, reverseRel } from './relations';
export { adapterFor, eventRow, recommendationRow, dispatchRow } from './kinds';
