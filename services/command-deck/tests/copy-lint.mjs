/**
 * Copy lint (SPEC §2.5, §3.5, §11) over the EN strings of the i18n packs.
 *
 *   title-length  a section title (a key ending in `title` / `Title` /
 *                 `heading` / `Heading`, or starting `section_`) is at most
 *                 32 characters;
 *   separator     a chrome string has at most one " · " (a data separator
 *                 such as "Vehicle · Car" is fine; a chain of helper clauses
 *                 is not);
 *   all-caps      no ALL-CAPS word outside the acronym allowlist (SPEC §3.4
 *                 plus plan X3). Tokens with a digit or • (ids, masked
 *                 marks) are never words.
 *
 * UI-S7B: the S7a PINNED_KEYS table is GONE — the final pins (§12.5, the
 * S7b column) hold the merged deck's own copy. What is left is explicit and
 * narrow; nothing exempts a WORD tree-wide except a real acronym:
 *
 *   ACRONYMS          the SPEC §3.4 acronym allowlist extended with the
 *                     operator-protocol acronyms the deck tells the operator
 *                     (API, JSON, NATS, PIN, SMS, VMS — glm/copylint_baseline.txt).
 *                     Acronyms ONLY: ordinary words (SIMULATED, EMULATED,
 *                     UNKNOWN, FEED …) are never here (audit E-S7B F3).
 *   CAPS_SHIELDS      per KEY and per EXACT EN TEXT, the all-caps words one
 *                     string may carry, each entry naming why: a test pin
 *                     that holds the all-caps form verbatim, or a reported
 *                     PRODUCT BLOCKER awaiting the polish round (UI-S7B
 *                     report). A shield stops applying the moment the
 *                     string's text changes, and only the all-caps rule is
 *                     shielded; each one is printed on every run.
 *   LONG_PINNED_TITLES  the two keys whose EN text a test pins VERBATIM and
 *                     which are not section titles (a queue card's rule
 *                     note; a canvas tooltip) — allowed for title-length
 *                     only; every other rule still applies to them.
 *
 * The EN strings are read from the TypeScript AST (no module is executed):
 * the object passed to registerPack('en', …), or a top-level `const en`.
 * Template literals and arrow-function templates are linted with their
 * interpolations as "‹x›".
 *
 * Usage (from services/command-deck):
 *   node tests/copy-lint.mjs         the packs named in tests/style-lint.targets/*.json "copy"
 *   node tests/copy-lint.mjs --all   every EN pack under src/lib/i18n/
 * Prints `file:line rule key — "text"` per hit; exit 1 on any hit.
 */

import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const DECK = path.resolve(HERE, '..');
const require = createRequire(path.join(DECK, 'package.json'));
const ts = require('typescript');

/**
 * SPEC §3.4 acronym allowlist + plan X3 + the operator-protocol acronyms
 * (glm/copylint_baseline.txt; the addendum's list: AI, API, ANPR, CCTV, DSS,
 * ETA, FIR, GPS, ICCC, IMD, IST, NDMA, OSINT, SDMA, SMS, VMS, VVIP and the
 * like). ACRONYMS ONLY — an ordinary English word never belongs here.
 */
const ACRONYMS = new Set(
	(
		'FIR ANPR IST VVIP AMA PS CCTV MV BNSS GPS ETA AI ID OSM SVPI CG SG GIDC RTO GJ UTC J ' +
		'OSINT ICCC SACHET IMD NDMA SDMA GDELT CAP AMC COA AHP TOPSIS EVOI DSS KMC KMDA NKDA WB WBSDMA WBTC WBFES CESC ERSS SSKM NRS BMC MMRDA MSDMA MSRDC BEST MTP MH BKC CSMT LTT WEH EEH JVLR SCLR LBS SV NM KEM JJ TT GSB LTMGH SVP VP JSS DN ' +
		// the deck tells the operator these protocol names as they are (tests pin them)
		'API JSON NATS PIN SMS VMS ' +
		// the open city feeds' publishers and indices (services/cityfeeds): acronyms people say as they are
		'AQI CPCB WBPCB CAMS DVC CWC GDACS USGS RSMC NWS NDMA ' +
		// Mumbai (the city pack): agencies, operators, hospitals, plates and the places people name by their initials
		// (BMC and its 1916 control, BEST, MMRDA, Maharashtra SDMA, MSRDC, MPCB, Mumbai Traffic Police, the metro
		// operators, Central/Western Railway, MH plates; CSMT, BKC, WEH/EEH, JVLR/SCLR, LBS Marg, SV Road, Dadar TT, KEM)
		'BMC BEST MMRDA MSDMA MSRDC MPCB MTP MMRCL MMMOCL MMOPL CR WR MH CSMT BKC WEH EEH JVLR SCLR LBS SV TT KEM LTMGH ' +
		// the language switch's short code (EN · हि · मरा): a code, not a word
		'EN'
	).split(/\s+/)
);

