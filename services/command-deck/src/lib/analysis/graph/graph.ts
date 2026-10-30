/**
 * The link graph's model (SPEC §5.3 "LinkGraph [S4]", §8.3), pure: the focus
 * object, its linked objects (the workspace's one object model, named from
 * both ends), and what the radial layout needs to know of each — its ROLE by
 * link type:
 *
 *   focus      the centre
 *   hub        cameras (and other infrastructure: junctions, roads) on a
 *              ring, in latest-pass order, so the ring reads like the route
 *   satellite  sightings on an arc outside their camera
 *   tertiary   recommendations outside their evidence sighting
 *   inner      links no camera mediates (pursuits, OSINT `reported_at` /
 *              `corroborates`, unattached decisions) on an inner ring
 *   merged     more than 8 links of one type to the focus collapse into one
 *              node with a count ("14 rejected"); Expand merged reverses it
 *   extra      objects Search around or Find paths added beyond one hop
 *
 * Merging (MERGE_OVER = 8). A link type is the relation from the focus and
 * the object's state ("recommendation · rejected"). A group of more than 8
 * collapses when its state is settled (rejected, dismissed, cancelled,
 * completed, expired …) or when none of it is mediated by a hub (every member
 * would crowd the inner ring). It never swallows an object that needs
 * attention — a pending decision, an alert, a selected object — so a merged
 * node never hides a decision waiting. Reads around a camera are never merged.
 *
 * Find paths: the shortest chain between two objects over the whole object
 * model (breadth first, at most MAX_PATH_HOPS hops), its objects added to the
 * graph and its edges marked.
 */
import { t } from '$lib/i18n/strings';
import '$lib/i18n/packs.analysis';
import { kindIcon, objectIcon, type IconName } from '$lib/design/icons';
import { fmtDay, fmtStamp, fmtTime, type SvgLabelPart } from '$lib/ui/format/format';
import { relLabel } from '$lib/workspace/relations';
import { kindOne, stateWord } from '$lib/workspace/kinds/generic';
import type { ObjectLink, ObjectRow } from '$lib/workspace/types';

/** What the graph reads of the object model (an ObjectGraph satisfies it). */
export interface GraphSource {
	get(urn: string | null | undefined): ObjectRow | null;
	links(urn: string): readonly ObjectLink[];
}

export type NodeRole = 'focus' | 'hub' | 'satellite' | 'tertiary' | 'inner' | 'merged' | 'extra';

export interface GNode {
	/** The URN (an object) or `agg:<relation>:<state>` (a merged node). */
	id: string;
	urn: string | null;
	kind: string;
	row: ObjectRow | null;
	role: NodeRole;
	/** The node it hangs off (a hub for a satellite, a sighting for a recommendation …), null for the focus and inner nodes. */
	parent: string | null;
	/** The relation from the focus (or from the parent) that brought it in. */
	relation: string;
	/** Radius (px). */
	r: number;
	icon: IconName;
	/** Its own time (epoch ms), for ordering and the time window. */
	t: number | null;
	/** Ordering key within its role (ring order, arc order). */
	order: number;
	/** The label (null: no label unless selected). */
	label: SvgLabelPart[];
	labelText: string;
	labelW: number;
	/**
	 * A shorter label the layout may draw when the full one fits nowhere near
	 * the node ("Pursuit · cancelled" for "Pursuit · cancelled · 24 Oct"); the
	 * full label stays in the hover. Null: the label has no shorter form.
	 */
	shortLabel: SvgLabelPart[] | null;
	shortW: number | null;
	/** Drawn with a label when nothing collides (satellites only when selected). */
	wantLabel: boolean;
	/** Label priority: focus, selection, merged, events, cameras, then the rest. */
	priority: number;
	/** State dot: orange pending, green approved. */
	dot: 'pending' | 'approved' | null;
	/** Red ring: watchlisted or stolen. */
	alert: boolean;
	/** A merged node's count and members. */
	agg: { count: number; relation: string; state: string | null; members: string[] } | null;
}

