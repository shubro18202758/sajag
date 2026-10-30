/**
 * The link graph's layout (SPEC §5.3, §13.6), deterministic and pure.
 *
 *   radial        the focus at the centre; hubs (cameras) on a ring of
 *                 radius 0.62·R in latest-pass order; satellites on arcs
 *                 outside their hub; tertiaries outside their satellite; the
 *                 inner ring (0.3·R, below the focus) for unmediated links
 *                 and merged nodes; R = min(W, 1.1·H)/2 − 36
 *   hierarchical  levels by link depth, left to right
 *   given         positions computed elsewhere (the force layout, force.ts)
 *
 * Then, in every mode: a fixed relaxation pass that pushes overlapping discs
 * apart (the focus never moves), a fit into the pane, a second relaxation in
 * screen pixels, and the labels — placed last, in priority order, greedily
 * over eight candidate positions (then eight further out) against the discs
 * and the labels already placed. Near before far: at each distance the full
 * label is tried, then its shorter form (an event without its day), before
 * the next distance out; and a label set apart from its disc is only placed
 * where it sits nearer its own disc than any other, with no other label
 * between them (else it would name the wrong node). A label that fits
 * nowhere is dropped (the node keeps
 * its hover). By construction no two placed labels overlap and no label
 * covers a disc.
 *
 * computeLayout() references NOTHING outside its own body: the graph posts
 * its source text to a `blob:` worker for more than SYNC_MAX_NODES nodes
 * (worker.ts), and runs it in place below that (< 30 ms for ≤ 80 nodes).
 */

export const SYNC_MAX_NODES = 80;

export type LayoutMode = 'radial' | 'force' | 'hierarchical';

export interface LayoutNodeIn {
	id: string;
	role: 'focus' | 'hub' | 'satellite' | 'tertiary' | 'inner' | 'merged' | 'extra';
	parent: string | null;
	r: number;
	order: number;
	labelW: number;
	/** The width of the label's shorter form (null: none). */
	shortW?: number | null;
	wantLabel: boolean;
	priority: number;
}

export interface LayoutInput {
	mode: 'radial' | 'hierarchical' | 'given';
	W: number;
	H: number;
	focus: string;
	nodes: LayoutNodeIn[];
	/** mode 'given': a position per node id (any scale; the pass fits them). */
	given?: Record<string, { x: number; y: number }>;
}

export interface LabelBox {
	x: number;
	y: number;
	w: number;
	h: number;
	/** The shorter form was placed (the full label did not fit near the node). */
	short?: boolean;
}

export interface LayoutOut {
	pos: Record<string, { x: number; y: number }>;
	labels: Record<string, LabelBox>;
	/** The radial R (px) for the pane. */
	R: number;
	/** Wall time the pass took (ms). */
	ms: number;
	/** Disc pairs still closer than their radii after relaxation (0 expected). */
	overlaps: number;
}