/**
 * Per-key, per-exact-text all-caps shields. `text` is the EN string exactly
 * as this lint reads it (interpolations as ‹x›); `words` the only all-caps
 * words it may carry; `why` the pin or the reported blocker.
 */
const CAPS_SHIELDS = new Map([
	[
		'adv_emulated_prefix',
		{
			file: 'src/lib/i18n/strings.citizen.ts',
			text: '[SIMULATED FEED · EMULATED — exercise text, not a real road hold]',
			words: ['SIMULATED', 'FEED', 'EMULATED'],
			why: 'PINNED: the exercise marker carried IN the copied draft string, all-caps so a copy never passes for a real hold — tests/ops-guard.entry.ts:1009 (startsWith "[SIMULATED FEED · EMULATED"), tests/workspace.unit.mjs:284-290',
		},
	],
]);

/**
 * Keys whose EN text a test pins VERBATIM and which are NOT section titles —
 * the title-length cap does not apply to them (every other rule still does).
 *   queueStolenTitle  strings.ops.ts — the stolen-vehicle queue card's rule
 *                     note; ops-wall-smoke pins the withheld sentence inside
 *                     it verbatim (C-N), so it cannot be shortened.
 *   canvas_ama_title  packs.agent.ts — the canvas chip's TOOLTIP (a title
 *                     attribute, not a section heading; UI-S1B round 1).
 */
const LONG_PINNED_TITLES = new Set(['queueStolenTitle', 'canvas_ama_title']);

const TITLE_MAX = 32;
const isTitleKey = (key) => /(?:^|_)(?:title|heading)$|(?:Title|Heading)$/.test(key) || /^(?:section|sec)_/.test(key);
const PLACEHOLDER = '‹x›';

// ── EN strings from the AST ───────────────────────────────────────────────

function unwrap(node) {
	let n = node;
	while (n && (ts.isAsExpression(n) || ts.isSatisfiesExpression?.(n) || ts.isParenthesizedExpression(n) || ts.isTypeAssertionExpression?.(n))) n = n.expression;
	return n;
}

/** The text of a string-ish expression, interpolations as ‹x›; null if not a string. */
function textOf(node) {
	const n = unwrap(node);
	if (!n) return null;
	if (ts.isStringLiteral(n) || ts.isNoSubstitutionTemplateLiteral(n)) return n.text;
	if (ts.isTemplateExpression(n)) return n.head.text + n.templateSpans.map((s) => PLACEHOLDER + s.literal.text).join('');
	if (ts.isBinaryExpression(n) && n.operatorToken.kind === ts.SyntaxKind.PlusToken) {
		const l = textOf(n.left);
		const r = textOf(n.right);
		if (l === null && r === null) return null;
		return (l ?? PLACEHOLDER) + (r ?? PLACEHOLDER);
	}
	if (ts.isArrowFunction(n) || ts.isFunctionExpression(n)) {
		if (n.body && !ts.isBlock(n.body)) return textOf(n.body);
		if (n.body && ts.isBlock(n.body)) {
			const ret = n.body.statements.filter(ts.isReturnStatement);
			if (ret.length === 1 && ret[0].expression) return textOf(ret[0].expression);
		}
		return null;
	}
	if (ts.isConditionalExpression(n)) {
		const a = textOf(n.whenTrue);
		const b = textOf(n.whenFalse);
		return a !== null ? a : b;
	}
	return null;
}

function flatten(obj, sf, prefix, out) {
	for (const p of obj.properties) {
		if (!ts.isPropertyAssignment(p) && !ts.isMethodDeclaration(p)) continue;
		const name = p.name && (ts.isIdentifier(p.name) || ts.isStringLiteral(p.name) || ts.isNumericLiteral(p.name)) ? p.name.text : null;
		if (name === null) continue;
		const key = prefix ? `${prefix}.${name}` : name;
		const line = sf.getLineAndCharacterOfPosition(p.getStart(sf)).line + 1;
		if (ts.isMethodDeclaration(p)) {
			const ret = p.body?.statements.filter(ts.isReturnStatement) ?? [];
			const text = ret.length === 1 && ret[0].expression ? textOf(ret[0].expression) : null;
			if (text !== null) out.push({ key, text, line });
			continue;
		}
		const init = unwrap(p.initializer);
		if (init && ts.isObjectLiteralExpression(init)) flatten(init, sf, key, out);
		else {
			const text = textOf(init);
			if (text !== null) out.push({ key, text, line });
		}
	}
}

