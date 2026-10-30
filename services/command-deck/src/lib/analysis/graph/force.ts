/**
 * The force layout (SPEC §5.3 "alternatives: force"), on the vendored ISC
 * d3-force 3.0.0 (src/lib/vendor/d3-force, SPEC §13.9 — no npm dependency).
 *
 * Deterministic: the simulation starts from the radial positions and d3's
 * own seeded random source (lcg), runs a fixed number of ticks (its timer is
 * stopped at once — nothing animates, nothing keeps a frame loop alive), and
 * hands the positions to computeLayout({mode: 'given'}) for the same
 * relaxation, fit and label pass as the radial layout.
 *
 * forcePositions runs the ticks in one go (≤ 80 nodes: a few tens of ms);
 * forcePositionsSliced runs the SAME ticks in slices, yielding to the event
 * loop between them, so a large graph never blocks the main thread for the
 * whole run (SPEC §13.6) — the vendored d3 modules cannot be posted to a
 * blob: worker as one self-contained body. Same ticks, same positions.
 */
import { forceCollide, forceLink, forceManyBody, forceSimulation, forceX, forceY } from '$lib/vendor/d3-force/src/index.js';
import type { LayoutNodeIn } from './layout';

interface SimNode {
	id: string;
	r: number;
	x: number;
	y: number;
	vx?: number;
	vy?: number;
	fx?: number | null;
	fy?: number | null;
}

interface SimLink {
	source: string | SimNode;
	target: string | SimNode;
	role: string;
}

/** The typed surface of the vendored simulation this module uses. */
interface Simulation {
	stop(): Simulation;
	tick(n?: number): Simulation;
	force(name: string, f: unknown): Simulation;
	nodes(): SimNode[];
}

/** Ticks per run (d3's own default cooling reaches alphaMin in 300). */
export const FORCE_TICKS = 300;

/** Ticks per slice of the sliced run (one slice ≈ a few ms for a few hundred nodes). */
export const FORCE_SLICE_TICKS = 20;

/** The stopped simulation over `nodes` and `edges`, seeded from `seed`. */
function simulation(
	nodes: readonly LayoutNodeIn[],
	edges: readonly { a: string; b: string }[],
	focus: string,
	seed: Record<string, { x: number; y: number }>,
): Simulation {
	const sim: SimNode[] = nodes.map((n) => {
		const s = seed[n.id] ?? { x: 0, y: 0 };
		const fixed = n.id === focus;
		return { id: n.id, r: n.r, x: s.x, y: s.y, fx: fixed ? s.x : null, fy: fixed ? s.y : null };
	});
	const ids = new Set(sim.map((n) => n.id));
	const role = new Map(nodes.map((n) => [n.id, n.role]));
	const links: SimLink[] = edges.filter((e) => ids.has(e.a) && ids.has(e.b)).map((e) => ({ source: e.a, target: e.b, role: role.get(e.b) ?? 'inner' }));
	const f = seed[focus] ?? { x: 0, y: 0 };
	const make = forceSimulation as unknown as (n: SimNode[]) => Simulation;
	const link = (forceLink as unknown as (l: SimLink[]) => { id(fn: (d: SimNode) => string): unknown })(links) as {
		id(fn: (d: SimNode) => string): { distance(fn: (l: SimLink) => number): { strength(v: number): unknown } };
	};
	const s = make(sim)
		.stop()
		.force(
			'link',
			link
				.id((d) => d.id)
				.distance((l) => (l.role === 'hub' ? 110 : l.role === 'satellite' || l.role === 'tertiary' ? 42 : 70))
				.strength(0.7),
		)
		.force('charge', (forceManyBody as unknown as () => { strength(v: number): unknown })().strength(-140))
		.force('collide', (forceCollide as unknown as (fn: (d: SimNode) => number) => unknown)((d) => d.r + 8))
		.force('x', (forceX as unknown as (v: number) => { strength(v: number): unknown })(f.x).strength(0.04))
		.force('y', (forceY as unknown as (v: number) => { strength(v: number): unknown })(f.y).strength(0.04));
	return s;
}

function positions(s: Simulation): Record<string, { x: number; y: number }> {
	const out: Record<string, { x: number; y: number }> = {};
	for (const n of s.nodes()) out[n.id] = { x: n.x, y: n.y };
	return out;
}

/** Force-directed positions for `nodes` (edges `[a, b]`), seeded from `seed` (the radial positions), in one run. */
export function forcePositions(
	nodes: readonly LayoutNodeIn[],
	edges: readonly { a: string; b: string }[],
	focus: string,
	seed: Record<string, { x: number; y: number }>,
	ticks = FORCE_TICKS,
): Record<string, { x: number; y: number }> {
	const s = simulation(nodes, edges, focus, seed);
	s.tick(ticks);
	return positions(s);
}

/** The same positions as forcePositions, the ticks run in slices with the event loop free between them. */
export async function forcePositionsSliced(
	nodes: readonly LayoutNodeIn[],
	edges: readonly { a: string; b: string }[],
	focus: string,
	seed: Record<string, { x: number; y: number }>,
	ticks = FORCE_TICKS,
	slice = FORCE_SLICE_TICKS,
): Promise<Record<string, { x: number; y: number }>> {
	const s = simulation(nodes, edges, focus, seed);
	for (let done = 0; done < ticks; ) {
		const n = Math.min(slice, ticks - done);
		s.tick(n);
		done += n;
		if (done < ticks) await new Promise<void>((r) => setTimeout(r, 0));
	}
	return positions(s);
}