export interface GEdge {
	id: string;
	a: string;
	b: string;
	/** The relation id, named from `a`'s end. */
	rel: string;
	/** The link type in words (hover). */
	label: string;
	/** Part of a found path. */
	path: boolean;
}

export interface GraphModel {
	focus: string;
	nodes: GNode[];
	edges: GEdge[];
	/** "51 linked · 14 merged": linked = the focus's 1-hop objects; merged = objects inside merged nodes. */
	stats: { linked: number; merged: number; nodes: number; edges: number; mergeable: number };
}

export interface BuildOptions {
	lang?: string;
	/** Show merged links one by one. */
	expandMerged?: boolean;
	/** Objects that must stay their own node (the selection). */
	keep?: readonly string[];
	/** Search around: object → the relation ids added from it. */
	expansions?: ReadonlyMap<string, ReadonlySet<string>>;
	/** Found paths (each a chain of URNs). */
	paths?: readonly (readonly string[])[];
	/** An anchor for times in labels (now). */
	anchor?: number;
}

/** More than this many links of one type to one node merge. */
export const MERGE_OVER = 8;
/** The longest chain Find paths follows. */
export const MAX_PATH_HOPS = 6;
/** Objects one Search around step may add. */
export const SEARCH_AROUND_MAX = 60;

const HUB_KINDS: ReadonlySet<string> = new Set(['camera', 'junction', 'segment']);
const HUB_RANK: Readonly<Record<string, number>> = { camera: 0, junction: 1, segment: 2 };
/** States that are over: a group of them may merge even when a hub mediates it. */
const SETTLED: ReadonlySet<string> = new Set([
	'rejected',
	'dismissed',
	'cancelled',
	'canceled',
	'completed',
	'closed',
	'expired',
	'superseded',
	'withdrawn',
	'resolved',
	'deferred',
]);
const PENDING: ReadonlySet<string> = new Set(['pending', 'proposed', 'requested', 'awaiting', 'awaiting_officer', 'needs_decision']);
const APPROVED: ReadonlySet<string> = new Set(['approved', 'confirmed', 'authorised', 'authorized']);

/** Rough text width at 12 px: Inter ≈ 6.4 px a character, JetBrains Mono ≈ 7.3 (the prototype's measure). */
export function textWidth(parts: readonly SvgLabelPart[]): number {
	let w = 0;
	parts.forEach((p, i) => {
		const s = 'id' in p ? p.id : 'text' in p ? p.text : fmtTime(p.time);
		w += Math.ceil(s.length * ('id' in p ? 7.3 : 6.4)) + (i > 0 ? 4 : 0);
	});
	return w + 2;
}

function attention(row: ObjectRow | null, keep: ReadonlySet<string>): boolean {
	if (!row) return false;
	if (keep.has(row.urn)) return true;
	if (row.state && PENDING.has(row.state)) return true;
	return row.stateIntent === 'danger' || row.kind === 'vehicle';
}

function dotOf(row: ObjectRow | null): GNode['dot'] {
	if (!row?.state) return null;
	if (PENDING.has(row.state)) return 'pending';
	if (APPROVED.has(row.state)) return 'approved';
	return null;
}

/** The shorter form of a node's label (an event without its day), or null when there is none. */
export function nodeShortLabel(row: ObjectRow, lang = 'en'): SvgLabelPart[] | null {
	if (row.kind !== 'event') return null;
	const p = row.props ?? {};
	const ek = typeof p.event_kind === 'string' ? p.event_kind : null;
	const what = ek === 'vehicle_pursuit' ? t(lang, 'an_g_pursuit') : row.label.length > 18 ? `${row.label.slice(0, 17)}…` : row.label;
	const st = stateWord(row.state, lang);
	return [{ text: [what, st?.toLowerCase()].filter(Boolean).join(' · ') }];
}

