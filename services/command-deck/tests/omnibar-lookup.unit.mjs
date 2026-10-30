/**
 * Omnibar lookup — the officer's console, RENDERED (FIX-E-LOOKUP; audit E
 * round 2: round 1's "component test" only compiled the file and pinned
 * substrings, and 19 of 35 deck mutants survived it — this file now RENDERS
 * the Omnibar with svelte/server through an esbuild .svelte loader, so a
 * mutant has to survive its own output HTML):
 *
 *   1. COMPILES  Omnibar.svelte compiles with the real Svelte 5 compiler —
 *                a mangled or renamed wiring fails here, loudly.
 *   2. RENDER    the whole panel, server-side (no browser, no new dependency:
 *                esbuild compiles .svelte with generate:'server', svelte/server
 *                renders it) — with the officer on and off:
 *                  - no offer for any mark spelling without an officer
 *                    (PS-D7, PS-D7b), and the wiring ORs nothing (E2-b: the
 *                    all-caps date the grammar refuses never offers);
 *                  - every quoted word masked without an officer (PS-D8b);
 *                  - with a seeded outcome (the component's render-test seed
 *                    prop) and an officer: the S3 block — header, key/value
 *                    pairs, human basis, "+N more reads", the reads under
 *                    "Lawful camera reads" with the camera ids in the mono
 *                    voice, both actions, the UNMASKED mark (PS-D8 via the
 *                    exact-Plate pin below), and no raw enum (E4-d…j);
 *                  - the same seeded block ABSENT the moment the officer is
 *                    off — a result never outlives its officer (E1).
 *   3. SIGN-OFF  the reset effect tracks `ops.officerOn` INSIDE the effect
 *                that clears the outcome (E1-b/E1-c moved it to a separate
 *                no-op effect — the block would outlive its officer), and the
 *                block renders only `{#if lookupLines && ops.officerOn}`.
 *   4. WIRES     the auditor-blessed exact pins for what a render cannot
 *                observe (SSR strips handlers): the offer gate reads the
 *                store, "Open vehicle" calls openVehicle, openVehicle
 *                selects, "Show trail" highlights, and the result mark
 *                renders through shown() + masked={!ops.officerOn} in EXACTLY
 *                the two Plate sites (PS-D8, PS-D8c — equivalent under the
 *                guard, so the count is the kill).
 *   5. DATES     the offer's own gate: no date phrase in any case, every mark
 *                spelling (1–4 digits included — the auditor's MH01AB123 /
 *                MH 1 AB 1 rows) and the BH series (plate-search.unit.mjs
 *                carries the full truth table).
 *   6. GRAMMAR   the palette words the help shows are typeable: parseCommand
 *                resolves "sensor ironbow", "sensor white hot" and their HI/MR
 *                spellings to the mode ids; an unknown word passes through
 *                untouched (the omnibar refuses it without echoing it).
 *   7. PRESENTER the block's lines (vehicle-lookup.ts): human labels not
 *                enums for EVERY lawful basis × EN/HI/MR, always-dated reads,
 *                "+N more reads", the URNs, the 422 through the translated
 *                key, the no-basis note through its key.
 *   8. PACKS     every ws_lookup_* / ws_basis_* / map_pal_* key exists in the
 *                EN, HI and MR packs THEMSELVES (t()'s EN fallback cannot
 *                mask a missing translation — E5-b/E5-c).
 *
 *   node tests/omnibar-lookup.unit.mjs
 *   node tests/omnibar-lookup.unit.mjs --src <dir>     a scratch copy of src
 *                                                      (the pre-change proof)
 *
 * Exits 0 with `ok <name>` lines, 1 on any failure.
 */

import { createRequire } from 'node:module';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const DECK = path.resolve(HERE, '..');
const opt = (name, dflt) => {
	const i = process.argv.indexOf(name);
	return i > 0 && process.argv[i + 1] ? path.resolve(process.argv[i + 1]) : dflt;
};
const SRC = opt('--src', path.join(DECK, 'src'));

let failures = 0;
function ok(name, cond, detail = '') {
	if (cond) console.log(`ok   ${name}${detail ? ` — ${detail}` : ''}`);
	else {
		failures++;
		console.error(`FAIL ${name}${detail ? ` — ${detail}` : ''}`);
	}
}

const require = createRequire(path.join(DECK, 'package.json'));
const { existsSync, readFileSync } = await import('node:fs');

// ─── 1. the component compiles (the real Svelte 5 compiler) ────────────────

const OMNIBAR = path.join(SRC, 'lib/workspace/components/omnibar/Omnibar.svelte');
const source = readFileSync(OMNIBAR, 'utf8');
const { compile } = require('svelte/compiler');
let compiled = null;
try {
	compiled = compile(source, { filename: OMNIBAR, generate: 'client', runes: true });
} catch (e) {
	console.error(`FAIL compiles — ${e && e.message ? e.message : e}`);
	failures++;
}
ok('compiles: Omnibar.svelte compiles with the real Svelte 5 compiler (runes)', !!compiled && compiled.js && compiled.js.code.length > 1000, `${source.length} chars of source`);

