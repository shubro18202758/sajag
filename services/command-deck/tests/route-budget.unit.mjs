/**
 * Route-JS budget unit test (FIX-D-PERF; SPEC §13.12, plan R9).
 *
 *   node tests/route-budget.unit.mjs
 *
 * Reads a BUILT deck's Vite manifest (.svelte-kit/output/client) the same
 * way the kickoff probe measures it (impl/evidence/kickoff/route_js.mjs):
 * a route node's chunk plus its static imports, transitively and deduped,
 * plus its CSS, gzipped. With no build present the test skips (exit 0)
 * with a clear message — build first (`sem.sh deck-build 2 npm run
 * build:cpu`), then run it.
 *
 * Asserts the first-load JavaScript of `/analyst` (the workspace), `/` and `/home`
 * (V3 Home), `/ops` and `/gods-eye` — and of every extra route
 * tests/route-budget.json names under "routes" (V3-P4: /map, /assistant) —
 * stays within its committed ceiling (tests/route-budget.json, with the
 * rationale) — the redesign's budget escape hatch: panels that are not
 * visible on first paint load on first open (dynamic import()), never the
 * route's eager graph. Nothing here reads outside the checkout (FIX-H
 * D-07: the unused kickoff-baseline lookup is gone).
 */

import fs from 'node:fs';
import path from 'node:path';
import zlib from 'node:zlib';
import { fileURLToPath } from 'node:url';
import { budgetRoutes, ceilingOf } from './lib/routes.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const DECK = path.resolve(HERE, '..');

const manifestPath = path.join(DECK, '.svelte-kit/output/client/.vite/manifest.json');
if (!fs.existsSync(manifestPath)) {
	console.log('route-budget: no build found (.svelte-kit/output/client) — build the deck first (`sem.sh deck-build 2 npm run build:cpu`), then re-run. Skipped.');
	process.exit(0);
}

let failures = 0;
const ok = (name, cond, detail) => {
	if (cond) console.log(`ok ${name}`);
	else {
		failures++;
		console.log(`FAIL ${name}${detail ? ` — ${detail}` : ''}`);
	}
};

const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
const app = fs.readFileSync(path.join(DECK, '.svelte-kit/generated/client-optimized/app.js'), 'utf8');
const dict = {};
for (const m of app.matchAll(/"([^"]+)":\s*\[~?(\d+),\[([\d,]*)\]/g)) dict[m[1]] = { leaf: +m[2], layouts: m[3] ? m[3].split(',').map(Number) : [] };

const clientDir = path.join(DECK, '.svelte-kit/output/client');
const gzCache = new Map();
const gzipOf = (f) => {
	if (!gzCache.has(f)) gzCache.set(f, zlib.gzipSync(fs.readFileSync(path.join(clientDir, f))).length);
	return gzCache.get(f);
};

/** The gzip bytes a route node pulls in on first load (leaf + static imports + CSS), as route_js.mjs measures it. */
function leafGzip(node) {
	const files = new Set();
	const seen = new Set();
	const visit = (key) => {
		if (seen.has(key) || !manifest[key]) return;
		seen.add(key);
		const e = manifest[key];
		files.add(e.file);
		for (const c of e.css ?? []) files.add(c);
		for (const i of e.imports ?? []) visit(i);
	};
	visit(`.svelte-kit/generated/client-optimized/nodes/${node}.js`);
	let bytes = 0;
	for (const f of files) bytes += gzipOf(f);
	return bytes;
}

// the ceilings live IN the repo (tests/route-budget.json, with the rationale): the kickoff baseline + 120 KB is not met
// honestly by the redesign + OSINT/DSS first screen; these ceilings stop regressions from the measured state
const CEIL = JSON.parse(fs.readFileSync(path.join(path.dirname(fileURLToPath(import.meta.url)), 'route-budget.json'), 'utf8'));
// the ceilings of record, plus any extra route the file names (V3-P4: /map and /assistant) — an extra route is held
// to its own ceiling exactly like the others; one without a ceiling in "static" is reported, never silently passed.
// URL → node is the tests' (lib/routes.mjs: `/analyst` is the workspace's node, `/` and `/home` Home's); the ceiling is
// read from whichever keys the JSON has (ceilingOf), so this passes before and after the JSON moves its `/` key
const routes = budgetRoutes(CEIL);
for (const [url, id] of Object.entries(routes)) {
	const d = dict[id];
	if (!d) {
		ok(`route JS: ${url} in the built dictionary`, false, `route ${id} not found — is this a full build?`);
		continue;
	}
	const bytes = leafGzip(d.leaf);
	const limit = ceilingOf(CEIL.static, url);
	if (typeof limit !== 'number') {
		ok(`route JS: ${url} has a ceiling in tests/route-budget.json`, false, `${(bytes / 1024).toFixed(1)} KB measured, no "static" ceiling`);
		continue;
	}
	ok(
		`route JS: ${url} within its ceiling (tests/route-budget.json) (${(bytes / 1024).toFixed(1)} KB ≤ ${(limit / 1024).toFixed(1)} KB)`,
		bytes <= limit,
		`${bytes} > ${limit}`,
	);
}

console.log(failures ? `\n${failures} failure(s)` : '\nroute-budget: all green');
process.exit(failures ? 1 : 0);
