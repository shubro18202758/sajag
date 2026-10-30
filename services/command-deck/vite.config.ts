import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig, type Plugin } from 'vite';

/**
 * Dev proxy targets (F-CONN-16): the same pinned loopback host as the
 * adapter-node proxy (src/hooks.server.ts), and ports the caller NAMES —
 * ORACLE_PORT, BRAIN_PORT and EMULATOR_PORT are required for `vite dev`.
 * There is no default: a default once pointed every dev deck at the LIVE
 * stack (8091/8092/8090). A sandbox dev deck (dev_deck.sh) exports its
 * sandbox's ports. `vite build` and `vite preview` need none (the built
 * server proxies through hooks.server.ts with its own env).
 *
 * The dev server binds 127.0.0.1 only (it used to bind 0.0.0.0 — a LAN
 * client could reach a dev deck and, through its proxy, the backends).
 * Note the dev proxy answers before SvelteKit, so the hook's authority
 * pinning, WebSocket 501 and operator gate apply in prod only.
 */
export function devBackends(env: Record<string, string | undefined>): { oracle: string; brain: string; emulator: string } {
	const port = (name: string): string => {
		const v = env[name]?.trim();
		if (!v || !/^\d{2,5}$/.test(v)) {
			throw new Error(
				`vite dev: set ${name} to the backend's port (e.g. a sandbox's) — there is no default, so a dev deck never reaches the live stack by accident`,
			);
		}
		return v;
	};
	return {
		oracle: `http://127.0.0.1:${port('ORACLE_PORT')}`,
		brain: `http://127.0.0.1:${port('BRAIN_PORT')}`,
		emulator: `http://127.0.0.1:${port('EMULATOR_PORT')}`,
	};
}

export const DEV_HOST = '127.0.0.1';

/** Optional dev proxies for the AI services: /api/<name> → 127.0.0.1:$<NAME>_PORT, prefix stripped. */
export function devAiProxies(env: Record<string, string | undefined>): Record<string, { target: string; changeOrigin: boolean; rewrite: (p: string) => string }> {
	const out: Record<string, { target: string; changeOrigin: boolean; rewrite: (p: string) => string }> = {};
	for (const name of ['speech', 'forecast', 'vision', 'hydro', 'twin', 'cityfeeds']) {
		const v = env[`${name.toUpperCase()}_PORT`]?.trim();
		if (!v || !/^\d{2,5}$/.test(v)) continue;
		const prefix = new RegExp(`^/api/${name}`);
		out[`/api/${name}`] = { target: `http://127.0.0.1:${v}`, changeOrigin: true, rewrite: (p) => p.replace(prefix, '') };
	}
	return out;
}

/**
 * The dev server refuses to START without the three ports (a plugin hook:
 * tools that only load this config — svelte-check, svelte-kit sync, the
 * preprocessor — never start a server and need no ports).
 */
function requireDevBackends(problem: string | null): Plugin {
	return {
		name: 'sajag-require-dev-backends',
		configureServer() {
			if (problem) throw new Error(problem);
		},
	};
}

export default defineConfig(({ command, isPreview }) => {
	// only the dev server proxies: a build or a preview never reads (or requires) the ports
	const dev = command === 'serve' && !isPreview;
	let t: ReturnType<typeof devBackends> | null = null;
	let problem: string | null = null;
	if (dev) {
		try {
			t = devBackends(process.env);
		} catch (err) {
			problem = err instanceof Error ? err.message : String(err);
		}
	}
	const ORACLE_TARGET = t?.oracle ?? '';
	const BRAIN_TARGET = t?.brain ?? '';
	const EMULATOR_TARGET = t?.emulator ?? '';
	return {
		plugins: [sveltekit(), requireDevBackends(problem)],
		server: {
			port: 5173,
			host: DEV_HOST, // loopback only (F-CONN-16)
			strictPort: true,
			proxy: t
				? {
						// Proxy API calls to convoy-brain orchestration service
						'/api/convoy': {
							target: BRAIN_TARGET,
							changeOrigin: true,
							ws: true, // Enable WebSocket proxying (dev only — prod answers 501)
							rewrite: (path) => path.replace(/^\/api\/convoy/, ''),
						},
						// Proxy traffic data calls to traffic-oracle
						'/api/traffic': {
							target: ORACLE_TARGET,
							changeOrigin: true,
						},
						// Proxy v1 API calls (events, spatial, dispatch, adaptive, …)
						'/api/v1': {
							target: ORACLE_TARGET,
							changeOrigin: true,
						},
						// Event emulator (loopback, EMULATOR_PORT) behind the same-origin prefix.
						'/api/emulator': {
							target: EMULATOR_TARGET,
							changeOrigin: true,
							rewrite: (path) => path.replace(/^\/api\/emulator/, ''),
						},
						// The on-prem AI services, each only when the caller names its port (no default: a dev deck never
						// reaches a production service by accident).
						...devAiProxies(process.env),
					}
				: undefined,
		},

		// Allow .wgsl shader imports as raw strings
		assetsInclude: ['**/*.wgsl'],

		// ─── CPU-Only Build Optimization ──────────────────────────────────
		// Preserves GPU VRAM entirely for backend AI logic (Qwen, ONNX, DQN).
		build: {
			// Disable source maps in production — saves ~40% build memory
			sourcemap: false,
			// Limit parallel operations to reduce peak memory
			minify: 'esbuild', // esbuild is CPU-only, faster than terser
			// Chunk strategy: keep vendor libs separate for caching.
			// Function form — the object form (package-name keys) hard-fails on
			// vite/rollup versions that resolve these dynamic-imported packages
			// as external (observed: "maplibre-gl cannot be included in
			// manualChunks because it is resolved as an external module").
			rollupOptions: {
				output: {
					manualChunks(id: string) {
						if (id.includes('maplibre-gl')) return 'maplibre';
						if (id.includes('@deck.gl')) return 'deckgl';
						return undefined;
					},
				},
			},
			// Target modern browsers only — skip polyfill bloat
			target: 'esnext',
			// Warn on chunks > 500KB
			chunkSizeWarningLimit: 500,
		},

		// esbuild runs entirely on CPU — no GPU acceleration possible
		esbuild: {
			// target esnext avoids unnecessary transforms
			target: 'esnext',
		},
	};
});
