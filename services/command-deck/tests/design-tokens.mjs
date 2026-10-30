/**
 * Design-token gate (SPEC §2.5, §13.11) — zero browser.
 *
 *   1.  PARITY      tokens.css ↔ tokens.ts: identical key sets and values in
 *                   BOTH themes; command and daylight share ONE key list;
 *                   every pre-redesign key still exists (values change,
 *                   names never do).
 *   1a. SPEC VALUES the SPEC §2.2 command values and the §2.3 new keys in
 *                   both themes; daylight keeps its pre-redesign values for
 *                   existing keys except --v-font-display and
 *                   --v-tracking-status (SPEC §2.1). Any drift is listed.
 *   1b. CONTRAST    WCAG AA 4.5:1 for every text ink on canvas, surface-1
 *                   and surface-2 in both themes (ink-1..3 and the intent and
 *                   AI text inks), the act text on surface-1, the daylight
 *                   CTA, the tooltip, ink on intent fills, map labels
 *                   (composited over white and black).
 *   1c. TYPE FLOOR  every --v-text-* ≥ 12 px (operator), ≥ 13 px (daylight);
 *                   operator base 14 px.
 *   2.  HEX SWEEP   no hex literal outside tokens.css / tokens.ts on every
 *                   surface on the token system (Svelte <style> included).
 *   3.  CONTRACTS   icons.ts (plan X1: the kind maps, the fallbacks, no
 *                   person glyph, path data for every mapped glyph,
 *                   LICENSE-blueprint.txt), packs.ui.ts (EN/HI/MR complete),
 *                   the formatter (IST, one format per column).
 *   4.  STYLE LINT  over the union of tests/style-lint.targets/*.json "style"
 *                   globs: letter-spacing other than 0, text-transform:
 *                   uppercase, backdrop-filter, a font-family not through the
 *                   tokens, the mono face or class="mono" outside
 *                   src/lib/ui/format/, and an active-state background other
 *                   than .is-pressed / .is-selected.
 *   5.  GLYPH LINT  over the "glyph" globs: no kind icon name (a KIND_ICON or
 *                   EVENT_KIND_ICON value) passed as a literal — use
 *                   kindIcon() / eventKindIcon() or a named map.
 *   6.  BOUNDARIES  the R4 import graph, textually (so .svelte is covered):
 *                   design/shell/primitives never import ops/gods-eye;
 *                   src/lib/ui imports nothing from $lib/ops, $lib/gods-eye or
 *                   $lib/workspace and no store; public/comms never import the
 *                   legacy stores; tokens.css and fonts.css are imported once,
 *                   by the root layout.
 *
 * Targets (plan R31/X24): tests/style-lint.targets/<wp>.json =
 *   {"style": [globs], "glyph": [globs], "copy": [pack files]}, all files
 *   unioned; paths relative to services/command-deck; `**`, `*`, `?` globs
 *   (`?deck?` matches the (deck) route group).
 *
 * Usage (from services/command-deck):
 *   node tests/design-tokens.mjs              the gate; exit 1 on any failure
 *   node tests/design-tokens.mjs --uncovered  every .svelte/.css under src/lib and
 *                                             src/routes that no targets file
 *                                             covers, one per line; exit 0
 *   node tests/design-tokens.mjs --all        the style and glyph lints over all of
 *                                             src/lib/** and src/routes/**, every
 *                                             hit as `file:line rule`; exit 1 on
 *                                             any hit (the orchestrator's preview)
 */

import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const DECK = path.resolve(HERE, '..');
const SRC = path.join(DECK, 'src');
const TARGETS_DIR = path.join(HERE, 'style-lint.targets');

const MODE = process.argv.includes('--uncovered') ? 'uncovered' : process.argv.includes('--all') ? 'all' : 'gate';

let failures = 0;
function ok(name, cond, detail = '') {
	if (cond) console.log(`ok   ${name}${detail ? ` — ${detail}` : ''}`);
	else {
		failures++;
		console.error(`FAIL ${name}${detail ? ` — ${detail}` : ''}`);
	}
}

// ── helpers ─────────────────────────────────────────────────────────────

function walk(root) {
	const out = [];
	let entries = [];
	try {
		entries = readdirSync(root);
	} catch {
		return out;
	}
	for (const entry of entries) {
		const p = path.join(root, entry);
		const st = statSync(p);
		if (st.isDirectory()) out.push(...walk(p));
		else out.push(p);
	}
	return out;
}

function walkMaybe(rel) {
	try {
		return walk(path.join(SRC, rel));
	} catch {
		return [];
	}
}

const rel = (f) => path.relative(DECK, f).split(path.sep).join('/');
const norm = (v) => v.replace(/\s+/g, ' ').trim();
const lineOf = (text, index) => {
	let n = 1;
	for (let i = 0; i < index && i < text.length; i++) if (text.charCodeAt(i) === 10) n++;
	return n;
};

/** A glob (`**`, `*`, `?`) as an anchored RegExp over deck-relative posix paths. */
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

// ── 0. targets ──────────────────────────────────────────────────────────

function readTargets() {
	const files = existsSync(TARGETS_DIR) ? readdirSync(TARGETS_DIR).filter((f) => f.endsWith('.json')).sort() : [];
	const union = { style: [], glyph: [], copy: [], sources: files, errors: [] };
	for (const f of files) {
		try {
			const j = JSON.parse(readFileSync(path.join(TARGETS_DIR, f), 'utf8'));
			for (const k of ['style', 'glyph', 'copy']) {
				if (j[k] === undefined) continue;
				if (!Array.isArray(j[k]) || j[k].some((g) => typeof g !== 'string')) {
					union.errors.push(`${f}: "${k}" must be an array of strings`);
					continue;
				}
				for (const g of j[k]) union[k].push({ glob: g, from: f });
			}
		} catch (e) {
			union.errors.push(`${f}: ${String(e).slice(0, 120)}`);
		}
	}
	return union;
}

const TARGETS = readTargets();
const ALL_FILES = [...walk(path.join(SRC, 'lib')), ...walk(path.join(SRC, 'routes'))].map(rel).sort();
const matchAny = (file, list) => list.some((t) => globRe(t.glob).test(file));

if (MODE === 'uncovered') {
	const covered = [...TARGETS.style, ...TARGETS.glyph];
	for (const f of ALL_FILES) {
		if (!/\.(svelte|css)$/.test(f)) continue;
		if (!matchAny(f, covered)) console.log(f);
	}
	process.exit(0);
}

// ── source views (comments blanked, line numbers kept) ───────────────────

const blank = (s) => s.replace(/[^\n]/g, ' ');

/** Blank // and /* *\/ comments in JS/TS, keeping strings and template literals. */
function stripJsComments(src) {
	let out = '';
	let i = 0;
	let mode = 'code';
	let quote = '';
	const tplDepth = [];
	while (i < src.length) {
		const c = src[i];
		const n = src[i + 1];
		if (mode === 'code') {
			if (c === '/' && n === '/') {
				const end = src.indexOf('\n', i);
				const stop = end < 0 ? src.length : end;
				out += blank(src.slice(i, stop));
				i = stop;
				continue;
			}
			if (c === '/' && n === '*') {
				const end = src.indexOf('*/', i + 2);
				const stop = end < 0 ? src.length : end + 2;
				out += blank(src.slice(i, stop));
				i = stop;
				continue;
			}
			if (c === "'" || c === '"' || c === '`') {
				mode = 'str';
				quote = c;
				out += c;
				i++;
				continue;
			}
			if (c === '}' && tplDepth.length && tplDepth[tplDepth.length - 1] === 0) {
				tplDepth.pop();
				mode = 'str';
				quote = '`';
				out += c;
				i++;
				continue;
			}
			if (c === '{' && tplDepth.length) tplDepth[tplDepth.length - 1]++;
			if (c === '}' && tplDepth.length) tplDepth[tplDepth.length - 1]--;
			out += c;
			i++;
			continue;
		}
		// inside a string
		if (c === '\\') {
			out += src.slice(i, i + 2);
			i += 2;
			continue;
		}
		if (quote === '`' && c === '$' && n === '{') {
			tplDepth.push(0);
			mode = 'code';
			out += '${';
			i += 2;
			continue;
		}
		if (c === quote || (c === '\n' && quote !== '`')) mode = 'code';
		out += c;
		i++;
	}
	return out;
}

