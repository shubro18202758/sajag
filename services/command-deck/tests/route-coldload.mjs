/**
 * Honest route-JS budget: the cold, interaction-free load (FIX-E-PERF2 round 2; SPEC §13.12).
 *
 *   ORACLE_PORT=8162 BRAIN_PORT=8262 EMULATOR_PORT=8962 node tests/route-coldload.mjs [--json out.json] [--langs en,hi,mr]
 *
 * tests/route-budget.unit.mjs counts a route's STATIC graph only (the kickoff
 * probe's method: the leaf node's chunk + its static imports + CSS, gzip).
 * Code that moved behind a dynamic import() but still downloads on every
 * cold load is invisible to it. This test closes that gap: it serves the
 * PRODUCTION build (`node build`, adapter-node, on a free 54xx loopback
 * port, backed by the sandbox the caller names), loads `/analyst` (the
 * workspace), `/` and `/home` (V3 Home), `/ops` and `/gods-eye` (and every extra route tests/route-budget.json names under
 * "routes": V3-P4's /map and /assistant) in headless Chrome with an empty cache and no interaction,
 * records every same-origin response until network idle + 3 s, and adds
 * every fetched Vite chunk (JS and CSS) that is not on the route's static
 * graph to the static leaf figure:
 *
 *   honest = static leaf (route_js.mjs's figure, the baseline's method)
 *          + every other `_app/immutable` JS/CSS file the load fetched,
 *            except the files the layouts and the client entry put on the
 *            static graph anyway (they sit outside the leaf figure in the
 *            baseline as well; they are listed, not hidden).
 *
 * gzip sizes come from the build's own files (zlib, as route_js.mjs does),
 * so the figure is comparable with the kickoff baseline. The budget is the
 * kickoff baseline + 120 KB on the EN load (the console's default); the HI
 * and MR cold loads are measured and printed beside it (they add the cookie
 * language's pack chunks, which must land before hydration — no English
 * flash) and are held to the same limit.
 *
 * Never the live stack: the preview this test spawns proxies the ports in
 * ORACLE_PORT / BRAIN_PORT / EMULATOR_PORT, which must be named (a sandbox's)
 * and must not be the live ones; every non-GET request from the page is
 * answered 204 in the browser, so a cold load writes nothing anywhere.
 */
import { spawn } from 'node:child_process';
import { createRequire } from 'node:module';
import fs from 'node:fs';
import net from 'node:net';
import os from 'node:os';
import path from 'node:path';
import zlib from 'node:zlib';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { budgetRoutes, ceilingOf } from './lib/routes.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
export const DECK = path.resolve(HERE, '..');
const CLIENT = path.join(DECK, '.svelte-kit/output/client');
const BUDGET = 120 * 1024;
const LIVE_PORTS = new Set(['5273', '8091', '8092', '8090', '56434', '6380', '4223', '8083', '8084', '8085']);
// URL → route node (lib/routes.mjs): `/analyst` is the workspace's node, `/` and `/home` are V3 Home's
export const ROUTES = budgetRoutes();

// ── harness: puppeteer + Chrome (the smokes' candidates) ───────────────────

export function loadPuppeteer() {
	const from = [process.env.PUPPETEER_FROM, path.resolve(DECK, '../../frontend/package.json')].filter(Boolean);
	for (const f of from) {
		try {
			const req = createRequire(f);
			return req('puppeteer').default ?? req('puppeteer');
		} catch {
			// next candidate
		}
	}
	throw new Error(`puppeteer not resolvable from ${from.join(', ')}`);
}

export function chromePath() {
	const c = [
		process.env.CHROME_PATH,
		path.join(os.homedir(), '.cache/puppeteer/chrome/linux_arm-153.0.8010.36/chrome-linux-arm64/chrome'),
		path.join(os.homedir(), '.cache/puppeteer/chrome/linux_arm-146.0.7680.76/chrome-linux-arm64/chrome'),
	].filter(Boolean);
	const p = c.find((x) => fs.existsSync(x));
	if (!p) throw new Error('no Chrome binary found (set CHROME_PATH)');
	return p;
}

export const CHROME_ARGS = ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage', '--enable-unsafe-swiftshader', '--use-gl=angle', '--use-angle=swiftshader'];

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function freePort(from = 5440, to = 5499) {
	return new Promise((resolve, reject) => {
		const tryPort = (p) => {
			if (p > to) return reject(new Error(`no free port in ${from}–${to}`));
			const srv = net.createServer();
			srv.once('error', () => tryPort(p + 1));
			srv.listen(p, '127.0.0.1', () => srv.close(() => resolve(p)));
		};
		tryPort(from);
	});
}