// ─── 2. the panel, RENDERED (esbuild svelte loader + svelte/server) ────────

const esbuild = require('esbuild');

/** SSR has no mount: run the callback synchronously so the panel's hotkey
 *  claim runs and `holding` becomes true (the body renders). */
function shimOnMount(js) {
	return js.replace(/import\s*\{([^}]*)\}\s*from\s*['"]svelte['"];?/g, (_m, names) => {
		const kept = names
			.split(',')
			.map((s) => s.trim())
			.filter(Boolean)
			.filter((n) => n !== 'onMount');
		const imp = kept.length ? `import { ${kept.join(', ')} } from 'svelte';` : '';
		return `${imp}\nconst onMount = (fn) => { try { fn && fn(); } catch {} };`;
	});
}

const svelteServerLoader = {
	name: 'svelte-server',
	setup(build) {
		// the render's hotkey claim is the test's: one holder, always
		build.onLoad({ filter: /omnibar[\\/]hotkey\.ts$/ }, () => ({
			contents: `export const claimHotkey = () => true;
export const releaseHotkey = () => {};
export const typingIn = () => false;`,
			loader: 'js',
		}));
		build.onLoad({ filter: /\.svelte$/ }, async (args) => {
			const src = readFileSync(args.path, 'utf8');
			try {
				const out = compile(src, { filename: args.path, generate: 'server', runes: true });
				return { contents: shimOnMount(out.js.code), loader: 'js', resolveDir: path.dirname(args.path) };
			} catch (e) {
				return { errors: [{ text: `${args.path}: ${e && e.message ? e.message : e}` }] };
			}
		});
	},
};

// Svelte 5 runes in .svelte.ts stores are runtime calls: identity stubs
// (the plate-search pattern), set BEFORE the bundle is imported.
globalThis.$state = Object.assign((v) => v, { raw: (v) => v, snapshot: (v) => v });
globalThis.$derived = Object.assign((v) => v, { by: (f) => f() });
globalThis.$effect = Object.assign(() => {}, { root: () => () => {}, pre: () => {} });
globalThis.window = { addEventListener() {}, removeEventListener() {} };

const RENTRY = `
import Omnibar from '${SRC}/lib/workspace/components/omnibar/Omnibar.svelte';
export { workspace } from '${SRC}/lib/workspace/workspace.svelte';
export { ops } from '${SRC}/lib/ops/store.svelte';
export { commandBar } from '${SRC}/lib/shell/command-bar.svelte';
export { render } from 'svelte/server';
export { Omnibar };
`;
let R = null;
try {
	const rbuilt = await esbuild.build({
		stdin: { contents: RENTRY, resolveDir: DECK, loader: 'ts', sourcefile: 'omnibar-render-entry.ts' },
		absWorkingDir: DECK,
		alias: { $lib: path.join(SRC, 'lib') },
		nodePaths: [path.join(DECK, 'node_modules')],
		plugins: [svelteServerLoader],
		define: { 'import.meta.env.DEV': 'false' },
		bundle: true,
		format: 'esm',
		platform: 'node',
		write: false,
		logLevel: 'silent',
	});
	ok('render: the bundle builds (esbuild compiles .svelte for svelte/server, in memory)', rbuilt.errors.length === 0 && rbuilt.outputFiles.length === 1, rbuilt.errors.map((e) => e.text).slice(0, 2).join('; ') || `${rbuilt.outputFiles[0].text.length} bytes`);
	R = await import(`data:text/javascript;base64,${Buffer.from(rbuilt.outputFiles[0].text).toString('base64')}`);
} catch (e) {
	console.error(`FAIL render bundle — ${e && e.message ? e.message : e}`);
	failures++;
}

/** The SSR'd input echoes its value attribute; every assertion here is about
 *  TEXT and structure, so the attribute is stripped before comparing. */
const stripValues = (html) => html.replace(/\svalue="[^"]*"/g, '');
/** A word must not appear in any TEXT node (attributes like data-key are grammar, not console copy). */
const noTextNode = (html, word) => !new RegExp(`>[^<]*${word.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}`).test(html);

/** Render the panel for one query/officer/seed — as a MAP page mounts it
 *  (onfly/onhighlight present, so "Show trail" and the fly commands serve). */
function renderOmnibar({ query = '', officer = false, seedOutcome = null, lang = 'en' } = {}) {
	R.commandBar.lang = lang;
	R.workspace.omnibar.open = true;
	R.workspace.omnibar.query = query;
	R.ops.setDutyOfficer(officer ? 'Duty Officer A' : '');
	return stripValues(R.render(R.Omnibar, { props: { onfly: () => {}, onhighlight: () => {}, onsensor: () => {}, onlayer: () => {}, seedOutcome } }).html);
}