const stripCssComments = (css) => css.replace(/\/\*[\s\S]*?\*\//g, (m) => blank(m));

/** css / script / markup views of one file, each the same length as the source. */
function views(file, src) {
	if (file.endsWith('.css')) return { css: stripCssComments(src), script: '', markup: '' };
	if (/\.(ts|js|mjs)$/.test(file)) return { css: '', script: stripJsComments(src), markup: '' };
	if (!file.endsWith('.svelte')) return { css: '', script: '', markup: '' };
	let css = blank(src);
	let script = blank(src);
	let markup = src;
	const take = (re, into) => {
		for (const m of src.matchAll(re)) {
			const inner = m[2];
			const start = m.index + m[0].indexOf(inner, m[1].length);
			const piece = into === 'css' ? stripCssComments(inner) : stripJsComments(inner);
			if (into === 'css') css = css.slice(0, start) + piece + css.slice(start + inner.length);
			else script = script.slice(0, start) + piece + script.slice(start + inner.length);
			markup = markup.slice(0, m.index) + blank(m[0]) + markup.slice(m.index + m[0].length);
		}
	};
	take(/(<style\b[^>]*>)([\s\S]*?)<\/style>/g, 'css');
	take(/(<script\b[^>]*>)([\s\S]*?)<\/script>/g, 'script');
	markup = markup.replace(/<!--[\s\S]*?-->/g, (m) => blank(m));
	return { css, script, markup };
}

// ── style rules ───────────────────────────────────────────────────────────

const FORMAT_DIR = 'src/lib/ui/format/';
const FONT_OK = /^(?:var\(--v-font-(?:ui|display)\)|inherit|initial|unset|revert)(?:\s*!important)?$/;
const FONT_MONO = /^var\(--v-font-mono\)(?:\s*!important)?$/;

function fontValueOk(value, file) {
	const v = value.trim().replace(/^['"]|['"]$/g, '').trim();
	if (FONT_OK.test(v)) return true;
	if (FONT_MONO.test(v)) return file.startsWith(FORMAT_DIR);
	return false;
}

function fontShorthandOk(value, file) {
	const v = value.trim();
	if (/^(inherit|initial|unset|revert)(\s*!important)?$/.test(v)) return true;
	if (/var\(--v-font-(ui|display)\)/.test(v)) return true;
	if (/var\(--v-font-mono\)/.test(v)) return file.startsWith(FORMAT_DIR);
	return false;
}

/** Declaration rules over any text (CSS, style attributes, CSS in strings). */
function declarationHits(text, file, hits, { skipFontFace = false } = {}) {
	let t = text;
	if (skipFontFace) t = t.replace(/@font-face\s*\{[^}]*\}/g, (m) => blank(m));
	for (const m of t.matchAll(/(?<![\w-])letter-spacing\s*:\s*([^;}"'`\n]+)/gi)) {
		const v = m[1].trim();
		if (!/^(0(px|em|rem)?|normal)(\s*!important)?$/i.test(v)) hits.push([lineOf(t, m.index), 'letter-spacing']);
	}
	for (const m of t.matchAll(/(?<![\w-])text-transform\s*:\s*uppercase/gi)) hits.push([lineOf(t, m.index), 'uppercase']);
	for (const m of t.matchAll(/(?<![\w-])(?:-webkit-)?backdrop-filter\s*:\s*([^;}"'`\n]+)/gi)) {
		// the ONE allowed blur: the V3 map's glass token (V3-P4 review item 6; contrast holds without it, glass.ts)
		if (!/^none(\s*!important)?$/i.test(m[1].trim()) && m[1].trim() !== 'var(--v3-glass-blur)') hits.push([lineOf(t, m.index), 'backdrop-filter']);
	}
	for (const m of t.matchAll(/(?<![\w-])font-family\s*:\s*([^;}"`\n]+)/gi)) {
		if (!fontValueOk(m[1], file)) hits.push([lineOf(t, m.index), 'font-family']);
	}
	for (const m of t.matchAll(/(?<![\w-])font\s*:\s*([^;}"`\n]+)/gi)) {
		if (!fontShorthandOk(m[1], file)) hits.push([lineOf(t, m.index), 'font-family']);
	}
}

/** The innermost declaration blocks of a stylesheet: {selector, body, start}. */
function cssBlocks(css) {
	const blocks = [];
	const stack = [];
	let last = 0;
	for (let i = 0; i < css.length; i++) {
		const c = css[i];
		if (c === '{') {
			stack.push({ prelude: css.slice(last, i), start: i + 1, nested: false });
			if (stack.length > 1) stack[stack.length - 2].nested = true;
			last = i + 1;
		} else if (c === '}') {
			const top = stack.pop();
			if (top && !top.nested) blocks.push({ selector: top.prelude.replace(/[^;{}]*;/g, ' ').trim(), body: css.slice(top.start, i), start: top.start });
			last = i + 1;
		} else if (c === ';' && stack.length === 0) last = i + 1;
	}
	return blocks;
}

const ACTIVE_MARKER =
	/\.(?:active|is-active|selected|on|pressed|current|checked)(?![\w-])|\[\s*aria-(?:pressed|selected|current|checked)\b|\[\s*data-(?:active|selected|pressed|current)\b|\[\s*data-state\s*=\s*["']?(?:active|on|selected|pressed)/i;

function activeBackgroundHits(css, hits) {
	for (const b of cssBlocks(css)) {
		if (b.selector.startsWith('@')) continue;
		// a marker inside :not(…) selects the INACTIVE state: not an active background
		const sel = b.selector.replace(/:not\((?:[^()]|\([^()]*\))*\)/g, '');
		if (/\.is-(?:pressed|selected)(?![\w-])/.test(sel)) continue;
		if (!ACTIVE_MARKER.test(sel)) continue;
		const m = /(?<![\w-])background(?:-color|-image)?\s*:/i.exec(b.body);
		if (m) hits.push([lineOf(css, b.start + m.index), 'active-background']);
	}
}

function monoClassHits(text, file, hits) {
	if (file.startsWith(FORMAT_DIR)) return;
	const res = [
		/\bclass\s*=\s*["'][^"']*\bmono\b[^"']*["']/g,
		/\bclass\s*=\s*\{[^}]*["'`][^"'`]*\bmono\b[^"'`]*["'`][^}]*\}/g,
		/\bclass:mono\b/g,
		/\bclass=\\?["'][^"'\\]*\bmono\b/g
	];
	const seen = new Set();
	for (const re of res) {
		for (const m of text.matchAll(re)) {
			const line = lineOf(text, m.index);
			if (seen.has(line)) continue;
			seen.add(line);
			hits.push([line, 'mono-class']);
		}
	}
}

function svgFontAttrHits(markup, file, hits) {
	for (const m of markup.matchAll(/\bfont-family\s*=\s*["']([^"']+)["']/g)) {
		if (!fontValueOk(m[1], file)) hits.push([lineOf(markup, m.index), 'font-family']);
	}
	for (const m of markup.matchAll(/\bstyle:(letter-spacing|text-transform|backdrop-filter|font-family)\s*=\s*(?:"([^"]*)"|'([^']*)'|\{([^}]*)\})/g)) {
		const prop = m[1];
		const val = (m[2] ?? m[3] ?? m[4] ?? '').replace(/^['"`]|['"`]$/g, '').trim();
		const line = lineOf(markup, m.index);
		if (prop === 'letter-spacing' && !/^(0(px|em|rem)?|normal)$/i.test(val)) hits.push([line, 'letter-spacing']);
		if (prop === 'text-transform' && /uppercase/i.test(val)) hits.push([line, 'uppercase']);
		if (prop === 'backdrop-filter' && !/^none$/i.test(val)) hits.push([line, 'backdrop-filter']);
		if (prop === 'font-family' && !fontValueOk(val, file)) hits.push([line, 'font-family']);
	}
}

function styleLint(file, src) {
	const v = views(file, src);
	const hits = [];
	if (v.css) {
		declarationHits(v.css, file, hits, { skipFontFace: true });
		activeBackgroundHits(v.css, hits);
	}
	if (v.markup) {
		declarationHits(v.markup, file, hits);
		monoClassHits(v.markup, file, hits);
		svgFontAttrHits(v.markup, file, hits);
	}
	if (v.script) {
		declarationHits(v.script, file, hits);
		monoClassHits(v.script, file, hits);
	}
	return hits;
}

// ── icons (bundled once: the glyph lint and the contracts read the real maps) ─

const esbuild = await import(pathToFileURL(path.join(DECK, 'node_modules/esbuild/lib/main.js')).href);

async function bundle(entries) {
	const contents = entries.map(([name, file]) => `export * as ${name} from ${JSON.stringify(path.join(DECK, file))};`).join('\n');
	const res = await esbuild.build({
		stdin: { contents, resolveDir: DECK, loader: 'ts', sourcefile: 'design-tokens.entry.ts' },
		absWorkingDir: DECK,
		alias: { $lib: './src/lib' },
		bundle: true,
		platform: 'node',
		format: 'esm',
		write: false,
		logLevel: 'silent'
	});
	const code = res.outputFiles[0].text;
	return import(`data:text/javascript;base64,${Buffer.from(code).toString('base64')}`);
}

const MOD = await bundle([
	['icons', 'src/lib/design/icons.ts'],
	['tokens', 'src/lib/design/tokens.ts'],
	['ui', 'src/lib/i18n/packs.ui.ts'],
	['fmt', 'src/lib/ui/format/format.ts']
]);
const { icons } = MOD;
const KIND_NAMES = new Set([...Object.values(icons.KIND_ICON), ...Object.values(icons.EVENT_KIND_ICON)]);
const ICON_FILE = 'src/lib/design/icons.ts';

function glyphLint(file, src) {
	if (file === ICON_FILE) return [];
	const v = views(file, src);
	const hits = [];
	const names = [...KIND_NAMES].map((n) => n.replace(/[-]/g, '\\-')).join('|');
	const attr = new RegExp(`\\b(?:icon|rightIcon|leftIcon|glyph)\\s*=\\s*(?:\\{\\s*)?["'\`](${names})["'\`]`, 'g');
	const prop = new RegExp(`\\b(?:icon|rightIcon|leftIcon|glyph)\\s*:\\s*["'\`](${names})["'\`]`, 'g');
	const iconTag = /<Icon\b[^>]*>/g;
	const nameAttr = new RegExp(`\\bname\\s*=\\s*(?:\\{\\s*)?["'\`](${names})["'\`]`);
	for (const text of [v.markup, v.script]) {
		if (!text) continue;
		for (const m of text.matchAll(attr)) hits.push([lineOf(text, m.index), 'kind-icon-literal']);
		for (const m of text.matchAll(prop)) hits.push([lineOf(text, m.index), 'kind-icon-literal']);
		for (const m of text.matchAll(iconTag)) {
			const n = nameAttr.exec(m[0]);
			if (n) hits.push([lineOf(text, m.index + n.index), 'kind-icon-literal']);
		}
	}
	return hits;
}

const LINTABLE = /\.(svelte|css|ts|js|mjs)$/;

function lintFiles(files, kinds) {
	const out = [];
	for (const f of files) {
		if (!LINTABLE.test(f) || f.endsWith('.d.ts')) continue;
		const src = readFileSync(path.join(DECK, f), 'utf8');
		const hits = [];
		if (kinds.includes('style')) hits.push(...styleLint(f, src));
		if (kinds.includes('glyph')) hits.push(...glyphLint(f, src));
		const seen = new Set();
		for (const [line, rule] of hits.sort((a, b) => a[0] - b[0])) {
			const key = `${line}:${rule}`;
			if (seen.has(key)) continue;
			seen.add(key);
			out.push(`${f}:${line} ${rule}`);
		}
	}
	return out;
}

if (MODE === 'all') {
	const hits = lintFiles(ALL_FILES, ['style', 'glyph']);
	for (const h of hits) console.log(h);
	const files = new Set(hits.map((h) => h.split(':')[0]));
	console.error(`design-tokens --all: ${hits.length} hit(s) in ${files.size} file(s) over src/lib and src/routes`);
	process.exit(hits.length ? 1 : 0);
}

// ── 1. PARITY: tokens.css ↔ tokens.ts ──────────────────────────────────

const cssText = readFileSync(path.join(SRC, 'lib/design/tokens.css'), 'utf8');
const tsText = readFileSync(path.join(SRC, 'lib/design/tokens.ts'), 'utf8');

/** Extract `--name: value;` pairs from one flat CSS block (comments removed). */
function cssVars(blockText) {
	const map = new Map();
	const re = /(--v-[a-z0-9-]+)\s*:\s*([^;]+);/g;
	let m;
	const text = blockText.replace(/\/\*[\s\S]*?\*\//g, '');
	while ((m = re.exec(text))) {
		if (map.has(m[1])) throw new Error(`duplicate ${m[1]} in one block`);
		map.set(m[1], norm(m[2]));
	}
	return map;
}

function sliceBlock(text, startMarker) {
	const start = text.indexOf(startMarker);
	if (start < 0) throw new Error(`marker not found: ${startMarker}`);
	const open = text.indexOf('{', start);
	const end = text.indexOf('\n}', open);
	return text.slice(open + 1, end);
}

/** The object literal after `marker` up to its matching brace. */
function sliceObject(text, marker) {
	const start = text.indexOf(marker);
	if (start < 0) return null;
	const open = text.indexOf('{', start);
	let depth = 0;
	for (let i = open; i < text.length; i++) {
		if (text[i] === '{') depth++;
		else if (text[i] === '}' && --depth === 0) return text.slice(open + 1, i);
	}
	return null;
}

function tsVars(sectionText) {
	const map = new Map();
	const re = /'(--v-[a-z0-9-]+)':\s*(['"])((?:\\.|(?!\2).)*)\2/g;
	let m;
	while ((m = re.exec(sectionText))) {
		if (map.has(m[1])) throw new Error(`duplicate ${m[1]} in ts section`);
		map.set(m[1], norm(m[3]));
	}
	return map;
}

const cssCommand = cssVars(sliceBlock(cssText, ":root,\n[data-theme='command']"));
const cssDaylight = cssVars(sliceBlock(cssText, "[data-theme='daylight']"));
const tsCommandText = sliceObject(tsText, 'command: {');
const tsDaylightText = sliceObject(tsText, 'daylight: {');
if (!tsCommandText || !tsDaylightText) {
	ok('tokens.ts sections found', false, 'expected TOKENS.command and TOKENS.daylight');
	process.exit(1);
}
const tsCommand = tsVars(tsCommandText);
const tsDaylight = tsVars(tsDaylightText);

const sameKeys = (a, b) => a.size === b.size && [...a.keys()].every((k) => b.has(k));
const keyDiff = (a, b) => [...a.keys()].filter((k) => !b.has(k)).concat([...b.keys()].filter((k) => !a.has(k)));

ok('parity: css command keys === ts command keys', sameKeys(cssCommand, tsCommand), `${cssCommand.size} vars ${keyDiff(cssCommand, tsCommand).join(' ')}`);
ok('parity: css daylight keys === ts daylight keys', sameKeys(cssDaylight, tsDaylight), `${cssDaylight.size} vars ${keyDiff(cssDaylight, tsDaylight).join(' ')}`);
ok('parity: command and daylight share ONE variable list', sameKeys(cssCommand, cssDaylight), keyDiff(cssCommand, cssDaylight).join(' ') || 'both themes define the same names');

const valueDiff = (a, b, label) => {
	const bad = [...a.keys()].filter((k) => b.has(k) && a.get(k) !== b.get(k));
	ok(`parity: ${label} values match`, bad.length === 0, bad.map((k) => `${k} css=${a.get(k)} ts=${b.get(k)}`).join(' | '));
};
valueDiff(cssCommand, tsCommand, 'command');
valueDiff(cssDaylight, tsDaylight, 'daylight');

// every pre-redesign key keeps its name (SPEC §2.1)
const LEGACY_KEYS = [
	'--v-canvas', '--v-surface-1', '--v-surface-2', '--v-surface-3', '--v-surface-sink', '--v-paper', '--v-line-1',
	'--v-line-2', '--v-line-select', '--v-ink-1', '--v-ink-2', '--v-ink-3', '--v-ink-4', '--v-act', '--v-act-2',
	'--v-act-focus', '--v-act-veil', '--v-act-text', '--v-band-green', '--v-band-amber', '--v-band-red',
	'--v-band-black-fill', '--v-band-black-hairline', '--v-band-veil', '--v-data', '--v-tool', '--v-glass-bg',
	'--v-glass-border', '--v-glass-blur', '--v-glow-act', '--v-flow-light', '--v-veil', '--v-font-ui',
	'--v-font-display', '--v-font-mono', '--v-text-2xs', '--v-text-xs', '--v-text-sm', '--v-text-base', '--v-text-md',
	'--v-text-lg', '--v-text-xl', '--v-weight-status', '--v-tracking-status', '--v-space-1', '--v-space-2',
	'--v-space-3', '--v-space-4', '--v-space-5', '--v-space-6', '--v-space-7', '--v-space-8', '--v-ctl-sm',
	'--v-ctl-md', '--v-ctl-lg', '--v-ctl-touch', '--v-radius-chip', '--v-radius-btn', '--v-radius-panel',
	'--v-radius-modal', '--v-radius-pill', '--v-pad-panel', '--v-gap-panel', '--v-ease', '--v-dur-out', '--v-dur-in',
	'--v-dur-wipe', '--v-dur-trace', '--v-dur-comet', '--v-dur-stagger', '--v-dur-pulse', '--v-dur-lift',
	'--v-dur-breathe', '--v-dur-sweep'
];
const lost = LEGACY_KEYS.filter((k) => !cssCommand.has(k) || !cssDaylight.has(k));
ok('names: every pre-redesign --v-* key still exists in both themes', lost.length === 0, lost.join(' ') || `${LEGACY_KEYS.length} keys kept`);

// ── 1a. SPEC VALUES (§2.2, §2.3) ─────────────────────────────────────────

const cmp = (v) => String(v ?? '').toLowerCase().replace(/\s+/g, '');

/** SPEC §2.2: existing keys, new command values (V3 re-points canvas, surfaces 1-3, inks 1-3, act, primary, ai and the map's decision / alert / route — V3-SPEC §4.2; the grounds and inks are neutral black / grey, AI and tool are the accent blue). */
const SPEC_COMMAND = {
	'--v-canvas': '#000000', '--v-surface-1': '#111111', '--v-surface-2': '#1A1A1A', '--v-surface-3': '#242424',
	'--v-surface-sink': '#0A0A0A', '--v-paper': '#242424', '--v-line-1': 'rgba(255,255,255,0.1)',
	'--v-line-2': 'rgba(255,255,255,0.2)', '--v-line-select': 'rgba(138,187,255,0.752)', '--v-ink-1': '#FFFFFF',
	'--v-ink-2': '#CBCBCB', '--v-ink-3': '#A6A6A6', '--v-ink-4': '#6B6B6B', '--v-act': '#FF9F43', '--v-act-2': '#C87619',
	'--v-act-focus': 'rgba(138,187,255,0.752)', '--v-act-veil': 'rgba(200,118,25,0.2)', '--v-act-text': '#FBB360',
	// 2026-10-29 (look): the amber band re-pointed from gold #F0B726 to the console's orange-amber (V3 meaning palette)
	'--v-band-green': '#32A467', '--v-band-amber': '#FFB257', '--v-band-red': '#E76A6E',
	'--v-band-black-fill': 'rgba(17,17,17,0.85)', '--v-band-black-hairline': '#E76A6E', '--v-data': '#4C90F0',
	'--v-tool': '#5B91F5', '--v-glass-bg': '#242424', '--v-glass-border': 'rgba(255,255,255,0.2)',
	'--v-glass-blur': '0px', '--v-glow-act': 'transparent', '--v-flow-light': '#C5CBD3', '--v-text-2xs': '12px',
	'--v-text-xs': '12px', '--v-text-sm': '12px', '--v-text-base': '14px', '--v-text-md': '16px', '--v-text-lg': '18px',
	'--v-text-xl': '22px', '--v-tracking-status': '0', '--v-ctl-sm': '24px', '--v-ctl-md': '30px', '--v-ctl-lg': '40px',
	'--v-ctl-touch': '44px', '--v-radius-chip': '4px', '--v-radius-btn': '4px', '--v-radius-panel': '4px',
	'--v-radius-modal': '4px', '--v-radius-pill': '999px', '--v-ease': 'cubic-bezier(0.4,1,0.75,0.9)',
	'--v-dur-out': '100ms', '--v-dur-in': '200ms', '--v-dur-stagger': '0ms', '--v-dur-pulse': '0ms',
	'--v-dur-lift': '0ms', '--v-dur-breathe': '0ms', '--v-dur-sweep': '0ms'
};

/** SPEC §2.3: new keys, [command, daylight]; null = any value (the SPEC names a family, not a value). */
const SPEC_NEW = {
	'--v-surface-4': ['#3D3D3D', '#DCE0E5'],
	'--v-hover': [null, null], '--v-row-hover': [null, null], '--v-minimal-hover': [null, null], '--v-minimal-active': [null, null],
	'--v-line-strong': ['rgba(255,255,255,0.3)', null], '--v-popover-line': ['#5E6064', null],
	'--v-focus': ['rgba(138,187,255,0.752)', null], '--v-ink-disabled': ['rgba(175,175,175,0.6)', 'rgba(95,107,124,0.6)'],
	'--v-primary': ['#276EF1', '#2D72D2'], '--v-primary-hover': ['#1E54B7', '#215DB0'], '--v-primary-active': ['#174291', '#184A90'],
	'--v-primary-text': ['#7FA8F7', '#215DB0'], '--v-primary-veil': ['rgba(39,110,241,0.2)', 'rgba(45,114,210,0.1)'],
	'--v-success': [null, null], '--v-success-text': ['#72CA9B', null], '--v-success-veil': [null, null],
	'--v-warning': [null, null], '--v-warning-text': ['#FBB360', null], '--v-warning-veil': [null, null],
	'--v-danger': [null, null], '--v-danger-text': ['#FA999C', null], '--v-danger-veil': [null, null],
	'--v-neutral-veil': ['rgba(150,150,150,0.15)', 'rgba(143,153,168,0.15)'],
	'--v-ai': ['#5B91F5', '#1E54B7'], '--v-ai-text': ['#8DB4F9', '#1E54B7'], '--v-ai-veil': ['rgba(91,145,245,0.2)', 'rgba(39,110,241,0.1)'],
	'--v-elev-0': [null, null], '--v-elev-1': [null, null], '--v-elev-2': [null, null], '--v-elev-3': [null, null], '--v-elev-4': [null, null],
	'--v-map-select': ['#FFFFFF', '#000000'], '--v-map-decision': ['#FF9F43', '#C87619'], '--v-map-alert': ['#FF5C61', '#CD4246'],
	'--v-map-route': ['#2DD4BF', '#00A396'], '--v-map-event': ['#5B91F5', '#276EF1'], '--v-map-marker': ['#C5CBD3', '#5F6B7C'],
	'--v-map-marker-fill': ['rgba(17,17,17,0.88)', 'rgba(255,255,255,0.9)'], '--v-map-casing': ['rgba(17,17,17,0.8)', 'rgba(255,255,255,0.85)'],
	'--v-map-label-bg': ['rgba(17,17,17,0.86)', 'rgba(255,255,255,0.9)'], '--v-map-label-ink': ['#F6F7F9', '#1C2127'],
	'--v-flow-1': ['#C4C4C4', '#238551'], '--v-flow-2': ['#D6D6D6', '#8EB125'], '--v-flow-3': ['#E6E6E6', '#D1980B'],
	'--v-flow-4': ['#F3F3F3', '#C87619'], '--v-flow-5': ['#FFFFFF', '#CD4246'],
	'--v-flow-width-1': ['3px', '3px'], '--v-flow-width-2': ['3.5px', '3.5px'], '--v-flow-width-3': ['4px', '4px'],
	'--v-flow-width-4': ['5px', '5px'], '--v-flow-width-5': ['6px', '6px'],
	'--v-z-content': [null, null], '--v-z-overlay': [null, null], '--v-z-dialog': [null, null], '--v-z-toast': [null, null]
};

/** SPEC §2.1: daylight keeps its pre-redesign values, except these two. */
const DAYLIGHT_KEPT = {
	'--v-canvas': '#edeae3', '--v-surface-1': '#ffffff', '--v-surface-2': '#f6f3ee', '--v-surface-3': '#fcfbf8',
	'--v-surface-sink': '#e5e1d8', '--v-paper': '#faf9f7', '--v-line-1': 'rgba(26, 31, 46, 0.12)',
	'--v-line-2': 'rgba(26, 31, 46, 0.2)', '--v-line-select': 'rgba(194, 65, 12, 0.35)', '--v-ink-1': '#1a1f2e',
	'--v-ink-2': '#4a5468', '--v-ink-3': '#5b6478', '--v-ink-4': '#98a0b3', '--v-act': '#ea580c', '--v-act-2': '#c2410c',
	'--v-act-focus': '#c2410c', '--v-act-veil': 'rgba(234, 88, 12, 0.1)', '--v-act-text': '#c2410c',
	'--v-band-green': '#2f9e6f', '--v-band-amber': '#b27a1e', '--v-band-red': '#c24444',
	'--v-band-black-fill': 'rgba(26, 31, 46, 0.4)', '--v-band-black-hairline': '#c24444',
	'--v-band-veil': 'rgba(178, 122, 30, 0.12)', '--v-data': '#2e6fae', '--v-tool': '#1e54b7',
	'--v-glass-bg': 'rgba(255, 255, 255, 0.92)', '--v-glass-border': 'rgba(26, 31, 46, 0.18)', '--v-glass-blur': '10px',
	'--v-glow-act': 'rgba(194, 65, 12, 0.16)', '--v-flow-light': '#5f8f2a', '--v-veil': 'rgba(26, 31, 46, 0.08)',
	'--v-font-ui': "Inter, 'Noto Sans', 'Noto Sans Devanagari', system-ui, sans-serif",
	'--v-font-mono': "'JetBrains Mono', 'Noto Sans Mono', ui-monospace, monospace", '--v-text-2xs': '13px',
	'--v-text-xs': '13px', '--v-text-sm': '14px', '--v-text-base': '16px', '--v-text-md': '16px', '--v-text-lg': '20px',
	'--v-text-xl': '28px', '--v-weight-status': '600', '--v-space-1': '4px', '--v-space-2': '8px', '--v-space-3': '12px',
	'--v-space-4': '16px', '--v-space-5': '20px', '--v-space-6': '24px', '--v-space-7': '32px', '--v-space-8': '40px',
	'--v-ctl-sm': '24px', '--v-ctl-md': '28px', '--v-ctl-lg': '32px', '--v-ctl-touch': '44px', '--v-radius-chip': '4px',
	'--v-radius-btn': '6px', '--v-radius-panel': '10px', '--v-radius-modal': '14px', '--v-radius-pill': '999px',
	'--v-pad-panel': '16px', '--v-gap-panel': '12px', '--v-ease': 'cubic-bezier(0.2, 0, 0, 1)', '--v-dur-out': '150ms',
	'--v-dur-in': '300ms', '--v-dur-wipe': '600ms', '--v-dur-trace': '1200ms', '--v-dur-comet': '300ms',
	'--v-dur-stagger': '120ms', '--v-dur-pulse': '200ms', '--v-dur-lift': '2s', '--v-dur-breathe': '2s', '--v-dur-sweep': '3.5s'
};

{
	const drift = [];
	for (const [k, v] of Object.entries(SPEC_COMMAND)) if (cmp(cssCommand.get(k)) !== cmp(v)) drift.push(`command ${k}=${cssCommand.get(k)} (SPEC ${v})`);
	if (cssCommand.get('--v-font-display') !== cssCommand.get('--v-font-ui')) drift.push('command --v-font-display ≠ --v-font-ui');
	if (/\boutfit\b/i.test(cssCommand.get('--v-font-ui') ?? '')) drift.push('command --v-font-ui names Outfit');
	for (const [k, [c, d]] of Object.entries(SPEC_NEW)) {
		if (!cssCommand.has(k) || !cssDaylight.has(k)) drift.push(`${k} missing`);
		if (c !== null && cmp(cssCommand.get(k)) !== cmp(c)) drift.push(`command ${k}=${cssCommand.get(k)} (SPEC ${c})`);
		if (d !== null && cmp(cssDaylight.get(k)) !== cmp(d)) drift.push(`daylight ${k}=${cssDaylight.get(k)} (SPEC ${d})`);
	}
	for (const [k, v] of Object.entries(DAYLIGHT_KEPT)) if (cmp(cssDaylight.get(k)) !== cmp(v)) drift.push(`daylight ${k}=${cssDaylight.get(k)} (kept value ${v})`);
	if (cssDaylight.get('--v-font-display') !== cssDaylight.get('--v-font-ui')) drift.push('daylight --v-font-display ≠ --v-font-ui');
	if (cmp(cssDaylight.get('--v-tracking-status')) !== '0') drift.push('daylight --v-tracking-status ≠ 0');
	const wsz = [...cssCommand.keys()].filter((k) => /^--v-(ws|z)-/.test(k));
	if (!wsz.some((k) => k.startsWith('--v-ws-')) || !wsz.some((k) => k.startsWith('--v-z-'))) drift.push('--v-ws-* / --v-z-* keys missing');
	ok('spec values: §2.2 command, §2.3 new keys (both themes), §2.1 daylight kept', drift.length === 0, drift.join(' | ') || `${Object.keys(SPEC_COMMAND).length} command + ${Object.keys(SPEC_NEW).length} new + ${Object.keys(DAYLIGHT_KEPT).length} daylight values as specified`);
}

// the reduced-motion block keeps its shape (design-smoke reads wipe and breathe)
{
	const rm = /@media\s*\(prefers-reduced-motion:\s*reduce\)\s*\{([\s\S]*?)\n\}/.exec(cssText)?.[1] ?? '';
	const has = (k, v) => new RegExp(`${k}\\s*:\\s*${v}\\s*;`).test(rm);
	ok('reduced motion: one block calms both themes (wipe 64ms, breathe 0ms)', has('--v-dur-wipe', '64ms') && has('--v-dur-breathe', '0ms') && /\[data-theme='daylight'\]/.test(rm), rm ? 'block present' : 'block missing');
}

// ── 1b. CONTRAST (WCAG relative luminance) ──────────────────────────────

function rgbOf(value) {
	const v = (value ?? '').trim();
	let m = /^#([0-9a-f]{6})$/i.exec(v);
	if (m) return { rgb: [0, 2, 4].map((i) => parseInt(m[1].slice(i, i + 2), 16)), a: 1 };
	m = /^rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*([\d.]+)\s*)?\)$/i.exec(v);
	if (m) return { rgb: [Number(m[1]), Number(m[2]), Number(m[3])], a: m[4] === undefined ? 1 : Number(m[4]) };
	return null;
}

const over = (fg, bg) => fg.rgb.map((c, i) => c * fg.a + bg[i] * (1 - fg.a));

function luminance(rgb) {
	const lin = rgb.map((c) => c / 255).map((v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4));
	return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2];
}

/** Contrast of a text colour on a background; an rgba background is composited over `under`. */
function contrast(fgValue, bgValue, under = [255, 255, 255]) {
	const fg = rgbOf(fgValue);
	const bg = rgbOf(bgValue);
	if (!fg || !bg) return null;
	const bgRgb = bg.a < 1 ? over(bg, under) : bg.rgb;
	const fgRgb = fg.a < 1 ? over(fg, bgRgb) : fg.rgb;
	const la = luminance(fgRgb);
	const lb = luminance(bgRgb);
	return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05);
}

const AA = 4.5;
for (const [theme, vars] of [
	['command', cssCommand],
	['daylight', cssDaylight]
]) {
	const fails = [];
	const need = (fg, bg, label = `${fg} on ${bg}`, under) => {
		const r = contrast(vars.get(fg), vars.get(bg), under);
		if (r == null || r < AA) fails.push(`${label} = ${r == null ? 'n/a' : r.toFixed(2)}`);
	};
	const inks = ['--v-ink-1', '--v-ink-2', '--v-ink-3', '--v-primary-text', '--v-success-text', '--v-warning-text', '--v-danger-text', '--v-ai-text'];
	for (const ink of inks) for (const bg of ['--v-canvas', '--v-surface-1', '--v-surface-2']) need(ink, bg);
	need('--v-act-text', '--v-surface-1');
	need('--v-tooltip-ink', '--v-tooltip-bg');
	for (const fill of ['--v-primary', '--v-success', '--v-danger']) need('--v-on-fill', fill);
	need('--v-canvas', '--v-warning-text', 'canvas ink on the warning fill');
	need('--v-map-label-ink', '--v-map-label-bg', 'map label over white', [255, 255, 255]);
	need('--v-map-label-ink', '--v-map-label-bg', 'map label over black', [0, 0, 0]);
	ok(`contrast: ${theme} text inks ≥ ${AA}:1 (inks, intent and AI text, tooltip, fills, map labels)`, fails.length === 0, fails.join(' | ') || 'AA');
}
const cta = contrast(cssDaylight.get('--v-act-2'), cssDaylight.get('--v-paper'));
ok('contrast: daylight CTA fill (act-2) carries paper text ≥ 4.5:1', cta != null && cta >= AA, cta?.toFixed(2) ?? 'n/a');

// ── 1c. TYPE FLOOR ──────────────────────────────────────────────────────

const px = (v) => (v && /^\d+(\.\d+)?px$/.test(v) ? Number.parseFloat(v) : NaN);
{
	const floorFails = [];
	for (const k of [...cssCommand.keys()].filter((k) => k.startsWith('--v-text-'))) {
		if (!(px(cssCommand.get(k)) >= 12)) floorFails.push(`command ${k}=${cssCommand.get(k)}`);
		if (!(px(cssDaylight.get(k)) >= 13)) floorFails.push(`daylight ${k}=${cssDaylight.get(k)}`);
	}
	if (cssCommand.get('--v-text-base') !== '14px') floorFails.push(`command --v-text-base=${cssCommand.get('--v-text-base')} (14px)`);
	ok('type floor: operator text ≥ 12 px (base 14), public text ≥ 13 px', floorFails.length === 0, floorFails.join(' | ') || 'floors hold');
}

// The token floor cannot see component CSS: in src/lib/ui every font-size is
// a type token, a px value ≥ 12, a relative size ≥ 1 (never smaller than its
// context), or guarded as max(≥12px, …) — so a 0.86em suffix can never land
// at 10 px inside a 12 px cell (SPEC §1.6, §3.2).
{
	const SIZE_OK = [
		/^var\(--v-text-[a-z0-9]+\)$/,
		/^calc\(\s*var\(--v-text-[a-z0-9]+\)\s*\+\s*\d+(?:\.\d+)?px\s*\)$/,
		/^(?:inherit|initial|unset|revert|larger|medium)$/
	];
	const sizeOk = (raw) => {
		const v = raw.replace(/\s*!important\s*$/i, '').trim();
		if (SIZE_OK.some((re) => re.test(v))) return true;
		let m = /^(\d+(?:\.\d+)?)px$/.exec(v);
		if (m) return Number(m[1]) >= 12;
		m = /^(\d+(?:\.\d+)?)(em|rem)$/.exec(v);
		if (m) return Number(m[1]) >= 1;
		m = /^(\d+(?:\.\d+)?)%$/.exec(v);
		if (m) return Number(m[1]) >= 100;
		m = /^max\(\s*(\d+(?:\.\d+)?)px\s*,/.exec(v);
		if (m) return Number(m[1]) >= 12;
		return false;
	};
	const hits = [];
	for (const f of walkMaybe('lib/ui').filter((x) => /\.(svelte|css)$/.test(x))) {
		const file = rel(f);
		const v = views(file, readFileSync(f, 'utf8'));
		for (const text of [v.css, v.markup]) {
			if (!text) continue;
			for (const m of text.matchAll(/(?<![\w-])font-size\s*:\s*([^;}"'`\n]+)/gi)) {
				if (!sizeOk(m[1])) hits.push(`${file}:${lineOf(text, m.index)} font-size: ${m[1].trim()}`);
			}
			for (const m of text.matchAll(/\bstyle:font-size\s*=\s*(?:"([^"]*)"|'([^']*)')/g)) {
				const val = (m[1] ?? m[2] ?? '').trim();
				if (!/[{}]/.test(val) && !sizeOk(val)) hits.push(`${file}:${lineOf(text, m.index)} style:font-size ${val}`);
			}
		}
	}
	ok('type floor in src/lib/ui: every font-size is a token, ≥ 12 px, ≥ 1em or max(12px, …)', hits.length === 0, hits.slice(0, 8).join(' | ') || 'no component text can fall under 12 px');
}

// ── 2. HEX SWEEP ────────────────────────────────────────────────────────
//
// Enforced on every surface that is ON the token system. The not-yet-rebuilt
// ops/gods-eye panels are out of scope until their owning slice lands them
// on the primitives — extend HEX_SWEEP_TARGETS in that same change
// (coverage added, never removed).
const TOKEN_FILES = new Set(['tokens.ts', 'tokens.css']);
const HEX_SWEEP_TARGETS = [
	'lib/design',
	'lib/ui',
	'lib/primitives',
	'lib/shell',
	'lib/i18n',
	'lib/citizen',
	'lib/comms',
	'lib/ops/components/template',
	'routes/(deck)/+page.svelte',
	'routes/(deck)/design',
	'routes/(deck)/comms',
	'routes/(deck)/chat',
	'routes/(deck)/+layout.svelte',
	'routes/(public)/citizen',
	'routes/(public)/driver',
	'routes/(public)/+layout.svelte',
	'routes/+layout.svelte'
];

const HEX_RE = /#[0-9a-fA-F]{3,8}/g;
const hexViolations = [];
for (const target of HEX_SWEEP_TARGETS) {
	const p = path.join(SRC, target);
	let files = [];
	try {
		files = statSync(p).isDirectory() ? walk(p) : [p];
	} catch {
		hexViolations.push(`${target}: target missing (topology broken?)`);
		continue;
	}
	for (const f of files) {
		if (TOKEN_FILES.has(path.basename(f)) && path.dirname(f).endsWith('design')) continue;
		if (!/\.(svelte|ts|js|css)$/.test(f)) continue;
		const lines = readFileSync(f, 'utf8').split('\n');
		lines.forEach((line, i) => {
			for (const m of line.matchAll(HEX_RE)) {
				// Svelte block tags ("#each" → "#eac") are keywords, never colours:
				// a hex colour is never immediately followed by a letter.
				const after = line[m.index + m[0].length] ?? '';
				if (/[a-zA-Z]/.test(after)) continue;
				hexViolations.push(`${rel(f)}:${i + 1}: ${line.trim().slice(0, 90)}`);
			}
		});
	}
}
ok('hex sweep: no hex literal outside the token files', hexViolations.length === 0, hexViolations.length ? hexViolations.slice(0, 8).join(' | ') : `${HEX_SWEEP_TARGETS.length} targets clean`);

// ── 3. CONTRACTS: icons (X1), packs.ui, the formatter ────────────────────

{
	const { KIND_ICON, EVENT_KIND_ICON, ACTION_ICON, ACTOR_ICON, MODULE_ICON, INTENT_ICON, PROVENANCE_ICON, ICONS_16, ICONS_20 } = icons;
	const bad = [];
	const X1 = [
		[KIND_ICON, 'osint_event', 'geosearch'], [KIND_ICON, 'place', 'map-marker'],
		[EVENT_KIND_ICON, 'reported_crime', 'high-priority'], [EVENT_KIND_ICON, 'public_disorder', 'issue'],
		[EVENT_KIND_ICON, 'road_accident', 'warning-sign'], [EVENT_KIND_ICON, 'hazard', 'flash'],
		[EVENT_KIND_ICON, 'flooding', 'area-of-interest'], [EVENT_KIND_ICON, 'infra_failure', 'error'],
		[ACTION_ICON, 'promote', 'arrow-up'], [ACTION_ICON, 'decision_support', 'diagram-tree'], [ACTION_ICON, 'osint', 'globe']
	];
	for (const [map, k, v] of X1) if (map[k] !== v) bad.push(`${k}=${map[k]} (X1 ${v})`);
	const SPEC42 = {
		vehicle: 'drive-time', sighting: 'detection', camera: 'camera', junction: 'intersection', segment: 'flow-linear',
		recommendation: 'take-action', event: 'timeline-events', dispatch: 'send-to', unit: 'badge', anomaly: 'pulse', convoy: 'route'
	};
	for (const [k, v] of Object.entries(SPEC42)) if (KIND_ICON[k] !== v) bad.push(`KIND_ICON.${k}=${KIND_ICON[k]} (SPEC ${v})`);
	for (const [k, v] of Object.entries({ vehicle_pursuit: 'path-search', protected_movement: 'route', procession: 'walk', work_zone: 'build' })) {
		if (EVENT_KIND_ICON[k] !== v) bad.push(`EVENT_KIND_ICON.${k}=${EVENT_KIND_ICON[k]} (SPEC ${v})`);
	}
	for (const [k, v] of Object.entries({ officer: 'user', ai: 'predictive-analysis', rules: 'function', sensor: 'camera', system: 'cog' })) {
		if (ACTOR_ICON[k] !== v) bad.push(`ACTOR_ICON.${k}=${ACTOR_ICON[k]} (SPEC ${v})`);
	}
	for (const [k, v] of Object.entries({ emulated: 'lab-test', simulated: 'random', test: 'playbook', osint: 'globe' })) {
		if (PROVENANCE_ICON[k] !== v) bad.push(`PROVENANCE_ICON.${k}=${PROVENANCE_ICON[k]} (X2 ${v})`);
	}
	ok('icons: SPEC §4.2 maps and plan X1 / X2 entries', bad.length === 0, bad.join(' | ') || `${Object.keys(KIND_ICON).length} kinds, ${Object.keys(EVENT_KIND_ICON).length} event kinds`);

	let throws = null;
	let fall = [];
	try {
		fall = [icons.kindIcon('no-such-kind'), icons.kindIcon(null), icons.kindIcon(undefined), icons.kindIcon(42), icons.eventKindIcon('no-such-kind'), icons.eventKindIcon(null), icons.eventKindIcon(undefined), icons.kindIcon('__proto__'), icons.eventKindIcon('constructor')];
	} catch (e) {
		throws = String(e);
	}
	ok(
		"icons: kindIcon → 'dot' and eventKindIcon → 'timeline-events' for unknown values, never throwing",
		throws === null && fall.slice(0, 4).every((n) => n === 'dot') && fall.slice(4, 7).every((n) => n === 'timeline-events') && fall[7] === 'dot' && fall[8] === 'timeline-events',
		throws ?? fall.join(',')
	);

	const PERSON = ['mugshot', 'person', 'people', 'blocked-person', 'follower', 'following', 'id-number'];
	const present = PERSON.filter((n) => n in ICONS_16 || n in ICONS_20);
	ok('icons: no person glyph in the set (vehicles only)', present.length === 0, present.join(' ') || `${Object.keys(ICONS_16).length} glyphs, none a person`);

	const missing = [];
	for (const map of [KIND_ICON, EVENT_KIND_ICON, ACTOR_ICON, ACTION_ICON, MODULE_ICON, INTENT_ICON, PROVENANCE_ICON]) {
		for (const name of Object.values(map)) if (!Array.isArray(ICONS_16[name]) || !ICONS_16[name].length) missing.push(name);
	}
	missing.push(...['dot', 'timeline-events'].filter((n) => !ICONS_16[n]));
	ok('icons: every mapped glyph has 16 px path data', missing.length === 0, missing.join(' ') || 'all mapped glyphs drawable');

	const lic = path.join(SRC, 'lib/design/LICENSE-blueprint.txt');
	const licText = existsSync(lic) ? readFileSync(lic, 'utf8') : '';
	ok(
		'icons: LICENSE-blueprint.txt carries the notice and the Apache-2.0 text',
		licText.includes('Icon path data and colour values from Blueprint (@blueprintjs/icons 6.14.1, @blueprintjs/colors 5.1.16), Copyright Palantir Technologies, Inc., Apache-2.0. Modified: subset.') && licText.includes('Apache License') && licText.includes('END OF TERMS AND CONDITIONS'),
		existsSync(lic) ? `${licText.length} bytes` : 'missing'
	);

	const { UI_PACKS } = MOD.ui;
	const en = Object.keys(UI_PACKS.en);
	const gaps = [];
	for (const lang of ['hi', 'mr']) {
		const keys = Object.keys(UI_PACKS[lang]);
		for (const k of en) if (!keys.includes(k)) gaps.push(`${lang} lacks ${k}`);
		for (const k of keys) if (!en.includes(k)) gaps.push(`${lang} has extra ${k}`);
	}
	for (const lang of ['en', 'hi', 'mr']) {
		for (const [k, v] of Object.entries(UI_PACKS[lang])) {
			const s = typeof v === 'function' ? v('x') : v;
			if (typeof s !== 'string' || !s.trim()) gaps.push(`${lang}.${k} empty`);
			if (!k.startsWith('ui_')) gaps.push(`${lang}.${k} lacks the ui_ prefix`);
		}
	}
	ok('packs.ui: EN, HI and MR complete for every ui_ key', gaps.length === 0, gaps.slice(0, 6).join(' | ') || `${en.length} keys × 3 languages`);

	const f = MOD.fmt;
	const at = (h, m, s = 0, d = 23) => Date.UTC(2026, 9, d, h, m, s) - 5.5 * 3600_000; // an IST wall time as epoch ms
	const anchor = at(3, 18);
	const fx = [];
	const eq = (got, want, what) => got !== want && fx.push(`${what}: '${got}' ≠ '${want}'`);
	eq(f.fmtTime(at(23, 52, 4, 22)), '23:52', 'fmtTime IST');
	eq(f.fmtTime(at(23, 52, 4, 22), { seconds: true }), '23:52:04', 'fmtTime seconds');
	eq(f.fmtStamp(at(1, 38), anchor), '01:38', 'fmtStamp same day');
	eq(f.fmtStamp(at(23, 52, 0, 22), anchor), '22 Oct 23:52', 'fmtStamp other day');
	eq(f.fmtRange(at(1, 20), at(1, 42), anchor), '01:20–01:42', 'fmtRange same day');
	eq(f.fmtRange(at(23, 52, 0, 22), at(0, 4), anchor), '22 Oct 23:52–00:04', 'fmtRange across midnight');
	eq(f.fmtRange(at(22, 0, 0, 22), at(6, 0), anchor), '22 Oct 22:00–06:00', 'fmtRange overnight, under 12 h');
	eq(f.fmtRange(at(10, 0, 0, 22), at(9, 0), anchor), '22 Oct 10:00–23 Oct 09:00', 'fmtRange 12–24 h across midnight dates its end');
	eq(f.fmtRange(at(10, 0, 0, 21), at(9, 0), anchor), '21 Oct 10:00–23 Oct 09:00', 'fmtRange over a day dates its end');
	const fullMark = ['GJ', '01', 'XX', '1237'].join(''); // fictional, assembled so no full mark sits in the source
	eq(f.maskMark(fullMark), 'GJ01XX•••7', 'maskMark masks a full mark');
	eq(f.maskMark('GJ01XX•••7'), 'GJ01XX•••7', 'maskMark keeps a masked mark');
	eq(f.maskMark(['GJ', '01', '1237'].join(' ')), 'GJ 01 •••7', 'maskMark spaced mark');
	eq(String(f.isMaskedMark('GJ01XX•••7')) + String(f.isMaskedMark(fullMark)), 'truefalse', 'isMaskedMark');
	eq(f.colStamp([at(1, 20), at(2, 5)], anchor).join(','), '01:20,02:05', 'colStamp one day');
	eq(f.colStamp([at(1, 20), at(23, 52, 0, 22)], anchor).join(','), '23 Oct 01:20,22 Oct 23:52', 'colStamp mixed days → dated for every row');
	eq(f.fmtAgo(anchor - 6000_000, anchor), '1 h 40 min ago', 'fmtAgo');
	eq(f.fmtDuration(47), '47 s', 'fmtDuration');
	eq(f.fmtTime('not a time'), '—', 'fmtTime invalid');
	eq(f.fmtCoord(23.0218, 72.5855), '23.0218° N 72.5855° E', 'fmtCoord');
	eq(String(f.parseIstTime('9:5')), '09:05', 'parseIstTime loose');
	eq(String(f.parseIstTime('24:00')), 'null', 'parseIstTime invalid');
	eq(f.istTimeToMs('01:38', anchor), at(1, 38), 'istTimeToMs');
	eq(f.svgLabel([{ id: 'EM-CAM-03' }, { time: at(1, 38) }]).includes('var(--v-font-mono)'), true, 'svgLabel mono id');
	ok('formatter: IST times, one format per column, ranges at one precision, marks masked', fx.length === 0, fx.join(' | ') || '23 cases');

	const { flowStop, flowStyle, mapColor, FLOW_RAMP_FALLBACK, TOKENS } = MOD.tokens;
	const tf = [];
	if (flowStop(Number.NaN) !== 1 || flowStop(-1) !== 1) tf.push('flowStop of NaN / a negative index is not "free"');
	if ([0, 0.2, 0.21, 0.4, 0.41, 0.6, 0.61, 0.8, 0.81, 1].map(flowStop).join('') !== '1122334455') tf.push(`flowStop ${[0, 0.2, 0.21, 0.4, 0.41, 0.6, 0.61, 0.8, 0.81, 1].map(flowStop).join('')}`);
	const s3 = flowStyle(3);
	if (s3.color !== TOKENS.command['--v-flow-3'] || s3.width !== 4 || s3.casing !== TOKENS.command['--v-map-casing']) tf.push('flowStyle(3)');
	if (flowStyle(1).casing !== null || flowStyle(5).width !== 6) tf.push('flowStyle(1|5)');
	if (mapColor('alert') !== TOKENS.command['--v-map-alert'] || mapColor('nope') !== TOKENS.command['--v-map-marker']) tf.push('mapColor');
	if (!Array.isArray(FLOW_RAMP_FALLBACK) || FLOW_RAMP_FALLBACK.length !== 5 || FLOW_RAMP_FALLBACK.map((s) => s.width).join() !== '3,3.5,4,5,6') tf.push('FLOW_RAMP_FALLBACK');
	// the LEGACY flowColor keeps its pre-redesign comparisons exactly: NaN falls through to severe
	const { flowColor } = MOD.tokens;
	const legacy = [
		[Number.NaN, '--v-band-red'], [0, '--v-band-green'], [0.2, '--v-band-green'], [0.3, '--v-flow-light'],
		[0.5, '--v-band-amber'], [0.7, '--v-act'], [0.9, '--v-band-red'], [-1, '--v-band-green']
	];
	for (const [c, key] of legacy) if (flowColor(c) !== TOKENS.command[key]) tf.push(`flowColor(${c}) ≠ ${key} (legacy)`);
	ok('tokens.ts: flowStop thresholds 0.2/0.4/0.6/0.8, flowStyle, mapColor, the bright neutral fallback ramp; legacy flowColor unchanged', tf.length === 0, tf.join(' | ') || 'as specified');
}

// ── 4–5. STYLE AND GLYPH LINTS over the targets union ────────────────────

ok('targets: tests/style-lint.targets/*.json parse', TARGETS.errors.length === 0 && TARGETS.sources.length > 0, TARGETS.errors.join(' | ') || TARGETS.sources.join(', '));
{
	const dead = [...TARGETS.style, ...TARGETS.glyph].filter((t) => !ALL_FILES.some((f) => globRe(t.glob).test(f)));
	const deadCopy = TARGETS.copy.filter((t) => !existsSync(path.join(DECK, t.glob)));
	ok('targets: every glob matches a file', dead.length + deadCopy.length === 0, [...dead, ...deadCopy].map((t) => `${t.from}: ${t.glob}`).join(' | ') || `${TARGETS.style.length} style, ${TARGETS.glyph.length} glyph, ${TARGETS.copy.length} copy`);
}
{
	const styleFiles = ALL_FILES.filter((f) => matchAny(f, TARGETS.style));
	const glyphFiles = ALL_FILES.filter((f) => matchAny(f, TARGETS.glyph));
	const styleHits = lintFiles(styleFiles, ['style']);
	const glyphHits = lintFiles(glyphFiles, ['glyph']);
	ok('style lint: tracking 0, no uppercase, no backdrop-filter, fonts through tokens, mono only in ui/format, active states via .is-pressed/.is-selected', styleHits.length === 0, styleHits.slice(0, 12).join(' | ') || `${styleFiles.length} files clean`);
	ok('glyph lint: no kind icon name passed as a literal', glyphHits.length === 0, glyphHits.slice(0, 12).join(' | ') || `${glyphFiles.length} files clean`);
}

// ── 6. BOUNDARIES (the R4 import graph, textual so .svelte is covered) ───

const IMPORT_RE = /(?:from\s+['"]([^'"]+)['"]|import\s+['"]([^'"]+)['"]|import\(\s*['"]([^'"]+)['"]\s*\))/g;
function importsOf(file) {
	const text = stripJsComments(readFileSync(file, 'utf8'));
	const list = [];
	for (const m of text.matchAll(IMPORT_RE)) list.push(m[1] ?? m[2] ?? m[3]);
	return list;
}

/** A specifier as a deck-relative path when it points into src/lib ($lib or relative). */
function resolveSpec(fromFile, spec) {
	if (spec.startsWith('$lib/')) return `src/lib/${spec.slice(5)}`;
	if (spec.startsWith('.')) return rel(path.resolve(path.dirname(fromFile), spec));
	return null;
}

const designFiles = [
	...walkMaybe('lib/design'),
	...walkMaybe('lib/primitives'),
	...walkMaybe('lib/shell'),
	path.join(SRC, 'routes/(deck)/+layout.svelte')
].filter((f) => /\.(ts|js|svelte)$/.test(f));
const rule1 = [];
for (const f of designFiles) {
	for (const imp of importsOf(f)) {
		if (/^\$lib\/(ops|gods-eye)(\/|$)/.test(imp)) rule1.push(`${rel(f)} → ${imp}`);
	}
}
ok('boundary: design/shell/primitives never import $lib/ops|$lib/gods-eye', rule1.length === 0, rule1.slice(0, 5).join(' | '));

const uiFiles = walkMaybe('lib/ui').filter((f) => /\.(ts|js|svelte)$/.test(f));
const ruleUi = [];
for (const f of uiFiles) {
	for (const imp of importsOf(f)) {
		const target = resolveSpec(f, imp);
		if (target && /^src\/lib\/(ops|gods-eye|workspace)(\/|$)/.test(target)) ruleUi.push(`${rel(f)} → ${imp}`);
		if (imp === 'svelte/store' || (target && /^src\/lib\/(shell|stores)(\/|$)/.test(target)) || /^\$stores(\/|$)/.test(imp)) ruleUi.push(`${rel(f)} → ${imp} (store)`);
		if (target && !target.startsWith('src/lib/ui/') && (existsSync(path.join(DECK, `${target}.ts`)) || existsSync(path.join(DECK, `${target}.js`))) && /\.svelte$/.test(target)) {
			ruleUi.push(`${rel(f)} → ${imp} (a .svelte.ts state module)`);
		}
	}
}
ok('boundary: src/lib/ui imports nothing from $lib/ops, $lib/gods-eye or $lib/workspace, and no store', uiFiles.length > 0 && ruleUi.length === 0, ruleUi.slice(0, 5).join(' | ') || `${uiFiles.length} files`);

const publicFiles = [
	...walkMaybe('lib/citizen'),
	...walkMaybe('lib/comms'),
	...walkMaybe('routes/(public)'),
	...walkMaybe('routes/(deck)/chat'),
	...walkMaybe('routes/(deck)/comms')
].filter((f) => /\.(ts|js|svelte)$/.test(f));
const rule2 = [];
for (const f of publicFiles) {
	for (const imp of importsOf(f)) {
		if (/^(\$stores|\$lib\/stores)(\/|$)/.test(imp) || imp === '$lib/api/data-service') rule2.push(`${rel(f)} → ${imp}`);
	}
}
ok('boundary: public/comms never import legacy stores or data-service', rule2.length === 0, rule2.slice(0, 5).join(' | '));

const rule3 = [];
for (const f of walk(SRC)) {
	if (!/\.(ts|js|svelte)$/.test(f)) continue;
	for (const imp of importsOf(f)) {
		if ((imp.includes('design/tokens.css') || imp.includes('design/fonts.css')) && rel(f) !== 'src/routes/+layout.svelte') rule3.push(`${rel(f)} → ${imp}`);
	}
}
ok('boundary: tokens.css and fonts.css imported only by the root layout', rule3.length === 0, rule3.join(' | '));

// ── result ──────────────────────────────────────────────────────────────

if (failures > 0) {
	console.error(`design-tokens: ${failures} FAILURE(S)`);
	process.exit(1);
}
console.log('ok   design-tokens — parity, spec values, contrast, floors, hex sweep, contracts, style and glyph lints, boundaries');
process.exit(0);
