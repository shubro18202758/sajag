/**
 * Assistant unit test (FIX-E-ASSIST round 2 — the audit E re-round).
 *
 *   node tests/assistant.unit.mjs
 *
 * Three harnesses (the wall.unit pattern). The audit E must-fix 2 demoted
 * the source regexes: what a mutant changes in the WIRING is asserted as
 * BEHAVIOUR here (bundle + rendered output), with only a few structural
 * checks kept as belt; the layout rules a browser must measure moved to
 * tests/assistant-smoke.mjs (computed styles, real clicks).
 *
 *   1.  esbuild bundles the REAL modules — the AssistantPanel's helpers
 *       (review-target.ts, page-interrupts.ts), the command bar, the ops
 *       store and the decisions/live strip — with `$lib` aliased to src/lib
 *       and `$app/navigation` stubbed; runes are expanded by compileModule.
 *   2.  the Svelte compiler renders the AssistantPanel for the SERVER
 *       (svelte/server); the assertions read the markup the page ships.
 *   3.  a few structural reads of the two pages for rules the smoke cannot
 *       reach without the deck running.
 *
 * Asserts (one group per audit item):
 *   S2-1  the step cards carry [hidden] and the stylesheet gives [hidden]
 *         display:none (the computed collapse is the smoke's)
 *   S2-2  /chat and /comms keep the interrupts: wireInterrupts puts the
 *         liveStripFeed in the command bar and routes the inbox to
 *         '/analyst#inbox'; inboxFromUnits counts the decision units (behaviour on
 *         the real stores)
 *   S2-3  both pages start and stop the city registry while mounted (belt;
 *         the omnibar behaviour is the smoke's)
 *   S2-4  a dock proposal/citation is reviewed on the CURRENT map
 *         (reviewTarget('dock') never navigates; a table view becomes the
 *         map); the /chat page opens /gods-eye
 *   S2-5  chat-tiers and chat-session render inside CLOSED Details, on the
 *         page AND the dock
 *   S3-6  cited marks render as ObjectTags — including a LABEL-SHAPED urn —
 *         and the dock's citation tooltip says "Select on the map" while
 *         the page column keeps the map-route copy
 *   S3-7  the page context column names the scoped vehicle by its masked
 *         mark (never the uuid) and states the scope ONCE
 *   S3-8  /comms: "Drafted — not delivered" twice (review badge + toast);
 *         the operator-only arm keeps the three [data-lang][data-withheld]
 *         nodes with an EMPTY draft line — no dash, no notice, no Copy
 *         button; the review column keeps its 360 px column at 1366
 *   pack  EN/HI/MR carry the scope keys, the dock citation key and the
 *         event-state keys; the HI/MR scope suffix is not the EN string
 *
 * Exits 0 with `ok <name>` lines, 1 on any failure.
 */

import { createRequire } from 'node:module';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const DECK = path.resolve(HERE, '..');
const OUT_DIR = path.join(HERE, 'artifacts');
const PANEL = path.join(DECK, 'src', 'lib', 'assistant', 'AssistantPanel.svelte');
const CHAT_PAGE = path.join(DECK, 'src', 'routes', '(deck)', 'chat', '+page.svelte');
const COMMS_PAGE = path.join(DECK, 'src', 'routes', '(deck)', 'comms', '+page.svelte');

let failures = 0;
function ok(name, cond, detail = '') {
	if (cond) console.log(`ok   ${name}${detail ? ` — ${detail}` : ''}`);
	else {
		failures++;
		console.error(`FAIL ${name}${detail ? ` — ${detail}` : ''}`);
	}
}

const panelSrc = readFileSync(PANEL, 'utf8');
const chatSrc = readFileSync(CHAT_PAGE, 'utf8');
const commsSrc = readFileSync(COMMS_PAGE, 'utf8');
/** A <style> block's body. */
const styleOf = (src) => (src.match(/<style>[\s\S]*<\/style>/) ?? [''])[0];

// ─── S2-1 the step collapse: [hidden] must beat the flex row ────────────────

const stepHidden = (styleOf(panelSrc).match(/\.step(?:\.[^{]*)?\[hidden\]\s*\{([^}]*)\}/) ?? [])[1] ?? '';
ok('S2-1: .step[hidden] collapses to display:none', /display:\s*none/.test(stepHidden), JSON.stringify(stepHidden.trim()));
ok('S2-1: the step cards render the [hidden] attribute while steps are off', /hidden=\{!showSteps\}/.test(panelSrc));

