/**
 * Running the layout (SPEC §13.6): synchronously for SYNC_MAX_NODES nodes or
 * fewer (< 30 ms), otherwise in a `blob:` worker (the deck's CSP allows
 * `worker-src 'self' blob:`) built from computeLayout's own source — it
 * references nothing outside its body. Should a worker fail to start or
 * answer within WORKER_TIMEOUT_MS, the same function runs in place, so a
 * large graph is late, never missing.
 *
 * Results are cached per focus and filter set (the caller's key: focus,
 * model build, merged/expanded state, Search around, paths, mode, size);
 * Fit and a resize ask again with a new size.
 *
 * The force layout runs the vendored d3-force (force.ts) with a fixed tick
 * count, then the same relaxation, fit and label pass: for 80 nodes or fewer
 * all in place; beyond, the radial seed and the final pass in the worker and
 * the ticks in slices between them (forcePositionsSliced), so the main
 * thread is never held for the whole simulation. Same ticks, same result.
 */
import { computeLayout, SYNC_MAX_NODES, type LayoutInput, type LayoutMode, type LayoutNodeIn, type LayoutOut } from './layout';
import { forcePositions, forcePositionsSliced } from './force';

export const WORKER_TIMEOUT_MS = 4000;
const CACHE_MAX = 24;

const cache = new Map<string, LayoutOut>();

function remember(key: string, out: LayoutOut): LayoutOut {
	if (cache.size >= CACHE_MAX) cache.delete(cache.keys().next().value as string);
	cache.set(key, out);
	return out;
}

/** The cached layout for `key`, if any. */
export function cachedLayout(key: string): LayoutOut | null {
	return cache.get(key) ?? null;
}

export function clearLayoutCache(): void {
	cache.clear();
}

let workerUrl: string | null = null;

function workerSource(): string {
	return `const computeLayout = ${computeLayout.toString()};\nself.onmessage = (e) => { try { self.postMessage({ ok: true, out: computeLayout(e.data) }); } catch (err) { self.postMessage({ ok: false, error: String(err) }); } };`;
}

/** computeLayout in a blob: worker; rejects when the worker cannot run it. */
export function layoutInWorker(input: LayoutInput, timeoutMs = WORKER_TIMEOUT_MS): Promise<LayoutOut> {
	return new Promise((resolve, reject) => {
		if (typeof Worker === 'undefined' || typeof Blob === 'undefined' || typeof URL === 'undefined') return reject(new Error('no worker'));
		let w: Worker;
		try {
			workerUrl ??= URL.createObjectURL(new Blob([workerSource()], { type: 'text/javascript' }));
			w = new Worker(workerUrl);
		} catch (err) {
			return reject(err instanceof Error ? err : new Error(String(err)));
		}
		const timer = setTimeout(() => {
			w.terminate();
			reject(new Error('layout worker timed out'));
		}, timeoutMs);
		w.onmessage = (e: MessageEvent<{ ok: boolean; out?: LayoutOut; error?: string }>) => {
			clearTimeout(timer);
			w.terminate();
			if (e.data?.ok && e.data.out) resolve(e.data.out);
			else reject(new Error(e.data?.error ?? 'layout worker failed'));
		};
		w.onerror = (e) => {
			clearTimeout(timer);
			w.terminate();
			reject(new Error(e.message || 'layout worker error'));
		};
		w.postMessage(input);
	});
}

export interface LayoutRequest {
	key: string;
	mode: LayoutMode;
	W: number;
	H: number;
	focus: string;
	nodes: LayoutNodeIn[];
	edges: { a: string; b: string }[];
}

export interface LayoutAnswer {
	out: LayoutOut;
	/** Where it ran. */
	via: 'cache' | 'sync' | 'worker' | 'fallback';
}

/** The layout synchronously (the radial seed for force included). */
export function layoutSync(req: LayoutRequest): LayoutOut {
	const base: LayoutInput = { mode: req.mode === 'hierarchical' ? 'hierarchical' : 'radial', W: req.W, H: req.H, focus: req.focus, nodes: req.nodes };
	if (req.mode !== 'force') return computeLayout(base);
	const t0 = typeof performance !== 'undefined' ? performance.now() : Date.now();
	const seed = computeLayout(base).pos;
	const given = forcePositions(req.nodes, req.edges, req.focus, seed);
	const out = computeLayout({ ...base, mode: 'given', given });
	return { ...out, ms: (typeof performance !== 'undefined' ? performance.now() : Date.now()) - t0 };
}

/** computeLayout in the worker, in place when the worker cannot run it. */
async function offThread(input: LayoutInput): Promise<{ out: LayoutOut; worker: boolean }> {
	try {
		return { out: await layoutInWorker(input), worker: true };
	} catch {
		return { out: computeLayout(input), worker: false };
	}
}

/**
 * The layout for a request: the cache, else in place (≤ 80 nodes), else a
 * blob: worker (falling back to in place); a large force layout seeds and
 * finishes in the worker and runs its ticks in slices.
 */
export async function layoutGraph(req: LayoutRequest): Promise<LayoutAnswer> {
	const hit = cache.get(req.key);
	if (hit) return { out: hit, via: 'cache' };
	if (req.nodes.length <= SYNC_MAX_NODES) return { out: remember(req.key, layoutSync(req)), via: 'sync' };
	const input: LayoutInput = { mode: req.mode === 'hierarchical' ? 'hierarchical' : 'radial', W: req.W, H: req.H, focus: req.focus, nodes: req.nodes };
	if (req.mode !== 'force') {
		const r = await offThread(input);
		return { out: remember(req.key, r.out), via: r.worker ? 'worker' : 'fallback' };
	}
	const t0 = typeof performance !== 'undefined' ? performance.now() : Date.now();
	const seed = await offThread(input);
	const given = await forcePositionsSliced(req.nodes, req.edges, req.focus, seed.out.pos);
	const fin = await offThread({ ...input, mode: 'given', given });
	const out = { ...fin.out, ms: (typeof performance !== 'undefined' ? performance.now() : Date.now()) - t0 };
	return { out: remember(req.key, out), via: seed.worker && fin.worker ? 'worker' : 'fallback' };
}