if (R) {
	// orchestrator make-up (audit E-LOOKUP R2): the BH-series offer renders with an officer (it was hidden behind
	// "No matches"), and the HI/MR offer row keeps the pack's word order with the mark between the halves
	const bh = renderOmnibar({ query: '22BH1234AA', officer: true });
	ok('render, officer on: a BH-series mark is offered and no "No matches" shows', bh.includes('data-key="vehicle-lookup"') && !bh.includes('No matches'), 'BH offer');
	for (const [lang, before, after] of [['hi', 'वाहन ', ' देखें'], ['mr', 'वाहन ', ' शोधा']]) {
		const h = renderOmnibar({ query: 'MH47EM9001', officer: true, lang });
		const row = h.slice(h.indexOf('data-key="vehicle-lookup"'), h.indexOf('data-key="vehicle-lookup"') + 1200);
		const iB = row.indexOf(before), iM = row.indexOf('MH47EM9001'), iA = row.indexOf(after);
		ok(`render, ${lang}: the offer row reads "${before}<mark>${after}" in the pack's order`, iB >= 0 && iM > iB && iA > iM, `${iB} ${iM} ${iA}`);
	}
	R.commandBar.lang = 'en';
	// 2a. no officer, no offer — for every mark spelling
	const OFFER_MARKS = ['MH47EM9001', 'mh 47 em 9001', '22BH1234AA'];
	const offBad = OFFER_MARKS.filter((q) => renderOmnibar({ query: q, officer: false }).includes('data-key="vehicle-lookup"'));
	ok(
		'render, no officer: the lookup offer never appears — every mark spelling (PS-D7, PS-D7b)',
		offBad.length === 0,
		offBad.join(' | ') || `${OFFER_MARKS.length} spellings offerless`,
	);

	// 2b. no officer: every quoted word masked (PS-D8b)
	const masked = renderOmnibar({ query: 'layer mh47em9001 on', officer: false });
	ok(
		'render, no officer: shown() masks every quoted word — the layer row carries the masked mark, never the raw one (PS-D8b)',
		masked.includes('mh47em•••1') && noTextNode(masked, 'mh47em9001'),
		(masked.match(/<span class="lbl[^>]*>([^<]*)<\/span>/) || [, 'no label'])[1],
	);

	// 2c. the S3 block, officer on, seeded outcome
	const FOUND_SEED = {
		ok: true,
		httpStatus: 200,
		result: {
			found: true,
			mark: 'MH47EM9001',
			mark_masked: 'MH47EM•••1',
			vehicle_id: '11111111-1111-4111-8111-111111111111',
			vehicle_class: 'car',
			earmark: { state: 'watch', reason: 'FIR 4401/2026', lawful_basis: 'stolen_vehicle_fir', retention_until: '2026-11-23T00:00:00Z' },
			open_recommendations: [{ recommendation_id: 'r1', rule_id: 'R_SPD_SEGMENT', status: 'pending' }],
			open_pursuits: [],
			disclosure: 'active_earmark',
			reads: [1, 2, 3, 4, 5].map((i) => ({ sighting_id: `s${i}`, camera_id: `EM-CAM-0${i}`, t: '2026-10-24T13:00:00Z' })),
			note: null,
			audit: { officer: 'Duty Officer A', looked_up_at: '2026-10-24T14:05:00Z' },
		},
	};
	const found = renderOmnibar({ query: 'MH47EM9001', officer: true, seedOutcome: FOUND_SEED });
	ok(
		'render, officer on: the S3 block — header, key/value pairs, the human basis, "+N more reads", the reads under "Lawful camera reads", the camera ids in the Id voice, both actions, the mark UNMASKED (E4-a…j, PS-D8)',
		found.includes('data-testid="omni-lookup"') &&
			found.includes('>Vehicle lookup<') &&
			found.includes('>Status<') &&
			found.includes('>Registration mark<') &&
			found.includes('Watchlisted · Stolen vehicle (FIR)') &&
			noTextNode(found, 'stolen_vehicle_fir') &&
			found.includes('+2 more reads') &&
			found.includes('Lawful camera reads · 5') &&
			/<span data-ui="id"[^>]*>EM-CAM-01<\/span>/g.test(found) &&
			found.includes('data-testid="omni-lookup-open"') &&
			found.includes('data-testid="omni-lookup-trail"') &&
			found.includes('data-masked="false"') &&
			noTextNode(found, '•••1'),
		`block ${found.includes('data-testid="omni-lookup"') ? '+' : '-'} unmasked ${found.includes('data-masked="false"') ? '+' : '-'} id+more ${found.includes('+2 more reads') ? '+' : '-'}`,
	);
	// the offer row too — its echoed mark through the format dir's Plate, unmasked
	ok(
		'render, officer on: the offer names the canonical mark, the mark through Plate (PS-D9, PS-D9b, S3)',
		found.includes('data-key="vehicle-lookup"') &&
			/Look up vehicle [\s\S]{0,120}?data-ui="plate"/.test(found) &&
			/data-masked="false"[^>]*><span class="mark[^"]*">MH47EM9001<\/span>/.test(found),
	);

	// 2d. sign-off: the seeded block never renders without its officer (E1)
	const retired = renderOmnibar({ query: 'MH47EM9001', officer: false, seedOutcome: FOUND_SEED });
	ok(
		'render, sign-off: the block never renders without an officer — a seeded result and no officer renders nothing (E1, E1-b)',
		!retired.includes('data-testid="omni-lookup"') && !retired.includes('Vehicle lookup'),
	);

	// 2e. the wiring ORs nothing: the all-caps date never offers (E2-b)
	const dated = renderOmnibar({ query: 'ON 12 OCT 2026', officer: true });
	ok(
		'render, officer on: the all-caps date the grammar refuses never offers — the wiring ORs nothing (E2-b)',
		!dated.includes('data-key="vehicle-lookup"'),
	);

	// 2f. "sensor ironbow" names the palette in words, never the flir-* id (TH-10)
	const iron = renderOmnibar({ query: 'sensor ironbow', officer: true });
	ok(
		'render: "sensor ironbow" resolves to the palette word — the flir-* id never reaches a text node (TH-10)',
		iron.includes('Thermal-style view: ironbow') && !iron.includes(': flir-iron'),
	);

	// 2g. an unknown mode is refused without echoing the typed word (audit E item 3)
	const plaid = renderOmnibar({ query: 'sensor plaid', officer: true });
	ok(
		'render: an unknown thermal-style view is refused honestly — the typed word never lands in a localised label',
		plaid.includes('No thermal-style view with that name') && noTextNode(plaid, 'plaid'),
	);
}

// ─── 3./4. the wires: exact pins for what a render cannot see ──────────────
// SSR strips event handlers, and the two Plate sites are equivalent under the
// guard — so the handler wiring and the Plate count are pinned exactly (the
// auditor's blessed minimum), on both the raw source and the compiled js.

const PINS = [
	{
		name: 'offer gate: lookupOfferActive takes ops.officerOn from the store, never a constant (PS-D7)',
		needle: 'lookupOfferActive(result, query, ops.officerOn)',
		js: /lookupOfferActive\([\s\S]{0,60}ops\.officerOn\)/,
	},
	{
		name: 'offer gate: the derived line ORs nothing (E2-b, PS-D7b)',
		needle: 'const lookupOffer = $derived(lookupOfferActive(result, query, ops.officerOn));',
		srcOnly: true, // the derived compiles away; the RENDER is the behavioural kill
	},
	{
		name: 'sign-off: the result block renders only while an officer is on console (E1)',
		needle: 'lookupLines && ops.officerOn',
		js: /lookupLines[\s\S]{0,30}&&\s*ops\.officerOn/,
	},
	{
		name: 'masking: the result mark renders through shown() with masked={!ops.officerOn} — at EXACTLY the two Plate sites (PS-D8, PS-D8c)',
		needle: '<Plate mark={shown(lookupLines.mark)} masked={!ops.officerOn} />',
		count: 2,
	},
	{
		name: 'canonical: the offer echoes normMark(q) — label and lookup, never the raw query (PS-D9)',
		needle: 'runLookup(normMark(q))',
	},
	{
		name: 'canonical: the offer label quotes the normalised mark, not the raw query (PS-D9)',
		needle: "L('ws_lookup_offer', normMark(q))",
	},
	{
		name: 'app path: runLookup stores the outcome for the block (R2-1)',
		needle: '\t\tlookupOutcome = outcome;',
		srcOnly: true,
	},
	{
		name: 'app path: a stale answer (newer lookup or changed query) is dropped (R2-2)',
		needle: 'if (seq !== lookupSeq || normMark(workspace.omnibar.query) !== mark) return;',
		srcOnly: true,
	},
	{
		name: 'action: "Open vehicle" wires openVehicle (E4-a)',
		needle: 'onclick={() => openVehicle(lookupLines)}',
		srcOnly: true, // SSR strips handlers — the exact pin is the auditor's blessed minimum
	},
	{
		name: 'action: openVehicle selects the looked-up vehicle (E4-b)',
		needle: "selection.select(lines.vehicleUrn, { fly: hasMap, source: 'omnibar' });",
		srcOnly: true,
	},
	{
		name: 'action: "Show trail" highlights the lawful reads (E4-c)',
		needle: 'onhighlight?.(lines.readUrns);',
		srcOnly: true,
	},
	{
		name: 'block: the section header renders (E4-e)',
		needle: "<p class=\"lk-head\">{L('ws_lookup_heading')}</p>",
		srcOnly: true, // markup compiles into template literals; the RENDER asserts the output
	},
	{
		name: 'block: "+N more reads" is gated on the presenter, not removed (E4-d)',
		needle: '{#if lookupLines.moreReads}',
		srcOnly: true,
	},
	{
		name: 'block: the actions block is gated on the URNs, not removed (E4-g)',
		needle: '{#if lookupLines.vehicleUrn || (hasMap && lookupLines.readUrns.length)}',
		srcOnly: true,
	},
	{
		name: 'block: the Status VALUE is the presenter heading, never a raw enum (E4-f)',
		needle: '<span class="v">{lookupLines.heading}</span>',
		srcOnly: true,
	},
	{
		name: 'block: the key/value grid keeps its Status key (E4-j)',
		needle: "<span class=\"k\">{L('ws_lookup_k_status')}</span>",
		srcOnly: true,
	},
];
for (const p of PINS) {
	if (p.count != null) {
		const n = source.split(p.needle).length - 1;
		ok(p.name, n === p.count, `${n} × ${p.needle}`);
		continue;
	}
	const inSrc = source.includes(p.needle);
	if (p.srcOnly) {
		ok(p.name, inSrc, inSrc ? 'pinned in the raw source' : 'absent from the raw source');
		continue;
	}
	const pats = p.js ? (Array.isArray(p.js) ? p.js : [p.js]) : [new RegExp(p.needle.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))];
	const inJs = pats.every((re) => !!compiled && re.test(compiled.js.code));
	ok(p.name, inSrc && inJs, inSrc && !inJs ? 'in the raw source but NOT in the compiled js' : !inSrc ? 'absent from the raw source' : 'present in source and compiled js');
}