// ─── S2-2 / S2-4 helpers bundled with the real stores ───────────────────────

mkdirSync(OUT_DIR, { recursive: true });
const esbuild = createRequire(path.join(DECK, 'package.json'))('esbuild');

// $app/navigation is SvelteKit's runtime; the deck's tests stub the two
// functions the pages use (goto records its target).
const NAV_STUB = path.join(OUT_DIR, 'app-navigation-stub.mjs');
writeFileSync(
	NAV_STUB,
	[
		'globalThis.__goto_calls ??= [];',
		'export function goto(href) { globalThis.__goto_calls.push(String(href)); return Promise.resolve(); }',
		'export function beforeNavigate() {}',
		'export function afterNavigate() {}',
		'export function onNavigate() {}',
	].join('\n'),
);

const BASE_ENTRY = `
import './src/lib/i18n/packs.agent';
import './src/lib/i18n/packs.assistant';
export { commandBar } from './src/lib/shell/command-bar.svelte';
export { ops } from './src/lib/ops/store.svelte';
export * as live from './src/lib/decisions/live';
export { reviewTarget } from './src/lib/assistant/review-target';
export { wireInterrupts, inboxFromUnits } from './src/lib/assistant/page-interrupts';
export { t } from './src/lib/i18n/strings';
`;
const OUT = path.join(OUT_DIR, 'assistant-bundle.mjs');
// Svelte 5 runes are compiler macros: identity stubs let the raw-bundled
// .svelte.ts stores run as plain classes (the views.unit pattern). The
// svelte-compiled modules below use the real server runtime instead.
globalThis.$state = Object.assign((v) => v, { raw: (v) => v, snapshot: (v) => v });
globalThis.$derived = Object.assign((v) => v, { by: (f) => f() });
globalThis.$effect = Object.assign(() => {}, { root: () => () => {}, pre: () => {} });
globalThis.$props = () => ({});
globalThis.$bindable = (v) => v;
globalThis.$inspect = () => {};
let M = null;
{
	// ONE bundle: the stores AND the helpers the fix introduces. On the
	// pre-change code this bundle cannot even resolve the helpers — the
	// first red — so the interrupts below are asserted on the same
	// commandBar instance the helpers write.
	const built = await esbuild
		.build({
			stdin: { contents: BASE_ENTRY, resolveDir: DECK, loader: 'ts', sourcefile: 'assistant-entry.ts' },
			absWorkingDir: DECK,
			alias: { $lib: './src/lib', '$app/navigation': NAV_STUB },
			bundle: true,
			format: 'esm',
			platform: 'node',
			outfile: OUT,
			logLevel: 'silent',
		})
		.catch((err) => {
			ok('bundle builds (esbuild, $lib aliased, helpers resolve)', false, String(err?.message ?? err).split('\n')[0]);
			return null;
		});
	if (built) {
		ok('bundle builds (esbuild, $lib aliased, helpers resolve)', built.errors.length === 0, `${built.errors.length} errors`);
		M = await import(`${pathToFileURL(OUT).href}?t=${Date.now()}`);
	}
}