/** The label of an object in the graph (SPEC §5.3: ids mono, times Inter). */
export function nodeLabel(row: ObjectRow, lang = 'en', anchor = Date.now()): SvgLabelPart[] {
	const p = row.props ?? {};
	switch (row.kind) {
		case 'vehicle':
			return [{ id: row.label }];
		case 'camera':
			return [{ id: row.id }];
		case 'sighting': {
			const cam = typeof p.camera_id === 'string' ? p.camera_id : null;
			return cam && row.t != null ? [{ id: cam }, { time: row.t }] : [{ text: row.label }];
		}
		case 'event': {
			const ek = typeof p.event_kind === 'string' ? p.event_kind : null;
			const what = ek === 'vehicle_pursuit' ? t(lang, 'an_g_pursuit') : row.label.length > 26 ? `${row.label.slice(0, 25)}…` : row.label;
			const st = stateWord(row.state, lang);
			const day = row.t != null ? fmtDay(row.t) : null;
			return [{ text: [what, st?.toLowerCase(), day].filter(Boolean).join(' · ') }];
		}
		case 'recommendation': {
			const st = stateWord(row.state, lang) ?? kindOne('recommendation', lang);
			return row.t != null ? [{ text: `${st} · ${fmtStamp(row.t, anchor)}` }] : [{ text: st }];
		}
		default: {
			const s = row.label || row.id;
			return [{ text: s.length > 30 ? `${s.slice(0, 29)}…` : s }];
		}
	}
}

function partsText(parts: readonly SvgLabelPart[]): string {
	return parts.map((p) => ('id' in p ? p.id : 'text' in p ? p.text : fmtTime(p.time))).join(' ');
}

/** The relation of `to` seen from `from` in the object model, or null. */
function relBetween(src: GraphSource, from: string, to: string): string | null {
	for (const l of src.links(from)) if (l.row.urn === to) return l.relation;
	return null;
}

function kindOfUrn(urn: string): string {
	const i = urn.indexOf(':');
	return i > 0 ? urn.slice(0, i) : urn;
}

/**
 * The shortest chain of URNs from `a` to `b` over the object model, at most
 * `maxHops` links; null when none (or a and b are the same object).
 */
export function findPath(src: GraphSource, a: string, b: string, maxHops = MAX_PATH_HOPS): string[] | null {
	if (!a || !b || a === b) return null;
	const prev = new Map<string, string | null>([[a, null]]);
	let frontier = [a];
	for (let hop = 0; hop < maxHops && frontier.length; hop++) {
		const next: string[] = [];
		for (const u of frontier) {
			const links = [...src.links(u)].sort((x, y) => (x.row.urn < y.row.urn ? -1 : 1));
			for (const l of links) {
				const v = l.row.urn;
				if (prev.has(v)) continue;
				prev.set(v, u);
				if (v === b) {
					const chain = [b];
					let cur: string | null = u;
					while (cur) {
						chain.push(cur);
						cur = prev.get(cur) ?? null;
					}
					return chain.reverse();
				}
				next.push(v);
			}
		}
		frontier = next;
		if (prev.size > 20_000) break;
	}
	return null;
}

/** The link types around `urn` (relation id, words, how many objects), the ones in `present` counted as shown. */
export function linkTypes(src: GraphSource, urn: string, present: ReadonlySet<string>, lang = 'en'): { relation: string; label: string; count: number; added: number }[] {
	const by = new Map<string, { relation: string; kind: string; count: number; added: number }>();
	for (const l of src.links(urn)) {
		const e = by.get(l.relation) ?? { relation: l.relation, kind: l.row.kind, count: 0, added: 0 };
		e.count++;
		if (present.has(l.row.urn)) e.added++;
		by.set(l.relation, e);
	}
	return [...by.values()]
		.map((e) => ({ relation: e.relation, label: relLabel(e.relation, e.kind, lang), count: e.count, added: e.added }))
		.sort((x, y) => y.count - x.count || (x.label < y.label ? -1 : 1));
}