// E1-b/E1-c: officerOn must be read INSIDE the effect that clears the outcome
// (moved to a separate no-op effect, the block outlives its officer).
{
	const bodies = [];
	let i = source.indexOf('$effect(');
	while (i >= 0) {
		const open = source.indexOf('{', i);
		let depth = 0;
		let j = open;
		for (; j < source.length; j++) {
			if (source[j] === '{') depth++;
			else if (source[j] === '}') {
				depth--;
				if (!depth) break;
			}
		}
		bodies.push(source.slice(open + 1, j));
		i = source.indexOf('$effect(', j);
	}
	ok(
		'sign-off: the reset effect tracks ops.officerOn IN the effect that clears the outcome (E1-b, E1-c)',
		bodies.some((b) => b.includes('officerOn') && b.includes('lookupOutcome = null')),
		`${bodies.length} $effect block(s) in the source`,
	);
}

// ─── 5. the presenter (the real vehicle-lookup.ts, bundled) ────────────────

const ENTRY = `
import '${SRC}/lib/i18n/packs';
export * as lookup from '${SRC}/lib/workspace/vehicle-lookup';
export * as search from '${SRC}/lib/workspace/search';
export * as mask from '${SRC}/lib/workspace/mask';
export { t } from '${SRC}/lib/i18n/strings';
`;
const built = await esbuild.build({
	stdin: { contents: ENTRY, resolveDir: DECK, loader: 'ts', sourcefile: 'omnibar-lookup-entry.ts' },
	absWorkingDir: DECK,
	alias: { $lib: path.join(SRC, 'lib') },
	bundle: true,
	format: 'esm',
	platform: 'node',
	write: false,
	logLevel: 'silent',
});
ok('bundle builds (esbuild, $lib aliased, in memory)', built.errors.length === 0 && built.outputFiles.length === 1, built.errors.map((e) => e.text).join('; ') || 'vehicle-lookup.ts + search.ts + i18n packs');