if (M) {
	// ── S2-2 the interrupts survive on the canvas-less pages ──
	const { ops, commandBar, live, wireInterrupts, inboxFromUnits, reviewTarget: rt, t } = M;
	const PURSUIT = {
		eventId: '6f1c2a3b-4d5e-4f60-8a71-92b3c4d5e6f7',
		name: 'Pursuit of the emulated vehicle',
		eventKind: 'vehicle_pursuit',
		protectionClass: 'none',
		crowdClass: 'none',
		// the board's phase state: a pursuit under way is 'active' (F-05: a planned one is not live)
		state: 'active',
		metadata: { vehicleId: '1b94e9d2-7e11-4174-a735-7dd3be3189cf' },
		routeSegmentIds: [],
		phases: [],
		currentPhase: null,
		band: null,
		windowStart: null,
		windowEnd: null,
		description: null,
		source: 'live-events-api',
		emulated: true,
	};
	const savedEvents = ops.events;
	if (wireInterrupts) {
		try {
			ops.events = [PURSUIT];
			const feed = live.liveStripFeed({ route: '/chat', now: Date.now() });
			ok('S2-2: a live pursuit gives /chat a live strip feed (not null)', feed !== null && Array.isArray(feed.pursuits) && feed.pursuits.length === 1);
			wireInterrupts('/chat');
			ok('S2-2: wireInterrupts puts the live strip in the command bar', commandBar.live === feed || (commandBar.live !== null && commandBar.live.pursuits.length === 1));
			ok('S2-2: wireInterrupts hands the inbox to the workspace deep link', typeof commandBar.onInbox === 'function');
			globalThis.__goto_calls = [];
			commandBar.onInbox?.();
			ok('S2-2: the inbox button routes to /analyst#inbox', globalThis.__goto_calls.includes('/analyst#inbox'), JSON.stringify(globalThis.__goto_calls));
			// F-06: /chat has no map — the pursuit segment opens the vehicle on the workspace (a bare selection did nothing)
			globalThis.__goto_calls = [];
			commandBar.live?.pursuits[0]?.onSelect();
			ok(
				'F-06: on /chat the pursuit segment navigates to the workspace with the vehicle selected',
				globalThis.__goto_calls.length === 1 && globalThis.__goto_calls[0] === `/analyst#${new URLSearchParams({ sel: 'vehicle:1b94e9d2-7e11-4174-a735-7dd3be3189cf' })}`,
				JSON.stringify(globalThis.__goto_calls),
			);
			// F-05: a PLANNED pursuit (planning / approved on the wire) is not under way — no live strip
			ops.events = [{ ...PURSUIT, state: 'planned', status: 'planning' }];
			ok('F-05: a planned pursuit gives no live strip (nothing is live)', live.liveStripFeed({ route: '/chat', now: Date.now() }) === null);
			ok('F-05: a planned pursuit is not an open pursuit (the map mode reads the same rule)', live.openPursuits(ops).length === 0);
		} finally {
			ops.events = savedEvents;
			commandBar.live = null;
			commandBar.onInbox = null;
		}
		inboxFromUnits([{ kind: 'pursuit', id: 'a' }, { kind: 'echallan', id: 'b' }]);
		ok('S2-2: inboxFromUnits counts the decision units (2 → warning)', commandBar.inboxCount === 2 && commandBar.inboxIntent === 'warning');
		inboxFromUnits([]);
		ok('S2-2: inboxFromUnits([]) recedes (0 → none)', commandBar.inboxCount === 0 && commandBar.inboxIntent === 'none');
	}

	// ── S2-4 the dock reviews on the current map ──
	ok('S2-4: reviewTarget exists (the review is a per-surface decision)', typeof rt === 'function');
	if (rt) {
		const page = rt('page');
		ok('S2-4: the /chat page reviews on the map route', page.goto === '/gods-eye', JSON.stringify(page));
		for (const [view, want] of [['map', 'map'], ['split', 'split'], ['table', 'map'], ['graph', 'split']]) {
			const dock = rt('dock', view);
			ok(`S2-4: the dock reviews where it is (view ${view} → ${want}, no navigation)`, dock.goto === null && dock.view === want, JSON.stringify(dock));
		}
	}

	// ── pack: the per-surface citation copy and the event states ──
	for (const key of ['asst_cite_select_map', 'asst_ev_state_planned', 'asst_ev_state_active']) {
		const vals = ['en', 'hi', 'mr'].map((l) => t(l, key));
		ok(`pack: ${key} exists in EN/HI/MR`, vals.every((v) => typeof v === 'string' && v !== key && v.length > 0), JSON.stringify(vals));
	}
	// the dock copy and the page copy differ — the dock's citation selects on
	// the CURRENT map, it does not open City command (audit E, S3)
	const DOCK_CITE = t('en', 'asst_cite_select_map');
	const PAGE_CITE = t('en', 'chat_open_city');
	ok('pack: the dock citation copy differs from the page copy', DOCK_CITE !== PAGE_CITE && DOCK_CITE.length > 0 && PAGE_CITE.length > 0, `dock="${DOCK_CITE}" page="${PAGE_CITE}"`);
	// the HI/MR scope suffix is NOT the English string (mutant 7d)
	const suffixes = ['en', 'hi', 'mr'].map((l) => t(l, 'asst_scope_suffix'));
	ok(
		'pack: the HI and MR scope suffix is not the English string',
		suffixes[0] === 'and this view' && suffixes[1] !== suffixes[0] && suffixes[2] !== suffixes[0],
		JSON.stringify(suffixes),
	);
}