/** The sandbox backend ports the caller named; refuses the live defaults. */
export function sandboxEnv() {
	const missing = ['ORACLE_PORT', 'BRAIN_PORT', 'EMULATOR_PORT'].filter((k) => !process.env[k]);
	if (missing.length) throw new Error(`name the sandbox backend: export ${missing.join(', ')} (e.g. int3cl: ORACLE_PORT=8162 BRAIN_PORT=8262 EMULATOR_PORT=8962) — never the live defaults`);
	for (const k of ['ORACLE_PORT', 'BRAIN_PORT', 'EMULATOR_PORT']) if (LIVE_PORTS.has(String(process.env[k]))) throw new Error(`${k}=${process.env[k]} is a live port — refused`);
	return { ORACLE_PORT: process.env.ORACLE_PORT, BRAIN_PORT: process.env.BRAIN_PORT, EMULATOR_PORT: process.env.EMULATOR_PORT };
}

/**
 * Serve the production build (`node build`) on a free loopback 54xx port. Private: the operator gate off and keyless
 * (the PIN, the session secret and the ion token stay with the deployed deck). Returns { origin, stop }.
 */
export async function startProdServer() {
	if (!fs.existsSync(path.join(DECK, 'build/index.js')) || !fs.existsSync(path.join(CLIENT, '.vite/manifest.json'))) {
		throw new Error('no production build (build/ + .svelte-kit/output/client) — run `sem.sh deck-build 2 npm run build:cpu` first');
	}
	const port = await freePort();
	const env = { ...process.env, ...sandboxEnv(), PORT: String(port), HOST: '127.0.0.1', NODE_ENV: 'production' };
	for (const k of ['SAJAG_OPERATOR_PIN', 'SAJAG_OPERATOR_PIN_FILE', 'SAJAG_SESSION_SECRET', 'SAJAG_SESSION_SECURE', 'SAJAG_CESIUM_ION_TOKEN']) delete env[k];
	const proc = spawn('node', ['build'], { cwd: DECK, env, stdio: ['ignore', 'ignore', 'pipe'] });
	let err = '';
	proc.stderr.on('data', (d) => (err += d));
	const origin = `http://127.0.0.1:${port}`;
	for (let i = 0; i < 60; i++) {
		try {
			const r = await fetch(`${origin}/design`, { redirect: 'manual', signal: AbortSignal.timeout(2000) });
			if (r.status < 500) return { origin, stop: () => proc.kill() };
		} catch {
			// not up yet
		}
		if (proc.exitCode !== null) break;
		await sleep(500);
	}
	proc.kill();
	throw new Error(`production server did not come up on ${origin}: ${err.slice(-400)}`);
}

/** A fresh, cache-less context with the language cookie set; non-GET requests answered locally (nothing is written). */
export async function coldPage(browser, origin, lang, { width = 1920, height = 1080 } = {}) {
	const ctx = await browser.createBrowserContext();
	const page = await ctx.newPage();
	await page.setViewport({ width, height });
	await page.setCacheEnabled(false);
	if (lang) await page.setCookie({ name: 'sajag_lang', value: lang, url: origin });
	await page.setRequestInterception(true);
	page.on('request', (r) => {
		const p = ['GET', 'HEAD', 'OPTIONS'].includes(r.method()) ? r.continue() : r.respond({ status: 204, body: '' });
		p.catch(() => {});
	});
	return { ctx, page };
}

// ── the build's own bookkeeping ────────────────────────────────────────────

export function buildIndex() {
	const manifest = JSON.parse(fs.readFileSync(path.join(CLIENT, '.vite/manifest.json'), 'utf8'));
	const app = fs.readFileSync(path.join(DECK, '.svelte-kit/generated/client-optimized/app.js'), 'utf8');
	const dict = {};
	for (const m of app.matchAll(/"([^"]+)":\s*\[~?(\d+),\[([\d,]*)\]/g)) dict[m[1]] = { leaf: +m[2], layouts: m[3] ? m[3].split(',').map(Number) : [] };
	const srcOf = {};
	for (const [k, v] of Object.entries(manifest)) {
		srcOf[v.file] = k;
		for (const c of v.css ?? []) srcOf[c] ??= `${k} (css)`;
	}
	const gzc = new Map();
	const gz = (f) => {
		if (!gzc.has(f)) gzc.set(f, zlib.gzipSync(fs.readFileSync(path.join(CLIENT, f))).length);
		return gzc.get(f);
	};
	const closure = (keys) => {
		const files = new Set();
		const seen = new Set();
		const visit = (k) => {
			if (seen.has(k) || !manifest[k]) return;
			seen.add(k);
			files.add(manifest[k].file);
			for (const c of manifest[k].css ?? []) files.add(c);
			for (const i of manifest[k].imports ?? []) visit(i);
		};
		for (const k of keys) visit(k);
		return files;
	};
	const node = (n) => `.svelte-kit/generated/client-optimized/nodes/${n}.js`;
	// the client entry (start + app), not the route nodes (every node is a rollup entry too)
	const entries = Object.entries(manifest).filter(([k, v]) => v.isEntry && !k.includes('/nodes/')).map(([k]) => k);
	return { manifest, dict, srcOf, gz, closure, node, entries };
}

const kb = (b) => (b / 1024).toFixed(1);