const { lookup: VL, search: SR, t } = await import(`data:text/javascript;base64,${Buffer.from(built.outputFiles[0].text).toString('base64')}`);

const calls = [];
let responder = null;
globalThis.fetch = async (url, init) => {
	calls.push({ url: String(url), init });
	if (!responder) throw new Error(`unexpected fetch: ${url}`);
	return responder(String(url), init);
};
const json = (status, body) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

// 5a. the dates truth table: a date phrase never offers, a mark always does (the
// offer's own gate, officer ON — the OFF state is plate-search's group 3).
const WATCHED = { kind: 'vehicle', urn: 'vehicle:00000000-0000-4000-8000-000000000007', id: '00000000-0000-4000-8000-000000000007', label: 'MH01XX•••7', props: { plate: 'MH01XX0007', plate_masked: 'MH01XX•••7' } };
const OFFER_ON = [
	'MH47EM9001', 'mh47em9001', 'Mh 47 Em 9001', 'MH-01-AB-1234', 'dl8sep1234', 'DL 8 SEP 1234', // a month series reads as a mark when the state code AND the series are upper case
	'22BH1234AA', '22bh1234aa', // the BH series (the mask structurally refuses it, the offer does not)
	'MH01AB123', 'MH 1 AB 1', // 1–3-digit numbers: plates.py accepts them (audit E round 2)
];
const OFFER_OFF_DATES = [
	'on 12 oct 2026', 'on 12 Oct 2026', 'up 12 dec 2026', // a month series with a separator is a date (mask.ts's rule)
	'ON 12 OCT 2026', 'ON 1 OCT 2026', 'BY 12 JAN 2027', // the all-caps spellings hasRawMark's superset pass still offered (audit E round 2)
	'24 Oct 2026', '2026-10-24', 'MH47EM', 'J15', 'strand road',
];
const offerOnBad = OFFER_ON.filter((q) => !SR.lookupOfferActive(SR.search([WATCHED], q), q, true));
const offerDateBad = OFFER_OFF_DATES.filter((q) => SR.lookupOfferActive(SR.search([WATCHED], q), q, true));
ok(
	'dates are never offered as a vehicle lookup; every mark spelling and the BH series still are',
	offerOnBad.length === 0 && offerDateBad.length === 0,
	`marks refused: ${offerOnBad.join(' | ') || 'none'} · dates offered: ${offerDateBad.join(' | ') || 'none'}`,
);