/** Build the graph around `focus`. Returns null when the focus is not in the model. */
export function buildGraph(src: GraphSource, focus: string, opts: BuildOptions = {}): GraphModel | null {
	const lang = opts.lang ?? 'en';
	const anchor = opts.anchor ?? Date.now();
	const focusRow = src.get(focus);
	if (!focusRow) return null;
	const keep = new Set(opts.keep ?? []);

	// ── 1-hop links of the focus, each once ──────────────────────────────
	const linked: ObjectLink[] = [];
	const seen = new Set<string>([focus]);
	for (const l of src.links(focus)) {
		if (seen.has(l.row.urn)) continue;
		seen.add(l.row.urn);
		linked.push(l);
	}
	const linkedSet = new Set(linked.map((l) => l.row.urn));

	// ── roles: hubs, satellites (sightings first), tertiaries, inner ─────
	const role = new Map<string, NodeRole>();
	const parent = new Map<string, string>();
	const hubs = linked.filter((l) => HUB_KINDS.has(l.row.kind) && l.row.urn !== focus);
	const hubSet = new Set(hubs.map((h) => h.row.urn));
	for (const h of hubs) role.set(h.row.urn, 'hub');

	const linkedTo = (urn: string, pool: ReadonlySet<string>): string[] => {
		const out: string[] = [];
		for (const l of src.links(urn)) if (pool.has(l.row.urn)) out.push(l.row.urn);
		return out;
	};
	const bestHub = (cands: string[]): string | null =>
		cands.sort((a, b) => (HUB_RANK[kindOfUrn(a)] ?? 9) - (HUB_RANK[kindOfUrn(b)] ?? 9) || (a < b ? -1 : 1))[0] ?? null;

	// pass A: sightings hang off their camera
	for (const l of linked) {
		if (role.has(l.row.urn) || l.row.kind !== 'sighting') continue;
		const cam = typeof l.row.props.camera_id === 'string' ? `camera:${l.row.props.camera_id}` : null;
		const p = cam && hubSet.has(cam) ? cam : bestHub(linkedTo(l.row.urn, hubSet));
		if (p) {
			role.set(l.row.urn, 'satellite');
			parent.set(l.row.urn, p);
		}
	}
	const sats = new Set([...role].filter(([, r]) => r === 'satellite').map(([u]) => u));
	// pass B: an object with evidence among the satellites hangs off it; else off a hub; else the inner ring
	for (const l of linked) {
		const u = l.row.urn;
		if (role.has(u)) continue;
		const ev = typeof l.row.props.sighting_id === 'string' ? `sighting:${l.row.props.sighting_id}` : null;
		const viaSat = ev && sats.has(ev) ? ev : (linkedTo(u, sats).sort()[0] ?? null);
		if (viaSat && l.row.kind !== 'event') {
			role.set(u, 'tertiary');
			parent.set(u, viaSat);
			continue;
		}
		const viaHub = l.row.kind === 'event' || l.row.kind === 'osint_event' || l.row.kind === 'place' ? null : bestHub(linkedTo(u, hubSet));
		if (viaHub) {
			role.set(u, 'satellite');
			parent.set(u, viaHub);
			continue;
		}
		role.set(u, 'inner');
	}

	// ── merging: > 8 links of one type (relation · state) ────────────────
	const groups = new Map<string, ObjectLink[]>();
	for (const l of linked) {
		if (HUB_KINDS.has(l.row.kind)) continue;
		const key = `${l.relation}|${l.row.state ?? ''}`;
		const g = groups.get(key);
		if (g) g.push(l);
		else groups.set(key, [l]);
	}
	const mergedInto = new Map<string, string>();
	const aggs: GNode[] = [];
	let mergeable = 0;
	for (const [key, list] of groups) {
		const [relation, state] = key.split('|');
		const members = list.filter((l) => !attention(l.row, keep));
		if (members.length <= MERGE_OVER) continue;
		const settled = !!state && SETTLED.has(state);
		const unmediated = members.every((l) => role.get(l.row.urn) === 'inner');
		if (!settled && !unmediated) continue;
		mergeable += members.length;
		if (opts.expandMerged) continue;
		const id = `agg:${relation}:${state || 'any'}`;
		const kind = members[0].row.kind;
		const word = state ? (stateWord(state, lang) ?? state).toLowerCase() : relLabel(relation, kind, lang).toLowerCase();
		const text = t(lang, 'an_g_merged_label', members.length, word);
		const label: SvgLabelPart[] = [{ text }];
		for (const l of members) mergedInto.set(l.row.urn, id);
		aggs.push({
			id,
			urn: null,
			kind,
			row: null,
			role: 'merged',
			parent: null,
			relation,
			r: 14,
			icon: kindIcon(kind),
			t: Math.max(...members.map((l) => l.row.t ?? 0)) || null,
			order: 0,
			label,
			labelText: text,
			labelW: textWidth(label),
			shortLabel: null,
			shortW: null,
			wantLabel: true,
			priority: 6,
			dot: null,
			alert: false,
			agg: { count: members.length, relation, state: state || null, members: members.map((l) => l.row.urn) },
		});
	}

	// ── nodes ────────────────────────────────────────────────────────────
	const nodes: GNode[] = [];
	const byId = new Map<string, GNode>();
	const mk = (row: ObjectRow, r: NodeRole, rel: string, par: string | null): GNode => {
		const label = nodeLabel(row, lang, anchor);
		const labelText = partsText(label);
		const short = nodeShortLabel(row, lang);
		const shortOk = short && partsText(short) !== labelText ? short : null;
		const pri = r === 'focus' ? 9 : row.kind === 'event' || row.kind === 'osint_event' ? 5 : HUB_KINDS.has(row.kind) ? 3 : 1;
		return {
			id: row.urn,
			urn: row.urn,
			kind: row.kind,
			row,
			role: r,
			parent: par,
			relation: rel,
			r: r === 'focus' ? 20 : r === 'hub' ? 14 : r === 'satellite' || r === 'tertiary' ? (row.kind === 'recommendation' ? 9 : 8) : r === 'extra' ? 10 : 11,
			icon: objectIcon(row.kind, typeof row.props.event_kind === 'string' ? row.props.event_kind : null),
			t: row.t,
			order: 0,
			label,
			labelText,
			labelW: textWidth(label),
			shortLabel: shortOk,
			shortW: shortOk ? textWidth(shortOk) : null,
			wantLabel: r === 'focus' || r === 'hub' || r === 'inner' || r === 'extra',
			priority: pri,
			dot: dotOf(row),
			alert: row.kind === 'vehicle' || row.stateIntent === 'danger',
			agg: null,
		};
	};
	const push = (n: GNode) => {
		if (byId.has(n.id)) return;
		byId.set(n.id, n);
		nodes.push(n);
	};
	push(mk(focusRow, 'focus', '', null));
	for (const l of linked) {
		if (mergedInto.has(l.row.urn)) continue;
		const r = role.get(l.row.urn) ?? 'inner';
		const par = parent.get(l.row.urn) ?? null;
		// a satellite whose parent was merged away falls back to the inner ring
		const parOk = par && !mergedInto.has(par) ? par : null;
		push(mk(l.row, parOk || r === 'hub' || r === 'inner' ? r : 'inner', l.relation, parOk));
	}
	for (const a of aggs) push(a);

	// ── Search around and Find paths: objects beyond one hop ─────────────
	const addExtra = (urn: string, from: string) => {
		if (byId.has(urn) || mergedInto.has(urn)) return;
		const row = src.get(urn);
		if (!row) return;
		const rel = relBetween(src, from, urn) ?? kindOfUrn(urn);
		push(mk(row, 'extra', rel, byId.has(from) ? from : focus));
	};
	for (const [from, rels] of opts.expansions ?? []) {
		if (!byId.has(from) && !mergedInto.has(from)) continue;
		let n = 0;
		for (const l of src.links(from)) {
			if (!rels.has(l.relation) || l.row.urn === focus) continue;
			if (n++ >= SEARCH_AROUND_MAX) break;
			addExtra(l.row.urn, mergedInto.get(from) ?? from);
		}
	}
	const pathEdges = new Set<string>();
	for (const chain of opts.paths ?? []) {
		for (let i = 0; i < chain.length; i++) {
			if (i > 0) addExtra(chain[i], chain[i - 1]);
			if (i > 0) pathEdges.add(`${chain[i - 1]}>${chain[i]}`);
		}
	}

	// ── ordering: the ring in latest-pass order, arcs by time ────────────
	const lastPass = new Map<string, number>();
	for (const n of nodes) {
		if (n.role !== 'satellite' || !n.parent) continue;
		lastPass.set(n.parent, Math.max(lastPass.get(n.parent) ?? 0, n.t ?? 0));
	}
	const ring = nodes.filter((n) => n.role === 'hub').sort((a, b) => (lastPass.get(a.id) ?? 0) - (lastPass.get(b.id) ?? 0) || (a.id < b.id ? -1 : 1));
	ring.forEach((n, i) => (n.order = i));
	const byTime = (a: GNode, b: GNode) => (a.t ?? 0) - (b.t ?? 0) || (a.id < b.id ? -1 : 1);
	const innerRank = (n: GNode) => (n.kind === 'event' ? 0 : n.kind === 'osint_event' ? 1 : n.role === 'merged' ? 3 : 2);
	nodes
		.filter((n) => n.role === 'inner' || n.role === 'merged')
		.sort((a, b) => innerRank(a) - innerRank(b) || byTime(a, b))
		.forEach((n, i) => (n.order = i));
	const arcs = new Map<string, GNode[]>();
	for (const n of nodes) {
		if ((n.role === 'satellite' || n.role === 'tertiary' || n.role === 'extra') && n.parent) {
			const a = arcs.get(n.parent);
			if (a) a.push(n);
			else arcs.set(n.parent, [n]);
		}
	}
	for (const list of arcs.values()) list.sort(byTime).forEach((n, i) => (n.order = i));

	// ── edges ────────────────────────────────────────────────────────────
	const edges: GEdge[] = [];
	const edgeIds = new Set<string>();
	const addEdge = (a: string, b: string, rel: string | null, path = false) => {
		if (a === b || !byId.has(a) || !byId.has(b)) return;
		const id = `${a}>${b}`;
		if (edgeIds.has(id) || edgeIds.has(`${b}>${a}`)) {
			if (path) for (const e of edges) if (e.id === id || e.id === `${b}>${a}`) e.path = true;
			return;
		}
		edgeIds.add(id);
		const relation = rel ?? relBetween(src, a, b) ?? kindOfUrn(b);
		edges.push({ id, a, b, rel: relation, label: relLabel(relation, byId.get(b)?.kind ?? kindOfUrn(b), lang), path });
	};
	for (const n of nodes) {
		if (n.role === 'focus') continue;
		if (n.role === 'hub' || n.role === 'inner' || n.role === 'merged') addEdge(focus, n.id, n.relation);
		else if (n.parent) addEdge(n.parent, n.id, relBetween(src, n.parent, n.id) ?? n.relation);
	}
	// cross links of the inner ring (a pursuit → the recommendation that authorised it)
	const drawn = new Set(nodes.filter((n) => n.urn).map((n) => n.id));
	let cross = 0;
	for (const n of nodes) {
		if (n.role !== 'inner' || !n.urn || cross > 40) continue;
		for (const l of src.links(n.urn)) {
			if (l.row.urn === focus || !drawn.has(l.row.urn) || l.row.urn === n.parent) continue;
			addEdge(n.id, l.row.urn, l.relation);
			cross++;
		}
	}
	for (const pe of pathEdges) {
		const [a, b] = pe.split('>');
		addEdge(a, b, null, true);
	}

	// labels: the selection is always labelled and first among its peers
	for (const n of nodes) {
		if (n.urn && keep.has(n.urn)) {
			n.wantLabel = true;
			n.priority += 8;
		}
	}

	return {
		focus,
		nodes,
		edges,
		stats: {
			linked: linkedSet.size,
			merged: aggs.reduce((s, a) => s + (a.agg?.count ?? 0), 0),
			nodes: nodes.length,
			edges: edges.length,
			mergeable,
		},
	};
}