/** One cold load: every same-origin Vite file fetched until network idle + 3 s. */
export async function measureColdLoad(browser, origin, route, lang, idx, routeIds = ROUTES) {
	const { ctx, page } = await coldPage(browser, origin, lang);
	const fetched = new Set();
	page.on('response', (r) => {
		try {
			const u = new URL(r.url());
			if (u.origin === origin && u.pathname.startsWith('/_app/immutable/') && /\.(js|css)$/.test(u.pathname)) fetched.add(u.pathname.slice(1));
		} catch {
			// not a URL we serve
		}
	});
	const errors = [];
	page.on('pageerror', (e) => errors.push(String(e?.message ?? e)));
	await page.goto(origin + route, { waitUntil: 'load', timeout: 120000 });
	await page.waitForNetworkIdle({ idleTime: 750, timeout: 30000 }).catch(() => {});
	await sleep(3000);
	await ctx.close();
	const d = idx.dict[routeIds[route] ?? ROUTES[route]];
	const sum = (files) => [...files].reduce((a, f) => a + idx.gz(f), 0);
	const leaf = idx.closure([idx.node(d.leaf)]);
	// the static shell every route shares: the root layout (node 0), the root error node (1), the group layout(s)
	// and the client entry — outside the baseline's leaf figure, so outside this one too; reported below
	const shell = idx.closure([idx.node(0), idx.node(1), ...d.layouts.map(idx.node), ...idx.entries]);
	const onDisk = [...fetched].filter((f) => fs.existsSync(path.join(CLIENT, f)));
	const staticLeaf = sum(leaf);
	const extra = onDisk.filter((f) => !leaf.has(f) && !shell.has(f));
	const dynamic = extra.map((f) => ({ file: f, src: idx.srcOf[f] ?? f, gz: idx.gz(f) })).sort((a, b) => b.gz - a.gz);
	const dynBytes = dynamic.reduce((a, x) => a + x.gz, 0);
	const shellOnly = sum(onDisk.filter((f) => shell.has(f) && !leaf.has(f)));
	const totalFetched = sum(onDisk);
	const staticNotFetched = [...leaf].filter((f) => !fetched.has(f) && f.endsWith('.js'));
	return { route, lang, staticLeaf, dynBytes, honest: staticLeaf + dynBytes, shellOnly, totalFetched, dynamic, staticNotFetched: staticNotFetched.length, errors };
}

// ── main ────────────────────────────────────────────────────────────────────

async function main() {
	const args = process.argv.slice(2);
	const jsonOut = args.includes('--json') ? args[args.indexOf('--json') + 1] : null;
	const langs = (args.includes('--langs') ? args[args.indexOf('--langs') + 1] : 'en,hi,mr').split(',');
	const CEIL = JSON.parse(fs.readFileSync(path.join(path.dirname(fileURLToPath(import.meta.url)), 'route-budget.json'), 'utf8'));
	const idx = buildIndex();
	const server = await startProdServer();
	const puppeteer = loadPuppeteer();
	const browser = await puppeteer.launch({ executablePath: chromePath(), headless: 'new', args: CHROME_ARGS });
	let failures = 0;
	const results = [];
	try {
		// the routes of record, then any extra route tests/route-budget.json names (V3-P4: /map, /assistant)
		const routeIds = budgetRoutes(CEIL);
		for (const route of Object.keys(routeIds)) {
			for (const lang of langs) {
				const limit = ceilingOf(lang === 'en' ? CEIL.coldload_en : CEIL.coldload_hi_mr, route);
				if (typeof limit !== 'number') {
					failures++;
					console.log(`FAIL cold load ${route} [${lang}]: no ceiling in tests/route-budget.json`);
					continue;
				}
				const r = await measureColdLoad(browser, server.origin, route, lang, idx, routeIds);
				r.limit = limit;
				r.headroom = limit - r.honest;
				results.push(r);
				const pass = r.honest <= limit;
				if (!pass) failures++;
				console.log(
					`${pass ? 'ok  ' : 'FAIL'} cold load ${route} [${lang}]: static leaf ${kb(r.staticLeaf)} KB + fetched dynamic ${kb(r.dynBytes)} KB = ${kb(r.honest)} KB ` +
						`(limit ${kb(limit)} KB, headroom ${kb(r.headroom)} KB); shell-only ${kb(r.shellOnly)} KB, everything fetched ${kb(r.totalFetched)} KB`,
				);
				for (const x of r.dynamic) console.log(`       + ${kb(x.gz).padStart(5)} KB  ${x.src}`);
				if (r.errors.length) console.log(`       page errors: ${r.errors.slice(0, 3).join(' | ')}`);
			}
		}
	} finally {
		await browser.close();
		server.stop();
	}
	if (jsonOut) fs.writeFileSync(jsonOut, JSON.stringify({ measured_at: new Date().toISOString(), budget_bytes: BUDGET, results }, null, 1) + '\n');
	console.log(failures ? `\nroute-coldload: ${failures} load(s) over the ceiling (tests/route-budget.json)` : '\nroute-coldload: every cold load within its ceiling (tests/route-budget.json)');
	process.exit(failures ? 1 : 0);
}

if (import.meta.url === pathToFileURL(process.argv[1]).href) {
	main().catch((e) => {
		console.error(`route-coldload: ${e.message}`);
		process.exit(1);
	});
}