/** The pass. Self-contained (see above): keep every helper inside. */
export function computeLayout(input: LayoutInput): LayoutOut {
	const clock = () => (typeof performance !== 'undefined' && performance.now ? performance.now() : Date.now());
	const started = clock();
	const W = Math.max(160, input.W);
	const H = Math.max(160, input.H);
	const nodes = input.nodes.slice();
	const byId: Record<string, LayoutNodeIn> = {};
	for (const n of nodes) byId[n.id] = n;
	const pos: Record<string, { x: number; y: number }> = {};
	const cx = W / 2;
	const cy = H / 2 + 6;
	const R = Math.max(80, Math.min(W, 1.1 * H) / 2 - 36);
	const TAU = Math.PI * 2;
	const focusId = input.focus;

	const kids: Record<string, LayoutNodeIn[]> = {};
	for (const n of nodes) {
		if (!n.parent) continue;
		(kids[n.parent] = kids[n.parent] || []).push(n);
	}
	for (const k in kids) kids[k].sort((a, b) => a.order - b.order || (a.id < b.id ? -1 : 1));
	const angleOf = (id: string): number => {
		const p = pos[id];
		const f = pos[focusId];
		return p && f ? Math.atan2(p.y - f.y, p.x - f.x) : 0;
	};

	/** Children on arcs outside `id`, row after row when one arc is full. */
	const placeArc = (id: string, out: number, base: number, step: number, rings = true) => {
		const list = kids[id];
		if (!list || !list.length) return;
		const c = pos[id];
		let i = 0;
		let row = 0;
		while (i < list.length) {
			const d = base + row * step;
			const span = 1.5;
			const per = Math.max(1, Math.floor((d * span) / (2 * Math.max(...list.map((k) => k.r)) + 6)) + 1);
			const take = list.slice(i, i + per);
			take.forEach((k, j) => {
				const s = take.length > 1 ? (j / (take.length - 1) - 0.5) * span : 0;
				const a = out + s;
				pos[k.id] = { x: c.x + Math.cos(a) * d, y: c.y + Math.sin(a) * d * 0.92 };
			});
			i += take.length;
			row++;
			if (!rings) break;
		}
	};

	// ── seed positions ───────────────────────────────────────────────────
	if (input.mode === 'given' && input.given) {
		for (const n of nodes) {
			const g = input.given[n.id];
			pos[n.id] = g ? { x: g.x, y: g.y } : { x: cx, y: cy };
		}
	} else if (input.mode === 'hierarchical') {
		const level: Record<string, number> = { [focusId]: 0 };
		const depth = (n: LayoutNodeIn, guard = 0): number => {
			if (level[n.id] != null) return level[n.id];
			if (guard > 12) return 1;
			const p = n.parent ? byId[n.parent] : null;
			const v = p ? depth(p, guard + 1) + 1 : n.role === 'focus' ? 0 : 1;
			level[n.id] = v;
			return v;
		};
		for (const n of nodes) depth(n);
		const maxL = Math.max(1, ...nodes.map((n) => level[n.id]));
		const pad = 56;
		const colW = (W - 2 * pad - 120) / maxL;
		const cols: LayoutNodeIn[][] = [];
		for (const n of nodes) (cols[level[n.id]] = cols[level[n.id]] || []).push(n);
		for (let l = 0; l < cols.length; l++) {
			const col = cols[l] || [];
			col.sort((a, b) => {
				const pa = a.parent && pos[a.parent] ? pos[a.parent].y : 0;
				const pb = b.parent && pos[b.parent] ? pos[b.parent].y : 0;
				return pa - pb || a.order - b.order || (a.id < b.id ? -1 : 1);
			});
			const gap = Math.max(18, Math.min(40, (H - 2 * pad) / Math.max(1, col.length)));
			const top = cy - ((col.length - 1) * gap) / 2;
			col.forEach((n, i) => (pos[n.id] = { x: pad + l * colW, y: top + i * gap }));
		}
	} else {
		pos[focusId] = { x: cx, y: cy };
		const hubs = nodes.filter((n) => n.role === 'hub').sort((a, b) => a.order - b.order);
		const rHub = R * 0.62;
		const a0 = Math.PI * 0.85;
		hubs.forEach((n, i) => {
			const a = a0 + (i / Math.max(1, hubs.length)) * TAU;
			pos[n.id] = { x: cx + Math.cos(a) * rHub, y: cy + Math.sin(a) * rHub * 0.86 };
		});
		const sd = Math.max(34, Math.min(52, R * 0.21));
		for (const h of hubs) placeArc(h.id, angleOf(h.id), sd, 18);
		// tertiaries outside their satellite, along the satellite's outward line
		for (const n of nodes) {
			if (n.role !== 'tertiary' || !n.parent || !pos[n.parent]) continue;
			const sat = pos[n.parent];
			const hubId = byId[n.parent] ? byId[n.parent].parent : null;
			const h = hubId && pos[hubId] ? pos[hubId] : pos[focusId];
			const out = Math.atan2(sat.y - h.y, sat.x - h.x);
			const sibs = kids[n.parent] || [n];
			const j = sibs.indexOf(n);
			const s = sibs.length > 1 ? (j / (sibs.length - 1) - 0.5) * 1.0 : 0;
			pos[n.id] = { x: sat.x + Math.cos(out + s) * 30, y: sat.y + Math.sin(out + s) * 28 };
		}
		// the inner ring, centred below the focus
		const inner = nodes.filter((n) => n.role === 'inner' || n.role === 'merged').sort((a, b) => a.order - b.order);
		const rIn = R * 0.3;
		const stepA = inner.length > 8 ? TAU / inner.length : 0.72;
		inner.forEach((n, i) => {
			const a = Math.PI / 2 + (i - (inner.length - 1) / 2) * stepA;
			pos[n.id] = { x: cx + Math.cos(a) * rIn, y: cy + Math.sin(a) * rIn };
		});
		// children of inner nodes and extras: arcs outside their parent
		const pending = nodes.filter((n) => !pos[n.id]);
		let guard = 0;
		while (pending.length && guard++ < 8) {
			for (let i = pending.length - 1; i >= 0; i--) {
				const n = pending[i];
				const p = n.parent && pos[n.parent] ? n.parent : null;
				if (!p && n.parent) continue;
				if (!p) {
					const a = (i / Math.max(1, pending.length)) * TAU;
					pos[n.id] = { x: cx + Math.cos(a) * R * 0.95, y: cy + Math.sin(a) * R * 0.95 };
				} else placeArc(p, p === focusId ? (i / Math.max(1, pending.length)) * TAU : angleOf(p), 40, 18);
				if (pos[n.id]) pending.splice(i, 1);
			}
		}
		for (const n of pending) pos[n.id] = { x: cx, y: cy + R };
	}

	// ── relaxation: discs never overlap; the focus never moves ───────────
	const relax = (iters: number, gap: number) => {
		const list = nodes;
		const N = list.length;
		for (let it = 0; it < iters; it++) {
			let moved = false;
			for (let i = 0; i < N; i++) {
				const a = list[i];
				const pa = pos[a.id];
				for (let j = i + 1; j < N; j++) {
					const b = list[j];
					const pb = pos[b.id];
					let dx = pb.x - pa.x;
					let dy = pb.y - pa.y;
					let d = Math.sqrt(dx * dx + dy * dy);
					const min = a.r + b.r + gap;
					if (d >= min) continue;
					if (d < 0.01) {
						// coincident: a fixed direction from the pair's indices (deterministic)
						const ang = ((i * 7 + j * 13) % 360) * (Math.PI / 180);
						dx = Math.cos(ang);
						dy = Math.sin(ang);
						d = 1;
					}
					const push = min - d;
					const ux = dx / d;
					const uy = dy / d;
					const af = a.id === focusId ? 0 : b.id === focusId ? 1 : 0.5;
					const bf = 1 - af;
					pa.x -= ux * push * af;
					pa.y -= uy * push * af;
					pb.x += ux * push * bf;
					pb.y += uy * push * bf;
					moved = true;
				}
			}
			if (!moved) break;
		}
	};
	const N = nodes.length;
	relax(N > 150 ? 30 : 80, 6);

	// ── fit into the pane ───────────────────────────────────────────────
	let minX = Infinity;
	let maxX = -Infinity;
	let minY = Infinity;
	let maxY = -Infinity;
	for (const n of nodes) {
		const p = pos[n.id];
		minX = Math.min(minX, p.x - n.r);
		maxX = Math.max(maxX, p.x + n.r);
		minY = Math.min(minY, p.y - n.r);
		maxY = Math.max(maxY, p.y + n.r);
	}
	const padX = input.mode === 'hierarchical' ? 40 : 56;
	const padY = 36;
	const sc = Math.min((W - 2 * padX) / Math.max(1, maxX - minX), (H - 2 * padY) / Math.max(1, maxY - minY), 1.25);
	const mx = (minX + maxX) / 2;
	const my = (minY + maxY) / 2;
	for (const n of nodes) {
		const p = pos[n.id];
		p.x = W / 2 + (p.x - mx) * sc;
		p.y = H / 2 + (p.y - my) * sc;
	}
	relax(N > 150 ? 20 : 60, 4);
	// keep every disc inside the pane
	for (const n of nodes) {
		const p = pos[n.id];
		p.x = Math.max(n.r + 2, Math.min(W - n.r - 2, p.x));
		p.y = Math.max(n.r + 2, Math.min(H - n.r - 2, p.y));
	}

	let overlaps = 0;
	for (let i = 0; i < N; i++)
		for (let j = i + 1; j < N; j++) {
			const a = pos[nodes[i].id];
			const b = pos[nodes[j].id];
			if (Math.hypot(a.x - b.x, a.y - b.y) < nodes[i].r + nodes[j].r - 0.5) overlaps++;
		}

	// ── labels: last, greedy, collision-free ────────────────────────────
	const LH = 16;
	const boxes: LabelBox[] = [];
	const hit = (b: LabelBox) => {
		for (const o of boxes) if (b.x < o.x + o.w && b.x + b.w > o.x && b.y < o.y + o.h && b.y + b.h > o.y) return true;
		return false;
	};
	for (const n of nodes) {
		const p = pos[n.id];
		boxes.push({ x: p.x - n.r - 1, y: p.y - n.r - 1, w: 2 * n.r + 2, h: 2 * n.r + 2 });
	}
	/** The gap (px) between a box and a disc's edge. */
	const gapTo = (b: LabelBox, q: { x: number; y: number }, r: number) => Math.max(0, Math.hypot(Math.max(b.x - q.x, 0, q.x - (b.x + b.w)), Math.max(b.y - q.y, 0, q.y - (b.y + b.h))) - r);
	/** The segment a→c crosses box o (Liang–Barsky). */
	const crosses = (ax: number, ay: number, cx: number, cy: number, o: LabelBox) => {
		let t0 = 0;
		let t1 = 1;
		const dx = cx - ax;
		const dy = cy - ay;
		const edges: [number, number][] = [
			[-dx, ax - o.x],
			[dx, o.x + o.w - ax],
			[-dy, ay - o.y],
			[dy, o.y + o.h - ay],
		];
		for (const [pp, q] of edges) {
			if (pp === 0) {
				if (q < 0) return false;
			} else {
				const r = q / pp;
				if (pp < 0) t0 = Math.max(t0, r);
				else t1 = Math.min(t1, r);
				if (t0 > t1) return false;
			}
		}
		return true;
	};
	const discCount = nodes.length;
	/**
	 * The box reads as `n`'s: no other disc is nearer to it than n's own, and
	 * no label already placed lies between it and its node.
	 */
	const owns = (b: LabelBox, n: LayoutNodeIn) => {
		const p = pos[n.id];
		const own = gapTo(b, p, n.r);
		for (const m of nodes) if (m.id !== n.id && gapTo(b, pos[m.id], m.r) < own - 0.5) return false;
		// the line the eye draws: from the node to the label's centre
		const cx = b.x + b.w / 2;
		const cy = b.y + b.h / 2;
		for (let i = discCount; i < boxes.length; i++) if (crosses(p.x, p.y, cx, cy, boxes[i])) return false;
		return true;
	};
	const labels: Record<string, LabelBox> = {};
	const want = nodes.filter((n) => n.wantLabel).sort((a, b) => b.priority - a.priority || a.order - b.order || (a.id < b.id ? -1 : 1));
	const centre = pos[focusId] || { x: W / 2, y: H / 2 };
	/** One label's place: near before far; at each distance the full label then its shorter form (or the reverse). */
	const place = (n: LayoutNodeIn, preferShort: boolean): LabelBox | null => {
		const p = pos[n.id];
		const widths: { w: number; short: boolean }[] = [{ w: n.labelW + 4, short: false }];
		if (n.shortW != null && n.shortW < n.labelW) widths[preferShort ? 'unshift' : 'push']({ w: n.shortW + 4, short: true });
		const out = Math.atan2(p.y - centre.y, p.x - centre.x);
		const prefer =
			n.id === focusId
				? ['b', 't', 'r', 'l']
				: input.mode === 'hierarchical'
					? ['r', 'br', 'tr', 'b', 't']
					: Math.abs(out) < Math.PI / 4
						? ['r', 'br', 'tr', 'b', 't']
						: Math.abs(out) > (3 * Math.PI) / 4
							? ['l', 'bl', 'tl', 'b', 't']
							: out > 0
								? ['b', 'br', 'bl', 'r', 'l']
								: ['t', 'tr', 'tl', 'r', 'l'];
		const order = prefer.concat(['b', 't', 'r', 'l', 'br', 'bl', 'tr', 'tl']).filter((v, i, a) => a.indexOf(v) === i);
		// eight positions around the disc, each also slid along its side, at three distances
		for (const far of [0, 10, 22]) {
			const g = n.r + 4 + far;
			for (const { w, short } of widths) {
				for (const k of order) {
					const c: Record<string, [number, number]> = {
						r: [p.x + g, p.y - LH / 2],
						l: [p.x - g - w, p.y - LH / 2],
						b: [p.x - w / 2, p.y + g],
						t: [p.x - w / 2, p.y - g - LH],
						br: [p.x + g - 2, p.y + 2],
						tr: [p.x + g - 2, p.y - LH - 2],
						bl: [p.x - g - w + 2, p.y + 2],
						tl: [p.x - g - w + 2, p.y - LH - 2],
					};
					const [bx0, by0] = c[k];
					// slid along the side: a third of the label either way (above or below), or a half and a full line (beside)
					const slide = k === 't' || k === 'b' ? [0, -w / 3, w / 3] : k === 'r' || k === 'l' ? [0, -(LH / 2 + 3), LH / 2 + 3, -(LH + 4), LH + 4] : [0];
					for (const s of slide) {
						const bx = k === 't' || k === 'b' ? bx0 + s : bx0;
						const by = k === 'r' || k === 'l' ? by0 + s : by0;
						const box: LabelBox = short ? { x: bx, y: by, w, h: LH, short: true } : { x: bx, y: by, w, h: LH };
						if (bx < 2 || by < 2 || bx + w > W - 2 || by + LH > H - 2) continue;
						// a label beside its disc (4 px) reads as its node's; one set further out (or slid a full
						// line along its side) must sit nearer it than any other disc
						if (hit(box) || ((far > 0 || Math.abs(s) > LH) && !owns(box, n))) continue;
						return box;
					}
				}
			}
		}
		return null;
	};
	/** A priority tier's labels, in order; each placed box joins `boxes` at once. */
	const placeTier = (tier: readonly LayoutNodeIn[], preferShort: boolean): Record<string, LabelBox> => {
		const got: Record<string, LabelBox> = {};
		for (const n of tier) {
			const b = place(n, preferShort);
			if (!b) continue;
			boxes.push(b);
			got[n.id] = b;
		}
		return got;
	};
	// tier by tier (focus, selection, merged, events, cameras …): when a tier loses a label (two
	// events on the crowded inner ring: the first one's full label blocks the second), the tier is
	// placed again with the shorter forms first, and the attempt that labels more nodes wins
	for (let i = 0; i < want.length; ) {
		let j = i;
		while (j < want.length && want[j].priority === want[i].priority) j++;
		const tier = want.slice(i, j);
		i = j;
		const mark = boxes.length;
		let got = placeTier(tier, false);
		const placedN = Object.keys(got).length;
		if (placedN < tier.length && tier.some((n) => n.shortW != null && n.shortW < n.labelW)) {
			const first = boxes.splice(mark);
			const again = placeTier(tier, true);
			if (Object.keys(again).length > placedN) got = again;
			else {
				boxes.splice(mark);
				boxes.push(...first);
			}
		}
		Object.assign(labels, got);
	}

	return { pos, labels, R, ms: clock() - started, overlaps };
}

/** Two label boxes overlap. */
export function boxesOverlap(a: LabelBox, b: LabelBox): boolean {
	return a.x < b.x + b.w && a.x + a.w > b.x && a.y < b.y + b.h && a.y + a.h > b.y;
}
