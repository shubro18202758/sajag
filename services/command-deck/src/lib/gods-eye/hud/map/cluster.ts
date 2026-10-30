/**
 * Marker clustering in screen space (SPEC §5.3 "Markers", §13.5).
 *
 * Markers closer than `radiusPx` (22 px on the operator map) merge into one
 * disc that wears a neutral count chip. A cluster's LEAD is the member the
 * operator is most likely after: one on the selection's track first
 * (`lead: true`), then the higher `weight`, then the id, so a re-run on the
 * same picture always picks the same lead. The cluster sits where its lead
 * is drawn; the other members are hidden until a click spiderfies them.
 *
 * Greedy, deterministic: points are taken in lead order and each joins the
 * first cluster whose lead lies within the radius, else starts its own.
 * O(n²) for 50 points or fewer; above that the cluster leads are bucketed in
 * a grid of radius-sized cells, so a point checks only the 3×3 cells around
 * it. Runs on camera-move end and on data change, never per frame.
 *
 * Exported for other layers to reuse (plan contract X7):
 *   clusterMarkers(points, radiusPx) → Cluster[]
 *   clusterAround(anchors, points, radiusPx, keep?) → Cluster[] (fixed leads first)
 */

/** A marker's screen position (CSS px, origin top-left) and its claim to lead. */
export interface ClusterPoint {
	id: string;
	x: number;
	y: number;
	/** On the selection's track (or otherwise preferred): leads its cluster. */
	lead?: boolean;
	/** Higher weight leads among equals (e.g. a marker with a waiting decision). */
	weight?: number;
}

/** One drawn disc: its lead (where it is drawn) and every member, lead first. */
export interface Cluster {
	lead: string;
	members: string[];
	x: number;
	y: number;
}

/** The operator map's merge distance (SPEC §5.3). */
export const CLUSTER_RADIUS_PX = 22;

/** Above this many points the leads are grid-bucketed instead of compared pairwise. */
export const CLUSTER_GRID_ABOVE = 50;

function order(a: ClusterPoint, b: ClusterPoint): number {
	return (
		Number(!!b.lead) - Number(!!a.lead) ||
		(b.weight ?? 0) - (a.weight ?? 0) ||
		(a.id < b.id ? -1 : a.id > b.id ? 1 : 0)
	);
}

const finite = (p: ClusterPoint) => Number.isFinite(p.x) && Number.isFinite(p.y);

/**
 * Merge markers closer than `radiusPx` (strictly less) into clusters.
 * Points with non-finite positions are left out. Pure.
 */
export function clusterMarkers(points: readonly ClusterPoint[], radiusPx: number = CLUSTER_RADIUS_PX): Cluster[] {
	const r = Number.isFinite(radiusPx) && radiusPx > 0 ? radiusPx : CLUSTER_RADIUS_PX;
	const sorted = points.filter(finite).sort(order);
	const clusters: Cluster[] = [];
	const near = (c: Cluster, p: ClusterPoint) => Math.hypot(c.x - p.x, c.y - p.y) < r;

	if (sorted.length <= CLUSTER_GRID_ABOVE) {
		for (const p of sorted) {
			const hit = clusters.find((c) => near(c, p));
			if (hit) hit.members.push(p.id);
			else clusters.push({ lead: p.id, members: [p.id], x: p.x, y: p.y });
		}
		return clusters;
	}

	// Grid-bucketed: a cluster lead lives in the cell of its position; a point
	// within r of a lead is at most one cell away in each direction.
	const grid = new Map<string, Cluster[]>();
	const cell = (v: number) => Math.floor(v / r);
	for (const p of sorted) {
		const cx = cell(p.x);
		const cy = cell(p.y);
		let hit: Cluster | null = null;
		let hitIndex = Number.POSITIVE_INFINITY;
		for (let dx = -1; dx <= 1 && hitIndex > 0; dx++) {
			for (let dy = -1; dy <= 1; dy++) {
				for (const c of grid.get(`${cx + dx}:${cy + dy}`) ?? []) {
					// the FIRST cluster in creation order wins, as in the pairwise pass
					const i = clusters.indexOf(c);
					if (i < hitIndex && near(c, p)) {
						hit = c;
						hitIndex = i;
					}
				}
			}
		}
		if (hit) {
			hit.members.push(p.id);
			continue;
		}
		const c: Cluster = { lead: p.id, members: [p.id], x: p.x, y: p.y };
		clusters.push(c);
		const key = `${cx}:${cy}`;
		const list = grid.get(key);
		if (list) list.push(c);
		else grid.set(key, [c]);
	}
	return clusters;
}

/**
 * Clusters around fixed ANCHORS (a pursuit's choke squares, SPEC §5.3): a
 * point closer than `radiusPx` to an anchor joins the nearest anchor's
 * cluster, which the anchor leads, so the square is drawn above whatever
 * sits at its junction (a camera there wears the anchor's count chip and
 * spreads out on a click). Anchors never merge with each other or with the
 * points' own clusters; a point `keep` says must stay in view (the
 * selection's, one with a waiting decision) is never absorbed; the points
 * left over cluster as clusterMarkers does. Every anchor is returned, alone
 * when nothing sits under it. Pure.
 */
export function clusterAround(
	anchors: readonly ClusterPoint[],
	points: readonly ClusterPoint[],
	radiusPx: number = CLUSTER_RADIUS_PX,
	keep: (p: ClusterPoint) => boolean = () => false,
): Cluster[] {
	const r = Number.isFinite(radiusPx) && radiusPx > 0 ? radiusPx : CLUSTER_RADIUS_PX;
	const leads = anchors.filter(finite).sort(order);
	const out: Cluster[] = leads.map((a) => ({ lead: a.id, members: [a.id], x: a.x, y: a.y }));
	const anchored = new Set(leads.map((a) => a.id));
	const rest: ClusterPoint[] = [];
	for (const p of [...points].filter(finite).sort(order)) {
		if (anchored.has(p.id)) continue;
		if (keep(p)) {
			rest.push(p);
			continue;
		}
		let best: Cluster | null = null;
		let bestD = r;
		for (const c of out) {
			const d = Math.hypot(c.x - p.x, c.y - p.y);
			if (d < bestD) {
				best = c;
				bestD = d;
			}
		}
		if (best) best.members.push(p.id);
		else rest.push(p);
	}
	return [...out, ...clusterMarkers(rest, r)];
}

/**
 * Spider positions: `n` members fanned out on a circle around their lead
 * (screen offsets in px, the first at 12 o'clock, clockwise). The radius
 * grows with the count so 21 px discs never overlap: the chord between
 * neighbours stays ≥ `spacing`.
 */
export function spiderOffsets(n: number, spacing = 26, minRadius = 30): Array<{ x: number; y: number }> {
	const count = Math.max(0, Math.floor(n));
	if (count === 0) return [];
	const radius = Math.max(minRadius, count > 1 ? spacing / (2 * Math.sin(Math.PI / count)) : minRadius);
	const out: Array<{ x: number; y: number }> = [];
	for (let i = 0; i < count; i++) {
		const a = -Math.PI / 2 + (2 * Math.PI * i) / count;
		out.push({ x: Math.round(radius * Math.cos(a) * 10) / 10, y: Math.round(radius * Math.sin(a) * 10) / 10 });
	}
	return out;
}