// ── the pages' wiring, read from the source (belt; the behaviour lives in
//    the bundle above and the smoke's real pages) ─────────────────────────────
ok('S2-2: /chat wires the interrupts (helper calls in the page)', chatSrc.includes('wireInterrupts(') && chatSrc.includes('inboxFromUnits('));
ok('S2-2: /comms wires the interrupts (helper calls in the page)', commsSrc.includes('wireInterrupts(') && commsSrc.includes('inboxFromUnits('));
ok('S2-2: neither page nulls the live strip or the inbox any more', !chatSrc.includes('commandBar.live = null') && !chatSrc.includes('commandBar.onInbox = null') && !commsSrc.includes('commandBar.live = null') && !commsSrc.includes('commandBar.onInbox = null'));

// ── S2-3 the pages start the city registry while mounted (belt; the smoke
//    proves the omnibar finds mh47) ───────────────────────────────────────────
ok('S2-3: /chat starts and stops the city registry', /cityRegistry\.start\(\)/.test(chatSrc) && /cityRegistry\.stop\(\)/.test(chatSrc));
ok('S2-3: /comms starts and stops the city registry', /cityRegistry\.start\(\)/.test(commsSrc) && /cityRegistry\.stop\(\)/.test(commsSrc));

// ─── the rendered panel (svelte/server) ─────────────────────────────────────

const req = createRequire(path.join(DECK, 'package.json'));
const { compile, compileModule } = req('svelte/compiler');
const sveltePlugin = {
	name: 'svelte-ssr',
	setup(b) {
		b.onLoad({ filter: /\.svelte$/ }, async (args) => {
			const src = readFileSync(args.path, 'utf8');
			const { js } = compile(src, { filename: args.path, generate: 'server', css: 'injected', dev: false });
			return { contents: js.code, loader: 'js', resolveDir: path.dirname(args.path) };
		});
		b.onLoad({ filter: /\.svelte\.(ts|js)$/ }, async (args) => {
			const src = readFileSync(args.path, 'utf8');
			const plain = args.path.endsWith('.ts') ? (await esbuild.transform(src, { loader: 'ts' })).code : src;
			const { js } = compileModule(plain, { filename: args.path, generate: 'server', dev: false });
			return { contents: js.code, loader: 'js', resolveDir: path.dirname(args.path) };
		});
	},
};
const SSR_ENTRY = `
export { render } from 'svelte/server';
export { default as AssistantPanel } from './src/lib/assistant/AssistantPanel.svelte';
export { selection } from './src/lib/gods-eye/entities/selection.svelte';
export { cityRegistry } from './src/lib/gods-eye/entities/registry.svelte';
export * as cityApi from './src/lib/gods-eye/city-api';
export { t } from './src/lib/i18n/strings';
`;
const OUT_SSR = path.join(OUT_DIR, 'assistant-ssr.mjs');
let S = null;
try {
	const ssr = await esbuild.build({
		stdin: { contents: SSR_ENTRY, resolveDir: DECK, loader: 'ts', sourcefile: 'assistant-ssr-entry.ts' },
		absWorkingDir: DECK,
		alias: { $lib: './src/lib', '$app/navigation': NAV_STUB },
		bundle: true,
		format: 'esm',
		platform: 'node',
		conditions: ['svelte', 'node'],
		outfile: OUT_SSR,
		logLevel: 'silent',
		plugins: [sveltePlugin],
	});
	ok('server bundle builds (svelte/compiler, generate: server)', ssr.errors.length === 0, `${ssr.errors.length} errors`);
	S = await import(`${pathToFileURL(OUT_SSR).href}?t=${Date.now()}`);
} catch (err) {
	ok('server bundle builds (svelte/compiler, generate: server)', false, String(err?.message ?? err).slice(0, 400));
}