/** The EN entries of one pack file: [{key, text, line}] (empty when it has no EN pack). */
function enEntries(file) {
	const src = readFileSync(file, 'utf8');
	const sf = ts.createSourceFile(file, src, ts.ScriptTarget.Latest, true, ts.ScriptKind.TS);
	const decls = new Map();
	const calls = [];
	(function visit(node) {
		if (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name) && node.initializer) decls.set(node.name.text, node.initializer);
		if (ts.isCallExpression(node) && ts.isIdentifier(node.expression) && node.expression.text === 'registerPack') {
			const [code, pack] = node.arguments;
			if (code && ts.isStringLiteral(code) && code.text === 'en' && pack) calls.push(pack);
		}
		ts.forEachChild(node, visit);
	})(sf);
	const objects = [];
	for (const arg of calls) {
		const a = unwrap(arg);
		if (ts.isObjectLiteralExpression(a)) objects.push(a);
		else if (ts.isIdentifier(a) && decls.has(a.text)) {
			const init = unwrap(decls.get(a.text));
			if (init && ts.isObjectLiteralExpression(init)) objects.push(init);
		}
	}
	if (!objects.length && decls.has('en')) {
		const init = unwrap(decls.get('en'));
		if (init && ts.isObjectLiteralExpression(init)) objects.push(init);
	}
	const out = [];
	for (const o of [...new Set(objects)]) flatten(o, sf, '', out);
	return out;
}

// ── rules ───────────────────────────────────────────────────────────────

const shieldsUsed = new Set();

function hitsOf(entry, file) {
	const out = [];
	const { key, text } = entry;
	const sh = CAPS_SHIELDS.get(key);
	const shield = sh && sh.file === file && sh.text === text ? sh : null;
	const top = key.split('.')[0];
	if (isTitleKey(key) && !LONG_PINNED_TITLES.has(top) && text.length > TITLE_MAX) out.push(`title-length (${text.length} > ${TITLE_MAX})`);
	const seps = text.split(' · ').length - 1;
	if (seps > 1) out.push(`separator (${seps} × " · ")`);
	const caps = [];
	for (const m of text.matchAll(/[A-Za-z0-9•]+/g)) {
		const w = m[0];
		if (/[0-9•]/.test(w) || w.length < 2) continue;
		if (w === w.toUpperCase() && !ACRONYMS.has(w)) {
			if (shield && shield.words.includes(w)) shieldsUsed.add(key);
			else caps.push(w);
		}
	}
	if (caps.length) out.push(`all-caps (${[...new Set(caps)].join(' ')})`);
	return out;
}

// ── which packs ─────────────────────────────────────────────────────────

/** A glob (`**`, `*`, `?`) as an anchored RegExp over deck-relative posix paths (design-tokens.mjs's grammar). */
function globRe(glob) {
	let re = '^';
	for (let i = 0; i < glob.length; i++) {
		const c = glob[i];
		if (c === '*') {
			if (glob[i + 1] === '*') {
				i++;
				if (glob[i + 1] === '/') {
					i++;
					re += '(?:.*/)?';
				} else re += '.*';
			} else re += '[^/]*';
		} else if (c === '?') re += '[^/]';
		else re += c.replace(/[.+^${}()|[\]\\]/g, '\\$&');
	}
	return new RegExp(`${re}$`);
}

/** Every deck-relative .ts file (not .d.ts) under `rel` (recursive). */
function tsFilesUnder(rel) {
	const abs = path.join(DECK, rel);
	if (!existsSync(abs)) return [];
	const out = [];
	for (const d of readdirSync(abs, { withFileTypes: true })) {
		const r = rel ? `${rel}/${d.name}` : d.name;
		if (d.isDirectory()) out.push(...tsFilesUnder(r));
		else if (/\.ts$/.test(d.name) && !d.name.endsWith('.d.ts')) out.push(r);
	}
	return out;
}

/**
 * COVERAGE (audit E-S7B F14): in gate mode every `src/lib/i18n/*.ts` that
 * holds an EN pack must be a copy target, so a NEW pack file can never sit
 * silently unlinted. all.json lists the packs by name because
 * tests/design-tokens.mjs (not this WP's file) checks each "copy" entry with
 * existsSync and rejects a glob there; copy-lint itself accepts either form.
 */
const COVERAGE_GLOB = 'src/lib/i18n/*.ts';