// 5a2. the palette words are TYPEABLE (audit E round 2, item 3): the help and
// the grammar agree, in EN, HI and MR.
const GRAMMAR = [
	['sensor ironbow', 'flir-iron'],
	['sensor White Hot', 'flir-whot'],
	['sensor black hot', 'flir-bhot'],
	['sensor normal colours', 'raw'],
	['sensor flir-iron', 'flir-iron'],
	['sensor command', 'raw'],
	['sensor सफ़ेद गर्म', 'flir-whot'],
	['sensor आयरनबो', 'flir-iron'],
	['sensor आयर्नबो', 'flir-iron'],
	['sensor नेहमीचे रंग', 'raw'],
];
const gBad = GRAMMAR.filter(([q, mode]) => (SR.parseCommand(q) || {}).mode !== mode);
ok(
	'the grammar accepts the palette words the help shows, in EN, HI and MR (audit E item 3)',
	gBad.length === 0,
	gBad.map(([q]) => q).join(' | ') || `${GRAMMAR.length} typeable words`,
);
ok(
	'an unresolvable sensor word stays the raw mode — the omnibar refuses it without echoing it',
	SR.parseCommand('sensor plaid')?.type === 'sensor' && SR.parseCommand('sensor plaid')?.mode === 'plaid',
	JSON.stringify(SR.parseCommand('sensor plaid')),
);