if (S) {
	const html = (C, props) => S.render(C, { props }).body.replace(/<!--[\s\S]*?-->/g, '');
	const strip = (s) => s.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ');

	// the labelled sample turn (S2-5, S3-6, S3-7): one locally composed turn,
	// no model called. The world holds the watchlisted vehicle (the fixture's
	// masked capture) and selection scopes the panel to it, so the scope line
	// and the context column read the same masked mark.
	S.cityRegistry.seed(
		S.cityApi.parseCitySnapshot({
			as_of: '2026-10-23T21:48:38.092Z',
			entities: [
				{
					urn: 'vehicle:1b94e9d2-7e11-4174-a735-7dd3be3189cf',
					kind: 'vehicle',
					id: '1b94e9d2-7e11-4174-a735-7dd3be3189cf',
					label: 'MH47EM•••1',
					lon: 88.369057,
					lat: 22.559545,
					state: 'flagged',
					source: 'emulated',
					t: '2026-10-23T20:08:37.889Z',
					links: [],
					props: {},
				},
			],
		}),
		'test harness',
	);
	S.selection.current = 'vehicle:1b94e9d2-7e11-4174-a735-7dd3be3189cf';
	const samplePage = html(S.AssistantPanel, { variant: 'page', sample: true });
	const sampleDock = html(S.AssistantPanel, { variant: 'dock', sample: true });

	// ── S2-5 Details holds the machinery while closed, page AND dock ──
	const closedDetails = /<details class="details[^"]*"(?![^>]*?\bopen)[\s\S]*?<\/details>/g;
	for (const [name, out] of [['page', samplePage], ['dock', sampleDock]]) {
		const closed = out.match(closedDetails) ?? [];
		ok(`S2-5: ${name} Details renders closed and holds chat-tiers`, closed.some((d) => d.includes('data-testid="chat-tiers"')), `${closed.length} closed details`);
		ok(`S2-5: ${name} Details renders closed and holds chat-session`, closed.some((d) => d.includes('data-testid="chat-session"')));
	}
	ok('S2-5: the sample turn names a tier and a session (the rows have content)', /heuristic[\s\S]*?sample-local/.test(samplePage));

	// ── S3-6 cited marks are ObjectTags — including a LABEL-SHAPED urn — and
	//    the citation copy is per-surface ──
	ok('S3-6: cited marks render as ObjectTags (vehicle)', /data-urn="vehicle:MH47EM4444"[^>]*data-kind="vehicle"|data-kind="vehicle"[^>]*data-urn="vehicle:MH47EM4444"/.test(samplePage));
	ok('S3-6: cited marks render as ObjectTags (camera)', /data-urn="camera:EM-CAM-03"[^>]*data-kind="camera"|data-kind="camera"[^>]*data-urn="camera:EM-CAM-03"/.test(samplePage));
	const dockCites = (sampleDock.match(/<button[^>]*class="cite[^"]*"[^>]*>[\s\S]*?<\/button>/g) ?? []).map((b) => ({
		title: (b.match(/title="([^"]*)"/) ?? [])[1] ?? '',
		tag: /data-ui="object-tag"/.test(b),
		urn: (b.match(/data-urn="([^"]*)"/) ?? [])[1] ?? null,
	}));
	const labelCite = dockCites.find((c) => c.urn === 'vehicle:MH47EM4444');
	ok('S3-6: the dock renders a label-shaped cited urn as an ObjectTag (not plain text)', !!labelCite && labelCite.tag, JSON.stringify(dockCites));
	const DOCK_CITE_COPY = M?.t?.('en', 'asst_cite_select_map') ?? 'Select on the map';
	const PAGE_CITE_COPY = M?.t?.('en', 'chat_open_city') ?? 'Open in City command';
	ok(
		'S3-6: the dock citation tooltip says "Select on the map" — never the page copy',
		dockCites.length >= 2 && dockCites.every((c) => c.title.endsWith(`— ${DOCK_CITE_COPY}`) && !c.title.includes(PAGE_CITE_COPY)),
		JSON.stringify(dockCites.map((c) => c.title)),
	);
	const pageCiteTitles = (samplePage.match(/<button[^>]*class="cite[^"]*"[^>]*title="([^"]*)"/g) ?? []).map((m) => (m.match(/title="([^"]*)"/) ?? [])[1]);
	ok(
		'S3-6: the page column keeps the map-route citation copy',
		pageCiteTitles.length >= 2 && pageCiteTitles.every((ti) => ti.endsWith(`— ${PAGE_CITE_COPY}`)),
		JSON.stringify(pageCiteTitles),
	);

	// ── S3-7 the context column names the scope by its masked mark, once ──
	const aside = (samplePage.match(/<aside class="aside[^"]*">[\s\S]*?<\/aside>/) ?? [''])[0];
	ok('S3-7: the context column renders', aside.length > 0);
	ok(
		'S3-7: the scoped vehicle reads as its masked mark — never the raw uuid',
		/MH47EM•••1/.test(strip(aside)) && !/1b94e9d2-7e11/.test(strip(aside)),
		JSON.stringify(strip(aside).slice(0, 120)),
	);
	ok('S3-7: the scope is stated once — no second "Scoped to this view" under the tag', !samplePage.includes('Scoped to this view'));
	const emptyPage = html(S.AssistantPanel, { variant: 'page' });
	const SUB = 'It reads the city and proposes';
	ok('S3-7: the empty state does not repeat the page subtitle', !emptyPage.includes(SUB), emptyPage.includes(SUB) ? 'the panel repeats the header line' : 'once, in the page header');

	// ── belt: the composer cannot push Send out of the dock (the geometry is
	//    the smoke's) ──
	ok('belt: the composer input has min-width: 0', /\.composer input\s*\{[^}]*min-width:\s*0/.test(panelSrc));
}

// ─── S3-8 the /comms desk (belt; the rendered behaviour is the smoke's) ─────

{
	ok('S3-8: "Drafted — not delivered" appears in /comms exactly twice (the review badge + the generate toast)', (commsSrc.match(/comms_drafted_badge/g) ?? []).length === 2, `${(commsSrc.match(/comms_drafted_badge/g) ?? []).length} call sites`);
	ok('S3-8: the review column keeps its 360 px column at 1366 (the wrap moved to 1280)', /max-width:\s*1280px/.test(commsSrc) && !/max-width:\s*1400px/.test(commsSrc));
	// the operator-only arm: the three [data-lang][data-withheld] nodes keep
	// an EMPTY draft line — no dash placeholder, no notice text, no Copy button
	const armStart = commsSrc.indexOf('{#if operatorOnly}');
	const triAt = commsSrc.indexOf('comms-trilingual');
	ok('S3-8: the operator-only arm holds the withheld draft columns', armStart >= 0 && triAt > armStart, `arm@${armStart} trilingual@${triAt}`);
	if (armStart >= 0 && triAt > armStart) {
		const seg = commsSrc.slice(armStart);
		const re = /\{#if\s|\{\/if\}|\{:else\}/g;
		let depth = 0;
		let m;
		let elseAt = -1;
		while ((m = re.exec(seg))) {
			if (m[0].startsWith('{#if')) depth += 1;
			else if (m[0] === '{/if}') depth -= 1;
			else if (depth === 1) {
				elseAt = m.index;
				break;
			}
		}
		const arm = elseAt > 0 ? seg.slice(0, elseAt) : seg;
		// the withheld trilingual's TEMPLATE: one node per language, its draft
		// line empty — no dash placeholder, no notice text, no Copy button
		const block = (arm.match(/<div class="trilingual withheld"[\s\S]*?<\/div>/) ?? [''])[0];
		ok(
			'S3-8: the withheld draft columns render quietly — empty draft line, no dash, no notice text, no Copy button',
			block.includes('data-withheld="yes"') &&
				block.includes('adv-text withheld') &&
				/lang=\{s\.code\}><\/p>/.test(block) &&
				!block.includes('—') &&
				!block.includes('comms_withheld') &&
				!block.includes('class="copy"'),
			block ? block.replace(/\s+/g, ' ').slice(0, 160) : 'withheld trilingual not found',
		);
	}
}

// ─── the pack: the new scope keys in every language ─────────────────────────

if (S) {
	for (const key of ['asst_scope_prefix', 'asst_scope_suffix']) {
		const vals = ['en', 'hi', 'mr'].map((l) => S.t(l, key));
		ok(`pack: ${key} exists in EN/HI/MR`, vals.every((v) => typeof v === 'string' && v !== key && v.length > 0 || key === 'asst_scope_prefix' && (v === '' || v.length > 0)) && vals[0].length > 0, JSON.stringify(vals));
	}
	ok('pack: EN scope line composes "Scoped to <subject> and this view"', S.t('en', 'asst_scope_prefix') === 'Scoped to' && S.t('en', 'asst_scope_suffix') === 'and this view');
}

if (failures) {
	console.error(`\nassistant.unit: ${failures} failure(s)`);
	process.exit(1);
}
console.log('\nassistant.unit: all checks passed');