/**
 * The "copy" entries of tests/style-lint.targets/*.json: a plain path names
 * one pack file (it must exist and hold an EN pack); a glob (`*`, `?`, `**`)
 * is expanded over the .ts files under its static prefix, so a NEW pack file
 * is covered the day it lands. A glob must match at least one file with an EN
 * pack; matched files without one (e.g. lang-cookie.ts) are listed, not linted.
 */
function targetPacks() {
	const dir = path.join(HERE, 'style-lint.targets');
	const list = [];
	const globbed = new Set();
	if (!existsSync(dir)) return { list, globbed, error: 'tests/style-lint.targets/ is missing' };
	for (const f of readdirSync(dir).filter((x) => x.endsWith('.json')).sort()) {
		let j;
		try {
			j = JSON.parse(readFileSync(path.join(dir, f), 'utf8'));
		} catch (e) {
			return { list, globbed, error: `${f}: ${String(e).slice(0, 120)}` };
		}
		for (const p of j.copy ?? []) {
			if (!/[*?]/.test(p)) {
				list.push(p);
				continue;
			}
			const re = globRe(p);
			const prefix = p.slice(0, p.search(/[*?]/)).replace(/\/[^/]*$/, '');
			const matched = tsFilesUnder(prefix).filter((r) => re.test(r)).sort();
			if (!matched.length) return { list, globbed, error: `${f}: copy glob ${p} matches no file` };
			for (const m of matched) {
				list.push(m);
				globbed.add(m);
			}
		}
	}
	return { list: [...new Set(list)], globbed, error: null };
}

const ALL = process.argv.includes('--all');
let packs;
let globbed = new Set();
if (ALL) {
	const dir = path.join(DECK, 'src/lib/i18n');
	packs = readdirSync(dir)
		.filter((f) => /\.ts$/.test(f) && !f.endsWith('.d.ts'))
		.map((f) => `src/lib/i18n/${f}`)
		.sort();
} else {
	const t = targetPacks();
	if (t.error) {
		console.error(`FAIL copy-lint targets — ${t.error}`);
		process.exit(1);
	}
	packs = t.list;
	globbed = t.globbed;
	const re = globRe(COVERAGE_GLOB);
	const uncovered = tsFilesUnder('src/lib/i18n')
		.filter((r) => re.test(r) && !packs.includes(r))
		.filter((r) => enEntries(path.join(DECK, r)).length > 0);
	if (uncovered.length) {
		console.error(`FAIL copy-lint coverage — EN pack file(s) under ${COVERAGE_GLOB} that no tests/style-lint.targets/*.json "copy" entry names: ${uncovered.join(', ')}`);
		process.exit(1);
	}
}

let hits = 0;
let strings = 0;
const missing = [];
const noPack = [];
for (const p of packs) {
	const file = path.join(DECK, p);
	if (!existsSync(file)) {
		missing.push(p);
		continue;
	}
	const entries = enEntries(file);
	if (!entries.length && !ALL && !globbed.has(p)) missing.push(`${p} (no EN pack found)`);
	if (!entries.length && globbed.has(p)) noPack.push(p);
	for (const e of entries) {
		strings++;
		for (const h of hitsOf(e, p)) {
			hits++;
			console.log(`${p}:${e.line} ${h.split(' ')[0]} ${e.key} — ${h.slice(h.indexOf(' ') + 1)} "${e.text.slice(0, 80)}"`);
		}
	}
}

for (const [key, sh] of CAPS_SHIELDS) {
	console.log(`copy-lint: shield ${shieldsUsed.has(key) ? 'APPLIED' : 'unused '} ${sh.file} ${key} (${sh.words.join(' ')}) — ${sh.why}`);
}

if (noPack.length) console.log(`copy-lint: glob-matched without an EN pack (not linted): ${noPack.join(', ')}`);
if (globbed.size && globbed.size === noPack.length) missing.push('the copy glob(s) matched no file with an EN pack');
if (missing.length) {
	console.error(`FAIL copy-lint: pack file(s) not found or without EN strings — ${missing.join(', ')}`);
	process.exit(1);
}
const scope = ALL ? `every EN pack under src/lib/i18n (${packs.length} files)` : `targets: ${packs.length - noPack.length} pack file(s) — ${packs.filter((p) => !noPack.includes(p)).join(', ') || 'none'}`;
const allowed = `acronym allowlist only; ${shieldsUsed.size} per-key all-caps shield(s) applied (exact text; listed above); ${LONG_PINNED_TITLES.size} long pinned titles allowed`;
if (hits) {
	console.error(`copy-lint: ${hits} hit(s) in ${strings} EN strings (${allowed}) — ${scope}`);
	process.exit(1);
}
console.log(`copy-lint: ok — ${strings} EN strings clean (${allowed}) — ${scope}`);
process.exit(0);