// 5b. the S3 result block, through the presenter
const NOW = Date.UTC(2026, 9, 24, 12, 0, 0); // 17:30 IST, 24 Oct 2026
const istDay = new Intl.DateTimeFormat('en-GB', { timeZone: 'Asia/Kolkata', day: 'numeric', month: 'short' });
const istHm = new Intl.DateTimeFormat('en-GB', { timeZone: 'Asia/Kolkata', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' });
const dated = (iso) => `${istDay.format(Date.parse(iso))} ${istHm.format(Date.parse(iso))}`;
const FOUND_BODY = {
	found: true,
	mark: 'MH47EM9001',
	mark_masked: 'MH47EM•••1',
	vehicle_id: '11111111-1111-4111-8111-111111111111',
	vehicle_class: 'car',
	earmark: { state: 'watch', reason: 'Stolen MH47EM9001 reported — FIR 4401/2026', lawful_basis: 'stolen_vehicle_fir', retention_until: '2026-11-23T00:00:00Z' },
	open_recommendations: [{ recommendation_id: '22222222-2222-4222-8222-222222222222', rule_id: 'R_SPD_SEGMENT', status: 'pending' }],
	open_pursuits: [],
	disclosure: 'active_earmark',
	reads: [
		{ sighting_id: 's1', camera_id: 'EM-CAM-03', t: '2026-10-24T13:00:00Z' },
		{ sighting_id: 's2', camera_id: 'EM-CAM-01', t: '2026-10-24T13:40:00Z' },
	],
	note: null,
	audit: { officer: 'Duty Officer A', looked_up_at: '2026-10-24T14:05:00Z' },
};
responder = () => json(200, FOUND_BODY);
const found = await VL.lookupVehicle('MH47EM9001');
const fv = VL.lookupView(found, 'en', NOW);
ok(
	'found: human labels not enums — the heading names the basis through its pack key, never `stolen_vehicle_fir`',
	fv.heading === `Watchlisted · ${t('en', 'ws_basis_stolen_vehicle_fir')}` && fv.heading.includes('Stolen vehicle (FIR)') && !fv.heading.includes('stolen_vehicle_fir'),
	fv.heading,
);
ok(
	'found: read times are ALWAYS dated (date + time, even the anchor day), and the block carries the trail and the vehicle URNs',
	fv.reads === 2 && fv.readRows[0] === `EM-CAM-03 · ${dated('2026-10-24T13:00:00Z')}` && fv.readRows[0].includes('24 Oct') && (fv.readUrns ?? []).join(',') === 'sighting:s1,sighting:s2' && fv.vehicleUrn === `vehicle:${FOUND_BODY.vehicle_id}`,
	`${fv.readRows.join(' / ')} · ${(fv.readUrns ?? []).join(',')} · ${fv.vehicleUrn}`,
);
ok('found: recommendations and pursuits arrive as counts', fv.recommendations === 1 && fv.pursuits === null, `${fv.recommendations} · ${fv.pursuits}`);

// 5b2. EVERY lawful basis the oracle accepts, in words, in every language
// (audit E round 2, item 5: four of the five fell through to the enum).
const BASIS_CODES = ['mva_1988_s177', 'mva_1988_s183', 'mva_1988_s207', 'bnss_2023_s94', 'stolen_vehicle_fir'];
const basisBad = [];
for (const code of BASIS_CODES) {
	for (const lang of ['en', 'hi', 'mr']) {
		const words = VL.basisWords(code, lang);
		const en = VL.basisWords(code, 'en');
		if (!words || words === `ws_basis_${code}` || words.includes('_') || /mva 1988 s\d|bnss 2023 s\d/.test(words.toLowerCase()) || (lang !== 'en' && words === en)) basisBad.push(`${lang}:${code}→${words}`);
	}
}
ok(
	'lawful bases: every basis renders in words in EN, HI and MR — no underscore, no enum sentence, HI/MR their own words (audit E item 5)',
	basisBad.length === 0,
	basisBad.join(' | ') || BASIS_CODES.map((c) => `${c}: ${VL.basisWords(c, 'en')} / ${VL.basisWords(c, 'hi')} / ${VL.basisWords(c, 'mr')}`).join(' · '),
);

// 5c. +N more reads
const MANY = { ...FOUND_BODY, reads: [1, 2, 3, 4, 5].map((i) => ({ sighting_id: `s${i}`, camera_id: `EM-CAM-0${i}`, t: '2026-10-24T13:00:00Z' })) };
responder = () => json(200, MANY);
const many = await VL.lookupVehicle('MH47EM9001');
const mv = VL.lookupView(many, 'en', NOW);
ok(
	'three reads shown, the rest as "+N more reads" (translated), the whole trail still in readUrns',
	mv.readRows.length === 3 && mv.moreReads === 2 && t('en', 'ws_lookup_more_reads', 2) === '+2 more reads' && (mv.readUrns ?? []).length === 5,
	`${mv.readRows.length} rows · +${mv.moreReads} · ${(mv.readUrns ?? []).length} urns`,
);

// 5d. the 422 shows the translated key, never the server detail (which echoed input)
responder = () => json(422, { detail: "not a registration plate: 'mh 12 oct 2026!' (expected e.g. MH47EM9001 or a BH-series plate such as 22BH1234AA)" });
const invalid = await VL.lookupVehicle('mh 12 oct 2026!');
const iv = VL.lookupView(invalid, 'en', NOW);
ok(
	'422: the deck shows the translated invalid-mark copy — never the server detail, the input, or a full mark',
	!invalid.ok && invalid.httpStatus === 422 && iv.state === 'error' && iv.detail === t('en', 'ws_lookup_invalid_plate') && !iv.detail.includes('mh 12 oct 2026!') && !iv.detail.includes('MH47EM9001') && !iv.detail.includes('22BH1234AA'),
	iv.detail,
);
ok('the invalid-mark copy is translated (HI and MR carry it; none echoes a full mark)', ['en', 'hi', 'mr'].every((l) => t(l, 'ws_lookup_invalid_plate') !== 'ws_lookup_invalid_plate'), `${t('hi', 'ws_lookup_invalid_plate')} · ${t('mr', 'ws_lookup_invalid_plate')}`);

// 5e. the no-basis note via the translated key (HI must not show the EN server sentence)
const NO_BASIS_NOTE = "No lawful basis to show this vehicle's camera reads — earmark it with a lawful basis to proceed";
const NO_BASIS_BODY = { ...FOUND_BODY, earmark: null, disclosure: 'none', reads: [], note: NO_BASIS_NOTE, audit: { ...FOUND_BODY.audit, disclosure: 'none' } };
responder = () => json(200, NO_BASIS_BODY);
const nobasis = await VL.lookupVehicle('MH47EM9001');
const bv = VL.lookupView(nobasis, 'en', NOW);
const bvHi = VL.lookupView(nobasis, 'hi', NOW);
ok(
	'no lawful basis: the note renders through the translated key (EN identical to the server sentence; HI in Hindi, never the EN sentence)',
	bv.note === t('en', 'ws_lookup_nobasis') && bv.note === NO_BASIS_NOTE && bvHi.note === t('hi', 'ws_lookup_nobasis') && bvHi.note !== NO_BASIS_NOTE && t('mr', 'ws_lookup_nobasis') !== NO_BASIS_NOTE,
	`hi: ${bvHi.note}`,
);
// …and ONLY that sentence maps to the key: any other server note is shown as sent
const OTHER_NOTE_BODY = { ...FOUND_BODY, earmark: null, disclosure: 'none', reads: [], note: 'Retention for this mark lapsed yesterday.', audit: { ...FOUND_BODY.audit, disclosure: 'none' } };
responder = () => json(200, OTHER_NOTE_BODY);
const other = await VL.lookupVehicle('MH47EM9001');
const ov = VL.lookupView(other, 'en', NOW);
ok(
	'no lawful basis: a DIFFERENT server note is shown as sent — round 1 mapped any note to the no-basis sentence (audit E nice-to-have)',
	ov.note === 'Retention for this mark lapsed yesterday.' && ov.note !== t('en', 'ws_lookup_nobasis'),
	ov.note,
);

// 5f. the new keys exist in the HI and MR packs THEMSELVES (audit E round 2,
// item 10): t() falls back to EN, so a rendered assertion cannot catch a
// missing translation — the pack source is parsed instead (the thermal test's
// registerPack AST walk).
{
	const ts = require('typescript');
	function unwrap(node) {
		let n = node;
		while (n && (ts.isAsExpression(n) || ts.isSatisfiesExpression?.(n) || ts.isParenthesizedExpression(n))) n = n.expression;
		return n;
	}
	function textOf(node) {
		const n = unwrap(node);
		if (!n) return null;
		if (ts.isStringLiteral(n) || ts.isNoSubstitutionTemplateLiteral(n)) return n.text;
		if (ts.isTemplateExpression(n)) return n.head.text + n.templateSpans.map((s) => '‹x›' + s.literal.text).join('');
		if (ts.isArrowFunction(n) || ts.isFunctionExpression(n)) {
			if (n.body && !ts.isBlock(n.body)) return textOf(n.body);
		}
		return null;
	}
	function packsOf(file) {
		const sf = ts.createSourceFile(file, readFileSync(file, 'utf8'), ts.ScriptTarget.Latest, true, ts.ScriptKind.TS);
		const decls = new Map();
		const calls = [];
		(function visit(node) {
			if (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name) && node.initializer) decls.set(node.name.text, node.initializer);
			if (ts.isCallExpression(node) && ts.isIdentifier(node.expression) && node.expression.text === 'registerPack') {
				const [code, pack] = node.arguments;
				if (code && ts.isStringLiteral(code.text ? code : code) && ['en', 'hi', 'mr'].includes(code.text) && pack) calls.push([code.text, pack]);
			}
			ts.forEachChild(node, visit);
		})(sf);
		const out = { en: {}, hi: {}, mr: {} };
		for (const [code, arg] of calls) {
			const a = unwrap(arg);
			const obj = ts.isObjectLiteralExpression(a) ? a : ts.isIdentifier(a) && decls.has(a.text) ? unwrap(decls.get(a.text)) : null;
			if (!obj || !ts.isObjectLiteralExpression(obj)) continue;
			for (const p of obj.properties) {
				if (!ts.isPropertyAssignment(p)) continue;
				const name = p.name && (ts.isIdentifier(p.name) || ts.isStringLiteral(p.name)) ? p.name.text : null;
				const text = textOf(p.initializer);
				if (name !== null && typeof text === 'string') out[code][name] = text;
			}
		}
		// HI and MR live ONLY in the per-language modules (FIX-E-PERF2): read `export const hi|mr = {…}` there
		for (const code of ['hi', 'mr']) {
			const chunk = file.replace(/\.ts$/, `.${code}.ts`);
			if (!existsSync(chunk)) continue;
			const cf = ts.createSourceFile(chunk, readFileSync(chunk, 'utf8'), ts.ScriptTarget.Latest, true, ts.ScriptKind.TS);
			for (const st of cf.statements) {
				if (!ts.isVariableStatement(st)) continue;
				for (const d of st.declarationList.declarations) {
					const obj = unwrap(d.initializer);
					if (!ts.isIdentifier(d.name) || d.name.text !== code || !obj || !ts.isObjectLiteralExpression(obj)) continue;
					for (const p of obj.properties) {
						if (!ts.isPropertyAssignment(p)) continue;
						const name = p.name && (ts.isIdentifier(p.name) || ts.isStringLiteral(p.name)) ? p.name.text : null;
						const text = textOf(p.initializer);
						if (name !== null && typeof text === 'string') out[code][name] = text;
					}
				}
			}
		}
		return out;
	}
	const CORE = packsOf(path.join(SRC, 'lib/i18n/packs.ts'));
	const MAPS = packsOf(path.join(SRC, 'lib/i18n/packs.map.ts'));
	const LOOKUP_KEYS = [
		'ws_lookup_offer', 'ws_lookup_offer_detail', 'ws_lookup_running', 'ws_lookup_officer_required', 'ws_lookup_error', 'ws_lookup_none', 'ws_lookup_watchlist', 'ws_lookup_unwatched',
		'ws_lookup_reads', 'ws_lookup_recommendations', 'ws_lookup_pursuits', 'ws_lookup_recorded', 'ws_lookup_heading', 'ws_lookup_k_mark', 'ws_lookup_k_status', 'ws_lookup_open_vehicle',
		'ws_lookup_show_trail', 'ws_lookup_more_reads', 'ws_lookup_nobasis', 'ws_lookup_invalid_plate',
	];
	const BASIS_KEYS = ['ws_basis_mva_1988_s177', 'ws_basis_mva_1988_s183', 'ws_basis_mva_1988_s207', 'ws_basis_bnss_2023_s94', 'ws_basis_stolen_vehicle_fir'];
	const missing = [];
	for (const lang of ['en', 'hi', 'mr']) {
		for (const k of [...LOOKUP_KEYS, ...BASIS_KEYS]) if (!(k in CORE[lang])) missing.push(`${lang}.${k}`);
		for (const k of ['map_pal_raw', 'map_pal_whot', 'map_pal_bhot', 'map_pal_iron']) if (!(k in MAPS[lang])) missing.push(`${lang}.${k}`);
	}
	ok(
		"pack parity: every lookup, basis and palette key exists in the EN, HI and MR packs themselves — t()'s EN fallback cannot mask a missing translation (E5-b, E5-c)",
		missing.length === 0,
		missing.join(', ') || `${LOOKUP_KEYS.length + BASIS_KEYS.length} core keys + 4 palette keys × 3 languages`,
	);
}

if (failures) {
	console.error(`\n${failures} check(s) failed`);
	process.exit(1);
}
console.log('\nok   omnibar lookup — the panel RENDERS officer-gated (no offer unofficered, no block past sign-off), dates never offer, the palette words are typeable, every basis is in words in three languages, and the packs carry their keys');
process.exit(0);
